//! Download-on-demand for additional Bible-translation assets (feature `download`).
//!
//! Additive, feature-gated supply-chain infra that mirrors `selahcue-stt`'s whisper-model
//! download discipline (`model_fetch.rs` / `model.rs`): a pinned [`TranslationAsset`] is
//! resolved to a verified local file. A **cache hit** returns the already-present,
//! SHA-256-matching file with no network; otherwise the asset is downloaded (streaming, in
//! bounded chunks), its pinned SHA-256 is verified, and only on success is it atomically
//! installed into the cache. On any integrity failure the bad bytes are discarded and an
//! error is returned — a corrupted or substituted file is never installed.
//!
//! Offline-first: nothing here runs unless the caller invokes it on an explicit action; a
//! network failure is a plain `Err`, never a panic; a cached asset needs no network. The
//! source URL and the pinned digest travel together in the [`TranslationAsset`], so a
//! substituted download is rejected before it is ever used.
//!
//! **Scope boundary:** this exposes only the verified file PATH. Downloaded translations are
//! deliberately NOT wired into the compiled `Translation` enum, the per-translation
//! quote-match index, or the cross-language-pinned LAN wire protocol; that runtime
//! integration is designed separately.

use std::fs::{self, File};
use std::io::{BufReader, Read, Write};
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

/// Bytes read per hash chunk. Bounds the memory used while hashing a large asset file — a
/// multi-MB (or larger) translation never sits whole in memory to be hashed.
pub const HASH_CHUNK_BYTES: usize = 64 * 1024;

/// Bytes streamed per read/write while downloading (bounds transient download memory).
pub const DL_CHUNK_BYTES: usize = 64 * 1024;

/// A pinned, downloadable Bible-translation asset: a stable id, a display name, the cache
/// file name, the source URL, the expected size, and the pinned lowercase-hex SHA-256 the
/// downloaded bytes must match. The URL and the digest travel together — the supply-chain pin.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranslationAsset {
    /// Stable identifier for this asset (e.g. a translation short code, lowercase).
    pub id: String,
    /// Human-readable name for attribution/UI.
    pub name: String,
    /// File name under the cache directory once installed.
    pub file_name: String,
    /// Full source URL to download from.
    pub url: String,
    /// Expected size in bytes (used as a progress fallback when no Content-Length is sent).
    pub size_bytes: u64,
    /// Lowercase-hex SHA-256 (64 chars) the downloaded file must match.
    pub sha256: String,
}

/// Why fetching a translation asset failed. A failure never installs a file.
#[derive(Debug)]
pub enum TranslationFetchError {
    /// The download itself failed (unreachable host, HTTP error, stream read error, …).
    Network(String),
    /// The pinned expected hash is not valid lowercase-hex SHA-256 (64 hex chars).
    BadExpectedHash,
    /// The downloaded bytes' SHA-256 did not match the pinned digest — the file was discarded.
    Verify { expected: String, actual: String },
    /// A filesystem error (create cache dir, write temp, install).
    Io(std::io::Error),
}

impl std::fmt::Display for TranslationFetchError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TranslationFetchError::Network(e) => write!(f, "translation download failed: {e}"),
            TranslationFetchError::BadExpectedHash => {
                write!(f, "pinned translation hash is not a 64-char hex SHA-256")
            }
            TranslationFetchError::Verify { expected, actual } => write!(
                f,
                "translation integrity check failed: expected {expected}, got {actual}"
            ),
            TranslationFetchError::Io(e) => write!(f, "translation I/O error: {e}"),
        }
    }
}

impl std::error::Error for TranslationFetchError {}

/// On-disk cache file name for the downloadable Young's Literal Translation index. The runtime
/// verse loader ([`crate::is_available`] / the `Translation::Ylt` lookup path) reads
/// [`default_cache_dir`]`().join(YLT_FILE_NAME)`, and the [`catalog`] entry installs to the
/// same name — so a fetched asset is found by the loader. The file is a gzipped
/// `book<TAB>chapter<TAB>verse<TAB>text` TSV (canonical book numbers 1–66), the SAME format as
/// the bundled `assets/*.tsv.gz`.
pub const YLT_FILE_NAME: &str = "ylt.tsv.gz";

// ---------------------------------------------------------------------------------------------
// OWNER-SUPPLIED PLACEHOLDERS for the YLT download pin.
//
// Young's Literal Translation (1898) is public domain, but SelahCue does not ship its text or
// invent a download source. The URL, the pinned SHA-256, and the byte size below are PLACEHOLDERS
// the owner MUST replace (same custody model as the NDI SDK) before YLT can actually be fetched:
//   * `YLT_URL_PLACEHOLDER`    -> the real owner-hosted URL of the gzipped verse-index asset
//   * `YLT_SHA256_PLACEHOLDER` -> the real lowercase-hex SHA-256 of that exact asset
//   * `YLT_SIZE_PLACEHOLDER`   -> the real byte size of that asset
// They are shaped as a well-formed pin (https URL, 64-char lowercase hex, positive size) so the
// catalog seam stays testable, but they are NOT a real, downloadable source.
// ---------------------------------------------------------------------------------------------
const YLT_URL_PLACEHOLDER: &str = "https://OWNER-SUPPLIED.invalid/selahcue/ylt.tsv.gz";
const YLT_SHA256_PLACEHOLDER: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";
const YLT_SIZE_PLACEHOLDER: u64 = 1;

