//! The HTTP transport seam. The client depends on this trait, not on any concrete
//! network library, so tests inject a deterministic [`crate::mock::MockTransport`]
//! and the production build injects [`ReqwestTransport`] (behind the `http` feature).

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

/// Read at most `cap` bytes from `r`, refusing anything larger.
///
/// **Deliberately free of `reqwest`** — it takes `impl Read`, so it compiles in the default
/// build and a test can drive it with a `Cursor` or a deliberately-failing reader. The
/// previous version took a `reqwest::blocking::Response`, which meant it existed only under
/// the `http` feature: linted there, but executed by no gate at all. A bound nothing runs is
/// the same category of thing as a control nothing exercises.
///
/// Reads `cap + 1` so **"exactly at the cap" is distinguishable from "over it"**. Stopping at
/// exactly `cap` would silently truncate a body that was legitimately that size, and a
/// silently truncated JSON body surfaces as a confusing parse error rather than as the size
/// problem it actually is.
///
/// The error carries the cap and **nothing from the body**: a response body is
/// attacker-influenced and, on at least one real provider, contains key material.
pub fn read_capped(r: impl std::io::Read, cap: usize) -> Result<Vec<u8>, TransportError> {
    use std::io::Read;
    let mut buf = Vec::new();
    r.take((cap as u64) + 1)
        .read_to_end(&mut buf)
        .map_err(|e| TransportError(e.to_string()))?;
    if buf.len() > cap {
        return Err(TransportError(format!(
            "response exceeded the {cap}-byte transport cap"
        )));
    }
    Ok(buf)
}

/// Read a response body with a hard ceiling, instead of `text()`'s read-to-end.
#[cfg(feature = "http")]
fn read_bounded(resp: reqwest::blocking::Response) -> Result<HttpResponse, TransportError> {
    let status = resp.status().as_u16();
    let buf = read_capped(resp, MAX_TRANSPORT_RESPONSE_BYTES)?;
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
