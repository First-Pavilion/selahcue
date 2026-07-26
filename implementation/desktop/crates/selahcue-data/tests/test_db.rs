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
    // v11 = saved_theme library table (86ajq4xmy).
    assert_eq!(migrations::target_version(), 11);
}

#[test]
fn a_pre_saved_theme_database_upgrades_and_gains_the_saved_theme_table() {
    // A v10 DB (no saved_theme table) must upgrade cleanly to v11 — a fresh table, so
    // existing data survives and the library simply starts empty. Dropping the table
    // + resetting to v10 forces the v10->v11 migration to re-run.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(
            "DROP TABLE saved_theme;
             PRAGMA user_version = 10;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(db.schema_version().unwrap(), 11, "re-ran the v11 migration");
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
             PRAGMA user_version = 9;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        11,
        "re-ran the v10 + v11 migrations"
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
             PRAGMA user_version = 7;",
        )
        .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(
        db.schema_version().unwrap(),
        11,
        "re-ran the v8 + v9 + v10 + v11 migrations"
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
