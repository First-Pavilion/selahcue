//! Integration tests for `db` — open/configure, migration, integrity, and the
//! forward-compat schema guard. Exercises only the public API (as any consumer
//! would); private internals, if ever tested, stay inline in `src/db.rs`.

#![allow(clippy::unwrap_used)]

use selahcue_data::{migrations, DataError, Database};

#[test]
fn opens_migrated_and_integrity_ok() {
    let db = Database::open_in_memory().unwrap();
    assert_eq!(db.schema_version().unwrap(), migrations::target_version());
    db.integrity_check().unwrap();
}

#[test]
fn schema_version_is_pinned() {
    // Append-only migrations: bump deliberately with each new migration so an
    // accidental reorder/removal is caught. v8 = session_state.theme (S8-3b);
    // v9 = session_state.custom_theme (S8-3c); v10 = plan_item.theme (S8-3d);
    // v11 = saved_theme library table (86ajq4xmy); v12 = screen_theme table (86ajq321k);
    // v13 = screen registry table; v14 = screen_output_config table (Screens 2.0 inspector);
    // v15 = NDI output columns (ndi_enabled/ndi_name) on screen_output_config;
    // v16 = deck table (authored slide-deck library, Design 2.0 node 329:124);
    // v17 = media_asset table (media library, Design 2.0 node 329:124);
    // v18 = plan_item.content_ref (linked scripture/deck/media, ADR-0020 follow-up);
    // v19 = providers_setting table (Providers & Privacy settings + consent, node 338:124);
    // v20 = transcript + transcript_segment + transcript_correction + detection +
    // transcript_setting tables (86ajtxzrn; FR-130/153/154/137/082);
    // v21 = sermon_note table (86akgqdv0; FR-123 "editable" half);
    // v22 = sermon_note.pending_* regeneration-retention columns (86akgqdx8; FR-129).
    assert_eq!(migrations::target_version(), 22);
}

#[test]
fn a_pre_saved_theme_database_upgrades_and_gains_the_saved_theme_table() {
    // A v10 DB (no saved_theme table) must upgrade cleanly to v11 — a fresh table, so
    // existing data survives and the library simply starts empty. Dropping saved_theme
    // + screen_theme and resetting to v10 forces the v10->v11->v12 migrations to re-run.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "DROP TABLE saved_theme;
             DROP TABLE screen_theme;
             DROP TABLE screen;
             DROP TABLE screen_output_config;
             DROP TABLE deck;
             DROP TABLE media_asset;
             DROP TABLE providers_setting;
             DROP TABLE detection;
             DROP TABLE transcript_correction;
             DROP TABLE transcript_segment;
             DROP TABLE transcript;
             DROP TABLE transcript_setting;
             DROP TABLE sermon_note;
             ALTER TABLE plan_item DROP COLUMN content_ref;
             PRAGMA user_version = 10;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the v11 + v12 + v13 migrations"
    );
    let present: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'saved_theme'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(present, 1, "saved_theme table present after upgrade");
}

#[test]
fn a_pre_screen_theme_database_upgrades_and_gains_the_screen_theme_table() {
    // A v11 DB (no screen_theme table) must upgrade cleanly to v12 — a fresh table, so
    // existing data survives and the per-screen map starts empty. Dropping the tables
    // added after v11 (screen_theme at v12, screen at v13) + resetting to v11 forces the
    // v11->v12->v13 migrations to re-run.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "DROP TABLE screen;
             DROP TABLE screen_theme;
             DROP TABLE screen_output_config;
             DROP TABLE deck;
             DROP TABLE media_asset;
             DROP TABLE providers_setting;
             DROP TABLE detection;
             DROP TABLE transcript_correction;
             DROP TABLE transcript_segment;
             DROP TABLE transcript;
             DROP TABLE transcript_setting;
             DROP TABLE sermon_note;
             ALTER TABLE plan_item DROP COLUMN content_ref;
             PRAGMA user_version = 11;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the migrations up to target"
    );
    let present: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'screen_theme'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(present, 1, "screen_theme table present after upgrade");
}

