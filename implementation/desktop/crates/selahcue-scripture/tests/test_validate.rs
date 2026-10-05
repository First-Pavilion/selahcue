//! Install-time validation of a downloaded asset (`selahcue_scripture::validate`, feature
//! `installed`).
//!
//! A downloaded file has passed its SHA-256 check by the time it gets here, but the digest only
//! says "these are the bytes the catalogue named". This is the second line: it refuses an asset
//! that is not shaped like a Bible even if the catalogue (or the build that produced the digest)
//! was wrong. Every refusal names the specific error it must reach, with the 1-based line number
//! where one applies, and is paired with a benign input that is accepted so "refused" is
//! distinguishable from "everything is refused".
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::io::Write;

use common::{big_asset, fixture, gz};
use selahcue_scripture::validate::{
    validate_asset, Counts, ValidationError, MAX_DECOMPRESSED_BYTES, MAX_LINE_BYTES,
};

/// Reading `rows` back through the validator with the counts they actually have.
fn counts(ot: u32, nt: u32) -> Counts {
    Counts { ot, nt }
}

/// Gzip of `lines` joined with newlines (and a final newline).
fn asset(lines: &[&str]) -> Vec<u8> {
    let mut text = lines.join("\n");
    text.push('\n');
    gz(text.as_bytes())
}

fn validate(lines: &[&str], expected: Counts) -> Result<(), ValidationError> {
    validate_asset(asset(lines).as_slice(), expected)
}

/// `char` for a code point, so a test never has to type an invisible or look-alike character.
fn ch(code: u32) -> char {
    char::from_u32(code).unwrap()
}

#[test]
fn a_well_formed_asset_passes_with_its_counts() {
    let f = fixture("TST", 3, 2);
    validate_asset(f.gz.as_slice(), counts(3, 2)).expect("the benign fixture is accepted");
}

#[test]
fn verse_counts_must_equal_the_catalogue_entry() {
    let f = fixture("TST", 3, 2);
    for (ot, nt) in [(4, 2), (3, 3), (2, 2), (3, 1), (0, 0), (2, 3)] {
        let err = validate_asset(f.gz.as_slice(), counts(ot, nt)).unwrap_err();
        assert_eq!(
            err,
            ValidationError::VerseCount {
                expected: counts(ot, nt),
                actual: counts(3, 2)
            },
            "expected {ot}/{nt}"
        );
    }
}

#[test]
fn the_old_and_new_testament_split_is_at_book_40() {
    // Book 39 (Malachi) is the last Old Testament book, 40 (Matthew) the first New Testament one.
    let lines = ["39\t1\t1\tlast of the Old", "40\t1\t1\tfirst of the New"];
    validate(&lines, counts(1, 1)).expect("39 is OT, 40 is NT");
    let err = validate(&lines, counts(0, 2)).unwrap_err();
    assert!(matches!(err, ValidationError::VerseCount { .. }));
    let err = validate(&lines, counts(2, 0)).unwrap_err();
    assert!(matches!(err, ValidationError::VerseCount { .. }));
}

#[test]
fn a_book_outside_1_to_66_is_refused() {
    for book in [0u32, 67, 68, 100, 200, 255] {
        let line = format!("{book}\t1\t1\ttext");
        let err = validate(&["1\t1\t1\tok", &line], counts(1, 0)).unwrap_err();
        assert_eq!(
            err,
            ValidationError::BookOutOfRange {
                line: 2,
                book: book as u8
            },
            "book {book}"
        );
    }
    // The first line too, and the boundary books are fine.
    let err = validate(&["0\t1\t1\ttext"], counts(0, 0)).unwrap_err();
    assert!(matches!(
        err,
        ValidationError::BookOutOfRange { line: 1, book: 0 }
    ));
    validate(&["1\t1\t1\tGenesis", "66\t1\t1\tRevelation"], counts(1, 1))
        .expect("1 and 66 are in range");
}

#[test]
fn a_chapter_or_verse_of_zero_is_refused() {
    for line in ["1\t0\t1\ttext", "1\t1\t0\ttext"] {
        let err = validate(&[line], counts(0, 0)).unwrap_err();
        assert_eq!(
            err,
            ValidationError::ZeroChapterOrVerse { line: 1 },
            "{line}"
        );
    }
}

#[test]
fn a_line_that_is_not_a_verse_row_is_refused_with_its_line_number() {
    let good = "1\t1\t1\tIn the beginning";
    for bad in [
        "1\t1",              // too few fields
        "1\t1\t2",           // no text field at all
        "one\t1\t2\ttext",   // book is not a number
        "1\t-1\t2\ttext",    // negative chapter
        "1\t1\t70000\ttext", // verse overflows 16 bits
        "300\t1\t2\ttext",   // book overflows 8 bits
        "1.5\t1\t2\ttext",   // not a whole number
        "",                  // a blank line
        "no tabs at all",
    ] {
        let err = validate(&[good, bad], counts(1, 0)).unwrap_err();
        assert_eq!(err, ValidationError::BadRow { line: 2 }, "{bad:?}");
    }
    // A blank line in the middle of the file is a bad row too, not skipped.
    let err = validate(&[good, "", "1\t1\t2\ttext"], counts(2, 0)).unwrap_err();
    assert_eq!(err, ValidationError::BadRow { line: 2 });
}

