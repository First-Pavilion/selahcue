//! Authored slide-deck library persistence (schema v16; Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_data::deck_repo::{self, MAX_DECK_NUMBER};
use selahcue_data::Database;

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
fn a_number_above_the_ceiling_is_refused_not_clamped() {
    // Clamping would record the ceiling and retire every number the database could still issue, so a
    // crafted deck number must be REFUSED. The ceiling itself (2^53 - 1, the largest integer a JSON
    // number holds exactly) is a valid number.
    let db = db();
    deck_repo::raise_high_water(&db, 4).unwrap();
    assert!(deck_repo::save_one_numbered(&db, "Crafted", ROW, u64::MAX).is_err());
    assert!(deck_repo::save_one_numbered(&db, "Crafted", ROW, MAX_DECK_NUMBER + 1).is_err());
    assert!(deck_repo::raise_high_water(&db, 1 << 63).is_err());
    assert_eq!(
        deck_repo::high_water(&db).unwrap(),
        4,
        "refusals leave the mark alone"
    );
    assert!(
        deck_repo::load_all(&db).unwrap().is_empty(),
        "and write no row"
    );
    assert_eq!(MAX_DECK_NUMBER, 9_007_199_254_740_991);
    deck_repo::save_one_numbered(&db, "Last", ROW, MAX_DECK_NUMBER).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), MAX_DECK_NUMBER);
}

/// The row count of every table in the database, by name: what "persisted state" is made of.
fn table_row_counts(db: &Database) -> std::collections::BTreeMap<String, i64> {
    let names: Vec<String> = db
        .conn()
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        .unwrap()
        .query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    names
        .into_iter()
        .map(|n| {
            let c = db
                .conn()
                .query_row(&format!("SELECT COUNT(*) FROM \"{n}\""), [], |r| r.get(0))
                .unwrap();
            (n, c)
        })
        .collect()
}

fn mark_columns(db: &Database) -> Vec<String> {
    db.conn()
        .prepare("SELECT name FROM pragma_table_info('deck_id_counter') ORDER BY cid")
        .unwrap()
        .query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect()
}

#[test]
fn many_write_and_delete_cycles_change_nothing_but_the_deck_table() {
    // Bounded growth: the mark is one integer in one row, however many decks come and go. Counting
    // two tables would miss a log table or a column that grows, so this snapshots EVERY table's row
    // count and the mark's columns before and after (Vera V-01).
    let db = db();
    deck_repo::save_one_numbered(&db, "Keeper", ROW, 1).unwrap();
    let before = table_row_counts(&db);
    assert_eq!(mark_columns(&db), ["id", "high_water"]);
    for n in 2..=301u64 {
        let name = format!("Deck {n}");
        let issued = deck_repo::issue_number(&db, 1).unwrap();
        deck_repo::save_one_numbered(&db, &name, ROW, issued).unwrap();
        deck_repo::delete_one(&db, &name).unwrap();
    }
    assert_eq!(deck_repo::high_water(&db).unwrap(), 301);
    assert_eq!(
        table_row_counts(&db),
        before,
        "no table may have grown, including the mark's own and any table a change might add"
    );
    assert_eq!(
        mark_columns(&db),
        ["id", "high_water"],
        "the mark holds exactly one integer"
    );
    assert_eq!(table_row_counts(&db)["deck_id_counter"], 1);
}

// --- issuing a number (17tnw2b9arx, review round 1) ---------------------------------------------

#[test]
fn issue_number_records_the_number_before_any_deck_row_exists() {
    let db = db();
    assert_eq!(deck_repo::issue_number(&db, 1).unwrap(), 1);
    assert_eq!(deck_repo::high_water(&db).unwrap(), 1);
    assert!(
        deck_repo::load_all(&db).unwrap().is_empty(),
        "no deck row was needed"
    );
    assert_eq!(deck_repo::issue_number(&db, 1).unwrap(), 2);
}

#[test]
fn issue_number_honours_the_callers_lower_bound_and_a_mark_that_is_ahead() {
    let db = db();
    // A mark that is behind or missing: the caller's own bound (one past its highest deck) wins.
    assert_eq!(deck_repo::issue_number(&db, 10).unwrap(), 10);
    assert_eq!(
        deck_repo::issue_number(&db, 3).unwrap(),
        11,
        "the mark is ahead of the bound"
    );
    deck_repo::raise_high_water(&db, 40).unwrap();
    assert_eq!(deck_repo::issue_number(&db, 1).unwrap(), 41);
    assert_eq!(deck_repo::high_water(&db).unwrap(), 41);
}

