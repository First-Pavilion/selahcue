//! HTTP handshake diagnostics must not carry peer headers or body bytes.
#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_lan::TransportError;
use tokio_tungstenite::tungstenite::{http::Response, Error};

#[test]
fn websocket_http_debug_keeps_status_without_peer_headers_or_body() {
    let body = b"BODY-SENTINEL-17tnw2b9dq1".to_vec();
    let response = Response::builder()
        .status(403)
        .header("x-peer-secret", "HEADER-SENTINEL-17tnw2b9dq1")
        .body(Some(body.clone()))
        .unwrap();
    let raw = Error::Http(Box::new(response));
    assert!(format!("{raw:?}").contains("HEADER-SENTINEL"));
    assert!(format!("{raw:?}").contains(&format!("{body:?}")));
    let error = TransportError::from(raw);
    for rendered in [
        error.to_string(),
        format!("{error:?}"),
        format!("{error:#?}"),
    ] {
        assert!(rendered.contains("403"), "status lost: {rendered}");
        assert!(
            !rendered.contains("HEADER-SENTINEL"),
            "header leaked: {rendered}"
        );
        assert!(
            !rendered.contains(&format!("{body:?}")),
            "body leaked: {rendered}"
        );
        assert!(
            !rendered.contains("66, 79, 68, 89"),
            "body prefix leaked: {rendered}"
        );
    }
    assert!(std::error::Error::source(&error).is_none());
}
