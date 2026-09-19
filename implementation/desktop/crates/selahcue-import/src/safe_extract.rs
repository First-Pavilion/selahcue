//! Safe on-disk extraction of a ZIP-family archive (PRD FR-138, ClickUp 86ak0qmzv) — the
//! write-capable sibling of [`crate::zip`]'s read-only, never-touches-disk reader.
//!
//! # Why this is a separate module rather than a change to how `zip::read_entry`'s callers use it
//!
//! `zip.rs`'s own module doc states the load-bearing reason [`crate::zip`]'s `EntryMeta` used to
//! carry no entry type or mode bits: "nothing in this reader can distinguish or act on a symlink
//! entry, which is the point" — safe *because* that reader never writes a byte to disk, so a
//! symlink entry is just an entry whose contents happen to be a string. Writing extracted files to
//! disk is a different threat model entirely: an entry NAME can escape a destination root
//! (zip-slip), and an entry whose CONTENT the archive controls can literally BE a symlink pointing
//! anywhere on the filesystem. Both need answering before the first byte is ever written, which is
//! what this module does — on top of, not instead of, every bomb/ratio/size control `zip.rs`
//! already enforces.
//!
//! # What this module does not do
//!
//! It does not touch a filesystem. Per `implementation/desktop/CLAUDE.md` and this crate's own
//! `lib.rs` doc, no filesystem primitive is reachable from any code in this crate — that is a
//! structural property, not merely a convention. [`safe_extract_zip`] **validates** every entry
//! and returns fully-read, cap-enforced bytes under a **validated relative path** the shell may
//! safely join to its own confinement root; the shell (which already owns exactly this
//! stage-then-atomic-commit pattern for imported media — see `selahcue-operator::media_store`)
//! does the actual `canonicalize` + `create_new` write.
//!
//! # What "safe" means for a name here, and why it differs from `pkgpath`
//!
//! [`crate::pkgpath::resolve`] legitimately RESOLVES a `..` that climbs within the package
//! namespace, because its output is only ever a lookup key into the archive's own entry set — it
//! never touches a real path. A destination-root confinement check cannot make the same
//! allowance: a `..` that legitimately resolves to `ppt/media/x.png` inside a package can, against
//! a real filesystem root, resolve to a location outside it, depending on how many segments
//! precede it. So [`safe_relative_path`] refuses **any** `..` component outright rather than
//! resolving it — the same choice `selahcue-operator::media_store::is_app_owned` already makes for
//! the analogous filesystem-confinement question.
//!
//! # Reuse, not reimplementation, of the bomb/ratio controls
//!
//! [`safe_extract_zip`] opens the archive with [`ZipArchive::open`] and reads each admitted entry
//! with [`Archive::read_entry`] — the very same calls the OOXML path makes. The entry-count cap,
//! the per-entry and whole-archive produced-byte caps and the compression-ratio guard are
//! therefore identical and already covered by `tests/test_zip.rs`'s battery; this module's own
//! tests cover only what is new here: name confinement and symlink refusal.

use crate::error::{ImportError, ZipError};
use crate::limits::{MAX_TOTAL_EXTRACTED_BYTES, MAX_ZIP_NAME_LEN};
use crate::source::ByteSource;
use crate::zip::{Archive, ZipArchive};

/// One archive entry that passed every safety check: safe to join to any destination root and
/// write, and already read in full with every bomb/ratio/size cap enforced.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtractedFile {
    /// A relative, forward-slash path with no `..` component, no leading `/`, no drive letter, no
    /// NUL and no backslash — validated by [`safe_relative_path`]. Never resolved against a real
    /// filesystem by this crate; the shell joins it to its own root.
    pub relative_path: String,
    /// The entry's bytes, already inflated or copied and cap-enforced by
    /// [`Archive::read_entry`].
    pub bytes: Vec<u8>,
}

/// One entry that was refused, and why — for the shell's import report. Never fatal to the whole
/// extraction on its own: an archive is a bag of entries, and one hostile or malformed member
/// costs only itself.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RefusedEntry {
    /// The archive's own name for the entry, truncated to [`MAX_ZIP_NAME_LEN`] if longer. Purely a
    /// display quote for a report line — never used as, or derived from, a path.
    pub name: String,
    pub reason: RefusalReason,
}

