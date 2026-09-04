//! Readiness — the crate API ticket 86akby7th renders, so it never has to guess.
//!
//! # Why this is a tri-state and not a boolean
//!
//! There are three different truths here and a boolean conflates two of them:
//!
//! | situation                                   | what the operator should be told                |
//! |---------------------------------------------|-------------------------------------------------|
//! | the `deepgram` feature is not in this build  | cloud transcription isn't part of this build     |
//! | the feature is in, but no key is present     | **set `DEEPGRAM_API_KEY` in the repo-root .env** |
//! | the feature is in and a key is present       | cloud transcription is ready                     |
//!
//! "Cloud transcription unavailable" is not an actionable message. "You have not put a key in
//! `.env`" is. That is the entire reason the middle state exists.
//!
//! # Shape
//!
//! Two vocabularies, deliberately, because two existing surfaces speak them:
//!
//! - [`CloudSttStatus::state`] mirrors the on-device readiness reply the Pre-service Check
//!   already renders (`ready` / `not_downloaded` / `size_mismatch` / `not_in_build`), so the
//!   transcription card can treat both engines the same way.
//! - [`CloudSttStatus::provider_status`] mirrors the sermon-notes lane's `cloud_status`
//!   (`not_configured` / `key_missing` / `direct_provider` / `hosted`), so the two halves of
//!   the Providers & Privacy panel read as one design rather than two idioms.
//!
//! [`CloudSttStatus::provider`] follows the notes side's `notes_provider` exactly, including
//! its invariant: **`provider.is_some() == ready`**. No claiming availability without naming
//! the provider, and no naming a provider while reporting unavailable. The engine name is
//! still reachable when unavailable — it is in the actionable [`CloudSttStatus::detail`]
//! text, which is where it belongs, rather than in a field that would imply readiness.

use crate::credential::{developer_credential_from_env, DEEPGRAM_API_KEY_VAR};

/// Whether the real Deepgram transport is compiled into this build.
///
/// A distinct type rather than a `bool`, and **produced by [`transport_in_build`] rather than
/// constructed at a call site**. Both inputs to [`readiness_from`] are yes/no facts, so as
/// bare booleans a caller could transpose them and the result would still compile and still
/// read correctly — reporting `KeyMissing` on a build with no socket, and `NotInBuild` on a
/// build that merely lacks a key.
///
/// The type only closes that if the identity travels from **where the value is made**.
/// Wrapping whatever a producer hands you, at the boundary, is a label the caller can
/// misapply: `TransportInBuild(credential_present().get())` typechecks perfectly well. So the
/// producers below return these types, and the transposition fails to compile.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TransportInBuild(bool);

impl TransportInBuild {
    /// State a build cannot reach on its own. **Tests only** — production reads
    /// [`transport_in_build`], which is the single source of this fact.
    pub const fn observed(compiled_in: bool) -> Self {
        TransportInBuild(compiled_in)
    }

    pub const fn get(self) -> bool {
        self.0
    }
}

/// Whether a usable credential is available. See [`TransportInBuild`] for why this is a
/// distinct type produced at its source rather than a `bool`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CredentialPresent(bool);

impl CredentialPresent {
    /// State a process cannot reach on its own. **Tests only** — production reads
    /// [`credential_present`].
    pub const fn observed(present: bool) -> Self {
        CredentialPresent(present)
    }

    pub const fn get(self) -> bool {
        self.0
    }
}

/// The producer for "is the transport compiled into this build" — the one place the `cfg` is
/// read, so the fact has a single origin.
pub const fn transport_in_build() -> TransportInBuild {
    TransportInBuild(cfg!(feature = "deepgram"))
}

/// The producer for "is a credential available" — the one place the environment is consulted
/// for readiness.
pub fn credential_present() -> CredentialPresent {
    CredentialPresent(developer_credential_from_env().is_ok())
}

/// The model this crate requests by default, named here so the status and the wire cannot
/// disagree about which model the console is claiming.
pub const DEFAULT_MODEL: &str = "nova-3";

/// The three states cloud transcription can be in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloudSttReadiness {
    /// The `deepgram` feature is not compiled into this build. Nothing the operator can do
    /// at the console.
    NotInBuild,
    /// The transport is in this build, but no credential is present. **Actionable.**
    KeyMissing,
    /// The transport is in this build and a credential is present.
    Ready,
}

