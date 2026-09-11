//! Integration tests for `transcript_repo` — round-trip fidelity, unbounded segment
//! storage (unlike the in-memory ring), detection persistence, cascade delete,
//! configurable retention, listing, and the FR-082 no-content-in-diagnostics
//! guarantee. Public API only (mirrors `test_screen_repo.rs`/`test_plan_repo.rs`).

#![allow(clippy::unwrap_used)]

use std::path::{Path, PathBuf};

use rusqlite::params;
use selahcue_core::plan::ServicePlan;
use selahcue_core::transcript::{MAX_SEGMENT_TEXT_LEN, MAX_TRANSCRIPT_SEGMENTS};
use selahcue_data::transcript_repo::{self, NewTranscript, RetentionSettings};
use selahcue_data::{plan_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

/// True iff `needle` occurs anywhere in `haystack` (mirrors `test_encryption.rs`'s
/// same-named helper — used here to prove ABSENCE of a marker on disk, not presence).
fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    !needle.is_empty() && haystack.windows(needle.len()).any(|w| w == needle)
}

/// Smallest chunk of a marker the FR-082 runtime leak check treats as a leak on its
/// own (PR #30 review, Sana F7). An exact, whole-marker match alone lets a truncated
/// diagnostic — e.g. "bad segment starting <first 24 chars>" — walk straight past the
/// check, because it never contains the FULL marker. `LEAK_WINDOW` is smaller than
/// every marker used in this file, so a genuine leak of any contiguous chunk at least
/// this long is caught even when the rest of the marker never appears.
const LEAK_WINDOW: usize = 12;

/// True iff some contiguous `LEAK_WINDOW`-byte-or-longer slice of `needle` appears
/// anywhere in `haystack` — not just an exact match of the whole string.
fn contains_a_leak_window_of(haystack: &str, needle: &str) -> bool {
    let needle = needle.as_bytes();
    let haystack = haystack.as_bytes();
    if needle.len() <= LEAK_WINDOW {
        return haystack.windows(needle.len()).any(|w| w == needle);
    }
    needle
        .windows(LEAK_WINDOW)
        .any(|nw| haystack.windows(LEAK_WINDOW).any(|hw| hw == nw))
}

