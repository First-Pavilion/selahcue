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
    BookDef { number: 1, name: "Genesis", aliases: &["gen", "ge", "gn"] },
    BookDef { number: 2, name: "Exodus", aliases: &["ex", "exo", "exod"] },
    BookDef { number: 3, name: "Leviticus", aliases: &["lev", "le", "lv"] },
    BookDef { number: 4, name: "Numbers", aliases: &["num", "nu", "nm", "nb"] },
    BookDef { number: 5, name: "Deuteronomy", aliases: &["deut", "dt", "de"] },
    BookDef { number: 6, name: "Joshua", aliases: &["josh", "jos", "jsh"] },
    BookDef { number: 7, name: "Judges", aliases: &["judg", "jdg", "jg", "jdgs"] },
    BookDef { number: 8, name: "Ruth", aliases: &["rth", "ru"] },
    BookDef { number: 9, name: "1 Samuel", aliases: &["1sam", "1sa", "1s", "isam", "isamuel", "firstsamuel", "1samuel"] },
    BookDef { number: 10, name: "2 Samuel", aliases: &["2sam", "2sa", "2s", "iisam", "iisamuel", "secondsamuel", "2samuel"] },
    BookDef { number: 11, name: "1 Kings", aliases: &["1kgs", "1ki", "1k", "ikings", "firstkings", "1kings"] },
    BookDef { number: 12, name: "2 Kings", aliases: &["2kgs", "2ki", "2k", "iikings", "secondkings", "2kings"] },
    BookDef { number: 13, name: "1 Chronicles", aliases: &["1chron", "1chr", "1ch", "ichronicles", "firstchronicles", "1chronicles"] },
    BookDef { number: 14, name: "2 Chronicles", aliases: &["2chron", "2chr", "2ch", "iichronicles", "secondchronicles", "2chronicles"] },
    BookDef { number: 15, name: "Ezra", aliases: &["ezr", "ez"] },
    BookDef { number: 16, name: "Nehemiah", aliases: &["neh", "ne"] },
    BookDef { number: 17, name: "Esther", aliases: &["est", "esth", "es"] },
    BookDef { number: 18, name: "Job", aliases: &["jb"] },
    BookDef { number: 19, name: "Psalms", aliases: &["ps", "psa", "psalm", "pss", "psm"] },
    BookDef { number: 20, name: "Proverbs", aliases: &["prov", "pro", "pr", "prv"] },
    BookDef { number: 21, name: "Ecclesiastes", aliases: &["eccl", "ecc", "ec", "qoh"] },
    BookDef { number: 22, name: "Song of Solomon", aliases: &["song", "songofsongs", "sos", "sng", "so", "canticles"] },
    BookDef { number: 23, name: "Isaiah", aliases: &["isa", "is"] },
    BookDef { number: 24, name: "Jeremiah", aliases: &["jer", "je", "jr"] },
    BookDef { number: 25, name: "Lamentations", aliases: &["lam", "la"] },
    BookDef { number: 26, name: "Ezekiel", aliases: &["ezek", "eze", "ezk"] },
    BookDef { number: 27, name: "Daniel", aliases: &["dan", "da", "dn"] },
    BookDef { number: 28, name: "Hosea", aliases: &["hos", "ho"] },
    BookDef { number: 29, name: "Joel", aliases: &["joe", "jl"] },
    BookDef { number: 30, name: "Amos", aliases: &["am", "amo"] },
    BookDef { number: 31, name: "Obadiah", aliases: &["obad", "ob"] },
    BookDef { number: 32, name: "Jonah", aliases: &["jnh", "jon"] },
    BookDef { number: 33, name: "Micah", aliases: &["mic", "mc"] },
    BookDef { number: 34, name: "Nahum", aliases: &["nah", "na"] },
    BookDef { number: 35, name: "Habakkuk", aliases: &["hab", "hb"] },
    BookDef { number: 36, name: "Zephaniah", aliases: &["zeph", "zep", "zp"] },
    BookDef { number: 37, name: "Haggai", aliases: &["hag", "hg"] },
    BookDef { number: 38, name: "Zechariah", aliases: &["zech", "zec", "zc"] },
    BookDef { number: 39, name: "Malachi", aliases: &["mal", "ml"] },
    BookDef { number: 40, name: "Matthew", aliases: &["matt", "mat", "mt"] },
    BookDef { number: 41, name: "Mark", aliases: &["mrk", "mk", "mr"] },
    BookDef { number: 42, name: "Luke", aliases: &["luk", "lk"] },
    BookDef { number: 43, name: "John", aliases: &["jhn", "jn", "joh"] },
    BookDef { number: 44, name: "Acts", aliases: &["act", "ac"] },
    BookDef { number: 45, name: "Romans", aliases: &["rom", "ro", "rm"] },
    BookDef { number: 46, name: "1 Corinthians", aliases: &["1cor", "1co", "1c", "icorinthians", "firstcorinthians", "1corinthians"] },
    BookDef { number: 47, name: "2 Corinthians", aliases: &["2cor", "2co", "2c", "iicorinthians", "secondcorinthians", "2corinthians"] },
    BookDef { number: 48, name: "Galatians", aliases: &["gal", "ga"] },
    BookDef { number: 49, name: "Ephesians", aliases: &["eph", "ephes"] },
    BookDef { number: 50, name: "Philippians", aliases: &["phil", "php", "pp"] },
    BookDef { number: 51, name: "Colossians", aliases: &["col", "co"] },
    BookDef { number: 52, name: "1 Thessalonians", aliases: &["1thess", "1thes", "1th", "ithessalonians", "firstthessalonians", "1thessalonians"] },
    BookDef { number: 53, name: "2 Thessalonians", aliases: &["2thess", "2thes", "2th", "iithessalonians", "secondthessalonians", "2thessalonians"] },
    BookDef { number: 54, name: "1 Timothy", aliases: &["1tim", "1ti", "1t", "itimothy", "firsttimothy", "1timothy"] },
    BookDef { number: 55, name: "2 Timothy", aliases: &["2tim", "2ti", "2t", "iitimothy", "secondtimothy", "2timothy"] },
    BookDef { number: 56, name: "Titus", aliases: &["tit", "ti"] },
    BookDef { number: 57, name: "Philemon", aliases: &["philem", "phm", "pm"] },
    BookDef { number: 58, name: "Hebrews", aliases: &["heb", "hbr"] },
    BookDef { number: 59, name: "James", aliases: &["jas", "jm", "jam"] },
    BookDef { number: 60, name: "1 Peter", aliases: &["1pet", "1pe", "1p", "ipeter", "firstpeter", "1peter"] },
    BookDef { number: 61, name: "2 Peter", aliases: &["2pet", "2pe", "2p", "iipeter", "secondpeter", "2peter"] },
    BookDef { number: 62, name: "1 John", aliases: &["1jn", "1jo", "1jhn", "1j", "ijohn", "firstjohn", "1john"] },
    BookDef { number: 63, name: "2 John", aliases: &["2jn", "2jo", "2jhn", "2j", "iijohn", "secondjohn", "2john"] },
    BookDef { number: 64, name: "3 John", aliases: &["3jn", "3jo", "3jhn", "3j", "iiijohn", "thirdjohn", "3john"] },
    BookDef { number: 65, name: "Jude", aliases: &["jud", "jd"] },
    BookDef { number: 66, name: "Revelation", aliases: &["rev", "re", "rv", "apocalypse"] },
];

