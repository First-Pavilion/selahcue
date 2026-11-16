//! Run only against the documented pre-upgrade dependency, never the new one.
#![cfg(feature = "encryption")]
#![allow(clippy::unwrap_used)]
use selahcue_data::{
    sermon_note_repo::{self, NewSermonNote},
    transcript_repo::{self, NewTranscript},
    Database, EncryptionKey,
};

#[test]
fn create_synthetic_pre_upgrade_backup() {
    let key = EncryptionKey::from_raw([0x2d; 32]);
    let dir = tempfile::tempdir().unwrap();
    let db = Database::open_encrypted(dir.path().join("source.db3"), &key).unwrap();
    let version: String = db
        .conn()
        .query_row("SELECT sqlite_version()", [], |r| r.get(0))
        .unwrap();
    let cipher: String = db
        .conn()
        .query_row("PRAGMA cipher_version", [], |r| r.get(0))
        .unwrap();
    println!(
        "Creating legacy fixture: SQLite {version}, SQLCipher {cipher}, schema {}",
        db.schema_version().unwrap()
    );
    assert_eq!(version, "3.51.3");
    assert_eq!(cipher.split_whitespace().next(), Some("4.14.0"));
    let id = transcript_repo::create(
        &db,
        &NewTranscript {
            label: "Synthetic legacy transcript".into(),
            provider: "manual".into(),
            plan_id: None,
            started_at_ms: 0,
        },
    )
    .unwrap();
    assert_eq!(id, 1);
    transcript_repo::append_segment(
        &db,
        id,
        0,
        1000,
        "Synthetic legacy segment: hope and peace.",
    )
    .unwrap();
    sermon_note_repo::create(
        &db,
        &NewSermonNote {
            transcript_id: id,
            title: "Synthetic legacy note".into(),
            summary: Some("Synthetic saved summary".into()),
            sections_json: r#"[{"heading":"Hope","items":["Synthetic point"],"points":[]}]"#.into(),
            scriptures_json: "[]".into(),
            ai_generated: true,
            disclosure: Some("TEST ONLY: synthetic generated draft".into()),
            provider: "Synthetic fixture".into(),
            model: None,
            created_at_ms: 0,
        },
    )
    .unwrap();
    db.backup_to_encrypted(
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/sqlcipher-4.14.0-backup.db3"
        ),
        &key,
    )
    .unwrap();
}
