//! Per-screen theme map persistence (schema v12; story 86ajq321k).

#![allow(clippy::unwrap_used)]

use selahcue_data::{screen_theme_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn map_round_trips_ordered_by_screen() {
    let db = db();
    assert!(screen_theme_repo::load_all(&db).unwrap().is_empty());

    let themes = vec![
        ("main".to_string(), "high-contrast".to_string()),
        ("lower-third".to_string(), "lower-third".to_string()),
    ];
    screen_theme_repo::save_all(&db, &themes).unwrap();

    let rows = screen_theme_repo::load_all(&db).unwrap();
    assert_eq!(
        rows,
        vec![
            ("lower-third".to_string(), "lower-third".to_string()),
            ("main".to_string(), "high-contrast".to_string()),
        ],
        "ordered by screen; theme names preserved"
    );
}

#[test]
fn save_all_replaces_the_whole_map_so_clears_persist() {
    let db = db();
    screen_theme_repo::save_all(
        &db,
        &[
            ("main".to_string(), "classic".to_string()),
            ("stream".to_string(), "high-contrast".to_string()),
        ],
    )
    .unwrap();
    assert_eq!(screen_theme_repo::load_all(&db).unwrap().len(), 2);

    // Mirroring the in-memory map after clearing `stream`: it is gone on disk too.
    screen_theme_repo::save_all(&db, &[("main".to_string(), "classic".to_string())]).unwrap();
    assert_eq!(
        screen_theme_repo::load_all(&db).unwrap(),
        vec![("main".to_string(), "classic".to_string())],
        "stream removed"
    );

    // An empty map clears the table entirely.
    screen_theme_repo::save_all(&db, &[]).unwrap();
    assert!(screen_theme_repo::load_all(&db).unwrap().is_empty());
}

#[test]
fn reassigning_a_screen_keeps_a_single_row() {
    let db = db();
    screen_theme_repo::save_all(&db, &[("main".to_string(), "classic".to_string())]).unwrap();
    screen_theme_repo::save_all(&db, &[("main".to_string(), "lower-third".to_string())]).unwrap();
    assert_eq!(
        screen_theme_repo::load_all(&db).unwrap(),
        vec![("main".to_string(), "lower-third".to_string())]
    );
}
