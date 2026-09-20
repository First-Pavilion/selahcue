//! Repository for generated sermon-note draft persistence (86akgqdv0; FR-123
//! "editable" half — generation, labelling, and the untouched-transcript invariant
//! shipped already in 86akby7d8).
//!
//! One editable draft per transcript (`transcript_id` is `UNIQUE`). [`create`]
//! upserts: a second call for a transcript that already has a draft REPLACES it
//! wholesale, including `created_at`. This is intentional and UNCHANGED by FR-129 —
//! [`create`] is what runs for a true first-time generate (no draft exists yet); see
//! the migration comment (v20 -> v21, `migrations.rs`).
//!
//! **Regenerate-with-retention (FR-129, 86akgqdx8)** sits ABOVE [`create`], as three
//! new functions operating on the SAME row's additive `pending_*` columns (migration
//! v21 -> v22): [`stage_regeneration`] writes a freshly generated draft into the
//! `pending_*` slot WITHOUT touching the currently-accepted columns at all (so the
//! prior draft is retrievable, byte-for-byte, via [`find_by_transcript`] the entire
//! time a regeneration is pending); [`confirm_regeneration`] moves `pending_*` onto
//! the accepted columns and clears `pending_*`; [`discard_regeneration`] clears
//! `pending_*` and leaves the accepted columns alone. The decided retention model —
//! single prior version, explicit-confirm-before-replace — is documented on each of
//! the three functions and in this ticket's Goal Contract / MR description.
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
/// Upper bound on the serialized `sections` JSON, in bytes. A multi-point outline with
/// sub-points realistically runs 3-10 KB (PR #33 review, Vera's own measurements); this
/// leaves generous headroom above that while staying well under what the LAN control link
/// can actually carry — see the note below.
///
/// **Reconciled with `selahcue_lan::MAX_MESSAGE_BYTES` (86akgqdv0 PR #33 review, Vera F5 /
/// Sana N1 — High), deliberately shrunk from an earlier `200_000`.** The old value was a
/// pure storage-side "stop an unbounded string" number that never considered the fact that
/// every persisted draft now travels over the LAN control link (`SaveSermonNoteDraft`/
/// `UpdateSermonNoteDraft`) inside a JSON `Request` envelope whose OWN transport caps the
/// whole frame at 64 KiB (`selahcue-lan/src/server.rs`'s `MAX_MESSAGE_BYTES`) — and a string
/// embedded inside a JSON string is escaped, so its wire cost can be UP TO 6x its raw byte
/// length (a raw control character becomes a 6-byte `\u00XX` escape; SQLite/this crate place
/// no format constraint on the content, only a byte-length one). At the old cap, a draft
/// need not even be adversarial to hang the operator's control link — Vera reproduced a
/// dropped connection from an ordinary `sections_json` around 63 KiB alone, before summary/
/// title/scriptures/disclosure/provider/model are even added in.
///
/// This crate has no channel to `selahcue-lan`'s cap (a lower layer must not depend on a
/// higher one), so the two are reconciled BY HAND and must be re-checked together if either
/// changes: with every field below at ITS OWN maximum, using the worst-case per-field
/// encoding (the widest of "all 4-byte UTF-8" and "all `\u00XX`-escaped control characters"),
/// the full `SaveSermonNoteDraft` `Request` envelope is ~60,060 bytes — about 5.4 KB (8%)
/// under the 64 KiB transport cap even in that worst case (verified by hand, worked example
/// in the PR description; `selahcue-app`'s `test_sermon_note_remote.rs` proves it against
/// the REAL wire, not just this arithmetic). This is the PRIMARY fix (data caps that fit);
/// `selahcue_app::RemoteOperator`'s pre-send guard (measuring the actual serialized frame
/// against `selahcue_lan::MAX_MESSAGE_BYTES` before sending) is the BACKSTOP for any content
/// that still manages to exceed it — e.g. a hostile LAN peer packing every byte of a field
/// with control characters, which can still blow past this budget's realistic-escaping
/// assumption. Neither alone is "the fix"; see the PR description's "LAN-cap fix direction"
/// section for the full reasoning on why both exist.
///
/// **Scope of the ~60,060 B reconciliation above (FR-129, 86akgqdx8 review — Vera F1):** it
/// covers exactly ONE draft travelling inside a `SaveSermonNoteDraft`/`UpdateSermonNoteDraft`
/// `Request` — the direction the pre-send guard (`RemoteOperator::would_exceed_wire_cap`) and
/// the server's `max_message_size`/`max_frame_size` (read side, `selahcue-lan/src/server.rs`)
/// actually enforce. It does NOT cover `ServerMessage::SermonNoteRegenerationState`, which
/// carries TWO drafts (`current` + `pending`) in one REPLY: measured against the real wire
/// (`selahcue-app`'s `a_two_draft_regeneration_state_reply_is_measured_against_the_wire_cap_
/// both_ways`), every field at its declared maximum with ordinary Latin-script content is
/// ~48.8 KB (fits, 74% of the cap), but the SAME maxima with ordinary NON-Latin content (any
/// 3-byte-UTF-8 script — `MAX_TITLE_CHARS`/`MAX_SUMMARY_CHARS` are CHARACTER bounds, so this
/// content triples their byte footprint) is ~71.6 KB — OVER the 64 KiB cap. This is not a live
/// defect: unlike the request direction, nothing on the REPLY path enforces any cap today
/// (tungstenite's write path performs no size check; `selahcue-lan/src/client.rs`'s
/// `client_async` call takes no `WebSocketConfig`, so it defaults to a large reader) — the
/// connection does not drop, it just silently carries a frame this reconciliation never sized
/// for. `OperatorStateView.transcript` was already unbounded on this same reply path before
/// FR-129; this ticket does not introduce the read/write asymmetry, only a second instance of
/// relying on it. Adding real enforcement to the reply direction (a `WebSocketConfig` on the
/// client, symmetric with the server's) is a follow-up, not fixed here — see 86akgwbq2.
pub const MAX_SECTIONS_JSON_BYTES: usize = 15_000;
/// Upper bound on the serialized `scriptures` JSON, in bytes. See
/// [`MAX_SECTIONS_JSON_BYTES`]'s doc for why this shrank from `20_000` — same reconciliation,
/// same combined worst-case budget.
pub const MAX_SCRIPTURES_JSON_BYTES: usize = 3_500;
/// Upper bound on the serving provider's label, in characters (PR #33 review, Sana N3 —
/// Low: previously unbounded — a 30,000-character `provider` was accepted and stored).
/// Generous for a human-readable label (`"SelahCue AI"`, `"Local (offline)"`) while keeping
/// this field out of the same unbounded-growth class `check_bounds` already closes for
/// title/summary/sections/scriptures.
pub const MAX_PROVIDER_CHARS: usize = 200;
/// Upper bound on the FR-128 fabrication disclosure, in characters (PR #33 review, Sana N3
/// — Low: previously unbounded — a 20,000-character `disclosure` was accepted and stored).
/// [`selahcue_core::providers::FABRICATION_DISCLOSURE`] is a fixed ~260-character template;
/// this leaves nearly 4x headroom for a future, longer disclosure without reopening the
/// unbounded-growth gap.
pub const MAX_DISCLOSURE_CHARS: usize = 1_000;
/// Upper bound on the provider-reported model identifier, in characters (PR #33 review,
/// Sana N3 — Low: previously unbounded — a 5,000-character `model` was accepted and
/// stored).
pub const MAX_MODEL_CHARS: usize = 200;

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

