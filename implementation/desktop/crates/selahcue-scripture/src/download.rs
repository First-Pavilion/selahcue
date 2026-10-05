//! Download-on-demand for Bible-translation assets (feature `download`).
//!
//! Two layers share one transport:
//!
//! - [`download_and_install`] is the product call. Given a registry, a catalogue code and a
//!   [`TermsAcceptance`] (which the caller must construct, so the function cannot be called without
//!   one), it fetches the catalogue's file over HTTPS and hands the bytes to the registry's install
//!   pipeline, which checks the pinned SHA-256, validates the file's shape and only then installs
//!   it (see [`crate::registry`]). It refuses, **before any request is made**, an unknown code, a
//!   translation still pending legal review, an acceptance for a different licence, and an entry
//!   with no published base URL ("not published yet"). An install that is already there and intact
//!   needs no network at all.
//! - [`fetch_translation`] is the low-level verified fetch it grew out of: a pinned URL and digest
//!   into a directory, with the same transport rules. It records no consent and installs nothing
//!   in a registry; product code uses [`download_and_install`].
//!
//! The transport rules (both layers):
//!
//! - **HTTPS only**, for the first request and for every redirect hop ([`crate::url_policy`]).
//!   Redirects are followed by hand, at most [`MAX_REDIRECTS`], so each hop is checked before it is
//!   requested. Plain http to a loopback address exists for tests, behind an explicit constructor.
//! - **Size-capped**: a correct download is exactly the pinned `size_bytes`, so the stream is cut off
//!   there (a hostile mirror's never-ending stream cannot fill the disk; the digest check only runs
//!   after EOF). The hard backstop [`DL_MAX_BYTES`] applies when no size is pinned.
//! - **Time-bounded**: connect and response-header timeouts, and a whole-body deadline sized from
//!   the cap at a minimum rate ([`body_deadline`]), so a stalled or trickling connection ends.
//! - **Streamed** in [`DL_CHUNK_BYTES`] chunks into a `.part` file that is created exclusively and
//!   removed on any failure, then verified and atomically renamed. Never held whole in memory.
//! - **No proxy, no compression**: the request carries no proxy and asks for `identity` encoding,
//!   because the asset is already a `.gz` and a server wrapping it again would break its digest.
//!
//! Offline-first: nothing here runs unless the caller invokes it on an explicit action; a network
//! failure is a plain `Err`, never a panic.

