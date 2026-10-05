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
//! Two layers are covered. `fetch_translation` is the low-level verified fetch (a pinned URL and
//! digest into a directory); `download_and_install` is the product call (a catalogue code, a
//! recorded terms acceptance, an installed and validated translation).
#![cfg(feature = "download")]
#![allow(clippy::unwrap_used)]
// Test guards like `assert!(1_000_000 > HASH_CHUNK_BYTES, ...)` assert on compile-time constants
// on purpose (they pin a fixture invariant) — allowed here, as `unwrap_used` is above.
#![allow(clippy::assertions_on_constants)]

mod common;

use std::cell::RefCell;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

use common::{
    catalogue_json, fixture, fixture_labelled, read_dir_names, sha256_hex, tmp_dir, Fixture,
};
use selahcue_scripture::catalog::Catalogue;
use selahcue_scripture::download::{
    default_cache_dir, download_and_install, fetch_translation, fetch_translation_with,
    sha256_file, DownloadError, DownloadOptions, TermsAcceptance, TermsError, TranslationAsset,
    TranslationFetchError, HASH_CHUNK_BYTES,
};
use selahcue_scripture::registry::{InstallError, Phase, Progress, Registry};
use selahcue_scripture::url_policy::{UrlPolicy, UrlRefusal};

/// Serializes the tests that mutate the PROCESS-GLOBAL `SELAHCUE_SCRIPTURE_CACHE` env var, so
/// they never race under cargo's multi-threaded test runner. Poison-tolerant: a failing test
/// must not wedge the others.
static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

const NOW: u64 = 1_790_000_000;

/// A unique temp directory for one test (no external tempfile dep).
fn tmp(tag: &str) -> PathBuf {
    tmp_dir(&format!("dl-{tag}"))
}

/// Serve `body` exactly once over loopback HTTP and return its URL. Detached —
/// the thread exits after the single response. No public network is touched.
fn serve_once(body: Vec<u8>) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let addr = listener.local_addr().expect("local addr");
    let url = format!("http://{addr}/translation.asset");
    thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            // Drain the request headers (a GET has no body).
            let mut req = Vec::new();
            let mut byte = [0u8; 1];
            while let Ok(1) = stream.read(&mut byte) {
                req.push(byte[0]);
                if req.ends_with(b"\r\n\r\n") {
                    break;
                }
            }
            let header = format!(
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            );
            let _ = stream.write_all(header.as_bytes());
            let _ = stream.write_all(&body);
            let _ = stream.flush();
        }
    });
    url
}

/// The SHA-256 of `bytes`, computed through the crate's own chunked hasher (via a
/// temp file) so fixtures can pin the exact digest the fetcher will recompute.
fn sha256_of(dir: &std::path::Path, bytes: &[u8]) -> String {
    let p = dir.join("hash-src.tmp");
    std::fs::write(&p, bytes).unwrap();
    let d = sha256_file(&p).unwrap();
    let _ = std::fs::remove_file(&p);
    d
}

fn loopback() -> UrlPolicy {
    UrlPolicy::allow_loopback_http_for_tests()
}

// ================================ fetch_translation (low level) ================================

