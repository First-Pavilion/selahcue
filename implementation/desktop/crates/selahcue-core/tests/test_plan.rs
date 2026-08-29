//! Integration tests for the service-plan domain model (FR-001/002). Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{
    plan_label_valid, ItemContent, ItemId, ItemKind, LinkResolution, PlanError, PlanItem,
    ServicePlan, VerseNumbers, MAX_LINK_LABEL_LEN, MAX_PLAN_LABEL_LEN,
};

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
            verse_numbers: None,
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
        verse_numbers: None,
    };
    match ItemContent::decode(&malicious.encode()).unwrap() {
        ItemContent::Scripture {
            reference,
            translation,
            verses_per_slide,
            verse_numbers: _,
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
            verse_numbers: None,
        },
        // Optional sub-fields absent — still lossless.
        ItemContent::Scripture {
            reference: "John 3:16".into(),
            translation: None,
            verses_per_slide: None,
            verse_numbers: None,
        },
        ItemContent::Deck {
            deck_id: 42,
            slide_count: None,
            label: None,
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
        verse_numbers: None,
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
            verse_numbers: None,
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
            label: None,
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
            verse_numbers: None,
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
            verse_numbers: None,
        }),
    )
    .unwrap();
    let present_deck = p.add_item(ItemKind::SlideGroup, "Sermon");
    p.set_item_content(
        present_deck,
        Some(ItemContent::Deck {
            deck_id: 1,
            slide_count: None,
            label: None,
        }),
    )
    .unwrap();
    let gone_deck = p.add_item(ItemKind::SlideGroup, "Old");
    p.set_item_content(
        gone_deck,
        Some(ItemContent::Deck {
            deck_id: 99,
            slide_count: None,
            label: None,
        }),
    )
    .unwrap();
    let gone_media = p.add_item(ItemKind::Media, "Testimony");
    p.set_item_content(gone_media, Some(ItemContent::Media { media_id: 8 }))
        .unwrap();
    let _unlinked = p.add_item(ItemKind::Song, "Opening"); // never flagged

    // Only deck 1 exists; no media exists.
    // The passage probe answers "yes" for anything that parses; an unparseable reference is
    // rejected inside `resolve` before the probe is consulted.
    let missing = p.unresolved_content(|_r, _t| true, |id| id == 1, |_| false);
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

// --- Link resolution: the three states, and the one that must never collapse -----------

/// Pin the premise at compile time: a cap small enough that the truncation test below actually
/// exercises truncation, and large enough that a real deck name is untouched. If someone raises
/// this to a huge value the test would silently stop testing anything, so fail the build instead.
const _: () = assert!(MAX_LINK_LABEL_LEN >= 16 && MAX_LINK_LABEL_LEN <= 4096);

#[test]
fn resolve_distinguishes_unknown_from_resolved_for_a_caller_that_cannot_check() {
    let deck = ItemContent::Deck {
        deck_id: 17,
        slide_count: None,
        label: None,
    };
    let media = ItemContent::Media { media_id: 4 };

    // The SAME link yields all three states, driven only by what the probe can answer. That is
    // what makes this bite: a `from_probe` that folded `None` into `Resolved` (the natural
    // bool-shaped mistake) passes an "is it Missing?" test and fails this one.
    assert_eq!(
        deck.resolve(|_, _| Some(true), |_| Some(true), |_| Some(true)),
        LinkResolution::Resolved,
        "a probe that says the deck exists must resolve"
    );
    assert_eq!(
        deck.resolve(|_, _| Some(true), |_| Some(false), |_| Some(false)),
        LinkResolution::Missing,
        "a probe that says the deck is gone must report missing"
    );
    assert_eq!(
        deck.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Unknown,
        "a caller that cannot see the deck library must report unknown"
    );
    // Stated separately and deliberately: `Unknown` collapsing into `Resolved` is the failure
    // that renders to an operator as "fine", so assert that specific confusion cannot happen.
    assert_ne!(
        deck.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Resolved,
        "unknown must never be reported as resolved — that is absent-equals-fine"
    );
    assert_eq!(
        media.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Unknown
    );

    // Scripture is answerable by a pure parse, so it is never Unknown, whatever the probes say.
    let good = ItemContent::Scripture {
        reference: "Romans 8:28-30".into(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    let bad = ItemContent::Scripture {
        reference: "Not a reference".into(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    assert_eq!(
        good.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Resolved
    );
    assert_eq!(
        bad.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Missing
    );
}

#[test]
fn link_resolution_tags_are_distinct_and_stable() {
    // The wire maps these tags directly, so a collision would silently merge two states.
    assert_eq!(LinkResolution::Resolved.as_tag(), "resolved");
    assert_eq!(LinkResolution::Missing.as_tag(), "missing");
    assert_eq!(LinkResolution::Unknown.as_tag(), "unknown");
}

// --- Deck label: captured, bounded, and not silently dropped ---------------------------

#[test]
fn deck_label_is_bounded_by_character_and_a_normal_name_is_kept_verbatim() {
    // Pin the premise inside the test too, so changing the cap cannot quietly make this vacuous.
    const _: () = assert!(MAX_LINK_LABEL_LEN >= 16);

    let mut p = ServicePlan::new("Sunday");
    let d = p.add_item(ItemKind::SlideGroup, "Sermon");

    // POSITIVE CONTROL first. Without it, "the label was shortened" is indistinguishable from
    // "labels are dropped/blanked entirely", and the cap below would pass against a dead field.
    let real_name = "Sunday Service \u{2014} Aug 4";
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: Some(24),
            label: Some(real_name.into()),
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, deck_id, .. }) => {
            assert_eq!(*deck_id, 17);
            assert_eq!(
                label.as_deref(),
                Some(real_name),
                "a normal deck name must survive verbatim — otherwise the cap test below is \
                 asserting against a field that never holds anything"
            );
        }
        other => panic!("expected a deck link, got {other:?}"),
    }

    // Now the cap. Multi-byte on purpose: truncating by BYTE would either panic on a char
    // boundary or corrupt the name, so this also pins that the bound is by character.
    let hostile: String = "\u{00e9}".repeat(MAX_LINK_LABEL_LEN * 4);
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: Some(hostile),
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, .. }) => {
            let stored = label.as_deref().expect("the link must still carry a label");
            // Assert the ENTITY — the stored label's own character count — not a proxy such as
            // "the plan is smaller than N bytes", which a dropped field would also satisfy.
            assert_eq!(
                stored.chars().count(),
                MAX_LINK_LABEL_LEN,
                "an over-long label must be bounded to exactly the cap, in characters"
            );
            assert!(
                stored.chars().all(|c| c == '\u{00e9}'),
                "truncation must not corrupt multi-byte characters: {stored:?}"
            );
        }
        other => panic!("expected a deck link, got {other:?}"),
    }

    // And the bound survives the persistence round-trip, so a hand-edited row cannot reintroduce
    // an unbounded label on load.
    let huge = format!("deck\t17\t\t{}", "x".repeat(MAX_LINK_LABEL_LEN * 10));
    match ItemContent::decode(&huge) {
        Some(ItemContent::Deck { label, .. }) => assert_eq!(
            label.as_deref().map(|l| l.chars().count()),
            Some(MAX_LINK_LABEL_LEN),
            "decode must re-bound a label that was never written through set_item_content"
        ),
        other => panic!("expected a deck link, got {other:?}"),
    }
}

