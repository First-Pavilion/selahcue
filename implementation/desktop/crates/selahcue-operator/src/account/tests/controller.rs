use std::{path::Path, sync::Arc};

use selahcue_licensing::{
    InMemorySecretStore, LicensingClient, RecordedRequest, SecretError, SecretStore, Token,
    TrustedKeys, ACCOUNT_SESSION_NAME, DEVICE_TOKEN_NAME,
};
use serde_json::{json, Value};

use crate::account::{
    controller::{AccountController, Command, Time, API_ORIGIN},
    state::{AccountMetadataStore, CredentialPresence},
    AccountView,
};

const DEVICE: &str = "dev_0123456789abcdef0123456789abcdef";
const SECRET: &str = "synthetic-show-once-device-token";
const SESSION: &str = "synthetic-account-session-token";
const PASSWORD: &str = "synthetic-password-never-exposed";
const ENROLLMENT: &str = "synthetic-enrollment-never-exposed";
const NOW: Time = (1_794_672_000, 123_456_789);

#[derive(Clone, Default)]
struct Custody {
    store: Arc<InMemorySecretStore>,
    fail_write: Arc<std::sync::atomic::AtomicBool>,
    denied_device_writes: Arc<std::sync::atomic::AtomicUsize>,
    fail_session_write: Arc<std::sync::atomic::AtomicBool>,
    fail_remove: Arc<std::sync::atomic::AtomicBool>,
}

impl SecretStore for Custody {
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
        self.store.get(name)
    }

    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
        if name == DEVICE_TOKEN_NAME && self.fail_write.load(std::sync::atomic::Ordering::SeqCst) {
            self.denied_device_writes
                .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            return Err(SecretError("synthetic keyring denial".into()));
        }
        if name == ACCOUNT_SESSION_NAME
            && self
                .fail_session_write
                .load(std::sync::atomic::Ordering::SeqCst)
        {
            return Err(SecretError("synthetic session write denial".into()));
        }
        self.store.set(name, token)
    }

    fn remove(&self, name: &str) -> Result<(), SecretError> {
        if name == ACCOUNT_SESSION_NAME
            && self.fail_remove.load(std::sync::atomic::Ordering::SeqCst)
        {
            return Err(SecretError("synthetic delete denial".into()));
        }
        self.store.remove(name)
    }
}

// Script the real response shape while echoing the generated, on-disk operation
// nonce. Individual protocol failure tests can inject an explicit bad echo.
struct ScriptedTransport(selahcue_licensing::ScriptedTransport);
impl ScriptedTransport {
    fn new() -> Self {
        Self(selahcue_licensing::ScriptedTransport::new())
    }
    fn responding(status: u16, body: impl Into<String>) -> Self {
        Self(selahcue_licensing::ScriptedTransport::responding(
            status, body,
        ))
    }
    fn push_response(&self, status: u16, body: impl Into<String>) -> &Self {
        self.0.push_response(status, body);
        self
    }
    fn push_failure(&self, reason: impl Into<String>) -> &Self {
        self.0.push_failure(reason);
        self
    }
    fn request_count(&self) -> usize {
        self.0.request_count()
    }
    fn request(&self, index: usize) -> Option<RecordedRequest> {
        self.0.request(index)
    }
    fn recorded(&self) -> Vec<RecordedRequest> {
        self.0.recorded()
    }
}
impl selahcue_licensing::HttpTransport for ScriptedTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_licensing::TransportError> {
        let mut response = self.0.post_json(url, body, bearer)?;
        if url.contains("/v1/activations:bound") {
            if let Ok(mut payload) = serde_json::from_str::<Value>(&response.body) {
                if payload["fixture_echo"] == true {
                    let request: Value = serde_json::from_str(body).expect("native request");
                    payload
                        .as_object_mut()
                        .expect("response")
                        .remove("fixture_echo");
                    payload["operation_version"] = json!(1);
                    payload["idempotency_key"] = request["idempotency_key"].clone();
                    payload["operation_state"] = json!(if payload["activation_token"].is_null() {
                        "replay"
                    } else {
                        "completed"
                    });
                    response.body = payload.to_string();
                } else if payload["completed_activation"]["idempotency_key"] == "fixture_nonce" {
                    let request: Value = serde_json::from_str(body).expect("native request");
                    payload["completed_activation"]["idempotency_key"] =
                        request["idempotency_key"].clone();
                    response.body = payload.to_string();
                }
            }
        }
        Ok(response)
    }
    fn get(
        &self,
        url: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_licensing::TransportError> {
        self.0.get(url, bearer)
    }
}

fn controller(directory: &Path, custody: Custody) -> AccountController<ScriptedTransport, Custody> {
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    AccountController::new(
        Some(directory.to_path_buf()),
        client,
        custody,
        TrustedKeys::new(),
        || NOW,
    )
}

fn sign_in() -> Command {
    Command::SignIn {
        email: "fixture@example.test".into(),
        password: Token::new(PASSWORD),
        display_name: "Booth".into(),
    }
}

fn enroll() -> Command {
    Command::Enroll {
        key: Token::new(ENROLLMENT),
        display_name: "Booth".into(),
    }
}

fn session_json() -> String {
    json!({
        "session_token": SESSION,
        "expires_at": "2027-01-01T00:00:00Z",
        "role": "ADMIN",
        "org_id": "org_fixture"
    })
    .to_string()
}

fn activated(token: Option<&str>, reminted: bool) -> String {
    json!({
        "fixture_echo": true,
        "created": token.is_some() && !reminted,
        "reminted": reminted,
        "activation_token": token,
        "device": {"device_public_id": DEVICE, "status": "ACTIVE", "platform": std::env::consts::OS},
        "token": {},
        "license": {"status": "ACTIVATED", "expires_at": "2027-01-01T00:00:00Z"}
    })
    .to_string()
}

fn wire(view: &AccountView) -> Value {
    let wire = serde_json::to_value(view).expect("serializable safe projection");
    let text = wire.to_string();
    for secret in [SECRET, SESSION, PASSWORD, ENROLLMENT] {
        assert!(!text.contains(secret));
    }
    wire
}

#[test]
fn untouched_install_is_local_even_on_foreground_and_skip() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let mut account = controller(dir.path(), Custody::default());
    let first = wire(&account.execute(Command::Startup));
    assert_eq!(first["setup_state"], "needed");
    assert_eq!(
        wire(&account.execute(Command::Refresh { explicit: false }))["setup_state"],
        "needed"
    );
    let worker =
        crate::account::controller::Worker::new(controller(dir.path(), Custody::default()));
    let skipped = wire(&worker.skip_setup().expect("durable Skip"));
    assert_eq!(skipped["setup_state"], "skipped");
    assert_eq!(account.client().transport().request_count(), 0);
    assert_eq!(
        wire(&account.execute(Command::Refresh { explicit: false }))["setup_state"],
        "skipped"
    );
    assert_eq!(account.client().transport().request_count(), 0);
    let mut restarted = controller(dir.path(), Custody::default());
    assert_eq!(
        wire(&restarted.execute(Command::Startup))["setup_state"],
        "skipped"
    );
    assert_eq!(restarted.client().transport().request_count(), 0);
}

#[test]
fn session_activation_saves_before_cleanup_and_survives_network_loss() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("offline after activation");
    let view = wire(&account.execute(sign_in()));
    assert_eq!(view["setup_state"], "completed");
    assert_eq!(view["entitlement_state"], "unavailable");
    assert_eq!(view["pending_cleanup"], false);
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("read fixture"),
        Some(Token::new(SECRET))
    );
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("read fixture")
        .is_none());
    let requests = account.client().transport().recorded();
    for (request, path) in requests.iter().zip([
        "/v1/sessions",
        "/v1/activations:bound-with-session",
        "/v1/sessions:revoke",
        "/v1/license:refresh",
    ]) {
        assert_eq!(request.url, format!("{API_ORIGIN}{path}"));
    }
    let metadata = AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Present)
        .expect("metadata");
    assert_eq!(metadata.activated_public_id.as_deref(), Some(DEVICE));
    assert!(metadata.pending_activation().is_none());
}

#[test]
fn lost_enrollment_response_reuses_frozen_request_after_restart() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account.client().transport().push_failure("lost reply");
    assert_eq!(
        wire(&account.execute(enroll()))["operation_state"],
        "retry_pending"
    );
    let first = account
        .client()
        .transport()
        .request(0)
        .expect("enrollment request");
    let mut restarted = controller(dir.path(), custody);
    assert_eq!(
        wire(&restarted.execute(Command::RetryActivation))["error_code"],
        "enrollment_key_required"
    );
    assert_eq!(restarted.client().transport().request_count(), 0);
    restarted
        .client()
        .transport()
        .push_response(200, activated(None, false));
    let replay = wire(&restarted.execute(enroll()));
    assert_eq!(replay["device_state"], "credential_missing");
    assert_eq!(replay["error_code"], "device_recovery_required");
    let second = restarted
        .client()
        .transport()
        .request(0)
        .expect("retry request");
    assert!(first == second, "retry must preserve the full request");
}

#[test]
fn failed_remint_save_does_not_revoke_session_or_accept_old_token() {
    let dir = tempfile::tempdir().expect("fixture directory");
    AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Missing)
        .expect("install ID");
    let custody = Custody::default();
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new("old-expired-token"))
        .expect("old token");
    custody
        .fail_write
        .store(true, std::sync::atomic::Ordering::SeqCst);
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, activated(Some(SECRET), true));
    let failed = wire(&account.execute(sign_in()));
    assert_eq!(failed["device_state"], "credential_not_saved");
    assert_eq!(failed["operation_state"], "retry_pending");
    assert_eq!(account.client().transport().request_count(), 2);
    assert_eq!(
        custody.get(ACCOUNT_SESSION_NAME).expect("read fixture"),
        Some(Token::new(SESSION))
    );
    let metadata = AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Present)
        .expect("metadata");
    assert_eq!(metadata.activated_public_id.as_deref(), Some(DEVICE));
    assert!(metadata.pending_activation().is_some());

    custody
        .fail_write
        .store(false, std::sync::atomic::Ordering::SeqCst);
    account
        .client()
        .transport()
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("offline after save retry");
    let retried = wire(&account.execute(Command::RetryActivation));
    assert_eq!(retried["setup_state"], "completed");
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("read fixture"),
        Some(Token::new(SECRET))
    );
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("read fixture")
        .is_none());
    assert_eq!(account.client().transport().request_count(), 4);
}

#[test]
fn session_cleanup_retry_never_touches_device_token() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, activated(Some(SECRET), false))
        .push_failure("cleanup offline")
        .push_failure("refresh offline")
        .push_response(200, r#"{"revoked":true}"#);
    let first = wire(&account.execute(sign_in()));
    assert_eq!(first["setup_state"], "completed");
    assert_eq!(first["pending_cleanup"], true);
    let cleaned = wire(&account.execute(Command::RetryCleanup));
    assert_eq!(cleaned["pending_cleanup"], false);
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("read fixture"),
        Some(Token::new(SECRET))
    );
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("read fixture")
        .is_none());
}

fn refresh_status(valid: bool) -> String {
    json!({
        "device": {"device_public_id": DEVICE, "status": "ACTIVE"},
        "license": {
            "status": if valid {"ACTIVATED"} else {"EXPIRED"},
            "starts_at": "2026-10-01T00:00:00Z",
            "expires_at": "2027-01-01T00:00:00Z",
            "valid_now": valid
        },
        "instances": {"used": 99, "limit": 99},
        "token": {"expires_at": "2027-01-01T00:00:00Z"}
    })
    .to_string()
}

fn signed_display(
    fingerprint: &str,
    issued: &str,
    expires: &str,
    license_expires: &str,
) -> (TrustedKeys, String) {
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
    use ed25519_dalek::{Signer, SigningKey};
    let key = SigningKey::from_bytes(&[77; 32]);
    let mut trust = TrustedKeys::new();
    let key_id = trust
        .insert(key.verifying_key().to_bytes())
        .expect("fixture trust");
    let payload = URL_SAFE_NO_PAD.encode(
        json!({
            "entitlement_version": 1,
            "device_public_id": DEVICE,
            "device_fingerprint": fingerprint,
            "issued_at": issued,
            "not_before": issued,
            "expires_at": expires,
            "license_expires_at": license_expires,
            "plan_display_label": "Signed fixture plan",
            "instances_used": 1,
            "instances_limit": 2,
            "grants": {}
        })
        .to_string(),
    );
    let signature = URL_SAFE_NO_PAD.encode(key.sign(payload.as_bytes()).to_bytes());
    let wire = json!({
        "envelope_version": 1, "alg": "Ed25519", "key_id": key_id,
        "payload": payload, "signature": signature
    });
    (trust, wire.to_string())
}

#[test]
fn enrollment_and_renewal_reopen_signed_cache_from_disk_without_using_unsigned_seats() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let identity = AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Missing)
        .expect("stable identity");
    let (trust, manifest) = signed_display(
        identity.fingerprint(),
        "2026-11-14T16:00:00Z",
        "2026-11-15T16:00:00Z",
        "2026-11-15T16:00:00Z",
    );
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        custody.clone(),
        trust.clone(),
        || NOW,
    );
    account
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, refresh_status(true))
        .push_response(200, manifest);
    let activated = wire(&account.execute(enroll()));
    assert_eq!(activated["entitlement_state"], "current");
    assert_eq!(activated["plan_label"], "Signed fixture plan");
    assert_eq!(activated["instances_used"], 1);
    assert_eq!(activated["instance_limit"], 2);
    assert_eq!(
        activated["last_checked_at"],
        "2026-11-14T16:00:00.123456789Z"
    );
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    let mut restarted =
        AccountController::new(Some(dir.path().into()), client, custody, trust, || NOW);
    assert_eq!(
        wire(&restarted.execute(Command::Startup))["entitlement_state"],
        "current"
    );
    assert_eq!(restarted.client().transport().request_count(), 0);
    restarted.client().transport().push_failure("offline");
    let stale = wire(&restarted.execute(Command::Refresh { explicit: false }));
    assert_eq!(stale["entitlement_state"], "current");
    assert!(stale.get("error_code").is_none());
    restarted.client().transport().push_failure("offline");
    let explicit = wire(&restarted.execute(Command::Refresh { explicit: true }));
    assert_eq!(explicit["entitlement_state"], "current");
    assert_eq!(explicit["error_code"], "network_unavailable");
}

