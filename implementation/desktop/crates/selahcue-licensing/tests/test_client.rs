//! Both activation paths, the replay/re-mint decision table, and failure classification.
//!
//! Every fixture body here is shaped from the shipped server's own source — the activation
//! payload from `platform/views.py::_activation_payload`, the sign-in payload from
//! `platform/views.py::create_session`, the error envelope from
//! `platform/responses.py::command_error_response`. Where the server emits a value with an unusual shape
//! (Python `isoformat()` with microseconds and a `+00:00` offset rather than `Z`) the
//! fixture keeps that shape, because a client that only ever sees `Z` in its tests is a
//! client that has not been tested.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::client::{
    ActivationPath, PersistOutcome, TokenDisposition, MAX_RESPONSE_BODY_BYTES,
};
use selahcue_licensing::contract::ACTIVATIONS_PATH;
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

/// A REST activation success body, as `POST /v1/activations` answers it.
fn rest_body(created: bool, reminted: bool, token: Option<&str>) -> String {
    activation_body("activation", created, reminted, token)
}

/// The same body as `POST /v1/activations:with-session` answers it: identical but for the
/// `operation` label (`platform/views.py::_activation_payload`).
fn session_activation_body(created: bool, reminted: bool, token: Option<&str>) -> String {
    activation_body("activation_with_session", created, reminted, token)
}

/// A `POST /v1/sessions` success body (`platform/views.py::create_session`), including the
/// two unsigned labels the view appends.
fn session_body() -> String {
    format!(
        r#"{{"session_token":"{SESSION}","expires_at":"2026-11-23T10:11:12.123456+00:00",
        "role":"ADMIN","org_id":"org_1","surface":"desktop","operation":"session_login"}}"#
    )
}

fn activation_body(operation: &str, created: bool, reminted: bool, token: Option<&str>) -> String {
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
        "surface":"desktop","operation":"{operation}"}}"#,
        fp = "a".repeat(64)
    )
}

/// A coded REST error body, as the enrollment-key route answers it.
fn rest_error(code: &str, message: &str) -> String {
    coded_error("activation", code, message)
}

/// A coded error body for any `/v1` operation (`platform/responses.py::command_error_response`).
fn coded_error(operation: &str, code: &str, message: &str) -> String {
    format!(
        r#"{{"error":{{"code":"{code}","message":"{message}"}},"surface":"desktop","operation":"{operation}"}}"#
    )
}

/// A coded error from `POST /v1/activations:with-session`.
fn session_error(code: &str, message: &str) -> String {
    coded_error("activation_with_session", code, message)
}

/// A coded error from `POST /v1/sessions`.
fn sign_in_error(code: &str, message: &str) -> String {
    coded_error("session_login", code, message)
}

// ---------------------------------------------------------------------------
// The primary path: account sign-in
// ---------------------------------------------------------------------------

#[test]
fn a_fresh_install_activates_by_signing_in_and_receives_a_device_token() {
    let transport = ScriptedTransport::new();
    transport.push_response(200, session_body());
    transport.push_response(200, session_activation_body(true, false, Some(TOKEN_A)));

    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();

    let session = client
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .expect("sign-in should succeed");
    assert_eq!(session.role, "ADMIN");
    assert_eq!(session.org_id, "org_1");
    assert_eq!(session.token.expose(), SESSION);
    assert_eq!(session.expires_at, "2026-11-23T10:11:12.123456+00:00");

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

    // What actually left the device. The paths are spelled out as literals on purpose: the
    // server's routes are the contract, and a test that read them back from the same
    // constant the client uses could never notice the constant drifting.
    assert_eq!(client.transport().request_count(), 2);
    let login = client.transport().request(0).unwrap();
    assert_eq!(login.method, "POST");
    assert_eq!(login.url, format!("{BASE}/v1/sessions"));
    assert!(
        !login.had_bearer,
        "sign-in must not send a bearer — it is the call that obtains one"
    );
    let login_body: serde_json::Value = serde_json::from_str(&login.body).unwrap();
    let login_keys: Vec<&str> = login_body
        .as_object()
        .unwrap()
        .keys()
        .map(String::as_str)
        .collect();
    assert_eq!(
        login_keys,
        ["email", "password"],
        "the sign-in body is exactly email + password: {login_body}"
    );
    assert_eq!(login_body["email"], "admin@example.test");
    assert_eq!(login_body["password"], "correct-horse");

    let activate = client.transport().request(1).unwrap();
    assert_eq!(activate.method, "POST");
    assert_eq!(activate.url, format!("{BASE}/v1/activations:with-session"));
    assert!(
        activate.had_bearer,
        "session activation must authenticate with the session token"
    );
    let body: serde_json::Value = serde_json::from_str(&activate.body).unwrap();
    let mut keys: Vec<&str> = body
        .as_object()
        .unwrap()
        .keys()
        .map(String::as_str)
        .collect();
    keys.sort_unstable();
    assert_eq!(
        keys,
        [
            "app_version",
            "device_fingerprint",
            "display_name",
            "idempotency_key",
            "platform"
        ],
        "the session body is the activation body minus license_key, snake_case: {body}"
    );
    assert_eq!(body["device_fingerprint"], "fp-booth-mac-01");
    assert!(
        !activate.body.contains("license_key") && !activate.body.contains("licenseKey"),
        "the session path sends no key — the org comes from the session: {}",
        activate.body
    );
}