/// SQLite's WAL sidecar path for a given database file path (`<path>-wal`).
fn wal_sidecar_path(db_path: &Path) -> PathBuf {
    let mut s = db_path.as_os_str().to_owned();
    s.push("-wal");
    PathBuf::from(s)
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
fn ord_continues_from_the_highest_surviving_value_not_a_row_count() {
    // append_segment must derive `ord` from a high-water mark, not `COUNT(*)` — a row
    // count under-counts as soon as any segment is removed from the middle of the
    // sequence, and then collides with an existing `ord`, violating
    // `UNIQUE (transcript_id, ord)` on the very next append (PR #30 review, Sana S1).
    // There is no single-segment delete in this ticket's public API yet, but the
    // schema permits arbitrary row deletion (e.g. a future correction/redaction
    // feature), and this is cheap to pin now while the migration is still unmerged.
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    let ids: Vec<i64> = (0..3)
        .map(|i| transcript_repo::append_segment(&db, transcript_id, i, i + 1, "x").unwrap())
        .collect();
    // Remove the middle segment (ord = 1) directly — simulating a future deletion path.
    // Remaining ords are {0, 2}; COUNT(*) now reports 2, which collides with the
    // surviving ord=2 row. A high-water mark correctly reports 3.
    db.conn()
        .execute(
            "DELETE FROM transcript_segment WHERE id = ?1",
            params![ids[1]],
        )
        .unwrap();

    // If `ord` were still assigned via COUNT(*), this insert would hit the UNIQUE
    // constraint and this unwrap would panic — that panic IS the regression signal.
    let next_id = transcript_repo::append_segment(&db, transcript_id, 3, 4, "next").unwrap();
    let next_ord: i64 = db
        .conn()
        .query_row(
            "SELECT ord FROM transcript_segment WHERE id = ?1",
            params![next_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(
        next_ord, 3,
        "next ord must continue past the highest surviving ord (2), not the post-delete \
         row count (2, which would collide)"
    );
}

#[test]
fn load_of_unknown_transcript_is_not_found() {
    let db = db();
    assert!(matches!(
        transcript_repo::load(&db, 999_999),
        Err(selahcue_data::DataError::NotFound)
    ));
}

#[test]
fn deleting_the_plan_sets_transcript_plan_id_null_the_transcript_survives() {
    // The entire reason `transcript.plan_id` is `INTEGER REFERENCES service_plan(id)
    // ON DELETE SET NULL` instead of a hard/blocking reference: "a transcript must
    // outlive the plan it was recorded against" (migrations.rs v19->v20 comment) — the
    // "raw transcript is immutable" principle this whole slice exists to serve. Every
    // other fixture in this file uses `plan_id: None`, so without this test the one
    // behaviour this migration is built around was unverified (PR #30 review, Cody
    // Medium #1): a future edit that quietly changed this to `ON DELETE CASCADE` (or
    // dropped the clause, defaulting to `RESTRICT`) would pass every other test here.
    let db = db();
    let plan_id = plan_repo::insert(&db, &ServicePlan::new("Sunday Service")).unwrap();
    let transcript_id = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "Sunday Service — 2026-09-06 09:03".into(),
            provider: "manual".into(),
            plan_id: Some(plan_id),
            started_at_ms: 1_757_150_000_000,
        },
    )
    .unwrap();

    plan_repo::delete(&db, plan_id).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        detail.plan_id, None,
        "transcript must survive its deleted plan with plan_id set to NULL, not RESTRICT \
         the plan delete and not cascade away with it"
    );
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
fn segment_id_is_none_reads_back_as_the_documented_zero_sentinel() {
    // `detection.segment_id` is nullable by design (a detection can exist with no
    // known source segment), but `DetectedReference::source_segment` is a mandatory
    // `u64` — `load()` maps `None` to `0`. Changing that representation is a
    // `selahcue-core` change, out of this ticket's `selahcue-data`-only file
    // footprint, so this pins the documented sentinel rather than the type (PR #30
    // review, Cody #2 / Quinn ADVISORY-1): nothing before this test ever called
    // `append_detection` with `segment_id: None`, so this path was previously
    // unexercised entirely.
    let db = db();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    transcript_repo::append_detection(&db, transcript_id, None, "Genesis 1:1", 70).unwrap();

    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.detections.len(), 1);
    assert_eq!(
        detail.detections[0].source_segment, 0,
        "a NULL segment_id must round-trip to the documented 0 sentinel"
    );
}

#[test]
fn transcript_segment_has_exactly_one_index_from_its_unique_constraint() {
    // `UNIQUE (transcript_id, ord)` already creates an implicit autoindex on those two
    // columns; a second explicit `CREATE INDEX` on the same columns is a byte-
    // identical duplicate B-tree maintained on every append with zero read benefit
    // (PR #30 review, Cody #3 / Vera F3 — measured ~7% extra file size at 5,000
    // segments, no plan-shape change when dropped). Pinning the count, not just query
    // plans, so a future re-added duplicate is caught even if it happens not to change
    // any plan.
    let db = db();
    let mut stmt = db
        .conn()
        .prepare("PRAGMA index_list('transcript_segment')")
        .unwrap();
    let names: Vec<String> = stmt
        .query_map([], |r| r.get::<_, String>(1))
        .unwrap()
        .collect::<std::result::Result<Vec<_>, _>>()
        .unwrap();
    assert_eq!(
        names.len(),
        1,
        "expected exactly one index on transcript_segment (the UNIQUE constraint's own \
         autoindex); found {names:?}"
    );
}

