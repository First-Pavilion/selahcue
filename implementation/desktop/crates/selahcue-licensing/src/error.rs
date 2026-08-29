//! Activation failures, classified — and the invariant that none of them may stop a
//! service.
//!
//! # The never-blank invariant, made structural
//!
//! CON-P1 (inheriting NFR-024) and CON-P2 (inheriting NFR-015/CON-2) say no licensing
//! failure or state may blank, alter or block live output, and that core presentation
//! runs with zero network for the entire entitlement window. This module carries that as
//! something a test can hold onto rather than a comment:
//!
//! - [`LicensingError::permits_presentation`] is written as an **exhaustive match** that
//!   answers `true` for every variant. A future variant cannot be added without the
//!   compiler demanding an answer here, and `every_error_permits_presentation` enumerates
//!   the variants and fails if any answers `false`.
//! - There is no `is_blocked`, `require_activation` or `enforce` anywhere in this crate.
//!   Enforcement is a separate ticket (86ak5mn1t) and a separate, *deliberately* ladder-
//!   shaped decision (FR-520); this crate obtains credentials and reports state.
//!
//! # What this client can and cannot tell apart — and why it is path-aware
//!
//! The account-setup design (`ACCOUNT-SETUP-HANDOFF.md` §5) specifies distinct frames for
//! "instance limit reached" (A5) and "licence expired / not yet active" (A6). Whether the
//! server distinguishes them **depends on which path you came in by**. An earlier version
//! of this note said flatly that it could not, which was generalising from the
//! enrollment-key path and was wrong:
//!
//! - **Account-session path (primary).** The server *does* distinguish. An org with no
//!   currently-valid licence key fails in `_resolve_org_active_license_key`
//!   (`devices/services.py:511-529`) with `NOT_FOUND` — covering expired, not yet started,
//!   and never issued — while the device limit still arrives as `POLICY_DENIED`. A5 and A6
//!   are separable here, and throwing that away is throwing away something the server took
//!   the trouble to tell us.
//! - **Enrollment-key path (delegation).** `NOT_FOUND` already means something else on this
//!   path — "that key is not recognised" (A4) — and both the over-limit checks
//!   (`:327-331`, `:416-417`) and the validity-window check (`:134-139`) raise an
//!   identical, detail-free `POLICY_DENIED`. Here A5 and A6 genuinely are indistinguishable,
//!   and [`ActivationFailure::PolicyDenied`] stays one honest state rather than a guess.
//!
//! Hence [`ActivationFailure::from_code`] takes the [`ActivationPath`]. The same
//! `NOT_FOUND` means "no active licence" on one path and "unknown key" on the other, and
//! collapsing them told a signed-in admin whose plan had lapsed to go and check their
//! enrollment key for typos — a key that path never uses.

use crate::client::ActivationPath;
use crate::contract::ErrorCode;

/// Why an activation attempt did not produce a device token.
///
/// Classified so the shell can render the design's error frames without parsing strings.
/// Every variant is non-fatal to presentation — see [`Self::permits_presentation`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ActivationFailure {
    /// The platform could not be reached at all: DNS, TLS, connection, timeout. Frame A7.
    ///
    /// **Retryable and silent.** FR-523 and NFR-504 require this to produce no
    /// operator-facing warning while the device is inside its entitlement window; it is
    /// the "unknown", not a fault. The message never contains request bodies or secrets.
    Unreachable(String),

    /// The org has no currently-valid licence: expired, not yet started, or never issued.
    /// Frame **A6** — "Your SelahCue plan has expired… Renew it."
    ///
    /// Reached only on the account-session path, where `NOT_FOUND` from
    /// `_resolve_org_active_license_key` means exactly this. On the enrollment-key path the
    /// same code means [`Self::UnknownKey`] instead — see the module docs.
    NoActiveLicense,

    /// The presented enrollment key is unknown, or its hash did not match. Frame A4.
    ///
    /// The server returns `NOT_FOUND` for both and the copy must not reveal which — that
    /// indistinguishability is deliberate, not an oversight to be improved on.
    UnknownKey,

    /// The org's policy refused this activation. Frame A5 **or** A6 — see the module docs
    /// for why the server does not say which.
    ///
    /// Covers: active devices at the plan's device limit; a licence outside its
    /// `starts_at`/`expires_at` window (expired *and* not-yet-started); a licence whose
    /// status is not activatable; and a revoked device re-enrolling.
    PolicyDenied,

    /// The credential presented for the *session* path was rejected, or the account
    /// session has expired. Sign in again.
    ///
    /// Note this says nothing about the **device** token: an expired account session never
    /// revokes a device token (DEC-007, FR-542) and never stops the app presenting.
    Unauthenticated,

    /// The signed-in account lacks the role activation requires (the server requires
    /// ADMIN on the session path, `devices/services.py:541`).
    PermissionDenied,

    /// The request was malformed. A client-side bug, not an operator error.
    ValidationFailed,

    /// Too many attempts. The activation endpoint allows 10 per minute per IP.
    RateLimited,

    /// The server failed or is misconfigured (5xx, including a missing signing key).
    /// Retryable, like [`Self::Unreachable`], and equally silent.
    Server(u16),

    /// A coded refusal this build does not recognise, kept rather than collapsed so a
    /// newer server's state is at least reportable.
    Coded(ErrorCode),

    /// The platform answered outside the API contract at a non-5xx status — an HTML error
    /// page from a proxy or from Django middleware rather than a coded refusal.
    ///
    /// Distinct from [`Self::Malformed`], which says the *contract* drifted, and from
    /// [`Self::Server`], which says the server failed. This one says something in front of
    /// the application answered instead of it. A CSRF rejection and a wrong-method 405 both
    /// land here, and reporting either as contract drift sends the reader hunting for a
    /// schema change that does not exist.
    UnexpectedStatus(u16),

    /// The response did not parse as the contract. Kept distinct from `Server` because it
    /// means the contract drifted, which is a developer-facing problem.
    Malformed(String),
}

