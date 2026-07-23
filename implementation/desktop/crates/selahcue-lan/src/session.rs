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
}

/// Why redeeming a pairing code failed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PairingError {
    /// No such pairing code is outstanding (never offered, or already redeemed).
    UnknownCode,
    /// The code existed but its time window has passed.
    ExpiredCode,
}

struct PendingPairing {
    role: Role,
    expires_at: Instant,
}

/// The operator's registry of outstanding pairing offers and active sessions.
#[derive(Default)]
pub struct SessionRegistry {
    pending: HashMap<String, PendingPairing>,
    active: HashMap<DeviceId, Session>,
}

impl SessionRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    /// Offer a single-use pairing `code` that grants `role`, valid until
    /// `now + ttl`. The caller generates `code` randomly (kept out of this layer
    /// for testability). Re-offering an existing code replaces it.
    pub fn offer_pairing(&mut self, code: impl Into<String>, role: Role, now: Instant, ttl: Duration) {
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
                let role = p.role;
                self.pending.remove(code);
                self.active.insert(
                    device_id.clone(),
                    Session {
                        device_id,
                        role,
                        token,
                    },
                );
                Ok(role)
            }
        }
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

    /// Revoke a device's session (e.g. operator removes a controller). Returns
    /// whether a session was actually removed.
    pub fn revoke(&mut self, device_id: &DeviceId) -> bool {
        self.active.remove(device_id).is_some()
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

    /// Drop pairing offers whose window has closed (housekeeping).
    pub fn prune_expired(&mut self, now: Instant) {
        self.pending.retain(|_, p| now < p.expires_at);
    }
}
