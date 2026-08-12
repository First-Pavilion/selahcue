//! Download-on-demand for whisper model files (feature `download`).
//!
//! Resolves a pinned [`ModelAsset`] to a verified local file: a **cache hit** returns the
//! already-present, SHA-256-matching file; otherwise the file is downloaded (streaming),
//! its pinned SHA-256 is verified (FR-156 / ADR-0012), and it is atomically installed into
//! the cache. Pure-Rust (no native toolchain), so this compiles and tests without whisper.
//!
//! Offline-first (NFR-015 / CON-2): nothing here runs unless the caller invokes it on an
//! explicit user action, a network failure is a plain `Err` (never a crash), and a cached
//! model needs no network. The URL and the pinned digest travel together in the manifest, so
//! a corrupted or substituted download is rejected before it is ever loaded.

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use crate::model::{verify_model, ModelAsset};

/// Bytes streamed per read/write while downloading (bounds transient memory).
const DL_CHUNK_BYTES: usize = 64 * 1024;

/// A phase of the on-demand model download, surfaced so the operator's "Offline Download Modal"
/// (Figma node 396-124) can render a distinct state per step. Driven in order: `Downloading*`
/// while bytes stream, then a single `Verifying` for the SHA-256 gate, then `Ready` on success —
/// or `Failed` (with a classified [`FailReason`]) at the point of failure.
///
/// A plain domain enum (this crate has no `serde`): the operator adapter maps it onto its own
/// serializable Tauri event payload.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DownloadPhase {
    /// Bytes are streaming in: `done` of `total` received (`total` is the pinned/advertised size).
    Downloading { done: u64, total: u64 },
    /// The transfer finished; the pinned SHA-256 is being recomputed (FR-156 / ADR-0012).
    Verifying,
    /// The file is present and integrity-verified — ready to load.
    Ready,
    /// The fetch failed at some step. `reason` classifies it; `resumable`/`bytes_kept` tell the UI
    /// whether progress can be resumed. This client does NOT support resume, so `resumable` is
    /// always `false` and `bytes_kept` `0` — a retry re-downloads from the start.
    Failed {
        reason: FailReason,
        message: String,
        resumable: bool,
        bytes_kept: u64,
    },
}

/// Why a model fetch failed — chooses which recovery the modal offers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FailReason {
    /// A network/HTTP/timeout error reaching or reading from the server ("Couldn't connect").
    Connect,
    /// DNS resolution failed — treated as "offline, needs a connection once".
    Offline,
    /// The downloaded bytes failed the pinned SHA-256 integrity check ("Couldn't verify"); the
    /// file is discarded.
    Verify,
    /// Any other failure (filesystem, config) that is neither connectivity nor integrity.
    Other,
}

/// The default per-user cache directory for downloaded models. Honours
/// `SELAHCUE_STT_CACHE`, then the platform cache convention, ending in `selahcue/models`.
pub fn default_cache_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("SELAHCUE_STT_CACHE") {
        return PathBuf::from(dir);
    }
    cache_root().join("selahcue").join("models")
}

/// Platform cache root (no `dirs` dependency; conventional locations).
fn cache_root() -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join("Library").join("Caches");
        }
    }
    #[cfg(target_os = "windows")]
    {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            return PathBuf::from(local);
        }
    }
    if let Ok(xdg) = std::env::var("XDG_CACHE_HOME") {
        return PathBuf::from(xdg);
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".cache");
    }
    std::env::temp_dir()
}

/// Resolve `asset` to a verified local model file under `cache_dir`.
///
/// - **Cache hit**: if the file already exists and its SHA-256 matches the pin, return it.
/// - **Miss**: stream the download to a `.part` temp file (invoking `progress(done, total)`),
///   verify the pinned SHA-256, then atomically rename it into place. On any integrity
///   failure the temp file is removed and an error returned — a bad file is never installed.
pub fn fetch_model(
    asset: &ModelAsset,
    cache_dir: &Path,
    mut progress: impl FnMut(u64, u64),
) -> Result<PathBuf, String> {
    // The `(done, total)` contract is a projection of the richer phase model: forward only the
    // Downloading phase so existing byte-progress callers are unchanged. This entry point never
    // cancels (`|| false`), so its behaviour is identical to before cancellation existed.
    fetch_model_phased(
        asset,
        cache_dir,
        |phase| {
            if let DownloadPhase::Downloading { done, total } = phase {
                progress(done, total);
            }
        },
        || false,
    )
}

