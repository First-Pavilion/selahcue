//! Integration tests for `plan_repo` — round-trip fidelity, item ordering,
//! cascade delete, and corruption handling. Public API only.

#![allow(clippy::unwrap_used)]

use rusqlite::params;
use selahcue_core::plan::{ItemId, ItemKind, ServicePlan};
use selahcue_data::plan_repo::{delete, insert, list, load};
use selahcue_data::{DataError, Database};

fn sample_plan() -> ServicePlan {
    let mut p = ServicePlan::new("Sunday Service");
    let a = p.add_item(ItemKind::Announcement, "Welcome");
    let b = p.add_item(ItemKind::Song, "Great Are You Lord");
    p.add_item(ItemKind::Scripture, "Romans 8:28-30");
    p.get_mut(a).unwrap().planned_secs = Some(120);
    p.get_mut(b).unwrap().owner = Some("Worship".into());
    p
}

#[test]
fn round_trips_a_plan_faithfully() {
    let db = Database::open_in_memory().unwrap();
    let original = sample_plan();
    let id = insert(&db, &original).unwrap();
    let loaded = load(&db, id).unwrap();
    // Equality covers name, every item (id/kind/title/planned/owner), order, and next_id.
    assert_eq!(loaded, original);
    // The rehydrated plan keeps the no-reuse invariant.
    let mut loaded = loaded;
    assert_eq!(loaded.add_item(ItemKind::Section, "X"), ItemId(4));
}

#[test]
fn preserves_item_order() {
    let db = Database::open_in_memory().unwrap();
    let mut p = ServicePlan::new("Order");
    for t in ["A", "B", "C", "D"] {
        p.add_item(ItemKind::Song, t);
    }
    p.reorder(3, 0).unwrap(); // D to front
    let id = insert(&db, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    let titles: Vec<_> = loaded.items().iter().map(|i| i.title.as_str()).collect();
    assert_eq!(titles, ["D", "A", "B", "C"]);
}

#[test]
fn list_and_delete() {
    let db = Database::open_in_memory().unwrap();
    let id1 = insert(&db, &ServicePlan::new("First")).unwrap();
    let _id2 = insert(&db, &ServicePlan::new("Second")).unwrap();
    let listed = list(&db).unwrap();
    assert_eq!(listed.len(), 2);
    assert_eq!(listed[0].name, "First");

    delete(&db, id1).unwrap();
    let remaining = list(&db).unwrap();
    assert_eq!(remaining.len(), 1);
    assert_eq!(remaining[0].name, "Second");
    // Deleting the same plan again errors NotFound.
    assert!(matches!(delete(&db, id1), Err(DataError::NotFound)));
}

#[test]
fn delete_missing_errors() {
    let db = Database::open_in_memory().unwrap();
    assert!(matches!(delete(&db, 999), Err(DataError::NotFound)));
}

#[test]
fn deleting_plan_cascades_items() {
    let db = Database::open_in_memory().unwrap();
    let id = insert(&db, &sample_plan()).unwrap();
    delete(&db, id).unwrap();
    // Items are gone (cascade); loading errors NotFound.
    assert!(matches!(load(&db, id), Err(DataError::NotFound)));
    let orphan_items: i64 = db
        .conn()
        .query_row("SELECT COUNT(*) FROM plan_item", [], |r| r.get(0))
        .unwrap();
    assert_eq!(orphan_items, 0);
}

#[test]
fn corrupt_kind_tag_is_reported() {
    let db = Database::open_in_memory().unwrap();
    let id = insert(&db, &ServicePlan::new("Bad")).unwrap();
    db.conn()
        .execute(
            "INSERT INTO plan_item (plan_id, item_id, ord, kind, title) VALUES (?1, 1, 0, 'gibberish', 'X')",
            params![id],
        )
        .unwrap();
    assert!(matches!(load(&db, id), Err(DataError::Corrupt(_))));
}

#[test]
fn out_of_range_planned_secs_is_reported_not_truncated() {
    let db = Database::open_in_memory().unwrap();
    let id = insert(&db, &ServicePlan::new("Bad")).unwrap();
    // A stored planned_secs beyond u32 must surface as corruption, not wrap.
    db.conn()
        .execute(
            "INSERT INTO plan_item (plan_id, item_id, ord, kind, title, planned_secs)
             VALUES (?1, 1, 0, 'song', 'X', ?2)",
            params![id, i64::from(u32::MAX) + 1],
        )
        .unwrap();
    assert!(matches!(load(&db, id), Err(DataError::Corrupt(_))));
}
