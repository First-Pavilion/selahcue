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
