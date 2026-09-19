//! Safe, hardened validation of a user-picked file (PRD FR-138, ClickUp 86ak0qmzv) — the choke
//! point every file-import Tauri command routes through before a path becomes a `MediaRef` or a
//! library asset.
//!
//! # The gap this closes
//!
//! [`pick_image`](crate::main) and [`deck_import_image`](crate::main) hand the native OS
//! picker's chosen path straight to the frontend / `DeckWorkspace::import_media` with **zero**
//! validation — not even that the path still resolves to a real file. The only hardening on this
//! whole chain is `selahcue_engine::media`'s FR-173 decode caps, which run on the BYTES, at
//! RENDER time, long after the path has already been stored as a `MediaRef` or a
//! `MediaLibrary` asset. A file whose extension lies about its content, or whose path has since
//! stopped resolving to what the operator thought they picked, is accepted at pick time and only
//! ever discovered — if at all — the next time a slide referencing it is composed.
//!
//! [`validate_picked_image`] closes that gap at the one place every image-import command already
//! calls before doing anything else with the path: it resolves the path to what it REALLY names
//! (following, never merely trusting, any symlink), confirms that is a regular file within an
//! admission size, and identifies its type by **magic bytes, never an extension** — the same rule
//! FR-173's own [`selahcue_present::sniff`] already applies at render time, reused here so the two
//! checks can never disagree about what a file "is".
//!
//! # What this is not
//!
//! There is no confinement root for this path: the user picked the file themselves, from
//! anywhere on their own system, via a native OS dialog they explicitly drove — unlike an archive
//! entry (see `selahcue_import::safe_extract`, which pairs with the same ticket for the
//! FR-139/plan-bundle case), nothing here is attacker-supplied *content deciding where a write
//! lands*. So this module never restricts *where* a legitimate pick may come from; it only makes
//! sure the path resolves to a real, size-bounded, correctly-typed file before anything downstream
//! trusts it.

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use selahcue_present::{sniff, ImageFormat};

/// Largest file this seam admits, enforced BEFORE the full read. Mirrors
/// `selahcue_engine::media::DecodeLimits::default().max_encoded_bytes` — the render path's own
/// cap — so a file this seam admits is never one FR-173's decode would go on to refuse anyway,
/// and a file this seam refuses was never going to render regardless.
const MAX_PICKED_FILE_BYTES: u64 = 64 * 1024 * 1024;

/// Why a picked file was refused.
///
/// Hand-rolled `Display` + [`std::error::Error`] — the house pattern (`MediaStoreError` in
/// `media_store.rs`, `ParseError` in `selahcue_core::scripture`) — and deliberately carries no
/// path, matching `MediaStoreError`'s own redaction rule (ADR-0011/FR-082): a rejection reason may
/// say what was wrong, never point at where.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SafeImportError {
    /// The path (or, if it is a symlink, its target) does not resolve to anything.
    NotFound,
    /// The filesystem refused the operation for some other reason (permissions, and similar).
    Io(std::io::ErrorKind),
    /// The resolved path is not a regular file — a directory, or (once resolved) a device, FIFO
    /// or socket. A symlink is followed and judged by what it resolves to; nothing is accepted
    /// merely for existing at the picked path.
    NotAFile,
    /// The file is larger than this seam admits.
    TooLarge,
    /// The bytes' own magic-byte signature is not one of the allowlisted formats — regardless of
    /// what the file's extension, or the OS picker's own filter, claimed.
    UnsupportedType,
}

impl std::fmt::Display for SafeImportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            SafeImportError::NotFound => "that file couldn't be found",
            SafeImportError::Io(std::io::ErrorKind::PermissionDenied) => {
                "SelahCue isn't allowed to read that file"
            }
            SafeImportError::Io(_) => "that file couldn't be read",
            SafeImportError::NotAFile => "that isn't a file SelahCue can import",
            SafeImportError::TooLarge => "that file is too large to import",
            SafeImportError::UnsupportedType => "that file isn't a supported image (PNG or JPEG)",
        };
        f.write_str(s)
    }
}

impl std::error::Error for SafeImportError {}

