//! Public-API tests for the authored slide-deck model (Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_present::deck::{
    AuthoredSlide, DeckId, SlideDeck, SlideId, Transition, MAX_DECK_SLIDES, MAX_NOTES_LEN,
};
use selahcue_present::{Element, Rgba, ShapeKind};

fn a_shape() -> Element {
    Element::Shape {
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
    }
}

#[test]
fn add_slide_assigns_stable_monotonic_ids_in_order() {
    let mut deck = SlideDeck::new("Sermon: Grace That Feeds");
    assert!(deck.is_empty());
    let a = deck.add_slide().unwrap();
    let b = deck.add_slide().unwrap();
    assert_eq!((a, b), (SlideId(1), SlideId(2)));
    assert_eq!(deck.len(), 2);
    // Removing a slide retires its id: the next add does NOT reuse it.
    assert!(deck.remove(a));
    let c = deck.add_slide().unwrap();
    assert_eq!(c, SlideId(3), "ids are never reused");
    assert!(deck.get(a).is_none());
    assert_eq!(deck.index_of(c), Some(1));
}

#[test]
fn slides_carry_their_own_layered_content() {
    let mut deck = SlideDeck::new("Deck");
    let id = deck.add_slide().unwrap();
    let slide = deck.get_mut(id).unwrap();
    slide.elements.push(a_shape());
    slide.notes = "read slowly".to_string();
    slide.transition = Transition::Fade;
    slide.auto_advance_secs = Some(8);
    let s = deck.get(id).unwrap();
    assert_eq!(s.elements.len(), 1);
    assert_eq!(s.notes, "read slowly");
    assert_eq!(s.transition, Transition::Fade);
    assert_eq!(s.auto_advance_secs, Some(8));
}

#[test]
fn insert_reorder_and_duplicate_maintain_order() {
    let mut deck = SlideDeck::new("Deck");
    let a = deck.add_slide().unwrap();
    let b = deck.add_slide().unwrap();
    let c = deck.insert_slide(1).unwrap(); // between a and b
    assert_eq!(
        deck.slides().iter().map(|s| s.id).collect::<Vec<_>>(),
        vec![a, c, b],
        "insert lands at the index"
    );
    // Reorder: move the first (a) to the end.
    assert!(deck.reorder(0, 2));
    assert_eq!(
        deck.slides().iter().map(|s| s.id).collect::<Vec<_>>(),
        vec![c, b, a]
    );
    // Duplicate b → a deep copy directly after it, with a fresh id.
    deck.get_mut(b).unwrap().elements.push(a_shape());
    let dup = deck.duplicate(b).unwrap();
    let order: Vec<SlideId> = deck.slides().iter().map(|s| s.id).collect();
    assert_eq!(
        order,
        vec![c, b, dup, a],
        "the duplicate follows the original"
    );
    assert_eq!(
        deck.get(dup).unwrap().elements,
        deck.get(b).unwrap().elements,
        "the duplicate is a deep copy of the content"
    );
    assert_ne!(dup, b, "the duplicate has a new id");
}

#[test]
fn reorder_is_a_noop_at_the_edges_and_when_empty() {
    let mut deck = SlideDeck::new("Deck");
    assert!(!deck.reorder(0, 1), "empty deck → no-op");
    deck.add_slide().unwrap();
    deck.add_slide().unwrap();
    assert!(!deck.reorder(1, 1), "same index → no-op");
    // Out-of-range indices clamp into range rather than panicking.
    assert!(deck.reorder(9, 0));
}