use std::fs::{self, File};
use std::io::{BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::time::Duration;

use sha2::{Digest, Sha256};

use crate::catalog::{validate_plain_name, LegalReview};
use crate::digest::hex_lower;
use crate::registry::{
    create_exclusive, Created, InstallError, InstallHooks, InstalledTranslation, Progress, Registry,
};
use crate::url_policy::{resolve_redirect, UrlPolicy, UrlRefusal};

/// Bytes read per hash chunk. Bounds the memory used while hashing a large asset file — a
/// multi-MB (or larger) translation never sits whole in memory to be hashed.
pub const HASH_CHUNK_BYTES: usize = 64 * 1024;

/// Bytes streamed per read/write while downloading (bounds transient download memory).
pub const DL_CHUNK_BYTES: usize = 64 * 1024;

/// Hard ceiling on a single translation download when the pinned `size_bytes` is unknown (`0`):
/// a backstop so an unbounded/never-ending stream cannot fill the disk. A real pinned asset caps
/// at its EXACT `size_bytes` instead (a correct download is exactly that many bytes, since the
/// bytes must match the pinned SHA-256); this ceiling only applies when no size is pinned.
pub const DL_MAX_BYTES: u64 = 256 * 1024 * 1024;

/// The most redirect hops that are followed. A real mirror redirects once; a loop must end.
pub const MAX_REDIRECTS: usize = 5;

/// Timeouts for a translation download: a stalled connection or a trickling stream must not hang
/// the fetch indefinitely (paired with the size cap, which bounds a fast, endless stream that
/// never stalls).
///
/// ureq 3 has no per-read timeout (ureq 2's `timeout_read` reset on every read, so it caught a
/// stall but never a slow trickle). It bounds the response *headers* (`DL_READ_TIMEOUT`) and the
/// *whole body* instead; [`body_deadline`] sizes the latter from the expected size, which also
/// closes the trickle case ureq 2 left open.
const DL_CONNECT_TIMEOUT: Duration = Duration::from_secs(15);
const DL_READ_TIMEOUT: Duration = Duration::from_secs(30);

/// The slowest sustained rate a download is allowed to average before it is abandoned (32 KiB/s,
/// about 256 kbit/s). Generous on purpose: this is a floor for "something is wrong", not a target.
const DL_MIN_BYTES_PER_SEC: u64 = 32 * 1024;

/// The longest the response *body* of a download capped at `max_bytes` may take: the time the
/// whole cap needs at [`DL_MIN_BYTES_PER_SEC`], and never less than [`DL_READ_TIMEOUT`].
fn body_deadline(max_bytes: u64) -> Duration {
    Duration::from_secs((max_bytes / DL_MIN_BYTES_PER_SEC).max(DL_READ_TIMEOUT.as_secs()))
}

// =============================================================================================
// The transport shared by both layers
// =============================================================================================

/// Why a request could not be opened.
enum OpenError {
    Insecure(UrlRefusal),
    Network(String),
}

impl From<OpenError> for TranslationFetchError {
    fn from(e: OpenError) -> Self {
        match e {
            OpenError::Insecure(r) => TranslationFetchError::Insecure(r),
            OpenError::Network(m) => TranslationFetchError::Network(m),
        }
    }
}

impl From<OpenError> for DownloadError {
    fn from(e: OpenError) -> Self {
        match e {
            OpenError::Insecure(r) => DownloadError::Insecure(r),
            OpenError::Network(m) => DownloadError::Network(m),
        }
    }
}

/// An open response body and the length the server declared for it, if any.
struct Stream {
    reader: ureq::BodyReader<'static>,
    content_length: Option<u64>,
}

fn agent(policy: UrlPolicy, max_bytes: u64) -> ureq::Agent {
    ureq::Agent::config_builder()
        .timeout_connect(Some(DL_CONNECT_TIMEOUT))
        .timeout_recv_response(Some(DL_READ_TIMEOUT))
        .timeout_recv_body(Some(body_deadline(max_bytes)))
        // ureq 3 reads HTTP(S)_PROXY from the environment by default; ureq 2 never did. Keep
        // the download's network path exactly what it was — routing it through a proxy is a
        // product decision, not a side effect of a dependency bump. (The SHA-256 pin means a
        // proxy could not alter the bytes anyway.)
        .proxy(None)
        // The belt to `UrlPolicy::check`'s braces: the client itself refuses plain http, unless
        // the (tests-only) loopback policy is in force.
        .https_only(!policy.allows_loopback_http())
        // Redirects are followed by hand below so that every hop is run through the policy
        // BEFORE it is requested.
        .max_redirects(0)
        // The asset is already a `.gz`; ask for it as it is.
        .accept_encoding("identity")
        .build()
        .into()
}

/// Open `url` (following at most [`MAX_REDIRECTS`] redirects, each checked against `policy`) and
/// return the response body of the first 2xx answer.
fn open_stream(url: &str, policy: UrlPolicy, max_bytes: u64) -> Result<Stream, OpenError> {
    let agent = agent(policy, max_bytes);
    let mut current = url.to_string();
    for _hop in 0..=MAX_REDIRECTS {
        policy.check(&current).map_err(OpenError::Insecure)?;
        let resp = agent
            .get(&current)
            .call()
            .map_err(|e| OpenError::Network(format!("download {current}: {e}")))?;
        let status = resp.status().as_u16();
        if matches!(status, 301 | 302 | 303 | 307 | 308) {
            let location = resp
                .headers()
                .get("Location")
                .and_then(|v| v.to_str().ok())
                .ok_or_else(|| {
                    OpenError::Network(format!("download {current}: redirect without a Location"))
                })?;
            current = resolve_redirect(&current, location).ok_or_else(|| {
                OpenError::Network(format!(
                    "download {current}: unsupported redirect to '{location}'"
                ))
            })?;
            continue;
        }
        if !(200..300).contains(&status) {
            return Err(OpenError::Network(format!(
                "download {current}: unexpected HTTP status {status}"
            )));
        }
        let content_length = resp
            .headers()
            .get("Content-Length")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| s.parse().ok());
        return Ok(Stream {
            reader: resp.into_body().into_reader(),
            content_length,
        });
    }
    Err(OpenError::Network(format!(
        "download {url}: more than {MAX_REDIRECTS} redirects"
    )))
}