#[test]
fn a_pre_registry_database_upgrades_and_gains_the_screen_table() {
    // A v12 DB (screen_theme but no screen-registry table) must upgrade cleanly to v13 —
    // a fresh `screen` table, so existing data survives and the registry starts empty
    // (the controller recovers to the four built-in screens). Dropping `screen` (and the
    // later screen_output_config) + resetting to v12 forces the v12->v13->v14 migrations to
    // re-run.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "DROP TABLE screen;
             DROP TABLE screen_output_config;
             DROP TABLE deck;
             DROP TABLE media_asset;
             DROP TABLE providers_setting;
             DROP TABLE detection;
             DROP TABLE transcript_correction;
             DROP TABLE transcript_segment;
             DROP TABLE transcript;
             DROP TABLE transcript_setting;
             DROP TABLE sermon_note;
             ALTER TABLE plan_item DROP COLUMN content_ref;
             PRAGMA user_version = 12;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the v13 + v14 migrations"
    );
    let present: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'screen'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(present, 1, "screen registry table present after upgrade");
    // The registry starts empty — the controller seeds the built-ins on load.
    let count: i64 = db
        .conn()
        .query_row("SELECT COUNT(*) FROM screen", [], |r| r.get(0))
        .unwrap();
    assert_eq!(count, 0, "the registry table starts empty");
}

#[test]
fn a_pre_per_item_theme_database_upgrades_and_gains_the_plan_item_theme_column() {
    // A v9 DB (no plan_item.theme) must upgrade cleanly to v10 — additive column, so
    // existing plan items survive and the new column reads back NULL (the global theme).
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "ALTER TABLE plan_item DROP COLUMN theme;
             DROP TABLE saved_theme;
             DROP TABLE screen_theme;
             DROP TABLE screen;
             DROP TABLE screen_output_config;
             DROP TABLE deck;
             DROP TABLE media_asset;
             DROP TABLE providers_setting;
             DROP TABLE detection;
             DROP TABLE transcript_correction;
             DROP TABLE transcript_segment;
             DROP TABLE transcript;
             DROP TABLE transcript_setting;
             DROP TABLE sermon_note;
             ALTER TABLE plan_item DROP COLUMN content_ref;
             PRAGMA user_version = 9;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the v10 + v11 + v12 + v13 migrations"
    );
    let present: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM pragma_table_info('plan_item') WHERE name = 'theme'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(present, 1, "plan_item.theme column present after upgrade");
}

#[test]
fn a_pre_theme_database_upgrades_and_gains_the_theme_columns() {
    // A v7 DB (no theme columns) must upgrade cleanly — the migrations are additive,
    // so existing rows survive and the new columns read back NULL. Dropping `theme`
    // + resetting to v7 forces v7->v8 (theme) and v8->v9 (custom_theme) to re-run.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "ALTER TABLE session_state DROP COLUMN theme;
             ALTER TABLE session_state DROP COLUMN custom_theme;
             ALTER TABLE plan_item DROP COLUMN theme;
             DROP TABLE saved_theme;
             DROP TABLE screen_theme;
             DROP TABLE screen;
             DROP TABLE screen_output_config;
             DROP TABLE deck;
             DROP TABLE media_asset;
             DROP TABLE providers_setting;
             DROP TABLE detection;
             DROP TABLE transcript_correction;
             DROP TABLE transcript_segment;
             DROP TABLE transcript;
             DROP TABLE transcript_setting;
             DROP TABLE sermon_note;
             ALTER TABLE plan_item DROP COLUMN content_ref;
             PRAGMA user_version = 7;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the v8 + v9 + v10 + v11 + v12 + v13 migrations"
    );
    for col in ["theme", "custom_theme"] {
        let present: i64 = db
            .conn()
            .query_row(
                "SELECT COUNT(*) FROM pragma_table_info('session_state') WHERE name = ?1",
                [col],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(present, 1, "{col} column present after upgrade");
    }
}

