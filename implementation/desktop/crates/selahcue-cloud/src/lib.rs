//! SelahCue-hosted cloud client for the Providers & Privacy screen (R3;
//! FR-131/132/134/135, NFR-018).
//!
//! **The live SelahCue cloud service does not exist yet.** This crate is the
//! desktop-side half: a versioned API [`contract`], a consent-gated [`client`]
//! implementing [`selahcue_core::providers::NoteProvider`] over an **injected**
//! [`transport::HttpTransport`] seam, a deterministic [`mock`] transport the tests
//! and the operator dev-build use, a [`local`] offline fallback, and an
//! OS-secret-store-backed account token ([`secret`]). Pointing at the real service
//! is a configuration change (base URL + token), not a code change.
//!
//! **Privacy posture.** The core owns the egress gate ([`ProvidersConfig::build_note_request`]);
//! this crate never sends anything the gate did not build — and the gate only ever
//! builds a request carrying the *completed transcript* (never live audio), only on
//! an explicit Generate, only once cloud-notes consent is set. On a transport failure
//! [`generate_sermon_notes`] degrades to the local fallback rather than blocking or
//! blanking (FR-135).
//!
//! [`ProvidersConfig::build_note_request`]: selahcue_core::providers::ProvidersConfig::build_note_request

#![forbid(unsafe_code)]

pub mod client;
pub mod contract;
pub mod local;
pub mod mock;
pub mod secret;
pub mod transport;

pub use client::SelahCueCloudClient;
pub use local::LocalNoteProvider;
pub use mock::MockTransport;
pub use secret::{InMemorySecretStore, SecretError, SecretStore, Token};
pub use transport::{HttpResponse, HttpTransport, TransportError};

use selahcue_core::providers::{NoteDraft, NoteError, NoteProvider, ProvidersConfig, Quota};

/// The outcome of a sermon-note generation: the draft, which provider served it, and
/// whether the result is degraded (cloud failed → local fallback, FR-135).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GenerationOutcome {
    pub draft: NoteDraft,
    /// The serving provider's label ("SelahCue AI" or the local fallback).
    pub provider_label: String,
    /// True when the cloud path failed and the local fallback served the draft.
    pub degraded: bool,
    /// The monthly quota, when the serving provider reports one (cloud only).
    pub quota: Option<Quota>,
}

/// Generate sermon notes end-to-end with consent gating and graceful fallback.
///
/// 1. The core builds a consent-gated request — returns [`NoteError::ConsentRequired`]
///    (and issues **no** network call) unless cloud-notes consent is set and Generate
///    was pressed.
/// 2. The `cloud` provider is tried first.
/// 3. On a **transport** failure only (network loss/unreachable), the `local` provider
///    serves a degraded draft (FR-135). `NotConfigured` and `QuotaExceeded` propagate
///    (they are honest states the UI must show, not network blips to paper over).
pub fn generate_sermon_notes<C, L>(
    config: &ProvidersConfig,
    transcript: &str,
    generate_pressed: bool,
    cloud: &C,
    local: &L,
) -> Result<GenerationOutcome, NoteError>
where
    C: CloudNoteProvider,
    L: NoteProvider,
{
    // Egress choke point — nothing leaves the device unless this succeeds.
    let req = config.build_note_request(transcript, generate_pressed)?;

    match cloud.generate_with_quota(&req) {
        Ok((draft, quota)) => Ok(GenerationOutcome {
            draft,
            provider_label: cloud.label().to_string(),
            degraded: false,
            quota,
        }),
        // Network blip / unreachable → fall back locally, clearly degraded.
        Err(NoteError::Transport(_)) => {
            let draft = local.generate(&req)?;
            Ok(GenerationOutcome {
                draft,
                provider_label: local.label().to_string(),
                degraded: true,
                quota: None,
            })
        }
        // Honest terminal states surface to the UI unchanged.
        Err(other) => Err(other),
    }
}

/// A [`NoteProvider`] that can also report the server-owned quota alongside the draft.
/// The cloud client implements this; the local fallback only implements `NoteProvider`.
pub trait CloudNoteProvider: NoteProvider {
    /// Generate a draft and return the provider's current quota when available.
    fn generate_with_quota(
        &self,
        req: &selahcue_core::providers::NoteRequest,
    ) -> Result<(NoteDraft, Option<Quota>), NoteError>;
}
