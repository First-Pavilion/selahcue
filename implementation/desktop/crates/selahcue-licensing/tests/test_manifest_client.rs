#![allow(clippy::unwrap_used)]

#[path = "../../selahcue-cloud/tests/support/credential_receiver.rs"]
#[allow(dead_code)] // This suite needs only the normal accepted socket path.
mod credential_receiver;

use selahcue_cloud::transport::ReqwestTransport;
use selahcue_licensing::{
    verify_entitlement, ActivationFailure, EntitlementVerificationError, LicensingClient,
    ScriptedTransport, Token, TrustedKeys,
};
use serde_json::{json, Value};

const ORIGIN: &str = "https://api.example.test";
const TOKEN: &str = "SC-device-fixture-token";
const DEVICE: &str = "dev_0123456789abcdef0123456789abcdef";

fn client(status: u16, body: impl Into<String>) -> LicensingClient<ScriptedTransport> {
    LicensingClient::new(ScriptedTransport::responding(status, body), ORIGIN).unwrap()
}

fn refresh_body() -> Value {
    json!({
        "device": {"device_public_id": DEVICE, "status": "ACTIVE"},
        "license": {
            "status": "EXPIRED",
            "starts_at": "2025-01-01T00:00:00+00:00",
            "expires_at": "2026-01-01T00:00:00+00:00",
            "valid_now": false
        },
        "instances": {"used": 1, "limit": 3},
        "token": {"expires_at": "2027-01-01T00:00:00+00:00"},
        "entitlement": {"feature_scope": "Everything", "territory": "NG"},
        "surface": "desktop",
        "operation": "license_refresh"
    })
}

#[test]
fn fetch_sends_a_bodyless_device_authenticated_get_and_returns_envelope_bytes() {
    let fixture: Value =
        serde_json::from_str(include_str!("fixtures/api-entitlement-v1.json")).unwrap();
    // Formatting and additional unsigned fields at the HTTP boundary must survive unchanged.
    let body = serde_json::to_string_pretty(&fixture["wire"]).unwrap();
    let client = client(200, &body);

    let fetched = client.fetch_entitlement(&Token::new(TOKEN)).unwrap();
    assert_eq!(fetched, body.as_bytes());
    let request = client.transport().request(0).unwrap();
    assert_eq!(client.transport().request_count(), 1);
    assert_eq!(request.method, "GET");
    assert_eq!(
        request.url,
        "https://api.example.test/v1/entitlements/manifest"
    );
    assert!(request.had_bearer);
    assert!(request.body.is_empty());
}

