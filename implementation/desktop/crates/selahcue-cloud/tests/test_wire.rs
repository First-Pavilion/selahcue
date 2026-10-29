//! What the production transport really puts on the wire.
//!
//! `selahcue-licensing`'s tests run on a scripted transport, which records a URL, a body and
//! whether a bearer was attached — and cannot see a header. The native sign-in routes are
//! CSRF-exempt (86ak5t1gw, ADR-0029) precisely because the desktop sends no cookie and nothing
//! a browser would, so that property needs a test that looks at real bytes. This drives the real
//! [`ReqwestTransport`] at a loopback socket (`std::net` only, no new dependency) and reads the
//! request back off it.
//!
//! PROXIES. `ReqwestTransport` honours `HTTP_PROXY` / `ALL_PROXY` and has no loopback bypass of its
//! own (adding one would change behaviour for people who really do sit behind a proxy). On a
//! machine with such a variable exported these loopback requests would go to the proxy and every
//! test here would fail. `make ci` and `ci.yml` therefore run this file with
//! `NO_PROXY=127.0.0.1,localhost`; run it by hand the same way. A test below refuses to run, with
//! this explanation, when a proxy variable is set without that bypass, rather than failing with a
//! connection error that points nowhere.
//!
//! Redirects are pinned elsewhere: the transport never follows one (ClickUp 17tnw2b9aaz), see
//! `test_redirect_credentials.rs` and `test_redirect_limit.rs`.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

/// Fail early and clearly when an ambient proxy would swallow the loopback requests.
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
                .any(|h| h == "127.0.0.1" || h == "*")
        });
    assert!(
        !proxied || bypassed,
        "a proxy variable (HTTP_PROXY / ALL_PROXY) is set without NO_PROXY=127.0.0.1,localhost: \
         ReqwestTransport would send these loopback requests to the proxy. Run with \
         NO_PROXY=127.0.0.1,localhost (see the header of this file)."
    );
}

/// One parsed HTTP/1.1 request.
struct Wire {
    request_line: String,
    /// Lower-cased name, value.
    headers: Vec<(String, String)>,
    body: String,
}

impl Wire {
    fn header(&self, name: &str) -> Option<&str> {
        let mut found = self
            .headers
            .iter()
            .filter(|(n, _)| n == name)
            .map(|(_, v)| v.as_str());
        let first = found.next();
        assert!(found.next().is_none(), "header {name} was sent twice");
        first
    }

    fn names(&self) -> Vec<&str> {
        self.headers.iter().map(|(n, _)| n.as_str()).collect()
    }
}

fn read_request(stream: &mut std::net::TcpStream) -> Wire {
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap();
    let mut buf = Vec::new();
    let mut chunk = [0u8; 1024];
    let (head_end, content_length) = loop {
        let n = stream.read(&mut chunk).expect("the request arrives");
        assert!(n > 0, "the client closed before finishing its request");
        buf.extend_from_slice(&chunk[..n]);
        let text = String::from_utf8_lossy(&buf).into_owned();
        if let Some(idx) = text.find("\r\n\r\n") {
            let length = text[..idx]
                .to_lowercase()
                .lines()
                .find_map(|l| {
                    l.strip_prefix("content-length:")
                        .map(|v| v.trim().parse().unwrap())
                })
                .unwrap_or(0usize);
            if buf.len() >= idx + 4 + length {
                break (idx, length);
            }
        }
    };
    let text = String::from_utf8_lossy(&buf).into_owned();
    let mut lines = text[..head_end].lines();
    let request_line = lines.next().unwrap().to_string();
    let headers = lines
        .map(|l| {
            let (n, v) = l.split_once(':').expect("a header line");
            (n.trim().to_lowercase(), v.trim().to_string())
        })
        .collect();
    Wire {
        request_line,
        headers,
        body: text[head_end + 4..head_end + 4 + content_length].to_string(),
    }
}

/// A loopback server that answers each of `replies` (raw HTTP) in turn, one connection each,
/// and hands back the requests it saw.
fn serve(replies: Vec<String>) -> (u16, mpsc::Receiver<Wire>) {
    assert_loopback_is_not_proxied();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        for reply in replies {
            let Ok((mut stream, _)) = listener.accept() else {
                return;
            };
            let wire = read_request(&mut stream);
            let _ = stream.write_all(reply.as_bytes());
            let _ = tx.send(wire);
        }
    });
    (port, rx)
}

const OK: &str = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}";

/// Headers a browser-shaped client (or a cookie jar, or a forged CSRF ceremony) would add.
const BROWSER_HEADERS: &[&str] = &[
    "cookie",
    "origin",
    "referer",
    "x-csrftoken",
    "x-csrf-token",
    "x-xsrf-token",
];

/// A body with a quote and a two-byte character, so that `Content-Length` is checked in BYTES.
/// The character is written as an escape: a literal one in source is invisible in review.
fn body() -> String {
    format!(
        r#"{{"email":"a@b.test","password":"pw \"quoted\" {}"}}"#,
        '\u{e9}'
    )
}

