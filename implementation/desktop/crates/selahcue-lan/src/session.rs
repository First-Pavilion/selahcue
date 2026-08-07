//! Device pairing and session management (FR-120; ADR-0009).
//!
//! A controller becomes trusted through an explicit, operator-initiated pairing:
//! the operator offers a short, single-use, time-limited code for a chosen
//! [`Role`]; the controller redeems it and receives an opaque bearer
//! [`SessionToken`]. Every later request is authenticated by matching that token
//! in **constant time**.
//!
//! Token and pairing-code *generation* (randomness) is injected by the caller —
//! and the clock is injected too — so this layer is pure and exhaustively testable,
//! the same discipline as [`selahcue_core::timer`].

use crate::rbac::Role;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use subtle::ConstantTimeEq;

/// A stable per-device identifier (client-generated, opaque to the server).
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DeviceId(pub String);

/// An opaque bearer token issued to a device at pairing time.
///
/// Compared in constant time (see [`SessionRegistry::authenticate`]) so a match
/// cannot be recovered byte-by-byte through timing. Never printed: its `Debug` is
/// redacted.
#[derive(Clone)]
pub struct SessionToken(String);

impl SessionToken {
    /// Wrap already-generated token material (e.g. a 256-bit random, hex/base64).
    pub fn new(token: impl Into<String>) -> Self {
        Self(token.into())
    }

    /// The token as a string (for transmission to the paired device only).
    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// Constant-time equality against a presented token.
    fn matches(&self, presented: &str) -> bool {
        bool::from(self.0.as_bytes().ct_eq(presented.as_bytes()))
    }
}

impl std::fmt::Debug for SessionToken {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("SessionToken(<redacted>)")
    }
}

/// An authenticated device session.
#[derive(Debug, Clone)]
pub struct Session {
    pub device_id: DeviceId,
    pub role: Role,
    token: SessionToken,
    /// When this session was last (re)authenticated. Set at pairing and refreshed on every
    /// handshake (`touch`); a session idle past [`SESSION_IDLE_TTL`] is reclaimed by
    /// [`prune_idle`](SessionRegistry::prune_idle) so the active-session cap (audit M3) bounds
    /// *recently-active* devices, not lifetime pairings (audit #8).
    last_seen: Instant,
    /// A PINNED session is exempt from idle reclamation — the trusted host-local operator
    /// session (pre-seeded once at startup with a fixed endpoint token, held over a single
    /// long-lived loopback connection so `touch` never refreshes it, and with no re-pair path)
    /// must never be idled out from under the host (audit #8). Remote pairings are never pinned.
    pinned: bool,
    /// Device-supplied display name + platform, captured when the pairing request was submitted
    /// and carried through approval so the operator's device list can show "Booth iPad · iPadOS"
    /// (Remote Control design). Empty for sessions created by the legacy `redeem` code-flow.
    name: String,
    platform: String,
}

/// A read-only, token-free summary of one active session — what the operator's device
/// manager (Remote Control surface, ClickUp 86ajxer8n) needs to list a paired controller
/// without ever exposing its bearer [`SessionToken`]. `idle_for` is `now - last_seen`; the
/// caller derives an Online/Idle/Offline status from it (the thresholds are a UI/host policy,
/// not this pure layer's concern).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionSummary {
    pub device_id: DeviceId,
    pub role: Role,
    /// Device-supplied display name / platform (empty for legacy `redeem`-created sessions).
    pub name: String,
    pub platform: String,
    pub idle_for: Duration,
    pub pinned: bool,
}

/// A device-initiated pairing request awaiting operator approval — the "PENDING REQUEST" of the
/// Remote Control design. A device that scanned the pairing QR (host-authenticated by the pinned
/// fingerprint at the transport layer) submits one with its name/platform + the pairing
/// fingerprint the operator verifies against the phone; the operator then **approves it with a
/// [`Role`]** (RBAC assigned at approval — not baked into a code) or denies it.
#[derive(Debug, Clone)]
struct PendingRequest {
    name: String,
    platform: String,
    fingerprint: String,
    requested_at: Instant,
}

