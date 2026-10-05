//! Behavioural tests for the feature-gated Bible-translation download path
//! (`selahcue_scripture::download`, feature `download`).
//!
//! Everything here uses LOCAL fixtures only: a temp directory, fixture files we create and hash
//! ourselves, and loopback HTTP responders on `127.0.0.1` (the same loopback discipline the LAN
//! crate uses for its E2E), never the public network. Plain http is only reachable through the
//! explicit `..._for_tests` constructors; the product policy refuses it, and a test below proves
//! that. With the `download` feature OFF this whole file compiles to nothing, so the pure
//! `cargo test -p selahcue-scripture` is unaffected.
//!
//! One entry point is covered: `download_and_install`, the product call (a catalogue code, a
//! recorded terms acceptance, an installed and validated translation). There is no other download
//! function to test: the legacy fetch-a-pinned-URL-into-a-directory path was removed in round 2.
#![cfg(feature = "download")]
#![allow(clippy::unwrap_used)]

// These tests call the test-only constructors (`..._for_tests`), which exist only when debug
// assertions are on. In a build without them this file would not compile; say why instead.
#[cfg(not(debug_assertions))]
compile_error!("run these tests without --release: the test-only constructors exist only with debug assertions");

mod common;

use std::cell::RefCell;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::Duration;

use common::{
    catalogue_json, fixture, fixture_labelled, gz, read_dir_names, replace_file, sha256_hex,
    tmp_dir, Fixture,
};
use selahcue_scripture::catalog::Catalogue;
use selahcue_scripture::download::{
    download_and_install, DownloadError, DownloadOptions, TermsAcceptance, TermsError,
};
use selahcue_scripture::registry::{InstallError, Phase, Progress, ReceiptError, Registry};
use selahcue_scripture::url_policy::{UrlPolicy, UrlRefusal};

const NOW: u64 = 1_790_000_000;

/// A unique temp directory for one test (no external tempfile dep).
fn tmp(tag: &str) -> PathBuf {
    tmp_dir(&format!("dl-{tag}"))
}

fn loopback() -> UrlPolicy {
    UrlPolicy::allow_loopback_http_for_tests()
}

// ================================== a loopback server ======================================

/// What a test server answers.
struct Resp {
    status: u16,
    headers: Vec<(String, String)>,
    body: Vec<u8>,
    /// Claim a `Content-Length` other than the body's (a body that stops short).
    declared_len: Option<usize>,
    /// Send no `Content-Length` at all (the body ends when the connection closes).
    no_length: bool,
}

impl Resp {
    fn ok(body: Vec<u8>) -> Resp {
        Resp {
            status: 200,
            headers: vec![],
            body,
            declared_len: None,
            no_length: false,
        }
    }

    fn status(status: u16) -> Resp {
        Resp {
            status,
            ..Resp::ok(Vec::new())
        }
    }

    fn redirect(status: u16, location: &str) -> Resp {
        Resp {
            headers: vec![("Location".into(), location.into())],
            ..Resp::status(status)
        }
    }
}

struct Server {
    /// `http://127.0.0.1:PORT`, no trailing slash.
    base: String,
    hits: Arc<AtomicUsize>,
    paths: Arc<Mutex<Vec<String>>>,
    stop: Arc<AtomicBool>,
    addr: std::net::SocketAddr,
}

impl Drop for Server {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        let _ = TcpStream::connect(self.addr); // wake the accept loop so it exits
    }
}

impl Server {
    fn hits(&self) -> usize {
        self.hits.load(Ordering::Relaxed)
    }

    fn paths(&self) -> Vec<String> {
        self.paths.lock().unwrap().clone()
    }
}

/// Read the request headers off `stream` (a GET has no body).
fn drain_request(stream: &mut TcpStream) -> String {
    let mut req = Vec::new();
    let mut byte = [0u8; 1];
    while let Ok(1) = stream.read(&mut byte) {
        req.push(byte[0]);
        if req.ends_with(b"\r\n\r\n") {
            break;
        }
    }
    String::from_utf8_lossy(&req).into_owned()
}

