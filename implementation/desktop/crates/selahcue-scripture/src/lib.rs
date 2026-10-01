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
//! One further public-domain translation — **Young's Literal Translation (1898)**
//! — is selectable but NOT bundled: it is the DOWNLOADABLE exemplar. It carries no
//! `include_bytes!` asset; under the `download` feature it loads its gzipped verse
//! index from the on-disk cache ([`download::default_cache_dir`]) at runtime, and
//! reports [`is_available`]`== false` until its owner-supplied asset has been
//! fetched. With the feature off it exists in the [`Translation`] enum but is never
//! available (no runtime file I/O is compiled). Licensed translations (NIV/NLT/…)
//! remain on story 86ajpqfyj.
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
//! nothing and allocates nothing, yet returns exactly what the lookup would (86ak84fbd). A
//! downloadable translation has no embedded asset to derive a table from; it falls back to the
//! lookup, which decodes its verses once if (and only if) they have been downloaded.

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
    match_quote_scored_in, ranked_offered_in, MAX_ALTERNATIVES, MAX_RANKED,
};

/// Download-on-demand for additional Bible-translation assets (feature `download`).
///
/// Additive, feature-gated supply-chain infra: fetch + SHA-256-verify + cache a pinned
/// translation file, mirroring `selahcue-stt`'s model-download discipline. It exposes only
/// the VERIFIED local file PATH — downloaded translations are deliberately NOT integrated
/// into the compiled [`Translation`] enum, the per-translation quote-match index, or the
/// cross-language-pinned LAN wire protocol. With the feature OFF this crate stays pure
/// (bundled text only, no I/O), exactly as before.
#[cfg(feature = "download")]
pub mod download;
#[cfg(feature = "download")]
pub use download::{
    catalog, default_cache_dir, fetch_translation, sha256_file, TranslationAsset,
    TranslationFetchError,
};

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

/// A selectable translation (KJV is the product default — owner decision,
/// 2026-07-24). The first five are BUNDLED (compiled into the binary) and public
/// domain worldwide (KJV: UK Crown letters patent covers printing within the UK;
/// see the module doc for the BBE exclusion rationale). [`Translation::Ylt`] is
/// public domain too but DOWNLOADABLE — see [`Translation::is_downloadable`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Translation {
    #[default]
    Kjv,
    Web,
    Asv,
    Webbe,
    Dby,
    /// Young's Literal Translation (1898) — public domain, but not bundled: its
    /// verses load from the on-disk cache at runtime (feature `download`).
    Ylt,
}

impl Translation {
    /// Every selectable translation, default first (drives the picker order). Includes
    /// downloadable translations, which may not be available yet — see [`is_available`].
    pub const ALL: [Translation; 6] = [
        Translation::Kjv,
        Translation::Web,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
        Translation::Ylt,
    ];

    /// Short display/wire code (`"KJV"`, `"WEB"`, …).
    pub fn code(self) -> &'static str {
        match self {
            Translation::Kjv => "KJV",
            Translation::Web => "WEB",
            Translation::Asv => "ASV",
            Translation::Webbe => "WEBBE",
            Translation::Dby => "DBY",
            Translation::Ylt => "YLT",
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
            Translation::Ylt => "Young's Literal Translation (1898)",
        }
    }

    /// Parse a wire/UI code (case-insensitive); `None` for unknown codes.
    pub fn from_code(code: &str) -> Option<Translation> {
        match code.to_ascii_uppercase().as_str() {
            "KJV" => Some(Translation::Kjv),
            "WEB" => Some(Translation::Web),
            "ASV" => Some(Translation::Asv),
            "WEBBE" => Some(Translation::Webbe),
            "DBY" => Some(Translation::Dby),
            "YLT" => Some(Translation::Ylt),
            _ => None,
        }
    }

    /// Whether this translation is fetched on demand — its verses load from the on-disk
    /// cache at runtime (feature `download`) — rather than being compiled into the binary.
    /// Pure classification: no I/O. Downloadable translations may not be available yet
    /// (nothing downloaded); use [`is_available`] to gate a lookup.
    pub fn is_downloadable(self) -> bool {
        matches!(self, Translation::Ylt)
    }
}

/// Whether translation `t` can be looked up right now. Bundled translations are always
/// available (compiled in). A downloadable translation ([`Translation::is_downloadable`]) is
/// available only once its verified asset has been downloaded into the cache and decodes to
/// verses; with the `download` feature off it is never available (no runtime file I/O is
/// compiled). Never performs network I/O and never panics.
pub fn is_available(t: Translation) -> bool {
    !t.is_downloadable() || !index_of(t).is_empty()
}

/// Short code of the DEFAULT translation (KJV).
pub const TRANSLATION: &str = "KJV";

static KJV_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static WEB_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static ASV_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static WEBBE_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();
static DBY_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();

/// Runtime-loaded index for the downloadable YLT translation: decoded from the on-disk cache
/// at most once (mirroring the bundled load-once discipline). A FAILED load is deliberately
/// NOT cached, so a later successful download loads on the next access.
#[cfg(feature = "download")]
static YLT_INDEX: OnceLock<Vec<Verse>> = OnceLock::new();