// --- Codec back-compat for both new fields ---------------------------------------------

#[test]
fn legacy_encoded_links_decode_with_the_new_fields_unset() {
    // Rows written before verse-numbers / labels existed must still load, unlinked-free.
    assert_eq!(
        ItemContent::decode("scripture\tRomans 8:28\tWEB\t2"),
        Some(ItemContent::Scripture {
            reference: "Romans 8:28".into(),
            translation: Some("WEB".into()),
            verses_per_slide: Some(2),
            verse_numbers: None,
        }),
        "a pre-verse-numbers scripture row loads with the mode unset"
    );
    assert_eq!(
        ItemContent::decode("deck\t17"),
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: None,
        }),
        "the oldest deck row (id only) still loads"
    );
    assert_eq!(
        ItemContent::decode("deck\t17\t24"),
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: Some(24),
            label: None,
        }),
        "a pre-label deck row loads with the label unset"
    );
    // An unknown mode degrades to unset rather than failing the whole link — the passage still
    // displays, which is the point of the link.
    assert_eq!(
        ItemContent::decode("scripture\tJohn 3:16\t\t\tsideways"),
        Some(ItemContent::Scripture {
            reference: "John 3:16".into(),
            translation: None,
            verses_per_slide: None,
            verse_numbers: None,
        })
    );
}

#[test]
fn verse_numbers_round_trip_through_the_codec_and_tags() {
    for mode in [
        VerseNumbers::Superscript,
        VerseNumbers::Inline,
        VerseNumbers::Hidden,
    ] {
        assert_eq!(VerseNumbers::from_tag(mode.as_tag()), Some(mode));
        let c = ItemContent::Scripture {
            reference: "Romans 8:28".into(),
            translation: None,
            verses_per_slide: None,
            verse_numbers: Some(mode),
        };
        assert_eq!(ItemContent::decode(&c.encode()), Some(c.clone()), "{c:?}");
    }
    assert_eq!(VerseNumbers::from_tag("sideways"), None);
}

#[test]
fn a_label_containing_a_tab_cannot_hijack_the_codec_fields() {
    // Same class of attack the scripture reference test already covers: the label is the LAST
    // deck field, so a tab in it would append phantom fields on decode.
    let c = ItemContent::Deck {
        deck_id: 17,
        slide_count: Some(24),
        label: Some("Sunday\tService".into()),
    };
    match ItemContent::decode(&c.encode()) {
        Some(ItemContent::Deck {
            label,
            deck_id,
            slide_count,
        }) => {
            assert_eq!(deck_id, 17);
            assert_eq!(slide_count, Some(24));
            let l = label.expect("label survives");
            assert!(!l.contains('\t'), "tab neutralized: {l:?}");
            assert_eq!(l, "Sunday Service");
        }
        other => panic!("expected a deck link, got {other:?}"),
    }
}