/// A loopback server answering every request through `handler(request_index, path)`.
fn serve(handler: impl Fn(usize, &str) -> Resp + Send + Sync + 'static) -> Server {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let addr = listener.local_addr().unwrap();
    let hits = Arc::new(AtomicUsize::new(0));
    let paths = Arc::new(Mutex::new(Vec::new()));
    let stop = Arc::new(AtomicBool::new(false));
    let handler = Arc::new(handler);
    {
        let (hits, paths, stop, handler) = (hits.clone(), paths.clone(), stop.clone(), handler);
        thread::spawn(move || {
            for stream in listener.incoming() {
                if stop.load(Ordering::Relaxed) {
                    break;
                }
                let Ok(mut stream) = stream else { continue };
                let index = hits.fetch_add(1, Ordering::Relaxed);
                let (paths, handler) = (paths.clone(), handler.clone());
                thread::spawn(move || {
                    let text = drain_request(&mut stream);
                    let path = text
                        .lines()
                        .next()
                        .and_then(|l| l.split_whitespace().nth(1))
                        .unwrap_or("")
                        .to_string();
                    paths.lock().unwrap().push(path.clone());
                    let r = handler(index, &path);
                    let reason = match r.status {
                        200 => "OK",
                        302 => "Found",
                        404 => "Not Found",
                        500 => "Internal Server Error",
                        _ => "Status",
                    };
                    let mut head = format!("HTTP/1.1 {} {reason}\r\n", r.status);
                    for (k, v) in &r.headers {
                        head.push_str(&format!("{k}: {v}\r\n"));
                    }
                    if !r.no_length {
                        head.push_str(&format!(
                            "Content-Length: {}\r\n",
                            r.declared_len.unwrap_or(r.body.len())
                        ));
                    }
                    head.push_str("Connection: close\r\n\r\n");
                    let _ = stream.write_all(head.as_bytes());
                    let _ = stream.write_all(&r.body);
                    let _ = stream.flush();
                });
            }
        });
    }
    Server {
        base: format!("http://{addr}"),
        hits,
        paths,
        stop,
        addr,
    }
}

/// A one-connection server that sends the headers and the first half of `body`, tells the test it
/// has, then goes quiet for `pause` and hangs up with the body unfinished: a download that stalls.
fn serve_then_stall(body: Vec<u8>, sent_first_half: mpsc::Sender<()>, pause: Duration) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let base = format!("http://{}", listener.local_addr().unwrap());
    thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            drain_request(&mut stream);
            let head = format!(
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            );
            let _ = stream.write_all(head.as_bytes());
            let _ = stream.write_all(&body[..body.len() / 2]);
            let _ = stream.flush();
            let _ = sent_first_half.send(());
            thread::sleep(pause);
            // Dropped here: the connection closes with the body unfinished.
        }
    });
    base
}

/// A one-connection server that reads the request, tells the test it has, answers nothing for
/// `pause`, and hangs up: a connection that stalls before any response.
fn serve_silent(got_request: mpsc::Sender<()>, pause: Duration) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let base = format!("http://{}", listener.local_addr().unwrap());
    thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            drain_request(&mut stream);
            let _ = got_request.send(());
            thread::sleep(pause);
        }
    });
    base
}

// ============================== download_and_install (the product call) ======================

fn terms() -> TermsAcceptance {
    TermsAcceptance::new("cc0", "2026-10", 1_789_999_000).unwrap()
}

fn test_options() -> DownloadOptions<'static> {
    DownloadOptions::new().allow_loopback_http_for_tests()
}

/// A registry whose catalogue lists `fixtures` (cleared unless named in `pending`), published at
/// `base` under `/t/`, or unpublished when `base` is `None`.
fn registry_for(
    fixtures: &[&Fixture],
    base: Option<&str>,
    pending: &[&str],
) -> (Registry, PathBuf) {
    let root = tmp("registry");
    let entries = fixtures
        .iter()
        .map(|f| {
            f.entry(if pending.contains(&f.code.as_str()) {
                "pending"
            } else {
                "cleared"
            })
        })
        .collect();
    let base_url = base.map(|b| format!("{b}/t/"));
    let catalogue =
        Catalogue::parse_with(&catalogue_json(base_url.as_deref(), entries), loopback()).unwrap();
    let dir = root.join("data");
    (Registry::new(dir.clone(), catalogue), dir)
}

