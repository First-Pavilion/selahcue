//! Integration tests for `transcript_repo` — round-trip fidelity, unbounded segment
//! storage (unlike the in-memory ring), detection persistence, cascade delete,
//! configurable retention, listing, and the FR-082 no-content-in-diagnostics
//! guarantee. Public API only (mirrors `test_screen_repo.rs`/`test_plan_repo.rs`).

#![allow(clippy::unwrap_used)]

use std::path::PathBuf;

use rusqlite::params;
use selahcue_core::transcript::{MAX_SEGMENT_TEXT_LEN, MAX_TRANSCRIPT_SEGMENTS};
use selahcue_data::transcript_repo::{self, NewTranscript, RetentionSettings};
use selahcue_data::Database;

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

fn sample_new_transcript() -> NewTranscript {
    NewTranscript {
        label: "Sunday Service — 2026-09-06 09:03".into(),
        provider: "manual".into(),
        plan_id: None,
        started_at_ms: 1_757_150_000_000,
    }
}

// --- Round trip: create, append across many calls, read back in order ---------------

#[test]
fn creates_appends_across_many_calls_and_reads_back_in_order_unmodified() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();

    // Simulate a real multi-hour service: many separate append calls, not one batch.
    let texts: Vec<String> = (0..50).map(|i| format!("segment number {i}")).collect();
    for (i, text) in texts.iter().enumerate() {
        let start = (i as u64) * 1000;
        let id =
            transcript_repo::append_segment(&db, transcript_id, start, start + 900, text).unwrap();
        // Ids are assigned in increasing order as segments are appended.
        assert!(id > 0);
    }
    transcript_repo::end(&db, transcript_id, 60_000).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.label, sample_new_transcript().label);
    assert_eq!(detail.provider, "manual");
    assert_eq!(detail.ended_at_ms, Some(60_000));
    assert_eq!(detail.segments.len(), texts.len());
    for (i, seg) in detail.segments.iter().enumerate() {
        assert_eq!(seg.text, texts[i], "segment {i} text must be unmodified");
        assert_eq!(
            seg.start_ms,
            (i as u64) * 1000,
            "segment {i} order must be preserved"
        );
    }
}

#[test]
fn load_of_unknown_transcript_is_not_found() {
    let db = db();
    assert!(matches!(
        transcript_repo::load(&db, 999_999),
        Err(selahcue_data::DataError::NotFound)
    ));
}

// --- Unbounded storage: the acceptance criterion this ticket exists to satisfy ------

// Pin the premise at compile time: if the in-memory ring's caps ever change, these
// test sizes must still exceed them, or this test would silently stop proving
// anything about "beyond the ring's cap" (bounded-memory test discipline).
const TEST_SEGMENT_COUNT: usize = MAX_TRANSCRIPT_SEGMENTS + 260;
const TEST_TEXT_LEN: usize = MAX_SEGMENT_TEXT_LEN * 3;
const _: () = assert!(TEST_SEGMENT_COUNT > MAX_TRANSCRIPT_SEGMENTS);
const _: () = assert!(TEST_TEXT_LEN > MAX_SEGMENT_TEXT_LEN);

#[test]
fn segment_count_is_not_capped_at_the_in_memory_ring_limit() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();

    for i in 0..TEST_SEGMENT_COUNT {
        transcript_repo::append_segment(&db, transcript_id, i as u64, i as u64 + 1, "x").unwrap();
    }

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        detail.segments.len(),
        TEST_SEGMENT_COUNT,
        "the store must retain every segment past MAX_TRANSCRIPT_SEGMENTS ({MAX_TRANSCRIPT_SEGMENTS}), \
         unlike the in-memory ring — the in-memory-ring eviction contract was not exercised \
         if this ever silently reads back {MAX_TRANSCRIPT_SEGMENTS} or fewer"
    );
    // The earliest segment (would be the FIRST evicted by the in-memory ring) is still
    // present and at position 0 — proof this isn't a ring that just grew its window.
    assert_eq!(detail.segments[0].start_ms, 0);
}