#[test]
fn a_new_slide_serialises_to_just_its_id_byte_stable_additive() {
    // The whole point of the skip-default serde: a brand-new empty slide's JSON is minimal, so
    // adding a field later never bloats existing slides.
    let slide = AuthoredSlide::new(SlideId(1));
    let js = serde_json::to_string(&slide).unwrap();
    assert_eq!(js, r#"{"id":1}"#, "an empty slide is just its id");
    for absent in [
        "elements",
        "background",
        "notes",
        "transition",
        "auto_advance",
    ] {
        assert!(!js.contains(absent), "{absent} is omitted when defaulted");
    }
}

#[test]
fn non_default_transition_and_auto_advance_serialise_and_round_trip() {
    // The two non-default AuthoredSlide fields must actually appear in JSON when set (the
    // skip-default only omits the DEFAULT), and survive a round-trip.
    let mut slide = AuthoredSlide::new(SlideId(2));
    slide.transition = Transition::Fade;
    slide.auto_advance_secs = Some(8);
    let js = serde_json::to_string(&slide).unwrap();
    assert!(
        js.contains(r#""transition":"fade""#),
        "Fade is serialised: {js}"
    );
    assert!(
        js.contains(r#""auto_advance_secs":8"#),
        "auto-advance is serialised: {js}"
    );
    let back: AuthoredSlide = serde_json::from_str(&js).unwrap();
    assert_eq!(
        back, slide,
        "non-default transition + auto-advance round-trip"
    );
}

#[test]
fn a_rehydrated_deck_with_a_stale_next_id_never_mints_a_colliding_id() {
    // Defence-in-depth: a deck loaded from a corrupt/tampered blob whose `next_id` is behind its
    // slide ids must still mint a fresh, collision-free id (a colliding id would make `remove`
    // delete two slides at once). The mint self-heals past the highest existing id.
    let mut deck: SlideDeck =
        serde_json::from_str(r#"{"name":"D","slides":[{"id":1},{"id":2}],"next_id":1}"#).unwrap();
    let fresh = deck.add_slide().unwrap();
    assert!(
        fresh.0 > 2,
        "the minted id jumps past the highest existing slide id"
    );
    let dup = deck.duplicate(SlideId(2)).unwrap();
    assert!(dup.0 > fresh.0, "duplicate also mints a collision-free id");
    // Every slide id is now unique.
    let mut ids: Vec<u64> = deck.slides().iter().map(|s| s.id.0).collect();
    let before = ids.len();
    ids.sort_unstable();
    ids.dedup();
    assert_eq!(
        ids.len(),
        before,
        "no two slides share an id after the self-healing mints"
    );
}

#[test]
fn deck_id_is_additive_byte_stable_and_round_trips() {
    // A deck with no assigned id (DeckId(0)) serialises WITHOUT an `id` key — byte-identical to the
    // pre-id format `{name,slides,next_id}`, so persisted decks + the pinned repo fixture are
    // unchanged. Old JSON (no id) deserialises to the unassigned DeckId(0).
    let deck = SlideDeck::new("Sermon");
    assert_eq!(deck.id(), DeckId(0), "a fresh deck is unassigned");
    assert_eq!(
        serde_json::to_string(&deck).unwrap(),
        r#"{"name":"Sermon","slides":[],"next_id":1}"#,
        "an unassigned deck's JSON is byte-identical to the pre-id format"
    );
    let back: SlideDeck = serde_json::from_str(r#"{"name":"D","slides":[],"next_id":1}"#).unwrap();
    assert_eq!(back.id(), DeckId(0), "old JSON without id → unassigned");

    // Once the library assigns an id, it serialises and round-trips.
    let mut assigned = SlideDeck::new("Grace");
    assigned.set_id(DeckId(42));
    let js2 = serde_json::to_string(&assigned).unwrap();
    assert!(
        js2.contains(r#""id":42"#),
        "an assigned id serialises: {js2}"
    );
    assert_eq!(
        serde_json::from_str::<SlideDeck>(&js2).unwrap().id(),
        DeckId(42),
        "the assigned id round-trips"
    );
}

#[test]
fn old_json_missing_fields_deserialises_to_defaults() {
    // Forward-compat: a slide persisted before these fields existed still loads.
    let slide: AuthoredSlide = serde_json::from_str(r#"{"id":5}"#).unwrap();
    assert_eq!(slide.id, SlideId(5));
    assert!(slide.elements.is_empty());
    assert!(slide.background.is_none());
    assert!(slide.notes.is_empty());
    assert_eq!(slide.transition, Transition::Cut);
    assert_eq!(slide.auto_advance_secs, None);
}

#[test]
fn a_full_deck_round_trips_through_serde() {
    let mut deck = SlideDeck::new("Grace That Feeds");
    let id = deck.add_slide().unwrap();
    deck.get_mut(id).unwrap().elements.push(a_shape());
    deck.get_mut(id).unwrap().notes = "pause after 'vinedressers'".to_string();
    deck.add_slide().unwrap();
    let js = serde_json::to_string(&deck).unwrap();
    let back: SlideDeck = serde_json::from_str(&js).unwrap();
    assert_eq!(
        back, deck,
        "the whole deck (name + slides + id counter) round-trips"
    );
}

#[test]
fn the_deck_is_bounded_no_unbounded_growth() {
    // Bounded-memory guarantee: add_slide stops at MAX_DECK_SLIDES and never grows past it.
    let mut deck = SlideDeck::new("Big");
    for _ in 0..MAX_DECK_SLIDES {
        assert!(deck.add_slide().is_some());
    }
    assert_eq!(deck.len(), MAX_DECK_SLIDES);
    assert!(deck.add_slide().is_none(), "add past the cap is rejected");
    assert!(
        deck.insert_slide(0).is_none(),
        "insert past the cap is rejected"
    );
    let full = deck.slides()[0].id;
    assert!(
        deck.duplicate(full).is_none(),
        "duplicate past the cap is rejected"
    );
    assert_eq!(
        deck.len(),
        MAX_DECK_SLIDES,
        "the deck never exceeds the cap"
    );
    assert!(deck.within_bounds());
}

#[test]
fn notes_over_the_cap_are_out_of_bounds() {
    // The bounded-memory check catches an over-long notes string (no-leak).
    let mut slide = AuthoredSlide::new(SlideId(1));
    slide.notes = "x".repeat(MAX_NOTES_LEN);
    assert!(slide.within_bounds());
    slide.notes.push('!');
    assert!(
        !slide.within_bounds(),
        "notes past the cap are out of bounds"
    );
}