fn serving(f: &Fixture) -> Server {
    let (file, body) = (f.file_name(), f.gz.clone());
    serve(move |_, path| {
        if path == format!("/t/{file}") {
            Resp::ok(body.clone())
        } else {
            Resp::status(404)
        }
    })
}

#[test]
fn a_catalogued_translation_downloads_validates_and_installs() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);

    let rec = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap();
    assert_eq!(rec.code.as_str(), "TST");
    assert_eq!(rec.sha256, f.sha256);
    assert_eq!(rec.installed_at, NOW);
    assert_eq!((rec.verses_ot, rec.verses_nt), (3, 2));
    assert_eq!(server.hits(), 1);
    // The URL came from the catalogue's single template: base_url + file_name.
    assert_eq!(server.paths(), ["/t/tst.tsv.gz"]);
    assert_eq!(read_dir_names(&dir), ["installed.json", "tst.tsv.gz"]);
    let bible = registry.bible("tst").expect("installed");
    assert_eq!(bible.verse_count(), 5);
}

#[test]
fn progress_runs_download_then_verify_then_install_and_ends_at_the_pinned_size() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &[]);
    let seen: RefCell<Vec<Progress>> = RefCell::new(Vec::new());
    let cb = |p: Progress| seen.borrow_mut().push(p);
    let opts = test_options().with_progress(&cb);
    download_and_install(&registry, "TST", &terms(), NOW, &opts).unwrap();

    let seen = seen.into_inner();
    let phases: Vec<Phase> = seen.iter().map(|p| p.phase).collect();
    assert_eq!(phases.first(), Some(&Phase::Downloading));
    assert_eq!(phases.last(), Some(&Phase::Installing));
    assert!(phases.contains(&Phase::Verifying));
    let total = f.gz.len() as u64;
    let last_download = seen
        .iter()
        .rev()
        .find(|p| p.phase == Phase::Downloading)
        .unwrap();
    assert_eq!((last_download.done, last_download.total), (total, total));
}

#[test]
fn cancel_stops_a_download_and_leaves_nothing_installed() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
    let cancel = AtomicBool::new(false);
    let cb = |p: Progress| {
        if p.phase == Phase::Downloading {
            cancel.store(true, Ordering::Relaxed);
        }
    };
    let opts = test_options().with_cancel(&cancel).with_progress(&cb);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &opts).unwrap_err();
    assert!(err.is_cancelled(), "{err:?}");
    assert_eq!(
        read_dir_names(&dir),
        Vec::<String>::new(),
        "a cancelled download left files"
    );
    assert_eq!(registry.installed().unwrap(), vec![]);

    // Positive control: without the flag the same call installs.
    assert!(download_and_install(&registry, "TST", &terms(), NOW, &test_options()).is_ok());
}

#[test]
fn a_flag_already_set_cancels_before_any_request_is_made() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &[]);
    let cancel = AtomicBool::new(true);
    let opts = test_options().with_cancel(&cancel);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &opts).unwrap_err();
    assert!(err.is_cancelled(), "{err:?}");
    assert_eq!(server.hits(), 0);
}

