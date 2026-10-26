//! No credential follows a redirect to another host: not the bearer, and not the request BODY
//! (ClickUp 17tnw2b9aaz).
//!
//! The body is where this app's credentials travel: the account password (`POST /v1/sessions`),
//! the enrollment key (`POST /v1/activations`) and the sermon transcript. reqwest strips
//! `Authorization` and cookies when a redirect changes host, port or scheme, but on a 307 or 308 it
//! replays the body to the new location, and it never strips the body. Measured on 0.12.28 and
//! 0.13.5 identically: a local server that answered a POST with a 307 to another port received
//! the whole JSON body. So the production transport does not follow redirects at all (see
//! `ReqwestTransport` and `test_redirect_limit.rs`), and the tests here pin the consequence that
//! matters: a server that redirects gets an answer carrying the redirect status, and the redirect
//! target is never contacted.
//!
//! What is asserted is that the redirect target saw NO connection at all, for every status
//! reqwest treats as a redirect and for both verbs, so neither the body nor the bearer (nor the
//! `Referer` reqwest adds) can have reached it. Earlier versions of this file also held a
//! bearer-stripping test that ran the old default policy and asserted reqwest's own
//! `Authorization` stripping; under "no redirects" the target is never contacted, so it asserted
//! nothing and was removed rather than kept as a decoration.
//!
//! Every "the target saw nothing" check has a positive control: the same recorder, hit directly,
//! does record a request and its body. Without it, "saw nothing" is indistinguishable from a
//! recorder that records nothing.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use selahcue_cloud::{SelahCueCloudClient, Token};
use selahcue_core::providers::{NoteError, NoteProvider, ProvidersConfig};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const BEARER: &str = "REDIRECT-PROBE-BEARER-51b0";
/// The credential-shaped body that must never reach the redirect target.
const SECRET_BODY: &str = r#"{"email":"a@b.test","password":"REDIRECT-PROBE-PASSWORD-7c2e"}"#;
const SECRET_FRAGMENT: &str = "REDIRECT-PROBE-PASSWORD-7c2e";

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

/// A loopback server that records every complete request it receives (head and body, as text)
/// and answers each with `reply`. It serves at most [`Recorder::MAX_CONNECTIONS`] connections
/// and stops listening after [`Recorder::LIFETIME`], so a test that never connects leaves no
/// thread parked on `accept` for the rest of the process.
struct Recorder {
    port: u16,
    seen: Arc<Mutex<Vec<String>>>,
}

impl Recorder {
    const MAX_CONNECTIONS: usize = 4;
    const LIFETIME: Duration = Duration::from_secs(20);

    fn serve(reply: String) -> Recorder {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let port = listener.local_addr().unwrap().port();
        let seen = Arc::new(Mutex::new(Vec::new()));
        let recorded = Arc::clone(&seen);
        std::thread::spawn(move || {
            let until = Instant::now() + Self::LIFETIME;
            let mut served = 0;
            while served < Self::MAX_CONNECTIONS && Instant::now() < until {
                let Ok((mut s, _)) = listener.accept() else {
                    std::thread::sleep(Duration::from_millis(5));
                    continue;
                };
                served += 1;
                s.set_nonblocking(false).unwrap();
                let request = read_request(&mut s);
                // Recorded BEFORE the reply goes out, so that by the time the client has its
                // answer the request is already visible to the test: no sleep is needed to
                // decide "was this server contacted".
                recorded.lock().unwrap().push(request);
                let _ = s.write_all(reply.as_bytes());
            }
        });
        Recorder { port, seen }
    }

    fn requests(&self) -> Vec<String> {
        self.seen.lock().unwrap().clone()
    }
}

