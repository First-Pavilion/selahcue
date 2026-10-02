//! `chapter_verse_bounds_in` must give EXACTLY the first and last verse number the corpus has in a
//! chapter, without being the corpus lookup.
//!
//! It answers from the same compile-time verse-run table as `passage_exists_in` (86ak84fbd), so a
//! plan's scripture links can be fitted to their chapter without decoding a translation. That is
//! only acceptable if it can never disagree with the corpus: too low a last verse would cut real
//! verses off a linked range, too high would advertise slides that show nothing. So this file pins
//! the table to `verses_in` the hard way, over every chapter of every book of every bundled
//! translation, the versification gaps included.
//!
//! A gap is why the answer is a pair of verse NUMBERS and not a count: the WEB has no Luke 17:36,
//! so Luke 17 holds 36 verses but ends at 37, and a count-based answer would clamp a link at 36 and
//! drop the last real verse.

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::{book_name, parse_one, Reference, VerseRange};
use selahcue_scripture::{chapter_verse_bounds_in, verses_in, Translation};

/// Every translation compiled into the binary, derived rather than listed, so a sixth bundled
/// translation joins the sweep automatically.
fn bundled() -> Vec<Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
        .collect()
}

fn reference(book: u8, chapter: u16, verses: Option<(u16, u16)>) -> Reference {
    Reference {
        book,
        book_name: book_name(book).unwrap_or("?"),
        chapter,
        verses: verses.map(|(start, end)| VerseRange { start, end }),
    }
}

fn parsed(s: &str) -> Reference {
    parse_one(s).unwrap_or_else(|e| panic!("test reference {s:?} must parse: {e:?}"))
}

/// What the renderer's own lookup finds for the whole chapter — the definition the accessor must
/// reproduce: its first and last verse number, `None` when it holds nothing.
fn from_the_corpus(t: Translation, book: u8, chapter: u16) -> Option<(u16, u16)> {
    let vs = verses_in(t, &reference(book, chapter, None));
    Some((vs.first()?.verse, vs.last()?.verse))
}

#[test]
fn the_bounds_agree_with_the_corpus_on_every_chapter_of_every_book() {
    let mut present = 0usize;
    let mut absent = 0usize;
    let mut gap_chapters = 0usize;

    for t in bundled() {
        for book in 0u8..=70 {
            // Past the end of the book, chapter 0, and far out: all must be `None` like the corpus.
            let mut chapters: Vec<u16> = (0..=152).collect();
            chapters.push(u16::MAX);
            for chapter in chapters {
                let expected = from_the_corpus(t, book, chapter);
                // The accessor ignores the reference's verse selection: ask with none, a range
                // inside the chapter, one past its end, and an inverted one — same answer each time.
                for verses in [
                    None,
                    Some((1, 1)),
                    Some((2, 5)),
                    Some((9_000, 9_001)),
                    Some((7, 3)),
                ] {
                    assert_eq!(
                        chapter_verse_bounds_in(t, &reference(book, chapter, verses)),
                        expected,
                        "{} book {book} chapter {chapter} (reference verses {verses:?}): the \
                         table disagrees with the corpus",
                        t.code(),
                    );
                }
                match expected {
                    Some((first, last)) => {
                        present += 1;
                        let count = verses_in(t, &reference(book, chapter, None)).len();
                        if usize::from(last) != count {
                            gap_chapters += 1;
                        }
                        assert!(first >= 1 && first <= last, "premise: a sane chapter");
                    }
                    None => absent += 1,
                }
            }
        }
    }

    eprintln!("swept {present} chapters present + {absent} absent, {gap_chapters} with a gap");

    // The comparison must have exercised both outcomes and the gaps, or "they agreed" could mean
    // "they both said None to everything".
    assert!(
        present >= 5 * 1189,
        "only {present} chapters were compared — the sweep is vacuous"
    );
    assert!(
        absent > 10_000,
        "only {absent} absent chapters were compared — the sweep is vacuous"
    );
    assert!(
        gap_chapters >= 26,
        "only {gap_chapters} gapped chapters were swept; this floor is pinned to the CURRENT \
         assets, which have 26 (WEB 4, ASV 15, WEBBE 4, DBY 3) — fewer means the gap handling went \
         unexercised, or an asset was legitimately replaced with one that has fewer gaps, in which \
         case re-derive the floor from the new assets rather than deleting it"
    );
}

