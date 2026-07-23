//! SelahCue LAN control core (FR-118/119/120; ADR-0009).
//!
//! The transport-independent heart of the operator↔controller link:
//! - [`protocol`] — the JSON wire messages (commands, events, auth frames) + version.
//! - [`rbac`] — roles, permissions, and the single [`rbac::authorize`] choke point.
//! - [`session`] — device pairing and constant-time-authenticated sessions.
//!
//! The TLS-pinned WebSocket transport that carries these messages is layered on top
//! separately (subsequent batch) so this core stays pure and exhaustively testable.

#![forbid(unsafe_code)]

pub mod protocol;
pub mod rbac;
pub mod session;

pub use rbac::{authorize, Permission, Role};
pub use session::{DeviceId, PairingError, Session, SessionRegistry, SessionToken};
