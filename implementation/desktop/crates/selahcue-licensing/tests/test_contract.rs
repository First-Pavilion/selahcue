//! The wire contract, pinned to the shipped server.
//!
//! These fixtures are the desktop half of a cross-language contract, in the same spirit as
//! the LAN protocol's byte-pinned JSON. The server is Python and this is Rust; nothing but
//! a test holds the two field-name sets together, and the failure mode when they drift is
//! silent — a `#[serde(default)]` quietly yielding an empty string where a device id was
//! expected.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::contract::{
    ActivationRequest, ActivationResponse, ApiErrorEnvelope, EntitlementEnvelope, ErrorCode,
    SessionActivationRequest, SessionRequest, SessionResponse, ACTIVATIONS_PATH,
    ACTIVATIONS_WITH_SESSION_PATH, ENTITLEMENT_MANIFEST_PATH, ENVELOPE_ALG, ENVELOPE_VERSION,
    MAX_CODE_LEN, SESSIONS_PATH, UNRECOGNISED_CODE,
};
use selahcue_licensing::Token;

#[test]
fn the_endpoint_paths_match_the_servers_routes() {
    // `platform/urls.py:7-9`. The missing trailing slash on `activations` is load-bearing:
    // Django's route is registered without one, so adding it is a 404 rather than a
    // redirect.
    assert_eq!(ACTIVATIONS_PATH, "/v1/activations");
    assert!(!ACTIVATIONS_PATH.ends_with('/'));
    assert_eq!(ENTITLEMENT_MANIFEST_PATH, "/v1/entitlements/manifest");

    // The native sign-in pair (`platform/urls.py`, 86ak5t1gw). Spelled out in full: the
    // colon in `activations:with-session` is part of the route, and `sessions` has no
    // trailing slash for the same reason `activations` has none.
    assert_eq!(SESSIONS_PATH, "/v1/sessions");
    assert_eq!(
        ACTIVATIONS_WITH_SESSION_PATH,
        "/v1/activations:with-session"
    );
    assert!(!SESSIONS_PATH.ends_with('/'));
    assert!(!ACTIVATIONS_WITH_SESSION_PATH.ends_with('/'));
    for path in [
        SESSIONS_PATH,
        ACTIVATIONS_WITH_SESSION_PATH,
        ACTIVATIONS_PATH,
    ] {
        assert!(
            path.starts_with("/v1/"),
            "{path}: the native client lives on the cookie-free /v1 surface, never on the \
             browser's /graphql/account (86ak5t1gw)"
        );
    }
}

#[test]
fn the_activation_request_serializes_to_the_field_names_the_server_reads() {
    // `platform/views.py:65-72` reads exactly these six keys. In particular the presented
    // enrollment key is `license_key` — a client sending `enrollment_key` would have it
    // coerced to "" and get a NOT_FOUND that looks like a bad key.
    let request = ActivationRequest {
        idempotency_key: "idem-0123456789ab".into(),
        license_key: "SC-TRIAL-KEY".into(),
        device_fingerprint: "fp-1".into(),
        platform: "macos".into(),
        app_version: "1.0.0".into(),
        display_name: "Booth".into(),
    };
    let json = serde_json::to_value(&request).unwrap();
    let object = json.as_object().unwrap();

    let expected = [
        "idempotency_key",
        "license_key",
        "device_fingerprint",
        "platform",
        "app_version",
        "display_name",
    ];
    for key in expected {
        assert!(object.contains_key(key), "missing wire field {key}: {json}");
    }
    assert_eq!(
        object.len(),
        expected.len(),
        "the request grew a field the server does not read: {json}"
    );
    assert!(
        !object.contains_key("enrollment_key"),
        "the key is sent as `license_key`; `enrollment_key` is not a field the server reads"
    );
}

#[test]
fn a_real_activation_success_body_parses() {
    // Shaped from `platform/views.py:83-110`, including the Python `isoformat()` stamps
    // with microseconds and a `+00:00` offset rather than a `Z`.
    let body = r#"{
      "created": true,
      "reminted": false,
      "activation_token": "SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8",
      "device": {"device_public_id": "dev_0123456789abcdef0123456789abcdef",
                 "status": "ACTIVE", "platform": "macos"},
      "token": {"masked": "SC-DEV-A1B2...Q7R8", "prefix": "SC-DEV-A1B2", "suffix": "Q7R8",
                "fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "expires_at": "2026-09-24T10:11:12.123456+00:00"},
      "license": {"status": "ACTIVATED", "expires_at": "2026-12-31T23:59:59.999999+00:00"},
      "surface": "desktop",
      "operation": "activation"
    }"#;

    let parsed: ActivationResponse = serde_json::from_str(body).unwrap();
    assert!(parsed.created);
    assert!(!parsed.reminted);
    assert_eq!(
        parsed.activation_token.as_ref().map(Token::expose),
        Some("SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8")
    );
    assert_eq!(
        parsed.device.device_public_id,
        "dev_0123456789abcdef0123456789abcdef"
    );
    assert_eq!(parsed.device.status, "ACTIVE");
    assert_eq!(
        parsed.token.expires_at.as_deref(),
        Some("2026-09-24T10:11:12.123456+00:00"),
        "the timestamp keeps its +00:00 offset; a hand-rolled Z parser would break here"
    );
    assert_eq!(parsed.license.status, "ACTIVATED");
}

