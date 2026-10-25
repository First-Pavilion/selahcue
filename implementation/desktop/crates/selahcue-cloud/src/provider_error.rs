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
//! - `error.type` / `error.code` are matched against a closed list (`TERMINAL_EXHAUSTION_CODES`
//!   and `OTHER_KNOWN_REASONS`). What comes out is the list's own `&'static str`, never the
//!   body's bytes, so a code that is not on the list yields nothing and a credential placed in
//!   the field is dropped by construction. The match is exact and case-sensitive.
//! - Everything else, `error.message` above all, and `error.request_id` too, is never read.
//!   There is deliberately no correlation-handle channel: nothing produces one today
//!   (`HttpResponse` carries no headers and the hosted envelope is undefined), and a check on
//!   the *shape* of a value cannot tell an identifier from an alphanumeric secret. 86akby3xu
//!   defines the hosted envelope and can add a channel with a producer behind it.
//!
//! This is deliberately an **allowlist of fields and values**, not a redaction pass over text:
//! a regex over arbitrary text can only remove the secrets someone thought to describe.
//!
//! **The parse is bounded.** A body longer than `MAX_ERROR_BODY_PARSE_BYTES` is not parsed
//! at all (the empty view is returned), so a hostile or buggy peer cannot make an error path
//! build a tree proportional to the transport's 4 MiB response cap. Real error envelopes are
//! under 1 KiB. serde_json's own recursion limit (128 levels) applies to what is parsed: a body
//! nested deeper than that fails to parse and reads as the empty view too.
//!
//! It is also the **one place** that decides "terminal exhaustion versus transient rate
//! limit". OpenAI overloads 429: `insufficient_quota` / `credit_balance_exhausted` means the
//! account is out of money (terminal, the operator must be told), a plain rate limit is a blip
//! (retryable, the local draft should be served). `openai::map_error_status` (behind the
//! `openai` feature) and [`crate::client::SelahCueCloudClient`] both call
//! `ErrorFields::is_terminal_exhaustion` (crate-private, so not linked); neither keeps a copy
//! of the codes.

/// The largest error body that is parsed at all, in bytes. Real envelopes are well under 1 KiB;
/// this mirrors `openai::MAX_PARSED_RESPONSE_BYTES` in spirit (refuse before building a tree)
/// at a size that fits an error body rather than a whole generated draft. A body over this is
/// read as the empty view: a terminal code in an oversized body is NOT seen, so a 429 carrying
/// one reads as transient.
pub const MAX_ERROR_BODY_PARSE_BYTES: usize = 32 * 1024;

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

/// The allowlisted view of an error body. Holds no body text it was not handed in a safe shape.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub(crate) struct ErrorFields {
    reason: Option<&'static str>,
}

impl ErrorFields {
    /// Parse `body`, reading only `error.type` and `error.code`. A body that is over
    /// [`MAX_ERROR_BODY_PARSE_BYTES`], is not JSON, is nested past serde_json's recursion limit,
    /// or has no `error` object yields the empty view.
    pub(crate) fn parse(body: &str) -> Self {
        // Refused BEFORE serde_json builds a tree, so an oversized body costs one length check
        // rather than an allocation proportional to the body.
        if body.len() > MAX_ERROR_BODY_PARSE_BYTES {
            return ErrorFields::default();
        }
        let Ok(root) = serde_json::from_str::<serde_json::Value>(body) else {
            return ErrorFields::default();
        };
        let Some(error) = root.get("error") else {
            return ErrorFields::default();
        };
        let field = |name: &str| error.get(name).and_then(|v| v.as_str());

        // Exhaustion in EITHER field wins, so a body that says `type: insufficient_quota` with
        // an unrelated `code` (say `rate_limit_exceeded`) is still terminal. Otherwise prefer
        // `code` (the more specific).
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

        ErrorFields { reason }
    }

    /// The account is out of credit: terminal, and the operator must be told.
    pub(crate) fn is_terminal_exhaustion(&self) -> bool {
        self.reason.is_some_and(is_terminal_code)
    }

    /// `" (reason: X)"` when the body carried a code on the closed list, otherwise `""`.
    /// Built only from the list's own strings.
    pub(crate) fn describe(&self) -> String {
        match self.reason {
            Some(r) => format!(" (reason: {r})"),
            None => String::new(),
        }
    }
}
