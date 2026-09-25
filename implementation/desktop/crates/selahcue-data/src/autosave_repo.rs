//! Repository for the bounded autosave-SLOT history (FR-005 "last-3" restore points;
//! ticket 86ajy0hxg).
//!
//! A sibling of [`crate::session_repo`]'s singleton crash-recovery row: that row is the
//! continuously-refreshed "resume exactly where I left off" snapshot the app loads on every
//! launch. This table is a bounded RING of distinct earlier restore points an operator can
//! choose from when the continuous one turns out to be the state they want to get AWAY from
//! (a failed open, a bad edit) — FR-005's "restore the last autosave" only makes sense as a
//! choice among more than one saved instant.

use crate::session_repo::SessionState;
use crate::{DataError, Database, Result};
use rusqlite::params;

/// Hard cap on the autosave-slot ring (FR-005 "last-3", no-leak). [`push`] keeps only the
/// newest this many rows, deleting the rest in the same transaction as the insert.
pub const MAX_AUTOSAVE_SLOTS: usize = 3;

/// One persisted restore point: its stable id (the `RestoreAutosave { slot }` wire value),
/// when it was captured, an optional human label, and the full session snapshot.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AutosaveSlot {
    pub id: i64,
    pub saved_at_ms: i64,
    pub label: Option<String>,
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
) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute(
        "INSERT INTO autosave_slot
            (saved_at_ms, label, plan_id, live_idx, staged_idx, plan_cursor, blackout,
             timer_total_secs, timer_elapsed_secs, timer_running, live_scripture,
             staged_scripture, live_free_text, live_slide, staged_slide, cursor_slide,
             live_free_body, theme, custom_theme)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17,
                 ?18, ?19)",
        params![
            saved_at_ms,
            label,
            state.plan_id,
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
    // Prune to the bound: keep only the newest MAX_AUTOSAVE_SLOTS rows, newest by
    // `saved_at_ms` (ties broken by `id`, so a same-millisecond burst still keeps exactly the
    // bound rather than an arbitrary tie-break letting the count drift).
    tx.execute(
        "DELETE FROM autosave_slot WHERE id NOT IN (
            SELECT id FROM autosave_slot ORDER BY saved_at_ms DESC, id DESC LIMIT ?1
        )",
        params![MAX_AUTOSAVE_SLOTS as i64],
    )?;
    tx.commit()?;
    Ok(())
}

/// List slots newest-first (already bounded on disk by [`push`]'s prune).
pub fn list(db: &Database) -> Result<Vec<AutosaveSlot>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT id, saved_at_ms, label, plan_id, live_idx, staged_idx, plan_cursor, blackout,
                timer_total_secs, timer_elapsed_secs, timer_running, live_scripture,
                staged_scripture, live_free_text, live_slide, staged_slide, cursor_slide,
                live_free_body, theme, custom_theme
         FROM autosave_slot ORDER BY saved_at_ms DESC, id DESC",
    )?;
    let rows = stmt.query_map([], row_to_slot)?;
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
        "SELECT id, saved_at_ms, label, plan_id, live_idx, staged_idx, plan_cursor, blackout,
                timer_total_secs, timer_elapsed_secs, timer_running, live_scripture,
                staged_scripture, live_free_text, live_slide, staged_slide, cursor_slide,
                live_free_body, theme, custom_theme
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
    let timer_running: Option<i64> = r.get(10)?;
    Ok(AutosaveSlot {
        id,
        saved_at_ms,
        label,
        state: SessionState {
            plan_id: r.get(3)?,
            live_idx: idx(r.get(4)?, "live_idx")?,
            staged_idx: idx(r.get(5)?, "staged_idx")?,
            plan_cursor: idx(r.get(6)?, "plan_cursor")?,
            blackout: r.get::<_, i64>(7)? != 0,
            timer_total_secs: idx(r.get(8)?, "timer_total_secs")?,
            timer_elapsed_secs: idx(r.get(9)?, "timer_elapsed_secs")?,
            timer_running: timer_running.unwrap_or(0) != 0,
            live_scripture: r.get(11)?,
            staged_scripture: r.get(12)?,
            live_free_text: r.get(13)?,
            live_slide: idx(r.get(14)?, "live_slide")?,
            staged_slide: idx(r.get(15)?, "staged_slide")?,
            cursor_slide: idx(r.get(16)?, "cursor_slide")?,
            live_free_body: r.get(17)?,
            theme: r.get(18)?,
            custom_theme: r.get(19)?,
        },
    })
}