#[test]
fn a_show_once_replay_parses_with_a_null_token_and_live_metadata() {
    // The replay case: `activation_token` is null, but `token.*` still describes the
    // still-live token. A client treating null as an error would turn a success into a
    // failure on every re-run of setup.
    let body = r#"{
      "created": false, "reminted": false, "activation_token": null,
      "device": {"device_public_id": "dev_1", "status": "ACTIVE", "platform": "macos"},
      "token": {"masked": "SC-DEV-A1B2...Q7R8", "prefix": "SC-DEV-A1B2", "suffix": "Q7R8",
                "fingerprint": "f", "expires_at": "2026-09-24T10:11:12.123456+00:00"},
      "license": {"status": "ACTIVATED", "expires_at": "2026-12-31T23:59:59.999999+00:00"},
      "surface": "desktop", "operation": "activation"
    }"#;

    let parsed: ActivationResponse = serde_json::from_str(body).unwrap();
    assert!(parsed.activation_token.is_none());
    assert!(
        parsed.token.expires_at.is_some(),
        "metadata about the live token is present even when the secret is not re-shown"
    );
}

#[test]
fn the_coded_error_envelope_parses_and_every_code_round_trips() {
    let body = r#"{"error": {"code": "POLICY_DENIED",
      "message": "The current policy does not allow this action."},
      "surface": "desktop", "operation": "activation"}"#;
    let parsed: ApiErrorEnvelope = serde_json::from_str(body).unwrap();
    assert_eq!(
        ErrorCode::parse(&parsed.error.code),
        ErrorCode::PolicyDenied
    );

    // The full vocabulary from `graphql/errors.py:6-17`.
    for code in [
        "UNAUTHENTICATED",
        "PERMISSION_DENIED",
        "VALIDATION_FAILED",
        "NOT_FOUND",
        "CONFLICT",
        "POLICY_DENIED",
        "RATE_LIMITED",
        "NOT_IMPLEMENTED",
        "INTERNAL",
    ] {
        let parsed = ErrorCode::parse(code);
        assert_eq!(parsed.as_str(), code, "{code} did not round-trip");
        assert!(
            !matches!(parsed, ErrorCode::Unknown(_)),
            "{code} is a known code and must not fall through to Unknown"
        );
    }

    // Forward compatibility: a newer server's code must survive, not fail to parse.
    match ErrorCode::parse("SOMETHING_NEW") {
        ErrorCode::Unknown(value) => assert_eq!(value, "SOMETHING_NEW"),
        other => panic!("expected Unknown, got {other:?}"),
    }
}

#[test]
fn the_sign_in_request_serializes_to_exactly_email_and_password() {
    // `platform/views.py::create_session` reads exactly these two keys and refuses any
    // other shape. A third field here would be a field the server silently ignores.
    let json = serde_json::to_value(SessionRequest {
        email: "admin@example.test".into(),
        password: "pw".into(),
    })
    .unwrap();
    let object = json.as_object().unwrap();
    assert_eq!(object.len(), 2, "unexpected sign-in field: {json}");
    assert_eq!(object["email"], "admin@example.test");
    assert_eq!(object["password"], "pw");
}

#[test]
fn the_session_activation_request_is_the_activation_request_without_the_key() {
    // ADR-0029: "the `POST /v1/activations` body minus `license_key`", snake_case. Derived
    // from `ActivationRequest` here so the claim is checked, not restated: if the key-path
    // body gains a field, this fails until the session path is decided deliberately.
    let with_key = serde_json::to_value(ActivationRequest {
        idempotency_key: "idem-0123456789ab".into(),
        license_key: "SC-TRIAL-KEY".into(),
        device_fingerprint: "fp-1".into(),
        platform: "macos".into(),
        app_version: "1.0.0".into(),
        display_name: "Booth".into(),
    })
    .unwrap();
    let without_key = serde_json::to_value(SessionActivationRequest {
        idempotency_key: "idem-0123456789ab".into(),
        device_fingerprint: "fp-1".into(),
        platform: "macos".into(),
        app_version: "1.0.0".into(),
        display_name: "Booth".into(),
    })
    .unwrap();

    let mut expected = with_key.as_object().unwrap().clone();
    expected.remove("license_key");
    assert_eq!(without_key.as_object().unwrap(), &expected);
    assert!(
        !without_key.to_string().contains("idempotencyKey"),
        "snake_case on the wire; camelCase was the GraphQL spelling"
    );
}