/// The whole request: head, then as many body bytes as `Content-Length` says.
fn read_request(s: &mut std::net::TcpStream) -> String {
    s.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
    let mut buf = Vec::new();
    let mut chunk = [0u8; 1024];
    loop {
        let n = s.read(&mut chunk).unwrap_or(0);
        if n == 0 {
            break;
        }
        buf.extend_from_slice(&chunk[..n]);
        let text = String::from_utf8_lossy(&buf).into_owned();
        if let Some(idx) = text.find("\r\n\r\n") {
            let length: usize = text[..idx]
                .to_lowercase()
                .lines()
                .find_map(|l| {
                    l.strip_prefix("content-length:")
                        .and_then(|v| v.trim().parse().ok())
                })
                .unwrap_or(0);
            if buf.len() >= idx + 4 + length {
                break;
            }
        }
    }
    String::from_utf8_lossy(&buf).into_owned()
}

fn redirect_to(status: u16, location: &str) -> String {
    let reason = match status {
        301 => "Moved Permanently",
        302 => "Found",
        303 => "See Other",
        307 => "Temporary Redirect",
        308 => "Permanent Redirect",
        _ => "Redirect",
    };
    format!(
        "HTTP/1.1 {status} {reason}\r\nlocation: {location}\r\ncontent-length: 0\r\nconnection: close\r\n\r\n"
    )
}

const OK_REPLY: &str = "HTTP/1.1 200 OK\r\ncontent-length: 2\r\nconnection: close\r\n\r\nok";

/// Every status reqwest's redirect policy acts on. 307 and 308 are the ones that replay a body;
/// 301, 302 and 303 turn a POST into a GET, but they still send the client to the new host, so a
/// client that follows them has still gone where the server pointed it.
const REDIRECT_STATUSES: [u16; 5] = [301, 302, 303, 307, 308];

/// The host names a hostile `Location` can use for the same loopback target. An IP literal is the
/// easy case; a DOMAIN NAME is the realistic one (a redirect to `evil.example`), and a policy that
/// followed only redirects to a name would pass every check that uses an IP. `localhost` is a
/// name that resolves to loopback, so the target is reachable and a follow would be visible.
const TARGET_HOSTS: [&str; 2] = ["127.0.0.1", "localhost"];

#[test]
fn a_redirect_is_returned_and_its_target_is_never_contacted() {
    assert_loopback_is_not_proxied();
    for status in REDIRECT_STATUSES {
        for target_host in TARGET_HOSTS {
            let case = format!("status {status}, Location host {target_host}");
            // B is another host:port. A answers the request with a redirect to it.
            let b = Recorder::serve(OK_REPLY.to_string());
            let a = Recorder::serve(redirect_to(
                status,
                &format!("http://{target_host}:{}/landed", b.port),
            ));
            let transport = ReqwestTransport::new().unwrap();

            let post = transport.post_json(
                &format!("http://127.0.0.1:{}/v1/sessions", a.port),
                SECRET_BODY,
                Some(BEARER),
            );

            // Positive control: the origin did receive the secret body, so "B saw nothing" is
            // about the redirect and not about a body that was never sent.
            let a_requests = a.requests();
            assert_eq!(a_requests.len(), 1, "{case}: {a_requests:?}");
            assert!(
                a_requests[0].contains(SECRET_FRAGMENT) && a_requests[0].contains(BEARER),
                "{case}: the origin should have received the body and the bearer"
            );

            assert!(
                b.requests().is_empty(),
                "{case}: the redirect was followed and the request reached another host: {:?}",
                b.requests()
            );
            let post = post.unwrap_or_else(|e| {
                panic!("{case}: a redirect on a POST should be returned, not an error: {e}")
            });
            assert_eq!(
                post.status, status,
                "{case}: the redirect status is returned as is"
            );

            // The same for a GET (the shape `fetch_quota` uses), which carries the bearer.
            let get = transport.get(
                &format!("http://127.0.0.1:{}/v1/quota", a.port),
                Some(BEARER),
            );
            assert!(
                b.requests().is_empty(),
                "{case}: a GET redirect was followed to another host: {:?}",
                b.requests()
            );
            let get = get.unwrap_or_else(|e| {
                panic!("{case}: a redirect on a GET should be returned, not an error: {e}")
            });
            assert_eq!(get.status, status, "{case}");
        }
    }
}

