//! A sequenced [`HttpTransport`] for tests and the operator dev-build.
//!
//! `selahcue_cloud::MockTransport` answers every call with one canned response, which is
//! right for a single-call surface and wrong here: the primary activation path is two
//! calls — sign in, then activate — and a test that cannot give them different answers
//! cannot exercise it.
//!
//! This transport hands back queued responses in order and records every request, so a
//! test can assert exactly what left the device, in what order, and with which
//! credential attached. It never touches the network.

use selahcue_cloud::{HttpResponse, HttpTransport, TransportError};
use std::sync::Mutex;

/// One recorded outbound request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordedRequest {
    pub method: &'static str,
    pub url: String,
    pub body: String,
    /// Whether an `Authorization: Bearer` was attached. The token itself is deliberately
    /// **not** recorded — a test fixture is exactly the kind of place a credential gets
    /// copied into a log and then into a bug report.
    pub had_bearer: bool,
}

/// A queued answer: either an HTTP response or a transport-level failure.
#[derive(Debug, Clone)]
enum Step {
    Respond(HttpResponse),
    Fail(String),
}

/// A transport that answers queued steps in order.
///
/// Running past the end of the queue is a transport failure rather than a panic, so an
/// over-eager client under test surfaces as a clean, assertable error.
#[derive(Debug)]
pub struct ScriptedTransport {
    steps: Mutex<std::collections::VecDeque<Step>>,
    requests: Mutex<Vec<RecordedRequest>>,
}

impl ScriptedTransport {
    /// An empty script. Every call fails until steps are queued.
    pub fn new() -> Self {
        ScriptedTransport {
            steps: Mutex::new(std::collections::VecDeque::new()),
            requests: Mutex::new(Vec::new()),
        }
    }

    /// A script answering one call with `status` + `body`.
    pub fn responding(status: u16, body: impl Into<String>) -> Self {
        let transport = Self::new();
        transport.push_response(status, body);
        transport
    }

    /// A script whose first call fails at the transport level (network unreachable).
    pub fn failing(reason: impl Into<String>) -> Self {
        let transport = Self::new();
        transport.push_failure(reason);
        transport
    }

    /// Queue an HTTP response.
    pub fn push_response(&self, status: u16, body: impl Into<String>) -> &Self {
        self.lock_steps().push_back(Step::Respond(HttpResponse {
            status,
            body: body.into(),
        }));
        self
    }

    /// Queue a transport-level failure.
    pub fn push_failure(&self, reason: impl Into<String>) -> &Self {
        self.lock_steps().push_back(Step::Fail(reason.into()));
        self
    }

    /// Every request issued so far, in order.
    pub fn recorded(&self) -> Vec<RecordedRequest> {
        self.lock_requests().clone()
    }

    /// How many requests were issued. `0` proves nothing left the device.
    pub fn request_count(&self) -> usize {
        self.lock_requests().len()
    }

    /// The request at `index`, or `None`. Per-index rather than a bare count so an
    /// assertion names the call it means.
    pub fn request(&self, index: usize) -> Option<RecordedRequest> {
        self.lock_requests().get(index).cloned()
    }

    fn lock_steps(&self) -> std::sync::MutexGuard<'_, std::collections::VecDeque<Step>> {
        self.steps
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    fn lock_requests(&self) -> std::sync::MutexGuard<'_, Vec<RecordedRequest>> {
        self.requests
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    fn run(
        &self,
        method: &'static str,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        self.lock_requests().push(RecordedRequest {
            method,
            url: url.to_string(),
            body: body.to_string(),
            had_bearer: bearer.is_some(),
        });
        match self.lock_steps().pop_front() {
            Some(Step::Respond(response)) => Ok(response),
            Some(Step::Fail(reason)) => Err(TransportError(reason)),
            None => Err(TransportError("scripted transport: no step queued".into())),
        }
    }
}

impl Default for ScriptedTransport {
    fn default() -> Self {
        Self::new()
    }
}

impl HttpTransport for ScriptedTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        self.run("POST", url, body, bearer)
    }

    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        self.run("GET", url, "", bearer)
    }
}
