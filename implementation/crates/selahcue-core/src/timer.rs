//! Monotonic-clock timers with a TIME UP state (FR-054, FR-055, FR-059, FR-060,
//! FR-065, NFR-022).
//!
//! Elapsed time is derived from an **injected [`Instant`]** rather than a render
//! tick, so the timer is accurate regardless of frame rate (NFR-022) and is
//! fully deterministic to test (the caller supplies `now`, mirroring the
//! ADR-0015 injected-clock approach). The wall clock never drives it.

use std::time::{Duration, Instant};

/// Whether the timer counts up from zero or down from a set duration.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TimerMode {
    CountUp,
    /// Count down from `duration` toward zero, then into overrun.
    CountDown { duration: Duration },
}

/// A pausable monotonic timer.
///
/// The timer accumulates running time across pause/resume cycles. All time
/// queries take the current [`Instant`]; the timer performs no I/O and reads no
/// global clock itself.
#[derive(Debug, Clone)]
pub struct Timer {
    mode: TimerMode,
    /// Running time accumulated during previous (now-ended) run segments.
    accumulated: Duration,
    /// If running, the instant the current segment started.
    running_since: Option<Instant>,
}

impl Timer {
    /// A stopped count-up timer at zero.
    pub fn count_up() -> Self {
        Timer {
            mode: TimerMode::CountUp,
            accumulated: Duration::ZERO,
            running_since: None,
        }
    }

    /// A stopped count-down timer of `duration`.
    pub fn count_down(duration: Duration) -> Self {
        Timer {
            mode: TimerMode::CountDown { duration },
            accumulated: Duration::ZERO,
            running_since: None,
        }
    }

    pub fn mode(&self) -> TimerMode {
        self.mode
    }

    pub fn is_running(&self) -> bool {
        self.running_since.is_some()
    }

    /// Start (or resume) the timer as of `now`. No-op if already running.
    pub fn start(&mut self, now: Instant) {
        if self.running_since.is_none() {
            self.running_since = Some(now);
        }
    }

    /// Pause the timer as of `now`, banking the current segment. No-op if paused.
    pub fn pause(&mut self, now: Instant) {
        if let Some(since) = self.running_since.take() {
            self.accumulated = self
                .accumulated
                .saturating_add(now.saturating_duration_since(since));
        }
    }

    /// Reset elapsed time to zero and stop. The mode (and count-down duration)
    /// is preserved.
    pub fn reset(&mut self) {
        self.accumulated = Duration::ZERO;
        self.running_since = None;
    }

    /// Total elapsed running time as of `now`.
    pub fn elapsed(&self, now: Instant) -> Duration {
        match self.running_since {
            Some(since) => self
                .accumulated
                .saturating_add(now.saturating_duration_since(since)),
            None => self.accumulated,
        }
    }

    /// Remaining time for a count-down timer (`Duration::ZERO` once expired);
    /// `None` for a count-up timer.
    pub fn remaining(&self, now: Instant) -> Option<Duration> {
        match self.mode {
            TimerMode::CountDown { duration } => Some(duration.saturating_sub(self.elapsed(now))),
            TimerMode::CountUp => None,
        }
    }

    /// Whether a count-down timer has reached or passed zero (the TIME UP state).
    /// Always `false` for count-up.
    pub fn is_time_up(&self, now: Instant) -> bool {
        match self.mode {
            TimerMode::CountDown { duration } => self.elapsed(now) >= duration,
            TimerMode::CountUp => false,
        }
    }

    /// How far a count-down timer has run past zero (`Duration::ZERO` before
    /// expiry, or for count-up) — the overrun shown on the TIME UP display
    /// (FR-060).
    pub fn overrun(&self, now: Instant) -> Duration {
        match self.mode {
            TimerMode::CountDown { duration } => self.elapsed(now).saturating_sub(duration),
            TimerMode::CountUp => Duration::ZERO,
        }
    }

    /// Add time to a count-down timer (the "+1:00" control, FR-055). No-op for
    /// count-up.
    pub fn add_time(&mut self, extra: Duration) {
        if let TimerMode::CountDown { duration } = &mut self.mode {
            *duration = duration.saturating_add(extra);
        }
    }

    /// Subtract time from a count-down timer (saturating at zero). No-op for
    /// count-up.
    pub fn subtract_time(&mut self, less: Duration) {
        if let TimerMode::CountDown { duration } = &mut self.mode {
            *duration = duration.saturating_sub(less);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
