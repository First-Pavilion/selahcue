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
/// text's IDF mass. Set low (0.30) so allusions/descriptions — not just verbatim quotes —
/// surface (e.g. "as you brought Peter out of the prison" → Acts 12, "thrown into the fiery
/// furnace" → Daniel 3), returning their real (possibly low) confidence for the operator to
/// judge. Recall-biased on purpose: detections are operator-confirmed and never auto-display
/// (FR-115), so a weak coincidental card is low-harm; the stopword list + [`MIN_SHARED_MASS`]
/// + [`MIN_DISCRIMINATIVE_TOKENS`] still keep pure devotional/greeting filler from firing.
const COVERAGE_THRESHOLD: f64 = 0.30;

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
        Translation::ALL.len() == 6,
        "resize CELLS to match Translation"
    );
    static CELLS: [OnceLock<QuoteIndex>; 6] = [
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
        OnceLock::new(),
    ];
    CELLS[t as usize].get_or_init(|| build_index(index_of(t)))
}

/// How many **alternative** verses a quotation match reports alongside the best one.
///
/// A spoken paraphrase often fits several verses — "by grace you have been saved" scores against
/// Ephesians 2:5 and 2:8 — and the matcher used to compute every one of them and then throw all
/// but the winner away. The operator, who is the one deciding, never saw that a second reading
/// existed. Small on purpose: this is a disambiguation aid on one approval card, not a search
/// results page.
pub const MAX_ALTERNATIVES: usize = 2;

/// Total ranked results: the best plus its alternatives.
pub const MAX_RANKED: usize = MAX_ALTERNATIVES + 1;

/// The ranked list must be able to hold more than one entry, or "alternatives" is a contradiction
/// and every test about truncation would be asserting against a branch that can never run.
const _: () = assert!(MAX_RANKED >= 2);

/// One scored candidate verse.
#[derive(Debug, Clone, Copy)]
struct Ranked {
    score: f64,
    shared_mass: f64,
    verse: u32,
}

/// Does `a` rank ahead of `b`?
///
/// This is the ORIGINAL tie-break, preserved exactly: strictly higher score wins; on an equal
/// score the greater shared IDF mass wins; on both equal the lower verse index wins (the old
/// loop iterated ascending and replaced only on a strict improvement, so the first-seen verse
/// held its place). Changing any leg of this silently changes which verse the operator is
/// offered first, so it is kept in one function rather than inlined.
fn ranks_before(a: &Ranked, b: &Ranked) -> bool {
    if a.score != b.score {
        return a.score > b.score;
    }
    // NOTE: this leg is **unreachable with the current scoring function**, and no test covers
    // it. `score` is `max(shared_mass/verse_mass, shared_mass/query_mass)`, and in the case
    // that produces ties the dominant term divides by a constant — so an equal score implies an
    // equal shared mass. Measured across 12 quotation queries: 30 tie groups, **0** in which
    // the masses differed. It is retained because it is pre-existing tie-break semantics that
    // would start deciding the moment the scoring function changes, but it is unreached rather
    // than verified — a mutation removing it survives the battery, correctly.
    if a.shared_mass != b.shared_mass {
        return a.shared_mass > b.shared_mass;
    }
    // This leg IS reachable and load-bearing: it is what makes ranking deterministic when
    // several verses match a stock phrase equally well ("and it came to pass in those days"
    // ties 17 ways). Pinned by `tied_candidates_are_ordered_deterministically`.
    false
}

/// A bounded top-N accumulator: a **fixed-size array**, so it cannot allocate and cannot grow.
///
/// The bound is a property of the type rather than of a cap a caller must remember to apply —
/// there is no `Vec` here to forget to truncate. `offered` counts every candidate presented,
/// which is what lets a test prove it actually saw more candidates than it kept; without that,
/// a corpus where no verse ever has a runner-up would leave the truncation branch dead and its
/// test silently vacuous.
struct TopRanked {
    slots: [Option<Ranked>; MAX_RANKED],
    offered: usize,
}

impl TopRanked {
    fn new() -> Self {
        TopRanked {
            slots: [None; MAX_RANKED],
            offered: 0,
        }
    }

    /// Offer a candidate. Kept if it ranks above one already held, or if there is room; the
    /// worst is displaced when full.
    fn offer(&mut self, cand: Ranked) {
        self.offered += 1;
        for i in 0..MAX_RANKED {
            match self.slots[i] {
                None => {
                    self.slots[i] = Some(cand);
                    return;
                }
                Some(held) if ranks_before(&cand, &held) => {
                    // Shift the tail down one and drop whatever falls off the end.
                    for j in (i + 1..MAX_RANKED).rev() {
                        self.slots[j] = self.slots[j - 1];
                    }
                    self.slots[i] = Some(cand);
                    return;
                }
                Some(_) => {}
            }
        }
    }