#[test]
fn two_connections_to_one_file_are_never_issued_the_same_number() {
    let file = tempfile::NamedTempFile::new().unwrap();
    let a = Database::open(file.path()).unwrap();
    let b = Database::open(file.path()).unwrap();
    let mut seen = std::collections::BTreeSet::new();
    for _ in 0..40 {
        for db in [&a, &b] {
            assert!(
                seen.insert(deck_repo::issue_number(db, 1).unwrap()),
                "a number was issued twice"
            );
        }
    }
    assert_eq!(seen.len(), 80);
    assert_eq!(deck_repo::high_water(&a).unwrap(), 80);
}

/// Put a value into the mark that the CHECK would refuse, as a damaged file or a hand edit could.
fn corrupt_the_mark(db: &Database, literal: &str) {
    db.conn()
        .execute_batch(&format!(
            "PRAGMA ignore_check_constraints = ON;
             DELETE FROM deck_id_counter;
             INSERT INTO deck_id_counter (id, high_water) VALUES (1, {literal});
             PRAGMA ignore_check_constraints = OFF;"
        ))
        .unwrap();
}

#[test]
fn an_unreadable_mark_refuses_a_new_number_instead_of_counting_as_zero() {
    for literal in ["'abc'", "12.5", "x'00'", "1e30"] {
        let db = db();
        corrupt_the_mark(&db, literal);
        assert!(
            deck_repo::high_water(&db).is_err(),
            "{literal}: reading it must fail, not read 0"
        );
        assert!(
            deck_repo::issue_number(&db, 1).is_err(),
            "{literal}: no number may be issued against a mark that cannot be read"
        );
        // ...and the damaged value is left for someone to look at, not silently overwritten.
        let still_wrong: String = db
            .conn()
            .query_row("SELECT typeof(high_water) FROM deck_id_counter", [], |r| {
                r.get(0)
            })
            .unwrap();
        assert_ne!(
            still_wrong, "integer",
            "{literal}: the damaged value was overwritten"
        );
    }
}

#[test]
fn the_mark_column_accepts_only_an_integer_within_the_json_safe_range() {
    let db = db();
    let insert = |literal: &str| {
        db.conn()
            .execute("DELETE FROM deck_id_counter", [])
            .unwrap();
        db.conn().execute(
            &format!("INSERT INTO deck_id_counter (id, high_water) VALUES (1, {literal})"),
            [],
        )
    };
    for bad in [
        "'abc'",
        "1e30",
        "x'00'",
        "-1",
        "9007199254740992",
        "NULL",
        "12.5",
    ] {
        assert!(insert(bad).is_err(), "{bad} must be refused by the table");
    }
    // SQLite's INTEGER affinity turns 12.0 into the integer 12 before the check, which is fine.
    insert("12.0").unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 12);
    insert("9007199254740991").unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), MAX_DECK_NUMBER);
}

#[test]
fn numbers_run_out_at_the_ceiling_with_a_refusal_not_a_wrap() {
    let db = db();
    deck_repo::raise_high_water(&db, MAX_DECK_NUMBER).unwrap();
    assert!(
        deck_repo::issue_number(&db, 1).is_err(),
        "nothing is left to issue"
    );
    assert_eq!(deck_repo::high_water(&db).unwrap(), MAX_DECK_NUMBER);
    let fresh = self::db();
    assert!(deck_repo::issue_number(&fresh, MAX_DECK_NUMBER + 1).is_err());
    assert_eq!(
        deck_repo::high_water(&fresh).unwrap(),
        0,
        "a refusal records nothing"
    );
}

// --- review round 2 (17tnw2b9arx) ----------------------------------------------------------------

/// The first v25 definition (before the CHECK on the column's type and range was added in review).
/// It was never released, but a scratch copy that ran the earlier head still has it, and the table is
/// never rebuilt: the ceiling must therefore hold in the CODE, not only in the table.
fn use_the_first_v25_definition(db: &Database, mark: &str) {
    db.conn()
        .execute_batch(&format!(
            "DROP TABLE deck_id_counter;
             CREATE TABLE deck_id_counter (
                 id         INTEGER PRIMARY KEY CHECK (id = 1),
                 high_water INTEGER NOT NULL CHECK (high_water >= 0)
             );
             CREATE TRIGGER deck_id_counter_never_lowers
             BEFORE UPDATE OF high_water ON deck_id_counter
             WHEN NEW.high_water < OLD.high_water
             BEGIN
                 SELECT RAISE(ABORT, 'the deck number high-water mark can only be raised');
             END;
             INSERT INTO deck_id_counter (id, high_water) VALUES (1, {mark});"
        ))
        .unwrap();
}

