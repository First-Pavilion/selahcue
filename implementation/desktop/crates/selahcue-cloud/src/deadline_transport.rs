//! Native deadline-bound HTTP: one admitted budget covers response head AND body.
//! The actual async I/O future and its private runtime are shut down at expiry;
//! an outer timeout around spawn_blocking is deliberately not the mechanism.
use crate::transport::{
    ensure_crypto_provider, require_https_base_url, require_loopback_test_url,
    reqwest_transport_error, HttpFailurePhase, HttpResponse, HttpTransport, TransportError,
    CONNECT_TIMEOUT_SECS, MAX_TRANSPORT_RESPONSE_BYTES, REQUEST_TIMEOUT_SECS,
};
use selahcue_core::deadline::AccessDeadline;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::Duration;

pub struct DeadlineTransport {
    client: reqwest::Client,
    deadline: AccessDeadline,
    rejected: Arc<AtomicBool>,
    loopback: bool,
}
impl DeadlineTransport {
    pub fn new(
        deadline: AccessDeadline,
        rejected: Arc<AtomicBool>,
    ) -> Result<Self, TransportError> {
        Self::build(deadline, rejected, false)
    }
    pub fn new_for_loopback_tests(
        deadline: AccessDeadline,
        rejected: Arc<AtomicBool>,
    ) -> Result<Self, TransportError> {
        Self::build(deadline, rejected, true)
    }
    fn build(
        deadline: AccessDeadline,
        rejected: Arc<AtomicBool>,
        loopback: bool,
    ) -> Result<Self, TransportError> {
        ensure_crypto_provider();
        let mut builder = reqwest::Client::builder()
            .https_only(!loopback)
            .connect_timeout(Duration::from_secs(CONNECT_TIMEOUT_SECS))
            .redirect(reqwest::redirect::Policy::none());
        if loopback {
            builder = builder.no_proxy();
        }
        let client = builder
            .build()
            .map_err(|e| reqwest_transport_error(&e, HttpFailurePhase::Build))?;
        Ok(Self {
            client,
            deadline,
            rejected,
            loopback,
        })
    }
    async fn perform(
        &self,
        method: reqwest::Method,
        url: &str,
        body: Option<&str>,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        let remaining = self.deadline.remaining().map_err(|_| unavailable())?;
        let mut request = self
            .client
            .request(method, url)
            .timeout(remaining.min(Duration::from_secs(REQUEST_TIMEOUT_SECS)));
        if let Some(body) = body {
            request = request
                .header("content-type", "application/json")
                .body(body.to_owned());
        }
        if let Some(token) = bearer {
            request = request.bearer_auth(token);
        }
        let mut response = request
            .send()
            .await
            .map_err(|e| reqwest_transport_error(&e, HttpFailurePhase::Send))?;
        let status = response.status().as_u16();
        if matches!(status, 401 | 403) {
            self.rejected.store(true, Ordering::SeqCst);
            return Ok(HttpResponse {
                status,
                body: String::new(),
            });
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|_| failed())? {
            self.deadline.remaining().map_err(|_| unavailable())?;
            if chunk.len() > MAX_TRANSPORT_RESPONSE_BYTES.saturating_sub(bytes.len()) {
                return Err(TransportError(
                    "HTTP response exceeded transport cap".into(),
                ));
            }
            bytes.extend_from_slice(&chunk);
        }
        self.deadline.remaining().map_err(|_| unavailable())?;
        Ok(HttpResponse {
            status,
            body: String::from_utf8_lossy(&bytes).into_owned(),
        })
    }
    fn request(
        &self,
        method: reqwest::Method,
        url: &str,
        body: Option<&str>,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        if self.loopback {
            require_loopback_test_url(url)?;
        } else {
            require_https_base_url(url)?;
        }
        self.deadline.remaining().map_err(|_| unavailable())?;
        if self.rejected.load(Ordering::SeqCst) {
            return Err(TransportError("provider access was rejected".into()));
        }
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|_| failed())?;
        let result=runtime.block_on(async {
            let work=self.perform(method,url,body,bearer);tokio::pin!(work);
            loop {
                let remaining=self.deadline.remaining().map_err(|_| unavailable())?;
                if self.rejected.load(Ordering::SeqCst) {return Err(TransportError("provider access was rejected".into()));}
                tokio::select! {
                    biased;
                    _=tokio::time::sleep(remaining.min(Duration::from_millis(20)))=>{},
                    result=&mut work=>{self.deadline.remaining().map_err(|_| unavailable())?;return result;}
                }
            }
        });
        // Cancel connection/background async tasks too. A blocking DNS resolver may
        // finish separately, but it holds no request/credential continuation.
        runtime.shutdown_timeout(Duration::from_millis(100));
        result
    }
}
fn unavailable() -> TransportError {
    TransportError("pilot access expired or clock unavailable".into())
}
fn failed() -> TransportError {
    TransportError("deadline-bound HTTP request failed".into())
}
impl HttpTransport for DeadlineTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        self.request(reqwest::Method::POST, url, Some(body), bearer)
    }
    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        self.request(reqwest::Method::GET, url, None, bearer)
    }
}