/// Why one entry was refused.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum RefusalReason {
    /// The name cannot be confined to any destination root: empty, absolute, carrying a `..`
    /// component anywhere in it, a NUL, a backslash, a colon (a Windows drive letter or stream
    /// marker), or over the name-length cap.
    UnsafeName,
    /// A later entry sharing an earlier entry's case-folded name; the earlier one already won.
    Duplicate,
    /// The central directory marks this entry as a Unix symlink. Its content could point the
    /// write anywhere in a way this reader — which never resolves link targets — cannot audit, so
    /// it is refused rather than risked.
    Symlink,
    /// The entry is password-protected and cannot be inspected.
    Encrypted,
    /// The entry's compression method is neither stored nor deflate.
    UnsupportedMethod,
    /// The entry's actual produced size passed the per-entry cap.
    EntryTooLarge,
    /// The entry inflated at a ratio past the guard.
    RatioExceeded,
    /// This archive's whole-extraction work budget is already spent; further entries are dropped
    /// rather than read. A stored member cannot expand, so reaching this means an enormous
    /// archive rather than a hostile one.
    ExtractionBudgetExhausted,
    /// The entry's local header disagrees with the central directory, or its data is corrupt or
    /// truncated.
    Malformed,
}

/// The outcome of one safe-extraction pass: what may be written, and what was refused.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SafeExtractResult {
    pub files: Vec<ExtractedFile>,
    pub refused: Vec<RefusedEntry>,
}

/// Validate and read every safely-extractable entry in a ZIP-family archive.
///
/// `cancel` is polled between entries and, via `read_entry`, inside the inflate loop at chunk
/// granularity — so there is no uninterruptible multi-gigabyte loop for a cancel or a timeout to
/// fail to interrupt, exactly as for [`crate::read_pptx`].
///
/// Returns `Err` only when NOTHING further in the archive can be trusted or produced: not a
/// readable archive at all, a ZIP64 archive, too many entries, the whole-archive bomb budget
/// breached, a cancellation, or an underlying read failure. Every other per-entry problem is
/// reported in [`SafeExtractResult::refused`] and extraction continues.
pub fn safe_extract_zip(
    src: &mut dyn ByteSource,
    cancel: &dyn Fn() -> bool,
) -> Result<SafeExtractResult, ImportError> {
    let mut archive = ZipArchive::open(src)?;
    let mut result = SafeExtractResult::default();
    let count = archive.entries().len();
    for idx in 0..count {
        if cancel() {
            return Err(ImportError::Cancelled);
        }
        let (name, duplicate, bad_name, is_symlink) = {
            let e = archive
                .entries()
                .get(idx)
                .ok_or(ImportError::NotAnArchive)?;
            (e.name.clone(), e.duplicate, e.bad_name, e.is_symlink())
        };
        if bad_name {
            result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::UnsafeName,
            });
            continue;
        }
        if duplicate {
            result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::Duplicate,
            });
            continue;
        }
        let Some(relative_path) = safe_relative_path(&name) else {
            result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::UnsafeName,
            });
            continue;
        };
        if is_symlink {
            result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::Symlink,
            });
            continue;
        }
        match archive.read_entry(idx, MAX_TOTAL_EXTRACTED_BYTES, cancel) {
            Ok(bytes) => result.files.push(ExtractedFile {
                relative_path,
                bytes,
            }),
            // ArchiveTooLarge, Cancelled and Source escalate — past them nothing further in the
            // file can be trusted to be proportionate or even readable. Every other reason drops
            // just this entry and continues. The mapping mirrors `pptx.rs`'s own handling of the
            // same `ZipError` exactly, entry for entry, so the two archive-reading paths agree
            // about what each variant means.
            Err(ZipError::ArchiveTooLarge) => {
                return Err(ImportError::ArchiveTooLarge {
                    limit: crate::limits::MAX_TOTAL_INFLATED_BYTES,
                })
            }
            Err(ZipError::Cancelled) => return Err(ImportError::Cancelled),
            Err(ZipError::Source(e)) => return Err(ImportError::Source(e)),
            Err(ZipError::EntryTooLarge) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::EntryTooLarge,
            }),
            Err(ZipError::RatioExceeded) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::RatioExceeded,
            }),
            Err(ZipError::ExtractionBudgetExhausted) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::ExtractionBudgetExhausted,
            }),
            Err(ZipError::UnsupportedMethod) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::UnsupportedMethod,
            }),
            Err(ZipError::Encrypted) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::Encrypted,
            }),
            Err(ZipError::Malformed) => result.refused.push(RefusedEntry {
                name,
                reason: RefusalReason::Malformed,
            }),
        }
    }
    Ok(result)
}

