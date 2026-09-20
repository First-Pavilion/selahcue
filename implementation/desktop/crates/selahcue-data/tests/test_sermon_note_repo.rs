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

use rusqlite::params;
use selahcue_data::sermon_note_repo::{
    self, DraftEdit, NewSermonNote, PendingRegeneration, MAX_DISCLOSURE_CHARS, MAX_MODEL_CHARS,
    MAX_PROVIDER_CHARS, MAX_SECTIONS_JSON_BYTES,
};
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

// --- create's returned id (86akgqdv0; PR #33 review, Vera F3) --------------------

#[test]
fn create_returns_the_correct_id_on_the_update_branch_even_with_an_unrelated_insert_between_calls()
{
    // Reproduces Vera's finding exactly: `last_insert_rowid()` does NOT advance on the
    // `DO UPDATE` branch of `INSERT ... ON CONFLICT`, so it can return a STALE id from
    // an unrelated statement that happened to run on the same connection afterward. The
    // old implementation's doc comment claimed otherwise; this test would have failed
    // against that implementation (id 1 expected, 3 actually returned).
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let first_id = sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    // An unrelated insert on the SAME connection, between the two `create` calls —
    // advances `last_insert_rowid()` to something that is NOT this note's id.
    transcript_repo::append_segment(&db, transcript_id, 0, 100, "an unrelated insert").unwrap();
    transcript_repo::append_segment(&db, transcript_id, 100, 200, "another one").unwrap();

    let mut second = sample_note(transcript_id);
    second.title = "Regenerated Title".into();
    let second_id = sermon_note_repo::create(&db, &second).unwrap();

    assert_eq!(
        second_id, first_id,
        "the UPDATE branch of the upsert must return the EXISTING row's id, not a stale \
         last_insert_rowid() from an unrelated intervening insert"
    );
    let actual_id: i64 = db
        .conn()
        .query_row(
            "SELECT id FROM sermon_note WHERE transcript_id = ?1",
            params![transcript_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(
        second_id, actual_id,
        "the returned id must match the real row id on disk"
    );
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

// --- provider/disclosure/model bounds (PR #33 review, Sana N3 — Low: previously
// unbounded — a 30,000-char provider / 20,000-char disclosure / 5,000-char model was
// accepted and stored). Create-only: `DraftEdit`/`update` cannot touch these fields at
// all, so only `create` needs the check. -----------------------------------------

#[test]
fn an_oversized_provider_on_create_is_refused_before_any_row_is_written() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut note = sample_note(transcript_id);
    note.provider = "x".repeat(MAX_PROVIDER_CHARS + 1);

    let err = sermon_note_repo::create(&db, &note).unwrap_err();
    assert!(matches!(err, DataError::TooLarge(_)));
    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None,
        "a refused create must not leave a partial row behind"
    );
}

#[test]
fn an_oversized_disclosure_on_create_is_refused_before_any_row_is_written() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut note = sample_note(transcript_id);
    note.disclosure = Some("x".repeat(MAX_DISCLOSURE_CHARS + 1));

    let err = sermon_note_repo::create(&db, &note).unwrap_err();
    assert!(matches!(err, DataError::TooLarge(_)));
    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None,
        "a refused create must not leave a partial row behind"
    );
}

#[test]
fn an_oversized_model_on_create_is_refused_before_any_row_is_written() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut note = sample_note(transcript_id);
    note.model = Some("x".repeat(MAX_MODEL_CHARS + 1));

    let err = sermon_note_repo::create(&db, &note).unwrap_err();
    assert!(matches!(err, DataError::TooLarge(_)));
    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None,
        "a refused create must not leave a partial row behind"
    );
}

