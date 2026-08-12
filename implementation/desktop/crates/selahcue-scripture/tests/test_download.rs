//! Behavioural tests for the feature-gated Bible-translation download infra
//! (`selahcue_scripture::download`, feature `download`).
//!
//! Everything here uses LOCAL fixtures only: a temp cache dir, temp fixture files
//! we create + hash ourselves, and a one-shot loopback HTTP responder on
//! `127.0.0.1` (the same loopback discipline the LAN crate uses for its E2E) —
//! never the public network. With the `download` feature OFF this whole file
//! compiles to nothing, so the pure `cargo test -p selahcue-scripture` is
//! unaffected.
#![cfg(feature = "download")]
#![allow(clippy::unwrap_used)]
// Test guards like `assert!(1_000_000 > HASH_CHUNK_BYTES, ...)` assert on compile-time constants
// on purpose (they pin a fixture invariant) — allowed here, as `unwrap_used` is above.
#![allow(clippy::assertions_on_constants)]

use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::thread;

use selahcue_scripture::download::{
    catalog, default_cache_dir, fetch_translation, sha256_file, TranslationAsset,
    TranslationFetchError, HASH_CHUNK_BYTES, YLT_FILE_NAME,
};

/// Serializes the tests that mutate the PROCESS-GLOBAL `SELAHCUE_SCRIPTURE_CACHE` env var, so
/// they never race under cargo's multi-threaded test runner. Poison-tolerant: a failing test
/// must not wedge the others.
static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

/// A synthetic gzipped verse index (`book<TAB>chapter<TAB>verse<TAB>text`, the SAME format as
/// the bundled `assets/*.tsv.gz`) holding one verse: John 3:16 (book 43). Pre-generated so the
/// test needs no gzip dependency; decompresses to
/// `"43\t3\t16\tfor God did so love the world (YLT fixture)\n"`.
const YLT_FIXTURE_GZIP: &[u8] = &[
    31, 139, 8, 0, 0, 0, 0, 0, 2, 255, 51, 49, 230, 52, 230, 52, 52, 227, 76, 203, 47, 82, 112,
    207, 79, 81, 72, 201, 76, 81, 40, 206, 87, 200, 201, 47, 75, 85, 40, 201, 72, 85, 40, 207, 47,
    202, 73, 81, 208, 136, 244, 9, 81, 72, 203, 172, 40, 41, 45, 74, 213, 228, 2, 0, 94, 204, 20,
    14, 52, 0, 0, 0,
];

/// A unique temp directory for one test (no external tempfile dep).
fn tmp_dir(tag: &str) -> PathBuf {
    static SEQ: AtomicU32 = AtomicU32::new(0);
    let n = SEQ.fetch_add(1, Ordering::Relaxed);
    let d = std::env::temp_dir().join(format!(
        "selahcue-scripture-dl-{}-{}-{}",
        tag,
        std::process::id(),
        n
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
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

#[test]
fn cache_hit_returns_the_verified_file_without_downloading() {
    // A correctly-hashed file already in the cache is returned as-is. The asset URL
    // points at an unreachable port; if the fetcher tried to download it would fail,
    // so a successful return proves the cache short-circuit ran (no network).
    let dir = tmp_dir("hit");
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
    let dir = tmp_dir("ok");
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
    let got = fetch_translation(&asset, &dir, |done, total| {
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
    let dir = tmp_dir("badhash");
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

    let err = fetch_translation(&asset, &dir, |_, _| {}).expect_err("must reject mismatch");
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
    let dir = tmp_dir("toobig");
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

    let err =
        fetch_translation(&asset, &dir, |_, _| {}).expect_err("must reject an oversized stream");
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
fn hashing_a_large_file_is_bounded_and_correct() {
    // Bounded memory: a 1,000,000-byte fixture is far larger than one hash chunk, so it
    // MUST be streamed in chunks. The digest is the canonical SHA-256 test vector for one
    // million 'a' bytes — proving the multi-chunk stream produces the correct hash without
    // ever holding the whole file in memory (mirrors selahcue-stt/src/model.rs).
    let dir = tmp_dir("bounded");
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
    // additionally serialises this against the runtime-load test below.
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

#[test]
fn youngs_literal_loads_from_the_cache_and_reports_availability() {
    // End-to-end runtime wiring of a DOWNLOADABLE translation: the verse data is NOT compiled
    // in — it loads from the on-disk cache the download machinery installs to. Uses a synthetic
    // local fixture (no network): absent -> unavailable + empty lookups; present -> available +
    // the fixture verse resolves. The loader reads `default_cache_dir().join(YLT_FILE_NAME)`,
    // which the `SELAHCUE_SCRIPTURE_CACHE` override points at our temp dir.
    use selahcue_core::scripture::parse_one;
    use selahcue_scripture::{is_available, passage_text_in, verses_in, Translation};

    let _env = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let dir = tmp_dir("ylt-runtime");
    std::env::set_var("SELAHCUE_SCRIPTURE_CACHE", &dir);

    let r = parse_one("John 3:16").unwrap();

    // Absent (not yet downloaded): unavailable, and every lookup degrades to nothing — no panic.
    assert!(
        !is_available(Translation::Ylt),
        "YLT is unavailable before its asset is present"
    );
    assert!(verses_in(Translation::Ylt, &r).is_empty());
    assert!(passage_text_in(Translation::Ylt, &r).is_none());

    // Install the synthetic gzipped verse index where the download machinery would put it.
    std::fs::write(dir.join(YLT_FILE_NAME), YLT_FIXTURE_GZIP).unwrap();

    // Present: available, and the verse lookup returns the fixture text (loaded from disk).
    assert!(
        is_available(Translation::Ylt),
        "YLT is available once its cached asset is present"
    );
    assert_eq!(
        passage_text_in(Translation::Ylt, &r).as_deref(),
        Some("for God did so love the world (YLT fixture)"),
        "verse text comes from the on-disk fixture, not a compiled asset"
    );
    let vs = verses_in(Translation::Ylt, &r);
    assert_eq!(vs.len(), 1);
    assert_eq!((vs[0].book, vs[0].chapter, vs[0].verse), (43, 3, 16));

    std::env::remove_var("SELAHCUE_SCRIPTURE_CACHE");
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn catalog_is_a_seam_and_every_entry_is_a_well_formed_pin() {
    // The catalog is intentionally EMPTY by default — real entries (URL + SHA-256 +
    // licensing) are owner-supplied (same custody model as the NDI SDK). Whatever it
    // holds must be a valid supply-chain pin: 64-char lowercase-hex SHA-256, an http(s)
    // URL, a non-empty file name/id, and a positive size.
    for a in catalog() {
        assert!(!a.id.is_empty(), "catalog entry has an empty id");
        assert!(!a.file_name.is_empty(), "{} has an empty file_name", a.id);
        assert_eq!(a.sha256.len(), 64, "{} sha256 is not 64 hex chars", a.id);
        assert!(
            a.sha256
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
            "{} sha256 must be lowercase hex",
            a.id
        );
        assert!(
            a.url.starts_with("http://") || a.url.starts_with("https://"),
            "{} url is not http(s): {}",
            a.id,
            a.url
        );
        assert!(a.size_bytes > 0, "{} has a zero size", a.id);
    }
}
