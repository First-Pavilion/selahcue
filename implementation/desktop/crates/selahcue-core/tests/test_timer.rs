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

#[test]
fn with_elapsed_resumes_a_recovered_countdown() {
    // Crash recovery: rebuild a 300s countdown that had 117s on the clock, resume,
    // and the remaining time continues from there.
    let base = Instant::now();
    let mut t = Timer::count_down(Duration::from_secs(300)).with_elapsed(Duration::from_secs(117));
    assert!(!t.is_running());
    assert_eq!(t.elapsed(base), Duration::from_secs(117));
    assert_eq!(t.remaining(base), Some(Duration::from_secs(183)));
    t.start(base);
    let later = base + Duration::from_secs(10);
    assert_eq!(t.remaining(later), Some(Duration::from_secs(173)));
    // Recovery past the target lands in TIME UP, never a rewind.
    let up = Timer::count_down(Duration::from_secs(60)).with_elapsed(Duration::from_secs(90));
    assert!(up.is_time_up(base));
    assert_eq!(up.overrun(base), Duration::from_secs(30));
}

#[test]
fn adjust_extends_reduces_and_clamps_a_countdown() {
    use std::time::{Duration, Instant};
    let t0 = Instant::now();
    let mut timer = Timer::count_down(Duration::from_secs(300));
    timer.start(t0);

    // +60 extends the target; elapsed is untouched (monotonic accuracy holds).
    assert_eq!(timer.adjust(60), Some(Duration::from_secs(360)));
    let at = t0 + Duration::from_secs(100);
    assert_eq!(timer.elapsed(at), Duration::from_secs(100));
    assert_eq!(timer.remaining(at), Some(Duration::from_secs(260)));

    // -200 below the elapsed lands in TIME UP on the next read.
    assert_eq!(timer.adjust(-300), Some(Duration::from_secs(60)));
    assert!(timer.is_time_up(at), "target 60 < elapsed 100");

    // The target clamps at zero, never underflows.
    assert_eq!(timer.adjust(-9_999), Some(Duration::ZERO));

    // ...and at u32::MAX seconds — the persisted-snapshot domain — so a
    // wire-legal absurd delta can never diverge from what recovery restores.
    assert_eq!(
        timer.adjust(i64::MAX),
        Some(Duration::from_secs(u64::from(u32::MAX)))
    );

    // A count-up timer has no target to adjust.
    let mut up = Timer::count_up();
    assert_eq!(up.adjust(60), None);
}
