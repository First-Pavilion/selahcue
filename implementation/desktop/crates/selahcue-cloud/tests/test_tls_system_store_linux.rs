//! The Linux/BSD "system store" path of the OS-trust decision (DEC-019): the platform verifier
//! reads the CA bundle that `SSL_CERT_FILE` / `SSL_CERT_DIR` (or the distribution's default
//! location) names. That gives this test what the macOS and Windows runs cannot have: a way to put
//! a root INTO "the platform store" and so exercise the production constructor, `new()`, with no
//! test-only trust hook at all.
//!
//! - an empty CA bundle: `ReqwestTransport::new()` fails CLOSED with a `TransportError` that says
//!   why ("No CA certificates were loaded from the system"), never panics, never trusts anything;
//! - a bundle holding the test CA: `new()` succeeds and a server signed by that CA is ACCEPTED
//!   (the case the other TLS tests can only reach through a private constructor);
//! - the same client refuses a server signed by a CA that is not in the bundle, and that server
//!   sees no request byte.
//!
//! Compiled only on Unix that is not Apple and not Android, the platforms where this verifier reads
//! a bundle, and written without being able to run it on macOS: it runs under Linux (CI, and a
//! container in the PR evidence). Its own process with one test, because it edits the environment
//! before the first client reads it.

#![cfg(all(
    feature = "http",
    unix,
    not(target_vendor = "apple"),
    not(target_os = "android")
))]
#![allow(clippy::unwrap_used)]

use rcgen::{
    date_time_ymd, BasicConstraints, CertificateParams, DnType, ExtendedKeyUsagePurpose, IsCa,
    Issuer, KeyPair, KeyUsagePurpose,
};
use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::{mpsc, Arc};
use std::time::Duration;

const BEARER: &str = "LINUX-STORE-BEARER-a41c";

struct Ca {
    pem: String,
    issuer: Issuer<'static, KeyPair>,
}

fn new_ca(name: &str) -> Ca {
    let mut params = CertificateParams::new(Vec::<String>::new()).unwrap();
    params.distinguished_name.push(DnType::CommonName, name);
    params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
    params.key_usages = vec![KeyUsagePurpose::KeyCertSign, KeyUsagePurpose::CrlSign];
    params.not_before = date_time_ymd(2020, 1, 1);
    params.not_after = date_time_ymd(2060, 1, 1);
    let key = KeyPair::generate().unwrap();
    let cert = params.self_signed(&key).unwrap();
    Ca {
        pem: cert.pem(),
        issuer: Issuer::new(params, key),
    }
}

/// Days since 1970-01-01 to (year, month, day) (Howard Hinnant's algorithm).
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

/// Serve ONE TLS connection with a certificate for `localhost` signed by `ca`; report whether a
/// request head was ever read.
fn serve_once(ca: &Ca) -> (u16, mpsc::Receiver<bool>) {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;
    let mut params = CertificateParams::new(vec!["localhost".to_string()]).unwrap();
    params
        .distinguished_name
        .push(DnType::CommonName, "localhost");
    params.is_ca = IsCa::NoCa;
    params.key_usages = vec![KeyUsagePurpose::DigitalSignature];
    params.extended_key_usages = vec![ExtendedKeyUsagePurpose::ServerAuth];
    let (y1, m1, d1) = civil(now.div_euclid(86_400) - 2);
    let (y2, m2, d2) = civil(now.div_euclid(86_400) + 30);
    params.not_before = date_time_ymd(y1, m1, d1);
    params.not_after = date_time_ymd(y2, m2, d2);
    let key = KeyPair::generate().unwrap();
    let cert = params.signed_by(&key, &ca.issuer).unwrap();

    use rustls::pki_types::{CertificateDer, PrivateKeyDer, PrivatePkcs8KeyDer};
    let config = rustls::ServerConfig::builder_with_provider(Arc::new(
        rustls::crypto::ring::default_provider(),
    ))
    .with_safe_default_protocol_versions()
    .unwrap()
    .with_no_client_auth()
    .with_single_cert(
        vec![CertificateDer::from(cert.der().to_vec())],
        PrivateKeyDer::from(PrivatePkcs8KeyDer::from(key.serialize_der())),
    )
    .unwrap();
    let config = Arc::new(config);
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let Ok((tcp, _)) = listener.accept() else {
            return;
        };
        let _ = tcp.set_read_timeout(Some(Duration::from_secs(10)));
        let mut tls = rustls::StreamOwned::new(rustls::ServerConnection::new(config).unwrap(), tcp);
        let mut head = Vec::new();
        let mut buf = [0u8; 2048];
        let mut got = false;
        loop {
            match tls.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    head.extend_from_slice(&buf[..n]);
                    if head.windows(4).any(|w| w == b"\r\n\r\n") {
                        got = true;
                        break;
                    }
                }
            }
        }
        let _ = tx.send(got);
        if got {
            let _ = tls
                .write_all(b"HTTP/1.1 200 OK\r\ncontent-length: 2\r\nconnection: close\r\n\r\nok");
            let _ = tls.flush();
            tls.conn.send_close_notify();
            let _ = tls.flush();
        }
    });
    (port, rx)
}

