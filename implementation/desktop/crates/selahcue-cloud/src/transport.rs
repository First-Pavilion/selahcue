//! The HTTP transport seam. The client depends on this trait, not on any concrete
//! network library, so tests inject a deterministic [`crate::mock::MockTransport`]
//! and the production build injects [`ReqwestTransport`] (behind the `http` feature).
//!
//! # Convention: an error branch lands with its no-echo assertion in the same commit
//!
//! Response bodies are attacker-influenced, and on at least one real provider a 401 body
//! contains a partially-masked copy of the API key that was sent. So no error raised anywhere in
//! this crate may quote a response body. That is a property of *every* branch, and it has now
//! been rediscovered three times in one review cycle, each time on a branch or fixture that
//! existed before its pin did:
//!
//! - status arms that had no captured fixture, so the sweep never reached them;
//! - a fixture that could drift until it no longer contained the markers asserted absent;
//! - a **newly added** branch — the timeout returns below — born unpinned.
//!
//! The rule that stops a fourth: **when you add an error branch, add its no-echo assertion in
//! the same commit.** Not in the same PR, not "when the file is next open" — the same commit,
//! because every instance so far is a gap that opened between writing the branch and getting
//! round to pinning it.

/// A minimal HTTP response: status code + raw body text.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

/// A transport-level failure (no HTTP response was obtained): DNS/TLS/connection/
/// timeout. Distinct from an HTTP error *status*, which arrives as an [`HttpResponse`]
/// with a non-2xx `status`. The message never contains request bodies or secrets.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransportError(pub String);

impl core::fmt::Display for TransportError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for TransportError {}

/// A blocking HTTP transport. Blocking (not async) keeps the seam simple and the core
/// deterministic; callers run it off any UI/render thread (the operator command is
/// `async` and offloads it). Implementations must not log request bodies or the bearer.
pub trait HttpTransport {
    /// POST a JSON `body` to `url`, optionally with a bearer token.
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError>;

    /// GET `url`, optionally with a bearer token.
    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError>;
}

/// The most response body the production transport will read off the socket.
///
/// **This is the bound that actually holds.** A cap applied after the body is in hand
/// bounds *parsing*, not memory: by then an unbounded read has already allocated
/// whatever the peer chose to send. `reqwest`'s `text()` reads to end-of-stream, so a
/// hostile or malfunctioning server could hand us gigabytes before any check ran.
/// Reading through `Read::take` refuses at the socket instead.
///
/// Set above the parse-side caps so the two do not collide: a body between the parse cap
/// and this one is still *read*, and then refused by the parser with a precise error,
/// which is a better diagnostic than a truncated read.
pub const MAX_TRANSPORT_RESPONSE_BYTES: usize = 4 * 1024 * 1024;