#[test]
fn a_chapter_with_a_gap_ends_at_its_last_verse_number_not_its_verse_count() {
    // Luke 17:36: KJV and Darby have it; WEB, ASV and WEBBE do not. Both end at 37, but only the
    // KJV and Darby have 37 verses.
    let luke = parsed("Luke 17");
    for t in bundled() {
        assert_eq!(
            chapter_verse_bounds_in(t, &luke),
            Some((1, 37)),
            "{} Luke 17 runs 1..=37 whether or not verse 36 exists",
            t.code()
        );
    }
    // The count differs, which is exactly what a count-based answer would get wrong.
    assert_eq!(verses_in(Translation::Kjv, &luke).len(), 37, "premise");
    assert_eq!(verses_in(Translation::Web, &luke).len(), 36, "premise");

    // Acts 8:37 is absent from every bundled translation but the KJV; the chapter still ends at 40.
    let acts = parsed("Acts 8");
    for t in bundled() {
        assert_eq!(
            chapter_verse_bounds_in(t, &acts),
            Some((1, 40)),
            "{}",
            t.code()
        );
    }
    assert_eq!(verses_in(Translation::Web, &acts).len(), 39, "premise");
}

#[test]
fn versification_differs_by_translation_so_the_answer_is_per_translation() {
    // Romans 14 and 16 are numbered differently in the KJV and the WEB. A bound taken from one
    // translation and applied to the other would clamp (or extend) a range wrongly.
    let (kjv_14, web_14) = (
        chapter_verse_bounds_in(Translation::Kjv, &parsed("Romans 14")),
        chapter_verse_bounds_in(Translation::Web, &parsed("Romans 14")),
    );
    assert_eq!(kjv_14, Some((1, 23)));
    assert_eq!(web_14, Some((1, 26)));
    assert_ne!(kjv_14, web_14, "premise: the translations disagree");
}

#[test]
fn a_chapter_outside_the_canon_has_no_bounds() {
    for t in bundled() {
        for (book, chapter) in [(0u8, 1u16), (67, 1), (255, 1), (1, 0), (43, 0), (66, 23)] {
            assert_eq!(
                chapter_verse_bounds_in(t, &reference(book, chapter, None)),
                None,
                "{} book {book} chapter {chapter} is outside the canon",
                t.code()
            );
        }
        for bad in ["Psalm 151", "Romans 99", "Genesis 51", "Jude 2"] {
            assert_eq!(
                chapter_verse_bounds_in(t, &parsed(bad)),
                None,
                "{} {bad} parses but has no verses",
                t.code()
            );
        }
    }
}

#[test]
fn real_chapters_have_their_real_bounds() {
    // Spot checks against well-known chapter lengths, so the sweep above cannot be satisfied by two
    // wrong-in-the-same-way implementations.
    for t in bundled() {
        for (chapter, bounds) in [
            ("Psalm 119", (1, 176)),
            ("Psalm 117", (1, 2)),
            ("John 3", (1, 36)),
            ("Jude 1", (1, 25)),
            ("Revelation 22", (1, 21)),
            ("Genesis 1", (1, 31)),
        ] {
            assert_eq!(
                chapter_verse_bounds_in(t, &parsed(chapter)),
                Some(bounds),
                "{} {chapter}",
                t.code()
            );
        }
    }
}

#[test]
fn a_translation_that_is_not_bundled_agrees_with_its_lookup() {
    // YLT is downloadable; with nothing downloaded (and, in the default build, no download
    // machinery at all) it has no verses, so no chapter has bounds — the answer `verses_in` implies.
    let r = parsed("John 3");
    assert_eq!(
        chapter_verse_bounds_in(Translation::Ylt, &r),
        from_the_corpus(Translation::Ylt, r.book, r.chapter)
    );
}
