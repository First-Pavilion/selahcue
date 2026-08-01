//! Fuzzy quote/paraphrase detection — the **fuzzy** rung of the R4 detection ladder
//! (parse → exact → fuzzy → semantic). When a verse is spoken as a near-verbatim quotation
//! (its reference NOT named), match the spoken text against the bundled corpus and return
//! the most-likely verse as a canonical reference (e.g. `"John 3:16"`).
//!
//! Approach (offline, deterministic, precision-biased):
//! - Lazily build (once, `OnceLock`) an **inverted index** over the translation: document
//!   frequency + IDF-mass per verse + postings (token → verse ids) for *discriminative*
//!   tokens only. Ubiquitous words ("the"/"and") and a domain **stopword** list of common
//!   devotional/liturgical words (god, lord, thanks, praise, glory, mercy, almighty, …) are
//!   NOT posted, so a devotional phrase built from them cannot drive a match — only genuinely
//!   distinctive scripture vocabulary can (precision over recall, FR-121).
//! - Score each candidate verse by **IDF-weighted token overlap** with the spoken text, and
//!   accept the best verse only when the overlap covers enough of the verse (or the spoken
//!   text) AND carries enough rare-word evidence.
//!
//! This is **suggestion-only**: the returned reference flows through the existing
//! operator-confirmed approval queue and is never auto-displayed (FR-115). Genuine loose
//! paraphrase (little shared distinctive vocabulary) is intentionally out of reach — that is
//! the semantic rung, barred from auto-display and with no infrastructure yet. Thresholds and
//! the stopword list are provisional and spike-gated (S11).

use std::collections::{BTreeSet, HashMap, HashSet};
use std::sync::OnceLock;

use crate::{display_reference, index_of, Translation};

/// Tokens present in more than this fraction of verses are treated as non-discriminative and
/// are not posted to the inverted index (they still contribute their small IDF weight to
/// scoring). Bounds candidate generation and postings size.
const DF_CAP_FRACTION: f64 = 0.03;

/// Minimum number of *discriminative* (posted, non-stopword) tokens the spoken text must
/// share with the index to be considered at all — enough distinctive signal that a phrase
/// built from common devotional words cannot fire.
const MIN_DISCRIMINATIVE_TOKENS: usize = 3;

/// The best verse must cover at least this fraction of either the verse's or the spoken
/// text's IDF mass. Full/near-full quotes clear it easily; ordinary speech does not.
const COVERAGE_THRESHOLD: f64 = 0.55;

/// Absolute IDF-mass floor on the shared tokens — the overlap must include enough *rare*
/// words, so a match built from only common/moderate vocabulary is rejected.
const MIN_SHARED_MASS: f64 = 14.0;

/// Hard cap on candidate verses scored per query (bounds per-call work under any input).
const MAX_CANDIDATES: usize = 5_000;

/// Common devotional / liturgical / archaic words that recur across both worship speech and
/// scripture. They are excluded from candidate generation (not posted, not counted toward
/// [`MIN_DISCRIMINATIVE_TOKENS`]) so a phrase like "we give thanks and praise to almighty
/// God" cannot fire on a verse that merely shares those words — only distinctive vocabulary
/// drives a match. They DO still contribute to the IDF-mass coverage score of a genuine
/// quote. Provisional (spike-gated S11).
const STOPWORDS: &[&str] = &[
    // Divine names / titles
    "god",
    "lord",
    "jesus",
    "christ",
    "holy",
    "spirit",
    "father",
    "almighty",
    "king",
    // Worship / thanksgiving vocabulary (the flooding class)
    "thanks",
    "thank",
    "thankful",
    "praise",
    "praises",
    "glory",
    "glorify",
    "mercy",
    "merciful",
    "bless",
    "blessed",
    "blessing",
    "worship",
    "pray",
    "prayer",
    "amen",
    "hallelujah",
    "alleluia",
    "grace",
    "faith",
    "hope",
    "peace",
    "love",
    "name",
    "heart",
    "hearts",
    "lift",
    "give",
    "given",
    "unto",
    "hosanna",
    "adore",
    "honour",
    "honor",
    // Very common archaic function words (belt-and-suspenders under the df cap)
    "thou",
    "thee",
    "thy",
    "thine",
    "ye",
    "hath",
    "shall",
    "art",
    "saith",
    "behold",
    "therefore",
    "upon",
    "come",
    "let",
];

