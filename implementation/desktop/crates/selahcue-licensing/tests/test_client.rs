//! Both activation paths, the replay/re-mint decision table, and failure classification.
//!
//! Every fixture body here is shaped from the shipped server's own source — the REST
//! payload from `platform/views.py:83-110`, the GraphQL payloads from
//! `graphql/account_schema.py:76-128`, the error envelope from
//! `platform/responses.py:33-42`. Where the server emits a value with an unusual shape
//! (Python `isoformat()` with microseconds and a `+00:00` offset rather than `Z`) the
//! fixture keeps that shape, because a client that only ever sees `Z` in its tests is a
//! client that has not been tested.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::client::{ActivationPath, PersistOutcome, TokenDisposition};
use selahcue_licensing::contract::{ACCOUNT_GRAPHQL_PATH, ACTIVATIONS_PATH};
use selahcue_licensing::{
    ActivationFailure, DeviceCredentials, DeviceIdentity, IdempotencyKey, InMemorySecretStore,
    LicensingClient, LicensingStatus, ScriptedTransport, Token,
};

const BASE: &str = "https://api.selahcue.example";
const TOKEN_A: &str = "SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8";
const TOKEN_B: &str = "SC-DEV-Z9Y8-X7W6-V5U4-T3S2-R1Q0-P9N8-M7L6-K5J4";
const SESSION: &str = "sess-11112222333344445555666677778888";
const ENROLLMENT_KEY: &str = "SC-TRIAL-Z9Y8-X7W6-V5U4-T3S2-R1Q0-P9N8-M7L6-K5J4";
const DEVICE_ID: &str = "dev_0123456789abcdef0123456789abcdef";

fn identity() -> DeviceIdentity {
    DeviceIdentity::new("fp-booth-mac-01", "macos", "1.0.0", "Sound booth Mac").unwrap()
}

fn idem() -> IdempotencyKey {
    IdempotencyKey::new("idem-0123456789ab").unwrap()
}

fn credentials() -> DeviceCredentials<InMemorySecretStore> {
    DeviceCredentials::new(InMemorySecretStore::new())
}

/// A REST activation success body.
fn rest_body(created: bool, reminted: bool, token: Option<&str>) -> String {
    let token_field = match token {
        Some(t) => format!("\"{t}\""),
        None => "null".to_string(),
    };
    format!(
        r#"{{"created":{created},"reminted":{reminted},"activation_token":{token_field},
        "device":{{"device_public_id":"{DEVICE_ID}","status":"ACTIVE","platform":"macos"}},
        "token":{{"masked":"SC-DEV-A1B2...Q7R8","prefix":"SC-DEV-A1B2","suffix":"Q7R8",
        "fingerprint":"{fp}","expires_at":"2026-09-24T10:11:12.123456+00:00"}},
        "license":{{"status":"ACTIVATED","expires_at":"2026-12-31T23:59:59.999999+00:00"}},
        "surface":"desktop","operation":"activation"}}"#,
        fp = "a".repeat(64)
    )
}

/// A coded REST error body.
fn rest_error(code: &str, message: &str) -> String {
    format!(
        r#"{{"error":{{"code":"{code}","message":"{message}"}},"surface":"desktop","operation":"activation"}}"#
    )
}

// ---------------------------------------------------------------------------
// The primary path: account sign-in
// ---------------------------------------------------------------------------