#[test]
fn malformed_or_oversized_success_and_http_errors_keep_wire_text_private() {
    let token = Token::new(TOKEN);
    for body in [format!(r#"{{"payload":"{TOKEN}"}}"#), TOKEN.repeat(6500)] {
        let error = client(200, body).fetch_entitlement(&token).unwrap_err();
        assert!(matches!(error, ActivationFailure::Malformed(_)));
        assert!(!format!("{error} {error:?}").contains(TOKEN));
    }
    for (status, expected) in [
        (302, ActivationFailure::UnexpectedStatus(302)),
        (401, ActivationFailure::Unauthenticated),
        (502, ActivationFailure::Server(502)),
    ] {
        let error = client(status, TOKEN).fetch_entitlement(&token).unwrap_err();
        assert_eq!(error, expected);
        assert!(!format!("{error} {error:?}").contains(TOKEN));
    }
    let transport = ScriptedTransport::failing(TOKEN);
    let client = LicensingClient::new(transport, ORIGIN).unwrap();
    let error = client.fetch_entitlement(&token).unwrap_err();
    assert!(matches!(error, ActivationFailure::Unreachable(_)));
    assert!(!format!("{error} {error:?}").contains(TOKEN));
}

#[test]
fn refresh_posts_an_empty_json_object_and_reports_expired_licence_with_live_token() {
    let client = client(200, refresh_body().to_string());
    let refreshed = client.refresh_license(&Token::new(TOKEN), DEVICE).unwrap();

    assert_eq!(refreshed.device_public_id, DEVICE);
    assert_eq!(refreshed.device_status, "ACTIVE");
    assert_eq!(refreshed.license_status, "EXPIRED");
    assert!(!refreshed.license_valid_now);
    assert_eq!(refreshed.license_starts_at, "2025-01-01T00:00:00+00:00");
    assert_eq!(refreshed.license_expires_at, "2026-01-01T00:00:00+00:00");
    assert_eq!(refreshed.token_expires_at, "2027-01-01T00:00:00+00:00");
    assert_eq!(
        (refreshed.instances_used, refreshed.instances_limit),
        (1, 3)
    );
    let request = client.transport().request(0).unwrap();
    assert_eq!(client.transport().request_count(), 1);
    assert_eq!(request.method, "POST");
    assert_eq!(request.url, "https://api.example.test/v1/license:refresh");
    assert_eq!(request.body, "{}");
    assert!(request.had_bearer);
}

#[test]
fn refresh_refuses_to_report_another_devices_status() {
    let client = client(200, refresh_body().to_string());
    let error = client
        .refresh_license(&Token::new(TOKEN), "dev_different_install")
        .unwrap_err();
    assert!(matches!(error, ActivationFailure::Malformed(_)));
    assert!(!format!("{error} {error:?}").contains(DEVICE));
}

#[test]
fn refresh_distinguishes_rejected_token_from_malformed_status() {
    let token = Token::new(TOKEN);
    let denied = client(
        401,
        json!({
            "error": {"code": "UNAUTHENTICATED", "message": TOKEN},
            "surface": "desktop",
            "operation": "license_refresh"
        })
        .to_string(),
    );
    let error = denied.refresh_license(&token, DEVICE).unwrap_err();
    assert_eq!(error, ActivationFailure::Unauthenticated);
    assert!(!format!("{error} {error:?}").contains(TOKEN));

    let mut malformed = refresh_body();
    malformed["license"]["valid_now"] = json!(TOKEN);
    let error = client(200, malformed.to_string())
        .refresh_license(&token, DEVICE)
        .unwrap_err();
    assert!(matches!(error, ActivationFailure::Malformed(_)));
    assert!(!format!("{error} {error:?}").contains(TOKEN));

    let unreachable = LicensingClient::new(ScriptedTransport::failing(TOKEN), ORIGIN).unwrap();
    let error = unreachable.refresh_license(&token, DEVICE).unwrap_err();
    assert!(matches!(error, ActivationFailure::Unreachable(_)));
    assert!(!format!("{error} {error:?}").contains(TOKEN));
}

#[test]
fn refresh_status_cannot_be_read_as_a_signed_manifest() {
    let body = refresh_body().to_string();
    assert_eq!(
        verify_entitlement(
            body.as_bytes(),
            &TrustedKeys::bundled(),
            DEVICE,
            "test-fixture-fingerprint"
        )
        .unwrap_err(),
        EntitlementVerificationError::MalformedEnvelope
    );
    assert!(matches!(
        client(200, body).fetch_entitlement(&Token::new(TOKEN)),
        Err(ActivationFailure::Malformed(_))
    ));
}

#[test]
fn real_device_reads_send_the_exact_bearer_only_in_the_authorization_header() {
    let receiver = credential_receiver::Receiver::start();
    let client = LicensingClient::new_for_loopback_tests(
        ReqwestTransport::new_for_loopback_tests().unwrap(),
        &receiver.base,
    )
    .unwrap();

    let token = Token::new(TOKEN);
    assert_eq!(
        client.fetch_entitlement(&token).unwrap_err(),
        ActivationFailure::Server(503)
    );
    assert_eq!(
        client.refresh_license(&token, DEVICE).unwrap_err(),
        ActivationFailure::Server(503)
    );
    let requests = receiver.finish();
    assert_eq!(requests.len(), 2);
    for (request, method_and_path, expected_body) in [
        (&requests[0], "GET /v1/entitlements/manifest HTTP/1.1", ""),
        (&requests[1], "POST /v1/license:refresh HTTP/1.1", "{}"),
    ] {
        let (headers, body) = request.split_once("\r\n\r\n").unwrap();
        assert_eq!(headers.lines().next(), Some(method_and_path));
        assert_eq!(body, expected_body);
        assert_eq!(request.matches(TOKEN).count(), 1);
        assert!(headers.lines().any(|line| {
            let Some((name, value)) = line.split_once(':') else {
                return false;
            };
            name.eq_ignore_ascii_case("authorization") && value.trim() == format!("Bearer {TOKEN}")
        }));
    }
}

#[test]
fn invalid_bearers_never_reach_the_device_transport() {
    let client = client(200, "{}");
    for raw in ["", "  ", "split\r\ntoken"] {
        let token = Token::new(raw);
        assert_eq!(
            client.fetch_entitlement(&token).unwrap_err(),
            ActivationFailure::Unauthenticated
        );
        assert_eq!(
            client.refresh_license(&token, DEVICE).unwrap_err(),
            ActivationFailure::Unauthenticated
        );
    }
    assert_eq!(client.transport().request_count(), 0);
}

#[test]
fn refresh_rejects_unbounded_statuses_and_non_timestamp_metadata() {
    for (group, field, value) in [
        ("device", "status", json!("A".repeat(17))),
        ("license", "status", json!("invalid\nstatus")),
        ("instances", "used", json!(-1)),
        ("token", "expires_at", json!(TOKEN)),
    ] {
        let mut malformed = refresh_body();
        malformed[group][field] = value;
        let error = client(200, malformed.to_string())
            .refresh_license(&Token::new(TOKEN), DEVICE)
            .unwrap_err();
        assert!(
            matches!(error, ActivationFailure::Malformed(_)),
            "{group}.{field}"
        );
        assert!(!format!("{error} {error:?}").contains(TOKEN));
    }
}
