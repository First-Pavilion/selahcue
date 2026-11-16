//! The production transport does not follow redirects: the first hop of a chain is returned as the
//! answer and the second hop is never requested (ClickUp 17tnw2b9aaz).
//!
//! The file name is historical and kept on purpose (other documents cite it): there is no longer a
//! limit to test, only the absence of a follow.
//!
//! This file used to be a CHARACTERISATION test of reqwest's default policy ("ten redirects are
//! followed, the eleventh is an error"), written so that a casual `.redirect(..)` call could not
//! change the policy unnoticed, and it said the expected values would change deliberately when
//! 17tnw2b9aaz landed. They have: following a redirect replays a 307/308 body, which is where the
//! account password, the enrollment key and the transcript travel, to whatever host the server
//! names, and no consumer of this transport has a reason to follow one (the hosted API and
//! OpenAI both answer at the URL they are given). The policy is therefore "none", and this file
//! pins it by counting what the server was asked for, not by reading the policy back.
//!
//! `test_redirect_credentials.rs` pins the credential consequence (the target host is never
//! contacted); this one pins the mechanism with a same-host chain, where no credential argument
//! can excuse a follow.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

/// A loopback server whose path `/hop/{k}/{n}` redirects to `/hop/{k+1}/{n}` while `k < n`, and
/// answers `200 done` at `k == n`: so `/hop/0/n` is a chain of exactly `n` redirects. Returns the
/// port and the path of every request it received, in order. It serves at most 40 connections and
/// stops listening after 20 seconds.
fn serve_chains() -> (u16, Arc<Mutex<Vec<String>>>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let port = listener.local_addr().unwrap().port();
    let paths = Arc::new(Mutex::new(Vec::new()));
    let recorded = Arc::clone(&paths);
    std::thread::spawn(move || {
        let until = Instant::now() + Duration::from_secs(20);
        let mut served = 0;
        while served < 40 && Instant::now() < until {
            let Ok((mut s, _)) = listener.accept() else {
                std::thread::sleep(Duration::from_millis(5));
                continue;
            };
            served += 1;
            s.set_nonblocking(false).unwrap();
            s.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut buf = [0u8; 4096];
            let n = s.read(&mut buf).unwrap_or(0);
            let head = String::from_utf8_lossy(&buf[..n]).into_owned();
            let path = head.split_whitespace().nth(1).unwrap_or("").to_string();
            // Recorded before the reply, so the client's answer implies the record exists.
            recorded.lock().unwrap().push(path.clone());
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
    (port, paths)
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
fn the_first_hop_of_a_redirect_chain_is_the_answer_and_the_second_is_never_requested() {
    assert_loopback_is_not_proxied();
    let (port, paths) = serve_chains();
    let transport = ReqwestTransport::new_for_loopback_tests().unwrap();

    let first = transport
        .get(&format!("http://127.0.0.1:{port}/hop/0/1"), None)
        .expect("a redirect is an answer, not a transport error");

    assert_eq!(
        first.status, 302,
        "the redirect itself is returned (a followed chain would end in the 200 `done`)"
    );
    assert_eq!(
        *paths.lock().unwrap(),
        vec!["/hop/0/1".to_string()],
        "only the first hop was requested"
    );
}

#[test]
fn the_server_does_answer_the_last_hop_of_a_chain_when_asked_for_it_directly() {
    // Positive control: asked for the LAST hop directly the server answers `done`, so "the second
    // hop was never requested" above is about the client and not a server that can only say 302.
    assert_loopback_is_not_proxied();
    let (port, paths) = serve_chains();
    let transport = ReqwestTransport::new_for_loopback_tests().unwrap();

    let last = transport
        .get(&format!("http://127.0.0.1:{port}/hop/1/1"), None)
        .unwrap();

    assert_eq!((last.status, last.body.as_str()), (200, "done"));
    assert_eq!(*paths.lock().unwrap(), vec!["/hop/1/1".to_string()]);
}
