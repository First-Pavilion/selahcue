//! Bounded autosave-SLOT history (FR-005 "last-3"; ticket 86ajy0hxg).

#![allow(clippy::unwrap_used)]

use selahcue_data::autosave_repo::{self, MAX_AUTOSAVE_SLOTS};
use selahcue_data::session_repo::SessionState;
use selahcue_data::Database;

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

fn state(live_idx: Option<u32>) -> SessionState {
    // `plan_id: None` deliberately — the FK is `ON DELETE SET NULL`, so NULL is always valid
    // without needing a real `service_plan` row; these tests exercise the slot ring's
    // bound/order/round-trip, not plan linkage.
    SessionState {
        plan_id: None,
        live_idx,
        ..Default::default()
    }
}

#[test]
fn push_bounds_the_ring_to_max_slots_keeping_the_newest() {
    let db = db();
    for i in 0..(MAX_AUTOSAVE_SLOTS as i64 + 2) {
        autosave_repo::push(&db, &state(Some(i as u32)), 1000 + i, None).unwrap();
    }
    let slots = autosave_repo::list(&db).unwrap();
    assert_eq!(
        slots.len(),
        MAX_AUTOSAVE_SLOTS,
        "the ring must not grow past the bound"
    );
    // Newest-first: the last pushed (live_idx = MAX+1) is slots[0].
    assert_eq!(slots[0].state.live_idx, Some(MAX_AUTOSAVE_SLOTS as u32 + 1));
    // The two oldest pushes (live_idx 0 and 1) must have been pruned away.
    assert!(!slots.iter().any(|s| s.state.live_idx == Some(0)));
    assert!(!slots.iter().any(|s| s.state.live_idx == Some(1)));
}

#[test]
fn load_returns_none_for_a_pruned_or_unknown_slot() {
    let db = db();
    autosave_repo::push(&db, &state(Some(1)), 1000, None).unwrap();
    assert!(autosave_repo::load(&db, 999).unwrap().is_none());
}

#[test]
fn load_round_trips_label_and_state() {
    let db = db();
    autosave_repo::push(&db, &state(Some(7)), 5000, Some("before sermon")).unwrap();
    let slots = autosave_repo::list(&db).unwrap();
    assert_eq!(slots.len(), 1);
    let id = slots[0].id;
    let loaded = autosave_repo::load(&db, id).unwrap().unwrap();
    assert_eq!(loaded.label.as_deref(), Some("before sermon"));
    assert_eq!(loaded.saved_at_ms, 5000);
    assert_eq!(loaded.state.live_idx, Some(7));
}

/// Positive control for the bound above: pushing exactly `MAX_AUTOSAVE_SLOTS` never prunes
/// anything — the bound test above only proves an OVER-cap push prunes; without this, a
/// mutation that pruned unconditionally (e.g. always dropping the oldest) would still pass.
#[test]
fn pushing_up_to_the_bound_prunes_nothing() {
    let db = db();
    for i in 0..MAX_AUTOSAVE_SLOTS as i64 {
        autosave_repo::push(&db, &state(Some(i as u32)), 1000 + i, None).unwrap();
    }
    let slots = autosave_repo::list(&db).unwrap();
    assert_eq!(slots.len(), MAX_AUTOSAVE_SLOTS);
    assert!(slots.iter().any(|s| s.state.live_idx == Some(0)));
}

/// A pushed-but-later-pruned slot leaves nothing dangling: the ring never accumulates rows
/// past the bound even across many pushes (no-leak, bounded-memory convention).
#[test]
fn many_pushes_never_exceed_the_bound() {
    let db = db();
    for i in 0..50i64 {
        autosave_repo::push(&db, &state(Some(i as u32)), 1000 + i, None).unwrap();
    }
    assert_eq!(autosave_repo::list(&db).unwrap().len(), MAX_AUTOSAVE_SLOTS);
}
