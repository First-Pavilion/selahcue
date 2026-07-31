//! Integration tests for scripture detection over transcript text (R4). Public API.

#![allow(clippy::unwrap_used)]

use selahcue_core::detection::{detect, DetectionQueue, TranscriptEngine, MAX_DETECTIONS};

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
    let id = q.enqueue("Romans 8:28".into(), 0).unwrap();
    assert!(
        q.enqueue("Romans 8:28".into(), 1).is_none(),
        "a still-pending reference is not enqueued twice"
    );
    assert_eq!(q.len(), 1);
    let approved = q.approve(id).unwrap();
    assert_eq!(approved.reference, "Romans 8:28");
    assert!(q.is_empty());
    assert!(q.approve(id).is_none(), "already approved");
}

#[test]
fn queue_dismiss_removes_without_returning() {
    let mut q = DetectionQueue::new();
    let id = q.enqueue("John 3:16".into(), 0).unwrap();
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
        q.enqueue(format!("Psalms {}", i + 1), i as u64);
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