fn assert_native(wire: &Wire, path: &str) {
    assert_native_body(wire, path, &body());
}

fn assert_native_body(wire: &Wire, path: &str, expected_body: &str) {
    assert_eq!(wire.request_line, format!("POST {path} HTTP/1.1"));
    // The server refuses anything else on these routes (it is what makes a cross-site form
    // unable to reach them), so a missing or different value is a total failure.
    assert_eq!(wire.header("content-type"), Some("application/json"));
    assert_eq!(
        wire.header("content-length"),
        Some(expected_body.len().to_string().as_str()),
        "content-length counts BYTES (the body has a multi-byte character)"
    );
    assert_eq!(wire.body, expected_body, "the body arrives byte for byte");
    for forbidden in BROWSER_HEADERS {
        assert!(
            wire.header(forbidden).is_none(),
            "the native client must not send `{forbidden}`; headers were {:?}",
            wire.names()
        );
    }
}

#[test]
fn a_post_with_a_bearer_carries_json_content_type_the_bearer_and_no_browser_headers() {
    let (port, rx) = serve(vec![OK.to_string()]);
    let transport = ReqwestTransport::new().unwrap();

    let response = transport
        .post_json(
            &format!("http://127.0.0.1:{port}/v1/activations:with-session"),
            &body(),
            Some("SESSION-TOKEN-123"),
        )
        .unwrap();

    assert_eq!((response.status, response.body.as_str()), (200, "{}"));
    let wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_native(&wire, "/v1/activations:with-session");
    assert_eq!(
        wire.header("authorization"),
        Some("Bearer SESSION-TOKEN-123")
    );
}

#[test]
fn a_post_without_a_bearer_sends_no_authorization_at_all() {
    // Sign-in and the enrollment-key path carry no Authorization header: the presented
    // credential is in the body, and an empty or placeholder bearer would be a bug.
    let (port, rx) = serve(vec![OK.to_string()]);
    ReqwestTransport::new()
        .unwrap()
        .post_json(
            &format!("http://127.0.0.1:{port}/v1/sessions"),
            &body(),
            None,
        )
        .unwrap();

    let wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_native(&wire, "/v1/sessions");
    assert_eq!(
        wire.header("authorization"),
        None,
        "headers were {:?}",
        wire.names()
    );
}

#[test]
fn a_cookie_the_server_sets_is_never_sent_back() {
    // There is no cookie jar. The browser surface hands out a session cookie on login; if the
    // transport ever grew `cookie_store(true)`, the second request here would carry it and the
    // "no ambient credential" argument for the CSRF exemption would be gone.
    let first = "HTTP/1.1 200 OK\r\nSet-Cookie: selahcue_account_session=abc; Path=/\r\n\
                 Set-Cookie: csrftoken=xyz; Path=/\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}";
    let (port, rx) = serve(vec![first.to_string(), OK.to_string()]);
    let transport = ReqwestTransport::new().unwrap();
    let url = format!("http://127.0.0.1:{port}/v1/sessions");

    transport.post_json(&url, &body(), None).unwrap();
    transport
        .post_json(&url, &body(), Some("SESSION-TOKEN-123"))
        .unwrap();

    let first_wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    let second_wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_native(&first_wire, "/v1/sessions");
    assert_native(&second_wire, "/v1/sessions");
    assert_eq!(
        second_wire.header("authorization"),
        Some("Bearer SESSION-TOKEN-123")
    );
}

#[test]
fn a_get_sends_no_content_type_and_the_same_absence_of_browser_headers() {
    // `get` is the other half of the trait; it must not grow a body header, and it carries the
    // same promise about cookies and the CSRF ceremony.
    let (port, rx) = serve(vec![OK.to_string()]);
    ReqwestTransport::new()
        .unwrap()
        .get(
            &format!("http://127.0.0.1:{port}/v1/entitlements/manifest"),
            Some("DEVICE-TOKEN"),
        )
        .unwrap();

    let wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_eq!(wire.request_line, "GET /v1/entitlements/manifest HTTP/1.1");
    assert_eq!(wire.header("authorization"), Some("Bearer DEVICE-TOKEN"));
    assert_eq!(wire.header("content-type"), None, "{:?}", wire.names());
    for forbidden in BROWSER_HEADERS {
        assert!(
            wire.header(forbidden).is_none(),
            "{forbidden}: {:?}",
            wire.names()
        );
    }
}

#[test]
fn native_session_revoke_sends_only_json_and_the_account_bearer() {
    let (port, rx) = serve(vec![OK.to_string()]);
    let response = ReqwestTransport::new()
        .unwrap()
        .post_json(
            &format!("http://127.0.0.1:{port}/v1/sessions:revoke"),
            "{}",
            Some("ACCOUNT-SESSION-FOR-CLEANUP"),
        )
        .unwrap();
    assert_eq!(response.status, 200);
    let wire = rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_native_body(&wire, "/v1/sessions:revoke", "{}");
    assert_eq!(
        wire.header("authorization"),
        Some("Bearer ACCOUNT-SESSION-FOR-CLEANUP")
    );
    assert_eq!(wire.body, "{}");
}