// =============================================================================================
// The low-level verified fetch
// =============================================================================================

/// A pinned, downloadable Bible-translation asset: a stable id, a display name, the cache
/// file name, the source URL, the expected size, and the pinned lowercase-hex SHA-256 the
/// downloaded bytes must match. The URL and the digest travel together — the supply-chain pin.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranslationAsset {
    /// Stable identifier for this asset (e.g. a translation short code, lowercase).
    pub id: String,
    /// Human-readable name for attribution/UI.
    pub name: String,
    /// File name under the cache directory once installed. Must be a plain name (see
    /// [`crate::catalog::validate_plain_name`]): a path component is refused before anything is
    /// created.
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
    /// The URL (the first, or a redirect's) is not allowed: not https.
    Insecure(UrlRefusal),
    /// The asset's `file_name` is not a plain name.
    BadFileName(&'static str),
    /// The stream exceeded its size ceiling (the pinned `size_bytes`, or the hard backstop) before
    /// the integrity gate — the transfer was aborted and the partial file discarded, so an
    /// oversized/never-ending stream can never fill the disk.
    TooLarge { limit: u64 },
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
            TranslationFetchError::Insecure(r) => write!(f, "translation download refused: {r}"),
            TranslationFetchError::BadFileName(why) => {
                write!(f, "translation file name is not a plain name: {why}")
            }
            TranslationFetchError::TooLarge { limit } => {
                write!(
                    f,
                    "translation download exceeded the {limit}-byte size limit"
                )
            }
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

/// The default per-user cache directory for downloaded translation assets fetched with
/// [`fetch_translation`]. Honours `SELAHCUE_SCRIPTURE_CACHE`, then the platform cache convention,
/// ending in `selahcue/translations` — deliberately distinct from the STT model cache
/// (`selahcue/models`). **Installed translations do not live here**: a cache may be purged by the
/// OS, so they go in the data directory ([`crate::registry::default_data_dir`]).
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

/// Stream `reader` into `file`, writing at most `max_bytes` before aborting with
/// [`TranslationFetchError::TooLarge`] — so an oversized/never-ending stream can't fill the disk
/// (the integrity gate only runs after EOF). Reads/writes in bounded [`DL_CHUNK_BYTES`] chunks and
/// reports progress as `(bytes_written, total)`. Never loads the whole file into memory.
fn stream_capped<R: Read>(
    reader: &mut R,
    file: &mut File,
    max_bytes: u64,
    total: u64,
    progress: &dyn Fn(u64, u64),
) -> Result<(), TranslationFetchError> {
    let mut buf = [0u8; DL_CHUNK_BYTES];
    let mut done: u64 = 0;
    loop {
        let n = reader
            .read(&mut buf)
            .map_err(|e| TranslationFetchError::Network(format!("read stream: {e}")))?;
        if n == 0 {
            break;
        }
        if done.saturating_add(n as u64) > max_bytes {
            return Err(TranslationFetchError::TooLarge { limit: max_bytes });
        }
        file.write_all(&buf[..n])
            .map_err(TranslationFetchError::Io)?;
        done = done.saturating_add(n as u64);
        progress(done, total);
    }
    file.flush().map_err(TranslationFetchError::Io)?;
    Ok(())
}

/// Resolve `asset` to a verified local translation file under `cache_dir` (https only).
/// See [`fetch_translation_with`].
pub fn fetch_translation(
    asset: &TranslationAsset,
    cache_dir: &Path,
    progress: impl Fn(u64, u64),
) -> Result<PathBuf, TranslationFetchError> {
    fetch_translation_with(asset, cache_dir, UrlPolicy::https_only(), progress)
}

/// Resolve `asset` to a verified local translation file under `cache_dir`, under `policy`.
///
/// - **Cache hit**: if the file already exists as a regular file and its SHA-256 matches the pin,
///   return it — no network is touched.
/// - **Miss**: stream the download to a `.part` temp file (invoking `progress(done, total)`),
///   verify the pinned SHA-256, then atomically rename it into place. The temp file is created
///   exclusively (a planted file or symlink there is never followed; the next free name is used).
///   On any integrity failure the temp file is removed and an error returned — a bad file is never
///   installed.
///
/// Only tests pass a policy other than [`UrlPolicy::https_only`].
pub fn fetch_translation_with(
    asset: &TranslationAsset,
    cache_dir: &Path,
    policy: UrlPolicy,
    progress: impl Fn(u64, u64),
) -> Result<PathBuf, TranslationFetchError> {
    validate_plain_name(&asset.file_name).map_err(TranslationFetchError::BadFileName)?;
    let target = cache_dir.join(&asset.file_name);
    let is_regular_file = fs::symlink_metadata(&target).is_ok_and(|m| m.file_type().is_file());
    if is_regular_file && verify_file(&target, &asset.sha256).is_ok() {
        return Ok(target);
    }
    policy
        .check(&asset.url)
        .map_err(TranslationFetchError::Insecure)?;
    fs::create_dir_all(cache_dir).map_err(TranslationFetchError::Io)?;

    // Bounded transfer: a correct download is EXACTLY `size_bytes` (it must match the pinned
    // SHA-256), so cap there when it is known; otherwise fall back to the hard backstop. This
    // rejects a hostile/compromised mirror's oversized or never-ending stream BEFORE it can fill
    // the disk — the SHA-256 gate only runs after EOF — and the connect/read timeouts bound a
    // stalled or trickling connection.
    let max_bytes = if asset.size_bytes > 0 {
        asset.size_bytes
    } else {
        DL_MAX_BYTES
    };
    let mut stream = open_stream(&asset.url, policy, max_bytes)?;
    let total = stream.content_length.unwrap_or(asset.size_bytes);

    // Stream to the `.part` file, capping the total. ANY error here (network, I/O, or over-cap)
    // discards the partial file, so a failed download never orphans bytes on disk.
    let (tmp_path, mut file) = create_exclusive(cache_dir, &asset.file_name, ".part")
        .map_err(TranslationFetchError::Io)?;
    let mut tmp = Created::new(tmp_path);
    stream_capped(&mut stream.reader, &mut file, max_bytes, total, &progress)?;
    drop(file);

    // Integrity gate: the downloaded bytes must match the pinned SHA-256.
    verify_file(&tmp.path, &asset.sha256)?;
    fs::rename(&tmp.path, &target).map_err(TranslationFetchError::Io)?;
    tmp.disarm();
    Ok(target)
}

// =============================================================================================
// The product call
// =============================================================================================

/// A record that the user accepted a licence's terms. [`download_and_install`] takes one, so the
/// call cannot be made without it. This crate does not store or check the acceptance beyond its
/// licence id: recording it durably is the operator's job (ticket A3), and it constructs this value
/// from that record.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TermsAcceptance {
    licence_id: String,
    terms_version: String,
    accepted_at: u64,
}

