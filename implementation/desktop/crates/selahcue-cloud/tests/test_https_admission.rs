//! The ordinary production transport must not send a first-hop HTTP credential.
#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]
#[path = "support/credential_receiver.rs"]
mod credential_receiver;
use credential_receiver::Receiver;
use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};

#[test]
fn dnu_production_transport_refuses_http_before_body_or_bearer_send() {
    let receiver = Receiver::start();
    let result = ReqwestTransport::new().unwrap().post_json(
        &receiver.base,
        "DNU-BODY-SECRET",
        Some("DNU-BEARER-SECRET"),
    );
    let seen = receiver.finish();
    assert!(
        seen.is_empty(),
        "production transport sent {} insecure requests",
        seen.len()
    );
    let error = result.unwrap_err();
    let message = format!("{error} {error:?}");
    for secret in ["DNU-BODY-SECRET", "DNU-BEARER-SECRET"] {
        assert!(!message.contains(secret));
    }
}

#[test]
fn dnu_production_get_refusal_does_not_echo_url_secrets() {
    let receiver = Receiver::start();
    let url = receiver
        .base
        .replacen("http://", "http://alice:URL-SECRET@", 1)
        + "/?q=QUERY-SECRET";
    let error = ReqwestTransport::new()
        .unwrap()
        .get(&url, Some("DNU-BEARER-SECRET"))
        .unwrap_err();
    assert!(receiver.finish().is_empty());
    let message = format!("{error} {error:?}");
    assert!(message.contains("HTTPS"));
    for secret in ["URL-SECRET", "QUERY-SECRET", "alice", "DNU-BEARER-SECRET"] {
        assert!(!message.contains(secret));
    }
}

#[test]
fn dnu_explicit_test_transport_keeps_http_on_loopback_only() {
    use selahcue_cloud::transport::{require_https_base_url, require_loopback_test_url};
    for base in [
        "http://127.0.0.1",
        "http://127.2.3.4:1234/base",
        "http://[::1]:1234",
        "http://localhost:1234",
        "https://api.selahcue.example",
    ] {
        assert!(require_loopback_test_url(base).is_ok());
    }
    let transport = ReqwestTransport::new_for_loopback_tests().unwrap();
    for base in [
        "http://192.0.2.1/?QUERY-SECRET",
        "http://localhost.example.invalid/?QUERY-SECRET",
        "http://127.0.0.1.example.invalid",
        "http://[::ffff:192.0.2.1]",
        "ftp://127.0.0.1",
        "https://",
        "//localhost",
    ] {
        assert!(require_https_base_url(base).is_err());
        assert!(require_loopback_test_url(base).is_err());
        // A request (not only the exposed parser) must refuse before DNS/connect.
        for error in [
            transport.get(base, None).unwrap_err(),
            transport
                .post_json(base, "BODY-SECRET", Some("BEARER-SECRET"))
                .unwrap_err(),
        ] {
            let text = format!("{error} {error:?}");
            assert!(text.contains("test URL must use HTTPS or HTTP on a loopback host"));
            for secret in ["QUERY-SECRET", "BODY-SECRET", "BEARER-SECRET"] {
                assert!(!text.contains(secret));
            }
        }
    }
    let receiver = Receiver::start();
    assert_eq!(transport.get(&receiver.base, None).unwrap().status, 503);
    assert_eq!(receiver.finish().len(), 1);
}
