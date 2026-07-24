//! Integration tests for the scripture reference parser (FR-027). Public API only.
//! (The all-66-books table test is white-box and lives inline in `src/scripture.rs`.)

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::{parse, parse_one, parse_strict, ParseError, Reference, VerseRange};

fn r(book: u8, name: &'static str, chapter: u16, verses: Option<(u16, u16)>) -> Reference {
    Reference {
        book,
        book_name: name,
        chapter,
        verses: verses.map(|(start, end)| VerseRange { start, end }),
    }
}

// ---- FR-027 acceptance cases ----

#[test]
fn single_verse_full_name() {
    assert_eq!(
        parse_one("Romans 8:28").unwrap(),
        r(45, "Romans", 8, Some((28, 28)))
    );
}

#[test]
fn abbreviation_and_range() {
    assert_eq!(
        parse_one("Rom 8:28-30").unwrap(),
        r(45, "Romans", 8, Some((28, 30)))
    );
}

#[test]
fn whole_chapter() {
    assert_eq!(parse_one("Ps 23").unwrap(), r(19, "Psalms", 23, None));
    assert_eq!(parse_one("Psalm 23").unwrap(), r(19, "Psalms", 23, None));
}

#[test]
fn chapter_verse_range() {
    assert_eq!(
        parse_one("Psalm 23:1-6").unwrap(),
        r(19, "Psalms", 23, Some((1, 6)))
    );
}

#[test]
fn numbered_book_full_and_abbrev() {
    let expected = r(46, "1 Corinthians", 13, Some((4, 4)));
    assert_eq!(parse_one("1 Corinthians 13:4").unwrap(), expected);
    assert_eq!(parse_one("1 Cor 13:4").unwrap(), expected);
    assert_eq!(parse_one("1Cor 13:4").unwrap(), expected);
}

#[test]
fn short_gospel_abbrev() {
    assert_eq!(
        parse_one("Jn 3:16").unwrap(),
        r(43, "John", 3, Some((16, 16)))
    );
}

#[test]
fn multi_reference_semicolon() {
    let refs = parse("John 3:16; 1 Cor 13:4");
    assert_eq!(refs.len(), 2);
    assert_eq!(refs[0], r(43, "John", 3, Some((16, 16))));
    assert_eq!(refs[1], r(46, "1 Corinthians", 13, Some((4, 4))));
}

// ---- normalisation / robustness ----

#[test]
fn case_insensitive_and_periods() {
    assert_eq!(parse_one("romans 8:28").unwrap().book, 45);
    assert_eq!(parse_one("Rom. 8:28").unwrap().book, 45);
    assert_eq!(parse_one("1 cor. 13:4").unwrap().book, 46);
}

#[test]
fn roman_and_word_numbered_books() {
    assert_eq!(
        parse_one("I John 1:9").unwrap(),
        r(62, "1 John", 1, Some((9, 9)))
    );
    assert_eq!(parse_one("First John 1:9").unwrap().book, 62);
    assert_eq!(parse_one("III John 4").unwrap(), r(64, "3 John", 4, None));
}

#[test]
fn samuel_roman_and_word_forms_resolve() {
    // Regression: "I/II Samuel" (roman + full word) must resolve like every
    // other numbered book (was UnknownBook before the alias fix).
    assert_eq!(parse_one("I Samuel 1:1").unwrap().book, 9);
    assert_eq!(parse_one("II Samuel 1:1").unwrap().book, 10);
    assert_eq!(parse_one("First Samuel 3:10").unwrap().book, 9);
    assert_eq!(parse_one("Second Samuel 7:12").unwrap().book, 10);
}

#[test]
fn verse_count_saturates_on_reversed_range() {
    // Hand-built out-of-order range (public fields) must not panic.
    let rev = Reference {
        book: 45,
        book_name: "Romans",
        chapter: 8,
        verses: Some(VerseRange { start: 30, end: 10 }),
    };
    assert_eq!(rev.verse_count(), 1); // saturating — no panic
}

#[test]
fn multiword_book() {
    assert_eq!(
        parse_one("Song of Solomon 2:1").unwrap(),
        r(22, "Song of Solomon", 2, Some((1, 1)))
    );
}

#[test]
fn verse_count() {
    assert_eq!(parse_one("Rom 8:28-30").unwrap().verse_count(), 3);
    assert_eq!(parse_one("Rom 8:28").unwrap().verse_count(), 1);
    assert_eq!(parse_one("Rom 8").unwrap().verse_count(), 0);
}

#[test]
fn display_round_trips() {
    assert_eq!(
        parse_one("Rom 8:28-30").unwrap().to_string(),
        "Romans 8:28-30"
    );
    assert_eq!(parse_one("Jn 3:16").unwrap().to_string(), "John 3:16");
    assert_eq!(parse_one("Ps 23").unwrap().to_string(), "Psalms 23");
}

// ---- malformed input: errors, never panics ----

#[test]
fn malformed_inputs_error_without_panic() {
    assert_eq!(parse_one(""), Err(ParseError::Empty));
    assert_eq!(parse_one("   "), Err(ParseError::Empty));
    assert_eq!(parse_one("Romans"), Err(ParseError::MissingChapter));
    assert_eq!(parse_one("Xyzzy 1:1"), Err(ParseError::UnknownBook));
    assert_eq!(parse_one("Romans 8:abc"), Err(ParseError::BadNumbers));
    assert_eq!(parse_one("Romans abc"), Err(ParseError::BadNumbers));
    assert_eq!(parse_one("Romans 8:"), Err(ParseError::BadNumbers));
    assert_eq!(parse_one("Romans 0:1"), Err(ParseError::BadNumbers)); // chapter 0
    assert_eq!(parse_one("Romans 8:30-10"), Err(ParseError::BadNumbers)); // descending
}

#[test]
fn parse_skips_bad_segments_but_strict_fails() {
    let refs = parse("John 3:16; not-a-ref; Ps 23");
    assert_eq!(refs.len(), 2); // lenient: keeps the two good ones
    assert!(parse_strict("John 3:16; not-a-ref").is_err()); // strict: fails
}

#[test]
fn large_verse_numbers_do_not_overflow() {
    // Psalm 119 has 176 verses — well within u16.
    assert_eq!(
        parse_one("Psalm 119:176").unwrap().verses,
        Some(VerseRange {
            start: 176,
            end: 176
        })
    );
}
