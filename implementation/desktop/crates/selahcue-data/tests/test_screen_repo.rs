//! Screen-registry persistence (schema v13; Screens page — dynamic registry).

#![allow(clippy::unwrap_used)]

use selahcue_data::{screen_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn registry_round_trips_in_saved_order() {
    let db = db();
    assert!(screen_repo::load_all(&db).unwrap().is_empty());

    // The registry's deterministic order (built-ins first, then a virtual feed) must
    // survive the round-trip — `ordering` is assigned by save position, not sorted by id.
    let rows: Vec<(String, String, bool, bool)> = vec![
        ("main".into(), "main".into(), true, false),
        ("lower-third".into(), "lower-third".into(), false, false),
        ("stream".into(), "stream".into(), true, false),
        ("stage".into(), "stage".into(), true, false),
        ("stream-2".into(), "stream".into(), true, true),
    ];
    screen_repo::save_all(&db, &rows).unwrap();

    let loaded = screen_repo::load_all(&db).unwrap();
    assert_eq!(
        loaded, rows,
        "role/enabled/deletable + insertion order preserved"
    );
    // The disabled + deletable flags round-trip precisely (not coerced).
    assert!(!loaded[1].2, "lower-third stayed disabled");
    assert!(loaded[4].3, "stream-2 stayed deletable (virtual)");
}

#[test]
fn save_all_replaces_the_whole_registry_so_deletes_persist() {
    let db = db();
    screen_repo::save_all(
        &db,
        &[
            ("main".into(), "main".into(), true, false),
            ("stream-2".into(), "stream".into(), true, true),
        ],
    )
    .unwrap();
    assert_eq!(screen_repo::load_all(&db).unwrap().len(), 2);

    // Mirroring the in-memory registry after deleting the virtual screen: it is gone on
    // disk too (a full-set replace, not an upsert).
    screen_repo::save_all(&db, &[("main".into(), "main".into(), false, false)]).unwrap();
    assert_eq!(
        screen_repo::load_all(&db).unwrap(),
        vec![("main".to_string(), "main".to_string(), false, false)],
        "the virtual screen was removed and main's disable persisted"
    );

    // An empty registry clears the table entirely (the loader then recovers to the
    // built-in default in the controller).
    screen_repo::save_all(&db, &[]).unwrap();
    assert!(screen_repo::load_all(&db).unwrap().is_empty());
}

#[test]
fn reassigning_a_screen_keeps_a_single_row() {
    // The screen id is the primary key — toggling enable rewrites the one row, not two.
    let db = db();
    screen_repo::save_all(&db, &[("main".into(), "main".into(), true, false)]).unwrap();
    screen_repo::save_all(&db, &[("main".into(), "main".into(), false, false)]).unwrap();
    assert_eq!(
        screen_repo::load_all(&db).unwrap(),
        vec![("main".to_string(), "main".to_string(), false, false)]
    );
}
