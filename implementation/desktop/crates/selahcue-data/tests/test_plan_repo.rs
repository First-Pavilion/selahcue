//! Integration tests for `plan_repo` — round-trip fidelity, item ordering,
//! cascade delete, and corruption handling. Public API only.

#![allow(clippy::unwrap_used)]

use rusqlite::params;
use selahcue_core::plan::{ItemId, ItemKind, ServicePlan};
use selahcue_data::plan_repo::{self, delete, insert, list, load};
use selahcue_data::{DataError, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

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
fn round_trips_a_per_item_theme_override() {
    // S8-3d: a plan item's per-item theme override persists + reloads; an item with no
    // override reloads as `None` (the global theme). Full PlanItem equality covers it.
    let db = Database::open_in_memory().unwrap();
    let mut p = ServicePlan::new("Themed");
    let a = p.add_item(ItemKind::Scripture, "John 3:16");
    let b = p.add_item(ItemKind::Announcement, "Notices");
    p.set_item_theme(a, Some("lower-third".into())).unwrap();
    let id = insert(&db, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    assert_eq!(loaded, p, "the per-item theme override round-trips");
    assert_eq!(
        loaded.get(a).unwrap().theme.as_deref(),
        Some("lower-third"),
        "overridden item keeps its theme"
    );
    assert_eq!(
        loaded.get(b).unwrap().theme,
        None,
        "un-overridden item is None"
    );
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

#[test]
fn update_replaces_items_atomically_and_survives_reload() {
    let db = db();
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "A");
    plan.add_item(ItemKind::Section, "B");
    let id = plan_repo::insert(&db, &plan).unwrap();

    // Edit: rename, remove one, add two, reorder — then persist via update.
    plan.add_item(ItemKind::Scripture, "C");
    let first = plan.items()[0].id;
    plan.remove(first).unwrap();
    plan.add_item(ItemKind::Song, "D");
    plan.reorder(0, 1).unwrap();
    plan_repo::update(&db, id, &plan).unwrap();

    let loaded = plan_repo::load(&db, id).unwrap();
    assert_eq!(loaded, plan, "update round-trips the edited plan exactly");
    assert!(
        plan_repo::update(&db, 9999, &plan).is_err(),
        "unknown plan errors"
    );
}

#[test]
fn library_search_and_duplicate() {
    let db = db();
    for name in ["Sunday AM", "Sunday PM", "Christmas Eve"] {
        plan_repo::insert(&db, &ServicePlan::new(name)).unwrap();
    }
    let hits = plan_repo::search(&db, "Sunday").unwrap();
    assert_eq!(hits.len(), 2);
    let all = plan_repo::search(&db, "").unwrap();
    assert_eq!(all.len(), 3);

    let dup = plan_repo::duplicate(&db, hits[0].id, "Sunday AM (copy)").unwrap();
    let copy = plan_repo::load(&db, dup).unwrap();
    assert_eq!(copy.name, "Sunday AM (copy)");
}

#[test]
fn library_search_is_fast_at_5k_plans() {
    // Story acceptance: library search <300ms at 5k plans.
    let db = db();
    for i in 0..5000u32 {
        plan_repo::insert(&db, &ServicePlan::new(format!("Plan {i}"))).unwrap();
    }
    let start = std::time::Instant::now();
    let hits = plan_repo::search(&db, "Plan 49").unwrap();
    let elapsed = start.elapsed();
    assert_eq!(
        hits.len(),
        111,
        "matches 'Plan 49' + 'Plan 490'..'499' + 'Plan 4900'..'4999'"
    );
    assert!(
        elapsed < std::time::Duration::from_millis(300),
        "library search exceeded 300ms: {elapsed:?}"
    );
}

#[test]
fn library_search_treats_like_wildcards_as_literals() {
    let db = db();
    plan_repo::insert(&db, &ServicePlan::new("100% Praise")).unwrap();
    plan_repo::insert(&db, &ServicePlan::new("Christmas Eve")).unwrap();
    plan_repo::insert(&db, &ServicePlan::new("youth_night")).unwrap();

    // `%` and `_` in the query are literal characters, not LIKE wildcards: a `%`
    // query must not match everything, and `_` must not match any-one-char.
    let hits = plan_repo::search(&db, "100%").unwrap();
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0].name, "100% Praise");
    let hits = plan_repo::search(&db, "h_n").unwrap();
    assert_eq!(hits.len(), 1, "'_' is literal — must not match 'has' etc.");
    assert_eq!(hits[0].name, "youth_night");
    assert!(plan_repo::search(&db, "\\").unwrap().is_empty());
}

// --- Songs: stanza content persistence + backfill (story S8-1, migration v6) ---

