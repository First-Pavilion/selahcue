//! Cross-machine presentation identity (ClickUp 86ak196cr · `FINDING-LIB-07`). Public API only.
//!
//! The pure rule: a deck link leaves a machine as an identity, never a local number, and is bound
//! on arrival to the receiving library's own deck for that identity or to the missing-content
//! state. The two-library integration test lives with the library, in `selahcue-operator`; these
//! tests pin the rule itself, including every hostile spelling of an identity.

#![allow(clippy::unwrap_used)]

use std::cell::Cell;

use selahcue_core::deck_ref::{
    export_deck_link, import_deck_link, DeckLinkMatch, DeckUid, LocalDeck, PortableDeckLink,
    DECK_UID_HEX_LEN, UNRESOLVED_DECK_ID,
};
use selahcue_core::plan::{ItemContent, ItemKind, LinkResolution, ServicePlan, MAX_LINK_LABEL_LEN};

const UID_A: &str = "00112233445566778899aabbccddeeff";
const UID_B: &str = "ffeeddccbbaa99887766554433221100";

fn uid(s: &str) -> DeckUid {
    DeckUid::parse(s).unwrap()
}

fn deck(id: u64, label: &str) -> ItemContent {
    ItemContent::Deck {
        deck_id: id,
        slide_count: Some(7),
        label: Some(label.to_string()),
    }
}

fn link(uid: Option<&str>, label: Option<&str>) -> PortableDeckLink {
    PortableDeckLink {
        uid: uid.map(str::to_string),
        slide_count: Some(99),
        label: label.map(str::to_string),
    }
}

fn local(id: u64, name: &str, slides: u32) -> LocalDeck {
    LocalDeck {
        id,
        slide_count: slides,
        name: name.to_string(),
    }
}

// --- DeckUid: one canonical spelling ---------------------------------------------------------

#[test]
fn a_canonical_uid_parses_and_prints_back_unchanged() {
    let u = DeckUid::parse(UID_A).unwrap();
    assert_eq!(u.as_str(), UID_A);
    assert_eq!(u.to_string(), UID_A);
    assert_eq!(UID_A.len(), DECK_UID_HEX_LEN);
}

#[test]
fn every_non_canonical_spelling_is_refused() {
    let wrong_len_31 = &UID_A[..31];
    let wrong_len_33 = format!("{UID_A}0");
    // 32 BYTES but not 32 hex digits: sixteen two-byte characters.
    let multibyte = "é".repeat(16);
    assert_eq!(multibyte.len(), DECK_UID_HEX_LEN);
    let cases: Vec<(&str, String)> = vec![
        ("empty", String::new()),
        ("31 digits", wrong_len_31.to_string()),
        ("33 digits", wrong_len_33),
        ("upper case", UID_A.to_uppercase()),
        ("one non-hex digit", format!("g{}", &UID_A[1..])),
        ("leading space", format!(" {}", &UID_A[1..])),
        ("trailing newline", format!("{}\n", &UID_A[..31])),
        (
            "embedded NUL",
            format!("{}\0{}", &UID_A[..16], &UID_A[17..]),
        ),
        ("0x prefix", format!("0x{}", &UID_A[2..])),
        ("dashed", "00112233-4455-6677-8899-aabbccddeeff".to_string()),
        ("multibyte of the right byte length", multibyte),
        ("all zero", "0".repeat(DECK_UID_HEX_LEN)),
        ("a megabyte", "a".repeat(1 << 20)),
    ];
    for (what, s) in cases {
        assert_eq!(DeckUid::parse(&s), None, "{what} must not parse");
    }
}

#[test]
fn from_bytes_writes_the_big_endian_hex_and_round_trips_through_parse() {
    let bytes = [
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee,
        0xff,
    ];
    let u = DeckUid::from_bytes(bytes).unwrap();
    assert_eq!(u.as_str(), UID_A);
    assert_eq!(DeckUid::parse(u.as_str()), Some(u));
}

#[test]
fn from_bytes_refuses_only_the_all_zero_buffer() {
    assert_eq!(DeckUid::from_bytes([0; 16]), None);
    // Boundaries: a single set bit at either end is a real identity.
    let mut first = [0u8; 16];
    first[0] = 1;
    let mut last = [0u8; 16];
    last[15] = 1;
    assert_eq!(
        DeckUid::from_bytes(first).unwrap().as_str(),
        "01000000000000000000000000000000"
    );
    assert_eq!(
        DeckUid::from_bytes(last).unwrap().as_str(),
        "00000000000000000000000000000001"
    );
    assert!(DeckUid::from_bytes([0xff; 16]).is_some());
}

