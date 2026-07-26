//! The persisted per-screen theme map (story 86ajq321k) — each Audience-class screen
//! (`main` / `lower-third` / `stream`) and its assigned theme NAME. One row per screen;
//! writes replace the whole set transactionally (mirrors the controller's in-memory
//! `screen_themes` map, so clearing a screen in memory clears it on disk).

use crate::{Database, Result};
use rusqlite::params;

/// Replace the persisted per-screen theme map with `themes` (`(screen, theme_name)`) in
/// one transaction: the on-disk set becomes exactly the supplied set, so a cleared screen
/// is honoured and a crash mid-write never leaves a partial map.
pub fn save_all(db: &Database, themes: &[(String, String)]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM screen_theme", [])?;
    for (screen, theme_name) in themes {
        tx.execute(
            "INSERT INTO screen_theme (screen, theme_name) VALUES (?1, ?2)",
            params![screen, theme_name],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole per-screen theme map as `(screen, theme_name)` pairs, ordered by screen.
pub fn load_all(db: &Database) -> Result<Vec<(String, String)>> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT screen, theme_name FROM screen_theme ORDER BY screen")?;
    let rows = stmt.query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}