#[test]
fn a_pre_pending_regeneration_database_upgrades_and_gains_the_pending_columns() {
    // A v21 DB (sermon_note exists, but with none of the v22 pending_* regeneration
    // columns) must upgrade cleanly to v22 — additive columns, so an EXISTING sermon_note
    // row survives with all its real data intact and the new columns read back NULL (no
    // regeneration pending), exactly the invariant FR-129 depends on: an app that already
    // has drafts saved must not lose or corrupt them merely by upgrading.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let db = Database::open(&path).unwrap();
        // Seed a real transcript + sermon_note row at the CURRENT (post-migration) schema,
        // then downgrade — mirrors how a real pre-upgrade database would have one.
        db.conn()
            .execute_batch(
                "INSERT INTO transcript (id, plan_id, label, provider, started_at, ended_at)
                 VALUES (1, NULL, 'Sunday', 'manual', 1000, 2000);
                 INSERT INTO sermon_note
                     (id, transcript_id, title, summary, sections, scriptures, ai_generated,
                      disclosure, provider, model, created_at, edited_at)
                 VALUES (1, 1, 'A Title', 'A summary', '[]', '[]', 1, 'disc', 'SelahCue AI', NULL, 5000, 5000);",
            )
            .unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "ALTER TABLE sermon_note DROP COLUMN pending_title;
             ALTER TABLE sermon_note DROP COLUMN pending_summary;
             ALTER TABLE sermon_note DROP COLUMN pending_sections;
             ALTER TABLE sermon_note DROP COLUMN pending_scriptures;
             ALTER TABLE sermon_note DROP COLUMN pending_ai_generated;
             ALTER TABLE sermon_note DROP COLUMN pending_disclosure;
             ALTER TABLE sermon_note DROP COLUMN pending_provider;
             ALTER TABLE sermon_note DROP COLUMN pending_model;
             ALTER TABLE sermon_note DROP COLUMN pending_generated_at;
             PRAGMA user_version = 21;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version(),
        "re-ran the v22 migration"
    );
    for col in [
        "pending_title",
        "pending_summary",
        "pending_sections",
        "pending_scriptures",
        "pending_ai_generated",
        "pending_disclosure",
        "pending_provider",
        "pending_model",
        "pending_generated_at",
    ] {
        let present: i64 = db
            .conn()
            .query_row(
                "SELECT COUNT(*) FROM pragma_table_info('sermon_note') WHERE name = ?1",
                [col],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(present, 1, "sermon_note.{col} column present after upgrade");
    }
    // The pre-existing row's own data survives, byte-for-byte, and the new columns read
    // back NULL (no regeneration pending) — never a fabricated default.
    let (title, pending_title): (String, Option<String>) = db
        .conn()
        .query_row(
            "SELECT title, pending_title FROM sermon_note WHERE id = 1",
            [],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .unwrap();
    assert_eq!(
        title, "A Title",
        "pre-existing row data must survive the upgrade"
    );
    assert_eq!(
        pending_title, None,
        "a pre-existing row has no pending regeneration after upgrading"
    );
}

#[test]
fn reopen_is_idempotent() {
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let db = Database::open(&path).unwrap();
        assert_eq!(db.schema_version().unwrap(), migrations::target_version());
    }
    // Reopening an already-migrated database must not re-run migrations.
    let db2 = Database::open(&path).unwrap();
    assert_eq!(db2.schema_version().unwrap(), migrations::target_version());
    db2.integrity_check().unwrap();
}

#[test]
fn refuses_database_from_a_newer_build() {
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    Database::open(&path).unwrap();
    // Simulate a database written by a future build with a higher schema.
    let future = migrations::target_version() + 5;
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(&format!("PRAGMA user_version = {future};"))
        .unwrap();
    drop(conn);
    // Opening it must refuse rather than silently write with the old schema.
    assert!(matches!(
        Database::open(&path),
        Err(DataError::SchemaTooNew { .. })
    ));
}

// ---------------------------------------------------------------------------------------------
// `open_existing_readonly` (86akcffvt review, Sana F1 / Cody Blocker): a caller that reads a
// store it does not own (the operator's Transcripts viewer, reading what `selahcue-desktop`
// alone writes and migrates) must not be able to create, write to, or migrate that store —
// structurally, not just by doc-comment claim. Each test below names exactly which guarantee it
// pins; the mutation check run separately (see the ticket's evidence) confirms swapping the
// constructor back to plain `open` (the pre-fix behaviour) turns (a) and (b) red together, which
// is what proves these are real discriminators and not vacuous assertions.
// ---------------------------------------------------------------------------------------------

#[test]
fn open_existing_readonly_a_creates_nothing_when_the_file_is_absent() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("selahcue.db3");
    assert!(!path.exists(), "premise: no file at this path yet");

    let result = Database::open_existing_readonly(&path);

    assert!(
        matches!(result, Err(DataError::NotFound)),
        "a missing file must be refused, not silently opened"
    );
    assert!(
        !path.exists(),
        "the read-only open must not have created a file at a path that had none"
    );
}

