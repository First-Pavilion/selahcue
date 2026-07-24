//! Output/display assignment persistence (schema v5).

#![allow(clippy::unwrap_used)]

use selahcue_data::{output_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn assignments_round_trip_and_upsert() {
    let db = db();
    assert!(output_repo::load_assignments(&db).unwrap().is_empty());

    output_repo::save_assignment(&db, "main", "DELL U2720Q|3840x2160").unwrap();
    output_repo::save_assignment(&db, "stage", "Color LCD|2560x1600").unwrap();
    // Re-assigning a role replaces its row (one display per role).
    output_repo::save_assignment(&db, "main", "Epson Projector|1920x1080").unwrap();

    let rows = output_repo::load_assignments(&db).unwrap();
    assert_eq!(
        rows,
        vec![
            ("main".to_string(), "Epson Projector|1920x1080".to_string()),
            ("stage".to_string(), "Color LCD|2560x1600".to_string()),
        ]
    );
}

#[test]
fn unknown_roles_are_rejected_by_the_schema() {
    let db = db();
    // The CHECK constraint keeps the table to the two real roles.
    assert!(output_repo::save_assignment(&db, "disco", "X|1x1").is_err());
}