#[test]
fn segment_text_is_not_capped_at_the_in_memory_ring_length_limit() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    // A single character repeated well past MAX_SEGMENT_TEXT_LEN (pathological input:
    // one extremely long segment) plus, separately, thousands of small ones below —
    // covered together with the count test above for the many-segments case.
    let long_text = "a".repeat(TEST_TEXT_LEN);
    transcript_repo::append_segment(&db, transcript_id, 0, 1000, &long_text).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.segments.len(), 1);
    assert_eq!(
        detail.segments[0].text.len(),
        TEST_TEXT_LEN,
        "text must not be truncated at MAX_SEGMENT_TEXT_LEN ({MAX_SEGMENT_TEXT_LEN}) the way \
         the in-memory ring truncates — the truncation contract was not exercised if this \
         ever silently reads back {MAX_SEGMENT_TEXT_LEN}"
    );
    assert_eq!(detail.segments[0].text, long_text);
}

#[test]
fn many_thousands_of_segments_and_detections_do_not_panic_or_corrupt_the_store() {
    // Pathological volume, not just pathological length (verification expectations).
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    const N: usize = 5_000;
    for i in 0..N {
        let seg_id =
            transcript_repo::append_segment(&db, transcript_id, i as u64, i as u64 + 1, "s")
                .unwrap();
        transcript_repo::append_detection(
            &db,
            transcript_id,
            Some(seg_id),
            &format!("Psalm {}", (i % 150) + 1),
            80,
        )
        .unwrap();
    }
    db.integrity_check().unwrap();
    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.segments.len(), N);
    assert_eq!(detail.detections.len(), N);
}

// --- Corrections (schema-only editable layer) ---------------------------------------

#[test]
fn correcting_a_segment_never_touches_the_raw_segment_text() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id =
        transcript_repo::append_segment(&db, transcript_id, 0, 1000, "the rong text").unwrap();
    transcript_repo::correct_segment(&db, seg_id, "the right text", 5000).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        detail.segments[0].text, "the rong text",
        "raw segment is immutable"
    );
    assert_eq!(detail.corrections.len(), 1);
    assert_eq!(detail.corrections[0].segment_id, seg_id);
    assert_eq!(detail.corrections[0].corrected_text, "the right text");
    assert_eq!(detail.corrections[0].corrected_at_ms, 5000);
}

#[test]
fn a_second_correction_replaces_the_first_not_appends() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id = transcript_repo::append_segment(&db, transcript_id, 0, 1000, "raw").unwrap();
    transcript_repo::correct_segment(&db, seg_id, "first edit", 1).unwrap();
    transcript_repo::correct_segment(&db, seg_id, "second edit", 2).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        detail.corrections.len(),
        1,
        "latest correction replaces, not appends"
    );
    assert_eq!(detail.corrections[0].corrected_text, "second edit");
}

// --- Detections -----------------------------------------------------------------------

#[test]
fn detections_persist_and_read_back_correctly() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id =
        transcript_repo::append_segment(&db, transcript_id, 0, 1000, "Romans 8 28").unwrap();
    let det_id =
        transcript_repo::append_detection(&db, transcript_id, Some(seg_id), "Romans 8:28", 95)
            .unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.detections.len(), 1);
    let d = &detail.detections[0];
    assert_eq!(d.id, det_id as u64);
    assert_eq!(d.reference, "Romans 8:28");
    assert_eq!(d.source_segment, seg_id as u64);
    assert_eq!(d.confidence, 95);
}