impl CloudSttReadiness {
    /// Whether cloud transcription can actually run right now.
    pub fn is_ready(self) -> bool {
        matches!(self, CloudSttReadiness::Ready)
    }

    /// The on-device-shaped state string.
    pub fn state(self) -> &'static str {
        match self {
            CloudSttReadiness::NotInBuild => "not_in_build",
            CloudSttReadiness::KeyMissing => "key_missing",
            CloudSttReadiness::Ready => "ready",
        }
    }

    /// The sermon-notes-shaped provider-status string.
    pub fn provider_status(self) -> &'static str {
        match self {
            CloudSttReadiness::NotInBuild => "not_configured",
            CloudSttReadiness::KeyMissing => "key_missing",
            CloudSttReadiness::Ready => "direct_provider",
        }
    }

    /// A message that names the operator's next action where there is one.
    pub fn detail(self) -> &'static str {
        match self {
            CloudSttReadiness::NotInBuild => {
                "Cloud transcription is not enabled in this build; on-device transcription is \
                 unaffected"
            }
            CloudSttReadiness::KeyMissing => {
                "Cloud transcription would use Deepgram. Set DEEPGRAM_API_KEY in the \
                 repository-root .env file to enable it"
            }
            CloudSttReadiness::Ready => {
                "Cloud transcription is configured to use Deepgram with a developer key on \
                 this machine"
            }
        }
    }

    /// The full status object, shaped for the console.
    pub fn status(self) -> CloudSttStatus {
        CloudSttStatus {
            ready: self.is_ready(),
            state: self.state(),
            provider_status: self.provider_status(),
            // Mirrors the notes lane's `notes_provider`: `Some` exactly when connected.
            provider: self.is_ready().then_some(SttProviderView {
                kind: "deepgram",
                name: "Deepgram",
                model: DEFAULT_MODEL,
                developer_key: true,
            }),
            detail: self.detail(),
            key_variable: DEEPGRAM_API_KEY_VAR,
        }
    }
}

/// Which transcription provider is in use, named honestly (FR-120 / FR-132). Mirrors the
/// sermon-notes lane's `NotesProviderView` field for field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SttProviderView {
    /// Machine-readable provider identity.
    pub kind: &'static str,
    /// Human-readable name — the disclosure string shown to the operator.
    pub name: &'static str,
    /// The model being requested.
    pub model: &'static str,
    /// `true` while this is the Phase 1 developer-key path rather than a server-minted grant
    /// token. Phase 2 sets it `false`.
    pub developer_key: bool,
}

/// Readiness, rendered.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CloudSttStatus {
    /// Whether cloud transcription can run right now.
    pub ready: bool,
    /// `"ready"` | `"key_missing"` | `"not_in_build"` — the on-device-shaped vocabulary.
    pub state: &'static str,
    /// `"direct_provider"` | `"key_missing"` | `"not_configured"` — the sermon-notes-shaped
    /// vocabulary.
    pub provider_status: &'static str,
    /// The provider, named. `Some` exactly when [`CloudSttStatus::ready`].
    pub provider: Option<SttProviderView>,
    /// A message naming the operator's next action where there is one.
    pub detail: &'static str,
    /// The environment variable the developer path reads, so the console can name it without
    /// hardcoding a second copy of the string.
    pub key_variable: &'static str,
}

/// Readiness as a pure function of its two inputs.
///
/// Taking both as parameters is what makes all three states reachable from a test in **either**
/// build. A function that read `cfg!` and the environment directly could only ever be observed
/// in the state the test process happened to be in — and a test looping over inputs it cannot
/// actually vary is decorative, however many iterations it has.
///
/// **Precedence is deliberate.** A build with no transport reports `NotInBuild` whatever the
/// environment holds: telling an operator to go and set a key, on a build that could not stream
/// even with one, sends them to edit a file that cannot help them.
pub fn readiness_from(
    transport: TransportInBuild,
    credential: CredentialPresent,
) -> CloudSttReadiness {
    match (transport.get(), credential.get()) {
        (false, _) => CloudSttReadiness::NotInBuild,
        (true, false) => CloudSttReadiness::KeyMissing,
        (true, true) => CloudSttReadiness::Ready,
    }
}

/// Readiness of *this* build and *this* process environment.
pub fn readiness() -> CloudSttReadiness {
    readiness_from(transport_in_build(), credential_present())
}

// Tests live in `tests/test_readiness.rs` (public-API integration tests).
