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
    /// A scripture reference on the LIVE output, if any (verse text recomposes
    /// from the bundled translation on restore).
    pub live_scripture: Option<String>,
    /// The title of a removed-but-still-on-screen plan item (a free slide) —
    /// restored verbatim as a title-only slide.
    pub live_free_text: Option<String>,
    /// The body lines (newline-joined) of that free slide — a removed song
    /// keeps its lyrics on screen (S8-1 review). NULL = title-only.
    pub live_free_body: Option<String>,
    /// A scripture reference staged in Preview, if any.
    pub staged_scripture: Option<String>,
    /// Within-item slide position of the LIVE item (songs; None = slide 0 /
    /// title-only — the pre-v6 shape).
    pub live_slide: Option<u32>,
    /// Within-item slide position of the STAGED item.
    pub staged_slide: Option<u32>,
    /// Within-item slide position paired with `plan_cursor` (survives a
    /// scripture interruption, like the cursor itself).
    pub cursor_slide: Option<u32>,
    /// The active audience-output theme name (`None` = the default, "classic" —
    /// the pre-v8 shape). Restored so recovery shows the same design (S8-3b).
    pub theme: Option<String>,
}

/// Upsert the singleton snapshot (atomic single-statement write).
pub fn save(db: &Database, s: &SessionState) -> Result<()> {
    db.conn().execute(
        "INSERT INTO session_state
            (id, plan_id, live_idx, staged_idx, plan_cursor, blackout,
             timer_total_secs, timer_elapsed_secs, timer_running,
             live_scripture, staged_scripture, live_free_text,
             live_slide, staged_slide, cursor_slide, live_free_body, theme)
         VALUES (1, ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16)
         ON CONFLICT(id) DO UPDATE SET
            plan_id = ?1, live_idx = ?2, staged_idx = ?3, plan_cursor = ?4,
            blackout = ?5, timer_total_secs = ?6, timer_elapsed_secs = ?7,
            timer_running = ?8, live_scripture = ?9, staged_scripture = ?10,
            live_free_text = ?11, live_slide = ?12, staged_slide = ?13,
            cursor_slide = ?14, live_free_body = ?15, theme = ?16",
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
            s.live_free_text,
            s.live_slide.map(i64::from),
            s.staged_slide.map(i64::from),
            s.cursor_slide.map(i64::from),
            s.live_free_body,
            s.theme,
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
                    live_scripture, staged_scripture, live_free_text,
                    live_slide, staged_slide, cursor_slide, live_free_body, theme
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
                    r.get::<_, Option<String>>(10)?,
                    r.get::<_, Option<i64>>(11)?,
                    r.get::<_, Option<i64>>(12)?,
                    r.get::<_, Option<i64>>(13)?,
                    r.get::<_, Option<String>>(14)?,
                    r.get::<_, Option<String>>(15)?,
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
        free_text,
        live_slide,
        staged_slide,
        cursor_slide,
        live_free_body,
        theme,
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
        live_free_text: free_text,
        live_slide: idx(live_slide, "live_slide")?,
        staged_slide: idx(staged_slide, "staged_slide")?,
        cursor_slide: idx(cursor_slide, "cursor_slide")?,
        live_free_body,
        theme,
    }))
}

/// Remove the snapshot (e.g. an explicit "end service" in the future).
pub fn clear(db: &Database) -> Result<()> {
    db.conn()
        .execute("DELETE FROM session_state WHERE id = 1", [])?;
    Ok(())
}
