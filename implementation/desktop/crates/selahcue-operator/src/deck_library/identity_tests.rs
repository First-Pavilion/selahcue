//! Two independent libraries with deliberately overlapping numbering (86ak196cr · FINDING-LIB-07).
//!
//! The single-library case cannot show the defect or the fix: the defect needs two machines each
//! handing out 1, 2, 3 to unrelated presentations. Everything here builds two (or more) real
//! [`DeckLibrary`] values, moves plan links between them through the same boundary the plan-bundle
//! import (FR-139, 86ak0qn15) must use -- [`DeckLibrary::export_link`] on the source and
//! [`DeckLibrary::import_link`] on the destination -- and asserts the one invariant that matters:
//! **an imported link is either the same presentation or explicitly missing, never a different
//! one.** `assert_same_or_missing` is that invariant, stated once and used by every test.

#![allow(clippy::unwrap_used)]

use super::*;
use selahcue_core::deck_ref::{PortableDeckLink, UNRESOLVED_DECK_ID};
use selahcue_core::plan::{ItemId, ItemKind, ServicePlan, MAX_LINK_LABEL_LEN, MAX_PLAN_ITEMS};
use selahcue_present::{Element, Rgba, ShapeKind, Transition};
use std::sync::atomic::{AtomicU64, Ordering};

// --- fixtures --------------------------------------------------------------------------------

/// A fresh in-memory library holding `names`, created in order (so they get ids 1, 2, 3, ...).
fn library_with(names: &[&str]) -> DeckLibrary {
    let mut lib = DeckLibrary::load(None);
    for n in names {
        lib.create(n);
    }
    lib
}

/// Machine A: Communion is deck number 3 here.
fn machine_a() -> DeckLibrary {
    library_with(&["Welcome", "Songs", "Communion"])
}

/// Machine B: unrelated presentations -- and "Guest Speaker - Notes" is ALSO deck number 3.
fn machine_b() -> DeckLibrary {
    library_with(&["Youth Night", "Baptism", "Guest Speaker - Notes"])
}

fn id_of(lib: &DeckLibrary, name: &str) -> DeckId {
    lib.list().into_iter().find(|m| m.name == name).unwrap().id
}

fn deck_link(lib: &DeckLibrary, name: &str) -> ItemContent {
    ItemContent::Deck {
        deck_id: id_of(lib, name).0,
        slide_count: lib.get(id_of(lib, name)).map(|d| d.len() as u32),
        label: Some(name.to_string()),
    }
}

/// A plan with one slide-group item per name, each linked to that deck in `lib`.
fn plan_linking(lib: &DeckLibrary, names: &[&str]) -> ServicePlan {
    let mut plan = ServicePlan::new("Sunday");
    for n in names {
        let item = plan.add_item(ItemKind::SlideGroup, *n);
        plan.set_item_content(item, Some(deck_link(lib, n)))
            .unwrap();
    }
    plan
}

/// Move `plan` from `src` to `dst` through the boundary: every deck link is exported by identity
/// and re-bound against the destination; every other item travels as it is. Returns the plan as
/// the destination sees it and how each deck link bound, in item order.
fn transfer(
    plan: &ServicePlan,
    src: &DeckLibrary,
    dst: &DeckLibrary,
) -> (ServicePlan, Vec<DeckLinkMatch>) {
    let mut out = ServicePlan::new(plan.name.clone());
    let mut matches = Vec::new();
    for it in plan.items() {
        let id = out.add_item(it.kind, it.title.clone());
        let content = match it.content.as_ref() {
            Some(c) => match src.export_link(c) {
                Some(portable) => {
                    let (bound, how) = dst.import_link(&portable);
                    matches.push(how);
                    Some(bound)
                }
                None => match c {
                    // Media ids are per-library numbers too (17tnw2b9ahh). This helper is the
                    // worked example for the plan-bundle import, so it must not teach the
                    // by-number habit for media: refuse rather than pass the number through.
                    ItemContent::Media { .. } => {
                        panic!("media ids are per-library numbers; see 17tnw2b9ahh")
                    }
                    other => Some(other.clone()),
                },
            },
            None => None,
        };
        out.set_item_content(id, content).unwrap();
    }
    (out, matches)
}

fn deck_id_of(plan: &ServicePlan, item: ItemId) -> u64 {
    match plan.get(item).unwrap().content.as_ref().unwrap() {
        ItemContent::Deck { deck_id, .. } => *deck_id,
        other => panic!("expected a deck link, got {other:?}"),
    }
}

/// THE invariant (RULE-LIB-XFER-01): for every deck link in `src_plan`, the link at the same
/// position in `dst_plan` points either at the destination deck with the SAME identity, or at
/// nothing at all. It compares identities, not names, so a coincidentally equal name cannot make a
/// wrong deck look right.
fn assert_same_or_missing(
    src_plan: &ServicePlan,
    src: &DeckLibrary,
    dst_plan: &ServicePlan,
    dst: &DeckLibrary,
) {
    assert_eq!(src_plan.len(), dst_plan.len());
    for (s, d) in src_plan.items().iter().zip(dst_plan.items()) {
        let Some(ItemContent::Deck {
            deck_id: src_id, ..
        }) = &s.content
        else {
            continue;
        };
        let ItemContent::Deck {
            deck_id: dst_id, ..
        } = d.content.as_ref().unwrap()
        else {
            panic!("a deck link stopped being a deck link");
        };
        if *dst_id == UNRESOLVED_DECK_ID {
            continue; // explicitly missing: allowed
        }
        let shown = dst.uid_of(DeckId(*dst_id));
        assert!(
            shown.is_some() && shown == src.uid_of(DeckId(*src_id)),
            "link {:?} ({}) now shows destination deck {:?} ({:?}) -- a different presentation",
            s.title,
            src_id,
            dst_id,
            dst.get(DeckId(*dst_id)).map(|x| x.name)
        );
    }
}

// Entropy sources for the library's identity minting.
fn counting_entropy() -> Option<[u8; 16]> {
    static N: AtomicU64 = AtomicU64::new(1);
    let mut b = [0u8; 16];
    b[0] = 0xAB;
    b[8..].copy_from_slice(&N.fetch_add(1, Ordering::SeqCst).to_be_bytes());
    Some(b)
}
thread_local! {
    static DRAWS: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
}
/// Like [`counting_entropy`] but per test thread, so a test can read how many draws it caused.
fn draw_counting_entropy() -> Option<[u8; 16]> {
    let n = DRAWS.with(|d| {
        d.set(d.get() + 1);
        d.get()
    });
    let mut b = [0xCD; 16];
    b[8..].copy_from_slice(&n.to_be_bytes());
    Some(b)
}
fn draws() -> u64 {
    DRAWS.with(std::cell::Cell::get)
}
fn stuck_entropy() -> Option<[u8; 16]> {
    Some([7; 16])
}
fn zero_entropy() -> Option<[u8; 16]> {
    Some([0; 16])
}
fn no_entropy() -> Option<[u8; 16]> {
    None
}

