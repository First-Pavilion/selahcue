//! Integration tests for the monotonic `Timer` (FR-054/065, NFR-022). Driven by
//! injected `Instant`s so they are deterministic and never sleep. Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_core::timer::{Timer, TimerMode};
use std::time::{Duration, Instant};

/// A fixed base instant; offsets are added deterministically (no sleeping).
fn base() -> Instant {
    Instant::now()
}
fn at(base: Instant, secs: u64) -> Instant {
    base + Duration::from_secs(secs)
}

#[test]
fn count_down_elapsed_and_remaining() {
    let b = base();
    let mut t = Timer::count_down(Duration::from_secs(300)); // 5:00
    t.start(b);
    assert_eq!(t.elapsed(at(b, 60)), Duration::from_secs(60));
    assert_eq!(t.remaining(at(b, 60)), Some(Duration::from_secs(240)));
    assert!(!t.is_time_up(at(b, 60)));
}

#[test]
fn pause_resume_banks_time() {
    let b = base();
    let mut t = Timer::count_up();
    t.start(b);
    t.pause(at(b, 60)); // banked 60s
    assert!(!t.is_running());
    // Time passing while paused does not accrue.
    assert_eq!(t.elapsed(at(b, 100)), Duration::from_secs(60));
    t.start(at(b, 100)); // resume
    assert_eq!(t.elapsed(at(b, 130)), Duration::from_secs(90)); // 60 + 30
}

#[test]
fn reset_zeros_and_stops() {
    let b = base();
    let mut t = Timer::count_up();
    t.start(b);
    assert_eq!(t.elapsed(at(b, 50)), Duration::from_secs(50));
    t.reset();
    assert!(!t.is_running());
    assert_eq!(t.elapsed(at(b, 200)), Duration::ZERO);
}

#[test]
fn time_up_and_overrun() {
    let b = base();
    let mut t = Timer::count_down(Duration::from_secs(60));
    t.start(b);
    assert!(!t.is_time_up(at(b, 59)));
    assert!(t.is_time_up(at(b, 60)));
    assert_eq!(t.remaining(at(b, 60)), Some(Duration::ZERO));
    assert_eq!(t.overrun(at(b, 75)), Duration::from_secs(15)); // FR-060 overrun
}

#[test]
fn add_and_subtract_time() {
    let b = base();
    let mut t = Timer::count_down(Duration::from_secs(60));
    t.start(b);
    t.add_time(Duration::from_secs(60)); // +1:00
    assert_eq!(t.remaining(at(b, 30)), Some(Duration::from_secs(90)));
    t.subtract_time(Duration::from_secs(120)); // saturates at 0 duration
    assert_eq!(t.remaining(at(b, 0)), Some(Duration::ZERO));
}

#[test]
fn count_up_has_no_remaining_or_time_up() {
    let b = base();
    let mut t = Timer::count_up();
    t.start(b);
    assert_eq!(t.remaining(at(b, 999)), None);
    assert!(!t.is_time_up(at(b, 999)));
    assert_eq!(t.overrun(at(b, 999)), Duration::ZERO);
}

#[test]
fn pause_is_idempotent_while_paused() {
    let b = base();
    let mut t = Timer::count_up();
    t.start(b);
    t.pause(at(b, 40));
    t.pause(at(b, 80)); // already paused — must not double-bank
    assert_eq!(t.elapsed(at(b, 200)), Duration::from_secs(40));
}

#[test]
fn add_subtract_are_noops_on_count_up() {
    let b = base();
    let mut t = Timer::count_up();
    t.add_time(Duration::from_secs(60));
    t.subtract_time(Duration::from_secs(60));
    assert_eq!(t.mode(), TimerMode::CountUp);
    assert_eq!(t.remaining(at(b, 0)), None);
}

#[test]
fn start_is_idempotent_while_running() {
    let b = base();
    let mut t = Timer::count_up();
    t.start(b);
    t.start(at(b, 30)); // ignored — must not reset the origin
    assert_eq!(t.elapsed(at(b, 60)), Duration::from_secs(60));
}

#[test]
fn elapsed_independent_of_query_frequency() {
    // Querying many times must not change accrual (drift-independence, NFR-022).
    let b = base();
    let mut t = Timer::count_down(Duration::from_secs(100));
    t.start(b);
    for s in 0..100 {
        let _ = t.elapsed(at(b, s));
    }
    assert_eq!(t.elapsed(at(b, 100)), Duration::from_secs(100));
    assert!(t.is_time_up(at(b, 100)));
}
