//! Media library persistence (schema v17; Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_core::media::{MediaAsset, MediaId, MediaKind};
use selahcue_data::{media_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

fn asset(id: u64, path: &str, kind: MediaKind) -> MediaAsset {
    MediaAsset {
        id: MediaId(id),
        path: path.to_string(),
        kind,
        size_bytes: 2_400_000,
        width: None,
        height: None,
        duration_ms: None,
        imported_at: 1000,
    }
}

#[test]
fn assets_round_trip_ordered_by_id_with_all_fields() {
    let db = db();
    assert!(media_repo::load_all(&db).unwrap().is_empty());

    let img = MediaAsset {
        width: Some(1920),
        height: Some(1080),
        ..asset(1, "harvest.jpg", MediaKind::Image)
    };
    let vid = MediaAsset {
        width: Some(1280),
        height: Some(720),
        duration_ms: Some(134_000),
        ..asset(2, "testimony.mp4", MediaKind::Video)
    };
    let aud = MediaAsset {
        duration_ms: Some(200_000),
        ..asset(3, "pad.wav", MediaKind::Audio)
    };
    media_repo::save_all(&db, &[img.clone(), vid.clone(), aud.clone()]).unwrap();

    let rows = media_repo::load_all(&db).unwrap();
    assert_eq!(
        rows,
        vec![img, vid, aud],
        "every field round-trips, ordered by id"
    );
}

#[test]
fn nullable_columns_preserve_absent_metadata() {
    // An image has no duration; an audio track has no pixel dimensions — the NULL columns must
    // come back as None, not 0.
    let db = db();
    let img = MediaAsset {
        width: Some(800),
        height: Some(600),
        ..asset(1, "a.jpg", MediaKind::Image)
    };
    let aud = MediaAsset {
        duration_ms: Some(9_000),
        ..asset(2, "b.wav", MediaKind::Audio)
    };
    media_repo::save_all(&db, &[img, aud]).unwrap();
    let rows = media_repo::load_all(&db).unwrap();
    assert_eq!(rows[0].duration_ms, None, "image duration stays None");
    assert_eq!(
        (rows[1].width, rows[1].height),
        (None, None),
        "audio dims stay None"
    );
}

#[test]
fn save_all_replaces_the_whole_set_so_removals_persist() {
    let db = db();
    media_repo::save_all(
        &db,
        &[
            asset(1, "a", MediaKind::Image),
            asset(2, "b", MediaKind::Image),
            asset(3, "c", MediaKind::Image),
        ],
    )
    .unwrap();
    assert_eq!(media_repo::load_all(&db).unwrap().len(), 3);

    media_repo::save_all(&db, &[asset(1, "a", MediaKind::Image)]).unwrap();
    let ids: Vec<MediaId> = media_repo::load_all(&db)
        .unwrap()
        .into_iter()
        .map(|a| a.id)
        .collect();
    assert_eq!(ids, vec![MediaId(1)], "the removed assets are gone on disk");

    media_repo::save_all(&db, &[]).unwrap();
    assert!(
        media_repo::load_all(&db).unwrap().is_empty(),
        "empty set clears the library"
    );
}

#[test]
fn a_row_with_an_unknown_kind_is_dropped_not_fatal() {
    // Forward-compat: an old build that wrote a kind this build doesn't know must not crash the
    // load — the unrecognised row is silently dropped.
    let db = db();
    media_repo::save_all(&db, &[asset(1, "known.jpg", MediaKind::Image)]).unwrap();
    db.conn()
        .execute(
            "INSERT INTO media_asset (id, path, kind, size_bytes, imported_at) \
             VALUES (2, 'future.xyz', 'hologram', 5, 0)",
            [],
        )
        .unwrap();
    let rows = media_repo::load_all(&db).unwrap();
    assert_eq!(rows.len(), 1, "the unknown-kind row is dropped");
    assert_eq!(rows[0].id, MediaId(1), "the known asset still loads");
}

#[test]
fn the_library_survives_a_reopen() {
    let dir = std::env::temp_dir().join(format!("selahcue-media-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("media.sqlite");
    let a = MediaAsset {
        width: Some(1920),
        height: Some(1080),
        ..asset(7, "harvest.jpg", MediaKind::Image)
    };
    {
        let db = Database::open(&path).unwrap();
        media_repo::save_all(&db, std::slice::from_ref(&a)).unwrap();
    }
    {
        let db = Database::open(&path).unwrap();
        assert_eq!(
            media_repo::load_all(&db).unwrap(),
            vec![a],
            "the library survived the reopen"
        );
    }
    std::fs::remove_dir_all(&dir).ok();
}