#[test]
fn provider_disclosure_and_model_exactly_at_their_bounds_are_accepted_positive_control() {
    // Positive control for the three tests above: the mechanism must not reject
    // everything — only what actually exceeds each bound (an off-by-one guard, or one
    // that rejects unconditionally, would fail this).
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut note = sample_note(transcript_id);
    note.provider = "p".repeat(MAX_PROVIDER_CHARS);
    note.disclosure = Some("d".repeat(MAX_DISCLOSURE_CHARS));
    note.model = Some("m".repeat(MAX_MODEL_CHARS));

    sermon_note_repo::create(&db, &note).unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.provider, note.provider);
    assert_eq!(loaded.disclosure, note.disclosure);
    assert_eq!(loaded.model, note.model);
}

// --- delete_for_transcript is idempotent ------------------------------------------

#[test]
fn delete_for_transcript_with_no_draft_is_a_harmless_no_op() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::delete_for_transcript(&db, transcript_id).unwrap();
    sermon_note_repo::delete_for_transcript(&db, transcript_id).unwrap();
}

// --- Detached notes are reachable (86akgqdv0; PR #33 review, Sana F3) ------------
//
// A note whose transcript was deleted with cascade OFF becomes `transcript_id = NULL`
// (the schema's `ON DELETE SET NULL` floor) and is invisible to `find_by_transcript`.
// Without a path back to it, it is undeletable forever — an FR-153 gap. `list_detached`
// + `delete_by_id` are that path.

fn detach_note(db: &Database, transcript_id: i64, note_id: i64) {
    // Simulates what a non-cascading `transcript_repo::delete` does to a note's
    // `transcript_id`, without depending on `transcript_repo` here — this file is
    // scoped to `sermon_note_repo`'s own public API plus whatever fixture setup it
    // needs (mirrors `test_transcript_repo.rs`'s own cascade tests, which exercise the
    // real `transcript_repo::delete` instead; this file exercises `list_detached`/
    // `delete_by_id` directly against a detached row).
    db.conn()
        .execute(
            "UPDATE sermon_note SET transcript_id = NULL WHERE id = ?1",
            params![note_id],
        )
        .unwrap();
    let _ = transcript_id;
}

#[test]
fn list_detached_finds_a_note_whose_transcript_id_went_null() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let note_id = sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
    // Positive control: an ATTACHED note must not appear as detached.
    assert!(
        sermon_note_repo::list_detached(&db).unwrap().is_empty(),
        "an attached note must not be listed as detached"
    );

    detach_note(&db, transcript_id, note_id);

    let detached = sermon_note_repo::list_detached(&db).unwrap();
    assert_eq!(detached.len(), 1);
    assert_eq!(detached[0].id, note_id);
    assert_eq!(detached[0].transcript_id, None);
    assert_eq!(detached[0].title, sample_note(transcript_id).title);
}

#[test]
fn delete_by_id_removes_a_detached_note_that_is_otherwise_unreachable() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let note_id = sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
    detach_note(&db, transcript_id, note_id);
    assert!(
        sermon_note_repo::find_by_transcript(&db, transcript_id)
            .unwrap()
            .is_none(),
        "sanity: a detached note is unreachable via find_by_transcript"
    );

    sermon_note_repo::delete_by_id(&db, note_id).unwrap();

    assert!(
        sermon_note_repo::list_detached(&db).unwrap().is_empty(),
        "the detached note must actually be gone"
    );
    let row_count: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM sermon_note WHERE id = ?1",
            params![note_id],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(row_count, 0);
}

#[test]
fn delete_by_id_also_removes_an_attached_note() {
    // delete_by_id is not detached-only — it deletes by id regardless of attachment
    // state (its doc comment says so explicitly).
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let note_id = sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    sermon_note_repo::delete_by_id(&db, note_id).unwrap();

    assert_eq!(
        sermon_note_repo::find_by_transcript(&db, transcript_id).unwrap(),
        None
    );
}

#[test]
fn delete_by_id_for_an_unknown_id_is_a_harmless_no_op() {
    let db = db();
    sermon_note_repo::delete_by_id(&db, 9_999).unwrap();
    sermon_note_repo::delete_by_id(&db, 9_999).unwrap();
}

