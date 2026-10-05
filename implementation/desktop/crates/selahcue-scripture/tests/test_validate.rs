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
    refused_character, scan, validate_asset, Counts, ValidationError, MAX_DECOMPRESSED_BYTES,
    MAX_LINE_BYTES,
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
    // The file holds 5 rows (3 OT, 2 NT). Counts that allow at least 5 rows read the whole file and
    // disagree on the split; counts that allow fewer stop at the first extra row.
    for (ot, nt) in [(4, 2), (3, 3), (2, 3), (5, 0), (0, 5)] {
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
    for (ot, nt) in [(2, 2), (3, 1), (0, 0), (1, 1)] {
        let err = validate_asset(f.gz.as_slice(), counts(ot, nt)).unwrap_err();
        assert_eq!(
            err,
            ValidationError::TooManyRows {
                limit: u64::from(ot + nt)
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
    const _: () = assert!(MAX_DECOMPRESSED_BYTES == 16 * 1024 * 1024);
    const ROW_BYTES: u64 = 16_000 + "1\t1\t1100\t".len() as u64 + 1;
    const UNDER: u32 = 1_000; // ~16.0 MB, under 16.8 MB
    const OVER: u32 = 1_100; // ~17.6 MB, over it
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
    // 16 MiB decompression cap instead (`TooLarge`), so this is the test that fails without it.
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

// ---------------------------------------------------------------------------------------------
// Round 2: one gzip member only, a row bound, and the stricter character refusal.
// ---------------------------------------------------------------------------------------------

/// Gzip of `lines` as ONE member, then `tail` appended raw.
fn asset_then(lines: &[&str], tail: &[u8]) -> Vec<u8> {
    let mut bytes = asset(lines);
    bytes.extend_from_slice(tail);
    bytes
}

#[test]
fn a_second_gzip_member_after_the_first_is_refused() {
    // Positive control: the first member alone is a valid asset, so what is refused below is the
    // extra bytes and nothing else.
    validate_asset(asset(&["1\t1\t1\tone"]).as_slice(), counts(1, 0)).expect("one member passes");

    let second = asset(&["1\t1\t2\ttwo"]);
    let both = asset_then(&["1\t1\t1\tone"], &second);
    let err = validate_asset(both.as_slice(), counts(1, 0)).unwrap_err();
    assert_eq!(err, ValidationError::TrailingData);
    // Even when the second member would make the counts come out "right", the file is refused:
    // the digest must not be able to vouch for a file that is two archives.
    let err = validate_asset(both.as_slice(), counts(2, 0)).unwrap_err();
    assert_eq!(err, ValidationError::TrailingData);
}

#[test]
fn bytes_after_the_end_of_the_gzip_member_are_refused() {
    for (name, tail) in [
        ("one zero byte", &[0u8][..]),
        ("garbage text", &b"not gzip at all"[..]),
        ("a gzip header alone", &[0x1f, 0x8b, 8, 0][..]),
        ("a newline", &b"\n"[..]),
    ] {
        let bytes = asset_then(&["1\t1\t1\tone"], tail);
        let err = validate_asset(bytes.as_slice(), counts(1, 0)).unwrap_err();
        assert_eq!(err, ValidationError::TrailingData, "{name}");
    }
}

#[test]
fn the_trailing_data_message_says_what_is_wrong() {
    // The text used to say "not gzip, truncated, or a bad checksum", which is false for a file
    // whose first member is perfectly good.
    let text = ValidationError::TrailingData.to_string();
    assert!(
        text.contains("after the end of its gzip stream"),
        "unhelpful: {text}"
    );
}

#[test]
fn more_rows_than_allowed_stops_at_the_first_extra_row() {
    let lines: Vec<String> = (1..=50u32).map(|v| format!("1\t1\t{v}\tx")).collect();
    let refs: Vec<&str> = lines.iter().map(String::as_str).collect();
    validate(&refs, counts(50, 0)).expect("positive control: exactly the allowed rows pass");

    let err = validate(&refs, counts(10, 0)).unwrap_err();
    assert_eq!(err, ValidationError::TooManyRows { limit: 10 });

    // The bound bites WHILE reading, not after: the callback sees exactly `limit` rows and no
    // more, so a file with millions of rows never has them all handed to a caller that keeps them.
    let mut seen = 0u64;
    let err = scan(asset(&refs).as_slice(), 10, |_| seen += 1).unwrap_err();
    assert_eq!(err, ValidationError::TooManyRows { limit: 10 });
    assert_eq!(seen, 10, "rows delivered before the refusal");
}

#[test]
fn a_zero_row_budget_refuses_the_first_row() {
    let mut seen = 0u64;
    let err = scan(asset(&["1\t1\t1\tone"]).as_slice(), 0, |_| seen += 1).unwrap_err();
    assert_eq!(err, ValidationError::TooManyRows { limit: 0 });
    assert_eq!(seen, 0);
}

#[test]
fn the_row_bound_is_checked_before_the_verse_count() {
    // A file with too many rows reports the bound, which is the cheaper and earlier fact; a file
    // with too few rows reports the counts.
    let two = ["1\t1\t1\ta", "1\t1\t2\tb"];
    assert_eq!(
        validate(&two, counts(1, 0)).unwrap_err(),
        ValidationError::TooManyRows { limit: 1 }
    );
    assert!(matches!(
        validate(&two, counts(3, 0)).unwrap_err(),
        ValidationError::VerseCount { .. }
    ));
}

/// Every character the stricter refusal adds, with the reason it is there.
fn newly_refused() -> Vec<(u32, &'static str)> {
    let mut v = vec![
        (0x7F, "DEL"),
        (0x80, "first C1 control"),
        (0x85, "NEL"),
        (0x9F, "last C1 control"),
        (0x2028, "line separator"),
        (0x2029, "paragraph separator"),
        (0x200B, "zero-width space"),
        (0x2060, "word joiner"),
        (0xFEFF, "byte-order mark"),
    ];
    for c in 0x202A..=0x202E {
        v.push((c, "bidi embedding or override"));
    }
    for c in 0x2066..=0x2069 {
        v.push((c, "bidi isolate"));
    }
    v
}

#[test]
fn invisible_and_direction_changing_characters_are_refused_wherever_they_hide() {
    for (code, why) in newly_refused() {
        let c = ch(code);
        assert!(refused_character(c), "U+{code:04X} ({why}) must be refused");
        for position in ["start", "middle", "end"] {
            let text = match position {
                "start" => format!("{c}word and more"),
                "middle" => format!("word {c} and more"),
                _ => format!("word and more{c}"),
            };
            let line = format!("1\t1\t1\t{text}");
            let err = validate(&[&line], counts(1, 0)).unwrap_err();
            assert_eq!(
                err,
                ValidationError::Residue {
                    line: 1,
                    character: c
                },
                "U+{code:04X} ({why}) at the {position}"
            );
        }
    }
}

#[test]
fn the_whole_c1_range_is_refused_and_its_neighbours_are_not() {
    for code in 0x7Fu32..=0x9F {
        assert!(
            refused_character(ch(code)),
            "U+{code:04X} is in DEL..=C1 and must be refused"
        );
    }
    // The characters just outside the range, and the ones that are allowed on purpose.
    for (code, why) in [
        (0x7E, "tilde"),
        (0xA0, "no-break space"),
        (0xA1, "inverted exclamation mark"),
        (0x200C, "zero-width non-joiner"),
        (0x200D, "zero-width joiner"),
        (0x2027, "hyphenation point"),
        (0x202F, "narrow no-break space"),
        (0x2065, "unassigned, between the refused ranges"),
        (0x206A, "inhibit symmetric swapping, outside the isolates"),
    ] {
        assert!(
            !refused_character(ch(code)),
            "U+{code:04X} ({why}) must not be refused"
        );
    }
}

#[test]
fn zero_width_joiners_pass_inside_text() {
    // A script that needs ZWNJ or ZWJ (Persian, Indic) must still install. U+200C and U+200D
    // are the characters the stricter refusal deliberately leaves alone.
    let text = format!("a{}b{}c", ch(0x200C), ch(0x200D));
    let line = format!("1\t1\t1\t{text}");
    validate(&[&line], counts(1, 0)).expect("ZWNJ and ZWJ are accepted");
}
