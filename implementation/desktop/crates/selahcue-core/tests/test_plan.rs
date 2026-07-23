//! Integration tests for the service-plan domain model (FR-001/002). Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemId, ItemKind, PlanError, PlanItem, ServicePlan};

#[test]
fn add_assigns_unique_increasing_ids() {
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Announcement, "Welcome");
    let b = p.add_item(ItemKind::Song, "Way Maker");
    assert_eq!(a, ItemId(1));
    assert_eq!(b, ItemId(2));
    assert_eq!(p.len(), 2);
    assert!(!p.is_empty());
}

#[test]
fn ids_are_not_reused_after_removal() {
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Song, "A");
    p.remove(a).unwrap();
    let b = p.add_item(ItemKind::Song, "B");
    assert_ne!(a, b, "removed id must not be reused");
    assert_eq!(b, ItemId(2));
}

#[test]
fn remove_unknown_errors() {
    let mut p = ServicePlan::new("Sunday");
    assert_eq!(p.remove(ItemId(99)), Err(PlanError::NotFound(ItemId(99))));
}

#[test]
fn reorder_moves_item() {
    let mut p = ServicePlan::new("Sunday");
    p.add_item(ItemKind::Song, "A");
    p.add_item(ItemKind::Song, "B");
    p.add_item(ItemKind::Song, "C");
    p.reorder(2, 0).unwrap(); // C to front
    let titles: Vec<_> = p.items().iter().map(|i| i.title.as_str()).collect();
    assert_eq!(titles, ["C", "A", "B"]);
}

#[test]
fn reorder_out_of_bounds_errors() {
    let mut p = ServicePlan::new("Sunday");
    p.add_item(ItemKind::Song, "A");
    assert_eq!(p.reorder(0, 5), Err(PlanError::IndexOutOfBounds));
    assert_eq!(p.reorder(5, 0), Err(PlanError::IndexOutOfBounds));
}

#[test]
fn insert_at_index() {
    let mut p = ServicePlan::new("Sunday");
    p.add_item(ItemKind::Song, "A");
    p.add_item(ItemKind::Song, "C");
    p.insert_item(1, ItemKind::Scripture, "B");
    let titles: Vec<_> = p.items().iter().map(|i| i.title.as_str()).collect();
    assert_eq!(titles, ["A", "B", "C"]);
}

#[test]
fn planned_total_sums_only_set_durations() {
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Announcement, "Welcome");
    let b = p.add_item(ItemKind::Song, "Way Maker");
    p.add_item(ItemKind::Section, "Break"); // no duration
    p.get_mut(a).unwrap().planned_secs = Some(120);
    p.get_mut(b).unwrap().planned_secs = Some(360);
    assert_eq!(p.planned_total_secs(), 480);
}

#[test]
fn duplicate_is_independent() {
    let mut p = ServicePlan::new("Sunday");
    p.add_item(ItemKind::Song, "A");
    let mut copy = p.duplicate("Sunday (copy)");
    copy.add_item(ItemKind::Song, "B");
    assert_eq!(p.len(), 1, "original unchanged");
    assert_eq!(copy.len(), 2);
    assert_eq!(copy.name, "Sunday (copy)");
    // The copy's new item gets a fresh, non-colliding id.
    assert_eq!(copy.items()[1].id, ItemId(2));
}

#[test]
fn item_kind_tag_round_trips() {
    for k in [
        ItemKind::SlideGroup,
        ItemKind::Song,
        ItemKind::Scripture,
        ItemKind::Media,
        ItemKind::Announcement,
        ItemKind::Timer,
        ItemKind::Section,
    ] {
        assert_eq!(ItemKind::from_tag(k.as_tag()), Some(k));
    }
    assert_eq!(ItemKind::from_tag("nonsense"), None);
}

#[test]
fn from_parts_preserves_no_reuse_invariant() {
    let items = vec![PlanItem {
        id: ItemId(7),
        kind: ItemKind::Song,
        title: "A".into(),
        planned_secs: None,
        owner: None,
    }];
    // Even if a too-small next_id is supplied, the next add must not collide.
    let mut p = ServicePlan::from_parts("Rehydrated", items, 1);
    let new = p.add_item(ItemKind::Song, "B");
    assert_eq!(new, ItemId(8)); // clamped to max(id)+1
    assert_eq!(p.next_id(), 9);
}

#[test]
fn get_mut_edits_title_and_owner() {
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Song, "Untitled");
    let item = p.get_mut(a).unwrap();
    item.title = "Great Are You Lord".into();
    item.owner = Some("Worship".into());
    assert_eq!(p.get(a).unwrap().title, "Great Are You Lord");
    assert_eq!(p.get(a).unwrap().owner.as_deref(), Some("Worship"));
}