/// The verse index of `t`. A BUNDLED translation decodes lazily on FIRST use and exactly
/// once (an unused translation costs only its compressed asset bytes). A DOWNLOADABLE
/// translation carries no compiled asset: it loads from the on-disk cache at runtime and
/// degrades to an EMPTY index when its file is absent/unreadable or the `download` feature is
/// off — so every lookup helper returns "nothing" gracefully rather than panicking.
fn index_of(t: Translation) -> &'static [Verse] {
    let (lock, compressed): (&OnceLock<Vec<Verse>>, &[u8]) = match t {
        Translation::Kjv => (&KJV_INDEX, include_bytes!("../assets/kjv.tsv.gz")),
        Translation::Web => (&WEB_INDEX, include_bytes!("../assets/web.tsv.gz")),
        Translation::Asv => (&ASV_INDEX, include_bytes!("../assets/asv.tsv.gz")),
        Translation::Webbe => (&WEBBE_INDEX, include_bytes!("../assets/webbe.tsv.gz")),
        Translation::Dby => (&DBY_INDEX, include_bytes!("../assets/dby.tsv.gz")),
        Translation::Ylt => return downloadable_index_or_empty(t),
    };
    lock.get_or_init(|| decode(compressed))
}

/// The runtime-loaded verse index for a DOWNLOADABLE translation, or an empty slice when it
/// is not available (not downloaded, unreadable, or the `download` feature is off). Never
/// panics. Feature-gated so the default (feature-off) build compiles no file I/O and stays
/// byte-identically pure for the bundled translations.
fn downloadable_index_or_empty(t: Translation) -> &'static [Verse] {
    #[cfg(feature = "download")]
    {
        downloadable_index(t).unwrap_or(&[])
    }
    #[cfg(not(feature = "download"))]
    {
        let _ = t;
        &[]
    }
}

/// Load a downloadable translation's verse index from the on-disk cache (feature `download`).
///
/// Reads `download::default_cache_dir().join(<file_name>)` — the SAME path the download
/// machinery installs the verified asset to — and decodes the gzipped TSV exactly once,
/// caching it process-wide so subsequent lookups hand out stable `&'static` verses (the same
/// load-once discipline as the bundled indices). Returns `None` — never panics — when the
/// translation is not downloadable, or its cached file is absent, unreadable, or decodes to no
/// verses; a failed load is deliberately NOT cached, so a later (successful) download loads on
/// the next access. Reads only a local file; never touches the network.
#[cfg(feature = "download")]
fn downloadable_index(t: Translation) -> Option<&'static [Verse]> {
    let (lock, file_name) = match t {
        Translation::Ylt => (&YLT_INDEX, download::YLT_FILE_NAME),
        _ => return None,
    };
    if let Some(verses) = lock.get() {
        return Some(verses.as_slice());
    }
    let path = download::default_cache_dir().join(file_name);
    let compressed = std::fs::read(&path).ok()?;
    let verses = decode(&compressed);
    if verses.is_empty() {
        // Absent/corrupt/empty → treat as not-yet-available WITHOUT caching, so a later
        // successful download can still load.
        return None;
    }
    // Cache the decode once; if a racing thread installed first, defer to theirs.
    let _ = lock.set(verses);
    lock.get().map(Vec::as_slice)
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
/// For a BUNDLED translation this answers from a compile-time table of verse runs: it never
/// decodes the translation, never allocates, and keeps no cache (the table is read-only static
/// data, ~1.2k rows of 8 bytes per translation). That is the point — it is the call to make on a
/// path that runs per action (the operator view's link status runs after every command, Blackout
/// and Clear included), where decoding a whole translation to ask a yes/no question is a
/// first-press stall. A well-formed reference that names nothing (`Jude 2:1`, `Romans 99:1`) is
/// `false`, and a verse one translation omits (the WEB has no Luke 17:36) is `false` there only.
///
/// A DOWNLOADABLE translation ([`Translation::is_downloadable`]) has no embedded asset to derive
/// a table from, so it falls back to the lookup: its verses decode once, and only once they have
/// been downloaded; until then it is `false` without decoding anything.
///
/// An exhaustive test (`tests/test_passage_exists.rs`) pins this to `verses_in` over every chapter
/// of every bundled translation.
pub fn passage_exists_in(t: Translation, reference: &Reference) -> bool {
    match versification::runs_of(t) {
        Some(runs) => versification::contains(
            runs,
            reference.book,
            reference.chapter,
            reference.verses.map(|r| (r.start, r.end)),
        ),
        None => !verses_in(t, reference).is_empty(),
    }
}

/// Whether translation `t`'s full verse index has been decoded yet in this process. Never
/// triggers a decode. A diagnostics/test seam: it is how a test proves a code path answered
/// without paying for the corpus (a global "how many decodes" counter would let a sibling's
/// decode mask a miss on your translation, so this is per translation).
pub fn is_index_loaded(t: Translation) -> bool {
    match t {
        Translation::Kjv => KJV_INDEX.get().is_some(),
        Translation::Web => WEB_INDEX.get().is_some(),
        Translation::Asv => ASV_INDEX.get().is_some(),
        Translation::Webbe => WEBBE_INDEX.get().is_some(),
        Translation::Dby => DBY_INDEX.get().is_some(),
        #[cfg(feature = "download")]
        Translation::Ylt => YLT_INDEX.get().is_some(),
        #[cfg(not(feature = "download"))]
        Translation::Ylt => false,
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
