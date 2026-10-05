//! Bundled public-domain scripture text with verse lookup and keyword search
//! (story 86ajpew05; FR-025..FR-029 foundation).
//!
//! Five public-domain translations ship inside the binary as gzipped TSVs
//! (`book\tchapter\tverse\ttext`, canonical book numbers 1–66 matching
//! [`selahcue_core::scripture::Reference::book`]), each from ebible.org:
//! the **King James Version** (31,102 verses — the product DEFAULT; supplied-word
//! brackets and pilcrows stripped for display), the **World English Bible**
//! (31,098), the **American Standard Version** (31,086), the **World English
//! English British Edition** (31,098), and the **Darby Translation** (31,099 —
//! apparatus asterisks stripped). Each decompresses
//! **lazily and exactly once** into a process-wide index on first use (a few MB
//! per touched translation, fixed size — bounded by design; the no-leak tests
//! assert idempotent initialization). Every bundled text is public domain
//! WORLDWIDE (KJV: UK Crown letters-patent printing exception noted). BBE was
//! deliberately NOT bundled — its PD status is US-only (Cambridge UP; life+70
//! jurisdictions plausibly until 2038).
//!
//! Further translations are DOWNLOADED, not bundled (story 17tnw2b2jfv). With the `installed`
//! feature, [`registry::Registry`] holds the ones a user has installed in the app data directory
//! (SHA-256-checked against a receipt, validated at install time, at most three decoded indexes in
//! memory at once), and [`Bible`] is the one handle that answers lookups for a bundled and an
//! installed translation alike. With the `download` feature, [`download::download_and_install`]
//! fetches a catalogued translation. The five bundled translations stay the closed
//! [`Translation`] enum, so their wire codes and the quote matcher are untouched. Licensed
//! translations (NIV/NLT/...) remain on story 86ajpqfyj.
//!
//! Everything works offline — a hard product requirement for live services.
//!
//! # Asking "does this passage exist?" without paying for the corpus
//!
//! Decoding a translation is the expensive part of every lookup here (≈4 MB of text and ≈31k
//! `String`s per translation). A caller that only needs a yes/no — the operator view's link
//! status, which is rebuilt after every command including Blackout — must therefore use
//! [`passage_exists_in`], never `!verses_in(..).is_empty()`. It answers from a small table of
//! verse runs that `build.rs` derives from the embedded assets at compile time, so it decodes
//! nothing and allocates nothing, yet returns exactly what the lookup would (86ak84fbd). An
//! installed translation has no embedded asset to derive a table from;
//! [`Bible::passage_exists`] answers from its decoded index, loading it if it is not resident.

#![forbid(unsafe_code)]

use selahcue_core::scripture::Reference;
use std::io::Read;
use std::sync::OnceLock;

/// The one definition of a verse line, shared with `build.rs` (see the module doc).
mod tsv_row;
/// Compile-time verse-run tables behind [`passage_exists_in`].
mod versification;

/// Fuzzy quote/paraphrase detection (R4 "fuzzy" rung) — match spoken text against the corpus.
pub mod quote_match;
pub use quote_match::{
    match_quote, match_quote_in, match_quote_ranked, match_quote_ranked_in, match_quote_scored,
    match_quote_scored_in, ranked_offered_in, warm, warm_in, MAX_ALTERNATIVES, MAX_RANKED,
};

/// One handle for a bundled or an installed translation (see [`Bible`]).
mod bible;
pub use bible::Bible;

/// The embedded catalogue of downloadable translations (feature `installed`).
#[cfg(feature = "installed")]
pub mod catalog;
/// SHA-256 helpers shared by the installer and the downloader.
#[cfg(feature = "installed")]
mod digest;
/// The install receipt, `installed.json` (feature `installed`).
#[cfg(feature = "installed")]
pub mod receipt;
/// Installed translations: storage, install, and the bounded cache (feature `installed`).
#[cfg(feature = "installed")]
pub mod registry;
/// Staging files for installs: exclusive creation and narrow cleanup.
#[cfg(feature = "installed")]
mod staging;
/// Which URLs the download path may request: HTTPS only (feature `installed`).
#[cfg(feature = "installed")]
pub mod url_policy;
/// Install-time validation of a translation asset (feature `installed`).
#[cfg(feature = "installed")]
pub mod validate;

/// Download-on-demand for catalogued Bible translations (feature `download`).
///
/// Fetches a catalogued translation over HTTPS, checks it against its pinned SHA-256, validates
/// it and installs it into the [`registry::Registry`]. It cannot be called without a
/// [`download::TermsAcceptance`], refuses an unpublished entry without making a request, and
/// refuses one still pending legal review. With the feature OFF this crate has no HTTP client.
#[cfg(feature = "download")]
pub mod download;
#[cfg(feature = "download")]
pub use download::download_and_install;

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

