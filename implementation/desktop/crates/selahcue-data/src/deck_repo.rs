//! The persisted authored slide-deck library (schema v16; Design 2.0 node 329:124) — reusable
//! presentation documents. One row per deck NAME; `deck_json` is the canonical serialized
//! `SlideDeck`, opaque to this layer (mirrors `saved_theme_repo` — the data crate never
//! deserializes the deck, so it takes no dependency on `selahcue-present`). Writes replace the
//! whole set transactionally, so a delete in memory becomes a delete on disk.
//!
//! **The deck-number high-water mark (schema v25; 17tnw2b9arx).** A deck is keyed by NAME on disk
//! but linked from plans by NUMBER, so a number the library has ever issued must never be issued
//! again, even after its deck is deleted and a restart has emptied the (memory-only) undo trash.
//! `deck_id_counter` holds one integer, the highest number ever issued here. [`issue_number`]
//! records a number BEFORE it is handed out (so a number whose deck write then fails is still
//! retired), the `*_numbered` writers raise it in the same transaction as the row they write,
//! [`high_water`] reads it, and nothing lowers it: deleting a deck does not touch it, and a trigger
//! refuses an UPDATE that would lower it. (The trigger does not stop `INSERT OR REPLACE`,
//! `REPLACE INTO` or a `DELETE` of the row; nothing here issues those.) The unnumbered
//! [`save_one`] / [`rename_one`] / [`save_all`] do NOT touch the mark: production code must use the
//! `*_numbered` twins, and these remain only for callers with no deck number and for tests that
//! build a legacy database on purpose.

use crate::{Database, Result};
use rusqlite::{params, OptionalExtension};

/// The largest deck number there can be: 2^53 - 1, the largest integer a JSON number holds exactly
/// (the webview, the wire and the plan codec all carry deck numbers as JSON numbers, so a larger
/// one would be silently rounded and two decks could alias). The table's CHECK enforces it too.
/// A deck row carrying a larger number (a crafted or damaged blob) is not trusted: the library
/// renumbers it at load, exactly as it does a zero or duplicate number.
pub const MAX_DECK_NUMBER: u64 = (1 << 53) - 1;

/// Replace the persisted deck library with `decks` (`(name, deck_json)` pairs) in one
/// transaction: the on-disk set becomes exactly the supplied set (removals honoured; a crash
/// mid-write never leaves a partial library).
///
/// Does NOT touch the deck-number high-water mark (see the module doc): production code must not
/// use it for decks that carry numbers.
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
///
/// Does NOT touch the deck-number high-water mark: production code must use
/// [`save_one_numbered`], which raises it in the same transaction.
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
///
/// Does NOT touch the deck-number high-water mark: production code must use
/// [`rename_one_numbered`].
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

/// `deck_id` as the mark's column value, or a refusal if it is not a deck number this database may
/// record (zero is allowed: it records nothing; above [`MAX_DECK_NUMBER`] is refused, never clamped,
/// because clamping would retire every number the database could still issue).
fn mark_param(deck_id: u64) -> Result<i64> {
    if deck_id > MAX_DECK_NUMBER {
        return Err(crate::DataError::Refused(
            "deck number is above the largest number a deck can have".into(),
        ));
    }
    i64::try_from(deck_id).map_err(|_| crate::DataError::Refused("deck number does not fit".into()))
}

/// Raise the mark to at least `deck_id` on `conn` (a connection or an open transaction). It touches the
/// row ONLY when the stored mark is an integer that is behind: a lower number is a no-op, so the mark
/// can never go down through here, and a damaged (non-integer) mark is left exactly as it is instead of
/// being compared, kept, and then rejected by the column's CHECK, which would roll back the deck write
/// it rides on and silently lose an edit to an existing deck. Refusing NEW numbers while the mark is
/// damaged is [`issue_number`]'s job.
fn raise_on(conn: &rusqlite::Connection, deck_id: u64) -> Result<()> {
    let mark = mark_param(deck_id)?;
    conn.execute(
        "INSERT INTO deck_id_counter (id, high_water) VALUES (1, ?1)
         ON CONFLICT(id) DO UPDATE SET high_water = excluded.high_water
         WHERE typeof(high_water) = 'integer' AND high_water < excluded.high_water",
        params![mark],
    )?;
    Ok(())
}

/// The highest deck number ever issued for a deck in this database, or `0` when nothing has been
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

/// Issue the next deck number, atomically: pick `max(mark + 1, at_least)`, record it as the mark and
/// return it, in ONE statement. The number is therefore durable before the caller can hand it out (a
/// deck write that fails afterwards still leaves the number retired), and two processes sharing the
/// database can never be issued the same number. `at_least` is the caller's own lower bound (one past
/// the highest deck it holds), so a mark that is behind or missing still yields a fresh number.
///
/// Refuses (`Err`) rather than issuing when the stored mark is not an integer (a damaged value must
/// never count as 0), when `at_least` is above [`MAX_DECK_NUMBER`], or when the next number would be.
pub fn issue_number(db: &Database, at_least: u64) -> Result<u64> {
    let want = mark_param(at_least.max(1))?;
    // One statement inside a transaction so the ceiling can be checked AFTER the number is picked and
    // refused without leaving the mark advanced: a table created by the first (unreleased) v25
    // definition has no CHECK on the range, and the code must not depend on which definition a file has.
    let tx = db.conn().unchecked_transaction()?;
    let issued: Option<i64> = tx
        .query_row(
            "INSERT INTO deck_id_counter (id, high_water) VALUES (1, ?1)
             ON CONFLICT(id) DO UPDATE SET high_water = MAX(high_water + 1, excluded.high_water)
             WHERE typeof(high_water) = 'integer'
             RETURNING high_water",
            params![want],
            |r| r.get(0),
        )
        .optional()?;
    let number = match issued {
        Some(n) => u64::try_from(n).map_err(|_| {
            crate::DataError::Corrupt("deck number high-water mark is negative".into())
        })?,
        None => {
            return Err(crate::DataError::Corrupt(
                "deck number high-water mark is not an integer".into(),
            ))
        }
    };
    if number > MAX_DECK_NUMBER {
        // Dropping `tx` rolls the advance back.
        return Err(crate::DataError::Refused("deck numbers are used up".into()));
    }
    tx.commit()?;
    Ok(number)
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

/// [`delete_one`], and raise the high-water mark to at least `deck_id` (the deleted deck's number) in
/// the same transaction, so a deleted deck's number is retired even when nothing else would have
/// recorded it: a library whose load could not write the mark (the identity backfill gave up) would
/// otherwise reissue the number of the highest deck deleted before any new deck was created.
pub fn delete_one_numbered(db: &Database, name: &str, deck_id: u64) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    raise_on(&tx, deck_id)?;
    tx.execute("DELETE FROM deck WHERE name = ?1", params![name])?;
    tx.commit()?;
    Ok(())
}