#[test]
fn restart_keeps_expired_or_future_signed_cache_stale_offline_and_omits_untrusted_plan() {
    use selahcue_licensing::EntitlementCache;
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let storage = AccountMetadataStore::new(dir.path().into());
    let mut identity = storage
        .load_or_create(CredentialPresence::Missing)
        .expect("install ID");
    identity.activated_public_id = Some(DEVICE.into());
    let identity = storage.save(&identity).expect("bound identity");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("saved token");
    let cache = EntitlementCache::new(dir.path());

    for (issued, expires, expected) in [
        (
            "2026-11-01T00:00:00Z",
            "2026-11-14T16:00:00.123456789Z",
            "expired",
        ),
        (
            "2026-11-14T16:02:00.123456790Z",
            "2026-11-15T16:00:00Z",
            "future_or_clock_skew",
        ),
    ] {
        let (trust, signed) = signed_display(
            identity.fingerprint(),
            issued,
            expires,
            "2027-01-01T00:00:00Z",
        );
        cache
            .replace(signed.as_bytes(), &trust, DEVICE, identity.fingerprint())
            .expect("signed cache");
        let client =
            LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
        let mut restarted = AccountController::new(
            Some(dir.path().into()),
            client,
            custody.clone(),
            trust,
            || NOW,
        );
        assert_eq!(
            wire(&restarted.execute(Command::Startup))["entitlement_state"],
            expected
        );
        let before = std::fs::read(cache.path()).expect("cache bytes");
        restarted.client().transport().push_failure("offline");
        let stale = wire(&restarted.execute(Command::Refresh { explicit: false }));
        assert_eq!(stale["entitlement_state"], expected);
        assert_eq!(stale["error_code"], "network_unavailable");
        assert_eq!(
            std::fs::read(cache.path()).expect("preserved cache"),
            before
        );
    }
    let mut unknown_signer = controller(dir.path(), custody);
    let view = wire(&unknown_signer.execute(Command::Startup));
    assert_eq!(view["entitlement_state"], "unavailable");
    assert!(view.get("plan_label").is_none());
}

#[test]
fn license_and_manifest_expire_independently() {
    use selahcue_licensing::EntitlementCache;
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let storage = AccountMetadataStore::new(dir.path().into());
    let mut identity = storage
        .load_or_create(CredentialPresence::Missing)
        .expect("install ID");
    identity.activated_public_id = Some(DEVICE.into());
    let identity = storage.save(&identity).expect("bound identity");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("saved token");
    let (trust, signed) = signed_display(
        identity.fingerprint(),
        "2026-11-01T00:00:00Z",
        "2026-11-15T16:00:00Z",
        "2026-11-14T16:00:00.123456789Z",
    );
    EntitlementCache::new(dir.path())
        .replace(signed.as_bytes(), &trust, DEVICE, identity.fingerprint())
        .expect("signed cache");
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    let mut account =
        AccountController::new(Some(dir.path().into()), client, custody, trust, || NOW);
    let view = wire(&account.execute(Command::Startup));
    assert_eq!(view["entitlement_state"], "current");
    assert_eq!(view["license_state"], "renewal_needed");
}

#[test]
fn exact_clock_policy_tolerates_only_two_minutes_of_future_lower_boundaries() {
    use crate::account::controller::temporal_state;
    let past = (NOW.0 - 1, 0);
    let expiry = (NOW.0 + 3600, 0);
    for (lower, expected) in [
        ((NOW.0 + 120, NOW.1 - 1), "current"),
        ((NOW.0 + 120, NOW.1), "current"),
        ((NOW.0 + 120, NOW.1 + 1), "future_or_clock_skew"),
        ((NOW.0 + 100_000, 0), "future_or_clock_skew"),
    ] {
        for (issued, not_before) in [(lower, past), (past, lower)] {
            assert_eq!(
                json!(temporal_state(issued, not_before, expiry, NOW)),
                expected
            );
        }
    }
    for (now, expected) in [
        ((expiry.0 - 1, 999_999_999), "current"),
        (expiry, "expired"),
        ((expiry.0, 1), "expired"),
        ((i64::MAX - 120, 0), "expired"),
        ((i64::MAX - 119, 0), "future_or_clock_skew"),
        ((i64::MIN, 0), "future_or_clock_skew"),
    ] {
        assert_eq!(json!(temporal_state(past, past, expiry, now)), expected);
    }
}

#[test]
fn in_flight_account_work_admits_no_second_mutation_and_publishes_newer_view() {
    use crate::account::controller::Worker;
    let dir = tempfile::tempdir().expect("fixture directory");
    let worker = Worker::new(controller(dir.path(), Custody::default()));
    let first = worker
        .admit()
        .unwrap_or_else(|_| panic!("admit first request"));
    let second = worker.admit().err().expect("duplicate rejected");
    assert_eq!(wire(&second)["operation_state"], "busy");
    assert_eq!(worker.view().revision, second.revision);
    let finished = first.run(Command::Startup);
    assert!(finished.revision > second.revision);
    assert_eq!(wire(&worker.view())["setup_state"], "needed");
    let next = worker
        .admit()
        .unwrap_or_else(|_| panic!("admit next request"));
    let pending = worker.view();
    assert!(pending.revision > finished.revision);
    let done = next.run(Command::Startup);
    assert!(done.revision > pending.revision);
    assert_eq!(worker.view().revision, done.revision);
}

#[test]
fn invalid_sign_in_does_not_freeze_a_new_activation_path() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let mut account = controller(dir.path(), Custody::default());
    account
        .client()
        .transport()
        .push_response(401, r#"{"error":{"code":"UNAUTHENTICATED"}}"#)
        .push_response(200, activated(Some(SECRET), false))
        .push_failure("offline after enrollment");
    assert_eq!(
        wire(&account.execute(sign_in()))["error_code"],
        "invalid_credentials"
    );
    assert_eq!(wire(&account.execute(enroll()))["setup_state"], "completed");
}

