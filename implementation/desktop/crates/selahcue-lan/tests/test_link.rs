//! Control-link state: the console may only say what is true.
//!
//! Three of the four fabrications this programme exists to remove are connection-pill lies, so
//! these tests are written as refutations of each specific lie rather than as generic coverage.

#![allow(clippy::unwrap_used)]

use selahcue_lan::link::{LinkState, LinkStatus, MAX_ERROR_LEN, MAX_RECONNECT_ATTEMPTS};

/// The premise the "gives up" tests depend on. Pinned at compile time so raising the breaker
/// cannot quietly turn those tests into assertions about a state they never reach.
const _: () = assert!(MAX_RECONNECT_ATTEMPTS >= 2);

/// **Fabrication 3.** The stand-alone demo backend showed a permanent green "Connected" because
/// its `view()` cannot fail — the pill was reporting the absence of a failure path, not the
/// presence of a host. `Local` is a distinct state, and no sequence of events can turn it into
/// a claim that a host is connected.
#[test]
fn the_demo_backend_never_claims_a_host_is_connected() {
    let mut s = LinkStatus::local();
    assert_eq!(s.state(), LinkState::Local);

    // Nothing that happens to a real link can move it.
    s.observe_failure("socket closed");
    assert_eq!(
        s.state(),
        LinkState::Local,
        "a demo backend has no socket to lose"
    );
    s.observe_success();
    assert_eq!(
        s.state(),
        LinkState::Local,
        "the demo backend must never report itself connected to a host"
    );
    s.observe_manual_retry();
    assert_eq!(s.state(), LinkState::Local);
    assert_ne!(s.state(), LinkState::Connected);
    assert_eq!(s.state().tag(), "local");
}

/// **Fabrication 1.** "Reconnecting…" was shown while nothing retried. The label and the
/// existence of a pending attempt must be the same fact, so `Reconnecting` and a scheduled
/// backoff have to agree in *both* directions — that pairing is the whole guard.
#[test]
fn reconnecting_is_claimed_only_while_an_attempt_is_actually_pending() {
    let mut s = LinkStatus::connected();
    assert_eq!(s.next_backoff(), None, "a live link schedules nothing");

    s.observe_failure("connection reset");
    assert_eq!(s.state(), LinkState::Reconnecting);
    assert!(
        s.next_backoff().is_some(),
        "claiming 'Reconnecting' obliges an attempt to actually be scheduled"
    );

    // Exhaust the breaker.
    for _ in 1..MAX_RECONNECT_ATTEMPTS {
        s.observe_failure("connection reset");
    }
    assert_eq!(s.state(), LinkState::Disconnected);
    assert_eq!(
        s.next_backoff(),
        None,
        "once it has given up, nothing is pending"
    );

    // The invariant, stated over every state: the label and the pending attempt never disagree.
    for state in LinkState::ALL {
        let probe = status_in(state);
        assert_eq!(
            probe.state() == LinkState::Reconnecting,
            probe.next_backoff().is_some(),
            "'{}' must claim to be reconnecting exactly when an attempt is scheduled",
            state.tag()
        );
    }
}

/// Build a status genuinely in `state` by driving the real transitions — never by poking fields,
/// so these probes exercise the same paths production does.
fn status_in(state: LinkState) -> LinkStatus {
    match state {
        LinkState::Local => LinkStatus::local(),
        LinkState::Connected => LinkStatus::connected(),
        LinkState::Reconnecting => {
            let mut s = LinkStatus::connected();
            s.observe_failure("dropped");
            s
        }
        LinkState::Disconnected => {
            let mut s = LinkStatus::connected();
            for _ in 0..MAX_RECONNECT_ATTEMPTS {
                s.observe_failure("dropped");
            }
            s
        }
    }
}

/// Retrying cannot go on forever: an unbounded loop lets the console show "Reconnecting…"
/// indefinitely, which is the original lie in slow motion. It must give up and say so.
#[test]
fn automatic_retries_are_bounded_and_end_in_an_honest_disconnected() {
    let mut s = LinkStatus::connected();
    for attempt in 1..=MAX_RECONNECT_ATTEMPTS {
        s.observe_failure("host went away");
        assert_eq!(s.attempts(), attempt);
    }
    assert_eq!(s.state(), LinkState::Disconnected);

    // Further failures must not reopen the loop or overflow the schedule.
    for _ in 0..50 {
        s.observe_failure("host went away");
        assert_eq!(s.state(), LinkState::Disconnected);
        assert_eq!(s.next_backoff(), None);
    }
}

#[test]
fn the_operator_can_restart_a_link_that_gave_up() {
    let mut s = status_in(LinkState::Disconnected);
    s.observe_manual_retry();
    assert_eq!(s.state(), LinkState::Reconnecting);
    assert_eq!(s.attempts(), 0);
    assert!(
        s.next_backoff().is_some(),
        "a manual retry must actually schedule an attempt"
    );
}