/// A freshly (re)generated draft awaiting operator confirmation, to [`stage_regeneration`]
/// against a transcript that already has an accepted draft (FR-129, 86akgqdx8). Field-for-
/// field identical to [`NewSermonNote`] minus `transcript_id` (the caller already has it —
/// it is the key, not payload) — a pending regeneration is exactly "a draft that has not
/// been accepted yet", carrying every field a confirmed one would.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PendingRegeneration {
    pub title: String,
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
    pub ai_generated: bool,
    pub disclosure: Option<String>,
    pub provider: String,
    pub model: Option<String>,
    pub generated_at_ms: i64,
}

/// A pending regeneration read back in full — the `pending_*` half of
/// [`SermonNoteRecord`], present exactly when a regeneration has been [`stage_regeneration`]d
/// and not yet [`confirm_regeneration`]d or [`discard_regeneration`]d.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PendingRegenerationRecord {
    pub title: String,
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
    pub ai_generated: bool,
    pub disclosure: Option<String>,
    pub provider: String,
    pub model: Option<String>,
    pub generated_at_ms: i64,
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
    /// A not-yet-confirmed regeneration awaiting the operator's accept/discard decision
    /// (FR-129, 86akgqdx8). `None` is the common state (no regeneration in flight, or one
    /// was just confirmed/discarded) — never an error.
    pub pending: Option<PendingRegenerationRecord>,
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