/// Run only with the synthetic Django live server assembler in
/// implementation/api/tests/test_native_account_controller_integration.py.
#[test]
#[ignore = "requires the disposable Django G1 integration fixture"]
fn django_g1_real_api() {
    use selahcue_cloud::{
        transport::{HttpResponse, ReqwestTransport},
        HttpTransport, TransportError,
    };
    use std::{
        io::{self, BufRead, Write},
        sync::atomic::{AtomicBool, Ordering},
    };

    // Only the test transport can inspect the show-once answer. Store a redacted
    // Token for comparisons on delivered answers; discard lost answers immediately.
    #[derive(Default)]
    struct StaffRefresh {
        public_id: String,
        original: Option<Token>,
        replacement: Option<Token>,
        lose_reply: bool,
        dropped: bool,
        calls: Vec<RefreshCall>,
        manifests_with_saved_replacement: Vec<bool>,
    }

    struct RefreshCall {
        capable: bool,
        original: bool,
        replacement: bool,
        status: u16,
        issued: bool,
    }

    impl StaffRefresh {
        fn observe(&mut self, body: &str, bearer: Option<&str>, response: &HttpResponse) -> bool {
            let request: Value = serde_json::from_str(body).expect("refresh request");
            let answer: Value =
                serde_json::from_str(&response.body).expect("live API refresh response");
            let sent = bearer.map(Token::new);
            let issued = answer["activation_token"].as_str().map(Token::new);
            self.calls.push(RefreshCall {
                capable: request == json!({"token_rotation": "staff-extension-v1"}),
                original: sent.is_some() && sent == self.original,
                replacement: sent.is_some() && sent == self.replacement,
                status: response.status,
                issued: issued.is_some(),
            });
            if let Some(token) = issued {
                assert_eq!(response.status, 200);
                assert_eq!(
                    answer["device"]["device_public_id"].as_str(),
                    Some(self.public_id.as_str())
                );
                assert_eq!(answer["license"]["valid_now"], true);
                assert!(answer["token"]["expires_at"].is_string());
                assert_eq!(
                    answer["token"]["expires_at"],
                    answer["license"]["expires_at"]
                );
                assert!(!token.is_blank() && !token.has_control_characters());
                assert!(Some(&token) != self.original.as_ref());
                if self.lose_reply && !self.dropped {
                    self.dropped = true;
                    return true;
                }
                self.replacement = Some(token);
            }
            false
        }
    }

    struct Wire {
        inner: ReqwestTransport,
        custody: Custody,
        directory: std::path::PathBuf,
        offline: Arc<AtomicBool>,
        expected_remint: Arc<AtomicBool>,
        lose_initial_reply: Arc<AtomicBool>,
        staff: Arc<std::sync::Mutex<StaffRefresh>>,
    }

    impl HttpTransport for Wire {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if self.offline.load(Ordering::SeqCst) {
                return Err(TransportError("synthetic network unavailable".into()));
            }
            if url.ends_with("/v1/sessions:revoke") {
                let device_present = self
                    .custody
                    .get(DEVICE_TOKEN_NAME)
                    .expect("fixture custody")
                    .is_some();
                assert!(
                    device_present
                        || matches!(
                            std::env::var("SELAHCUE_G1_SCENARIO").as_deref(),
                            Ok("initial-restart" | "lost-initial")
                        )
                );
                let metadata = AccountMetadataStore::new(self.directory.clone())
                    .load_or_create(CredentialPresence::Present)
                    .expect("persisted device binding before revoke");
                assert!(metadata.activated_public_id.is_some());
                assert!(metadata.pending_activation().is_none());
            }
            if url.ends_with("/v1/activations:bound-with-session")
                && self
                    .staff
                    .lock()
                    .expect("staff refresh trace lock poisoned")
                    .lose_reply
            {
                let request: Value = serde_json::from_str(body).expect("generic sign-in request");
                assert_ne!(
                    request["operation_version"], 2,
                    "generic sign-in or Retry requested credential replacement"
                );
            }
            let response = self.inner.post_json(url, body, bearer)?;
            if url.ends_with("/v1/license:refresh") {
                let mut staff = self
                    .staff
                    .lock()
                    .expect("staff refresh trace lock poisoned");
                if staff.original.is_some() && staff.observe(body, bearer, &response) {
                    return Err(TransportError(
                        "lost committed staff refresh response".into(),
                    ));
                }
            }
            if url.ends_with("/v1/activations:bound-with-session")
                && self.lose_initial_reply.swap(false, Ordering::SeqCst)
            {
                assert_eq!(response.status, 200);
                return Err(TransportError("synthetic lost activation answer".into()));
            }
            if (url.ends_with("/v1/activations:bound")
                || url.ends_with("/v1/activations:bound-with-session"))
                && response.status == 200
                && self.expected_remint.swap(false, Ordering::SeqCst)
            {
                let parsed: Value =
                    serde_json::from_str(&response.body).expect("activation response fixture");
                assert_eq!(parsed["created"], false);
                assert_eq!(parsed["reminted"], true);
                assert!(parsed["activation_token"].is_string());
                let scenario = std::env::var("SELAHCUE_G1_SCENARIO").unwrap_or_default();
                if scenario.starts_with("race-") {
                    let request: Value = serde_json::from_str(body).expect("frozen request");
                    let retry_wire = Wire {
                        inner: ReqwestTransport::new_for_loopback_tests().expect("retry HTTP"),
                        custody: self.custody.clone(),
                        directory: self.directory.clone(),
                        offline: Arc::new(AtomicBool::new(scenario == "race-loss")),
                        expected_remint: Arc::new(AtomicBool::new(false)),
                        lose_initial_reply: Arc::new(AtomicBool::new(false)),
                        staff: self.staff.clone(),
                    };
                    let base = std::env::var("SELAHCUE_G1_FIXTURE_URL").expect("base");
                    let client =
                        LicensingClient::new_for_loopback_tests(retry_wire, &base).expect("client");
                    let mut retry = AccountController::new(
                        Some(self.directory.clone()),
                        client,
                        self.custody.clone(),
                        TrustedKeys::new(),
                        crate::account::controller::system_time,
                    );
                    let result = wire(&retry.execute(Command::Enroll {
                        key: Token::new(request["license_key"].as_str().expect("enrollment proof")),
                        display_name: "ignored on retry".into(),
                    }));
                    assert_eq!(result["operation_state"], "retry_pending");
                    assert_eq!(
                        result["error_code"],
                        if scenario == "race-loss" {
                            "network_unavailable"
                        } else {
                            "device_recovery_required"
                        }
                    );
                }
            }
            Ok(response)
        }

        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            if self.offline.load(Ordering::SeqCst) {
                return Err(TransportError("synthetic network unavailable".into()));
            }
            if url.ends_with("/v1/entitlements/manifest") {
                let mut staff = self
                    .staff
                    .lock()
                    .expect("staff refresh trace lock poisoned");
                if staff.original.is_some() {
                    let sent = bearer.map(Token::new);
                    let saved = self
                        .custody
                        .get(DEVICE_TOKEN_NAME)
                        .expect("custody at manifest GET");
                    let matches = sent.is_some() && sent == staff.replacement && sent == saved;
                    staff.manifests_with_saved_replacement.push(matches);
                }
            }
            self.inner.get(url, bearer)
        }
    }

    fn checkpoint(input: &mut impl BufRead, marker: &str) {
        println!("G1 {marker}");
        io::stdout().flush().expect("checkpoint flush");
        let mut command = String::new();
        input.read_line(&mut command).expect("fixture control");
        assert!(
            command.trim() == "continue",
            "integration fixture did not acknowledge checkpoint"
        );
    }

    let base = std::env::var("SELAHCUE_G1_FIXTURE_URL").expect("loopback fixture URL");
    let scenario = std::env::var("SELAHCUE_G1_SCENARIO").expect("fixture scenario");
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let offline = Arc::new(AtomicBool::new(false));
    let expected_remint = Arc::new(AtomicBool::new(false));
    let lose_initial_reply = Arc::new(AtomicBool::new(false));
    let staff = Arc::new(std::sync::Mutex::new(StaffRefresh::default()));
    let synthetic_seed: [u8; 32] = std::array::from_fn(|i| i as u8);
    let public_key = ed25519_dalek::SigningKey::from_bytes(&synthetic_seed)
        .verifying_key()
        .to_bytes();
    let mut trust = TrustedKeys::new();
    trust.insert(public_key).expect("fixture trust");
    let make_controller = || {
        let transport = Wire {
            inner: ReqwestTransport::new_for_loopback_tests().expect("local test HTTP"),
            custody: custody.clone(),
            directory: dir.path().into(),
            offline: offline.clone(),
            expected_remint: expected_remint.clone(),
            lose_initial_reply: lose_initial_reply.clone(),
            staff: staff.clone(),
        };
        let api = LicensingClient::new_for_loopback_tests(transport, &base).expect("loopback only");
        AccountController::new(
            Some(dir.path().into()),
            api,
            custody.clone(),
            trust.clone(),
            crate::account::controller::system_time,
        )
    };
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut init = String::new();
    input
        .read_line(&mut init)
        .expect("local synthetic fixtures");
    let init: Value = serde_json::from_str(&init).expect("fixture inputs");
    let auth = || match scenario.as_str() {
        "cascade"
        | "initial-restart"
        | "lost-initial"
        | "staff-extension-managed-free"
        | "staff-extension-response-lost" => Command::SignIn {
            email: init["email"].as_str().expect("fixture email").into(),
            password: Token::new(init["password"].as_str().expect("fixture password")),
            display_name: "G1 live booth".into(),
        },
        _ => Command::Enroll {
            key: Token::new(
                init["enrollment_key"]
                    .as_str()
                    .expect("fixture enrollment key"),
            ),
            display_name: "G1 live booth".into(),
        },
    };
    let mut account = make_controller();
    if scenario == "initial-restart" {
        custody.fail_write.store(true, Ordering::SeqCst);
        let first = wire(&account.execute(auth()));
        assert_eq!(first["device_state"], "credential_not_saved");
        let storage = AccountMetadataStore::new(dir.path().into());
        let saved = storage
            .load_or_create(CredentialPresence::Missing)
            .expect("saved binding");
        assert!(saved.activated_public_id.is_some());
        assert!(saved
            .pending_activation()
            .expect("frozen initial")
            .expected_device_public_id()
            .is_none());
        checkpoint(&mut input, "initial unsaved");
        drop(account);
        custody.fail_write.store(false, Ordering::SeqCst);
        let mut restarted = make_controller();
        let replay = wire(&restarted.execute(Command::RetryActivation));
        assert_eq!(replay["error_code"], "device_recovery_required");
        assert!(custody
            .get(DEVICE_TOKEN_NAME)
            .expect("device custody")
            .is_none());
        let bound = storage
            .load_or_create(CredentialPresence::Missing)
            .expect("unchanged binding");
        assert_eq!(bound.activated_public_id, saved.activated_public_id);
        assert_eq!(bound.fingerprint(), saved.fingerprint());
        println!("G1 initial replay");
        return;
    }
    if scenario == "lost-initial" {
        // Simulate losing the complete response after Django commits the initial
        // transaction. The controller must obtain identity via the receipt alone.
        lose_initial_reply.store(true, Ordering::SeqCst);
        let first = wire(&account.execute(auth()));
        assert_eq!(first["error_code"], "network_unavailable");
        let storage = AccountMetadataStore::new(dir.path().into());
        let saved = storage
            .load_or_create(CredentialPresence::Missing)
            .expect("ambiguous operation");
        assert!(saved.activated_public_id.is_none());
        assert!(saved.pending_activation().is_some());
        checkpoint(&mut input, "initial response lost");
        let mut restarted = make_controller();
        let learned = wire(&restarted.execute(Command::RetryActivation));
        assert_eq!(learned["error_code"], "activation_operation_completed");
        assert_eq!(learned["device_state"], "reauthentication_needed");
        assert!(custody
            .get(DEVICE_TOKEN_NAME)
            .expect("credential custody")
            .is_none());
        let bound = storage
            .load_or_create(CredentialPresence::Missing)
            .expect("learned identity");
        assert!(bound.activated_public_id.is_some() && bound.pending_activation().is_none());
        assert_eq!(bound.fingerprint(), saved.fingerprint());
        checkpoint(&mut input, "completed receipt learned");
        let recovered = wire(&restarted.execute(auth()));
        assert_eq!(recovered["entitlement_state"], "current");
        let final_binding = storage
            .load_or_create(CredentialPresence::Present)
            .expect("preserved identity");
        assert_eq!(final_binding.activated_public_id, bound.activated_public_id);
        println!("G1 lost-initial recovered");
        return;
    }
    let activate = wire(&account.execute(auth()));
    assert_eq!(activate["setup_state"], "completed");
    assert_eq!(activate["entitlement_state"], "current");
    let original = custody
        .get(DEVICE_TOKEN_NAME)
        .expect("saved original")
        .expect("original token");
    let storage = AccountMetadataStore::new(dir.path().into());
    let initial_id = storage
        .load_or_create(CredentialPresence::Present)
        .expect("original binding");
    let public_id = initial_id
        .activated_public_id
        .as_deref()
        .expect("public ID");

    let operator = crate::demo_shell();
    let first = operator.view().items.first().expect("test plan item").id;
    operator.select(first);
    let live = operator.go_live().live_index.expect("fixture slide on air");
    checkpoint(&mut input, "activated");

    if scenario.starts_with("staff-extension") {
        // The parent sends the licence expiry reloaded after the staff writer committed.
        // Compare instants so UTC offsets and fractional-second formatting can differ.
        let mut expiry_line = String::new();
        input
            .read_line(&mut expiry_line)
            .expect("staff expiry from database");
        let parse_expiry = |date: &str| {
            time::OffsetDateTime::parse(date, &time::format_description::well_known::Rfc3339)
                .expect("fixture licence expiry")
        };
        let extended_expiry = parse_expiry(expiry_line.trim());
        assert_ne!(
            parse_expiry(
                activate["license_expires_at"]
                    .as_str()
                    .expect("original signed expiry")
            ),
            extended_expiry
        );
        let assert_extended_entitlement = |view: &Value| {
            assert!(
                view["error_code"].is_null(),
                "unexpected account command error: {}",
                view["error_code"]
            );
            assert_eq!(view["entitlement_state"], "current");
            let signed_expiry = view["license_expires_at"]
                .as_str()
                .expect("signed licence expiry");
            assert_eq!(
                parse_expiry(signed_expiry),
                extended_expiry,
                "the verified entitlement must contain the committed staff expiry"
            );
        };
        let loss = scenario == "staff-extension-response-lost";
        let store_fault = scenario == "staff-extension-store-failed";
        let restart = scenario == "staff-extension-restart";
        let managed = scenario == "staff-extension-managed-free";
        {
            let mut trace = staff.lock().expect("staff refresh trace lock poisoned");
            trace.original = Some(original.clone());
            trace.public_id = public_id.to_owned();
            trace.lose_reply = loss;
        }
        custody.fail_write.store(store_fault, Ordering::SeqCst);
        let refresh = || Command::Refresh { explicit: true };
        let first = wire(&account.execute(refresh()));
        checkpoint(&mut input, "staff refresh returned");
        assert_eq!(operator.view().live_index, Some(live));
        assert_eq!(first["entitlement_state"], "current");

        if loss {
            assert!(staff.lock().expect("staff refresh trace lock poisoned").dropped,
                "no successful replacement response from the real API to drop after staff extension");
            assert_eq!(first["error_code"], "network_unavailable");
        }
        if store_fault {
            assert_eq!(
                custody.denied_device_writes.load(Ordering::SeqCst),
                1,
                "staff refresh never attempted to store the replacement in device custody"
            );
            assert_eq!(first["device_state"], "credential_not_saved");
        }
        if loss || store_fault {
            assert_eq!(
                custody.get(DEVICE_TOKEN_NAME).expect("old custody"),
                Some(original.clone())
            );
            assert!(staff
                .lock()
                .expect("staff refresh trace lock poisoned")
                .manifests_with_saved_replacement
                .is_empty());
            assert_eq!(
                first["manifest_expires_at"],
                activate["manifest_expires_at"]
            );
            assert_eq!(first["license_expires_at"], activate["license_expires_at"]);
            checkpoint(&mut input, "replacement unavailable locally");
        } else {
            assert_extended_entitlement(&first);
        }
        if store_fault {
            custody.fail_write.store(false, Ordering::SeqCst);
            let saved = wire(&account.execute(Command::RetryActivation));
            assert_extended_entitlement(&saved);
        }
        if restart || managed {
            if restart {
                drop(account);
                account = make_controller();
                let startup = wire(&account.execute(Command::Startup));
                assert_extended_entitlement(&startup);
            }
            let next = wire(&account.execute(refresh()));
            assert_extended_entitlement(&next);
            assert_eq!(next["instances_used"], 1);
            assert_eq!(next["instance_limit"], activate["instance_limit"]);
            let trace = staff.lock().expect("staff refresh trace lock poisoned");
            assert_eq!(trace.calls.len(), 2);
            let next = &trace.calls[1];
            assert!(next.replacement && next.capable && next.status == 200 && !next.issued,
                "the next online refresh must use the already-stored staff replacement and receive status only");
        }
        {
            let trace = staff.lock().expect("staff refresh trace lock poisoned");
            let call = trace.calls.first().expect("real staff refresh POST");
            assert!(call.capable && call.original && call.status == 200 && call.issued,
                "the native refresh did not negotiate and receive a replacement for the live original bearer");
            if !loss {
                assert_eq!(
                    trace.manifests_with_saved_replacement,
                    vec![true; if restart || managed { 2 } else { 1 }],
                    "every manifest GET must already have the real replacement in device custody and in its bearer header"
                );
                assert_eq!(
                    custody.get(DEVICE_TOKEN_NAME).expect("final custody"),
                    trace.replacement
                );
            }
            if store_fault {
                assert!(
                    trace.calls[1..]
                        .iter()
                        .all(|call| call.replacement && !call.issued && call.status == 200),
                    "retry must use the retained answer without re-posting the revoked original"
                );
            }
        }
        let calls_before_probe = staff
            .lock()
            .expect("staff refresh trace lock poisoned")
            .calls
            .len();
        assert!(matches!(
            account.client().refresh_license(&original, public_id),
            Err(selahcue_licensing::ActivationFailure::Unauthenticated)
        ));
        {
            let trace = staff.lock().expect("staff refresh trace lock poisoned");
            assert_eq!(trace.calls.len(), calls_before_probe + 1);
            let probe = &trace.calls[calls_before_probe];
            assert!(probe.original, "probe must present the original bearer");
            assert_eq!(
                probe.status, 401,
                "real API must reject the original bearer with HTTP 401"
            );
        }
        if loss {
            // Restart has only the previously stored bearer. Generic actions
            // must preserve the presentation and cannot authorize replacement.
            drop(account);
            account = make_controller();
            for command in [Command::RetryActivation, auth()] {
                let view = wire(&account.execute(command));
                assert_eq!(view["entitlement_state"], "current");
                assert_eq!(
                    custody.get(DEVICE_TOKEN_NAME).expect("old custody"),
                    Some(original.clone())
                );
                assert_eq!(operator.view().live_index, Some(live));
            }
        }
        let after = storage
            .load_or_create(CredentialPresence::Present)
            .expect("preserved staff binding");
        assert_eq!(after.activated_public_id, initial_id.activated_public_id);
        assert_eq!(after.fingerprint(), initial_id.fingerprint());
        assert_eq!(operator.view().live_index, Some(live));
        println!("G1 staff extension checked");
        return;
    }

    if scenario == "missing-local" {
        custody
            .remove(DEVICE_TOKEN_NAME)
            .expect("simulate lost OS credential");
        let lost = wire(&account.execute(Command::Refresh { explicit: true }));
        assert_eq!(lost["device_state"], "credential_missing");
        assert_eq!(lost["error_code"], "device_recovery_required");
        let replay = wire(&account.execute(auth()));
        assert_eq!(replay["device_state"], "credential_missing");
        assert_eq!(replay["error_code"], "device_recovery_required");
        assert!(custody
            .get(DEVICE_TOKEN_NAME)
            .expect("no replay credential")
            .is_none());
        assert!(account
            .client()
            .refresh_license(&original, public_id)
            .is_ok());
        let after = storage
            .load_or_create(CredentialPresence::Missing)
            .expect("unchanged identity");
        assert_eq!(after.fingerprint(), initial_id.fingerprint());
        assert_eq!(after.activated_public_id, initial_id.activated_public_id);
        assert_eq!(operator.view().live_index, Some(live));
        println!("G1 recovery required");
        return;
    }

    offline.store(true, Ordering::SeqCst);
    let background = wire(&account.execute(Command::Refresh { explicit: false }));
    assert_eq!(background["entitlement_state"], "current");
    assert_eq!(operator.view().live_index, Some(live));
    offline.store(false, Ordering::SeqCst);

    let lapsed = wire(&account.execute(Command::Refresh { explicit: true }));
    match scenario.as_str() {
        "live" => assert_eq!(lapsed["license_state"], "renewal_needed"),
        _ => assert_eq!(lapsed["device_state"], "reauthentication_needed"),
    }
    assert_eq!(operator.view().live_index, Some(live));
    assert!(operator.blackout(true).blackout);
    assert!(!operator.blackout(false).blackout);
    assert_eq!(operator.view().live_index, Some(live));
    checkpoint(&mut input, "lapsed");

    if scenario == "live" {
        let renewed = wire(&account.execute(Command::Refresh { explicit: true }));
        assert_eq!(renewed["entitlement_state"], "current");
        assert_eq!(renewed["license_state"], "active");
        assert_eq!(
            custody.get(DEVICE_TOKEN_NAME).expect("unchanged custody"),
            Some(original)
        );
    } else {
        assert!(matches!(
            account.client().refresh_license(&original, public_id),
            Err(selahcue_licensing::ActivationFailure::Unauthenticated)
        ));
        // Dismissing re-auth without dispatching an activation leaves the same
        // device credential, saved device identity and live presentation.
        assert_eq!(
            custody.get(DEVICE_TOKEN_NAME).expect("cancelled recovery"),
            Some(original.clone())
        );
        assert_eq!(operator.view().live_index, Some(live));
        checkpoint(&mut input, "dead_token");
        expected_remint.store(true, Ordering::SeqCst);
        custody.fail_write.store(true, Ordering::SeqCst);
        let unsaved = wire(&account.execute(auth()));
        assert_eq!(unsaved["device_state"], "credential_not_saved");
        assert!(
            !expected_remint.load(Ordering::SeqCst),
            "live API did not return the remint"
        );
        assert_eq!(
            custody
                .get(DEVICE_TOKEN_NAME)
                .expect("unsaved prior custody"),
            Some(original.clone())
        );
        if scenario == "cascade" {
            assert!(custody
                .get(ACCOUNT_SESSION_NAME)
                .expect("saved bootstrap")
                .is_some());
        }
        assert_eq!(operator.view().live_index, Some(live));
        checkpoint(&mut input, "unsaved");
        custody.fail_write.store(false, Ordering::SeqCst);
        let renewed = wire(&account.execute(Command::RetryActivation));
        assert_eq!(renewed["entitlement_state"], "current");
        let replacement = custody
            .get(DEVICE_TOKEN_NAME)
            .expect("saved replacement")
            .expect("replacement token");
        assert_ne!(original, replacement);
        assert!(account
            .client()
            .refresh_license(&replacement, public_id)
            .is_ok());
        assert!(custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("cleanup")
            .is_none());
        assert!(matches!(
            account.client().refresh_license(&original, public_id),
            Err(selahcue_licensing::ActivationFailure::Unauthenticated)
        ));
    }
    assert_eq!(operator.view().live_index, Some(live));
    operator.clear();
    assert!(operator.view().live_index.is_none());
    let after = storage
        .load_or_create(CredentialPresence::Present)
        .expect("recovered binding");
    assert_eq!(after.activated_public_id, initial_id.activated_public_id);
    assert_eq!(after.fingerprint(), initial_id.fingerprint());
    let mut restarted = make_controller();
    offline.store(true, Ordering::SeqCst);
    assert_eq!(
        wire(&restarted.execute(Command::Startup))["entitlement_state"],
        "current"
    );
    println!("G1 recovered");
}