#[test]
fn the_system_store_decides_who_is_trusted_and_an_empty_one_fails_closed() {
    let dir = std::env::temp_dir().join(format!("selahcue-cloud-store-{}", std::process::id()));
    let empty_dir = dir.join("empty-dir");
    std::fs::create_dir_all(&empty_dir).unwrap();
    let empty_bundle = dir.join("empty.pem");
    std::fs::write(&empty_bundle, b"").unwrap();

    // 1. An empty bundle: fail closed, say why, do not panic.
    std::env::set_var("SSL_CERT_FILE", &empty_bundle);
    std::env::set_var("SSL_CERT_DIR", &empty_dir);
    for v in [
        "NO_PROXY",
        "no_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ] {
        std::env::remove_var(v);
    }
    let err = match ReqwestTransport::new() {
        Err(e) => e,
        Ok(_) => panic!("a transport was built with no CA certificates at all"),
    };
    let text = err.to_string();
    assert!(text.starts_with("could not set up TLS"), "{text}");
    assert!(
        text.contains("No CA certificates were loaded from the system"),
        "the failure should name the cause: {text}"
    );

    // 2. A bundle holding the test CA: new() works with no test-only hook, and a server signed by
    //    that CA is accepted.
    let trusted = new_ca("Linux Store Probe CA (in the bundle)");
    let bundle = dir.join("bundle.pem");
    std::fs::write(&bundle, trusted.pem.as_bytes()).unwrap();
    std::env::set_var("SSL_CERT_FILE", &bundle);
    let transport = ReqwestTransport::new().expect("a transport over a bundle that holds a CA");
    let (port, seen) = serve_once(&trusted);
    // The test names the server `localhost`; loopback must not be proxied (removed above).
    let resp = transport
        .post_json(
            &format!("https://localhost:{port}/probe"),
            "{}",
            Some(BEARER),
        )
        .expect("a server signed by a CA in the system store must be accepted");
    assert_eq!((resp.status, resp.body.as_str()), (200, "ok"));
    assert!(seen.recv_timeout(Duration::from_secs(10)).unwrap());

    // 3. A CA that is NOT in the bundle: refused, and the server never reads a request.
    let stranger = new_ca("Linux Store Probe CA (not in the bundle)");
    let (port, seen) = serve_once(&stranger);
    let refused = transport.post_json(
        &format!("https://localhost:{port}/probe"),
        "{}",
        Some(BEARER),
    );
    let err =
        refused.expect_err("a server signed by a CA outside the system store must be refused");
    assert!(!err.to_string().contains(BEARER), "{err}");
    assert!(
        !seen.recv_timeout(Duration::from_secs(10)).unwrap(),
        "the client wrote a request to a server signed by an untrusted CA"
    );
    let _ = std::fs::remove_dir_all(&dir);
}
