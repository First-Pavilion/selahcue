//! Bible scripture reference parsing (FR-027).
//!
//! Deterministic parsing of typed references: book (canonical name, abbreviation,
//! or numbered form), chapter, single verse, verse range, whole chapter, and
//! multiple references separated by `;`. The parser is **total** — malformed
//! input yields an error, never a panic — because it runs on operator-typed and
//! (later) transcript-derived text.
//!
//! Examples handled: `"Romans 8:28"`, `"Rom 8:28-30"`, `"Ps 23"`,
//! `"Psalm 23:1-6"`, `"1 Corinthians 13:4"`, `"1 Cor 13:4"`, `"Jn 3:16"`,
//! `"John 3:16; 1 Cor 13:4"`.

use std::fmt;

/// A parsed scripture reference.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reference {
    /// Canonical book number, 1 (Genesis) … 66 (Revelation).
    pub book: u8,
    /// Canonical book name (e.g. `"Romans"`, `"1 Corinthians"`).
    pub book_name: &'static str,
    /// Chapter number (1-based).
    pub chapter: u16,
    /// Verse selection. `None` = the whole chapter.
    pub verses: Option<VerseRange>,
}

impl Reference {
    /// Total number of verses selected (0 = whole chapter). Saturating, so a
    /// hand-built out-of-order [`VerseRange`] (fields are public) can never panic.
    pub fn verse_count(&self) -> u16 {
        match self.verses {
            Some(r) => r.end.saturating_sub(r.start).saturating_add(1),
            None => 0,
        }
    }
}

impl fmt::Display for Reference {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.verses {
            None => write!(f, "{} {}", self.book_name, self.chapter),
            Some(VerseRange { start, end }) if start == end => {
                write!(f, "{} {}:{}", self.book_name, self.chapter, start)
            }
            Some(VerseRange { start, end }) => {
                write!(f, "{} {}:{}-{}", self.book_name, self.chapter, start, end)
            }
        }
    }
}

/// An inclusive verse range; `start == end` for a single verse.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct VerseRange {
    pub start: u16,
    pub end: u16,
}

/// Why a single reference could not be parsed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseError {
    Empty,
    /// No book + chapter could be separated (e.g. just `"Romans"`).
    MissingChapter,
    /// The leading book name was not recognised.
    UnknownBook,
    /// The chapter/verse portion was malformed (e.g. `"8:abc"`, `"8:30-10"`).
    BadNumbers,
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            ParseError::Empty => "empty reference",
            ParseError::MissingChapter => "missing chapter",
            ParseError::UnknownBook => "unknown book",
            ParseError::BadNumbers => "malformed chapter/verse",
        };
        f.write_str(s)
    }
}

impl std::error::Error for ParseError {}

/// Parse one or more references separated by `;`, returning every reference that
/// parsed successfully (malformed segments are skipped). Use [`parse_strict`] to
/// require all segments to parse.
pub fn parse(input: &str) -> Vec<Reference> {
    input
        .split(';')
        .filter(|s| !s.trim().is_empty())
        .filter_map(|seg| parse_one(seg).ok())
        .collect()
}

/// Like [`parse`] but returns `Err` on the first unparseable segment.
pub fn parse_strict(input: &str) -> Result<Vec<Reference>, ParseError> {
    input
        .split(';')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(parse_one)
        .collect()
}

/// Parse a single reference (no `;`).
pub fn parse_one(input: &str) -> Result<Reference, ParseError> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err(ParseError::Empty);
    }
    let tokens: Vec<&str> = trimmed.split_whitespace().collect();
    if tokens.len() < 2 {
        // Need at least "<book> <chapter…>".
        return Err(ParseError::MissingChapter);
    }
    let cv = tokens[tokens.len() - 1];
    let book_raw: String = tokens[..tokens.len() - 1].concat();
    let (book, book_name) = lookup_book(&normalize(&book_raw)).ok_or(ParseError::UnknownBook)?;
    let (chapter, verses) = parse_chapter_verse(cv)?;
    Ok(Reference {
        book,
        book_name,
        chapter,
        verses,
    })
}

