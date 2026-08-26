//! The Platform API licensing **contract** — serde wire types pinned to the shipped
//! server, read from its source rather than from documentation.
//!
//! ## The two activation paths do not share a transport
//!
//! This is the single most important fact about this contract, and it is easy to get
//! wrong: `POST /v1/activations` is the **enrollment-key path only**. It has no session
//! branch and no discriminator field — the handler passes `license_key` straight into
//! the service (`platform/views.py:65-72`). The **account sign-in path is a GraphQL
//! mutation**, `activateDeviceWithSession` on `POST /graphql/account`
//! (`graphql/account_schema.py:236-255`). The two converge server-side in
//! `_activate_device_for_key` but arrive over different transports with different
//! response shapes (REST `snake_case` / `activation_token` vs GraphQL `camelCase` /
//! `fullToken`). Both are permanently in scope (DEC-011 pt 3).
//!
//! ## Field-name traps pinned here on purpose
//!
//! - The presented enrollment key is sent as **`license_key`**, not `enrollment_key`.
//! - The returned device token is **`activation_token`**, not `device_token` — the
//!   server's audit redaction denylist normalises `device_token`/`deviceToken`/
//!   `DEVICE-TOKEN` to one key and *raises* on it (`graphql/redaction.py:41-46`), so the
//!   one legitimate egress of a token had to be named something else. Renaming this
//!   field to the "obvious" name would break the server, not just the client.
//! - `activation_token` is **`Option`**: it is `null` on a show-once replay, when the
//!   device already holds a live token. That is success, not an error.
//! - The sibling `token` object carries only *metadata* (masked/prefix/suffix/
//!   fingerprint/expiry) and never the secret.
//!
//! ## Errors
//!
//! REST and GraphQL share one code vocabulary ([`ErrorCode`]) with fixed, detail-free
//! messages (`graphql/errors.py:20-32`). **Branch on the code, never the HTTP status or
//! the message**: `PERMISSION_DENIED` and `POLICY_DENIED` both map to 403, and the
//! message string is a constant per code that carries no detail at all.

use selahcue_cloud::Token;
use serde::{Deserialize, Serialize};

/// How a hand-redacted field renders.
///
/// `Token` distinguishes empty from redacted for a reason that applies just as much to the
/// wire types that must hold a raw `String`: a marker printed unconditionally cannot tell
/// "this hid a real secret" from "this had nothing to hide", so a test fixture neutered to
/// `""` sails through a redaction sweep while exercising none of it. Emptiness is not
/// secret material — only the bytes are — so it is safe to say which happened.
pub(crate) fn redacted(value: &str) -> &'static str {
    if value.is_empty() {
        "<empty>"
    } else {
        "***redacted***"
    }
}

/// Enrollment-key activation (REST). **No trailing slash** — the route is registered as
/// `path("activations", ...)` (`platform/urls.py:7`), so a trailing slash is a 404.
pub const ACTIVATIONS_PATH: &str = "/v1/activations";

/// The account GraphQL surface: sign-in and session-authenticated activation.
pub const ACCOUNT_GRAPHQL_PATH: &str = "/graphql/account";

/// The signed entitlement manifest. Fetching, verifying and caching it is **not** this
/// ticket's work (86ak5mn1d); the path and the envelope shape are pinned here so that
/// ticket inherits a contract that already carries `key_id`.
pub const ENTITLEMENT_MANIFEST_PATH: &str = "/v1/entitlements/manifest";

// ---------------------------------------------------------------------------
// Enrollment-key activation — POST /v1/activations
// ---------------------------------------------------------------------------

/// Request body for `POST /v1/activations`.
///
/// Every field is sent explicitly, including the two the server defaults, so a schema
/// change shows up as a diff here. The server coerces missing/`null` values to `""`
/// (`str(raw.get(x) or "")`) and then *rejects* empty `device_fingerprint`/`platform`
/// — so sending them is not optional in practice.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActivationRequest {
    /// Client-chosen retry key. Server-validated against `^[A-Za-z0-9._:-]{12,128}$`
    /// — see [`crate::device::IdempotencyKey`], which enforces the same rule locally so
    /// a malformed key fails on this side instead of burning a round trip and a
    /// throttle slot.
    pub idempotency_key: String,
    /// The presented enrollment key. Named `license_key` on the wire.
    pub license_key: String,
    pub device_fingerprint: String,
    pub platform: String,
    pub app_version: String,
    pub display_name: String,
}