/// A BUNDLED translation (KJV is the product default — owner decision, 2026-07-24). All five are
/// compiled into the binary and public domain worldwide (KJV: UK Crown letters patent covers
/// printing within the UK; see the module doc for the BBE exclusion rationale). Translations a user
/// downloads are not variants of this enum: they are keyed by validated code strings in
/// [`registry::Registry`] (feature `installed`), and [`Bible`] is the handle that covers both.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Translation {
    #[default]
    Kjv,
    Web,
    Asv,
    Webbe,
    Dby,
}

impl Translation {
    /// Every bundled translation, default first (drives the picker order).
    pub const ALL: [Translation; 5] = [
        Translation::Kjv,
        Translation::Web,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
    ];

    /// Short display/wire code (`"KJV"`, `"WEB"`, …).
    pub fn code(self) -> &'static str {
        match self {
            Translation::Kjv => "KJV",
            Translation::Web => "WEB",
            Translation::Asv => "ASV",
            Translation::Webbe => "WEBBE",
            Translation::Dby => "DBY",
        }
    }

    /// Full name for attribution.
    pub fn name(self) -> &'static str {
        match self {
            Translation::Kjv => "King James Version",
            Translation::Web => "World English Bible",
            Translation::Asv => "American Standard Version",
            Translation::Webbe => "World English Bible (British Edition)",
            Translation::Dby => "Darby Translation",
        }
    }

    /// Parse a wire/UI code (case-insensitive); `None` for unknown codes. Only the five bundled
    /// codes: a downloaded translation's code is resolved by [`Bible::from_code`].
    pub fn from_code(code: &str) -> Option<Translation> {
        match code.to_ascii_uppercase().as_str() {
            "KJV" => Some(Translation::Kjv),
            "WEB" => Some(Translation::Web),
            "ASV" => Some(Translation::Asv),
            "WEBBE" => Some(Translation::Webbe),
            "DBY" => Some(Translation::Dby),
            _ => None,
        }
    }
}

/// Whether bundled translation `t` can be looked up right now. Always: bundled text is compiled in.
/// Kept so existing callers keep compiling; to ask the same of a translation that may be a
/// downloaded one, use [`Bible::is_available`]. Never performs I/O and never panics.
pub fn is_available(t: Translation) -> bool {
    let _ = t;
    true
}

/// Short code of the DEFAULT translation (KJV).
pub const TRANSLATION: &str = "KJV";

static KJV_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static WEB_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static ASV_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static WEBBE_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static DBY_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();

/// The verse index of `t`. A bundled translation decodes lazily on FIRST use and exactly once (an
/// unused translation costs only its compressed asset bytes).
pub(crate) fn index_of(t: Translation) -> &'static [Verse] {
    let (lock, compressed): (&OnceLock<Vec<Verse>>, &[u8]) = match t {
        Translation::Kjv => (&KJV_INDEX, include_bytes!("../assets/kjv.tsv.gz")),
        Translation::Web => (&WEB_INDEX, include_bytes!("../assets/web.tsv.gz")),
        Translation::Asv => (&ASV_INDEX, include_bytes!("../assets/asv.tsv.gz")),
        Translation::Webbe => (&WEBBE_INDEX, include_bytes!("../assets/webbe.tsv.gz")),
        Translation::Dby => (&DBY_INDEX, include_bytes!("../assets/dby.tsv.gz")),
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
        // `parse_row` is shared with `build.rs`, so the compile-time verse-run table and this
        // index agree on which lines are verses by construction.
        let mut verses: Vec<Verse> = tsv
            .lines()
            .filter_map(|line| {
                let (book, chapter, verse, text) = tsv_row::parse_row(line)?;
                Some(Verse {
                    book,
                    chapter,
                    verse,
                    text: text.to_string(),
                })
            })
            .collect();
        verses.sort_by_key(|v| (v.book, v.chapter, v.verse));
        verses
    }
}

/// Whether `reference` presents at least one verse in translation `t` — exactly
/// `!verses_in(t, reference).is_empty()`, without the cost of `verses_in`.
///
/// It answers from a compile-time table of verse runs: it never decodes the translation, never
/// allocates, and keeps no cache (the table is read-only static data, ~1.2k rows of 8 bytes per
/// translation). That is the point — it is the call to make on a path that runs per action (the
/// operator view's link status runs after every command, Blackout and Clear included), where
/// decoding a whole translation to ask a yes/no question is a first-press stall. A well-formed
/// reference that names nothing (`Jude 2:1`, `Romans 99:1`) is `false`, and a verse one translation
/// omits (the WEB has no Luke 17:36) is `false` there only.
///
/// An exhaustive test (`tests/test_passage_exists.rs`) pins this to `verses_in` over every chapter
/// of every bundled translation.
pub fn passage_exists_in(t: Translation, reference: &Reference) -> bool {
    versification::contains(
        versification::runs_of(t),
        reference.book,
        reference.chapter,
        reference.verses.map(|r| (r.start, r.end)),
    )
}