#[test]
fn a_session_activation_reports_everything_the_enrollment_path_does() {
    // 86ak5t1gw: `/v1/activations:with-session` answers with exactly the
    // `/v1/activations` shape, so the primary path can now report `reminted`, the token
    // metadata and the licence block, which the old GraphQL payload never carried (all three
    // were `None` on this path, and a re-mint could not be told from "not reported").
    let transport =
        ScriptedTransport::responding(200, session_activation_body(false, true, Some(TOKEN_B)));
    let client = LicensingClient::new(transport, BASE);

    let activation = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap();

    assert_eq!(activation.path, ActivationPath::AccountSession);
    assert!(activation.reminted);
    assert_eq!(activation.platform, "macos");
    let meta = &activation.token_meta;
    assert_eq!(meta.prefix.as_deref(), Some("SC-DEV-A1B2"));
    assert_eq!(
        meta.expires_at.as_deref(),
        Some("2026-09-24T10:11:12.123456+00:00")
    );
    assert_eq!(activation.license.status, "ACTIVATED");

    // A re-mint over this path must overwrite, exactly as over the key path.
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();
    assert_eq!(activation.persist(&creds).unwrap(), PersistOutcome::Stored);
    assert_eq!(creds.device_token().unwrap().unwrap().expose(), TOKEN_B);
}

