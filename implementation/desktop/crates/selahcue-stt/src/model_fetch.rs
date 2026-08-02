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
    let target = cache_dir.join(asset.file_name);
    if target.exists() && verify_model(&target, asset.sha256).is_ok() {
        return Ok(target);
    }
    fs::create_dir_all(cache_dir).map_err(|e| format!("create cache dir {cache_dir:?}: {e}"))?;

    let tmp = cache_dir.join(format!("{}.part", asset.file_name));
    let url = asset.download_url();
    let resp = ureq::get(&url)
        .call()
        .map_err(|e| format!("download {url}: {e}"))?;
    let total: u64 = resp
        .header("Content-Length")
        .and_then(|s| s.parse().ok())
        .unwrap_or(asset.size_bytes);

    let mut reader = resp.into_reader();
    {
        let mut file = fs::File::create(&tmp).map_err(|e| format!("create {tmp:?}: {e}"))?;
        let mut buf = [0u8; DL_CHUNK_BYTES];
        let mut done: u64 = 0;
        loop {
            let n = reader
                .read(&mut buf)
                .map_err(|e| format!("read download stream: {e}"))?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])
                .map_err(|e| format!("write {tmp:?}: {e}"))?;
            done = done.saturating_add(n as u64);
            progress(done, total);
        }
        let _ = file.flush();
    }

    // Integrity gate (FR-156): the downloaded bytes must match the pinned SHA-256.
    match verify_model(&tmp, asset.sha256) {
        Ok(_) => {
            fs::rename(&tmp, &target).map_err(|e| format!("install model {target:?}: {e}"))?;
            Ok(target)
        }
        Err(e) => {
            let _ = fs::remove_file(&tmp);
            Err(format!("downloaded model failed the integrity check: {e}"))
        }
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
}
