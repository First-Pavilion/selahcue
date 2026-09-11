//! Repository for transcript + detection persistence (86ajtxzrn; FR-130/153/154/137/082).
//!
//! A transcript = one listening session (one start-to-stop of the STT engine,
//! ADR-0010/0019), provider-agnostic. Its segments are the "raw immutable stream" —
//! unlike [`selahcue_core::transcript::TranscriptLog`]'s in-memory ring, nothing here
//! caps segment count or text length (that is this module's whole reason to exist: a
//! transcript survives the process and the ring's drop-oldest eviction). Corrections
//! are a separate, explicitly-editable layer that never overwrites the raw segment
//! text. Detections mirror [`selahcue_core::detection::DetectedReference`], tied to a
//! transcript and, where known, the segment that produced them.
//!
//! Deleting a transcript is one statement: FK `ON DELETE CASCADE` (enabled globally in
//! `Database::init`) removes its segments, corrections, and detections together in the
//! same transaction as the parent row — FR-153's "reliable deletion incl. derived
//! artifacts", for everything this ticket's schema owns. Retention is a
//! `transcript_setting` row, not a hardcoded constant (FR-153/FR-137): see
//! [`RetentionSettings`].
//!
//! No function in this module formats segment/detection/correction **text** (the raw
//! speech, its correction, or a detected reference) into a diagnostic — every error
//! path over that content carries only ids, counts, or a fixed literal (FR-082). The
//! one deliberate exception is [`load_retention_settings`], which echoes a malformed
//! `transcript_setting` *value* into `DataError::Corrupt` (PR #30 review, Sana F5/F4):
//! that string is an operator-set configuration value (e.g. a bad `retention_days`),
//! never speech, and surfacing it is the point — a privacy control that fails silently
//! on bad input is worse than one that names it. `tests/test_transcript_repo.rs`
//! verifies the no-speech-in-diagnostics half holds at runtime (every `DataError`
//! reachable from this module that touches segment/detection/correction text,
//! formatted, never contains planted marker text — checked against partial/truncated
//! leaks, not just an exact match, PR #30 review, Sana F7) with a positive control
//! proving the marker really was persisted, plus a static source scan mirroring
//! `selahcue-licensing`'s "never handed to a formatter" guard — see that scan's own
//! comment for exactly which tokens it forbids and why `format!` itself is still
//! allowed.
//!
//! The aggregate types below (`NewTranscript`, `TranscriptSummary`,
//! `SegmentCorrection`, `TranscriptDetail`) derive `Debug` even though they carry raw
//! text (PR #30 review, Sana F4). That is not itself an FR-082 exposure: the guarantee
//! above is about what this module's own functions *format into an error*, and none of
//! them ever formats a value of these types wholesale — only individual id/count
//! fields, which is what the static scan and the runtime test both check. `Debug` on
//! these structs is reachable today only from a test's own assertion-failure message
//! (this crate's tests, printed to `cargo test`'s own output, never a production log or
//! diagnostic) or a future caller's own debugging code. If a future caller (e.g.
//! 86akcfftu, the live write path) ever logs or reports one of these values wholesale,
//! that call site — not this derive — is what would need a redacting `Debug` or to log
//! selected fields only; nothing here forecloses that.

use crate::{DataError, Database, Result};
use rusqlite::params;
use selahcue_core::detection::DetectedReference;
use selahcue_core::transcript::TranscriptSegment;

/// A new transcript to open (the STT engine just started listening).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NewTranscript {
    /// Display label — the active plan's name + start timestamp, or just the
    /// timestamp when no plan was active. The caller resolves this string; the repo
    /// stores whatever it is given and never invents one, so a later rename
    /// (FR-130/R5, out of this ticket's scope) is a plain `UPDATE` against a column
    /// that already exists.
    pub label: String,
    /// The producing `TranscriptProvider::label()` (e.g. `"manual"`, `"whisper"`,
    /// `"deepgram"`) — free text, not an enum, so a new provider needs no migration.
    pub provider: String,
    /// The `service_plan` row active when listening started, if any.
    pub plan_id: Option<i64>,
    /// Listening start, caller-supplied epoch milliseconds — this crate reads no
    /// clock itself, matching `media_asset.imported_at`'s convention.
    pub started_at_ms: i64,
}

