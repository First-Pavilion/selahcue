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

/// The production transport over `reqwest` (blocking, rustls TLS). Compiled only with
/// the `http` feature so the default workspace build/tests stay light and offline.
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

#[cfg(feature = "http")]
impl ReqwestTransport {
    /// A transport that is bounded at both the connect phase and the whole request, so a
    /// stalling peer always fails rather than hanging the caller.
    pub fn new() -> Result<Self, TransportError> {
        let client = reqwest::blocking::Client::builder()
            .connect_timeout(std::time::Duration::from_secs(CONNECT_TIMEOUT_SECS))
            .timeout(std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .build()
            .map_err(|e| TransportError(e.to_string()))?;
        Ok(ReqwestTransport { client })
    }
}

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
        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;
        read_bounded(resp)
    }

    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        let mut req = self.client.get(url);
        if let Some(t) = bearer {
            req = req.bearer_auth(t);
        }
        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;
        read_bounded(resp)
    }
}