#[test]
fn a_fresh_install_activates_by_signing_in_and_receives_a_device_token() {
    let transport = ScriptedTransport::new();
    transport.push_response(
        200,
        format!(
            r#"{{"data":{{"login":{{"sessionToken":"{SESSION}",
            "expiresAt":"2026-09-24T10:11:12.123456+00:00","role":"ADMIN","orgId":"org_1"}}}}}}"#
        ),
    );
    transport.push_response(
        200,
        format!(
            r#"{{"data":{{"activateDeviceWithSession":{{"fullToken":"{TOKEN_A}","created":true,
            "devicePublicId":"{DEVICE_ID}","platform":"macos"}}}}}}"#
        ),
    );

    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();

    let session = client
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .expect("sign-in should succeed");
    assert_eq!(session.role, "ADMIN");
    assert_eq!(session.org_id, "org_1");

    let activation = client
        .activate_with_session(&session.token, &identity(), &idem())
        .expect("activation should succeed");

    assert_eq!(activation.path, ActivationPath::AccountSession);
    assert!(activation.created);
    assert_eq!(activation.device_public_id, DEVICE_ID);
    assert_eq!(
        activation.persist(&creds).unwrap(),
        PersistOutcome::Stored,
        "a fresh activation must write the token"
    );
    assert_eq!(creds.device_token().unwrap().unwrap().expose(), TOKEN_A);

    // What actually left the device.
    let login = client.transport().request(0).unwrap();
    assert_eq!(login.url, format!("{BASE}{ACCOUNT_GRAPHQL_PATH}"));
    assert!(
        !login.had_bearer,
        "sign-in must not send a bearer — it is the call that obtains one"
    );

    let activate = client.transport().request(1).unwrap();
    assert_eq!(activate.url, format!("{BASE}{ACCOUNT_GRAPHQL_PATH}"));
    assert!(
        activate.had_bearer,
        "session activation must authenticate with the session token"
    );
    assert!(
        activate
            .body
            .contains("\"deviceFingerprint\":\"fp-booth-mac-01\""),
        "the GraphQL input must be camelCased: {}",
        activate.body
    );
    assert!(
        !activate.body.contains("license_key") && !activate.body.contains("licenseKey"),
        "the session path sends no key — the org comes from the session: {}",
        activate.body
    );
}

#[test]
fn an_activation_reports_a_status_that_still_permits_presentation() {
    // The status type is what the console renders. It is reachable from an activation on
    // both paths, and — like every other state in this crate — it permits presentation.
    let transport = ScriptedTransport::responding(200, rest_body(true, false, Some(TOKEN_A)));
    let client = LicensingClient::new(transport, BASE);

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    let status = activation.status();
    assert!(status.is_activated());
    assert_eq!(
        status,
        LicensingStatus::Activated {
            device_public_id: DEVICE_ID.to_string()
        }
    );
    assert!(status.permits_presentation());
}

#[test]
fn the_password_is_used_once_and_never_persisted() {
    let transport = ScriptedTransport::responding(
        200,
        format!(
            r#"{{"data":{{"login":{{"sessionToken":"{SESSION}","expiresAt":"x","role":"ADMIN","orgId":"o"}}}}}}"#
        ),
    );
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();

    let session = client
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .unwrap();
    creds.store_account_session(&session.token).unwrap();

    // Only the session token is held; the password is not in the store under any name.
    assert_eq!(
        creds.account_session().unwrap().unwrap().expose(),
        SESSION,
        "the session token is what gets persisted"
    );
    assert!(
        creds.device_token().unwrap().is_none(),
        "signing in alone must not fabricate a device token"
    );
}

// ---------------------------------------------------------------------------
// The delegation path: enrollment key
// ---------------------------------------------------------------------------

#[test]
fn the_enrollment_key_path_activates_the_same_machine() {
    let transport = ScriptedTransport::responding(200, rest_body(true, false, Some(TOKEN_A)));
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .expect("enrollment-key activation should succeed");

    assert_eq!(activation.path, ActivationPath::EnrollmentKey);
    assert!(activation.created);
    assert_eq!(activation.reminted, Some(false));
    assert_eq!(activation.device_public_id, DEVICE_ID);
    assert_eq!(
        activation.license.as_ref().unwrap().status,
        "ACTIVATED",
        "the REST path reports the backing licence; the session path does not"
    );
    assert_eq!(activation.persist(&creds).unwrap(), PersistOutcome::Stored);
    assert_eq!(creds.device_token().unwrap().unwrap().expose(), TOKEN_A);
}

