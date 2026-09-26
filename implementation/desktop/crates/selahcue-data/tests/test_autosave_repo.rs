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

/// `push` with no label and no fingerprint — the common case for most of these tests, which
/// exercise the ring's bound/order/round-trip, not the fingerprint guard (see
/// `implementation/desktop/crates/selahcue-desktop/src/main.rs`'s `autosave_restore_tests` for
/// that — this crate stores/retrieves the fingerprint faithfully; comparing it is the caller's
/// job, per the module doc).
fn push(db: &Database, live_idx: Option<u32>, saved_at_ms: i64) {
    autosave_repo::push(db, &state(live_idx), saved_at_ms, None, None).unwrap();
}

#[test]
fn push_bounds_the_ring_to_max_slots_keeping_the_newest() {
    let db = db();
    for i in 0..(MAX_AUTOSAVE_SLOTS as i64 + 2) {
        push(&db, Some(i as u32), 1000 + i);
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
    push(&db, Some(1), 1000);
    assert!(autosave_repo::load(&db, 999).unwrap().is_none());
}

#[test]
fn load_round_trips_label_and_state() {
    let db = db();
    autosave_repo::push(&db, &state(Some(7)), 5000, Some("before sermon"), None).unwrap();
    let slots = autosave_repo::list(&db).unwrap();
    assert_eq!(slots.len(), 1);
    let id = slots[0].id;
    let loaded = autosave_repo::load(&db, id).unwrap().unwrap();
    assert_eq!(loaded.label.as_deref(), Some("before sermon"));
    assert_eq!(loaded.saved_at_ms, 5000);
    assert_eq!(loaded.state.live_idx, Some(7));
}

/// `plan_fingerprint` round-trips exactly like every other field — the guard that COMPARES it
/// lives in the caller (`selahcue-desktop`), but this crate must store and return it faithfully
/// or that guard has nothing reliable to compare against.
#[test]
fn load_round_trips_the_plan_fingerprint() {
    let db = db();
    autosave_repo::push(&db, &state(Some(2)), 1000, None, Some("fingerprint-abc")).unwrap();
    let slots = autosave_repo::list(&db).unwrap();
    assert_eq!(
        slots[0].plan_fingerprint.as_deref(),
        Some("fingerprint-abc")
    );
    let loaded = autosave_repo::load(&db, slots[0].id).unwrap().unwrap();
    assert_eq!(loaded.plan_fingerprint.as_deref(), Some("fingerprint-abc"));
}

/// Positive control for the bound above: pushing exactly `MAX_AUTOSAVE_SLOTS` never prunes
/// anything — the bound test above only proves an OVER-cap push prunes; without this, a
/// mutation that pruned unconditionally (e.g. always dropping the oldest) would still pass.
#[test]
fn pushing_up_to_the_bound_prunes_nothing() {
    let db = db();
    for i in 0..MAX_AUTOSAVE_SLOTS as i64 {
        push(&db, Some(i as u32), 1000 + i);
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
        push(&db, Some(i as u32), 1000 + i);
    }
    assert_eq!(autosave_repo::list(&db).unwrap().len(), MAX_AUTOSAVE_SLOTS);
}

/// Regression for a bug Sana reproduced live against real SQLite in PR #102's security review
/// (S-4): pruning by `saved_at_ms DESC` instead of `id` meant a backward WALL-CLOCK jump (NTP
/// correction, manual clock change) made every subsequent push look "older" than the existing
/// three, so the prune kept deleting the just-inserted row and the ring silently froze on the
/// pre-jump slots forever — `push` still returned `Ok(())`, nothing logged the failure. Fill the
/// ring at ascending timestamps, then push MORE entries at timestamps that go BACKWARD: the ring
/// must still advance to the newest (by insertion order), never freeze.
#[test]
fn a_backward_wall_clock_jump_does_not_freeze_the_ring() {
    let db = db();
    for i in 0..MAX_AUTOSAVE_SLOTS as i64 {
        push(&db, Some(i as u32), 1000 + i);
    }
    // Positive control: before the clock jump, the ring holds exactly the three just pushed.
    let before = autosave_repo::list(&db).unwrap();
    assert_eq!(before.len(), MAX_AUTOSAVE_SLOTS);
    assert!(before.iter().any(|s| s.state.live_idx == Some(0)));

    // The wall clock jumps BACKWARD (e.g. an NTP correction) for the next two captures.
    push(&db, Some(100), 500);
    push(&db, Some(101), 560);

    let after = autosave_repo::list(&db).unwrap();
    assert_eq!(
        after.len(),
        MAX_AUTOSAVE_SLOTS,
        "the ring must stay at the bound, not grow"
    );
    assert!(
        after.iter().any(|s| s.state.live_idx == Some(101)),
        "the ring must advance to the newest INSERTED slot even under a backward clock jump — \
         got {:?}",
        after.iter().map(|s| s.state.live_idx).collect::<Vec<_>>()
    );
    assert!(
        !after.iter().any(|s| s.state.live_idx == Some(0)),
        "the oldest pre-jump slot must have been pruned, not the just-inserted one"
    );
}
