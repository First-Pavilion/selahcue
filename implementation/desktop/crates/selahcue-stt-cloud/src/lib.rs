//! Cloud streaming transcription behind the core's [`TranscriptProvider`] seam
//! (R3; ADR-0019; FR-101 / FR-131 / FR-135).
//!
//! This crate streams live microphone audio to **Deepgram** over a WebSocket and turns the
//! service's interim and final results into [`ProviderSegment`]s the rest of the app already
//! consumes. It is deliberately a separate crate from `selahcue-cloud`: that crate is the
//! **SelahCue-hosted** client and the sermon-notes egress gate, which is the opposite
//! topology from reaching a third party directly, and it is deliberately blocking and light
//! where this one needs an async runtime and a TLS WebSocket stack.
//!
//! # The developer-key path in this crate is temporary
//!
//! Phase 1 authenticates with a **developer Deepgram API key** taken from the repository-root
//! `.env` — a throwaway posture that exists so cloud transcription can be built and measured
//! before the platform's auth is ready. **It is not the design.** The shipping path is
//! already specified and ticketed: the desktop asks the SelahCue platform for a short-lived,
//! **server-minted grant token** via `POST /v1/stt/session`, and our Deepgram key never
//! leaves our server (Phase 2, ClickUp 86akby3xu).
//!
//! The code is shaped for that swap rather than for today. The credential is an **injected
//! constructor parameter** ([`Credential`]), never a global read from inside the client, and
//! it already models both spellings Deepgram accepts — `Authorization: Token <api-key>` for a
//! raw key and `Authorization: Bearer <jwt>` for a minted token. Phase 2 is therefore a
//! change of what is passed to a constructor, not a rewrite. Exactly one function in this
//! crate touches the process environment — [`developer_credential_from_env`] — so a change to
//! the shared `.env` loader costs one function here.
//!
//! **A credential is only checked when the socket is opened.** Deepgram does not terminate an
//! established stream when the credential behind it expires, so nothing here may assume that
//! an expiring token ends a session; session lifetime is this crate's business, not the
//! credential's.
//!
//! # What is in the default build, and why that matters
//!
//! The real socket is behind the off-by-default `deepgram` feature, so the default workspace
//! build pulls in no async runtime and no WebSocket stack. Everything decidable without a
//! socket is **not** behind the feature — frame parsing ([`protocol`]), the interim-versus-
//! settled mapping, both bounded buffers ([`SegmentQueue`], [`AudioRing`]), the consent gate
//! ([`StreamAuthorization`]), the retry policy ([`RetryPolicy`]), error classification
//! ([`DeepgramError`]) and readiness ([`readiness`]).
//!
//! That split is a coverage decision, not a stylistic one. `make ci` and the CI workflow run
//! feature-gated Rust suites only from explicit per-crate lines, so a control living behind a
//! feature that no line names would be run by nothing — the condition `CLAUDE.md` records for
//! `selahcue-stt`. Keeping the controls in the default build puts them inside the
//! `cargo test --workspace`, `cargo clippy --workspace`, `cargo deny` and `cargo audit` that
//! CI already runs.
//!
//! # Invariants
//!
//! - **`poll()` never blocks.** The socket runs on its own thread and fills [`SegmentQueue`];
//!   [`CloudTranscriptProvider::poll`] only drains it, so the render path never waits on AI
//!   (FR-083 / NFR-024).
//! - **Both directions are bounded in entry count *and* bytes.** A live network transcript
//!   source feeding a queue that a synchronous poll drains is the classic unbounded-growth
//!   shape; so is an audio buffer filled by a capture callback. Neither can grow without
//!   limit however slowly the other end runs.
//! - **Streaming is unreachable without consent.** A streaming session cannot be constructed
//!   without a [`StreamAuthorization`], and the only way to obtain one is to pass a
//!   `ProvidersConfig` whose `may_stream_cloud_audio()` — the core's single choke point —
//!   returns true.
//! - **The secret never reaches a log line, a `Debug` output or an error message.**
//!   [`Credential`]'s `Debug` is written by hand, it has no `Display`, and transport errors
//!   are scrubbed of the secret before they are constructed.

pub mod audio;
pub mod credential;
pub mod error;
pub mod protocol;
pub mod provider;
pub mod queue;
pub mod readiness;
pub mod retry;
pub mod session;

#[cfg(feature = "deepgram")]
pub mod transport;

pub use audio::{AudioChunk, AudioRing, MAX_QUEUED_AUDIO_BYTES, MAX_QUEUED_AUDIO_CHUNKS};
pub use credential::{
    developer_credential_from_env, Credential, CredentialScheme, DEEPGRAM_API_KEY_VAR,
};
pub use error::{DeepgramError, OperatorAction};
pub use protocol::{DeepgramFrame, ResultsFrame};
pub use provider::{
    CloudTranscriptProvider, SessionState, SessionStatus, DEEPGRAM_LABEL, DEGRADED_FALLBACK_NOTICE,
};
pub use queue::{SegmentQueue, MAX_QUEUED_SEGMENTS, MAX_QUEUED_SEGMENT_BYTES};
pub use readiness::{
    credential_present, readiness, readiness_from, transport_in_build, CloudSttReadiness,
    CloudSttStatus, CredentialPresent, SttProviderView, TransportInBuild,
};
pub use retry::{RetryPolicy, MAX_RECONNECT_ATTEMPTS};
pub use session::{DeepgramEndpoint, Encoding, RequestSpec, StreamAuthorization, StreamParams};