/// The production transport over `reqwest` 0.13 (blocking, rustls). Compiled only with
/// the `http` feature so the default workspace build/tests stay light and offline.
///
/// # TLS posture (owner decision 2026-10-24, DEC-019, ClickUp 17tnw2b9ax2)
///
/// - **Trust roots are the operating system's store**, through `rustls-platform-verifier`
///   (reqwest 0.13's own default). There is no bundled Mozilla root set in this client, so a
///   root the operating system trusts *for this user* is a root this client trusts. That
///   includes a TLS-inspecting (man-in-the-middle) root. Getting one in needs no administrator
///   rights: on macOS a standard user can mark a root "Always Trust" in their own login keychain
///   (user-domain trust settings), on Windows a user can add a root to the current-user store
///   (after a confirmation dialog), and on Linux and the BSDs `SSL_CERT_FILE` and `SSL_CERT_DIR`
///   REPLACE the system bundle for the process (rustls-native-certs 0.8.4, `lib.rs`
///   `load_native_certs`: when either is set it is used exclusively). The macOS and Windows
///   mechanisms are the platform's documented behaviour and were not exercised here. This is a
///   same-user vector, not a privilege escalation, and `tests/test_tls_system_store_linux.rs`
///   uses exactly the Linux mechanism.
/// - **`ring` is the only crypto provider.** reqwest's own `rustls` feature would add aws-lc-rs;
///   we use `rustls-no-provider` and install ring ourselves ([`ensure_crypto_provider`]). A client
///   built before a provider is installed panics, so every constructor goes through it.
/// - **A machine with no usable roots fails closed.** On Linux the verifier reads the CA bundle
///   through `rustls-native-certs`; when it finds none, building the client fails with
///   "No CA certificates were loaded from the system", and [`ReqwestTransport::new`] returns a
///   [`TransportError`] saying so. It never falls back to trusting everything, and the message
///   carries no request data. Run: on a macOS host and in a Debian bookworm arm64 container
///   (`tests/test_tls_system_store_linux.rs`). Not run: Windows and the ubuntu CI runner. macOS
///   and Windows use the system verifier APIs, which have no such load step. A consequence for
///   anyone running the tests on a Linux host with no CA bundle: every test that calls `new()`
///   fails, including the plaintext loopback ones, because `new()` itself errors by design.
/// - **Revocation is now checked, where the old bundled-roots client checked none.** Observed on
///   macOS: a revoked certificate is refused (cause "Revoked"); Linux accepted it. From the
///   verifier's source (`windows.rs`, around lines 461-469, not run): on Windows the end
///   certificate is checked online with a 10 s URL-retrieval budget and accepted if no answer
///   arrives. The checks send OCSP/CRL requests from the user's machine to the CA's responder
///   (no user data, but the CA learns which certificate is being checked) and are an extra source
///   of latency. Whether a network that silently drops port 80 pushes a handshake past
///   [`CONNECT_TIMEOUT_SECS`] is unverified.
/// - **Certificates are checked, not skipped**: an unknown signer, a wrong name and an expired
///   certificate are each refused before a single request byte is written. Pinned in
///   `transport/tls_tests.rs`.
#[cfg(feature = "http")]
pub struct ReqwestTransport {
    client: reqwest::blocking::Client,
}

/// Ceiling on the TCP/TLS connect phase alone.
///
/// A pure improvement with no trade-off: it can only make a failure *faster*, never abort
/// valid work, because no legitimate connect takes ten seconds. It exists so the common
/// case — an unreachable host, a church that has lost its uplink mid-service — reports in
/// ten seconds rather than sitting on the full request budget.
#[cfg(feature = "http")]
pub const CONNECT_TIMEOUT_SECS: u64 = 10;

/// Ceiling on the whole request: connect, send, and body read.
///
/// **Measured, not guessed.** Four live runs of a realistic 7,165-word sermon (a ~45-minute
/// service) through the shipped prompt took **15.3s, 16.5s, 16.8s and 17.3s**. Latency is
/// dominated by *output* length, which the schema bounds, rather than by transcript length —
/// so it does not grow with the sermon the way one would expect.
///
/// At 30s that was only ~1.7-2x headroom, and every one of those measurements came from a fast
/// connection to an unloaded API. 60s is chosen on the **asymmetry of the two failures**, not
/// on the numbers: crossing the cap costs a real church its notes on a slow day, while an
/// over-long cap costs only that a genuine hang reports in 60s instead of 30s. With
/// [`CONNECT_TIMEOUT_SECS`] at 10s the common unreachable case never approaches either.
///
/// This bound is real and is exercised: a peer that completes the handshake and then says
/// nothing, and a peer that sends headers and stalls before the body, were both measured
/// against stalling TCP servers and both fail at the deadline rather than hanging. The second
/// case matters most — the body read is a hand-rolled `Read::take(..).read_to_end(..)` in
/// [`read_capped`], not `reqwest`'s own `text()`, so that the client deadline still covers it
/// was worth measuring rather than assuming.
#[cfg(feature = "http")]
pub const REQUEST_TIMEOUT_SECS: u64 = 60;