#[test]
fn a_read_that_fails_after_cancel_was_pressed_is_reported_as_cancelled() {
    // The download is blocked reading the second half of the body when the user presses Cancel;
    // the server then hangs up, which is a read error. That error is the cancel, not a network
    // failure to put on screen.
    let f = fixture("TST", 3, 2);
    let (tx, rx) = mpsc::channel();
    let base = serve_then_stall(f.gz.clone(), tx, Duration::from_millis(700));
    let (registry, dir) = registry_for(&[&f], Some(&base), &[]);
    let cancel = AtomicBool::new(false);
    let result = thread::scope(|scope| {
        let download = scope.spawn(|| {
            let opts = test_options().with_cancel(&cancel);
            download_and_install(&registry, "TST", &terms(), NOW, &opts)
        });
        rx.recv_timeout(Duration::from_secs(10))
            .expect("the server never sent its first half");
        // The download has taken the first half and is now blocked waiting for the rest.
        thread::sleep(Duration::from_millis(200));
        cancel.store(true, Ordering::SeqCst);
        download.join().unwrap()
    });
    let err = result.unwrap_err();
    assert!(err.is_cancelled(), "{err:?}");
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
    assert_eq!(registry.installed().unwrap(), vec![]);

    // Positive control: the very same failure, with nobody having pressed Cancel, is a network
    // failure.
    let (tx, rx) = mpsc::channel();
    let base = serve_then_stall(f.gz.clone(), tx, Duration::from_millis(200));
    let (registry, _dir) = registry_for(&[&f], Some(&base), &[]);
    let cancel = AtomicBool::new(false);
    let opts = test_options().with_cancel(&cancel);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &opts).unwrap_err();
    drop(rx);
    assert!(matches!(err, DownloadError::Network(_)), "{err:?}");
}

#[test]
fn a_connection_that_fails_after_cancel_was_pressed_is_reported_as_cancelled() {
    // The same for the other place a request can be blocked: before any response header.
    let f = fixture("TST", 3, 2);
    let (tx, rx) = mpsc::channel();
    let base = serve_silent(tx, Duration::from_millis(700));
    let (registry, _dir) = registry_for(&[&f], Some(&base), &[]);
    let cancel = AtomicBool::new(false);
    let result = thread::scope(|scope| {
        let download = scope.spawn(|| {
            let opts = test_options().with_cancel(&cancel);
            download_and_install(&registry, "TST", &terms(), NOW, &opts)
        });
        rx.recv_timeout(Duration::from_secs(10))
            .expect("the server never saw the request");
        thread::sleep(Duration::from_millis(200));
        cancel.store(true, Ordering::SeqCst);
        download.join().unwrap()
    });
    let err = result.unwrap_err();
    assert!(err.is_cancelled(), "{err:?}");

    // Positive control: without the flag the same hang-up is a network failure.
    let (tx, _rx) = mpsc::channel();
    let base = serve_silent(tx, Duration::from_millis(200));
    let (registry, _dir) = registry_for(&[&f], Some(&base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(matches!(err, DownloadError::Network(_)), "{err:?}");
}

#[test]
fn an_unpublished_entry_reports_not_published_and_makes_no_request() {
    let f = fixture("TST", 3, 2);
    // The control: the same server, with a catalogue that points at it, is requested.
    let server = serving(&f);
    let (published, _) = registry_for(&[&f], Some(&server.base), &[]);
    download_and_install(&published, "TST", &terms(), NOW, &test_options()).unwrap();
    assert_eq!(
        server.hits(),
        1,
        "premise: a published catalogue does make a request"
    );

    // No base URL: there is no URL to request, so nothing is.
    let (unpublished, dir) = registry_for(&[&f], None, &[]);
    let err =
        download_and_install(&unpublished, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(matches!(err, DownloadError::NotPublished), "{err:?}");
    assert_eq!(err.to_string(), "not published yet");
    assert_eq!(
        server.hits(),
        1,
        "an unpublished entry must never attempt a request"
    );
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
}

#[test]
fn the_shipped_catalogue_cannot_download_anything_yet() {
    // The embedded catalogue has no base URL. Through a registry built over it, even the cleared
    // BSB entry (CC0, so the acceptance below is for the right licence) reports "not published
    // yet" and never reaches a socket.
    let dir = tmp("shipped").join("data");
    let registry = Registry::new(dir.clone(), Catalogue::embedded().clone());
    let err =
        download_and_install(&registry, "BSB", &terms(), NOW, &DownloadOptions::new()).unwrap_err();
    assert!(matches!(err, DownloadError::NotPublished), "{err:?}");
    assert!(
        !dir.exists(),
        "nothing may be created for an unpublished entry"
    );
}

#[test]
fn a_pending_entry_is_refused_unless_a_test_override_is_set() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &["TST"]);

    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(
        matches!(err, DownloadError::LegalReviewPending { ref code } if code == "TST"),
        "{err:?}"
    );
    assert_eq!(server.hits(), 0, "a pending entry must not be requested");

    // The override exists, is explicit, and is what lets it through.
    let opts = test_options().allow_legal_pending_for_tests();
    assert!(download_and_install(&registry, "TST", &terms(), NOW, &opts).is_ok());
    assert_eq!(server.hits(), 1);
}

#[test]
fn an_unknown_code_is_refused_without_a_request() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &[]);
    for code in ["NOPE", "KJV", "", "../x"] {
        let err =
            download_and_install(&registry, code, &terms(), NOW, &test_options()).unwrap_err();
        assert!(
            matches!(err, DownloadError::UnknownCode { .. }),
            "{code:?}: {err:?}"
        );
    }
    assert_eq!(server.hits(), 0);
}

