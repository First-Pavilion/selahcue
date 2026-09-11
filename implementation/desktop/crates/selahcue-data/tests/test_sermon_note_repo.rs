//! Integration tests for `sermon_note_repo` (86akgqdv0; FR-123 "editable" half).
//! Public API only (mirrors `test_transcript_repo.rs`/`test_screen_repo.rs`).
//!
//! Covers: create/read-by-transcript round trip, survival across a fresh
//! `Database::open` of the same file (the "restart the app, reopen the same
//! transcript" acceptance criterion), editing preserves the FR-123/FR-128 label,
//! the persisted-storage byte-identical-transcript regression (companion to
//! `selahcue-cloud/tests/test_openai.rs`'s in-memory
//! `generation_and_draft_editing_leave_the_source_transcript_byte_identical`), and a
//! mutation-verified bounded-memory test proving an oversized edit is refused rather
//! than silently accepted.

#![allow(clippy::unwrap_used)]

use selahcue_data::sermon_note_repo::{self, DraftEdit, NewSermonNote, MAX_SECTIONS_JSON_BYTES};
use selahcue_data::transcript_repo::{self, NewTranscript};
use selahcue_data::{DataError, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

fn make_transcript(db: &Database, started_at_ms: i64) -> i64 {
    transcript_repo::create(
        db,
        &NewTranscript {
            label: "Sunday Service".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms,
        },
    )
    .unwrap()
}

fn sample_note(transcript_id: i64) -> NewSermonNote {
    NewSermonNote {
        transcript_id,
        title: "The Faithful Servant".into(),
        summary: Some("A message on faithfulness in small things.".into()),
        sections_json: r#"[{"heading":"Main Points","items":[],"points":[{"text":"Be faithful","sub_points":["In little","In much"]}]}]"#.into(),
        scriptures_json: r#"["Luke 16:10","Matthew 25:21"]"#.into(),
        ai_generated: true,
        disclosure: Some(
            "AI-generated. It can invent quotations. Check every reference.".into(),
        ),
        provider: "SelahCue AI".into(),
        model: None,
        created_at_ms: 5_000,
    }
}

// --- Round trip ------------------------------------------------------------------

#[test]
fn a_created_draft_reads_back_identical_by_transcript_id() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let note = sample_note(transcript_id);
    let id = sermon_note_repo::create(&db, &note).unwrap();
    assert!(id > 0);

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .expect("draft must exist right after create");

    assert_eq!(loaded.transcript_id, Some(transcript_id));
    assert_eq!(loaded.title, note.title);
    assert_eq!(loaded.summary, note.summary);
    assert_eq!(loaded.sections_json, note.sections_json);
    assert_eq!(loaded.scriptures_json, note.scriptures_json);
    assert_eq!(loaded.ai_generated, note.ai_generated);
    assert_eq!(loaded.disclosure, note.disclosure);
    assert_eq!(loaded.provider, note.provider);
    assert_eq!(loaded.model, note.model);
    assert_eq!(loaded.created_at_ms, note.created_at_ms);
    assert_eq!(
        loaded.edited_at_ms, note.created_at_ms,
        "unedited: edited_at == created_at"
    );
}

#[test]
fn no_draft_for_a_transcript_reads_back_none_not_an_error() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None
    );
}

#[test]
fn create_is_scoped_per_transcript() {
    let db = db();
    let a = make_transcript(&db, 1_000);
    let b = make_transcript(&db, 2_000);
    sermon_note_repo::create(&db, &sample_note(a)).unwrap();

    assert!(sermon_note_repo::find_by_transcript(&db, a)
        .unwrap()
        .is_some());
    assert!(sermon_note_repo::find_by_transcript(&db, b)
        .unwrap()
        .is_none());
}

// --- Regenerate = upsert (FR-129 is out of this ticket's scope) ------------------

#[test]
fn a_second_create_for_the_same_transcript_replaces_the_draft_wholesale() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    let mut second = sample_note(transcript_id);
    second.title = "Regenerated Title".into();
    second.created_at_ms = 9_000;
    sermon_note_repo::create(&db, &second).unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.title, "Regenerated Title");
    assert_eq!(
        loaded.created_at_ms, 9_000,
        "a regenerate replaces created_at too — no version history until FR-129"
    );
}

