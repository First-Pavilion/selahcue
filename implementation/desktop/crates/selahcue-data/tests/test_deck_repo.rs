//! Authored slide-deck library persistence (schema v16; Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_data::{deck_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn deck_library_round_trips_ordered_by_name() {
    let db = db();
    assert!(deck_repo::load_all(&db).unwrap().is_empty());

    let decks = vec![
        (
            "Sermon".to_string(),
            r#"{"name":"Sermon","slides":[],"next_id":1}"#.to_string(),
        ),
        (
            "Announcements".to_string(),
            r#"{"name":"Announcements","slides":[],"next_id":1}"#.to_string(),
        ),
    ];
    deck_repo::save_all(&db, &decks).unwrap();

    let rows = deck_repo::load_all(&db).unwrap();
    assert_eq!(
        rows.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>(),
        vec!["Announcements", "Sermon"],
        "ordered by name"
    );
    assert!(
        rows[1].1.contains("\"name\":\"Sermon\""),
        "the deck JSON is preserved verbatim"
    );
}

#[test]
fn save_all_replaces_the_whole_set_so_deletions_persist() {
    let db = db();
    deck_repo::save_all(
        &db,
        &[
            ("A".to_string(), "{}".to_string()),
            ("B".to_string(), "{}".to_string()),
        ],
    )
    .unwrap();
    assert_eq!(deck_repo::load_all(&db).unwrap().len(), 2);

    // A save mirroring the in-memory library after deleting B.
    deck_repo::save_all(&db, &[("A".to_string(), "{}".to_string())]).unwrap();
    let names: Vec<String> = deck_repo::load_all(&db)
        .unwrap()
        .into_iter()
        .map(|(n, _)| n)
        .collect();
    assert_eq!(names, vec!["A".to_string()], "B removed on disk");

    // Saving an empty set clears the library entirely.
    deck_repo::save_all(&db, &[]).unwrap();
    assert!(deck_repo::load_all(&db).unwrap().is_empty());
}

#[test]
fn a_deck_survives_a_reopen() {
    // Persistence proper: write, drop the handle, reopen the SAME file, read it back.
    let dir = std::env::temp_dir().join(format!("selahcue-deck-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("decks.sqlite");
    let json = r#"{"name":"Grace","slides":[{"id":1}],"next_id":2}"#.to_string();
    {
        let db = Database::open(&path).unwrap();
        deck_repo::save_all(&db, &[("Grace".to_string(), json.clone())]).unwrap();
    }
    {
        let db = Database::open(&path).unwrap();
        let rows = deck_repo::load_all(&db).unwrap();
        assert_eq!(
            rows,
            vec![("Grace".to_string(), json)],
            "the deck survived the reopen"
        );
    }
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn save_one_upserts_by_name_without_touching_others() {
    // Per-deck autosave: save_one inserts a new deck, then updates it in place on a second call
    // (same name), leaving other decks untouched — no whole-set rewrite needed.
    let db = db();
    deck_repo::save_one(&db, "Grace", r#"{"name":"Grace","slides":[],"next_id":1}"#).unwrap();
    deck_repo::save_one(
        &db,
        "Sermon",
        r#"{"name":"Sermon","slides":[],"next_id":1}"#,
    )
    .unwrap();
    // Update "Grace" in place.
    deck_repo::save_one(
        &db,
        "Grace",
        r#"{"name":"Grace","slides":[{"id":1}],"next_id":2}"#,
    )
    .unwrap();
    let rows = deck_repo::load_all(&db).unwrap();
    assert_eq!(rows.len(), 2, "upsert did not add a duplicate row");
    let grace = rows.iter().find(|(n, _)| n == "Grace").unwrap();
    assert!(
        grace.1.contains(r#""id":1"#),
        "the update replaced Grace's json"
    );
    assert!(
        rows.iter()
            .any(|(n, j)| n == "Sermon" && j.contains(r#""next_id":1"#)),
        "Sermon is untouched by the Grace upsert"
    );
}

#[test]
fn delete_one_removes_a_single_deck_and_is_idempotent() {
    let db = db();
    deck_repo::save_one(&db, "Grace", r#"{"name":"Grace","slides":[],"next_id":1}"#).unwrap();
    deck_repo::save_one(
        &db,
        "Sermon",
        r#"{"name":"Sermon","slides":[],"next_id":1}"#,
    )
    .unwrap();
    deck_repo::delete_one(&db, "Grace").unwrap();
    let rows = deck_repo::load_all(&db).unwrap();
    assert_eq!(
        rows.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>(),
        vec!["Sermon"],
        "only Grace was removed"
    );
    // Deleting an absent deck is a no-op, not an error.
    deck_repo::delete_one(&db, "Grace").unwrap();
    assert_eq!(
        deck_repo::load_all(&db).unwrap().len(),
        1,
        "idempotent delete"
    );
}

#[test]
fn rename_one_moves_the_row_atomically() {
    let db = db();
    deck_repo::save_one(&db, "Old", r#"{"name":"Old","slides":[],"next_id":1}"#).unwrap();
    deck_repo::rename_one(
        &db,
        "Old",
        "New",
        r#"{"name":"New","slides":[{"id":1}],"next_id":2}"#,
    )
    .unwrap();
    let rows = deck_repo::load_all(&db).unwrap();
    assert_eq!(
        rows.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>(),
        vec!["New"],
        "old row dropped, new row present — one atomic move"
    );
    assert!(rows[0].1.contains(r#""id":1"#), "the new json was stored");
    // Same-name rename collapses to a content upsert (no drop, no duplicate).
    deck_repo::rename_one(
        &db,
        "New",
        "New",
        r#"{"name":"New","slides":[],"next_id":3}"#,
    )
    .unwrap();
    assert_eq!(
        deck_repo::load_all(&db).unwrap().len(),
        1,
        "same-name rename is an upsert"
    );
}