    /// The kept candidates, best first.
    fn ranked(&self) -> impl Iterator<Item = &Ranked> {
        self.slots.iter().flatten()
    }
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
    match_quote_scored_in(t, text)
        .into_iter()
        .map(|(r, _)| r)
        .collect()
}

/// Like [`match_quote`], but each suggestion carries the detector's **confidence** as a
/// whole percent (`0..=100`) — the greater of the verse/query IDF coverage, scaled. Feeds
/// the operator's match-% pill so a fuzzy paraphrase reads as e.g. "72% MATCH". Still a
/// suggestion only, never auto-displayed (FR-115).
pub fn match_quote_scored(text: &str) -> Vec<(String, u8)> {
    match_quote_scored_in(Translation::default(), text)
}

/// Map a coverage score (`>= COVERAGE_THRESHOLD`, at most `1.0`) to a whole-percent
/// confidence for the operator UI. Saturating: a verbatim quote can read 100%.
fn score_to_confidence(score: f64) -> u8 {
    (score * 100.0).round().clamp(0.0, 100.0) as u8
}

/// [`match_quote_scored`] against an explicit translation.
///
/// Still at most ONE result — the best match. Alternatives are a separate, opt-in read
/// ([`match_quote_ranked_in`]), because this function feeds the detection queue and every entry
/// it returns becomes its own approval card: reporting three here would put three cards in front
/// of the operator for a single spoken sentence, which is noise, not disambiguation.
pub fn match_quote_scored_in(t: Translation, text: &str) -> Vec<(String, u8)> {
    let (mut ranked, _) = rank_in(t, text);
    ranked.truncate(1);
    ranked
}

/// The best match for a spoken quotation **plus up to [`MAX_ALTERNATIVES`] runner-ups**, best
/// first, each with its confidence — in the default translation (KJV).
///
/// For the operator's approval card: when a paraphrase fits several verses, the second reading
/// is a fact the matcher already computed, and hiding it made the card look more certain than
/// the evidence was. Bounded by construction — see [`MAX_RANKED`].
pub fn match_quote_ranked(text: &str) -> Vec<(String, u8)> {
    match_quote_ranked_in(Translation::default(), text)
}

/// [`match_quote_ranked`] against an explicit translation.
pub fn match_quote_ranked_in(t: Translation, text: &str) -> Vec<(String, u8)> {
    rank_in(t, text).0
}

/// How many candidates passed the precision thresholds and were offered to the bounded top-N.
///
/// **A test seam, not a product API.** A truncation test that does not first establish that more
/// candidates existed than were kept proves nothing — the corpus may simply never produce a
/// runner-up, leaving the branch dead. This makes that premise checkable.
#[doc(hidden)]
pub fn ranked_offered_in(t: Translation, text: &str) -> usize {
    rank_in(t, text).1
}

/// Rank a spoken quotation against a translation: the best match plus up to
/// [`MAX_ALTERNATIVES`] runner-ups, best first, with each one's confidence.
///
/// Returns the ranked list and **how many candidates were offered** to the bounded top-N. The
/// count exists for tests: proving the truncation actually truncated requires knowing that more
/// candidates were seen than kept, and without it a corpus that never produces a runner-up would
/// leave the truncation branch dead and its test vacuous.
fn rank_in(t: Translation, text: &str) -> (Vec<(String, u8)>, usize) {
    let verses = index_of(t);
    let n = verses.len();
    if n == 0 {
        return (Vec::new(), 0);
    }
    let idx = quote_index(t);

    // Unique query tokens; the discriminative (posted, non-stopword) ones drive candidates.
    let q_tokens: HashSet<String> = tokenize(text).into_iter().collect();
    let mut discriminative: Vec<&String> = q_tokens
        .iter()
        .filter(|tok| idx.postings.contains_key(*tok))
        .collect();
    if discriminative.len() < MIN_DISCRIMINATIVE_TOKENS {
        return (Vec::new(), 0);
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

    // Score each candidate into a BOUNDED top-N. Previously this kept a single running best and
    // discarded every runner-up as it went, so the alternatives the matcher had already computed
    // were unrecoverable by the time the operator saw the suggestion.
    let mut top = TopRanked::new();
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
        top.offer(Ranked {
            score,
            shared_mass,
            verse: vi,
        });
    }

    let ranked = top
        .ranked()
        .map(|r| {
            (
                display_reference(&verses[r.verse as usize]),
                score_to_confidence(r.score),
            )
        })
        .collect();
    (ranked, top.offered)
}
