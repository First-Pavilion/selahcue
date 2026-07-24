//! Bundled public-domain scripture text with verse lookup and keyword search
//! (story 86ajpew05; FR-025..FR-029 foundation).
//!
//! The **World English Bible** (WEB, public domain, protestant canon — 31,098
//! verses from ebible.org) ships inside the binary as a gzipped TSV
//! (`book\tchapter\tverse\ttext`, canonical book numbers 1–66 matching
//! [`selahcue_core::scripture::Reference::book`]). It decompresses **once** into
//! a process-wide index on first use (a few MB, fixed size — bounded by design;
//! the no-leak tests assert idempotent initialization). Further public-domain
//! translations (ASV/BSB/BBE) extend this crate as additional assets.
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

/// Short code of the bundled translation.
pub const TRANSLATION: &str = "WEB";
/// Full name (public domain — no licence text required, attribution courteous).
pub const TRANSLATION_NAME: &str = "World English Bible";

static INDEX: OnceLock<Vec<Verse>> = OnceLock::new();

/// The full verse index (decoded once; sorted by book, chapter, verse).
fn index() -> &'static [Verse] {
    INDEX.get_or_init(|| {
        let compressed: &[u8] = include_bytes!("../assets/web.tsv.gz");
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
    })
}

/// All verses of `reference` in canonical order. A whole-chapter reference
/// (no verse range) returns the entire chapter. Empty when the reference is
/// outside the canon (e.g. a chapter that does not exist).
pub fn verses(reference: &Reference) -> Vec<&'static Verse> {
    let all = index();
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

/// The verse text of `reference` as one string (verses joined by a space), or
/// `None` when nothing matches. Suitable for confidence-monitor previews.
pub fn passage_text(reference: &Reference) -> Option<String> {
    let vs = verses(reference);
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
    let words: Vec<String> = query.split_whitespace().map(|w| w.to_lowercase()).collect();
    if words.is_empty() {
        return Vec::new();
    }
    let mut hits = Vec::new();
    for v in index() {
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

/// Number of bundled verses (0 only if the compiled asset failed to decode).
pub fn verse_count() -> usize {
    index().len()
}