#[test]
fn a_segment_delete_never_full_scans_the_detection_table() {
    // FK `detection.segment_id ON DELETE CASCADE` fires once per deleted segment.
    // Without an index on `detection(segment_id)` that lookup is a full scan of the
    // whole `detection` table — across every transcript, not just the one being
    // deleted (PR #30 review, Vera F1 — measured 144M full-scan VM steps / 6.6s for a
    // single delete against a 30k-row detection table without the index; 0 steps /
    // 5-10ms with it). Mutation check performed by hand: removing the `CREATE INDEX
    // idx_detection_segment` line from the v20 migration turns this RED with a plan
    // containing "SCAN detection"; restoring it turns it GREEN again.
    let db = db();
    let mut stmt = db
        .conn()
        .prepare("EXPLAIN QUERY PLAN SELECT 1 FROM detection WHERE segment_id = ?1")
        .unwrap();
    let plan: Vec<String> = stmt
        .query_map(params![1i64], |r| r.get::<_, String>(3))
        .unwrap()
        .collect::<std::result::Result<Vec<_>, _>>()
        .unwrap();
    assert!(
        !plan.iter().any(|p| p.contains("SCAN")),
        "detection.segment_id lookup is a full scan, not index-backed: {plan:?}"
    );
    assert!(
        plan.iter()
            .any(|p| p.contains("INDEX") && p.contains("segment_id")),
        "expected an index-backed search naming segment_id: {plan:?}"
    );
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

#[test]
fn deleting_a_transcript_removes_its_text_from_the_plain_store_file_and_wal() {
    // FR-153 "reliable deletion" must mean the text is actually gone from disk, not
    // merely unreachable via the read API. Bundled SQLite defaults `secure_delete`
    // OFF, which leaves a deleted row's bytes sitting in freed pages until some
    // unrelated later write happens to reuse that page (PR #30 review, Sana F1 — this
    // is the live path today: `make launch`, `make output`, and the installer all
    // build the plaintext output-window path, so this is not merely a theoretical gap
    // behind the off-by-default `encryption` feature). Mutation check performed by
    // hand: removing `PRAGMA secure_delete = ON;` from `Database::init` turns the
    // main-file assertion below RED; restoring it turns it GREEN again.
    //
    // `secure_delete` alone only covers the main `.db3` file. In WAL mode, freed-page
    // zeroing happens inside a *new* WAL frame; the earlier, now-superseded frame that
    // still holds the deleted row's original bytes can remain physically present in
    // the `-wal` sidecar until something truncates it (PR #30 review, Sana F6) — so
    // `delete()` now runs a best-effort `wal_checkpoint(TRUNCATE)` itself (see
    // `Database::try_checkpoint_truncate`). This test does NOT call
    // `checkpoint_truncate()` itself, and reads both files with the connection STILL
    // OPEN, immediately after `delete()` returns — deliberately, on both counts: an
    // explicit test-side checkpoint (the previous version of this test) or even just
    // `drop(db)` (SQLite auto-checkpoints and typically deletes the WAL on a clean
    // close) would truncate the WAL regardless of whether `delete()`'s own internal
    // checkpoint did anything, making the WAL assertion pass unconditionally — exactly
    // the vacuousness Cody's review flagged in the prior version of this test. Mutation
    // check performed by hand: removing the `db.try_checkpoint_truncate();` call from
    // `transcript_repo::delete` turns the WAL assertion below RED (the marker survives
    // in the stale, superseded WAL frame); restoring it turns it GREEN again.
    const MARKER: &str = "FR153_SECURE_DELETE_MARKER_Nahum_Elkoshite_Oracle";
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    let wal_path = wal_sidecar_path(&path);

    let db = Database::open(&path).unwrap();
    let transcript_id = transcript_repo::create(&db, &sample_new_transcript()).unwrap();
    for i in 0..40 {
        transcript_repo::append_segment(&db, transcript_id, i, i + 1, MARKER).unwrap();
    }

    // Positive control: the marker really is on disk before delete (WAL mode defers
    // writes to the main file, so it lives in the WAL sidecar at this point) —
    // otherwise "absent after delete" below would be true merely because it was never
    // written to disk in the first place.
    let wal_before = std::fs::read(&wal_path).unwrap_or_default();
    let main_before = std::fs::read(&path).unwrap();
    assert!(
        contains(&wal_before, MARKER.as_bytes()) || contains(&main_before, MARKER.as_bytes()),
        "positive control: marker must be present on disk before delete"
    );

    transcript_repo::delete(&db, transcript_id).unwrap();

    // Read with `db` still open — see the doc comment above for why.
    let main_after = std::fs::read(&path).unwrap();
    let wal_after = std::fs::read(&wal_path).unwrap_or_default();
    assert!(
        !contains(&main_after, MARKER.as_bytes()),
        "deleted transcript text remained in the main .db3 file — secure_delete is not \
         zeroing freed pages (FR-153)"
    );
    assert!(
        !contains(&wal_after, MARKER.as_bytes()),
        "deleted transcript text remained in the -wal file immediately after delete() \
         returned, before any connection close — delete()'s own best-effort \
         wal_checkpoint(TRUNCATE) did not clear it (FR-153)"
    );

    drop(db);
}

#[test]
fn purging_expired_transcripts_removes_their_text_from_the_plain_store_file_and_wal() {
    // Same FR-153 guarantee as the delete test above, through `purge_expired` — the
    // other deletion path Sana F6's fix applies to. Same reasoning for reading with
    // the connection still open and never calling `checkpoint_truncate()` in the test:
    // a clean close would truncate the WAL regardless of whether `purge_expired()`'s
    // own best-effort checkpoint did anything. Mutation check performed by hand:
    // removing the `db.try_checkpoint_truncate();` call from
    // `transcript_repo::purge_expired` turns the WAL assertion below RED; restoring it
    // turns it GREEN again.
    const MARKER: &str = "FR153_PURGE_SECURE_DELETE_MARKER_Habakkuk_Zephaniah_Oracle";
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    let wal_path = wal_sidecar_path(&path);
    const DAY_MS: i64 = 86_400_000;
    let now = 100 * DAY_MS;

    let db = Database::open(&path).unwrap();
    let transcript_id = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "to purge".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 10 * DAY_MS,
        },
    )
    .unwrap();
    for i in 0..40 {
        transcript_repo::append_segment(&db, transcript_id, i, i + 1, MARKER).unwrap();
    }
    transcript_repo::end(&db, transcript_id, now - 9 * DAY_MS).unwrap();
    transcript_repo::save_retention_settings(
        &db,
        &RetentionSettings {
            retention_days: Some(7),
            delete_cascade_to_notes: false,
        },
    )
    .unwrap();

    // Positive control, same reasoning as the delete test above.
    let wal_before = std::fs::read(&wal_path).unwrap_or_default();
    let main_before = std::fs::read(&path).unwrap();
    assert!(
        contains(&wal_before, MARKER.as_bytes()) || contains(&main_before, MARKER.as_bytes()),
        "positive control: marker must be present on disk before purge"
    );

    let purged = transcript_repo::purge_expired(&db, now).unwrap();
    assert_eq!(
        purged,
        vec![transcript_id],
        "sanity: the fixture transcript must actually be the one purged"
    );

    // Read with `db` still open — see the doc comment above for why.
    let main_after = std::fs::read(&path).unwrap();
    let wal_after = std::fs::read(&wal_path).unwrap_or_default();
    assert!(
        !contains(&main_after, MARKER.as_bytes()),
        "purged transcript text remained in the main .db3 file — secure_delete is not \
         zeroing freed pages (FR-153)"
    );
    assert!(
        !contains(&wal_after, MARKER.as_bytes()),
        "purged transcript text remained in the -wal file immediately after \
         purge_expired() returned, before any connection close — its own best-effort \
         wal_checkpoint(TRUNCATE) did not clear it (FR-153)"
    );

    drop(db);
}

