//! Download-on-demand for catalogued Bible translations (feature `download`).
//!
//! [`download_and_install`] is the one entry point. Given a registry, a catalogue code and a
//! [`TermsAcceptance`] (which the caller must construct, so the function cannot be called without
//! one), it fetches the catalogue's file over HTTPS and hands the bytes to the registry's install
//! pipeline, which checks the pinned SHA-256, validates the file's shape and only then installs it
//! (see [`crate::registry`]). It refuses, **before any request is made**, an unknown code, a
//! translation still pending legal review, an acceptance for a different licence, and an entry with
//! no published base URL ("not published yet"). An install that is already there and intact needs
//! no network at all. There is no other download function: nothing here fetches an arbitrary URL.
//!
//! The transport rules:
//!
//! - **HTTPS only**, for the first request and for every redirect hop ([`crate::url_policy`]).
//!   Redirects are followed by hand, at most [`MAX_REDIRECTS`], so each hop is checked before it is
//!   requested. Plain http to a loopback address exists for tests, behind an explicit constructor
//!   that is compiled only with debug assertions.
//! - **Size-capped**: a correct download is exactly the pinned `size_bytes`, so the stream is cut off
//!   there (a hostile mirror's never-ending stream cannot fill the disk; the digest check only runs
//!   after EOF).
//! - **Time-bounded**: connect and response-header timeouts, and a whole-body deadline sized from
//!   the cap at a minimum rate ([`body_deadline`]), so a stalled or trickling connection ends.
//! - **Streamed** in bounded chunks into a staging file that is created exclusively and removed on
//!   any failure, then verified and atomically renamed. Never held whole in memory.
//! - **No proxy**: the request ignores `HTTP(S)_PROXY`. A network that forces a proxy cannot
//!   download until a decision is made (ClickUp A3).
//! - **Content encoding**: the request asks for `identity`. ureq's default `gzip` feature would
//!   still inflate a response labelled `Content-Encoding: gzip`, but the size cap and the digest
//!   run on the DECODED stream, so a response wrapped that way is safe: it is cut at the pinned size
//!   and must hash to the pinned digest like any other. (The asset itself is a `.gz`; a server that
//!   compresses it again and says so is simply undone before it is checked.)
//! - **No query strings in errors**: every error text that mentions a URL has its query string and
//!   fragment removed ([`crate::url_policy::redact_urls`]), because those errors end up in the UI,
//!   in events and in logs, and a CDN's signed redirect carries its secret there.
//!
//! Offline-first: nothing here runs unless the caller invokes it on an explicit action; a network
//! failure is a plain `Err`, never a panic.

use std::sync::atomic::AtomicBool;
use std::time::Duration;

use crate::catalog::LegalReview;
use crate::registry::{InstallError, InstallHooks, InstalledTranslation, Progress, Registry};
use crate::url_policy::{redact_urls, resolve_redirect, UrlPolicy, UrlRefusal};

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
// The transport
// =============================================================================================

/// An open response body.
struct Stream {
    reader: ureq::BodyReader<'static>,
}

fn agent(policy: UrlPolicy, max_bytes: u64) -> ureq::Agent {
    ureq::Agent::config_builder()
        .timeout_connect(Some(DL_CONNECT_TIMEOUT))
        .timeout_recv_response(Some(DL_READ_TIMEOUT))
        .timeout_recv_body(Some(body_deadline(max_bytes)))
        // ureq 3 reads HTTP(S)_PROXY from the environment by default; ureq 2 never did. Keep
        // the download's network path exactly what it was: routing it through a proxy is a
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
/// return the response body of the first 2xx answer. Every error text is redacted.
fn open_stream(url: &str, policy: UrlPolicy, max_bytes: u64) -> Result<Stream, DownloadError> {
    let network = |what: String| DownloadError::Network(redact_urls(&what));
    let agent = agent(policy, max_bytes);
    let mut current = url.to_string();
    for _hop in 0..=MAX_REDIRECTS {
        policy.check(&current).map_err(DownloadError::Insecure)?;
        let resp = agent
            .get(&current)
            .call()
            .map_err(|e| network(format!("download {current}: {e}")))?;
        let status = resp.status().as_u16();
        if matches!(status, 301 | 302 | 303 | 307 | 308) {
            let location = resp
                .headers()
                .get("Location")
                .and_then(|v| v.to_str().ok())
                .ok_or_else(|| {
                    network(format!("download {current}: redirect without a Location"))
                })?;
            current = resolve_redirect(&current, location).ok_or_else(|| {
                // `location` need not look like a URL (a relative reference has no `://`), so it
                // is cut at its query and fragment here, not left to `redact_urls`.
                let shown: String = location
                    .split(['?', '#'])
                    .next()
                    .unwrap_or_default()
                    .chars()
                    .take(200)
                    .collect();
                network(format!(
                    "download {current}: unsupported redirect to '{shown}'"
                ))
            })?;
            continue;
        }
        if !(200..300).contains(&status) {
            return Err(network(format!(
                "download {current}: unexpected HTTP status {status}"
            )));
        }
        return Ok(Stream {
            reader: resp.into_body().into_reader(),
        });
    }
    Err(network(format!(
        "download {url}: more than {MAX_REDIRECTS} redirects"
    )))
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

    /// Call `report` as the download advances (Downloading, then Verifying, then Installing). The
    /// report for the last phase is made while the registry's write lock is held, so `report` must
    /// not call back into the registry (see [`crate::registry::Phase::Installing`]): send it to
    /// another thread.
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
    /// The server could not be reached or answered badly, or the stream broke. The text never
    /// carries a URL's query string or fragment.
    Network(String),
    /// The install pipeline refused it: cancelled, too large, wrong digest, not a valid
    /// translation, an unreadable receipt, or a disk error. Nothing was installed.
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
            InstallError::Source(io) => {
                DownloadError::Network(redact_urls(&format!("read stream: {io}")))
            }
            other => DownloadError::Install(other),
        }
    }
}