/// A read-only summary of one pending pairing request (for the operator's "PENDING REQUEST" list).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PendingRequestSummary {
    pub device_id: DeviceId,
    pub name: String,
    pub platform: String,
    pub fingerprint: String,
    /// How long the request has been waiting (`now - requested_at`).
    pub waiting_for: Duration,
}

/// Why submitting a pairing request failed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RequestError {
    /// The pending-request buffer is at [`MAX_PENDING_REQUESTS`] and this is a NEW device — the
    /// operator must clear (approve/deny) a request before another new device can queue. Bounds
    /// the buffer so a flood of pair attempts cannot grow it without limit (no-leak).
    TooManyRequests,
}

/// Why approving a pairing request failed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApproveError {
    /// No pending request for that device (never submitted, already approved, denied, or pruned).
    NoSuchRequest,
    /// The active-session registry is at [`MAX_ACTIVE_SESSIONS`] and this is a NEW device. The
    /// request is left intact so the operator can retry after freeing a slot (revoking a stale
    /// session), matching `redeem`'s fail-closed behaviour.
    TooManySessions,
}

/// Hard cap on concurrent active (paired) sessions (audit M3 no-leak rule). Far above any
/// realistic setup (a handful of volunteer devices + the loopback operator shell), so it
/// never fires in legitimate use — it only stops the `active` map from accumulating one
/// permanent entry per distinct device without bound when stale sessions are never revoked.
pub const MAX_ACTIVE_SESSIONS: usize = 256;

/// Hard cap on outstanding device-initiated pairing requests (no-leak): bounds the pending-request
/// buffer so a burst of pair attempts cannot grow it without limit. Generous vs. any real setup
/// (a few volunteers pairing at once); stale requests also self-reclaim via
/// [`prune_stale_requests`](SessionRegistry::prune_stale_requests).
pub const MAX_PENDING_REQUESTS: usize = 64;

/// How long an active session may sit idle (no re-authentication) before
/// [`prune_idle`](SessionRegistry::prune_idle) reclaims it (audit #8). Generous — far
/// longer than a service — so an active device is never pruned mid-use, while a dead session
/// (a device that paired once and never reconnected, e.g. after a reinstall that mints a fresh
/// `device_id`) self-reclaims within the window rather than permanently consuming a slot.
pub const SESSION_IDLE_TTL: Duration = Duration::from_secs(6 * 3600);

/// Why redeeming a pairing code failed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PairingError {
    /// No such pairing code is outstanding (never offered, or already redeemed).
    UnknownCode,
    /// The code existed but its time window has passed.
    ExpiredCode,
    /// The active-session registry is at `MAX_ACTIVE_SESSIONS` and this is a NEW device.
    /// The single-use code is still consumed; the operator frees a slot (revokes a stale
    /// session) and offers a fresh code. (Re-pairing an already-active device is always
    /// allowed — it replaces, no growth.)
    TooManySessions,
}

struct PendingPairing {
    role: Role,
    expires_at: Instant,
}

/// The operator's registry of outstanding pairing offers and active sessions.
#[derive(Default)]
pub struct SessionRegistry {
    pending: HashMap<String, PendingPairing>,
    /// Device-initiated pairing requests awaiting operator approval (keyed by device — one live
    /// request per device; a re-submit replaces it). Bounded by [`MAX_PENDING_REQUESTS`].
    requests: HashMap<DeviceId, PendingRequest>,
    active: HashMap<DeviceId, Session>,
}

