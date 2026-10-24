//! TLS trust tests for [`ReqwestTransport`] (DEC-019, ClickUp 17tnw2b9ax2).
//!
//! The owner decided that the cloud client trusts the **operating-system certificate store**
//! (reqwest 0.13's default, through `rustls-platform-verifier`) with `ring` as the only crypto
//! provider. These tests pin what that means for a request that carries a password or a bearer:
//!
//! - a server whose certificate is signed by a root the client was given is accepted (the positive
//!   control that makes every refusal below mean something);
//! - a server signed by a root the machine does not trust is refused, and **no request byte
//!   reaches it**: the server records what it read, and it must have read nothing;
//! - the right signer is not enough: a certificate for another name, an expired one, and one
//!   signed by a different root than the one we trusted are each refused;
//! - a root handed to one client is that client's alone: a production `ReqwestTransport::new()`
//!   built afterwards in the same process still refuses it;
//! - a client that cannot be built is a [`TransportError`] with a readable reason, not a panic.
//!
//! These are unit tests, not files in `tests/`, on purpose: the extra-root constructor they need
//! (`ReqwestTransport::build`) is private so no release code path can widen the trust set, and an
//! integration test could only reach it through a public (and therefore shippable) door.
//!
//! WHAT THIS CANNOT SHOW. A root in the real operating-system store cannot be installed from a
//! test, so "a public CA's certificate is accepted" is a manual check (a live GET against a
//! public host; see the PR description) and "a TLS-inspecting root installed on the machine is
//! trusted" is a documented consequence rather than a test. Linux's "no CA bundle" and Windows'
//! verifier are not exercised here at all: only the host the test runs on is.
//!
//! NO CA BUNDLE. On a Linux host whose system has no CA bundle (a bare container), every test that
//! calls `ReqwestTransport::new()` fails, the plaintext loopback ones in `tests/test_wire.rs`
//! included, because `new()` itself returns an error by design (DEC-019: fail closed). Install
//! `ca-certificates`, or point `SSL_CERT_FILE` at any PEM file, before running them there.
//!
//! PROXIES. As in `tests/test_wire.rs`, a proxy variable without a loopback bypass would send these
//! loopback requests to the proxy; run with `NO_PROXY=127.0.0.1,localhost` (the Makefile and CI do).

use super::{HttpTransport, ReqwestTransport, TransportError};
use rcgen::{
    date_time_ymd, BasicConstraints, CertificateParams, DnType, ExtendedKeyUsagePurpose, IsCa,
    Issuer, KeyPair, KeyUsagePurpose,
};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener};
use std::sync::{mpsc, Arc};
use std::time::Duration;

/// Distinct, searchable markers: if either shows up in an error or at a server that should never
/// have seen a request, the test names which one leaked.
const BEARER: &str = "PROBE-BEARER-7f3a91";
const BODY: &str = r#"{"password":"PROBE-BODY-2c88d0"}"#;

fn assert_loopback_is_not_proxied() {
    let var = |n: &str| std::env::var(n).ok().filter(|v| !v.trim().is_empty());
    let proxied = [
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ]
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
        "a proxy variable is set without NO_PROXY=127.0.0.1,localhost: these loopback TLS requests \
         would be sent to the proxy. Run with NO_PROXY=127.0.0.1,localhost (see the file header)."
    );
}

// ---- a throwaway certificate authority and server -----------------------------------------

struct TestCa {
    der: Vec<u8>,
    issuer: Issuer<'static, KeyPair>,
}

fn new_ca(name: &str) -> TestCa {
    let mut params = CertificateParams::new(Vec::<String>::new()).expect("ca params");
    params.distinguished_name.push(DnType::CommonName, name);
    params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
    params.key_usages = vec![KeyUsagePurpose::KeyCertSign, KeyUsagePurpose::CrlSign];
    params.not_before = date_time_ymd(2020, 1, 1);
    params.not_after = date_time_ymd(2060, 1, 1);
    let key = KeyPair::generate().expect("ca key");
    let cert = params.self_signed(&key).expect("ca cert");
    TestCa {
        der: cert.der().to_vec(),
        issuer: Issuer::new(params, key),
    }
}