/// Resolve `asset` to a verified local model file under `cache_dir`, driving `phase` through the
/// download lifecycle (for the operator's phase-aware modal).
///
/// - **Cache hit**: an already-present, integrity-matching file emits [`DownloadPhase::Ready`] and
///   returns immediately — no download, no re-hash pass.
/// - **Miss**: stream the download (emitting [`DownloadPhase::Downloading`] per chunk), then
///   [`DownloadPhase::Verifying`] before the pinned SHA-256 gate, then [`DownloadPhase::Ready`] on
///   success. On any failure a terminal [`DownloadPhase::Failed`] is emitted with a classified
///   [`FailReason`] and the partial/bad file is discarded (a bad file is never installed).
///
/// `cancel` is polled cooperatively once per streamed chunk (and again before the SHA-256 gate);
/// when it returns `true` the transfer stops immediately, the partial `.part` file is removed
/// (nothing is left installed), and the fetch reports a terminal
/// `Failed { reason: FailReason::Other, message: "cancelled", resumable: false, bytes_kept: 0 }`
/// via `phase` and returns `Err("cancelled")`. A **cache hit** resolves to `Ready` before `cancel`
/// is ever consulted, so cancelling an already-installed model never deletes the good file.
pub fn fetch_model_phased(
    asset: &ModelAsset,
    cache_dir: &Path,
    mut phase: impl FnMut(DownloadPhase),
    cancel: impl Fn() -> bool,
) -> Result<PathBuf, String> {
    let target = cache_dir.join(asset.file_name);
    if target.exists() && verify_model(&target, asset.sha256).is_ok() {
        // Already present and integrity-verified — Ready with no download/verify pass. A cache hit
        // wins over a pending cancel: an installed model is never removed by cancellation.
        phase(DownloadPhase::Ready);
        return Ok(target);
    }
    if let Err(e) = fs::create_dir_all(cache_dir) {
        return fail(
            &mut phase,
            FailReason::Other,
            format!("create cache dir {cache_dir:?}: {e}"),
        );
    }

    let url = asset.download_url();
    let resp = match ureq::get(&url).call() {
        Ok(r) => r,
        Err(e) => {
            let reason = classify_ureq_error(&e);
            return fail(&mut phase, reason, format!("download {url}: {e}"));
        }
    };
    let total: u64 = resp
        .header("Content-Length")
        .and_then(|s| s.parse().ok())
        .unwrap_or(asset.size_bytes);
    let reader = resp.into_reader();
    install_from_stream(asset, cache_dir, total, reader, &mut phase, &cancel)
}