#[test]
fn issue_number_refuses_a_number_past_the_ceiling_whatever_definition_the_table_has() {
    let db = db();
    use_the_first_v25_definition(&db, "9007199254740991");
    // On this definition nothing in the table stops 2^53 - 1 + 1 = 2^53, which a JSON number cannot
    // hold exactly (it equals 2^53 + 1 in the webview). The code must refuse it, and the refusal must
    // not leave the mark advanced.
    assert!(deck_repo::issue_number(&db, 1).is_err());
    assert_eq!(
        deck_repo::high_water(&db).unwrap(),
        MAX_DECK_NUMBER,
        "rolled back"
    );
    // Right up to the ceiling is fine.
    let db = self::db();
    use_the_first_v25_definition(&db, "9007199254740989");
    assert_eq!(
        deck_repo::issue_number(&db, 1).unwrap(),
        MAX_DECK_NUMBER - 1
    );
    assert_eq!(deck_repo::issue_number(&db, 1).unwrap(), MAX_DECK_NUMBER);
    assert!(deck_repo::issue_number(&db, 1).is_err());
    assert_eq!(deck_repo::high_water(&db).unwrap(), MAX_DECK_NUMBER);
}

#[test]
fn a_damaged_mark_does_not_stop_a_deck_row_from_being_saved_or_renamed() {
    // An unreadable mark must refuse NEW numbers (issue_number, tested above) but it must not turn
    // every edit to an existing deck into a silently lost write: the numbered writers only touch the
    // mark when it is an integer that is behind.
    for literal in ["'abc'", "12.5", "x'00'"] {
        let db = db();
        corrupt_the_mark(&db, literal);
        deck_repo::save_one_numbered(&db, "Edited", ROW, 3)
            .unwrap_or_else(|e| panic!("{literal}: the row write was refused: {e}"));
        deck_repo::rename_one_numbered(&db, "Edited", "Renamed", ROW, 3)
            .unwrap_or_else(|e| panic!("{literal}: the rename was refused: {e}"));
        let names: Vec<String> = deck_repo::load_all(&db)
            .unwrap()
            .into_iter()
            .map(|r| r.0)
            .collect();
        assert_eq!(names, ["Renamed"], "{literal}");
        let kind: String = db
            .conn()
            .query_row("SELECT typeof(high_water) FROM deck_id_counter", [], |r| {
                r.get(0)
            })
            .unwrap();
        assert_ne!(
            kind, "integer",
            "{literal}: the damaged value is left for someone to look at"
        );
    }
}

#[test]
fn delete_one_numbered_removes_the_row_and_records_the_retirement_together() {
    let db = db();
    deck_repo::save_one(&db, "Legacy", ROW).unwrap(); // a row from before the mark: nothing recorded
    assert_eq!(deck_repo::high_water(&db).unwrap(), 0);
    deck_repo::delete_one_numbered(&db, "Legacy", 7).unwrap();
    assert!(deck_repo::load_all(&db).unwrap().is_empty());
    assert_eq!(
        deck_repo::high_water(&db).unwrap(),
        7,
        "the deleted deck's number is retired"
    );
    // A lower number never lowers it, and an absent name is still fine (idempotent delete).
    deck_repo::delete_one_numbered(&db, "Nobody", 2).unwrap();
    assert_eq!(deck_repo::high_water(&db).unwrap(), 7);
}

#[test]
fn a_failed_delete_leaves_the_mark_where_it_was() {
    let db = db();
    deck_repo::save_one_numbered(&db, "Keeper", ROW, 1).unwrap();
    db.conn()
        .execute_batch(
            "CREATE TRIGGER refuse_deck_deletes BEFORE DELETE ON deck
             BEGIN SELECT RAISE(ABORT, 'disk says no'); END;",
        )
        .unwrap();
    assert!(deck_repo::delete_one_numbered(&db, "Keeper", 50).is_err());
    assert_eq!(deck_repo::high_water(&db).unwrap(), 1);
    assert_eq!(deck_repo::load_all(&db).unwrap().len(), 1);
}