// --- Planned-duration roll-up: the total, and whether it covers the plan (FR-202) -------

#[test]
fn planned_total_marks_itself_partial_only_when_a_real_item_lacks_a_duration() {
    // POSITIVE CONTROL FIRST. A fully-planned plan must NOT be partial — otherwise an
    // always-true flag would satisfy every "is it partial?" assertion below, and a broken
    // control would be indistinguishable from a working one.
    let mut full = ServicePlan::new("Complete");
    let a = full.add_item(ItemKind::Song, "Opening");
    let b = full.add_item(ItemKind::Scripture, "Romans");
    full.set_item_planned_secs(a, Some(300)).unwrap();
    full.set_item_planned_secs(b, Some(120)).unwrap();
    let t = full.planned_total();
    assert_eq!(t.secs, 420);
    assert_eq!(t.counted, 2);
    assert_eq!(t.unplanned, 0);
    assert!(
        !t.is_partial(),
        "a plan where every item has a duration reports a COMPLETE total"
    );

    // One unset duration makes the total a floor, and it must say so.
    let mut partial = full.clone();
    let c = partial.add_item(ItemKind::Media, "Testimony");
    let t = partial.planned_total();
    assert_eq!(t.secs, 420, "the unset item contributes nothing to the sum");
    assert_eq!(t.counted, 2);
    assert_eq!(t.unplanned, 1);
    assert!(
        t.is_partial(),
        "a total that omits an item must be marked partial — otherwise it renders as the \
         whole service length while being short by however long that item runs"
    );

    // Filling it in clears the flag, so the flag tracks the data rather than latching on.
    partial.set_item_planned_secs(c, Some(192)).unwrap();
    let t = partial.planned_total();
    assert_eq!(t.secs, 612);
    assert!(
        !t.is_partial(),
        "filling in the last duration completes the total"
    );
}

#[test]
fn inert_section_dividers_never_make_a_total_partial() {
    // A section is a divider that never fires, so carrying no duration is its normal state.
    // Counting it would mark every sectioned plan partial — and a warning that is always on is
    // one coordinators learn to ignore, which is worse than not having one.
    let mut p = ServicePlan::new("Sectioned");
    let s1 = p.add_item(ItemKind::Section, "GATHERING");
    let song = p.add_item(ItemKind::Song, "Opening");
    let _s2 = p.add_item(ItemKind::Section, "THE WORD");
    p.set_item_planned_secs(song, Some(300)).unwrap();

    let t = p.planned_total();
    assert_eq!(t.secs, 300);
    assert_eq!(t.unplanned, 0, "dividers are not unplanned items");
    assert!(
        !t.is_partial(),
        "a plan whose only duration-less rows are section dividers is COMPLETE"
    );

    // A divider cannot be given a duration at all, so the roll-up can never disagree with a
    // value sitting on a row. Refused rather than stored-and-ignored: a stored value would be
    // invisible to the totals while still riding on the item view.
    assert_eq!(
        p.set_item_planned_secs(s1, Some(60)),
        Err(PlanError::NotApplicable(s1)),
        "a divider is not schedulable, so setting a duration on one is refused"
    );
    let t = p.planned_total();
    assert_eq!(
        t.secs, 300,
        "and the total is untouched by the refused edit"
    );
    assert_eq!(t.counted, 1);
    // Clearing is still allowed, so a legacy item can always be cleaned up.
    assert_eq!(p.set_item_planned_secs(s1, None), Ok(()));
}

#[test]
fn an_empty_plans_total_is_complete_not_partial() {
    // Nothing is missing from a total of nothing. Marking an empty plan "partial" would put a
    // warning on the empty state the design shows as clean ("0 items · 0:00").
    let t = ServicePlan::new("Empty").planned_total();
    assert_eq!(t.secs, 0);
    assert_eq!(t.counted, 0);
    assert!(!t.is_partial());
}

#[test]
fn planned_total_secs_agrees_with_the_roll_up_it_delegates_to() {
    // The two must never diverge: `planned_total_secs` is the older API and still has callers.
    let mut p = ServicePlan::new("Sunday");
    let a = p.add_item(ItemKind::Song, "Opening");
    let _b = p.add_item(ItemKind::Media, "Unplanned");
    p.set_item_planned_secs(a, Some(300)).unwrap();
    assert_eq!(p.planned_total_secs(), p.planned_total().secs);
}

