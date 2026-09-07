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
//! No function in this module formats segment/detection/correction **text** into a
//! diagnostic — every error path here carries only ids, counts, or a fixed literal
//! (FR-082). `tests/test_transcript_repo.rs` verifies this holds at runtime (every
//! `DataError` reachable from this module, formatted, never contains planted marker
//! text) with a positive control proving the marker really was persisted, plus a
//! static source scan mirroring `selahcue-licensing`'s "never handed to a formatter"
//! guard.

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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct RetentionSettings {
    /// Days after which a transcript becomes eligible for automatic deletion via
    /// [`purge_expired`]. `None` = kept indefinitely — FR-153's current provisional
    /// default; this ticket does not change it (see 86ajtxzrn's open questions).
    pub retention_days: Option<u32>,
    /// Whether deleting a transcript should also delete notes generated from it.
    /// 86akcffy0 (note generation) is not built yet, so this flag is currently inert
    /// — reading it is a no-op until a notes table exists to consult it. Defaults to
    /// `false` (notes outlive their source) as the conservative, non-destructive
    /// placeholder pending the product/legal answer; this is not this ticket's
    /// decision to make final.
    pub delete_cascade_to_notes: bool,
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
/// is 86ajtxzrn's acceptance criterion, not an oversight. `ord` is assigned as the
/// transcript's current segment count (inside the same transaction as the insert),
/// so segments always read back in append order regardless of whatever id the live
/// in-memory engine assigned them.
pub fn append_segment(
    db: &Database,
    transcript_id: i64,
    start_ms: u64,
    end_ms: u64,
    text: &str,
) -> Result<i64> {
    let tx = db.conn().unchecked_transaction()?;
    let ord: i64 = tx.query_row(
        "SELECT COUNT(*) FROM transcript_segment WHERE transcript_id = ?1",
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
/// detections — together, in one statement (FK `ON DELETE CASCADE`, FR-153). Whether
/// this should also delete generated notes is the open deletion-cascade question
/// (86ajtxzrn); there is no notes table yet, so nothing here decides it — the future
/// integration point is [`RetentionSettings::delete_cascade_to_notes`], read by
/// whichever future ticket adds the notes table and its FK. `NotFound` if no such
/// transcript.
pub fn delete(db: &Database, transcript_id: i64) -> Result<()> {
    let n = db.conn().execute(
        "DELETE FROM transcript WHERE id = ?1",
        params![transcript_id],
    )?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}

/// Load the retention/deletion-cascade settings. An empty store yields the safe
/// placeholder defaults (kept indefinitely; notes not cascade-deleted) — never an
/// error, mirroring `providers_repo::load`'s empty-store fallback.
pub fn load_retention_settings(db: &Database) -> Result<RetentionSettings> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT key, value FROM transcript_setting")?;
    let rows = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))?;
    let mut settings = RetentionSettings::default();
    for row in rows {
        let (key, value) = row?;
        match key.as_str() {
            KEY_RETENTION_DAYS => settings.retention_days = value.parse::<u32>().ok(),
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

/// Delete every transcript whose retention window has elapsed as of `now_ms`
/// (`ended_at + retention_days` days, in epoch milliseconds) — a transcript still
/// being recorded (`ended_at IS NULL`) is never purged. Cascades to
/// segments/corrections/detections exactly like [`delete`]. A `None` `retention_days`
/// (the default) purges nothing — retention stays opt-in until the FR-153 default is
/// finalized. Returns the deleted ids.
pub fn purge_expired(db: &Database, now_ms: i64) -> Result<Vec<i64>> {
    let settings = load_retention_settings(db)?;
    let Some(days) = settings.retention_days else {
        return Ok(Vec::new());
    };
    let window_ms = i64::from(days) * 86_400_000;
    let cutoff = now_ms - window_ms;

    let tx = db.conn().unchecked_transaction()?;
    let mut stmt =
        tx.prepare("SELECT id FROM transcript WHERE ended_at IS NOT NULL AND ended_at <= ?1")?;
    let ids: Vec<i64> = stmt
        .query_map(params![cutoff], |r| r.get(0))?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    drop(stmt);
    for id in &ids {
        tx.execute("DELETE FROM transcript WHERE id = ?1", params![id])?;
    }
    tx.commit()?;
    Ok(ids)
}