/// Why a [`TermsAcceptance`] could not be built.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TermsError {
    /// The licence id or the terms version is empty (or only spaces).
    Empty,
    /// Longer than 64 characters.
    TooLong,
    /// Contains a control character.
    BadCharacter,
}

impl std::fmt::Display for TermsError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TermsError::Empty => write!(f, "the licence id and terms version must not be empty"),
            TermsError::TooLong => write!(f, "the licence id or terms version is too long"),
            TermsError::BadCharacter => {
                write!(f, "the licence id or terms version has a control character")
            }
        }
    }
}

impl std::error::Error for TermsError {}

impl TermsAcceptance {
    /// An acceptance of licence `licence_id` (the catalogue's `licence.id`, e.g. `"cc0"`), at
    /// version `terms_version` of the terms text, at `accepted_at` (the caller's clock).
    pub fn new(
        licence_id: &str,
        terms_version: &str,
        accepted_at: u64,
    ) -> Result<TermsAcceptance, TermsError> {
        let (licence_id, terms_version) = (licence_id.trim(), terms_version.trim());
        if licence_id.is_empty() || terms_version.is_empty() {
            return Err(TermsError::Empty);
        }
        for s in [licence_id, terms_version] {
            if s.chars().count() > 64 {
                return Err(TermsError::TooLong);
            }
            if s.chars().any(char::is_control) {
                return Err(TermsError::BadCharacter);
            }
        }
        Ok(TermsAcceptance {
            licence_id: licence_id.to_string(),
            terms_version: terms_version.to_string(),
            accepted_at,
        })
    }