#[test]
fn a_corrupt_confidence_value_is_reported_without_leaking_the_reference_text() {
    // A malformed row (e.g. a future schema mismatch) must surface as `Corrupt`, not a
    // panic — and the Corrupt message must name the field, never the sensitive
    // reference/text sitting in the very same row (FR-082's Corrupt-path corner case,
    // not reachable through this repo's own API, only through a hand-corrupted store).
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id = transcript_repo::append_segment(&db, transcript_id, 0, 1000, "text").unwrap();
    const MARKER: &str = "FR082_CORRUPT_PATH_MARKER_Shadrach_Meshach_Abednego";
    transcript_repo::append_detection(&db, transcript_id, Some(seg_id), MARKER, 10).unwrap();
    db.conn()
        .execute("UPDATE detection SET confidence = 999", [])
        .unwrap();

    let err = transcript_repo::load(&db, transcript_id).unwrap_err();
    let msg = format!("{err} {err:?}");
    assert!(
        !msg.contains(MARKER),
        "corrupt-confidence error leaked the reference text: {msg}"
    );
    assert!(
        msg.contains("confidence"),
        "expected the corrupt-confidence message to at least name the field it \
         complains about; got: {msg}"
    );
}

// --- Cascade delete (FR-153: reliable deletion incl. derived artifacts) -------------

#[test]
fn deleting_a_transcript_removes_segments_corrections_and_detections_together() {
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id = transcript_repo::append_segment(&db, transcript_id, 0, 1000, "text").unwrap();
    transcript_repo::correct_segment(&db, seg_id, "fixed text", 10).unwrap();
    transcript_repo::append_detection(&db, transcript_id, Some(seg_id), "John 3:16", 90).unwrap();

    // Positive control: the derived rows actually exist before delete — otherwise
    // "gone after delete" would be true trivially.
    let count = |table: &str| -> i64 {
        db.conn()
            .query_row(
                &format!("SELECT COUNT(*) FROM {table} WHERE transcript_id = ?1"),
                params![transcript_id],
                |r| r.get(0),
            )
            .unwrap()
    };
    let segment_count_direct: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM transcript_segment WHERE transcript_id = ?1",
            params![transcript_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(
        segment_count_direct, 1,
        "positive control: segment must exist before delete"
    );
    assert_eq!(
        count("detection"),
        1,
        "positive control: detection must exist before delete"
    );
    let correction_count: i64 = db
        .conn()
        .query_row("SELECT COUNT(*) FROM transcript_correction", [], |r| {
            r.get(0)
        })
        .unwrap();
    assert_eq!(
        correction_count, 1,
        "positive control: correction must exist before delete"
    );

    transcript_repo::delete(&db, transcript_id).unwrap();

    assert!(matches!(
        transcript_repo::load(&db, transcript_id),
        Err(selahcue_data::DataError::NotFound)
    ));
    let segment_count_after: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM transcript_segment WHERE transcript_id = ?1",
            params![transcript_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(segment_count_after, 0, "segments must cascade away");
    assert_eq!(count("detection"), 0, "detections must cascade away");
    let correction_count_after: i64 = db
        .conn()
        .query_row("SELECT COUNT(*) FROM transcript_correction", [], |r| {
            r.get(0)
        })
        .unwrap();
    assert_eq!(correction_count_after, 0, "corrections must cascade away");
}

#[test]
fn deleting_an_unknown_transcript_is_not_found() {
    let db = db();
    assert!(matches!(
        transcript_repo::delete(&db, 999_999),
        Err(selahcue_data::DataError::NotFound)
    ));
}

// --- Listing (enough per row for a list UI, no second read) -------------------------

#[test]
fn listing_returns_label_provider_timing_and_segment_count_without_a_second_read() {
    let db = db();
    let a = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "Older Service".into(),
            provider: "whisper".into(),
            plan_id: None,
            started_at_ms: 1000,
        },
    )
    .unwrap();
    transcript_repo::append_segment(&db, a, 0, 100, "one").unwrap();
    transcript_repo::append_segment(&db, a, 100, 200, "two").unwrap();

    let b = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "Newer Service".into(),
            provider: "deepgram".into(),
            plan_id: None,
            started_at_ms: 2000,
        },
    )
    .unwrap();
    transcript_repo::append_segment(&db, b, 0, 100, "only one").unwrap();

    let rows = transcript_repo::list(&db).unwrap();
    assert_eq!(rows.len(), 2);
    // Most recently started first.
    assert_eq!(rows[0].id, b);
    assert_eq!(rows[0].label, "Newer Service");
    assert_eq!(rows[0].provider, "deepgram");
    assert_eq!(rows[0].started_at_ms, 2000);
    assert_eq!(
        rows[0].segment_count, 1,
        "segment count must come from the listing row itself"
    );
    assert_eq!(rows[1].id, a);
    assert_eq!(rows[1].segment_count, 2);
}