/// The catalog of downloadable translations.
///
/// Holds the **Young's Literal Translation (1898)** exemplar as a downloadable pin. Its source
/// URL and pinned SHA-256 are OWNER-SUPPLIED PLACEHOLDERS (see the constants above) — the same
/// owner-custody model this repo uses for the NDI SDK. The mechanism is exercised with a
/// synthetic local fixture in the tests, never the network; the owner replaces the placeholders
/// with a real mirror + digest to make YLT actually fetchable.
pub fn catalog() -> Vec<TranslationAsset> {
    vec![TranslationAsset {
        id: "ylt".into(),
        name: "Young's Literal Translation (1898)".into(),
        file_name: YLT_FILE_NAME.into(),
        url: YLT_URL_PLACEHOLDER.into(),
        size_bytes: YLT_SIZE_PLACEHOLDER,
        sha256: YLT_SHA256_PLACEHOLDER.into(),
    }]
}

/// The default per-user cache directory for downloaded translation assets. Honours
/// `SELAHCUE_SCRIPTURE_CACHE`, then the platform cache convention, ending in
/// `selahcue/translations` — deliberately distinct from the STT model cache
/// (`selahcue/models`).
pub fn default_cache_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("SELAHCUE_SCRIPTURE_CACHE") {
        return PathBuf::from(dir);
    }
    cache_root().join("selahcue").join("translations")
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

/// Compute the lowercase-hex SHA-256 of the file at `path`, reading in bounded chunks so a
/// large file is never loaded whole into memory.
pub fn sha256_file(path: &Path) -> Result<String, TranslationFetchError> {
    let file = File::open(path).map_err(TranslationFetchError::Io)?;
    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buf = [0u8; HASH_CHUNK_BYTES];
    loop {
        let n = reader.read(&mut buf).map_err(TranslationFetchError::Io)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex_lower(&hasher.finalize()))
}

/// Verify the file at `path` against `expected_sha256` (64-char lowercase-hex). Returns the
/// verified digest on success; a malformed pin or a mismatch is an error (never accepted).
fn verify_file(path: &Path, expected_sha256: &str) -> Result<String, TranslationFetchError> {
    let expected = expected_sha256.trim().to_ascii_lowercase();
    if expected.len() != 64 || !expected.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(TranslationFetchError::BadExpectedHash);
    }
    let actual = sha256_file(path)?;
    if actual == expected {
        Ok(actual)
    } else {
        Err(TranslationFetchError::Verify { expected, actual })
    }
}

/// Resolve `asset` to a verified local translation file under `cache_dir`.
///
/// - **Cache hit**: if the file already exists and its SHA-256 matches the pin, return it —
///   no network is touched.
/// - **Miss**: stream the download to a `.part` temp file (invoking `progress(done, total)`),
///   verify the pinned SHA-256, then atomically rename it into place. On any integrity
///   failure the temp file is removed and an error returned — a bad file is never installed.
pub fn fetch_translation(
    asset: &TranslationAsset,
    cache_dir: &Path,
    progress: impl Fn(u64, u64),
) -> Result<PathBuf, TranslationFetchError> {
    let target = cache_dir.join(&asset.file_name);
    if target.exists() && verify_file(&target, &asset.sha256).is_ok() {
        return Ok(target);
    }
    fs::create_dir_all(cache_dir).map_err(TranslationFetchError::Io)?;

    let tmp = cache_dir.join(format!("{}.part", asset.file_name));
    let resp = ureq::get(&asset.url)
        .call()
        .map_err(|e| TranslationFetchError::Network(format!("download {}: {e}", asset.url)))?;
    let total: u64 = resp
        .header("Content-Length")
        .and_then(|s| s.parse().ok())
        .unwrap_or(asset.size_bytes);

    let mut reader = resp.into_reader();
    {
        let mut file = File::create(&tmp).map_err(TranslationFetchError::Io)?;
        let mut buf = [0u8; DL_CHUNK_BYTES];
        let mut done: u64 = 0;
        loop {
            let n = reader
                .read(&mut buf)
                .map_err(|e| TranslationFetchError::Network(format!("read stream: {e}")))?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])
                .map_err(TranslationFetchError::Io)?;
            done = done.saturating_add(n as u64);
            progress(done, total);
        }
        let _ = file.flush();
    }

    // Integrity gate: the downloaded bytes must match the pinned SHA-256.
    match verify_file(&tmp, &asset.sha256) {
        Ok(_) => {
            fs::rename(&tmp, &target).map_err(TranslationFetchError::Io)?;
            Ok(target)
        }
        Err(e) => {
            let _ = fs::remove_file(&tmp);
            Err(e)
        }
    }
}

/// Lowercase-hex encode a byte slice (no external hex dependency).
fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}
