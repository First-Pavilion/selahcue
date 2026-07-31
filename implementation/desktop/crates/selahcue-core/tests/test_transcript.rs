//! Integration tests for the transcript segment stream + provider seam (R3). Public API.

#![allow(clippy::unwrap_used)]

use selahcue_core::transcript::{
    ManualProvider, TranscriptLog, TranscriptProvider, MAX_SEGMENT_TEXT_LEN,
    MAX_TRANSCRIPT_SEGMENTS,
};

#[test]
fn push_assigns_monotonic_ids_and_preserves_text_and_timestamps() {
    let mut log = TranscriptLog::new();
    let a = log.push("and God so loved the world", 0, 1_500);
    let b = log.push("that he gave his only son", 1_500, 3_200);
    assert_eq!(a, 0);
    assert_eq!(b, 1);
    let segs: Vec<_> = log.segments().collect();
    assert_eq!(segs.len(), 2);
    assert_eq!(segs[0].text, "and God so loved the world");
    assert_eq!(segs[0].start_ms, 0);
    assert_eq!(segs[0].end_ms, 1_500);
    assert_eq!(segs[1].id, 1);
}

#[test]
fn end_before_start_is_clamped_never_panics() {
    let mut log = TranscriptLog::new();
    log.push("clamp me", 5_000, 1_000);
    let seg = log.segments().next().unwrap();
    assert_eq!(seg.start_ms, 5_000);
    assert_eq!(seg.end_ms, 5_000, "end_ms clamps up to start_ms");
}

#[test]
fn segment_text_is_length_bounded() {
    let mut log = TranscriptLog::new();
    let huge = "a".repeat(MAX_SEGMENT_TEXT_LEN * 4);
    log.push(&huge, 0, 10);
    let seg = log.segments().next().unwrap();
    assert!(
        seg.text.len() <= MAX_SEGMENT_TEXT_LEN,
        "a single segment must not store unbounded text ({} > {})",
        seg.text.len(),
        MAX_SEGMENT_TEXT_LEN
    );
}

#[test]
fn multibyte_truncation_never_splits_a_codepoint() {
    let mut log = TranscriptLog::new();
    // Each 'é' is 2 bytes; a long run forces truncation on a boundary.
    let huge = "é".repeat(MAX_SEGMENT_TEXT_LEN);
    log.push(&huge, 0, 10);
    let seg = log.segments().next().unwrap();
    // If truncation split a codepoint this string would be invalid — reaching here
    // (valid UTF-8) plus the length bound is the assertion.
    assert!(seg.text.len() <= MAX_SEGMENT_TEXT_LEN);
    assert!(seg.text.chars().all(|c| c == 'é'));
}

/// The no-leak invariant: a flood of pushes can never grow the log past its cap.
#[test]
fn log_is_bounded_under_flood() {
    let mut log = TranscriptLog::new();
    for i in 0..(MAX_TRANSCRIPT_SEGMENTS * 50) {
        log.push(&format!("utterance {i}"), i as u64, i as u64 + 1);
    }
    assert_eq!(
        log.len(),
        MAX_TRANSCRIPT_SEGMENTS,
        "the transcript log must be hard-capped (no unbounded growth)"
    );
    // The retained window is the MOST RECENT segments (oldest evicted).
    let first = log.segments().next().unwrap();
    let last_id = (MAX_TRANSCRIPT_SEGMENTS * 50 - 1) as u64;
    assert_eq!(first.id, last_id - (MAX_TRANSCRIPT_SEGMENTS as u64 - 1));
}

#[test]
fn recent_returns_bounded_tail_oldest_first() {
    let mut log = TranscriptLog::new();
    for i in 0..10 {
        log.push(&format!("s{i}"), i, i + 1);
    }
    let tail = log.recent(3);
    assert_eq!(tail.len(), 3);
    assert_eq!(tail[0].text, "s7");
    assert_eq!(tail[2].text, "s9");
    // Asking for more than exist returns everything, not a panic.
    assert_eq!(log.recent(100).len(), 10);
}

#[test]
fn clear_empties_but_keeps_ids_unique() {
    let mut log = TranscriptLog::new();
    log.push("one", 0, 1);
    log.clear();
    assert!(log.is_empty());
    let id = log.push("two", 0, 1);
    assert_eq!(id, 1, "ids keep counting after clear (never reused)");
}

// --- The provider seam (ADR-0010 STTProvider) -----------------------------------

#[test]
fn manual_provider_is_the_deterministic_default() {
    let mut p = ManualProvider::new();
    assert_eq!(p.label(), "manual");
    assert!(p.poll().is_empty(), "nothing submitted yet");
    p.submit("first", 0, 1_000);
    p.submit("second", 1_000, 2_000);
    let drained = p.poll();
    assert_eq!(drained.len(), 2);
    assert_eq!(drained[0].text, "first");
    assert!(drained[0].is_final);
    assert_eq!(drained[1].start_ms, 1_000);
    // A second poll drains nothing (already consumed) — deterministic.
    assert!(p.poll().is_empty());
}

/// The seam is generic over the trait: any `TranscriptProvider` drains the same way.
#[test]
fn provider_drains_through_the_trait_object() {
    let mut p = ManualProvider::new();
    p.submit("through the trait", 0, 500);
    let provider: &mut dyn TranscriptProvider = &mut p;
    let out = provider.poll();
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].text, "through the trait");
}
