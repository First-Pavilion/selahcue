//! `HTTP_PROXY` and `NO_PROXY` are still honoured by the production transport (reqwest 0.13,
//! DEC-019 parity).
//!
//! reqwest 0.13 moved system-proxy discovery behind a `system-proxy` feature that this crate does
//! not enable (`default-features = false`). Measured on 0.12.28 and 0.13.5 alike, the environment
//! variables are still read; this test keeps that true, because a church network that requires a
//! proxy would otherwise find the cloud features silently dead after a dependency bump, and a
//! `NO_PROXY` that stops working would send internal traffic through the proxy.
//! `tests/test_wire.rs` documents the same behaviour from the other side (its loopback tests must
//! be run with `NO_PROXY`).
//!
//! Two cases against the SAME loopback target, differing only in `NO_PROXY`:
//! - `HTTP_PROXY` set, no `NO_PROXY`: the request goes to the proxy (it answers "via-proxy");
//! - `HTTP_PROXY` set and `NO_PROXY` naming the target: the request goes straight to the target
//!   (it answers "direct") and the proxy sees no further connection.
//!
//! Its own process with one test: it edits the process environment before each client exists,
//! which no other test may observe.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{mpsc, Arc};
use std::time::Duration;

/// A server that answers every connection with `body` and reports each request head.
fn serve(body: &'static str, connections: Arc<AtomicUsize>) -> (u16, mpsc::Receiver<String>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        for s in listener.incoming() {
            let Ok(mut s) = s else { return };
            connections.fetch_add(1, Ordering::SeqCst);
            s.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut buf = [0u8; 4096];
            let n = s.read(&mut buf).unwrap_or(0);
            let _ = tx.send(String::from_utf8_lossy(&buf[..n]).into_owned());
            let _ = s.write_all(
                format!(
                    "HTTP/1.1 200 OK\r\ncontent-length: {}\r\nconnection: close\r\n\r\n{body}",
                    body.len()
                )
                .as_bytes(),
            );
        }
    });
    (port, rx)
}

#[test]
fn http_proxy_routes_the_request_through_the_proxy_and_no_proxy_bypasses_it() {
    let proxy_hits = Arc::new(AtomicUsize::new(0));
    let target_hits = Arc::new(AtomicUsize::new(0));
    let (proxy_port, proxy_seen) = serve("via-proxy", Arc::clone(&proxy_hits));
    let (target_port, target_seen) = serve("direct", Arc::clone(&target_hits));

    // The Makefile and CI export NO_PROXY=127.0.0.1,localhost for the loopback wire tests; start
    // from a clean slate and point both spellings of HTTP_PROXY at our proxy.
    for v in ["NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy"] {
        std::env::remove_var(v);
    }
    let proxy = format!("http://127.0.0.1:{proxy_port}");
    std::env::set_var("HTTP_PROXY", &proxy);
    std::env::set_var("http_proxy", &proxy);
    let target = format!("http://127.0.0.1:{target_port}/probe");

    // Case 1: no bypass, so the proxy answers and the target is never contacted.
    let transport = ReqwestTransport::new_for_loopback_tests().unwrap();
    let resp = transport
        .get(&target, None)
        .expect("the request should have been answered by the proxy");
    assert_eq!((resp.status, resp.body.as_str()), (200, "via-proxy"));
    let seen = proxy_seen.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        seen.starts_with(&format!("GET {target} HTTP/1.1")),
        "the proxy should receive the absolute-form request line, got: {seen}"
    );
    assert_eq!(
        target_hits.load(Ordering::SeqCst),
        0,
        "the target was contacted directly"
    );

    // Case 2: the same target named in NO_PROXY, so the request goes straight to it.
    std::env::set_var("NO_PROXY", "127.0.0.1");
    std::env::set_var("no_proxy", "127.0.0.1");
    let transport = ReqwestTransport::new_for_loopback_tests().unwrap();
    let resp = transport
        .get(&target, None)
        .expect("the request should have been answered by the target");
    assert_eq!((resp.status, resp.body.as_str()), (200, "direct"));
    let seen = target_seen.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        seen.starts_with("GET /probe HTTP/1.1"),
        "the target should receive an origin-form request line, got: {seen}"
    );
    assert_eq!(
        proxy_hits.load(Ordering::SeqCst),
        1,
        "NO_PROXY was ignored: the proxy saw a second connection"
    );
}