#[test]
fn a_real_sign_in_success_body_parses() {
    // Shaped from `platform/views.py::create_session`: the four fields plus the unsigned
    // `surface` / `operation` labels the view appends, which must be ignored, not rejected.
    let body = r#"{"session_token": "sess-abc",
      "expires_at": "2026-11-23T10:11:12.123456+00:00", "role": "ADMIN", "org_id": "org_1",
      "surface": "desktop", "operation": "session_login"}"#;
    let parsed: SessionResponse = serde_json::from_str(body).unwrap();
    assert_eq!(parsed.session_token.expose(), "sess-abc");
    assert_eq!(parsed.expires_at, "2026-11-23T10:11:12.123456+00:00");
    assert_eq!(parsed.role, "ADMIN");
    assert_eq!(parsed.org_id, "org_1");
}

#[test]
fn a_sign_in_body_missing_a_field_is_contract_drift_not_a_blank_default() {
    // The old GraphQL payload defaulted `role` and `org_id` to "". A defaulted org id is a
    // value later code would send as if it were real, so the server's four fields are all
    // required and a short body fails loudly.
    for body in [
        r#"{"expires_at": "x", "role": "ADMIN", "org_id": "o"}"#,
        r#"{"session_token": "s", "role": "ADMIN", "org_id": "o"}"#,
        r#"{"session_token": "s", "expires_at": "x", "org_id": "o"}"#,
        r#"{"session_token": "s", "expires_at": "x", "role": "ADMIN"}"#,
    ] {
        assert!(
            serde_json::from_str::<SessionResponse>(body).is_err(),
            "{body} must not parse"
        );
    }
}

#[test]
fn the_session_activation_answer_is_the_activation_shape() {
    // `activate_device_with_session` answers with `_activation_payload`, the same function
    // as `POST /v1/activations`, labelled `activation_with_session`.
    let body = r#"{
      "created": true, "reminted": false,
      "activation_token": "SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8",
      "device": {"device_public_id": "dev_0123456789abcdef0123456789abcdef",
                 "status": "ACTIVE", "platform": "macos"},
      "token": {"masked": "SC-DEV-A1B2...Q7R8", "prefix": "SC-DEV-A1B2", "suffix": "Q7R8",
                "fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "expires_at": "2026-09-24T10:11:12.123456+00:00"},
      "license": {"status": "ACTIVATED", "expires_at": "2026-12-31T23:59:59.999999+00:00"},
      "surface": "desktop", "operation": "activation_with_session"
    }"#;
    let parsed: ActivationResponse = serde_json::from_str(body).unwrap();
    assert!(parsed.created);
    assert!(parsed.activation_token.is_some());
    assert_eq!(parsed.license.status, "ACTIVATED");
    assert_eq!(parsed.token.prefix.as_deref(), Some("SC-DEV-A1B2"));
}

#[test]
fn an_error_code_that_is_not_shaped_like_a_code_is_never_carried() {
    // The envelope comes from a body anything in front of the API can write, and an unknown
    // code is later printed. Only a code-shaped string survives; everything else collapses
    // to a fixed marker, so a proxy's JSON page cannot ride a `code` field to a screen.
    let hostile = [
        "<html><body>Access denied by WAF, ray 8a7f</body></html>",
        "lowercase_is_not_a_code",
        "CODE WITH SPACES",
        "",
        "9STARTS_WITH_DIGIT",
        "CODE\nNEWLINE",
    ];
    for value in hostile {
        match ErrorCode::parse(value) {
            ErrorCode::Unknown(kept) => assert_eq!(
                kept, UNRECOGNISED_CODE,
                "{value:?} is not code-shaped and must not be carried"
            ),
            other => panic!("{value:?} parsed as {other:?}"),
        }
    }

    // Length: at the cap is kept, one over is not.
    let at_cap = format!("X{}", "A".repeat(MAX_CODE_LEN - 1));
    assert_eq!(at_cap.len(), MAX_CODE_LEN);
    assert_eq!(
        ErrorCode::parse(&at_cap),
        ErrorCode::Unknown(at_cap.clone()),
        "a code-shaped value at the cap is kept"
    );
    let over = format!("{at_cap}A");
    assert_eq!(
        ErrorCode::parse(&over),
        ErrorCode::Unknown(UNRECOGNISED_CODE.to_string())
    );

    // Positive control: a plausible newer-server code is still reportable.
    assert_eq!(
        ErrorCode::parse("QUOTA_EXCEEDED_V2"),
        ErrorCode::Unknown("QUOTA_EXCEEDED_V2".to_string())
    );
}