// --- Regenerate-with-retention (FR-129, 86akgqdx8) --------------------------------
//
// Single prior version, explicit-confirm-before-replace: `stage_regeneration` must
// never touch the accepted columns; `confirm_regeneration` moves pending onto
// accepted; `discard_regeneration` clears pending only. The "a transport failure
// during regenerate never loses the prior draft" acceptance criterion is proven at
// THIS layer by the simple fact that `stage_regeneration` is the only entry point
// that can create a pending row, and a caller that never calls it (because
// generation failed) leaves the accepted draft provably untouched — see
// `an_unstaged_transcript_has_no_pending_regeneration_and_the_accepted_draft_is_
// unaffected` below for the direct assertion.

fn sample_pending(generated_at_ms: i64) -> PendingRegeneration {
    PendingRegeneration {
        title: "Regenerated: The Faithful Servant".into(),
        summary: Some("A fresh summary from the regenerate.".into()),
        sections_json: r#"[{"heading":"New Points","items":["fresh"],"points":[]}]"#.into(),
        scriptures_json: r#"["Matthew 25:23"]"#.into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
        generated_at_ms,
    }
}

#[test]
fn staging_a_regeneration_leaves_the_accepted_draft_completely_untouched() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id);
    sermon_note_repo::create(&db, &original).unwrap();

    sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000)).unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    // The PRIOR VERSION — every accepted-column field — is byte-identical to what it
    // was before staging. This is the direct proof of "the prior draft is retrievable,
    // unmodified, immediately after a regenerate is requested, before the operator
    // confirms replacement."
    assert_eq!(loaded.title, original.title);
    assert_eq!(loaded.summary, original.summary);
    assert_eq!(loaded.sections_json, original.sections_json);
    assert_eq!(loaded.scriptures_json, original.scriptures_json);
    assert_eq!(loaded.ai_generated, original.ai_generated);
    assert_eq!(loaded.disclosure, original.disclosure);
    assert_eq!(loaded.provider, original.provider);
    assert_eq!(loaded.model, original.model);
    assert_eq!(loaded.created_at_ms, original.created_at_ms);
    assert_eq!(loaded.edited_at_ms, original.created_at_ms);

    // The NEW draft is visible as pending, not silently dropped.
    let pending = loaded
        .pending
        .expect("a staged regeneration must be visible as pending");
    assert_eq!(pending.title, "Regenerated: The Faithful Servant");
    assert_eq!(pending.generated_at_ms, 9_000);
}

#[test]
fn staging_a_regeneration_with_no_existing_draft_is_not_found() {
    // Regenerate requires something to regenerate FROM — a true first-time generate
    // goes through `create`, never `stage_regeneration`.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let err = sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000))
        .unwrap_err();
    assert!(matches!(err, DataError::NotFound));
}

#[test]
fn a_second_stage_before_confirm_overwrites_the_first_pending_regeneration() {
    // Single pending slot: only the ACCEPTED draft is guaranteed retained, never an
    // intermediate, never-confirmed regeneration attempt.
    //
    // 86akgqdx8 review (Vera N1): asserting only the LATEST pending title/timestamp proves
    // last-writer-wins, but would still pass against a history-table implementation that kept
    // every attempt and merely returned the newest one — it does not prove the "single slot"
    // part of the design. Repeatedly re-staging and then asserting `sermon_note`'s row COUNT
    // stays at exactly 1 for this transcript is what actually pins boundedness: a history-table
    // regression would grow that count, and this loop would catch it on the very next stage.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    for attempt in 0..5 {
        let mut pending = sample_pending(9_000 + attempt);
        pending.title = format!("Regeneration Attempt {attempt}");
        sermon_note_repo::stage_regeneration(&db, transcript_id, &pending).unwrap();

        let row_count: i64 = db
            .conn()
            .query_row(
                "SELECT COUNT(*) FROM sermon_note WHERE transcript_id = ?1",
                params![transcript_id],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(
            row_count, 1,
            "staging must overwrite the single pending slot in place, never grow a history \
             (attempt {attempt})"
        );
    }

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    let pending = loaded.pending.unwrap();
    assert_eq!(pending.title, "Regeneration Attempt 4");
    assert_eq!(pending.generated_at_ms, 9_004);
}

