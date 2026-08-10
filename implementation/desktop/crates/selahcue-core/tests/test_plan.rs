//! Integration tests for the service-plan domain model (FR-001/002). Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemContent, ItemId, ItemKind, PlanError, PlanItem, ServicePlan};

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
        theme: None,
        content: None,
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
fn slide_count_is_one_for_a_scripture_linked_item_even_with_stanzas() {
    let mut p = ServicePlan::new("Sunday");
    let s = p.add_item(ItemKind::Song, "Hybrid");
    {
        let item = p.get_mut(s).unwrap();
        item.stanzas = vec![
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
        item.content = Some(ItemContent::Scripture {
            reference: "John 3:16".into(),
            translation: None,
            verses_per_slide: None,
        });
    }
    // A scripture link renders one passage slide, so it counts as one regardless of the stanzas
    // the item also carries (the picker must not advertise N slides that all render the passage).
    assert_eq!(p.get(s).unwrap().slide_count(), 1);
}

#[test]
fn scripture_encode_neutralizes_control_chars_and_cannot_hijack_fields() {
    // A wire-supplied reference containing a TAB must NOT be able to shift the codec's field
    // boundaries and hijack the translation field.
    let malicious = ItemContent::Scripture {
        reference: "Romans 8:28\tKJV".into(),
        translation: None,
        verses_per_slide: None,
    };
    match ItemContent::decode(&malicious.encode()).unwrap() {
        ItemContent::Scripture {
            reference,
            translation,
            verses_per_slide,
        } => {
            assert!(!reference.contains('\t'), "tab neutralized: {reference:?}");
            assert_eq!(
                translation, None,
                "translation must not be hijacked by an injected tab"
            );
            assert_eq!(verses_per_slide, None);
        }
        other => panic!("expected Scripture, got {other:?}"),
    }
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

#[test]
fn item_content_codec_round_trips_every_variant() {
    let cases = [
        ItemContent::Scripture {
            reference: "Romans 8:28-30".into(),
            translation: Some("WEB".into()),
            verses_per_slide: Some(2),
        },
        // Optional sub-fields absent — still lossless.
        ItemContent::Scripture {
            reference: "John 3:16".into(),
            translation: None,
            verses_per_slide: None,
        },
        ItemContent::Deck {
            deck_id: 42,
            slide_count: None,
        },
        ItemContent::Media { media_id: 7 },
    ];
    for c in cases {
        assert_eq!(ItemContent::decode(&c.encode()), Some(c.clone()), "{c:?}");
    }
    // Corrupt / unknown persisted values decode to None (item loads unlinked), never panic.
    assert_eq!(ItemContent::decode("bogus\t1"), None);
    assert_eq!(ItemContent::decode("deck\tnotanumber"), None);
    assert_eq!(ItemContent::decode(""), None);
}

#[test]
fn set_item_content_links_and_blank_scripture_ref_unlinks() {
    let mut p = ServicePlan::new("Sunday");
    let s = p.add_item(ItemKind::Scripture, "Romans 8:28");
    assert!(p.get(s).unwrap().content.is_none()); // unlinked by default

    let link = ItemContent::Scripture {
        reference: "Romans 8:28-30".into(),
        translation: Some("WEB".into()),
        verses_per_slide: Some(2),
    };
    p.set_item_content(s, Some(link.clone())).unwrap();
    assert_eq!(p.get(s).unwrap().content.as_ref(), Some(&link));

    // A blank-reference scripture link normalizes to unlinked (no half-linked item).
    p.set_item_content(
        s,
        Some(ItemContent::Scripture {
            reference: "   ".into(),
            translation: None,
            verses_per_slide: None,
        }),
    )
    .unwrap();
    assert!(p.get(s).unwrap().content.is_none());

    // Clearing and an unknown id.
    p.set_item_content(
        s,
        Some(ItemContent::Deck {
            deck_id: 5,
            slide_count: None,
        }),
    )
    .unwrap();
    p.set_item_content(s, None).unwrap();
    assert!(p.get(s).unwrap().content.is_none());
    assert_eq!(
        p.set_item_content(ItemId(999), None),
        Err(PlanError::NotFound(ItemId(999)))
    );
}

#[test]
fn unresolved_content_flags_missing_decks_media_and_bad_refs() {
    let mut p = ServicePlan::new("Sunday");
    let good_scr = p.add_item(ItemKind::Scripture, "Romans");
    p.set_item_content(
        good_scr,
        Some(ItemContent::Scripture {
            reference: "Romans 8:28".into(),
            translation: None,
            verses_per_slide: None,
        }),
    )
    .unwrap();
    let bad_scr = p.add_item(ItemKind::Scripture, "Broken");
    p.set_item_content(
        bad_scr,
        Some(ItemContent::Scripture {
            reference: "Not a reference".into(),
            translation: None,
            verses_per_slide: None,
        }),
    )
    .unwrap();
    let present_deck = p.add_item(ItemKind::SlideGroup, "Sermon");
    p.set_item_content(
        present_deck,
        Some(ItemContent::Deck {
            deck_id: 1,
            slide_count: None,
        }),
    )
    .unwrap();
    let gone_deck = p.add_item(ItemKind::SlideGroup, "Old");
    p.set_item_content(
        gone_deck,
        Some(ItemContent::Deck {
            deck_id: 99,
            slide_count: None,
        }),
    )
    .unwrap();
    let gone_media = p.add_item(ItemKind::Media, "Testimony");
    p.set_item_content(gone_media, Some(ItemContent::Media { media_id: 8 }))
        .unwrap();
    let _unlinked = p.add_item(ItemKind::Song, "Opening"); // never flagged

    // Only deck 1 exists; no media exists.
    let missing = p.unresolved_content(|id| id == 1, |_| false);
    assert_eq!(missing, vec![bad_scr, gone_deck, gone_media]);
}

#[test]
fn set_item_owner_and_planned_secs_assign_clear_and_normalize() {
    let mut p = ServicePlan::new("Svc");
    let a = p.add_item(ItemKind::Song, "Opening");
    // Assign owner + duration.
    p.set_item_owner(a, Some("Grace".into())).unwrap();
    p.set_item_planned_secs(a, Some(240)).unwrap();
    assert_eq!(p.items()[0].owner.as_deref(), Some("Grace"));
    assert_eq!(p.items()[0].planned_secs, Some(240));
    // A blank owner normalizes to None (never half-assigned).
    p.set_item_owner(a, Some("   ".into())).unwrap();
    assert_eq!(p.items()[0].owner, None);
    // Clearing.
    p.set_item_planned_secs(a, None).unwrap();
    assert_eq!(p.items()[0].planned_secs, None);
    // Unknown id errors.
    assert_eq!(
        p.set_item_owner(ItemId(999), Some("x".into())),
        Err(PlanError::NotFound(ItemId(999)))
    );
    assert_eq!(
        p.set_item_planned_secs(ItemId(999), Some(1)),
        Err(PlanError::NotFound(ItemId(999)))
    );
}