/// A server certificate for `sans`, signed by `ca`, valid between the two dates.
fn leaf(ca: &TestCa, sans: &[&str], valid: ((i32, u8, u8), (i32, u8, u8))) -> (Vec<u8>, Vec<u8>) {
    let names: Vec<String> = sans.iter().map(|s| s.to_string()).collect();
    let mut params = CertificateParams::new(names).expect("leaf params");
    params.distinguished_name.push(DnType::CommonName, sans[0]);
    params.is_ca = IsCa::NoCa;
    params.key_usages = vec![KeyUsagePurpose::DigitalSignature];
    params.extended_key_usages = vec![ExtendedKeyUsagePurpose::ServerAuth];
    let ((y1, m1, d1), (y2, m2, d2)) = valid;
    params.not_before = date_time_ymd(y1, m1, d1);
    params.not_after = date_time_ymd(y2, m2, d2);
    let key = KeyPair::generate().expect("leaf key");
    let cert = params.signed_by(&key, &ca.issuer).expect("leaf cert");
    (cert.der().to_vec(), key.serialize_der())
}

const EXPIRED: ((i32, u8, u8), (i32, u8, u8)) = ((2000, 1, 1), (2001, 1, 1));

/// A short validity window around today. Apple's verifier applies its "standards compliant" rules
/// (a server certificate may not be valid for more than 398 days) even to a root we supply, and
/// rejects anything longer with an opaque -67901, so a fixed far-future `notAfter` cannot be used.
fn valid_now() -> ((i32, u8, u8), (i32, u8, u8)) {
    let days = |offset: i64| {
        let secs = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock")
            .as_secs() as i64;
        civil(secs.div_euclid(86_400) + offset)
    };
    (days(-2), days(30))
}

/// Days since 1970-01-01 to (year, month, day), proleptic Gregorian (Howard Hinnant's algorithm).
fn civil(z: i64) -> (i32, u8, u8) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u8;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u8;
    ((y + i64::from(m <= 2)) as i32, m, d)
}

/// What the one-shot server saw.
#[derive(Debug)]
enum Seen {
    /// The TLS handshake did not complete; nothing was read.
    HandshakeFailed,
    /// The handshake completed and this request head arrived.
    Request(String),
}

struct TestServer {
    addr: SocketAddr,
    seen: mpsc::Receiver<Seen>,
}

impl TestServer {
    fn url(&self) -> String {
        format!("https://localhost:{}/probe", self.addr.port())
    }
    fn outcome(&self) -> Seen {
        self.seen
            .recv_timeout(Duration::from_secs(10))
            .expect("the server thread reported nothing within 10s")
    }
}

/// Serve `connections` TLS connections, one after another, with `leaf_der`/`key_der`, answering a
/// request with `200 ok`, and report for each whether a request was ever read.
fn serve(leaf_der: Vec<u8>, key_der: Vec<u8>, connections: usize) -> TestServer {
    use rustls::pki_types::{CertificateDer, PrivateKeyDer, PrivatePkcs8KeyDer};
    let provider = Arc::new(rustls::crypto::ring::default_provider());
    let config = rustls::ServerConfig::builder_with_provider(provider)
        .with_safe_default_protocol_versions()
        .expect("protocol versions")
        .with_no_client_auth()
        .with_single_cert(
            vec![CertificateDer::from(leaf_der)],
            PrivateKeyDer::from(PrivatePkcs8KeyDer::from(key_der)),
        )
        .expect("server config");
    let config = Arc::new(config);
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let addr = listener.local_addr().expect("addr");
    let (tx, seen) = mpsc::channel();
    std::thread::spawn(move || {
        for _ in 0..connections {
            let Ok((tcp, _)) = listener.accept() else {
                return;
            };
            let _ = tcp.set_read_timeout(Some(Duration::from_secs(10)));
            let conn = rustls::ServerConnection::new(config.clone()).expect("server connection");
            let mut tls = rustls::StreamOwned::new(conn, tcp);
            let mut head = Vec::new();
            let mut buf = [0u8; 2048];
            let mut got_request = false;
            loop {
                match tls.read(&mut buf) {
                    Ok(0) | Err(_) => break,
                    Ok(n) => {
                        head.extend_from_slice(&buf[..n]);
                        if head.windows(4).any(|w| w == b"\r\n\r\n") {
                            got_request = true;
                            break;
                        }
                    }
                }
            }
            if !got_request {
                let _ = tx.send(Seen::HandshakeFailed);
                continue;
            }
            let _ = tx.send(Seen::Request(String::from_utf8_lossy(&head).into_owned()));
            let _ = tls
                .write_all(b"HTTP/1.1 200 OK\r\ncontent-length: 2\r\nconnection: close\r\n\r\nok");
            let _ = tls.flush();
            tls.conn.send_close_notify();
            let _ = tls.flush();
        }
    });
    TestServer { addr, seen }
}

