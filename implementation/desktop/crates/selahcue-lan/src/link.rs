//! Control-link state — what the operator console's connection pill is actually allowed to say.
//!
//! The console used to claim three things that were not true: a **"Reconnecting…"** label when
//! nothing retried (`build_backend()` runs exactly once, at Tauri setup — there was no loop, no
//! backoff, no re-dial), a permanent green **"Connected"** in the stand-alone demo backend where
//! the call that would prove it can never fail, and a hard **"NO SIGNAL"** for telemetry that was
//! merely absent. This module is the state those labels must be read from.
//!
//! ## Not the same thing as output-window retry
//!
//! `selahcue-desktop`'s screen-window logic deliberately does **not** loop: a failed window open
//! costs one attempt and is retried only when the operator switches that screen off and on again —
//! *"the operator's gesture, never a loop"*. That decision stands and is untouched here. It is
//! about creating an OS window for an audience screen. This is the operator↔host **control link**,
//! a socket that can drop for ordinary network reasons and that the operator is not watching. The
//! two are different problems with different right answers; do not unify them.
//!
//! ## Why this is pure, and here
//!
//! The dialling itself belongs to the Tauri shell, which is excluded from the workspace and
//! compile-checked only. A reconnect rule living there would be verified by nothing, so the rule
//! is here — transport-free, in the default build, exhaustively testable — and the shell keeps
//! only the socket. This mirrors the pure/IO split `guard.rs` already uses.

use std::time::Duration;

/// How many automatic attempts are made before the link gives up and asks the operator.
///
/// Bounded on purpose: an unbounded retry loop against a host that is genuinely gone burns
/// battery and file descriptors forever, and — worse for this programme — lets the console show
/// "Reconnecting…" indefinitely, which is the very lie being removed. After this many failures
/// the state becomes an honest [`LinkState::Disconnected`] with a manual retry.
pub const MAX_RECONNECT_ATTEMPTS: u32 = 5;

/// Backoff before each automatic attempt, indexed by attempts already made.
///
/// A fixed array rather than a computed exponential: the schedule is bounded by construction,
/// has no overflow case, and is readable in one glance. Its length must cover every attempt the
/// breaker allows, which is pinned below.
const BACKOFF_MS: [u64; MAX_RECONNECT_ATTEMPTS as usize] = [250, 500, 1_000, 2_000, 4_000];

/// The schedule must have an entry for every attempt the breaker permits. If someone raises
/// [`MAX_RECONNECT_ATTEMPTS`] without extending the table this fails to compile, rather than
/// panicking on an out-of-range index at the worst possible moment — mid-service, mid-outage.
const _: () = assert!(BACKOFF_MS.len() == MAX_RECONNECT_ATTEMPTS as usize);

/// Longest error text retained for display.
///
/// A transport error can be arbitrarily long (a certificate chain, a nested cause). Exactly one
/// is held at a time and each replaces the last, but an uncapped single string is still unbounded
/// growth, so it is truncated on a char boundary.
pub const MAX_ERROR_LEN: usize = crate::protocol::MAX_ERROR_TEXT_LEN;

/// What the control link is doing, as the console is permitted to describe it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinkState {
    /// No control link exists because none is wanted: the stand-alone demo backend drives an
    /// in-process controller.
    ///
    /// A distinct state, **not** `Connected`. The demo's `view()` cannot fail, so treating it as
    /// connected produced a green pill that was green for the wrong reason — it reported the
    /// absence of a failure path, not the presence of a host.
    Local,
    /// A live link to the host.
    Connected,
    /// The link dropped and automatic attempts are still in progress. Only ever true while
    /// something really is retrying.
    Reconnecting,
    /// The link is down and automatic attempts are exhausted. Honest terminal state: the console
    /// offers the operator a retry rather than implying one is already happening.
    Disconnected,
}

impl LinkState {
    /// The stable, lowercase tag the console switches on.
    pub fn tag(self) -> &'static str {
        match self {
            LinkState::Local => "local",
            LinkState::Connected => "connected",
            LinkState::Reconnecting => "reconnecting",
            LinkState::Disconnected => "disconnected",
        }
    }

    /// Every state — for exhaustive matrix tests.
    pub const ALL: [LinkState; 4] = [
        LinkState::Local,
        LinkState::Connected,
        LinkState::Reconnecting,
        LinkState::Disconnected,
    ];
}

