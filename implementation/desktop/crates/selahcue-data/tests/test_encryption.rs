//! Integration tests for at-rest encryption (FR-154). Compiled only with the
//! `encryption` feature; run with `cargo test -p selahcue-data --features encryption`.

#![cfg(feature = "encryption")]
#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::sermon_note_repo::{self, NewSermonNote};
use selahcue_data::transcript_repo::{self, NewTranscript};
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
fn encrypted_transcript_round_trips_and_leaves_no_plaintext_on_disk() {
    // FR-154 for the new transcript/segment/detection tables (86ajtxzrn): no per-table
    // wiring exists or is needed — the whole database file is keyed before migrations
    // run, so this table is encrypted at rest exactly like `service_plan` above.
    const MARKER: &str = "PLAINTEXT_MARKER_Habakkuk_Woe_Oracle_Sermon_Transcript";
    let file = tempfile::NamedTempFile::new().unwrap();
    let (transcript_id, seg_id) = {
        let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
        let transcript_id = transcript_repo::create(
            &db,
            &NewTranscript {
                label: MARKER.to_string(),
                provider: "manual".into(),
                plan_id: None,
                started_at_ms: 0,
            },
        )
        .unwrap();
        let seg_id = transcript_repo::append_segment(&db, transcript_id, 0, 1000, MARKER).unwrap();
        transcript_repo::append_detection(&db, transcript_id, Some(seg_id), MARKER, 90).unwrap();
        db.checkpoint_truncate().unwrap();
        (transcript_id, seg_id)
    };

    // Reopening with the correct key returns the data intact.
    let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
    db.integrity_check().unwrap();
    let detail = transcript_repo::load(&db, transcript_id).unwrap();
    assert_eq!(detail.label, MARKER);
    assert_eq!(detail.segments.len(), 1);
    assert_eq!(detail.segments[0].text, MARKER);
    assert_eq!(detail.detections.len(), 1);
    assert_eq!(detail.detections[0].reference, MARKER);
    assert_eq!(detail.detections[0].source_segment, seg_id as u64);
    drop(db);

    // The raw file must not contain the plaintext marker anywhere — label, segment
    // text, and detection reference all carry it, so this exercises every new column.
    let bytes = std::fs::read(file.path()).unwrap();
    assert!(
        !contains(&bytes, MARKER.as_bytes()),
        "transcript/detection plaintext leaked into the encrypted database file"
    );
    assert!(
        !bytes.starts_with(b"SQLite format 3\0"),
        "database header is not encrypted"
    );
}

#[test]
fn encrypted_sermon_note_round_trips_and_leaves_no_plaintext_on_disk() {
    // FR-154 for the `sermon_note` table (86akgqdv0 PR #33 review, Sana N5 — Low,
    // carried from the original round: no `sermon_note` marker existed in this file).
    // Same "no per-table wiring needed" story as the transcript test above — the whole
    // database file is keyed before migrations run — but that posture had never
    // actually been exercised for THIS table's columns until now.
    const MARKER: &str = "PLAINTEXT_MARKER_Nehemiah_Wall_Rebuilding_Sermon_Note";
    let file = tempfile::NamedTempFile::new().unwrap();
    let transcript_id = {
        let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
        let transcript_id = transcript_repo::create(
            &db,
            &NewTranscript {
                label: "svc".into(),
                provider: "manual".into(),
                plan_id: None,
                started_at_ms: 0,
            },
        )
        .unwrap();
        sermon_note_repo::create(
            &db,
            &NewSermonNote {
                transcript_id,
                title: MARKER.to_string(),
                summary: Some(MARKER.to_string()),
                sections_json: format!(r#"[{{"heading":"{MARKER}","items":[],"points":[]}}]"#),
                scriptures_json: "[]".into(),
                ai_generated: true,
                disclosure: Some(MARKER.to_string()),
                provider: "SelahCue AI".into(),
                model: None,
                created_at_ms: 0,
            },
        )
        .unwrap();
        db.checkpoint_truncate().unwrap();
        transcript_id
    };

    // Reopening with the correct key returns the data intact.
    let db = Database::open_encrypted(file.path(), &key_a()).unwrap();
    db.integrity_check().unwrap();
    let note = sermon_note_repo::find_by_transcript(&db, transcript_id)
        .unwrap()
        .unwrap();
    assert_eq!(note.title, MARKER);
    assert_eq!(note.summary.as_deref(), Some(MARKER));
    assert!(note.sections_json.contains(MARKER));
    assert_eq!(note.disclosure.as_deref(), Some(MARKER));
    drop(db);

    // The raw file must not contain the plaintext marker anywhere — title, summary,
    // sections, and disclosure all carry it, so this exercises every text-bearing
    // column this table has.
    let bytes = std::fs::read(file.path()).unwrap();
    assert!(
        !contains(&bytes, MARKER.as_bytes()),
        "sermon-note plaintext leaked into the encrypted database file"
    );
    assert!(
        !bytes.starts_with(b"SQLite format 3\0"),
        "database header is not encrypted"
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
