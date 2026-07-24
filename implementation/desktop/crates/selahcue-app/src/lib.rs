//! SelahCue application wiring.
//!
//! [`LiveController`] maps RBAC-checked LAN control commands onto the presenter and
//! service plan, so a remote/mobile controller drives the audience output. With the
//! `server` feature, [`handler_for`] plugs it into the pinned-TLS control server.

#![forbid(unsafe_code)]

mod controller;
pub mod keymap;
mod operator;

pub use controller::{ControllerReply, ControllerSnapshot, LiveController};
pub use keymap::{CanonicalAction, KeyPress, Keymap};
pub use operator::{ItemView, OperatorShell, OperatorView};

#[cfg(feature = "server")]
pub use controller::handler_for;
#[cfg(feature = "server")]
pub use operator::RemoteOperator;
