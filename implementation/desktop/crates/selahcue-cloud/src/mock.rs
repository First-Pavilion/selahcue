//! A deterministic in-process [`HttpTransport`] for tests and the operator dev-build.
//!
//! It records every request (so a test can assert *exactly* what left the device —
//! or that nothing did) and returns canned responses. It can be put into a failing
//! mode to exercise the graceful-fallback path (FR-135) without real networking.

use crate::transport::{HttpResponse, HttpTransport, TransportError};
use std::sync::{Arc, Mutex};

/// One recorded outbound request (for privacy assertions in tests).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordedRequest {
    pub method: &'static str,
    pub url: String,
    pub body: String,
    pub had_bearer: bool,
}

/// A scripted transport. Not thread-heavy: a `Mutex` guards the recording so it can be
/// shared behind `&self` (the trait takes `&self`). The recording itself is behind an
/// `Arc` (not a bare `Mutex`) so [`MockTransport::requests_handle`] can hand out a cloned
/// handle BEFORE the transport is moved by value into a client (e.g.
/// `SelahCueCloudClient::new(transport, ...)`, which takes ownership) — a test can still
/// inspect exactly what left the device afterward without needing the client to expose
/// its transport back out.
#[derive(Debug)]
pub struct MockTransport {
    response: HttpResponse,
    fail: bool,
    requests: Arc<Mutex<Vec<RecordedRequest>>>,
}

impl MockTransport {
    /// A transport that returns `status` + `body` for every call.
    pub fn responding(status: u16, body: impl Into<String>) -> Self {
        MockTransport {
            response: HttpResponse {
                status,
                body: body.into(),
            },
            fail: false,
            requests: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// A transport that always fails at the transport level (network loss / unreachable)
    /// — drives the local fallback path.
    pub fn failing() -> Self {
        MockTransport {
            response: HttpResponse {
                status: 0,
                body: String::new(),
            },
            fail: true,
            requests: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Every request recorded so far (in order).
    pub fn recorded(&self) -> Vec<RecordedRequest> {
        self.requests
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .clone()
    }

    /// How many requests have been issued — `0` proves nothing left the device.
    pub fn request_count(&self) -> usize {
        self.requests
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .len()
    }

    /// A cloned handle onto the SAME recording this transport writes to — call this
    /// BEFORE handing the transport by value to something that takes ownership of it
    /// (e.g. `SelahCueCloudClient::new`), so a test can still inspect exactly what left
    /// the device afterward. Reads through it with the same lock/clone shape as
    /// [`MockTransport::recorded`].
    pub fn requests_handle(&self) -> Arc<Mutex<Vec<RecordedRequest>>> {
        Arc::clone(&self.requests)
    }

    fn record(&self, method: &'static str, url: &str, body: &str, bearer: Option<&str>) {
        self.requests
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .push(RecordedRequest {
                method,
                url: url.to_string(),
                body: body.to_string(),
                had_bearer: bearer.is_some(),
            });
    }
}

impl HttpTransport for MockTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        self.record("POST", url, body, bearer);
        if self.fail {
            return Err(TransportError("mock: network unreachable".into()));
        }
        Ok(self.response.clone())
    }

    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        self.record("GET", url, "", bearer);
        if self.fail {
            return Err(TransportError("mock: network unreachable".into()));
        }
        Ok(self.response.clone())
    }
}
