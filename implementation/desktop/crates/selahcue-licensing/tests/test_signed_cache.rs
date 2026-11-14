#![allow(clippy::unwrap_used)]

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use ed25519_dalek::{Signer, SigningKey};
use selahcue_licensing::{
    verify_entitlement, Allowance, CacheDecision, EntitlementCache, EntitlementCacheError,
    EntitlementEnvelope, EntitlementVerificationError as VerifyError, KeepReason, TrustedKeys,
    MAX_ENTITLEMENT_ENVELOPE_BYTES,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::fs;
use tempfile::tempdir;

const DEVICE: &str = "dev_0123456789abcdef0123456789abcdef";
const FINGERPRINT: &str = "test-fixture-fingerprint";
const FIRST_ISSUANCE: &str = "2026-11-14T16:00:00+00:00";
const NEXT_ISSUANCE: &str = "2026-11-15T16:00:00+00:00";

fn key(marker: u8) -> SigningKey {
    SigningKey::from_bytes(&[marker; 32])
}

fn public_key(key: &SigningKey) -> [u8; 32] {
    key.verifying_key().to_bytes()
}

fn trust(key: &SigningKey) -> (TrustedKeys, String) {
    let mut keys = TrustedKeys::new();
    let key_id = keys.insert(public_key(key)).unwrap();
    (keys, key_id)
}

fn facts(issued_at: &str) -> Value {
    json!({
        "entitlement_version": 1,
        "device_public_id": DEVICE,
        "device_fingerprint": FINGERPRINT,
        "issued_at": issued_at,
        "not_before": "2026-11-01T00:00:00+00:00",
        "expires_at": "2027-11-01T00:00:00+00:00",
        "license_expires_at": "2027-11-01T00:00:00+00:00",
        "grants": {"transcription": true}
    })
}

fn sign_encoded(key: &SigningKey, key_id: &str, payload: String) -> EntitlementEnvelope {
    let signature = key.sign(payload.as_bytes());
    EntitlementEnvelope {
        envelope_version: 1,
        alg: "Ed25519".into(),
        key_id: key_id.into(),
        payload,
        signature: URL_SAFE_NO_PAD.encode(signature.to_bytes()),
    }
}

fn sign(key: &SigningKey, key_id: &str, payload: &Value) -> EntitlementEnvelope {
    sign_encoded(
        key,
        key_id,
        URL_SAFE_NO_PAD.encode(serde_json::to_vec(payload).unwrap()),
    )
}

fn wire(envelope: &EntitlementEnvelope) -> Vec<u8> {
    serde_json::to_vec(envelope).unwrap()
}

#[test]
fn verifies_actual_api_signer_fixture_with_python_escaped_unicode() {
    #[derive(Deserialize)]
    struct Fixture {
        test_public_key: [u8; 32],
        wire: Value,
    }
    let fixture: Fixture =
        serde_json::from_str(include_str!("fixtures/api-entitlement-v1.json")).unwrap();
    let mut keys = TrustedKeys::new();
    keys.insert(fixture.test_public_key).unwrap();
    let body = serde_json::to_vec(&fixture.wire).unwrap();

    let verified = verify_entitlement(&body, &keys, DEVICE, FINGERPRINT).unwrap();
    assert_eq!(verified.device_public_id(), DEVICE);
    assert_eq!(verified.device_fingerprint(), FINGERPRINT);
    assert_eq!(verified.facts().issued_at_unix(), 1_794_672_000);
    assert_eq!(verified.not_before_unix(), 1_793_491_200);
    assert_eq!(
        verified.grants().allowance("remote_devices"),
        Allowance::Unlimited
    );
    assert_eq!(verified.grants().allowance("storage"), Allowance::Count(3));
}

#[test]
fn verifies_both_rotation_keys_and_a_third_added_to_the_same_set() {
    let first = key(11);
    let second = key(22);
    let third = key(33);
    let (mut keys, first_id) = trust(&first);
    let second_id = keys.insert(public_key(&second)).unwrap();
    let payload = facts(FIRST_ISSUANCE);
    let first_wire = wire(&sign(&first, &first_id, &payload));
    let second_wire = wire(&sign(&second, &second_id, &payload));

    for body in [&first_wire, &second_wire] {
        assert!(verify_entitlement(body, &keys, DEVICE, FINGERPRINT).is_ok());
    }

    let third_id = keys.insert(public_key(&third)).unwrap();
    let third_wire = wire(&sign(&third, &third_id, &payload));
    for body in [&first_wire, &second_wire, &third_wire] {
        assert!(verify_entitlement(body, &keys, DEVICE, FINGERPRINT).is_ok());
    }

    let wrong_id = wire(&sign(&second, &first_id, &payload));
    assert_eq!(
        verify_entitlement(&wrong_id, &keys, DEVICE, FINGERPRINT).unwrap_err(),
        VerifyError::BadSignature
    );
}

#[test]
fn rejects_tampering_over_the_transmitted_string_before_parsing_the_payload() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let mut envelope = sign(&key, &key_id, &facts(FIRST_ISSUANCE));

    envelope.payload.insert(0, '!');
    assert_eq!(
        verify_entitlement(&wire(&envelope), &keys, DEVICE, FINGERPRINT).unwrap_err(),
        VerifyError::BadSignature
    );

    let envelope = sign_encoded(&key, &key_id, "!!!".into());
    assert_eq!(
        verify_entitlement(&wire(&envelope), &keys, DEVICE, FINGERPRINT).unwrap_err(),
        VerifyError::MalformedPayload
    );
}