/// Parse the trailing `<chapter>[:<verse>[-<verse>]]` token.
fn parse_chapter_verse(cv: &str) -> Result<(u16, Option<VerseRange>), ParseError> {
    let mut parts = cv.splitn(2, ':');
    let chapter_str = parts.next().unwrap_or("");
    let chapter: u16 = chapter_str.parse().map_err(|_| ParseError::BadNumbers)?;
    if chapter == 0 {
        return Err(ParseError::BadNumbers);
    }
    match parts.next() {
        None => Ok((chapter, None)), // whole chapter
        Some(verse_part) => {
            let verse_part = verse_part.trim();
            if verse_part.is_empty() {
                return Err(ParseError::BadNumbers);
            }
            let mut vp = verse_part.splitn(2, '-');
            let start: u16 = vp
                .next()
                .unwrap_or("")
                .trim()
                .parse()
                .map_err(|_| ParseError::BadNumbers)?;
            let end: u16 = match vp.next() {
                None => start,
                Some(e) => e.trim().parse().map_err(|_| ParseError::BadNumbers)?,
            };
            if start == 0 || end < start {
                return Err(ParseError::BadNumbers);
            }
            Ok((chapter, Some(VerseRange { start, end })))
        }
    }
}

/// Normalise a book string for lookup: lowercase, keep only ASCII alphanumerics
/// (drops spaces, periods, etc.). `"1 Cor."` → `"1cor"`, `"Song of Solomon"` →
/// `"songofsolomon"`.
fn normalize(s: &str) -> String {
    s.chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .map(|c| c.to_ascii_lowercase())
        .collect()
}

/// Canonical book name for a book number, 1 (Genesis) … 66 (Revelation).
pub fn book_name(number: u8) -> Option<&'static str> {
    BOOKS.iter().find(|b| b.number == number).map(|b| b.name)
}

/// Resolve a normalised book string to `(number, canonical name)`.
fn lookup_book(norm: &str) -> Option<(u8, &'static str)> {
    if norm.is_empty() {
        return None;
    }
    for b in BOOKS {
        if normalize(b.name) == norm || b.aliases.contains(&norm) {
            return Some((b.number, b.name));
        }
    }
    None
}

struct BookDef {
    number: u8,
    name: &'static str,
    /// Pre-normalised aliases (lowercase, alphanumeric-only).
    aliases: &'static [&'static str],
}

