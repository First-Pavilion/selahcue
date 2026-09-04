//! Reconnection policy: it backs off, it is bounded, and it **gives up**.
//!
//! The give-up is the part worth testing hardest. A reconnect loop that retries forever is not
//! resilience — mid-sermon it leaves a console stuck on "reconnecting…" while the real cause
//! never surfaces and no operator action is ever prompted.

#![allow(clippy::unwrap_used)]

use std::time::Duration;

use selahcue_stt_cloud::retry::{INITIAL_BACKOFF_MS, MAX_BACKOFF_MS};
use selahcue_stt_cloud::{RetryPolicy, MAX_RECONNECT_ATTEMPTS};

#[test]
fn the_policy_gives_up_rather_than_retrying_forever() {
    let policy = RetryPolicy::default();

    // The bound was exercised: every attempt inside the budget yields a wait.
    for attempt in 0..policy.max_attempts {
        assert!(
            policy.backoff_for_attempt(attempt).is_some(),
            "attempt {attempt} of {} was refused a wait, so the policy gives up earlier than \
             it claims and the give-up assertion below is not testing the boundary",
            policy.max_attempts
        );
    }

    assert_eq!(
        policy.backoff_for_attempt(policy.max_attempts),
        None,
        "the policy did not give up at its own bound; a dropped connection would retry \
         forever behind a spinner"
    );
    assert_eq!(policy.backoff_for_attempt(u32::MAX), None);
}

#[test]
fn waits_grow_and_then_stop_growing() {
    let policy = RetryPolicy::default();
    let waits: Vec<Duration> = (0..policy.max_attempts)
        .filter_map(|a| policy.backoff_for_attempt(a))
        .collect();

    assert_eq!(waits.len(), MAX_RECONNECT_ATTEMPTS as usize);
    assert_eq!(waits[0], Duration::from_millis(INITIAL_BACKOFF_MS));

    // Exercised before contract: if no wait ever grew, "backoff" would be a constant delay
    // and the ceiling below would be untested.
    assert!(
        waits[1] > waits[0],
        "the second wait is not longer than the first, so this is a fixed delay rather than \
         backoff"
    );

    for pair in waits.windows(2) {
        assert!(
            pair[1] >= pair[0],
            "waits are not monotonic: {:?} then {:?}",
            pair[0],
            pair[1]
        );
    }
    for wait in &waits {
        assert!(
            *wait <= Duration::from_millis(MAX_BACKOFF_MS),
            "a wait of {wait:?} exceeded the {MAX_BACKOFF_MS} ms ceiling; unbounded doubling \
             reaches waits longer than the service being transcribed"
        );
    }
    assert_eq!(
        *waits.last().expect("at least one wait"),
        Duration::from_millis(MAX_BACKOFF_MS),
        "the ceiling is never actually reached within the attempt budget, so the clamp goes \
         untested"
    );
}

#[test]
fn the_total_time_before_giving_up_is_a_finite_stateable_number() {
    // 500 + 1000 + 2000 + 4000 + 8000 ms.
    let policy = RetryPolicy::default();
    assert_eq!(
        policy.total_backoff(),
        Duration::from_millis(15_500),
        "the time before cloud transcription gives up changed; it is a number an operator's \
         expectations are set by"
    );
    assert!(
        policy.total_backoff() < Duration::from_secs(60),
        "a minute of silent reconnection mid-sermon is too long to leave an operator without \
         an actionable message"
    );
}

#[test]
fn a_ceiling_below_the_doubling_clamps_rather_than_overflowing() {
    let policy = RetryPolicy {
        max_attempts: 40,
        initial_backoff: Duration::from_secs(1),
        max_backoff: Duration::from_secs(5),
    };
    // Attempt 39 would be 2^39 seconds if the doubling were unclamped, and the shift itself
    // overflows a u32 well before that.
    assert_eq!(
        policy.backoff_for_attempt(39),
        Some(Duration::from_secs(5)),
        "a large attempt number overflowed or escaped the ceiling"
    );
    assert_eq!(policy.backoff_for_attempt(40), None);
}

#[test]
fn a_zero_attempt_policy_gives_up_immediately() {
    let policy = RetryPolicy {
        max_attempts: 0,
        ..RetryPolicy::default()
    };
    assert_eq!(policy.backoff_for_attempt(0), None);
    assert_eq!(policy.total_backoff(), Duration::ZERO);
}