#[test]
fn session_retry_after_lost_response_checks_retained_bearer_against_device_binding() {
    for (status, expected) in [(200, "credential_present"), (401, "credential_unconfirmed")] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let custody = Custody::default();
        let mut first = controller(dir.path(), custody.clone());
        first
            .client()
            .transport()
            .push_response(200, session_json())
            .push_failure("lost activation response");
        assert_eq!(
            wire(&first.execute(sign_in()))["operation_state"],
            "retry_pending"
        );
        custody
            .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
            .expect("cached device credential");
        let mut restarted = controller(dir.path(), custody.clone());
        restarted
            .client()
            .transport()
            .push_response(200, activated(None, false))
            .push_response(
                status,
                if status == 200 {
                    refresh_status(true)
                } else {
                    String::new()
                },
            )
            .push_response(200, r#"{"revoked":true}"#)
            .push_failure("manifest fetch offline");
        let retry = wire(&restarted.execute(Command::RetryActivation));
        assert_eq!(retry["device_state"], expected);
        let sent = first
            .client()
            .transport()
            .request(1)
            .expect("original activation");
        let replay = restarted
            .client()
            .transport()
            .request(0)
            .expect("replayed activation");
        assert!(sent == replay);
        let verify = restarted
            .client()
            .transport()
            .request(1)
            .expect("device bearer verification");
        assert!(verify.url.ends_with("/v1/license:refresh"));
        assert!(verify.had_bearer);
        assert_eq!(
            custody
                .get(ACCOUNT_SESSION_NAME)
                .expect("custody")
                .is_none(),
            status == 200
        );
        assert_eq!(
            AccountMetadataStore::new(dir.path().into())
                .load_or_create(CredentialPresence::Present)
                .expect("metadata")
                .pending_activation()
                .is_some(),
            status == 401
        );
    }
}

#[test]
fn known_remote_cleanup_ack_can_retry_only_matching_local_removal() {
    use std::sync::atomic::Ordering;
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    custody.fail_remove.store(true, Ordering::SeqCst);
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("refresh offline");
    let first = wire(&account.execute(sign_in()));
    assert_eq!(first["pending_cleanup"], true);
    assert_eq!(first["cleanup_error_code"], "session_cleanup_local_failure");
    assert_eq!(first["error_code"], "network_unavailable");
    assert_eq!(
        custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("failed local cleanup"),
        Some(Token::new(SESSION))
    );
    let unrelated = Token::new("another-stored-session");
    custody
        .set(ACCOUNT_SESSION_NAME, &unrelated)
        .expect("external replacement");
    custody.fail_remove.store(false, Ordering::SeqCst);
    let retry = wire(&account.execute(Command::RetryCleanup));
    assert_eq!(account.client().transport().request_count(), 4);
    assert_eq!(
        custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("unrelated entry remains"),
        Some(unrelated)
    );
    assert!(retry.get("cleanup_error_code").is_none());
}

#[test]
fn refreshed_cache_failure_never_removes_credentials_or_changes_a_live_service() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let storage = AccountMetadataStore::new(dir.path().into());
    let metadata = storage
        .load_or_create(CredentialPresence::Missing)
        .expect("install ID");
    let (trust, body) = signed_display(
        metadata.fingerprint(),
        "2026-11-01T00:00:00Z",
        "2026-11-15T16:00:00Z",
        "2027-01-01T00:00:00Z",
    );
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        custody.clone(),
        trust,
        || NOW,
    );
    std::fs::create_dir(dir.path().join("entitlement-cache.json")).expect("unusable destination");
    let shell = crate::demo_shell();
    shell.select(shell.view().items.first().expect("test plan item").id);
    let live = shell.go_live().live_index.expect("live item");
    account
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, refresh_status(true))
        .push_response(200, body);
    let view = wire(&account.execute(enroll()));
    assert_eq!(view["device_state"], "credential_present");
    assert_eq!(view["entitlement_state"], "unavailable");
    assert_eq!(view["error_code"], "manifest_unavailable");
    assert!(view.get("plan_label").is_none());
    assert_eq!(
        custody
            .get(DEVICE_TOKEN_NAME)
            .expect("device token survives"),
        Some(Token::new(SECRET))
    );
    assert_eq!(shell.view().live_index, Some(live));
    assert!(shell.blackout(true).blackout);
    shell.clear();
    assert!(shell.view().live_index.is_none());
}

#[test]
fn unexpected_device_public_id_keeps_existing_binding_and_device_credential() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_failure("refresh offline");
    assert_eq!(wire(&account.execute(enroll()))["setup_state"], "completed");

    let other_id = "dev_ffeeddccbbaa99887766554433221100";
    account.client().transport().push_response(
        200,
        activated(Some("different-device-token"), true).replace(DEVICE, other_id),
    );
    let rejected = wire(&account.execute(enroll()));
    assert_eq!(rejected["error_code"], "device_binding_mismatch");
    let bound = AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Present)
        .expect("persisted binding");
    assert_eq!(bound.activated_public_id.as_deref(), Some(DEVICE));
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("original token"),
        Some(Token::new(SECRET))
    );
    assert_eq!(account.client().transport().request_count(), 3);
}

#[test]
fn registering_the_worker_is_local_and_leaves_metadata_unopened() {
    use crate::account::controller::Worker;
    let dir = tempfile::tempdir().expect("fixture directory");
    let worker = Worker::new(controller(dir.path(), Custody::default()));
    assert_eq!(std::fs::read_dir(dir.path()).expect("app data").count(), 0);
    assert_eq!(
        wire(&worker.view()),
        json!({
            "revision": 0,
            "setup_state": "unknown",
            "device_state": "unknown",
            "entitlement_state": "unavailable",
            "operation_state": "idle",
            "pending_cleanup": false
        })
    );
}

#[test]
fn failed_public_id_save_retries_from_native_response_without_a_second_activation() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use std::sync::atomic::{AtomicBool, Ordering};

    struct MetadataFault {
        directory: std::path::PathBuf,
        requests: ScriptedTransport,
        drained: AtomicBool,
    }

    impl HttpTransport for MetadataFault {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound") && !self.drained.swap(true, Ordering::SeqCst)
            {
                let lock = self.directory.join("account-metadata.lock");
                std::fs::remove_file(&lock).expect("release test writer lock");
                std::fs::create_dir(lock).expect("block later metadata save");
            }
            self.requests.post_json(url, body, bearer)
        }

        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.requests.get(url, bearer)
        }
    }

    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let transport = MetadataFault {
        directory: dir.path().into(),
        requests: ScriptedTransport::responding(200, activated(Some(SECRET), false)),
        drained: AtomicBool::new(false),
    };
    transport.requests.push_failure("offline after saved retry");
    let client = LicensingClient::new(transport, API_ORIGIN).expect("fixture client");
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        custody.clone(),
        TrustedKeys::new(),
        || NOW,
    );
    let failure = wire(&account.execute(enroll()));
    assert_eq!(failure["error_code"], "metadata_unavailable");
    assert_eq!(failure["operation_state"], "retry_pending");
    assert!(custody
        .get(DEVICE_TOKEN_NAME)
        .expect("device token withheld before ID save")
        .is_none());
    std::fs::remove_dir(dir.path().join("account-metadata.lock")).expect("restore writer lock");
    let recovered = wire(&account.execute(Command::RetryActivation));
    assert_eq!(recovered["setup_state"], "completed");
    let requests = account.client().transport().requests.recorded();
    assert_eq!(requests.len(), 2);
    assert!(requests[0].url.ends_with("/v1/activations:bound"));
    assert!(requests[1].url.ends_with("/v1/license:refresh"));
}

#[test]
fn failed_bootstrap_custody_retires_fresh_preparation_but_preserves_sent_retry() {
    use std::sync::atomic::Ordering;
    for already_sent in [false, true] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let custody = Custody::default();
        let mut account = controller(dir.path(), custody.clone());
        if already_sent {
            account
                .client()
                .transport()
                .push_response(200, session_json())
                .push_failure("possibly sent");
            assert_eq!(
                wire(&account.execute(sign_in()))["operation_state"],
                "retry_pending"
            );
        }
        custody.fail_session_write.store(true, Ordering::SeqCst);
        account
            .client()
            .transport()
            .push_response(
                200,
                session_json().replace(SESSION, "different-session-for-retry"),
            )
            .push_response(200, r#"{"revoked":true}"#);
        assert_eq!(
            wire(&account.execute(sign_in()))["error_code"],
            "account_session_save_failed"
        );
        let saved = AccountMetadataStore::new(dir.path().into())
            .load_or_create(CredentialPresence::Missing)
            .expect("persisted preparation");
        assert_eq!(saved.pending_activation().is_some(), already_sent);

        let mut restarted = controller(dir.path(), custody);
        restarted
            .client()
            .transport()
            .push_response(200, activated(Some(SECRET), false))
            .push_failure("offline");
        let result = wire(&restarted.execute(enroll()));
        if already_sent {
            assert_eq!(result["error_code"], "pending_activation_path");
            assert_eq!(restarted.client().transport().request_count(), 0);
        } else {
            assert_eq!(result["setup_state"], "completed");
        }
    }
}

#[test]
fn restart_can_replace_prepared_path_that_never_dispatched() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let store = AccountMetadataStore::new(dir.path().into());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    metadata
        .begin_activation(
            crate::account::state::ActivationPath::AccountSession,
            std::env::consts::OS,
            "1.0",
            "Booth",
        )
        .expect("prepare account path");
    store.save(&metadata).expect("durable preparation");
    let mut restarted = controller(dir.path(), Custody::default());
    restarted
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_failure("offline");
    assert_eq!(
        wire(&restarted.execute(enroll()))["setup_state"],
        "completed"
    );
}

#[test]
fn legacy_phase_absence_preserves_ambiguous_operation() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let mut account = controller(dir.path(), Custody::default());
    account
        .client()
        .transport()
        .push_failure("lost enrollment reply");
    assert_eq!(
        wire(&account.execute(enroll()))["operation_state"],
        "retry_pending"
    );
    let file = dir.path().join("account-metadata.json");
    let body = std::fs::read(&file).expect("metadata");
    let mut json: Value = serde_json::from_slice(&body).expect("metadata JSON");
    json["pending_activation"]
        .as_object_mut()
        .expect("pending")
        .remove("phase");
    json["pending_activation"]
        .as_object_mut()
        .expect("pending")
        .remove("protocol");
    json["pending_activation"]
        .as_object_mut()
        .expect("pending")
        .remove("expected_device_public_id");
    json["pending_activation"]
        .as_object_mut()
        .expect("pending")
        .remove("mode");
    std::fs::write(
        file,
        serde_json::to_vec(&json).expect("serialize legacy shape"),
    )
    .expect("legacy fixture");
    let mut restarted = controller(dir.path(), Custody::default());
    assert_eq!(
        wire(&restarted.execute(sign_in()))["error_code"],
        "legacy_activation_outcome_unknown"
    );
    assert_eq!(restarted.client().transport().request_count(), 0);
}

#[test]
fn cached_projection_expires_at_exact_time_during_blocked_refresh() {
    use crate::account::controller::Worker;
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use selahcue_licensing::EntitlementCache;
    use std::sync::{
        atomic::{AtomicU32, Ordering},
        mpsc, Mutex,
    };
    static NANOSECOND: AtomicU32 = AtomicU32::new(0);
    fn clock() -> Time {
        (NOW.0, NANOSECOND.load(Ordering::SeqCst))
    }
    struct BlockRefresh {
        entered: mpsc::Sender<()>,
        first: std::sync::atomic::AtomicBool,
        manifest: String,
        release: Mutex<mpsc::Receiver<()>>,
    }
    impl HttpTransport for BlockRefresh {
        fn post_json(
            &self,
            _: &str,
            _: &str,
            _: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if !self.first.swap(true, Ordering::SeqCst) {
                return Ok(HttpResponse {
                    status: 200,
                    body: refresh_status(true)
                        .replace("2027-01-01T00:00:00Z", "2026-11-14T16:00:00.123456789Z"),
                });
            }
            self.entered.send(()).expect("refresh reached wire");
            self.release
                .lock()
                .expect("hold refresh")
                .recv_timeout(std::time::Duration::from_secs(8))
                .expect("unblock refresh");
            Err(TransportError("offline".into()))
        }
        fn get(&self, _: &str, _: Option<&str>) -> Result<HttpResponse, TransportError> {
            Ok(HttpResponse {
                status: 200,
                body: self.manifest.clone(),
            })
        }
    }
    let dir = tempfile::tempdir().expect("fixture directory");
    let store = AccountMetadataStore::new(dir.path().into());
    let custody = Custody::default();
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    metadata.activated_public_id = Some(DEVICE.into());
    store.save(&metadata).expect("bind");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("durable custody");
    let (trust, manifest) = signed_display(
        metadata.fingerprint(),
        "2026-11-14T15:00:00Z",
        "2026-11-14T16:00:00.123456789Z",
        "2026-11-17T16:00:00Z",
    );
    EntitlementCache::new(dir.path())
        .replace(manifest.as_bytes(), &trust, DEVICE, metadata.fingerprint())
        .expect("verified fixture");
    let (entered, wait_entered) = mpsc::channel();
    let (release, wait_release) = mpsc::channel();
    let transport = BlockRefresh {
        entered,
        first: std::sync::atomic::AtomicBool::new(false),
        manifest,
        release: Mutex::new(wait_release),
    };
    let client = LicensingClient::new(transport, API_ORIGIN).expect("fixture client");
    let worker = Worker::new(AccountController::new(
        Some(dir.path().into()),
        client,
        custody,
        trust,
        clock,
    ));
    NANOSECOND.store(123_456_788, Ordering::SeqCst);
    let start = worker
        .admit()
        .unwrap_or_else(|_| panic!("startup slot"))
        .run(Command::Startup);
    assert_eq!(wire(&start)["entitlement_state"], "current");
    let online = worker
        .admit()
        .unwrap_or_else(|_| panic!("online slot"))
        .run(Command::Refresh { explicit: true });
    assert_eq!(wire(&online)["license_state"], "active");
    let work = worker.admit().unwrap_or_else(|_| panic!("refresh slot"));
    let busy = worker.view();
    let task = std::thread::spawn(move || work.run(Command::Refresh { explicit: false }));
    wait_entered
        .recv_timeout(std::time::Duration::from_secs(5))
        .expect("running refresh");
    NANOSECOND.store(123_456_789, Ordering::SeqCst);
    let new_view = worker.view();
    let competing = worker.admit().err().expect("busy reply");
    release.send(()).expect("release pending refresh");
    let done = task.join().expect("refresh finished");
    assert_eq!(wire(&new_view)["entitlement_state"], "expired");
    assert_eq!(wire(&new_view)["license_state"], "renewal_needed");
    assert_eq!(wire(&competing)["license_state"], "renewal_needed");
    assert_eq!(wire(&competing)["entitlement_state"], "expired");
    assert!(new_view.revision > busy.revision);
    assert_eq!(new_view.revision, competing.revision);
    assert!(done.revision > new_view.revision);
    assert_eq!(wire(&done)["entitlement_state"], "expired");
}