#[test]
fn the_terms_acceptance_must_be_for_the_licence_of_the_translation() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &[]);
    let wrong = TermsAcceptance::new("cc-by-sa-4.0", "2026-10", 1).unwrap();
    let err = download_and_install(&registry, "TST", &wrong, NOW, &test_options()).unwrap_err();
    match err {
        DownloadError::TermsMismatch { expected, accepted } => {
            assert_eq!(
                (expected.as_str(), accepted.as_str()),
                ("cc0", "cc-by-sa-4.0")
            );
        }
        other => panic!("expected TermsMismatch, got {other:?}"),
    }
    assert_eq!(server.hits(), 0);
}

#[test]
fn a_terms_acceptance_has_to_be_well_formed() {
    let t = TermsAcceptance::new("cc0", "2026-10", 42).unwrap();
    assert_eq!(
        (t.licence_id(), t.terms_version(), t.accepted_at()),
        ("cc0", "2026-10", 42)
    );
    for (licence, version) in [("", "v1"), ("cc0", ""), ("   ", "v1"), ("cc0", "  ")] {
        assert!(
            matches!(
                TermsAcceptance::new(licence, version, 1),
                Err(TermsError::Empty)
            ),
            "{licence:?} {version:?}"
        );
    }
    assert!(matches!(
        TermsAcceptance::new(&"x".repeat(200), "v1", 1),
        Err(TermsError::TooLong)
    ));
    assert!(matches!(
        TermsAcceptance::new("cc0\nHost: evil", "v1", 1),
        Err(TermsError::BadCharacter)
    ));
}

#[test]
fn the_product_policy_refuses_a_plain_http_url_before_any_request() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    // The catalogue is built with the test policy (so it may name a loopback http base)...
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
    // ...but the DOWNLOAD defaults to https only.
    let err =
        download_and_install(&registry, "TST", &terms(), NOW, &DownloadOptions::new()).unwrap_err();
    assert!(
        matches!(err, DownloadError::Insecure(UrlRefusal::NotHttps { ref scheme }) if scheme == "http"),
        "{err:?}"
    );
    assert_eq!(
        server.hits(),
        0,
        "an http URL must be refused before a connection is opened"
    );
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
    // Positive control: under the test policy the very same call goes through.
    assert!(download_and_install(&registry, "TST", &terms(), NOW, &test_options()).is_ok());
}

