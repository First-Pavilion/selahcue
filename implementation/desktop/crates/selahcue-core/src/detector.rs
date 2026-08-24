//! Detector liveness — telling "the detector died" apart from "the room is silent".
//!
//! The acceptance bar for the console's health UI is that *a dead scripture detector and a
//! silent room must not render identically*. They did, because nothing reported detector
//! liveness at all: [`TranscriptProvider::label`](crate::transcript::TranscriptProvider::label)
//! (the FR-120 honest-disclosure hook) was unsurfaced, and the operator shell's
//! `is_listening()` had no callers.
//!
//! ## Why the derivation lives here
//!
//! The on-device capture worker lives in the Tauri operator shell, which is **excluded from
//! the workspace** *and* compiled only under its `stt` feature — so CI compile-checks it
//! without that feature and therefore checks this logic not at all. Putting the rule in a
//! place nothing verifies is how a health signal quietly rots into a lie. The rule is
//! therefore pure and lives here, compiled and tested unconditionally; only the worker handle
//! and the phase subscription stay behind the `#[cfg]` in the shell. This mirrors the split
//! `guard.rs` already uses for the crash/disk guards.
//!
//! ## Why `Unsupported` is its own state
//!
//! Not because it reads differently from [`DetectorState::Unavailable`], but because it
//! **affords** differently. `Unavailable` means the detector failed, so retrying is
//! meaningful and a retry control belongs on screen. `Unsupported` means this build has no
//! detector compiled in at all, so retrying is *impossible* — offering a retry there would be
//! a button that cannot work, which is a fresh fabrication of exactly the kind this module
//! exists to remove. The type system enforces the difference: see [`RetryRequest`].
//!
//! It is a build-configuration state, not the product's normal condition — the shipped
//! Windows installer builds `--features stt`, and `make` auto-enables it when cmake is
//! present. It is correct when it happens and should not be designed for prominence.

/// What the on-device detector can currently do.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DetectorState {
    /// No detector is compiled into this build. Retry is impossible, not merely unavailable.
    Unsupported,
    /// A detector exists but no capture worker is running.
    Idle,
    /// A capture worker is running: the microphone is live. Silence now means a silent room,
    /// which is the distinction the acceptance bar is about.
    Listening,
    /// The detector failed. Retrying is meaningful.
    Unavailable,
}

impl DetectorState {
    /// The stable, lowercase tag the operator UI switches on.
    pub fn tag(self) -> &'static str {
        match self {
            DetectorState::Unsupported => "unsupported",
            DetectorState::Idle => "idle",
            DetectorState::Listening => "listening",
            DetectorState::Unavailable => "unavailable",
        }
    }

    /// Every state — for exhaustive matrix tests.
    pub const ALL: [DetectorState; 4] = [
        DetectorState::Unsupported,
        DetectorState::Idle,
        DetectorState::Listening,
        DetectorState::Unavailable,
    ];

    /// Permission to attempt a retry, minted **only** in the state where retrying could
    /// actually change anything.
    ///
    /// This returns a token rather than a `bool` on purpose. A boolean is advice a caller can
    /// ignore; a token that cannot be constructed elsewhere makes the retry path *unreachable*
    /// from a state where it is meaningless, rather than merely disabled there. See
    /// [`RetryRequest`].
    ///
    /// `Idle` deliberately yields nothing: "not started" is served by the existing *start*
    /// control, not by a retry. `Listening` yields nothing because there is nothing to
    /// recover from.
    pub fn retry_request(self) -> Option<RetryRequest> {
        match self {
            DetectorState::Unavailable => Some(RetryRequest(())),
            DetectorState::Unsupported | DetectorState::Idle | DetectorState::Listening => None,
        }
    }
}

/// Proof that a retry is meaningful in the state it was minted from.
///
/// The single unit field is private, so this type cannot be constructed outside this module —
/// a caller cannot fabricate permission to retry. Any code path that performs a retry must
/// take one of these, which is what makes retry *unreachable* rather than disabled when the
/// build has no detector at all.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RetryRequest(());

/// What the shell can observe about the detector, as named fields.
///
/// Named rather than positional because `compiled` and `worker_running` are both booleans and
/// transposing them at a call site would silently invert the verdict — reporting a healthy
/// detector in a build that has none.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DetectorSignals<'a> {
    /// Whether a detector is compiled into this build at all (the `stt` feature).
    pub compiled: bool,
    /// Whether a capture worker is currently running.
    pub worker_running: bool,
    /// The last terminal failure reported by the detector, if one is being held.
    ///
    /// The shell must retain this: the phase channel is fire-and-forget, so a terminal
    /// failure that nothing was listening for is otherwise lost, leaving a dead detector
    /// looking exactly like an idle one.
    pub last_failure: Option<&'a str>,
}

/// Derive the detector's state from what the shell can observe. Pure and total.
///
/// Order matters, and each precedence is a deliberate honesty choice:
///
/// 1. **`compiled` wins over everything.** A build with no detector cannot be listening or
///    failing, whatever stale flags say.
/// 2. **A running worker outranks a retained failure.** A successful restart makes an earlier
///    failure history, and reporting `Unavailable` while the microphone is live would be the
///    original bug inverted — a working detector shown as dead.
/// 3. A retained failure with no worker running is a genuine `Unavailable`.
/// 4. Otherwise the detector simply has not been started.
pub fn detector_state(signals: DetectorSignals<'_>) -> DetectorState {
    if !signals.compiled {
        DetectorState::Unsupported
    } else if signals.worker_running {
        DetectorState::Listening
    } else if signals.last_failure.is_some() {
        DetectorState::Unavailable
    } else {
        DetectorState::Idle
    }
}
