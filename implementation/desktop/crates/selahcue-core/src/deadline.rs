//! Pure admitted-deadline policy over an injected wall/monotonic clock. There is no
//! system-clock read here. A retry clones the admission; it cannot reset its budget.
use std::sync::{
    atomic::{AtomicU8, Ordering},
    Arc,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy)]
pub struct ClockReading {
    pub wall: Option<SystemTime>,
    pub monotonic: Instant,
}
pub trait Clock: Send + Sync {
    fn now(&self) -> ClockReading;
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeadlineError {
    Expired,
    Unavailable,
}
#[derive(Clone)]
pub struct AccessDeadline {
    expires_at: SystemTime,
    admitted_at: Instant,
    monotonic_end: Instant,
    clock: Arc<dyn Clock>,
    terminal: Arc<AtomicU8>,
}
impl std::fmt::Debug for AccessDeadline {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AccessDeadline")
            .field("expires_at", &self.expires_at)
            .finish_non_exhaustive()
    }
}
impl AccessDeadline {
    pub fn admit(expires_at: SystemTime, clock: Arc<dyn Clock>) -> Result<Self, DeadlineError> {
        let reading = clock.now();
        let wall = reading
            .wall
            .filter(|w| w.duration_since(UNIX_EPOCH).is_ok())
            .ok_or(DeadlineError::Unavailable)?;
        let remaining = expires_at
            .duration_since(wall)
            .map_err(|_| DeadlineError::Expired)?;
        if remaining.is_zero() {
            return Err(DeadlineError::Expired);
        }
        let monotonic_end = reading
            .monotonic
            .checked_add(remaining)
            .ok_or(DeadlineError::Unavailable)?;
        Ok(Self {
            expires_at,
            admitted_at: reading.monotonic,
            monotonic_end,
            clock,
            terminal: Arc::new(AtomicU8::new(0)),
        })
    }
    pub fn remaining(&self) -> Result<Duration, DeadlineError> {
        match self.terminal.load(Ordering::SeqCst) {
            1 => return Err(DeadlineError::Expired),
            2 => return Err(DeadlineError::Unavailable),
            _ => {}
        }
        let result = self.remaining_sample();
        if let Err(error) = result {
            let code = match error {
                DeadlineError::Expired => 1,
                DeadlineError::Unavailable => 2,
            };
            let _ = self
                .terminal
                .compare_exchange(0, code, Ordering::SeqCst, Ordering::SeqCst);
        }
        match self.terminal.load(Ordering::SeqCst) {
            1 => Err(DeadlineError::Expired),
            2 => Err(DeadlineError::Unavailable),
            _ => result,
        }
    }
    fn remaining_sample(&self) -> Result<Duration, DeadlineError> {
        let reading = self.clock.now();
        let wall = reading
            .wall
            .filter(|w| w.duration_since(UNIX_EPOCH).is_ok())
            .ok_or(DeadlineError::Unavailable)?;
        if reading.monotonic < self.admitted_at {
            return Err(DeadlineError::Unavailable);
        }
        let wall_remaining = self
            .expires_at
            .duration_since(wall)
            .map_err(|_| DeadlineError::Expired)?;
        let mono_remaining = self
            .monotonic_end
            .checked_duration_since(reading.monotonic)
            .ok_or(DeadlineError::Expired)?;
        let remaining = wall_remaining.min(mono_remaining);
        if remaining.is_zero() {
            Err(DeadlineError::Expired)
        } else {
            Ok(remaining)
        }
    }
}
