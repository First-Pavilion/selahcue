//! Package-namespace path normalisation — the part everyone gets wrong.
//!
//! Relationship targets in OOXML are package-relative and **legitimately contain `..`**:
//! `ppt/slides/_rels/slide1.xml.rels` carries `Target="../media/image1.png"`, which resolves to
//! `ppt/media/image1.png`. So the two obvious answers are both wrong. "Reject any target
//! containing `..`" breaks every real `.pptx`. "Join it to a directory" is zip-slip.
//!
//! The rule that satisfies both:
//!
//! > Normalisation happens entirely **within the package namespace**, and the result is only ever
//! > used as a lookup key into the archive's own entry set. It never touches, constructs, or
//! > resembles a filesystem path.
//!
//! Because the output is only ever a key, an attacker who wins the normalisation still only names
//! an entry that is already inside the archive. Zip-slip is structurally absent here rather than
//! defended against.
//!
//! This module parses untrusted names, so it denies `indexing_slicing` and
//! `arithmetic_side_effects` along with the ZIP reader.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

use crate::limits::MAX_ZIP_NAME_LEN;

/// Resolve a relationship `target` against the part it was declared in.
///
/// `source_part` is the part holding the `.rels` file's OWNER — e.g. for
/// `ppt/slides/_rels/slide1.xml.rels` the owner is `ppt/slides/slide1.xml`, so the base directory
/// is `ppt/slides`.
///
/// Returns `None` for anything that cannot be a key into this package: an absolute target, a
/// backslash (a Windows path separator has no meaning in a package name and its presence is a
/// signal, not a typo), a NUL, an over-long name, or a `..` that would climb above the package
/// root.
pub(crate) fn resolve(source_part: &str, target: &str) -> Option<String> {
    if target.is_empty()
        || target.len() > MAX_ZIP_NAME_LEN
        || target.contains('\0')
        || target.contains('\\')
    {
        return None;
    }
    // A leading '/' is absolute-in-package. OOXML does use that form, and it means "from the
    // package root" — never from a filesystem root, because there is no filesystem here.
    let (base, rest) = if let Some(stripped) = target.strip_prefix('/') {
        (Vec::new(), stripped)
    } else {
        (directory_of(source_part), target)
    };

    let mut stack = base;
    for segment in rest.split('/') {
        match segment {
            // Empty segments come from a doubled separator or a trailing slash; both are noise.
            "" | "." => continue,
            ".." => {
                // Refuse to climb above the package root rather than silently clamping: a target
                // that tries to is not naming something in this package.
                stack.pop()?;
            }
            s => {
                if s.len() > MAX_ZIP_NAME_LEN {
                    return None;
                }
                stack.push(s);
            }
        }
    }
    if stack.is_empty() {
        return None;
    }
    let joined = stack.join("/");
    if joined.len() > MAX_ZIP_NAME_LEN {
        return None;
    }
    Some(joined)
}

/// The directory segments of a part name (`ppt/slides/slide1.xml` → `["ppt", "slides"]`).
fn directory_of(part: &str) -> Vec<&str> {
    let mut segments: Vec<&str> = part.split('/').filter(|s| !s.is_empty()).collect();
    segments.pop(); // drop the file name itself
    segments
}

/// The `.rels` part that describes `part`: `ppt/slides/slide1.xml` →
/// `ppt/slides/_rels/slide1.xml.rels`.
pub(crate) fn rels_for(part: &str) -> Option<String> {
    let (dir, file) = match part.rfind('/') {
        Some(i) => (part.get(..i)?, part.get(i.checked_add(1)?..)?),
        None => ("", part),
    };
    if file.is_empty() {
        return None;
    }
    Some(if dir.is_empty() {
        format!("_rels/{file}.rels")
    } else {
        format!("{dir}/_rels/{file}.rels")
    })
}

/// Case-fold a package name for comparison only. Archive names are compared case-insensitively
/// because APFS and NTFS are, but the ORIGINAL name is what is looked up — folding is never
/// written anywhere.
pub(crate) fn fold(name: &str) -> String {
    name.to_ascii_lowercase()
}

