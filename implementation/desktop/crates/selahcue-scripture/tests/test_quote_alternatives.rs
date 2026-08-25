//! Detection alternatives: when a spoken paraphrase fits several verses, the operator sees the
//! runner-ups instead of a single answer that looks more certain than the evidence was.
//!
//! The matcher always computed these — it scored every candidate and then threw all but the
//! winner away as it went. The change is a **bounded top-N**, not "stop discarding": an
//! unbounded list of every verse that scored above threshold would be 25 entries for a common
//! phrase, which is a search results page, not a disambiguation aid.
//!
//! Every truncation assertion here is preceded by a check that the corpus **actually produced
//! more candidates than the cap**. Without that, a query with no runner-ups would leave the
//! truncation branch dead and the test would pass while proving nothing — the same failure that
//! made a byte budget no legal deck could exceed look like a working guard.

#![allow(clippy::unwrap_used)]

use selahcue_scripture::{
    match_quote_ranked, match_quote_scored, ranked_offered_in, Translation, MAX_ALTERNATIVES,
    MAX_RANKED,
};

/// The cap must admit at least one alternative, or "alternatives" is a contradiction and every
/// test below is asserting against a branch that cannot run. Pinned at the point of use so a
/// later change to the constant breaks the build rather than quietly hollowing these tests out.
const _: () = assert!(MAX_RANKED >= 2);
const _: () = assert!(MAX_ALTERNATIVES >= 1);
const _: () = assert!(MAX_RANKED == MAX_ALTERNATIVES + 1);

/// A paraphrase that genuinely fits several verses. Ephesians 2:8 is the quotation; 2:5 carries
/// the same "by grace ye are saved" clause, which is exactly the ambiguity an operator needs to
/// see rather than have resolved for them.
const AMBIGUOUS: &str = "for by grace are ye saved through faith and that not of yourselves";

/// A quotation with a clear winner and only one weak runner-up — fewer candidates than the cap.
const NARROW: &str = "i can do all things through christ which strengtheneth me";

fn offered(text: &str) -> usize {
    ranked_offered_in(Translation::default(), text)
}

#[test]
fn a_paraphrase_that_fits_several_verses_reports_its_alternatives() {
    // The premise, asserted BEFORE the contract: the corpus really does produce more candidates
    // than the cap, so truncation is exercised rather than merely assumed.
    let seen = offered(AMBIGUOUS);
    assert!(
        seen > MAX_RANKED,
        "premise unmet: only {seen} candidates passed the thresholds, which is not more than \
         the cap of {MAX_RANKED} — the truncation branch was never reached, so this test \
         proves nothing about the bound"
    );

    let ranked = match_quote_ranked(AMBIGUOUS);
    assert_eq!(
        ranked.len(),
        MAX_RANKED,
        "a query with {seen} candidates must be truncated to the cap"
    );
    assert_eq!(
        ranked[0].0, "Ephesians 2:8",
        "the best match must be unchanged by ranking"
    );
    assert!(
        ranked[1..].iter().any(|(r, _)| r == "Ephesians 2:5"),
        "the verse sharing the quoted clause is the alternative worth showing; got {ranked:?}"
    );
}

/// Truncation must drop the WORST, not an arbitrary end. Asserted by confidence ordering plus
/// the premise that something really was dropped.
#[test]
fn ranking_keeps_the_strongest_candidates_and_orders_them() {
    let seen = offered(AMBIGUOUS);
    assert!(seen > MAX_RANKED, "premise: {seen} candidates > cap");

    let ranked = match_quote_ranked(AMBIGUOUS);
    let confidences: Vec<u8> = ranked.iter().map(|(_, c)| *c).collect();
    let mut sorted = confidences.clone();
    sorted.sort_unstable_by(|a, b| b.cmp(a));
    assert_eq!(
        confidences, sorted,
        "alternatives must be ordered best-first, or the operator's second choice is not \
         actually the second-best reading: {ranked:?}"
    );
    assert!(
        confidences[0] >= *confidences.last().unwrap(),
        "the head must be the strongest"
    );
}