/// A directory removed on drop, holding one sqlite file, for the persistence tests.
struct TempDb(std::path::PathBuf);
impl TempDb {
    fn new(tag: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("selahcue-ident-{}-{tag}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        TempDb(dir)
    }
    fn open(&self) -> Database {
        Database::open(self.0.join("lib.sqlite")).unwrap()
    }
}
impl Drop for TempDb {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// A deck row exactly as an install from before identities existed stored it (no `uid` key).
fn legacy_row(id: u64, name: &str, slides: u64) -> String {
    let slides_json: Vec<String> = (1..=slides).map(|s| format!(r#"{{"id":{s}}}"#)).collect();
    format!(
        r#"{{"name":"{name}","id":{id},"slides":[{}],"next_id":{}}}"#,
        slides_json.join(","),
        slides + 1
    )
}

const UID_X: &str = "0123456789abcdef0123456789abcdef";

// --- the defect, and the fix -----------------------------------------------------------------

#[test]
fn premise_both_libraries_hand_out_the_same_numbers_to_different_decks() {
    // If this stops being true the tests below stop proving anything.
    let (a, b) = (machine_a(), machine_b());
    assert_eq!(a.get(DeckId(3)).unwrap().name, "Communion");
    assert_eq!(b.get(DeckId(3)).unwrap().name, "Guest Speaker - Notes");
}

/// CHARACTERISATION of the old hazard, not a guarantee: what the product could do before this
/// change to move a link between machines (write it with the plan codec, read it back, look the
/// NUMBER up in the receiving library) still lands on a different presentation, because the lookup
/// by number is unchanged and still public. It is kept to say why the identity exists. It asserts
/// the bug's behaviour, so it goes RED if lookup by number is ever made safe (for example by
/// carrying the uid on the plan link, 17tnw2b9ahj): delete or invert it then.
#[test]
fn characterisation_lookup_by_number_alone_still_shows_a_different_presentation() {
    let (a, b) = (machine_a(), machine_b());
    let plan = plan_linking(&a, &["Communion"]);
    let wire = plan.items()[0].content.as_ref().unwrap().encode();
    let ItemContent::Deck { deck_id, .. } = ItemContent::decode(&wire).unwrap() else {
        panic!("a deck link stays a deck link");
    };
    assert_eq!(
        b.get(DeckId(deck_id)).unwrap().name,
        "Guest Speaker - Notes"
    );
}

/// The acceptance test for the ticket: the same scenario, carried through the boundary.
#[test]
fn a_link_carried_through_the_boundary_never_shows_a_different_presentation() {
    let (a, b) = (machine_a(), machine_b());
    let plan = plan_linking(&a, &["Communion"]);
    let (imported, matches) = transfer(&plan, &a, &b);

    assert_eq!(matches, vec![DeckLinkMatch::NotInLibrary]);
    let item = imported.items()[0].id;
    assert_eq!(deck_id_of(&imported, item), UNRESOLVED_DECK_ID);
    assert_same_or_missing(&plan, &a, &imported, &b);
    // ...and the operator is told before the service, with the presentation's name.
    let missing =
        imported.unresolved_content(|_, _| true, |id| b.get(DeckId(id)).is_some(), |_| true);
    assert_eq!(missing, vec![item]);
    assert!(matches!(
        imported.items()[0].content.as_ref().unwrap(),
        ItemContent::Deck { label: Some(l), .. } if l == "Communion"
    ));
}

#[test]
fn every_link_into_an_overlapping_populated_library_is_missing_never_another_deck() {
    // A holds five presentations; B holds three unrelated ones. Numbers 1..=3 collide, 4 and 5 do
    // not exist on B at all -- exactly the "any link numbered N or lower" shape of the ticket.
    let names = ["Welcome", "Songs", "Communion", "Offering", "Benediction"];
    let a = library_with(&names);
    let b = machine_b();
    let plan = plan_linking(&a, &names);
    let (imported, matches) = transfer(&plan, &a, &b);

    assert_eq!(matches, vec![DeckLinkMatch::NotInLibrary; 5]);
    assert_same_or_missing(&plan, &a, &imported, &b);
    for it in imported.items() {
        assert_eq!(
            deck_id_of(&imported, it.id),
            UNRESOLVED_DECK_ID,
            "{}",
            it.title
        );
    }
    assert_eq!(
        imported
            .unresolved_content(|_, _| true, |id| b.get(DeckId(id)).is_some(), |_| true)
            .len(),
        5,
        "every one of them is flagged for the operator"
    );
}

#[test]
fn a_presentation_present_on_both_machines_under_different_numbers_resolves_to_the_receivers_own() {
    let (a, mut b) = (machine_a(), machine_b());
    // The same presentation reaches B (a file copied over): B adopts it, so it keeps its identity
    // but takes B's next number, 4.
    let communion_on_a = a.get(id_of(&a, "Communion")).unwrap();
    let on_b = b.adopt_trusted_identity(communion_on_a);
    assert_eq!(on_b.id(), DeckId(4), "it is not number 3 on this machine");
    assert_eq!(b.get(DeckId(3)).unwrap().name, "Guest Speaker - Notes");

    // B's copy has been edited since: three slides, not one.
    let mut edited = b.get(on_b.id()).unwrap();
    edited.add_slide();
    edited.add_slide();
    b.store(&edited);

    let plan = plan_linking(&a, &["Communion"]);
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::Matched]);
    let item = imported.items()[0].id;
    assert_eq!(
        deck_id_of(&imported, item),
        4,
        "B's own number for it, not A's 3"
    );
    assert_same_or_missing(&plan, &a, &imported, &b);
    // The count shown is B's copy, not the 1 slide A exported.
    assert!(matches!(
        imported.items()[0].content.as_ref().unwrap(),
        ItemContent::Deck {
            slide_count: Some(3),
            ..
        }
    ));
    assert!(imported
        .unresolved_content(|_, _| true, |id| b.get(DeckId(id)).is_some(), |_| true)
        .is_empty());
}

#[test]
fn a_mixed_plan_binds_each_link_on_its_own_merits() {
    let (a, mut b) = (machine_a(), machine_b());
    b.adopt_trusted_identity(a.get(id_of(&a, "Welcome")).unwrap()); // B gets Welcome (number 4); not Songs, not Communion
    let plan = plan_linking(&a, &["Welcome", "Songs", "Communion"]);
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(
        matches,
        vec![
            DeckLinkMatch::Matched,
            DeckLinkMatch::NotInLibrary,
            DeckLinkMatch::NotInLibrary
        ]
    );
    assert_same_or_missing(&plan, &a, &imported, &b);
    let ids: Vec<u64> = imported
        .items()
        .iter()
        .map(|i| deck_id_of(&imported, i.id))
        .collect();
    assert_eq!(ids, vec![4, UNRESOLVED_DECK_ID, UNRESOLVED_DECK_ID]);
}

#[test]
fn importing_into_an_empty_library_is_all_missing() {
    let a = machine_a();
    let empty = DeckLibrary::load(None);
    let plan = plan_linking(&a, &["Welcome", "Songs", "Communion"]);
    let (imported, matches) = transfer(&plan, &a, &empty);
    assert_eq!(matches, vec![DeckLinkMatch::NotInLibrary; 3]);
    assert_same_or_missing(&plan, &a, &imported, &empty);
    assert!(empty.is_empty(), "importing never creates a deck");
}

#[test]
fn a_plan_with_no_deck_links_transfers_unchanged_and_touches_nothing() {
    let (a, b) = (machine_a(), machine_b());
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening");
    plan.add_item(ItemKind::Announcement, "Welcome");
    let before = b.list();
    let (imported, matches) = transfer(&plan, &a, &b);
    assert!(matches.is_empty(), "no deck link, nothing to bind");
    assert_eq!(imported.len(), 2);
    assert_eq!(imported.items()[1].title, "Welcome");
    assert_eq!(b.list(), before);
}

#[test]
fn a_plan_referencing_the_same_deck_twice_binds_both_to_the_same_local_deck() {
    let (a, mut b) = (machine_a(), machine_b());
    b.adopt_trusted_identity(a.get(id_of(&a, "Communion")).unwrap());
    let mut plan = plan_linking(&a, &["Communion"]);
    let again = plan.add_item(ItemKind::SlideGroup, "Communion (again)");
    plan.set_item_content(again, Some(deck_link(&a, "Communion")))
        .unwrap();
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::Matched; 2]);
    let first = deck_id_of(&imported, imported.items()[0].id);
    let second = deck_id_of(&imported, imported.items()[1].id);
    assert_eq!(first, second);
    assert_eq!(first, 4);
}

