//! Repository for generated sermon-note draft persistence (86akgqdv0; FR-123
//! "editable" half — generation, labelling, and the untouched-transcript invariant
//! shipped already in 86akby7d8).
//!
//! One editable draft per transcript (`transcript_id` is `UNIQUE`). [`create`]
//! upserts: a second call for a transcript that already has a draft REPLACES it
//! wholesale, including `created_at` — regenerating a draft and retaining a prior
//! version (FR-129, 86akgqdx8) is a separate, not-yet-built ticket, so today a
//! regenerate silently discards any edits made to the previous draft. This is a
//! deliberate interim behaviour, not an oversight; see the migration comment
//! (v20 -> v21, `migrations.rs`) and this ticket's PR description.
//!
//! `sections`/`scriptures` are opaque JSON `TEXT` — this crate never parses them.
//! `selahcue_core::providers::NoteSection` is a tagged union (flat items XOR
//! outline points/sub-points, FR-122) whose codec lives in `selahcue-operator`
//! (which already depends on `serde_json` for the wire to the JS UI), mirroring
//! `deck_repo`'s `deck_json` precedent: the data layer is a dumb store that
//! round-trips whatever shape the caller hands it. Consequently this module can
//! only bound *size*, not well-formedness — a syntactically malformed JSON string
//! is expected to be rejected by the caller (via its own `serde_json` parse)
//! before ever reaching [`create`]/[`update`]; see those functions' docs.
//!
//! [`update`] touches ONLY the editable columns (`title`, `summary`, `sections`,
//! `scriptures`, `edited_at`). `ai_generated`, `disclosure`, `provider`, and
//! `model` are set once at [`create`] time and are never touched by an edit — so
//! editing a draft can never silently drop the FR-123 AI-generated label or the
//! FR-128 fabrication disclosure.
//!
//! Deleting a transcript's cascade to its note (or not) is NOT decided in this
//! module — it is decided by `transcript_repo::delete`/`purge_expired`, which
//! consult `transcript_repo::RetentionSettings::delete_cascade_to_notes` and
//! explicitly delete the matching row here when that setting is on. The schema's
//! own `ON DELETE SET NULL` (see the migration) is only the FLOOR behaviour: a
//! note whose transcript is gone and cascade was OFF simply has `transcript_id =
//! NULL`, and [`find_by_transcript`] can no longer find it (which is the point —
//! its source is gone) even though the row itself still exists.

use crate::{DataError, Database, Result};
use rusqlite::params;

/// Upper bound on a draft title, in characters (not bytes — multi-byte text is not
/// penalized for using more bytes per glyph).
pub const MAX_TITLE_CHARS: usize = 300;
/// Upper bound on a draft summary, in characters.
pub const MAX_SUMMARY_CHARS: usize = 4_000;
/// Upper bound on the serialized `sections` JSON, in bytes. Generous (a multi-point
/// outline with sub-points easily runs a few KB) but bounded — this is the ceiling
/// that stops a hostile or malformed edit from parking an unbounded string in the
/// database, not a realistic-content estimate.
pub const MAX_SECTIONS_JSON_BYTES: usize = 200_000;
/// Upper bound on the serialized `scriptures` JSON, in bytes.
pub const MAX_SCRIPTURES_JSON_BYTES: usize = 20_000;

/// A freshly generated draft to persist against its source transcript.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NewSermonNote {
    pub transcript_id: i64,
    pub title: String,
    pub summary: Option<String>,
    /// Serialized `Vec<NoteSection>` (FR-122 items-XOR-points shape) — opaque to
    /// this crate; see the module docs.
    pub sections_json: String,
    /// Serialized `Vec<String>` of scripture references — opaque to this crate.
    pub scriptures_json: String,
    /// FR-123: whether a generative model produced this draft.
    pub ai_generated: bool,
    /// FR-128: the fabrication-risk disclosure. `Some` exactly when `ai_generated`
    /// — this invariant is the caller's (`GenerationOutcome`'s) to keep; this repo
    /// stores whatever it is given without re-deriving or checking the pairing.
    pub disclosure: Option<String>,
    /// The serving provider's human-readable label (e.g. `"SelahCue AI"`,
    /// `"Local (offline)"`).
    pub provider: String,
    /// A model identifier, when the serving provider reports one. `None` is
    /// expected and honest at every call site wired by this ticket — no
    /// `NoteProvider` implementation exposes a model id through
    /// `GenerationOutcome` today.
    pub model: Option<String>,
    pub created_at_ms: i64,
}

