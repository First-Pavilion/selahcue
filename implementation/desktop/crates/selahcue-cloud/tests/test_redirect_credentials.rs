//! A bearer token never follows a redirect to another host (reqwest 0.13, DEC-019 parity).
//!
//! reqwest strips `Authorization` (and cookies) when a redirect changes host or port. That is a
//! property of the library the transport leans on, so a dependency bump is exactly when it could
//! change. This test pins the property, not the redirect policy.
//!
//! Deliberately NOT asserted: that the redirect is followed at all, or what happens to the request
//! BODY. The transport follows up to ten redirects today and replays a 307/308 body to the new host;
//! that is a known weakness tracked as ClickUp 17tnw2b9aaz, and pinning it here would pin the wrong
//! behaviour (see the header of `test_wire.rs`). Measured on 0.12.28 and 0.13.5 identically. The
//! assertion below holds whether the redirect is followed or, after 17tnw2b9aaz, refused.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::mpsc;
use std::time::Duration;

const BEARER: &str = "REDIRECT-PROBE-BEARER-51b0";

fn assert_loopback_is_not_proxied() {
    let var = |n: &str| std::env::var(n).ok().filter(|v| !v.trim().is_empty());
    let proxied = ["HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]
        .iter()
        .any(|n| var(n).is_some());
    let bypassed = ["NO_PROXY", "no_proxy"]
        .iter()
        .filter_map(|n| var(n))
        .any(|v| {
            v.split(',')
                .map(str::trim)
                .any(|h| h == "127.0.0.1" || h == "localhost" || h == "*")
        });
    assert!(
        !proxied || bypassed,
        "a proxy variable is set without NO_PROXY=127.0.0.1,localhost; run with it (see test_wire.rs)"
    );
}

/// Answer one connection with `reply`, send the raw request head down the channel.
fn serve_one(reply: String) -> (u16, mpsc::Receiver<String>) {
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
        let _ = s.write_all(reply.as_bytes());
    });
    (port, rx)
}

#[test]
fn the_bearer_is_not_sent_to_a_different_host_after_a_redirect() {
    assert_loopback_is_not_proxied();
    // B is the redirect target, on another port and under another host name.
    let (b_port, b_seen) = serve_one(
        "HTTP/1.1 200 OK\r\ncontent-length: 2\r\nconnection: close\r\n\r\nok".to_string(),
    );
    let (a_port, a_seen) = serve_one(format!(
        "HTTP/1.1 302 Found\r\nlocation: http://localhost:{b_port}/landed\r\ncontent-length: 0\r\nconnection: close\r\n\r\n"
    ));

    let transport = ReqwestTransport::new().unwrap();
    // Whether this returns Ok (redirect followed) or an error (redirect refused) is not the point.
    let _ = transport.get(&format!("http://127.0.0.1:{a_port}/start"), Some(BEARER));

    // Positive control: the origin really did receive the bearer, so a "not on B" result below is
    // about the redirect and not about a token that was never sent.
    let a_head = a_seen.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        a_head.contains(&format!("Bearer {BEARER}")),
        "the origin should have received the bearer: {a_head}"
    );

    if let Ok(b_head) = b_seen.recv_timeout(Duration::from_secs(2)) {
        assert!(
            !b_head.contains(BEARER),
            "the bearer followed a redirect to another host: {b_head}"
        );
        assert!(
            !b_head.to_lowercase().contains("\r\nauthorization:"),
            "an Authorization header followed a redirect to another host: {b_head}"
        );
    }
}