#[test]
fn a_duplicate_and_its_original_are_different_presentations_on_the_other_machine_too() {
    let mut a = machine_a();
    let original = id_of(&a, "Communion");
    let copy = a.duplicate(original).unwrap();
    assert_ne!(
        a.uid_of(original),
        a.uid_of(copy.id()),
        "a copy is its own presentation"
    );

    // B holds only the copy.
    let mut b = machine_b();
    b.adopt_trusted_identity(a.get(copy.id()).unwrap());

    let plan = plan_linking(&a, &["Communion", "Communion copy"]);
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(
        matches,
        vec![DeckLinkMatch::NotInLibrary, DeckLinkMatch::Matched]
    );
    assert_same_or_missing(&plan, &a, &imported, &b);
}

#[test]
fn renaming_on_either_machine_does_not_break_the_match_and_the_shown_name_is_the_receivers() {
    let (mut a, mut b) = (machine_a(), machine_b());
    b.adopt_trusted_identity(a.get(id_of(&a, "Communion")).unwrap());
    let plan = plan_linking(&a, &["Communion"]); // label "Communion" is baked in at link time

    let a_id = id_of(&a, "Communion");
    a.rename(a_id, "The Lord's Supper").unwrap();
    let b_id = id_of(&b, "Communion");
    b.rename(b_id, "Holy Communion").unwrap();

    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::Matched]);
    assert_same_or_missing(&plan, &a, &imported, &b);
    assert!(matches!(
        imported.items()[0].content.as_ref().unwrap(),
        ItemContent::Deck { label: Some(l), .. } if l == "Holy Communion"
    ));
}

#[test]
fn a_deck_deleted_on_the_source_is_exported_unidentified_and_is_missing_even_where_it_exists() {
    let (mut a, mut b) = (machine_a(), machine_b());
    b.adopt_trusted_identity(a.get(id_of(&a, "Communion")).unwrap());
    let plan = plan_linking(&a, &["Communion"]);
    let communion = id_of(&a, "Communion");

    a.delete(communion);
    // The source can no longer say WHICH presentation the number meant, so it says nothing.
    let portable = a
        .export_link(plan.items()[0].content.as_ref().unwrap())
        .unwrap();
    assert_eq!(portable.uid, None);
    assert_eq!(portable.label.as_deref(), Some("Communion"));
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::NotInLibrary]);
    assert_same_or_missing(&plan, &a, &imported, &b);

    // Undo the delete: the identity comes back with the deck, and the link matches again.
    assert!(a.restore(communion).is_some());
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::Matched]);
    assert_same_or_missing(&plan, &a, &imported, &b);
}

#[test]
fn export_then_import_on_the_same_machine_gives_back_the_same_deck() {
    let a = machine_a();
    let plan = plan_linking(&a, &["Welcome", "Songs", "Communion"]);
    let (imported, matches) = transfer(&plan, &a, &a);
    assert_eq!(matches, vec![DeckLinkMatch::Matched; 3]);
    for (s, d) in plan.items().iter().zip(imported.items()) {
        assert_eq!(deck_id_of(&plan, s.id), deck_id_of(&imported, d.id));
    }
}

#[test]
fn a_link_that_imported_as_missing_stays_missing_when_exported_onward() {
    // ADR-0031 known limit 1, pinned: a link that bound to nothing keeps only its name, so a third
    // machine that DOES hold the presentation cannot match it. Safe, not ideal. If the identity is
    // ever carried on the plan link (17tnw2b9ahj) this test should flip to Matched.
    let (a, b) = (machine_a(), machine_b());
    let mut c = library_with(&["Songs for Youth"]);
    c.adopt_trusted_identity(a.get(id_of(&a, "Communion")).unwrap());

    let plan = plan_linking(&a, &["Communion"]);
    let (on_b, how_b) = transfer(&plan, &a, &b);
    assert_eq!(how_b, vec![DeckLinkMatch::NotInLibrary]);
    let (on_c, how_c) = transfer(&on_b, &b, &c);
    assert_eq!(how_c, vec![DeckLinkMatch::NotInLibrary]);
    assert_same_or_missing(&on_b, &b, &on_c, &c);
    assert!(matches!(
        on_c.items()[0].content.as_ref().unwrap(),
        ItemContent::Deck { deck_id: UNRESOLVED_DECK_ID, label: Some(l), .. } if l == "Communion"
    ));
}

#[test]
#[should_panic(expected = "media ids are per-library numbers")]
fn the_worked_example_refuses_to_carry_a_media_number_across() {
    let (a, b) = (machine_a(), machine_b());
    let mut plan = ServicePlan::new("Sunday");
    let item = plan.add_item(ItemKind::Media, "Photo");
    plan.set_item_content(item, Some(ItemContent::Media { media_id: 3 }))
        .unwrap();
    let _ = transfer(&plan, &a, &b);
}

#[test]
fn very_large_deck_numbers_bind_by_identity_like_any_other() {
    let (ta, tb) = (TempDb::new("big-a"), TempDb::new("big-b"));
    let big = u64::MAX;
    deck_repo::save_one(&ta.open(), "Giant", &legacy_row(big, "Giant", 2)).unwrap();
    deck_repo::save_one(
        &tb.open(),
        "Other Giant",
        &legacy_row(big, "Other Giant", 1),
    )
    .unwrap();
    let a = DeckLibrary::load(Some(ta.open()));
    let b = DeckLibrary::load(Some(tb.open()));
    assert_eq!(a.get(DeckId(big)).unwrap().name, "Giant");
    assert_eq!(
        b.get(DeckId(big)).unwrap().name,
        "Other Giant",
        "the numbers collide at the maximum"
    );

    let plan = plan_linking(&a, &["Giant"]);
    let (imported, matches) = transfer(&plan, &a, &b);
    assert_eq!(matches, vec![DeckLinkMatch::NotInLibrary]);
    assert_same_or_missing(&plan, &a, &imported, &b);

    let (back, matches) = transfer(&plan, &a, &a);
    assert_eq!(matches, vec![DeckLinkMatch::Matched]);
    assert_eq!(deck_id_of(&back, back.items()[0].id), big);
}

#[test]
fn nothing_in_a_library_ever_answers_to_the_unresolved_number() {
    let mut lib = machine_a();
    lib.delete(DeckId(1));
    assert!(lib.get(DeckId(UNRESOLVED_DECK_ID)).is_none());
    assert!(lib.uid_of(DeckId(UNRESOLVED_DECK_ID)).is_none());
    assert!(lib.list().iter().all(|m| m.id.0 != UNRESOLVED_DECK_ID));
    // A stored row claiming number 0 is healed to a real number, so it cannot become an answer.
    let t = TempDb::new("zero");
    deck_repo::save_one(&t.open(), "Zero", &legacy_row(0, "Zero", 1)).unwrap();
    let healed = DeckLibrary::load(Some(t.open()));
    assert!(healed.list().iter().all(|m| m.id.0 != UNRESOLVED_DECK_ID));
    let uid = healed
        .list()
        .first()
        .and_then(|m| healed.uid_of(m.id))
        .unwrap();
    assert_ne!(healed.find_by_uid(&uid).unwrap().id, UNRESOLVED_DECK_ID);
}

