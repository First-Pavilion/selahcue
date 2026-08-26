//! The wire contract, pinned to the shipped server.
//!
//! These fixtures are the desktop half of a cross-language contract, in the same spirit as
//! the LAN protocol's byte-pinned JSON. The server is Python and this is Rust; nothing but
//! a test holds the two field-name sets together, and the failure mode when they drift is
//! silent — a `#[serde(default)]` quietly yielding an empty string where a device id was
//! expected.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::contract::{
    ActivateDeviceInput, ActivateWithSessionData, ActivationRequest, ActivationResponse,
    ApiErrorEnvelope, EntitlementEnvelope, ErrorCode, GraphQlResponse, InputVariables, LoginData,
    ACCOUNT_GRAPHQL_PATH, ACTIVATIONS_PATH, ENTITLEMENT_MANIFEST_PATH, ENVELOPE_ALG,
    ENVELOPE_VERSION,
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
    assert_eq!(ACCOUNT_GRAPHQL_PATH, "/graphql/account");
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
fn the_graphql_input_is_camel_cased() {
    // Strawberry auto-camel-cases and this schema uses the default config
    // (`account_schema.py:258-261`). A snake_case input is rejected as an unknown argument.
    let variables = InputVariables {
        input: ActivateDeviceInput {
            idempotency_key: "idem-0123456789ab".into(),
            device_fingerprint: "fp-1".into(),
            platform: "macos".into(),
            app_version: "1.0.0".into(),
            display_name: "Booth".into(),
        },
    };
    let json = serde_json::to_string(&variables).unwrap();

    for key in [
        "\"idempotencyKey\"",
        "\"deviceFingerprint\"",
        "\"appVersion\"",
        "\"displayName\"",
    ] {
        assert!(json.contains(key), "expected {key} in {json}");
    }
    assert!(
        !json.contains("idempotency_key"),
        "snake_case would be an unknown argument to the GraphQL schema: {json}"
    );
}

#[test]
fn graphql_payloads_parse_from_their_camel_cased_wire_form() {
    let login = r#"{"data": {"login": {"sessionToken": "sess-abc",
      "expiresAt": "2026-09-24T10:11:12.123456+00:00", "role": "ADMIN", "orgId": "org_1"}}}"#;
    let parsed: GraphQlResponse<LoginData> = serde_json::from_str(login).unwrap();
    let payload = parsed.data.unwrap().login;
    assert_eq!(payload.session_token.expose(), "sess-abc");
    assert_eq!(payload.role, "ADMIN");

    let activate = r#"{"data": {"activateDeviceWithSession": {"fullToken": "SC-DEV-XYZ",
      "created": true, "devicePublicId": "dev_1", "platform": "macos"}}}"#;
    let parsed: GraphQlResponse<ActivateWithSessionData> = serde_json::from_str(activate).unwrap();
    let payload = parsed.data.unwrap().activate_device_with_session;
    assert_eq!(
        payload.full_token.as_ref().map(Token::expose),
        Some("SC-DEV-XYZ")
    );
    assert!(payload.created);

    // The device token is `fullToken` here and `activation_token` over REST. Same secret,
    // two names, because neither may be called `device_token` without tripping the
    // server's own redaction guard.
    assert!(!activate.contains("deviceToken"));
}

#[test]
fn a_graphql_error_carries_its_code_in_extensions() {
    let body = r#"{"data": null, "errors": [{"message": "Authentication is required.",
      "extensions": {"code": "UNAUTHENTICATED"}}]}"#;
    let parsed: GraphQlResponse<LoginData> = serde_json::from_str(body).unwrap();

    let errors = parsed.errors.unwrap();
    assert_eq!(errors.len(), 1);
    assert_eq!(errors[0].code(), Some(ErrorCode::Unauthenticated));
    assert!(parsed.data.is_none());
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
