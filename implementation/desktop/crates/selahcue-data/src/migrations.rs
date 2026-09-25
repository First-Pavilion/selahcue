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
    // v19 -> v20: TRANSCRIPT + DETECTION PERSISTENCE (86ajtxzrn; FR-130/153/154/137/082).
    //
    // Identity — an assumption cleared to proceed on, NOT a confirmed product/
    // architecture decision (corrected here after review; the previous wording in this
    // comment overstated its status — see the ClickUp comments on 86ajtxzrn, which state
    // plainly that sign-off is still outstanding): a transcript = one listening session
    // (one start-to-stop of the STT engine), provider-agnostic (ADR-0010/0019). `label`
    // defaults to the active `ServicePlan`'s name + start timestamp, or just the
    // timestamp when no plan was active (`selahcue_core::plan::ServicePlan` is app-layer
    // knowledge; this table only stores the resolved string) — `label` is a plain,
    // renamable column (no separate "custom label" flag needed), so the future rename
    // affordance (FR-130/R5) is already free. `plan_id` is nullable and ON DELETE SET
    // NULL: a transcript must outlive the plan it was recorded against, per the "raw
    // transcript is immutable" principle this whole slice exists to serve.
    //
    // Segments are the "raw immutable stream": `transcript_segment` has no counterpart to
    // `MAX_TRANSCRIPT_SEGMENTS`/`MAX_SEGMENT_TEXT_LEN` (selahcue-core::transcript — those
    // cap only the in-memory ring) — `text`/`ord` are unbounded by construction (SQLite
    // TEXT/INTEGER columns), which is the acceptance criterion this migration exists to
    // satisfy. `ord` is assigned by the repo at append time (current count for that
    // transcript), not reused from the in-memory ring's per-session id, so a segment's
    // position survives independently of whatever the live engine numbered it.
    //
    // `transcript_correction` is the "editable correction layer" — schema only, no editing
    // UI in this ticket (non-goal). One row per corrected segment (`segment_id UNIQUE`): a
    // second edit replaces the first via upsert, the same "latest wins" shape as
    // `session_state`. The segment it corrects cascades away with it, and the raw segment
    // text is never overwritten (FR-123's mirror for the correction layer, not just notes).
    //
    // `detection` persists `selahcue_core::detection::DetectedReference` rows tied to a
    // transcript (and, where known, the segment that produced them); `segment_id` is
    // nullable + ON DELETE CASCADE so a detection's provenance link cascades with its
    // segment without forcing every caller to resolve one. `idx_detection_segment`
    // exists so that cascade lookup (fired once per deleted segment, by every
    // `transcript_repo::delete`/`purge_expired` call) is index-backed rather than a full
    // scan of every detection ever stored across every transcript — measured at 144M
    // full-scan VM steps / 6.6s for one delete of a 3,000-segment transcript against a
    // 30k-row detection table without this index, 0 steps / 5-10ms with it (Vera, PR #30
    // review). Cheap now, forward-only migration after merge.
    //
    // `transcript_setting` is a flat key/value table — the same shape as `providers_setting`
    // (v18->v19) — so retention config is a *setting*, not a hardcoded constant (per this
    // ticket's acceptance criterion), and every open product/legal question 86ajtxzrn leaves
    // unresolved (the FR-153 retention-days default, the delete-cascade-to-notes flag once
    // notes exist, a future consent/administrator-scope key) is answerable by adding a KEY,
    // never a further migration. An absent key reads back as the placeholder default via
    // `transcript_repo`, exactly as `providers_repo::load` falls back to
    // `ProvidersConfig::default()` for an empty store — at the time this migration shipped
    // that default was "kept indefinitely; notes are not cascade-deleted" (notes did not
    // exist yet); 86akgqdv0, which added the `sermon_note` table (v20 -> v21 below), PROPOSED
    // and implemented flipping the notes-cascade half to `true` by default — see
    // `RetentionSettings::delete_cascade_to_notes`'s doc comment for the current default and
    // why it is a proposal pending product sign-off, not a settled decision.
    // FR-137 "Administrator-gated" enforcement (who may change this setting) is a command/
    // RBAC-layer concern per the existing precedent for provider consent (see
    // `selahcue-core::providers` — "Administrator-gated at the command layer" — and
    // `selahcue-lan::rbac::authorize`); this migration only makes the setting exist,
    // outside a hardcoded constant, for that layer to gate.
    //
    // Encryption (FR-154): no per-table wiring is needed or added here. SQLCipher (the
    // `encryption` feature) keys the whole database file before `migrations::run` ever
    // executes (`Database::open_encrypted` / `open_in_memory_encrypted`), so every table
    // created by this migration is encrypted at rest exactly like every table that came
    // before it — proven for this schema by the encrypted round-trip test added alongside
    // `test_encryption.rs`'s existing coverage.
    r#"
    CREATE TABLE transcript (
        id         INTEGER PRIMARY KEY,
        plan_id    INTEGER REFERENCES service_plan(id) ON DELETE SET NULL,
        label      TEXT    NOT NULL,
        provider   TEXT    NOT NULL,
        started_at INTEGER NOT NULL,
        ended_at   INTEGER
    );
    CREATE INDEX idx_transcript_started_at ON transcript(started_at);

    CREATE TABLE transcript_segment (
        id            INTEGER PRIMARY KEY,
        transcript_id INTEGER NOT NULL REFERENCES transcript(id) ON DELETE CASCADE,
        ord           INTEGER NOT NULL,
        start_ms      INTEGER NOT NULL,
        end_ms        INTEGER NOT NULL,
        text          TEXT    NOT NULL,
        UNIQUE (transcript_id, ord)
    );
    -- No separate CREATE INDEX on (transcript_id, ord) here: the UNIQUE constraint
    -- above already creates that exact index (SQLite's implicit autoindex), so a
    -- second explicit one would be a byte-identical second B-tree maintained on every
    -- append with zero query benefit (Cody #3 / Vera F3 — measured ~7% extra file size
    -- at 5,000 segments, no plan-shape change when dropped).

    CREATE TABLE transcript_correction (
        id             INTEGER PRIMARY KEY,
        segment_id     INTEGER NOT NULL UNIQUE REFERENCES transcript_segment(id) ON DELETE CASCADE,
        corrected_text TEXT    NOT NULL,
        corrected_at   INTEGER NOT NULL
    );

    CREATE TABLE detection (
        id            INTEGER PRIMARY KEY,
        transcript_id INTEGER NOT NULL REFERENCES transcript(id) ON DELETE CASCADE,
        segment_id    INTEGER REFERENCES transcript_segment(id) ON DELETE CASCADE,
        reference     TEXT    NOT NULL,
        confidence    INTEGER NOT NULL
    );
    CREATE INDEX idx_detection_transcript ON detection(transcript_id);
    CREATE INDEX idx_detection_segment ON detection(segment_id);

    CREATE TABLE transcript_setting (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    "#,
    // v20 -> v21: persist generated sermon-note drafts so they survive past the
    // confirm-and-generate dialog, and let the operator edit them afterward
    // (86akgqdv0; FR-123 "editable" half — generation + labelling + the untouched-
    // transcript invariant shipped already in 86akby7d8/PR #19).
    //
    // One editable draft per transcript: `transcript_id` is UNIQUE. Regenerating a
    // draft and retaining a prior version (FR-129, 86akgqdx8) was explicitly out of
    // THIS migration's scope when it shipped — `sermon_note_repo::create` upserts
    // (replaces) the single row for a transcript rather than keeping history, which
    // was a deliberate interim behaviour, not an oversight, pending FR-129. FR-129
    // (v21 -> v22, below) has since shipped retention as ADDITIVE `pending_*`
    // columns on this SAME row rather than a second table — `create`'s own
    // upsert-replace behaviour described here is UNCHANGED and still exactly what
    // runs when no draft exists yet (a true first-time generate); see the v21 -> v22
    // migration comment for how a regenerate against an EXISTING draft differs.
    //
    // `sections` and `scriptures` are opaque JSON TEXT, not normalized child tables —
    // the same "dumb store" shape as `deck.deck_json` (see `deck_repo`): the data
    // layer round-trips whatever the caller hands it without knowing its shape.
    // `selahcue-core` stays dependency-free (no serde here either), so the JSON
    // encode/decode of `NoteSection`'s items-XOR-points shape (FR-122) lives in
    // `selahcue-operator`, which already depends on `serde_json` for the wire to the
    // JS UI (`draft_json()`) — never in this crate or in core.
    //
    // `ai_generated`/`disclosure`/`provider`/`model` are set ONLY at create time (from
    // the generating `GenerationOutcome`) and are never touched by
    // `sermon_note_repo::update` — editing a draft's text must never silently drop
    // the FR-123 label or the FR-128 fabrication disclosure. `disclosure` is
    // nullable because it is `None` exactly when `ai_generated` is false (the FR-135
    // offline-fallback scaffold), mirroring `GenerationOutcome::disclosure`'s own
    // invariant. `model` is nullable and, at the one call site wired by this ticket,
    // always NULL today: no `NoteProvider` implementation currently exposes a model
    // identifier through `GenerationOutcome` (only a human-readable `provider_label`)
    // — the column exists for a future provider that can report one, not invented
    // data.
    //
    // `transcript_id` is NULLABLE with `ON DELETE SET NULL` as the schema-level
    // FLOOR behaviour: on its own, deleting a transcript detaches its note (the note
    // survives, non-destructively) rather than losing it. Whether a transcript
    // delete instead CASCADES to remove its notes is governed by the existing
    // `transcript_setting` key `delete_cascade_to_notes` — added empty/inert by
    // 86ajtxzrn in anticipation of exactly this ticket — and is enforced by
    // `transcript_repo::delete`/`purge_expired` EXPLICITLY deleting the matching
    // `sermon_note` row inside the same transaction, BEFORE the transcript row goes
    // away, whenever that setting is on. This keeps the cascade answer a runtime
    // setting, not a schema decision baked into the FK — the exact seam 86ajtxzrn
    // left open, so the answer can change without a second migration. See
    // `transcript_repo::RetentionSettings::delete_cascade_to_notes`'s doc comment for
    // this ticket's PROPOSED (not yet product-signed-off) default.
    // `transcript_id UNIQUE` already creates an implicit autoindex on that column
    // (`sqlite_autoindex_sermon_note_1`) — an explicit `CREATE INDEX` on the same column would
    // be a byte-identical second B-tree the planner never picks for any statement (the exact
    // pattern PR #30 already fixed once for `transcript_segment`; see
    // `transcript_segment_has_exactly_one_index_from_its_unique_constraint` in
    // `tests/test_transcript_repo.rs`, mirrored here by
    // `sermon_note_has_exactly_one_index_from_its_unique_constraint`). No explicit index is
    // added (PR #33 review, Vera F1).
    r#"
    CREATE TABLE sermon_note (
        id            INTEGER PRIMARY KEY,
        transcript_id INTEGER UNIQUE REFERENCES transcript(id) ON DELETE SET NULL,
        title         TEXT    NOT NULL,
        summary       TEXT,
        sections      TEXT    NOT NULL,
        scriptures    TEXT    NOT NULL,
        ai_generated  INTEGER NOT NULL,
        disclosure    TEXT,
        provider      TEXT    NOT NULL,
        model         TEXT,
        created_at    INTEGER NOT NULL,
        edited_at     INTEGER NOT NULL
    );
    "#,
    // v21 -> v22: single-prior-version RETENTION for regenerate (FR-129, 86akgqdx8).
    //
    // The decided model (see this ticket's Goal Contract / MR description for the full
    // reasoning): SINGLE prior version, never a history stack — the PRD's own wording is
    // "prior version" (singular) — and EXPLICIT-CONFIRM-BEFORE-REPLACE, not
    // automatic-replace-with-undo — the ticket's scope text says the prior draft is
    // retained "until the new draft is confirmed/accepted by the operator".
    //
    // Nine additive, all-nullable columns hold a NOT-YET-CONFIRMED regenerated draft
    // ALONGSIDE the currently-accepted one, in the SAME row, rather than a second table or
    // a history table:
    //   - The currently-accepted draft keeps living in the existing, unrenamed columns
    //     (`title`/`summary`/`sections`/`scriptures`/`ai_generated`/`disclosure`/
    //     `provider`/`model`/`created_at`/`edited_at`) — completely untouched by staging a
    //     regeneration, which is exactly what makes "the prior draft is retrievable,
    //     unmodified, immediately after a regenerate is requested" true by construction
    //     rather than by a second copy that could drift.
    //   - `pending_*` mirrors every create-time field of a fresh draft (see
    //     `sermon_note_repo::NewSermonNote`) EXCEPT `edited_at` — a pending regeneration is
    //     not yet "the" draft, so it has no edit history yet; `pending_generated_at` is its
    //     create-time stamp, reused for both `created_at` and `edited_at` when it is
    //     confirmed (mirroring `create`'s own `VALUES (?10, ?10)` for a brand-new row).
    //   - All nine are NULL together (the default for every pre-v22 row, and the state
    //     after a fresh `create`/after a `confirm`/after a `discard`) or non-NULL together
    //     (immediately after a `stage`) — `pending_title` is the single non-nullable-in-a-
    //     real-draft field this crate treats as the presence sentinel, mirroring how
    //     `disclosure`'s own NULL-exactly-when-not-`ai_generated` pairing already works one
    //     column over.
    //
    // A second `stage` before the first is confirmed/discarded OVERWRITES the pending
    // slot outright — there is only one pending-regeneration slot per transcript, matching
    // the single-prior-version decision above: only the CONFIRMED version is guaranteed
    // retained, never an intermediate, never-confirmed regeneration attempt.
    //
    // No new FK, no new cascade path to design: a `pending_*` set lives and dies with the
    // `sermon_note` row it sits on (the existing `ON DELETE SET NULL`/detached-note/
    // `list_detached`/`delete_by_id` machinery for the whole row already covers it — there
    // is no separate row to leak).
    r#"
    ALTER TABLE sermon_note ADD COLUMN pending_title TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_summary TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_sections TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_scriptures TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_ai_generated INTEGER;
    ALTER TABLE sermon_note ADD COLUMN pending_disclosure TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_provider TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_model TEXT;
    ALTER TABLE sermon_note ADD COLUMN pending_generated_at INTEGER;
    "#,
    // v22 -> v23: bounded autosave-SLOT history (FR-005 "last-3"; ticket 86ajy0hxg).
    //
    // `session_state` (v1) stays exactly what it always was: a SINGLETON row, continuously
    // overwritten, that crash recovery restores from on every launch. This table is a sibling,
    // not a replacement — a bounded RING of distinct earlier restore points (`autosave_repo`
    // enforces the count via prune-after-insert), so "restore the last autosave" (FR-005) has
    // more than the single most-recent instant to offer when THAT instant turns out to be the
    // state the operator wants to get away from (a failed open, a bad edit). Mirrors
    // `session_state`'s columns exactly, plus `saved_at_ms` (when this restore point was
    // captured) and an optional `label`. A fresh table, so no existing row's shape changes.
    r#"
    CREATE TABLE autosave_slot (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        saved_at_ms        INTEGER NOT NULL,
        label              TEXT,
        plan_id            INTEGER REFERENCES service_plan(id) ON DELETE SET NULL,
        live_idx           INTEGER,
        staged_idx         INTEGER,
        plan_cursor        INTEGER,
        blackout           INTEGER NOT NULL DEFAULT 0,
        timer_total_secs   INTEGER,
        timer_elapsed_secs INTEGER,
        timer_running      INTEGER,
        live_scripture     TEXT,
        staged_scripture   TEXT,
        live_free_text     TEXT,
        live_slide         INTEGER,
        staged_slide       INTEGER,
        cursor_slide       INTEGER,
        live_free_body     TEXT,
        theme              TEXT,
        custom_theme       TEXT
    );
    CREATE INDEX idx_autosave_slot_saved_at ON autosave_slot(saved_at_ms);
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
