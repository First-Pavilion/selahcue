//! Repository for the bounded autosave-SLOT history (FR-005 "last-3" restore points;
//! ticket 86ajy0hxg).
//!
//! A sibling of [`crate::session_repo`]'s singleton crash-recovery row: that row is the
//! continuously-refreshed "resume exactly where I left off" snapshot the app loads on every
//! launch. This table is a bounded RING of distinct earlier restore points an operator can
//! choose from when the continuous one turns out to be the state they want to get AWAY from
//! (a failed open) — FR-005's "restore the last autosave" only makes sense as a choice among
//! more than one saved instant.
//!
//! Each row is a `plan_id` POINTER plus session position, not an independent copy of the
//! plan's content — `plan_repo::update` mutates a plan's rows in place on every edit, so a
//! slot's referenced plan can (and, given ordinary use, WILL) have different content by the
//! time it is restored. `plan_fingerprint` exists to make that honest rather than silent: it is
//! a deterministic snapshot of the plan's item content at capture time, opaque to this crate
//! (computed and compared by the caller — `selahcue-desktop`'s `plan_fingerprint` — since this
//! crate has no reason to depend on `selahcue-core`'s plan-content shape for that). A caller
//! MUST refuse to restore a slot whose stored fingerprint disagrees with the plan's CURRENT one
//! (Cody, PR #102 code review — Blocking-1: reproduced live — remove a plan item, then restore
//! a slot captured before the removal, and the wrong item went LIVE with no error at all).

use crate::session_repo::SessionState;
use crate::{DataError, Database, Result};
use rusqlite::params;

/// Hard cap on the autosave-slot ring (FR-005 "last-3", no-leak). [`push`] keeps only the
/// newest this many rows, deleting the rest in the same transaction as the insert.
pub const MAX_AUTOSAVE_SLOTS: usize = 3;

/// One persisted restore point: its stable id (the `RestoreAutosave { slot }` wire value),
/// when it was captured, an optional human label, the plan-content fingerprint captured
/// alongside it (see the module doc), and the full session snapshot.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AutosaveSlot {
    pub id: i64,
    pub saved_at_ms: i64,
    pub label: Option<String>,
    pub plan_fingerprint: Option<String>,
    pub state: SessionState,
}

/// Capture a new restore point and enforce [`MAX_AUTOSAVE_SLOTS`]. The insert and the prune run
/// inside one transaction (rolled back on any error, including an early return via `?` —
/// `rusqlite::Transaction` rolls back on drop unless `commit()` runs), so a crash or a failed
/// write between them can never leave the ring over-full or leave the newest row uninserted
/// while an old one is already gone.
pub fn push(
    db: &Database,
    state: &SessionState,
    saved_at_ms: i64,
    label: Option<&str>,
    plan_fingerprint: Option<&str>,
) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute(
        "INSERT INTO autosave_slot
            (saved_at_ms, label, plan_id, plan_fingerprint, live_idx, staged_idx, plan_cursor,
             blackout, timer_total_secs, timer_elapsed_secs, timer_running, live_scripture,
             staged_scripture, live_free_text, live_slide, staged_slide, cursor_slide,
             live_free_body, theme, custom_theme)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17,
                 ?18, ?19, ?20)",
        params![
            saved_at_ms,
            label,
            state.plan_id,
            plan_fingerprint,
            state.live_idx.map(i64::from),
            state.staged_idx.map(i64::from),
            state.plan_cursor.map(i64::from),
            state.blackout as i64,
            state.timer_total_secs.map(i64::from),
            state.timer_elapsed_secs.map(i64::from),
            if state.timer_running { 1i64 } else { 0 },
            state.live_scripture,
            state.staged_scripture,
            state.live_free_text,
            state.live_slide.map(i64::from),
            state.staged_slide.map(i64::from),
            state.cursor_slide.map(i64::from),
            state.live_free_body,
            state.theme,
            state.custom_theme,
        ],
    )?;
    // Prune to the bound: keep only the newest MAX_AUTOSAVE_SLOTS rows, newest by `id`
    // (AUTOINCREMENT, monotonic by construction) — deliberately NOT `saved_at_ms`, which is a
    // wall-clock value the host stamps (Sana, PR #102 security review — S-4, reproduced live):
    // pruning by `saved_at_ms DESC` means a backward wall-clock jump (NTP correction, manual
    // clock change, DST-adjacent skew) makes every SUBSEQUENT push look "older" than the
    // existing three, so the prune keeps deleting the just-inserted row and the ring silently
    // freezes on the pre-jump slots forever — `push` still returns `Ok(())`, so nothing even
    // logs the failure. `id` cannot regress: it is assigned by SQLite on insert, independent of
    // wall-clock time, so ordering by it alone is both simpler (no tie-break needed) and
    // strictly more correct than the timestamp it was meant to be a tie-break FOR.
    tx.execute(
        "DELETE FROM autosave_slot WHERE id NOT IN (
            SELECT id FROM autosave_slot ORDER BY id DESC LIMIT ?1
        )",
        params![MAX_AUTOSAVE_SLOTS as i64],
    )?;
    tx.commit()?;
    Ok(())
}