// The wire types are the one place a raw credential sits in a plain `String` — it has to, to
// be serialized. A derived `Debug` would therefore print an enrollment key or a password
// into any log line, panic payload or error report that formatted the request, which is
// exactly the leak `Token`'s redaction prevents everywhere else. These hand-written impls
// keep the diagnostic value — shape and non-secret fields — and drop the secret.
impl core::fmt::Debug for ActivationRequest {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("ActivationRequest")
            .field("idempotency_key", &self.idempotency_key)
            .field("license_key", &redacted(&self.license_key))
            .field("device_fingerprint", &self.device_fingerprint)
            .field("platform", &self.platform)
            .field("app_version", &self.app_version)
            .field("display_name", &self.display_name)
            .finish()
    }
}

/// Success body for `POST /v1/activations` (HTTP 200).
// No `Serialize` here, and that is deliberate: this is a response type, the client only
// ever reads it, and leaving the derive off means the show-once token below cannot be
// written back out to JSON by accident. The same reasoning applies to the two GraphQL
// payloads further down.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct ActivationResponse {
    pub created: bool,
    /// `true` when an existing device was issued a **replacement** token because its own
    /// was expired or revoked. A `true` here is an instruction to overwrite whatever is
    /// cached: the previous token is now `REVOKED`, not merely stale, and will 401.
    pub reminted: bool,
    /// The show-once device token. `None` on an idempotent replay where the device still
    /// holds a live token — the server refuses to re-show a secret it already issued.
    ///
    /// Typed as [`Token`], not `String`, so the derived `Debug` on this struct prints
    /// `Some(Token(***redacted***))`. The redaction is a property of the field's type
    /// rather than of a hand-written formatter someone has to remember to update.
    #[serde(default)]
    pub activation_token: Option<Token>,
    pub device: DeviceDto,
    #[serde(default)]
    pub token: TokenMetaDto,
    pub license: LicenseDto,
}

/// The activated device instance.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct DeviceDto {
    /// `dev_` + 32 hex characters.
    pub device_public_id: String,
    /// `"ACTIVE"` | `"REVOKED"`.
    pub status: String,
    pub platform: String,
}

/// Non-secret metadata *about* the device token. Never carries the token itself.
///
/// Present even on a replay where [`ActivationResponse::activation_token`] is `None`,
/// where it describes the still-live token the device is expected to already hold.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct TokenMetaDto {
    /// `"{first 12 chars}...{last 4 chars}"`.
    #[serde(default)]
    pub masked: Option<String>,
    #[serde(default)]
    pub prefix: Option<String>,
    #[serde(default)]
    pub suffix: Option<String>,
    /// HMAC-SHA256 hex digest (64 chars).
    #[serde(default)]
    pub fingerprint: Option<String>,
    /// Python `isoformat()` — microseconds and a `+00:00` offset, **not** a `Z` suffix.
    #[serde(default)]
    pub expires_at: Option<String>,
}

/// The licence backing the activation.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct LicenseDto {
    pub status: String,
    /// Python `isoformat()` — see [`TokenMetaDto::expires_at`].
    #[serde(default)]
    pub expires_at: String,
}

// ---------------------------------------------------------------------------
// Coded errors — shared by the REST and GraphQL surfaces
// ---------------------------------------------------------------------------

/// The server's error vocabulary (`graphql/errors.py:6-17`).
///
/// Not a `derive(Deserialize)` enum on purpose: an unknown code from a newer server must
/// parse into [`ErrorCode::Unknown`] and be handled, never fail deserialization and turn
/// a coded refusal into an unparseable blob.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ErrorCode {
    Unauthenticated,
    PermissionDenied,
    ValidationFailed,
    NotFound,
    Conflict,
    PolicyDenied,
    RateLimited,
    NotImplemented,
    Internal,
    /// A code this build does not know about.
    Unknown(String),
}

impl ErrorCode {
    /// Parse a wire code. Unrecognised values become [`ErrorCode::Unknown`].
    pub fn parse(value: &str) -> Self {
        match value {
            "UNAUTHENTICATED" => ErrorCode::Unauthenticated,
            "PERMISSION_DENIED" => ErrorCode::PermissionDenied,
            "VALIDATION_FAILED" => ErrorCode::ValidationFailed,
            "NOT_FOUND" => ErrorCode::NotFound,
            "CONFLICT" => ErrorCode::Conflict,
            "POLICY_DENIED" => ErrorCode::PolicyDenied,
            "RATE_LIMITED" => ErrorCode::RateLimited,
            "NOT_IMPLEMENTED" => ErrorCode::NotImplemented,
            "INTERNAL" => ErrorCode::Internal,
            other => ErrorCode::Unknown(other.to_string()),
        }
    }

