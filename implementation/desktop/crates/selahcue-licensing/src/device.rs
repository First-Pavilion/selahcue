//! What this install claims to be, and the retry key that makes activation replayable.
//!
//! This module deliberately does **no** OS probing. The fingerprint, platform and version
//! are supplied by the application shell, which keeps this crate pure, deterministic and
//! testable, and keeps the (necessarily platform-specific, necessarily privacy-sensitive)
//! question of *how* a machine is fingerprinted out of the licensing logic.

/// The identity an install presents at activation.
///
/// The server enforces a uniqueness constraint on `(license_key, device_fingerprint)`,
/// which has a consequence worth stating plainly: **rotating the idempotency key does not
/// buy a second device slot.** Re-running activation for the same fingerprint under the
/// same licence is a replay, not a new instance — which is exactly what makes
/// re-activating a machine the ordinary flow (FR-513) rather than a special case.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeviceIdentity {
    /// Stable per-install hardware/install fingerprint. Server: non-empty after trimming,
    /// max 128 chars.
    pub fingerprint: String,
    /// e.g. `"macos"`, `"windows"`, `"linux"`. Server: non-empty after trimming, max 32.
    pub platform: String,
    /// e.g. `"1.0.0"`. Optional server-side; max 32.
    pub app_version: String,
    /// Operator-visible name, e.g. `"Sound booth Mac"`. Optional server-side; max 128.
    pub display_name: String,
}

/// The server's length limits, mirrored so an over-long value is caught here rather than
/// as an opaque `VALIDATION_FAILED` after a round trip
/// (`apps/devices/models.py:31-34`).
pub const MAX_FINGERPRINT: usize = 128;
/// See [`MAX_FINGERPRINT`].
pub const MAX_PLATFORM: usize = 32;
/// See [`MAX_FINGERPRINT`].
pub const MAX_APP_VERSION: usize = 32;
/// See [`MAX_FINGERPRINT`].
pub const MAX_DISPLAY_NAME: usize = 128;

/// A device identity was not acceptable to send.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdentityError {
    /// A required field was empty after trimming.
    Empty(&'static str),
    /// A field exceeded the server's column width.
    TooLong {
        field: &'static str,
        max: usize,
        actual: usize,
    },
}

impl core::fmt::Display for IdentityError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            IdentityError::Empty(field) => write!(f, "{field} must not be empty"),
            IdentityError::TooLong { field, max, actual } => {
                write!(f, "{field} is {actual} characters; the maximum is {max}")
            }
        }
    }
}

impl std::error::Error for IdentityError {}

impl DeviceIdentity {
    /// Build an identity, trimming as the server does and rejecting what the server would
    /// reject.
    pub fn new(
        fingerprint: impl AsRef<str>,
        platform: impl AsRef<str>,
        app_version: impl AsRef<str>,
        display_name: impl AsRef<str>,
    ) -> Result<Self, IdentityError> {
        let fingerprint = fingerprint.as_ref().trim();
        let platform = platform.as_ref().trim();
        let app_version = app_version.as_ref().trim();
        let display_name = display_name.as_ref().trim();

        check_required("device_fingerprint", fingerprint, MAX_FINGERPRINT)?;
        check_required("platform", platform, MAX_PLATFORM)?;
        check_optional("app_version", app_version, MAX_APP_VERSION)?;
        check_optional("display_name", display_name, MAX_DISPLAY_NAME)?;

        Ok(DeviceIdentity {
            fingerprint: fingerprint.to_string(),
            platform: platform.to_string(),
            app_version: app_version.to_string(),
            display_name: display_name.to_string(),
        })
    }
}

fn check_required(field: &'static str, value: &str, max: usize) -> Result<(), IdentityError> {
    if value.is_empty() {
        return Err(IdentityError::Empty(field));
    }
    check_optional(field, value, max)
}

fn check_optional(field: &'static str, value: &str, max: usize) -> Result<(), IdentityError> {
    let actual = value.chars().count();
    if actual > max {
        return Err(IdentityError::TooLong { field, max, actual });
    }
    Ok(())
}

/// Lower bound on an idempotency key's length (server: `{12,128}`).
pub const IDEMPOTENCY_MIN: usize = 12;
/// Upper bound on an idempotency key's length (server: `{12,128}`).
pub const IDEMPOTENCY_MAX: usize = 128;

/// A retry key the server will accept.
///
/// The server validates against `^[A-Za-z0-9._:-]{12,128}$` after trimming
/// (`graphql/context.py:47,158`). Enforcing the same rule here means a malformed key is a
/// local error instead of a `VALIDATION_FAILED` round trip that also consumes one of the
/// ten activation attempts per minute the endpoint allows.
#[derive(Clone, PartialEq, Eq)]
pub struct IdempotencyKey(String);

impl IdempotencyKey {
    /// Validate and wrap. Trims first, exactly as the server does.
    pub fn new(value: impl AsRef<str>) -> Result<Self, IdempotencyKeyError> {
        let value = value.as_ref().trim();
        let len = value.len();
        if !(IDEMPOTENCY_MIN..=IDEMPOTENCY_MAX).contains(&len) {
            return Err(IdempotencyKeyError::Length(len));
        }
        if let Some(bad) = value.chars().find(|c| !is_allowed_key_char(*c)) {
            return Err(IdempotencyKeyError::Character(bad));
        }
        Ok(IdempotencyKey(value.to_string()))
    }

    /// The wire value.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// The server's character class for an idempotency key: `A-Za-z0-9._:-`.
///
/// Named for what it validates rather than the tempting bare `is_allowed`: this crate
/// deliberately contains nothing that decides whether anything is *permitted to happen*,
/// and a generic name here reads like it does.
fn is_allowed_key_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | ':' | '-')
}

impl core::fmt::Debug for IdempotencyKey {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "IdempotencyKey({})", self.0)
    }
}

/// Why an idempotency key was refused locally.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdempotencyKeyError {
    /// Outside `12..=128` characters.
    Length(usize),
    /// Contained a character outside `A-Za-z0-9._:-`.
    Character(char),
}

impl core::fmt::Display for IdempotencyKeyError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            IdempotencyKeyError::Length(len) => write!(
                f,
                "idempotency key must be {IDEMPOTENCY_MIN}..={IDEMPOTENCY_MAX} characters, got {len}"
            ),
            IdempotencyKeyError::Character(c) => {
                write!(f, "idempotency key contains an unsupported character {c:?}")
            }
        }
    }
}

impl std::error::Error for IdempotencyKeyError {}