/// White-box tests, inline by exception.
///
/// The house rule is public-API integration tests in `tests/`, and the tree already carries one
/// documented exception for the same reason this is the second: a private, total, pure parser
/// whose exact behaviour is a merge gate, where routing every case through the public API would
/// obscure what is actually being asserted. `selahcue_core::scripture` sets the precedent.
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_legitimate_dot_dot_target_resolves_inside_the_package() {
        // The case a naive "reject any `..`" breaks — and it is in EVERY real .pptx.
        assert_eq!(
            resolve("ppt/slides/slide1.xml", "../media/image1.png").as_deref(),
            Some("ppt/media/image1.png")
        );
        assert_eq!(
            resolve("ppt/slides/slide1.xml", "../notesSlides/notesSlide1.xml").as_deref(),
            Some("ppt/notesSlides/notesSlide1.xml")
        );
        // A sibling target needs no traversal at all.
        assert_eq!(
            resolve("ppt/presentation.xml", "slides/slide1.xml").as_deref(),
            Some("ppt/slides/slide1.xml")
        );
        // `/`-prefixed means "from the package root", never a filesystem root — there is no
        // filesystem here for it to mean anything else.
        assert_eq!(
            resolve("ppt/slides/slide1.xml", "/ppt/media/x.png").as_deref(),
            Some("ppt/media/x.png")
        );
        // Redundant separators and `.` segments are noise, not structure.
        assert_eq!(
            resolve("ppt/slides/slide1.xml", ".//..//media//x.png").as_deref(),
            Some("ppt/media/x.png")
        );
        // Climbing exactly TO the package root is legitimate and lands there — the refusal is for
        // climbing ABOVE it. `b` is a root-level package entry, and like every other result it is
        // only a lookup key, so naming it grants nothing that the entry set does not already hold.
        assert_eq!(
            resolve("ppt/slides/slide1.xml", "a/../../../b").as_deref(),
            Some("b")
        );
    }

    #[test]
    fn nothing_can_climb_above_the_package_root() {
        // Refused rather than clamped: a target that tries to climb out is not naming something
        // in this package, and silently clamping would turn an attack into a near-miss.
        for target in [
            "../../../../etc/passwd",
            "../../..",
            "/../secret",
            "../../../..",
        ] {
            assert_eq!(
                resolve("ppt/slides/slide1.xml", target),
                None,
                "{target} must not resolve"
            );
        }
    }

    #[test]
    fn windows_separators_nuls_and_over_long_names_are_refused() {
        // A backslash has no meaning in a package name; its presence is a signal, not a typo.
        assert_eq!(resolve("ppt/slides/slide1.xml", "..\\..\\evil"), None);
        assert_eq!(
            resolve("ppt/slides/slide1.xml", "C:\\Windows\\evil.dll"),
            None
        );
        assert_eq!(resolve("ppt/slides/slide1.xml", "media/x\0.png"), None);
        assert_eq!(resolve("ppt/slides/slide1.xml", ""), None);
        let long = "a".repeat(MAX_ZIP_NAME_LEN + 1);
        assert_eq!(resolve("ppt/slides/slide1.xml", &long), None);
    }

    #[test]
    fn the_output_is_only_ever_a_key_and_never_resembles_a_path() {
        // Every successful resolution is a relative, forward-slashed package name with no leading
        // separator, no drive letter and no traversal left in it. That is what makes zip-slip
        // structurally absent: the result can only ever name an entry already in the archive.
        //
        // The `Some` is ASSERTED, not skipped past. This loop used to `continue` on `None`, which
        // meant a `resolve` that refused everything — including every legitimate target in every
        // real `.pptx` — satisfied it without checking a single property. A test whose body can be
        // skipped by the code it is testing is not a test.
        for target in [
            "../media/x.png",
            "/ppt/x.xml",
            "sub/./y.xml",
            "..//media//y.png",
            "a/../../media/z.png",
        ] {
            // `unwrap_or_default` then assert non-empty, rather than `unwrap` or `panic!`: this
            // crate denies both, and `resolve` never yields `Some("")` — an empty segment stack is
            // `None` — so an empty result here means exactly "it refused a legitimate target".
            let out = resolve("ppt/slides/slide1.xml", target).unwrap_or_default();
            assert!(
                !out.is_empty(),
                "{target} is a legitimate package target and must resolve"
            );
            assert!(!out.starts_with('/'), "{out}");
            assert!(!out.contains(".."), "{out}");
            assert!(!out.contains('\\'), "{out}");
            assert!(!out.contains(':'), "{out}");
            assert!(!out.contains('\0'), "{out}");
        }
    }

    #[test]
    fn a_rels_part_name_is_derived_correctly() {
        assert_eq!(
            rels_for("ppt/slides/slide1.xml").as_deref(),
            Some("ppt/slides/_rels/slide1.xml.rels")
        );
        assert_eq!(
            rels_for("ppt/presentation.xml").as_deref(),
            Some("ppt/_rels/presentation.xml.rels")
        );
        assert_eq!(rels_for("root.xml").as_deref(), Some("_rels/root.xml.rels"));
        assert_eq!(rels_for("trailing/"), None);
    }

    #[test]
    fn folding_is_for_comparison_only() {
        // APFS and NTFS fold case, so the lookup must too — but the ORIGINAL name is what gets
        // looked up, and the folded form is never written anywhere.
        assert_eq!(fold("ppt/Media/IMAGE1.PNG"), "ppt/media/image1.png");
    }
}