// --- Listing (enough per row for a list UI, no second read) -------------------------

#[test]
fn listing_returns_label_provider_timing_and_segment_count() {
    // Renamed from `..._without_a_second_read` (PR #30 review, Vera F4, mutation-
    // verified): this test only checks the returned values, which a rewritten N+1
    // `list()` would return identically, so it cannot actually guard "one statement" —
    // see the doc comment on `transcript_repo::list` for where that invariant really
    // lives and why a public-API test structurally cannot pin it here.
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
fn malformed_retention_days_is_reported_corrupt_not_silently_kept_forever() {
    // retention_days is a privacy control (FR-153); a value nobody could parse must
    // fail CLOSED (surfaced as an error) rather than fail OPEN (silently treated as
    // "kept indefinitely", the least protective outcome) — PR #30 review, Sana F5.
    // Mutation check performed by hand: reverting the parse to `.ok()` turns this RED
    // (returns Ok with retention_days: None instead of an error); restoring the `?`
    // turns it GREEN again.
    let db = db();
    db.conn()
        .execute(
            "INSERT INTO transcript_setting (key, value) VALUES ('retention_days', 'not-a-number')",
            [],
        )
        .unwrap();

    let err = transcript_repo::load_retention_settings(&db).unwrap_err();
    assert!(
        matches!(err, selahcue_data::DataError::Corrupt(_)),
        "expected DataError::Corrupt for an unparseable retention_days, got {err:?}"
    );
}

#[test]
fn a_recently_started_unended_transcript_survives_purge_even_with_zero_day_retention() {
    // Grace-period floor, isolated from the orphan-sweep test below: even the most
    // aggressive configured retention (0 days) must never purge a transcript that
    // started inside the orphan grace window, or a short retention_days setting could
    // delete a live, still-recording service out from under it (PR #30 review, Sana
    // F2's fix). Mutation check performed by hand: dropping the
    // `.min(now_ms - ORPHAN_GRACE_MS)` clause from `purge_expired`'s `orphan_cutoff`
    // (using the plain retention `cutoff` alone for orphans) turns this RED (the live
    // transcript gets purged); restoring it turns it GREEN again.
    let db = db();
    let now = 1_000_000_000_i64;
    let live = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "live".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 60_000, // 1 minute ago — nowhere near the grace period
        },
    )
    .unwrap();
    transcript_repo::save_retention_settings(
        &db,
        &RetentionSettings {
            retention_days: Some(0),
            delete_cascade_to_notes: false,
        },
    )
    .unwrap();

    assert_eq!(
        transcript_repo::purge_expired(&db, now).unwrap(),
        Vec::<i64>::new()
    );
    assert!(transcript_repo::load(&db, live).is_ok());
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

    // (c) started 2 hours ago, still recording (no ended_at) — must survive even
    // against a configured window, because it has not yet cleared the crash-orphan
    // grace period; a genuinely live multi-hour service must never be purged out from
    // under it.
    let live = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "live".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 2 * 60 * 60 * 1000,
        },
    )
    .unwrap();

    // (d) started 100 days ago, NEVER ended (a crash mid-service, FR-075 treats this
    // as routine) — once the grace period has long passed, this is an abandoned
    // orphan, not a live session, and must be evaluated against the same retention
    // window using started_at as the effective end. Before the fix, this transcript
    // was exempt from retention forever regardless of age (86ajtxzrn open question #1
    // / Sana F2).
    let orphan = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "orphan".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: now - 100 * DAY_MS,
        },
    )
    .unwrap();

    // With the default (kept indefinitely), purge is a deliberate no-op for
    // everything, orphan included — retention stays opt-in even with eligible-looking
    // rows sitting in the store.
    assert_eq!(
        transcript_repo::purge_expired(&db, now).unwrap(),
        Vec::<i64>::new()
    );
    assert!(
        transcript_repo::load(&db, old).is_ok(),
        "no purge without a configured window"
    );
    assert!(
        transcript_repo::load(&db, orphan).is_ok(),
        "no purge without a configured window, even for a long-abandoned orphan"
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
    let mut expected = vec![old, orphan];
    expected.sort_unstable();
    assert_eq!(
        purged, expected,
        "the ended, past-window transcript AND the long-abandoned orphan are purged"
    );
    assert!(matches!(
        transcript_repo::load(&db, old),
        Err(selahcue_data::DataError::NotFound)
    ));
    assert!(matches!(
        transcript_repo::load(&db, orphan),
        Err(selahcue_data::DataError::NotFound)
    ));
    assert!(
        transcript_repo::load(&db, recent).is_ok(),
        "inside the window must survive"
    );
    assert!(
        transcript_repo::load(&db, live).is_ok(),
        "a recent, genuinely live session must never be purged"
    );
}