/// Reject an oversized `provider`/`disclosure`/`model` before a write. Separate from
/// [`check_bounds`] because these three are set ONLY at [`create`] time — [`DraftEdit`] has
/// no fields for them, so [`update`] never needs to check them (PR #33 review, Sana N3 —
/// Low: these were previously unbounded at the data layer).
fn check_create_only_bounds(
    provider: &str,
    disclosure: Option<&str>,
    model: Option<&str>,
) -> Result<()> {
    if provider.chars().count() > MAX_PROVIDER_CHARS {
        return Err(DataError::TooLarge(format!(
            "sermon_note.provider exceeds {MAX_PROVIDER_CHARS} characters"
        )));
    }
    if let Some(d) = disclosure {
        if d.chars().count() > MAX_DISCLOSURE_CHARS {
            return Err(DataError::TooLarge(format!(
                "sermon_note.disclosure exceeds {MAX_DISCLOSURE_CHARS} characters"
            )));
        }
    }
    if let Some(m) = model {
        if m.chars().count() > MAX_MODEL_CHARS {
            return Err(DataError::TooLarge(format!(
                "sermon_note.model exceeds {MAX_MODEL_CHARS} characters"
            )));
        }
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
///
/// Returns the row's own id — correct on BOTH the INSERT and the UPDATE branch of the
/// upsert, via `RETURNING id` (PR #33 review, Vera F3: `last_insert_rowid()` does
/// **not** advance on the `DO UPDATE` branch of an `INSERT ... ON CONFLICT`, contrary
/// to what an earlier version of this function's doc comment claimed — SQLite leaves
/// it at whatever the connection's last real INSERT was, which on a busy connection
/// can be an unrelated row's id. `RETURNING` reads the actual row back from the
/// statement itself, so there is no fallback branch left to reach or forget).
pub fn create(db: &Database, note: &NewSermonNote) -> Result<i64> {
    check_bounds(
        &note.title,
        note.summary.as_deref(),
        &note.sections_json,
        &note.scriptures_json,
    )?;
    check_create_only_bounds(
        &note.provider,
        note.disclosure.as_deref(),
        note.model.as_deref(),
    )?;
    db.conn()
        .query_row(
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
                edited_at = excluded.edited_at
             RETURNING id",
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
            |r| r.get(0),
        )
        .map_err(Into::into)
}

/// The full column list shared by every `SELECT` that produces a [`SermonNoteRecord`] via
/// [`row_to_record`] — one definition, so [`find_by_transcript`] and [`list_detached`]
/// cannot drift out of the column order [`row_to_record`] expects.
const SELECT_COLUMNS: &str =
    "id, transcript_id, title, summary, sections, scriptures, ai_generated,
        disclosure, provider, model, created_at, edited_at,
        pending_title, pending_summary, pending_sections, pending_scriptures,
        pending_ai_generated, pending_disclosure, pending_provider, pending_model,
        pending_generated_at";

/// Read the draft for a transcript, if one exists (and has not been detached by a
/// non-cascading transcript delete — see the module docs). Carries the `pending`
/// regeneration slot (FR-129, 86akgqdx8) exactly as stored — `Some` only when a
/// regeneration has been staged and not yet confirmed/discarded.
pub fn find_by_transcript(db: &Database, transcript_id: i64) -> Result<Option<SermonNoteRecord>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLUMNS} FROM sermon_note WHERE transcript_id = ?1"
    ))?;
    let mut rows = stmt.query_map(params![transcript_id], row_to_record)?;
    match rows.next() {
        Some(row) => Ok(Some(row?)),
        None => Ok(None),
    }
}