#[test]
fn whatever_from_bytes_produces_parse_accepts() {
    // Any byte value, in any position, must land in the canonical alphabet.
    for b in 0..=255u8 {
        for pos in [0usize, 7, 15] {
            let mut bytes = [0u8; 16];
            bytes[pos] = b;
            if let Some(u) = DeckUid::from_bytes(bytes) {
                assert_eq!(DeckUid::parse(u.as_str()).as_ref(), Some(&u), "byte {b}");
            } else {
                assert_eq!(b, 0, "only the all-zero buffer is refused");
            }
        }
    }
}

// --- export ----------------------------------------------------------------------------------

#[test]
fn export_carries_the_identity_the_label_and_the_count_but_not_the_number() {
    let c = deck(3, "Communion");
    let p = export_deck_link(&c, |id| (id == 3).then(|| uid(UID_A))).unwrap();
    assert_eq!(p.uid.as_deref(), Some(UID_A));
    assert_eq!(p.label.as_deref(), Some("Communion"));
    assert_eq!(p.slide_count, Some(7));
}

#[test]
fn export_of_a_deck_the_library_no_longer_holds_is_unidentified_not_guessed() {
    let c = deck(3, "Communion");
    let p = export_deck_link(&c, |_| None).unwrap();
    assert_eq!(p.uid, None);
    assert_eq!(
        p.label.as_deref(),
        Some("Communion"),
        "the name still travels"
    );
}

#[test]
fn export_of_anything_but_a_deck_link_is_none() {
    let scripture = ItemContent::Scripture {
        reference: "John 3:16".to_string(),
        translation: None,
        verses_per_slide: None,
        verse_numbers: None,
    };
    let media = ItemContent::Media { media_id: 3 };
    assert_eq!(export_deck_link(&scripture, |_| Some(uid(UID_A))), None);
    assert_eq!(export_deck_link(&media, |_| Some(uid(UID_A))), None);
}

#[test]
fn export_never_asks_for_the_identity_of_the_unresolved_sentinel() {
    // A link that imported as missing has no presentation behind it. Even a library that would
    // (wrongly) answer for deck 0 must not give it an identity.
    let asked = Cell::new(0u32);
    let p = export_deck_link(&deck(UNRESOLVED_DECK_ID, "Communion"), |_| {
        asked.set(asked.get() + 1);
        Some(uid(UID_A))
    })
    .unwrap();
    assert_eq!(p.uid, None);
    assert_eq!(asked.get(), 0, "the sentinel was looked up");
}

#[test]
fn export_passes_the_largest_local_number_to_the_library_untouched() {
    let seen = Cell::new(0u64);
    let p = export_deck_link(&deck(u64::MAX, "Big"), |id| {
        seen.set(id);
        Some(uid(UID_A))
    })
    .unwrap();
    assert_eq!(seen.get(), u64::MAX);
    assert_eq!(p.uid.as_deref(), Some(UID_A));
}

// --- import: the rule ------------------------------------------------------------------------

#[test]
fn a_known_uid_binds_to_the_receiving_librarys_own_deck_and_its_own_facts() {
    // The link was exported with count 99 and the name "Communion"; on this machine the same
    // presentation is deck 41, has 12 slides and has since been renamed.
    let l = link(Some(UID_A), Some("Communion"));
    let (c, m) = import_deck_link(&l, |u| {
        (u == &uid(UID_A)).then(|| local(41, "Lord's Supper", 12))
    });
    assert_eq!(m, DeckLinkMatch::Matched);
    assert_eq!(
        c,
        ItemContent::Deck {
            deck_id: 41,
            slide_count: Some(12),
            label: Some("Lord's Supper".to_string()),
        }
    );
}

#[test]
fn an_unknown_uid_becomes_the_missing_state_and_keeps_the_name_it_was_exported_with() {
    let l = link(Some(UID_A), Some("Communion"));
    let (c, m) = import_deck_link(&l, |_| None);
    assert_eq!(m, DeckLinkMatch::NotInLibrary);
    assert_eq!(
        c,
        ItemContent::Deck {
            deck_id: UNRESOLVED_DECK_ID,
            slide_count: None,
            label: Some("Communion".to_string()),
        }
    );
}

#[test]
fn an_unidentified_link_is_missing_and_the_library_is_not_even_asked() {
    let asked = Cell::new(0u32);
    let (c, m) = import_deck_link(&link(None, Some("Communion")), |_| {
        asked.set(asked.get() + 1);
        Some(local(3, "Whatever", 1))
    });
    assert_eq!(m, DeckLinkMatch::NotInLibrary);
    assert!(matches!(
        c,
        ItemContent::Deck {
            deck_id: UNRESOLVED_DECK_ID,
            ..
        }
    ));
    assert_eq!(asked.get(), 0);
}