// --- FR-082: no transcript/detection content in logs or diagnostics ------------------

/// `err` must be `DataError::Sqlite(_)` — the variant this test exists to exercise for
/// FR-082 (a real SQLite constraint failure, not the data-free `NotFound` path). This
/// is itself a control, not just a cast: BLOCKING-1 (PR #30 review, Quinn/Sana) was
/// exactly that the original test's captured errors were structurally incapable of
/// carrying data (`NotFound` only), which "the diagnostics don't contain MARKER" alone
/// cannot distinguish from "the diagnostics were never real errors to begin with".
fn assert_is_sqlite_variant(err: &selahcue_data::DataError, context: &str) {
    assert!(
        matches!(err, selahcue_data::DataError::Sqlite(_)),
        "{context}: expected DataError::Sqlite(_) — got {err:?} instead, which means \
         this arm was not exercising a real SQLite constraint failure"
    );
}

#[test]
fn no_segment_or_detection_text_reaches_a_dataerror_diagnostic() {
    // BLOCKING-1 (PR #30 review, Quinn and Sana, found independently): the original
    // version of this test called `load`/`end`/`delete` on a hardcoded nonexistent id
    // (999_999) — a row that never held the marker — so every captured error was a
    // plain `NotFound`, which structurally carries no data and can never leak
    // anything. Quinn proved this with a real injected leak in `load()` that the old
    // test never caught (all 17 tests stayed green). This version captures diagnostics
    // from THREE kinds of paths against the transcript that ACTUALLY holds the marker:
    // (a) NotFound, from a genuinely nonexistent id (data-free by construction, kept
    // as one arm for completeness — this alone is what BLOCKING-1 found insufficient);
    // (b) real `Sqlite(rusqlite::Error)` FK-constraint failures raised while MARKER
    // itself is bound as the failing statement's parameter, operating on the real
    // transcript/segment ids — the path BLOCKING-1 found completely unexercised;
    // (c) a genuinely ordinary `load()` call on the transcript that actually holds the
    // marker — the exact call Quinn's own reproduction mutated (making `load()` return
    // `DataError::Corrupt` embedding real segment text whenever a segment's text
    // contained a substring of MARKER, reachable from a completely normal `load()` on
    // marker-bearing data). Re-verified here by hand: applying that exact mutation to
    // `transcript_repo::load` and running this whole file with its siblings (never
    // `--exact`) left arms (a) and (b) alone green — neither one ever calls `load` on
    // the real, existing `transcript_id` — until arm (c) was added; with (c) present,
    // the same mutation turns this test (and only this test) red, and reverting the
    // mutation turns it green again.
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

    let mut diagnostics = String::new();

    // (a) NotFound arm: a genuinely nonexistent id, unrelated to the marker-bearing
    // transcript. Kept for completeness; this alone is what BLOCKING-1 found was the
    // ENTIRE original test.
    let nonexistent = transcript_id + 1_000_000;
    let load_err = transcript_repo::load(&db, nonexistent).unwrap_err();
    diagnostics.push_str(&format!("{load_err} {load_err:?} "));
    let end_err = transcript_repo::end(&db, nonexistent, 0).unwrap_err();
    diagnostics.push_str(&format!("{end_err} {end_err:?} "));
    let delete_err = transcript_repo::delete(&db, nonexistent).unwrap_err();
    diagnostics.push_str(&format!("{delete_err} {delete_err:?} "));

    // (b) Sqlite(rusqlite::Error) arms: MARKER is the actual bound parameter in each
    // failing statement, against the real (existing) transcript_id / seg_id. Each
    // assert_is_sqlite_variant call is itself a positive control that the arm is
    // really hitting a constraint failure, not silently degrading to NotFound or some
    // other data-free path.
    let append_segment_err =
        transcript_repo::append_segment(&db, nonexistent, 0, 1, MARKER).unwrap_err();
    assert_is_sqlite_variant(
        &append_segment_err,
        "append_segment against a bad transcript_id",
    );
    diagnostics.push_str(&format!("{append_segment_err} {append_segment_err:?} "));

    let correct_segment_err =
        transcript_repo::correct_segment(&db, seg_id + 1_000_000, MARKER, 1).unwrap_err();
    assert_is_sqlite_variant(
        &correct_segment_err,
        "correct_segment against a bad segment_id",
    );
    diagnostics.push_str(&format!("{correct_segment_err} {correct_segment_err:?} "));

    let append_detection_err =
        transcript_repo::append_detection(&db, transcript_id, Some(seg_id + 1_000_000), MARKER, 50)
            .unwrap_err();
    assert_is_sqlite_variant(
        &append_detection_err,
        "append_detection against a bad segment_id",
    );
    diagnostics.push_str(&format!("{append_detection_err} {append_detection_err:?}"));

    // (c) The real, ordinary `load()` call on the transcript that actually holds the
    // marker. On today's code this succeeds — a success value is expected to carry the
    // real content back (that is `load()`'s whole job, not a leak) — so this arm is not
    // captured into `diagnostics` on the `Ok` path, only on `Err`, exactly like every
    // other arm above. What this arm actually guards is the class of regression that
    // silently turns that ordinary success into an error carrying real content (Quinn's
    // reproduction: a conditional inside the segment loop that returns
    // `DataError::Corrupt(format!("... {text}"))` for ordinary marker-bearing data). If
    // `load()` ever does that, it lands here and the final assertion below catches it.
    match transcript_repo::load(&db, transcript_id) {
        Ok(detail) => {
            assert_eq!(
                detail.segments.len(),
                1,
                "expected exactly the one marker-bearing segment created above"
            );
            assert_eq!(
                detail.segments[0].text, MARKER,
                "a successful load() must return the real segment text unmodified"
            );
        }
        Err(load_real_err) => {
            diagnostics.push_str(&format!(" {load_real_err} {load_real_err:?}"));
        }
    }

    assert!(
        !contains_a_leak_window_of(&diagnostics, MARKER),
        "sensitive transcript/detection text leaked into a DataError's Display/Debug \
         output (FR-082) — matched at least a {LEAK_WINDOW}-byte window of the marker, \
         not just a full exact match (PR #30 review, Sana F7): {diagnostics}"
    );
    // Second positive control: the captured diagnostics string is real, non-trivial
    // content — proving the capture-and-search methodology isn't itself dead (an empty
    // or unrelated string would make the assertion above vacuous).
    assert!(
        diagnostics.contains("not found") && diagnostics.contains("FOREIGN KEY"),
        "expected both the well-known NotFound message AND a real FOREIGN KEY \
         constraint message in the captured diagnostics; got: {diagnostics} — the \
         capture methodology may not be exercising real error paths"
    );
}

#[test]
fn transcript_repo_source_never_calls_a_logging_or_print_macro() {
    // FR-082, enforced textually as well as at runtime (previous test): nothing in this
    // module needs to log, print, or dbg! anything at all, so the simplest durable
    // control is that none of these ever appear in its source — an addition is caught
    // here even before any test exercises the new line. Mirrors
    // `selahcue-licensing/tests/test_custody.rs`'s "never handed to a formatter" guard.
    // Also forbids panic!/todo!/unimplemented!/.expect( (PR #30 review, Sana F4): a
    // panic's message is exactly as capable of embedding sensitive text as a log line
    // is, and none of the four is otherwise needed in this module.
    //
    // `format!` itself is deliberately NOT in this list: this module already uses it
    // to build `DataError::Corrupt` messages, always over ids, counts, or a fixed
    // literal — with the one documented exception of `load_retention_settings` echoing
    // a malformed *configuration value* (never segment/detection/correction text). See
    // the module doc comment at the top of `transcript_repo.rs` for the full claim;
    // this scan only catches an outright logging/print/panic call, not a `format!` that
    // captures the wrong variable — that half is the runtime test above's job.
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
        "panic!",
        "todo!",
        "unimplemented!",
        ".expect(",
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