#[test]
fn the_recorder_does_see_a_body_when_it_is_contacted_directly() {
    // The positive control for the test above, as a test of its own so that a recorder that
    // silently records nothing (a parse bug, a wrong port) fails here rather than passing there.
    assert_loopback_is_not_proxied();
    let b = Recorder::serve(OK_REPLY.to_string());
    let transport = ReqwestTransport::new().unwrap();

    let response = transport
        .post_json(
            &format!("http://127.0.0.1:{}/landed", b.port),
            SECRET_BODY,
            Some(BEARER),
        )
        .unwrap();

    assert_eq!((response.status, response.body.as_str()), (200, "ok"));
    let requests = b.requests();
    assert_eq!(requests.len(), 1);
    assert!(
        requests[0].contains(SECRET_FRAGMENT),
        "the recorder should capture the request body: {:?}",
        requests[0]
    );

    // And the host-NAME form of the same target is reachable too, so the `localhost` rows of the
    // sweep above are "refused", not "unreachable".
    transport
        .post_json(
            &format!("http://localhost:{}/landed", b.port),
            SECRET_BODY,
            Some(BEARER),
        )
        .unwrap();
    assert_eq!(b.requests().len(), 2, "the recorder is reachable by name");
}

#[test]
fn a_redirect_through_the_hosted_notes_client_is_an_unexpected_status_that_quotes_nothing() {
    // The shipped notes path end to end: `SelahCueCloudClient` over the REAL transport, against a
    // server that redirects. The Location carries a secret in its query and the redirect's own
    // body carries a marker; neither may reach the error, and the transcript and bearer must
    // not reach the target.
    const LOCATION_SECRET: &str = "LOCATION-QUERY-SECRET-93ad";
    const REDIRECT_BODY_MARKER: &str = "REDIRECT-BODY-MARKER-1f6c";
    const TRANSCRIPT: &str = "REDIRECT-PROBE-TRANSCRIPT-a41e the completed sermon";
    assert_loopback_is_not_proxied();

    let b = Recorder::serve(OK_REPLY.to_string());
    let a = Recorder::serve(format!(
        "HTTP/1.1 307 Temporary Redirect\r\nlocation: http://127.0.0.1:{}/landed?token={LOCATION_SECRET}\r\ncontent-length: {}\r\nconnection: close\r\n\r\n{REDIRECT_BODY_MARKER}",
        b.port,
        REDIRECT_BODY_MARKER.len()
    ));
    let client = SelahCueCloudClient::new(
        ReqwestTransport::new().unwrap(),
        format!("http://127.0.0.1:{}", a.port),
        Token::new(BEARER),
    );
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    let request = cfg.build_note_request(TRANSCRIPT, true).unwrap();

    let outcome = client.generate(&request);

    assert!(
        a.requests()[0].contains("REDIRECT-PROBE-TRANSCRIPT-a41e"),
        "premise: the origin received the transcript"
    );
    assert!(
        b.requests().is_empty(),
        "the transcript or the bearer reached the redirect target: {:?}",
        b.requests()
    );
    let err = outcome.expect_err("a redirect is not a draft");
    assert_eq!(
        err,
        NoteError::Malformed("unexpected status 307".to_string()),
        "a redirect is an unexpected status, in the client's own words"
    );
    let rendered = format!("{err} {err:?}");
    for leaked in [
        LOCATION_SECRET,
        REDIRECT_BODY_MARKER,
        "REDIRECT-PROBE-TRANSCRIPT",
        BEARER,
        "127.0.0.1",
    ] {
        assert!(
            !rendered.contains(leaked),
            "the error carries `{leaked}`: {rendered}"
        );
    }
}
