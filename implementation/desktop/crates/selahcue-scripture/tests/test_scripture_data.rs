//! The bundled WEB translation: canonical lookup, keyword search, perf, and
//! bounded-memory behaviour (story 86ajpew05 acceptance).

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{
    passage_text, passage_text_in, search, verse_count, verse_count_in, verses, Translation,
    TRANSLATION,
};

#[test]
fn both_protestant_canons_are_bundled_and_kjv_is_the_default() {
    // Owner decision (2026-07-24): KJV is the default translation.
    assert_eq!(TRANSLATION, "KJV");
    assert_eq!(Translation::default(), Translation::Kjv);
    assert_eq!(Translation::ALL[0], Translation::Kjv);
    // ebible.org VPL exports.
    assert_eq!(verse_count_in(Translation::Kjv), 31_102);
    assert_eq!(verse_count_in(Translation::Web), 31_098);
    assert_eq!(verse_count_in(Translation::Asv), 31_086);
    assert_eq!(verse_count_in(Translation::Webbe), 31_098);
    assert_eq!(verse_count_in(Translation::Dby), 31_099);
    assert_eq!(verse_count(), 31_102, "default count is the KJV's");
    // First and last verses of the canon resolve in EVERY translation (wording
    // varies legitimately — BBE opens "At the first God made…").
    let gen = parse_one("Genesis 1:1").unwrap();
    let rev = parse_one("Revelation 22:21").unwrap();
    for t in Translation::ALL {
        assert!(
            passage_text_in(t, &gen).unwrap().contains("God"),
            "{} Genesis 1:1",
            t.code()
        );
        assert!(
            !passage_text_in(t, &rev).unwrap().is_empty(),
            "{} Revelation 22:21",
            t.code()
        );
    }
    assert!(
        passage_text(&gen).unwrap().contains("In the beginning"),
        "KJV default wording"
    );
    // Codes round-trip (wire/UI selector), case-insensitively — for ALL.
    for t in Translation::ALL {
        assert_eq!(Translation::from_code(t.code()), Some(t));
        assert_eq!(Translation::from_code(&t.code().to_lowercase()), Some(t));
    }
    assert_eq!(Translation::from_code("NIV"), None);
}

#[test]
fn romans_8_28_reads_correctly_in_each_translation() {
    let r = parse_one("Romans 8:28").unwrap();
    // Default (KJV) wording — with the ebible supplied-word brackets stripped.
    let kjv = passage_text(&r).unwrap();
    assert!(
        kjv.contains("all things work together for good to them that love God"),
        "unexpected KJV text: {kjv}"
    );
    assert!(!kjv.contains('[') && !kjv.contains('¶'), "markup stripped");
    // Each alternative translation keeps its own wording.
    let web = passage_text_in(Translation::Web, &r).unwrap();
    assert!(web.contains("work together for good for those who love God"));
    let asv = passage_text_in(Translation::Asv, &r).unwrap();
    assert!(asv.contains("to them that love God all things work together"));
    let webbe = passage_text_in(Translation::Webbe, &r).unwrap();
    assert!(webbe.contains("work together for good for those who love God"));
    let dby = passage_text_in(Translation::Dby, &r).unwrap();
    assert!(dby.contains("all things work together for good to those who love"));
}

#[test]
fn ranges_and_whole_chapters_resolve() {
    let range = parse_one("Romans 8:28-30").unwrap();
    assert_eq!(verses(&range).len(), 3);
    // Psalm 117 is the shortest chapter: exactly 2 verses.
    let chapter = parse_one("Psalm 117").unwrap();
    assert_eq!(verses(&chapter).len(), 2);
    // Single-chapter books address explicitly (the parser reads "Jude 9" as
    // chapter 9 — bare-number shorthand is a later parser nicety).
    let jude = parse_one("Jude 1:9").unwrap();
    assert_eq!(verses(&jude).len(), 1);
    // A chapter outside the canon yields nothing (never panics).
    let no_such = parse_one("Psalm 151:1").unwrap();
    assert!(verses(&no_such).is_empty());
}

#[test]
fn keyword_search_finds_verses_and_is_bounded() {
    let hits = search("work together for good", 8);
    assert!(
        hits.iter().any(|h| h.reference == "Romans 8:28"),
        "hits: {:?}",
        hits.iter().map(|h| &h.reference).collect::<Vec<_>>()
    );
    // Search results can be staged directly: the reference round-trips.
    let r = parse_one(&hits[0].reference).unwrap();
    assert!(passage_text(&r).is_some());
    // The limit bounds the result set on common words.
    assert_eq!(search("the", 5).len(), 5);
    // Case-insensitive; empty query is empty.
    assert!(!search("SHEPHERD", 8).is_empty());
    assert!(search("   ", 8).is_empty());
}

