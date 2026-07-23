//! SelahCue persistence layer.
//!
//! Encrypted-at-rest-ready SQLite storage for the domain model: a WAL-configured
//! [`Database`] with versioned [`migrations`], integrity checks, crash-safe
//! backups (FR-079; ADR-0007), and repositories that map the pure
//! [`selahcue_core`] types to tables and back.
//!
//! Modules:
//! - [`db`] — open/configure, integrity, checkpoint, backup.
//! - [`migrations`] — versioned, append-only schema migrations.
//! - [`plan_repo`] — [`selahcue_core::plan::ServicePlan`] persistence (FR-001/002).

#![forbid(unsafe_code)]
#![cfg_attr(test, allow(clippy::unwrap_used))]

mod db;
mod error;
pub mod migrations;
pub mod plan_repo;

pub use db::Database;
pub use error::{DataError, Result};
