//! Integration tests for at-rest encryption (FR-154). Compiled only with the
//! `encryption` feature; run with `cargo test -p selahcue-data --features encryption`.

#![cfg(feature = "encryption")]
#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::{plan_repo, Database, EncryptionKey};

fn key_a() -> EncryptionKey {
    EncryptionKey::from_raw([0x2d; 32])
}

fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    !needle.is_empty() && haystack.windows(needle.len()).any(|w| w == needle)
}

#[test]
fn encrypted_db_round_trips_and_leaves_no_plaintext_on_disk() {
    // A distinctive marker we can then search the raw file for.
    const MARKER: &str = "PLAINTEXT_MARKER_Zephaniah_Sunday_Service";
    let file = tempfile::NamedTempFile::new().unwrap();
    {
        let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
        let mut p = ServicePlan::new(MARKER);
        p.add_item(ItemKind::Scripture, MARKER);
        plan_repo::insert(&db, &p).unwrap();
        // Flush the WAL into the main file so the on-disk scan is meaningful.
        db.checkpoint_truncate().unwrap();
    }

    // Reopening with the correct key returns the data intact.
    let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
    db.integrity_check().unwrap();
    let plans = plan_repo::list(&db).unwrap();
    assert_eq!(plans.len(), 1);
    assert_eq!(plans[0].name, MARKER);
    drop(db);

    // The raw file must not contain the plaintext marker, and SQLCipher
    // encrypts the header too (a plain SQLite file starts with this magic).
    let bytes = std::fs::read(file.path()).unwrap();
    assert!(
        !contains(&bytes, MARKER.as_bytes()),
        "plaintext leaked into the encrypted database file"
    );
    assert!(
        !bytes.starts_with(b"SQLite format 3\0"),
        "database header is not encrypted"
    );
}

#[test]
fn encrypted_backup_round_trips_and_stays_encrypted() {
    // Regression test for the crash-safe backup path under encryption (FR-079 +
    // FR-154): the plain `backup_to` opens the destination unkeyed and fails on an
    // encrypted source, so `backup_to_encrypted` keys the destination first.
    const MARKER: &str = "BACKUP_MARKER_Habakkuk_Praise_Offering";
    let src = tempfile::NamedTempFile::new().unwrap();
    let dst = tempfile::NamedTempFile::new().unwrap();
    {
        let db = Database::open_encrypted(src.path(), &key_a()).unwrap();
        let mut p = ServicePlan::new(MARKER);
        p.add_item(ItemKind::Song, MARKER);
        plan_repo::insert(&db, &p).unwrap();
        // Online backup of the live encrypted DB, keyed with the same key.
        db.backup_to_encrypted(dst.path(), &key_a()).unwrap();
    }

    // The backup opens with the same key, passes integrity, and has the data.
    let restored = Database::open_encrypted(dst.path(), &key_a()).unwrap();
    restored.integrity_check().unwrap();
    let plans = plan_repo::list(&restored).unwrap();
    assert_eq!(plans.len(), 1);
    assert_eq!(plans[0].name, MARKER);
    drop(restored);

    // The backup file is itself encrypted — no plaintext, no SQLite header magic.
    let bytes = std::fs::read(dst.path()).unwrap();
    assert!(
        !contains(&bytes, MARKER.as_bytes()),
        "backup leaked plaintext to disk"
    );
    assert!(
        !bytes.starts_with(b"SQLite format 3\0"),
        "backup header is not encrypted"
    );
}

#[test]
fn wrong_key_is_rejected() {
    let file = tempfile::NamedTempFile::new().unwrap();
    {
        let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
        plan_repo::insert(&db, &ServicePlan::new("Secret")).unwrap();
        db.checkpoint_truncate().unwrap();
    }
    // A different key cannot decrypt the header → open must fail.
    let wrong = EncryptionKey::from_raw([0x99; 32]);
    assert!(
        Database::open_encrypted(file.path(), &wrong).is_err(),
        "a wrong key must not open the database"
    );
}

#[test]
fn plain_open_of_encrypted_db_fails() {
    let file = tempfile::NamedTempFile::new().unwrap();
    {
        let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
        db.checkpoint_truncate().unwrap();
    }
    // Opening an encrypted database with no key at all must fail, not silently
    // return garbage.
    assert!(
        Database::open(file.path()).is_err(),
        "an unkeyed open of an encrypted database must fail"
    );
}

#[test]
fn in_memory_encrypted_round_trips() {
    // The keyed in-memory path (no disk, no WAL sidecar) still opens, migrates,
    // and round-trips.
    let db = Database::open_in_memory_encrypted(&key_a()).unwrap();
    db.integrity_check().unwrap();
    let mut p = ServicePlan::new("Ephemeral");
    p.add_item(ItemKind::Section, "Sermon");
    let id = plan_repo::insert(&db, &p).unwrap();
    let loaded = plan_repo::load(&db, id).unwrap();
    assert_eq!(loaded.name, "Ephemeral");
    assert_eq!(loaded.len(), 1);
}