/// A lightweight transcript listing row: label, provider, timing, and segment count —
/// enough to render a list without a second read per row (86ajtxzrn acceptance
/// criterion).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranscriptSummary {
    pub id: i64,
    pub label: String,
    pub provider: String,
    pub plan_id: Option<i64>,
    pub started_at_ms: i64,
    pub ended_at_ms: Option<i64>,
    pub segment_count: i64,
}

/// One segment's correction (the "editable correction layer"). The raw segment text in
/// `transcript_segment` is never modified — a correction is a separate row a future
/// viewer overlays on it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SegmentCorrection {
    pub segment_id: i64,
    pub corrected_text: String,
    pub corrected_at_ms: i64,
}

/// A transcript read back in full: identity, the raw immutable segments (in original
/// order), any corrections, and any detections.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranscriptDetail {
    pub id: i64,
    pub label: String,
    pub provider: String,
    pub plan_id: Option<i64>,
    pub started_at_ms: i64,
    pub ended_at_ms: Option<i64>,
    pub segments: Vec<TranscriptSegment>,
    pub corrections: Vec<SegmentCorrection>,
    pub detections: Vec<DetectedReference>,
}

/// Configurable retention + deletion-cascade policy (FR-153/FR-137). Persisted as a
/// flat key/value set (`transcript_setting`, mirroring `providers_setting`) rather
/// than typed columns, so a further open question resolves to a new key, never a new
/// migration.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RetentionSettings {
    /// Days after which a transcript becomes eligible for automatic deletion via
    /// [`purge_expired`]. `None` = kept indefinitely — FR-153's current provisional
    /// default; this ticket does not change it (see 86ajtxzrn's open questions).
    pub retention_days: Option<u32>,
    /// Whether deleting a transcript should also delete the sermon-note draft
    /// generated from it. Enforced by [`delete`] and [`purge_expired`], which
    /// explicitly remove the matching `sermon_note` row (via
    /// `sermon_note_repo::delete_for_transcript`) inside the same transaction as the
    /// transcript delete, BEFORE it happens, whenever this is `true` — the schema's
    /// own `sermon_note.transcript_id ON DELETE SET NULL` is only the fallback floor
    /// for `false` (detach, don't delete).
    ///
    /// **Default is `true` (cascade) as of 86akgqdv0** — this is a PROPOSAL this
    /// ticket implements against, not a settled product decision, and it reverses
    /// 86ajtxzrn's placeholder `false`. Rationale: an AI-generated artifact derived
    /// from congregation speech shouldn't outlive the source once someone has asked
    /// for that speech to be deleted. Flagged explicitly in 86akgqdv0's PR/ClickUp
    /// comment as needing the product owner's explicit sign-off before merge — the
    /// same pattern 86ajtxzrn used for its own open questions (this field included,
    /// at the time it was only inert scaffolding). The seam stays fully live either
    /// way: an explicit `save_retention_settings` call with `delete_cascade_to_notes:
    /// false` restores the non-destructive behaviour with no migration required.
    pub delete_cascade_to_notes: bool,
}

impl Default for RetentionSettings {
    fn default() -> Self {
        RetentionSettings {
            retention_days: None,
            delete_cascade_to_notes: true,
        }
    }
}

const KEY_RETENTION_DAYS: &str = "retention_days";
const KEY_DELETE_CASCADE_TO_NOTES: &str = "delete_cascade_to_notes";

/// Open a new transcript. Returns its row id.
pub fn create(db: &Database, t: &NewTranscript) -> Result<i64> {
    db.conn().execute(
        "INSERT INTO transcript (plan_id, label, provider, started_at, ended_at)
         VALUES (?1, ?2, ?3, ?4, NULL)",
        params![t.plan_id, t.label, t.provider, t.started_at_ms],
    )?;
    Ok(db.conn().last_insert_rowid())
}

/// Mark a transcript's listening session as stopped (caller-supplied epoch ms).
/// `NotFound` if no such transcript.
pub fn end(db: &Database, transcript_id: i64, ended_at_ms: i64) -> Result<()> {
    let n = db.conn().execute(
        "UPDATE transcript SET ended_at = ?2 WHERE id = ?1",
        params![transcript_id, ended_at_ms],
    )?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}

