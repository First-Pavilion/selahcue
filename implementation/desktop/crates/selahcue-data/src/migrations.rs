//! Versioned, forward-only schema migrations.
//!
//! The applied version is tracked in SQLite's `user_version` pragma. On open,
//! [`run`] applies every migration whose index is `>= user_version`, each inside
//! its own transaction, then bumps the version. Adding a new schema change means
//! appending one SQL string to [`MIGRATIONS`] — never editing an existing one.

use crate::Result;
use rusqlite::Connection;

/// Ordered schema migrations. Index `n` migrates a database at `user_version == n`
/// to `user_version == n + 1`. **Append only.**
const MIGRATIONS: &[&str] = &[
    // v0 -> v1: service plans + ordered items.
    r#"
    CREATE TABLE service_plan (
        id       INTEGER PRIMARY KEY,
        name     TEXT    NOT NULL,
        next_id  INTEGER NOT NULL
    );
    CREATE TABLE plan_item (
        plan_id      INTEGER NOT NULL REFERENCES service_plan(id) ON DELETE CASCADE,
        item_id      INTEGER NOT NULL,
        ord          INTEGER NOT NULL,
        kind         TEXT    NOT NULL,
        title        TEXT    NOT NULL,
        planned_secs INTEGER,
        owner        TEXT,
        PRIMARY KEY (plan_id, item_id),
        UNIQUE (plan_id, ord)
    );
    CREATE INDEX idx_plan_item_order ON plan_item(plan_id, ord);
    "#,
];

/// The schema version this build expects (== `MIGRATIONS.len()`).
pub fn target_version() -> i64 {
    MIGRATIONS.len() as i64
}

/// Apply any pending migrations. Idempotent: a fully-migrated database is a no-op.
pub fn run(conn: &Connection) -> Result<()> {
    let mut version: i64 = conn.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    // Forward-compat guard: never write to a database created by a newer build.
    if version > target_version() {
        return Err(crate::DataError::SchemaTooNew {
            found: version,
            supported: target_version(),
        });
    }
    while (version as usize) < MIGRATIONS.len() {
        let sql = MIGRATIONS[version as usize];
        let next = version + 1;
        // Each migration + its version bump is one atomic transaction, so a crash
        // mid-migration never leaves a half-applied schema (rollback safety).
        conn.execute_batch(&format!(
            "BEGIN;\n{sql}\nPRAGMA user_version = {next};\nCOMMIT;"
        ))?;
        version = next;
    }
    Ok(())
}