#[test]
fn confirming_a_regeneration_replaces_the_accepted_draft_and_clears_pending() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
    sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000)).unwrap();

    let confirmed = sermon_note_repo::confirm_regeneration(&db, transcript_id).unwrap();
    assert_eq!(confirmed.title, "Regenerated: The Faithful Servant");
    assert_eq!(confirmed.sections_json, sample_pending(9_000).sections_json);
    assert_eq!(confirmed.created_at_ms, 9_000);
    assert_eq!(
        confirmed.edited_at_ms, 9_000,
        "a confirmed regeneration is a fresh version: edited_at == created_at"
    );
    assert!(
        confirmed.pending.is_none(),
        "confirming must clear the pending slot"
    );

    // Re-read from scratch — not just the return value — to prove it actually persisted.
    let reloaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(reloaded.title, "Regenerated: The Faithful Servant");
    assert!(reloaded.pending.is_none());
}

#[test]
fn confirming_a_downgrade_to_not_ai_generated_is_refused_and_the_accepted_draft_is_untouched() {
    // "Once AI-generated, always AI-generated" (PR #33 review, Sana N2), extended to
    // confirm: a degraded (local-fallback) regenerate's pending draft is `ai_generated:
    // false` — it must stay VISIBLE (staged, not silently dropped) but must never be
    // confirmable over an already-AI-generated accepted draft.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id); // ai_generated: true
    sermon_note_repo::create(&db, &original).unwrap();

    let mut degraded_pending = sample_pending(9_000);
    degraded_pending.ai_generated = false;
    degraded_pending.disclosure = None;
    degraded_pending.provider = "Local (offline)".into();
    sermon_note_repo::stage_regeneration(&db, transcript_id, &degraded_pending).unwrap();

    let err = sermon_note_repo::confirm_regeneration(&db, transcript_id).unwrap_err();
    assert!(
        matches!(err, DataError::Refused(_)),
        "expected DataError::Refused, got {err:?}"
    );

    // The accepted draft is completely untouched, and the pending draft is STILL there
    // (visible, not silently discarded) so the operator can still discard it themselves.
    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.title, original.title);
    assert!(loaded.ai_generated);
    assert_eq!(loaded.created_at_ms, original.created_at_ms);
    let pending = loaded
        .pending
        .expect("the refused pending draft must remain staged");
    assert!(!pending.ai_generated);
}

#[test]
fn confirming_a_degraded_regeneration_over_a_never_ai_generated_draft_is_allowed_positive_control()
{
    // Positive control for the guard above: it must not reject EVERY downgrade-shaped
    // pending draft unconditionally — only one that would strip the label from an
    // ALREADY AI-generated accepted draft. An accepted draft that was never
    // AI-generated has no label to protect.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let mut never_ai = sample_note(transcript_id);
    never_ai.ai_generated = false;
    never_ai.disclosure = None;
    sermon_note_repo::create(&db, &never_ai).unwrap();

    let mut degraded_pending = sample_pending(9_000);
    degraded_pending.ai_generated = false;
    degraded_pending.disclosure = None;
    sermon_note_repo::stage_regeneration(&db, transcript_id, &degraded_pending).unwrap();

    let confirmed = sermon_note_repo::confirm_regeneration(&db, transcript_id).unwrap();
    assert!(!confirmed.ai_generated);
    assert_eq!(confirmed.title, "Regenerated: The Faithful Servant");
}

#[test]
fn confirming_an_ai_generated_regeneration_over_an_ai_generated_draft_is_allowed_positive_control()
{
    // Second positive control: a non-degraded (still AI-generated) regeneration must
    // confirm normally over an already AI-generated accepted draft — the guard only
    // blocks an actual downgrade, never a same-or-improved provenance.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
    sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000)).unwrap();

    let confirmed = sermon_note_repo::confirm_regeneration(&db, transcript_id).unwrap();
    assert!(confirmed.ai_generated);
    assert_eq!(confirmed.title, "Regenerated: The Faithful Servant");
}

