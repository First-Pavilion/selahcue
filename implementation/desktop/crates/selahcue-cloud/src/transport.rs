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
        let status = resp.status().as_u16();
        let body = resp.text().map_err(|e| TransportError(e.to_string()))?;
        Ok(HttpResponse { status, body })
    }

    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        let mut req = self.client.get(url);
        if let Some(t) = bearer {
            req = req.bearer_auth(t);
        }
        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;
        let status = resp.status().as_u16();
        let body = resp.text().map_err(|e| TransportError(e.to_string()))?;
        Ok(HttpResponse { status, body })
    }
}
