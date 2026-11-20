use crate::contract::EntitlementEnvelope;
use crate::trust::KEY_ID_HEX_CHARS;
use crate::{Grants, SignedFacts, TrustedKeys};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::DateTime;
use ed25519_dalek::{Signature, VerifyingKey};
use serde::Deserialize;
use std::fmt;

/// Maximum input and on-disk envelope size, matching the licensing response limit.
/// Transport callers must separately bound their read before passing a response here.
pub const MAX_ENTITLEMENT_ENVELOPE_BYTES: usize = crate::client::MAX_RESPONSE_BODY_BYTES;

const ENTITLEMENT_VERSION: u32 = 1;
// Plan.display_name in the signing API is capped at 128 Unicode characters.
const MAX_PLAN_DISPLAY_CHARS: usize = 128;
const SIGNATURE_BYTES: usize = 64;
const SIGNATURE_ENCODED_BYTES: usize = (SIGNATURE_BYTES * 4).div_ceil(3);

/// Display metadata carried inside a verified payload. Feature decisions use grants.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EntitlementDisplay {
    pub plan_display_label: Option<String>,
    pub instances_used: Option<u32>,
    pub instances_limit: Option<u32>,
    /// RFC 3339 end of the plan allowance (exclusive), exactly as signed. `None` when the
    /// field is absent (older entitlements) or null. Only the WebView formats it.
    pub plan_ends_at: Option<String>,
}

/// A signature-verified version 1 manifest bound to the expected device and fingerprint.
/// Verification establishes provenance and shape. Consumers evaluate signed times separately.
#[derive(Clone, PartialEq, Eq)]
pub struct VerifiedEntitlement {
    device_public_id: String,
    device_fingerprint: String,
    not_before: (i64, u32),
    facts: SignedFacts,
    grants: Grants,
    display: EntitlementDisplay,
}

impl fmt::Debug for VerifiedEntitlement {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("VerifiedEntitlement")
            .finish_non_exhaustive()
    }
}

impl VerifiedEntitlement {
    pub fn device_public_id(&self) -> &str {
        &self.device_public_id
    }

    pub fn device_fingerprint(&self) -> &str {
        &self.device_fingerprint
    }

    /// Signed lower validity bound as (Unix seconds, nanoseconds within the second).
    pub fn not_before(&self) -> (i64, u32) {
        self.not_before
    }

    /// Whole Unix seconds for display. Use [`Self::not_before`] for time comparisons.
    pub fn not_before_unix(&self) -> i64 {
        self.not_before().0
    }

    pub fn facts(&self) -> SignedFacts {
        self.facts
    }

    pub fn grants(&self) -> &Grants {
        &self.grants
    }

    pub fn display(&self) -> &EntitlementDisplay {
        &self.display
    }
}

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum EntitlementVerificationError {
    Oversized,
    MalformedEnvelope,
    UnsupportedEnvelope,
    UnknownKey,
    BadSignature,
    MalformedPayload,
    UnsupportedPayload,
    WrongDevice,
}

impl fmt::Display for EntitlementVerificationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        use EntitlementVerificationError::*;
        f.write_str(match self {
            Oversized => "entitlement envelope exceeds the byte limit",
            MalformedEnvelope => "malformed entitlement envelope",
            UnsupportedEnvelope => "unsupported entitlement envelope algorithm or version",
            UnknownKey => "unknown entitlement signing key",
            BadSignature => "invalid entitlement signature",
            MalformedPayload => "malformed entitlement payload",
            UnsupportedPayload => "unsupported entitlement payload version",
            WrongDevice => "entitlement is bound to a different device",
        })
    }
}

impl std::error::Error for EntitlementVerificationError {}

#[derive(Deserialize)]
struct Payload {
    entitlement_version: u32,
    device_public_id: String,
    device_fingerprint: String,
    not_before: String,
    expires_at: String,
    license_expires_at: String,
    issued_at: String,
    degraded: Option<bool>,
    // Added compatibly to v1. Old v1 issuers sent no grants.
    #[serde(default)]
    grants: Grants,
    plan_display_label: Option<String>,
    instances_used: Option<u32>,
    instances_limit: Option<u32>,
    // Absent in entitlements issued before beta licensing. Read leniently: a display-only
    // field must never invalidate a signed licence, so any bad value is treated as absent.
    #[serde(default)]
    plan_ends_at: Option<serde_json::Value>,
}