/// Stale-reply invalidation, the part mobile already had and the desktop console did not. While
/// the link was down the host stayed authoritative, so an intent formed against the old world
/// must be recognisable as stale after a reconnect.
#[test]
fn a_reconnect_advances_the_epoch_so_pre_drop_replies_are_stale() {
    let mut s = LinkStatus::connected();
    let before = s.epoch();
    assert!(!s.is_stale(before), "a current reply is not stale");

    s.observe_failure("dropped");
    s.observe_success();

    assert!(s.epoch() > before, "a reconnect must advance the epoch");
    assert!(
        s.is_stale(before),
        "a reply formed against the pre-drop world must be recognisable as stale"
    );
    assert!(!s.is_stale(s.epoch()));
}

/// A steady link must not churn the epoch — otherwise every in-flight request would look stale
/// and the console would discard perfectly good replies.
#[test]
fn a_link_that_never_dropped_keeps_its_epoch() {
    let mut s = LinkStatus::connected();
    let epoch = s.epoch();
    for _ in 0..10 {
        s.observe_success();
    }
    assert_eq!(
        s.epoch(),
        epoch,
        "success on a live link is not a reconnect"
    );
}

#[test]
fn a_recovered_link_stops_showing_the_reason_it_was_down() {
    let mut s = LinkStatus::connected();
    s.observe_failure("certificate pin mismatch");
    assert_eq!(s.last_error(), Some("certificate pin mismatch"));

    s.observe_success();
    assert_eq!(
        s.last_error(),
        None,
        "a live link must not still display the failure it recovered from"
    );
    assert_eq!(s.attempts(), 0);
}

/// Bounded memory. Exactly one error is retained and it is length-capped: a transport error can
/// be arbitrarily long, and repeated failures must not grow anything. Asserts the retained
/// **entity**, not a proxy.
#[test]
fn the_retained_error_is_capped_and_never_accumulates() {
    let huge = "x".repeat(10_000);
    let mut s = LinkStatus::connected();
    s.observe_failure(&huge);
    let stored = s.last_error().unwrap();
    assert!(
        stored.len() <= MAX_ERROR_LEN,
        "retained error must be capped, got {} bytes",
        stored.len()
    );

    // Each failure REPLACES the previous one — nothing is appended.
    for i in 0..500 {
        s.observe_failure(&format!("failure {i}"));
        assert!(s.last_error().unwrap().len() <= MAX_ERROR_LEN);
    }
    assert_eq!(
        s.last_error(),
        Some("failure 499"),
        "only the most recent failure is kept; a history here would be an unbounded queue"
    );

    // Positive control: a short error is retained verbatim, so the cap above is not just
    // proving that the mechanism stores nothing at all.
    let mut t = LinkStatus::connected();
    t.observe_failure("short");
    assert_eq!(t.last_error(), Some("short"));
}

/// Error text is exactly where non-ASCII arrives — a hostname, an OS message in the user's
/// locale. Truncating mid-character would panic *while reporting a failure*, taking out the
/// reporting path along with the thing it reports.
///
/// The first version of this test was vacuous: it used a 2-byte character against a 200-byte
/// cap, so the cut always landed on a boundary and a naive `&s[..max]` passed it. Character
/// width alone cannot be trusted to misalign, and neither can any single width once the cap
/// changes — so this sweeps widths AND leading offsets, and **asserts that some case really did
/// put the cap mid-character** before believing anything the run proves.
#[test]
fn capping_a_multibyte_error_never_splits_a_character() {
    let mut exercised_mid_character = false;

    for prefix_len in 0..4 {
        for ch in ['\u{e9}', '\u{2603}', '\u{1f600}'] {
            // 2, 3 and 4 bytes.
            let input = format!("{}{}", "a".repeat(prefix_len), ch.to_string().repeat(500));
            if !input.is_char_boundary(MAX_ERROR_LEN) {
                exercised_mid_character = true;
            }

            let mut s = LinkStatus::connected();
            s.observe_failure(&input); // a naive byte slice panics here
            let stored = s.last_error().unwrap();

            assert!(stored.len() <= MAX_ERROR_LEN, "cap must hold for {ch:?}");
            assert!(
                input.starts_with(stored),
                "the retained text must be a genuine prefix of the error, not mangled"
            );
        }
    }

    assert!(
        exercised_mid_character,
        "no case put the cap mid-character, so this test proves nothing about char-boundary \
         handling — widen the sweep or the cap has become aligned to every width tried"
    );
}

#[test]
fn every_state_has_its_own_stable_tag() {
    let tags: Vec<&str> = LinkState::ALL.iter().map(|s| s.tag()).collect();
    let mut unique = tags.clone();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(unique.len(), tags.len(), "tags must be distinct: {tags:?}");
    assert_eq!(tags, ["local", "connected", "reconnecting", "disconnected"]);
}
