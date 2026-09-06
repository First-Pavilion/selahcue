//! Integration tests for scripture detection over transcript text (R4). Public API.

#![allow(clippy::unwrap_used)]

use selahcue_core::detection::{
    detect, DetectionQueue, TranscriptEngine, MAX_DETECTIONS, MAX_DIGIT_RUN,
    NAMED_REFERENCE_CONFIDENCE,
};

// ---- Spoken-form detection correctness (the cases the story names) ----

#[test]
fn chapter_verse_spoken_words() {
    assert_eq!(
        detect("open your bibles to John chapter 3 verse 16"),
        vec!["John 3:16"]
    );
}

#[test]
fn numbered_book_whole_chapter() {
    assert_eq!(
        detect("we are reading First Corinthians 13 this morning"),
        vec!["1 Corinthians 13"]
    );
}

#[test]
fn fully_spelled_out_numbers() {
    assert_eq!(
        detect("as Romans eight twenty-eight reminds us"),
        vec!["Romans 8:28"]
    );
}

#[test]
fn spelled_chapter_and_verse_with_connectors() {
    assert_eq!(
        detect("turn to John chapter three verse sixteen"),
        vec!["John 3:16"]
    );
}

#[test]
fn hundreds_for_long_psalms() {
    assert_eq!(
        detect("Psalm one hundred nineteen verse one hundred five"),
        vec!["Psalms 119:105"]
    );
}

// ---- Digit-by-digit spoken numbers, e.g. "psalm one zero three" (86akd8903) ----
//
// Root cause: `classify()` had no entry for "zero"/"oh", so `take_number` stopped at
// the first one it hit. Verified against `detect()` directly before this fix landed:
// `detect("psalm one zero three")` did not fail to detect — it returned `["Psalms 1"]`,
// a WRONG reference, because the scan then found "psalm 1" as a shorter valid window.
// That is the severity this section pins: a silently wrong high-confidence detection,
// not a missed one.

#[test]
fn digit_by_digit_reading_with_zero_word_gives_the_correct_psalm() {
    assert_eq!(
        detect("psalm one zero three"),
        vec!["Psalms 103"],
        "before the 86akd8903 fix this returned [\"Psalms 1\"] — the wrong psalm, not no detection"
    );
}

#[test]
fn digit_by_digit_reading_with_oh_word_gives_the_correct_psalm() {
    // "oh" is the everyday spoken alternative to "zero" ("one oh three"); it must be
    // recognised the same way.
    assert_eq!(detect("psalm one oh three"), vec!["Psalms 103"]);
}

#[test]
fn digit_by_digit_reading_requires_an_internal_zero_or_oh() {
    // Positive control for the fix's discriminator: a run of single-digit words with NO
    // zero/oh must NOT be folded into one digit-concatenated number. "three four" has no
    // zero, so it must stay two separate numbers ("3", "4"), which the existing
    // space-shorthand chapter:verse parsing then reads as "John 3:4". If the zero/oh
    // guard in `take_digit_run` were ever dropped (folding any 2+ run of single-digit
    // words), this would instead wrongly produce "John 34" (whole chapter 34) — this
    // test is mutation-verified to catch exactly that (see PR evidence).
    assert_eq!(
        detect("John chapter three four"),
        vec!["John 3:4"],
        "a digit-word run with no zero/oh must use the existing cardinal folding, not the new digit-concatenation path"
    );
}

// ---- The zero/oh must be INTERNAL, not merely present (PR #27 review: Sana High,
// independently confirmed by Cody) ----
//
// The first cut of this fix accepted a zero/oh anywhere in a 2+ digit-word run,
// including trailing. A trailing "oh"/"zero" immediately after a real spoken digit is
// common English (interjection "oh", vocative "O Lord", idioms "zero tolerance"/"zero
// in"), and folding it multiplied the preceding digit by ten — reintroducing the exact
// silently-wrong-high-confidence-detection bug class 86akd8903 exists to fix, via a
// different trigger word. Worst case found: "psalm eight oh lord our lord how majestic
// is your name" is literally Psalm 8's own opening line (Psalm 8:1) — reading it aloud
// used to misdetect as Psalm 80.
//
// These eight phrases are Sana's exact probe set, each independently verified against
// both `162bcd8` (base, pre-86akd8903) and this fix — all eight must reproduce the base
// (correct) result.