/// Stream `reader` (`total` advertised bytes) into the cache for `asset`, driving `phase`:
/// [`DownloadPhase::Downloading`] per chunk, then [`DownloadPhase::Verifying`] before the SHA-256
/// gate, then [`DownloadPhase::Ready`] on success — or [`DownloadPhase::Failed`] (partial/bad file
/// discarded) on any error. Network-free and deterministic, so tests drive it with an in-memory
/// reader. A read error mid-transfer is a connectivity failure (`Connect`); a write error is local
/// (`Other`); a digest mismatch is `Verify`.
///
/// `cancel` is polled once per streamed chunk (and once more before the SHA-256 gate). When it
/// returns `true` the transfer stops at once, the `.part` file is removed after its handle is
/// dropped (so nothing is left installed — verified even on Windows), and a terminal
/// `Failed { FailReason::Other, "cancelled", .. }` is emitted with `Err("cancelled")` returned.
fn install_from_stream(
    asset: &ModelAsset,
    cache_dir: &Path,
    total: u64,
    mut reader: impl Read,
    phase: &mut dyn FnMut(DownloadPhase),
    cancel: &dyn Fn() -> bool,
) -> Result<PathBuf, String> {
    let target = cache_dir.join(asset.file_name);
    let tmp = cache_dir.join(format!("{}.part", asset.file_name));

    let mut cancelled = false;
    {
        let mut file = match fs::File::create(&tmp) {
            Ok(f) => f,
            Err(e) => return fail(phase, FailReason::Other, format!("create {tmp:?}: {e}")),
        };
        let mut buf = [0u8; DL_CHUNK_BYTES];
        let mut done: u64 = 0;
        loop {
            // Cooperative cancel: poll once per chunk. Break out (rather than removing the still-open
            // file here) so the handle is dropped before the `.part` is unlinked below.
            if cancel() {
                cancelled = true;
                break;
            }
            let n = match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => n,
                Err(e) => {
                    let _ = fs::remove_file(&tmp);
                    return fail(
                        phase,
                        FailReason::Connect,
                        format!("read download stream: {e}"),
                    );
                }
            };
            if let Err(e) = file.write_all(&buf[..n]) {
                let _ = fs::remove_file(&tmp);
                return fail(phase, FailReason::Other, format!("write {tmp:?}: {e}"));
            }
            done = done.saturating_add(n as u64);
            phase(DownloadPhase::Downloading { done, total });
        }
        let _ = file.flush();
    }

    // Cancelled mid-transfer (or just before the gate): the `.part` handle is now dropped, so remove
    // it and report the cancellation. Nothing is installed; no bytes are kept (retry re-downloads).
    if cancelled || cancel() {
        let _ = fs::remove_file(&tmp);
        return fail(phase, FailReason::Other, "cancelled".to_string());
    }

    // Integrity gate (FR-156): the downloaded bytes must match the pinned SHA-256.
    phase(DownloadPhase::Verifying);
    match verify_model(&tmp, asset.sha256) {
        Ok(_) => {
            if let Err(e) = fs::rename(&tmp, &target) {
                let _ = fs::remove_file(&tmp);
                return fail(
                    phase,
                    FailReason::Other,
                    format!("install model {target:?}: {e}"),
                );
            }
            phase(DownloadPhase::Ready);
            Ok(target)
        }
        Err(e) => {
            // A corrupt/substituted download is discarded — never installed, and (no resume) no
            // bytes are kept, so the modal must retry from the start.
            let _ = fs::remove_file(&tmp);
            fail(
                phase,
                FailReason::Verify,
                format!("downloaded model failed the integrity check: {e}"),
            )
        }
    }
}

/// Emit a terminal [`DownloadPhase::Failed`] and return the same message as the `Err`. Resume is
/// NOT supported, so `resumable` is always `false` and `bytes_kept` `0` (documented so the
/// "Couldn't connect" modal never promises to keep progress).
fn fail(
    phase: &mut dyn FnMut(DownloadPhase),
    reason: FailReason,
    message: String,
) -> Result<PathBuf, String> {
    phase(DownloadPhase::Failed {
        reason,
        message: message.clone(),
        resumable: false,
        bytes_kept: 0,
    });
    Err(message)
}

/// Classify a `ureq` download error into a [`FailReason`] for the modal.
fn classify_ureq_error(e: &ureq::Error) -> FailReason {
    fail_reason_for_kind(e.kind())
}