/// How this process came to have a rustls crypto provider; see [`ensure_crypto_provider`].
#[cfg(feature = "http")]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CryptoProviderInstall {
    /// Nothing was installed, so this call installed `ring` as the process default.
    InstalledRing,
    /// A default provider was already installed by someone else (in this workspace only
    /// `selahcue-stt-cloud`'s Deepgram transport does that; `selahcue-lan` builds its configs with
    /// `builder_with_provider` and never installs a default). It is **kept, never replaced**, and
    /// not inspected: reqwest uses whichever default is installed. In this workspace that can only be `ring`, because
    /// `scripts/import_guards.sh` refuses any lock file that contains aws-lc.
    AlreadyInstalled,
}

/// Install `ring` as rustls' process-wide crypto provider, once, and say how it came about.
///
/// reqwest 0.13's `rustls-no-provider` feature builds no provider of its own and **panics at
/// `Client` construction** when none is installed, so every [`ReqwestTransport`] constructor
/// calls this first. It is idempotent and safe to call from any number of threads: the first
/// caller does the work, concurrent callers wait for it, and every caller gets the same answer
/// (the outcome of that first install, not a fresh probe). `install_default` returns `Err` when
/// a provider is already installed; that is success for our purposes and is reported as
/// [`CryptoProviderInstall::AlreadyInstalled`] rather than treated as a failure or, worse,
/// replaced.
#[cfg(feature = "http")]
pub fn ensure_crypto_provider() -> CryptoProviderInstall {
    static OUTCOME: std::sync::OnceLock<CryptoProviderInstall> = std::sync::OnceLock::new();
    *OUTCOME.get_or_init(
        || match rustls::crypto::ring::default_provider().install_default() {
            Ok(()) => CryptoProviderInstall::InstalledRing,
            Err(_already_installed) => CryptoProviderInstall::AlreadyInstalled,
        },
    )
}

/// How many causes of an error [`cause_chain`] will print. A rustls or hyper chain is two or
/// three deep; the bound only keeps a pathological chain from producing an unbounded message.
#[cfg(feature = "http")]
const MAX_CAUSES: usize = 8;

/// The causes of `e` (not `e` itself), each preceded by ": ", at most [`MAX_CAUSES`] of them.
///
/// reqwest's own `Display` stops at the top of the chain: a builder error reads only "builder
/// error" and a send error only "error sending request for url (...)", so an operator whose note
/// generation fails cannot tell "the certificate is for another name" from "the network is down".
/// The causes of a *builder* error come from TLS set-up and the causes of a *send* error from the
/// connection and the TLS handshake (for example "invalid peer certificate: UnknownIssuer" or
/// "Revoked"); none of them carries a request header, a request body or a credential (the bearer
/// is a header, and a header is not part of an error). The URL in the top-level text is as it
/// always was.
#[cfg(feature = "http")]
fn cause_chain(e: &(dyn std::error::Error + 'static)) -> String {
    let mut text = String::new();
    let mut cause = e.source();
    let mut shown = 0;
    while let Some(c) = cause {
        if shown == MAX_CAUSES {
            text.push_str(": ...");
            break;
        }
        text.push_str(": ");
        text.push_str(&c.to_string());
        cause = c.source();
        shown += 1;
    }
    text
}

/// The reason a client could not be built, from reqwest's error and its causes.
#[cfg(feature = "http")]
fn describe_build_error(e: &reqwest::Error) -> String {
    format!("could not set up TLS{}", cause_chain(e))
}

/// A failed send: reqwest's one-line text (with the URL, as before) plus the causes.
#[cfg(feature = "http")]
fn describe_send_error(e: &reqwest::Error) -> String {
    format!("{e}{}", cause_chain(e))
}

#[cfg(feature = "http")]
impl ReqwestTransport {
    /// A transport that is bounded at both the connect phase and the whole request, so a
    /// stalling peer always fails rather than hanging the caller. Trusts the operating
    /// system's certificate store and nothing else (see the type documentation).
    pub fn new() -> Result<Self, TransportError> {
        Self::build(&[])
    }

    /// The one place a production client is built. `extra_roots` is always empty in production;
    /// the TLS tests pass a throwaway CA so that "signed by a root we were given" can be exercised
    /// against the real client. The function is private and its only non-test caller is
    /// [`ReqwestTransport::new`] passing `&[]`, so no release code path can widen the trust set.
    fn build(extra_roots: &[reqwest::Certificate]) -> Result<Self, TransportError> {
        Self::from_builder(Self::shipped_builder(extra_roots))
    }

    /// The builder `build` uses: the shipped timeouts, [`CONNECT_TIMEOUT_SECS`] and
    /// [`REQUEST_TIMEOUT_SECS`], applied by [`ReqwestTransport::configured_builder`]. A separate
    /// function so a test can read back what `build` configures (the `Debug` text of a reqwest
    /// builder carries both timeouts) instead of trusting that the constants were passed on.
    fn shipped_builder(extra_roots: &[reqwest::Certificate]) -> reqwest::blocking::ClientBuilder {
        Self::configured_builder(
            extra_roots,
            std::time::Duration::from_secs(CONNECT_TIMEOUT_SECS),
            std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS),
        )
    }

    /// The client builder before `.build()`, with the two timeouts as arguments so a test can prove
    /// they take effect without waiting ten or sixty seconds.
    fn configured_builder(
        extra_roots: &[reqwest::Certificate],
        connect_timeout: std::time::Duration,
        timeout: std::time::Duration,
    ) -> reqwest::blocking::ClientBuilder {
        let mut builder = reqwest::blocking::Client::builder()
            .connect_timeout(connect_timeout)
            .timeout(timeout);
        if !extra_roots.is_empty() {
            builder = builder.tls_certs_merge(extra_roots.iter().cloned());
        }
        builder
    }

    /// Install the crypto provider, then build. Reqwest 0.13 with `rustls-no-provider` panics at
    /// this point if no provider is installed, so nothing builds a client without going through here.
    fn from_builder(builder: reqwest::blocking::ClientBuilder) -> Result<Self, TransportError> {
        ensure_crypto_provider();
        let client = builder
            .build()
            .map_err(|e| TransportError(describe_build_error(&e)))?;
        Ok(ReqwestTransport { client })
    }
}

