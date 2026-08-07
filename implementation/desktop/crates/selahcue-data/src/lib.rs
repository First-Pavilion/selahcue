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
//! - [`deck_repo`] — authored slide-deck library persistence (Design 2.0 node 329:124).
//! - [`media_repo`] — [`selahcue_core::media::MediaLibrary`] persistence (Design 2.0 node 329:124).
//!
//! At-rest encryption (FR-154) is behind the `encryption` feature: it compiles
//! SQLCipher and exposes [`EncryptionKey`] plus [`Database::open_encrypted`].

#![forbid(unsafe_code)]

mod db;
pub mod deck_repo;
mod error;
#[cfg(feature = "encryption")]
mod key;
pub mod media_repo;
pub mod migrations;
pub mod output_repo;
pub mod plan_repo;
pub mod saved_theme_repo;
pub mod screen_config_repo;
pub mod screen_repo;
pub mod screen_theme_repo;
pub mod session_repo;

pub use db::Database;
pub use error::{DataError, Result};
#[cfg(feature = "encryption")]
pub use key::EncryptionKey;
