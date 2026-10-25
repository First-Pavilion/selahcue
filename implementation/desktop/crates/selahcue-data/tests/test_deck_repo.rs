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

// --- the deck-number high-water mark (schema v25; 17tnw2b9arx) ----------------------------------

const ROW: &str = r#"{"name":"x","slides":[],"next_id":1}"#;

fn mark_rows(db: &Database) -> i64 {
    db.conn()
        .query_row("SELECT COUNT(*) FROM deck_id_counter", [], |r| r.get(0))
        .unwrap()
}

#[test]
fn a_database_that_never_recorded_a_number_reads_as_zero() {
    let db = db();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 0);
    assert_eq!(
        mark_rows(&db),
        0,
        "reading the mark must not create the row"
    );
}

#[test]
fn save_one_numbered_writes_the_row_and_raises_the_mark_together() {
    let db = db();
    deck_repo::save_one_numbered(&db, "Welcome", ROW, 1).unwrap();
    deck_repo::save_one_numbered(&db, "Communion", ROW, 3).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 3);
    assert_eq!(deck_repo::load_all(&db).unwrap().len(), 2);
}

#[test]
fn the_mark_only_ever_goes_up_and_deleting_a_deck_leaves_it_alone() {
    let db = db();
    deck_repo::save_one_numbered(&db, "Communion", ROW, 3).unwrap();
    // A lower number (an older deck re-saved) cannot pull it down...
    deck_repo::save_one_numbered(&db, "Welcome", ROW, 1).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 3);
    deck_repo::raise_high_water(&db, 2).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 3);
    // ...and removing the deck that holds the highest number does not either.
    deck_repo::delete_one(&db, "Communion").unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 3);
    deck_repo::raise_high_water(&db, 9).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 9);
}

#[test]
fn the_database_itself_refuses_to_lower_the_mark() {
    let db = db();
    deck_repo::raise_high_water(&db, 5).unwrap();
    let err = db
        .conn()
        .execute("UPDATE deck_id_counter SET high_water = 2", [])
        .expect_err("a direct UPDATE that lowers the mark must be refused");
    assert!(err.to_string().contains("can only be raised"), "{err}");
    assert_eq!(deck_repo::high_water(&db).unwrap(), 5);
    // The table holds one row, however the mark is raised.
    deck_repo::raise_high_water(&db, 6).unwrap();
    assert_eq!(mark_rows(&db), 1);
    assert!(
        db.conn()
            .execute(
                "INSERT INTO deck_id_counter (id, high_water) VALUES (2, 1)",
                []
            )
            .is_err(),
        "only row id 1 may exist"
    );
}

#[test]
fn rename_one_numbered_moves_the_row_and_raises_the_mark_together() {
    let db = db();
    deck_repo::save_one_numbered(&db, "Old", ROW, 1).unwrap();
    deck_repo::rename_one_numbered(&db, "Old", "New", ROW, 4).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 4);
    let rows = deck_repo::load_all(&db).unwrap();
    assert_eq!(rows.len(), 1, "the old row was dropped");
    assert_eq!(rows[0].0, "New");
}

#[test]
fn a_failed_deck_write_leaves_the_mark_where_it_was() {
    // The mark and the row are one transaction: if the row cannot be written the mark must not move,
    // or a number would be retired for a deck that never existed (harmless) -- and, the case that
    // matters, the two could disagree the other way if the order were ever reversed.
    let db = db();
    deck_repo::raise_high_water(&db, 2).unwrap();
    db.conn()
        .execute_batch(
            "CREATE TRIGGER refuse_deck_writes BEFORE INSERT ON deck
             BEGIN SELECT RAISE(ABORT, 'disk says no'); END;",
        )
        .unwrap();
    assert!(deck_repo::save_one_numbered(&db, "Doomed", ROW, 50).is_err());
    assert_eq!(
        deck_repo::high_water(&db).unwrap(),
        2,
        "rolled back with the row"
    );
    assert!(deck_repo::rename_one_numbered(&db, "A", "B", ROW, 60).is_err());
    assert_eq!(deck_repo::high_water(&db).unwrap(), 2);
}

#[test]
fn a_number_beyond_what_sqlite_can_hold_is_clamped_not_a_panic() {
    let db = db();
    deck_repo::save_one_numbered(&db, "Crafted", ROW, u64::MAX).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), i64::MAX as u64);
}

#[test]
fn many_write_and_delete_cycles_keep_the_mark_to_one_row() {
    // Bounded growth: the mark is one integer however many decks come and go.
    let db = db();
    for n in 1..=300u64 {
        let name = format!("Deck {n}");
        deck_repo::save_one_numbered(&db, &name, ROW, n).unwrap();
        deck_repo::delete_one(&db, &name).unwrap();
    }
    assert_eq!(deck_repo::high_water(&db).unwrap(), 300);
    assert_eq!(mark_rows(&db), 1);
    assert!(deck_repo::load_all(&db).unwrap().is_empty());
}
