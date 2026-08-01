//! Offline, on-device speech-to-text engine for SelahCue (R3; ADR-0010 / ADR-0019).
//!
//! This crate turns live microphone audio into bounded, timestamped transcript segments
//! behind the [`selahcue_core::transcript::TranscriptProvider`] seam — the exact trait the
//! deterministic `ManualProvider` already implements. The host drains it out-of-band and
//! pumps it into `LiveController::ingest_transcript`, so **nothing in the presentation core,
//! the wire, the controller, or the UI changes** (ADR-0019 decision 3).
//!
//! # Design invariants
//!
//! - **Offline-first.** No network; recognition runs entirely on-device (ADR-0010 / FR-101).
//! - **AI never gates the render path** (FR-083 / NFR-024). Recognition happens off the
//!   host thread and [`SttProvider::poll`](crate::provider::SttProvider) never blocks; a
//!   backlog or an absent model can never stall or back-pressure live output.
//! - **Bounded memory (no-leak).** Every buffer — the PCM ring, the utterance accumulator,
//!   and the pending-segment queue — is hard-capped; an endless sermon cannot grow memory.
//! - **Deterministic tested path.** The pure-Rust pipeline reads no wall clock (timestamps
//!   are derived from the 16 kHz sample position) and uses no RNG, so the whole
//!   audio → VAD → recognizer → segment flow is reproducible with fakes and needs no
//!   microphone, native toolchain, or model file.
//!
//! # Feature flags
//!
//! - `capture` — real microphone capture via `cpal` ([`audio::CpalSource`]).
//! - `whisper` — real recognition via `whisper-rs`/whisper.cpp ([`recognizer::WhisperRecognizer`]).
//!
//! Both are **off by default**: the default build compiles and tests with
//! [`audio::FakeAudioSource`] + [`recognizer::FakeRecognizer`] only. The native backends'
//! accuracy and latency stay spike-gated (S8/S11) and are not claimed verified here.

pub mod audio;
pub mod engine;
pub mod guard;
pub mod model;
pub mod provider;
pub mod pump;
pub mod recognizer;
pub mod resample;
pub mod vad;

pub use audio::{AudioChunk, AudioSource, FakeAudioSource, PcmRing, MAX_PCM_SAMPLES};
pub use engine::{EngineConfig, SttEngine};
pub use guard::FeedbackGuard;
pub use model::{verify_model, Backend, HardwareProbe, ModelError, ModelSelection, WhisperModel};
pub use provider::{SttProvider, MAX_PENDING_SEGMENTS};
pub use pump::pump;
pub use recognizer::{FakeRecognizer, RecognizedSegment, Recognizer};
pub use resample::resample_to_16k_mono;
pub use vad::{EnergyVad, Vad, VadConfig};

/// The recognizer's target sample rate. whisper.cpp consumes 16 kHz mono `f32` in `[-1, 1]`.
pub const TARGET_SAMPLE_RATE: u32 = 16_000;
