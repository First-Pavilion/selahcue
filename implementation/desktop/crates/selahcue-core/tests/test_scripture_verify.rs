//! `verify_scriptures` — the pure algorithm (86akby820; FR-125/FR-128).
//!
//! This crate cannot depend on `selahcue-scripture` (that crate depends on this one), so
//! every test here drives `verify_scriptures` with a STUB oracle — a fixed set of
//! reference strings treated as "exists". That is deliberate: these tests guard the
//! algorithm (parsing, iteration order, dedup, bounding, embedded-text scanning, never
//! silently dropping an unparseable segment), not the real Bible text. The real,
//! end-to-end behaviour against the bundled KJV text — including the exact
//! looks-plausible-but-isn't cases from the ticket (Obadiah 2:1, 3 John 4:12, Jude 2:1,
//! Philemon 2:3) — is covered in `selahcue-operator`'s tests, the layer that actually
//! wires the real `selahcue_scripture::verses` oracle in.

use selahcue_core::providers::{
    verify_scriptures, DraftCaveat, NotePoint, NoteSection, ScriptureVerdict,
};
use std::collections::HashSet;

/// A stub "exists" oracle: true iff the reference's canonical `to_string()` is in `known`.
fn oracle(
    known: &'static [&'static str],
) -> impl FnMut(&selahcue_core::scripture::Reference) -> bool {
    let known: HashSet<&str> = known.iter().copied().collect();
    move |r| known.contains(r.to_string().as_str())
}

fn verdict(reference: &str, verified: bool) -> ScriptureVerdict {
    ScriptureVerdict {
        reference: reference.to_string(),
        verified,
    }
}

// ===========================================================================
// 1 · The extracted `scriptures` list — table-driven
// ===========================================================================

#[test]
fn a_valid_known_reference_is_verified() {
    let verdicts = verify_scriptures(&["John 3:16".to_string()], &[], oracle(&["John 3:16"]));
    assert_eq!(verdicts, vec![verdict("John 3:16", true)]);
}

#[test]
fn a_reference_the_oracle_does_not_know_is_unverified_not_dropped() {
    // Stands in for "chapter past the book's end" / "verse past the chapter's end" at
    // this layer: the oracle simply reports it does not exist, exactly as the real
    // `selahcue_scripture::verses` would for an out-of-canon reference.
    let verdicts = verify_scriptures(&["3 John 4:12".to_string()], &[], oracle(&["John 3:16"]));
    assert_eq!(
        verdicts,
        vec![verdict("3 John 4:12", false)],
        "an out-of-canon reference must be REPORTED as unverified, never silently dropped"
    );
}

#[test]
fn an_unparseable_reference_is_unverified_and_kept_verbatim_never_dropped() {
    // The ticket's most important negative requirement: `parse()` (scripture.rs) silently
    // drops what it cannot parse via `filter_map(...ok())`. `verify_scriptures` must NOT
    // use that entry point — every segment gets a verdict, including this one.
    let verdicts = verify_scriptures(&["not a reference at all".to_string()], &[], oracle(&[]));
    assert_eq!(
        verdicts,
        vec![verdict("not a reference at all", false)],
        "an unparseable reference must still appear, verbatim, marked unverified"
    );
}

#[test]
fn a_blank_or_whitespace_only_entry_produces_no_verdict() {
    // Not a reference at all — nothing to report either way, verified or not.
    let verdicts = verify_scriptures(&["   ".to_string(), "".to_string()], &[], oracle(&[]));
    assert!(verdicts.is_empty());
}

#[test]
fn every_entry_in_a_mixed_list_gets_its_own_independent_verdict() {
    let verdicts = verify_scriptures(
        &[
            "John 3:16".to_string(),
            "3 John 4:12".to_string(),
            "gibberish".to_string(),
        ],
        &[],
        oracle(&["John 3:16"]),
    );
    assert_eq!(
        verdicts,
        vec![
            verdict("John 3:16", true),
            verdict("3 John 4:12", false),
            verdict("gibberish", false),
        ]
    );
}

// ===========================================================================
// 2 · References embedded in a section's body text — the more dangerous case
// ===========================================================================

#[test]
fn a_reference_embedded_in_a_flat_sections_item_text_is_found_and_verified() {
    let sections = vec![NoteSection::flat(
        "Illustrations",
        vec!["As it says in Isaiah 55:1, come.".to_string()],
    )];
    let verdicts = verify_scriptures(&[], &sections, oracle(&["Isaiah 55:1"]));
    assert_eq!(verdicts, vec![verdict("Isaiah 55:1", true)]);
}

