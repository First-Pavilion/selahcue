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

// ---- A range, however a person writes it (Service Plan link box) ----

#[test]
fn a_range_is_accepted_however_it_is_written() {
    let expected = r(19, "Psalms", 1, Some((2, 10)));
    for typed in [
        "Psalms 1:2-10",    // canonical
        "Psalms 1:2 to 10", // the way it is SAID
        "Psalms 1:2 through 10",
        "Psalms 1:2 thru 10",
        "Psalms 1:2 - 10",      // spaced hyphen
        "Psalms 1:2\u{2013}10", // en dash: what the Settings copy itself shows as the example
        "Psalms 1:2 \u{2013} 10",
        "Psalms 1:2\u{2014}10", // em dash
        "Psalm 1 verses 2 to 10",
        "Psalm 1 verse 2 through 10",
        "psalm chapter 1 verses 2-10",
        "Ps 1 2-10",    // the existing space-separated shorthand
        "Ps 1 2 to 10", // ...and with a connective
        "PSALMS 1:2 TO 10",
    ] {
        assert_eq!(parse_one(typed).unwrap(), expected, "{typed:?}");
    }
}

#[test]
fn a_loosely_written_range_displays_canonically() {
    // The canonical spelling is what gets stored and compared everywhere, so it must not drift
    // with how the operator happened to type it.
    for typed in [
        "Romans 8:28 to 30",
        "Romans 8:28 \u{2013} 30",
        "Romans 8 verses 28 through 30",
    ] {
        assert_eq!(
            parse_one(typed).unwrap().to_string(),
            "Romans 8:28-30",
            "{typed:?}"
        );
    }
}

#[test]
fn a_single_verse_is_still_one_verse() {
    // Positive control: the connective handling must not turn a lone verse into a range.
    for typed in ["Romans 8:28", "Romans 8 28", "Romans chapter 8 verse 28"] {
        assert_eq!(
            parse_one(typed).unwrap(),
            r(45, "Romans", 8, Some((28, 28))),
            "{typed:?}"
        );
    }
}

#[test]
fn loosening_the_range_syntax_does_not_loosen_what_is_rejected() {
    for bad in [
        "Romans 8:30 to 28", // descending
        "Romans 8:30 - 28",  // descending, spaced
        "Romans 8:0 to 3",   // verse 0
        "Romans 8 to 9",     // a span of CHAPTERS is not expressible
        "Romans 8:28 to",    // dangling connective
        "Romans 8:28 to to 30",
        "Romans 8:28 -", // dangling dash
        "Romans 8:28 \u{2013}",
    ] {
        assert!(parse_one(bad).is_err(), "{bad:?} must still be rejected");
    }
}

#[test]
fn range_syntax_handling_never_panics_on_odd_input() {
    // The parser takes untrusted text; every one of these must return, Ok or Err, without panicking.
    for odd in [
        "-",
        "\u{2013}",
        "\u{2014}",
        "to",
        " to ",
        "through",
        "1-",
        "-1",
        "1 to",
        "to 1",
        "1 to 2",
        "- - -",
        "to to to",
        "verse",
        "verses verses",
        "chapter chapter 1",
        "Romans \u{2013}\u{2013} 8",
        "Romans 8:28\u{2013}",
        "\u{2013}8:28",
        "\u{1F600} to \u{1F600}",
        "Romans 8:28 to 30 to 32",
        "Romans 8:28-30-32",
        "Romans 99999999999 to 99999999999",
    ] {
        let _ = parse_one(odd);
    }
    let long = format!("Psalms 1:2 {}10", "to ".repeat(10_000));
    let _ = parse_one(&long);
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

#[test]
fn space_separated_shorthand_resolves_chapter_and_verse() {
    // Owner request (86ajpwkte): "gen 1 1" == "Genesis 1:1".
    let r = parse_one("gen 1 1").unwrap();
    assert_eq!((r.book_name, r.chapter), ("Genesis", 1));
    assert_eq!(r.verses, Some(VerseRange { start: 1, end: 1 }));

    // Numbered books keep their leading digit with the book.
    let r = parse_one("1 cor 13 4").unwrap();
    assert_eq!((r.book_name, r.chapter), ("1 Corinthians", 13));
    assert_eq!(r.verses, Some(VerseRange { start: 4, end: 4 }));
    let r = parse_one("1 sam 13 1").unwrap();
    assert_eq!((r.book_name, r.chapter), ("1 Samuel", 13));

    // Ranges work in the shorthand too.
    let r = parse_one("gen 1 1-3").unwrap();
    assert_eq!(r.verses, Some(VerseRange { start: 1, end: 3 }));

    // Existing spellings are untouched, and chapter-only stays chapter-only.
    assert_eq!(
        parse_one("Genesis 1:1").unwrap(),
        parse_one("gen 1 1").unwrap()
    );
    assert_eq!(parse_one("gen 1").unwrap().verses, None);

    // Garbage stays rejected: no book resolves, numbers alone mean nothing.
    assert!(parse_one("2 2 2").is_err());
    assert!(parse_one("zzz 1 1").is_err());
}