// --- hostile bundle contents -----------------------------------------------------------------

#[test]
fn a_hostile_bundle_cannot_hit_a_deck_by_malformed_identity_and_changes_nothing() {
    let mut b = machine_b();
    let before = b.list();
    let hostile_uids = [
        String::new(),
        "1".to_string(),
        "3".to_string(),
        UID_X.to_uppercase(),
        format!("{UID_X}{UID_X}"),
        "0".repeat(32),
        "../../x".to_string(),
        "a".repeat(1 << 20),
    ];
    for bad in hostile_uids {
        let link = PortableDeckLink {
            uid: Some(bad.clone()),
            slide_count: Some(u32::MAX),
            label: Some("Communion".to_string()),
        };
        let (content, how) = b.import_link(&link);
        assert_eq!(
            how,
            DeckLinkMatch::NotInLibrary,
            "uid of {} bytes",
            bad.len()
        );
        assert!(matches!(
            content,
            ItemContent::Deck {
                deck_id: UNRESOLVED_DECK_ID,
                ..
            }
        ));
    }
    // A well-formed identity nobody holds is missing too.
    let (_, how) = b.import_link(&PortableDeckLink {
        uid: Some(UID_X.to_string()),
        slide_count: None,
        label: None,
    });
    assert_eq!(how, DeckLinkMatch::NotInLibrary);
    // Importing reads the library only: nothing added, removed or renumbered.
    assert_eq!(b.list(), before);
    assert_eq!(
        b.create("Next").id(),
        DeckId(4),
        "the number counter did not move"
    );
}

#[test]
fn a_bundle_at_the_plan_cap_with_hostile_labels_is_bounded_and_leaves_the_library_alone() {
    // MAX_PLAN_ITEMS links, each with a very long label: the import must neither grow without
    // bound nor touch the library. Positive control: the labels are kept, just cut.
    let b = machine_b();
    let before = b.list();
    let huge = "n".repeat(300 * 1024);
    let mut total = 0usize;
    for _ in 0..MAX_PLAN_ITEMS {
        let (content, _) = b.import_link(&PortableDeckLink {
            uid: Some(UID_X.to_string()),
            slide_count: None,
            label: Some(huge.clone()),
        });
        let ItemContent::Deck { label: Some(l), .. } = content else {
            panic!("a label was supplied");
        };
        assert!(l.chars().count() <= MAX_LINK_LABEL_LEN);
        total += l.len();
    }
    assert!(
        total >= MAX_PLAN_ITEMS * MAX_LINK_LABEL_LEN,
        "labels were dropped, not cut"
    );
    assert!(
        total <= MAX_PLAN_ITEMS * MAX_LINK_LABEL_LEN * 4,
        "labels are not bounded: {total}"
    );
    assert_eq!(b.list(), before);
}

#[test]
fn a_forged_identity_can_only_ever_reach_the_deck_that_really_has_it() {
    // By design the identity IS the claim: whoever writes a bundle can name any uid. What it buys
    // them is exactly the deck that carries that uid -- never a neighbour by number or by name.
    let b = machine_b();
    let b_deck = id_of(&b, "Guest Speaker - Notes");
    let b_uid = b.uid_of(b_deck).unwrap();
    let forged = PortableDeckLink {
        uid: Some(b_uid.as_str().to_string()),
        slide_count: None,
        label: Some("Communion".to_string()),
    };
    let (content, how) = b.import_link(&forged);
    assert_eq!(how, DeckLinkMatch::Matched);
    // And the label shown is B's own, not the forger's "Communion".
    assert!(matches!(
        content,
        ItemContent::Deck { deck_id, label: Some(ref l), .. }
            if deck_id == b_deck.0 && l == "Guest Speaker - Notes"
    ));
}

// --- identities: how the library mints, keeps and refuses them -------------------------------

#[test]
fn every_created_deck_gets_a_valid_identity_and_no_two_share_one() {
    let mut lib = DeckLibrary::load(None);
    let uids: Vec<DeckUid> = (0..25)
        .map(|i| lib.create(&format!("Deck {i}")).uid().cloned().unwrap())
        .collect();
    let distinct: std::collections::HashSet<&DeckUid> = uids.iter().collect();
    assert_eq!(distinct.len(), uids.len());
    assert!(uids.iter().all(|u| DeckUid::parse(u.as_str()).is_some()));
}

#[test]
fn the_identity_survives_rename_store_replace_and_delete_then_restore() {
    let mut lib = DeckLibrary::load(None);
    let id = lib.create("Sermon").id();
    let uid = lib.uid_of(id).unwrap();

    // rename
    lib.rename(id, "Sermon - Grace").unwrap();
    assert_eq!(lib.uid_of(id), Some(uid.clone()));

    // store: an editor copy that carries NO identity, and one that carries a FOREIGN one
    let mut editing = lib.get(id).unwrap();
    editing.set_uid(None);
    lib.store(&editing);
    assert_eq!(
        lib.uid_of(id),
        Some(uid.clone()),
        "store kept the library's identity"
    );
    editing.set_uid(DeckUid::parse(UID_X));
    lib.store(&editing);
    assert_eq!(
        lib.uid_of(id),
        Some(uid.clone()),
        "an editor copy cannot rewrite the identity"
    );

    // replace (ADR-0024 decision 5): the incoming deck brings its own, different identity
    let mut incoming = SlideDeck::new("Imported");
    incoming.set_uid(DeckUid::parse(UID_X));
    lib.replace_deck(id, incoming, None).unwrap();
    assert_eq!(
        lib.uid_of(id),
        Some(uid.clone()),
        "replace keeps the target's identity"
    );

    // delete is not "in the library"; restore brings the same identity back
    assert!(lib.delete(id));
    assert!(
        lib.find_by_uid(&uid).is_none(),
        "a deleted deck is missing, not claimable"
    );
    assert!(lib.restore(id).is_some());
    assert_eq!(lib.find_by_uid(&uid).unwrap().id, id.0);
}

#[test]
fn a_duplicate_is_a_new_identity_and_the_original_keeps_its_own() {
    let mut lib = DeckLibrary::load(None);
    let id = lib.create("Sermon").id();
    let original = lib.uid_of(id).unwrap();
    let copy = lib.duplicate(id).unwrap();
    assert_ne!(copy.uid().cloned(), Some(original.clone()));
    assert!(copy.uid().is_some());
    assert_eq!(lib.uid_of(id), Some(original.clone()));
    assert_eq!(lib.find_by_uid(&original).unwrap().id, id.0);
}

#[test]
fn adopt_always_mints_a_fresh_identity_even_when_a_valid_free_one_arrives() {
    let mut lib = DeckLibrary::load(None);
    let mut arriving = SlideDeck::new("Traveller");
    arriving.set_uid(DeckUid::parse(UID_X));
    let adopted = lib.adopt(arriving);
    assert!(adopted.uid().is_some());
    assert_ne!(
        adopted.uid().map(DeckUid::as_str),
        Some(UID_X),
        "adopt honoured a claimed uid"
    );
    assert!(lib.find_by_uid(&DeckUid::parse(UID_X).unwrap()).is_none());

    // No identity at all: minted. The very same deck adopted twice yields two identities.
    let plain = SlideDeck::new("Plain");
    let first = lib.adopt(plain.clone());
    let second = lib.adopt(plain);
    assert!(first.uid().is_some() && second.uid().is_some());
    assert_ne!(first.uid(), second.uid());
}

