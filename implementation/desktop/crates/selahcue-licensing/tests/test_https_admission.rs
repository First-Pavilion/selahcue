//! DNU first-hop admission through the actual licensing consumer and real receiver.
#![allow(clippy::unwrap_used)]
#[path = "../../selahcue-cloud/tests/support/credential_receiver.rs"]
mod credential_receiver;
use credential_receiver::Receiver;
use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use selahcue_licensing::{
    DeviceIdentity, IdempotencyKey, LicensingClient, ScriptedTransport, Token,
};

const SECRET: &str = "DNU-LICENSING-CREDENTIAL-56e1";

fn insecure_operation(operation: &str) {
    let receiver = Receiver::start();
    let constructed = LicensingClient::new(ReqwestTransport::new().unwrap(), &receiver.base);
    let refused_at_construction = constructed.is_err();
    // A removed constructor guard must still exercise the real consumer, rather than pass
    // because a second transport guard happened to prevent its credential request.
    if let Ok(client) = constructed {
        let credential = Token::new(SECRET);
        let identity = DeviceIdentity::new("dnu-fingerprint", "linux", "1.0", "DNU test").unwrap();
        let idem = IdempotencyKey::new("dnu-idem-0123456789").unwrap();
        match operation {
            "password" => {
                let _ = client.sign_in("a@example.test", &credential);
            }
            "enrollment" => {
                let _ = client.activate_with_enrollment_key(&credential, &identity, &idem);
            }
            "session" => {
                let _ = client.activate_with_session(&credential, &identity, &idem);
            }
            "revoke" => {
                let _ = client.revoke_session(&credential);
            }
            _ => unreachable!(),
        }
    }
    let seen = receiver.finish();
    assert!(
        refused_at_construction,
        "ordinary licensing constructor must refuse HTTP"
    );
    // No request, not merely no bearer: credentials also travel in JSON bodies.
    assert!(
        seen.is_empty(),
        "DNU refused HTTP consumer {operation} must make zero requests; observed {}",
        seen.len()
    );
}
#[test]
fn dnu_http_password_is_refused_before_send() {
    insecure_operation("password");
}
#[test]
fn dnu_http_enrollment_is_refused_before_send() {
    insecure_operation("enrollment");
}
#[test]
fn dnu_http_session_is_refused_before_send() {
    insecure_operation("session");
}
#[test]
fn dnu_http_revoke_is_refused_before_send() {
    insecure_operation("revoke");
}

#[test]
fn dnu_insecure_scheme_refusal_does_not_echo_configuration() {
    for base in [
        "http://alice:URL-SECRET@127.0.0.1/?query=QUERY-SECRET",
        "ftp://alice:URL-SECRET@example.test",
        "//example.test/?QUERY-SECRET",
        "httpsnot://example.test/?QUERY-SECRET",
        "",
        "https://",
    ] {
        let error =
            match LicensingClient::new(ScriptedTransport::failing("fixed test failure"), base) {
                Err(error) => error,
                Ok(_) => panic!("invalid base must refuse at construction before transport"),
            };
        let message = format!("{error} {error:?}");
        assert!(message.contains("HTTPS"));
        for secret in ["URL-SECRET", "QUERY-SECRET", SECRET, "alice"] {
            assert!(!message.contains(secret));
        }
    }
}

#[test]
fn dnu_real_receiver_positive_records_body_and_bearer() {
    let receiver = Receiver::start();
    let response = ReqwestTransport::new_for_loopback_tests()
        .unwrap()
        .post_json(&receiver.base, SECRET, Some(SECRET))
        .unwrap();
    assert_eq!(response.status, 503);
    let seen = receiver.finish();
    assert_eq!(seen.len(), 1);
    assert!(seen[0].ends_with(SECRET));
    assert!(seen[0].to_ascii_lowercase().contains(&format!(
        "authorization: bearer {}",
        SECRET.to_ascii_lowercase()
    )));
}

#[test]
fn dnu_licensing_explicit_loopback_test_constructor_is_scoped_and_functional() {
    for base in [
        "http://localhost",
        "http://127.2.3.4:1234",
        "http://[::1]:1234",
        "https://api.selahcue.example",
    ] {
        assert!(LicensingClient::new_for_loopback_tests(ScriptedTransport::new(), base).is_ok());
    }
    for base in [
        "http://192.0.2.1/?QUERY-SECRET",
        "http://localhost.example.invalid",
        "http://127.0.0.1.example.invalid",
        "ftp://127.0.0.1",
        "https://",
    ] {
        let error = match LicensingClient::new_for_loopback_tests(ScriptedTransport::new(), base) {
            Err(error) => error,
            Ok(_) => panic!("explicit HTTP test constructor must retain its loopback boundary"),
        };
        assert!(error.to_string().contains("loopback"));
        assert!(!format!("{error:?}").contains("QUERY-SECRET"));
    }
    let receiver = Receiver::start();
    let client = LicensingClient::new_for_loopback_tests(
        ReqwestTransport::new_for_loopback_tests().unwrap(),
        &receiver.base,
    )
    .unwrap();
    let error = client
        .sign_in("a@example.test", &Token::new(SECRET))
        .unwrap_err();
    assert_eq!(error, selahcue_licensing::ActivationFailure::Server(503));
    let seen = receiver.finish();
    assert_eq!(seen.len(), 1);
    assert!(seen[0].contains(SECRET));
    assert!(seen[0].starts_with("POST /v1/sessions HTTP/1.1"));
}