/// Append one immutable segment to a transcript's raw stream; returns its row id.
///
/// Unbounded: unlike [`selahcue_core::transcript::TranscriptLog`], neither the
/// segment's text length nor the transcript's segment count is capped here — that
/// is 86ajtxzrn's acceptance criterion, not an oversight. `ord` is assigned from a
/// high-water mark (`COALESCE(MAX(ord), -1) + 1`), inside the same transaction as the
/// insert, so segments always read back in append order regardless of whatever id the
/// live in-memory engine assigned them. This must be a high-water mark, not a row
/// count: a row count under-counts as soon as any segment is removed from the middle
/// of the sequence (nothing in this ticket's API does that today, but the schema
/// permits arbitrary row deletion), and it would then collide with an existing `ord`
/// and fail `UNIQUE (transcript_id, ord)` on the very next append (PR #30 review,
/// Sana S1). `MAX` on the indexed `(transcript_id, ord)` column is also one B-tree
/// seek instead of a full per-transcript count, which matters here because this is
/// the one call the live writer (86akcfftu) will make on every single segment of
/// every service (measured: ~2.4µs vs ~190µs at n=20,000 — Vera F2).
pub fn append_segment(
    db: &Database,
    transcript_id: i64,
    start_ms: u64,
    end_ms: u64,
    text: &str,
) -> Result<i64> {
    let tx = db.conn().unchecked_transaction()?;
    let ord: i64 = tx.query_row(
        "SELECT COALESCE(MAX(ord), -1) + 1 FROM transcript_segment WHERE transcript_id = ?1",
        params![transcript_id],
        |r| r.get(0),
    )?;
    tx.execute(
        "INSERT INTO transcript_segment (transcript_id, ord, start_ms, end_ms, text)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        params![transcript_id, ord, start_ms as i64, end_ms as i64, text],
    )?;
    let id = tx.last_insert_rowid();
    tx.commit()?;
    Ok(id)
}

/// Upsert the correction for one segment (the "editable correction layer"); a second
/// call for the same segment replaces the first (latest wins, the same shape as
/// `session_state`'s singleton upsert) — the raw segment itself is never touched.
pub fn correct_segment(
    db: &Database,
    segment_id: i64,
    corrected_text: &str,
    corrected_at_ms: i64,
) -> Result<()> {
    db.conn().execute(
        "INSERT INTO transcript_correction (segment_id, corrected_text, corrected_at)
         VALUES (?1, ?2, ?3)
         ON CONFLICT(segment_id) DO UPDATE SET
            corrected_text = ?2, corrected_at = ?3",
        params![segment_id, corrected_text, corrected_at_ms],
    )?;
    Ok(())
}

/// Persist one detection tied to a transcript (and, where known, the segment that
/// produced it). Returns its row id.
pub fn append_detection(
    db: &Database,
    transcript_id: i64,
    segment_id: Option<i64>,
    reference: &str,
    confidence: u8,
) -> Result<i64> {
    db.conn().execute(
        "INSERT INTO detection (transcript_id, segment_id, reference, confidence)
         VALUES (?1, ?2, ?3, ?4)",
        params![transcript_id, segment_id, reference, confidence as i64],
    )?;
    Ok(db.conn().last_insert_rowid())
}

/// List transcripts, most recently started first — enough per row (label, provider,
/// timing, segment count) to render a list UI without a second read per row.
///
/// The "no second read" guarantee is structural, in the SQL below: `segment_count` is
/// a correlated subquery inside the single `SELECT`, not a per-row follow-up query
/// issued from Rust (`EXPLAIN QUERY PLAN` shows one statement, no N+1) — verified by
/// hand during the PR #30 review (Vera F4). This is *not* a property a public-API test
/// can pin directly: a real statement-count guard needs `Connection::trace`, which
/// needs `&mut Connection`, and [`Database::conn`] hands out `&Connection`. The test
/// `listing_returns_label_provider_timing_and_segment_count` therefore checks only the
/// returned values, which an N+1 rewrite would return identically — that test does not
/// (and structurally cannot, through this crate's public API) guard "one statement";
/// this comment is where that invariant actually lives.
pub fn list(db: &Database) -> Result<Vec<TranscriptSummary>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT t.id, t.label, t.provider, t.plan_id, t.started_at, t.ended_at,
                (SELECT COUNT(*) FROM transcript_segment s WHERE s.transcript_id = t.id)
         FROM transcript t
         ORDER BY t.started_at DESC, t.id DESC",
    )?;
    let rows = stmt.query_map([], |r| {
        Ok(TranscriptSummary {
            id: r.get(0)?,
            label: r.get(1)?,
            provider: r.get(2)?,
            plan_id: r.get(3)?,
            started_at_ms: r.get(4)?,
            ended_at_ms: r.get(5)?,
            segment_count: r.get(6)?,
        })
    })?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}