/// The [`FailReason`] for a `ureq::ErrorKind` — split out so the mapping is unit-testable without
/// a live socket. DNS failure ⇒ `Offline` (no connection to resolve the host); other
/// transport/HTTP/timeout errors ⇒ `Connect`; a malformed URL/scheme (config, not connectivity)
/// ⇒ `Other`. Deterministic given the error kind.
fn fail_reason_for_kind(kind: ureq::ErrorKind) -> FailReason {
    match kind {
        ureq::ErrorKind::Dns => FailReason::Offline,
        ureq::ErrorKind::ConnectionFailed
        | ureq::ErrorKind::Io
        | ureq::ErrorKind::HTTP
        | ureq::ErrorKind::BadStatus
        | ureq::ErrorKind::BadHeader
        | ureq::ErrorKind::TooManyRedirects => FailReason::Connect,
        _ => FailReason::Other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::WhisperModel;

    fn tmp_dir(tag: &str) -> PathBuf {
        use std::sync::atomic::{AtomicU32, Ordering};
        static SEQ: AtomicU32 = AtomicU32::new(0);
        let n = SEQ.fetch_add(1, Ordering::Relaxed);
        let d = std::env::temp_dir().join(format!(
            "selahcue-fetch-{}-{}-{}",
            tag,
            std::process::id(),
            n
        ));
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn cache_hit_returns_the_verified_file_without_network() {
        // A pre-cached file whose bytes match the asset's pinned hash is returned as-is (no
        // network is touched — this test runs offline). Uses the NIST SHA-256("abc") vector.
        let dir = tmp_dir("hit");
        let asset = ModelAsset {
            model: WhisperModel::Base,
            file_name: "test.bin",
            url: "https://example.invalid/", // never contacted on a cache hit
            sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            size_bytes: 3,
        };
        fs::write(dir.join("test.bin"), b"abc").unwrap();
        let got = fetch_model(&asset, &dir, |_, _| {}).expect("cache hit");
        assert_eq!(got, dir.join("test.bin"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn default_cache_dir_resolves_and_honours_the_env_override() {
        // One test (not two) to avoid a parallel race on the shared env var.
        std::env::set_var("SELAHCUE_STT_CACHE", "/tmp/selahcue-test-cache");
        assert_eq!(
            default_cache_dir(),
            PathBuf::from("/tmp/selahcue-test-cache")
        );
        std::env::remove_var("SELAHCUE_STT_CACHE");
        assert!(
            default_cache_dir().ends_with("selahcue/models"),
            "got {:?}",
            default_cache_dir()
        );
    }

    /// A 64-hex-char SHA-256 that no real content produces (all zeros) — forces a verify failure.
    const NON_MATCHING_SHA: &str =
        "0000000000000000000000000000000000000000000000000000000000000000";

    /// An asset pinned to `sha` with a throwaway name/URL (never contacted in these tests).
    fn asset_pinned(sha: &'static str, size: u64) -> ModelAsset {
        ModelAsset {
            model: WhisperModel::Base,
            file_name: "test.bin",
            url: "https://example.invalid/",
            sha256: sha,
            size_bytes: size,
        }
    }

    #[test]
    fn cache_hit_emits_ready_only_and_does_not_download() {
        // A pre-cached, integrity-matching file resolves to Ready immediately — the modal shows
        // "Ready" with no Downloading/Verifying pass and no network is touched (SHA-256("abc")).
        let dir = tmp_dir("hit-phase");
        let asset = asset_pinned(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            3,
        );
        fs::write(dir.join("test.bin"), b"abc").unwrap();
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let got =
            fetch_model_phased(&asset, &dir, |p| phases.push(p), || false).expect("cache hit");
        assert_eq!(got, dir.join("test.bin"));
        assert_eq!(phases, vec![DownloadPhase::Ready]);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn successful_fetch_phase_order_is_downloading_then_verifying_then_ready() {
        // The happy path drives the modal states in order: one-or-more Downloading, then a single
        // Verifying (SHA-256), then Ready. Uses an in-memory stream — no network.
        let dir = tmp_dir("ok-phase");
        let asset = asset_pinned(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            3,
        );
        fs::create_dir_all(&dir).unwrap();
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let got = install_from_stream(
            &asset,
            &dir,
            3,
            &b"abc"[..],
            &mut |p| phases.push(p),
            &|| false,
        )
        .expect("install");
        assert_eq!(got, dir.join("test.bin"));
        assert!(got.exists(), "the verified file is installed");
        assert!(
            matches!(phases.first(), Some(DownloadPhase::Downloading { .. })),
            "first phase is Downloading, got {phases:?}"
        );
        let verify_idx = phases
            .iter()
            .position(|p| matches!(p, DownloadPhase::Verifying))
            .expect("a Verifying phase is present");
        assert!(
            phases[..verify_idx]
                .iter()
                .all(|p| matches!(p, DownloadPhase::Downloading { .. })),
            "only Downloading precedes Verifying, got {phases:?}"
        );
        assert_eq!(phases.last(), Some(&DownloadPhase::Ready));
        assert_eq!(
            verify_idx,
            phases.len() - 2,
            "Verifying immediately precedes Ready, got {phases:?}"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn hash_mismatch_yields_failed_verify_and_discards_the_file() {
        // Bytes that don't match the pin fail the integrity gate: the modal gets Failed{Verify},
        // the bad file is DISCARDED (neither installed nor left as a .part), and — since a corrupt
        // file is never resumed — resumable is false with zero bytes kept.
        let dir = tmp_dir("mismatch-phase");
        let asset = asset_pinned(NON_MATCHING_SHA, 3);
        fs::create_dir_all(&dir).unwrap();
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let res = install_from_stream(
            &asset,
            &dir,
            3,
            &b"abc"[..],
            &mut |p| phases.push(p),
            &|| false,
        );
        assert!(res.is_err(), "a hash mismatch must fail the fetch");
        assert!(
            !dir.join("test.bin").exists(),
            "the corrupt file must not be installed"
        );
        assert!(
            !dir.join("test.bin.part").exists(),
            "the partial file must be removed (discarded)"
        );
        match phases.last() {
            Some(DownloadPhase::Failed {
                reason,
                resumable,
                bytes_kept,
                ..
            }) => {
                assert_eq!(*reason, FailReason::Verify);
                assert!(!*resumable, "a corrupt file is not resumable");
                assert_eq!(*bytes_kept, 0);
            }
            other => panic!("expected a terminal Failed{{Verify}} phase, got {other:?}"),
        }
        assert!(
            phases.iter().any(|p| matches!(p, DownloadPhase::Verifying)),
            "Verifying is announced before the integrity failure, got {phases:?}"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn download_stream_is_read_in_bounded_chunks_no_leak() {
        // No-leak: a multi-hundred-MB model must never be buffered whole. The stream is copied in
        // fixed DL_CHUNK_BYTES reads, so each Downloading step advances by at most one chunk —
        // mirroring the bounded hash chunk in model.rs. Assert the cadence, not final integrity.
        assert!(
            DL_CHUNK_BYTES <= 64 * 1024,
            "download chunk must stay small (bounded memory)"
        );
        let dir = tmp_dir("chunked-phase");
        let asset = asset_pinned(NON_MATCHING_SHA, 0);
        fs::create_dir_all(&dir).unwrap();
        let len = DL_CHUNK_BYTES * 3 + 7; // spans several chunks plus a remainder
        let data = vec![0u8; len];
        let mut deltas: Vec<u64> = Vec::new();
        let mut last = 0u64;
        let _ = install_from_stream(
            &asset,
            &dir,
            len as u64,
            &data[..],
            &mut |p| {
                if let DownloadPhase::Downloading { done, .. } = p {
                    deltas.push(done - last);
                    last = done;
                }
            },
            &|| false,
        );
        assert!(
            deltas.len() >= 4,
            "a >3-chunk stream must be read in multiple bounded reads, got {} reads",
            deltas.len()
        );
        assert!(
            deltas.iter().all(|d| *d <= DL_CHUNK_BYTES as u64),
            "no single read may exceed one chunk (bounded per-iteration memory)"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn cancel_mid_download_removes_partial_and_returns_cancelled() {
        // A cooperative cancel that flips true after the first chunk stops the transfer at once:
        // the modal gets a terminal Failed{Other,"cancelled"}, the fetch returns an Err whose
        // message is "cancelled", and NOTHING is left behind — no installed file and no `.part`.
        // It never reaches the SHA-256 gate (no Verifying).
        use std::sync::atomic::{AtomicBool, Ordering};
        let dir = tmp_dir("cancel-mid");
        let asset = asset_pinned(NON_MATCHING_SHA, 0);
        fs::create_dir_all(&dir).unwrap();
        let len = DL_CHUNK_BYTES * 4; // several chunks so a mid-stream cancel is observable
        let data = vec![0u8; len];
        let cancel_flag = AtomicBool::new(false);
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let res = install_from_stream(
            &asset,
            &dir,
            len as u64,
            &data[..],
            &mut |p| {
                // Ask to cancel as soon as the first chunk has streamed.
                if matches!(p, DownloadPhase::Downloading { .. }) {
                    cancel_flag.store(true, Ordering::SeqCst);
                }
                phases.push(p);
            },
            &|| cancel_flag.load(Ordering::SeqCst),
        );
        let err = res.expect_err("a cancelled download must fail the fetch");
        assert!(err.contains("cancelled"), "err was {err:?}");
        assert!(
            !dir.join("test.bin").exists(),
            "nothing is installed on cancel"
        );
        assert!(
            !dir.join("test.bin.part").exists(),
            "the partial .part file is removed on cancel"
        );
        match phases.last() {
            Some(DownloadPhase::Failed {
                reason,
                message,
                resumable,
                bytes_kept,
            }) => {
                assert_eq!(*reason, FailReason::Other);
                assert_eq!(message, "cancelled");
                assert!(!*resumable);
                assert_eq!(*bytes_kept, 0);
            }
            other => panic!("expected a terminal Failed cancelled phase, got {other:?}"),
        }
        let downloads = phases
            .iter()
            .filter(|p| matches!(p, DownloadPhase::Downloading { .. }))
            .count();
        assert!(
            (1..4).contains(&downloads),
            "cancel stops early: some but not all chunks stream, got {downloads}"
        );
        assert!(
            !phases.iter().any(|p| matches!(p, DownloadPhase::Verifying)),
            "a cancelled download never reaches the SHA-256 gate, got {phases:?}"
        );
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn cancel_that_never_fires_completes_the_download_normally() {
        // No regression: a cancel that always returns false leaves the happy path intact —
        // Downloading → Verifying → Ready and the verified file installed (SHA-256("abc")).
        let dir = tmp_dir("cancel-never");
        let asset = asset_pinned(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            3,
        );
        fs::create_dir_all(&dir).unwrap();
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let got = install_from_stream(
            &asset,
            &dir,
            3,
            &b"abc"[..],
            &mut |p| phases.push(p),
            &|| false,
        )
        .expect("install");
        assert_eq!(got, dir.join("test.bin"));
        assert!(got.exists(), "the verified file is installed");
        assert!(
            matches!(phases.first(), Some(DownloadPhase::Downloading { .. })),
            "first phase is Downloading, got {phases:?}"
        );
        assert!(
            phases.iter().any(|p| matches!(p, DownloadPhase::Verifying)),
            "Verifying is announced, got {phases:?}"
        );
        assert_eq!(phases.last(), Some(&DownloadPhase::Ready));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn cancel_is_a_noop_after_ready_and_keeps_the_cached_file() {
        // Cancelling once the model is already installed must NOT delete the good cached file: a
        // cache hit resolves to Ready before the cancel flag is ever consulted (SHA-256("abc")).
        let dir = tmp_dir("cancel-noop-ready");
        let asset = asset_pinned(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            3,
        );
        fs::write(dir.join("test.bin"), b"abc").unwrap();
        let mut phases: Vec<DownloadPhase> = Vec::new();
        let got = fetch_model_phased(&asset, &dir, |p| phases.push(p), || true)
            .expect("a cache hit ignores cancel");
        assert_eq!(got, dir.join("test.bin"));
        assert!(
            dir.join("test.bin").exists(),
            "the cached file survives a cancel after Ready"
        );
        assert_eq!(phases, vec![DownloadPhase::Ready]);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn transport_errors_classify_dns_as_offline_and_the_rest_of_the_network_as_connect() {
        // Deterministic (no socket): DNS failure ⇒ Offline (nothing to connect to); other
        // transport/HTTP errors ⇒ Connect ("Couldn't connect"); a malformed URL/scheme is a config
        // bug ⇒ Other.
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::Dns),
            FailReason::Offline
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::ConnectionFailed),
            FailReason::Connect
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::HTTP),
            FailReason::Connect
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::Io),
            FailReason::Connect
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::TooManyRedirects),
            FailReason::Connect
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::InvalidUrl),
            FailReason::Other
        );
        assert_eq!(
            fail_reason_for_kind(ureq::ErrorKind::UnknownScheme),
            FailReason::Other
        );
    }
}