/// The first and last verse NUMBERS translation `t` has in the chapter `reference` names (its verse
/// selection is ignored), or `None` when that chapter has no verse in `t` (outside the canon).
/// Exactly the first and last `verse` of `verses_in(t, <the whole chapter>)`, without the cost of
/// `verses_in`.
///
/// It answers from the same compile-time verse-run table as [`passage_exists_in`]: no decode, no
/// allocation, no cache. It is the call to make to ask "how far does this chapter run?" on a path
/// that must not stall (resolving a plan's links when it loads or is edited), where the answer to
/// that question used to be a whole-translation decode (86ak84fbd). The last verse NUMBER is not
/// the verse COUNT: a translation that omits a verse in the middle of a chapter (the WEB has no
/// Luke 17:36 or Acts 8:37) has a last number one higher than its count.
///
/// An exhaustive test (`tests/test_chapter_verse_bounds.rs`) pins this to `verses_in` over every
/// chapter of every bundled translation.
pub fn chapter_verse_bounds_in(t: Translation, reference: &Reference) -> Option<(u16, u16)> {
    versification::chapter_bounds(versification::runs_of(t), reference.book, reference.chapter)
}

/// Whether translation `t`'s full verse index has been decoded yet in this process. Never
/// triggers a decode.
///
/// **A test seam, not a product API.** It is how a test proves a code path answered without
/// paying for the corpus (a global "how many decodes" counter would let a sibling's decode mask a
/// miss on your translation, so this is per translation).
#[doc(hidden)]
pub fn is_index_loaded(t: Translation) -> bool {
    match t {
        Translation::Kjv => KJV_INDEX.get().is_some(),
        Translation::Web => WEB_INDEX.get().is_some(),
        Translation::Asv => ASV_INDEX.get().is_some(),
        Translation::Webbe => WEBBE_INDEX.get().is_some(),
        Translation::Dby => DBY_INDEX.get().is_some(),
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
    select_verses(index_of(t), reference)
}

/// The verses of `reference` in `all`, a verse index sorted by (book, chapter, verse). The ONE
/// definition of "which verses does this reference present", shared by the bundled lookups and by
/// [`Bible`] over an installed translation.
pub(crate) fn select_verses<'a>(all: &'a [Verse], reference: &Reference) -> Vec<&'a Verse> {
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

/// The first and last verse numbers of the chapter `reference` names in `all` (verse selection
/// ignored), or `None` when the chapter holds nothing. Only an installed translation needs it (a
/// bundled one answers from its verse-run table).
#[cfg(feature = "installed")]
pub(crate) fn bounds_in_index(all: &[Verse], reference: &Reference) -> Option<(u16, u16)> {
    let whole_chapter = Reference {
        verses: None,
        ..reference.clone()
    };
    let verses = select_verses(all, &whole_chapter);
    Some((verses.first()?.verse, verses.last()?.verse))
}

/// The verse text of `reference` in the DEFAULT translation (KJV).
pub fn passage_text(reference: &Reference) -> Option<String> {
    passage_text_in(Translation::default(), reference)
}

/// The verse text of `reference` as one string (verses joined by a space), or
/// `None` when nothing matches. Suitable for confidence-monitor previews.
pub fn passage_text_in(t: Translation, reference: &Reference) -> Option<String> {
    join_verses(&verses_in(t, reference))
}

/// `verses` joined by a space, or `None` when there are none.
pub(crate) fn join_verses(verses: &[&Verse]) -> Option<String> {
    if verses.is_empty() {
        return None;
    }
    Some(
        verses
            .iter()
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
    search_index(index_of(t), query, limit)
}

pub(crate) fn search_index(all: &[Verse], query: &str, limit: usize) -> Vec<SearchHit> {
    let words: Vec<String> = query.split_whitespace().map(|w| w.to_lowercase()).collect();
    if words.is_empty() {
        return Vec::new();
    }
    let mut hits = Vec::new();
    for v in all {
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
    chapter_of_index(index_of(t), reference)
}

pub(crate) fn chapter_of_index(all: &[Verse], reference: &Reference) -> Option<Chapter> {
    let full = Reference {
        book: reference.book,
        book_name: reference.book_name,
        chapter: reference.chapter,
        verses: None,
    };
    let vs = select_verses(all, &full);
    if vs.is_empty() {
        return None;
    }
    // From the index itself, never from an assumption that all 66 books are present: an index
    // without (say) the Old Testament has no chapter before Matthew 1.
    let has_prev = adjacent_in_index(all, reference, false).is_some();
    let has_next = adjacent_in_index(all, reference, true).is_some();
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
    adjacent_in_index(index_of(t), reference, forward)
}

pub(crate) fn adjacent_in_index(
    all: &[Verse],
    reference: &Reference,
    forward: bool,
) -> Option<String> {
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