/// Read one transcript back in full: identity, raw segments in original order,
/// corrections, and detections. `NotFound` if no such transcript.
pub fn load(db: &Database, transcript_id: i64) -> Result<TranscriptDetail> {
    let conn = db.conn();
    let (label, provider, plan_id, started_at_ms, ended_at_ms): (
        String,
        String,
        Option<i64>,
        i64,
        Option<i64>,
    ) = conn
        .query_row(
            "SELECT label, provider, plan_id, started_at, ended_at
             FROM transcript WHERE id = ?1",
            params![transcript_id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)),
        )
        .map_err(|e| match e {
            rusqlite::Error::QueryReturnedNoRows => DataError::NotFound,
            other => DataError::from(other),
        })?;

    let mut seg_stmt = conn.prepare(
        "SELECT id, start_ms, end_ms, text FROM transcript_segment
         WHERE transcript_id = ?1 ORDER BY ord",
    )?;
    let seg_rows = seg_stmt.query_map(params![transcript_id], |r| {
        let id: i64 = r.get(0)?;
        let start_ms: i64 = r.get(1)?;
        let end_ms: i64 = r.get(2)?;
        let text: String = r.get(3)?;
        Ok((id, start_ms, end_ms, text))
    })?;
    let mut segments = Vec::new();
    for row in seg_rows {
        let (id, start_ms, end_ms, text) = row?;
        let id = u64::try_from(id)
            .map_err(|_| DataError::Corrupt(format!("negative transcript_segment id {id}")))?;
        segments.push(TranscriptSegment {
            id,
            start_ms: start_ms as u64,
            end_ms: end_ms as u64,
            text,
        });
    }
    drop(seg_stmt);

    let mut corr_stmt = conn.prepare(
        "SELECT c.segment_id, c.corrected_text, c.corrected_at
         FROM transcript_correction c
         JOIN transcript_segment s ON s.id = c.segment_id
         WHERE s.transcript_id = ?1
         ORDER BY s.ord",
    )?;
    let corr_rows = corr_stmt.query_map(params![transcript_id], |r| {
        Ok(SegmentCorrection {
            segment_id: r.get(0)?,
            corrected_text: r.get(1)?,
            corrected_at_ms: r.get(2)?,
        })
    })?;
    let corrections = corr_rows.collect::<std::result::Result<Vec<_>, _>>()?;
    drop(corr_stmt);

    let mut det_stmt = conn.prepare(
        "SELECT id, segment_id, reference, confidence FROM detection
         WHERE transcript_id = ?1 ORDER BY id",
    )?;
    let det_rows = det_stmt.query_map(params![transcript_id], |r| {
        let id: i64 = r.get(0)?;
        let segment_id: Option<i64> = r.get(1)?;
        let reference: String = r.get(2)?;
        let confidence: i64 = r.get(3)?;
        Ok((id, segment_id, reference, confidence))
    })?;
    let mut detections = Vec::new();
    for row in det_rows {
        let (id, segment_id, reference, confidence) = row?;
        let id = u64::try_from(id)
            .map_err(|_| DataError::Corrupt(format!("negative detection id {id}")))?;
        // `detection.segment_id` is nullable by design (a detection can exist with no
        // known source segment), but `DetectedReference::source_segment` is a mandatory
        // `u64` with no "unknown" representation — changing that is out of this ticket's
        // `selahcue-data`-only file footprint (it is a `selahcue-core` domain type used
        // elsewhere, e.g. the live detection queue). `0` is a deliberate, documented
        // sentinel for "no known segment" here, not a real segment id: `transcript_
        // segment.id` is an `INTEGER PRIMARY KEY` rowid alias, which SQLite allocates
        // starting at 1, so a genuine segment `0` cannot exist via this insert path
        // (PR #30 review, Cody #2 / Quinn ADVISORY-1). `segment_id_is_none_reads_back_
        // as_the_documented_zero_sentinel` in `tests/test_transcript_repo.rs` pins this
        // on purpose so it cannot silently drift.
        let source_segment = u64::try_from(segment_id.unwrap_or(0)).map_err(|_| {
            DataError::Corrupt(format!("negative detection segment_id {segment_id:?}"))
        })?;
        let confidence = u8::try_from(confidence).map_err(|_| {
            DataError::Corrupt(format!("detection confidence {confidence} out of range"))
        })?;
        detections.push(DetectedReference {
            id,
            reference,
            source_segment,
            confidence,
        });
    }

    Ok(TranscriptDetail {
        id: transcript_id,
        label,
        provider,
        plan_id,
        started_at_ms,
        ended_at_ms,
        segments,
        corrections,
        detections,
    })
}