// --- Restart survival (acceptance criterion: reopen the app, draft is still there) -

#[test]
fn a_draft_survives_a_fresh_database_open_of_the_same_file() {
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();

    let transcript_id;
    {
        let db = Database::open(&path).unwrap();
        transcript_id = make_transcript(&db, 1_000);
        sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
        // `db` dropped here — simulates the app closing.
    }

    // Simulates the app reopening: a brand new `Database::open` of the same file.
    let db = Database::open(&path).unwrap();
    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .expect("the draft must still be there after a restart");
    assert_eq!(loaded.title, sample_note(transcript_id).title);
    assert!(loaded.ai_generated);
    assert!(loaded.disclosure.is_some());
}

// --- Editing preserves the FR-123/FR-128 label ------------------------------------

#[test]
fn editing_title_summary_and_sections_persists_and_survives_reopen() {
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    let transcript_id;
    {
        let db = Database::open(&path).unwrap();
        transcript_id = make_transcript(&db, 1_000);
        sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

        let edit = DraftEdit {
            title: "Edited: The Faithful Servant".into(),
            summary: Some("Rewritten by the operator.".into()),
            sections_json: r#"[{"heading":"Main Points","items":["A flat item now"],"points":[]}]"#
                .into(),
            scriptures_json: r#"["Luke 16:10"]"#.into(),
        };
        sermon_note_repo::update(&db, transcript_id, &edit, 8_000).unwrap();
    }

    let db = Database::open(&path).unwrap();
    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.title, "Edited: The Faithful Servant");
    assert_eq!(
        loaded.summary.as_deref(),
        Some("Rewritten by the operator.")
    );
    assert_eq!(
        loaded.sections_json,
        r#"[{"heading":"Main Points","items":["A flat item now"],"points":[]}]"#
    );
    assert_eq!(loaded.scriptures_json, r#"["Luke 16:10"]"#);
    assert_eq!(loaded.edited_at_ms, 8_000);
}

#[test]
fn editing_a_draft_never_drops_the_ai_generated_label_or_disclosure() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id);
    sermon_note_repo::create(&db, &original).unwrap();

    sermon_note_repo::update(
        &db,
        transcript_id,
        &DraftEdit {
            title: "A totally rewritten title".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
        },
        6_000,
    )
    .unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    // FR-123 / FR-128: the label and disclosure are set once at generation time and
    // are structurally unreachable from `DraftEdit` — this asserts the outcome, not
    // just the API shape.
    assert!(
        loaded.ai_generated,
        "FR-123: editing must not silently drop the AI-generated label"
    );
    assert_eq!(
        loaded.disclosure, original.disclosure,
        "FR-128: editing must not silently drop the fabrication disclosure"
    );
    assert_eq!(loaded.provider, original.provider);
    assert_eq!(
        loaded.created_at_ms, original.created_at_ms,
        "editing must not disturb when the draft was originally generated"
    );
}

#[test]
fn updating_a_transcript_with_no_draft_is_not_found() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let err = sermon_note_repo::update(
        &db,
        transcript_id,
        &DraftEdit {
            title: "x".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
        },
        1,
    )
    .unwrap_err();
    assert!(matches!(err, DataError::NotFound));
}

// --- Byte-identical transcript through generate + persist + edit -----------------
//
// Companion to `selahcue-cloud/tests/test_openai.rs`'s
// `generation_and_draft_editing_leave_the_source_transcript_byte_identical`, which
// proves the invariant purely in memory (no persistence exists in that crate). This
// test proves the same invariant at the persistence layer, where 86akgqdv0 actually
// writes data: `selahcue-cloud` has no dependency on `selahcue-data` (and
// deliberately gains none for this ticket — see the PR description), so the
// persisted-storage half of the invariant is proven here instead, where both
// `transcript_repo` and `sermon_note_repo` already live together.

