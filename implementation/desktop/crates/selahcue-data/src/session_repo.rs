//! Repository for the live-session snapshot (crash recovery).
//!
//! A singleton row holding the last autosaved live state: which plan is loaded and
//! where the service is in it (live/staged/cursor/blackout/timer). On a crash, the
//! next launch restores from here — the "force-kill + recover exact live state"
//! demo requirement.

use crate::{DataError, Database, Result};
use rusqlite::params;

/// The persisted live-session snapshot (pure data; the application layer maps it
/// onto its controller).
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct SessionState {
    /// Row id of the loaded plan (`service_plan.id`), if one is persisted.
    pub plan_id: Option<i64>,
    pub live_idx: Option<u32>,
    pub staged_idx: Option<u32>,
    pub plan_cursor: Option<u32>,
    pub blackout: bool,
    /// Active countdown: target duration in whole seconds.
    pub timer_total_secs: Option<u32>,
    /// Elapsed at the moment of the save.
    pub timer_elapsed_secs: Option<u32>,
    /// Whether the countdown was running (restore resumes it).
    pub timer_running: bool,
    /// A scripture reference on the LIVE output (a non-plan slide), if any.
    pub live_scripture: Option<String>,
    /// A scripture reference staged in Preview, if any.
    pub staged_scripture: Option<String>,
}

/// Upsert the singleton snapshot (atomic single-statement write).
pub fn save(db: &Database, s: &SessionState) -> Result<()> {
    db.conn().execute(
        "INSERT INTO session_state
            (id, plan_id, live_idx, staged_idx, plan_cursor, blackout,
             timer_total_secs, timer_elapsed_secs, timer_running,
             live_scripture, staged_scripture)
         VALUES (1, ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
         ON CONFLICT(id) DO UPDATE SET
            plan_id = ?1, live_idx = ?2, staged_idx = ?3, plan_cursor = ?4,
            blackout = ?5, timer_total_secs = ?6, timer_elapsed_secs = ?7,
            timer_running = ?8, live_scripture = ?9, staged_scripture = ?10",
        params![
            s.plan_id,
            s.live_idx.map(i64::from),
            s.staged_idx.map(i64::from),
            s.plan_cursor.map(i64::from),
            s.blackout as i64,
            s.timer_total_secs.map(i64::from),
            s.timer_elapsed_secs.map(i64::from),
            if s.timer_running { 1i64 } else { 0 },
            s.live_scripture,
            s.staged_scripture,
        ],
    )?;
    Ok(())
}

/// Load the snapshot, `None` if none was ever saved. Out-of-range stored values
/// surface as [`DataError::Corrupt`] rather than being silently truncated.
pub fn load(db: &Database) -> Result<Option<SessionState>> {
    let row = db
        .conn()
        .query_row(
            "SELECT plan_id, live_idx, staged_idx, plan_cursor, blackout,
                    timer_total_secs, timer_elapsed_secs, timer_running,
                    live_scripture, staged_scripture
             FROM session_state WHERE id = 1",
            [],
            |r| {
                Ok((
                    r.get::<_, Option<i64>>(0)?,
                    r.get::<_, Option<i64>>(1)?,
                    r.get::<_, Option<i64>>(2)?,
                    r.get::<_, Option<i64>>(3)?,
                    r.get::<_, i64>(4)?,
                    r.get::<_, Option<i64>>(5)?,
                    r.get::<_, Option<i64>>(6)?,
                    r.get::<_, Option<i64>>(7)?,
                    r.get::<_, Option<String>>(8)?,
                    r.get::<_, Option<String>>(9)?,
                ))
            },
        )
        .map(Some)
        .or_else(|e| match e {
            rusqlite::Error::QueryReturnedNoRows => Ok(None),
            other => Err(DataError::from(other)),
        })?;

    let Some((
        plan_id,
        live,
        staged,
        cursor,
        blackout,
        t_total,
        t_elapsed,
        t_running,
        live_scr,
        staged_scr,
    )) = row
    else {
        return Ok(None);
    };
    fn idx(v: Option<i64>, what: &str) -> Result<Option<u32>> {
        v.map(|n| {
            u32::try_from(n).map_err(|_| DataError::Corrupt(format!("{what} {n} out of range")))
        })
        .transpose()
    }
    Ok(Some(SessionState {
        plan_id,
        live_idx: idx(live, "live_idx")?,
        staged_idx: idx(staged, "staged_idx")?,
        plan_cursor: idx(cursor, "plan_cursor")?,
        blackout: blackout != 0,
        timer_total_secs: idx(t_total, "timer_total_secs")?,
        timer_elapsed_secs: idx(t_elapsed, "timer_elapsed_secs")?,
        timer_running: t_running.unwrap_or(0) != 0,
        live_scripture: live_scr,
        staged_scripture: staged_scr,
    }))
}

/// Remove the snapshot (e.g. an explicit "end service" in the future).
pub fn clear(db: &Database) -> Result<()> {
    db.conn()
        .execute("DELETE FROM session_state WHERE id = 1", [])?;
    Ok(())
}