/// `pending_title` is the presence sentinel for a staged-but-unconfirmed regeneration (see
/// the v21 -> v22 migration comment for why): a real draft always has a non-empty
/// `pending_title` when ANY `pending_*` column is set, since [`stage_regeneration`] writes
/// all nine together and [`confirm_regeneration`]/[`discard_regeneration`] clear all nine
/// together. `None` for every OTHER `pending_*` column here is a genuine `unwrap`-free
/// decode failure (a hand-edited or corrupt row), not an expected state — this crate is a
/// dumb store, so it decodes optimistically and never invents placeholder text for a column
/// this module itself always writes as a group; see [`row_to_record`].
fn row_to_record(r: &rusqlite::Row<'_>) -> rusqlite::Result<SermonNoteRecord> {
    let pending_title: Option<String> = r.get(12)?;
    let pending = match pending_title {
        Some(title) => Some(PendingRegenerationRecord {
            title,
            summary: r.get(13)?,
            sections_json: r.get(14)?,
            scriptures_json: r.get(15)?,
            ai_generated: r.get(16)?,
            disclosure: r.get(17)?,
            provider: r.get(18)?,
            model: r.get(19)?,
            generated_at_ms: r.get(20)?,
        }),
        None => None,
    };
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
        pending,
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

/// Read every DETACHED note — `transcript_id IS NULL`, the schema's `ON DELETE SET NULL`
/// floor firing for a transcript deleted with cascade OFF (see the module docs).
///
/// Without this, a detached note is unreachable through every OTHER function in this
/// module: [`find_by_transcript`]/[`update`]/[`delete_for_transcript`] are all keyed on
/// `transcript_id`, which is exactly the column that is now `NULL`. A detached row still
/// carries the sermon's title/summary/outline derived from the deleted speech, so leaving
/// it permanently unlistable is an FR-153 "reliable deletion" gap (PR #33 review, Sana F3)
/// — this is the read half of giving it a path back into view; [`delete_by_id`] is the
/// write half.
pub fn list_detached(db: &Database) -> Result<Vec<SermonNoteRecord>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLUMNS} FROM sermon_note WHERE transcript_id IS NULL"
    ))?;
    let rows = stmt.query_map([], row_to_record)?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}

/// Delete one note row by its own id (idempotent — `Ok(())` whether or not it existed),
/// regardless of whether it is currently attached or detached. The write half of
/// [`list_detached`]'s read half: together they give a detached note (otherwise
/// unreachable — see that function's doc) a real deletion path (PR #33 review, Sana F3).
/// [`transcript_repo::purge_expired`](crate::transcript_repo::purge_expired) calls this to
/// purge detached notes past the retention window, the same way it purges transcripts.
pub fn delete_by_id(db: &Database, id: i64) -> Result<()> {
    db.conn()
        .execute("DELETE FROM sermon_note WHERE id = ?1", params![id])?;
    Ok(())
}

// --- Regenerate-with-retention (FR-129, 86akgqdx8) --------------------------------
//
// Single prior version, explicit-confirm-before-replace (see the module docs and the
// v21 -> v22 migration comment for the full reasoning). All three functions below
// operate on the `pending_*` columns only — none of them ever touches the accepted
// columns except `confirm_regeneration`, which is the ONE place that does, and does so
// by copying `pending_*` onto them, mirroring `create`'s own `VALUES (?10, ?10)` for
// `created_at`/`edited_at`.

/// Stage a freshly (re)generated draft against a transcript that already has an
/// ACCEPTED draft, without touching that accepted draft at all. `NotFound` if no
/// accepted draft exists yet for `transcript_id` — regenerate requires something to
/// regenerate FROM; a true first-time generate goes through [`create`] instead, never
/// this function.
///
/// A second call before the first is confirmed/discarded OVERWRITES the pending slot
/// (single pending slot per transcript; only the ACCEPTED draft is guaranteed
/// retained — an intermediate, never-confirmed regeneration is not).
///
/// Rejects an oversized field with [`DataError::TooLarge`] before writing anything —
/// the SAME bounds as [`create`], since a pending draft is exactly as capable of being
/// oversized as an accepted one and travels the same LAN frame once confirmed.
pub fn stage_regeneration(
    db: &Database,
    transcript_id: i64,
    pending: &PendingRegeneration,
) -> Result<()> {
    check_bounds(
        &pending.title,
        pending.summary.as_deref(),
        &pending.sections_json,
        &pending.scriptures_json,
    )?;
    check_create_only_bounds(
        &pending.provider,
        pending.disclosure.as_deref(),
        pending.model.as_deref(),
    )?;
    let n = db.conn().execute(
        "UPDATE sermon_note
         SET pending_title = ?2, pending_summary = ?3, pending_sections = ?4,
             pending_scriptures = ?5, pending_ai_generated = ?6, pending_disclosure = ?7,
             pending_provider = ?8, pending_model = ?9, pending_generated_at = ?10
         WHERE transcript_id = ?1",
        params![
            transcript_id,
            pending.title,
            pending.summary,
            pending.sections_json,
            pending.scriptures_json,
            pending.ai_generated,
            pending.disclosure,
            pending.provider,
            pending.model,
            pending.generated_at_ms,
        ],
    )?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}