#[test]
fn a_malformed_uid_is_missing_and_the_library_is_not_asked() {
    let hostile = [
        String::new(),
        "3".to_string(),
        UID_A.to_uppercase(),
        format!("{UID_A}{UID_A}"),
        "0".repeat(DECK_UID_HEX_LEN),
        "a".repeat(1 << 20),
        "../../etc/passwd".to_string(),
    ];
    for bad in hostile {
        let asked = Cell::new(0u32);
        let (c, m) = import_deck_link(&link(Some(&bad), Some("X")), |_| {
            asked.set(asked.get() + 1);
            Some(local(3, "Whatever", 1))
        });
        assert_eq!(m, DeckLinkMatch::NotInLibrary, "uid of {} bytes", bad.len());
        assert!(matches!(
            c,
            ItemContent::Deck {
                deck_id: UNRESOLVED_DECK_ID,
                ..
            }
        ));
        assert_eq!(asked.get(), 0, "a malformed uid reached the library");
    }
}

#[test]
fn a_library_answering_with_the_sentinel_is_treated_as_not_found() {
    let (c, m) = import_deck_link(&link(Some(UID_A), Some("Communion")), |_| {
        Some(local(UNRESOLVED_DECK_ID, "Ghost", 5))
    });
    assert_eq!(m, DeckLinkMatch::NotInLibrary);
    assert_eq!(
        c,
        ItemContent::Deck {
            deck_id: UNRESOLVED_DECK_ID,
            slide_count: None,
            label: Some("Communion".to_string()),
        }
    );
}

#[test]
fn the_largest_local_number_binds_like_any_other() {
    let (c, m) = import_deck_link(&link(Some(UID_A), None), |_| {
        Some(local(u64::MAX, "Big", 1))
    });
    assert_eq!(m, DeckLinkMatch::Matched);
    assert!(matches!(
        c,
        ItemContent::Deck {
            deck_id: u64::MAX,
            ..
        }
    ));
}

// There is deliberately no test that "the exporter's number is not an input": `import_deck_link`
// takes only the portable link (whose type has no field for a local number) and a lookup into the
// RECEIVING library, so the compiler already guarantees the property, and a test that looped over
// exporter numbers could not fail. The tests that bite are the ones that fix what the lookup
// returns and assert what comes out (the matched and not-found cases above and below).

#[test]
fn the_same_identity_imported_twice_binds_to_the_same_deck_both_times() {
    let l = link(Some(UID_A), Some("Communion"));
    let find = |u: &DeckUid| (u == &uid(UID_A)).then(|| local(9, "Communion", 4));
    assert_eq!(import_deck_link(&l, find), import_deck_link(&l, find));
}

#[test]
fn two_identities_bind_independently() {
    let find = |u: &DeckUid| {
        if u == &uid(UID_A) {
            Some(local(1, "One", 1))
        } else if u == &uid(UID_B) {
            Some(local(2, "Two", 2))
        } else {
            None
        }
    };
    let (a, _) = import_deck_link(&link(Some(UID_A), None), find);
    let (b, _) = import_deck_link(&link(Some(UID_B), None), find);
    assert!(matches!(a, ItemContent::Deck { deck_id: 1, .. }));
    assert!(matches!(b, ItemContent::Deck { deck_id: 2, .. }));
}

// --- import: hostile labels and bounded output -----------------------------------------------

#[test]
fn an_oversized_label_is_cut_to_the_documented_bound_by_character() {
    let long = "é".repeat(1 << 20); // a megabyte-plus of two-byte characters
    let (c, _) = import_deck_link(&link(None, Some(&long)), |_| None);
    let ItemContent::Deck { label: Some(l), .. } = c else {
        panic!("a label was supplied");
    };
    assert_eq!(l.chars().count(), MAX_LINK_LABEL_LEN);
    // Cut on a character boundary, never inside one.
    assert!(l.chars().all(|ch| ch == 'é'));
}

#[test]
fn a_label_with_control_and_hostile_characters_is_cleaned() {
    let nasty = "Com\tmu\nnion\u{202E}\u{0}";
    let (c, _) = import_deck_link(&link(None, Some(nasty)), |_| None);
    let ItemContent::Deck { label: Some(l), .. } = c else {
        panic!("a label was supplied");
    };
    assert!(
        !l.chars().any(|ch| ch.is_control() || ch == '\u{202E}'),
        "label kept a control or bidi-override character: {l:?}"
    );
    assert!(l.starts_with("Com"));
}

