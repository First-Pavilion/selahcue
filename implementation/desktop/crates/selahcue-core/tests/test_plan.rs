//! Integration tests for the service-plan domain model (FR-001/002). Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{
    ItemContent, ItemId, ItemKind, LinkResolution, PlanError, PlanItem, ServicePlan, VerseNumbers,
    MAX_LINK_LABEL_LEN,
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

    // A divider is excluded from the roll-up ENTIRELY, so even a duration set on one does not
    // reach the total. Otherwise `counted` could exceed the plan's item count and the UI would
    // render "7 of 6".
    p.set_item_planned_secs(s1, Some(60)).unwrap();
    let t = p.planned_total();
    assert_eq!(
        t.secs, 300,
        "a divider contributes no duration even when one has been set on it"
    );
    assert_eq!(t.counted, 1, "and it is not counted as a contributing item");
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