fn must_not_have_leaked(err: &TransportError) {
    let text = err.to_string();
    assert!(!text.contains(BEARER), "the bearer leaked into: {text}");
    assert!(!text.contains("PROBE-BODY"), "the body leaked into: {text}");
}

fn transport_trusting(ca: &TestCa) -> ReqwestTransport {
    let root = reqwest::Certificate::from_der(&ca.der).expect("root certificate");
    ReqwestTransport::build(&[root]).expect("a client that trusts the test root")
}

/// Send the probe request through the real client and return the whole error chain, panicking if
/// it succeeds. The chain (not just `TransportError`'s top line, which reads only "error sending
/// request") is what proves a refusal was a *certificate* refusal and not, say, a refused
/// connection that would make every "refused" assertion pass for the wrong reason. The leading
/// text of the certificate cause comes from rustls and is the same on every platform.
fn refusal_chain(t: &ReqwestTransport, url: &str) -> String {
    use std::error::Error as _;
    let err = match t
        .client
        .post(url)
        .header("content-type", "application/json")
        .body(BODY)
        .bearer_auth(BEARER)
        .send()
    {
        Ok(r) => panic!(
            "the request was accepted ({}) when it had to be refused",
            r.status()
        ),
        Err(e) => e,
    };
    let mut chain = vec![err.to_string()];
    let mut cause = err.source();
    while let Some(c) = cause {
        chain.push(c.to_string());
        cause = c.source();
    }
    let text = chain.join(" | ");
    assert!(!text.contains(BEARER), "the bearer leaked into: {text}");
    assert!(!text.contains("PROBE-BODY"), "the body leaked into: {text}");
    assert!(
        text.contains("invalid peer certificate"),
        "the request failed, but not because the certificate was refused (so a refusal test \
         would pass for the wrong reason): {text}"
    );
    text
}

fn post(t: &ReqwestTransport, url: &str) -> Result<crate::transport::HttpResponse, TransportError> {
    t.post_json(url, BODY, Some(BEARER))
}

// ---- tests ----------------------------------------------------------------------------------

#[test]
fn a_server_signed_by_a_root_we_were_given_is_accepted() {
    assert_loopback_is_not_proxied();
    let ca = new_ca("Probe Root A");
    let (leaf_der, key) = leaf(&ca, &["localhost"], valid_now());
    let server = serve(leaf_der, key, 1);
    let t = transport_trusting(&ca);
    let resp = post(&t, &server.url()).expect(
        "the positive control failed: a certificate chaining to a root we handed the client must \
         be accepted, otherwise every refusal in this file proves nothing",
    );
    assert_eq!((resp.status, resp.body.as_str()), (200, "ok"));
    match server.outcome() {
        Seen::Request(head) => {
            assert!(
                head.starts_with("POST /probe"),
                "unexpected request: {head}"
            );
            assert!(head
                .to_lowercase()
                .contains(&format!("bearer {}", BEARER.to_lowercase())));
        }
        other => panic!("the accepted connection never delivered a request: {other:?}"),
    }
}

