//! The Linux/BSD "system store" path of the OS-trust decision (DEC-019): the platform verifier
//! reads the CA bundle that `SSL_CERT_FILE` / `SSL_CERT_DIR` (or the distribution's default
//! location) names. That gives this test what the macOS and Windows runs cannot have: a way to put
//! a root INTO "the platform store" and so exercise the production constructor, `new()`, with no
//! test-only trust hook at all.
//!
//! - an empty CA bundle: `ReqwestTransport::new()` fails closed and eligible generation uses
//!   the offline provider with the fixed empty-root reason;
//! - a bundle holding the test CA: `new()` succeeds and a server signed by that CA is ACCEPTED
//!   (the case the other TLS tests can only reach through a private constructor);
//! - the same client refuses a server signed by a CA that is not in the bundle, and that server
//!   sees no request byte.
//!
//! Compiled only on Unix that is not Apple and not Android, the platforms where this verifier reads
//! a bundle, and written without being able to run it on macOS: it runs under Linux (CI, and a
//! container in the PR evidence). Each environment runs in its own child process.

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
use selahcue_cloud::{
    generate_sermon_notes_with_factory, DegradedNoteReason, LocalNoteProvider, SelahCueCloudClient,
    Token,
};
use selahcue_core::providers::{NoteError, ProvidersConfig};
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
        loop {
            match tls.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    head.extend_from_slice(&buf[..n]);
                    if head.windows(4).any(|w| w == b"\r\n\r\n") {
                        break;
                    }
                }
            }
        }
        let got = !head.is_empty();
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
    use std::{path::PathBuf, process::Command};

    struct Cleanup(PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    const CHILD: &str = "SELAHCUE_TRUST_STORE_TEST_CASE";
    let Ok(case) = std::env::var(CHILD) else {
        let dir = std::env::temp_dir().join(format!("selahcue-cloud-store-{}", std::process::id()));
        std::fs::create_dir(&dir).unwrap();
        let _cleanup = Cleanup(dir.clone());
        let empty_dir = dir.join("empty-dir");
        std::fs::create_dir(&empty_dir).unwrap();
        let empty_bundle = dir.join("empty.pem");
        std::fs::write(&empty_bundle, b"").unwrap();

        for (case, key) in [
            ("empty", None::<&str>),
            ("trusted", None),
            #[cfg(feature = "openai")]
            ("missing-key", None),
            #[cfg(feature = "openai")]
            ("blank-key", Some("   ")),
        ] {
            let mut child = Command::new(std::env::current_exe().unwrap());
            child
                .args([
                    "--exact",
                    "the_system_store_decides_who_is_trusted_and_an_empty_one_fails_closed",
                ])
                .env(CHILD, case)
                .env("SSL_CERT_FILE", &empty_bundle)
                .env("SSL_CERT_DIR", &empty_dir)
                .env_remove("OPENAI_API_KEY");
            for var in [
                "NO_PROXY",
                "no_proxy",
                "HTTP_PROXY",
                "http_proxy",
                "ALL_PROXY",
                "all_proxy",
                "HTTPS_PROXY",
                "https_proxy",
            ] {
                child.env_remove(var);
            }
            if let Some(key) = key {
                child.env("OPENAI_API_KEY", key);
            }
            let output = child.output().unwrap();
            assert!(
                output.status.success()
                    && String::from_utf8_lossy(&output.stdout).contains("1 passed"),
                "{case}: {}",
                String::from_utf8_lossy(&output.stdout)
            );
        }
        return;
    };

    let mut config = ProvidersConfig::default();
    config.consent.cloud_notes = true;
    let local = LocalNoteProvider::new();
    let build = || ReqwestTransport::new().map_err(|e| NoteError::Transport(e.to_string()));
    if case == "empty" {
        use selahcue_cloud::deadline_transport::DeadlineTransport;
        use selahcue_core::deadline::{AccessDeadline, Clock, ClockReading};
        use std::{
            sync::atomic::AtomicBool,
            time::{Instant, SystemTime},
        };

        struct WallClock;
        impl Clock for WallClock {
            fn now(&self) -> ClockReading {
                ClockReading {
                    wall: Some(SystemTime::now()),
                    monotonic: Instant::now(),
                }
            }
        }
        let deadline = AccessDeadline::admit(
            SystemTime::now() + Duration::from_secs(30),
            Arc::new(WallClock),
        )
        .unwrap();
        let error = DeadlineTransport::new(deadline, Arc::new(AtomicBool::new(false)))
            .err()
            .expect("empty trust must also prevent construction of the deadline transport");
        assert_eq!(error.0, "cloud TLS trust store empty");

        let result = generate_sermon_notes_with_factory(
            &config,
            "Opening point. Another point.",
            true,
            || {
                let transport = build()?;
                Ok(SelahCueCloudClient::new(
                    transport,
                    "https://localhost:1",
                    Token::new(BEARER),
                ))
            },
            &local,
        )
        .expect("broken trust must yield the existing local outline");
        assert!(result.degraded);
        assert_eq!(result.provider_label, "Local (offline)");
        assert_eq!(result.draft.title, "Opening point");
        assert_eq!(
            result.degraded_reason,
            Some(DegradedNoteReason::NoTrustedCertificates)
        );
        return;
    }
    #[cfg(feature = "openai")]
    if matches!(case.as_str(), "missing-key" | "blank-key") {
        let calls = std::cell::Cell::new(0);
        let result = generate_sermon_notes_with_factory(
            &config,
            "Opening point. Another point.",
            true,
            || {
                selahcue_cloud::OpenAiNoteProvider::from_env_with_transport(|| {
                    calls.set(calls.get() + 1);
                    build()
                })
            },
            &local,
        );
        assert_eq!(result.unwrap_err(), NoteError::NotConfigured);
        assert_eq!(calls.get(), 0);
        return;
    }

    assert_eq!(case, "trusted");
    // A bundle holding the test CA works without a private trust hook.
    let trusted = new_ca("Linux Store Probe CA (in the bundle)");
    let bundle = std::env::var_os("SSL_CERT_FILE")
        .map(PathBuf::from)
        .unwrap()
        .with_file_name("trusted.pem");
    std::fs::write(&bundle, trusted.pem.as_bytes()).unwrap();
    // Only this single selected test runs in the child, before any verifier is constructed.
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
    assert_eq!(err.0, "cloud TLS certificate rejected");
    assert!(
        !seen.recv_timeout(Duration::from_secs(10)).unwrap(),
        "the client wrote a request to a server signed by an untrusted CA"
    );
}