#[test]
fn trailing_oh_after_a_chapter_digit_is_not_folded_into_it() {
    assert_eq!(
        detect("psalm eight oh lord our lord how majestic is your name"),
        vec!["Psalms 8"],
        "reading Psalm 8:1 aloud must not misdetect as Psalm 80"
    );
}

#[test]
fn trailing_oh_before_i_forget_is_not_folded() {
    assert_eq!(detect("john three oh before i forget"), vec!["John 3"]);
}

#[test]
fn oh_splitting_a_chapter_from_its_verse_does_not_weld_them() {
    assert_eq!(
        detect("john chapter three oh sixteen verse sixteen"),
        vec!["John 3"],
        "before this fix this produced \"John 30:16\""
    );
}

#[test]
fn trailing_oh_man_what_a_chapter_is_not_folded() {
    // Genesis 30 genuinely exists, so no downstream chapter-range check could ever have
    // caught this one — the guard itself has to be right.
    assert_eq!(
        detect("genesis three oh man what a chapter"),
        vec!["Genesis 3"]
    );
}

#[test]
fn trailing_oh_what_a_promise_is_not_folded() {
    assert_eq!(detect("romans eight oh what a promise"), vec!["Romans 8"]);
}

#[test]
fn trailing_oh_after_a_completed_chapter_verse_pair_is_not_folded() {
    assert_eq!(
        detect("john chapter three four oh how i love it"),
        vec!["John 3:4"],
        "before this fix this produced \"John 340\""
    );
}

#[test]
fn trailing_zero_tolerance_idiom_is_not_folded() {
    assert_eq!(detect("john three zero tolerance for sin"), vec!["John 3"]);
}

#[test]
fn trailing_zero_in_idiom_is_not_folded() {
    // Acts 20 genuinely exists too — same point as the Genesis case above.
    assert_eq!(detect("acts two zero in the year"), vec!["Acts 2"]);
}

#[test]
fn a_completed_digit_by_digit_fold_is_not_extended_by_a_following_trailing_oh() {
    // The harder case: an internal zero DOES fold ("one zero three" -> 103), but a
    // trailing "oh" immediately after that completed fold must not extend it further.
    assert_eq!(
        detect("psalm one zero three oh how great is our God"),
        vec!["Psalms 103"]
    );
}

#[test]
fn trailing_zero_with_nothing_after_it_does_not_fold() {
    // Recorded trade-off (see `take_digit_run`'s doc): a chapter/verse number that
    // genuinely ends in a spoken zero ("one zero" for a hypothetical "10") is not read
    // digit-by-digit here — indistinguishable from a trailing interjection, so it falls
    // back to plain single-digit handling, matching base (pre-86akd8903) behaviour.
    assert_eq!(detect("psalm one zero"), vec!["Psalms 1"]);
}

#[test]
fn digit_by_digit_run_is_bounded_and_never_panics() {
    // Pin the premise: the bound must still be small enough for this test to be
    // meaningful (i.e. shorter than the 10-word hostile run below).
    const _: () = assert!(MAX_DIGIT_RUN < 10);

    // Ten consecutive single-digit words (well past MAX_DIGIT_RUN) must not panic, must
    // not unboundedly grow the folded value, and must consume at most MAX_DIGIT_RUN of
    // them per run. "zero one two three four five" (6 words, capped) folds to 12345;
    // the leftover "six seven eight nine" contains no zero, so the fix's own guard
    // refuses to fold it further and it falls back to plain single-digit tokens, which
    // detect()'s pre-existing space-shorthand chapter:verse reading then picks up the
    // trailing "8 9" from. A naive unbounded fold of all ten words would instead have
    // produced the ten-digit chapter "0123456789" — this exact string proves it did not.
    assert_eq!(
        detect("psalm zero one two three four five six seven eight nine"),
        vec!["Psalms 12345:6"]
    );
}

#[test]
fn spoken_range_is_captured() {
    assert_eq!(
        detect("Romans chapter 8 verse 28 through 30"),
        vec!["Romans 8:28-30"]
    );
}

#[test]
fn multiple_references_in_one_utterance() {
    let got = detect("compare John 3:16 with First John four eight");
    assert_eq!(got, vec!["John 3:16", "1 John 4:8"]);
}