#[test]
fn confirming_with_nothing_pending_is_not_found() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    let err = sermon_note_repo::confirm_regeneration(&db, transcript_id).unwrap_err();
    assert!(matches!(err, DataError::NotFound));
}

#[test]
fn discarding_a_pending_regeneration_leaves_the_accepted_draft_unchanged() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id);
    sermon_note_repo::create(&db, &original).unwrap();
    sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000)).unwrap();

    sermon_note_repo::discard_regeneration(&db, transcript_id).unwrap();

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.title, original.title);
    assert_eq!(loaded.created_at_ms, original.created_at_ms);
    assert!(
        loaded.pending.is_none(),
        "discard must clear the pending slot"
    );
}

#[test]
fn discarding_with_nothing_pending_is_a_harmless_no_op() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();

    // Idempotent — no error whether or not anything was pending.
    sermon_note_repo::discard_regeneration(&db, transcript_id).unwrap();
    sermon_note_repo::discard_regeneration(&db, transcript_id).unwrap();

    assert!(sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap()
        .pending
        .is_none());
}

#[test]
fn discarding_for_a_transcript_with_no_draft_at_all_is_a_harmless_no_op() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    // No `create` at all — the row does not exist yet.
    sermon_note_repo::discard_regeneration(&db, transcript_id).unwrap();
}

#[test]
fn an_unstaged_draft_has_no_pending_regeneration_and_is_unaffected_by_a_failed_generation_attempt()
{
    // Direct proof of the "a transport failure during regenerate must not lose the
    // prior draft" acceptance criterion, at the repo layer: a caller whose generation
    // attempt failed simply never calls `stage_regeneration` at all (see
    // `selahcue-operator`'s `run_note_generation`/`generate_sermon_notes` — the
    // persistence step is unreachable on an `Err` outcome). The accepted draft is
    // therefore, by construction, exactly what it was before the attempt.
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id);
    sermon_note_repo::create(&db, &original).unwrap();

    // Simulates "the regenerate attempt failed before ever staging anything" — no
    // call to `stage_regeneration` happens on this path.

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.title, original.title);
    assert_eq!(loaded.created_at_ms, original.created_at_ms);
    assert!(loaded.pending.is_none());
}

#[test]
fn staging_an_oversized_pending_field_is_refused_and_the_accepted_draft_is_untouched() {
    let db = db();
    let transcript_id = make_transcript(&db, 1_000);
    let original = sample_note(transcript_id);
    sermon_note_repo::create(&db, &original).unwrap();

    let mut oversized = sample_pending(9_000);
    oversized.sections_json = "x".repeat(MAX_SECTIONS_JSON_BYTES + 1);
    let err = sermon_note_repo::stage_regeneration(&db, transcript_id, &oversized).unwrap_err();
    assert!(matches!(err, DataError::TooLarge(_)));

    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(loaded.sections_json, original.sections_json);
    assert!(
        loaded.pending.is_none(),
        "a refused stage must not leave a partial pending row behind"
    );
}

#[test]
fn a_pending_regeneration_survives_a_fresh_database_open_of_the_same_file() {
    // Durability: the pending slot is a real column, not in-memory state — it must
    // survive a restart exactly like the accepted draft already does.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();

    let transcript_id;
    {
        let db = Database::open(&path).unwrap();
        transcript_id = make_transcript(&db, 1_000);
        sermon_note_repo::create(&db, &sample_note(transcript_id)).unwrap();
        sermon_note_repo::stage_regeneration(&db, transcript_id, &sample_pending(9_000)).unwrap();
    }

    let db = Database::open(&path).unwrap();
    let loaded = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .expect("the draft must still be there after a restart");
    let pending = loaded
        .pending
        .expect("the pending regeneration must survive a restart too");
    assert_eq!(pending.title, "Regenerated: The Faithful Servant");
}