impl SessionRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    /// Offer a single-use pairing `code` that grants `role`, valid until
    /// `now + ttl`. The caller generates `code` randomly (kept out of this layer
    /// for testability). Re-offering an existing code replaces it.
    pub fn offer_pairing(
        &mut self,
        code: impl Into<String>,
        role: Role,
        now: Instant,
        ttl: Duration,
    ) {
        let code = code.into();
        // Defence in depth: an empty code carries no entropy and must never be a
        // valid offer, even if a caller bug produced one.
        if code.is_empty() {
            return;
        }
        self.pending.insert(
            code,
            PendingPairing {
                role,
                expires_at: now.checked_add(ttl).unwrap_or(now),
            },
        );
    }

    /// Redeem `code` for `device_id`, binding the caller-generated `token` to a new
    /// active session and returning the granted role. The code is single-use — it is
    /// consumed whether it matched, expired (removed), so it can never be replayed.
    pub fn redeem(
        &mut self,
        code: &str,
        device_id: DeviceId,
        token: SessionToken,
        now: Instant,
    ) -> Result<Role, PairingError> {
        // An empty code is never a valid offer (see `offer_pairing`); reject before
        // the map lookup so it can never collide with anything.
        if code.is_empty() {
            return Err(PairingError::UnknownCode);
        }
        match self.pending.get(code) {
            None => Err(PairingError::UnknownCode),
            Some(p) if now >= p.expires_at => {
                self.pending.remove(code);
                Err(PairingError::ExpiredCode)
            }
            Some(p) => {
                // Single-use: consume the code on redeem WHATEVER the outcome, so `pending`
                // strictly shrinks and the code can never be replayed (even a cap rejection
                // below burns it).
                let role = p.role;
                self.pending.remove(code);
                // Bound the active-session map (audit M3): a NEW `device_id` can only pair
                // when there is room. Re-pairing an ALREADY-active `device_id` overwrites its
                // entry (no growth) and is always allowed — but note this only helps callers
                // that present a STABLE id: the loopback operator shell reuses the host device
                // id, whereas the remote WS server (`server.rs`) mints a fresh random id per
                // pairing, so a remote re-pair takes a NEW slot. That is fine because the cap
                // now bounds RECENTLY-ACTIVE devices, not lifetime pairings (audit #8): a dead
                // session self-reclaims via [`prune_idle`] after [`SESSION_IDLE_TTL`] of no
                // re-authentication (the caller prunes before this cap check), so a full
                // registry frees slots as idle devices age out; past the cap a new device is
                // still refused (fail-closed) and `revoke` remains the immediate manual escape.
                if !self.active.contains_key(&device_id) && self.active.len() >= MAX_ACTIVE_SESSIONS
                {
                    return Err(PairingError::TooManySessions);
                }
                self.active.insert(
                    device_id.clone(),
                    Session {
                        device_id,
                        role,
                        token,
                        last_seen: now,
                        pinned: false,
                        // The legacy code-flow carries no device metadata; the device-initiated
                        // request→approve flow populates these instead.
                        name: String::new(),
                        platform: String::new(),
                    },
                );
                Ok(role)
            }
        }
    }

    /// Whether `code` is an outstanding, unexpired pairing offer — **without**
    /// consuming it. Used to reject a bad code cheaply (e.g. before prompting the
    /// host for confirmation); redemption still happens only via [`redeem`](Self::redeem).
    pub fn code_valid(&self, code: &str, now: Instant) -> bool {
        if code.is_empty() {
            return false;
        }
        self.pending.get(code).is_some_and(|p| now < p.expires_at)
    }

    /// Authenticate a request: the device's [`Role`] iff an active session exists
    /// and `token` matches it in constant time.
    pub fn authenticate(&self, device_id: &DeviceId, token: &str) -> Option<Role> {
        // An empty token is never valid — reject before any comparison so a
        // caller (or attacker) presenting "" can never authenticate, regardless of
        // what was stored.
        if token.is_empty() {
            return None;
        }
        let session = self.active.get(device_id)?;
        if session.token.matches(token) {
            Some(session.role)
        } else {
            None
        }
    }

    /// Mark a device's session as active as of `now` — the caller invokes this on every
    /// successful (re)authentication so [`prune_idle`](Self::prune_idle) does not reclaim a
    /// device that is still connecting (audit #8). Returns whether a session was refreshed.
    pub fn touch(&mut self, device_id: &DeviceId, now: Instant) -> bool {
        if let Some(session) = self.active.get_mut(device_id) {
            session.last_seen = now;
            true
        } else {
            false
        }
    }

    /// Pin a session so it is exempt from idle reclamation — for the trusted host-local operator
    /// credential (pre-seeded once, held over one long-lived loopback connection so `touch` never
    /// refreshes it, and with no re-pair path); it must never idle out from under the host
    /// (audit #8). Returns whether a session was pinned.
    pub fn pin(&mut self, device_id: &DeviceId) -> bool {
        if let Some(session) = self.active.get_mut(device_id) {
            session.pinned = true;
            true
        } else {
            false
        }
    }

    /// Reclaim active sessions idle (no re-authentication) for longer than `ttl` — housekeeping
    /// so the active-session cap (audit M3) bounds *recently-active* devices, not lifetime
    /// pairings (audit #8). PINNED sessions (the host-local operator) are never reclaimed.
    /// `saturating_duration_since` never panics if a clock ran backwards. Returns the count reclaimed.
    pub fn prune_idle(&mut self, now: Instant, ttl: Duration) -> usize {
        let before = self.active.len();
        self.active
            .retain(|_, s| s.pinned || now.saturating_duration_since(s.last_seen) <= ttl);
        before - self.active.len()
    }

    /// Revoke a device's session (e.g. operator removes a controller). Returns
    /// whether a session was actually removed.
    pub fn revoke(&mut self, device_id: &DeviceId) -> bool {
        self.active.remove(device_id).is_some()
    }

    /// Change a device's granted [`Role`] in place — the operator re-roles a controller
    /// (the `ManageDevices` authority; Operator-only at the command layer). Takes effect on
    /// the device's next authenticated request. Returns whether an active session was updated.
    pub fn set_role(&mut self, device_id: &DeviceId, role: Role) -> bool {
        if let Some(session) = self.active.get_mut(device_id) {
            session.role = role;
            true
        } else {
            false
        }
    }

    /// A token-free snapshot of every active session, for the operator's device manager.
    /// Sorted by device id so the listing is deterministic (the `active` map is unordered);
    /// `idle_for` is `now - last_seen` (saturating, never panics on a backwards clock). Bounded
    /// by [`MAX_ACTIVE_SESSIONS`] and NEVER exposes a bearer token (no-leak, no sensitive return).
    pub fn sessions(&self, now: Instant) -> Vec<SessionSummary> {
        let mut out: Vec<SessionSummary> = self
            .active
            .values()
            .map(|s| SessionSummary {
                device_id: s.device_id.clone(),
                role: s.role,
                name: s.name.clone(),
                platform: s.platform.clone(),
                idle_for: now.saturating_duration_since(s.last_seen),
                pinned: s.pinned,
            })
            .collect();
        out.sort_by(|a, b| a.device_id.0.cmp(&b.device_id.0));
        out
    }

    /// Submit a device-initiated pairing request (the device scanned the pairing QR and is
    /// host-authenticated at the transport layer). Records the device's `name`/`platform` and the
    /// pairing `fingerprint` the operator verifies against the phone; it does NOT create a session
    /// — the operator must [`approve_request`](Self::approve_request) it with a role. A re-submit
    /// from the same device replaces its outstanding request; an already-active device is a no-op.
    /// Bounded by [`MAX_PENDING_REQUESTS`].
    pub fn submit_request(
        &mut self,
        device_id: DeviceId,
        name: impl Into<String>,
        platform: impl Into<String>,
        fingerprint: impl Into<String>,
        now: Instant,
    ) -> Result<(), RequestError> {
        // An already-active device needs no request (re-roling it is an operator action, not a
        // fresh pairing) — no-op success, never consuming a request slot.
        if self.active.contains_key(&device_id) {
            return Ok(());
        }
        // Bound NEW devices; an already-queued device replaces its request (no growth).
        if !self.requests.contains_key(&device_id) && self.requests.len() >= MAX_PENDING_REQUESTS {
            return Err(RequestError::TooManyRequests);
        }
        self.requests.insert(
            device_id,
            PendingRequest {
                name: name.into(),
                platform: platform.into(),
                fingerprint: fingerprint.into(),
                requested_at: now,
            },
        );
        Ok(())
    }

    /// A token-free, deterministic (sorted by device id) snapshot of outstanding pairing requests,
    /// for the operator's "PENDING REQUEST" list. Bounded by [`MAX_PENDING_REQUESTS`].
    pub fn pending_requests(&self, now: Instant) -> Vec<PendingRequestSummary> {
        let mut out: Vec<PendingRequestSummary> = self
            .requests
            .iter()
            .map(|(id, r)| PendingRequestSummary {
                device_id: id.clone(),
                name: r.name.clone(),
                platform: r.platform.clone(),
                fingerprint: r.fingerprint.clone(),
                waiting_for: now.saturating_duration_since(r.requested_at),
            })
            .collect();
        out.sort_by(|a, b| a.device_id.0.cmp(&b.device_id.0));
        out
    }

    /// Number of outstanding pairing requests (so callers can assert the buffer stays bounded).
    pub fn pending_request_count(&self) -> usize {
        self.requests.len()
    }

    /// Approve a device's pending request, assigning it `role` — the operator's RBAC choice at
    /// approval time (`ManageDevices`-gated at the command layer) — and binding the caller-generated
    /// `token` to a new active session that carries the device's captured name/platform. Consumes
    /// the request. Fails closed with [`ApproveError::NoSuchRequest`] if none is outstanding, or
    /// [`ApproveError::TooManySessions`] if the active cap is reached for a NEW device (the request
    /// is left intact so the operator can retry after freeing a slot).
    pub fn approve_request(
        &mut self,
        device_id: &DeviceId,
        role: Role,
        token: SessionToken,
        now: Instant,
    ) -> Result<Role, ApproveError> {
        let req = self
            .requests
            .get(device_id)
            .ok_or(ApproveError::NoSuchRequest)?;
        // Bound the active map (audit M3): a NEW device can only pair when there is room. Checked
        // BEFORE consuming the request so a cap rejection is retryable (unlike the single-use code).
        if !self.active.contains_key(device_id) && self.active.len() >= MAX_ACTIVE_SESSIONS {
            return Err(ApproveError::TooManySessions);
        }
        let name = req.name.clone();
        let platform = req.platform.clone();
        self.requests.remove(device_id);
        self.active.insert(
            device_id.clone(),
            Session {
                device_id: device_id.clone(),
                role,
                token,
                last_seen: now,
                pinned: false,
                name,
                platform,
            },
        );
        Ok(role)
    }

    /// Deny (drop) a device's pending request — the operator rejects it. Returns whether a request
    /// was actually removed.
    pub fn deny_request(&mut self, device_id: &DeviceId) -> bool {
        self.requests.remove(device_id).is_some()
    }

    /// Reclaim pairing requests that have waited longer than `ttl` without an operator decision
    /// (housekeeping, no-leak — an abandoned request self-clears). Returns the count reclaimed.
    pub fn prune_stale_requests(&mut self, now: Instant, ttl: Duration) -> usize {
        let before = self.requests.len();
        self.requests
            .retain(|_, r| now.saturating_duration_since(r.requested_at) <= ttl);
        before - self.requests.len()
    }

    /// Number of active (authenticated) sessions.
    pub fn active_count(&self) -> usize {
        self.active.len()
    }

    /// Number of outstanding (unredeemed) pairing offers. Exposed so callers can
    /// assert the registry does not grow without bound (offers are consumed on
    /// redeem and reclaimed by [`prune_expired`](Self::prune_expired)).
    pub fn pending_count(&self) -> usize {
        self.pending.len()
    }

    /// Withdraw a specific outstanding pairing offer (e.g. the operator cancels
    /// pairing mode while the code is still within its TTL). Returns whether an
    /// offer was actually removed.
    pub fn withdraw(&mut self, code: &str) -> bool {
        self.pending.remove(code).is_some()
    }

    /// Drop pairing offers whose window has closed (housekeeping).
    pub fn prune_expired(&mut self, now: Instant) {
        self.pending.retain(|_, p| now < p.expires_at);
    }
}