#[test]
fn a_redirect_to_a_non_https_host_is_refused() {
    let f = fixture("TST", 3, 2);
    // To plain http on a real-looking host: refused even under the loopback test policy.
    let origin = serve(|_, _| Resp::redirect(302, "http://downloads.example.org/tst.tsv.gz"));
    let (registry, dir) = registry_for(&[&f], Some(&origin.base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(
        matches!(err, DownloadError::Insecure(UrlRefusal::NotHttps { ref scheme }) if scheme == "http"),
        "{err:?}"
    );
    assert_eq!(origin.hits(), 1, "only the first request may be made");
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
}

#[test]
fn a_redirect_that_stays_on_an_allowed_url_is_followed() {
    // Positive control for the refusal above: the same redirect machinery follows a good hop.
    let f = fixture("TST", 3, 2);
    let body = f.gz.clone();
    let origin = serve(move |_, path| match path {
        "/t/tst.tsv.gz" => Resp::redirect(302, "/moved/tst.tsv.gz"),
        "/moved/tst.tsv.gz" => Resp::ok(body.clone()),
        _ => Resp::status(404),
    });
    let (registry, _dir) = registry_for(&[&f], Some(&origin.base), &[]);
    download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap();
    assert_eq!(origin.paths(), ["/t/tst.tsv.gz", "/moved/tst.tsv.gz"]);
}

#[test]
fn a_redirect_loop_and_a_redirect_without_a_target_are_bounded_failures() {
    let f = fixture("TST", 3, 2);
    let looping = serve(|_, _| Resp::redirect(302, "/t/tst.tsv.gz"));
    let (registry, dir) = registry_for(&[&f], Some(&looping.base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(matches!(err, DownloadError::Network(_)), "{err:?}");
    assert!(
        looping.hits() <= 8,
        "a redirect loop was followed {} times",
        looping.hits()
    );
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());

    let nowhere = serve(|_, _| Resp::status(302));
    let (registry, _dir) = registry_for(&[&f], Some(&nowhere.base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(matches!(err, DownloadError::Network(_)), "{err:?}");
}

#[test]
fn a_server_error_or_an_unreachable_host_is_a_network_failure_that_installs_nothing() {
    let f = fixture("TST", 3, 2);
    for status in [404u16, 500] {
        let server = serve(move |_, _| Resp::status(status));
        let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
        let err =
            download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
        assert!(
            matches!(err, DownloadError::Network(_)),
            "{status}: {err:?}"
        );
        assert_eq!(read_dir_names(&dir), Vec::<String>::new(), "{status}");
    }
    // Nothing listening: bind, note the port, drop the listener.
    let closed = {
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        format!("http://{}", l.local_addr().unwrap())
    };
    let (registry, dir) = registry_for(&[&f], Some(&closed), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(matches!(err, DownloadError::Network(_)), "{err:?}");
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
}

#[test]
fn a_wrong_oversized_or_truncated_body_is_rejected_and_leaves_no_partial_install() {
    let f = fixture("TST", 3, 2);
    let mut flipped = f.gz.clone();
    flipped[12] ^= 0xFF;
    let mut bigger = f.gz.clone();
    bigger.extend_from_slice(&vec![0u8; 300_000]);
    let short = f.gz[..f.gz.len() / 2].to_vec();

    // (what, what the server sends, the error it must reach)
    let cases: Vec<(&str, Resp, &str)> = vec![
        (
            "a body with the wrong digest",
            Resp::ok(flipped),
            "Install(Verify",
        ),
        // No Content-Length, so only the size cap can stop it.
        (
            "an oversized stream",
            Resp {
                no_length: true,
                ..Resp::ok(bigger)
            },
            "Install(TooLarge",
        ),
        // Promises the full length, delivers half, closes.
        (
            "a body cut short",
            Resp {
                declared_len: Some(f.gz.len()),
                ..Resp::ok(short)
            },
            "Network(",
        ),
    ];
    for (what, resp, expect) in cases {
        let resp = Arc::new(Mutex::new(Some(resp)));
        let server = serve(move |_, _| {
            resp.lock()
                .unwrap()
                .take()
                .unwrap_or_else(|| Resp::status(404))
        });
        let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
        let err =
            download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
        let shown = format!("{err:?}");
        assert!(
            shown.starts_with(expect),
            "{what}: expected {expect}..., got {shown}"
        );
        assert_eq!(
            read_dir_names(&dir),
            Vec::<String>::new(),
            "{what}: a partial install was left"
        );
        assert_eq!(registry.installed().unwrap(), vec![], "{what}");
    }
}

#[test]
fn an_already_installed_intact_translation_needs_no_network() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
    let first = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap();
    assert_eq!(server.hits(), 1);

    // Same pin, intact file: served from disk, no request, the original receipt.
    let again =
        download_and_install(&registry, "TST", &terms(), NOW + 99, &test_options()).unwrap();
    assert_eq!(again, first);
    assert_eq!(
        server.hits(),
        1,
        "an intact install must not be downloaded again"
    );

    // Damage the file (a replacement with the same size and one byte flipped; a new inode, so the
    // registry's remembered answer for the old file cannot apply): the digest check fails, so it
    // IS downloaded again and repaired.
    let path = dir.join("tst.tsv.gz");
    let mut bytes = std::fs::read(&path).unwrap();
    bytes[12] ^= 0xFF;
    replace_file(&path, &bytes);
    let repaired =
        download_and_install(&registry, "TST", &terms(), NOW + 100, &test_options()).unwrap();
    assert_eq!(server.hits(), 2, "a damaged install must be fetched again");
    assert_eq!(repaired.installed_at, NOW + 100);
    assert_eq!(std::fs::read(&path).unwrap(), f.gz);
}

#[test]
fn an_unreadable_install_record_is_refused_before_any_request() {
    let f = fixture("TST", 3, 2);
    let server = serving(&f);
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("installed.json"), b"{not json").unwrap();

    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(
        matches!(
            err,
            DownloadError::Install(InstallError::Receipt(ReceiptError::Corrupt(_)))
        ),
        "{err:?}"
    );
    assert_eq!(
        server.hits(),
        0,
        "a download that could only be discarded was started"
    );
    assert_eq!(
        std::fs::read(dir.join("installed.json")).unwrap(),
        b"{not json",
        "the unreadable record was changed"
    );

    // Positive control: once the record is repaired, the same call downloads.
    registry.repair_receipt(NOW).unwrap();
    assert!(download_and_install(&registry, "TST", &terms(), NOW, &test_options()).is_ok());
    assert_eq!(server.hits(), 1);
}

#[test]
fn a_download_asks_for_the_file_as_it_is_and_not_compressed_again() {
    // The asset is a .gz. The request says `identity` so a server has no reason to wrap it again.
    let f = fixture("TST", 3, 2);
    let seen = Arc::new(Mutex::new(String::new()));
    let seen2 = seen.clone();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let addr = listener.local_addr().unwrap();
    let body = f.gz.clone();
    thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            let request = drain_request(&mut stream);
            *seen2.lock().unwrap() = request.to_ascii_lowercase();
            let head = format!(
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            );
            let _ = stream.write_all(head.as_bytes());
            let _ = stream.write_all(&body);
        }
    });
    let base = format!("http://{addr}");
    let (registry, _dir) = registry_for(&[&f], Some(&base), &[]);
    download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap();
    let request = seen.lock().unwrap().clone();
    assert!(
        request.contains("accept-encoding: identity"),
        "the request must ask for the file as it is, got:\n{request}"
    );
}

#[test]
fn a_response_wrapped_in_gzip_is_undone_before_the_size_cap_and_the_digest_are_checked() {
    // The asset is itself a .gz. A server that compresses it AGAIN and says so
    // (`Content-Encoding: gzip`) is not trusted to be right, and does not need to be: the client
    // undoes the wrapping, and the size cap and the digest are applied to what comes out. So a
    // wrapped response of the right file installs, and a wrapped response that inflates to far more
    // than the pinned size is stopped at the pinned size, however small it was on the wire.
    let f = fixture("TST", 3, 2);
    let wrapped = gz(&f.gz);
    assert_ne!(wrapped.len(), f.gz.len(), "premise: it really is wrapped");
    let server = serve(move |_, _| Resp {
        headers: vec![("Content-Encoding".into(), "gzip".into())],
        ..Resp::ok(wrapped.clone())
    });
    let (registry, _dir) = registry_for(&[&f], Some(&server.base), &[]);
    let rec = download_and_install(&registry, "TST", &terms(), NOW, &test_options())
        .expect("a wrapped response of the right file is undone and then checked like any other");
    assert_eq!(rec.sha256, f.sha256);

    // The bomb: 20 MiB of zeros is a few tens of KB wrapped.
    let bomb = gz(&vec![0u8; 20 * 1024 * 1024]);
    assert!(bomb.len() < 100 * 1024, "premise: small on the wire");
    let server = serve(move |_, _| Resp {
        headers: vec![("Content-Encoding".into(), "gzip".into())],
        ..Resp::ok(bomb.clone())
    });
    let (registry, dir) = registry_for(&[&f], Some(&server.base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(
        matches!(
            err,
            DownloadError::Install(InstallError::TooLarge { limit }) if limit == f.gz.len() as u64
        ),
        "{err:?}"
    );
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
}

#[test]
fn error_texts_never_carry_a_query_string_or_a_fragment() {
    // A CDN redirects to a signed URL (`?token=...`). If the download then fails, the error goes to
    // the screen, to events and to logs: the token must not go with it, in `Display` or `Debug`.
    let f = fixture("TST", 3, 2);
    let signed = "?token=SECRET123&sig=abc#frag";
    let closed = {
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        format!("http://{}", l.local_addr().unwrap())
    };

    // (what, the redirect the origin sends, a status for the signed target if it is reached,
    //  a piece of the URL that SHOULD still be in the text: the redaction cuts, it does not blank)
    let cases: Vec<(&str, String, u16, &str)> = vec![
        (
            "a signed URL answering 500",
            format!("/signed/tst.tsv.gz{signed}"),
            500,
            "/signed/tst.tsv.gz",
        ),
        (
            "a signed URL answering 404",
            format!("/signed/tst.tsv.gz{signed}"),
            404,
            "/signed/tst.tsv.gz",
        ),
        (
            "a signed URL on a host that refuses the connection",
            format!("{closed}/x/tst.tsv.gz{signed}"),
            500,
            "/x/tst.tsv.gz",
        ),
        (
            "a relative reference that is not followed",
            format!("tst.tsv.gz{signed}"),
            500,
            "unsupported redirect to 'tst.tsv.gz'",
        ),
        (
            "a redirect loop through signed URLs",
            format!("/t/tst.tsv.gz{signed}"),
            302,
            "redirects",
        ),
    ];
    for (what, location, target_status, keep) in cases {
        // The catalogue's URL (`/t/...`) always redirects to `location`. Whatever is reached after
        // that answers `target_status`, or redirects again when that is 302 (the loop case).
        let origin = serve(move |_, path| {
            if path.starts_with("/t/") || target_status == 302 {
                Resp::redirect(302, &location)
            } else {
                Resp::status(target_status)
            }
        });
        let (registry, dir) = registry_for(&[&f], Some(&origin.base), &[]);
        let err =
            download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
        for (kind, text) in [("Display", err.to_string()), ("Debug", format!("{err:?}"))] {
            for secret in ["SECRET123", "token=", "sig=abc", "frag"] {
                assert!(
                    !text.contains(secret),
                    "{what}: {kind} of the error carries {secret:?}: {text}"
                );
            }
        }
        assert!(
            err.to_string().contains(keep),
            "{what}: the redaction removed more than the query: {err}"
        );
        assert_eq!(read_dir_names(&dir), Vec::<String>::new(), "{what}");
    }
}

#[test]
fn a_body_that_is_not_the_pinned_file_is_refused_through_the_product_call() {
    // A different, perfectly valid translation served under the pinned file name is refused: the
    // digest is the pin. (A second statement of the substitution refusal, through the whole call.)
    let pinned = fixture("TST", 3, 2);
    let other = fixture_labelled("TST", "OTHER", 3, 2);
    assert_ne!(sha256_hex(&other.gz), pinned.sha256);
    let server = serving(&other);
    let (registry, dir) = registry_for(&[&pinned], Some(&server.base), &[]);
    let err = download_and_install(&registry, "TST", &terms(), NOW, &test_options()).unwrap_err();
    assert!(
        matches!(
            err,
            DownloadError::Install(InstallError::Verify { .. })
                | DownloadError::Install(InstallError::TooLarge { .. })
        ),
        "{err:?}"
    );
    assert_eq!(read_dir_names(&dir), Vec::<String>::new());
}

#[test]
fn the_default_options_are_the_product_configuration() {
    let o = DownloadOptions::new();
    assert_eq!(o.url_policy(), UrlPolicy::https_only());
    assert!(!o.allows_pending_for_tests());
    let o = DownloadOptions::new()
        .allow_loopback_http_for_tests()
        .allow_legal_pending_for_tests();
    assert_eq!(o.url_policy(), UrlPolicy::allow_loopback_http_for_tests());
    assert!(o.allows_pending_for_tests());
}
