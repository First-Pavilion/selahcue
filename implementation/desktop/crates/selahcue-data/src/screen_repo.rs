//! The persisted SCREEN REGISTRY (Screens page — dynamic registry): each managed screen
//! (built-in `main`/`lower-third`/`stream`/`stage` plus any virtual feed the operator
//! added), its role, enable state, deletability, and a stable ordering. One row per
//! screen; writes replace the whole set transactionally (mirrors the controller's
//! in-memory `ScreenRegistry`, so a deleted virtual screen is honoured on disk).
//!
//! The registry is **rebuilt** by the controller via `ScreenRegistry::from_persisted`,
//! which recovers robustly (the four built-ins are always present, corrupt/over-cap rows
//! are dropped). This repo is only the transactional persistence layer — it does not
//! interpret roles, so a forward-compatible role tag round-trips untouched.

use crate::{Database, Result};
use rusqlite::params;

/// One persisted registry row: `(screen_id, role_tag, enabled, deletable)`. Ordering is
/// assigned by the save position (the registry's deterministic order).
pub type ScreenRow = (String, String, bool, bool);

/// Replace the persisted screen registry with `screens` in one transaction: the on-disk
/// set becomes exactly the supplied set (in order), so a deleted screen is honoured and a
/// crash mid-write never leaves a partial registry.
pub fn save_all(db: &Database, screens: &[ScreenRow]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM screen", [])?;
    for (ordering, (screen, role, enabled, deletable)) in screens.iter().enumerate() {
        tx.execute(
            "INSERT INTO screen (screen, role, enabled, deletable, ordering) \
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![screen, role, *enabled, *deletable, ordering as i64],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole screen registry as `(screen, role, enabled, deletable)` rows, in the stored
/// `ordering` (the registry's deterministic order — built-ins first, then virtuals).
pub fn load_all(db: &Database) -> Result<Vec<ScreenRow>> {
    let conn = db.conn();
    let mut stmt =
        conn.prepare("SELECT screen, role, enabled, deletable FROM screen ORDER BY ordering")?;
    let rows = stmt.query_map([], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, bool>(2)?,
            r.get::<_, bool>(3)?,
        ))
    })?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}