/// An operator-supplied edit to an existing draft's text. Deliberately carries
/// none of `ai_generated`/`disclosure`/`provider`/`model`/`created_at` — there is
/// no way to pass them to [`update`], which is what makes "an edit cannot touch
/// the label" a property of the API rather than a convention callers must
/// remember.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DraftEdit {
    pub title: String,
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
}

/// A draft read back in full.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SermonNoteRecord {
    pub id: i64,
    /// `None` when the source transcript was deleted without cascade (the schema's
    /// `ON DELETE SET NULL` floor) — the note survives, detached.
    pub transcript_id: Option<i64>,
    pub title: String,
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
    pub ai_generated: bool,
    pub disclosure: Option<String>,
    pub provider: String,
    pub model: Option<String>,
    pub created_at_ms: i64,
    pub edited_at_ms: i64,
}

/// Reject an oversized field before it ever reaches a write. Shared by [`create`]
/// and [`update`] so the bound is one expression, not two copies that could drift.
fn check_bounds(
    title: &str,
    summary: Option<&str>,
    sections_json: &str,
    scriptures_json: &str,
) -> Result<()> {
    if title.chars().count() > MAX_TITLE_CHARS {
        return Err(DataError::TooLarge(format!(
            "sermon_note.title exceeds {MAX_TITLE_CHARS} characters"
        )));
    }
    if let Some(s) = summary {
        if s.chars().count() > MAX_SUMMARY_CHARS {
            return Err(DataError::TooLarge(format!(
                "sermon_note.summary exceeds {MAX_SUMMARY_CHARS} characters"
            )));
        }
    }
    if sections_json.len() > MAX_SECTIONS_JSON_BYTES {
        return Err(DataError::TooLarge(format!(
            "sermon_note.sections exceeds {MAX_SECTIONS_JSON_BYTES} bytes"
        )));
    }
    if scriptures_json.len() > MAX_SCRIPTURES_JSON_BYTES {
        return Err(DataError::TooLarge(format!(
            "sermon_note.scriptures exceeds {MAX_SCRIPTURES_JSON_BYTES} bytes"
        )));
    }
    Ok(())
}

/// Persist a freshly generated draft against its source transcript. Upserts: a
/// second call for the same `transcript_id` REPLACES the existing row wholesale
/// (see the module docs — this is FR-129's territory to change). Rejects an
/// oversized field with [`DataError::TooLarge`] before writing anything.
///
/// **Does not validate JSON well-formedness** — `sections_json`/`scriptures_json`
/// are stored verbatim. A caller that accepts these from an untrusted or
/// user-editable surface (the edit command, not this one — a freshly generated
/// draft is provider output the operator already trusted enough to display) is
/// expected to have already validated them; see [`update`].
pub fn create(db: &Database, note: &NewSermonNote) -> Result<i64> {
    check_bounds(
        &note.title,
        note.summary.as_deref(),
        &note.sections_json,
        &note.scriptures_json,
    )?;
    db.conn().execute(
        "INSERT INTO sermon_note
            (transcript_id, title, summary, sections, scriptures, ai_generated,
             disclosure, provider, model, created_at, edited_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?10)
         ON CONFLICT(transcript_id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            sections = excluded.sections,
            scriptures = excluded.scriptures,
            ai_generated = excluded.ai_generated,
            disclosure = excluded.disclosure,
            provider = excluded.provider,
            model = excluded.model,
            created_at = excluded.created_at,
            edited_at = excluded.edited_at",
        params![
            note.transcript_id,
            note.title,
            note.summary,
            note.sections_json,
            note.scriptures_json,
            note.ai_generated,
            note.disclosure,
            note.provider,
            note.model,
            note.created_at_ms,
        ],
    )?;
    // `last_insert_rowid()` is correct even on the UPDATE branch of an upsert: per
    // SQLite's own docs, an `INSERT ... ON CONFLICT DO UPDATE` that takes the
    // UPDATE path still counts as the "most recent successful INSERT" for this
    // purpose and `last_insert_rowid()` returns the existing row's id, not 0 or a
    // stale value from a prior statement.
    let id = db.conn().last_insert_rowid();
    if id == 0 {
        // Defensive fallback (should be unreachable per the above) — resolve the
        // id by its unique key rather than return a bogus 0.
        return db
            .conn()
            .query_row(
                "SELECT id FROM sermon_note WHERE transcript_id = ?1",
                params![note.transcript_id],
                |r| r.get(0),
            )
            .map_err(Into::into);
    }
    Ok(id)
}

/// Read the draft for a transcript, if one exists (and has not been detached by a
/// non-cascading transcript delete — see the module docs).
pub fn find_by_transcript(db: &Database, transcript_id: i64) -> Result<Option<SermonNoteRecord>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT id, transcript_id, title, summary, sections, scriptures, ai_generated,
                disclosure, provider, model, created_at, edited_at
         FROM sermon_note WHERE transcript_id = ?1",
    )?;
    let mut rows = stmt.query_map(params![transcript_id], row_to_record)?;
    match rows.next() {
        Some(row) => Ok(Some(row?)),
        None => Ok(None),
    }
}

