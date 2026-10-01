//! `passage_exists_in` must give EXACTLY the answer the renderer's lookup gives — "does this
//! reference present at least one verse?" — without being the renderer's lookup (86ak84fbd).
//!
//! The probe answers from a small per-translation table built at compile time, so it never
//! decodes the ~4 MB corpus. That is only acceptable if it can never disagree with the corpus: a
//! false "exists" re-opens the original defect (a plan reports `Jude 2:1` healthy while it can
//! present nothing), and a false "missing" flags a healthy passage in front of the operator.
//! So this file pins the table to the corpus the hard way — by comparing it to `verses_in` over
//! every chapter of every book, every verse boundary, and every range that straddles a
//! versification gap.
//!
//! Gaps are real, which is why a per-chapter verse COUNT would not do: the WEB has no Luke
//! 17:36, so Luke 17 holds 36 verses but its last verse is 37. A count-based probe calls
//! `Luke 17:37` missing in the WEB (37 > 36) and `Luke 17:36` present, both wrong.

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::{book_name, parse_one, Reference, VerseRange};
use selahcue_scripture::{passage_exists_in, verses_in, Translation};

const BUNDLED: [Translation; 5] = [
    Translation::Kjv,
    Translation::Web,
    Translation::Asv,
    Translation::Webbe,
    Translation::Dby,
];

fn reference(book: u8, chapter: u16, verses: Option<(u16, u16)>) -> Reference {
    Reference {
        book,
        book_name: book_name(book).unwrap_or("?"),
        chapter,
        verses: verses.map(|(start, end)| VerseRange { start, end }),
    }
}

/// What the renderer would find — the definition `passage_exists_in` must reproduce.
fn renders(t: Translation, r: &Reference) -> bool {
    !verses_in(t, r).is_empty()
}

fn parsed(s: &str) -> Reference {
    parse_one(s).unwrap_or_else(|e| panic!("test reference {s:?} must parse: {e:?}"))
}

/// The set of verse numbers translation `t` really has in a chapter, read from the corpus.
fn verse_set(t: Translation, book: u8, chapter: u16) -> Vec<u16> {
    verses_in(t, &reference(book, chapter, None))
        .iter()
        .map(|v| v.verse)
        .collect()
}

#[test]
fn the_probe_agrees_with_the_corpus_on_every_chapter_boundary_and_gap() {
    let mut present = 0usize;
    let mut absent = 0usize;
    let mut gap_chapters = 0usize;

    for t in BUNDLED {
        for book in 0u8..=70 {
            // Two chapters past the end of the book, plus chapter 0 and a far-out one.
            let last_chapter = (1u16..=151)
                .rev()
                .find(|c| renders(t, &reference(book, *c, None)))
                .unwrap_or(0);
            let mut chapters: Vec<u16> = (0..=last_chapter.saturating_add(2)).collect();
            chapters.push(151);
            chapters.push(u16::MAX);

            for chapter in chapters {
                let vs = verse_set(t, book, chapter);
                let max = vs.last().copied().unwrap_or(0);
                let has_gap = !vs.is_empty() && vs.len() != usize::from(max);
                if has_gap {
                    gap_chapters += 1;
                }

                // Every start/end that matters: both ends of the chapter, both sides of every
                // missing verse, and well past the end.
                let mut points: Vec<u16> = vec![0, 1, 2, max, max.saturating_add(1), u16::MAX];
                for w in vs.windows(2) {
                    if w[1] != w[0] + 1 {
                        points.extend([w[0], w[0] + 1, w[1] - 1, w[1]]);
                    }
                }
                points.sort_unstable();
                points.dedup();

                let mut cases: Vec<Option<(u16, u16)>> = vec![None];
                for &a in &points {
                    for &b in &points {
                        // `a > b` is an inverted range: verses_in matches nothing, and so must the probe.
                        cases.push(Some((a, b)));
                    }
                }
                // A chapter with a gap gets EVERY range, not just the interesting points.
                if has_gap {
                    for a in 0..=max + 2 {
                        for b in 0..=max + 2 {
                            cases.push(Some((a, b)));
                        }
                    }
                }

                for verses in cases {
                    let r = reference(book, chapter, verses);
                    let expected = renders(t, &r);
                    assert_eq!(
                        passage_exists_in(t, &r),
                        expected,
                        "{} book {book} chapter {chapter} verses {verses:?}: the probe says {} \
                         but the renderer's lookup says {expected}",
                        t.code(),
                        !expected,
                    );
                    if expected {
                        present += 1;
                    } else {
                        absent += 1;
                    }
                }
            }
        }
    }

    eprintln!(
        "swept {present} present + {absent} absent passages over {gap_chapters} gapped chapters"
    );

    // The comparison must have exercised both outcomes and the versification gaps, or "they
    // agreed" could mean "they both said false to everything".
    assert!(
        present > 100_000,
        "only {present} existing passages were compared — the sweep is vacuous"
    );
    assert!(
        absent > 100_000,
        "only {absent} missing passages were compared — the sweep is vacuous"
    );
    assert!(
        gap_chapters >= 26,
        "only {gap_chapters} gapped chapters were swept; the corpus has 26 (WEB 4, ASV 15, \
         WEBBE 4, DBY 3) — the gap handling went unexercised"
    );
}

