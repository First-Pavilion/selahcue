//! Install-time validation of a translation asset (feature `installed`).
//!
//! A downloaded file has passed its SHA-256 check by the time it is validated, but the digest only
//! says "these are the bytes the catalogue named". This is the second line of defence, and it does
//! for a downloaded asset what `build.rs` does for a bundled one: it refuses anything that is not
//! shaped like a Bible, even if the catalogue (or the build that produced the digest) was wrong.
//!
//! The asset is read as a stream and never held whole: the gzip decoder is capped at 16 MiB of
//! output (a decompression bomb is refused at the cap, not after it has been inflated), and one
//! line at a time is held, capped at 16 KiB. Every line must be a verse row in the same grammar the
//! bundled assets use (`tsv_row::parse_row`, shared with `build.rs` and the runtime decoder), and:
//!
//! - the input is exactly ONE gzip member: any byte after its end is refused, so the digest cannot
//!   vouch for a file that is also a valid archive of something else;
//! - the book is 1 to 66, the chapter and verse are at least 1;
//! - rows are strictly ascending by (book, chapter, verse), so no duplicates and no reordering
//!   (gaps are fine: translations omit verses);
//! - there are no more rows than the caller's verse counts allow (checked as each row is read, so a
//!   file that claims fewer verses than it holds is stopped early);
//! - the text is non-empty, has no leading or trailing whitespace, and contains none of
//!   `[ ] \u{b6} * | \`, no control character (C0, DEL or C1), and none of the invisible or
//!   direction-changing characters listed at [`refused_character`] (the markup residue A1's
//!   converter also refuses, and more);
//! - the Old Testament (books 1 to 39) and New Testament (40 to 66) verse counts equal the
//!   caller's.
//!
//! A refusal names the 1-based line number where there is one. Nothing here touches the disk.

use std::io::{BufRead, BufReader, Read};

use flate2::bufread::GzDecoder;

use crate::{tsv_row, Verse};

/// The most bytes the gzip decoder may produce for one downloaded asset: 16 MiB, about three times
/// the largest real asset (5.6 MB inflated). The cap counts BYTES, and the registry keeps up to
/// three decoded indexes, so a looser cap lets one pinned file cost far more memory per index than
/// any real Bible does (at 64 MiB a hostile asset cost 64 MiB per index).
pub const MAX_DECOMPRESSED_BYTES: u64 = 16 * 1024 * 1024;

/// The longest one line (one verse row, without its newline) may be. The longest real verse is
/// well under 2 KiB, so this is generous; its job is bounding the line buffer.
pub const MAX_LINE_BYTES: usize = 16 * 1024;

/// How many verses a testament holds.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Counts {
    /// Rows whose book is 1 to 39.
    pub ot: u32,
    /// Rows whose book is 40 to 66.
    pub nt: u32,
}

impl Counts {
    /// `ot + nt`.
    pub fn total(self) -> u64 {
        u64::from(self.ot) + u64::from(self.nt)
    }
}