#[test]
fn rows_must_be_strictly_ascending() {
    let ok = ["1\t1\t1\ta", "1\t1\t2\tb", "1\t2\t1\tc", "2\t1\t1\td"];
    validate(&ok, counts(4, 0)).expect("ascending rows pass");
    // Gaps are fine: translations omit verses (the WEB has no Luke 17:36).
    validate(&["1\t1\t1\ta", "1\t1\t4\tb"], counts(2, 0)).expect("a verse gap is allowed");
    for (name, rows) in [
        ("a duplicate row", ["1\t1\t1\ta", "1\t1\t1\ta"]),
        ("a verse going backwards", ["1\t1\t2\ta", "1\t1\t1\tb"]),
        ("a chapter going backwards", ["1\t2\t1\ta", "1\t1\t5\tb"]),
        ("a book going backwards", ["2\t1\t1\ta", "1\t5\t5\tb"]),
    ] {
        let err = validate(&rows, counts(2, 0)).unwrap_err();
        assert_eq!(err, ValidationError::NotAscending { line: 2 }, "{name}");
    }
}

#[test]
fn markup_residue_is_refused_wherever_it_hides_in_the_text() {
    let pilcrow = ch(0xB6);
    let nul = ch(0);
    let bell = ch(7);
    let del = ch(0x7F);
    let planted = [
        '[', ']', '*', pilcrow, '|', '\\', nul, bell, '\r', del, '\t',
    ];
    for c in planted {
        for position in ["start", "middle", "end"] {
            let text = match position {
                "start" => format!("{c}word and more"),
                "middle" => format!("word {c} and more"),
                _ => format!("word and more{c}"),
            };
            let line = format!("1\t1\t1\t{text}");
            let err = validate(&[&line], counts(1, 0)).unwrap_err();
            // A control character at the very start or end may be refused as untrimmed instead,
            // but it is refused: the error is one of the two text errors and never a pass.
            match err {
                ValidationError::Residue { line: 1, character } => assert_eq!(character, c),
                ValidationError::EmptyOrUntrimmed { line: 1 } => {
                    assert!(c.is_whitespace() || c.is_control(), "{c:?} at {position}")
                }
                other => panic!("{c:?} at {position}: unexpected {other:?}"),
            }
        }
    }
    // Planted at the named marks specifically: the three the brief lists, mid-text, must be
    // reported as residue with the character itself.
    for c in ['[', ']', '*', pilcrow] {
        let line = format!("1\t1\t1\tbefore {c} after");
        let err = validate(&[&line], counts(1, 0)).unwrap_err();
        assert_eq!(
            err,
            ValidationError::Residue {
                line: 1,
                character: c
            }
        );
    }
}

#[test]
fn ordinary_scripture_punctuation_and_diacritics_are_not_residue() {
    // Positive control for the residue refusals: real verse text carries all of these.
    let yoruba = format!(
        "O{}{} d{} {}",
        ch(0x1ECD),
        ch(0x0300),
        ch(0x00E1),
        ch(0x1E63)
    );
    let text = format!(
        "He said, {}Fear not{} (it is written) - and it was so; why? Yes! {}{}",
        ch(0x201C),
        ch(0x201D),
        ch(0xA0), // a no-break space inside the text (WEBBE has some)
        yoruba
    );
    let line = format!("1\t1\t1\t{text}");
    validate(&[&line], counts(1, 0)).expect("punctuation, NBSP and combining marks are accepted");
}

#[test]
fn empty_or_untrimmed_text_is_refused() {
    for text in ["", " ", " leading", "trailing ", "\u{a0}nbsp-led"] {
        let line = format!("1\t1\t1\t{text}");
        let err = validate(&[&line], counts(1, 0)).unwrap_err();
        assert!(
            matches!(err, ValidationError::EmptyOrUntrimmed { line: 1 }),
            "{text:?}: {err:?}"
        );
    }
}

#[test]
fn text_that_is_not_utf8_is_refused() {
    let mut bytes = b"1\t1\t1\tfine\n1\t1\t2\tbad ".to_vec();
    bytes.extend_from_slice(&[0xFF, 0xFE]);
    bytes.extend_from_slice(b" bytes\n");
    let err = validate_asset(gz(&bytes).as_slice(), counts(2, 0)).unwrap_err();
    assert_eq!(err, ValidationError::NotUtf8 { line: 2 });
}

#[test]
fn one_line_may_not_be_longer_than_the_line_cap() {
    let at_cap = "a".repeat(MAX_LINE_BYTES - "1\t1\t1\t".len());
    let over_cap = "a".repeat(MAX_LINE_BYTES - "1\t1\t1\t".len() + 1);
    validate(&[&format!("1\t1\t1\t{at_cap}")], counts(1, 0))
        .expect("a line exactly at the cap passes");
    let err = validate(
        &["1\t1\t1\tok", &format!("1\t1\t2\t{over_cap}")],
        counts(2, 0),
    )
    .unwrap_err();
    assert_eq!(err, ValidationError::LineTooLong { line: 2 });
}

