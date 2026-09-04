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
#[cfg(feature = "http")]
pub const MAX_RESPONSE_BYTES: usize = 4 * 1024 * 1024;

/// The production transport over `reqwest` (blocking, rustls TLS). Compiled only with
/// the `http` feature so the default workspace build/tests stay light and offline.
#[cfg(feature = "http")]
pub struct ReqwestTransport {
    client: reqwest::blocking::Client,
}

#[cfg(feature = "http")]
impl ReqwestTransport {
    /// A transport with a sane timeout (never hangs the caller indefinitely).
    pub fn new() -> Result<Self, TransportError> {
        let client = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(|e| TransportError(e.to_string()))?;
        Ok(ReqwestTransport { client })
    }
}

/// Read a response body with a hard ceiling, instead of `text()`'s read-to-end.
///
/// Takes `MAX_RESPONSE_BYTES + 1` so "exactly at the cap" is distinguishable from "over
/// it" — reading exactly the cap and stopping would silently truncate a body that was
/// legitimately that size, and a silently truncated JSON body surfaces as a confusing
/// parse error rather than as the size problem it is.
///
/// The error message carries the cap and nothing from the body: a response body is
/// attacker-influenced and, on at least one real provider, contains key material.
#[cfg(feature = "http")]
fn read_bounded(resp: reqwest::blocking::Response) -> Result<HttpResponse, TransportError> {
    use std::io::Read;
    let status = resp.status().as_u16();
    let mut buf = Vec::new();
    let mut limited = resp.take((MAX_RESPONSE_BYTES as u64) + 1);
    limited
        .read_to_end(&mut buf)
        .map_err(|e| TransportError(e.to_string()))?;
    if buf.len() > MAX_RESPONSE_BYTES {
        return Err(TransportError(format!(
            "response exceeded the {MAX_RESPONSE_BYTES}-byte transport cap"
        )));
    }
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