/// Why an asset was refused. One variant per reason; `line` is 1-based.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationError {
    /// Not a valid gzip stream: not gzip at all, truncated, or its checksum does not match.
    Decode(String),
    /// A valid gzip member is followed by more bytes (trailing data, or a second member).
    TrailingData,
    /// The stream inflates past [`MAX_DECOMPRESSED_BYTES`].
    TooLarge {
        limit: u64,
    },
    NotUtf8 {
        line: u64,
    },
    /// A line is longer than [`MAX_LINE_BYTES`].
    LineTooLong {
        line: u64,
    },
    /// Not `book<TAB>chapter<TAB>verse<TAB>text` with whole numbers (a blank line included).
    BadRow {
        line: u64,
    },
    BookOutOfRange {
        line: u64,
        book: u8,
    },
    ZeroChapterOrVerse {
        line: u64,
    },
    /// A row is not strictly after the one before it (a duplicate or out of order).
    NotAscending {
        line: u64,
    },
    /// The text holds a markup mark, a control character or an invisible or direction-changing one.
    Residue {
        line: u64,
        character: char,
    },
    /// The text is empty or has leading or trailing whitespace.
    EmptyOrUntrimmed {
        line: u64,
    },
    /// The asset holds more verse rows than the verse counts it was checked against allow.
    TooManyRows {
        limit: u64,
    },
    /// The testament counts differ from what the catalogue pins.
    VerseCount {
        expected: Counts,
        actual: Counts,
    },
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ValidationError::Decode(e) => write!(
                f,
                "the file is not a valid gzip stream (not gzip, truncated, or a bad checksum): {e}"
            ),
            ValidationError::TrailingData => {
                write!(f, "the file has bytes after the end of its gzip stream")
            }
            ValidationError::TooLarge { limit } => {
                write!(f, "the file inflates past the {limit}-byte limit")
            }
            ValidationError::NotUtf8 { line } => write!(f, "line {line} is not valid UTF-8"),
            ValidationError::LineTooLong { line } => {
                write!(f, "line {line} is longer than {MAX_LINE_BYTES} bytes")
            }
            ValidationError::BadRow { line } => write!(f, "line {line} is not a verse row"),
            ValidationError::BookOutOfRange { line, book } => {
                write!(f, "line {line} names book {book}, outside 1 to 66")
            }
            ValidationError::ZeroChapterOrVerse { line } => {
                write!(f, "line {line} has chapter or verse 0")
            }
            ValidationError::NotAscending { line } => {
                write!(f, "line {line} is not after the line before it")
            }
            ValidationError::Residue { line, character } => {
                write!(
                    f,
                    "line {line} contains {character:?}, which verse text must not"
                )
            }
            ValidationError::EmptyOrUntrimmed { line } => {
                write!(f, "line {line} has empty or untrimmed text")
            }
            ValidationError::TooManyRows { limit } => {
                write!(f, "the file holds more than the {limit} verses it may")
            }
            ValidationError::VerseCount { expected, actual } => write!(
                f,
                "verse counts are OT {} / NT {}, the catalogue pins OT {} / NT {}",
                actual.ot, actual.nt, expected.ot, expected.nt
            ),
        }
    }
}

impl std::error::Error for ValidationError {}

/// One row that passed every check.
pub struct Row<'a> {
    pub book: u8,
    pub chapter: u16,
    pub verse: u16,
    pub text: &'a str,
}

/// Whether verse text may not contain `c`. Refused: the markup marks A1's converter refuses
/// (`[ ] * |` and `\`) and the pilcrow; every control character (C0, DEL and the C1 range
/// U+0080 to U+009F, which includes NEL, U+0085); the line and paragraph separators U+2028 and
/// U+2029; the bidirectional embeddings, overrides and isolates (U+202A to U+202E and U+2066 to
/// U+2069), which can make text read backwards; and the invisible characters zero-width space
/// (U+200B), word joiner (U+2060) and byte-order mark (U+FEFF). Allowed on purpose: the
/// no-break space (WEBBE has some), and the zero-width non-joiner and joiner (U+200C, U+200D),
/// which a script a future translation uses may need. The real A1 assets contain none of the
/// refused ones.
pub fn refused_character(c: char) -> bool {
    const PILCROW: char = '\u{b6}';
    matches!(c, '[' | ']' | '*' | '|' | '\\' | PILCROW)
        || c < ' '
        || ('\u{7f}'..='\u{9f}').contains(&c)
        || matches!(
            c,
            '\u{2028}'
                | '\u{2029}'
                | '\u{202a}'..='\u{202e}'
                | '\u{2066}'..='\u{2069}'
                | '\u{200b}'
                | '\u{2060}'
                | '\u{feff}'
        )
}

fn residue(text: &str) -> Option<char> {
    text.chars().find(|&c| refused_character(c))
}

