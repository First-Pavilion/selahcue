//! The injected Deepgram credential, and the one function in this crate that reads the
//! process environment.
//!
//! The credential is a **constructor parameter**, never a global read from inside the
//! client. Phase 1 passes a developer API key; Phase 2 (`POST /v1/stt/session`, ClickUp
//! 86akby3xu) passes a short-lived server-minted grant token instead. Both spellings
//! Deepgram accepts are modelled here so that swap adds no new concept:
//!
//! | credential            | header                        |
//! |-----------------------|-------------------------------|
//! | raw API key           | `Authorization: Token <key>`  |
//! | minted short-lived JWT| `Authorization: Bearer <jwt>` |
//!
//! **The secret does not leave this module in plain text except through one named method.**
//! [`Credential`] has a hand-written `Debug` that prints `<redacted>`, has no `Display`, and
//! derives no comparison traits, so it cannot be printed, formatted or compared into a log
//! by accident. [`Credential::authorization_header_value`] is the single deliberate exit.

use crate::error::{DeepgramError, MalformedCredential};

/// The environment variable the shared developer `.env` loader (ClickUp 86akby6yy) exports
/// the Deepgram key under.
///
/// This crate's **entire** coupling to that loader is this one name: it deliberately does not
/// import the loader's constants, which are `cfg`-gated on the operator's `dev-keys` feature,
/// so a change to the loader's API under security review costs nothing here.
pub const DEEPGRAM_API_KEY_VAR: &str = "DEEPGRAM_API_KEY";

/// A secret shorter than this is a paste error, not a credential. Rejecting it early gives
/// the operator a clear message instead of an opaque `401` several seconds later — and it
/// keeps [`crate::error::DeepgramError::transport`]'s scrubber from matching a short string
/// all over an unrelated error message.
pub const MIN_SECRET_LEN: usize = 16;

// Pinned beside the constant so a later edit cannot silently make the scrubber unsafe or
// the "reject a paste error" test vacuous.
const _: () = assert!(
    MIN_SECRET_LEN >= 8,
    "a secret shorter than 8 bytes would make the transport-error scrubber match common \
     substrings of unrelated error text"
);

/// Which `Authorization` spelling a credential uses.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CredentialScheme {
    /// A raw Deepgram API key — `Authorization: Token <key>`. The Phase 1 developer path.
    Token,
    /// A short-lived, server-minted grant token — `Authorization: Bearer <jwt>`. Phase 2.
    Bearer,
}

impl CredentialScheme {
    /// The literal scheme prefix Deepgram expects in the `Authorization` header value.
    pub fn prefix(self) -> &'static str {
        match self {
            CredentialScheme::Token => "Token",
            CredentialScheme::Bearer => "Bearer",
        }
    }
}

/// A Deepgram credential: a scheme and a secret.
///
/// Deliberately **not** `Debug`-derived, **not** `Display`, and **not** `PartialEq` — the
/// three ways a secret usually escapes into a log or a test failure message.
#[derive(Clone)]
pub struct Credential {
    scheme: CredentialScheme,
    secret: String,
}

impl Credential {
    /// A raw Deepgram API key (Phase 1, developer path — see the crate documentation for why
    /// this is temporary).
    pub fn developer_key(secret: impl Into<String>) -> Result<Self, DeepgramError> {
        Credential::new(CredentialScheme::Token, secret)
    }

    /// A short-lived, server-minted grant token (Phase 2, `POST /v1/stt/session`).
    ///
    /// Deepgram checks a credential **only when the socket is opened** and does not close an
    /// established stream when the credential behind it expires, so callers must not treat
    /// this token's expiry as a session lifetime.
    pub fn grant_token(secret: impl Into<String>) -> Result<Self, DeepgramError> {
        Credential::new(CredentialScheme::Bearer, secret)
    }

    fn new(scheme: CredentialScheme, secret: impl Into<String>) -> Result<Self, DeepgramError> {
        let secret = secret.into();
        if secret.trim().is_empty() {
            return Err(DeepgramError::MissingCredential {
                variable: DEEPGRAM_API_KEY_VAR,
            });
        }
        // A credential goes straight into an HTTP header value. A CR, LF or NUL in it would
        // be header injection on the upgrade request, so it is refused rather than escaped.
        if let Some(bad) = secret
            .chars()
            .find(|c| c.is_control() || !c.is_ascii() || *c == ' ')
        {
            return Err(DeepgramError::MalformedCredential(
                if bad.is_control() || !bad.is_ascii() {
                    MalformedCredential::IllegalHeaderCharacter
                } else {
                    MalformedCredential::ContainsWhitespace
                },
            ));
        }
        if secret.len() < MIN_SECRET_LEN {
            return Err(DeepgramError::MalformedCredential(
                MalformedCredential::TooShort,
            ));
        }
        Ok(Credential { scheme, secret })
    }

    /// Which `Authorization` spelling this credential uses.
    pub fn scheme(&self) -> CredentialScheme {
        self.scheme
    }

    /// The full `Authorization` header value — **the one place the secret becomes a plain
    /// string**. Send it; never log it, never store it, never put it in an error.
    pub fn authorization_header_value(&self) -> String {
        format!("{} {}", self.scheme.prefix(), self.secret)
    }

    /// Replace every occurrence of the secret in `text` with a redaction marker.
    ///
    /// Transport stacks quote request context into their error strings, so an error built
    /// from one is a real escape route for the secret. [`DeepgramError::transport`] routes
    /// every transport error through this.
    pub(crate) fn scrub(&self, text: &str) -> String {
        text.replace(&self.secret, REDACTED)
    }
}

/// What stands in for the secret wherever a credential is formatted.
pub const REDACTED: &str = "<redacted>";

impl std::fmt::Debug for Credential {
    /// Hand-written so the secret cannot reach a log, a panic message or a test failure.
    /// Deriving `Debug` here would print it.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Credential")
            .field("scheme", &self.scheme)
            .field("secret", &REDACTED)
            .finish()
    }
}

/// Read the **developer** Deepgram key from the process environment.
///
/// This is the only function in the crate that touches the environment, and it exists so the
/// operator can obtain a [`Credential`] to inject — clients never call it themselves. The
/// shared loader (ClickUp 86akby6yy) exports [`DEEPGRAM_API_KEY_VAR`] from the repository-root
/// `.env` behind the operator's off-by-default `dev-keys` feature; a blank value in that file
/// leaves the variable unset, so an empty string is not a case this has to handle specially.
///
/// **Temporary.** Phase 2 replaces this entirely with a short-lived grant token fetched from
/// `POST /v1/stt/session`; at that point this function is deleted rather than adapted.
pub fn developer_credential_from_env() -> Result<Credential, DeepgramError> {
    match std::env::var(DEEPGRAM_API_KEY_VAR) {
        Ok(secret) => Credential::developer_key(secret),
        Err(_) => Err(DeepgramError::MissingCredential {
            variable: DEEPGRAM_API_KEY_VAR,
        }),
    }
}

// Tests live in `tests/test_credential.rs` (public-API integration tests).
