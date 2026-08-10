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
    // v12 -> v13: the SCREEN REGISTRY (Screens page — dynamic registry). Each managed
    // screen (built-in `main`/`lower-third`/`stream`/`stage` plus any virtual feed the
    // operator added), its role, enable state, deletability, and a stable ordering. A
    // fresh table, so an older database opens unchanged and simply starts with an empty
    // registry — the controller recovers to the default four built-ins when it loads an
    // empty/corrupt set (`ScreenRegistry::from_persisted`).
    r#"
    CREATE TABLE screen (
        screen    TEXT PRIMARY KEY,
        role      TEXT NOT NULL,
        enabled   INTEGER NOT NULL,
        deletable INTEGER NOT NULL,
        ordering  INTEGER NOT NULL
    );
    "#,
    // v13 -> v14: per-SCREEN OUTPUT CONFIG (Screens page Design 2.0 inspector) — each
    // configured screen's orientation, scaling/fit, mirror, output delay, frame-rate target,
    // safe-area guides, and per-layer visibility. A fresh table (named `screen_output_config`
    // to avoid the v4 role→display `output_config`), so an older database opens unchanged and
    // starts with no per-output config (every screen uses the identity default). Only a
    // NON-default config occupies a row; the controller drops unknown/default rows on load.
    r#"
    CREATE TABLE screen_output_config (
        screen            TEXT PRIMARY KEY,
        orientation       INTEGER NOT NULL,
        scale_fit         TEXT NOT NULL,
        mirror            INTEGER NOT NULL,
        delay_ms          INTEGER NOT NULL,
        frame_rate        INTEGER NOT NULL,
        layer_background  INTEGER NOT NULL,
        layer_text        INTEGER NOT NULL,
        layer_lower_third INTEGER NOT NULL,
        layer_logo        INTEGER NOT NULL,
        layer_timer       INTEGER NOT NULL,
        safe_area         INTEGER NOT NULL
    );
    "#,
    // v14 -> v15: NDI output delivery (Screens page — set up an NDI output). Two additive
    // columns on the per-screen output-config table: whether the screen broadcasts as an NDI
    // source, and its NDI source name. Additive (ALTER ADD with defaults), so an older database
    // opens unchanged and every existing row defaults to NDI off / empty name.
    r#"
    ALTER TABLE screen_output_config ADD COLUMN ndi_enabled INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE screen_output_config ADD COLUMN ndi_name    TEXT    NOT NULL DEFAULT '';
    "#,
    // v15 -> v16: the authored slide-DECK library (Design 2.0 "Presentation & Media", node
    // 329:124) — reusable presentation documents. One row per deck NAME; `deck_json` is the
    // canonical serialized `SlideDeck` (name + authored slides + id counter), opaque to the data
    // layer (it never deserializes it, exactly like `saved_theme.theme_json`). A fresh table, so
    // an older database opens unchanged and simply starts with no decks.
    r#"
    CREATE TABLE deck (
        name      TEXT PRIMARY KEY,
        deck_json TEXT NOT NULL
    );
    "#,
    // v16 -> v17: the MEDIA LIBRARY (Design 2.0 node 329:124) — the imported media-asset
    // registry. Structured columns (not a JSON blob) so storage accounting and missing/unused
    // queries stay first-class; `kind` is the `MediaKind` string tag; width/height/duration_ms
    // are NULL when unknown (image has no duration, audio has no pixels). A fresh table, so an
    // older database opens unchanged and starts with an empty library.
    r#"
    CREATE TABLE media_asset (
        id          INTEGER PRIMARY KEY,
        path        TEXT    NOT NULL,
        kind        TEXT    NOT NULL,
        size_bytes  INTEGER NOT NULL,
        width       INTEGER,
        height      INTEGER,
        duration_ms INTEGER,
        imported_at INTEGER NOT NULL
    );
    "#,
    // v17 -> v18: a plan item's linked CONTENT REFERENCE (ADR-0020 follow-up) — the
    // scripture passage / deck / media asset it shows, stored as the opaque, reversible
    // `ItemContent::encode` string (the codec lives in the pure core). NULL = an
    // *unlinked* / title-only item, identical to every existing row — so an older
    // database opens unchanged.
    r#"
    ALTER TABLE plan_item ADD COLUMN content_ref TEXT;
    "#,
    // v18 -> v19: the PROVIDERS & PRIVACY settings + consent store (Settings → Providers
    // & Privacy, Design 2.0 node 338:124; FR-131/132/137). A flat key-value table (one row
    // per setting) — the same replace-the-whole-set shape as `saved_theme`, so the pure core
    // owns the `(key, value)` <-> `ProvidersConfig` mapping and the data layer stays a dumb
    // store. A fresh table, so an older database opens unchanged and simply starts with no
    // rows — which the core reads back as the safe defaults (offline-first, cloud OFF).
    r#"
    CREATE TABLE providers_setting (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
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
