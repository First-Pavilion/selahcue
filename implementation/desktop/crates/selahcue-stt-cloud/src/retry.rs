//! Reconnection policy: bounded, backed off, and it **gives up**.
//!
//! Pure — no clock, no sleeping — so the whole policy is decided and tested without waiting
//! for real time to pass. The transport asks it what to do; it never reads a clock itself.
//!
//! The property that matters is the one it is easy to omit: a reconnect loop that retries
//! forever is not resilience. Mid-sermon it produces a console stuck on "reconnecting…" for
//! an hour with no operator action ever prompted, while the real message — a revoked key, an
//! unplugged router — never surfaces. So the policy is finite, its give-up point is
//! observable ([`RetryPolicy::backoff_for_attempt`] returning `None`), and the total time
//! before giving up is a bounded number this module can state
//! ([`RetryPolicy::total_backoff`]).

use std::time::Duration;

/// How many reconnection attempts before giving up.
pub const MAX_RECONNECT_ATTEMPTS: u32 = 5;

/// The wait before the first reconnection attempt.
pub const INITIAL_BACKOFF_MS: u64 = 500;

/// The ceiling on a single wait. Backoff doubles up to here and then stays flat — an
/// unbounded doubling reaches waits longer than the service it is trying to transcribe.
pub const MAX_BACKOFF_MS: u64 = 8_000;

const _: () = assert!(
    MAX_RECONNECT_ATTEMPTS > 0,
    "zero attempts would mean a single dropped packet ends cloud transcription for the service"
);

const _: () = assert!(
    MAX_RECONNECT_ATTEMPTS < 32,
    "the backoff doubles per attempt; beyond 32 attempts the shift would overflow before the \
     ceiling clamped it"
);

const _: () = assert!(
    MAX_BACKOFF_MS > INITIAL_BACKOFF_MS,
    "the ceiling must be above the first wait, or backoff never actually backs off and the \
     'waits grow' test is vacuous"
);

/// Bounded exponential backoff with a hard give-up.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RetryPolicy {
    /// Attempts before giving up.
    pub max_attempts: u32,
    /// The wait before attempt 0.
    pub initial_backoff: Duration,
    /// The ceiling on any single wait.
    pub max_backoff: Duration,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        RetryPolicy {
            max_attempts: MAX_RECONNECT_ATTEMPTS,
            initial_backoff: Duration::from_millis(INITIAL_BACKOFF_MS),
            max_backoff: Duration::from_millis(MAX_BACKOFF_MS),
        }
    }
}

impl RetryPolicy {
    /// How long to wait before `attempt` (zero-based), or `None` to **give up**.
    ///
    /// `None` is the whole point of this type: it is the signal that the session stops
    /// cleanly and hands control back, rather than retrying behind a spinner forever.
    pub fn backoff_for_attempt(&self, attempt: u32) -> Option<Duration> {
        if attempt >= self.max_attempts {
            return None;
        }
        let doubled = self
            .initial_backoff
            .checked_mul(1u32.checked_shl(attempt).unwrap_or(u32::MAX))
            .unwrap_or(self.max_backoff);
        Some(doubled.min(self.max_backoff))
    }

    /// The total time spent waiting if every attempt is used — a finite, stateable number,
    /// which is what "it gives up" means in practice.
    pub fn total_backoff(&self) -> Duration {
        (0..self.max_attempts)
            .filter_map(|a| self.backoff_for_attempt(a))
            .sum()
    }
}

// Tests live in `tests/test_retry.rs` (public-API integration tests).