/// A network failure while the caller's cancel flag is set is the cancel (a blocked read that
/// ended after Cancel was pressed), not a connection problem.
fn cancelled_or(e: DownloadError, hooks: &InstallHooks<'_>) -> DownloadError {
    if matches!(e, DownloadError::Network(_)) && hooks.is_cancelled() {
        DownloadError::Install(InstallError::Cancelled)
    } else {
        e
    }
}

/// Download catalogued translation `code` and install it into `registry`.
///
/// In order, and each refusal before any request is made: the code must be in the registry's
/// catalogue; the entry must have cleared legal review (unless a test override is set); `accepted`
/// must be an acceptance of the entry's licence; the catalogue must have a base URL ("not published
/// yet" otherwise); the caller's cancel flag must not be set; the install record must be readable
/// (see [`Registry::repair_receipt`]). If the same file (same digest) is
/// already installed and intact, it is returned with no network at all. Otherwise the file is
/// fetched: the URL, and every redirect hop, must pass the policy (https only) immediately before
/// it is requested, and the transfer is capped at the pinned size. It is installed by
/// [`Registry::install_from_reader`], which checks the digest, validates the file and only then
/// installs it, replacing any earlier install of the code. `installed_at` is the caller's clock.
/// If the caller cancels while a read is blocked, the result is `Cancelled` when that read ends,
/// not a network error.
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
    // An unreadable install record is refused BEFORE a request is made: the install would refuse
    // it too (it cannot tell what else is installed), so the download could only be thrown away.
    registry
        .installed()
        .map_err(|e| DownloadError::Install(InstallError::Receipt(e)))?;

    // Already installed, same file, and the file on disk still passes every check a load applies:
    // nothing to fetch.
    if let Some(installed) = registry.installed_entry(&entry.code) {
        if installed.sha256 == entry.sha256 && registry.verify(&entry.code).is_ok() {
            return Ok(installed);
        }
    }

    let mut stream = open_stream(&url, options.policy, entry.size_bytes)
        .map_err(|e| cancelled_or(e, &options.hooks))?;
    registry
        .install_from_reader(code, &mut stream.reader, installed_at, &options.hooks)
        .map_err(|e| match DownloadError::from(e) {
            DownloadError::Network(m) => {
                DownloadError::Network(redact_urls(&format!("download {url}: {m}")))
            }
            other => other,
        })
        .map_err(|e| cancelled_or(e, &options.hooks))
}

#[cfg(test)]
mod body_deadline_tests {
    use super::*;
    use crate::catalog::MAX_ASSET_BYTES;

    #[test]
    fn a_small_asset_still_gets_the_header_timeout_as_its_floor() {
        // A tiny pinned asset must never be cut off faster than the 30 s the old per-read timeout
        // allowed.
        assert_eq!(body_deadline(1), DL_READ_TIMEOUT);
        assert_eq!(body_deadline(0), DL_READ_TIMEOUT);
    }

    #[test]
    fn the_deadline_scales_with_the_cap_at_the_minimum_rate() {
        assert_eq!(body_deadline(5 * 1024 * 1024), Duration::from_secs(160));
        // The largest asset a catalogue may pin (16 MiB) allows 512 s: slow links finish, a stuck
        // trickle does not run forever.
        assert_eq!(body_deadline(MAX_ASSET_BYTES), Duration::from_secs(512));
    }
}