#[test]
fn a_hostile_deck_cannot_choose_its_identity_through_adopt_or_adopt_with_policy() {
    let mut lib = DeckLibrary::load(None);
    let real = lib.create("Real");
    let real_uid = real.uid().cloned().unwrap();
    let claim = |name: &str, uid: Option<DeckUid>| {
        let mut d = SlideDeck::new(name);
        d.set_uid(uid);
        d
    };
    // Claiming the real deck's identity, under each policy that can add a deck.
    let by_adopt = lib.adopt(claim("Hostile via adopt", Some(real_uid.clone())));
    assert_ne!(by_adopt.uid().cloned(), Some(real_uid.clone()));
    for (name, policy) in [
        ("Hostile keep-both", NameCollisionPolicy::KeepBoth),
        ("Hostile fail", NameCollisionPolicy::Fail),
    ] {
        let d = lib
            .adopt_with_policy(claim(name, Some(real_uid.clone())), policy, None)
            .unwrap();
        assert_ne!(d.uid().cloned(), Some(real_uid.clone()), "{name}");
    }
    // On a NAME collision KeepBoth files the deck beside the original, and still mints -- even
    // when the identity it claims is free (a held one would be re-minted by any code).
    let beside = lib
        .adopt_with_policy(
            claim("Real", DeckUid::parse(UID_X)),
            NameCollisionPolicy::KeepBoth,
            None,
        )
        .unwrap();
    assert_eq!(beside.name, "Real (2)");
    assert_ne!(beside.uid().map(DeckUid::as_str), Some(UID_X));
    // Claiming a FREE identity is not honoured either.
    let free = lib
        .adopt_with_policy(
            claim("Hostile free", DeckUid::parse(UID_X)),
            NameCollisionPolicy::KeepBoth,
            None,
        )
        .unwrap();
    assert_ne!(free.uid().map(DeckUid::as_str), Some(UID_X));
    // Replace keeps the TARGET's identity, whatever the incoming deck says.
    let replaced = lib
        .adopt_with_policy(
            claim("Real", DeckUid::parse(UID_X)),
            NameCollisionPolicy::Replace,
            None,
        )
        .unwrap();
    assert_eq!(replaced.uid().cloned(), Some(real_uid.clone()));
    // Through all of that the real deck is still the only holder of its identity, and nobody got UID_X.
    assert_eq!(lib.find_by_uid(&real_uid).unwrap().name, "Real");
    assert!(lib.find_by_uid(&DeckUid::parse(UID_X).unwrap()).is_none());
}

#[test]
fn a_refused_adopt_mints_nothing_and_an_accepted_one_mints_exactly_once() {
    let mut lib = DeckLibrary::load_inner(None, draw_counting_entropy);
    let id = lib.create("Sermon").id();
    let uid = lib.uid_of(id);
    let base = draws();
    let again = || SlideDeck::new("Sermon");

    let refused = lib.adopt_with_policy(again(), NameCollisionPolicy::Fail, None);
    assert_eq!(refused.unwrap_err(), AdoptError::NameTaken);
    let live = lib.adopt_with_policy(again(), NameCollisionPolicy::Replace, Some(id));
    assert_eq!(live.unwrap_err(), AdoptError::TargetIsLive);
    assert_eq!(draws(), base, "a refused adopt drew identity bits");

    lib.adopt_with_policy(again(), NameCollisionPolicy::KeepBoth, None)
        .unwrap();
    assert_eq!(
        draws(),
        base + 1,
        "an accepted adopt mints exactly one identity"
    );

    lib.adopt_with_policy(again(), NameCollisionPolicy::Replace, None)
        .unwrap();
    assert_eq!(
        draws(),
        base + 1,
        "replace keeps the target's identity and mints none"
    );
    assert_eq!(lib.uid_of(id), uid);
}

#[test]
fn the_trusted_adopt_keeps_a_free_identity_but_never_a_held_one() {
    let mut lib = DeckLibrary::load(None);
    let held = lib.create("Existing");
    let held_uid = held.uid().cloned().unwrap();

    // A deck arriving with an identity nobody here has keeps it: the same presentation stays the
    // same presentation.
    let mut free = SlideDeck::new("Traveller");
    free.set_uid(DeckUid::parse(UID_X));
    let adopted = lib.adopt_trusted_identity(free);
    assert_eq!(adopted.uid().map(DeckUid::as_str), Some(UID_X));

    // One arriving with a held identity (a copy, or a hostile claim) gets a fresh one.
    let mut clash = SlideDeck::new("Clash");
    clash.set_uid(Some(held_uid.clone()));
    let adopted = lib.adopt_trusted_identity(clash);
    assert_ne!(adopted.uid().cloned(), Some(held_uid.clone()));
    assert!(adopted.uid().is_some());
    assert_eq!(lib.find_by_uid(&held_uid).unwrap().name, "Existing");

    // An identity held only by a deck in the undo-delete trash is held too: restoring that deck
    // must not put two decks under one identity.
    let trashed = lib.create("Soon gone");
    let trashed_uid = trashed.uid().cloned().unwrap();
    lib.delete(trashed.id());
    let mut claim = SlideDeck::new("Claims the trashed one");
    claim.set_uid(Some(trashed_uid.clone()));
    let adopted = lib.adopt_trusted_identity(claim);
    assert_ne!(adopted.uid().cloned(), Some(trashed_uid.clone()));
    lib.restore(trashed.id()).unwrap();
    assert_eq!(lib.find_by_uid(&trashed_uid).unwrap().name, "Soon gone");

    // None at all: minted.
    let plain = lib.adopt_trusted_identity(SlideDeck::new("Plain"));
    assert!(plain.uid().is_some());
}

#[test]
fn identities_persist_across_a_reopen() {
    let t = TempDb::new("reopen");
    let (id, uid) = {
        let mut lib = DeckLibrary::load(Some(t.open()));
        let d = lib.create("Sermon");
        (d.id(), d.uid().cloned().unwrap())
    };
    let lib = DeckLibrary::load(Some(t.open()));
    assert_eq!(lib.uid_of(id), Some(uid.clone()));
    assert_eq!(lib.find_by_uid(&uid).unwrap().id, id.0);
}

// --- equivalence over existing rows (acceptance criterion 4) ---------------------------------

/// A deck as an install from before identities existed stored it: real content (several slides
/// with shapes, notes, transitions and auto-advance), no `uid` key.
fn rich_legacy_deck(id: u64, name: &str, slides: u64) -> SlideDeck {
    let mut d = SlideDeck::new(name);
    d.set_id(DeckId(id));
    for i in 0..slides {
        let sid = d.add_slide().unwrap();
        let s = d.get_mut(sid).unwrap();
        s.notes = format!("notes {i} for {name}");
        s.transition = Transition::Fade;
        s.auto_advance_secs = Some(5 + i as u32);
        s.elements.push(Element::Shape {
            x_permille: 100,
            y_permille: 100,
            w_permille: 200,
            h_permille: 200,
            fill: Rgba::rgb(200, 30, 30),
            border: Rgba::new(0, 0, 0, 0),
            border_permille: 0,
            opacity: 255,
            z: 0,
            variant: ShapeKind::Rect,
            corner_permille: 0,
            visible: true,
        });
    }
    assert!(d.uid().is_none(), "premise: a legacy deck has no identity");
    d
}

