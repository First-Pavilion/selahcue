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
//! - [`media`] — the bounded media-asset library (FR-003; Design 2.0 node 329:124).
//! - [`timer`] — monotonic-clock timers with a TIME UP state (FR-054/065, NFR-022).
//! - [`transcript`] — bounded, timestamped transcript segments + the STT provider seam
//!   (R3; ADR-0010).
//! - [`providers`] — Providers & Privacy settings/consent + the offline-by-default
//!   egress gate and the note-generation seam (R3; FR-131/132/135/137).
//! - [`detection`] — scripture-reference detection over the transcript stream (R4).
//! - [`audio_capacity`] — the one place "how many samples for N seconds of captured audio"
//!   gets computed, so every capture→consumer hand-off (on-device and cloud alike) derives its
//!   retention cap from the device's real configuration rather than each re-deriving its own
//!   arithmetic (86akby7th).

#![forbid(unsafe_code)]
// The `unwrap_used` lint guards the library's runtime paths (which are
// panic-free); tests legitimately unwrap known-good values.
#![cfg_attr(test, allow(clippy::unwrap_used))]

pub mod audio_capacity;
pub mod detection;
pub mod detector;
pub mod media;
pub mod plan;
pub mod providers;
pub mod scripture;
pub mod timer;
pub mod transcript;