#[test]
fn digits_in_transcript_also_detect() {
    assert_eq!(detect("look at Genesis 1 verse 1"), vec!["Genesis 1:1"]);
}

// ---- Precision: ordinary speech must NOT produce detections (FR-121) ----

#[test]
fn plain_speech_yields_no_detections() {
    assert!(detect("and so this is the fifth thing I want to say today").is_empty());
    assert!(detect("let us pray and worship together").is_empty());
    assert!(detect("").is_empty());
}

#[test]
fn two_letter_typing_aliases_do_not_fire_on_speech() {
    // "is" is a valid TYPED alias for Isaiah and "so" for Song of Solomon; they must
    // not fire when spoken as ordinary words followed by a number.
    assert!(
        detect("this is 5 oclock and so 3 of us left").is_empty(),
        "short aliases must not detect on conversational speech"
    );
}

#[test]
fn a_bare_book_name_without_chapter_is_not_a_detection() {
    assert!(detect("the book of John is my favourite").is_empty());
}

// ---- Determinism (NFR-014) ----

#[test]
fn detection_is_deterministic() {
    let text = "John chapter 3 verse 16, then First Corinthians 13, and Romans eight twenty eight";
    let a = detect(text);
    let b = detect(text);
    assert_eq!(a, b);
    assert_eq!(a, vec!["John 3:16", "1 Corinthians 13", "Romans 8:28"]);
}

#[test]
fn duplicates_within_one_call_collapse() {
    assert_eq!(
        detect("John 3:16 John chapter 3 verse 16 John 3 16"),
        vec!["John 3:16"]
    );
}

// ---- The bounded detection queue ----

#[test]
fn queue_enqueue_dedups_pending_and_approves() {
    let mut q = DetectionQueue::new();
    let id = q.enqueue("Romans 8:28".into(), 0, 95).unwrap();
    assert!(
        q.enqueue("Romans 8:28".into(), 1, 95).is_none(),
        "a still-pending reference is not enqueued twice"
    );
    assert_eq!(q.len(), 1);
    let approved = q.approve(id).unwrap();
    assert_eq!(approved.reference, "Romans 8:28");
    assert_eq!(
        approved.confidence, 95,
        "the detector confidence is carried through the queue"
    );
    assert!(q.is_empty());
    assert!(q.approve(id).is_none(), "already approved");
}

#[test]
fn queue_dismiss_removes_without_returning() {
    let mut q = DetectionQueue::new();
    let id = q.enqueue("John 3:16".into(), 0, 95).unwrap();
    assert!(q.dismiss(id));
    assert!(!q.dismiss(id), "dismiss is idempotent");
    assert!(q.is_empty());
}

/// The no-leak invariant: flooding the queue can never grow it past its cap.
#[test]
fn queue_is_bounded_under_flood() {
    let mut q = DetectionQueue::new();
    for i in 0..(MAX_DETECTIONS * 20) {
        // Distinct references so dedup never suppresses — pure eviction pressure.
        q.enqueue(format!("Psalms {}", i + 1), i as u64, 50);
    }
    assert_eq!(
        q.len(),
        MAX_DETECTIONS,
        "the detection queue must be hard-capped (no unbounded growth)"
    );
}

// ---- The composing engine ----

#[test]
fn engine_ingest_streams_transcript_and_enqueues_detections() {
    let mut e = TranscriptEngine::new();
    let new = e.ingest("please turn to John chapter 3 verse 16", 0, 2_000);
    assert_eq!(new.len(), 1);
    assert_eq!(e.transcript().len(), 1);
    let pending: Vec<_> = e.detections().pending().collect();
    assert_eq!(pending.len(), 1);
    assert_eq!(pending[0].reference, "John 3:16");
    assert_eq!(pending[0].source_segment, 0, "detection carries provenance");
}

#[test]
fn engine_dedups_repeated_reference_across_segments() {
    let mut e = TranscriptEngine::new();
    e.ingest("John 3:16", 0, 1_000);
    let again = e.ingest("as I said John three sixteen", 1_000, 2_000);
    assert!(
        again.is_empty(),
        "a reference repeated soon after is not re-queued (precision)"
    );
    assert_eq!(
        e.transcript().len(),
        2,
        "but both utterances are transcribed"
    );
    assert_eq!(e.detections().len(), 1);
}