/// Verify the API's transmitted base64url string before decoding the signed payload.
/// Only the named, trusted Ed25519 key can authenticate the envelope.
pub fn verify_entitlement(
    body: &[u8],
    keys: &TrustedKeys,
    device_public_id: &str,
    device_fingerprint: &str,
) -> Result<VerifiedEntitlement, EntitlementVerificationError> {
    verify_with_envelope(body, keys, device_public_id, device_fingerprint)
        .map(|(_, verified)| verified)
}

pub(crate) fn verify_with_envelope(
    body: &[u8],
    keys: &TrustedKeys,
    device_public_id: &str,
    device_fingerprint: &str,
) -> Result<(EntitlementEnvelope, VerifiedEntitlement), EntitlementVerificationError> {
    use EntitlementVerificationError::*;
    if body.len() > MAX_ENTITLEMENT_ENVELOPE_BYTES {
        return Err(Oversized);
    }
    let envelope: EntitlementEnvelope =
        serde_json::from_slice(body).map_err(|_| MalformedEnvelope)?;
    if !envelope.header_is_supported() {
        return Err(UnsupportedEnvelope);
    }
    if envelope.key_id.len() != KEY_ID_HEX_CHARS {
        return Err(UnknownKey);
    }
    let key = keys.get(&envelope.key_id).ok_or(UnknownKey)?;
    let key = VerifyingKey::from_bytes(key.public_key()).map_err(|_| BadSignature)?;
    if envelope.signature.len() != SIGNATURE_ENCODED_BYTES {
        return Err(BadSignature);
    }
    let mut sig = [0; SIGNATURE_BYTES];
    URL_SAFE_NO_PAD
        .decode_slice(&envelope.signature, &mut sig)
        .map_err(|_| BadSignature)?;
    key.verify_strict(envelope.signed_bytes(), &Signature::from_bytes(&sig))
        .map_err(|_| BadSignature)?;

    let decoded = URL_SAFE_NO_PAD
        .decode(&envelope.payload)
        .map_err(|_| MalformedPayload)?;
    let payload: Payload = serde_json::from_slice(&decoded).map_err(|_| MalformedPayload)?;
    if payload.entitlement_version != ENTITLEMENT_VERSION {
        return Err(UnsupportedPayload);
    }
    if payload.device_public_id != device_public_id
        || payload.device_fingerprint != device_fingerprint
        || payload.device_public_id.is_empty()
        || payload.device_fingerprint.is_empty()
    {
        return Err(WrongDevice);
    }

    if payload
        .plan_display_label
        .as_ref()
        .is_some_and(|label| label.chars().count() > MAX_PLAN_DISPLAY_CHARS)
    {
        return Err(MalformedPayload);
    }

    let timestamp = |date: &str| {
        DateTime::parse_from_rfc3339(date)
            .map(|value| (value.timestamp(), value.timestamp_subsec_nanos()))
            .map_err(|_| MalformedPayload)
    };
    let plan_ends_at = payload
        .plan_ends_at
        .and_then(|value| value.as_str().map(str::to_owned))
        .filter(|ends| DateTime::parse_from_rfc3339(ends).is_ok());
    let facts = SignedFacts::with_precision(
        timestamp(&payload.expires_at)?,
        timestamp(&payload.license_expires_at)?,
        timestamp(&payload.issued_at)?,
        payload.degraded,
        payload.grants.len(),
    );
    let verified = VerifiedEntitlement {
        device_public_id: payload.device_public_id,
        device_fingerprint: payload.device_fingerprint,
        not_before: timestamp(&payload.not_before)?,
        facts,
        grants: payload.grants,
        display: EntitlementDisplay {
            // The issuer permits controls such as embedded tabs in plan names. Keep
            // the verified entitlement while suppressing unsafe display text.
            plan_display_label: payload
                .plan_display_label
                .filter(|label| !label.chars().any(char::is_control)),
            instances_used: payload.instances_used,
            instances_limit: payload.instances_limit,
            plan_ends_at,
        },
    };
    Ok((envelope, verified))
}