    /// The wire spelling.
    pub fn as_str(&self) -> &str {
        match self {
            ErrorCode::Unauthenticated => "UNAUTHENTICATED",
            ErrorCode::PermissionDenied => "PERMISSION_DENIED",
            ErrorCode::ValidationFailed => "VALIDATION_FAILED",
            ErrorCode::NotFound => "NOT_FOUND",
            ErrorCode::Conflict => "CONFLICT",
            ErrorCode::PolicyDenied => "POLICY_DENIED",
            ErrorCode::RateLimited => "RATE_LIMITED",
            ErrorCode::NotImplemented => "NOT_IMPLEMENTED",
            ErrorCode::Internal => "INTERNAL",
            ErrorCode::Unknown(other) => other,
        }
    }
}

/// The REST error body: `{"error": {"code", "message"}, "surface", "operation"}`
/// (`platform/responses.py:33-42`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApiErrorEnvelope {
    pub error: ApiErrorBody,
    #[serde(default)]
    pub surface: String,
    #[serde(default)]
    pub operation: String,
}

/// The coded error itself. `message` is a fixed string per code and carries no detail —
/// it exists for logs, never for branching.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApiErrorBody {
    pub code: String,
    #[serde(default)]
    pub message: String,
}

// ---------------------------------------------------------------------------
// Account GraphQL surface — sign-in and session activation
// ---------------------------------------------------------------------------

/// The `login` mutation document. Field names are camelCase: Strawberry auto-camel-cases
/// and this schema is built with the default config (`account_schema.py:258-261`).
pub const LOGIN_MUTATION: &str = "mutation Login($input: LoginInput!) { \
login(input: $input) { sessionToken expiresAt role orgId } }";

/// The session-authenticated activation mutation (`account_schema.py:236-255`).
pub const ACTIVATE_WITH_SESSION_MUTATION: &str =
    "mutation ActivateDeviceWithSession($input: ActivateDeviceInput!) { \
activateDeviceWithSession(input: $input) { fullToken created devicePublicId platform } }";

/// A GraphQL request: a document plus its variables.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GraphQlRequest<V> {
    pub query: &'static str,
    pub variables: V,
}

/// `{"input": {...}}` — every mutation here takes a single `input` argument.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InputVariables<T> {
    pub input: T,
}

/// `LoginInput` (`account_schema.py:52-55`).
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LoginInput {
    pub email: String,
    pub password: String,
}

impl core::fmt::Debug for LoginInput {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("LoginInput")
            .field("email", &self.email)
            .field("password", &redacted(&self.password))
            .finish()
    }
}

/// `ActivateDeviceInput` (`account_schema.py:113-119`), camelCased for the wire.
///
/// Note what is **absent**: no key, no org id. The caller's org is resolved server-side
/// from the session, which is exactly why this path spares a volunteer installer the
/// admin's password — they sign in as themselves.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ActivateDeviceInput {
    pub idempotency_key: String,
    pub device_fingerprint: String,
    pub platform: String,
    pub app_version: String,
    pub display_name: String,
}

/// A GraphQL response: `data` and/or `errors`. Both are optional — a mutation that fails
/// returns HTTP 200 with `errors` populated and `data` null.
#[derive(Debug, Clone, PartialEq, Deserialize)]
pub struct GraphQlResponse<T> {
    #[serde(default = "none")]
    pub data: Option<T>,
    #[serde(default)]
    pub errors: Option<Vec<GraphQlError>>,
}

fn none<T>() -> Option<T> {
    None
}

/// One GraphQL error. The code lives in `extensions.code`
/// (`graphql/errors.py:41-52`).
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct GraphQlError {
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub extensions: Option<GraphQlErrorExtensions>,
}

impl GraphQlError {
    /// The coded error, when the server supplied one.
    pub fn code(&self) -> Option<ErrorCode> {
        self.extensions
            .as_ref()
            .and_then(|e| e.code.as_deref())
            .map(ErrorCode::parse)
    }
}

/// The `extensions` bag; only `code` is contractual.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct GraphQlErrorExtensions {
    #[serde(default)]
    pub code: Option<String>,
}