// ---------------------------------------------------------------------------
// The signed entitlement envelope (shape only — verification is 86ak5mn1d)
// ---------------------------------------------------------------------------

#[test]
fn the_entitlement_envelope_carries_a_key_id_and_ignores_the_views_extra_fields() {
    // FR-518 / DEC-011 pt 2: `key_id` is top-level in the envelope, a sibling of alg /
    // payload / signature — not inside the signed payload and not a header. The HTTP body
    // also carries unsigned `surface`/`operation` the view appends
    // (`platform/views.py:191-199`); ignoring rather than rejecting them is deliberate.
    let body = r#"{
      "envelope_version": 1,
      "alg": "Ed25519",
      "key_id": "630dcd29",
      "payload": "eyJkZXZpY2VfcHVibGljX2lkIjoiZGV2X2FhYSJ9",
      "signature": "c2lnbmF0dXJlLWJ5dGVz",
      "surface": "desktop",
      "operation": "entitlement_manifest"
    }"#;

    let envelope: EntitlementEnvelope = serde_json::from_str(body).unwrap();
    assert_eq!(envelope.key_id, "630dcd29");
    assert_eq!(envelope.alg, ENVELOPE_ALG);
    assert_eq!(envelope.envelope_version, ENVELOPE_VERSION);
    assert!(envelope.header_is_supported());
}

#[test]
fn the_signed_bytes_are_the_transmitted_base64url_string_not_the_decoded_payload() {
    // CON-P7, and the single easiest thing to get wrong in this contract. The server signs
    // `encoded.encode("ascii")` — the base64url string itself (`signing.py:83-86`). A
    // verifier that decodes first, or re-serializes the decoded JSON, produces a signature
    // check that fails for reasons no one can see.
    //
    // The payload below was produced by Python running the server's own canonicalisation
    // (`json.dumps(sort_keys=True, separators=(",", ":"))` then base64url without padding).
    let payload = "eyJkZXZpY2VfcHVibGljX2lkIjoiZGV2X2FhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhIiwiZW50aXRsZW1lbnRfdmVyc2lvbiI6MSwibGljZW5zZV9zdGF0dXMiOiJBQ1RJVkFURUQifQ";
    let envelope = EntitlementEnvelope {
        envelope_version: 1,
        alg: "Ed25519".into(),
        key_id: "630dcd29".into(),
        payload: payload.into(),
        signature: "sig".into(),
    };

    assert_eq!(
        envelope.signed_bytes(),
        payload.as_bytes(),
        "the signature covers the transmitted base64url string exactly (CON-P7)"
    );
    // It is emphatically NOT the decoded JSON.
    assert!(
        !envelope.signed_bytes().starts_with(b"{"),
        "signed_bytes must be the encoded form, never the decoded JSON"
    );
    assert!(
        !payload.contains('='),
        "the server strips base64 padding; a padded comparison would not match"
    );
}

#[test]
fn an_unsupported_algorithm_or_version_is_rejected_before_key_selection() {
    // `signing.py:99-104` checks `alg` against a one-element allow-list before touching
    // any key material — dispatching on a caller-supplied algorithm is how confusion
    // attacks work. The header check is mirrored here so 86ak5mn1d inherits the ordering.
    let base = EntitlementEnvelope {
        envelope_version: 1,
        alg: "Ed25519".into(),
        key_id: "630dcd29".into(),
        payload: "p".into(),
        signature: "s".into(),
    };
    assert!(base.header_is_supported());

    let wrong_alg = EntitlementEnvelope {
        alg: "none".into(),
        ..base.clone()
    };
    assert!(
        !wrong_alg.header_is_supported(),
        "`alg: none` must never be accepted"
    );

    let wrong_alg = EntitlementEnvelope {
        alg: "HS256".into(),
        ..base.clone()
    };
    assert!(!wrong_alg.header_is_supported());

    let wrong_version = EntitlementEnvelope {
        envelope_version: 2,
        ..base
    };
    assert!(!wrong_version.header_is_supported());
}
