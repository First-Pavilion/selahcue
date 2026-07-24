//! Bundled public-domain scripture text with verse lookup and keyword search
//! (story 86ajpew05; FR-025..FR-029 foundation).
//!
//! Two public-domain translations ship inside the binary as gzipped TSVs
//! (`book\tchapter\tverse\ttext`, canonical book numbers 1–66 matching
//! [`selahcue_core::scripture::Reference::book`]), each from ebible.org:
//! the **King James Version** (31,102 verses — the product DEFAULT; supplied-word
//! brackets and pilcrows stripped for display) and the **World English Bible**
//! (31,098 verses). Each decompresses **once** into a process-wide index on
//! first use (a few MB per translation, fixed size — bounded by design; the
//! no-leak tests assert idempotent initialization). Further public-domain
//! translations extend this crate as additional assets; licensed translations
//! (NIV/NLT/…) are a separate licensing story (86ajpqfyj).
//!
//! Everything works offline — a hard product requirement for live services.

#![forbid(unsafe_code)]

use selahcue_core::scripture::Reference;
use std::io::Read;
use std::sync::OnceLock;

/// One verse of the bundled translation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Verse {
    /// Canonical book number, 1 (Genesis) … 66 (Revelation).
    pub book: u8,
    pub chapter: u16,
    pub verse: u16,
    pub text: String,
}

/// A keyword-search hit: the verse plus its display reference (parseable back
/// into a [`Reference`], so results can be staged directly).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchHit {
    /// e.g. `"Romans 8:28"`.
    pub reference: String,
    pub text: String,
}

/// A bundled translation. KJV is the product default (owner decision,
/// 2026-07-24); WEB remains available. Both are public domain (KJV: public
/// domain worldwide except UK Crown letters patent for printing within the UK).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Translation {
    #[default]
    Kjv,
    Web,
}

impl Translation {
    /// Every bundled translation, default first (drives the picker order).
    pub const ALL: [Translation; 2] = [Translation::Kjv, Translation::Web];

    /// Short display/wire code (`"KJV"` / `"WEB"`).
    pub fn code(self) -> &'static str {
        match self {
            Translation::Kjv => "KJV",
            Translation::Web => "WEB",
        }
    }

    /// Full name for attribution.
    pub fn name(self) -> &'static str {
        match self {
            Translation::Kjv => "King James Version",
            Translation::Web => "World English Bible",
        }
    }

    /// Parse a wire/UI code (case-insensitive); `None` for unknown codes.
    pub fn from_code(code: &str) -> Option<Translation> {
        match code.to_ascii_uppercase().as_str() {
            "KJV" => Some(Translation::Kjv),
            "WEB" => Some(Translation::Web),
            _ => None,
        }
    }
}

/// Short code of the DEFAULT translation (KJV).
pub const TRANSLATION: &str = "KJV";

static KJV_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static WEB_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();

/// The verse index of `t` (each decoded once; sorted by book, chapter, verse).
fn index_of(t: Translation) -> &'static [Verse] {
    let (lock, compressed): (&OnceLock<Vec<Verse>>, &[u8]) = match t {
        Translation::Kjv => (&KJV_INDEX, include_bytes!("../assets/kjv.tsv.gz")),
        Translation::Web => (&WEB_INDEX, include_bytes!("../assets/web.tsv.gz")),
    };
    lock.get_or_init(|| decode(compressed))
}

fn decode(compressed: &[u8]) -> Vec<Verse> {
    {
        let mut tsv = String::new();
        // The asset is compiled in; a decode failure is a build defect, not a
        // runtime condition — degrade to an empty index rather than panic.
        if flate2::read::GzDecoder::new(compressed)
            .read_to_string(&mut tsv)
            .is_err()
        {
            return Vec::new();
        }
        let mut verses: Vec<Verse> = tsv
            .lines()
            .filter_map(|line| {
                let mut parts = line.splitn(4, '\t');
                Some(Verse {
                    book: parts.next()?.parse().ok()?,
                    chapter: parts.next()?.parse().ok()?,
                    verse: parts.next()?.parse().ok()?,
                    text: parts.next()?.to_string(),
                })
            })
            .collect();
        verses.sort_by_key(|v| (v.book, v.chapter, v.verse));
        verses
    }
}

/// All verses of `reference` in the DEFAULT translation (KJV).
pub fn verses(reference: &Reference) -> Vec<&'static Verse> {
    verses_in(Translation::default(), reference)
}

/// All verses of `reference` in canonical order for translation `t`. A
/// whole-chapter reference (no verse range) returns the entire chapter. Empty
/// when the reference is outside the canon (e.g. a chapter that does not exist).
pub fn verses_in(t: Translation, reference: &Reference) -> Vec<&'static Verse> {
    let all = index_of(t);
    // The index is sorted; find the chapter span, then filter the range.
    let start = all.partition_point(|v| (v.book, v.chapter) < (reference.book, reference.chapter));
    let chapter = all[start..]
        .iter()
        .take_while(|v| v.book == reference.book && v.chapter == reference.chapter);
    match reference.verses {
        None => chapter.collect(),
        Some(range) => chapter
            .filter(|v| v.verse >= range.start && v.verse <= range.end)
            .collect(),
    }
}

/// The verse text of `reference` in the DEFAULT translation (KJV).
pub fn passage_text(reference: &Reference) -> Option<String> {
    passage_text_in(Translation::default(), reference)
}