/// `data` for the `login` mutation.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
pub struct LoginData {
    pub login: LoginPayload,
}

/// `LoginPayload` (`account_schema.py:76-82`).
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LoginPayload {
    /// The show-once account session token. [`Token`]-typed for the reason given on
    /// [`ActivationResponse::activation_token`].
    pub session_token: Token,
    #[serde(default)]
    pub expires_at: String,
    #[serde(default)]
    pub role: String,
    #[serde(default)]
    pub org_id: String,
}

/// `data` for the `activateDeviceWithSession` mutation.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ActivateWithSessionData {
    pub activate_device_with_session: ActivateDevicePayload,
}

/// `ActivateDevicePayload` (`account_schema.py:122-128`).
///
/// Deliberately **narrower** than the REST response: no `reminted`, no token metadata,
/// no licence block. See [`crate::client::LicensingClient::activate_with_session`] for
/// how the two are reconciled without inventing values the server did not send.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ActivateDevicePayload {
    /// The show-once device token; `null` on an idempotent replay. [`Token`]-typed for
    /// the reason given on [`ActivationResponse::activation_token`].
    #[serde(default)]
    pub full_token: Option<Token>,
    pub created: bool,
    #[serde(default)]
    pub device_public_id: String,
    #[serde(default)]
    pub platform: String,
}

// ---------------------------------------------------------------------------
// The signed entitlement envelope (shape only — verification is 86ak5mn1d)
// ---------------------------------------------------------------------------

/// The signing envelope returned by `GET /v1/entitlements/manifest`
/// (`apps/entitlements/signing.py:82-93`).
///
/// **Pinned here, in the foundation, deliberately.** Verification and caching belong to
/// 86ak5mn1d, but the *shape* does not get to be decided later: DEC-011 pt 2 requires the
/// client to select the signing key from a **set** by `key_id` in the first build that
/// verifies an entitlement, because the public key is compiled into every installed copy
/// and the machines that matter are deliberately offline. Landing the envelope with
/// `key_id` on it now means the dependent ticket implements `verify()` against an already
/// rotation-ready contract rather than retrofitting one.
///
/// # The verification rule this type exists to protect (CON-P7)
///
/// The signature covers **the ASCII bytes of the `payload` base64url string exactly as
/// transmitted** — not the decoded payload, and not a re-serialization of it. So a
/// verifier must check `signature` against `payload.as_bytes()` and only then decode.
/// [`Self::signed_bytes`] is the only supported way to obtain those bytes, so the
/// dependent ticket cannot reach for the decoded form by accident. The server's own
/// comment gives the reason: a canonical-JSON scheme would require Python and Rust to
/// agree byte-for-byte on key order, separators, unicode escaping and float formatting,
/// and every one of those is a place a signature silently fails to verify.
///
/// The HTTP body also carries unsigned `surface`/`operation` fields the view adds
/// (`platform/views.py:191-199`); they are ignored here rather than rejected, which is
/// why this type does **not** use `deny_unknown_fields`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntitlementEnvelope {
    pub envelope_version: u32,
    /// Always `"Ed25519"`. Check this against a one-element allow-list **before** touching
    /// key material — dispatching on a caller-supplied algorithm is how confusion attacks
    /// work (`signing.py:99-101`).
    pub alg: String,
    /// Names the signing key: the first 8 lowercase hex chars of SHA-256 over the raw
    /// 32-byte public key. Look it up in [`crate::trust::TrustedKeys`].
    pub key_id: String,
    /// base64url, no padding. The signed bytes are this string's ASCII bytes.
    pub payload: String,
    /// base64url, no padding — a raw 64-byte Ed25519 signature.
    pub signature: String,
}

/// The algorithm this client will ever accept.
pub const ENVELOPE_ALG: &str = "Ed25519";
/// The envelope version this client understands.
pub const ENVELOPE_VERSION: u32 = 1;

impl EntitlementEnvelope {
    /// The exact bytes the signature covers (CON-P7).
    ///
    /// Returning the transmitted base64url string's bytes — never the decoded payload —
    /// is the whole point; see the type-level docs.
    pub fn signed_bytes(&self) -> &[u8] {
        self.payload.as_bytes()
    }

    /// Whether the envelope's algorithm and version are ones this build accepts. Checked
    /// before key selection, per the server's reference verifier.
    pub fn header_is_supported(&self) -> bool {
        self.alg == ENVELOPE_ALG && self.envelope_version == ENVELOPE_VERSION
    }
}