#[test]
fn the_enrollment_key_travels_in_the_body_and_the_path_has_no_trailing_slash() {
    let transport = ScriptedTransport::responding(200, rest_body(true, false, Some(TOKEN_A)));
    let client = LicensingClient::new(transport, BASE);

    client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    let sent = client.transport().request(0).unwrap();
    assert_eq!(
        sent.url,
        format!("{BASE}{ACTIVATIONS_PATH}"),
        "the route is registered without a trailing slash; adding one is a 404"
    );
    assert!(!sent.url.ends_with('/'));
    assert!(
        !sent.had_bearer,
        "this endpoint takes no Authorization header — the presented key IS the credential"
    );
    assert!(
        sent.body
            .contains(&format!("\"license_key\":\"{ENROLLMENT_KEY}\"")),
        "the key is sent as `license_key`, not `enrollment_key`: {}",
        sent.body
    );
    assert!(sent
        .body
        .contains("\"idempotency_key\":\"idem-0123456789ab\""));
    assert!(sent
        .body
        .contains("\"device_fingerprint\":\"fp-booth-mac-01\""));
}

// ---------------------------------------------------------------------------
// The replay / re-mint decision table
// ---------------------------------------------------------------------------

#[test]
fn a_replay_keeps_the_token_the_device_already_holds() {
    // created=false, reminted=false, activation_token=null → show-once replay. The server
    // refuses to re-show a secret it already issued, and that is success, not an error.
    let transport = ScriptedTransport::responding(200, rest_body(false, false, None));
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .expect("a replay is a success");

    assert!(!activation.created);
    assert!(!activation.is_remint());
    assert_eq!(activation.disposition(), TokenDisposition::KeepExisting);
    assert_eq!(
        activation.persist(&creds).unwrap(),
        PersistOutcome::KeptExisting
    );
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        TOKEN_A,
        "a replay must not disturb the cached token"
    );
}

#[test]
fn a_remint_overwrites_the_cached_token_because_the_old_one_is_revoked() {
    // created=false, reminted=true → the previous token was expired or revoked and has now
    // been replaced. Keeping the old one would 401 on its next use, so overwriting is
    // mandatory rather than an optimisation.
    let transport = ScriptedTransport::responding(200, rest_body(false, true, Some(TOKEN_B)));
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    assert!(activation.is_remint(), "the server reported a re-mint");
    assert_eq!(
        activation.disposition(),
        TokenDisposition::Store(Token::new(TOKEN_B))
    );
    assert_eq!(activation.persist(&creds).unwrap(), PersistOutcome::Stored);
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        TOKEN_B,
        "the re-minted token must replace the revoked one"
    );
}

#[test]
fn a_replay_with_no_local_token_is_reported_rather_than_silently_succeeding() {
    // The awkward case: the server replays (so it will not re-show the token) but this
    // install has none — a deleted keychain entry, or a re-image. Retrying cannot fix it.
    // Reporting it beats a "success" that leaves the install with no credential.
    let transport = ScriptedTransport::responding(200, rest_body(false, false, None));
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    assert_eq!(
        activation.persist(&creds).unwrap(),
        PersistOutcome::MissingLocally,
        "a replay with nothing cached locally must be surfaced, not hidden"
    );
    assert!(!creds.is_activated().unwrap());
}

// ---------------------------------------------------------------------------
// Failure classification
// ---------------------------------------------------------------------------

#[test]
fn an_unknown_enrollment_key_is_classified_as_such() {
    let transport = ScriptedTransport::responding(
        404,
        rest_error("NOT_FOUND", "The requested resource was not found."),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new("SC-TRIAL-nope"), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::UnknownKey);
}

#[test]
fn a_policy_refusal_is_one_state_because_the_server_does_not_distinguish_them() {
    // The design wants separate frames for "device limit reached" (A5) and "licence
    // expired" (A6). The shipped server returns a byte-identical POLICY_DENIED for both,
    // so this client reports one state rather than guessing which. Splitting it here would
    // mean telling a church its plan is full when its licence had merely expired.
    let transport = ScriptedTransport::responding(
        403,
        rest_error(
            "POLICY_DENIED",
            "The current policy does not allow this action.",
        ),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::PolicyDenied);
}

#[test]
fn permission_denied_is_not_collapsed_into_policy_denied() {
    // Both are HTTP 403. Branching on status rather than code would merge them, and they
    // mean different things: one is "your plan does not allow this", the other is "your
    // account may not do this".
    let transport = ScriptedTransport::responding(
        403,
        rest_error(
            "PERMISSION_DENIED",
            "You do not have permission to perform this action.",
        ),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::PermissionDenied);
    assert_ne!(failure, ActivationFailure::PolicyDenied);
}