/// Validate a user-picked image path before anything downstream trusts it.
///
/// Resolves `picked` to its real, canonical path (following any symlink to what it actually
/// names — never trusting a link's own metadata), confirms that is a regular file within the
/// admission size, and identifies its content by magic bytes — rejected before any decode is
/// attempted if the type is not allowlisted, regardless of the file's extension.
///
/// Returns the **canonical** path on success — symlink-resolved, `.`/`..`-free — for the caller
/// to store instead of the OS dialog's raw string, so anything downstream (a `MediaRef`, the
/// media library, the render-time decode) operates on a path that has already been proven to
/// resolve to real, admitted bytes.
pub fn validate_picked_image(picked: &Path) -> Result<PathBuf, SafeImportError> {
    validate_picked_image_within(picked, MAX_PICKED_FILE_BYTES)
}

/// [`validate_picked_image`]'s actual logic, parametrised on the size cap so the cap's own
/// enforcement is testable without a multi-megabyte fixture on disk.
fn validate_picked_image_within(picked: &Path, max_bytes: u64) -> Result<PathBuf, SafeImportError> {
    let canonical = fs::canonicalize(picked).map_err(|e| match e.kind() {
        std::io::ErrorKind::NotFound => SafeImportError::NotFound,
        kind => SafeImportError::Io(kind),
    })?;
    // ONE handle for metadata AND content, not `fs::metadata` + `fs::read` as two separate
    // path lookups: those re-touch the same path independently, leaving a TOCTOU window for a
    // local swap of the target between the two. A single open `File` decides both from the same
    // underlying inode.
    let mut file = match fs::File::open(&canonical) {
        Ok(f) => f,
        Err(e) => {
            // Unlike Unix, `File::open` on Windows refuses a directory outright (no handle to
            // read metadata from at all) instead of succeeding and letting `is_file()` below
            // catch it. Fall back to a plain metadata lookup ONLY to classify this failure —
            // the TOCTOU this seam closes is between the size/type decision and the content
            // read, both of which still come from one handle on every path that gets this far.
            if fs::metadata(&canonical).is_ok_and(|m| !m.is_file()) {
                return Err(SafeImportError::NotAFile);
            }
            return Err(match e.kind() {
                std::io::ErrorKind::NotFound => SafeImportError::NotFound,
                kind => SafeImportError::Io(kind),
            });
        }
    };
    let metadata = file.metadata().map_err(|e| SafeImportError::Io(e.kind()))?;
    if !metadata.is_file() {
        return Err(SafeImportError::NotAFile);
    }
    // CHEAP EARLY ABORT on the metadata's own claim, before a single byte is read — not the only
    // check, because metadata can be stale by the time the read below happens.
    if metadata.len() > max_bytes {
        return Err(SafeImportError::TooLarge);
    }
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .map_err(|e| SafeImportError::Io(e.kind()))?;
    // THE CAP THAT ACTUALLY HOLDS: re-checked on what was actually read, in case the file grew
    // between the metadata check and this read.
    if bytes.len() as u64 > max_bytes {
        return Err(SafeImportError::TooLarge);
    }
    let _format: ImageFormat = sniff(&bytes).ok_or(SafeImportError::UnsupportedType)?;
    Ok(canonical)
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;
    use std::io::Write;
    use std::sync::atomic::{AtomicU64, Ordering};

    /// A fresh temp directory, unique per test and per run, so the suite is safe under `cargo
    /// test`'s thread parallelism.
    fn temp_dir(tag: &str) -> PathBuf {
        static N: AtomicU64 = AtomicU64::new(0);
        let dir = std::env::temp_dir().join(format!(
            "selahcue-safe-import-{}-{tag}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    const PNG_SIGNATURE: [u8; 8] = [0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];

    fn write(dir: &Path, name: &str, bytes: &[u8]) -> PathBuf {
        let path = dir.join(name);
        let mut f = fs::File::create(&path).unwrap();
        f.write_all(bytes).unwrap();
        path
    }

    #[test]
    fn a_nonexistent_path_is_refused_as_not_found() {
        let dir = temp_dir("missing");
        assert_eq!(
            validate_picked_image(&dir.join("nope.png")),
            Err(SafeImportError::NotFound)
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_directory_is_refused_not_read_as_a_file() {
        let dir = temp_dir("dir");
        let sub = dir.join("looks-like-an-image.png");
        fs::create_dir_all(&sub).unwrap();
        assert_eq!(validate_picked_image(&sub), Err(SafeImportError::NotAFile));
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_legitimate_png_is_accepted_and_its_canonical_path_returned() {
        let dir = temp_dir("legit");
        let mut bytes = PNG_SIGNATURE.to_vec();
        bytes.extend_from_slice(b"rest-of-a-png-does-not-matter-to-sniff");
        let path = write(&dir, "photo.png", &bytes);

        let canonical = validate_picked_image(&path).expect("a real PNG must be accepted");
        assert_eq!(canonical, fs::canonicalize(&path).unwrap());
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_png_extension_with_non_png_content_is_refused_by_content_not_by_name() {
        // AC3, exactly: an allowlisted EXTENSION whose header is not is rejected before any
        // decode is attempted. A `.png` that is actually an ELF binary is the canonical case.
        let dir = temp_dir("lying-ext");
        let elf = [0x7f, b'E', b'L', b'F', 0, 0, 0, 0];
        let path = write(&dir, "totally-a-photo.png", &elf);

        assert_eq!(
            validate_picked_image(&path),
            Err(SafeImportError::UnsupportedType)
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn plain_text_masquerading_as_an_image_is_refused() {
        let dir = temp_dir("text");
        let path = write(
            &dir,
            "not-an-image.png",
            b"just some text, not an image at all",
        );
        assert_eq!(
            validate_picked_image(&path),
            Err(SafeImportError::UnsupportedType)
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_file_over_the_size_cap_is_refused_before_being_fully_read() {
        // A tiny cap, not a 64 MiB fixture: this proves the CAP's own enforcement, which
        // `validate_picked_image`'s public constant only parametrises.
        let dir = temp_dir("oversize");
        let mut bytes = PNG_SIGNATURE.to_vec();
        bytes.extend(std::iter::repeat_n(0u8, 100));
        let path = write(&dir, "big.png", &bytes);

        assert_eq!(
            validate_picked_image_within(&path, 16),
            Err(SafeImportError::TooLarge)
        );
        // Positive control: the SAME file, under a cap it fits, is accepted — proving the refusal
        // above is the size cap firing and not some other defect swallowing every file.
        assert!(validate_picked_image_within(&path, bytes.len() as u64).is_ok());
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_file_exactly_at_the_cap_is_accepted_one_byte_over_is_not() {
        let dir = temp_dir("boundary");
        let mut at_cap = PNG_SIGNATURE.to_vec();
        at_cap.resize(20, 0);
        let mut over_cap = at_cap.clone();
        over_cap.push(0);
        let at_path = write(&dir, "at.png", &at_cap);
        let over_path = write(&dir, "over.png", &over_cap);

        assert!(validate_picked_image_within(&at_path, at_cap.len() as u64).is_ok());
        assert_eq!(
            validate_picked_image_within(&over_path, at_cap.len() as u64),
            Err(SafeImportError::TooLarge)
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[cfg(unix)]
    #[test]
    fn a_symlink_is_resolved_to_its_real_target_and_judged_by_that_targets_content() {
        let dir = temp_dir("symlink");
        let mut bytes = PNG_SIGNATURE.to_vec();
        bytes.extend_from_slice(b"target-bytes");
        let real = write(&dir, "real.png", &bytes);
        let link = dir.join("link.png");
        std::os::unix::fs::symlink(&real, &link).unwrap();

        let canonical =
            validate_picked_image(&link).expect("a symlink to a real PNG must be accepted");
        assert_eq!(
            canonical,
            fs::canonicalize(&real).unwrap(),
            "the returned path is the RESOLVED target, not the symlink itself"
        );
        fs::remove_dir_all(&dir).ok();
    }

    #[cfg(unix)]
    #[test]
    fn a_symlink_to_a_directory_is_refused_not_treated_as_a_file() {
        let dir = temp_dir("symlink-dir");
        let real_dir = dir.join("a-real-directory");
        fs::create_dir_all(&real_dir).unwrap();
        let link = dir.join("looks-like-a-file.png");
        std::os::unix::fs::symlink(&real_dir, &link).unwrap();

        assert_eq!(validate_picked_image(&link), Err(SafeImportError::NotAFile));
        fs::remove_dir_all(&dir).ok();
    }

    #[cfg(unix)]
    #[test]
    fn a_broken_symlink_is_refused_as_not_found() {
        let dir = temp_dir("symlink-broken");
        let link = dir.join("dangling.png");
        std::os::unix::fs::symlink(dir.join("never-existed.png"), &link).unwrap();

        assert_eq!(validate_picked_image(&link), Err(SafeImportError::NotFound));
        fs::remove_dir_all(&dir).ok();
    }
}