#[test]
fn failed_unsent_retirement_preserves_primary_custody_error_and_can_be_retried() {
    struct FailRetirement {
        directory: std::path::PathBuf,
        store: Custody,
    }
    impl SecretStore for FailRetirement {
        fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
            self.store.get(name)
        }
        fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
            if name == ACCOUNT_SESSION_NAME {
                let lock = self.directory.join("account-metadata.lock");
                std::fs::remove_file(&lock).expect("closed prep lock");
                std::fs::create_dir(lock).expect("block completion save");
                return Err(SecretError("blocked account custody".into()));
            }
            self.store.set(name, token)
        }
        fn remove(&self, name: &str) -> Result<(), SecretError> {
            self.store.remove(name)
        }
    }
    let dir = tempfile::tempdir().expect("fixture directory");
    let client = LicensingClient::new(ScriptedTransport::new(), API_ORIGIN).expect("static origin");
    let store = Custody::default();
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        FailRetirement {
            directory: dir.path().into(),
            store: store.clone(),
        },
        TrustedKeys::new(),
        || NOW,
    );
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, r#"{"revoked":true}"#);
    let failed = wire(&account.execute(sign_in()));
    assert_eq!(failed["error_code"], "account_session_save_failed");
    assert_eq!(failed["preparation_error_code"], "metadata_unavailable");
    assert!(account
        .client()
        .transport()
        .recorded()
        .iter()
        .all(|r| !r.url.contains("/v1/activations:bound")));
    std::fs::remove_dir(dir.path().join("account-metadata.lock")).expect("restore lock path");
    let mut restarted = controller(dir.path(), store);
    restarted
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_failure("offline");
    assert_eq!(
        wire(&restarted.execute(enroll()))["setup_state"],
        "completed"
    );
}

#[test]
fn dedicated_bound_path_refuses_old_server_without_fallback() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(404, "<html>old server</html>");
    let reply = wire(&account.execute(enroll()));
    assert_eq!(reply["error_code"], "bound_activation_unsupported");
    assert_eq!(reply["operation_state"], "retry_pending");
    let requests = account.client().transport().recorded();
    assert_eq!(requests.len(), 1);
    assert!(requests[0].url.ends_with("/v1/activations:bound"));
    assert!(custody
        .get(DEVICE_TOKEN_NAME)
        .expect("local custody")
        .is_none());
}

#[test]
fn restart_replays_initial_expectation_after_public_id_survives_failed_custody() {
    use std::sync::atomic::Ordering;
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    custody.fail_write.store(true, Ordering::SeqCst);
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false));
    assert_eq!(
        wire(&account.execute(enroll()))["device_state"],
        "credential_not_saved"
    );
    let sent = account
        .client()
        .transport()
        .request(0)
        .expect("initial request");
    let metadata = AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Missing)
        .expect("on-disk receipt");
    assert_eq!(metadata.activated_public_id.as_deref(), Some(DEVICE));
    assert_eq!(
        metadata
            .pending_activation()
            .expect("frozen operation")
            .expected_device_public_id(),
        None
    );
    let mut restarted = controller(dir.path(), custody);
    restarted
        .client()
        .transport()
        .push_response(200, activated(None, false));
    assert_eq!(
        wire(&restarted.execute(enroll()))["error_code"],
        "device_recovery_required"
    );
    let retried = restarted
        .client()
        .transport()
        .request(0)
        .expect("replay request");
    assert!(sent == retried);
    let request: Value = serde_json::from_str(&sent.body).expect("initial wire");
    assert_eq!(request["mode"], "initial");
    assert!(request["expected_device_public_id"].is_null());
}

#[test]
fn unusable_completed_initial_receipt_cannot_reserve_a_second_slot() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let mut account = controller(dir.path(), Custody::default());
    account.client().transport()
        .push_failure("initial outcome lost")
        .push_response(409, r#"{"operation_version":1,"error":{"code":"ACTIVATION_OPERATION_COMPLETED","message":"fixture"}}"#)
        .push_response(404, r#"{"operation_version":1,"error":{"code":"NOT_FOUND","message":"fixture"}}"#);
    account.execute(enroll());
    assert_eq!(
        wire(&account.execute(enroll()))["error_code"],
        "activation_operation_completed"
    );
    assert_eq!(
        wire(&account.execute(enroll()))["error_code"],
        "unknown_key"
    );
    let requests = account.client().transport().recorded();
    assert!(requests[0] == requests[1] && requests[1] == requests[2]);
    assert_eq!(
        wire(&account.execute(sign_in()))["error_code"],
        "pending_activation_path"
    );
}

fn completed_proof(device: &str, platform: &str) -> String {
    json!({
        "operation_version": 1,
        "error": {"code": "ACTIVATION_OPERATION_COMPLETED", "message": "fixture"},
        "completed_activation": {
            "idempotency_key": "fixture_nonce",
            "device_public_id": device,
            "platform": platform,
        }
    })
    .to_string()
}

#[test]
fn completed_proof_with_wrong_device_or_platform_preserves_pending_operation() {
    let forged = "dev_ffeeddccbbaa99887766554433221100";
    for (id, platform) in [(forged, std::env::consts::OS), (DEVICE, "wrong-platform")] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let store = AccountMetadataStore::new(dir.path().into());
        let mut local = store
            .load_or_create(CredentialPresence::Missing)
            .expect("identity");
        local.activated_public_id = Some(DEVICE.into());
        store.save(&local).expect("bound ID");
        let custody = Custody::default();
        let mut account = controller(dir.path(), custody.clone());
        account
            .client()
            .transport()
            .push_response(409, completed_proof(id, platform));
        let view = wire(&account.execute(enroll()));
        assert_eq!(view["error_code"], "device_binding_mismatch");
        let saved = store
            .load_or_create(CredentialPresence::Missing)
            .expect("original metadata");
        assert_eq!(saved.activated_public_id.as_deref(), Some(DEVICE));
        assert!(saved.pending_activation().is_some());
        assert!(custody
            .get(DEVICE_TOKEN_NAME)
            .expect("no overwrite")
            .is_none());
    }
}

#[test]
fn failed_completed_proof_cas_can_retry_the_same_pending_request() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use std::sync::atomic::{AtomicBool, Ordering};

    struct FaultOnce {
        directory: std::path::PathBuf,
        script: ScriptedTransport,
        block: AtomicBool,
    }
    impl HttpTransport for FaultOnce {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            let response = self.script.post_json(url, body, bearer)?;
            if self.block.swap(false, Ordering::SeqCst) {
                let lock = self.directory.join("account-metadata.lock");
                std::fs::remove_file(&lock).expect("closed metadata lock");
                std::fs::create_dir(lock).expect("simulate metadata CAS failure");
            }
            Ok(response)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }

    let dir = tempfile::tempdir().expect("fixture directory");
    let script = ScriptedTransport::responding(409, completed_proof(DEVICE, std::env::consts::OS));
    script.push_response(409, completed_proof(DEVICE, std::env::consts::OS));
    let transport = FaultOnce {
        directory: dir.path().into(),
        script,
        block: AtomicBool::new(true),
    };
    let client = LicensingClient::new(transport, API_ORIGIN).expect("fixture origin");
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        Custody::default(),
        TrustedKeys::new(),
        || NOW,
    );
    assert_eq!(
        wire(&account.execute(enroll()))["error_code"],
        "metadata_unavailable"
    );
    let store = AccountMetadataStore::new(dir.path().into());
    let initial = store
        .load_or_create(CredentialPresence::Missing)
        .expect("read frozen receipt");
    assert!(initial.activated_public_id.is_none());
    assert!(initial.pending_activation().is_some());
    std::fs::remove_dir(dir.path().join("account-metadata.lock")).expect("restore writer");
    let learned = wire(&account.execute(enroll()));
    assert_eq!(learned["error_code"], "activation_operation_completed");
    assert_eq!(learned["device_state"], "reauthentication_needed");
    let final_binding = store
        .load_or_create(CredentialPresence::Missing)
        .expect("bound identity");
    assert_eq!(final_binding.activated_public_id.as_deref(), Some(DEVICE));
    assert!(final_binding.pending_activation().is_none());
    let sent = account.client().transport().script.recorded();
    assert!(sent[0] == sent[1]);
}

fn bound_refusal(operation: &str, code: &str) -> String {
    json!({
        "operation_version": 1,
        "surface": "desktop",
        "operation": operation,
        "error": {"code": code, "message": "fixture refusal"}
    })
    .to_string()
}

#[test]
fn definitive_first_account_refusal_enables_enrollment_after_restart() {
    for (status, code, expected) in [
        (403, "PERMISSION_DENIED", "permission_denied"),
        (404, "NOT_FOUND", "no_active_license"),
        (400, "VALIDATION_FAILED", "invalid_input"),
        (403, "POLICY_DENIED", "policy_denied"),
    ] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let custody = Custody::default();
        let mut account = controller(dir.path(), custody.clone());
        account
            .client()
            .transport()
            .push_response(200, session_json())
            .push_response(status, bound_refusal("activation_bound_with_session", code))
            .push_response(200, r#"{"revoked":true}"#);
        let result = wire(&account.execute(sign_in()));
        assert_eq!(result["error_code"], expected);
        assert_eq!(result["operation_state"], "idle");
        assert!(custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("session custody")
            .is_none());
        assert!(account
            .client()
            .transport()
            .request(2)
            .expect("revoke")
            .url
            .ends_with("/v1/sessions:revoke"));

        let mut restarted = controller(dir.path(), custody);
        restarted
            .client()
            .transport()
            .push_response(200, activated(Some(SECRET), false))
            .push_failure("offline");
        assert_eq!(
            wire(&restarted.execute(enroll()))["setup_state"],
            "completed"
        );
    }
}

#[test]
fn first_wrong_enrollment_key_does_not_block_authorized_bound_account_recovery() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let store = AccountMetadataStore::new(dir.path().into());
    let mut bound = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    bound.activated_public_id = Some(DEVICE.into());
    store.save(&bound).expect("bound device");
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(404, bound_refusal("activation_bound", "NOT_FOUND"))
        .push_response(200, session_json())
        .push_response(200, activated(Some(SECRET), true))
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("offline");
    let refused = wire(&account.execute(enroll()));
    assert_eq!(refused["error_code"], "unknown_key");
    assert_eq!(refused["operation_state"], "idle");
    assert_eq!(
        wire(&account.execute(sign_in()))["setup_state"],
        "completed"
    );
    let requests = account.client().transport().recorded();
    let old: Value = serde_json::from_str(&requests[0].body).expect("enrollment");
    let next: Value = serde_json::from_str(&requests[2].body).expect("account activation");
    assert_eq!(next["expected_device_public_id"], DEVICE);
    assert_eq!(next["mode"], "recover");
    assert_ne!(old["idempotency_key"], next["idempotency_key"]);
}

#[test]
fn definitive_refusal_after_an_ambiguous_account_attempt_cannot_retire_it() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_failure("first result lost");
    assert_eq!(
        wire(&account.execute(sign_in()))["operation_state"],
        "retry_pending"
    );

    let mut restarted = controller(dir.path(), custody.clone());
    restarted.client().transport().push_response(
        403,
        bound_refusal("activation_bound_with_session", "PERMISSION_DENIED"),
    );
    let retry = wire(&restarted.execute(Command::RetryActivation));
    assert_eq!(retry["error_code"], "permission_denied");
    assert_eq!(retry["operation_state"], "retry_pending");
    assert_eq!(
        wire(&restarted.execute(enroll()))["error_code"],
        "pending_activation_path"
    );
    assert_eq!(restarted.client().transport().request_count(), 1);
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("session still in custody")
        .is_some());
    assert_eq!(
        account.client().transport().request(1),
        restarted.client().transport().request(0)
    );
}

#[test]
fn first_dispatch_keeps_pending_when_reply_lacks_definitive_refusal_provenance() {
    for (status, body) in [
        (404, "<html>old server</html>".into()),
        (
            404,
            r#"{"operation_version":1,"error":{"code":"NOT_FOUND"}}"#.into(),
        ),
        (
            404,
            bound_refusal("activation_bound_with_session", "NOT_FOUND"),
        ),
        (404, bound_refusal("activation_bound", "POLICY_DENIED")),
        (
            409,
            bound_refusal("activation_bound", "ACTIVATION_OPERATION_CONFLICT"),
        ),
        (
            403,
            bound_refusal("activation_bound", "POLICY_DENIED")
                .replace(r#""operation_version":1"#, r#""operation_version":2"#),
        ),
    ] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let mut account = controller(dir.path(), Custody::default());
        account.client().transport().push_response(status, body);
        assert_eq!(
            wire(&account.execute(enroll()))["operation_state"],
            "retry_pending"
        );
        assert_eq!(
            wire(&account.execute(sign_in()))["error_code"],
            "pending_activation_path"
        );
        assert_eq!(account.client().transport().request_count(), 1);
    }
}

// Runs two independently constructed controllers against the same disk/custody.
// Blocking only the test edges gives both send-generation interleavings without sleeps.
#[test]
fn independent_controllers_fence_fresh_retirement_and_retry_before_http() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use std::{
        sync::{mpsc, Mutex},
        time::Duration,
    };

    const DEADLINE: Duration = Duration::from_secs(8);
    type Gate = (mpsc::Sender<()>, Mutex<mpsc::Receiver<()>>);
    fn wait(gate: &Gate) {
        gate.0.send(()).expect("entered fixture gate");
        gate.1
            .lock()
            .expect("gate lock")
            .recv_timeout(DEADLINE)
            .expect("release gate");
    }

    struct GatedWire {
        script: Arc<ScriptedTransport>,
        gate: Option<Gate>,
    }
    impl HttpTransport for GatedWire {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound-with-session") {
                if let Some(gate) = &self.gate {
                    wait(gate);
                }
            }
            self.script.post_json(url, body, bearer)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }
    struct GatedCustody {
        store: Custody,
        gate: Mutex<Option<Gate>>,
    }
    impl SecretStore for GatedCustody {
        fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
            let observed = self.store.get(name);
            if name == ACCOUNT_SESSION_NAME {
                if let Some(gate) = self.gate.lock().expect("custody gate").take() {
                    wait(&gate);
                }
            }
            observed
        }
        fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
            self.store.set(name, token)
        }
        fn remove(&self, name: &str) -> Result<(), SecretError> {
            self.store.remove(name)
        }
    }
    for competing_fence_first in [false, true] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let path = dir.path().to_path_buf();
        let custody = Custody::default();

        let (first_enter, wait_first) = mpsc::channel();
        let (release_first, first_release) = mpsc::channel();
        let first_script = Arc::new(ScriptedTransport::new());
        first_script
            .push_response(200, session_json())
            .push_response(
                403,
                bound_refusal("activation_bound_with_session", "PERMISSION_DENIED"),
            )
            .push_response(200, r#"{"revoked":true}"#);
        let first_client = LicensingClient::new(
            GatedWire {
                script: first_script.clone(),
                gate: Some((first_enter, Mutex::new(first_release))),
            },
            API_ORIGIN,
        )
        .expect("fixture client");
        let mut first = AccountController::new(
            Some(path.clone()),
            first_client,
            custody.clone(),
            TrustedKeys::new(),
            || NOW,
        );
        let a = std::thread::spawn(move || first.execute(sign_in()));
        wait_first.recv_timeout(DEADLINE).expect("first dispatch");

        let (second_enter, wait_second) = mpsc::channel();
        let (release_second, second_release) = mpsc::channel();
        let second_gate = (second_enter, Mutex::new(second_release));
        let (request_gate, custody_gate) = if competing_fence_first {
            (Some(second_gate), None)
        } else {
            (None, Some(second_gate))
        };
        let second_script = Arc::new(ScriptedTransport::new());
        second_script
            .push_response(200, activated(Some(SECRET), false))
            .push_response(200, r#"{"revoked":true}"#)
            .push_failure("offline");
        let second_client = LicensingClient::new(
            GatedWire {
                script: second_script.clone(),
                gate: request_gate,
            },
            API_ORIGIN,
        )
        .expect("fixture client");
        let second_store = GatedCustody {
            store: custody.clone(),
            gate: Mutex::new(custody_gate),
        };
        let mut second = AccountController::new(
            Some(path.clone()),
            second_client,
            second_store,
            TrustedKeys::new(),
            || NOW,
        );
        let b = std::thread::spawn(move || second.execute(Command::RetryActivation));
        wait_second
            .recv_timeout(DEADLINE)
            .expect("competing retry paused");

        release_first
            .send(())
            .expect("first refusal reaches controller");
        let refused = wire(&a.join().expect("first worker"));
        assert_eq!(refused["error_code"], "permission_denied");
        if competing_fence_first {
            assert_eq!(refused["preparation_error_code"], "metadata_changed");
            assert_eq!(first_script.request_count(), 2);
            assert_eq!(
                custody.get(ACCOUNT_SESSION_NAME).expect("custody"),
                Some(Token::new(SESSION))
            );
        } else {
            assert_eq!(refused["operation_state"], "idle");
            assert_eq!(first_script.request_count(), 3);
        }
        release_second.send(()).expect("competing retry resumes");
        let retried = wire(&b.join().expect("second worker"));
        if competing_fence_first {
            assert_eq!(retried["setup_state"], "completed");
            assert_eq!(first_script.request(1), second_script.request(0));
        } else {
            // The pending generation was retired before this process could
            // advance it. This process must dispatch no activation.
            assert_eq!(retried["error_code"], "metadata_changed");
            assert_eq!(second_script.request_count(), 0);
        }
    }
}