/// Lazily-built set of [`STOPWORDS`] for O(1) lookup.
fn stopwords() -> &'static HashSet<&'static str> {
    static SET: OnceLock<HashSet<&'static str>> = OnceLock::new();
    SET.get_or_init(|| STOPWORDS.iter().copied().collect())
}

/// The prebuilt fuzzy-match index for one translation.
struct QuoteIndex {
    /// Document frequency: how many verses contain each token.
    df: HashMap<String, u32>,
    /// Postings for discriminative (non-stopword, non-ubiquitous) tokens only:
    /// token → ascending verse indices.
    postings: HashMap<String, Vec<u32>>,
    /// Precomputed total IDF mass of each verse's unique tokens (indexed by verse position).
    verse_mass: Vec<f64>,
    /// Number of verses in the translation.
    n: usize,
}

impl QuoteIndex {
    /// IDF weight of a token: `ln(n / (1 + df))`, floored at 0.
    fn idf(&self, token: &str) -> f64 {
        let df = self.df.get(token).copied().unwrap_or(0) as f64;
        (self.n as f64 / (1.0 + df)).ln().max(0.0)
    }
}

/// Split text into lowercase alphanumeric tokens of length ≥ 2 (drops punctuation, single
/// letters, and the possessive `s` of `God's`). Deterministic.
fn tokenize(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() >= 2)
        .map(|w| w.to_lowercase())
        .collect()
}

/// Whether `token` may drive candidate generation (posted): not a stopword and not ubiquitous.
fn is_discriminative(token: &str, df: u32, cap: u32) -> bool {
    df <= cap && !stopwords().contains(token)
}

/// Build the inverted index for `verses` (one-time, cached).
fn build_index(verses: &[crate::Verse]) -> QuoteIndex {
    let n = verses.len();
    let mut df: HashMap<String, u32> = HashMap::new();
    // Unique tokens per verse (kept for the second pass; freed after).
    let mut per_verse: Vec<Vec<String>> = Vec::with_capacity(n);
    for v in verses {
        let toks: HashSet<String> = tokenize(&v.text).into_iter().collect();
        for tok in &toks {
            *df.entry(tok.clone()).or_insert(0) += 1;
        }
        per_verse.push(toks.into_iter().collect());
    }
    // Second pass: postings for discriminative tokens + precomputed per-verse IDF mass.
    let cap = ((n as f64) * DF_CAP_FRACTION).ceil() as u32;
    let idf = |tok: &str| -> f64 {
        let d = df.get(tok).copied().unwrap_or(0) as f64;
        (n as f64 / (1.0 + d)).ln().max(0.0)
    };
    let mut postings: HashMap<String, Vec<u32>> = HashMap::new();
    let mut verse_mass: Vec<f64> = Vec::with_capacity(n);
    for (vi, toks) in per_verse.iter().enumerate() {
        // Deterministic mass: sum IDF over the verse's tokens in sorted order.
        let mut sorted: Vec<&String> = toks.iter().collect();
        sorted.sort();
        verse_mass.push(sorted.iter().map(|t| idf(t)).sum());
        for tok in toks {
            if is_discriminative(tok, df.get(tok).copied().unwrap_or(0), cap) {
                // Verses are visited in ascending index order → each postings vec is sorted.
                postings.entry(tok.clone()).or_default().push(vi as u32);
            }
        }
    }
    QuoteIndex {
        df,
        postings,
        verse_mass,
        n,
    }
}

