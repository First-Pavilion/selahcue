use std::{path::Path, sync::Arc};

use selahcue_licensing::{
    InMemorySecretStore, LicensingClient, ScriptedTransport, SecretError, SecretStore, Token,
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
    fail_remove: Arc<std::sync::atomic::AtomicBool>,
}

impl SecretStore for Custody {
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
        self.store.get(name)
    }

    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
        if name == DEVICE_TOKEN_NAME && self.fail_write.load(std::sync::atomic::Ordering::SeqCst) {
            return Err(SecretError("synthetic keyring denial".into()));
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
    let skipped = wire(&account.execute(Command::Skip));
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
        "/v1/activations:with-session",
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
    let finished = first.run(Command::Skip);
    assert!(finished.revision > second.revision);
    assert_eq!(wire(&worker.view())["setup_state"], "skipped");
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

    struct Wire {
        inner: ReqwestTransport,
        custody: Custody,
        directory: std::path::PathBuf,
        offline: Arc<AtomicBool>,
        expected_remint: Arc<AtomicBool>,
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
                assert!(self
                    .custody
                    .get(DEVICE_TOKEN_NAME)
                    .expect("fixture custody")
                    .is_some());
                let metadata = AccountMetadataStore::new(self.directory.clone())
                    .load_or_create(CredentialPresence::Present)
                    .expect("persisted device binding before revoke");
                assert!(metadata.activated_public_id.is_some());
                assert!(metadata.pending_activation().is_none());
            }
            let response = self.inner.post_json(url, body, bearer)?;
            if (url.ends_with("/v1/activations") || url.ends_with("/v1/activations:with-session"))
                && response.status == 200
                && self.expected_remint.swap(false, Ordering::SeqCst)
            {
                let parsed: Value =
                    serde_json::from_str(&response.body).expect("activation response fixture");
                assert_eq!(parsed["created"], false);
                assert_eq!(parsed["reminted"], true);
                assert!(parsed["activation_token"].is_string());
            }
            Ok(response)
        }

        fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
            if self.offline.load(Ordering::SeqCst) {
                return Err(TransportError("synthetic network unavailable".into()));
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
        "cascade" => Command::SignIn {
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
    for (status, expected) in [
        (200, "credential_present"),
        (401, "reauthentication_needed"),
    ] {
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
        assert!(custody
            .get(ACCOUNT_SESSION_NAME)
            .expect("cleanup")
            .is_none());
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
            if url.ends_with("/v1/activations") && !self.drained.swap(true, Ordering::SeqCst) {
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
    assert!(requests[0].url.ends_with("/v1/activations"));
    assert!(requests[1].url.ends_with("/v1/license:refresh"));
}