#[cfg(all(test, feature = "http"))]
mod tls_tests;

/// Read at most `cap` bytes from `r`, refusing anything larger, and giving up at `deadline`.
///
/// **Deliberately free of `reqwest`** — it takes `impl Read`, so it compiles in the default build
/// and a test can drive it with a `Cursor`, a failing reader, or a dripping one. An earlier version
/// took a `reqwest::blocking::Response`, which meant it existed only under the `http` feature:
/// linted there, executed by no gate at all.
///
/// # Why this takes a deadline (PERF-2)
///
/// This function replaced `reqwest`'s own `text()`, and that swap **introduced a hang** that
/// `text()` did not have. Measured: a drip server was still being read **172 seconds past** a
/// 60-second client deadline, while the pre-change `text()` path errored at exactly 30.0s under
/// an identical drip.
///
/// **Which phase owns which bound — the precise version, because the loose one is dangerous.**
/// `reqwest`'s client timeout *is* a running total over the **response head**: connect, send,
/// status line and headers. Measured, a peer that sends a valid status line and then drips header
/// bytes forever is cut off at exactly the client deadline, by `reqwest`, with no help from here.
/// It degrades to **per read-wait** only over the **body**, and only once the body read is taken
/// out from under `reqwest`'s own bookkeeping — which is exactly what replacing `text()` with this
/// loop did.
///
/// So this is **not an inherited `reqwest` weakness**. The gap was created by moving the read
/// here, and it is re-created by any future change that takes a read into its own hands. That is
/// the thing to watch for, not `reqwest`. Saying "reqwest's timeout is per-wait" without the split
/// invites a reader to conclude this deadline is redundant *wherever* `reqwest` is involved and
/// delete it; over the body it is the only bound there is.
///
/// | peer behaviour              | phase         | outcome                          |
/// |-----------------------------|---------------|----------------------------------|
/// | headers done, body drips    | body read     | 60.0s — this function's deadline  |
/// | status line, headers drip   | response head | 60.0s — `reqwest`'s client timeout |
///
/// A **zero-byte** stall also cuts at the client deadline, which is why the hang was invisible:
/// every probe written for the original bound tested silence, and silence was the one shape that
/// already worked. "It fails rather than hanging" was true for the case that had been tried and
/// false in general.
///
/// So the loop owns its own deadline. It is checked before every read and after every chunk, which
/// bounds total elapsed time regardless of how the bytes are paced.
///
/// Reads `cap + 1` so **"exactly at the cap" is distinguishable from "over it"**: stopping at
/// exactly `cap` would silently truncate a legitimately cap-sized body, and a truncated JSON body
/// surfaces as a confusing parse error rather than the size problem it is.
///
/// Errors carry the cap or the deadline and **nothing from the body**: a response body is
/// attacker-influenced and, on at least one real provider, contains key material.
pub fn read_capped(
    r: impl std::io::Read,
    cap: usize,
    deadline: Option<std::time::Instant>,
) -> Result<Vec<u8>, TransportError> {
    use std::io::Read;
    let expired = |d: Option<std::time::Instant>| d.is_some_and(|d| std::time::Instant::now() >= d);
    // `saturating_add`: a caller may legitimately pass `usize::MAX` to mean "no size cap, bound
    // me by the deadline alone", and `+ 1` on that overflows and panics in a debug build. Found by
    // the PERF-2 drip test, which does exactly that.
    let mut limited = r.take((cap as u64).saturating_add(1));
    let mut buf: Vec<u8> = Vec::new();
    let mut chunk = [0u8; 8 * 1024];
    loop {
        if expired(deadline) {
            return Err(TransportError(
                "timed out reading the response body".to_string(),
            ));
        }
        let n = limited
            .read(&mut chunk)
            .map_err(|e| TransportError(e.to_string()))?;
        if n == 0 {
            break;
        }
        buf.extend_from_slice(&chunk[..n]);
        // Checked inside the loop, so an over-cap body is refused as soon as it crosses rather
        // than after the whole thing is resident.
        if buf.len() > cap {
            return Err(TransportError(format!(
                "response exceeded the {cap}-byte transport cap"
            )));
        }
        if expired(deadline) {
            return Err(TransportError(
                "timed out reading the response body".to_string(),
            ));
        }
    }
    Ok(buf)
}