#[test]
fn engine_approve_returns_reference_for_staging() {
    let mut e = TranscriptEngine::new();
    let ids = e.ingest("First Corinthians 13", 0, 1_000);
    let staged = e.approve(ids[0]).unwrap();
    assert_eq!(staged.reference, "1 Corinthians 13");
    assert!(e.detections().is_empty());
}

#[test]
fn engine_ingest_is_bounded_and_deterministic() {
    let mut a = TranscriptEngine::new();
    let mut b = TranscriptEngine::new();
    for i in 0..500 {
        let text = format!("reading Psalm {} verse {}", (i % 150) + 1, (i % 20) + 1);
        a.ingest(&text, i as u64 * 10, i as u64 * 10 + 5);
        b.ingest(&text, i as u64 * 10, i as u64 * 10 + 5);
    }
    // Bounded on both axes.
    assert!(a.transcript().len() <= selahcue_core::transcript::MAX_TRANSCRIPT_SEGMENTS);
    assert!(a.detections().len() <= MAX_DETECTIONS);
    // Deterministic: identical input sequence → identical queue contents.
    let refs_a: Vec<_> = a.detections().pending().map(|d| &d.reference).collect();
    let refs_b: Vec<_> = b.detections().pending().map(|d| &d.reference).collect();
    assert_eq!(refs_a, refs_b);
}

#[test]
fn recent_dedup_ring_is_bounded_under_many_distinct_references() {
    // Audit L1: the cross-segment dedup ring (recent_refs) is capped at RECENT_DEDUP_WINDOW
    // in code; pin it directly. Ingest FAR more than the window's worth of DISTINCT references
    // and assert the ring stays at exactly the cap (it fills to the cap and stops growing).
    use selahcue_core::detection::RECENT_DEDUP_WINDOW;
    let mut e = TranscriptEngine::new();
    for i in 0..200u64 {
        let text = format!("reading Psalm {} verse {}", (i % 150) + 1, (i % 20) + 1);
        e.ingest(&text, i * 10, i * 10 + 5);
    }
    assert_eq!(
        e.recent_dedup_len(),
        RECENT_DEDUP_WINDOW,
        "the cross-segment dedup ring must stay bounded to RECENT_DEDUP_WINDOW"
    );
}

// ---- Fuzzy quote candidates injected alongside exact detection (R4 fuzzy rung) ----

#[test]
fn engine_ingest_with_quotes_enqueues_injected_candidates() {
    // A spoken quote whose reference is NOT named: the exact detector finds nothing, but the
    // caller's fuzzy matcher supplies the most-likely verse, which is queued for approval.
    let mut e = TranscriptEngine::new();
    let quotes = vec![("John 3:16".to_string(), 72u8)];
    let new = e.ingest_with_quotes("for God so loved the world", 0, 2_000, &quotes);
    assert_eq!(new.len(), 1);
    let pending: Vec<_> = e.detections().pending().collect();
    assert_eq!(pending.len(), 1);
    assert_eq!(pending[0].reference, "John 3:16");
    assert_eq!(
        pending[0].source_segment, 0,
        "quote candidate carries provenance"
    );
    assert_eq!(
        pending[0].confidence, 72,
        "a fuzzy quote candidate carries the matcher's coverage score, not the named default"
    );
}

#[test]
fn engine_named_reference_gets_named_confidence_and_outranks_a_quote_dup() {
    // An explicitly-spoken reference is enqueued at the high NAMED confidence; when the same
    // verse is ALSO supplied as a lower-scored fuzzy quote, the named one wins the dedup and
    // its high confidence is what the operator sees (never downgraded by the paraphrase).
    let mut e = TranscriptEngine::new();
    let quotes = vec![("John 3:16".to_string(), 60u8)];
    e.ingest_with_quotes(
        "turn to John chapter 3 verse 16 — for God so loved the world",
        0,
        2_000,
        &quotes,
    );
    let pending: Vec<_> = e.detections().pending().collect();
    assert_eq!(
        pending.len(),
        1,
        "the named ref + its quote dup collapse to one"
    );
    assert_eq!(
        pending[0].confidence, NAMED_REFERENCE_CONFIDENCE,
        "the explicitly-spoken reference keeps its high confidence over the quote score"
    );
}