/// Validate one archive entry name as safe to join to ANY destination root, refusing rather than
/// resolving anything that could escape it. See the module doc for why this is deliberately
/// stricter than [`crate::pkgpath::resolve`].
///
/// Returns a normalised, forward-slash, relative path with no leading `/`, no `..` segment
/// anywhere, no drive letter or colon, no NUL and no backslash — or `None` if the name cannot be
/// made one safely.
fn safe_relative_path(name: &str) -> Option<String> {
    if name.is_empty()
        || name.len() > MAX_ZIP_NAME_LEN
        || name.contains('\0')
        || name.contains('\\')
        || name.contains(':')
        // A leading slash is absolute and must be refused outright, never silently stripped down
        // to a relative name — `/etc/passwd` is not the same request as `etc/passwd`.
        || name.starts_with('/')
        // A trailing slash is a ZIP directory-entry marker, not a file. Without this check a
        // directory entry named `media/` would filter down to the segment list `["media"]` —
        // indistinguishable from a real file named `media` — and be handed back as one.
        || name.ends_with('/')
    {
        return None;
    }
    let mut segments: Vec<&str> = Vec::new();
    for segment in name.split('/') {
        match segment {
            // Doubled separators, a trailing slash (a directory entry), or a `.` segment: noise,
            // not structure.
            "" | "." => continue,
            // Refuse, never resolve — the module doc explains why this differs from `pkgpath`.
            ".." => return None,
            s => segments.push(s),
        }
    }
    if segments.is_empty() {
        // Either a directory entry (a trailing-slash-only name) or a name that was entirely
        // separators/dots. Neither names a file this function may hand back.
        return None;
    }
    let joined = segments.join("/");
    if joined.len() > MAX_ZIP_NAME_LEN {
        return None;
    }
    Some(joined)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_legitimate_relative_path_is_kept_unchanged() {
        assert_eq!(
            safe_relative_path("media/image1.png").as_deref(),
            Some("media/image1.png")
        );
        assert_eq!(safe_relative_path("top.txt").as_deref(), Some("top.txt"));
    }

    #[test]
    fn redundant_separators_and_dot_segments_are_cleaned_up() {
        assert_eq!(
            safe_relative_path(".//media//./x.png").as_deref(),
            Some("media/x.png")
        );
    }

    #[test]
    fn nothing_can_climb_above_the_destination_root() {
        for name in [
            "../../evil",
            "../etc/passwd",
            "a/../../b",
            "..",
            "media/../../../escape",
        ] {
            assert_eq!(safe_relative_path(name), None, "{name} must be refused");
        }
    }

    #[test]
    fn an_absolute_or_windows_shaped_name_is_refused() {
        for name in [
            "/etc/passwd",
            "C:\\Windows\\evil",
            "C:evil",
            "\\\\server\\share\\evil",
            "media\\x.png",
        ] {
            assert_eq!(safe_relative_path(name), None, "{name} must be refused");
        }
    }

    #[test]
    fn a_nul_bearing_or_over_long_or_empty_name_is_refused() {
        assert_eq!(safe_relative_path("media/x\0.png"), None);
        assert_eq!(safe_relative_path(""), None);
        assert_eq!(safe_relative_path(&"a".repeat(MAX_ZIP_NAME_LEN + 1)), None);
    }

    #[test]
    fn a_directory_entry_is_refused_not_written_as_a_file() {
        assert_eq!(safe_relative_path("media/"), None);
        assert_eq!(safe_relative_path("/"), None);
    }
}