/// Read `compressed` as ONE gzip member of verse rows, applying every check except the expected
/// counts, calling `on_row` for each row that passes, and return the counts found. At most
/// `max_rows` rows are read: the next one is refused as [`ValidationError::TooManyRows`]. Streams:
/// only one line is held at a time, and the decoder stops at [`MAX_DECOMPRESSED_BYTES`].
pub fn scan<R: Read>(
    compressed: R,
    max_rows: u64,
    mut on_row: impl FnMut(Row<'_>),
) -> Result<Counts, ValidationError> {
    let mut source = BufReader::new(compressed);
    let counts = scan_member(&mut source, max_rows, &mut on_row)?;
    // The member is over (its checksum has been checked). Nothing may follow it.
    match source.fill_buf() {
        Ok([]) => Ok(counts),
        Ok(_) => Err(ValidationError::TrailingData),
        Err(e) => Err(ValidationError::Decode(e.to_string())),
    }
}

fn scan_member<R: BufRead>(
    source: &mut R,
    max_rows: u64,
    on_row: &mut impl FnMut(Row<'_>),
) -> Result<Counts, ValidationError> {
    // One byte past the cap: reading it is how an asset EXACTLY at the cap (accepted) is told
    // apart from one that goes on (refused).
    let decoder = GzDecoder::new(source).take(MAX_DECOMPRESSED_BYTES + 1);
    let mut reader = BufReader::new(decoder);
    let mut buf: Vec<u8> = Vec::with_capacity(1024);
    let mut line: u64 = 0;
    let mut rows: u64 = 0;
    let mut inflated: u64 = 0;
    let mut previous: Option<(u8, u16, u16)> = None;
    let mut counts = Counts::default();

    loop {
        buf.clear();
        // At most one byte more than the longest allowed line plus its newline can be read, so a
        // line with no newline in sight is bounded here and not by the decompression cap.
        let n = (&mut reader)
            .take(MAX_LINE_BYTES as u64 + 1)
            .read_until(b'\n', &mut buf)
            .map_err(|e| ValidationError::Decode(e.to_string()))?;
        if n == 0 {
            break;
        }
        inflated += n as u64;
        if inflated > MAX_DECOMPRESSED_BYTES {
            return Err(ValidationError::TooLarge {
                limit: MAX_DECOMPRESSED_BYTES,
            });
        }
        line += 1;

        let content = match buf.last() {
            Some(b'\n') => &buf[..buf.len() - 1],
            // No newline: either the last line of the file, or a line longer than the cap.
            _ if buf.len() > MAX_LINE_BYTES => return Err(ValidationError::LineTooLong { line }),
            _ => &buf[..],
        };
        let text_line =
            std::str::from_utf8(content).map_err(|_| ValidationError::NotUtf8 { line })?;
        let (book, chapter, verse, text) =
            tsv_row::parse_row(text_line).ok_or(ValidationError::BadRow { line })?;

        if !(1..=66).contains(&book) {
            return Err(ValidationError::BookOutOfRange { line, book });
        }
        if chapter == 0 || verse == 0 {
            return Err(ValidationError::ZeroChapterOrVerse { line });
        }
        let key = (book, chapter, verse);
        if previous.is_some_and(|p| p >= key) {
            return Err(ValidationError::NotAscending { line });
        }
        previous = Some(key);
        if let Some(character) = residue(text) {
            return Err(ValidationError::Residue { line, character });
        }
        if text.is_empty() || text != text.trim() {
            return Err(ValidationError::EmptyOrUntrimmed { line });
        }

        rows += 1;
        if rows > max_rows {
            return Err(ValidationError::TooManyRows { limit: max_rows });
        }
        if book <= 39 {
            counts.ot += 1;
        } else {
            counts.nt += 1;
        }
        on_row(Row {
            book,
            chapter,
            verse,
            text,
        });
    }
    Ok(counts)
}

/// Validate `compressed` and require its testament counts to equal `expected`. A file with more
/// rows than `expected` allows is stopped at the first extra row.
pub fn validate_asset<R: Read>(compressed: R, expected: Counts) -> Result<(), ValidationError> {
    let actual = scan(compressed, expected.total(), |_| {})?;
    if actual == expected {
        Ok(())
    } else {
        Err(ValidationError::VerseCount { expected, actual })
    }
}

/// Decode an installed asset into its verse index, applying the same checks as install did (the
/// file may have been touched since) and the verse counts the install recorded: no more rows than
/// they allow, and exactly them.
pub(crate) fn decode_verses(
    compressed: &[u8],
    expected: Counts,
) -> Result<Vec<Verse>, ValidationError> {
    let mut verses = Vec::with_capacity(expected.total().min(200_000) as usize);
    let actual = scan(compressed, expected.total(), |row| {
        verses.push(Verse {
            book: row.book,
            chapter: row.chapter,
            verse: row.verse,
            text: row.text.to_string(),
        });
    })?;
    if actual != expected {
        return Err(ValidationError::VerseCount { expected, actual });
    }
    Ok(verses)
}