/// Delete a transcript and everything derived from it — segments, corrections, and
/// detections — together, in one statement (FK `ON DELETE CASCADE`, FR-153).
/// `NotFound` if no such transcript.
///
/// Whether this also deletes the transcript's generated sermon-note draft (added by
/// 86akgqdv0) is read from [`RetentionSettings::delete_cascade_to_notes`]: when
/// `true` (the current PROPOSED default — see that field's doc comment), the
/// `sermon_note` row is deleted explicitly, inside the same transaction as the
/// transcript delete and BEFORE it, so the schema's own `ON DELETE SET NULL` floor
/// (detach, don't delete) never gets a chance to apply. When `false`, nothing extra
/// happens here and that floor is exactly what fires: the note survives with
/// `transcript_id = NULL`.
///
/// The `DELETE FROM sermon_note` below is deliberately inline raw SQL rather than a
/// call into `sermon_note_repo` — that module's functions take `&Database` (they
/// open their own implicit transaction per call), and this cascade must run inside
/// the SAME transaction as the transcript delete, which a `&Database`-shaped API
/// cannot participate in. `sermon_note_repo::delete_for_transcript` remains the
/// canonical row-level API for every other caller.
pub fn delete(db: &Database, transcript_id: i64) -> Result<()> {
    let settings = load_retention_settings(db)?;
    let tx = db.conn().unchecked_transaction()?;
    if settings.delete_cascade_to_notes {
        tx.execute(
            "DELETE FROM sermon_note WHERE transcript_id = ?1",
            params![transcript_id],
        )?;
    }
    let n = tx.execute(
        "DELETE FROM transcript WHERE id = ?1",
        params![transcript_id],
    )?;
    if n == 0 {
        // Dropping `tx` without committing rolls back (rusqlite's `Drop` impl) — the
        // cascade delete above, if it ran, is undone too, so "no such transcript" is
        // still a true no-op even when cascade is on.
        return Err(DataError::NotFound);
    }
    tx.commit()?;
    // Best-effort: try to keep the just-deleted text from lingering in the `-wal`
    // sidecar (FR-153; PR #30 review, Sana F6). Bounded to near-zero wait via a
    // scoped `busy_timeout = 0` (PR #30 review, Vera F5) — it cannot meaningfully
    // block this call or any other connection's write, but under contention it may
    // skip the truncate entirely; see `Database::try_checkpoint_truncate`'s doc
    // comment for the full trade-off and why that is still an acceptable, self-
    // healing degradation rather than a failure.
    db.try_checkpoint_truncate();
    Ok(())
}

/// Load the retention/deletion-cascade settings. An empty store yields the safe
/// placeholder defaults (kept indefinitely; notes not cascade-deleted) — never an
/// error, mirroring `providers_repo::load`'s empty-store fallback.
///
/// A *present but malformed* `retention_days` value is different from an absent one,
/// and is reported as [`DataError::Corrupt`] rather than silently falling back to
/// "kept indefinitely" (PR #30 review, Sana F5/T4): `retention_days` is a privacy
/// control (FR-153), and silently discarding a value nobody could parse would fail
/// *open* — the one setting on this whole table where the safe direction is to refuse
/// and surface the problem, not to quietly grant the least protection.
pub fn load_retention_settings(db: &Database) -> Result<RetentionSettings> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT key, value FROM transcript_setting")?;
    let rows = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))?;
    let mut settings = RetentionSettings::default();
    for row in rows {
        let (key, value) = row?;
        match key.as_str() {
            KEY_RETENTION_DAYS => {
                settings.retention_days = Some(value.parse::<u32>().map_err(|_| {
                    DataError::Corrupt(format!(
                        "transcript_setting {KEY_RETENTION_DAYS} value {value:?} is not a valid u32"
                    ))
                })?);
            }
            KEY_DELETE_CASCADE_TO_NOTES => settings.delete_cascade_to_notes = value == "true",
            // Forward-compatible: an unknown key written by a newer build is ignored,
            // not fatal (the same spirit as `media_repo::load_all` dropping an
            // unrecognised `kind` tag rather than failing the whole load).
            _ => {}
        }
    }
    Ok(settings)
}

