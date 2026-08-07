//! The persisted authored slide-deck library (schema v16; Design 2.0 node 329:124) — reusable
//! presentation documents. One row per deck NAME; `deck_json` is the canonical serialized
//! `SlideDeck`, opaque to this layer (mirrors `saved_theme_repo` — the data crate never
//! deserializes the deck, so it takes no dependency on `selahcue-present`). Writes replace the
//! whole set transactionally, so a delete in memory becomes a delete on disk.

use crate::{Database, Result};
use rusqlite::params;

/// Replace the persisted deck library with `decks` (`(name, deck_json)` pairs) in one
/// transaction: the on-disk set becomes exactly the supplied set (removals honoured; a crash
/// mid-write never leaves a partial library).
pub fn save_all(db: &Database, decks: &[(String, String)]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM deck", [])?;
    for (name, deck_json) in decks {
        tx.execute(
            "INSERT INTO deck (name, deck_json) VALUES (?1, ?2)",
            params![name, deck_json],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole deck library as `(name, deck_json)` pairs, ordered by name (deterministic).
pub fn load_all(db: &Database) -> Result<Vec<(String, String)>> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT name, deck_json FROM deck ORDER BY name")?;
    let rows = stmt.query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}

/// Upsert a SINGLE deck by name (INSERT-OR-REPLACE) — the per-deck autosave path, so editing one
/// deck does not rewrite the whole library each time (`save_all` is the whole-set replace, used for
/// bulk/consistency writes). The caller keys the library by a stable [`DeckId`] but persists by
/// NAME (the table PK), so it must keep names unique before calling this — an upsert on a name that
/// already belongs to a DIFFERENT deck would otherwise overwrite that row.
///
/// [`DeckId`]: https://docs — see `selahcue_present::DeckId`.
pub fn save_one(db: &Database, name: &str, deck_json: &str) -> Result<()> {
    db.conn().execute(
        "INSERT INTO deck (name, deck_json) VALUES (?1, ?2)
         ON CONFLICT(name) DO UPDATE SET deck_json = excluded.deck_json",
        params![name, deck_json],
    )?;
    Ok(())
}

/// Delete a single deck by name. Idempotent — deleting an absent name is a no-op (0 rows).
pub fn delete_one(db: &Database, name: &str) -> Result<()> {
    db.conn()
        .execute("DELETE FROM deck WHERE name = ?1", params![name])?;
    Ok(())
}

/// Rename a deck ATOMICALLY (drop the old-name row + upsert the new-name row in one transaction),
/// so a crash mid-rename can never lose the deck's on-disk row. `new_name` must be unique (the
/// caller keeps names unique); `old_name == new_name` collapses to a plain content upsert.
pub fn rename_one(db: &Database, old_name: &str, new_name: &str, deck_json: &str) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    if old_name != new_name {
        tx.execute("DELETE FROM deck WHERE name = ?1", params![old_name])?;
    }
    tx.execute(
        "INSERT INTO deck (name, deck_json) VALUES (?1, ?2)
         ON CONFLICT(name) DO UPDATE SET deck_json = excluded.deck_json",
        params![new_name, deck_json],
    )?;
    tx.commit()?;
    Ok(())
}