#[test]
fn rejects_untrusted_headers_and_malformed_signatures() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let envelope = sign(&key, &key_id, &facts(FIRST_ISSUANCE));
    for (field, new_value, expected) in [
        ("alg", json!("ed25519"), VerifyError::UnsupportedEnvelope),
        (
            "envelope_version",
            json!(2),
            VerifyError::UnsupportedEnvelope,
        ),
        ("key_id", json!("deadbeef"), VerifyError::UnknownKey),
        ("signature", json!("="), VerifyError::BadSignature),
    ] {
        let mut candidate = serde_json::to_value(&envelope).unwrap();
        candidate[field] = new_value;
        let body = serde_json::to_vec(&candidate).unwrap();
        assert_eq!(
            verify_entitlement(&body, &keys, DEVICE, FINGERPRINT).unwrap_err(),
            expected
        );
    }
    let mut missing = serde_json::to_value(&envelope).unwrap();
    missing.as_object_mut().unwrap().remove("key_id");
    assert_eq!(
        verify_entitlement(
            &serde_json::to_vec(&missing).unwrap(),
            &keys,
            DEVICE,
            FINGERPRINT
        )
        .unwrap_err(),
        VerifyError::MalformedEnvelope
    );
}

#[test]
fn rejects_unsupported_payload_version_and_binds_both_identity_fields() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let mut payload = facts(FIRST_ISSUANCE);
    let body = wire(&sign(&key, &key_id, &payload));
    for (id, fingerprint) in [(DEVICE, "other-install"), ("dev_other", FINGERPRINT)] {
        assert_eq!(
            verify_entitlement(&body, &keys, id, fingerprint).unwrap_err(),
            VerifyError::WrongDevice
        );
    }

    payload["entitlement_version"] = json!(2);
    let body = wire(&sign(&key, &key_id, &payload));
    assert_eq!(
        verify_entitlement(&body, &keys, DEVICE, FINGERPRINT).unwrap_err(),
        VerifyError::UnsupportedPayload
    );
}

#[test]
fn bounds_wire_bytes_before_decode() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let mut body = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    body.resize(MAX_ENTITLEMENT_ENVELOPE_BYTES, b' ');
    assert!(verify_entitlement(&body, &keys, DEVICE, FINGERPRINT).is_ok());
    body.push(b' ');
    assert_eq!(
        verify_entitlement(&body, &keys, DEVICE, FINGERPRINT).unwrap_err(),
        VerifyError::Oversized
    );
}

