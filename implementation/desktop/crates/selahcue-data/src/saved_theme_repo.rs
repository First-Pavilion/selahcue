//! The persisted saved-theme library (story 86ajq4xmy) — named CUSTOM themes the
//! Theme Designer can save, list, and re-apply. One row per name; `theme_json` is
//! the canonical serialized `Theme`. Writes replace the whole set transactionally
//! (mirrors the controller's in-memory `saved_themes` map, so a delete in memory
//! becomes a delete on disk).

use crate::{Database, Result};
use rusqlite::params;

/// Replace the persisted library with `themes` (`(name, theme_json)` pairs) in one
/// transaction: the on-disk set becomes exactly the supplied set, so removals are
/// honoured and a crash mid-write never leaves a partial library.
pub fn save_all(db: &Database, themes: &[(String, String)]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM saved_theme", [])?;
    for (name, theme_json) in themes {
        tx.execute(
            "INSERT INTO saved_theme (name, theme_json) VALUES (?1, ?2)",
            params![name, theme_json],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole library as `(name, theme_json)` pairs, ordered by name (deterministic).
pub fn load_all(db: &Database) -> Result<Vec<(String, String)>> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT name, theme_json FROM saved_theme ORDER BY name")?;
    let rows = stmt.query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}