#[test]
fn a_label_cannot_smuggle_invisible_or_bidi_characters_into_the_run_sheet() {
    // `char::is_control` covers the Cc category only, so these Cf characters used to survive
    // into a label that is echoed to every paired device and rendered in the run sheet. A
    // right-to-left override makes a name DISPLAY as something other than what it is, and
    // zero-width joiners let two distinct decks look identical. (Security review, PR #13.)
    let hostile = "Sermon\u{202E}exe.gpj\u{200B}\u{FEFF}";
    let mut p = ServicePlan::new("Sunday");
    let d = p.add_item(ItemKind::SlideGroup, "Sermon");
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: Some(hostile.into()),
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, .. }) => {
            let l = label
                .as_deref()
                .expect("the label survives, minus the spoofing");
            assert!(
                !l.chars().any(|ch| matches!(ch,
                    '\u{200B}'..='\u{200F}' | '\u{202A}'..='\u{202E}'
                    | '\u{2060}'..='\u{2064}' | '\u{2066}'..='\u{2069}' | '\u{FEFF}')),
                "no invisible or bidi character may reach the run sheet: {l:?}"
            );
            // POSITIVE CONTROL: the visible text is KEPT. A sanitizer that returned an empty
            // string would also satisfy the assertion above and be useless.
            assert_eq!(
                l, "Sermonexe.gpj",
                "the readable characters survive verbatim; only the invisible ones are dropped"
            );
        }
        other => panic!("expected a deck link, got {other:?}"),
    }

    // A legitimate name with non-ASCII letters is untouched — the filter targets invisible
    // formatting, not "anything unusual".
    let real = "Sunday Service \u{2014} Ao\u{00FB}t 4";
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: Some(real.into()),
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, .. }) => assert_eq!(label.as_deref(), Some(real)),
        other => panic!("expected a deck link, got {other:?}"),
    }
}

#[test]
fn a_reference_that_parses_but_names_no_verse_is_missing_not_resolved() {
    // `parse_one` validates SYNTAX. "Jude 2:1" (Jude has a single chapter) and "Romans 99:1"
    // are well-formed and name nothing, so a parse-only rule reported them as healthy — on the
    // one content kind the host claims authority over, and no client can correct it downstream.
    // (Code review, PR #13.)
    let phantom = ItemContent::Scripture {
        reference: "Jude 2:1".into(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    assert!(
        crate_parses("Jude 2:1"),
        "premise: this reference really does parse, so the test is exercising the gap \
         between parsing and existing rather than a parse failure"
    );
    assert_eq!(
        phantom.resolve(|_, _| Some(false), |_| None, |_| None),
        LinkResolution::Missing,
        "a passage the corpus cannot produce is MISSING, never resolved"
    );

    // POSITIVE CONTROL: the same code path reports a real passage as resolved, so "missing"
    // above is a verdict about the passage and not a probe that always refuses.
    let real = ItemContent::Scripture {
        reference: "Romans 8:28-30".into(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    assert_eq!(
        real.resolve(|_, _| Some(true), |_| None, |_| None),
        LinkResolution::Resolved
    );

    // And a caller that cannot consult a corpus at all says so, rather than guessing.
    assert_eq!(
        real.resolve(|_, _| None, |_| None, |_| None),
        LinkResolution::Unknown
    );

    // An unparseable reference never reaches the probe — it is missing on syntax alone.
    let broken = ItemContent::Scripture {
        reference: "Not a reference".into(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    assert_eq!(
        broken.resolve(
            |_, _| panic!("the probe must not be consulted for an unparseable reference"),
            |_| None,
            |_| None
        ),
        LinkResolution::Missing
    );
}

fn crate_parses(r: &str) -> bool {
    selahcue_core::scripture::parse_one(r).is_ok()
}

#[test]
fn a_deck_relink_without_a_name_keeps_the_last_known_good_one() {
    // `set_item_content` is a full replace, so an absent label must mean "nothing new to say",
    // not "forget it" — otherwise syncing a slide count destroys the very name a deleted deck
    // needs to be described by. (Code review, PR #13.)
    let mut p = ServicePlan::new("Sunday");
    let d = p.add_item(ItemKind::SlideGroup, "Sermon");
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: Some(24),
            label: Some("Sunday Service".into()),
        }),
    )
    .unwrap();

    // Same deck, no name supplied: the stored name survives.
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: Some(25),
            label: None,
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck {
            label, slide_count, ..
        }) => {
            assert_eq!(*slide_count, Some(25), "the update itself still applied");
            assert_eq!(
                label.as_deref(),
                Some("Sunday Service"),
                "an update silent about the name must not erase it"
            );
        }
        other => panic!("expected a deck link, got {other:?}"),
    }

    // A supplied name still wins — this is how a rename is recorded.
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: Some(25),
            label: Some("Sunday Service — Aug 11".into()),
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, .. }) => {
            assert_eq!(label.as_deref(), Some("Sunday Service — Aug 11"))
        }
        other => panic!("expected a deck link, got {other:?}"),
    }

    // Relinking to a DIFFERENT deck drops it: it is not that deck's name.
    p.set_item_content(
        d,
        Some(ItemContent::Deck {
            deck_id: 99,
            slide_count: None,
            label: None,
        }),
    )
    .unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, deck_id, .. }) => {
            assert_eq!(*deck_id, 99);
            assert_eq!(
                *label, None,
                "a different deck must not inherit the previous deck's name"
            );
        }
        other => panic!("expected a deck link, got {other:?}"),
    }
}

