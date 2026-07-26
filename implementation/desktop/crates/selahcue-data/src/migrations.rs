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
    // v1 -> v2: live-session snapshot for crash recovery (FR: force-kill + recover).
    // A singleton row (id = 1) — the last autosaved live state; NULLs = "nothing".
    r#"
    CREATE TABLE session_state (
        id                 INTEGER PRIMARY KEY CHECK (id = 1),
        plan_id            INTEGER REFERENCES service_plan(id) ON DELETE SET NULL,
        live_idx           INTEGER,
        staged_idx         INTEGER,
        plan_cursor        INTEGER,
        blackout           INTEGER NOT NULL DEFAULT 0,
        timer_total_secs   INTEGER,
        timer_elapsed_secs INTEGER,
        timer_running      INTEGER
    );
    "#,
    // v2 -> v3: a scripture (a non-plan slide) can be live or staged — persist its
    // reference so recovery restores it instead of a blank surface (review 7u-E).
    r#"
    ALTER TABLE session_state ADD COLUMN live_scripture TEXT;
    ALTER TABLE session_state ADD COLUMN staged_scripture TEXT;
    "#,
    // v3 -> v4: a removed-but-still-on-screen plan item is a FREE SLIDE, not a
    // scripture — recovery must re-render its title-only slide verbatim, never
    // recompose verse text for a title that happens to parse (review 7y-B).
    r#"
    ALTER TABLE session_state ADD COLUMN live_free_text TEXT;
    "#,
    // v4 -> v5: per-venue output → physical-display assignment (FR-040/FR-151).
    r#"
    CREATE TABLE output_config (
        role        TEXT PRIMARY KEY CHECK (role IN ('main', 'stage')),
        display_key TEXT NOT NULL
    );
    "#,
    // v5 -> v6: songs are multi-slide (story S8-1). `content` holds the item's
    // stanza text (blank-line-separated; NULL = title-only, the pre-8a shape,
    // so every existing row keeps its exact behaviour). The session gains the
    // within-item slide positions so a force-kill mid-song restores the same
    // stanza (cursor_slide pairs with plan_cursor and survives a scripture
    // interruption).
    r#"
    ALTER TABLE plan_item ADD COLUMN content TEXT;
    ALTER TABLE session_state ADD COLUMN live_slide INTEGER;
    ALTER TABLE session_state ADD COLUMN staged_slide INTEGER;
    ALTER TABLE session_state ADD COLUMN cursor_slide INTEGER;
    "#,
    // v6 -> v7: a removed live song keeps its LYRICS on screen (a free slide
    // with a body), so recovery must restore the body verbatim, not just the
    // title (batch-8a review). NULL = a title-only free slide, the prior shape.
    r#"
    ALTER TABLE session_state ADD COLUMN live_free_body TEXT;
    "#,
    // v7 -> v8: the audience output has a switchable theme (FR-010, S8-3b). Persist
    // the active theme by its stable built-in name so recovery restores the same
    // design. NULL = the default ("classic"), so every existing row keeps its look.
    r#"
    ALTER TABLE session_state ADD COLUMN theme TEXT;
    "#,
    // v8 -> v9: a CUSTOM theme authored in the Theme Designer (S8-3c), persisted as
    // serialized JSON so recovery restores the exact custom design. NULL = no custom
    // theme (the built-in `theme` name applies) — the pre-v9 shape.
    r#"
    ALTER TABLE session_state ADD COLUMN custom_theme TEXT;
    "#,
    // v9 -> v10: a plan item's per-item theme OVERRIDE by built-in name (S8-3d). The
    // audience output renders that item on its own template; NULL = the global theme
    // (the pre-v10 shape for every existing item).
    r#"
    ALTER TABLE plan_item ADD COLUMN theme TEXT;
    "#,
    // v10 -> v11: the saved-theme library (86ajq4xmy) — named CUSTOM themes the
    // Theme Designer can save, list, and re-apply. `theme_json` is the canonical
    // serialized `Theme`. A fresh table (not a column), so an older database opens
    // unchanged and simply starts with an empty library.
    r#"
    CREATE TABLE saved_theme (
        name       TEXT PRIMARY KEY,
        theme_json TEXT NOT NULL
    );
    "#,
    // v11 -> v12: the per-SCREEN theme map (86ajq321k) — each Audience-class screen
    // (main / lower-third / stream) and its assigned theme NAME (a built-in or a
    // saved-library name). A fresh table, so an older database opens unchanged and
    // simply starts with no per-screen overrides (every screen follows the global).
    r#"
    CREATE TABLE screen_theme (
        screen     TEXT PRIMARY KEY,
        theme_name TEXT NOT NULL
    );
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
