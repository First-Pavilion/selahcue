//! Which verses each bundled translation has, as a compile-time table (86ak84fbd).
//!
//! `build.rs` reads the embedded assets and writes, per translation, a sorted `static` slice of
//! `(book, chapter, first verse, last verse)` runs (see its module doc for why runs and not
//! counts). This module is the read side: it answers "does this passage present anything?"
//! without decoding the corpus, without allocating, and without any cache — the table is
//! read-only static data of ~1.2k × 8 bytes per translation, fixed by the asset.
//!
//! The answer is, by construction and by an exhaustive test, exactly
//! `!verses_in(t, reference).is_empty()`. The same table also yields a chapter's first and last
//! verse numbers ([`chapter_bounds`]), pinned to the corpus the same way.

use crate::Translation;

/// `(book, chapter, first verse, last verse)` — one maximal run of consecutive verse numbers.
pub(crate) type Run = (u8, u16, u16, u16);

include!(concat!(env!("OUT_DIR"), "/verse_runs.rs"));

/// The run table of a BUNDLED translation, or `None` for a downloadable one, which has no
/// embedded asset and therefore nothing to build a table from. Exhaustive on purpose: adding a
/// `Translation` variant is a compile error here until someone decides which kind it is.
pub(crate) fn runs_of(t: Translation) -> Option<&'static [Run]> {
    match t {
        Translation::Kjv => Some(KJV),
        Translation::Web => Some(WEB),
        Translation::Asv => Some(ASV),
        Translation::Webbe => Some(WEBBE),
        Translation::Dby => Some(DBY),
        Translation::Ylt => None,
    }
}

/// Whether any verse of `book chapter` — restricted to the inclusive `verses` range when one is
/// given — appears in `runs`. Mirrors `verses_in`'s selection exactly: a whole-chapter reference
/// (`None`) matches when the chapter has any verse, and a range matches when some run overlaps
/// it. An inverted range (`start > end`) overlaps nothing, as it selects nothing there.
pub(crate) fn contains(runs: &[Run], book: u8, chapter: u16, verses: Option<(u16, u16)>) -> bool {
    let first = runs.partition_point(|&(b, c, _, _)| (b, c) < (book, chapter));
    runs[first..]
        .iter()
        .take_while(|&&(b, c, _, _)| b == book && c == chapter)
        .any(|&(_, _, run_first, run_last)| match verses {
            None => true,
            Some((start, end)) => run_first.max(start) <= run_last.min(end),
        })
}

/// The first and last verse numbers `book chapter` has in `runs`, or `None` when the chapter has no
/// verse at all (outside the canon, or past a book's end). A chapter with a versification gap keeps
/// its true last verse number (the WEB's Luke 17 is `(1, 37)` though it holds 36 verses), which is
/// why this reads the runs and does not count. Mirrors `verses_in(t, whole chapter)`'s first and
/// last verse exactly: the runs are maximal, disjoint and sorted, so the chapter's first run opens
/// at its first verse and its last run closes at its last.
pub(crate) fn chapter_bounds(runs: &[Run], book: u8, chapter: u16) -> Option<(u16, u16)> {
    let first = runs.partition_point(|&(b, c, _, _)| (b, c) < (book, chapter));
    let mut in_chapter = runs[first..]
        .iter()
        .take_while(|&&(b, c, _, _)| b == book && c == chapter);
    let head = in_chapter.next()?;
    let tail = in_chapter.last().unwrap_or(head);
    Some((head.2, tail.3))
}