#[test]
fn a_blank_or_invisible_label_is_no_label() {
    for blank in ["", "   ", "\u{200B}\u{200B}", "\t\n"] {
        let (c, _) = import_deck_link(&link(None, Some(blank)), |_| None);
        assert!(
            matches!(c, ItemContent::Deck { label: None, .. }),
            "{blank:?} should not become a name"
        );
    }
}

#[test]
fn a_local_deck_name_is_bounded_too() {
    let (c, _) = import_deck_link(&link(Some(UID_A), None), |_| {
        Some(local(2, &"n".repeat(1 << 20), 1))
    });
    let ItemContent::Deck { label: Some(l), .. } = c else {
        panic!("matched link carries the local name");
    };
    assert_eq!(l.chars().count(), MAX_LINK_LABEL_LEN);
}

#[test]
fn importing_many_hostile_links_keeps_the_total_output_bounded() {
    // The import holds nothing between calls; what it returns is bounded per link. 300 links with
    // 128 KiB labels (the plan cap is far lower) must total no more than 300 bounded labels.
    let huge = "x".repeat(128 * 1024);
    let mut total_label_bytes = 0usize;
    for _ in 0..300 {
        let (c, _) = import_deck_link(&link(Some(UID_A), Some(&huge)), |_| None);
        if let ItemContent::Deck { label: Some(l), .. } = c {
            total_label_bytes += l.len();
        }
    }
    assert!(
        total_label_bytes <= 300 * MAX_LINK_LABEL_LEN * 4,
        "import output is not bounded: {total_label_bytes} bytes"
    );
    // Positive control: the labels were not simply dropped.
    assert!(total_label_bytes >= 300 * MAX_LINK_LABEL_LEN);
}

#[test]
fn only_the_head_of_a_label_is_examined_so_work_does_not_grow_with_the_input() {
    // A label that opens with more invisible characters than the scan window and only then says
    // "Communion" reads as blank: the window is the documented limit, and the tail beyond it is
    // never even copied. This pins the window (remove it and the name appears).
    let window = MAX_LINK_LABEL_LEN * 4;
    let zero_width = "\u{200B}".repeat(window);
    let sneaky = format!("{zero_width}Communion");
    let (c, _) = import_deck_link(&link(None, Some(&sneaky)), |_| None);
    assert!(matches!(c, ItemContent::Deck { label: None, .. }));
    // Positive control: the same name just inside the window survives.
    let inside = format!("{}Communion", "\u{200B}".repeat(window - 20));
    let (c, _) = import_deck_link(&link(None, Some(&inside)), |_| None);
    assert!(matches!(c, ItemContent::Deck { label: Some(ref l), .. } if l == "Communion"));
}

// --- composition with the plan ---------------------------------------------------------------

#[test]
fn an_imported_missing_link_is_stored_and_resolves_as_missing_whatever_the_library_holds() {
    let (content, _) = import_deck_link(&link(Some(UID_A), Some("Communion")), |_| None);
    let mut plan = ServicePlan::new("Sunday");
    let item = plan.add_item(ItemKind::SlideGroup, "Communion");
    plan.set_item_content(item, Some(content)).unwrap();

    let stored = plan.get(item).unwrap().content.clone().unwrap();
    // The label survives the plan's own normalisation.
    assert!(matches!(
        &stored,
        ItemContent::Deck { deck_id: UNRESOLVED_DECK_ID, label: Some(l), .. } if l == "Communion"
    ));
    // A library that holds decks 1..=1000 still reports this link missing, because no library
    // answers to the sentinel (the operator's tests pin that on the real library).
    let resolution = stored.resolve(|_, _| None, |id| Some((1..=1000).contains(&id)), |_| None);
    assert_eq!(resolution, LinkResolution::Missing);
    assert_eq!(
        plan.unresolved_content(|_, _| true, |id| (1..=1000).contains(&id), |_| true),
        vec![item]
    );
}

#[test]
fn an_imported_missing_link_survives_the_persistence_codec() {
    let (content, _) = import_deck_link(&link(Some(UID_A), Some("Communion")), |_| None);
    let decoded = ItemContent::decode(&content.encode()).unwrap();
    assert_eq!(decoded, content);
}

#[test]
fn a_plan_with_no_deck_links_exports_nothing_to_translate() {
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening");
    plan.add_item(ItemKind::Announcement, "Welcome");
    let exported = plan
        .items()
        .iter()
        .filter_map(|it| it.content.as_ref())
        .filter_map(|c| export_deck_link(c, |_| Some(uid(UID_A))))
        .count();
    assert_eq!(exported, 0);
}
