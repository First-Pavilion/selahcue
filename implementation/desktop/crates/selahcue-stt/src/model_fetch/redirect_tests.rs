//! Genuine first-hop/multihop TLS model downloads, not a duplicated URL parser.
//! The thread-local CA seam is cfg(test) only and never changes redirect/proxy/deadline policy.
#![allow(clippy::unwrap_used)]
use super::{fetch_model_phased, DownloadPhase, FailReason};
use crate::model::{ModelAsset, WhisperModel};
use rcgen::{BasicConstraints, CertificateParams, DnType, IsCa, Issuer, KeyPair, KeyUsagePurpose};
use std::cell::RefCell;
use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, AtomicU32, Ordering},
    Arc, Mutex,
};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

const PIN: &str = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
thread_local! { static ROOT: RefCell<Option<Vec<u8>>> = const { RefCell::new(None) }; }

pub(super) fn fixture_tls() -> Option<ureq::tls::TlsConfig> {
    ROOT.with(|root| {
        root.borrow().as_ref().map(|der| {
            let cert = ureq::tls::Certificate::from_der(der).to_owned();
            ureq::tls::TlsConfig::builder()
                .root_certs(ureq::tls::RootCerts::new_with_certs(&[cert]))
                .build()
        })
    })
}
struct Trust(Option<Vec<u8>>);
impl Trust {
    fn install(ca: &Ca) -> Self {
        Self(ROOT.with(|root| root.replace(Some(ca.der.clone()))))
    }
}
impl Drop for Trust {
    fn drop(&mut self) {
        ROOT.with(|root| root.replace(self.0.take()));
    }
}

struct Ca {
    der: Vec<u8>,
    config: Arc<rustls::ServerConfig>,
}
impl Ca {
    fn new() -> Self {
        let mut params = CertificateParams::new(Vec::<String>::new()).unwrap();
        params
            .distinguished_name
            .push(DnType::CommonName, "DNV Test CA");
        params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
        params.key_usages = vec![KeyUsagePurpose::KeyCertSign, KeyUsagePurpose::CrlSign];
        let key = KeyPair::generate().unwrap();
        let ca = params.self_signed(&key).unwrap();
        let issuer = Issuer::new(params, key);
        let params = CertificateParams::new(vec!["localhost".into()]).unwrap();
        let leaf_key = KeyPair::generate().unwrap();
        let leaf = params.signed_by(&leaf_key, &issuer).unwrap();
        let config = rustls::ServerConfig::builder_with_provider(Arc::new(
            rustls::crypto::ring::default_provider(),
        ))
        .with_safe_default_protocol_versions()
        .unwrap()
        .with_no_client_auth()
        .with_single_cert(
            vec![leaf.der().clone()],
            rustls::pki_types::PrivatePkcs8KeyDer::from(leaf_key.serialize_der()).into(),
        )
        .unwrap();
        Self {
            der: ca.der().to_vec(),
            config: Arc::new(config),
        }
    }
}