#[test]
fn reopens_a_valid_envelope_and_filters_unsigned_transport_fields_from_disk() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let mut response = serde_json::to_value(sign(&key, &key_id, &facts(FIRST_ISSUANCE))).unwrap();
    response["activation_token"] = json!("test-token-never-cache");

    let cache = EntitlementCache::new(dir.path());
    assert!(cache.load(&keys, DEVICE, FINGERPRINT).unwrap().is_none());
    assert_eq!(
        cache
            .replace(
                &serde_json::to_vec(&response).unwrap(),
                &keys,
                DEVICE,
                FINGERPRINT
            )
            .unwrap(),
        CacheDecision::Replace
    );
    let stored = fs::read_to_string(cache.path()).unwrap();
    assert!(!stored.contains("test-token-never-cache"));
    assert!(!stored.contains("activation_token"));

    let reopened = EntitlementCache::new(dir.path());
    let verified = reopened.load(&keys, DEVICE, FINGERPRINT).unwrap().unwrap();
    assert_eq!(
        verified.grants().allowance("transcription"),
        Allowance::Flag(true)
    );
    assert!(matches!(
        reopened.load(&keys, DEVICE, "wrong-fingerprint"),
        Err(EntitlementCacheError::Verification(
            VerifyError::WrongDevice
        ))
    ));
    assert!(matches!(
        reopened.load(&TrustedKeys::new(), DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::Verification(VerifyError::UnknownKey))
    ));
}

#[test]
fn preserves_verifiable_cache_after_bad_signature_and_replacement_policy_refusals() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    let original = wire(&sign(&key, &key_id, &facts(NEXT_ISSUANCE)));
    cache
        .replace(&original, &keys, DEVICE, FINGERPRINT)
        .unwrap();
    let before = fs::read(cache.path()).unwrap();

    let stale = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    assert!(matches!(
        cache.replace(&stale, &keys, DEVICE, FINGERPRINT).unwrap(),
        CacheDecision::KeepCached(KeepReason::StaleIssuance { .. })
    ));
    let mut degraded = facts(NEXT_ISSUANCE);
    degraded["expires_at"] = json!("2026-11-15T16:15:00+00:00");
    degraded["grants"] = json!({});
    assert!(matches!(
        cache
            .replace(
                &wire(&sign(&key, &key_id, &degraded)),
                &keys,
                DEVICE,
                FINGERPRINT
            )
            .unwrap(),
        CacheDecision::KeepCached(KeepReason::DegradedWouldDropGrants { .. })
    ));

    let mut bad = sign(&key, &key_id, &facts(NEXT_ISSUANCE));
    bad.signature = URL_SAFE_NO_PAD.encode([0_u8; 64]);
    assert!(matches!(
        cache.replace(&wire(&bad), &keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::Verification(
            VerifyError::BadSignature
        ))
    ));
    let reopened = EntitlementCache::new(dir.path());
    assert!(reopened.load(&keys, DEVICE, FINGERPRINT).unwrap().is_some());
    assert_eq!(fs::read(reopened.path()).unwrap(), before);
}

#[test]
fn rejects_truncated_and_oversized_files_then_recovers_with_a_verified_candidate() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    fs::write(cache.path(), b"{").unwrap();
    assert!(matches!(
        cache.load(&keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::Verification(
            VerifyError::MalformedEnvelope
        ))
    ));
    fs::write(cache.path(), vec![b' '; MAX_ENTITLEMENT_ENVELOPE_BYTES + 1]).unwrap();
    assert!(matches!(
        cache.load(&keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::Verification(VerifyError::Oversized))
    ));
    let body = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    cache.replace(&body, &keys, DEVICE, FINGERPRINT).unwrap();
    assert!(EntitlementCache::new(dir.path())
        .load(&keys, DEVICE, FINGERPRINT)
        .unwrap()
        .is_some());
}

#[test]
fn refuses_non_regular_destination() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    fs::create_dir(cache.path()).unwrap();
    assert!(matches!(
        cache.load(&keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::UnsafeFile)
    ));
    let body = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    assert!(matches!(
        cache.replace(&body, &keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::UnsafeFile)
    ));
    assert!(cache.path().is_dir());
}

#[cfg(unix)]
#[test]
fn refuses_a_symlink_to_a_valid_cache_file() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let other = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    let external = other.path().join("external");
    let body = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    fs::write(&external, &body).unwrap();
    std::os::unix::fs::symlink(&external, cache.path()).unwrap();
    assert!(matches!(
        cache.load(&keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::UnsafeFile)
    ));
    assert!(matches!(
        cache.replace(&body, &keys, DEVICE, FINGERPRINT),
        Err(EntitlementCacheError::UnsafeFile)
    ));
    assert_eq!(fs::read(external).unwrap(), body);
    assert!(cache.path().is_symlink());
}