#[test]
fn engine_ingest_with_quotes_dedups_quote_against_exact_hit() {
    // The same verse is BOTH spoken as a reference and matched as a quote → one detection,
    // not two (exact is enqueued first; the duplicate quote candidate is dropped).
    let mut e = TranscriptEngine::new();
    let quotes = vec![("John 3:16".to_string(), 70u8)];
    let new = e.ingest_with_quotes(
        "John chapter 3 verse 16 — for God so loved the world",
        0,
        2_000,
        &quotes,
    );
    assert_eq!(
        new.len(),
        1,
        "exact + duplicate quote collapse to one detection"
    );
    assert_eq!(e.detections().len(), 1);
}

#[test]
fn engine_ingest_with_quotes_is_bounded_under_a_flood_of_candidates() {
    // A flood of DISTINCT injected quote candidates cannot grow the queue past its cap.
    let mut e = TranscriptEngine::new();
    for i in 0..(MAX_DETECTIONS * 10) {
        let quotes = vec![(format!("Psalms {}:1", (i % 150) + 1), 60u8)];
        e.ingest_with_quotes("a spoken quotation", i as u64, i as u64 + 1, &quotes);
    }
    assert!(e.detections().len() <= MAX_DETECTIONS);
}

#[test]
fn engine_ingest_with_no_quotes_matches_plain_ingest() {
    // `ingest` delegates to `ingest_with_quotes(&[])` — behaviour is identical (regression).
    let mut a = TranscriptEngine::new();
    let mut b = TranscriptEngine::new();
    let ta = a.ingest("please turn to John chapter 3 verse 16", 0, 2_000);
    let tb = b.ingest_with_quotes("please turn to John chapter 3 verse 16", 0, 2_000, &[]);
    assert_eq!(ta.len(), tb.len());
    let ra: Vec<_> = a
        .detections()
        .pending()
        .map(|d| d.reference.clone())
        .collect();
    let rb: Vec<_> = b
        .detections()
        .pending()
        .map(|d| d.reference.clone())
        .collect();
    assert_eq!(ra, rb);
}

#[test]
fn parser_leniency_on_out_of_range_chapters_is_pre_existing_not_a_backstop() {
    // Backs the corrected comment in take_digit_run: parse_chapter_verse does not
    // range-check chapters/verses against real book lengths. Pre-existing behaviour,
    // unrelated to and out of scope for this fix -- pinned here only so the comment's
    // factual claim about it doesn't drift silently (PR #27 review finding, Sana).
    assert_eq!(detect("psalm 151"), vec!["Psalms 151"]);
    assert_eq!(detect("john 99999"), vec!["John 65535"]);
}

// ---- A digit-by-digit run must not cross "chapter"/"verse" (86akd8jzg, folded into
// this PR at the delivery lead's direction) ----
//
// `take_digit_run` used to run AFTER "chapter"/"verse" filler was stripped, so it had no
// way to see that a boundary had ever been there: a chapter read digit-by-digit,
// immediately followed by a verse also read digit-by-digit, fused into one run across
// the (already-removed) "verse". Fixed by folding numbers over the raw tokens, before
// the filler strip -- "chapter"/"verse" then act as a natural stop for the scan, the
// same way they already do for take_number's cardinal grammar.

#[test]
fn a_digit_by_digit_chapter_does_not_fuse_with_a_following_digit_by_digit_verse() {
    assert_eq!(
        detect("psalm one zero three verse four"),
        vec!["Psalms 103:4"],
        "before this fix this fused into \"Psalms 1034\""
    );
}

#[test]
fn a_digit_by_digit_chapter_and_verse_both_survive_independently() {
    // The harder case: BOTH sides read digit-by-digit, separated by "verse".
    assert_eq!(
        detect("psalm one zero three verse one zero five"),
        vec!["Psalms 103:105"]
    );
}

#[test]
fn a_digit_by_digit_chapter_does_not_fuse_across_the_chapter_filler_word() {
    assert_eq!(
        detect("john chapter one zero three"),
        vec!["John 103"],
        "\"chapter\" must act as a boundary the same as \"verse\" does"
    );
}