// --- Retention settings (configurable, not hardcoded; FR-153/FR-137) ---------------

#[test]
fn empty_store_loads_the_safe_placeholder_retention_defaults() {
    let db = db();
    let settings = transcript_repo::load_retention_settings(&db).unwrap();
    assert_eq!(settings, RetentionSettings::default());
    assert_eq!(
        settings.retention_days, None,
        "kept indefinitely by default (FR-153)"
    );
    assert!(!settings.delete_cascade_to_notes);
}

#[test]
fn retention_settings_round_trip_and_save_replaces_the_whole_set() {
    let db = db();
    let custom = RetentionSettings {
        retention_days: Some(30),
        delete_cascade_to_notes: true,
    };
    transcript_repo::save_retention_settings(&db, &custom).unwrap();
    assert_eq!(
        transcript_repo::load_retention_settings(&db).unwrap(),
        custom
    );

    // Saving again with retention_days cleared must actually clear the stored key, not
    // leave a stale "30" behind (same regression class as providers_repo's replace test).
    let cleared = RetentionSettings {
        retention_days: None,
        delete_cascade_to_notes: true,
    };
    transcript_repo::save_retention_settings(&db, &cleared).unwrap();
    assert_eq!(
        transcript_repo::load_retention_settings(&db).unwrap(),
        cleared
    );
}

#[test]
fn purge_expired_removes_only_ended_transcripts_past_the_configured_window() {
    let db = db();
    const DAY_MS: i64 = 86_400_000;
    let now = 100 * DAY_MS;

    // (a) ended 10 days ago — past a 7-day window, must be purged.
    let old = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "old".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 11 * DAY_MS,
        },
    )
    .unwrap();
    transcript_repo::end(&db, old, now - 10 * DAY_MS).unwrap();

    // (b) ended 1 day ago — inside the window, must survive.
    let recent = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "recent".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 2 * DAY_MS,
        },
    )
    .unwrap();
    transcript_repo::end(&db, recent, now - DAY_MS).unwrap();

    // (c) started 100 days ago but still recording (no ended_at) — never auto-purged,
    // regardless of age, because it is still live.
    let live = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "live".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 100 * DAY_MS,
        },
    )
    .unwrap();

    // With the default (kept indefinitely), purge is a deliberate no-op — retention
    // stays opt-in even with an eligible-looking row sitting in the store.
    assert_eq!(
        transcript_repo::purge_expired(&db, now).unwrap(),
        Vec::<i64>::new()
    );
    assert!(
        transcript_repo::load(&db, old).is_ok(),
        "no purge without a configured window"
    );

    transcript_repo::save_retention_settings(
        &db,
        &RetentionSettings {
            retention_days: Some(7),
            delete_cascade_to_notes: false,
        },
    )
    .unwrap();

    let mut purged = transcript_repo::purge_expired(&db, now).unwrap();
    purged.sort_unstable();
    assert_eq!(
        purged,
        vec![old],
        "only the ended, past-window transcript is purged"
    );
    assert!(matches!(
        transcript_repo::load(&db, old),
        Err(selahcue_data::DataError::NotFound)
    ));
    assert!(
        transcript_repo::load(&db, recent).is_ok(),
        "inside the window must survive"
    );
    assert!(
        transcript_repo::load(&db, live).is_ok(),
        "still-recording must never be purged"
    );
}