#[test]
fn open_existing_readonly_b_refuses_a_zero_byte_placeholder_and_leaves_it_untouched() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("selahcue.db3");
    // A zero-byte file is exactly the shape a `touch`, an interrupted first write, or an
    // installer-created placeholder leaves behind — and, per db.rs's own doc comment, exactly
    // the shape plain SQLite (even opened read-only) would otherwise treat as a legitimate,
    // brand-new empty database.
    std::fs::write(&path, []).unwrap();
    assert_eq!(
        path.metadata().unwrap().len(),
        0,
        "premise: file is zero bytes"
    );

    let result = Database::open_existing_readonly(&path);

    assert!(
        matches!(result, Err(DataError::NotFound)),
        "a zero-byte file has no SQLite header and must read as 'no store', not 'an empty one'"
    );
    assert_eq!(
        path.metadata().unwrap().len(),
        0,
        "the refused open must not have written anything into the placeholder"
    );
}

#[test]
fn open_existing_readonly_c_reads_a_store_from_a_newer_build_without_migrating_it() {
    // Every migration recorded to date is purely additive (CREATE TABLE / ALTER TABLE ... ADD
    // COLUMN — see migrations.rs's own "append only" contract), so a read-only, non-migrating
    // open against a store whose user_version is AHEAD of this build's target should still
    // succeed and read correctly: there is nothing to protect by refusing it (no write follows),
    // and refusing would only break the reverse case this repo actually hits in practice — an
    // older read-only build pointed at a store a newer sibling build already migrated forward
    // (PR #33 added migration v21 on top of this ticket's v20 in the same shared data directory).
    // The one invariant that must hold is the second half of this test: the version on disk is
    // genuinely left exactly as found, proving no migration ran.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let db = Database::open(&path).unwrap();
        selahcue_data::transcript_repo::create(
            &db,
            &selahcue_data::transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_722_760_800_000,
            },
        )
        .unwrap();
        // Simulate a sibling build's future migration having already run.
        let future = migrations::target_version() + 1;
        db.conn()
            .execute_batch(&format!("PRAGMA user_version = {future};"))
            .unwrap();
    }

    let db = Database::open_existing_readonly(&path).expect("a newer-schema store still opens");

    assert_eq!(
        db.schema_version().unwrap(),
        migrations::target_version() + 1,
        "user_version must be left exactly as found — this path never migrates, forward or back"
    );
    let rows = selahcue_data::transcript_repo::list(&db).unwrap();
    assert_eq!(
        rows.len(),
        1,
        "the transcript written before the version bump is still readable"
    );
}

#[test]
fn open_existing_readonly_d_positive_control_reads_a_real_store() {
    // Positive control (CLAUDE.md bounded-memory discipline): the two refusal tests above are
    // meaningless without proof the SAME constructor still does its one real job — open a
    // genuine, ordinary store and return its data.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let db = Database::open(&path).unwrap();
        selahcue_data::transcript_repo::create(
            &db,
            &selahcue_data::transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_722_760_800_000,
            },
        )
        .unwrap();
    }

    let db = Database::open_existing_readonly(&path).expect("a real, ordinary store opens fine");

    let rows = selahcue_data::transcript_repo::list(&db).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].label, "Sunday Service");
}

#[test]
fn backup_produces_a_loadable_copy() {
    use selahcue_core::plan::{ItemKind, ServicePlan};

    let db = Database::open_in_memory().unwrap();
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Announcement, "Welcome");
    plan.add_item(ItemKind::Song, "Great Are You Lord");
    plan.add_item(ItemKind::Scripture, "Romans 8:28-30");
    let id = selahcue_data::plan_repo::insert(&db, &plan).unwrap();

    let dst = tempfile::NamedTempFile::new().unwrap();
    db.backup_to(dst.path()).unwrap();

    let restored = Database::open(dst.path()).unwrap();
    restored.integrity_check().unwrap();
    let loaded = selahcue_data::plan_repo::load(&restored, id).unwrap();
    assert_eq!(loaded.name, "Sunday Service");
    assert_eq!(loaded.len(), 3);
}
