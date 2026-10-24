//! `HTTP_PROXY` is still honoured by the production transport (reqwest 0.13, DEC-019 parity).
//!
//! reqwest 0.13 moved system-proxy discovery behind a `system-proxy` feature that this crate does
//! not enable (`default-features = false`). Measured on 0.12.28 and 0.13.5 alike, the environment
//! variables are still read; this test keeps that true, because a church network that requires a
//! proxy would otherwise find the cloud features silently dead after a dependency bump.
//! `tests/test_wire.rs` documents the same behaviour from the other side (its loopback tests must
//! be run with `NO_PROXY`).
//!
//! Its own process with one test: it edits the process environment before the first client exists,
//! which no other test may observe.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::mpsc;
use std::time::Duration;

#[test]
fn an_http_proxy_variable_routes_the_request_through_the_proxy() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let Ok((mut s, _)) = listener.accept() else {
            return;
        };
        s.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
        let mut buf = [0u8; 4096];
        let n = s.read(&mut buf).unwrap_or(0);
        let _ = tx.send(String::from_utf8_lossy(&buf[..n]).into_owned());
        let _ = s.write_all(
            b"HTTP/1.1 200 OK\r\ncontent-length: 9\r\nconnection: close\r\n\r\nvia-proxy",
        );
    });

    // The Makefile and CI export NO_PROXY=127.0.0.1,localhost for the loopback wire tests; here the
    // target is a name that cannot resolve, so only a proxy can answer. Clear any ambient bypass
    // and point both spellings at our listener.
    for v in ["NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy"] {
        std::env::remove_var(v);
    }
    let proxy = format!("http://127.0.0.1:{port}");
    std::env::set_var("HTTP_PROXY", &proxy);
    std::env::set_var("http_proxy", &proxy);

    let transport = ReqwestTransport::new().unwrap();
    let resp = transport
        .get("http://proxied-target.invalid:81/probe", None)
        .expect("the request should have been answered by the proxy");
    assert_eq!((resp.status, resp.body.as_str()), (200, "via-proxy"));

    let seen = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        seen.starts_with("GET http://proxied-target.invalid:81/probe HTTP/1.1"),
        "the proxy should receive the absolute-form request line, got: {seen}"
    );
}