// --- FR-082: no transcript/detection content in logs or diagnostics ------------------

#[test]
fn no_segment_or_detection_text_reaches_a_dataerror_diagnostic() {
    const MARKER: &str = "FR082_SENSITIVE_SERMON_TEXT_Nebuchadnezzar_Belshazzar_Confession";
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let seg_id = transcript_repo::append_segment(&db, transcript_id, 0, 1000, MARKER).unwrap();
    transcript_repo::correct_segment(&db, seg_id, MARKER, 1).unwrap();
    transcript_repo::append_detection(&db, transcript_id, Some(seg_id), MARKER, 50).unwrap();

    // Positive control: the marker really was persisted. Without this, "the marker
    // never appears in diagnostics" below would be true merely because it was never
    // stored anywhere — a dead check, not a real one.
    let raw_text: String = db
        .conn()
        .query_row(
            "SELECT text FROM transcript_segment WHERE id = ?1",
            params![seg_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(
        raw_text, MARKER,
        "positive control: marker must actually be persisted"
    );

    // Force every DataError this module can produce and capture their Display+Debug —
    // the realistic path by which an application layer would ever log one of these.
    let mut diagnostics = String::new();
    let load_err = transcript_repo::load(&db, 999_999).unwrap_err();
    diagnostics.push_str(&format!("{load_err} {load_err:?} "));
    let end_err = transcript_repo::end(&db, 999_999, 0).unwrap_err();
    diagnostics.push_str(&format!("{end_err} {end_err:?} "));
    let delete_err = transcript_repo::delete(&db, 999_999).unwrap_err();
    diagnostics.push_str(&format!("{delete_err} {delete_err:?}"));

    assert!(
        !diagnostics.contains(MARKER),
        "sensitive transcript/detection text leaked into a DataError's Display/Debug \
         output (FR-082): {diagnostics}"
    );
    // Second positive control: the captured diagnostics string is real, non-trivial
    // content — proving the capture-and-search methodology isn't itself dead (an empty
    // or unrelated string would make the assertion above vacuous).
    assert!(
        diagnostics.contains("not found"),
        "expected the well-known NotFound message in the captured diagnostics; got: \
         {diagnostics} — the capture methodology may not be exercising real error paths"
    );
}

#[test]
fn transcript_repo_source_never_calls_a_logging_or_print_macro() {
    // FR-082, enforced textually as well as at runtime (previous test): nothing in this
    // module needs to log, print, or dbg! anything at all, so the simplest durable
    // control is that none of these ever appear in its source — an addition is caught
    // here even before any test exercises the new line. Mirrors
    // `selahcue-licensing/tests/test_custody.rs`'s "never handed to a formatter" guard.
    let src_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src/transcript_repo.rs");
    let body = std::fs::read_to_string(&src_path).unwrap();
    const FORBIDDEN: &[&str] = &[
        "println!",
        "eprintln!",
        "print!",
        "eprint!",
        "log::",
        "tracing::",
        "dbg!",
    ];

    let mut scanned_lines = 0usize;
    for (lineno, line) in body.lines().enumerate() {
        scanned_lines += 1;
        // Strip line comments so a doc-comment mentioning "tracing::" (as this file's
        // own module doc does, describing what must NOT happen) can't false-positive.
        let code = line.split("//").next().unwrap_or("");
        for forbidden in FORBIDDEN {
            assert!(
                !code.contains(forbidden),
                "{}:{} uses {forbidden} — transcript/detection text must never reach a \
                 log/print macro (FR-082):\n  {}",
                src_path.display(),
                lineno + 1,
                line.trim()
            );
        }
    }
    // Positive control: the scan actually looked at the real, full-sized file.
    assert!(
        scanned_lines > 150,
        "expected to scan the full transcript_repo.rs source ({scanned_lines} lines) — \
         the file may be missing, moved, or truncated, which would make every assertion \
         above vacuous"
    );
}