/// The 66-book Protestant canon with common abbreviations and numbered variants.
/// Aliases are already in `normalize()` form.
const BOOKS: &[BookDef] = &[
    BookDef {
        number: 1,
        name: "Genesis",
        aliases: &["gen", "ge", "gn"],
    },
    BookDef {
        number: 2,
        name: "Exodus",
        aliases: &["ex", "exo", "exod"],
    },
    BookDef {
        number: 3,
        name: "Leviticus",
        aliases: &["lev", "le", "lv"],
    },
    BookDef {
        number: 4,
        name: "Numbers",
        aliases: &["num", "nu", "nm", "nb"],
    },
    BookDef {
        number: 5,
        name: "Deuteronomy",
        aliases: &["deut", "dt", "de"],
    },
    BookDef {
        number: 6,
        name: "Joshua",
        aliases: &["josh", "jos", "jsh"],
    },
    BookDef {
        number: 7,
        name: "Judges",
        aliases: &["judg", "jdg", "jg", "jdgs"],
    },
    BookDef {
        number: 8,
        name: "Ruth",
        aliases: &["rth", "ru"],
    },
    BookDef {
        number: 9,
        name: "1 Samuel",
        aliases: &[
            "1sam",
            "1sa",
            "1s",
            "isam",
            "isamuel",
            "firstsamuel",
            "1samuel",
        ],
    },
    BookDef {
        number: 10,
        name: "2 Samuel",
        aliases: &[
            "2sam",
            "2sa",
            "2s",
            "iisam",
            "iisamuel",
            "secondsamuel",
            "2samuel",
        ],
    },
    BookDef {
        number: 11,
        name: "1 Kings",
        aliases: &["1kgs", "1ki", "1k", "ikings", "firstkings", "1kings"],
    },
    BookDef {
        number: 12,
        name: "2 Kings",
        aliases: &["2kgs", "2ki", "2k", "iikings", "secondkings", "2kings"],
    },
    BookDef {
        number: 13,
        name: "1 Chronicles",
        aliases: &[
            "1chron",
            "1chr",
            "1ch",
            "ichronicles",
            "firstchronicles",
            "1chronicles",
        ],
    },
    BookDef {
        number: 14,
        name: "2 Chronicles",
        aliases: &[
            "2chron",
            "2chr",
            "2ch",
            "iichronicles",
            "secondchronicles",
            "2chronicles",
        ],
    },
    BookDef {
        number: 15,
        name: "Ezra",
        aliases: &["ezr", "ez"],
    },
    BookDef {
        number: 16,
        name: "Nehemiah",
        aliases: &["neh", "ne"],
    },
    BookDef {
        number: 17,
        name: "Esther",
        aliases: &["est", "esth", "es"],
    },
    BookDef {
        number: 18,
        name: "Job",
        aliases: &["jb"],
    },
    BookDef {
        number: 19,
        name: "Psalms",
        aliases: &["ps", "psa", "psalm", "pss", "psm"],
    },
    BookDef {
        number: 20,
        name: "Proverbs",
        aliases: &["prov", "pro", "pr", "prv"],
    },
    BookDef {
        number: 21,
        name: "Ecclesiastes",
        aliases: &["eccl", "ecc", "ec", "qoh"],
    },
    BookDef {
        number: 22,
        name: "Song of Solomon",
        aliases: &["song", "songofsongs", "sos", "sng", "so", "canticles"],
    },
    BookDef {
        number: 23,
        name: "Isaiah",
        aliases: &["isa", "is"],
    },
    BookDef {
        number: 24,
        name: "Jeremiah",
        aliases: &["jer", "je", "jr"],
    },
    BookDef {
        number: 25,
        name: "Lamentations",
        aliases: &["lam", "la"],
    },
    BookDef {
        number: 26,
        name: "Ezekiel",
        aliases: &["ezek", "eze", "ezk"],
    },
    BookDef {
        number: 27,
        name: "Daniel",
        aliases: &["dan", "da", "dn"],
    },
    BookDef {
        number: 28,
        name: "Hosea",
        aliases: &["hos", "ho"],
    },
    BookDef {
        number: 29,
        name: "Joel",
        aliases: &["joe", "jl"],
    },
    BookDef {
        number: 30,
        name: "Amos",
        aliases: &["am", "amo"],
    },
    BookDef {
        number: 31,
        name: "Obadiah",
        aliases: &["obad", "ob"],
    },
    BookDef {
        number: 32,
        name: "Jonah",
        aliases: &["jnh", "jon"],
    },
    BookDef {
        number: 33,
        name: "Micah",
        aliases: &["mic", "mc"],
    },
    BookDef {
        number: 34,
        name: "Nahum",
        aliases: &["nah", "na"],
    },
    BookDef {
        number: 35,
        name: "Habakkuk",
        aliases: &["hab", "hb"],
    },
    BookDef {
        number: 36,
        name: "Zephaniah",
        aliases: &["zeph", "zep", "zp"],
    },
    BookDef {
        number: 37,
        name: "Haggai",
        aliases: &["hag", "hg"],
    },
    BookDef {
        number: 38,
        name: "Zechariah",
        aliases: &["zech", "zec", "zc"],
    },
    BookDef {
        number: 39,
        name: "Malachi",
        aliases: &["mal", "ml"],
    },
    BookDef {
        number: 40,
        name: "Matthew",
        aliases: &["matt", "mat", "mt"],
    },
    BookDef {
        number: 41,
        name: "Mark",
        aliases: &["mrk", "mk", "mr"],
    },
    BookDef {
        number: 42,
        name: "Luke",
        aliases: &["luk", "lk"],
    },
    BookDef {
        number: 43,
        name: "John",
        aliases: &["jhn", "jn", "joh"],
    },
    BookDef {
        number: 44,
        name: "Acts",
        aliases: &["act", "ac"],
    },
    BookDef {
        number: 45,
        name: "Romans",
        aliases: &["rom", "ro", "rm"],
    },
    BookDef {
        number: 46,
        name: "1 Corinthians",
        aliases: &[
            "1cor",
            "1co",
            "1c",
            "icorinthians",
            "firstcorinthians",
            "1corinthians",
        ],
    },
    BookDef {
        number: 47,
        name: "2 Corinthians",
        aliases: &[
            "2cor",
            "2co",
            "2c",
            "iicorinthians",
            "secondcorinthians",
            "2corinthians",
        ],
    },
    BookDef {
        number: 48,
        name: "Galatians",
        aliases: &["gal", "ga"],
    },
    BookDef {
        number: 49,
        name: "Ephesians",
        aliases: &["eph", "ephes"],
    },
    BookDef {
        number: 50,
        name: "Philippians",
        aliases: &["phil", "php", "pp"],
    },
    BookDef {
        number: 51,
        name: "Colossians",
        aliases: &["col", "co"],
    },
    BookDef {
        number: 52,
        name: "1 Thessalonians",
        aliases: &[
            "1thess",
            "1thes",
            "1th",
            "ithessalonians",
            "firstthessalonians",
            "1thessalonians",
        ],
    },
    BookDef {
        number: 53,
        name: "2 Thessalonians",
        aliases: &[
            "2thess",
            "2thes",
            "2th",
            "iithessalonians",
            "secondthessalonians",
            "2thessalonians",
        ],
    },
    BookDef {
        number: 54,
        name: "1 Timothy",
        aliases: &["1tim", "1ti", "1t", "itimothy", "firsttimothy", "1timothy"],
    },
    BookDef {
        number: 55,
        name: "2 Timothy",
        aliases: &[
            "2tim",
            "2ti",
            "2t",
            "iitimothy",
            "secondtimothy",
            "2timothy",
        ],
    },
    BookDef {
        number: 56,
        name: "Titus",
        aliases: &["tit", "ti"],
    },
    BookDef {
        number: 57,
        name: "Philemon",
        aliases: &["philem", "phm", "pm"],
    },
    BookDef {
        number: 58,
        name: "Hebrews",
        aliases: &["heb", "hbr"],
    },
    BookDef {
        number: 59,
        name: "James",
        aliases: &["jas", "jm", "jam"],
    },
    BookDef {
        number: 60,
        name: "1 Peter",
        aliases: &["1pet", "1pe", "1p", "ipeter", "firstpeter", "1peter"],
    },
    BookDef {
        number: 61,
        name: "2 Peter",
        aliases: &["2pet", "2pe", "2p", "iipeter", "secondpeter", "2peter"],
    },
    BookDef {
        number: 62,
        name: "1 John",
        aliases: &["1jn", "1jo", "1jhn", "1j", "ijohn", "firstjohn", "1john"],
    },
    BookDef {
        number: 63,
        name: "2 John",
        aliases: &["2jn", "2jo", "2jhn", "2j", "iijohn", "secondjohn", "2john"],
    },
    BookDef {
        number: 64,
        name: "3 John",
        aliases: &["3jn", "3jo", "3jhn", "3j", "iiijohn", "thirdjohn", "3john"],
    },
    BookDef {
        number: 65,
        name: "Jude",
        aliases: &["jud", "jd"],
    },
    BookDef {
        number: 66,
        name: "Revelation",
        aliases: &["rev", "re", "rv", "apocalypse"],
    },
];

// Black-box parser tests live in `tests/test_scripture.rs`. The one white-box
// test below stays inline because it reads the private `BOOKS` table directly —
// exactly the documented exception for tests that need crate-private internals.
#[cfg(test)]
mod tests {
    use super::{parse_one, BOOKS};

    #[test]
    fn all_66_books_resolve_by_canonical_name() {
        for b in BOOKS {
            let input = format!("{} 1:1", b.name);
            let parsed = parse_one(&input).unwrap_or_else(|_| panic!("failed: {}", b.name));
            assert_eq!(parsed.book, b.number, "wrong number for {}", b.name);
        }
        assert_eq!(BOOKS.len(), 66);
    }
}