struct Reply {
    status: u16,
    location: Option<String>,
    body: &'static [u8],
    length: usize,
}
impl Reply {
    fn body(body: &'static [u8]) -> Self {
        Self {
            status: 200,
            location: None,
            body,
            length: body.len(),
        }
    }
    fn redirect(status: u16, location: String) -> Self {
        Self {
            status,
            location: Some(location),
            body: b"",
            length: 0,
        }
    }
}
struct Server {
    base: String,
    seen: Arc<Mutex<Vec<String>>>,
    stop: Arc<AtomicBool>,
    worker: Option<JoinHandle<()>>,
}
impl Server {
    fn start(ca: Option<&Ca>, reply: impl Fn(&str) -> Reply + Send + 'static) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let addr = listener.local_addr().unwrap();
        let base = match ca {
            Some(_) => format!("https://localhost:{}", addr.port()),
            None => format!("http://127.0.0.1:{}", addr.port()),
        };
        let config = ca.map(|ca| Arc::clone(&ca.config));
        let seen = Arc::new(Mutex::new(Vec::new()));
        let recorded = Arc::clone(&seen);
        let stop = Arc::new(AtomicBool::new(false));
        let stopping = Arc::clone(&stop);
        let worker = thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_secs(15);
            let mut accepted = 0;
            while accepted < 20 && Instant::now() < deadline {
                match listener.accept() {
                    Ok((socket, _)) => {
                        accepted += 1;
                        socket.set_nonblocking(false).unwrap();
                        socket
                            .set_read_timeout(Some(Duration::from_secs(2)))
                            .unwrap();
                        socket
                            .set_write_timeout(Some(Duration::from_secs(2)))
                            .unwrap();
                        if let Some(config) = &config {
                            let connection =
                                rustls::ServerConnection::new(Arc::clone(config)).unwrap();
                            handle(
                                rustls::StreamOwned::new(connection, socket),
                                &recorded,
                                &reply,
                            );
                        } else {
                            handle(socket, &recorded, &reply);
                        }
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        if stopping.load(Ordering::SeqCst) {
                            break;
                        }
                        thread::sleep(Duration::from_millis(2));
                    }
                    Err(error) => panic!("fixture accept: {error}"),
                }
            }
        });
        Self {
            base,
            seen,
            stop,
            worker: Some(worker),
        }
    }
    fn finish(mut self) -> Vec<String> {
        self.stop.store(true, Ordering::SeqCst);
        self.worker.take().unwrap().join().unwrap();
        self.seen.lock().unwrap().clone()
    }
}
impl Drop for Server {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
fn handle(
    mut socket: impl Read + Write,
    seen: &Mutex<Vec<String>>,
    reply: &impl Fn(&str) -> Reply,
) {
    let mut head = Vec::new();
    let mut buffer = [0u8; 1024];
    while head.len() < 16 * 1024 {
        match socket.read(&mut buffer) {
            Ok(0) | Err(_) => return, // unknown-CA refusal may stop during handshake.
            Ok(n) => {
                head.extend_from_slice(&buffer[..n]);
            }
        }
        if head.windows(4).any(|bytes| bytes == b"\r\n\r\n") {
            break;
        }
    }
    let head = String::from_utf8(head).unwrap();
    let response = reply(&head);
    seen.lock().unwrap().push(head); // recorded BEFORE response, so completed fetch observes it.
    let location = response
        .location
        .map(|value| format!("Location: {value}\r\n"))
        .unwrap_or_default();
    let header = format!(
        "HTTP/1.1 {} Fixture\r\n{}Content-Length: {}\r\nConnection: close\r\n\r\n",
        response.status, location, response.length
    );
    let _ = socket.write_all(header.as_bytes());
    let _ = socket.write_all(response.body);
    let _ = socket.flush();
}
struct Cache(PathBuf);
impl Cache {
    fn new() -> Self {
        static NEXT: AtomicU32 = AtomicU32::new(0);
        let path = std::env::temp_dir().join(format!(
            "dnv-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::SeqCst)
        ));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
    fn empty(&self) {
        assert!(!self.0.join("model.bin").exists());
        assert!(!self.0.join("model.bin.part").exists());
    }
}
impl Drop for Cache {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn asset(base: &str) -> ModelAsset {
    // ModelAsset's production manifest fields are static. At most one tiny fixture URL per
    // bounded test case is retained until this test process exits; no production allocation.
    ModelAsset {
        model: WhisperModel::Base,
        file_name: "model.bin",
        url: Box::leak(format!("{base}/").into_boxed_str()),
        sha256: PIN,
        size_bytes: 3,
    }
}
fn no_credentials(requests: &[String]) {
    assert!(
        !requests.is_empty(),
        "must observe at least one real request"
    );
    for request in requests {
        let lower = request.to_ascii_lowercase();
        assert!(!lower.contains("authorization:"));
        assert!(!lower.contains("cookie:"));
    }
}
fn failed(phases: &[DownloadPhase], reason: FailReason) {
    assert!(
        matches!(phases.last(), Some(DownloadPhase::Failed { reason: got, resumable: false, bytes_kept: 0, .. }) if *got == reason)
    );
    assert!(!phases.contains(&DownloadPhase::Ready));
}
fn downgrade(status: u16, extra_tls_hop: bool) {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let target = Server::start(None, |_| Reply::body(b"abc"));
    let location = format!("{}/model.bin", target.base);
    let middle = Server::start(Some(&ca), move |_| {
        Reply::redirect(status, location.clone())
    });
    let first_location = format!("{}/model.bin", middle.base);
    let first = Server::start(Some(&ca), move |_| {
        Reply::redirect(302, first_location.clone())
    });
    let base = if extra_tls_hop {
        &first.base
    } else {
        &middle.base
    };
    let cache = Cache::new();
    let mut phases = Vec::new();
    let result = fetch_model_phased(&asset(base), &cache.0, |phase| phases.push(phase), || false);
    let insecure = target.finish();
    let secure = middle.finish();
    let earlier = first.finish();
    println!("DNV_DOWNGRADE status={status} extraTls={extra_tls_hop} tlsRequests={} httpRequests={} resultOk={}", secure.len() + earlier.len(), insecure.len(), result.is_ok());
    no_credentials(&secure);
    if extra_tls_hop {
        no_credentials(&earlier);
    } else {
        assert!(earlier.is_empty());
    }
    assert!(
        insecure.is_empty(),
        "HTTP redirect target received {} requests",
        insecure.len()
    );
    assert!(result.is_err(), "downgrade must refuse rather than install");
    cache.empty();
    failed(&phases, FailReason::Other);
}
macro_rules! downgrade_case {
    ($name:ident, $status:expr) => {
        #[test]
        fn $name() {
            downgrade($status, false);
        }
    };
}
downgrade_case!(dnv_https_301_to_http_is_never_requested, 301);
downgrade_case!(dnv_https_302_to_http_is_never_requested, 302);
downgrade_case!(dnv_https_303_to_http_is_never_requested, 303);
downgrade_case!(dnv_https_307_to_http_is_never_requested, 307);
downgrade_case!(dnv_https_308_to_http_is_never_requested, 308);
#[test]
fn dnv_later_tls_hop_cannot_downgrade_to_http() {
    downgrade(307, true);
}
#[test]
fn dnv_plain_http_first_request_is_refused_before_send() {
    let server = Server::start(None, |_| Reply::body(b"abc"));
    let cache = Cache::new();
    let mut phases = Vec::new();
    let result = fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| phases.push(phase),
        || false,
    );
    let seen = server.finish();
    println!(
        "DNV_FIRST_HTTP requests={} resultOk={}",
        seen.len(),
        result.is_ok()
    );
    assert!(seen.is_empty());
    assert!(result.is_err());
    cache.empty();
    failed(&phases, FailReason::Other);
}
#[test]
fn dnv_tls_redirect_loop_stops_at_five_hops() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |_| {
        Reply::redirect(302, "/loop/model.bin".into())
    });
    let cache = Cache::new();
    let mut phases = Vec::new();
    let result = fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| phases.push(phase),
        || false,
    );
    let seen = server.finish();
    println!("DNV_HOP_BOUND requests={}", seen.len());
    no_credentials(&seen);
    assert_eq!(seen.len(), 6, "initial request plus at most five redirects");
    assert!(result.is_err());
    cache.empty();
    failed(&phases, FailReason::Connect);
}
#[test]
fn dnv_exactly_five_legitimate_tls_redirects_install_verified_bytes() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |request| {
        let path = request.split_whitespace().nth(1).unwrap();
        let step: u32 = path.split('/').nth(2).unwrap().parse().unwrap();
        if step < 5 {
            Reply::redirect(302, format!("/step/{}/model.bin", step + 1))
        } else {
            Reply::body(b"abc")
        }
    });
    let cache = Cache::new();
    let mut phases = Vec::new();
    let result = fetch_model_phased(
        &asset(&format!("{}/step/0", server.base)),
        &cache.0,
        |phase| phases.push(phase),
        || false,
    )
    .unwrap();
    let seen = server.finish();
    no_credentials(&seen);
    assert_eq!(seen.len(), 6);
    assert_eq!(fs::read(result).unwrap(), b"abc");
    assert!(!cache.0.join("model.bin.part").exists());
    assert!(matches!(
        phases.first(),
        Some(DownloadPhase::Downloading { done: 3, total: 3 })
    ));
    assert!(phases.contains(&DownloadPhase::Verifying));
    assert_eq!(phases.last(), Some(&DownloadPhase::Ready));
}
#[test]
fn dnv_relative_and_scheme_relative_tls_locations_still_work() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |request| {
        let path = request.split_whitespace().nth(1).unwrap();
        if path == "/model.bin" {
            Reply::redirect(301, "./next/model.bin".into())
        } else if path == "/next/model.bin" {
            let host = request
                .lines()
                .find_map(|line| {
                    let (name, value) = line.split_once(':')?;
                    name.eq_ignore_ascii_case("host").then(|| value.trim())
                })
                .unwrap();
            Reply::redirect(307, format!("//{host}/final/model.bin"))
        } else {
            assert_eq!(path, "/final/model.bin");
            Reply::body(b"abc")
        }
    });
    let cache = Cache::new();
    let result = fetch_model_phased(&asset(&server.base), &cache.0, |_| {}, || false).unwrap();
    assert_eq!(fs::read(result).unwrap(), b"abc");
    let seen = server.finish();
    no_credentials(&seen);
    assert_eq!(seen.len(), 3);
}
#[test]
fn dnv_http_recorder_positive_receives_actual_request() {
    let server = Server::start(None, |_| Reply::body(b"abc"));
    let agent: ureq::Agent = ureq::Agent::config_builder().proxy(None).build().into();
    let mut response = agent
        .get(&format!("{}/model.bin", server.base))
        .call()
        .unwrap();
    let body = response.body_mut().read_to_vec().unwrap();
    assert_eq!(body, b"abc");
    let seen = server.finish();
    no_credentials(&seen);
    assert_eq!(seen.len(), 1);
}
#[test]
fn dnv_valid_cached_model_needs_no_network_and_wins_over_cancel() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |_| Reply::body(b"abc"));
    let cache = Cache::new();
    let asset = asset(&server.base);
    fetch_model_phased(&asset, &cache.0, |_| {}, || false).unwrap();
    assert_eq!(server.finish().len(), 1);
    let mut phases = Vec::new();
    let path = fetch_model_phased(&asset, &cache.0, |phase| phases.push(phase), || true).unwrap();
    assert_eq!(fs::read(path).unwrap(), b"abc");
    assert_eq!(phases, vec![DownloadPhase::Ready]);
}
#[test]
fn dnv_tls_integrity_mismatch_removes_partial_and_installed_files() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |_| Reply::body(b"bad"));
    let cache = Cache::new();
    let mut phases = Vec::new();
    assert!(fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| phases.push(phase),
        || false
    )
    .is_err());
    assert_eq!(server.finish().len(), 1);
    cache.empty();
    failed(&phases, FailReason::Verify);
}
#[test]
fn dnv_tls_truncated_body_removes_partial_file() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |_| Reply {
        length: 9,
        ..Reply::body(b"abc")
    });
    let cache = Cache::new();
    let mut phases = Vec::new();
    assert!(fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| phases.push(phase),
        || false
    )
    .is_err());
    assert_eq!(server.finish().len(), 1);
    cache.empty();
    failed(&phases, FailReason::Connect);
}
#[test]
fn dnv_tls_download_cancellation_keeps_nothing_and_never_emits_ready() {
    let ca = Ca::new();
    let _trust = Trust::install(&ca);
    let server = Server::start(Some(&ca), |_| Reply::body(b"abc"));
    let cache = Cache::new();
    let mut phases = Vec::new();
    let cancel = AtomicBool::new(false);
    let error = fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| {
            if matches!(phase, DownloadPhase::Downloading { .. }) {
                cancel.store(true, Ordering::SeqCst);
            }
            phases.push(phase);
        },
        || cancel.load(Ordering::SeqCst),
    )
    .unwrap_err();
    assert_eq!(error, "cancelled");
    assert_eq!(server.finish().len(), 1);
    cache.empty();
    failed(&phases, FailReason::Other);
}
#[test]
fn dnv_unknown_ca_is_refused_before_a_request_reaches_tls_server() {
    assert!(fixture_tls().is_none());
    let ca = Ca::new();
    let server = Server::start(Some(&ca), |_| Reply::body(b"abc"));
    let cache = Cache::new();
    let mut phases = Vec::new();
    assert!(fetch_model_phased(
        &asset(&server.base),
        &cache.0,
        |phase| phases.push(phase),
        || false
    )
    .is_err());
    assert!(server.finish().is_empty());
    cache.empty();
    failed(&phases, FailReason::Connect);
}