#[test]
fn keyword_search_meets_the_500ms_budget() {
    // Story acceptance: search <500ms. Worst case: a rare phrase forces a scan
    // of all 31k verses. The one-time index decode is warmed first — the budget
    // measures SEARCH, and test ordering must not decide which test pays init.
    let _ = verse_count();
    let start = std::time::Instant::now();
    let hits = search("Mephibosheth", 20);
    let elapsed = start.elapsed();
    assert!(!hits.is_empty());
    assert!(
        elapsed < std::time::Duration::from_millis(500),
        "full-scan search took {elapsed:?}"
    );
}

#[test]
fn the_indexes_are_bounded_and_idempotent() {
    // No-leak rule: repeated use never grows EITHER decoded index — one fixed
    // decode per translation.
    let first: Vec<usize> = Translation::ALL
        .iter()
        .map(|t| verse_count_in(*t))
        .collect();
    for _ in 0..50 {
        let r = parse_one("John 3:16").unwrap();
        for t in Translation::ALL {
            let _ = passage_text_in(t, &r);
            let _ = selahcue_scripture::search_in(t, "love", 4);
        }
        let _ = passage_text(&r);
        let _ = search("love", 4);
    }
    let after: Vec<usize> = Translation::ALL
        .iter()
        .map(|t| verse_count_in(*t))
        .collect();
    assert_eq!(after, first);
    assert_eq!(verse_count(), first[0], "default remains the KJV index");
}

#[test]
fn chapter_browser_returns_full_chapters_with_paging() {
    use selahcue_scripture::{adjacent_chapter, chapter};
    // A verse-level reference yields its WHOLE chapter.
    let r = parse_one("Genesis 1:3").unwrap();
    let ch = chapter(&r).unwrap();
    assert_eq!((ch.book_name.as_str(), ch.chapter), ("Genesis", 1));
    assert_eq!(ch.verses.len(), 31);
    assert_eq!(ch.verses[0].0, 1);
    assert!(!ch.has_prev, "nothing before Genesis 1");
    assert!(ch.has_next);

    // Paging crosses book boundaries in both directions.
    assert_eq!(adjacent_chapter(&r, true).as_deref(), Some("Genesis 2"));
    assert_eq!(adjacent_chapter(&r, false), None);
    let mal = parse_one("Malachi 4").unwrap();
    assert_eq!(adjacent_chapter(&mal, true).as_deref(), Some("Matthew 1"));
    let rev = parse_one("Revelation 22").unwrap();
    assert!(chapter(&rev).unwrap().has_prev);
    assert!(adjacent_chapter(&rev, true).is_none(), "end of the canon");
    // The returned display string parses back (round-trips into the browser).
    let next = adjacent_chapter(&mal, true).unwrap();
    assert!(chapter(&parse_one(&next).unwrap()).is_some());

    // Out-of-canon chapters are None, never a panic.
    assert!(chapter(&parse_one("Psalm 151").unwrap()).is_none());
}

#[test]
fn no_markup_residue_in_any_bundled_translation() {
    // Every marker class seen in ebible exports must be stripped everywhere:
    // supplied-word brackets, pilcrows, and footnote-apparatus asterisks (the
    // review found '*' residue in Darby's Psalm 119 and BBE placeholders).
    use selahcue_scripture::verses_in;
    let whole_bible = selahcue_core::scripture::parse_one("Genesis 1").unwrap();
    let _ = whole_bible; // per-translation full scans below
    for t in Translation::ALL {
        let mut scanned = 0usize;
        for book in 1..=66u8 {
            for chapter in 1..=200u16 {
                let r = selahcue_core::scripture::Reference {
                    book,
                    book_name: "",
                    chapter,
                    verses: None,
                };
                let vs = verses_in(t, &r);
                if vs.is_empty() {
                    break;
                }
                for v in vs {
                    scanned += 1;
                    assert!(
                        !v.text.contains(['[', ']', '¶', '*']),
                        "{} {}:{}:{} has residue: {}",
                        t.code(),
                        book,
                        chapter,
                        v.verse,
                        v.text
                    );
                }
            }
        }
        assert!(scanned > 30_000, "{} scanned {scanned}", t.code());
    }
}
