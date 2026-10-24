//! The production transport follows at most ten redirects (reqwest's default policy), no more and
//! no fewer.
//!
//! A CHARACTERISATION test of today's behaviour, written so that a dependency bump or a casual
//! `.redirect(..)` call cannot change it unnoticed: a chain of exactly ten redirects is followed to
//! the end, and a chain of eleven is an error that says it was a redirect problem. It does not say
//! the limit is RIGHT. ClickUp 17tnw2b9aaz is the open decision about whether this transport should
//! follow redirects at all (a 307/308 replays the request body to another host); when that lands the
//! expected values here change deliberately, in the same commit. See `test_redirect_credentials.rs`
//! for the credential property that holds under either policy.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::time::Duration;

/// A loopback server whose path `/hop/{k}/{n}` redirects to `/hop/{k+1}/{n}` while `k < n`, and
/// answers `200 done` at `k == n`: so `/hop/0/n` is a chain of exactly `n` redirects. Serves up to
/// 40 connections (one per hop; the client is told to close each).
fn serve_chains() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    std::thread::spawn(move || {
        for s in listener.incoming().take(40) {
            let Ok(mut s) = s else { return };
            s.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut buf = [0u8; 4096];
            let n = s.read(&mut buf).unwrap_or(0);
            let head = String::from_utf8_lossy(&buf[..n]).into_owned();
            let path = head.split_whitespace().nth(1).unwrap_or("").to_string();
            let mut parts = path.trim_start_matches("/hop/").split('/');
            let k: u32 = parts.next().and_then(|v| v.parse().ok()).unwrap_or(0);
            let n: u32 = parts.next().and_then(|v| v.parse().ok()).unwrap_or(0);
            let reply = if k < n {
                format!(
                    "HTTP/1.1 302 Found\r\nlocation: /hop/{}/{n}\r\ncontent-length: 0\r\nconnection: close\r\n\r\n",
                    k + 1
                )
            } else {
                "HTTP/1.1 200 OK\r\ncontent-length: 4\r\nconnection: close\r\n\r\ndone".to_string()
            };
            let _ = s.write_all(reply.as_bytes());
        }
    });
    port
}

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

#[test]
fn ten_redirects_are_followed_and_the_eleventh_is_an_error() {
    assert_loopback_is_not_proxied();
    let port = serve_chains();
    let transport = ReqwestTransport::new().unwrap();

    let ten = transport
        .get(&format!("http://127.0.0.1:{port}/hop/0/10"), None)
        .expect("a chain of ten redirects is within the limit");
    assert_eq!((ten.status, ten.body.as_str()), (200, "done"));

    let eleven = transport
        .get(&format!("http://127.0.0.1:{port}/hop/0/11"), None)
        .expect_err("a chain of eleven redirects is over the limit");
    let text = eleven.to_string().to_lowercase();
    assert!(
        text.contains("redirect"),
        "the failure should say it was a redirect problem: {eleven}"
    );
}