impl ActivationFailure {
    /// Map a coded server error onto a classified failure, for the path it arrived on.
    ///
    /// The path is not decoration: `NOT_FOUND` means "no active licence" on the session
    /// path and "unknown enrollment key" on the key path. See the module docs.
    pub fn from_code(code: ErrorCode, path: ActivationPath) -> Self {
        match code {
            ErrorCode::NotFound => match path {
                ActivationPath::AccountSession => ActivationFailure::NoActiveLicense,
                ActivationPath::EnrollmentKey => ActivationFailure::UnknownKey,
            },
            ErrorCode::PolicyDenied => ActivationFailure::PolicyDenied,
            ErrorCode::Unauthenticated => ActivationFailure::Unauthenticated,
            ErrorCode::PermissionDenied => ActivationFailure::PermissionDenied,
            ErrorCode::ValidationFailed => ActivationFailure::ValidationFailed,
            ErrorCode::RateLimited => ActivationFailure::RateLimited,
            ErrorCode::Internal => ActivationFailure::Server(500),
            other => ActivationFailure::Coded(other),
        }
    }

    /// **The never-blank invariant (CON-P1 / NFR-501): always `true`.**
    ///
    /// Written as an exhaustive match rather than `true` so that adding a variant is a
    /// compile error here — someone introducing a "licence revoked" state has to look at
    /// this function and say, in code, that it still does not stop a service. It always
    /// should: a revoked licence refuses *future* API service, it does not command the
    /// running app (CON-P3, NG-5).
    pub fn permits_presentation(&self) -> bool {
        match self {
            ActivationFailure::Unreachable(_) => true,
            ActivationFailure::NoActiveLicense => true,
            ActivationFailure::UnknownKey => true,
            ActivationFailure::PolicyDenied => true,
            ActivationFailure::Unauthenticated => true,
            ActivationFailure::PermissionDenied => true,
            ActivationFailure::ValidationFailed => true,
            ActivationFailure::RateLimited => true,
            ActivationFailure::Server(_) => true,
            ActivationFailure::Coded(_) => true,
            ActivationFailure::UnexpectedStatus(_) => true,
            ActivationFailure::Malformed(_) => true,
        }
    }

    /// Whether the shell should retry silently rather than show the operator anything.
    ///
    /// FR-523: "Airplane-mode refresh = silent retry, no operator-facing warning".
    /// Network trouble and server trouble are transient; a coded refusal is a decision
    /// somebody made, and is surfaced between sessions.
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            ActivationFailure::Unreachable(_)
                | ActivationFailure::Server(_)
                | ActivationFailure::RateLimited
        )
    }
}

impl core::fmt::Display for ActivationFailure {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            ActivationFailure::Unreachable(why) => {
                write!(f, "the SelahCue platform could not be reached: {why}")
            }
            ActivationFailure::NoActiveLicense => write!(
                f,
                "this account has no active SelahCue plan; renew it to activate a device"
            ),
            ActivationFailure::UnknownKey => {
                write!(f, "that enrollment key was not recognised")
            }
            ActivationFailure::PolicyDenied => write!(
                f,
                "the plan's policy does not allow this activation \
                 (device limit reached, or the licence is outside its validity window)"
            ),
            ActivationFailure::Unauthenticated => {
                write!(f, "the account session is not valid; sign in again")
            }
            ActivationFailure::PermissionDenied => write!(
                f,
                "this account does not have permission to activate a device"
            ),
            ActivationFailure::ValidationFailed => {
                write!(f, "the activation request was rejected as invalid")
            }
            ActivationFailure::RateLimited => {
                write!(f, "too many activation attempts; try again shortly")
            }
            ActivationFailure::Server(status) => {
                write!(
                    f,
                    "the SelahCue platform returned an error (status {status})"
                )
            }
            ActivationFailure::Coded(code) => {
                write!(f, "the platform refused the request ({})", code.as_str())
            }
            ActivationFailure::UnexpectedStatus(status) => write!(
                f,
                "the SelahCue platform answered unexpectedly (status {status})"
            ),
            ActivationFailure::Malformed(why) => {
                write!(f, "the platform's response could not be read: {why}")
            }
        }
    }
}

impl std::error::Error for ActivationFailure {}