#[cfg(test)]
mod tests {
    use super::*;

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
        assert_eq!(parse_one("Romans 8:28").unwrap(), r(45, "Romans", 8, Some((28, 28))));
    }

    #[test]
    fn abbreviation_and_range() {
        assert_eq!(parse_one("Rom 8:28-30").unwrap(), r(45, "Romans", 8, Some((28, 30))));
    }

    #[test]
    fn whole_chapter() {
        assert_eq!(parse_one("Ps 23").unwrap(), r(19, "Psalms", 23, None));
        assert_eq!(parse_one("Psalm 23").unwrap(), r(19, "Psalms", 23, None));
    }

    #[test]
    fn chapter_verse_range() {
        assert_eq!(parse_one("Psalm 23:1-6").unwrap(), r(19, "Psalms", 23, Some((1, 6))));
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
        assert_eq!(parse_one("Jn 3:16").unwrap(), r(43, "John", 3, Some((16, 16))));
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
        assert_eq!(parse_one("I John 1:9").unwrap(), r(62, "1 John", 1, Some((9, 9))));
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
        assert_eq!(parse_one("Song of Solomon 2:1").unwrap(), r(22, "Song of Solomon", 2, Some((1, 1))));
    }

    #[test]
    fn all_66_books_resolve_by_canonical_name() {
        for b in BOOKS {
            let input = format!("{} 1:1", b.name);
            let parsed = parse_one(&input).unwrap_or_else(|_| panic!("failed: {}", b.name));
            assert_eq!(parsed.book, b.number, "wrong number for {}", b.name);
        }
        assert_eq!(BOOKS.len(), 66);
    }

    #[test]
    fn verse_count() {
        assert_eq!(parse_one("Rom 8:28-30").unwrap().verse_count(), 3);
        assert_eq!(parse_one("Rom 8:28").unwrap().verse_count(), 1);
        assert_eq!(parse_one("Rom 8").unwrap().verse_count(), 0);
    }

    #[test]
    fn display_round_trips() {
        assert_eq!(parse_one("Rom 8:28-30").unwrap().to_string(), "Romans 8:28-30");
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
        assert_eq!(parse_one("Psalm 119:176").unwrap().verses, Some(VerseRange { start: 176, end: 176 }));
    }
}
