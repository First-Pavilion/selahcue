//! Live run of the REAL desktop client (ReqwestTransport + selahcue-licensing) against a
//! locally running API. Prints outcomes only: never a token, password or response body.
use selahcue_cloud::transport::ReqwestTransport;
use selahcue_cloud::HttpTransport;
use selahcue_licensing::{
    ActivationFailure, DeviceCredentials, DeviceIdentity, IdempotencyKey, InMemorySecretStore,
    LicensingClient, Token,
};

fn main() {
    let base = std::env::args().nth(1).expect("base url");
    let seed: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(std::env::args().nth(2).expect("seed")).unwrap()).unwrap();
    // The password is random per seed run and lives only in the 0600 seed file (seed_live_api.py);
    // it is read here and never printed.
    let password = seed["password"].as_str().unwrap().to_string();
    let enrollment_key = seed["enrollment_key"].as_str().unwrap().to_string();

    // 0. CONTROL: what the old path got. Same transport, the old route.
    let raw = ReqwestTransport::new().unwrap();
    let old = raw
        .post_json(&format!("{base}/graphql/account"), r#"{"query":"{__typename}"}"#, None)
        .unwrap();
    println!("[control] POST /graphql/account (old route) -> HTTP {} ; html_body={}", old.status, old.body.trim_start().starts_with('<'));

    let client = LicensingClient::new(ReqwestTransport::new().unwrap(), base.clone());
    let creds = DeviceCredentials::new(InMemorySecretStore::new());
    let id = |fp: &str, name: &str| DeviceIdentity::new(fp, "macos", "1.0.0", name).unwrap();
    let idem = |s: &str| IdempotencyKey::new(s).unwrap();

    // 1. Admin: sign in, then activate.
    let session = client.sign_in("admin@grace.example", &Token::new(&password)).expect("admin sign-in");
    println!("[admin] sign_in OK: role={} org_id={} expires_at={} session_token_len={}", session.role, session.org_id, session.expires_at, session.token.expose().len());
    let a = client.activate_with_session(&session.token, &id("live-fp-booth-1", "Live booth 1"), &idem("live-idem-000001")).expect("activate");
    println!("[admin] activate_with_session OK: path={:?} created={} reminted={} device={} platform={} token_issued={} token_prefix={:?} license_status={} license_expires={}",
        a.path, a.created, a.reminted, a.device_public_id, a.platform, a.token.is_some(), a.token_meta.prefix, a.license.status, a.license.expires_at);
    println!("[admin] persist -> {:?}; device token held in store: {}", a.persist(&creds).unwrap(), creds.is_activated().unwrap());
    // Use the minted token against the rest of /v1 (status only).
    let dt = creds.device_token().unwrap().unwrap();
    let refresh = raw.post_json(&format!("{base}/v1/license:refresh"), "{}", Some(dt.expose())).unwrap();
    println!("[admin] minted device token against POST /v1/license:refresh -> HTTP {}", refresh.status);
    // Replay with the same idempotency key: show-once, no second token.
    let r = client.activate_with_session(&session.token, &id("live-fp-booth-1", "Live booth 1"), &idem("live-idem-000001")).expect("replay");
    println!("[admin] replay: created={} reminted={} token_issued={} disposition={:?} persist={:?}", r.created, r.reminted, r.token.is_some(), r.disposition(), r.persist(&creds).unwrap());

    // 2. Typed failures.
    let show = |label: &str, f: ActivationFailure| println!("[{label}] -> {:?} | permits_presentation={} retryable={} | \"{}\"", f, f.permits_presentation(), f.is_retryable(), f);
    show("wrong password", client.sign_in("admin@grace.example", &Token::new("not-the-password")).unwrap_err());
    show("unknown email", client.sign_in("nobody@grace.example", &Token::new("not-the-password")).unwrap_err());
    show("unverified account", client.sign_in("unverified@grace.example", &Token::new(&password)).unwrap_err());
    let member = client.sign_in("member@grace.example", &Token::new(&password)).expect("member sign-in");
    println!("[member] sign_in OK: role={}", member.role);
    show("MEMBER activation", client.activate_with_session(&member.token, &id("live-fp-member", "Member box"), &idem("live-idem-member1")).unwrap_err());
    let empty = client.sign_in("admin@empty.example", &Token::new(&password)).expect("empty-org sign-in");
    println!("[no-licence admin] sign_in OK: role={}", empty.role);
    show("no active licence", client.activate_with_session(&empty.token, &id("live-fp-empty", "Empty org box"), &idem("live-idem-empty01")).unwrap_err());
    show("bad session token", client.activate_with_session(&Token::new("sess-not-a-real-session"), &id("live-fp-x", "x"), &idem("live-idem-bad0001")).unwrap_err());

    // 3. The enrollment-key path, unchanged.
    let k = client.activate_with_enrollment_key(&Token::new(&enrollment_key), &id("live-fp-booth-2", "Live booth 2"), &idem("live-idem-key0001")).expect("key activation");
    println!("[enrollment key] OK: path={:?} created={} reminted={} device={} token_issued={} license_status={}", k.path, k.created, k.reminted, k.device_public_id, k.token.is_some(), k.license.status);
    show("enrollment key (wrong key)", client.activate_with_enrollment_key(&Token::new("SC-TRIAL-NOPE-NOPE"), &id("live-fp-booth-3", "b3"), &idem("live-idem-key0002")).unwrap_err());
}