#[test]
fn a_passage_that_parses_but_names_no_verse_does_not_exist() {
    // The defect 1840f1c fixed, restated against the probe itself: all well-formed, none presentable.
    for t in BUNDLED {
        for bad in [
            "Jude 2:1",
            "Romans 99:1",
            "Psalm 151:1",
            "Genesis 51:1",
            "John 3:99",
        ] {
            assert!(
                !passage_exists_in(t, &parsed(bad)),
                "{} {bad} parses but names no verse, so it must not exist",
                t.code()
            );
        }
    }
}

#[test]
fn real_passages_exist_in_every_bundled_translation() {
    for t in BUNDLED {
        for good in [
            "Jude 1:1",
            "Jude 1",
            "John 3:16",
            "John 3:16-18",
            "Romans 8",
            "Psalm 119:176",
            "Genesis 1:1",
            "Revelation 22:21",
        ] {
            assert!(
                passage_exists_in(t, &parsed(good)),
                "{} {good} is a real passage and must exist",
                t.code()
            );
        }
    }
}

#[test]
fn a_verse_one_translation_omits_is_missing_there_and_present_in_the_others() {
    // Versification differs by translation, so the answer is per-translation, not per-reference.
    // Luke 17:36 — KJV and Darby have it; WEB, ASV and WEBBE do not.
    let luke = parsed("Luke 17:36");
    assert!(passage_exists_in(Translation::Kjv, &luke));
    assert!(passage_exists_in(Translation::Dby, &luke));
    for t in [Translation::Web, Translation::Asv, Translation::Webbe] {
        assert!(
            !passage_exists_in(t, &luke),
            "{} has no Luke 17:36 — the chapter's verse COUNT is 36 but its last verse is 37",
            t.code()
        );
    }
    // …yet the verse after the gap is there, which a count-based probe (37 > 36) gets wrong.
    for t in [Translation::Web, Translation::Asv, Translation::Webbe] {
        assert!(
            passage_exists_in(t, &parsed("Luke 17:37")),
            "{} Luke 17:37 exists",
            t.code()
        );
        // A range that merely SPANS the gap still presents the verses around it.
        assert!(
            passage_exists_in(t, &parsed("Luke 17:35-36")),
            "{} Luke 17:35-36 presents verse 35",
            t.code()
        );
    }
    // Acts 8:37 is absent from every bundled translation except the KJV.
    let acts = parsed("Acts 8:37");
    assert!(passage_exists_in(Translation::Kjv, &acts));
    for t in [
        Translation::Web,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
    ] {
        assert!(
            !passage_exists_in(t, &acts),
            "{} has no Acts 8:37",
            t.code()
        );
    }
    // Matthew 17:21 only the ASV drops.
    assert!(!passage_exists_in(
        Translation::Asv,
        &parsed("Matthew 17:21")
    ));
    assert!(passage_exists_in(
        Translation::Kjv,
        &parsed("Matthew 17:21")
    ));
}

#[test]
fn a_reference_outside_the_canon_does_not_exist() {
    for t in BUNDLED {
        for (book, chapter) in [(0u8, 1u16), (67, 1), (255, 1), (1, 0), (43, 0), (66, 23)] {
            assert!(
                !passage_exists_in(t, &reference(book, chapter, None)),
                "{} book {book} chapter {chapter} is outside the canon",
                t.code()
            );
        }
        // Inverted range inside a real chapter presents nothing, exactly like `verses_in`.
        let inverted = reference(43, 3, Some((17, 16)));
        assert!(!renders(t, &inverted), "premise: verses_in finds nothing");
        assert!(!passage_exists_in(t, &inverted));
    }
}

#[test]
fn a_translation_that_is_not_bundled_is_never_reported_present_when_it_has_no_verses() {
    // YLT is downloadable; with nothing downloaded (and, in the default build, no download
    // machinery at all) it has no verses, so nothing exists in it — the same answer `verses_in` gives.
    let r = parsed("John 3:16");
    assert_eq!(
        passage_exists_in(Translation::Ylt, &r),
        renders(Translation::Ylt, &r)
    );
}
