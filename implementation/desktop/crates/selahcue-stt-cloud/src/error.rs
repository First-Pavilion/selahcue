//! What can go wrong, classified by **what the operator should do about it**.
//!
//! The classification is the point, not the taxonomy. A rejected credential and a dropped
//! network are both "cloud transcription stopped", and an operator standing at a console
//! mid-service needs to know which: one is fixed by replacing a key, the other by waiting or
//! checking the Wi-Fi, and retrying is right for exactly one of them. So every variant
//! answers two questions directly — [`DeepgramError::operator_action`] and
//! [`DeepgramError::is_retryable`] — rather than leaving a caller to pattern-match a string.

use crate::credential::Credential;

/// Why a credential could not be used at all (as distinct from being *rejected* by Deepgram,
/// which needs a round trip to discover).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MalformedCredential {
    /// Contains a control character or a non-ASCII byte — it cannot go in an HTTP header
    /// value, and pasting it in would be header injection on the upgrade request.
    IllegalHeaderCharacter,
    /// Contains a space — almost always a copied `"Token abc…"` including the scheme prefix.
    ContainsWhitespace,
    /// Shorter than [`crate::credential::MIN_SECRET_LEN`] — a truncated paste, not a key.
    TooShort,
}

impl MalformedCredential {
    fn reason(self) -> &'static str {
        match self {
            MalformedCredential::IllegalHeaderCharacter => {
                "it contains a control or non-ASCII character"
            }
            MalformedCredential::ContainsWhitespace => {
                "it contains a space — paste the key on its own, without the \"Token \" prefix"
            }
            MalformedCredential::TooShort => "it is too short to be a Deepgram key",
        }
    }
}

/// What the operator should do next. Distinct variants for distinct actions — this is what
/// makes "the credential was rejected" and "the network failed" *usefully* different rather
/// than merely differently spelled.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OperatorAction {
    /// No credential at all. Supply one.
    SupplyCredential,
    /// A credential exists but Deepgram will not accept it. Replace it.
    ReplaceCredential,
    /// Cloud transcription is switched off or not consented to. Change the setting.
    GrantConsent,
    /// The network or the service is unreachable. Check connectivity, or wait.
    CheckNetwork,
    /// Nothing the operator can do — this is ours to fix.
    ReportDefect,
}

/// Everything this crate can fail with.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeepgramError {
    /// No credential is available. `variable` names the environment variable the developer
    /// path reads, so the message can tell the operator exactly what to set.
    MissingCredential { variable: &'static str },
    /// A credential was supplied but cannot be used as-is.
    MalformedCredential(MalformedCredential),
    /// Streaming live audio is not permitted by the operator's settings. The core's
    /// `ProvidersConfig::may_stream_cloud_audio()` said no; see
    /// [`crate::session::StreamAuthorization`].
    ConsentRequired,
    /// The endpoint would carry the credential in clear text. Refused before connecting.
    InsecureEndpoint { url: String },
    /// **Deepgram rejected the credential** at the WebSocket upgrade (HTTP `401` / `403`).
    /// Distinct from [`DeepgramError::Transport`] because the operator's next action is
    /// completely different and because retrying it is pointless.
    CredentialRejected { status: u16 },
    /// **The network or the service was unreachable** — DNS, TCP, TLS, or a socket that
    /// dropped mid-stream. Worth retrying.
    Transport { detail: String },
    /// Deepgram sent something this client cannot read. Ours to fix, not the operator's.
    Protocol { detail: String },
    /// Reconnection was attempted the bounded number of times and gave up. The session has
    /// stopped cleanly; it is not still retrying in the background.
    GaveUp { attempts: u32 },
}

impl DeepgramError {
    /// Build a transport error with the credential's secret **scrubbed out of the detail**.
    ///
    /// Transport stacks quote request context into their error strings, which makes an error
    /// built from one a real escape route for a secret. Taking the credential here means the
    /// scrubbing cannot be forgotten at a call site: there is no other constructor for this
    /// variant that accepts free text.
    pub fn transport(detail: impl std::fmt::Display, credential: Option<&Credential>) -> Self {
        let detail = detail.to_string();
        DeepgramError::Transport {
            detail: match credential {
                Some(c) => c.scrub(&detail),
                None => detail,
            },
        }
    }

    /// Build a protocol error, scrubbed the same way — a malformed frame may quote the
    /// request that produced it.
    pub fn protocol(detail: impl std::fmt::Display, credential: Option<&Credential>) -> Self {
        let detail = detail.to_string();
        DeepgramError::Protocol {
            detail: match credential {
                Some(c) => c.scrub(&detail),
                None => detail,
            },
        }
    }

    /// What the operator should do about this.
    pub fn operator_action(&self) -> OperatorAction {
        match self {
            DeepgramError::MissingCredential { .. } => OperatorAction::SupplyCredential,
            DeepgramError::MalformedCredential(_) | DeepgramError::CredentialRejected { .. } => {
                OperatorAction::ReplaceCredential
            }
            DeepgramError::ConsentRequired => OperatorAction::GrantConsent,
            DeepgramError::Transport { .. } | DeepgramError::GaveUp { .. } => {
                OperatorAction::CheckNetwork
            }
            DeepgramError::InsecureEndpoint { .. } | DeepgramError::Protocol { .. } => {
                OperatorAction::ReportDefect
            }
        }
    }

    /// Whether reconnecting could plausibly succeed.
    ///
    /// Only a transport failure is retryable. Retrying a credential Deepgram has already
    /// rejected cannot succeed — it only hammers the service and hides the real message from
    /// the operator behind a reconnect spinner.
    pub fn is_retryable(&self) -> bool {
        matches!(self, DeepgramError::Transport { .. })
    }
}

impl std::fmt::Display for DeepgramError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DeepgramError::MissingCredential { variable } => write!(
                f,
                "no Deepgram credential: set {variable} in the repository-root .env file"
            ),
            DeepgramError::MalformedCredential(reason) => {
                write!(
                    f,
                    "the Deepgram credential is unusable: {}",
                    reason.reason()
                )
            }
            DeepgramError::ConsentRequired => write!(
                f,
                "cloud transcription is not permitted: it needs both the Cloud transcription \
                 mode and the cloud-transcription opt-in"
            ),
            DeepgramError::InsecureEndpoint { url } => write!(
                f,
                "refusing to send a credential in clear text to a non-loopback endpoint: {url}"
            ),
            DeepgramError::CredentialRejected { status } => write!(
                f,
                "Deepgram rejected the credential (HTTP {status}) — the key is wrong, revoked, \
                 or lacks scope for streaming transcription"
            ),
            DeepgramError::Transport { detail } => {
                write!(f, "could not reach Deepgram: {detail}")
            }
            DeepgramError::Protocol { detail } => {
                write!(
                    f,
                    "Deepgram sent something this client cannot read: {detail}"
                )
            }
            DeepgramError::GaveUp { attempts } => write!(
                f,
                "gave up reconnecting to Deepgram after {attempts} attempts; cloud \
                 transcription has stopped"
            ),
        }
    }
}

impl std::error::Error for DeepgramError {}

// Tests live in `tests/test_error.rs` (public-API integration tests).