/// Persist the retention/deletion-cascade settings, replacing the stored set in one
/// transaction — the same replace-the-whole-set shape as `providers_repo::save`.
///
/// FR-137 "Administrator-gated": enforcing WHO may call this is a command/RBAC-layer
/// concern, per the existing precedent for provider consent (`selahcue-core::providers`
/// — "Administrator-gated at the command layer" — and `selahcue-lan::rbac::authorize`).
/// This function only makes the setting exist outside a hardcoded constant, which is
/// this ticket's acceptance criterion; it does not itself check any role.
pub fn save_retention_settings(db: &Database, settings: &RetentionSettings) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM transcript_setting", [])?;
    if let Some(days) = settings.retention_days {
        tx.execute(
            "INSERT INTO transcript_setting (key, value) VALUES (?1, ?2)",
            params![KEY_RETENTION_DAYS, days.to_string()],
        )?;
    }
    tx.execute(
        "INSERT INTO transcript_setting (key, value) VALUES (?1, ?2)",
        params![
            KEY_DELETE_CASCADE_TO_NOTES,
            if settings.delete_cascade_to_notes {
                "true"
            } else {
                "false"
            }
        ],
    )?;
    tx.commit()?;
    Ok(())
}

/// A never-`end()`ed transcript is only ever treated as abandoned (see [`purge_expired`])
/// once it has been running at least this long — long enough that no real service is
/// still recording. This is a floor, not a target: it exists so a short or zero-day
/// `retention_days` setting can never purge a genuinely live, still-recording session
/// out from under it (86ajtxzrn Sana F2 / this ticket's own FR-075 crash-path note).
const ORPHAN_GRACE_MS: i64 = 86_400_000; // 24h

/// Delete every transcript whose retention window has elapsed as of `now_ms`.
///
/// A normally-ended transcript expires `retention_days` days after `ended_at`. A
/// transcript that was never `end()`ed — a crash mid-service, which FR-075 treats as
/// routine, not exceptional — used to be exempt from retention *forever*, regardless
/// of how old it was (86ajtxzrn open question #1 / Sana F2): retention only ever
/// looked at `ended_at`, and an orphan has none. That is fixed here by treating
/// `started_at` as the effective end for a never-ended transcript, but only once it
/// has been running longer than [`ORPHAN_GRACE_MS`] — a transcript that started
/// recently and simply hasn't stopped yet (a real, in-progress multi-hour service)
/// must never be purged regardless of the configured window; one that started days or
/// weeks ago and never stopped is, past the grace period, indistinguishable from an
/// abandoned crash artifact and is evaluated against the same retention window using
/// `started_at`. Cascades to segments/corrections/detections exactly like [`delete`].
/// A `None` `retention_days` (the default) purges nothing at all, orphans included —
/// retention stays opt-in until the FR-153 default is finalized. Returns the deleted
/// ids.
pub fn purge_expired(db: &Database, now_ms: i64) -> Result<Vec<i64>> {
    let settings = load_retention_settings(db)?;
    let Some(days) = settings.retention_days else {
        return Ok(Vec::new());
    };
    let window_ms = i64::from(days) * 86_400_000;
    let cutoff = now_ms - window_ms;
    // An orphan (`ended_at IS NULL`) is eligible only once it clears BOTH floors: the
    // grace period (it can no longer plausibly be a live session) AND the configured
    // retention window measured from its `started_at`.
    let orphan_cutoff = cutoff.min(now_ms - ORPHAN_GRACE_MS);

    let tx = db.conn().unchecked_transaction()?;
    let mut stmt = tx.prepare(
        "SELECT id FROM transcript
         WHERE (ended_at IS NOT NULL AND ended_at <= ?1)
            OR (ended_at IS NULL AND started_at <= ?2)",
    )?;
    let ids: Vec<i64> = stmt
        .query_map(params![cutoff, orphan_cutoff], |r| r.get(0))?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    drop(stmt);
    for id in &ids {
        // Same cascade decision as `delete` — see its doc comment. Deleting the note
        // first, in the same transaction, means an interrupted purge cannot leave a
        // transcript gone with its note still pointing at a live cascade-eligible id.
        if settings.delete_cascade_to_notes {
            tx.execute(
                "DELETE FROM sermon_note WHERE transcript_id = ?1",
                params![id],
            )?;
        }
        tx.execute("DELETE FROM transcript WHERE id = ?1", params![id])?;
    }
    tx.commit()?;
    if !ids.is_empty() {
        // Same best-effort WAL truncate as `delete` (FR-153; Sana F6) — only worth
        // attempting when something was actually removed.
        db.try_checkpoint_truncate();
    }
    Ok(ids)
}
