//! Device identity and the idempotency key.
//!
//! Every rule here mirrors one the server enforces. Duplicating validation is usually a
//! smell; here it buys something specific — the activation endpoint allows ten attempts
//! per minute per IP, so a request that was always going to be rejected costs a round trip
//! *and* a tenth of the operator's retry budget. Catching it locally costs neither.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::device::{
    IdempotencyKeyError, IdentityError, IDEMPOTENCY_MAX, IDEMPOTENCY_MIN, MAX_FINGERPRINT,
    MAX_PLATFORM,
};
use selahcue_licensing::{DeviceIdentity, IdempotencyKey};

// Pin the server's bounds at compile time so a local edit cannot drift from them silently.
const _: () = assert!(IDEMPOTENCY_MIN == 12 && IDEMPOTENCY_MAX == 128);
const _: () = assert!(MAX_FINGERPRINT == 128 && MAX_PLATFORM == 32);

#[test]
fn a_well_formed_identity_is_accepted_and_trimmed() {
    let identity = DeviceIdentity::new("  fp-1  ", " macos ", " 1.0.0 ", " Booth Mac ").unwrap();
    assert_eq!(identity.fingerprint, "fp-1");
    assert_eq!(identity.platform, "macos");
    assert_eq!(identity.app_version, "1.0.0");
    assert_eq!(identity.display_name, "Booth Mac");
}

#[test]
fn the_required_fields_are_the_ones_the_server_rejects_when_empty() {
    // `devices/services.py:485-488` rejects an empty fingerprint or platform after
    // stripping; app_version and display_name legitimately default to "".
    assert_eq!(
        DeviceIdentity::new("", "macos", "1.0.0", "Booth").unwrap_err(),
        IdentityError::Empty("device_fingerprint")
    );
    assert_eq!(
        DeviceIdentity::new("   ", "macos", "1.0.0", "Booth").unwrap_err(),
        IdentityError::Empty("device_fingerprint"),
        "whitespace is empty once trimmed, exactly as the server sees it"
    );
    assert_eq!(
        DeviceIdentity::new("fp-1", "", "1.0.0", "Booth").unwrap_err(),
        IdentityError::Empty("platform")
    );

    // The optional pair really is optional.
    let sparse = DeviceIdentity::new("fp-1", "macos", "", "").unwrap();
    assert_eq!(sparse.app_version, "");
    assert_eq!(sparse.display_name, "");
}

#[test]
fn over_long_fields_are_refused_locally_with_the_field_named() {
    let long = "x".repeat(MAX_FINGERPRINT + 1);
    assert_eq!(
        DeviceIdentity::new(&long, "macos", "1.0.0", "Booth").unwrap_err(),
        IdentityError::TooLong {
            field: "device_fingerprint",
            max: MAX_FINGERPRINT,
            actual: MAX_FINGERPRINT + 1,
        }
    );

    // Positive control: exactly at the limit is fine, so the check is a boundary and not a
    // blanket refusal.
    let at_limit = "x".repeat(MAX_FINGERPRINT);
    assert!(DeviceIdentity::new(&at_limit, "macos", "1.0.0", "Booth").is_ok());
}

#[test]
fn an_idempotency_key_matches_the_servers_pattern() {
    // Server: `^[A-Za-z0-9._:-]{12,128}$` (`graphql/context.py:47`).
    assert!(IdempotencyKey::new("idem-0123456789ab").is_ok());
    assert!(IdempotencyKey::new("A.b_c:d-0123456789").is_ok());

    // Boundaries, both sides.
    let min = "a".repeat(IDEMPOTENCY_MIN);
    let max = "a".repeat(IDEMPOTENCY_MAX);
    assert!(
        IdempotencyKey::new(&min).is_ok(),
        "the minimum is inclusive"
    );
    assert!(
        IdempotencyKey::new(&max).is_ok(),
        "the maximum is inclusive"
    );

    assert_eq!(
        IdempotencyKey::new("a".repeat(IDEMPOTENCY_MIN - 1)).unwrap_err(),
        IdempotencyKeyError::Length(IDEMPOTENCY_MIN - 1)
    );
    assert_eq!(
        IdempotencyKey::new("a".repeat(IDEMPOTENCY_MAX + 1)).unwrap_err(),
        IdempotencyKeyError::Length(IDEMPOTENCY_MAX + 1)
    );
}

#[test]
fn characters_outside_the_servers_class_are_refused() {
    for (value, bad) in [
        ("idem 0123456789ab", ' '),
        ("idem/0123456789ab", '/'),
        ("idem+0123456789ab", '+'),
        ("idém0123456789ab", 'é'),
    ] {
        assert_eq!(
            IdempotencyKey::new(value).unwrap_err(),
            IdempotencyKeyError::Character(bad),
            "{value:?} should be refused for {bad:?}"
        );
    }
}

#[test]
fn an_idempotency_key_is_trimmed_before_validation_like_the_server_does() {
    // `context.py:158` strips before matching, so a padded value that fits after trimming
    // is legitimate — and one that only reaches the minimum *because* of its padding is not.
    let key = IdempotencyKey::new("  idem-0123456789ab  ").unwrap();
    assert_eq!(key.as_str(), "idem-0123456789ab");

    assert!(
        IdempotencyKey::new("    short     ").is_err(),
        "padding must not be counted toward the minimum length"
    );
}

#[test]
fn the_idempotency_key_is_not_a_secret_and_says_so() {
    // Unlike a token, this is deliberately visible in diagnostics: it is the client's own
    // correlation id, and the server records it as the audit `request_id`, so being able
    // to read it out of a log is the point.
    let key = IdempotencyKey::new("idem-0123456789ab").unwrap();
    assert!(format!("{key:?}").contains("idem-0123456789ab"));
}