#[test]
fn song_stanza_content_round_trips_through_the_store() {
    use selahcue_core::plan::Stanza;
    let db = db();
    let mut p = ServicePlan::new("Sunday");
    let s = p.add_item(ItemKind::Song, "Great Are You Lord");
    p.get_mut(s).unwrap().stanzas = vec![
        Stanza {
            lines: vec!["Great are You Lord".into(), "It's Your breath".into()],
        },
        Stanza {
            lines: vec!["So we pour out our praise".into()],
        },
    ];
    let id = insert(&db, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    let item = &loaded.items()[0];
    assert_eq!(item.slide_count(), 2, "two stanzas survive the round-trip");
    assert_eq!(item.stanzas[0].lines[0], "Great are You Lord");
    assert_eq!(item.stanzas[1].lines[0], "So we pour out our praise");
    // A title-only item alongside keeps NULL content (no phantom stanzas).
    // (add a plain item and re-load to prove the backfill semantics)
    let mut p2 = ServicePlan::new("Plain");
    p2.add_item(ItemKind::Announcement, "Welcome");
    let id2 = insert(&db, &p2).unwrap();
    assert!(load(&db, id2).unwrap().items()[0].stanzas.is_empty());
}

#[test]
fn update_preserves_stanza_content_atomically() {
    use selahcue_core::plan::Stanza;
    let db = db();
    let mut p = ServicePlan::new("Sunday");
    let s = p.add_item(ItemKind::Song, "Way Maker");
    p.get_mut(s).unwrap().stanzas = vec![Stanza {
        lines: vec!["Way maker".into()],
    }];
    let id = insert(&db, &p).unwrap();
    // Edit: add a second stanza and persist via update (DELETE-then-INSERT path).
    p.get_mut(s).unwrap().stanzas.push(Stanza {
        lines: vec!["Miracle worker".into()],
    });
    plan_repo::update(&db, id, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    assert_eq!(loaded.items()[0].slide_count(), 2);
    assert_eq!(loaded.items()[0].stanzas[1].lines[0], "Miracle worker");
}

#[test]
fn a_pre_v6_row_with_null_content_loads_as_a_title_only_item() {
    // Simulate an existing store: insert a plan, then NULL its content column
    // directly (as a v5 row would have no content) and confirm it loads clean.
    let db = db();
    let mut p = ServicePlan::new("Legacy");
    p.add_item(ItemKind::Song, "Old Song");
    let id = insert(&db, &p).unwrap();
    db.conn()
        .execute(
            "UPDATE plan_item SET content = NULL WHERE plan_id = ?1",
            params![id],
        )
        .unwrap();
    let loaded = load(&db, id).unwrap();
    assert!(loaded.items()[0].stanzas.is_empty());
    assert_eq!(loaded.items()[0].slide_count(), 1);
    assert_eq!(loaded.items()[0].title, "Old Song");
}

#[test]
fn load_is_bounded_to_max_plan_items() {
    // Audit M2: a corrupt/oversized persisted plan must not materialize an unbounded number
    // of rows on reload. Persist MAX_PLAN_ITEMS + extra (via the trusted, uncapped domain
    // add_item), then assert the reload stops at the cap.
    use selahcue_core::plan::MAX_PLAN_ITEMS;
    let db = db();
    let mut p = ServicePlan::new("Oversized");
    for i in 0..(MAX_PLAN_ITEMS + 25) {
        p.add_item(ItemKind::Song, format!("Item {i}"));
    }
    let id = insert(&db, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    assert_eq!(
        loaded.len(),
        MAX_PLAN_ITEMS,
        "reload is capped at MAX_PLAN_ITEMS"
    );
}

#[test]
fn round_trips_a_linked_content_reference() {
    // ADR-0020 follow-up: a plan item's linked content (scripture ref / deck / media)
    // persists + reloads; an unlinked item reloads as `None`. Full PlanItem equality
    // (incl. the new `content` field) covers it.
    use selahcue_core::plan::ItemContent;
    let db = Database::open_in_memory().unwrap();
    let mut p = ServicePlan::new("Linked");
    let scr = p.add_item(ItemKind::Scripture, "Romans");
    let deck = p.add_item(ItemKind::SlideGroup, "Sermon");
    let med = p.add_item(ItemKind::Media, "Testimony");
    let _bare = p.add_item(ItemKind::Song, "Opening"); // stays unlinked
    p.set_item_content(
        scr,
        Some(ItemContent::Scripture {
            reference: "Romans 8:28-30".into(),
            translation: Some("WEB".into()),
            verses_per_slide: Some(2),
            verse_numbers: None,
        }),
    )
    .unwrap();
    p.set_item_content(
        deck,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: None,
        }),
    )
    .unwrap();
    p.set_item_content(med, Some(ItemContent::Media { media_id: 4 }))
        .unwrap();

    let id = insert(&db, &p).unwrap();
    let loaded = load(&db, id).unwrap();
    assert_eq!(loaded, p, "every linked content reference round-trips");

    // And it survives the atomic update/replace path too.
    let mut edited = loaded;
    edited
        .set_item_content(
            deck,
            Some(ItemContent::Deck {
                deck_id: 99,
                slide_count: None,
                label: None,
            }),
        )
        .unwrap();
    plan_repo::update(&db, id, &edited).unwrap();
    assert_eq!(
        load(&db, id).unwrap(),
        edited,
        "update replaces the reference"
    );
}