/// The cached index for translation `t` (built at most once per translation).
fn quote_index(t: Translation) -> &'static QuoteIndex {
    // One cell per translation; the array length is coupled to the variant count below.
    const _: () = assert!(
        Translation::ALL.len() == 5,
        "resize CELLS to match Translation"
    );
    static CELLS: [OnceLock<QuoteIndex>; 5] = [
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
    ];
    CELLS[t as usize].get_or_init(|| build_index(index_of(t)))
}

/// Most-likely verse(s) for a spoken quotation, in the DEFAULT translation (KJV).
///
/// Returns canonical references (e.g. `["John 3:16"]`) — at most one, the best match above
/// the precision thresholds — or an empty vec when nothing matches confidently. The result
/// is a *suggestion* for the operator-confirmed queue, never auto-displayed (FR-115).
pub fn match_quote(text: &str) -> Vec<String> {
    match_quote_in(Translation::default(), text)
}

/// [`match_quote`] against an explicit translation.
pub fn match_quote_in(t: Translation, text: &str) -> Vec<String> {
    let verses = index_of(t);
    let n = verses.len();
    if n == 0 {
        return Vec::new();
    }
    let idx = quote_index(t);

    // Unique query tokens; the discriminative (posted, non-stopword) ones drive candidates.
    let q_tokens: HashSet<String> = tokenize(text).into_iter().collect();
    let mut discriminative: Vec<&String> = q_tokens
        .iter()
        .filter(|tok| idx.postings.contains_key(*tok))
        .collect();
    if discriminative.len() < MIN_DISCRIMINATIVE_TOKENS {
        return Vec::new();
    }
    // Rarest tokens first (deterministic: by df, then by token) so the candidate cap keeps
    // the most informative postings.
    discriminative.sort_by(|a, b| idx.df[*a].cmp(&idx.df[*b]).then_with(|| a.cmp(b)));

    // Candidate verses = union of the discriminative tokens' postings (bounded). BTreeSet
    // keeps them in ascending (canonical) verse order for a deterministic tie-break.
    let mut candidates: BTreeSet<u32> = BTreeSet::new();
    'gather: for tok in &discriminative {
        for &vi in &idx.postings[*tok] {
            candidates.insert(vi);
            if candidates.len() >= MAX_CANDIDATES {
                break 'gather;
            }
        }
    }

    // The spoken text's total IDF mass (summed in sorted order — deterministic).
    let mut q_sorted: Vec<&String> = q_tokens.iter().collect();
    q_sorted.sort();
    let query_mass: f64 = q_sorted.iter().map(|t| idx.idf(t)).sum();

    // Score each candidate; keep the strictly-best (ties resolve to the lowest verse index
    // because we iterate ascending and only replace on a strict improvement).
    let mut best: Option<(f64, f64, u32)> = None; // (score, shared_mass, verse_idx)
    for &vi in &candidates {
        let v = &verses[vi as usize];
        // Shared IDF mass, summed over the verse's tokens in sorted order (deterministic).
        let v_tokens: BTreeSet<String> = tokenize(&v.text).into_iter().collect();
        let shared_mass: f64 = v_tokens
            .iter()
            .filter(|tok| q_tokens.contains(*tok))
            .map(|tok| idx.idf(tok))
            .sum();
        let verse_mass = idx.verse_mass[vi as usize];
        if verse_mass <= 0.0 || shared_mass < MIN_SHARED_MASS {
            continue;
        }
        let verse_coverage = shared_mass / verse_mass;
        let query_coverage = if query_mass > 0.0 {
            shared_mass / query_mass
        } else {
            0.0
        };
        // A full/near-full quote covers most of the verse; a partial quote of a long verse
        // still covers most of the (short) spoken text — accept either.
        let score = verse_coverage.max(query_coverage);
        if score < COVERAGE_THRESHOLD {
            continue;
        }
        let better = match best {
            None => true,
            Some((bscore, bmass, _)) => score > bscore || (score == bscore && shared_mass > bmass),
        };
        if better {
            best = Some((score, shared_mass, vi));
        }
    }

    match best {
        Some((_, _, vi)) => vec![display_reference(&verses[vi as usize])],
        None => Vec::new(),
    }
}