fn save_legacy(db: &Database, deck: &SlideDeck) {
    deck_repo::save_one(db, &deck.name, &serde_json::to_string(deck).unwrap()).unwrap();
    assert!(
        !serde_json::to_string(deck).unwrap().contains("uid"),
        "premise: the stored row has no uid key"
    );
}

#[test]
fn decks_stored_before_identities_existed_are_given_one_once_and_nothing_else_changes() {
    let t = TempDb::new("legacy");
    let originals = [
        rich_legacy_deck(1, "Welcome", 2),
        rich_legacy_deck(2, "Songs", 3),
        rich_legacy_deck(3, "Communion", 1),
        rich_legacy_deck(9, "Sparse", 4),
    ];
    {
        let db = t.open();
        for d in &originals {
            save_legacy(&db, d);
        }
    }
    // The plan as it was saved before the change: links by number, in the persistence codec.
    let stored_links: Vec<(u64, String)> = originals
        .iter()
        .map(|d| {
            let c = ItemContent::Deck {
                deck_id: d.id().0,
                slide_count: None,
                label: Some(d.name.clone()),
            };
            (d.id().0, c.encode())
        })
        .collect();

    let (first, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_eq!(
        stats,
        BackfillStats {
            attempted: 4,
            failed: 0
        }
    );
    // Same decks, same numbers, same names, same slides: only the identity is new.
    let summary = |lib: &DeckLibrary| -> Vec<(u64, String, usize)> {
        lib.list()
            .into_iter()
            .map(|m| (m.id.0, m.name, m.slides))
            .collect()
    };
    assert_eq!(
        summary(&first),
        vec![
            (3, "Communion".to_string(), 1),
            (2, "Songs".to_string(), 3),
            (9, "Sparse".to_string(), 4),
            (1, "Welcome".to_string(), 2),
        ]
    );
    // Every stored link still resolves to the same presentation it did before, on this machine.
    for (id, encoded) in &stored_links {
        let ItemContent::Deck { deck_id, label, .. } = ItemContent::decode(encoded).unwrap() else {
            panic!("stored a deck link");
        };
        assert_eq!(deck_id, *id);
        assert_eq!(first.get(DeckId(deck_id)).unwrap().name, label.unwrap());
    }
    let uids: Vec<DeckUid> = first
        .list()
        .iter()
        .map(|m| first.uid_of(m.id).unwrap())
        .collect();
    assert_eq!(
        uids.iter().collect::<std::collections::HashSet<_>>().len(),
        4,
        "four decks, four distinct identities"
    );

    // Stable: a second launch reads the same identities back instead of minting new ones, and
    // writes nothing (there is nothing left to backfill).
    drop(first);
    let (second, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_eq!(stats, BackfillStats::default());
    let uids_again: Vec<DeckUid> = second
        .list()
        .iter()
        .map(|m| second.uid_of(m.id).unwrap())
        .collect();
    assert_eq!(uids, uids_again);
    assert_eq!(summary(&second).len(), 4);

    // The stored rows are the original decks WHOLE (every slide, element, note, transition and
    // timing; the number too) with exactly one thing added: the identity.
    let rows = deck_repo::load_all(&t.open()).unwrap();
    assert_eq!(rows.len(), 4, "backfilling added no rows");
    for (key, json) in rows {
        let mut stored: SlideDeck = serde_json::from_str(&json).unwrap();
        assert_eq!(key, stored.name);
        assert_eq!(stored.uid().cloned(), second.uid_of(stored.id()));
        stored.set_uid(None);
        let original = originals.iter().find(|d| d.name == key).unwrap();
        assert_eq!(&stored, original, "row {key} changed beyond the identity");
    }
}

#[test]
fn healing_never_leaves_two_decks_sharing_an_identity_and_replaces_a_damaged_one() {
    let t = TempDb::new("heal");
    {
        let db = t.open();
        let with_uid = |id: u64, name: &str, uid_json: &str| {
            format!(
                r#"{{"name":"{name}","id":{id},"uid":{uid_json},"slides":[{{"id":1}}],"next_id":2}}"#
            )
        };
        deck_repo::save_one(
            &db,
            "First",
            &with_uid(1, "First", &format!(r#""{UID_X}""#)),
        )
        .unwrap();
        deck_repo::save_one(
            &db,
            "Second",
            &with_uid(2, "Second", &format!(r#""{UID_X}""#)),
        )
        .unwrap();
        deck_repo::save_one(&db, "Third", &with_uid(3, "Third", r#""not-a-uid""#)).unwrap();
        deck_repo::save_one(&db, "Fourth", &with_uid(4, "Fourth", "12345")).unwrap();
    }
    let lib = DeckLibrary::load(Some(t.open()));
    assert_eq!(
        lib.list().len(),
        4,
        "a damaged identity never costs the deck"
    );
    let uids: Vec<DeckUid> = lib
        .list()
        .iter()
        .map(|m| lib.uid_of(m.id).unwrap())
        .collect();
    assert_eq!(
        uids.iter().collect::<std::collections::HashSet<_>>().len(),
        4
    );
    // The first holder of the shared identity keeps it; the later copy is the one re-minted.
    assert_eq!(
        lib.uid_of(DeckId(1)).map(|u| u.as_str().to_string()),
        Some(UID_X.to_string())
    );
    assert_ne!(lib.uid_of(DeckId(2)), lib.uid_of(DeckId(1)));

    // The healed identities were persisted: a second launch sees the same four, and heals nothing.
    drop(lib);
    let (again, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_eq!(
        stats,
        BackfillStats::default(),
        "the second launch had nothing to heal"
    );
    let uids_again: Vec<DeckUid> = again
        .list()
        .iter()
        .map(|m| again.uid_of(m.id).unwrap())
        .collect();
    assert_eq!(
        uids, uids_again,
        "healed identities are stable across launches"
    );
}

// --- the backfill writes only to the row it read (Shadow S-C1) -------------------------------

#[test]
fn the_backfill_never_overwrites_a_row_other_than_the_one_it_read() {
    // A database in the state the heal code and its tests already expect (a restored, hand-edited
    // or older-build file): row "Alpha" holds an old 1-slide copy whose JSON name is "Zed", and
    // row "Zed" holds the real 3-slide "Zed". Writing a healed deck back by its JSON name would
    // land the copy on row "Zed" and destroy the real presentation.
    let t = TempDb::new("rowkey");
    let alpha_row = legacy_row(1, "Zed", 1);
    let zed_row = legacy_row(2, "Zed", 3);
    let beta_row = legacy_row(3, "Beta", 2);
    {
        let db = t.open();
        deck_repo::save_one(&db, "Alpha", &alpha_row).unwrap();
        deck_repo::save_one(&db, "Zed", &zed_row).unwrap();
        deck_repo::save_one(&db, "Beta", &beta_row).unwrap();
    }
    let rows_now = || deck_repo::load_all(&t.open()).unwrap();
    let before = rows_now();
    let slides_of = |lib: &DeckLibrary| {
        let mut v: Vec<usize> = lib.list().iter().map(|m| m.slides).collect();
        v.sort_unstable();
        v
    };

    for launch in 1..=2 {
        let lib = DeckLibrary::load_inner(Some(t.open()), counting_entropy);
        // No presentation was lost, and all three are identified in memory.
        assert_eq!(slides_of(&lib), vec![1, 2, 3], "launch {launch}");
        assert!(lib.list().iter().all(|m| lib.uid_of(m.id).is_some()));
        // The two rows whose key disagrees with the name inside them are byte-identical.
        let after = rows_now();
        for key in ["Alpha", "Zed"] {
            let b = before.iter().find(|(k, _)| k == key).unwrap();
            let a = after.iter().find(|(k, _)| k == key).unwrap();
            assert_eq!(a, b, "launch {launch}: row {key} was rewritten");
        }
        assert_eq!(
            after.len(),
            3,
            "launch {launch}: a row appeared or vanished"
        );
    }
    // The ordinary row beside them WAS backfilled (so the guard is not just switching the
    // backfill off): same deck, plus an identity.
    let beta = rows_now().into_iter().find(|(k, _)| k == "Beta").unwrap().1;
    let mut parsed: SlideDeck = serde_json::from_str(&beta).unwrap();
    assert!(parsed.uid().is_some(), "the control row was not backfilled");
    parsed.set_uid(None);
    assert_eq!(
        parsed,
        serde_json::from_str::<SlideDeck>(&beta_row).unwrap()
    );
}

fn rows_of(t: &TempDb) -> Vec<(String, String)> {
    deck_repo::load_all(&t.open()).unwrap()
}

/// Launch the library twice over `t` (counting entropy) and, after each launch, assert every row is
/// byte-identical to `before` and the decks read are exactly `expected_slides` (sorted).
fn assert_rows_untouched_across_two_launches(
    t: &TempDb,
    before: &[(String, String)],
    expected_slides: &[usize],
) {
    for launch in 1..=2 {
        let (lib, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
        let mut slides: Vec<usize> = lib.list().iter().map(|m| m.slides).collect();
        slides.sort_unstable();
        assert_eq!(
            slides, expected_slides,
            "launch {launch}: a deck was lost or doubled"
        );
        assert!(
            lib.list().iter().all(|m| lib.uid_of(m.id).is_some()),
            "launch {launch}: every deck is still identified in memory"
        );
        assert_eq!(stats.attempted, 0, "launch {launch}: something was written");
        drop(lib);
        assert_eq!(
            rows_of(t),
            before,
            "launch {launch}: a row was written, added or removed"
        );
    }
}

#[test]
fn an_unreadable_row_never_shifts_which_row_a_deck_is_written_to() {
    // Row "A" cannot be parsed and is skipped. If its key were still recorded, every later deck
    // would be paired with the PREVIOUS row's key: the deck named "B" (read from row "C") would be
    // paired with key "B", look like it belongs there, and be written over row "B", destroying
    // that row's real presentation "Q".
    let t = TempDb::new("unreadable-shift");
    {
        let db = t.open();
        deck_repo::save_one(&db, "A", "{this is not json").unwrap();
        deck_repo::save_one(&db, "B", &legacy_row(1, "Q", 1)).unwrap();
        deck_repo::save_one(&db, "C", &legacy_row(2, "B", 3)).unwrap();
    }
    let before = rows_of(&t);
    assert_eq!(before.len(), 3);
    assert_rows_untouched_across_two_launches(&t, &before, &[1, 3]);
}

#[test]
fn a_healed_name_equal_to_an_unreadable_rows_key_never_writes_over_that_row() {
    // The same pairing hazard in the shape where the colliding key belongs to the unreadable row
    // itself: the deck read from row "X" is healed in memory to "Untitled presentation", which is
    // exactly the key of a row that cannot be read. Writing it by name would replace that row.
    let t = TempDb::new("unreadable-collide");
    {
        let db = t.open();
        deck_repo::save_one(&db, "X", &legacy_row(1, "", 2)).unwrap();
        deck_repo::save_one(&db, "Untitled presentation", "{not json").unwrap();
        deck_repo::save_one(&db, "Alpha", &legacy_row(2, "Zed", 1)).unwrap();
        deck_repo::save_one(&db, "Zed", &legacy_row(3, "Zed", 3)).unwrap();
        deck_repo::save_one(&db, "Zed (2)", "{also not json").unwrap();
    }
    let before = rows_of(&t);
    assert_eq!(before.len(), 5);
    assert_rows_untouched_across_two_launches(&t, &before, &[1, 2, 3]);
}

#[test]
fn a_key_that_differs_from_the_name_only_by_case_or_a_space_is_never_written_as_a_second_row() {
    // SQLite keys are case- and space-sensitive, so a write by the JSON name would be a SECOND row.
    // A guard that compared the key and the name case-insensitively or trimmed would allow it.
    let t = TempDb::new("case-only");
    deck_repo::save_one(&t.open(), "zed", &legacy_row(1, "Zed", 2)).unwrap();
    deck_repo::save_one(&t.open(), "Gamma ", &legacy_row(2, "Gamma", 1)).unwrap();
    let before = rows_of(&t);
    assert_rows_untouched_across_two_launches(&t, &before, &[1, 2]);
}

#[test]
fn a_mismatched_key_with_no_row_at_the_deck_name_does_not_multiply_the_library() {
    // Row "Alpha" holds a deck named "Gamma" and no row "Gamma" exists: a write by name would
    // create one, and the library would then hold the same presentation twice.
    let t = TempDb::new("no-multiply");
    deck_repo::save_one(&t.open(), "Alpha", &legacy_row(1, "Gamma", 2)).unwrap();
    deck_repo::save_one(&t.open(), "Beta", &legacy_row(2, "Beta", 1)).unwrap();
    let before = rows_of(&t);
    for launch in 1..=3 {
        let (lib, _) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
        assert_eq!(lib.list().len(), 2, "launch {launch}: decks multiplied");
        drop(lib);
        let after = rows_of(&t);
        assert_eq!(after.len(), 2, "launch {launch}: rows multiplied");
        assert_eq!(
            after.iter().find(|(k, _)| k == "Alpha"),
            before.iter().find(|(k, _)| k == "Alpha"),
            "launch {launch}: the mismatched row was rewritten"
        );
    }
}

#[test]
fn a_three_way_name_collision_loses_nothing_and_writes_only_the_deck_that_owns_its_row() {
    // Rows "Mid" and "Zed" both hold a deck named "Zed"; row "Zed (2)" holds one named "Zed (2)".
    // In memory the later "Zed" becomes "Zed (3)". Only the deck whose in-memory name still equals
    // its own row key ("Zed (2)") may be written, and then only to gain its uid.
    let t = TempDb::new("three-way");
    deck_repo::save_one(&t.open(), "Mid", &legacy_row(1, "Zed", 1)).unwrap();
    deck_repo::save_one(&t.open(), "Zed", &legacy_row(2, "Zed", 3)).unwrap();
    deck_repo::save_one(&t.open(), "Zed (2)", &legacy_row(3, "Zed (2)", 5)).unwrap();
    let before = rows_of(&t);
    let without_uid = |json: &str| {
        let mut v: serde_json::Value = serde_json::from_str(json).unwrap();
        v.as_object_mut().unwrap().remove("uid");
        v
    };
    for launch in 1..=2 {
        let lib = DeckLibrary::load_inner(Some(t.open()), counting_entropy);
        let mut slides: Vec<usize> = lib.list().iter().map(|m| m.slides).collect();
        slides.sort_unstable();
        assert_eq!(slides, vec![1, 3, 5], "launch {launch}: a deck was lost");
        drop(lib);
        let after = rows_of(&t);
        assert_eq!(
            after.len(),
            3,
            "launch {launch}: a row appeared or vanished"
        );
        for key in ["Mid", "Zed"] {
            assert_eq!(
                after.iter().find(|(k, _)| k == key),
                before.iter().find(|(k, _)| k == key),
                "launch {launch}: row {key} was written"
            );
        }
        let find = |rows: &[(String, String)]| {
            without_uid(&rows.iter().find(|(k, _)| k == "Zed (2)").unwrap().1)
        };
        assert_eq!(
            find(&after),
            find(&before),
            "launch {launch}: more than the uid changed"
        );
    }
}

#[test]
fn duplicate_stored_numbers_are_healed_persisted_and_stable() {
    let t = TempDb::new("dup-ids");
    deck_repo::save_one(&t.open(), "One", &legacy_row(1, "One", 1)).unwrap();
    deck_repo::save_one(&t.open(), "Two", &legacy_row(1, "Two", 2)).unwrap();
    let facts = |lib: &DeckLibrary| -> Vec<(String, u64, Option<DeckUid>)> {
        lib.list()
            .iter()
            .map(|m| (m.name.clone(), m.id.0, lib.uid_of(m.id)))
            .collect()
    };
    let first = DeckLibrary::load(Some(t.open()));
    let a = facts(&first);
    drop(first);
    let b = facts(&DeckLibrary::load(Some(t.open())));
    assert_eq!(
        a, b,
        "the healed numbers and identities are stable across launches"
    );
    assert_ne!(a[0].1, a[1].1, "the duplicate number was healed");
}

#[test]
fn a_deck_deleted_and_re_created_under_the_same_name_is_a_new_presentation() {
    let mut lib = DeckLibrary::load(None);
    let id = lib.create("Communion").id();
    let link = lib.export_link(&deck_link(&lib, "Communion")).unwrap();
    assert!(lib.delete(id));
    lib.create("Communion");
    // The old link names the deleted presentation, which is neither in the library nor (as a
    // trashed deck) claimable: it must not bind to the new one that merely shares a name.
    assert_eq!(lib.import_link(&link).1, DeckLinkMatch::NotInLibrary);
}

#[test]
fn a_blank_named_row_never_gains_a_second_row_and_its_identity_is_new_each_launch() {
    // A row whose name had to be healed in memory cannot be written back without creating a second
    // row, so it is skipped: identified in memory, re-identified on every launch. Anything
    // exported from it therefore fails closed on the next launch, never to a wrong deck.
    let t = TempDb::new("blankname");
    deck_repo::save_one(&t.open(), "", &legacy_row(1, "", 1)).unwrap();

    let (first, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_eq!(
        stats,
        BackfillStats::default(),
        "nothing was written for it"
    );
    assert_eq!(first.list()[0].name, "Untitled presentation");
    let uid_then = first.uid_of(DeckId(1));
    assert!(uid_then.is_some(), "identified in memory for this launch");
    let exported = first
        .export_link(&deck_link(&first, "Untitled presentation"))
        .unwrap();
    assert!(exported.uid.is_some());
    drop(first);
    assert_eq!(
        deck_repo::load_all(&t.open()).unwrap().len(),
        1,
        "no second row"
    );

    let (second, _) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_ne!(
        second.uid_of(DeckId(1)),
        uid_then,
        "re-minted on the next launch"
    );
    assert_eq!(
        second.import_link(&exported).1,
        DeckLinkMatch::NotInLibrary,
        "yesterday's export fails closed"
    );
    assert_eq!(
        deck_repo::load_all(&t.open()).unwrap().len(),
        1,
        "still no second row"
    );
}

#[test]
fn the_backfill_gives_up_at_the_first_failed_write_and_the_next_launch_retries() {
    let t = TempDb::new("failwrite");
    {
        let db = t.open();
        for (id, name) in [(1, "One"), (2, "Two"), (3, "Three"), (4, "Four")] {
            deck_repo::save_one(&db, name, &legacy_row(id, name, 1)).unwrap();
        }
    }
    let before = deck_repo::load_all(&t.open()).unwrap();

    // A read-only handle: every read works and every write fails.
    let read_only = Database::open_existing_readonly(t.0.join("lib.sqlite")).unwrap();
    let (lib, stats) = DeckLibrary::load_reporting(Some(read_only), counting_entropy);
    assert_eq!(
        stats,
        BackfillStats {
            attempted: 1,
            failed: 1
        },
        "it kept writing after the first failure"
    );
    assert!(
        lib.list().iter().all(|m| lib.uid_of(m.id).is_some()),
        "all four are still identified in memory"
    );
    drop(lib);
    assert_eq!(
        deck_repo::load_all(&t.open()).unwrap(),
        before,
        "nothing was written"
    );

    // The next launch, with a writable database, retries and writes all four.
    let (_, stats) = DeckLibrary::load_reporting(Some(t.open()), counting_entropy);
    assert_eq!(
        stats,
        BackfillStats {
            attempted: 4,
            failed: 0
        }
    );
}

// --- a platform with no randomness, or a broken one ------------------------------------------

#[test]
fn without_randomness_decks_still_work_unidentified_and_a_later_launch_identifies_them() {
    let t = TempDb::new("noentropy");
    deck_repo::save_one(&t.open(), "Welcome", &legacy_row(1, "Welcome", 2)).unwrap();
    {
        let mut lib = DeckLibrary::load_inner(Some(t.open()), no_entropy);
        assert_eq!(lib.get(DeckId(1)).unwrap().len(), 2, "the deck still opens");
        assert!(lib.uid_of(DeckId(1)).is_none());
        let created = lib.create("Made offline");
        assert!(
            created.uid().is_none(),
            "creating still works, unidentified"
        );
        // Unidentified exports as such, and so can only import as missing.
        let link = deck_link(&lib, "Welcome");
        let portable = lib.export_link(&link).unwrap();
        assert_eq!(portable.uid, None);
        assert_eq!(lib.import_link(&portable).1, DeckLinkMatch::NotInLibrary);
    }
    let lib = DeckLibrary::load_inner(Some(t.open()), counting_entropy);
    assert!(lib.uid_of(DeckId(1)).is_some(), "healed on the next launch");
    assert!(lib.uid_of(DeckId(2)).is_some());
}

#[test]
fn a_stuck_source_never_hands_two_decks_the_same_identity() {
    let mut lib = DeckLibrary::load_inner(None, stuck_entropy);
    let decks: Vec<SlideDeck> = (0..4).map(|i| lib.create(&format!("D{i}"))).collect();
    let held: Vec<&DeckUid> = decks.iter().filter_map(|d| d.uid()).collect();
    assert_eq!(
        held.len(),
        1,
        "the one draw it could offer went to the first deck"
    );
    // duplicate() under the same source: refused rather than shared.
    let copy = lib.duplicate(decks[0].id()).unwrap();
    assert!(copy.uid().is_none());
}

#[test]
fn the_all_zero_draw_is_never_an_identity() {
    let mut lib = DeckLibrary::load_inner(None, zero_entropy);
    let d = lib.create("Zeroed");
    assert!(d.uid().is_none());
    assert_eq!(lib.list().len(), 1);
}

#[test]
fn the_production_source_gives_fresh_non_zero_bits_on_every_call() {
    // The one real source: two libraries on two machines draw from it independently, so a constant
    // or repeating answer would hand different presentations the same identity -- the defect again.
    let draws: Vec<[u8; 16]> = (0..32).map(|_| os_entropy().unwrap()).collect();
    assert!(draws.iter().all(|d| d.iter().any(|b| *b != 0)));
    let distinct: std::collections::HashSet<&[u8; 16]> = draws.iter().collect();
    assert_eq!(distinct.len(), draws.len());
}
