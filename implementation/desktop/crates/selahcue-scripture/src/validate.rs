//! Install-time validation of a translation asset (feature `installed`).
//!
//! A downloaded file has passed its SHA-256 check by the time it is validated, but the digest only
//! says "these are the bytes the catalogue named". This is the second line of defence, and it does
//! for a downloaded asset what `build.rs` does for a bundled one: it refuses anything that is not
//! shaped like a Bible, even if the catalogue (or the build that produced the digest) was wrong.
//!
//! The asset is read as a stream and never held whole: the gzip decoder is capped at 64 MiB of
//! output (a decompression bomb is refused at the cap, not after it has been inflated), and one
//! line at a time is held, capped at 16 KiB. Every line must be a verse row in the same grammar the
//! bundled assets use (`tsv_row::parse_row`, shared with `build.rs` and the runtime decoder), and:
//!
//! - the book is 1 to 66, the chapter and verse are at least 1;
//! - rows are strictly ascending by (book, chapter, verse), so no duplicates and no reordering
//!   (gaps are fine: translations omit verses);
//! - the text is non-empty, has no leading or trailing whitespace, and contains none of
//!   `[ ] \u{b6} * | \` nor a control character (the markup residue A1's converter also refuses);
//! - the Old Testament (books 1 to 39) and New Testament (40 to 66) verse counts equal the
//!   catalogue entry's.
//!
//! A refusal names the 1-based line number where there is one. Nothing here touches the disk.

use std::io::{BufRead, BufReader, Read};

use flate2::read::GzDecoder;

use crate::{tsv_row, Verse};

/// The most bytes the gzip decoder may produce for one asset: 64 MiB, the same ceiling `build.rs`
/// puts on a bundled asset. Real assets inflate to about 4.5 MB.
pub const MAX_DECOMPRESSED_BYTES: u64 = 64 * 1024 * 1024;

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

/// Why an asset was refused. One variant per reason; `line` is 1-based.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationError {
    /// Not a gzip stream, truncated, or its checksum does not match.
    Decode(String),
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
    /// The text holds a markup mark or control character.
    Residue {
        line: u64,
        character: char,
    },
    /// The text is empty or has leading or trailing whitespace.
    EmptyOrUntrimmed {
        line: u64,
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
            ValidationError::Decode(e) => write!(f, "the file is not a complete gzip stream: {e}"),
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

/// The characters verse text must not contain: the markup marks A1's converter refuses (`[ ] * |`
/// and `\`) and the pilcrow, plus any ASCII control character.
fn residue(text: &str) -> Option<char> {
    const PILCROW: char = '\u{b6}';
    text.chars()
        .find(|&c| matches!(c, '[' | ']' | '*' | '|' | '\\' | PILCROW) || c < ' ' || c == '\u{7f}')
}

/// Read `compressed` as a gzip stream of verse rows, applying every check except the expected
/// counts, calling `on_row` for each row that passes, and return the counts found. Streams: only
/// one line is held at a time, and the decoder stops at [`MAX_DECOMPRESSED_BYTES`].
pub fn scan<R: Read>(
    compressed: R,
    mut on_row: impl FnMut(Row<'_>),
) -> Result<Counts, ValidationError> {
    // One byte past the cap: reading it is how an asset EXACTLY at the cap (accepted) is told
    // apart from one that goes on (refused).
    let decoder = GzDecoder::new(compressed).take(MAX_DECOMPRESSED_BYTES + 1);
    let mut reader = BufReader::new(decoder);
    let mut buf: Vec<u8> = Vec::with_capacity(1024);
    let mut line: u64 = 0;
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

/// Validate `compressed` and require its testament counts to equal `expected`.
pub fn validate_asset<R: Read>(compressed: R, expected: Counts) -> Result<(), ValidationError> {
    let actual = scan(compressed, |_| {})?;
    if actual == expected {
        Ok(())
    } else {
        Err(ValidationError::VerseCount { expected, actual })
    }
}

/// Decode an installed asset into its verse index, applying the same checks as install did (the
/// file may have been touched since). `size_hint` is the expected verse count, for allocation only.
pub(crate) fn decode_verses(
    compressed: &[u8],
    size_hint: usize,
) -> Result<Vec<Verse>, ValidationError> {
    let mut verses = Vec::with_capacity(size_hint);
    scan(compressed, |row| {
        verses.push(Verse {
            book: row.book,
            chapter: row.chapter,
            verse: row.verse,
            text: row.text.to_string(),
        });
    })?;
    Ok(verses)
}
