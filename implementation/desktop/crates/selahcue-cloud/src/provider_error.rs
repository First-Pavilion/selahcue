//! What a provider's error body is allowed to tell us (86akbzxjg).
//!
//! An error body from a provider, or from a proxy that forwards one, is **untrusted free
//! text that has been observed to carry credential material**: OpenAI's 401 contains a masked
//! but partly clear copy of the key that was sent (`sk-proj-********************-key`), and a
//! thin hosted proxy that passes an upstream body through would pass that along with it. So
//! nothing in a body is ever copied into an error message, a log line or a `Debug` rendering.
//!
//! What this module does instead is **extract**, from a fixed set of fields, into values that
//! cannot contain body text:
//!
//! - `error.type` / `error.code` are matched against a closed list ([`KNOWN_REASONS`]). What
//!   comes out is the list's own `&'static str`, never the body's bytes, so a code that is not
//!   on the list yields nothing and a credential placed in the field is dropped by construction.
//! - `error.request_id` is kept only when it has the exact shape of a correlation handle
//!   (`req_` and 8 to 64 ASCII alphanumerics, [`is_request_id`]), so a token shaped like
//!   `sk-...` cannot pass as one.
//! - Everything else, `error.message` above all, is never read.
//!
//! This is deliberately an **allowlist of fields and values**, not a redaction pass over text:
//! a regex over arbitrary text can only remove the secrets someone thought to describe.
//!
//! It is also the **one place** that decides "terminal exhaustion versus transient rate
//! limit". OpenAI overloads 429: `insufficient_quota` / `credit_balance_exhausted` means the
//! account is out of money (terminal, the operator must be told), a plain rate limit is a blip
//! (retryable, the local draft should be served). `openai::map_error_status` (behind the `openai` feature) and
//! [`crate::client::SelahCueCloudClient`] both call [`ErrorFields::is_terminal_exhaustion`];
//! neither keeps a copy of the codes.

/// The error codes that mean the account has run out of credit. Terminal.
const TERMINAL_EXHAUSTION_CODES: [&str; 2] = ["insufficient_quota", "credit_balance_exhausted"];

/// Every other reason code the client may repeat to the operator. Closed on purpose: a code
/// that is not here, or not exactly equal to an entry, is dropped.
const OTHER_KNOWN_REASONS: [&str; 9] = [
    "rate_limit_exceeded",
    "invalid_api_key",
    "invalid_request_error",
    "model_not_found",
    "missing_required_parameter",
    "context_length_exceeded",
    "server_error",
    "service_unavailable",
    "requests",
];

/// Whether `code` is one of the terminal-exhaustion codes. The single definition.
fn is_terminal_code(code: &str) -> bool {
    TERMINAL_EXHAUSTION_CODES.contains(&code)
}

/// The list's own copy of `code` if (and only if) it is on the closed list.
fn known_reason(code: &str) -> Option<&'static str> {
    TERMINAL_EXHAUSTION_CODES
        .iter()
        .chain(OTHER_KNOWN_REASONS.iter())
        .copied()
        .find(|k| *k == code)
}

/// Whether `s` has the shape of a correlation handle: `req_` then 8 to 64 ASCII alphanumerics.
pub(crate) fn is_request_id(s: &str) -> bool {
    match s.strip_prefix("req_") {
        Some(rest) => {
            (8..=64).contains(&rest.len()) && rest.bytes().all(|b| b.is_ascii_alphanumeric())
        }
        None => false,
    }
}

/// The allowlisted view of an error body. Holds no body text it was not handed in a safe shape.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub(crate) struct ErrorFields {
    reason: Option<&'static str>,
    request_id: Option<String>,
}

impl ErrorFields {
    /// Parse `body`, reading only `error.type`, `error.code` and `error.request_id`. A body that
    /// is not JSON, or has no `error` object, yields the empty view.
    pub(crate) fn parse(body: &str) -> Self {
        let Ok(root) = serde_json::from_str::<serde_json::Value>(body) else {
            return ErrorFields::default();
        };
        let Some(error) = root.get("error") else {
            return ErrorFields::default();
        };
        let field = |name: &str| error.get(name).and_then(|v| v.as_str());

        // Exhaustion in EITHER field wins, so a body that says `type: insufficient_quota` with
        // an unrelated `code` is still terminal. Otherwise prefer `code` (the more specific).
        let candidates = [field("code"), field("type")];
        let reason = candidates
            .iter()
            .flatten()
            .find(|c| is_terminal_code(c))
            .or_else(|| {
                candidates
                    .iter()
                    .flatten()
                    .find(|c| known_reason(c).is_some())
            })
            .and_then(|c| known_reason(c));

        let request_id = field("request_id")
            .filter(|r| is_request_id(r))
            .map(str::to_string);

        ErrorFields { reason, request_id }
    }

    /// The account is out of credit: terminal, and the operator must be told.
    pub(crate) fn is_terminal_exhaustion(&self) -> bool {
        self.reason.is_some_and(is_terminal_code)
    }

    /// `" (reason: X, request: req_...)"`, `" (reason: X)"`, `" (request: req_...)"` or `""`.
    /// Built only from the two allowlisted fields.
    pub(crate) fn describe(&self) -> String {
        match (self.reason, self.request_id.as_deref()) {
            (Some(r), Some(id)) => format!(" (reason: {r}, request: {id})"),
            (Some(r), None) => format!(" (reason: {r})"),
            (None, Some(id)) => format!(" (request: {id})"),
            (None, None) => String::new(),
        }
    }
}