    pub fn licence_id(&self) -> &str {
        &self.licence_id
    }

    pub fn terms_version(&self) -> &str {
        &self.terms_version
    }

    pub fn accepted_at(&self) -> u64 {
        self.accepted_at
    }
}

/// How a [`download_and_install`] call behaves: a progress report, a cancel flag, and (tests only)
/// two overrides. [`DownloadOptions::new`] is the product configuration.
#[derive(Default)]
pub struct DownloadOptions<'a> {
    policy: UrlPolicy,
    allow_pending: bool,
    hooks: InstallHooks<'a>,
}

impl<'a> DownloadOptions<'a> {
    /// The product configuration: https only, a pending entry refused, no hooks.
    pub fn new() -> DownloadOptions<'a> {
        DownloadOptions::default()
    }

    /// Stop, cleanly, when `flag` becomes true. See [`InstallHooks::with_cancel`].
    pub fn with_cancel(mut self, flag: &'a AtomicBool) -> Self {
        self.hooks = std::mem::take(&mut self.hooks).with_cancel(flag);
        self
    }

    /// Call `report` as the download advances (Downloading, then Verifying, then Installing).
    pub fn with_progress(mut self, report: &'a dyn Fn(Progress)) -> Self {
        self.hooks = std::mem::take(&mut self.hooks).with_progress(report);
        self
    }

    /// **Tests only.** Allow plain http to a loopback address. Exists only when debug assertions
    /// are on, like [`UrlPolicy::allow_loopback_http_for_tests`].
    #[cfg(debug_assertions)]
    #[doc(hidden)]
    pub fn allow_loopback_http_for_tests(mut self) -> Self {
        self.policy = UrlPolicy::allow_loopback_http_for_tests();
        self
    }

    /// **Tests only.** Let a download proceed for an entry still pending legal review. Exists only
    /// when debug assertions are on: a release build cannot download a pending translation.
    #[cfg(debug_assertions)]
    #[doc(hidden)]
    pub fn allow_legal_pending_for_tests(mut self) -> Self {
        self.allow_pending = true;
        self
    }

    #[doc(hidden)]
    pub fn url_policy(&self) -> UrlPolicy {
        self.policy
    }

    #[doc(hidden)]
    pub fn allows_pending_for_tests(&self) -> bool {
        self.allow_pending
    }
}

/// Why [`download_and_install`] did not install anything.
#[derive(Debug)]
pub enum DownloadError {
    /// The catalogue has no such code.
    UnknownCode { code: String },
    /// The catalogue has no base URL yet: "not published yet". No request was made.
    NotPublished,
    /// The translation has not cleared legal review. No request was made.
    LegalReviewPending { code: String },
    /// The acceptance is for a different licence than the translation's. No request was made.
    TermsMismatch { expected: String, accepted: String },
    /// A URL (the first, or a redirect's) is not https.
    Insecure(UrlRefusal),
    /// The server could not be reached or answered badly, or the stream broke.
    Network(String),
    /// The install pipeline refused it: cancelled, too large, wrong digest, not a valid
    /// translation, or a disk error. Nothing was installed.
    Install(InstallError),
}