#[test]
fn a_divider_cannot_carry_an_owner_a_duration_or_a_link() {
    // Excluding dividers from the summary is only half the invariant: if a divider could still
    // HOLD these, one frame would report `missing: 0` beside a row whose own link said
    // "missing", and `assigned` would disagree with a visible owner. Refuse at the source.
    // (Code review, PR #13.)
    let mut p = ServicePlan::new("Sunday");
    let divider = p.add_item(ItemKind::Section, "GATHERING");
    let song = p.add_item(ItemKind::Song, "Opening");

    assert_eq!(
        p.set_item_owner(divider, Some("Pastor".into())),
        Err(PlanError::NotApplicable(divider))
    );
    assert_eq!(
        p.set_item_planned_secs(divider, Some(600)),
        Err(PlanError::NotApplicable(divider))
    );
    assert_eq!(
        p.set_item_content(
            divider,
            Some(ItemContent::Scripture {
                reference: "Jude 2:1".into(),
                translation: None,
                verses_per_slide: None,
                verse_numbers: None,
            })
        ),
        Err(PlanError::NotApplicable(divider))
    );
    let d = p.get(divider).unwrap();
    assert!(d.owner.is_none() && d.planned_secs.is_none() && d.content.is_none());

    // POSITIVE CONTROL: the very same calls succeed on a real item, so the refusals above are
    // about the divider and not about a setter that has stopped working.
    assert_eq!(p.set_item_owner(song, Some("Worship".into())), Ok(()));
    assert_eq!(p.set_item_planned_secs(song, Some(300)), Ok(()));
    assert_eq!(
        p.set_item_content(
            song,
            Some(ItemContent::Deck {
                deck_id: 17,
                slide_count: None,
                label: Some("Deck".into()),
            })
        ),
        Ok(())
    );

    // Clearing a divider is always permitted — otherwise a legacy row could never be tidied.
    assert_eq!(p.set_item_owner(divider, None), Ok(()));
    assert_eq!(p.set_item_content(divider, None), Ok(()));
}

#[test]
fn rehydration_strips_data_an_older_build_stored_on_a_divider() {
    // The setters refuse it now, but rehydration is the one path that bypasses them — and a
    // database written before the guard existed is exactly where such a row comes from. The
    // invariant has to hold for DATA, not only for edits.
    let contaminated = PlanItem {
        id: ItemId(1),
        kind: ItemKind::Section,
        title: "GATHERING".into(),
        planned_secs: Some(600),
        owner: Some("Pastor".into()),
        stanzas: Vec::new(),
        theme: None,
        content: Some(ItemContent::Scripture {
            reference: "Jude 2:1".into(),
            translation: None,
            verses_per_slide: None,
            verse_numbers: None,
        }),
    };
    let real = PlanItem {
        id: ItemId(2),
        kind: ItemKind::Song,
        title: "Opening".into(),
        planned_secs: Some(300),
        owner: Some("Worship".into()),
        stanzas: Vec::new(),
        theme: None,
        content: None,
    };
    let p = ServicePlan::from_parts("Sunday", vec![contaminated, real], 3);

    let d = p.get(ItemId(1)).unwrap();
    assert_eq!(d.owner, None, "a divider's stored owner is swept on load");
    assert_eq!(d.planned_secs, None);
    assert_eq!(d.content, None);
    assert_eq!(
        d.title, "GATHERING",
        "but the divider itself survives intact"
    );

    // POSITIVE CONTROL: a real item's data is untouched by the sweep.
    let r = p.get(ItemId(2)).unwrap();
    assert_eq!(r.owner.as_deref(), Some("Worship"));
    assert_eq!(r.planned_secs, Some(300));

    // And the roll-up now matches what the rows actually show.
    let t = p.planned_total();
    assert_eq!(t.secs, 300);
    assert_eq!(t.counted, 1);
    assert!(!t.is_partial());
}

#[test]
fn a_blank_or_invisible_only_label_is_treated_as_absent() {
    // Keying the carry-forward on `Option` alone stored `Some("")` and `Some("   ")` as real
    // names, which rendered as `⚠ "" is missing`. Worse, the invisible-character filter turns a
    // hostile all-zero-width label into exactly that. Blank means absent here, as it already
    // does for owners, scripture references and themes. (Code review, PR #13.)
    let mut p = ServicePlan::new("Sunday");
    let d = p.add_item(ItemKind::SlideGroup, "Sermon");
    let deck = |label: Option<&str>| {
        Some(ItemContent::Deck {
            deck_id: 17,
            slide_count: None,
            label: label.map(str::to_string),
        })
    };
    p.set_item_content(d, deck(Some("Sunday Service"))).unwrap();

    for blank in ["", "   ", "\u{200B}\u{200B}\u{FEFF}"] {
        p.set_item_content(d, deck(Some(blank))).unwrap();
        match p.get(d).unwrap().content.as_ref() {
            Some(ItemContent::Deck { label, .. }) => assert_eq!(
                label.as_deref(),
                Some("Sunday Service"),
                "a blank label ({blank:?}) is nothing new to say, so the real name survives"
            ),
            other => panic!("expected a deck link, got {other:?}"),
        }
    }

    // POSITIVE CONTROL: a real name still replaces it, so the guard has not frozen the field.
    p.set_item_content(d, deck(Some("Renamed"))).unwrap();
    match p.get(d).unwrap().content.as_ref() {
        Some(ItemContent::Deck { label, .. }) => assert_eq!(label.as_deref(), Some("Renamed")),
        other => panic!("expected a deck link, got {other:?}"),
    }
}