fn row_to_record(r: &rusqlite::Row<'_>) -> rusqlite::Result<SermonNoteRecord> {
    Ok(SermonNoteRecord {
        id: r.get(0)?,
        transcript_id: r.get(1)?,
        title: r.get(2)?,
        summary: r.get(3)?,
        sections_json: r.get(4)?,
        scriptures_json: r.get(5)?,
        ai_generated: r.get(6)?,
        disclosure: r.get(7)?,
        provider: r.get(8)?,
        model: r.get(9)?,
        created_at_ms: r.get(10)?,
        edited_at_ms: r.get(11)?,
    })
}

/// Apply an operator edit to an existing draft's text. Touches ONLY `title`,
/// `summary`, `sections`, `scriptures`, and `edited_at` — `ai_generated`,
/// `disclosure`, `provider`, `model`, and `created_at` are structurally
/// unreachable from this function (see [`DraftEdit`]), so an edit can never
/// silently drop the FR-123 label or FR-128 disclosure. `NotFound` if no draft
/// exists for `transcript_id` (edit a draft into existence is not supported —
/// generate one first via [`create`]).
///
/// Rejects an oversized field with [`DataError::TooLarge`] before writing
/// anything (storage stays bounded even under a hostile or malformed edit).
/// Well-formedness of `sections_json`/`scriptures_json` is the caller's
/// responsibility — this crate has no JSON parser (see the module docs); the
/// wired caller (`selahcue-operator`) validates with `serde_json::from_str`
/// before ever calling this function.
pub fn update(
    db: &Database,
    transcript_id: i64,
    edit: &DraftEdit,
    edited_at_ms: i64,
) -> Result<()> {
    check_bounds(
        &edit.title,
        edit.summary.as_deref(),
        &edit.sections_json,
        &edit.scriptures_json,
    )?;
    let n = db.conn().execute(
        "UPDATE sermon_note
         SET title = ?2, summary = ?3, sections = ?4, scriptures = ?5, edited_at = ?6
         WHERE transcript_id = ?1",
        params![
            transcript_id,
            edit.title,
            edit.summary,
            edit.sections_json,
            edit.scriptures_json,
            edited_at_ms,
        ],
    )?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}

/// Delete the draft for a transcript, if any. `Ok(())` whether or not a row
/// existed (idempotent) — used by `transcript_repo::delete`/`purge_expired` when
/// cascade is enabled; a caller that needs to know whether a row was actually
/// removed can check [`find_by_transcript`] first.
pub fn delete_for_transcript(db: &Database, transcript_id: i64) -> Result<()> {
    db.conn().execute(
        "DELETE FROM sermon_note WHERE transcript_id = ?1",
        params![transcript_id],
    )?;
    Ok(())
}