/// List slots newest-first by `id` (see [`push`]'s doc on why `id`, not `saved_at_ms`, is the
/// ordering — S-4). Already bounded on disk by `push`'s prune; the `LIMIT` here is defence in
/// depth (Sana, PR #102 security review — N-1), not load-bearing.
pub fn list(db: &Database) -> Result<Vec<AutosaveSlot>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT id, saved_at_ms, label, plan_id, plan_fingerprint, live_idx, staged_idx,
                plan_cursor, blackout, timer_total_secs, timer_elapsed_secs, timer_running,
                live_scripture, staged_scripture, live_free_text, live_slide, staged_slide,
                cursor_slide, live_free_body, theme, custom_theme
         FROM autosave_slot ORDER BY id DESC LIMIT ?1",
    )?;
    let rows = stmt.query_map(params![MAX_AUTOSAVE_SLOTS as i64], row_to_slot)?;
    let mut out = Vec::new();
    for row in rows {
        out.push(row?);
    }
    Ok(out)
}

/// Load one slot's full snapshot by id. `None` if it does not exist (already pruned, or never
/// existed — both read the same to a caller).
pub fn load(db: &Database, id: i64) -> Result<Option<AutosaveSlot>> {
    let conn = db.conn();
    conn.query_row(
        "SELECT id, saved_at_ms, label, plan_id, plan_fingerprint, live_idx, staged_idx,
                plan_cursor, blackout, timer_total_secs, timer_elapsed_secs, timer_running,
                live_scripture, staged_scripture, live_free_text, live_slide, staged_slide,
                cursor_slide, live_free_body, theme, custom_theme
         FROM autosave_slot WHERE id = ?1",
        params![id],
        row_to_slot,
    )
    .map(Some)
    .or_else(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => Ok(None),
        other => Err(DataError::from(other)),
    })
}

/// Decode one `autosave_slot` row. Out-of-range stored integers surface as
/// [`DataError::Corrupt`] rather than being silently truncated — mirrors
/// [`crate::session_repo::load`]'s own decoding discipline.
fn row_to_slot(r: &rusqlite::Row<'_>) -> rusqlite::Result<AutosaveSlot> {
    fn idx(v: Option<i64>, what: &str) -> rusqlite::Result<Option<u32>> {
        v.map(|n| {
            u32::try_from(n).map_err(|_| {
                rusqlite::Error::FromSqlConversionFailure(
                    0,
                    rusqlite::types::Type::Integer,
                    format!("{what} {n} out of range").into(),
                )
            })
        })
        .transpose()
    }
    let id: i64 = r.get(0)?;
    let saved_at_ms: i64 = r.get(1)?;
    let label: Option<String> = r.get(2)?;
    let plan_fingerprint: Option<String> = r.get(4)?;
    let timer_running: Option<i64> = r.get(11)?;
    Ok(AutosaveSlot {
        id,
        saved_at_ms,
        label,
        plan_fingerprint,
        state: SessionState {
            plan_id: r.get(3)?,
            live_idx: idx(r.get(5)?, "live_idx")?,
            staged_idx: idx(r.get(6)?, "staged_idx")?,
            plan_cursor: idx(r.get(7)?, "plan_cursor")?,
            blackout: r.get::<_, i64>(8)? != 0,
            timer_total_secs: idx(r.get(9)?, "timer_total_secs")?,
            timer_elapsed_secs: idx(r.get(10)?, "timer_elapsed_secs")?,
            timer_running: timer_running.unwrap_or(0) != 0,
            live_scripture: r.get(12)?,
            staged_scripture: r.get(13)?,
            live_free_text: r.get(14)?,
            live_slide: idx(r.get(15)?, "live_slide")?,
            staged_slide: idx(r.get(16)?, "staged_slide")?,
            cursor_slide: idx(r.get(17)?, "cursor_slide")?,
            live_free_body: r.get(18)?,
            theme: r.get(19)?,
            custom_theme: r.get(20)?,
        },
    })
}