#[test]
fn a_fabricated_reference_embedded_inside_a_sermon_point_is_found_and_marked_unverified() {
    // The exact scenario the ticket calls out: a fabricated verse quoted inside a sermon
    // point is exactly as dangerous as one in the reference list, and checking only the
    // tidy list would miss it. `points`/`sub_points` text must be scanned too, not just
    // flat `items`.
    let sections = vec![NoteSection::outline(
        "Main points",
        vec![NotePoint {
            text: "This truth is affirmed in Jude 2:1 as well.".to_string(),
            sub_points: vec!["Some quote from Philemon 2:3 too.".to_string()],
        }],
    )];
    let verdicts = verify_scriptures(&[], &sections, oracle(&[]));
    assert_eq!(
        verdicts,
        vec![verdict("Jude 2:1", false), verdict("Philemon 2:3", false)],
        "both the point text and its sub-point text must be scanned"
    );
}

#[test]
fn the_same_reference_in_the_list_and_embedded_in_text_is_reported_once() {
    let sections = vec![NoteSection::flat(
        "Illustrations",
        vec!["John 3:16 says it plainly.".to_string()],
    )];
    let verdicts = verify_scriptures(
        &["John 3:16".to_string()],
        &sections,
        oracle(&["John 3:16"]),
    );
    assert_eq!(
        verdicts,
        vec![verdict("John 3:16", true)],
        "a reference appearing twice (list + embedded) must not be double-reported"
    );
}

#[test]
fn a_section_the_operator_left_off_is_not_scanned_because_it_never_reaches_the_draft() {
    // Not this function's job to gate on `IncludeInNotes` — a disabled section never
    // reaches `NoteDraft.sections` at all (openai.rs's own second layer), so
    // `verify_scriptures` naturally never sees its text. Documented here as the reason
    // this function takes no `IncludeInNotes` parameter.
    let verdicts = verify_scriptures(&[], &[], oracle(&[]));
    assert!(verdicts.is_empty());
}

// ===========================================================================
// 3 · Bounded and total — never panics, never grows without limit
// ===========================================================================

#[test]
fn an_absurd_number_of_distinct_scriptures_is_bounded_not_unbounded() {
    let many: Vec<String> = (0..10_000)
        .map(|i| format!("garbage reference {i}"))
        .collect();
    let verdicts = verify_scriptures(&many, &[], oracle(&[]));
    assert!(
        verdicts.len() <= selahcue_core::providers::MAX_VERIFIED_REFERENCES,
        "got {} verdicts, bound is {}",
        verdicts.len(),
        selahcue_core::providers::MAX_VERIFIED_REFERENCES
    );
    assert_eq!(
        verdicts.len(),
        selahcue_core::providers::MAX_VERIFIED_REFERENCES,
        "10,000 DISTINCT candidates must actually hit the cap, not stop early for some \
         other reason — the positive control that proves the bound is exercised"
    );
}

#[test]
fn an_absurdly_long_single_item_does_not_panic_and_stays_bounded() {
    // A hostile/adversarial model output: one enormous string with many repeated
    // embedded-looking tokens. Must not panic and must not produce unbounded verdicts.
    let hostile = "Isaiah 55:1 ".repeat(50_000);
    let sections = vec![NoteSection::flat("Illustrations", vec![hostile])];
    let verdicts = verify_scriptures(&[], &sections, oracle(&["Isaiah 55:1"]));
    // The same reference repeated: at most ONE verdict (dedup), well under the cap either way.
    assert!(verdicts.len() <= 1);
}

#[test]
fn duplicates_do_not_erode_the_bound_budget_for_genuinely_distinct_references() {
    // The dedup-by-string-before-counting-toward-the-cap design: repeating one reference
    // thousands of times must not exhaust the budget that distinct references need.
    let mut many = vec!["John 3:16".to_string(); 9_999];
    many.push("Romans 8:28".to_string());
    let verdicts = verify_scriptures(&many, &[], oracle(&["John 3:16", "Romans 8:28"]));
    assert_eq!(
        verdicts,
        vec![verdict("John 3:16", true), verdict("Romans 8:28", true)],
        "9,999 duplicates of one reference must not crowd out a later distinct one"
    );
}

// ===========================================================================
// 4 · The caveat side: an unverified verdict is exactly what a caller turns into a
//     DraftCaveat — this pins the shape a caller like selahcue-operator relies on.
// ===========================================================================

#[test]
fn only_unverified_verdicts_are_the_caveat_shape_callers_are_expected_to_extract() {
    let verdicts = verify_scriptures(
        &["John 3:16".to_string(), "3 John 4:12".to_string()],
        &[],
        oracle(&["John 3:16"]),
    );
    let caveats: Vec<DraftCaveat> = verdicts
        .iter()
        .filter(|v| !v.verified)
        .map(|v| DraftCaveat::ScriptureUnverified {
            reference: v.reference.clone(),
        })
        .collect();
    assert_eq!(
        caveats,
        vec![DraftCaveat::ScriptureUnverified {
            reference: "3 John 4:12".to_string()
        }]
    );
}