#[test]
fn a_session_activation_replay_keeps_the_token_the_device_already_holds() {
    let transport = ScriptedTransport::responding(200, session_activation_body(false, false, None));
    let client = LicensingClient::new(transport, BASE);
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();

    let activation = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .expect("a replay is a success");

    assert!(!activation.reminted);
    assert_eq!(activation.disposition(), TokenDisposition::KeepExisting);
    assert_eq!(
        activation.persist(&creds).unwrap(),
        PersistOutcome::KeptExisting
    );
    assert_eq!(creds.device_token().unwrap().unwrap().expose(), TOKEN_A);
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
    let transport = ScriptedTransport::responding(200, session_body());
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
    assert!(!activation.reminted);
    assert_eq!(activation.device_public_id, DEVICE_ID);
    assert_eq!(
        activation.license.status, "ACTIVATED",
        "the backing licence is reported on this path"
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
    assert!(!activation.reminted);
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

    assert!(activation.reminted, "the server reported a re-mint");
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
fn a_deactivated_machine_is_refused_by_policy_and_keeps_presenting() {
    // AC-5 says "a deactivated machine re-activates when a slot is free". **The shipped
    // server does not do that.** `_assert_device_activatable` (`devices/services.py:127-131`)
    // refuses any device whose status is not ACTIVE with `POLICY_DENIED`, and says why:
    // "A revoked device is terminal for this slice... Re-provisioning a revoked install is a
    // separate future flow."
    //
    // So this pins what the system ACTUALLY does rather than the criterion as written: the
    // refusal is classified correctly, the local token is untouched, and — the part that
    // matters on a Sunday — the app carries on presenting. The gap between AC-5 and the
    // server is recorded in the Goal Contract and raised for the owner; it is not something
    // to paper over with a green test.
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();

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
    assert!(
        failure.permits_presentation(),
        "a deactivated machine must keep presenting; licensing gates nothing (CON-P1)"
    );
    assert!(
        !failure.is_retryable(),
        "a policy refusal is a decision somebody made, not a blip to retry silently"
    );
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        TOKEN_A,
        "a refused re-activation must not clear the token the machine already holds"
    );
}

#[test]
fn a_device_whose_token_was_revoked_is_re_minted_which_is_the_supported_recovery() {
    // The half of AC-5 the server DOES support: the device row stays ACTIVE but its token
    // was revoked or expired, so a re-activation mints a replacement
    // (`devices/services.py:300-312`) — gated on the plan's allowance, which is where a
    // downgraded licence would otherwise leak seats. This is the real "machine comes back"
    // path, and it consumes the allowance like any activation.
    let creds = credentials();
    creds.store_device_token(&Token::new(TOKEN_A)).unwrap();

    let transport = ScriptedTransport::responding(200, rest_body(false, true, Some(TOKEN_B)));
    let client = LicensingClient::new(transport, BASE);

    let activation = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    assert!(activation.reminted);
    assert_eq!(activation.persist(&creds).unwrap(), PersistOutcome::Stored);
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        TOKEN_B,
        "the replacement token must be stored; the old one is revoked server-side"
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
fn not_found_on_the_session_path_means_no_active_plan_not_a_bad_key() {
    // THE F3 FIX. On the account-session path there IS no enrollment key, so `NOT_FOUND`
    // cannot mean "bad key". It comes from `_resolve_org_active_license_key`
    // (`devices/services.py:511-529`) and means the org has no currently-valid licence —
    // expired, not yet started, or never issued. Frame A6.
    //
    // Before this, a signed-in admin whose plan had lapsed was told to check their
    // enrollment key for typos — a key that path never uses and they may never have had.
    let transport = ScriptedTransport::responding(
        404,
        session_error("NOT_FOUND", "The requested resource was not found."),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(
        failure,
        ActivationFailure::NoActiveLicense,
        "NOT_FOUND on the session path is an expired/absent plan (A6), not a bad key (A4)"
    );
    assert_ne!(
        failure,
        ActivationFailure::UnknownKey,
        "telling a signed-in admin to check a key they never used is the bug this fixes"
    );

    // The copy the console renders must talk about the plan, not about a key.
    let rendered = failure.to_string();
    assert!(
        rendered.contains("plan"),
        "A6 copy should name the plan, got: {rendered}"
    );
    assert!(
        !rendered.contains("enrollment key"),
        "A6 copy must not mention an enrollment key, got: {rendered}"
    );
}

#[test]
fn not_found_on_the_enrollment_key_path_still_means_a_bad_key() {
    // The other half of the same fix: making the session path correct must not break the
    // path where NOT_FOUND genuinely does mean "that key is not recognised" (A4).
    let transport = ScriptedTransport::responding(
        404,
        rest_error("NOT_FOUND", "The requested resource was not found."),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new("SC-TRIAL-nope"), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::UnknownKey);
    let rendered = failure.to_string();
    assert!(
        rendered.contains("enrollment key"),
        "A4 copy should name the key, got: {rendered}"
    );
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
        401,
        session_error("UNAUTHENTICATED", "Authentication is required."),
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::Unauthenticated);
}

#[test]
fn a_member_account_is_refused_by_permission_not_by_policy() {
    // The server requires ADMIN to activate a device, and answers a MEMBER with
    // `403 PERMISSION_DENIED`. The instance limit is ALSO a 403, with `POLICY_DENIED`. The
    // two must stay apart: one is "your account may not do this", the other is "your plan
    // does not allow it", and the next step for the person differs.
    let member = LicensingClient::new(
        ScriptedTransport::responding(
            403,
            session_error(
                "PERMISSION_DENIED",
                "You do not have permission to perform this action.",
            ),
        ),
        BASE,
    );
    let at_limit = LicensingClient::new(
        ScriptedTransport::responding(
            403,
            session_error(
                "POLICY_DENIED",
                "The current policy does not allow this action.",
            ),
        ),
        BASE,
    );

    let member_failure = member
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    let limit_failure = at_limit
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(member_failure, ActivationFailure::PermissionDenied);
    assert_eq!(limit_failure, ActivationFailure::PolicyDenied);
    assert_ne!(member_failure, limit_failure);
    for failure in [&member_failure, &limit_failure] {
        assert!(!matches!(failure, ActivationFailure::Malformed(_)));
        assert!(failure.permits_presentation());
    }
}

#[test]
fn a_coded_session_refusal_is_classified_by_its_code_whatever_the_status() {
    // The code is authoritative; the status is not consulted when a coded body is present.
    // A 400 `VALIDATION_FAILED` and a 429 `RATE_LIMITED` are the two a native caller can
    // reach before any credential check.
    let invalid = LicensingClient::new(
        ScriptedTransport::responding(
            400,
            session_error("VALIDATION_FAILED", "The request is invalid."),
        ),
        BASE,
    );
    let failure = invalid
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    assert_eq!(failure, ActivationFailure::ValidationFailed);
    assert!(
        !matches!(failure, ActivationFailure::Malformed(_)),
        "a well-formed coded refusal must never be reported as contract drift"
    );

    let limited = LicensingClient::new(
        ScriptedTransport::responding(429, session_error("RATE_LIMITED", "Too many requests.")),
        BASE,
    );
    let failure = limited
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    assert_eq!(failure, ActivationFailure::RateLimited);
    assert!(failure.is_retryable());

    // The code wins over the status: a coded `NOT_FOUND` is believed even when the status
    // says 500, because the body is the application speaking and the status is not.
    let odd = LicensingClient::new(
        ScriptedTransport::responding(500, session_error("NOT_FOUND", "x")),
        BASE,
    );
    assert_eq!(
        odd.activate_with_session(&Token::new(SESSION), &identity(), &idem())
            .unwrap_err(),
        ActivationFailure::NoActiveLicense
    );
}

#[test]
fn a_proxy_error_page_on_the_session_path_is_classified_by_status() {
    // Positive control for the fallback: when the body is not a coded error at all — a
    // proxy error page — status classification must still apply.
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
    // This test was named for a 405 and fixtured with a 500, so it exercised the 5xx branch
    // and never the case it was named for — and the 4xx-with-HTML branch it was supposed to
    // cover did not exist: everything non-5xx fell through to `Malformed`, i.e. "the
    // contract drifted", which is the wrong thing to tell anyone about a middleware
    // rejection.
    let transport = ScriptedTransport::responding(
        405,
        "<html><head><title>405 Method Not Allowed</title></head><body></body></html>",
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::UnexpectedStatus(405));
    assert!(
        !matches!(failure, ActivationFailure::Malformed(_)),
        "an HTML error page is not contract drift"
    );
}

#[test]
fn an_html_403_is_reported_as_an_unexpected_status_not_as_contract_drift() {
    // The shape that 86ak5t1gw was: Django's CSRF middleware answering with an HTML 403.
    // The client no longer reaches that route, but a 403 page can still come from a
    // proxy or a WAF in front of the API, and it must still be said truthfully.
    let transport = ScriptedTransport::responding(
        403,
        "<html><body>CSRF verification failed. Request aborted.</body></html>",
    );
    let client = LicensingClient::new(transport, BASE);

    let failure = client
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();

    assert_eq!(failure, ActivationFailure::UnexpectedStatus(403));
}

#[test]
fn a_5xx_html_body_is_a_retryable_server_error() {
    // The branch the 405 test used to cover by accident, now covered on purpose.
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

// ---------------------------------------------------------------------------
// Sign-in failures: each is its own typed state, none is "Malformed"
// ---------------------------------------------------------------------------

fn sign_in_failure(status: u16, body: String) -> ActivationFailure {
    LicensingClient::new(ScriptedTransport::responding(status, body), BASE)
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .unwrap_err()
}

#[test]
fn a_wrong_password_is_invalid_credentials_not_an_expired_session() {
    // `POST /v1/sessions` answers an unknown email, a wrong password and a locked account
    // identically: `401 UNAUTHENTICATED`. The activation call answers an expired session
    // with the same code. Telling a person who has just typed a password that "the account
    // session is not valid" is wrong, so the two calls classify the code differently.
    let failure = sign_in_failure(
        401,
        sign_in_error("UNAUTHENTICATED", "Authentication is required."),
    );

    assert_eq!(failure, ActivationFailure::InvalidCredentials);
    assert_ne!(failure, ActivationFailure::Unauthenticated);
    assert!(!matches!(failure, ActivationFailure::Malformed(_)));
    assert!(
        failure.to_string().contains("password"),
        "the copy should talk about the password, got: {failure}"
    );
    assert!(
        !failure.is_retryable(),
        "retrying a wrong password is how accounts get locked"
    );
    assert!(failure.permits_presentation());

    // The other half: the SAME code on the activation call is still an expired session.
    let activation = LicensingClient::new(
        ScriptedTransport::responding(
            401,
            session_error("UNAUTHENTICATED", "Authentication is required."),
        ),
        BASE,
    )
    .activate_with_session(&Token::new(SESSION), &identity(), &idem())
    .unwrap_err();
    assert_eq!(activation, ActivationFailure::Unauthenticated);
}

#[test]
fn an_unverified_account_is_not_active_rather_than_over_its_plan_limit() {
    // `403 POLICY_DENIED` from sign-in means the password was right and the account is
    // unverified or disabled. The same code from activation means the plan's device limit
    // or an unactivatable licence, and "device limit reached" would be a baffling thing to
    // tell someone who has not yet confirmed their email address.
    let failure = sign_in_failure(
        403,
        sign_in_error(
            "POLICY_DENIED",
            "The current policy does not allow this action.",
        ),
    );

    assert_eq!(failure, ActivationFailure::AccountNotActive);
    assert_ne!(failure, ActivationFailure::PolicyDenied);
    assert!(
        failure.to_string().contains("verified"),
        "the copy should say what to do, got: {failure}"
    );
    assert!(!failure.is_retryable());
}

#[test]
fn the_other_sign_in_refusals_are_typed_too() {
    assert_eq!(
        sign_in_failure(
            400,
            sign_in_error("VALIDATION_FAILED", "The request is invalid.")
        ),
        ActivationFailure::ValidationFailed
    );

    let limited = sign_in_failure(429, sign_in_error("RATE_LIMITED", "Too many requests."));
    assert_eq!(limited, ActivationFailure::RateLimited);
    assert!(limited.is_retryable());

    // This route never answers NOT_FOUND. If it ever did, "your plan has lapsed" would be
    // the wrong reading of a failed sign-in, so it stays an uninterpreted coded refusal.
    let failure = sign_in_failure(404, sign_in_error("NOT_FOUND", "x"));
    assert_ne!(failure, ActivationFailure::NoActiveLicense);
    assert_ne!(failure, ActivationFailure::UnknownKey);
    assert!(
        matches!(failure, ActivationFailure::Coded(_)),
        "got {failure:?}"
    );

    assert_eq!(
        sign_in_failure(500, sign_in_error("INTERNAL", "x")),
        ActivationFailure::Server(500)
    );
}

#[test]
fn an_unreachable_platform_during_sign_in_is_unreachable() {
    let client = LicensingClient::new(ScriptedTransport::failing("dns error"), BASE);
    let failure = client
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .unwrap_err();
    assert!(matches!(failure, ActivationFailure::Unreachable(_)));
    assert!(failure.is_retryable());
}

// ---------------------------------------------------------------------------
// A response body is never quoted
// ---------------------------------------------------------------------------

/// Unique enough that it cannot appear in a failure's text by coincidence.
const LEAK: &str = "LEAK-MARKER-7f3a9c";

/// Every shape of "something other than the API's coded envelope" the client can meet on a
/// credential path, each carrying [`LEAK`]: Django's CSRF page (the original 86ak5t1gw
/// body), a proxy page, a captive portal answering 200, a WAF's JSON block, an envelope
/// whose `code` is free text, and a 200 whose fields have the wrong types.
fn hostile_responses() -> Vec<(&'static str, u16, String)> {
    vec![
        (
            "django csrf page",
            403,
            format!("<html><body><h1>Forbidden (403)</h1><p>CSRF verification failed. {LEAK}</p></body></html>"),
        ),
        ("proxy 502 page", 502, format!("<html>502 Bad Gateway {LEAK}</html>")),
        ("proxy 429 page", 429, format!("Too Many Requests {LEAK}")),
        ("captive portal answering 200", 200, format!("<html>Sign in to the wifi {LEAK}</html>")),
        ("waf json block", 403, format!(r#"{{"detail":"blocked {LEAK}","ray":"{LEAK}"}}"#)),
        (
            "envelope with a free-text code",
            403,
            format!(r#"{{"error":{{"code":"<html>{LEAK}</html>","message":"{LEAK}"}}}}"#),
        ),
        (
            "envelope with a code-shaped but oversized code",
            403,
            format!(r#"{{"error":{{"code":"{}","message":"{LEAK}"}}}}"#, "A".repeat(4000)),
        ),
        (
            "200 with a string where a bool belongs",
            200,
            format!(
                r#"{{"created":"{LEAK}","reminted":false,"activation_token":null,
                "device":{{"device_public_id":"d","status":"ACTIVE","platform":"p"}},
                "token":{{}},"license":{{"status":"ACTIVATED","expires_at":"x"}}}}"#
            ),
        ),
        ("200 with a truncated body", 200, format!(r#"{{"session_token":"{LEAK}"#)),
        ("200 with an empty body", 200, String::new()),
    ]
}

/// The three calls a credential travels in.
#[derive(Debug, Clone, Copy)]
enum Call {
    SignIn,
    ActivateWithSession,
    ActivateWithEnrollmentKey,
}

impl Call {
    const ALL: [Call; 3] = [
        Call::SignIn,
        Call::ActivateWithSession,
        Call::ActivateWithEnrollmentKey,
    ];

    /// Run this call against `client` and return the failure it must produce.
    fn run(self, client: &LicensingClient<ScriptedTransport>) -> ActivationFailure {
        match self {
            Call::SignIn => client
                .sign_in("admin@example.test", &Token::new("pw-LEAK-PASSWORD"))
                .unwrap_err(),
            Call::ActivateWithSession => client
                .activate_with_session(&Token::new(SESSION), &identity(), &idem())
                .unwrap_err(),
            Call::ActivateWithEnrollmentKey => client
                .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
                .unwrap_err(),
        }
    }
}

#[test]
fn no_failure_quotes_the_response_body_on_any_call() {
    // THE 86ak5t1gw REGRESSION CLASS. The user-visible symptom of the original defect was
    // an HTML page being classified; the lasting risk is that any such page, or any
    // attacker-influenced body, reaches an operator's screen or a log. Swept across all
    // three calls and every failure rendering a caller can obtain.
    let mut exercised = 0usize;
    for (label, status, body) in hostile_responses() {
        for call in Call::ALL {
            let client =
                LicensingClient::new(ScriptedTransport::responding(status, body.clone()), BASE);
            let failure = call.run(&client);
            let rendered = [format!("{failure}"), format!("{failure:?}")];
            for text in &rendered {
                for secret in [LEAK, "LEAK-PASSWORD", SESSION, ENROLLMENT_KEY] {
                    assert!(
                        !text.contains(secret),
                        "{call:?} on `{label}` put {secret:?} into a failure: {text}"
                    );
                }
                assert!(
                    text.len() < 600,
                    "{call:?} on `{label}` produced a {}-byte failure; a body is leaking in",
                    text.len()
                );
                assert!(
                    !text.contains("<html") && !text.contains("</"),
                    "{call:?} on `{label}` let markup into a failure: {text}"
                );
            }
            assert!(failure.permits_presentation());
            exercised += 1;
        }
    }
    assert_eq!(
        exercised,
        hostile_responses().len() * Call::ALL.len(),
        "the sweep covered fewer cases than it lists"
    );
}

#[test]
fn the_body_quoting_sweep_can_fail() {
    // Positive control for the sweep above: serde's own message DOES quote the value, so
    // forwarding `e.to_string()` is exactly what the sweep catches. If this stops being
    // true the sweep's premise is gone and it should be re-examined, not trusted.
    let body = format!(
        r#"{{"created":"{LEAK}","reminded":false,"activation_token":null,"device":{{}},"token":{{}},"license":{{}}}}"#
    );
    let raw = serde_json::from_str::<selahcue_licensing::contract::ActivationResponse>(&body)
        .unwrap_err()
        .to_string();
    assert!(
        raw.contains(LEAK),
        "serde no longer quotes the offending value ({raw}); re-derive what the sweep protects"
    );

    // ...and the client, handed that same body, does not forward it.
    let failure = LicensingClient::new(ScriptedTransport::responding(200, body), BASE)
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    match &failure {
        ActivationFailure::Malformed(why) => {
            assert!(!why.contains(LEAK), "{why}");
            assert!(
                why.contains("line 1"),
                "position is kept for diagnosis: {why}"
            );
        }
        other => panic!("expected Malformed, got {other:?}"),
    }
}

#[test]
fn a_missing_field_is_named_because_the_name_comes_from_this_crate() {
    // The one piece of a parse error that IS worth keeping: which field the contract
    // expected. It comes from our own struct definitions, never from the body.
    let failure = LicensingClient::new(
        ScriptedTransport::responding(
            200,
            r#"{"expires_at":"x","role":"ADMIN","org_id":"o","surface":"desktop"}"#,
        ),
        BASE,
    )
    .sign_in("admin@example.test", &Token::new("correct-horse"))
    .unwrap_err();

    match failure {
        ActivationFailure::Malformed(why) => assert!(why.contains("`session_token`"), "{why}"),
        other => panic!("expected Malformed, got {other:?}"),
    }
}

#[test]
fn an_unknown_code_from_a_proxy_is_reported_as_unrecognised_not_echoed() {
    let failure = LicensingClient::new(
        ScriptedTransport::responding(
            403,
            format!(r#"{{"error":{{"code":"<html>{LEAK}</html>"}}}}"#),
        ),
        BASE,
    )
    .activate_with_session(&Token::new(SESSION), &identity(), &idem())
    .unwrap_err();

    match &failure {
        ActivationFailure::Coded(code) => assert_eq!(code.as_str(), "UNRECOGNISED"),
        other => panic!("expected a Coded refusal, got {other:?}"),
    }
    assert!(!failure.to_string().contains(LEAK));
}

// ---------------------------------------------------------------------------
// Bounded: a response over the cap is refused unparsed
// ---------------------------------------------------------------------------

// The premise, pinned at compile time so changing a cap cannot quietly turn the tests below
// vacuous: the parse cap must sit BELOW the transport's read cap (it is the tighter bound),
// and above the largest legitimate body by a wide margin.
const _: () =
    assert!(MAX_RESPONSE_BODY_BYTES < selahcue_cloud::transport::MAX_TRANSPORT_RESPONSE_BYTES);
const _: () = assert!(MAX_RESPONSE_BODY_BYTES >= 16 * 1024);

#[test]
fn a_success_body_over_the_cap_is_refused_and_one_at_the_cap_is_not() {
    // Whitespace padding after a COMPLETE, valid body: the only thing that differs between
    // the two cases is the length, so a refusal can only be the cap. (Without the positive
    // control, "refused" would be indistinguishable from "this fixture never parsed".)
    let valid = session_activation_body(true, false, Some(TOKEN_A));
    let padded = |total: usize| format!("{valid}{}", " ".repeat(total - valid.len()));

    let at_cap = padded(MAX_RESPONSE_BODY_BYTES);
    assert_eq!(at_cap.len(), MAX_RESPONSE_BODY_BYTES);
    LicensingClient::new(ScriptedTransport::responding(200, at_cap), BASE)
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .expect("a body exactly at the cap is still read: the cap must not truncate");

    let over = padded(MAX_RESPONSE_BODY_BYTES + 1);
    let failure = LicensingClient::new(ScriptedTransport::responding(200, over), BASE)
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    match &failure {
        ActivationFailure::Malformed(why) => {
            assert!(why.contains("larger than"), "{why}");
            assert!(!why.contains(TOKEN_A), "{why}");
        }
        other => panic!("an over-cap body must be refused as Malformed, got {other:?}"),
    }
}

#[test]
fn an_error_body_over_the_cap_is_classified_by_status_without_being_parsed() {
    // A perfectly good coded envelope, padded past the cap. If it were parsed, the code
    // would win (`PERMISSION_DENIED`); refused unparsed, only the status is left.
    let envelope = session_error(
        "PERMISSION_DENIED",
        "You do not have permission to perform this action.",
    );
    let at_cap = format!(
        "{envelope}{}",
        " ".repeat(MAX_RESPONSE_BODY_BYTES - envelope.len())
    );
    let over = format!("{at_cap} ");

    let read = LicensingClient::new(ScriptedTransport::responding(403, at_cap), BASE)
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    assert_eq!(
        read,
        ActivationFailure::PermissionDenied,
        "positive control: at the cap the code is read"
    );

    let refused = LicensingClient::new(ScriptedTransport::responding(403, over), BASE)
        .activate_with_session(&Token::new(SESSION), &identity(), &idem())
        .unwrap_err();
    assert_eq!(refused, ActivationFailure::UnexpectedStatus(403));

    let refused_5xx = LicensingClient::new(
        ScriptedTransport::responding(503, "x".repeat(MAX_RESPONSE_BODY_BYTES + 1)),
        BASE,
    )
    .sign_in("admin@example.test", &Token::new("correct-horse"))
    .unwrap_err();
    assert_eq!(refused_5xx, ActivationFailure::Server(503));
}

// ---------------------------------------------------------------------------
// The native client has no cookie and no CSRF ceremony, and never targets /graphql
// ---------------------------------------------------------------------------

#[test]
fn every_request_goes_to_a_cookie_free_v1_route_and_carries_no_browser_ceremony() {
    let transport = ScriptedTransport::new();
    transport.push_response(200, session_body());
    transport.push_response(200, session_activation_body(true, false, Some(TOKEN_A)));
    transport.push_response(200, rest_body(true, false, Some(TOKEN_B)));
    let client = LicensingClient::new(transport, BASE);

    let session = client
        .sign_in("admin@example.test", &Token::new("correct-horse"))
        .unwrap();
    client
        .activate_with_session(&session.token, &identity(), &idem())
        .unwrap();
    client
        .activate_with_enrollment_key(&Token::new(ENROLLMENT_KEY), &identity(), &idem())
        .unwrap();

    let sent = client.transport().recorded();
    assert_eq!(sent.len(), 3);
    for request in &sent {
        assert_eq!(request.method, "POST");
        assert!(
            request.url.starts_with(&format!("{BASE}/v1/")),
            "{} is not on the /v1 device surface",
            request.url
        );
        assert!(
            !request.url.contains("graphql"),
            "{} targets a GraphQL route",
            request.url
        );
    }
    // The transport seam is `post_json(url, body, bearer)`: a bearer is the ONLY header the
    // client can influence, so there is no cookie, CSRF token, Origin or Referer to send.
    // Recorded as a flag, so this asserts WHICH calls carry the one credential header.
    assert_eq!(
        sent.iter().map(|r| r.had_bearer).collect::<Vec<_>>(),
        [false, true, false],
        "sign-in and the key path carry no Authorization; the session activation carries it"
    );
}

#[test]
fn the_source_names_no_cookie_csrf_origin_or_graphql_route() {
    // The seam already cannot carry these; this makes the absence a tripwire for whoever
    // widens the seam or adds a second transport. Comment lines are skipped because the docs
    // deliberately NAME these things to explain their absence (and a guard silenced by
    // deleting a comment would be measuring the wrong thing).
    const FORBIDDEN: &[&str] = &[
        "graphql",
        "cookie",
        "csrf",
        "x-csrftoken",
        "referer",
        "origin:",
        "\"origin\"",
    ];
    let src = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut scanned = 0usize;
    let mut saw_sessions_route = false;
    for entry in std::fs::read_dir(&src).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_none_or(|e| e != "rs") {
            continue;
        }
        scanned += 1;
        let body = std::fs::read_to_string(&path).unwrap();
        for (lineno, line) in body.lines().enumerate() {
            let code = line.trim_start();
            if code.starts_with("//") {
                continue;
            }
            let code = code.split("//").next().unwrap_or("").to_lowercase();
            saw_sessions_route |= code.contains("\"/v1/sessions\"");
            for pattern in FORBIDDEN {
                assert!(
                    !code.contains(pattern),
                    "{}:{} names {pattern:?}; the native client must not take part in the \
                     browser's cookie/CSRF surface (86ak5t1gw):\n  {code}",
                    path.display(),
                    lineno + 1
                );
            }
        }
    }
    assert_eq!(scanned, 9, "expected to scan 9 modules, scanned {scanned}");
    assert!(
        saw_sessions_route,
        "the scan never saw the sign-in route, so it was not reading the right files"
    );
}
