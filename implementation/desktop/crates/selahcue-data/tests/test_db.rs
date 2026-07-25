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
    // accidental reorder/removal is caught. v8 = session_state.theme (S8-3b).
    assert_eq!(migrations::target_version(), 8);
}

#[test]
fn a_pre_theme_database_upgrades_and_gains_the_theme_column() {
    // A v7 DB (no `theme` column) must upgrade cleanly to v8 — the migration is
    // additive, so existing rows survive and the new column reads back NULL.
    let file = tempfile::NamedTempFile::new().unwrap();
    let path = file.path().to_path_buf();
    {
        let _ = Database::open(&path).unwrap();
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch("ALTER TABLE session_state DROP COLUMN theme; PRAGMA user_version = 7;")
            .unwrap();
    }
    let db = Database::open(&path).unwrap();
    assert_eq!(db.schema_version().unwrap(), 8, "re-ran the v8 migration");
    let has_theme: i64 = db
        .conn()
        .query_row(
            "SELECT COUNT(*) FROM pragma_table_info('session_state') WHERE name = 'theme'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(has_theme, 1, "theme column present after upgrade");
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