impl DownloadError {
    /// Whether the caller's cancel flag stopped the download.
    pub fn is_cancelled(&self) -> bool {
        matches!(self, DownloadError::Install(InstallError::Cancelled))
    }
}

impl std::fmt::Display for DownloadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DownloadError::UnknownCode { code } => write!(f, "'{code}' is not in the catalogue"),
            DownloadError::NotPublished => write!(f, "not published yet"),
            DownloadError::LegalReviewPending { code } => {
                write!(f, "{code} has not cleared legal review yet")
            }
            DownloadError::TermsMismatch { expected, accepted } => write!(
                f,
                "the accepted terms are for '{accepted}', but this translation is under '{expected}'"
            ),
            DownloadError::Insecure(r) => write!(f, "download refused: {r}"),
            DownloadError::Network(m) => write!(f, "{m}"),
            DownloadError::Install(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for DownloadError {}

impl From<InstallError> for DownloadError {
    fn from(e: InstallError) -> Self {
        match e {
            // A read that failed while receiving is the network's failure.
            InstallError::Source(io) => DownloadError::Network(format!("read stream: {io}")),
            other => DownloadError::Install(other),
        }
    }
}

/// Download catalogued translation `code` and install it into `registry`.
///
/// In order, and each refusal before any request is made: the code must be in the registry's
/// catalogue; the entry must have cleared legal review (unless a test override is set); `accepted`
/// must be an acceptance of the entry's licence; the catalogue must have a base URL ("not published
/// yet" otherwise); the URL must pass the policy; the caller's cancel flag must not be set. If the
/// same file (same digest) is already installed and intact, it is returned with no network at all.
/// Otherwise the file is fetched (capped at the pinned size) and installed by
/// [`Registry::install_from_reader`], which checks the digest, validates the file and only then
/// installs it, replacing any earlier install of the code. `installed_at` is the caller's clock.
pub fn download_and_install(
    registry: &Registry,
    code: &str,
    accepted: &TermsAcceptance,
    installed_at: u64,
    options: &DownloadOptions<'_>,
) -> Result<InstalledTranslation, DownloadError> {
    let catalogue = registry.catalogue();
    let entry = catalogue
        .find(code)
        .ok_or_else(|| DownloadError::UnknownCode {
            code: code.to_string(),
        })?;
    if entry.legal_review != LegalReview::Cleared && !options.allow_pending {
        return Err(DownloadError::LegalReviewPending {
            code: entry.code.to_string(),
        });
    }
    if accepted.licence_id() != entry.licence.id {
        return Err(DownloadError::TermsMismatch {
            expected: entry.licence.id.clone(),
            accepted: accepted.licence_id().to_string(),
        });
    }
    let url = catalogue
        .download_url(entry)
        .map_err(|_| DownloadError::NotPublished)?;
    // (The URL is checked against the policy by `open_stream`, for the first request and for every
    // redirect hop, immediately before each is made. Not here as well: a second check ahead of the
    // cache-hit shortcut below would only make an intact install depend on the URL's scheme.)
    options.hooks.check_cancel()?;

    // Already installed, same file, and the file on disk still hashes to it: nothing to fetch.
    if let Some(installed) = registry.installed_entry(&entry.code) {
        if installed.sha256 == entry.sha256 && registry.verify(&entry.code).is_ok() {
            return Ok(installed);
        }
    }

    let mut stream = open_stream(&url, options.policy, entry.size_bytes)?;
    registry
        .install_from_reader(code, &mut stream.reader, installed_at, &options.hooks)
        .map_err(|e| match DownloadError::from(e) {
            DownloadError::Network(m) => DownloadError::Network(format!("download {url}: {m}")),
            other => other,
        })
}