/// The control link's observable status: state, connection epoch, attempts made, last error.
///
/// Bounded by construction — three integers, an enum and at most one capped `String`. There is
/// deliberately no attempt log or error history: that would be an unbounded queue, and a
/// reconnect loop is exactly the workload that would fill one.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinkStatus {
    state: LinkState,
    epoch: u64,
    attempts: u32,
    last_error: Option<String>,
}

impl LinkStatus {
    /// A stand-alone (demo) backend. Permanently [`LinkState::Local`].
    pub fn local() -> Self {
        LinkStatus {
            state: LinkState::Local,
            epoch: 0,
            attempts: 0,
            last_error: None,
        }
    }

    /// A freshly established link to a real host.
    pub fn connected() -> Self {
        LinkStatus {
            state: LinkState::Connected,
            epoch: 1,
            attempts: 0,
            last_error: None,
        }
    }

    pub fn state(&self) -> LinkState {
        self.state
    }

    /// Monotonic connection epoch, bumped every time a link is (re)established.
    ///
    /// The spine of stale-reply invalidation: while the link was down the host stayed
    /// authoritative and may have staged something else entirely, so an intent formed against
    /// the pre-drop world must not be applied afterwards. Comparing the epoch a request was sent
    /// under against the current one makes that a cheap local check needing no host cooperation.
    /// The mobile controller already does this; the desktop console did not.
    pub fn epoch(&self) -> u64 {
        self.epoch
    }

    /// Automatic attempts made since the link dropped.
    pub fn attempts(&self) -> u32 {
        self.attempts
    }

    /// The most recent failure, truncated for display. Exactly one is retained.
    pub fn last_error(&self) -> Option<&str> {
        self.last_error.as_deref()
    }

    /// Whether a reply minted under `epoch` describes a world that has since been replaced.
    pub fn is_stale(&self, epoch: u64) -> bool {
        epoch != self.epoch
    }

    /// Record a failed request or a dropped link.
    ///
    /// A [`LinkState::Local`] status is untouched: the demo backend has no socket to lose, so a
    /// failure there is not a link failure and must never be shown as one.
    pub fn observe_failure(&mut self, error: &str) {
        if self.state == LinkState::Local {
            return;
        }
        self.attempts = self.attempts.saturating_add(1);
        self.last_error = Some(crate::protocol::truncate_for_wire(error, MAX_ERROR_LEN));
        self.state = if self.attempts >= MAX_RECONNECT_ATTEMPTS {
            LinkState::Disconnected
        } else {
            LinkState::Reconnecting
        };
    }

    /// Record a successful (re)connect: the epoch advances so replies from the previous
    /// connection are recognisably stale, and the failure record is cleared so a recovered link
    /// never displays the reason it used to be down.
    ///
    /// A [`LinkState::Local`] status is untouched — the demo backend never becomes connected.
    pub fn observe_success(&mut self) {
        if self.state == LinkState::Local {
            return;
        }
        if self.state != LinkState::Connected {
            self.epoch = self.epoch.saturating_add(1);
        }
        self.state = LinkState::Connected;
        self.attempts = 0;
        self.last_error = None;
    }

    /// The operator asked to try again after the link gave up. Restarts the automatic sequence;
    /// the retained error stays until something actually succeeds.
    pub fn observe_manual_retry(&mut self) {
        if self.state == LinkState::Local {
            return;
        }
        self.attempts = 0;
        self.state = LinkState::Reconnecting;
    }

    /// How long to wait before the next automatic attempt.
    ///
    /// `None` means **no automatic attempt is coming** — either there is nothing to reconnect
    /// (`Local`, `Connected`) or the breaker has given up (`Disconnected`). A caller must not
    /// display "Reconnecting…" when this is `None`; that pairing is what made the old label
    /// untrue.
    pub fn next_backoff(&self) -> Option<Duration> {
        if self.state != LinkState::Reconnecting {
            return None;
        }
        BACKOFF_MS
            .get(self.attempts as usize)
            .map(|ms| Duration::from_millis(*ms))
    }
}
