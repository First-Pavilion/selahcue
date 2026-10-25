//! The persisted authored slide-deck library (schema v16; Design 2.0 node 329:124) — reusable
//! presentation documents. One row per deck NAME; `deck_json` is the canonical serialized
//! `SlideDeck`, opaque to this layer (mirrors `saved_theme_repo` — the data crate never
//! deserializes the deck, so it takes no dependency on `selahcue-present`). Writes replace the
//! whole set transactionally, so a delete in memory becomes a delete on disk.
//!
//! **The deck-number high-water mark (schema v25; 17tnw2b9arx).** A deck is keyed by NAME on disk
//! but linked from plans by NUMBER, so a number the library has ever issued must never be issued
//! again, even after its deck is deleted and a restart has emptied the (memory-only) undo trash.
//! `deck_id_counter` holds one integer, the highest number ever written for a deck here. The
//! `*_numbered` writers raise it in the same transaction as the row they write; [`high_water`] reads
//! it; nothing lowers it (deleting a deck does not touch it, and a trigger refuses an UPDATE that
//! would). The unnumbered [`save_one`] / [`rename_one`] / [`save_all`] do NOT touch it: they are for
//! callers that have no deck number (and for tests that build a legacy database on purpose).

use crate::{Database, Result};
use rusqlite::{params, OptionalExtension};

/// The largest number the mark can hold: SQLite integers are signed 64-bit. A deck number above this
/// (a crafted blob; the library's counter saturates at `u64::MAX`) is recorded as this, which is
/// still above every number the library can mint before it runs out of memory.
const MARK_MAX: u64 = i64::MAX as u64;

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

// --- the deck-number high-water mark (schema v25; 17tnw2b9arx) -----------------------------------

fn mark_param(deck_id: u64) -> i64 {
    // `MARK_MAX == i64::MAX`, so the conversion cannot fail; the fallback is the same value.
    i64::try_from(deck_id.min(MARK_MAX)).unwrap_or(i64::MAX)
}

/// Raise the mark to at least `deck_id` on `conn` (a connection or an open transaction). SQL `MAX`
/// makes this a no-op for a lower number, so the mark can never go down through here.
fn raise_on(conn: &rusqlite::Connection, deck_id: u64) -> Result<()> {
    conn.execute(
        "INSERT INTO deck_id_counter (id, high_water) VALUES (1, ?1)
         ON CONFLICT(id) DO UPDATE SET high_water = MAX(high_water, excluded.high_water)",
        params![mark_param(deck_id)],
    )?;
    Ok(())
}

/// The highest deck number ever written for a deck in this database, or `0` when nothing has been
/// recorded (a fresh database, or one written by a build from before the mark existed).
pub fn high_water(db: &Database) -> Result<u64> {
    let mark: Option<i64> = db
        .conn()
        .query_row(
            "SELECT high_water FROM deck_id_counter WHERE id = 1",
            [],
            |r| r.get(0),
        )
        .optional()?;
    Ok(mark.map_or(0, |m| u64::try_from(m).unwrap_or(0)))
}

/// Raise the mark to at least `deck_id` without writing a deck: what a library does on load, so a
/// database written before the mark existed records the highest number it already holds. Never
/// lowers the mark.
pub fn raise_high_water(db: &Database, deck_id: u64) -> Result<()> {
    raise_on(db.conn(), deck_id)
}

/// [`save_one`], and raise the high-water mark to at least `deck_id` in the SAME transaction: the
/// deck row and the mark commit together or not at all, so a row never exists on disk with a number
/// above the mark. `deck_id` is the deck's own number (the one plans link).
pub fn save_one_numbered(db: &Database, name: &str, deck_json: &str, deck_id: u64) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    raise_on(&tx, deck_id)?;
    tx.execute(
        "INSERT INTO deck (name, deck_json) VALUES (?1, ?2)
         ON CONFLICT(name) DO UPDATE SET deck_json = excluded.deck_json",
        params![name, deck_json],
    )?;
    tx.commit()?;
    Ok(())
}

/// [`rename_one`], and raise the high-water mark to at least `deck_id` in the same transaction.
pub fn rename_one_numbered(
    db: &Database,
    old_name: &str,
    new_name: &str,
    deck_json: &str,
    deck_id: u64,
) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    raise_on(&tx, deck_id)?;
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