fn same_operation_progress_preserves_original_show_once_response_case(replay: bool) {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use std::sync::atomic::{AtomicBool, Ordering};

    struct AdvanceOnSecondDispatch {
        directory: std::path::PathBuf,
        script: ScriptedTransport,
        custody: Custody,
        advanced: AtomicBool,
        replay: bool,
    }
    impl HttpTransport for AdvanceOnSecondDispatch {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound") && !self.advanced.swap(true, Ordering::SeqCst)
            {
                let mut competitor = controller(&self.directory, self.custody.clone());
                if self.replay {
                    competitor
                        .client()
                        .transport()
                        .push_response(200, activated(None, false))
                        .push_response(401, r#"{"error":{"code":"UNAUTHENTICATED"}}"#);
                } else {
                    competitor
                        .client()
                        .transport()
                        .push_failure("competitor's outcome is ambiguous");
                }
                assert_eq!(
                    wire(&competitor.execute(enroll()))["operation_state"],
                    "retry_pending"
                );
                assert_eq!(
                    competitor
                        .client()
                        .transport()
                        .request(0)
                        .expect("competing send")
                        .body,
                    body
                );
            }
            self.script.post_json(url, body, bearer)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }
    let dir = tempfile::tempdir().expect("fixture directory");
    let store = AccountMetadataStore::new(dir.path().into());
    let mut binding = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    binding.activated_public_id = Some(DEVICE.into());
    store.save(&binding).expect("existing binding");
    let custody = Custody::default();
    let original = Token::new("previous-device-credential");
    custody
        .set(DEVICE_TOKEN_NAME, &original)
        .expect("existing custody");
    let transport = AdvanceOnSecondDispatch {
        directory: dir.path().into(),
        script: ScriptedTransport::responding(200, activated(Some(SECRET), true)),
        custody: custody.clone(),
        advanced: AtomicBool::new(false),
        replay,
    };
    let client = LicensingClient::new(transport, API_ORIGIN).expect("origin");
    let mut first = AccountController::new(
        Some(dir.path().into()),
        client,
        custody.clone(),
        TrustedKeys::new(),
        || NOW,
    );
    first.execute(enroll());
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("saved response"),
        Some(Token::new(SECRET))
    );
    assert!(store
        .load_or_create(CredentialPresence::Present)
        .expect("metadata")
        .pending_activation()
        .is_none());
}

#[test]
fn same_operation_progress_preserves_original_show_once_response() {
    same_operation_progress_preserves_original_show_once_response_case(false);
}
#[test]
fn same_operation_no_secret_replay_preserves_delayed_remint_response() {
    same_operation_progress_preserves_original_show_once_response_case(true);
}

#[test]
fn failed_fresh_refusal_retirement_keeps_metadata_and_session_for_existing_retry() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};

    struct BlockRetirement {
        directory: std::path::PathBuf,
        script: ScriptedTransport,
    }
    impl HttpTransport for BlockRetirement {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound-with-session") {
                let lock = self.directory.join("account-metadata.lock");
                std::fs::remove_file(&lock).expect("closed lock");
                std::fs::create_dir(lock).expect("block refusal retirement");
            }
            self.script.post_json(url, body, bearer)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let transport = BlockRetirement {
        directory: dir.path().into(),
        script: ScriptedTransport::responding(200, session_json()),
    };
    transport.script.push_response(
        403,
        bound_refusal("activation_bound_with_session", "PERMISSION_DENIED"),
    );
    let client = LicensingClient::new(transport, API_ORIGIN).expect("origin");
    let mut account = AccountController::new(
        Some(dir.path().into()),
        client,
        custody.clone(),
        TrustedKeys::new(),
        || NOW,
    );
    let refused = wire(&account.execute(sign_in()));
    assert_eq!(refused["error_code"], "permission_denied");
    assert_eq!(refused["preparation_error_code"], "metadata_unavailable");
    assert_eq!(refused["operation_state"], "retry_pending");
    assert_eq!(account.client().transport().script.request_count(), 2);
    std::fs::remove_dir(dir.path().join("account-metadata.lock")).expect("restore writer");
    let mut restarted = controller(dir.path(), custody);
    restarted.client().transport().push_response(
        403,
        bound_refusal("activation_bound_with_session", "PERMISSION_DENIED"),
    );
    assert_eq!(
        wire(&restarted.execute(Command::RetryActivation))["operation_state"],
        "retry_pending"
    );
    assert_eq!(
        account.client().transport().script.request(1),
        restarted.client().transport().request(0)
    );
}

#[test]
fn fresh_refusal_cannot_remove_another_controllers_retry_session() {
    use std::{
        sync::{mpsc, Mutex},
        time::Duration,
    };

    struct PausedRemoval {
        inner: Custody,
        pause: Mutex<Option<(mpsc::Sender<()>, mpsc::Receiver<()>)>>,
    }

    impl SecretStore for PausedRemoval {
        fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
            self.inner.get(name)
        }

        fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
            self.inner.set(name, token)
        }

        fn remove(&self, name: &str) -> Result<(), SecretError> {
            if name == ACCOUNT_SESSION_NAME {
                if let Some((entered, release)) = self.pause.lock().expect("gate").take() {
                    entered
                        .send(())
                        .expect("cleanup has compared the exact original session");
                    release
                        .recv_timeout(Duration::from_secs(8))
                        .expect("continue cleanup");
                }
            }
            self.inner.remove(name)
        }
    }

    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let script = ScriptedTransport::responding(200, session_json());
    script
        .push_response(
            403,
            bound_refusal("activation_bound_with_session", "PERMISSION_DENIED"),
        )
        .push_response(200, r#"{"revoked":true}"#);
    let client = LicensingClient::new(script, API_ORIGIN).expect("origin");
    let (entered, pause) = mpsc::channel();
    let (resume, release) = mpsc::channel();
    let mut first = AccountController::new(
        Some(dir.path().into()),
        client,
        PausedRemoval {
            inner: custody.clone(),
            pause: Mutex::new(Some((entered, release))),
        },
        TrustedKeys::new(),
        || NOW,
    );
    let first_attempt = std::thread::spawn(move || first.execute(sign_in()));
    pause
        .recv_timeout(Duration::from_secs(5))
        .expect("first cleanup paused after matching A");

    let mut second = controller(dir.path(), custody.clone());
    let second_session = "synthetic-retry-session-B";
    second
        .client()
        .transport()
        .push_response(200, session_json().replace(SESSION, second_session))
        .push_failure("replacement activation or cleanup reply lost");
    let during_cleanup = wire(&second.execute(sign_in()));
    resume.send(()).expect("resume original cleanup");
    let first_view = wire(&first_attempt.join().expect("first controller"));
    assert_eq!(first_view["error_code"], "permission_denied");
    assert_eq!(during_cleanup["error_code"], "session_cleanup_unconfirmed");
    assert_eq!(
        during_cleanup["cleanup_error_code"],
        "session_cleanup_unconfirmed"
    );
    assert!(second
        .client()
        .transport()
        .request(1)
        .expect("revoke only")
        .url
        .ends_with("/v1/sessions:revoke"));

    // The OS lock was released at completion. A subsequent authorized sign-in
    // can save B and dispatch. Losing its activation response keeps B retryable.
    second
        .client()
        .transport()
        .push_response(200, session_json().replace(SESSION, second_session))
        .push_failure("replacement activation reply lost");
    let after_cleanup = wire(&second.execute(sign_in()));
    assert_eq!(after_cleanup["operation_state"], "retry_pending");
    assert_eq!(
        custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("B remains in custody"),
        Some(Token::new(second_session))
    );

    let mut restarted = controller(dir.path(), custody);
    restarted
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("offline");
    assert_eq!(
        wire(&restarted.execute(Command::RetryActivation))["setup_state"],
        "completed"
    );
}

#[test]
fn cleanup_cannot_select_a_session_while_a_writer_owns_local_authority() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let store = AccountMetadataStore::new(dir.path().into());
    store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    let custody = Custody::default();
    custody
        .set(ACCOUNT_SESSION_NAME, &Token::new(SESSION))
        .expect("session A");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("device credential");
    let mut account = controller(dir.path(), custody.clone());
    account
        .client()
        .transport()
        .push_response(200, r#"{"revoked":true}"#);

    let competing_writer = store
        .try_lock_account_session()
        .expect("writer owns custody lock");
    let blocked = wire(&account.execute(Command::RetryCleanup));
    assert_eq!(
        blocked["cleanup_error_code"],
        "session_cleanup_local_failure"
    );
    assert_eq!(blocked["pending_cleanup"], true);
    assert_eq!(account.client().transport().request_count(), 0);
    assert_eq!(
        custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("unchanged credential"),
        Some(Token::new(SESSION))
    );

    let replacement = Token::new("synthetic-replacement-while-cleanup-is-blocked");
    custody
        .set(ACCOUNT_SESSION_NAME, &replacement)
        .expect("writer saves session B under lock");
    drop(competing_writer);
    let retried = wire(&account.execute(Command::Startup));
    assert_eq!(retried["pending_cleanup"], true);
    assert_eq!(account.client().transport().request_count(), 0);
    assert_eq!(
        custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("replacement preserved"),
        Some(replacement)
    );
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("device preserved"),
        Some(Token::new(SECRET))
    );
}

#[test]
fn unsafe_session_lock_path_blocks_local_keyring_mutations_until_restored() {
    let dir = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = controller(dir.path(), custody.clone());
    let obstruction = dir.path().join("account-session-custody.lock");
    std::fs::create_dir(&obstruction).expect("unsafe lock path");
    account
        .client()
        .transport()
        .push_response(200, session_json())
        .push_response(200, r#"{"revoked":true}"#);
    let denied = wire(&account.execute(sign_in()));
    assert_eq!(denied["error_code"], "metadata_changed");
    assert_eq!(
        denied["cleanup_error_code"],
        "session_cleanup_local_failure"
    );
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("no stored session")
        .is_none());
    assert_eq!(account.client().transport().request_count(), 2);
    assert!(account
        .client()
        .transport()
        .request(1)
        .expect("revoke unused A")
        .url
        .ends_with("/v1/sessions:revoke"));

    std::fs::remove_dir(obstruction).expect("restore lock path");
    let after_repair = wire(&account.execute(Command::RetryCleanup));
    assert!(after_repair.get("cleanup_error_code").is_none());
    assert_eq!(after_repair["pending_cleanup"], false);
    assert_eq!(account.client().transport().request_count(), 2);
}

#[test]
fn existing_blank_or_invalid_device_entry_never_bootstraps_identity() {
    for raw in ["", "   ", "invalid\ntoken"] {
        let dir = tempfile::tempdir().expect("directory");
        let custody = Custody::default();
        custody
            .set(DEVICE_TOKEN_NAME, &Token::new(raw))
            .expect("entry");
        let mut account = controller(dir.path(), custody);
        assert_eq!(
            wire(&account.execute(Command::Startup))["error_code"],
            "identity_recovery_required"
        );
        assert!(!dir.path().join("account-metadata.json").exists());
    }
}

