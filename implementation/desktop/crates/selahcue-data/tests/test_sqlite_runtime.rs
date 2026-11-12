//! Guard the actual linked native library, including the SQLCipher feature path.
#![allow(clippy::unwrap_used)]

use selahcue_data::Database;

#[test]
fn linked_runtime_meets_patched_sqlite_baseline() {
    let db = Database::open_in_memory().unwrap();
    let (version, source): (String, String) = db
        .conn()
        .query_row("SELECT sqlite_version(), sqlite_source_id()", [], |row| {
            Ok((row.get(0)?, row.get(1)?))
        })
        .unwrap();
    println!("SQLite {version}; source_id={source}");
    #[cfg(feature = "encryption")]
    {
        let cipher: String = db
            .conn()
            .query_row("PRAGMA cipher_version", [], |r| r.get(0))
            .unwrap();
        println!("SQLCipher {cipher}");
        assert_eq!(
            cipher.split_whitespace().next(),
            Some("4.20.0"),
            "unexpected SQLCipher source"
        );
    }
    let parts: Vec<u32> = version
        .split('.')
        .map(|part| part.parse().unwrap())
        .collect();
    assert!(
        parts.as_slice() >= [3, 54, 0].as_slice(),
        "linked SQLite {version} predates the WAL zero-fill fix (3.54.0); source_id={source}"
    );
    assert!(
        !source.is_empty(),
        "linked SQLite must report its source identity"
    );
}

#[cfg(feature = "encryption")]
#[test]
fn pre_upgrade_encrypted_backup_preserves_transcript_notes_and_key_behavior() {
    use selahcue_data::{sermon_note_repo, transcript_repo, EncryptionKey};
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("legacy.db3");
    std::fs::copy(
        concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/sqlcipher-4.14.0-backup.db3"
        ),
        &path,
    )
    .unwrap();
    let key = EncryptionKey::from_raw([0x2d; 32]); // Public, synthetic TEST key only.
    let wrong = EncryptionKey::from_raw([0x99; 32]);
    assert!(Database::open_encrypted(&path, &wrong).is_err());
    assert!(Database::open(&path).is_err());
    // Exercise the operator's read-only path before opening the writable store.
    let readonly = Database::open_existing_readonly_encrypted(&path, &key).unwrap();
    assert_eq!(
        transcript_repo::load(&readonly, 1).unwrap().label,
        "Synthetic legacy transcript"
    );
    drop(readonly);
    let db = Database::open_encrypted(&path, &key).unwrap();
    db.integrity_check().unwrap();
    let transcript = transcript_repo::load(&db, 1).unwrap();
    assert_eq!(transcript.label, "Synthetic legacy transcript");
    assert_eq!(transcript.segments.len(), 1);
    assert_eq!(
        transcript.segments[0].text,
        "Synthetic legacy segment: hope and peace."
    );
    let note = sermon_note_repo::find_by_transcript(&db, 1)
        .unwrap()
        .unwrap();
    assert_eq!(note.title, "Synthetic legacy note");
    assert_eq!(note.summary.as_deref(), Some("Synthetic saved summary"));
    assert_eq!(
        note.sections_json,
        r#"[{"heading":"Hope","items":["Synthetic point"],"points":[]}]"#
    );
    assert!(note.ai_generated);
    assert_eq!(
        note.disclosure.as_deref(),
        Some("TEST ONLY: synthetic generated draft")
    );
    let backup = dir.path().join("new-backup.db3");
    db.backup_to_encrypted(&backup, &key).unwrap();
    drop(db);
    assert!(Database::open_encrypted(&backup, &wrong).is_err());
    let restored = Database::open_encrypted(&backup, &key).unwrap();
    restored.integrity_check().unwrap();
    assert_eq!(
        transcript_repo::load(&restored, 1).unwrap().segments[0].text,
        "Synthetic legacy segment: hope and peace."
    );
    assert_eq!(
        sermon_note_repo::find_by_transcript(&restored, 1)
            .unwrap()
            .unwrap()
            .summary
            .as_deref(),
        Some("Synthetic saved summary")
    );
    let bytes = std::fs::read(backup).unwrap();
    assert!(!bytes.starts_with(b"SQLite format 3\0"));
    assert!(!bytes
        .windows(b"Synthetic".len())
        .any(|part| part == b"Synthetic"));
}
