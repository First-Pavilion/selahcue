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
        stanzas: Vec::new(),
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

// --- Songs: stanza content + plain-text import (story S8-1) ---

use selahcue_core::plan::{stanzas_from_text, stanzas_to_text, Stanza};

#[test]
fn slide_count_is_one_for_a_title_only_item_and_stanza_count_for_a_song() {
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Announcement, "Welcome");
    // A brand-new item has no stanzas → renders as its single title slide.
    assert_eq!(p.get(a).unwrap().slide_count(), 1);
    let s = p.add_item(ItemKind::Song, "Way Maker");
    p.get_mut(s).unwrap().stanzas = vec![
        Stanza {
            lines: vec!["v1".into()],
        },
        Stanza {
            lines: vec!["v2".into()],
        },
        Stanza {
            lines: vec!["v3".into()],
        },
    ];
    assert_eq!(p.get(s).unwrap().slide_count(), 3);
}

#[test]
fn stanzas_from_text_splits_on_blank_lines_and_is_total() {
    let text = "Line 1a\nLine 1b\n\nLine 2a\n\n\nLine 3a\nLine 3b";
    let st = stanzas_from_text(text);
    assert_eq!(st.len(), 3, "three stanzas (double-blank runs collapse)");
    assert_eq!(st[0].lines, vec!["Line 1a", "Line 1b"]);
    assert_eq!(st[1].lines, vec!["Line 2a"]);
    assert_eq!(st[2].lines, vec!["Line 3a", "Line 3b"]);
    // Total: empty / whitespace-only input yields zero stanzas, never panics.
    assert!(stanzas_from_text("").is_empty());
    assert!(stanzas_from_text("   \n\t\n  ").is_empty());
}

#[test]
fn stanzas_text_round_trips_through_serialize_and_parse() {
    let original = "Great are You Lord\nIt's Your breath in our lungs\n\nSo we pour out our praise";
    let parsed = stanzas_from_text(original);
    let serialized = stanzas_to_text(&parsed);
    // Re-parsing the serialized form yields identical stanzas (lossless).
    assert_eq!(stanzas_from_text(&serialized), parsed);
    assert_eq!(serialized, original);
}

#[test]
fn stanzas_from_text_normalizes_crlf_and_trims() {
    let st = stanzas_from_text("  A line  \r\n\r\n  B line\r\n");
    assert_eq!(st.len(), 2);
    assert_eq!(st[0].lines, vec!["A line"]);
    assert_eq!(st[1].lines, vec!["B line"]);
}
