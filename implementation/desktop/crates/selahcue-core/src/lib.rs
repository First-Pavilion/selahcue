//! SelahCue domain core.
//!
//! Pure, deterministic domain logic with **no I/O** — the foundation every other
//! SelahCue crate (rendering, persistence, LAN, mobile) builds on. Keeping this
//! layer side-effect-free makes it exhaustively unit-testable (ADR-0015 spirit)
//! and safe against untrusted input (the parser never panics — it returns
//! `Result`/`Option`).
//!
//! Modules:
//! - [`scripture`] — Bible reference parsing (FR-027).
//! - [`plan`] — the service-plan domain model (FR-001/002).
//! - [`timer`] — monotonic-clock timers with a TIME UP state (FR-054/065, NFR-022).

#![forbid(unsafe_code)]
// The `unwrap_used` lint guards the library's runtime paths (which are
// panic-free); tests legitimately unwrap known-good values.
#![cfg_attr(test, allow(clippy::unwrap_used))]

pub mod plan;
pub mod scripture;
pub mod timer;