/// Read a response body with a hard ceiling, instead of `text()`'s read-to-end.
#[cfg(feature = "http")]
fn read_bounded(resp: reqwest::blocking::Response) -> Result<HttpResponse, TransportError> {
    let status = resp.status().as_u16();
    // The body read gets its own deadline because the client timeout does not bound it (PERF-2).
    // Worst case is therefore the head phase plus this budget rather than a single
    // REQUEST_TIMEOUT_SECS — stated plainly rather than hidden, since the alternative is a bound
    // that only holds for peers that stay silent.
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS);
    let buf = read_capped(resp, MAX_TRANSPORT_RESPONSE_BYTES, Some(deadline))?;
    // Bodies are untrusted bytes; decode lossily rather than failing on bad UTF-8, so a
    // mangled response becomes a parse error the caller can map, not a transport error
    // that would trigger the degraded-fallback path for the wrong reason.
    Ok(HttpResponse {
        status,
        body: String::from_utf8_lossy(&buf).into_owned(),
    })
}

#[cfg(feature = "http")]
impl HttpTransport for ReqwestTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        let mut req = self
            .client
            .post(url)
            .header("content-type", "application/json")
            .body(body.to_string());
        if let Some(t) = bearer {
            req = req.bearer_auth(t);
        }
        let resp = req
            .send()
            .map_err(|e| TransportError(describe_send_error(&e)))?;
        read_bounded(resp)
    }

    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        let mut req = self.client.get(url);
        if let Some(t) = bearer {
            req = req.bearer_auth(t);
        }
        let resp = req
            .send()
            .map_err(|e| TransportError(describe_send_error(&e)))?;
        read_bounded(resp)
    }
}