#[test]
fn a_file_without_a_final_newline_is_accepted() {
    let bytes = b"1\t1\t1\tone\n1\t1\t2\ttwo".to_vec();
    validate_asset(gz(&bytes).as_slice(), counts(2, 0)).expect("the last line needs no newline");
}

#[test]
fn crlf_line_endings_are_refused_not_silently_trimmed() {
    let err = validate_asset(gz(b"1\t1\t1\tone\r\n").as_slice(), counts(1, 0)).unwrap_err();
    assert_eq!(
        err,
        ValidationError::Residue {
            line: 1,
            character: '\r'
        }
    );
}

#[test]
fn a_truncated_or_corrupt_gzip_stream_is_refused() {
    let f = fixture("TST", 3, 2);
    validate_asset(f.gz.as_slice(), counts(3, 2))
        .expect("positive control: the intact file passes");

    // Cut off the end: the deflate data and the trailer are incomplete.
    for cut in [1usize, 8, 20, f.gz.len() / 2] {
        let truncated = &f.gz[..f.gz.len() - cut];
        let err = validate_asset(truncated, counts(3, 2)).unwrap_err();
        assert!(
            matches!(err, ValidationError::Decode(_)),
            "cut {cut}: {err:?}"
        );
    }

    // The gzip trailer is CRC-32 then length; flipping a bit in the CRC must be caught.
    let mut bad_crc = f.gz.clone();
    let n = bad_crc.len();
    bad_crc[n - 8] ^= 0xFF;
    let err = validate_asset(bad_crc.as_slice(), counts(3, 2)).unwrap_err();
    assert!(matches!(err, ValidationError::Decode(_)), "{err:?}");

    // Not gzip at all.
    let err = validate_asset(&b"1\t1\t1\tplain text, not gzip\n"[..], counts(1, 0)).unwrap_err();
    assert!(matches!(err, ValidationError::Decode(_)), "{err:?}");
}

#[test]
fn an_empty_input_is_refused() {
    let err = validate_asset(&b""[..], counts(1, 0)).unwrap_err();
    assert!(
        matches!(
            err,
            ValidationError::Decode(_) | ValidationError::VerseCount { .. }
        ),
        "{err:?}"
    );
    let err = validate_asset(gz(b"").as_slice(), counts(1, 0)).unwrap_err();
    assert!(matches!(err, ValidationError::VerseCount { .. }), "{err:?}");
}

#[test]
fn a_decompression_bomb_is_refused_at_the_cap_and_a_big_honest_file_is_not() {
    // The cap this test is written against. If it changes, the row counts below must be re-derived,
    // and this fails to compile until they are.
    const _: () = assert!(MAX_DECOMPRESSED_BYTES == 64 * 1024 * 1024);
    const ROW_BYTES: u64 = 16_000 + "1\t1\t4400\t".len() as u64 + 1;
    const UNDER: u32 = 4_000; // ~64.0 MB, under 67.1 MB
    const OVER: u32 = 4_400; // ~70.4 MB, over it
    const _: () = assert!((UNDER as u64) * ROW_BYTES < MAX_DECOMPRESSED_BYTES);
    const _: () = assert!((OVER as u64) * ROW_BYTES > MAX_DECOMPRESSED_BYTES);

    // Positive control: a file that inflates to almost the cap, every row valid, passes. So the
    // refusal below is the cap and not some other check tripping on a big file.
    let honest = big_asset(UNDER);
    validate_asset(honest.as_slice(), counts(UNDER, 0))
        .expect("a big honest file under the cap passes");
    drop(honest);

    let bomb = big_asset(OVER);
    assert!(
        bomb.len() < 1024 * 1024,
        "premise: the bomb is small on the wire ({} bytes) and large inflated",
        bomb.len()
    );
    let err = validate_asset(bomb.as_slice(), counts(OVER, 0)).unwrap_err();
    assert_eq!(
        err,
        ValidationError::TooLarge {
            limit: MAX_DECOMPRESSED_BYTES
        }
    );
}

#[test]
fn an_endless_line_is_refused_at_the_line_cap_not_buffered() {
    // The per-line buffer is the one place the validator holds inflated text, so it is capped. A
    // single 100 MB line with no newline must be refused as an over-long LINE after the cap's
    // worth of text. With the cap removed the whole line would be read and the answer would be the
    // 64 MiB decompression cap instead (`TooLarge`), so this is the test that fails without it.
    let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    enc.write_all(b"1\t1\t1\t").unwrap();
    let chunk = vec![b'a'; 1024 * 1024];
    for _ in 0..100 {
        enc.write_all(&chunk).unwrap();
    }
    let bomb = enc.finish().unwrap();
    let err = validate_asset(bomb.as_slice(), counts(1, 0)).unwrap_err();
    assert_eq!(err, ValidationError::LineTooLong { line: 1 });
}