#[cfg(unix)]
#[test]
fn failed_filesystem_replacement_preserves_previous_cache() {
    use std::os::unix::fs::PermissionsExt;
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    cache
        .replace(
            &wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE))),
            &keys,
            DEVICE,
            FINGERPRINT,
        )
        .unwrap();
    let original = fs::read(cache.path()).unwrap();

    let before = fs::metadata(dir.path()).unwrap().permissions();
    let mut read_only = before.clone();
    read_only.set_mode(0o500);
    fs::set_permissions(dir.path(), read_only).unwrap();
    let result = cache.replace(
        &wire(&sign(&key, &key_id, &facts(NEXT_ISSUANCE))),
        &keys,
        DEVICE,
        FINGERPRINT,
    );
    fs::set_permissions(dir.path(), before).unwrap();

    assert!(matches!(result, Err(EntitlementCacheError::Io(_))));
    let reopened = EntitlementCache::new(dir.path());
    assert!(reopened.load(&keys, DEVICE, FINGERPRINT).unwrap().is_some());
    assert_eq!(fs::read(reopened.path()).unwrap(), original);
}

#[test]
fn refuses_an_earlier_api_issuance_within_the_same_second() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    let newer = sign(&key, &key_id, &facts("2026-11-14T16:00:00.900000+00:00"));
    let older = sign(&key, &key_id, &facts("2026-11-14T16:00:00.800000+00:00"));
    cache
        .replace(&wire(&newer), &keys, DEVICE, FINGERPRINT)
        .unwrap();
    assert!(matches!(
        cache
            .replace(&wire(&older), &keys, DEVICE, FINGERPRINT)
            .unwrap(),
        CacheDecision::KeepCached(KeepReason::StaleIssuance { .. })
    ));
    assert_eq!(fs::read(cache.path()).unwrap(), wire(&newer));
}

#[test]
fn interrupted_staging_keeps_old_cache_and_reuses_the_single_staging_name() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let dir = tempdir().unwrap();
    let cache = EntitlementCache::new(dir.path());
    let original = wire(&sign(&key, &key_id, &facts(FIRST_ISSUANCE)));
    cache
        .replace(&original, &keys, DEVICE, FINGERPRINT)
        .unwrap();
    let staging = dir.path().join("entitlement-cache.stage");
    fs::write(&staging, b"{").unwrap();

    let reopened = EntitlementCache::new(dir.path());
    assert!(reopened.load(&keys, DEVICE, FINGERPRINT).unwrap().is_some());
    assert_eq!(fs::read(reopened.path()).unwrap(), original);
    let next = wire(&sign(&key, &key_id, &facts(NEXT_ISSUANCE)));
    reopened.replace(&next, &keys, DEVICE, FINGERPRINT).unwrap();
    assert_eq!(fs::read(cache.path()).unwrap(), next);
    assert!(!staging.exists());
}

#[test]
fn exposes_exact_signed_validity_boundaries_after_reopen() {
    let key = key(11);
    let (keys, key_id) = trust(&key);
    let mut payload = facts("2026-11-14T16:00:00.123456+00:00");
    payload["not_before"] = json!("2026-11-14T16:00:00.123455+00:00");
    payload["expires_at"] = json!("2026-11-14T16:00:00.987654+00:00");
    payload["license_expires_at"] = json!("2026-11-14T16:00:00.987655+00:00");
    let body = wire(&sign(&key, &key_id, &payload));

    let dir = tempdir().unwrap();
    EntitlementCache::new(dir.path())
        .replace(&body, &keys, DEVICE, FINGERPRINT)
        .unwrap();
    let verified = EntitlementCache::new(dir.path())
        .load(&keys, DEVICE, FINGERPRINT)
        .unwrap()
        .unwrap();

    let seconds = 1_794_672_000;
    assert_eq!(verified.not_before(), (seconds, 123_455_000));
    assert_eq!(verified.facts().issued_at(), (seconds, 123_456_000));
    assert_eq!(verified.facts().expires_at(), (seconds, 987_654_000));
    assert_eq!(
        verified.facts().license_expires_at(),
        (seconds, 987_655_000)
    );
    assert!(verified.facts().is_degraded());
}