/// Accept the pending regeneration for `transcript_id`: the accepted columns become
/// what `pending_*` held, `created_at`/`edited_at` both become `pending_generated_at`
/// (mirroring a fresh [`create`]'s own `VALUES (?10, ?10)`), and `pending_*` is cleared.
/// The version this replaces is now gone — single prior version, not a history (see the
/// module docs).
///
/// `NotFound` if nothing is currently pending for `transcript_id` (whether because none
/// was ever staged, or a prior confirm/discard already cleared it) — this is a real
/// refusal, not a silent no-op, so a caller cannot mistake "nothing happened" for "your
/// regeneration was accepted".
///
/// `Refused` if accepting would silently strip the FR-123 AI-generated label: once a
/// draft is accepted as AI-generated, it can never be replaced by a NOT-AI-generated
/// one via confirm — "once AI-generated, always AI-generated", the same invariant
/// `selahcue_app::LiveController::apply`'s `SaveSermonNoteDraft` handler already
/// enforces for a direct save (PR #33 review, Sana N2). This is exactly the case a
/// degraded (local-fallback) regenerate produces: the pending draft is still staged and
/// VISIBLE (so the operator sees the degraded outline and its `degraded_notice`), but it
/// cannot be confirmed over an existing AI-generated draft — only discarded. A pending
/// draft that is ITSELF `ai_generated: true`, or one replacing an accepted draft that
/// was never AI-generated in the first place, is unaffected by this guard.
///
/// Returns the record read back after the write — the source of truth, never an echo of
/// the pending input, mirroring [`create`]'s own read-after-write discipline.
pub fn confirm_regeneration(db: &Database, transcript_id: i64) -> Result<SermonNoteRecord> {
    let n = db.conn().execute(
        "UPDATE sermon_note
         SET title = pending_title,
             summary = pending_summary,
             sections = pending_sections,
             scriptures = pending_scriptures,
             ai_generated = pending_ai_generated,
             disclosure = pending_disclosure,
             provider = pending_provider,
             model = pending_model,
             created_at = pending_generated_at,
             edited_at = pending_generated_at,
             pending_title = NULL,
             pending_summary = NULL,
             pending_sections = NULL,
             pending_scriptures = NULL,
             pending_ai_generated = NULL,
             pending_disclosure = NULL,
             pending_provider = NULL,
             pending_model = NULL,
             pending_generated_at = NULL
         WHERE transcript_id = ?1
           AND pending_title IS NOT NULL
           AND NOT (ai_generated != 0 AND pending_ai_generated = 0)",
        params![transcript_id],
    )?;
    if n > 0 {
        return find_by_transcript(db, transcript_id)?.ok_or(DataError::NotFound);
    }
    // Distinguish "nothing pending" from "would downgrade provenance" so the two
    // reach the caller as different, honest refusals — a plain re-read costs nothing
    // extra on an already-refused write.
    match find_by_transcript(db, transcript_id)? {
        Some(record) if record.pending.is_some() => Err(DataError::Refused(
            "confirming this regeneration would remove the AI-generated label from an \
             already AI-generated draft"
                .to_string(),
        )),
        _ => Err(DataError::NotFound),
    }
}

/// Discard the pending regeneration for `transcript_id`, leaving the accepted draft
/// completely unchanged. Idempotent — `Ok(())` whether or not anything was pending
/// (mirrors [`delete_for_transcript`]'s own idempotent convention): a caller discarding
/// a regeneration that was already confirmed/discarded elsewhere (or never staged at
/// all) gets the same honest "nothing is pending now" outcome either way, not an error
/// for a state that is not actually wrong.
pub fn discard_regeneration(db: &Database, transcript_id: i64) -> Result<()> {
    db.conn().execute(
        "UPDATE sermon_note
         SET pending_title = NULL,
             pending_summary = NULL,
             pending_sections = NULL,
             pending_scriptures = NULL,
             pending_ai_generated = NULL,
             pending_disclosure = NULL,
             pending_provider = NULL,
             pending_model = NULL,
             pending_generated_at = NULL
         WHERE transcript_id = ?1",
        params![transcript_id],
    )?;
    Ok(())
}