#[test]
fn an_expired_account_session_asks_for_a_new_sign_in() {
    let transport = ScriptedTransport::responding(
        200,
        r#"{"data":null,"errors":[{"message":"Authentication is required.",
        "extensions":{"code":"UNAUTHENTICATED"}}]}"#,
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::Unauthenticated);
}

#[test]
fn a_graphql_refusal_arrives_as_http_200_and_is_still_a_failure() {
    // GraphQL returns 200 with an `errors` array. A client that checked only the status
    // would read this as success and then find `data` missing.
    let transport = ScriptedTransport::responding(
        200,
        r#"{"data":null,"errors":[{"message":"The current policy does not allow this action.",
        "extensions":{"code":"POLICY_DENIED"}}]}"#,
    );
    let client = LicensingClient::new(transport, BASE);

    assert_eq!(
        client
            .activate_with_session(&Token::new(SESSION), &identity(), &idem())
            .unwrap_err(),
        ActivationFailure::PolicyDenied
    );
}

#[test]
fn a_non_2xx_graphql_response_still_yields_its_coded_error() {
    // The GraphQL view answers a non-2xx with the GRAPHQL error shape, not the REST one:
    // `safe_error_payload` builds `{"errors": [...]}` (`graphql/views.py:52-54`). A client
    // that classified non-2xx by status first would discard the code and report contract
    // drift — turning "sign in again" into "something is broken".
    let transport = ScriptedTransport::responding(
        400,
        r#"{"errors":[{"message":"The request is invalid.",
        "extensions":{"code":"VALIDATION_FAILED"}}]}"#,
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(
        failure,
        ActivationFailure::ValidationFailed,
        "the coded error in the body must win over the HTTP status"
    );
    assert!(
        !matches!(failure, ActivationFailure::Malformed(_)),
        "a well-formed coded refusal must never be reported as contract drift"
    );
}

#[test]
fn a_non_graphql_error_page_still_falls_back_to_status_classification() {
    // Positive control for the fallback: when the body genuinely is not a GraphQL
    // response — a proxy error page — status classification must still apply, or the
    // ordering fix above would have simply swapped one blind spot for another.
    let transport = ScriptedTransport::responding(502, "<html>502 Bad Gateway</html>");
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::Server(502));
    assert!(failure.is_retryable());
}

#[test]
fn rate_limiting_and_server_errors_are_retryable_but_refusals_are_not() {
    let limited = LicensingClient::new(
        ScriptedTransport::responding(429, rest_error("RATE_LIMITED", "Too many requests.")),
        BASE,
    );
    let failure = limited
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();
    assert_eq!(failure, ActivationFailure::RateLimited);
    assert!(failure.is_retryable());

    let refused = LicensingClient::new(
        ScriptedTransport::responding(404, rest_error("NOT_FOUND", "x")),
        BASE,
    );
    let failure = refused
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();
    assert!(
        !failure.is_retryable(),
        "a coded refusal is a decision somebody made; retrying it silently is wrong"
    );
}

#[test]
fn a_bare_405_html_body_is_classified_by_status_not_reported_as_contract_drift() {
    // A wrong HTTP method yields a bare Django 405 with an HTML body, not the JSON error
    // envelope. Treating every unparseable error as "the contract drifted" would make that
    // case shout about the wrong problem.
    let transport = ScriptedTransport::responding(500, "<html><body>Server Error</body></html>");
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::Server(500));
    assert!(failure.is_retryable());
}

#[test]
fn an_unknown_error_code_is_kept_rather_than_collapsed() {
    let transport = ScriptedTransport::responding(
        403,
        rest_error("SOME_FUTURE_CODE", "The request is invalid."),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();

    match failure {
        ActivationFailure::Coded(code) => assert_eq!(code.as_str(), "SOME_FUTURE_CODE"),
        other => panic!("a newer server's code must remain reportable, got {other:?}"),
    }
}