#[test]
fn cache_hit_returns_the_verified_file_without_downloading() {
    // A correctly-hashed file already in the cache is returned as-is. The asset URL
    // points at an unreachable port; if the fetcher tried to download it would fail,
    // so a successful return proves the cache short-circuit ran (no network).
    let dir = tmp("hit");
    let body = b"KJV fixture verses".to_vec();
    let sha256 = sha256_of(&dir, &body);
    std::fs::write(dir.join("kjv.asset"), &body).unwrap();

    let asset = TranslationAsset {
        id: "kjv".into(),
        name: "King James Version".into(),
        file_name: "kjv.asset".into(),
        url: "http://127.0.0.1:9/never".into(), // never contacted on a cache hit
        size_bytes: body.len() as u64,
        sha256,
    };

    let got = fetch_translation(&asset, &dir, |_, _| {}).expect("cache hit");
    assert_eq!(got, dir.join("kjv.asset"));
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn successful_download_verifies_installs_and_reports_progress() {
    // A cache miss downloads the bytes, verifies the pinned SHA-256, and atomically
    // installs the file; progress is reported and ends at done == total.
    let dir = tmp("ok");
    let body = b"World English Bible fixture bytes, long enough to matter".to_vec();
    let sha256 = sha256_of(&dir, &body);
    let url = serve_once(body.clone());

    let asset = TranslationAsset {
        id: "web".into(),
        name: "World English Bible".into(),
        file_name: "web.asset".into(),
        url,
        size_bytes: body.len() as u64,
        sha256,
    };

    let last_done = AtomicU64::new(0);
    let total_seen = AtomicU64::new(0);
    let got = fetch_translation_with(&asset, &dir, loopback(), |done, total| {
        last_done.store(done, Ordering::Relaxed);
        total_seen.store(total, Ordering::Relaxed);
    })
    .expect("download + verify + install");

    assert_eq!(got, dir.join("web.asset"));
    assert_eq!(std::fs::read(&got).unwrap(), body);
    assert_eq!(last_done.load(Ordering::Relaxed), body.len() as u64);
    assert_eq!(total_seen.load(Ordering::Relaxed), body.len() as u64);
    // No leftover partial file.
    assert!(!dir.join("web.asset.part").exists());
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn verify_failure_discards_the_bad_file_and_errors() {
    // The server returns bytes that do NOT match the pinned hash. The download must be
    // rejected, the temp file discarded, and nothing installed into the cache.
    let dir = tmp("badhash");
    let body = b"substituted / corrupted payload".to_vec();
    let url = serve_once(body.clone());

    let asset = TranslationAsset {
        id: "asv".into(),
        name: "American Standard Version".into(),
        file_name: "asv.asset".into(),
        url,
        size_bytes: body.len() as u64,
        sha256: "0".repeat(64), // valid hex, but not the body's digest
    };

    let err = fetch_translation_with(&asset, &dir, loopback(), |_, _| {})
        .expect_err("must reject mismatch");
    assert!(
        matches!(err, TranslationFetchError::Verify { .. }),
        "expected a Verify error, got {err:?}"
    );
    // The bad bytes were discarded: neither the installed file nor the .part remain.
    assert!(!dir.join("asv.asset").exists(), "a bad file was installed");
    assert!(
        !dir.join("asv.asset.part").exists(),
        "a .part was left behind"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn oversized_stream_is_capped_before_verification_and_leaves_no_partial() {
    // Bounded disk: a hostile/misconfigured mirror streams FAR more bytes than the pinned size.
    // The fetcher must abort on the size ceiling BEFORE the (post-EOF) SHA-256 gate — so an
    // oversized / never-ending stream can never fill the disk — and must discard the `.part`.
    let dir = tmp("toobig");
    let body = vec![b'x'; 200_000]; // 200 KB streamed...
    let url = serve_once(body);

    let asset = TranslationAsset {
        id: "big".into(),
        name: "Oversized".into(),
        file_name: "big.asset".into(),
        url,
        size_bytes: 1_024, // ...but the pin says 1 KB — the transfer must be capped here.
        sha256: "0".repeat(64),
    };

    let err = fetch_translation_with(&asset, &dir, loopback(), |_, _| {})
        .expect_err("must reject an oversized stream");
    assert!(
        matches!(err, TranslationFetchError::TooLarge { limit } if limit == 1_024),
        "expected TooLarge {{ limit: 1024 }} before verification, got {err:?}"
    );
    // Nothing installed, and the partial file was discarded (no orphaned bytes on disk).
    assert!(
        !dir.join("big.asset").exists(),
        "an oversized file was installed"
    );
    assert!(
        !dir.join("big.asset.part").exists(),
        "a .part was left behind after the over-cap abort"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn the_low_level_fetch_is_https_only_and_refuses_a_hostile_file_name() {
    let dir = tmp("lowpolicy");
    let body = b"fixture".to_vec();
    let sha256 = sha256_of(&dir, &body);
    let url = serve_once(body.clone());
    let asset = TranslationAsset {
        id: "x".into(),
        name: "X".into(),
        file_name: "x.asset".into(),
        url,
        size_bytes: body.len() as u64,
        sha256: sha256.clone(),
    };
    // The product policy refuses the plain-http loopback URL before any request is made...
    let err = fetch_translation(&asset, &dir, |_, _| {}).unwrap_err();
    assert!(
        matches!(
            err,
            TranslationFetchError::Insecure(UrlRefusal::NotHttps { .. })
        ),
        "{err:?}"
    );
    assert!(!dir.join("x.asset").exists());
    // ...and the same call under the test policy succeeds, so the refusal was the policy.
    assert!(fetch_translation_with(&asset, &dir, loopback(), |_, _| {}).is_ok());

    // A file name with a path in it is refused before anything is created.
    for name in [
        "../escape.asset",
        "a/b.asset",
        "/abs.asset",
        ".hidden",
        "",
        "con.asset",
    ] {
        let bad = TranslationAsset {
            file_name: name.to_string(),
            ..asset.clone()
        };
        let err = fetch_translation_with(&bad, &dir, loopback(), |_, _| {}).unwrap_err();
        assert!(
            matches!(err, TranslationFetchError::BadFileName(_)),
            "{name:?}: {err:?}"
        );
    }
    assert_eq!(read_dir_names(&dir), ["x.asset"]);
}

#[cfg(unix)]
#[test]
fn a_planted_symlink_at_the_staging_name_is_not_followed_by_the_low_level_fetch() {
    let dir = tmp("lowsymlink");
    let victim = dir.join("victim.txt");
    std::fs::write(&victim, b"precious").unwrap();
    let body = b"fixture bytes".to_vec();
    let sha256 = sha256_of(&dir, &body);
    std::os::unix::fs::symlink(&victim, dir.join("y.asset.part")).unwrap();
    let asset = TranslationAsset {
        id: "y".into(),
        name: "Y".into(),
        file_name: "y.asset".into(),
        url: serve_once(body.clone()),
        size_bytes: body.len() as u64,
        sha256,
    };
    fetch_translation_with(&asset, &dir, loopback(), |_, _| {}).unwrap();
    assert_eq!(
        std::fs::read(&victim).unwrap(),
        b"precious",
        "written through a symlink"
    );
    assert_eq!(std::fs::read(dir.join("y.asset")).unwrap(), body);
    assert!(std::fs::symlink_metadata(dir.join("y.asset.part"))
        .unwrap()
        .is_symlink());
}

#[test]
fn hashing_a_large_file_is_bounded_and_correct() {
    // Bounded memory: a 1,000,000-byte fixture is far larger than one hash chunk, so it
    // MUST be streamed in chunks. The digest is the canonical SHA-256 test vector for one
    // million 'a' bytes — proving the multi-chunk stream produces the correct hash without
    // ever holding the whole file in memory (mirrors selahcue-stt/src/model.rs).
    let dir = tmp("bounded");
    let big = dir.join("million-a.bin");
    std::fs::write(&big, vec![b'a'; 1_000_000]).unwrap();

    assert!(
        1_000_000 > HASH_CHUNK_BYTES,
        "fixture must exceed one hash chunk to exercise streaming"
    );
    let digest = sha256_file(&big).expect("hash large file");
    assert_eq!(
        digest,
        "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn default_cache_dir_honours_env_override_and_falls_back_to_translations() {
    // One test (not two) so the shared env var is never raced by a parallel test; the ENV_LOCK
    // additionally serialises this against anything else that touches it.
    let _env = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    std::env::set_var(
        "SELAHCUE_SCRIPTURE_CACHE",
        "/tmp/selahcue-scripture-test-cache",
    );
    assert_eq!(
        default_cache_dir(),
        PathBuf::from("/tmp/selahcue-scripture-test-cache")
    );
    std::env::remove_var("SELAHCUE_SCRIPTURE_CACHE");
    assert!(
        default_cache_dir().ends_with("selahcue/translations"),
        "fallback cache dir was {:?}",
        default_cache_dir()
    );
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
                    let mut req = Vec::new();
                    let mut byte = [0u8; 1];
                    while let Ok(1) = stream.read(&mut byte) {
                        req.push(byte[0]);
                        if req.ends_with(b"\r\n\r\n") {
                            break;
                        }
                    }
                    let text = String::from_utf8_lossy(&req).into_owned();
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

    // Damage the file in place: the digest check fails, so it IS downloaded again and repaired.
    let path = dir.join("tst.tsv.gz");
    let mut bytes = std::fs::read(&path).unwrap();
    bytes[12] ^= 0xFF;
    std::fs::write(&path, &bytes).unwrap();
    let repaired =
        download_and_install(&registry, "TST", &terms(), NOW + 100, &test_options()).unwrap();
    assert_eq!(server.hits(), 2, "a damaged install must be fetched again");
    assert_eq!(repaired.installed_at, NOW + 100);
    assert_eq!(std::fs::read(&path).unwrap(), f.gz);
}

#[test]
fn a_download_asks_for_the_file_as_it_is_and_not_compressed_again() {
    // The asset is a .gz. Asking for gzip on top would let a server (or a misconfigured bucket)
    // wrap it again and the digest would never match; the request says `identity`.
    let f = fixture("TST", 3, 2);
    let seen = Arc::new(Mutex::new(String::new()));
    let seen2 = seen.clone();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let addr = listener.local_addr().unwrap();
    let body = f.gz.clone();
    thread::spawn(move || {
        if let Ok((mut stream, _)) = listener.accept() {
            let mut req = Vec::new();
            let mut byte = [0u8; 1];
            while let Ok(1) = stream.read(&mut byte) {
                req.push(byte[0]);
                if req.ends_with(b"\r\n\r\n") {
                    break;
                }
            }
            *seen2.lock().unwrap() = String::from_utf8_lossy(&req).to_ascii_lowercase();
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