#[test]
fn a_server_signed_by_a_root_outside_the_store_is_refused_and_sees_no_request() {
    assert_loopback_is_not_proxied();
    let ca = new_ca("Probe Root B (not in any store)");
    let (leaf_der, key) = leaf(&ca, &["localhost"], valid_now());
    let server = serve(leaf_der, key, 2);
    // The production constructor: no extra root, so only the operating-system store counts.
    let t = ReqwestTransport::new().expect("production transport");
    // Once through the public seam (what the operator sees) ...
    let err = post(&t, &server.url())
        .expect_err("a certificate from a root the machine does not trust must be refused");
    must_not_have_leaked(&err);
    // The text a user sees must say WHY (a bare "error sending request" cannot tell a certificate
    // problem from a dead network), while still naming the URL as before and nothing the request
    // carried.
    let shown = err.to_string();
    assert!(
        shown.starts_with("error sending request for url ("),
        "the URL-bearing first line should be kept as it was: {shown}"
    );
    assert!(
        shown.contains("invalid peer certificate"),
        "the send error dropped the certificate cause: {shown}"
    );
    assert!(
        matches!(server.outcome(), Seen::HandshakeFailed),
        "first connection"
    );
    // ... and once for the cause, which must be the certificate and nothing the request carried.
    let chain = refusal_chain(&t, &server.url());
    assert!(
        chain.contains("UnknownIssuer") || chain.contains("certificate"),
        "unexpected refusal reason: {chain}"
    );
    match server.outcome() {
        Seen::HandshakeFailed => {}
        Seen::Request(head) => panic!(
            "the client wrote a request to a server it could not verify, so the bearer and the \
             body left the machine: {head}"
        ),
    }
}

#[test]
fn a_certificate_for_another_name_is_refused_even_when_its_root_is_trusted() {
    assert_loopback_is_not_proxied();
    let ca = new_ca("Probe Root C");
    let (leaf_der, key) = leaf(&ca, &["not-localhost.example"], valid_now());
    let server = serve(leaf_der, key, 1);
    let t = transport_trusting(&ca);
    refusal_chain(&t, &server.url());
    assert!(
        matches!(server.outcome(), Seen::HandshakeFailed),
        "a request reached a server whose certificate names a different host"
    );
}

#[test]
fn an_expired_certificate_is_refused_even_when_its_root_is_trusted() {
    assert_loopback_is_not_proxied();
    let ca = new_ca("Probe Root D");
    let (leaf_der, key) = leaf(&ca, &["localhost"], EXPIRED);
    let server = serve(leaf_der, key, 1);
    let t = transport_trusting(&ca);
    refusal_chain(&t, &server.url());
    assert!(
        matches!(server.outcome(), Seen::HandshakeFailed),
        "a request reached a server presenting an expired certificate"
    );
}

#[test]
fn trusting_one_root_does_not_trust_a_certificate_signed_by_another() {
    assert_loopback_is_not_proxied();
    let trusted = new_ca("Probe Root E (given to the client)");
    let rogue = new_ca("Probe Root F (signs the server)");
    let (leaf_der, key) = leaf(&rogue, &["localhost"], valid_now());
    let server = serve(leaf_der, key, 1);
    let t = transport_trusting(&trusted);
    refusal_chain(&t, &server.url());
    assert!(
        matches!(server.outcome(), Seen::HandshakeFailed),
        "a request reached a server signed by a root the client was not given"
    );
}

#[test]
fn a_root_given_to_one_client_does_not_leak_into_a_production_client() {
    assert_loopback_is_not_proxied();
    let ca = new_ca("Probe Root G");
    // Same CA, one connection each: the client that was given the root accepts it; a production
    // client built AFTERWARDS in the same process must not.
    let (l1, k1) = leaf(&ca, &["localhost"], valid_now());
    let first = serve(l1, k1, 1);
    let trusting = transport_trusting(&ca);
    post(&trusting, &first.url()).expect("the client that was given the root accepts it");
    assert!(
        matches!(first.outcome(), Seen::Request(_)),
        "positive control"
    );

    let (l2, k2) = leaf(&ca, &["localhost"], valid_now());
    let second = serve(l2, k2, 1);
    let production = ReqwestTransport::new().expect("a second production transport");
    refusal_chain(&production, &second.url());
    assert!(
        matches!(second.outcome(), Seen::HandshakeFailed),
        "the production client wrote a request after another client was given the root"
    );
}

