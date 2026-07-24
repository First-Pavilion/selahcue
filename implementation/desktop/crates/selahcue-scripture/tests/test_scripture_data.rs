//! The bundled WEB translation: canonical lookup, keyword search, perf, and
//! bounded-memory behaviour (story 86ajpew05 acceptance).

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{passage_text, search, verse_count, verses, TRANSLATION};

#[test]
fn the_full_protestant_canon_is_bundled() {
    assert_eq!(TRANSLATION, "WEB");
    // 31,098 verses (WEB protestant canon, ebible.org VPL export).
    assert_eq!(verse_count(), 31_098);
    // First and last verses of the canon resolve.
    let gen = parse_one("Genesis 1:1").unwrap();
    assert!(passage_text(&gen).unwrap().contains("In the beginning"));
    let rev = parse_one("Revelation 22:21").unwrap();
    assert!(passage_text(&rev).unwrap().contains("grace"));
}

#[test]
fn romans_8_28_has_its_web_text() {
    // The story's acceptance verse, verbatim from the translation.
    let r = parse_one("Romans 8:28").unwrap();
    let text = passage_text(&r).unwrap();
    assert!(
        text.contains("all things work together for good"),
        "unexpected text: {text}"
    );
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
fn the_index_is_bounded_and_idempotent() {
    // No-leak rule: repeated use never grows the index — one fixed decode.
    let first = verse_count();
    for _ in 0..50 {
        let r = parse_one("John 3:16").unwrap();
        let _ = passage_text(&r);
        let _ = search("love", 4);
    }
    assert_eq!(verse_count(), first);
}
