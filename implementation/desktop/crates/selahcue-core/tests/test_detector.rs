//! Detector liveness: a dead detector and a silent room must not look the same, and a build
//! that cannot listen must not offer a retry that cannot work.
//!
//! This is an **external** integration test (it links `selahcue_core` as a dependency, exactly
//! as the operator shell does), which is what makes the privacy claim in
//! `test_a_retry_token_cannot_be_forged_from_outside_the_crate` meaningful: if `RetryRequest`
//! were constructible from outside, that test would compile.
//!
//! Every arm here — including `Unsupported` — is compiled and run unconditionally. That arm is
//! precisely the one a `#[cfg(feature = "stt")]`-gated test would never reach, and it is the
//! state CI itself runs in.

#![allow(clippy::unwrap_used)]

use selahcue_core::detector::{detector_state, DetectorSignals, DetectorState};

/// A build with the detector compiled in, nothing running, no failure held.
fn ready() -> DetectorSignals<'static> {
    DetectorSignals {
        compiled: true,
        worker_running: false,
        last_failure: None,
    }
}

/// **The acceptance bar, stated directly.** A detector that has died and a microphone that is
/// live in a quiet room produce the same thing downstream — no transcript — so if the state
/// does not separate them, nothing can. Silence is not evidence either way; only liveness is.
#[test]
fn a_dead_detector_and_a_silent_room_do_not_look_the_same() {
    let silent_room = detector_state(DetectorSignals {
        worker_running: true,
        ..ready()
    });
    let dead_detector = detector_state(DetectorSignals {
        worker_running: false,
        last_failure: Some("audio device disappeared"),
        ..ready()
    });

    assert_eq!(silent_room, DetectorState::Listening);
    assert_eq!(dead_detector, DetectorState::Unavailable);
    assert_ne!(
        silent_room, dead_detector,
        "a live microphone in a quiet room and a detector that has died must be \
         distinguishable — this is the bar the whole programme is measured against"
    );
    assert_ne!(silent_room.tag(), dead_detector.tag());
}

#[test]
fn an_unstarted_detector_is_idle_not_failed() {
    assert_eq!(
        detector_state(ready()),
        DetectorState::Idle,
        "never started is not the same as broken; reporting a fault here would be the \
         'absent telemetry shown as a hard failure' bug in a new place"
    );
}

/// Precedence 1. A build with no detector cannot be listening or failing, whatever other
/// flags claim — so `compiled` must dominate. Asserted against every combination of the
/// other signals so no corner leaks a state this build cannot be in.
#[test]
fn a_build_without_a_detector_is_unsupported_whatever_else_is_claimed() {
    for worker_running in [false, true] {
        for last_failure in [None, Some("stale")] {
            let s = detector_state(DetectorSignals {
                compiled: false,
                worker_running,
                last_failure,
            });
            assert_eq!(
                s,
                DetectorState::Unsupported,
                "compiled:false must dominate (worker_running={worker_running}, \
                 last_failure={last_failure:?})"
            );
        }
    }
}

/// Precedence 2. A successful restart makes an earlier failure history. Reporting
/// `Unavailable` while the microphone is live would be the original defect inverted — a
/// working detector displayed as dead — which is just as much a fabrication.
#[test]
fn a_running_worker_outranks_a_retained_failure() {
    let s = detector_state(DetectorSignals {
        worker_running: true,
        last_failure: Some("previous run failed"),
        ..ready()
    });
    assert_eq!(
        s,
        DetectorState::Listening,
        "a live worker must not be reported dead because of a stale failure"
    );
}

/// Retry is offered **only** where it could change something. `Unsupported` is the case that
/// matters: a build with no detector must not present a control that cannot possibly work.
#[test]
fn a_retry_is_offered_only_where_retrying_could_help() {
    assert!(
        DetectorState::Unavailable.retry_request().is_some(),
        "a failed detector is exactly where retry belongs"
    );
    for state in [
        DetectorState::Unsupported,
        DetectorState::Idle,
        DetectorState::Listening,
    ] {
        assert!(
            state.retry_request().is_none(),
            "{} must not offer a retry: in this state retrying cannot change anything, and \
             a control that cannot work is a fresh fabrication",
            state.tag()
        );
    }
}

/// The point of returning a token rather than a boolean: a caller cannot fabricate permission
/// to retry, so the retry path is *unreachable* from `Unsupported` rather than merely
/// discouraged there.
///
/// The negative half of this is enforced by the compiler, not by an assertion: `RetryRequest`
/// has a private field, so `RetryRequest(())` in this external test crate does not compile.
/// Uncommenting the line below must break the build — that is the guard.
#[test]
fn a_retry_token_cannot_be_forged_from_outside_the_crate() {
    // let forged = selahcue_core::detector::RetryRequest(()); // must not compile
    let honest = DetectorState::Unavailable
        .retry_request()
        .expect("the only way to obtain one");
    assert_eq!(
        Some(honest),
        DetectorState::Unavailable.retry_request(),
        "the token is obtainable only by asking the state that permits it"
    );
}

/// Each state needs its own operator-facing tag, or two conditions that call for different
/// operator responses collapse into one on screen.
#[test]
fn every_state_has_its_own_stable_tag() {
    let tags: Vec<&str> = DetectorState::ALL.iter().map(|s| s.tag()).collect();
    let mut unique = tags.clone();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(unique.len(), tags.len(), "tags must be distinct: {tags:?}");
    // Pinned: the operator UI switches on these exact strings.
    assert_eq!(tags, ["unsupported", "idle", "listening", "unavailable"]);
}

/// The derivation is total: every combination of observable signals yields a state, and only
/// a build with the detector compiled in can ever report `Listening`.
#[test]
fn the_derivation_is_total_and_only_a_real_build_can_listen() {
    for compiled in [false, true] {
        for worker_running in [false, true] {
            for last_failure in [None, Some("boom")] {
                let s = detector_state(DetectorSignals {
                    compiled,
                    worker_running,
                    last_failure,
                });
                assert!(DetectorState::ALL.contains(&s));
                if s == DetectorState::Listening {
                    assert!(
                        compiled && worker_running,
                        "only a compiled-in, running detector may claim to be listening"
                    );
                }
            }
        }
    }
}
