//! Saved-theme library persistence (schema v11; story 86ajq4xmy).

#![allow(clippy::unwrap_used)]

use selahcue_data::{saved_theme_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn library_round_trips_ordered_by_name() {
    let db = db();
    assert!(saved_theme_repo::load_all(&db).unwrap().is_empty());

    // save_all persists the whole set; load_all reads it back ordered by name.
    let themes = vec![
        (
            "Sermon Bold".to_string(),
            r#"{"background":{}}"#.to_string(),
        ),
        ("Announcements".to_string(), r#"{"title":{}}"#.to_string()),
    ];
    saved_theme_repo::save_all(&db, &themes).unwrap();

    let rows = saved_theme_repo::load_all(&db).unwrap();
    assert_eq!(
        rows,
        vec![
            ("Announcements".to_string(), r#"{"title":{}}"#.to_string()),
            (
                "Sermon Bold".to_string(),
                r#"{"background":{}}"#.to_string()
            ),
        ],
        "ordered by name, JSON preserved verbatim"
    );
}

#[test]
fn save_all_replaces_the_whole_set_so_deletions_persist() {
    let db = db();
    saved_theme_repo::save_all(
        &db,
        &[
            ("A".to_string(), "{}".to_string()),
            ("B".to_string(), "{}".to_string()),
            ("C".to_string(), "{}".to_string()),
        ],
    )
    .unwrap();
    assert_eq!(saved_theme_repo::load_all(&db).unwrap().len(), 3);

    // A save mirroring the in-memory map after a delete: B is gone on disk too.
    saved_theme_repo::save_all(
        &db,
        &[
            ("A".to_string(), "{}".to_string()),
            ("C".to_string(), "{}".to_string()),
        ],
    )
    .unwrap();
    let names: Vec<String> = saved_theme_repo::load_all(&db)
        .unwrap()
        .into_iter()
        .map(|(n, _)| n)
        .collect();
    assert_eq!(names, vec!["A".to_string(), "C".to_string()], "B removed");

    // Saving an empty set clears the library entirely.
    saved_theme_repo::save_all(&db, &[]).unwrap();
    assert!(saved_theme_repo::load_all(&db).unwrap().is_empty());
}

#[test]
fn overwriting_a_name_keeps_a_single_row() {
    let db = db();
    saved_theme_repo::save_all(&db, &[("Look".to_string(), r#"{"v":1}"#.to_string())]).unwrap();
    saved_theme_repo::save_all(&db, &[("Look".to_string(), r#"{"v":2}"#.to_string())]).unwrap();
    let rows = saved_theme_repo::load_all(&db).unwrap();
    assert_eq!(rows, vec![("Look".to_string(), r#"{"v":2}"#.to_string())]);
}