/// The bound must not become padding. A query with fewer candidates than the cap returns fewer
/// — inventing entries to fill the list would fabricate alternatives that do not exist, which is
/// the same class of defect as every other item in this programme.
#[test]
fn fewer_candidates_than_the_cap_are_not_padded_out() {
    let seen = offered(NARROW);
    assert!(
        seen > 0 && seen < MAX_RANKED,
        "premise unmet: {seen} candidates is not strictly between zero and the cap of \
         {MAX_RANKED}, so the under-cap branch was not exercised"
    );

    let ranked = match_quote_ranked(NARROW);
    assert_eq!(
        ranked.len(),
        seen,
        "with {seen} real candidates the list must hold exactly {seen}, never {MAX_RANKED}"
    );
}

/// The detection queue turns every returned reference into its own approval card, so the primary
/// path must still return exactly one. Reporting three here would put three cards in front of
/// the operator for a single spoken sentence — noise, not disambiguation.
#[test]
fn the_detection_path_still_returns_exactly_one_match() {
    let seen = offered(AMBIGUOUS);
    assert!(seen > MAX_RANKED, "premise: this query has alternatives");

    let scored = match_quote_scored(AMBIGUOUS);
    assert_eq!(
        scored.len(),
        1,
        "match_quote_scored feeds the approval queue and must stay single-valued"
    );
    assert_eq!(
        scored[0],
        match_quote_ranked(AMBIGUOUS)[0],
        "and it must be the SAME best match the ranked list reports, or the card the operator \
         approves is not the one the alternatives were computed against"
    );
}

#[test]
fn alternatives_are_distinct_references() {
    let ranked = match_quote_ranked(AMBIGUOUS);
    let mut refs: Vec<&str> = ranked.iter().map(|(r, _)| r.as_str()).collect();
    let n = refs.len();
    refs.sort_unstable();
    refs.dedup();
    assert_eq!(
        refs.len(),
        n,
        "the same verse must never appear twice: {ranked:?}"
    );
}

#[test]
fn ordinary_speech_yields_no_alternatives() {
    for text in [
        "god is good all the time",
        "let us welcome one another this morning",
    ] {
        assert_eq!(offered(text), 0, "premise: {text:?} matches nothing");
        assert!(
            match_quote_ranked(text).is_empty(),
            "a non-quotation must not acquire alternatives"
        );
    }
}

#[test]
fn ranking_is_deterministic() {
    assert_eq!(match_quote_ranked(AMBIGUOUS), match_quote_ranked(AMBIGUOUS));
    assert_eq!(offered(AMBIGUOUS), offered(AMBIGUOUS));
}

/// A stock biblical phrase matches many verses **equally well** — "and it came to pass in those
/// days" ties 17 ways at an identical score. Which three the operator is shown must therefore be
/// decided by the tie-break, not by iteration order, or the same sentence would surface different
/// alternatives run to run and an operator could not trust what they saw.
///
/// The equal-confidence assertion is this test's own vacuity guard: if the three differed in
/// score, the ordering would have come from the score leg and the tie-break would be unexercised.
#[test]
fn tied_candidates_are_ordered_deterministically() {
    const TIED: &str = "and it came to pass in those days";

    let seen = offered(TIED);
    assert!(
        seen > MAX_RANKED,
        "premise unmet: {seen} candidates is not more than the cap, so nothing was truncated"
    );

    let ranked = match_quote_ranked(TIED);
    assert_eq!(ranked.len(), MAX_RANKED);

    let first = ranked[0].1;
    assert!(
        ranked.iter().all(|(_, c)| *c == first),
        "premise unmet: the kept candidates are NOT tied ({ranked:?}), so their order was \
         decided by score and the tie-break leg went unexercised"
    );

    // Ties resolve to the earliest verse in canon order — the rule the original running-max
    // implemented by replacing only on a strict improvement.
    assert_eq!(
        ranked.iter().map(|(r, _)| r.as_str()).collect::<Vec<_>>(),
        ["Exodus 2:11", "Judges 19:1", "1 Samuel 28:1"],
        "tied candidates must resolve to the earliest verses in canon order"
    );
    assert_eq!(
        match_quote_ranked(TIED),
        ranked,
        "and the resolution must be stable across runs"
    );
}