#[test]
fn a_scripture_reference_is_sanitized_on_the_way_in_not_only_on_encode() {
    // Sanitizing only inside `encode` let a right-to-left override ride the WIRE into the run
    // sheet while never reaching disk, because the controller stores what it validated.
    let mut p = ServicePlan::new("Sunday");
    let s = p.add_item(ItemKind::Scripture, "Romans");
    p.set_item_content(
        s,
        Some(ItemContent::Scripture {
            reference: "Romans\u{202E} 8:28".into(),
            translation: Some("WE\u{200B}B".into()),
            verses_per_slide: None,
            verse_numbers: None,
        }),
    )
    .unwrap();
    match p.get(s).unwrap().content.as_ref() {
        Some(ItemContent::Scripture {
            reference,
            translation,
            ..
        }) => {
            assert_eq!(
                reference, "Romans 8:28",
                "stored clean, not merely encoded clean"
            );
            assert_eq!(translation.as_deref(), Some("WEB"));
        }
        other => panic!("expected a scripture link, got {other:?}"),
    }
}

#[test]
fn a_section_with_a_duration_would_break_the_operators_summary_validation_seam() {
    // TRIPWIRE for a coupling that spans two crates, two languages and two pull requests.
    //
    // The operator console does not trust the host's summary on sight: `planSummaryIsSound` in
    // `selahcue-operator/dist/app.js` recomputes `planned_total_secs` from the rows it was sent
    // and rejects the whole summary if the two disagree. Its recomputation sums `planned_secs`
    // over EVERY item, sections included. `ServicePlan::planned_total` EXCLUDES sections. Two
    // different definitions that agree for exactly one reason: a section cannot hold a duration.
    //
    // Relax that guard and nothing fails loudly. The console stops trusting a correct summary
    // and silently falls back to computing its own, so the panel keeps showing plausible numbers
    // that are no longer the host's — no panic, no error, no red test. This test exists to make
    // that day loud instead.
    //
    // It is CONDITIONAL on purpose. The state it guards is unconstructible today, which is the
    // whole point of the guard; asserting it directly would be a test that can only ever pass.
    // So it asks the domain whether the state has become reachable, and only then asserts the
    // invariant the seam depends on. Today the `Err` arm runs and carries a positive control, so
    // it is not vacuous; the day the guard is relaxed, the `Ok` arm opens and the assert fires.
    let mut plan = ServicePlan::new("Sunday");
    let song = plan.add_item(ItemKind::Song, "Opening Song");
    let divider = plan.add_item(ItemKind::Section, "SERMON");
    plan.set_item_planned_secs(song, Some(300)).unwrap();

    match plan.set_item_planned_secs(divider, Some(600)) {
        Err(PlanError::NotApplicable(id)) => {
            assert_eq!(id, divider, "the refusal must name the divider it refused");
            // POSITIVE CONTROL: the same call on a real item must still succeed. Without this,
            // a setter that had been broken into always returning Err would satisfy the arm
            // above and this test would vouch for a guard that no longer guards anything.
            assert!(
                plan.set_item_planned_secs(song, Some(301)).is_ok(),
                "positive control: the setter must still work on a non-divider, or the Err arm \
                 above proves nothing about dividers specifically"
            );
            // And the premise the seam actually rests on: with the guard intact, our total and
            // the operator's all-items recomputation are the same number.
            let ours = plan.planned_total().secs;
            let as_the_operator_recomputes_it: u32 =
                plan.items().iter().filter_map(|i| i.planned_secs).sum();
            assert_eq!(
                ours, as_the_operator_recomputes_it,
                "with no section able to hold a duration, the two definitions must coincide"
            );
        }
        Err(other) => panic!("expected NotApplicable for a divider, got {other:?}"),
        Ok(()) => {
            // The guard has been relaxed. The cross-language seam now depends on these agreeing.
            let ours = plan.planned_total().secs;
            let as_the_operator_recomputes_it: u32 =
                plan.items().iter().filter_map(|i| i.planned_secs).sum();
            assert_eq!(
                ours, as_the_operator_recomputes_it,
                "a section can now carry a duration, so ServicePlan::planned_total ({ours}) no \
                 longer matches the all-items sum the operator console recomputes \
                 ({as_the_operator_recomputes_it}). planSummaryIsSound in \
                 selahcue-operator/dist/app.js will reject this summary and the Plan Summary \
                 panel will silently fall back to its own local computation. Either keep \
                 durations off dividers, or change that validator to exclude them too — the two \
                 definitions must move together."
            );
        }
    }
}