/// The verse text of `reference` as one string (verses joined by a space), or
/// `None` when nothing matches. Suitable for confidence-monitor previews.
pub fn passage_text_in(t: Translation, reference: &Reference) -> Option<String> {
    let vs = verses_in(t, reference);
    if vs.is_empty() {
        return None;
    }
    Some(
        vs.iter()
            .map(|v| v.text.as_str())
            .collect::<Vec<_>>()
            .join(" "),
    )
}

/// Case-insensitive keyword search over the whole translation (bounded by
/// `limit`). Multi-word queries match verses containing ALL words. Intended for
/// operator search-as-you-type — a full scan of 31k verses stays well under the
/// story's 500ms budget (perf-tested).
pub fn search(query: &str, limit: usize) -> Vec<SearchHit> {
    search_in(Translation::default(), query, limit)
}

/// Keyword search over translation `t` (see [`search`]).
pub fn search_in(t: Translation, query: &str, limit: usize) -> Vec<SearchHit> {
    let words: Vec<String> = query.split_whitespace().map(|w| w.to_lowercase()).collect();
    if words.is_empty() {
        return Vec::new();
    }
    let mut hits = Vec::new();
    for v in index_of(t) {
        if hits.len() >= limit {
            break;
        }
        let hay = v.text.to_lowercase();
        if words.iter().all(|w| hay.contains(w.as_str())) {
            hits.push(SearchHit {
                reference: display_reference(v),
                text: v.text.clone(),
            });
        }
    }
    hits
}

/// `"Romans 8:28"`-style display for a verse (parseable by `scripture::parse`).
fn display_reference(v: &Verse) -> String {
    let name = selahcue_core::scripture::book_name(v.book).unwrap_or("?");
    format!("{} {}:{}", name, v.chapter, v.verse)
}

/// Verse count of the DEFAULT translation (KJV).
pub fn verse_count() -> usize {
    verse_count_in(Translation::default())
}

/// Verse count of translation `t` (0 only if its compiled asset failed to decode).
pub fn verse_count_in(t: Translation) -> usize {
    index_of(t).len()
}

/// A whole chapter for the operator's chapter browser (story 86ajpkfcd):
/// numbered verses plus whether neighbouring chapters exist for ‹ › paging.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chapter {
    /// Canonical book number, 1–66.
    pub book: u8,
    /// Canonical book name (e.g. `"Genesis"`).
    pub book_name: String,
    pub chapter: u16,
    /// `(verse number, text)` in canonical order.
    pub verses: Vec<(u16, String)>,
    /// A previous chapter exists (within the same book or the previous book).
    pub has_prev: bool,
    /// A next chapter exists (within the same book or the next book).
    pub has_next: bool,
}

/// The full chapter containing `reference` in the DEFAULT translation (KJV).
pub fn chapter(reference: &Reference) -> Option<Chapter> {
    chapter_in(Translation::default(), reference)
}

/// The full chapter containing `reference` (its verse selection is ignored),
/// or `None` when the chapter is outside the canon.
pub fn chapter_in(t: Translation, reference: &Reference) -> Option<Chapter> {
    let full = Reference {
        book: reference.book,
        book_name: reference.book_name,
        chapter: reference.chapter,
        verses: None,
    };
    let vs = verses_in(t, &full);
    if vs.is_empty() {
        return None;
    }
    let all = index_of(t);
    let exists = |book: u8, chapter: u16| {
        (1..=66).contains(&book) && {
            let i = all.partition_point(|v| (v.book, v.chapter) < (book, chapter));
            all.get(i)
                .is_some_and(|v| v.book == book && v.chapter == chapter)
        }
    };
    let has_prev = reference.chapter > 1 && exists(reference.book, reference.chapter - 1)
        || reference.book > 1;
    let has_next = exists(reference.book, reference.chapter + 1) || reference.book < 66;
    Some(Chapter {
        book: reference.book,
        book_name: selahcue_core::scripture::book_name(reference.book)
            .unwrap_or(reference.book_name)
            .to_string(),
        chapter: reference.chapter,
        verses: vs.iter().map(|v| (v.verse, v.text.clone())).collect(),
        has_prev,
        has_next,
    })
}

/// Previous/next chapter in the DEFAULT translation (KJV).
pub fn adjacent_chapter(reference: &Reference, forward: bool) -> Option<String> {
    adjacent_chapter_in(Translation::default(), reference, forward)
}

/// The reference addressing the previous/next chapter relative to `reference`
/// (crossing book boundaries; `None` at the ends of the canon). The returned
/// display string parses back via `scripture::parse_one`.
pub fn adjacent_chapter_in(t: Translation, reference: &Reference, forward: bool) -> Option<String> {
    let all = index_of(t);
    if forward {
        // First verse strictly after this chapter.
        let i = all.partition_point(|v| (v.book, v.chapter) <= (reference.book, reference.chapter));
        all.get(i).map(|v| {
            let name = selahcue_core::scripture::book_name(v.book).unwrap_or("?");
            format!("{} {}", name, v.chapter)
        })
    } else {
        // Last verse strictly before this chapter.
        let i = all.partition_point(|v| (v.book, v.chapter) < (reference.book, reference.chapter));
        i.checked_sub(1).and_then(|j| all.get(j)).map(|v| {
            let name = selahcue_core::scripture::book_name(v.book).unwrap_or("?");
            format!("{} {}", name, v.chapter)
        })
    }
}
