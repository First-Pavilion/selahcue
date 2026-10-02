//! The ONE definition of what a line of a bundled verse asset is.
//!
//! Compiled twice, deliberately: into the crate (`mod tsv_row` in `lib.rs`, used by the runtime
//! decoder that builds the full verse index) and into `build.rs` (`#[path]`, used to derive the
//! compile-time verse-run table that `passage_exists_in` answers from). Because both read verse
//! lines through this one function, "which lines of the asset count as verses" cannot drift
//! between the table and the index — a malformed line is skipped by both or by neither. The
//! exhaustive agreement test (`tests/test_passage_exists.rs`) is the backstop; this is what makes
//! it unlikely to ever fire.

/// Parse one `book\tchapter\tverse\ttext` line into `(book, chapter, verse, text)`, or `None`
/// when it is not a verse line (too few fields, or a non-numeric / out-of-range number).
pub(crate) fn parse_row(line: &str) -> Option<(u8, u16, u16, &str)> {
    let mut parts = line.splitn(4, '\t');
    Some((
        parts.next()?.parse().ok()?,
        parts.next()?.parse().ok()?,
        parts.next()?.parse().ok()?,
        parts.next()?,
    ))
}