#[test]
fn same_document_ignores_the_id_counter_and_nothing_else() {
    // `same_document` answers "would an operator see any difference?", which is a different
    // question from `==`. The two come apart on exactly one field, and that difference is the
    // whole reason the method exists: the change-since-publish badge must not latch on for good
    // after an add-then-remove that leaves the run sheet exactly as it was.
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");

    let baseline = plan.clone();
    assert!(
        baseline.same_document(&plan),
        "a clone is the same document"
    );
    assert_eq!(baseline, plan, "and is also equal");

    // Add then remove: observably identical, but the id counter has advanced for good.
    let temp = plan.add_item(ItemKind::Song, "Temporary");
    plan.remove(temp).unwrap();
    assert_ne!(
        baseline, plan,
        "the premise: `==` DOES see the advanced id counter, so this test is not vacuous"
    );
    assert!(
        baseline.same_document(&plan),
        "add-then-remove leaves a run sheet an operator cannot tell apart, so it must compare \
         as the same document"
    );

    // Everything a person CAN see still counts as a difference.
    let mut renamed = plan.clone();
    renamed.name = "Next Week".into();
    assert!(
        !baseline.same_document(&renamed),
        "the plan name is on screen, so a rename is a real difference"
    );

    let mut retitled = plan.clone();
    retitled.get_mut(retitled.items()[0].id).unwrap().title = "Changed".into();
    assert!(
        !baseline.same_document(&retitled),
        "an item title is on screen, so retitling is a real difference"
    );

    let mut reordered = plan.clone();
    reordered.reorder(0, 1).unwrap();
    assert!(
        !baseline.same_document(&reordered),
        "order IS the run sheet, so reordering is a real difference"
    );

    let mut shorter = plan.clone();
    shorter.remove(shorter.items()[0].id).unwrap();
    assert!(
        !baseline.same_document(&shorter),
        "a removed row is a real difference"
    );
}

#[test]
fn a_plan_label_must_be_visible_bounded_and_single_line() {
    // The ingress rule for plan names, item titles and owners. The predicate is: refuse
    // characters that act at a distance or have no role in writing words; admit invisibles whose
    // effect is confined to the glyphs they touch.
    assert!(plan_label_valid("Sunday Morning"));
    assert!(
        plan_label_valid("  trimmed  "),
        "surrounding space is trimmed"
    );

    assert!(!plan_label_valid(""), "empty");
    assert!(!plan_label_valid("   "), "whitespace only");
    assert!(
        !plan_label_valid(&"x".repeat(MAX_PLAN_LABEL_LEN + 1)),
        "one character over the bound"
    );
    assert!(
        plan_label_valid(&"x".repeat(MAX_PLAN_LABEL_LEN)),
        "exactly at the bound is fine — the bound must not be off by one"
    );

    // --- Refused: control characters, line separators, and invisibles that act at a distance ---
    assert!(!plan_label_valid("Sun\u{7}day"), "Cc: bell");
    assert!(!plan_label_valid("Sun\u{2028}day"), "Zl: line separator");
    assert!(
        !plan_label_valid("Sun\u{2029}day"),
        "Zp: paragraph separator"
    );
    // Stateful direction controls: these reorder text BEYOND their own position, which is the
    // Trojan-Source primitive the original advisory was about.
    assert!(!plan_label_valid("Sun\u{202E}day"), "RLO override");
    assert!(!plan_label_valid("Sun\u{202A}day"), "LRE embedding");
    assert!(
        !plan_label_valid("Sun\u{2066}day"),
        "LRI isolate — the isolates were previously untested entirely"
    );
    assert!(!plan_label_valid("Sun\u{2069}day"), "PDI isolate");
    // Zero-orthography invisibles: no script spells with these.
    assert!(!plan_label_valid("Sun\u{200B}day"), "zero-width space");
    assert!(!plan_label_valid("Sun\u{FEFF}day"), "BOM / ZWNBSP");
    assert!(!plan_label_valid("Sun\u{2060}day"), "word joiner");
    // Deprecated shaping controls and interlinear anchors, added after the security re-test: no
    // practical spoofing power (renderers ignore them) but they satisfied the visible-content
    // guard, so a name made only of one was valid.
    assert!(
        !plan_label_valid("Sun\u{206E}day"),
        "deprecated digit-shape control"
    );
    assert!(
        !plan_label_valid("\u{206E}"),
        "and it is not a valid name on its own"
    );
    assert!(
        !plan_label_valid("Sun\u{FFFA}day"),
        "interlinear annotation separator"
    );

    // --- Admitted: the joiners are SPELLING, not decoration ---
    //
    // Each of these is a real word in a real script that cannot be written without the joiner.
    // Refusing them does not harden a name field; it stops the language being typed into one.
    assert!(
        plan_label_valid("\u{06A9}\u{062A}\u{0627}\u{0628}\u{200C}\u{0647}\u{0627}"),
        "Persian: ZWNJ carries the plural suffix"
    );
    assert!(
        plan_label_valid("\u{0646}\u{200C}\u{06C1}"),
        "Urdu: ZWNJ between joining forms"
    );
    assert!(
        plan_label_valid("\u{0915}\u{094D}\u{200C}\u{0937}"),
        "Devanagari: ZWNJ forces the explicit halant"
    );
    assert!(
        plan_label_valid("\u{0DC1}\u{0DCA}\u{200D}\u{0DBB}\u{0DD3}"),
        "Sinhala \u{0DC1}\u{0DCA}\u{200D}\u{0DBB}\u{0DD3} — the word Sri, as in Sri Lanka. It \
         cannot be written without U+200D at all, so refusing ZWJ stopped a congregation typing \
         their own country's name"
    );
    assert!(
        plan_label_valid("\u{0D23}\u{0D4D}\u{200D}"),
        "Malayalam: ZWJ forms the chillu letter"
    );
    assert!(
        plan_label_valid("Sunday \u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}"),
        "a family emoji is bound by the same ZWJ — this used to be a documented 'accepted cost' \
         and is simply valid now"
    );
    // Implicit bidi marks are stateless: they influence adjacent neutrals only and cannot
    // reorder a strong-directional run. U+061C always passed, so refusing these two was not even
    // internally consistent.
    assert!(plan_label_valid("Sun\u{200E}day"), "LRM");
    assert!(plan_label_valid("Sun\u{200F}day"), "RLM");
    assert!(plan_label_valid("Sun\u{061C}day"), "ALM");
    assert!(
        !plan_label_valid("\u{061C}"),
        "ALM alone is still an invisible name — this only holds if the visible-content guard \
         counts ALM as invisible, so it pins that U+061C is admitted BY THE RULE rather than \
         merely unlisted"
    );

    // U+180E MONGOLIAN VOWEL SEPARATOR is orthographic — required Mongolian spelling — and it
    // must pass. This is the counter-case that makes the divergence from `is_display_unsafe`
    // (`selahcue-lan/src/server.rs`) load-bearing rather than merely tolerated: that list DROPS
    // U+180E, so copying it here would have repeated the ZWNJ mistake for Mongolian. Found by
    // security re-test of PR #14.
    assert!(
        plan_label_valid("\u{1824}\u{180E}\u{1822}"),
        "Mongolian: the vowel separator is spelling, and the device-name list would refuse it"
    );

    // --- The companion guard: admitting joiners must not admit an INVISIBLE name ---
    //
    // Load-bearing. Before the joiners were admitted this string was refused only as a side
    // effect of the over-broad list, so narrowing without this would have opened a hole.
    assert!(
        !plan_label_valid("\u{200C}\u{200C}"),
        "a label made only of joiners renders as nothing and must be refused"
    );
    assert!(
        !plan_label_valid("\u{200D}"),
        "one joiner alone is still an invisible name"
    );
    assert!(
        !plan_label_valid(" \u{200C} "),
        "whitespace plus a joiner is still nothing to look at"
    );
    assert!(
        plan_label_valid("\u{0915}\u{094D}\u{200C}\u{0937}"),
        "POSITIVE CONTROL beside it: the same joiner INSIDE a word is fine, so the guard rejects \
         invisibility rather than rejecting the joiner"
    );

    // Ordinary international text, unaffected either way.
    assert!(plan_label_valid("主日崇拜"), "Chinese");
    assert!(plan_label_valid("خدمة الأحد"), "Arabic");
    assert!(plan_label_valid("Богослужение"), "Cyrillic");
    assert!(plan_label_valid("Opening 🎉"), "a single emoji");
    assert!(
        plan_label_valid("Café — Sunday's 1st"),
        "accents, dashes and apostrophes are ordinary label text"
    );
}