#[test]
fn a_client_that_cannot_be_built_is_a_transport_error_with_a_reason_not_a_panic() {
    // A root that is not a certificate stands in for "the TLS roots could not be loaded" (on Linux,
    // an empty CA bundle takes the same road: `Client::build` fails and `new()` must say why).
    let bogus = reqwest::Certificate::from_der(b"this is not a certificate")
        .expect("reqwest defers validation of a DER root to build time");
    let err = match ReqwestTransport::build(&[bogus]) {
        Err(e) => e,
        Ok(_) => panic!("a client was built from a root that is not a certificate"),
    };
    let text = err.to_string();
    assert!(
        text.starts_with("could not set up TLS"),
        "the failure should say it is a TLS set-up failure, not just 'builder error': {text}"
    );
    assert!(
        text.len() > "could not set up TLS".len(),
        "no reason was given: {text}"
    );
}

#[test]
fn two_production_transports_in_one_process_both_work() {
    // The second `new()` must neither panic (the provider is already installed) nor fail.
    let a = ReqwestTransport::new().expect("first");
    let b = ReqwestTransport::new().expect("second");
    drop((a, b));
}

#[test]
fn the_shipped_connect_timeout_is_on_the_client_builder() {
    // `build()` configures its builder through `shipped_builder`; reading that builder back pins
    // that the shipped connect timeout reaches it, not merely that the constant exists. A connect
    // that hangs cannot be provoked deterministically in a unit test (it needs a black-hole
    // address), so this read-back is the guard for the connect timeout.
    //
    // KNOWN GAP: reqwest's blocking builder does not print its TOTAL timeout, so the value
    // `shipped_builder` passes for it is not read back; the next test proves `configured_builder`
    // applies a total timeout (removing it hangs), but a wrong value written in `shipped_builder`
    // would survive.
    let shown = format!("{:?}", ReqwestTransport::shipped_builder(&[]));
    let connect = format!(
        "connect_timeout: {:?}",
        Duration::from_secs(super::CONNECT_TIMEOUT_SECS)
    );
    assert!(
        shown.contains(&connect),
        "no connect timeout on the builder: {shown}"
    );
}

#[test]
fn a_peer_that_accepts_and_never_answers_is_cut_off_at_the_request_timeout() {
    assert_loopback_is_not_proxied();
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();
    std::thread::spawn(move || {
        // Accept, say nothing, hold the connection open for longer than the test waits.
        let held = listener.accept();
        std::thread::sleep(Duration::from_secs(8));
        drop(held);
    });
    let t = ReqwestTransport::from_builder(ReqwestTransport::configured_builder(
        &[],
        Duration::from_millis(300),
        Duration::from_millis(500),
    ))
    .expect("transport with short timeouts");
    let (tx, rx) = mpsc::channel();
    let url = format!("http://127.0.0.1:{port}/stall");
    let started = std::time::Instant::now();
    std::thread::spawn(move || {
        let _ = tx.send(t.get(&url, None));
    });
    // Without a request timeout reqwest's blocking client waits 30 s; a hang here is the failure.
    let outcome = rx
        .recv_timeout(Duration::from_secs(5))
        .expect("the request was still pending after 5 s: no request timeout took effect");
    let err = outcome.expect_err("a peer that never answers must be an error");
    assert!(
        started.elapsed() < Duration::from_secs(4),
        "took {:?}",
        started.elapsed()
    );
    assert!(
        err.to_string().to_lowercase().contains("timed out"),
        "the failure should say it timed out: {err}"
    );
}
