//! Fuzzy quote/paraphrase detection — the **fuzzy** rung of the R4 detection ladder
//! (parse → exact → fuzzy → semantic). When a verse is spoken as a near-verbatim quotation
//! (its reference NOT named), match the spoken text against the bundled corpus and return
//! the most-likely verse as a canonical reference (e.g. `"John 3:16"`).
//!
//! Approach (offline, deterministic, precision-biased):
//! - Lazily build (once, `OnceLock`) an **inverted index** over the translation: document
//!   frequency per token + postings (token → verse ids) for *discriminative* tokens only
//!   (ubiquitous words like "the"/"and" are not posted, which bounds candidate generation).
//! - Score each candidate verse by **IDF-weighted token overlap** with the spoken text, and
//!   accept the best verse only when the overlap covers enough of the verse (or the spoken
//!   text) AND carries enough rare-word evidence. Ordinary speech shares too little rare
//!   vocabulary with any single verse, so it does not fire (precision over recall, FR-121).
//!
//! This is **suggestion-only**: the returned reference flows through the existing
//! operator-confirmed approval queue and is never auto-displayed (FR-115). Genuine loose
//! paraphrase (little shared vocabulary) is intentionally out of reach here — that is the
//! semantic rung, which research bars from auto-display and which has no infrastructure yet.
//! Thresholds are provisional and spike-gated (S11).

use std::collections::{BTreeSet, HashMap, HashSet};
use std::sync::OnceLock;

use crate::{display_reference, index_of, Translation};

/// Tokens present in more than this fraction of verses are treated as non-discriminative and
/// are not posted to the inverted index (they still contribute their small IDF weight to
/// scoring). Bounds candidate generation and postings size.
const DF_CAP_FRACTION: f64 = 0.03;

/// Minimum number of *discriminative* (posted) tokens the spoken text must share with the
/// index to be considered at all — enough distinctive signal to avoid firing on a generic
/// phrase built from a couple of moderately-common words.
const MIN_DISCRIMINATIVE_TOKENS: usize = 3;

/// The best verse must cover at least this fraction of either the verse's or the spoken
/// text's IDF mass. Full/near-full quotes clear it easily; ordinary speech does not.
const COVERAGE_THRESHOLD: f64 = 0.55;

/// Absolute IDF-mass floor on the shared tokens — guarantees the overlap includes enough
/// *rare* words, so a match built from only common/moderate vocabulary is rejected.
const MIN_SHARED_MASS: f64 = 14.0;

/// Hard cap on candidate verses scored per query (bounds per-call work under any input).
const MAX_CANDIDATES: usize = 5_000;

/// The prebuilt fuzzy-match index for one translation.
struct QuoteIndex {
    /// Document frequency: how many verses contain each token.
    df: HashMap<String, u32>,
    /// Postings for discriminative tokens only: token → ascending verse indices.
    postings: HashMap<String, Vec<u32>>,
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

/// Build the inverted index for `verses` (one-time, cached).
fn build_index(verses: &[crate::Verse]) -> QuoteIndex {
    let n = verses.len();
    let mut df: HashMap<String, u32> = HashMap::new();
    // Unique tokens per verse (kept only for the second pass; freed after).
    let mut per_verse: Vec<Vec<String>> = Vec::with_capacity(n);
    for v in verses {
        let toks: HashSet<String> = tokenize(&v.text).into_iter().collect();
        for tok in &toks {
            *df.entry(tok.clone()).or_insert(0) += 1;
        }
        per_verse.push(toks.into_iter().collect());
    }
    let cap = ((n as f64) * DF_CAP_FRACTION).ceil() as u32;
    let mut postings: HashMap<String, Vec<u32>> = HashMap::new();
    // Verses are visited in ascending index order, so each postings vec is already sorted.
    for (vi, toks) in per_verse.iter().enumerate() {
        for tok in toks {
            if df.get(tok).copied().unwrap_or(0) <= cap {
                postings.entry(tok.clone()).or_default().push(vi as u32);
            }
        }
    }
    QuoteIndex { df, postings, n }
}

/// The cached index for translation `t` (built at most once per translation).
fn quote_index(t: Translation) -> &'static QuoteIndex {
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

    // Unique query tokens; the discriminative (posted) ones drive candidate generation.
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

    // The spoken text's total IDF mass (for the query-coverage side of the metric).
    let query_mass: f64 = q_tokens.iter().map(|t| idx.idf(t)).sum();

    // Score each candidate; keep the strictly-best (ties resolve to the lowest verse index
    // because we iterate ascending and only replace on a strict improvement).
    let mut best: Option<(f64, f64, u32)> = None; // (score, shared_mass, verse_idx)
    for &vi in &candidates {
        let v = &verses[vi as usize];
        let v_tokens: HashSet<String> = tokenize(&v.text).into_iter().collect();
        let mut verse_mass = 0.0;
        let mut shared_mass = 0.0;
        for tok in &v_tokens {
            let w = idx.idf(tok);
            verse_mass += w;
            if q_tokens.contains(tok) {
                shared_mass += w;
            }
        }
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