#[test]
fn the_codec_preserves_orthographic_joiners_in_a_stored_label() {
    // `sanitize_field` DROPS what `plan_label_valid` REFUSES, over the same set — so narrowing
    // that set fixes the codec too. It previously misspelled stored labels silently: Persian lost
    // its ZWNJ (7 characters in, 6 out) and Sinhala "Sri" was broken outright.
    //
    // Different verb, deliberately: the codec runs on already-stored data and has nobody to
    // report a failure to, so it must be total and drops. Ingress creating a new document can
    // refuse. That split is only safe because no orthographic character is in the set any more.
    let persian = "\u{06A9}\u{062A}\u{0627}\u{0628}\u{200C}\u{0647}\u{0627}";
    let sinhala = "\u{0DC1}\u{0DCA}\u{200D}\u{0DBB}\u{0DD3}";

    for label in [persian, sinhala] {
        let link = ItemContent::Deck {
            deck_id: 7,
            slide_count: Some(3),
            label: Some(label.to_string()),
        };
        let decoded = ItemContent::decode(&link.encode()).expect("the link must decode");
        let ItemContent::Deck { label: out, .. } = decoded else {
            panic!("expected a deck link");
        };
        let out = out.expect("the label must survive the round trip");
        assert_eq!(
            out.chars().count(),
            label.chars().count(),
            "the codec dropped a character from {label:?} — an orthographic joiner is spelling, \
             and dropping it misspells the stored label with no way to notice"
        );
        assert_eq!(out, label, "the label must round-trip byte-identically");
    }

    // POSITIVE CONTROL: the codec still drops what it is supposed to drop, so the assertions
    // above are not passing because the filter is dead.
    let hostile = ItemContent::Deck {
        deck_id: 7,
        slide_count: None,
        label: Some("Deck\u{202E}Name".to_string()),
    };
    let decoded = ItemContent::decode(&hostile.encode()).expect("decodes");
    let ItemContent::Deck { label: out, .. } = decoded else {
        panic!("expected a deck link");
    };
    assert_eq!(
        out.as_deref(),
        Some("DeckName"),
        "a direction override must still be stripped from a stored label"
    );
}