#[test]
fn generating_persisting_and_editing_a_draft_leaves_the_stored_transcript_byte_identical() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    const SEGMENT_TEXT: &str = "In the beginning God created the heavens and the earth.";
    transcript_repo::append_segment(&db, transcript_id, 0, 5_000, SEGMENT_TEXT).unwrap();

    let stored_before = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(stored_before.segments[0].text, SEGMENT_TEXT);

    // "After generation": persist a freshly generated draft against this transcript.
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
    let stored_after_generate = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        stored_after_generate.segments[0].text.as_bytes(),
        SEGMENT_TEXT.as_bytes(),
        "FR-123: persisting the generated draft must not touch the source transcript"
    );

    // "After editing": edit the draft's text.
    sermon_note_repo::update(
        &db,
        transcript_id,
        &DraftEdit {
            title: "Edited by the operator".into(),
            summary: Some("rewritten".into()),
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
        },
        9_000,
    )
    .unwrap();
    let stored_after_edit = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(
        stored_after_edit.segments[0].text.as_bytes(),
        SEGMENT_TEXT.as_bytes(),
        "FR-123: editing the draft must not write back into the source transcript"
    );

    // All three reads are byte-identical to each other, not just to the constant.
    assert_eq!(
        stored_before.segments[0].text,
        stored_after_generate.segments[0].text
    );
    assert_eq!(
        stored_after_generate.segments[0].text,
        stored_after_edit.segments[0].text
    );
}

// --- Bounded storage (mutation-verified) ------------------------------------------
//
// The entity under test is "an oversized/malformed edit is REFUSED, so storage
// cannot grow unbounded" — not a byte-count proxy. Both directions are asserted: the
// hostile case is refused AND the benign case still writes (positive control), per
// this repo's bounded-memory-test convention (CLAUDE.md).
//
// Mutation check performed by hand: commenting out the `check_bounds` call at the
// top of `sermon_note_repo::update` turns `an_oversized_edit_is_refused_and_storage_
// stays_at_the_prior_value` RED (the oversized write succeeds); restoring the call
// turns it GREEN again. Run with siblings (`cargo test -p selahcue-data`), not
// `--exact`, per the repo's mutation-verification convention.

#[test]
fn an_oversized_edit_is_refused_and_storage_stays_at_the_prior_value() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    // One byte past the documented bound.
    let oversized_sections = "x".repeat(MAX_SECTIONS_JSON_BYTES + 1);
    let err = sermon_note_repo::update(
        &db,
        transcript_id,
        &DraftEdit {
            title: "still fine".into(),
            summary: None,
            sections_json: oversized_sections,
            scriptures_json: "[]".into(),
        },
        7_000,
    )
    .unwrap_err();
    assert!(
        matches!(err, DataError::TooLarge(_)),
        "expected DataError::TooLarge, got {err:?}"
    );

    // The write must not have partially applied — the prior draft is untouched.
    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(
        loaded.sections_json,
        sample_note(transcript_id).sections_json,
        "an oversized edit must be refused wholesale, not partially written"
    );
    assert_eq!(
        loaded.edited_at_ms,
        sample_note(transcript_id).created_at_ms
    );
}

#[test]
fn a_field_exactly_at_the_bound_is_accepted_positive_control() {
    // Positive control for the test above: the mechanism must not reject everything
    // — only what actually exceeds the bound (an off-by-one guard would fail this).
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    let at_bound_sections = format!(r#"["{}"]"#, "x".repeat(MAX_SECTIONS_JSON_BYTES - 4));
    assert_eq!(at_bound_sections.len(), MAX_SECTIONS_JSON_BYTES);
    sermon_note_repo::update(
        &db,
        transcript_id,
        &DraftEdit {
            title: "still fine".into(),
            summary: None,
            sections_json: at_bound_sections.clone(),
            scriptures_json: "[]".into(),
        },
        7_000,
    )
    .unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.sections_json, at_bound_sections);
}

#[test]
fn an_oversized_title_on_create_is_refused_before_any_row_is_written() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut note = sample_note(transcript_id);
    note.title = "x".repeat(sermon_note_repo::MAX_TITLE_CHARS + 1);

    let err = sermon_note_repo::create(&db, &note).unwrap_err();
    assert!(matches!(err, DataError::TooLarge(_)));
    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None,
        "a refused create must not leave a partial row behind"
    );
}

// --- delete_for_transcript is idempotent ------------------------------------------

#[test]
fn delete_for_transcript_with_no_draft_is_a_harmless_no_op() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::delete_for_transcript(&db, transcript_id).unwrap();
    sermon_note_repo::delete_for_transcript(&db, transcript_id).unwrap();
}