#[test]
fn cleanup_reservation_survives_lost_ack_and_restart_after_local_remove_failure() {
    use std::sync::atomic::Ordering;
    for lost_ack in [true, false] {
        let dir = tempfile::tempdir().expect("directory");
        let custody = Custody::default();
        let mut first = controller(dir.path(), custody.clone());
        first.execute(Command::Startup);
        custody
            .set(ACCOUNT_SESSION_NAME, &Token::new(SESSION))
            .expect("session");
        custody
            .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
            .expect("device");
        if lost_ack {
            first
                .client()
                .transport()
                .push_failure("server revoked, acknowledgement lost");
        } else {
            first
                .client()
                .transport()
                .push_response(200, r#"{"revoked":true}"#);
            custody.fail_remove.store(true, Ordering::SeqCst);
        }
        assert_eq!(
            wire(&first.execute(Command::RetryCleanup))["pending_cleanup"],
            true
        );
        assert!(
            AccountMetadataStore::new(dir.path().into())
                .load_or_create(CredentialPresence::Present)
                .expect("durable cleanup reservation")
                .cleanup_reserved
        );
        drop(first);
        custody.fail_remove.store(false, Ordering::SeqCst);
        let mut restart = controller(dir.path(), custody.clone());
        restart
            .client()
            .transport()
            .push_response(200, r#"{"revoked":true}"#);
        assert_eq!(
            wire(&restart.execute(Command::RetryCleanup))["pending_cleanup"],
            false
        );
        assert!(custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("removed")
            .is_none());
        assert_eq!(
            custody.get(DEVICE_TOKEN_NAME).expect("device preserved"),
            Some(Token::new(SECRET))
        );
    }
}

#[test]
fn stale_sign_in_cannot_overwrite_the_dispatched_sessions_restart_authority() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    struct LoginRace {
        directory: std::path::PathBuf,
        custody: Custody,
        script: ScriptedTransport,
    }
    impl HttpTransport for LoginRace {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/sessions") {
                let mut dispatcher = controller(&self.directory, self.custody.clone());
                dispatcher
                    .client()
                    .transport()
                    .push_failure("A committed but reply lost");
                assert_eq!(
                    wire(&dispatcher.execute(Command::RetryActivation))["operation_state"],
                    "retry_pending"
                );
            }
            self.script.post_json(url, body, bearer)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }
    let dir = tempfile::tempdir().expect("directory");
    let custody = Custody::default();
    let mut seed = controller(dir.path(), custody.clone());
    seed.client()
        .transport()
        .push_response(200, session_json())
        .push_failure("A sent");
    seed.execute(sign_in());
    let script = ScriptedTransport::responding(
        200,
        session_json()
            .replace(SESSION, "different-org-session-B")
            .replace("org_fixture", "different-org"),
    );
    script.push_response(200, r#"{"revoked":true}"#);
    let mut stale = AccountController::new(
        Some(dir.path().into()),
        LicensingClient::new(
            LoginRace {
                directory: dir.path().into(),
                custody: custody.clone(),
                script,
            },
            API_ORIGIN,
        )
        .expect("client"),
        custody.clone(),
        TrustedKeys::new(),
        || NOW,
    );
    assert_eq!(
        wire(&stale.execute(sign_in()))["error_code"],
        "metadata_changed"
    );
    assert_eq!(
        custody.get(ACCOUNT_SESSION_NAME).expect("A preserved"),
        Some(Token::new(SESSION))
    );
    let mut restart = controller(dir.path(), custody.clone());
    restart
        .client()
        .transport()
        .push_response(200, activated(Some(SECRET), false))
        .push_response(200, r#"{"revoked":true}"#)
        .push_failure("offline refresh");
    assert_eq!(
        wire(&restart.execute(Command::RetryActivation))["setup_state"],
        "completed"
    );
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("device saved"),
        Some(Token::new(SECRET))
    );
}

#[test]
fn later_online_renewal_does_not_inherit_old_signed_license_expiry() {
    let dir = tempfile::tempdir().expect("directory");
    let custody = Custody::default();
    let store = AccountMetadataStore::new(dir.path().into());
    let mut metadata = store
        .load_or_create(CredentialPresence::Missing)
        .expect("identity");
    metadata.activated_public_id = Some(DEVICE.into());
    store.save(&metadata).expect("binding");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("token");
    let (trust, signed) = signed_display(
        metadata.fingerprint(),
        "2026-11-14T15:00:00Z",
        "2026-11-17T16:00:00Z",
        "2026-11-14T15:30:00Z",
    );
    selahcue_licensing::EntitlementCache::new(dir.path())
        .replace(signed.as_bytes(), &trust, DEVICE, metadata.fingerprint())
        .expect("cache");
    let transport = ScriptedTransport::responding(200, refresh_status(true));
    transport.push_response(200, signed);
    let mut account = AccountController::new(
        Some(dir.path().into()),
        LicensingClient::new(transport, API_ORIGIN).expect("client"),
        custody,
        trust,
        || NOW,
    );
    assert_eq!(
        wire(&account.execute(Command::Startup))["license_state"],
        "renewal_needed"
    );
    let refreshed = wire(&account.execute(Command::Refresh { explicit: true }));
    assert_eq!(refreshed["license_state"], "active");
    assert_eq!(refreshed["entitlement_state"], "current");
}

#[test]
fn a_different_operation_still_fences_a_delayed_secret_response() {
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    struct ReplaceOperation {
        directory: std::path::PathBuf,
        script: ScriptedTransport,
    }
    impl HttpTransport for ReplaceOperation {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound") {
                let store = AccountMetadataStore::new(self.directory.clone());
                let mut current = store
                    .load_or_create(CredentialPresence::Missing)
                    .expect("current");
                current.clear_pending_activation();
                current = store.save(&current).expect("retired operation");
                current
                    .begin_activation(
                        crate::account::state::ActivationPath::EnrollmentKey,
                        std::env::consts::OS,
                        env!("CARGO_PKG_VERSION"),
                        "different operation",
                    )
                    .expect("new nonce");
                store.save(&current).expect("new operation");
            }
            self.script.post_json(url, body, bearer)
        }
        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.script.get(url, bearer)
        }
    }
    let dir = tempfile::tempdir().expect("directory");
    let custody = Custody::default();
    let mut account = AccountController::new(
        Some(dir.path().into()),
        LicensingClient::new(
            ReplaceOperation {
                directory: dir.path().into(),
                script: ScriptedTransport::responding(200, activated(Some(SECRET), false)),
            },
            API_ORIGIN,
        )
        .expect("client"),
        custody.clone(),
        TrustedKeys::new(),
        || NOW,
    );
    assert_eq!(
        wire(&account.execute(enroll()))["error_code"],
        "metadata_changed"
    );
    assert!(custody
        .get(DEVICE_TOKEN_NAME)
        .expect("no stale write")
        .is_none());
}

#[test]
fn cleanup_selection_is_fenced_against_a_new_session_dispatch() {
    use std::sync::Mutex;
    struct Interleave {
        custody: Custody,
        dispatch: Mutex<Option<std::path::PathBuf>>,
    }
    impl SecretStore for Interleave {
        fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
            if name == ACCOUNT_SESSION_NAME {
                if let Some(path) = self.dispatch.lock().expect("gate").take() {
                    let mut second = controller(&path, self.custody.clone());
                    second
                        .client()
                        .transport()
                        .push_response(200, session_json().replace(SESSION, "session-B"))
                        .push_response(200, r#"{"revoked":true}"#);
                    assert_eq!(
                        wire(&second.execute(sign_in()))["error_code"],
                        "metadata_changed"
                    );
                    assert!(!second
                        .client()
                        .transport()
                        .recorded()
                        .iter()
                        .any(|r| r.url.contains("/v1/activations")));
                }
            }
            self.custody.get(name)
        }
        fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
            self.custody.set(name, token)
        }
        fn remove(&self, name: &str) -> Result<(), SecretError> {
            self.custody.remove(name)
        }
    }
    let dir = tempfile::tempdir().expect("directory");
    AccountMetadataStore::new(dir.path().into())
        .load_or_create(CredentialPresence::Missing)
        .expect("metadata");
    let custody = Custody::default();
    custody
        .set(ACCOUNT_SESSION_NAME, &Token::new(SESSION))
        .expect("A");
    let client = LicensingClient::new(
        ScriptedTransport::responding(200, r#"{"revoked":true}"#),
        API_ORIGIN,
    )
    .expect("client");
    let mut cleanup = AccountController::new(
        Some(dir.path().into()),
        client,
        Interleave {
            custody: custody.clone(),
            dispatch: Mutex::new(Some(dir.path().into())),
        },
        TrustedKeys::new(),
        || NOW,
    );
    assert_eq!(
        wire(&cleanup.execute(Command::RetryCleanup))["pending_cleanup"],
        false
    );
    assert!(custody
        .get(ACCOUNT_SESSION_NAME)
        .expect("only captured A removed")
        .is_none());
    let mut second = controller(dir.path(), custody.clone());
    second
        .client()
        .transport()
        .push_response(200, session_json().replace(SESSION, "session-B"))
        .push_failure("B reply lost");
    assert_eq!(
        wire(&second.execute(sign_in()))["operation_state"],
        "retry_pending"
    );
    assert_eq!(
        custody.get(ACCOUNT_SESSION_NAME).expect("B preserved"),
        Some(Token::new("session-B"))
    );
}

#[test]
fn skip_is_durable_while_bound_activation_http_is_held() {
    use crate::account::controller::Worker;
    use selahcue_cloud::{transport::HttpResponse, HttpTransport, TransportError};
    use std::sync::{mpsc, Mutex};
    use std::time::Duration;

    struct HeldActivation {
        transport: ScriptedTransport,
        entered: mpsc::Sender<()>,
        release: Mutex<mpsc::Receiver<()>>,
    }

    impl HttpTransport for HeldActivation {
        fn post_json(
            &self,
            url: &str,
            body: &str,
            bearer: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            if url.ends_with("/v1/activations:bound-with-session") {
                self.entered.send(()).expect("activation reached HTTP");
                self.release
                    .lock()
                    .expect("receiver")
                    .recv_timeout(Duration::from_secs(8))
                    .expect("test releases HTTP");
            }
            self.transport.post_json(url, body, bearer)
        }

        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            self.transport.get(url, bearer)
        }
    }

    for activation_succeeds in [false, true] {
        let dir = tempfile::tempdir().expect("fixture directory");
        let path = dir.path().to_path_buf();
        let store = AccountMetadataStore::new(path.clone());
        let custody = Custody::default();
        let transport = ScriptedTransport::new();
        transport.push_response(200, session_json());
        if activation_succeeds {
            transport
                .push_response(200, activated(Some(SECRET), false))
                .push_response(200, r#"{"revoked":true}"#)
                .push_failure("synthetic refresh failure");
        } else {
            transport.push_failure("synthetic activation failure");
        }
        let (entered, wait) = mpsc::channel();
        let (release, held) = mpsc::channel();
        let worker = Worker::new(AccountController::new(
            Some(path),
            LicensingClient::new(
                HeldActivation {
                    transport,
                    entered,
                    release: Mutex::new(held),
                },
                API_ORIGIN,
            )
            .expect("licensing client"),
            custody.clone(),
            TrustedKeys::new(),
            || NOW,
        ));
        worker
            .admit()
            .unwrap_or_else(|_| panic!("startup slot"))
            .run(Command::Startup);
        let work = worker.admit().unwrap_or_else(|_| panic!("activation slot"));
        let activation = std::thread::spawn(move || work.run(sign_in()));
        wait.recv_timeout(Duration::from_secs(4))
            .expect("held HTTP");
        let before = store
            .load_or_create(CredentialPresence::Unavailable)
            .expect("frozen operation before Skip");
        assert!(before.pending_activation().is_some());
        let skip = worker.skip_setup();
        let after = store
            .load_or_create(CredentialPresence::Unavailable)
            .expect("frozen operation after Skip");
        let restarted = controller(dir.path(), custody.clone()).execute(Command::Startup);
        let session = custody.get(ACCOUNT_SESSION_NAME).expect("account custody");
        let device = custody.get(DEVICE_TOKEN_NAME).expect("device custody");
        release.send(()).expect("release HTTP");
        let late = activation.join().expect("activation worker");

        let skip = skip.expect("Skip acknowledged before HTTP release");
        assert_eq!(wire(&skip)["setup_state"], "skipped");
        assert_eq!(wire(&skip)["operation_state"], "busy");
        assert_eq!(wire(&restarted)["setup_state"], "skipped");
        assert_eq!(wire(&late)["error_code"], "network_unavailable");
        assert!(late.revision > skip.revision);
        assert_eq!(after, before);
        assert_eq!(session, Some(Token::new(SESSION)));
        assert_eq!(device, None);
        if activation_succeeds {
            assert_eq!(wire(&late)["setup_state"], "completed");
            assert_eq!(
                custody.get(DEVICE_TOKEN_NAME).expect("saved device"),
                Some(Token::new(SECRET))
            );
            assert_eq!(
                custody.get(ACCOUNT_SESSION_NAME).expect("cleaned session"),
                None
            );
            // Completion must not erase the independent Skip preference even
            // when a future restart finds that system custody is missing.
            custody
                .remove(DEVICE_TOKEN_NAME)
                .expect("simulate later OS-store loss");
            let restarted = controller(dir.path(), custody).execute(Command::Startup);
            assert_eq!(wire(&restarted)["device_state"], "credential_missing");
            assert_eq!(wire(&restarted)["setup_state"], "skipped");
        } else {
            assert_eq!(wire(&late)["setup_state"], "skipped");
        }
    }
}

#[test]
fn unsafe_dismissal_path_leaves_setup_pending_and_can_be_retried() {
    use crate::account::controller::Worker;

    let dir = tempfile::tempdir().expect("fixture directory");
    let worker = Worker::new(controller(dir.path(), Custody::default()));
    worker
        .admit()
        .unwrap_or_else(|_| panic!("startup slot"))
        .run(Command::Startup);

    let marker = dir.path().join("account-setup-dismissed");
    std::fs::create_dir(&marker).expect("block dismissal write");
    assert!(worker.skip_setup().is_err());
    assert_eq!(wire(&worker.view())["setup_state"], "needed");

    std::fs::remove_dir(marker).expect("allow dismissal write");
    assert_eq!(
        wire(&worker.skip_setup().expect("dismissal retried"))["setup_state"],
        "skipped"
    );
}

// Fabricated values with the same shape as device credentials from the API.
const STAFF_REPLACEMENT: &str = "SC-DEV-AB23-CD45-EF67-GH89-JK23-LM45-NP67-QR89";
const SIBLING_REPLACEMENT: &str = "SC-DEV-ST23-UV45-WX67-YZ89-AB23-CD45-EF67-GH89";

enum StaffRefreshReply {
    Replacement,
    StaleReplacement,
    Unauthorized { custody_updated: bool },
    ManifestUnauthorized { custody_updated: bool },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum StaffBearer {
    Original,
    Replacement,
    Sibling,
    Other,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum StaffRoute {
    Status,
    Manifest,
}

#[derive(Clone, Copy, Debug)]
struct StaffRequest {
    route: StaffRoute,
    bearer: StaffBearer,
    stored: bool,
    replacement_read_back: bool,
    negotiated_rotation: bool,
}

#[derive(Default)]
struct StaffCustodyTrace {
    saved_replacement: std::cell::Cell<bool>,
    read_back_replacement: std::cell::Cell<bool>,
}

#[derive(Clone)]
struct StaffCustody {
    inner: Custody,
    trace: std::rc::Rc<StaffCustodyTrace>,
}

impl SecretStore for StaffCustody {
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
        let token = self.inner.get(name)?;
        if name == DEVICE_TOKEN_NAME && token.as_ref().map(Token::expose) == Some(STAFF_REPLACEMENT)
        {
            self.trace.read_back_replacement.set(true);
        }
        Ok(token)
    }

    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
        self.inner.set(name, token)?;
        if name == DEVICE_TOKEN_NAME {
            self.trace.read_back_replacement.set(false);
            if token.expose() == STAFF_REPLACEMENT {
                self.trace.saved_replacement.set(true);
            }
        }
        Ok(())
    }

    fn remove(&self, name: &str) -> Result<(), SecretError> {
        self.inner.remove(name)?;
        if name == DEVICE_TOKEN_NAME {
            self.trace.read_back_replacement.set(false);
        }
        Ok(())
    }
}

struct StaffRefreshTransport {
    reply: StaffRefreshReply,
    custody: StaffCustody,
    storage: AccountMetadataStore,
    extended_manifest: String,
    sibling_manifest: String,
    requests: std::cell::RefCell<Vec<StaffRequest>>,
}

impl StaffRefreshTransport {
    fn store_sibling_credential(&self) {
        // A cooperating controller can take ownership while the response is
        // outstanding. Closing the handle releases the lock before delivery.
        let _ownership = self
            .storage
            .try_lock_account_session()
            .expect("sibling can acquire ownership during HTTP");
        self.custody
            .inner
            .set(DEVICE_TOKEN_NAME, &Token::new(SIBLING_REPLACEMENT))
            .expect("sibling stores its current credential");
    }

