//! The desktop's licensing client (EPIC-PL-C foundation; FR-513, FR-517, FR-518).
//!
//! Before this crate the desktop consumed none of the platform: no activation, no
//! entitlement, no licence code in any workspace crate. This is the seam that makes the
//! desktop a client of the Platform API at all — and it is deliberately a *narrow* one.
//! It does exactly three things:
//!
//! 1. **Activates a device**, over both server-side paths — account sign-in (primary) and
//!    enrollment key (delegation). See [`client`].
//!
//!    **The sign-in path does not currently work end to end against the deployed API**, and
//!    nothing here should be read as saying it does. Django's CSRF middleware rejects
//!    `POST /graphql/account` with an HTML 403 before the mutation runs, and the injected
//!    `HttpTransport` can only carry a bearer, so the call cannot succeed from this client.
//!    It fails closed — no credential is exposed and nothing is blocked — and now reports
//!    [`ActivationFailure::UnexpectedStatus`] rather than pretending the contract drifted.
//!    Resolution is an API-side decision, tracked as **86ak5t1gw**; it is deliberately not
//!    worked around here. The enrollment-key path is unaffected.
//! 2. **Keeps the resulting device token in the OS secret store**, never in a file and
//!    never in the app database, and keeps it there across sign-out. See [`custody`].
//! 3. **Holds the trusted entitlement-signing keys as a rotation-ready set** selected by
//!    `key_id`. See [`trust`].
//!
//! It does **not** gate, block, enforce or degrade anything. There is no `is_allowed` and
//! no `enforce` in this crate, and that absence is the design.
//!
//! # The invariant that outranks the feature
//!
//! A church runs disconnected for a week and must keep presenting. So:
//!
//! - **Absent or unreachable licensing is [`LicensingStatus::Unknown`]** — an ordinary
//!   state, not a fault and not a block. A fresh install, an install whose operator chose
//!   "Skip — set up later", and an install that cannot reach the platform are all
//!   *unknown*, and the app presents identically in all three.
//! - **Every failure permits presentation.** [`ActivationFailure::permits_presentation`]
//!   and [`LicensingStatus::permits_presentation`] are exhaustive matches returning `true`
//!   for every variant, so a new state cannot be added without someone explicitly
//!   answering the question, and the tests fail if any answer changes.
//! - **No licensing call is on the render, go-live or live-control path** (CON-P1/CON-P2).
//!   This is asserted structurally, not assumed: `tests/test_never_blank.rs` reads the
//!   manifests of the render and live-control crates and fails if any of them takes a
//!   dependency on this crate. Adding `selahcue-licensing` to `selahcue-present` turns
//!   that test red.
//!
//! # Credential hygiene
//!
//! Every secret — enrollment key, account session token, device token — is carried in
//! [`Token`], whose `Debug` and `Display` are redacted, so the usual ways a credential
//! escapes into a log cannot reach it. Tokens are persisted only through [`SecretStore`].
//!
//! That applies in **both** directions. The wire types that must hold a raw secret to
//! serialize it — the enrollment key and the password — carry hand-written redacting
//! `Debug` impls; the response types that receive a secret name [`Token`] directly, so
//! their derived `Debug` redacts structurally rather than by remembering to.
//!
//! The desktop equivalent of the server's audit-redaction discipline is
//! `tests/test_custody.rs`. It sweeps the formatted forms of the credential-bearing types
//! for token material, and — because a hand-written list of types is precisely the thing
//! that falls behind — it also reads `contract.rs` and fails if any public field whose
//! name says it holds a secret is not [`Token`]-typed. That second check is what stops the
//! sweep quietly going out of date as the contract grows.
//!
//! # Deliberately not here
//!
//! Manifest fetching, Ed25519 signature verification and entitlement caching are
//! **86ak5mn1d**. This crate pins the envelope shape (with its `key_id`) and holds the key
//! *set*, so that ticket implements `verify()` against an already rotation-ready contract
//! — DEC-011 pt 2 requires the set from the first build that verifies an entitlement, and
//! retrofitting one later is the failure mode it exists to prevent. Enforcement is
//! **86ak5mn1t**; opportunistic refresh is **86ak5mn1h**.

#![forbid(unsafe_code)]

pub mod client;
pub mod contract;
pub mod custody;
pub mod device;
pub mod entitlement;
pub mod error;
pub mod script;
pub mod trust;

pub use client::{
    AccountSession, Activation, ActivationPath, LicensingClient, PersistOutcome, TokenDisposition,
};
pub use contract::{EntitlementEnvelope, ErrorCode};
pub use custody::{DeviceCredentials, ACCOUNT_SESSION_NAME, DEVICE_TOKEN_NAME, KEYRING_SERVICE};
pub use device::{DeviceIdentity, IdempotencyKey};
pub use entitlement::{
    decide_cache_replacement, Allowance, CacheDecision, GrantScalar, Grants, KeepReason,
};
pub use error::ActivationFailure;
pub use script::{RecordedRequest, ScriptedTransport};
pub use trust::{TrustedKey, TrustedKeys, MAX_TRUSTED_KEYS};

// Re-exported so a consumer needs one dependency, not two, and so the seams the shell
// must inject are discoverable from here.
pub use selahcue_cloud::{
    HttpTransport, InMemorySecretStore, MockTransport, SecretError, SecretStore, Token,
    TransportError,
};

/// What this install knows about its own licensing.
///
/// Deliberately small, and deliberately missing an "invalid" variant. Licensing is either
/// known (this device is activated) or **not known** — and "not known" is the ordinary
/// state of a fresh install, a skipped setup, and an offline booth alike. Collapsing those
/// into one state is what keeps the never-blank promise cheap to hold: there is no state
/// here that any caller could reasonably read as "stop".
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LicensingStatus {
    /// No device token is held, or the platform could not be reached to learn anything.
    ///
    /// Not a fault. Not a block. The operator console may offer activation; the output
    /// path may not change by so much as a pixel.
    Unknown,
    /// This install holds a device token for a registered instance.
    Activated {
        /// The server-side instance id, `dev_` + 32 hex.
        device_public_id: String,
    },
}

impl LicensingStatus {
    /// **The never-blank invariant (CON-P1 / NFR-501): always `true`.**
    ///
    /// An exhaustive match rather than a bare `true`, so that adding a state is a compile
    /// error here and someone has to decide, in code, that it still does not stop a
    /// service. `licensing_status_never_blocks_presentation` enumerates the variants and
    /// fails if any answer changes.
    pub fn permits_presentation(&self) -> bool {
        match self {
            LicensingStatus::Unknown => true,
            LicensingStatus::Activated { .. } => true,
        }
    }

    /// Whether this install is a registered instance.
    pub fn is_activated(&self) -> bool {
        matches!(self, LicensingStatus::Activated { .. })
    }
}

impl Default for LicensingStatus {
    /// A fresh install knows nothing — and presents fine.
    fn default() -> Self {
        LicensingStatus::Unknown
    }
}