    fn record_request(
        &self,
        route: StaffRoute,
        bearer: Option<&str>,
        negotiated_rotation: bool,
    ) -> StaffRequest {
        let role = match bearer {
            Some(SECRET) => StaffBearer::Original,
            Some(STAFF_REPLACEMENT) => StaffBearer::Replacement,
            Some(SIBLING_REPLACEMENT) => StaffBearer::Sibling,
            _ => StaffBearer::Other,
        };
        // The fixture's observation must not stand in for the controller's own
        // read-back through SecretStore after a successful write.
        let saved = self
            .custody
            .inner
            .get(DEVICE_TOKEN_NAME)
            .expect("custody at HTTP request");
        let request = StaffRequest {
            route,
            bearer: role,
            stored: bearer.is_some() && saved.as_ref().map(Token::expose) == bearer,
            replacement_read_back: self.custody.trace.read_back_replacement.get(),
            negotiated_rotation,
        };
        self.requests.borrow_mut().push(request);
        request
    }
}

impl selahcue_licensing::HttpTransport for StaffRefreshTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_licensing::TransportError> {
        use selahcue_cloud::transport::HttpResponse;
        assert!(url.ends_with("/v1/license:refresh"));
        let request = serde_json::from_str::<Value>(body).expect("refresh payload");
        let request = self.record_request(
            StaffRoute::Status,
            bearer,
            request == json!({"token_rotation":"staff-extension-v1"}),
        );
        if let (StaffBearer::Original, StaffRefreshReply::Unauthorized { custody_updated }) =
            (request.bearer, &self.reply)
        {
            if *custody_updated {
                self.store_sibling_credential();
            }
            return Ok(HttpResponse {
                status: 401,
                body: "{}".into(),
            });
        }
        if !request.stored {
            return Ok(HttpResponse {
                status: 401,
                body: "{}".into(),
            });
        }
        let mut status: Value =
            serde_json::from_str(&refresh_status(true)).expect("fixture status");
        status["surface"] = json!("desktop");
        status["operation"] = json!("license_refresh");
        status["entitlement"] = json!({"feature_scope":"CHURCH","territory":""});
        if request.bearer == StaffBearer::Original {
            if matches!(&self.reply, StaffRefreshReply::StaleReplacement) {
                self.store_sibling_credential();
            }
            if !matches!(&self.reply, StaffRefreshReply::ManifestUnauthorized { .. }) {
                // Expose adoption and ordering even on the legacy unit request.
                status["activation_token"] = json!(STAFF_REPLACEMENT);
            }
        } else if request.bearer == StaffBearer::Sibling {
            status["license"]["expires_at"] = json!("2027-02-01T00:00:00Z");
            status["token"]["expires_at"] = json!("2027-02-01T00:00:00Z");
        }
        Ok(HttpResponse {
            status: 200,
            body: status.to_string(),
        })
    }

    fn get(
        &self,
        url: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_licensing::TransportError> {
        use selahcue_cloud::transport::HttpResponse;
        assert!(url.ends_with("/v1/entitlements/manifest"));
        let request = self.record_request(StaffRoute::Manifest, bearer, false);
        let manifest = match (request.bearer, request.stored, &self.reply) {
            (StaffBearer::Replacement, true, _) => Some(&self.extended_manifest),
            (StaffBearer::Sibling, true, _) => Some(&self.sibling_manifest),
            (StaffBearer::Original, _, StaffRefreshReply::StaleReplacement) => {
                // Give an erroneously sent GET a distinct, valid but stale
                // signed result. It must never replace the winning cache.
                Some(&self.extended_manifest)
            }
            (
                StaffBearer::Original,
                _,
                StaffRefreshReply::ManifestUnauthorized {
                    custody_updated: true,
                },
            ) => {
                self.store_sibling_credential();
                None
            }
            _ => None,
        };
        Ok(match manifest {
            Some(body) => HttpResponse {
                status: 200,
                body: body.clone(),
            },
            None => HttpResponse {
                status: 401,
                body: "{}".into(),
            },
        })
    }
}

fn staff_refresh_controller(
    directory: &Path,
    custody: &Custody,
    reply: StaffRefreshReply,
) -> AccountController<StaffRefreshTransport, StaffCustody> {
    let storage = AccountMetadataStore::new(directory.into());
    let mut binding = storage
        .load_or_create(CredentialPresence::Missing)
        .expect("fixture installation");
    binding.activated_public_id = Some(DEVICE.into());
    let binding = storage.save(&binding).expect("established installation");
    custody
        .set(DEVICE_TOKEN_NAME, &Token::new(SECRET))
        .expect("initial device custody");
    let manifest = |expiry| {
        signed_display(
            binding.fingerprint(),
            "2026-11-14T12:00:00Z",
            expiry,
            expiry,
        )
    };
    let (trust, initial) = manifest("2026-12-01T00:00:00Z");
    selahcue_licensing::EntitlementCache::new(directory)
        .replace(initial.as_bytes(), &trust, DEVICE, binding.fingerprint())
        .expect("current signed cache");
    let (_, extended_manifest) = manifest("2027-01-01T00:00:00Z");
    let (_, sibling_manifest) = manifest("2027-02-01T00:00:00Z");
    let custody = StaffCustody {
        inner: custody.clone(),
        trace: Default::default(),
    };
    let transport = StaffRefreshTransport {
        reply,
        custody: custody.clone(),
        storage,
        extended_manifest,
        sibling_manifest,
        requests: Default::default(),
    };
    let client = LicensingClient::new(transport, API_ORIGIN).expect("static origin");
    AccountController::new(Some(directory.into()), client, custody, trust, || NOW)
}

#[test]
fn negotiated_refresh_stores_replacement_before_requesting_the_signed_manifest() {
    let directory = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account =
        staff_refresh_controller(directory.path(), &custody, StaffRefreshReply::Replacement);
    let result = wire(&account.execute(Command::Refresh { explicit: true }));
    let transport = account.client().transport();
    let requests = transport.requests.borrow();
    let [status, manifest] = requests.as_slice() else {
        panic!("refresh must request status and then a manifest");
    };
    assert!(
        manifest.route == StaffRoute::Manifest
            && manifest.bearer == StaffBearer::Replacement
            && manifest.stored,
        "manifest GET must use the replacement already saved in device custody"
    );
    assert!(
        status.route == StaffRoute::Status
            && status.bearer == StaffBearer::Original
            && status.negotiated_rotation,
        "refresh must negotiate staff extension using the original credential"
    );
    assert!(result["error_code"].is_null());
    assert_eq!(result["entitlement_state"], "current");
    assert_eq!(result["license_expires_at"], "2027-01-01T00:00:00Z");
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("final custody"),
        Some(Token::new(STAFF_REPLACEMENT))
    );
}

#[test]
fn refresh_store_failure_keeps_answer_for_local_retry() {
    use std::sync::atomic::Ordering;
    let directory = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account =
        staff_refresh_controller(directory.path(), &custody, StaffRefreshReply::Replacement);
    custody.fail_write.store(true, Ordering::SeqCst);
    let result = wire(&account.execute(Command::Refresh { explicit: true }));
    assert_eq!(
        custody.denied_device_writes.load(Ordering::SeqCst),
        1,
        "refresh should attempt to save the real-shaped replacement before fetching a manifest"
    );
    assert_eq!(result["device_state"], "credential_not_saved");
    assert_eq!(result["entitlement_state"], "current");
    assert_eq!(result["license_expires_at"], "2026-12-01T00:00:00Z");
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("preserved custody"),
        Some(Token::new(SECRET))
    );
    assert!(matches!(
        account.client().transport().requests.borrow().as_slice(),
        [StaffRequest {
            route: StaffRoute::Status,
            ..
        }]
    ));

    custody.fail_write.store(false, Ordering::SeqCst);
    let result = wire(&account.execute(Command::RetryActivation));
    let transport = account.client().transport();
    let requests = transport.requests.borrow();
    let (initial, retry_requests) = requests.split_first().expect("initial status request");
    assert!(initial.bearer == StaffBearer::Original && initial.negotiated_rotation);
    assert!(
        retry_requests
            .iter()
            .all(|request| request.bearer != StaffBearer::Original),
        "local save retry must not re-use the superseded original bearer"
    );
    assert!(
        retry_requests.iter().all(|request| {
            request.bearer == StaffBearer::Replacement
                && request.stored
                && request.replacement_read_back
        }),
        "local retry must save and read back the retained credential before any network use"
    );
    assert_eq!(
        retry_requests
            .iter()
            .filter(|request| request.route == StaffRoute::Manifest)
            .count(),
        1,
        "local retry must fetch a signed manifest after saving the credential"
    );
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("retried custody"),
        Some(Token::new(STAFF_REPLACEMENT))
    );
    assert!(result["error_code"].is_null());
    assert_eq!(result["entitlement_state"], "current");
    assert_eq!(result["license_expires_at"], "2027-01-01T00:00:00Z");
}

#[test]
fn stale_refresh_response_cannot_replace_newer_custody() {
    let directory = tempfile::tempdir().expect("fixture directory");
    let custody = Custody::default();
    let mut account = staff_refresh_controller(
        directory.path(),
        &custody,
        StaffRefreshReply::StaleReplacement,
    );
    let storage = AccountMetadataStore::new(directory.path().into());
    let before = storage
        .load_or_create(CredentialPresence::Unavailable)
        .expect("original metadata");
    let cache_path = selahcue_licensing::EntitlementCache::new(directory.path()).path();
    let read_manifest = || {
        let bytes = std::fs::read(&cache_path).expect("signed cache");
        serde_json::from_slice::<Value>(&bytes).expect("signed envelope")
    };
    let original_manifest = read_manifest();
    let result = wire(&account.execute(Command::Refresh { explicit: true }));
    let transport = account.client().transport();

    let requests = transport.requests.borrow();
    let (initial, follow_ups) = requests.split_first().expect("initial status request");
    assert!(
        initial.route == StaffRoute::Status
            && initial.bearer == StaffBearer::Original
            && initial.stored,
        "fixture must start a status request with the originally stored bearer"
    );
    assert!(
        !transport.custody.trace.saved_replacement.get(),
        "the stale answer must never enter custody, even temporarily"
    );
    assert_eq!(
        custody.get(DEVICE_TOKEN_NAME).expect("current custody"),
        Some(Token::new(SIBLING_REPLACEMENT)),
        "the older response must leave the sibling's current credential in custody"
    );
    assert!(
        follow_ups
            .iter()
            .all(|request| request.bearer != StaffBearer::Original),
        "the older response must not use the superseded bearer in a follow-up request"
    );
    let mut sibling_status_read = false;
    let mut sibling_manifest_read = false;
    for request in follow_ups {
        assert!(
            request.bearer == StaffBearer::Sibling && request.stored,
            "a follow-up may use only the sibling's stored credential"
        );
        match request.route {
            StaffRoute::Status => sibling_status_read = true,
            StaffRoute::Manifest => {
                assert!(
                    sibling_status_read,
                    "a new manifest fetch requires fresh sibling status"
                );
                sibling_manifest_read = true;
            }
        }
    }
    let (expected_manifest, expected_expiry) = if sibling_manifest_read {
        (
            serde_json::from_str(&transport.sibling_manifest).expect("sibling signed envelope"),
            "2027-02-01T00:00:00Z",
        )
    } else {
        (original_manifest, "2026-12-01T00:00:00Z")
    };
    assert!(
        read_manifest() == expected_manifest,
        "the signed cache may change only to the manifest from a fresh sibling read"
    );
    assert_eq!(
        storage
            .load_or_create(CredentialPresence::Unavailable)
            .expect("unchanged installation"),
        before
    );
    assert_eq!(result["device_state"], "credential_present");
    assert_eq!(result["entitlement_state"], "current");
    assert_eq!(result["manifest_expires_at"], expected_expiry);
    assert_eq!(result["license_expires_at"], expected_expiry);
}

#[test]
fn stale_refresh_401_does_not_reject_newer_custody() {
    for custody_updated in [false, true] {
        let directory = tempfile::tempdir().expect("fixture directory");
        let custody = Custody::default();
        let mut account = staff_refresh_controller(
            directory.path(),
            &custody,
            StaffRefreshReply::Unauthorized { custody_updated },
        );
        let storage = AccountMetadataStore::new(directory.path().into());
        let before = storage
            .load_or_create(CredentialPresence::Unavailable)
            .expect("original metadata");
        let result = wire(&account.execute(Command::Refresh { explicit: true }));
        let transport = account.client().transport();
        let requests = transport.requests.borrow();
        let initial = requests.first().expect("initial status request");
        assert!(initial.route == StaffRoute::Status && initial.bearer == StaffBearer::Original);
        assert!(requests
            .iter()
            .all(|request| request.route != StaffRoute::Manifest));
        assert_eq!(
            storage
                .load_or_create(CredentialPresence::Unavailable)
                .expect("unchanged installation"),
            before
        );
        assert_eq!(result["entitlement_state"], "current");
        if custody_updated {
            assert_eq!(
                result["device_state"], "credential_present",
                "a status 401 for the previous bearer must leave current custody usable"
            );
            assert_ne!(
                result["error_code"], "reauthentication_required",
                "a stale status error must not ask the operator to sign in"
            );
            assert_eq!(
                custody.get(DEVICE_TOKEN_NAME).expect("current custody"),
                Some(Token::new(SIBLING_REPLACEMENT))
            );
        } else {
            assert_eq!(
                result["device_state"], "reauthentication_needed",
                "a 401 for the current bearer still requires reauthentication"
            );
        }
    }
}

#[test]
fn stale_manifest_401_does_not_reject_newer_custody() {
    for custody_updated in [false, true] {
        let directory = tempfile::tempdir().expect("fixture directory");
        let custody = Custody::default();
        let mut account = staff_refresh_controller(
            directory.path(),
            &custody,
            StaffRefreshReply::ManifestUnauthorized { custody_updated },
        );
        let storage = AccountMetadataStore::new(directory.path().into());
        let before = storage
            .load_or_create(CredentialPresence::Unavailable)
            .expect("original metadata");
        let result = wire(&account.execute(Command::Refresh { explicit: true }));
        let transport = account.client().transport();

        let requests = transport.requests.borrow();
        let [status, manifest, ..] = requests.as_slice() else {
            panic!("fixture must reach the manifest request");
        };
        assert!(status.route == StaffRoute::Status && status.bearer == StaffBearer::Original);
        assert!(manifest.route == StaffRoute::Manifest && manifest.bearer == StaffBearer::Original);
        assert_eq!(
            storage
                .load_or_create(CredentialPresence::Unavailable)
                .expect("unchanged installation"),
            before
        );
        assert_eq!(result["entitlement_state"], "current");
        assert_eq!(result["manifest_expires_at"], "2026-12-01T00:00:00Z");
        if custody_updated {
            assert_eq!(
                custody.get(DEVICE_TOKEN_NAME).expect("current custody"),
                Some(Token::new(SIBLING_REPLACEMENT))
            );
            assert_eq!(
                result["device_state"], "credential_present",
                "a manifest 401 for the previous bearer must leave current custody usable"
            );
            assert_ne!(
                result["error_code"], "reauthentication_required",
                "a stale manifest error must not ask the operator to sign in"
            );
        } else {
            assert_eq!(
                result["device_state"], "reauthentication_needed",
                "a manifest 401 for the current bearer still requires reauthentication"
            );
        }
    }
}
