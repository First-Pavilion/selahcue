//! 86akbzxjg: the SelahCue cloud client never puts any part of a provider response body into
//! an error, and tells a terminal out-of-credit 429 from a transient rate-limit 429.
//!
//! **No feature gate.** `SelahCueCloudClient` is part of the default build, so these run in the
//! default build too (unlike `test_openai.rs`, which is `#![cfg(feature = "openai")]`).
//! Nothing here touches the network: every case runs against `MockTransport`, and every
//! "credential" below is a made-up string of the right shape, never a real key.
//!
//! The first three bodies in [`fixtures`] are copied verbatim from `test_openai.rs`, which
//! recorded them from the live OpenAI API on 2026-09-04 (the 429 rate-limit body is the one
//! constructed shape, built to differ from the captured out-of-credit 429 in exactly the field the
//! mapping reads). The 401 matters most: it carries a masked but partly clear copy of the key.
//!
//! The crate has no logging macros or print macros of its own (checked by grep over `src/`), so
//! the surfaces a log line could carry are the error's `Display` and its derived `Debug`; both are
//! asserted on everywhere below. With the `http` feature the `rustls` dependency carries its own
//! TLS-internal logging, which never sees an HTTP body. No log output is captured by these tests.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::contract::{GenerateNotesResponse, QuotaDto};
use selahcue_cloud::provider_error::MAX_ERROR_BODY_PARSE_BYTES;
use selahcue_cloud::transport::MAX_TRANSPORT_RESPONSE_BYTES;
use selahcue_cloud::{
    generate_sermon_notes, CloudNoteProvider, GenerationOutcome, LocalNoteProvider, MockTransport,
    SelahCueCloudClient, Token,
};
use selahcue_core::providers::{ConsentState, NoteError, NoteRequest, ProvidersConfig};

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

mod fixtures {
    /// Verbatim from the live API, 2026-09-04 (copied from `test_openai.rs`).
    pub const ERR_401_INVALID_KEY: &str = r#"{
  "error": {
    "message": "Incorrect API key provided: sk-proj-********************-key. You can find your API key at https://platform.openai.com/account/api-keys.",
    "type": "invalid_request_error",
    "code": "invalid_api_key",
    "param": null
  },
  "status": 401
}"#;

    /// Verbatim from the live API, 2026-09-04 (account at zero credits).
    pub const ERR_429_NO_CREDITS: &str = r#"{
  "error": {
    "message": "You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.",
    "type": "insufficient_quota",
    "param": null,
    "code": "credit_balance_exhausted"
  }
}"#;

    /// The one constructed shape: a rate-limit 429, built to differ from the captured
    /// out-of-credit 429 in exactly the field the mapping reads.
    pub const ERR_429_RATE_LIMIT: &str = r#"{
  "error": {
    "message": "Rate limit reached for requests",
    "type": "requests",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}"#;
}

/// The fragment of the key that survives OpenAI's masking in the captured 401 body.
const CAPTURED_KEY_FRAGMENT: &str = "sk-proj-********************-key";

/// Made-up credential-shaped strings, one per position, each distinct so a failure names the
/// position that leaked. None is a real key.
const KEY_AT_START: &str = "sk-proj-LEAKSTARTaaaa1111bbbb2222cccc3333";
const KEY_IN_MIDDLE: &str = "sk-proj-LEAKMIDDLEdddd4444eeee5555ffff6666";
const KEY_PAST_200: &str = "sk-proj-LEAKFAR0000gggg7777hhhh8888iiii9999";
const KEY_AT_END: &str = "sk-proj-LEAKENDjjjj1212kkkk3434llll5656mmmm";
const KEY_AS_CODE: &str = "sk-proj-LEAKCODEnnnn7878oooo9090pppp1313qqqq";
const KEY_AS_TYPE: &str = "sk-proj-LEAKTYPErrrr2424ssss3535tttt4646uuuu";
const KEY_AS_REQUEST_ID: &str = "sk-proj-LEAKREQIDvvvv5757wwww6868xxxx7979";
const KEY_IN_EXTRA_FIELD: &str = "sk-proj-LEAKEXTRAyyyy8080zzzz9191AAAA0202";
/// The account token this client itself sends as the bearer; a proxy that echoes the
/// `Authorization` header back would carry it in the body.
const ACCOUNT_TOKEN: &str = "acct-session-token-LEAKBEARER-0123456789";

const BASE: &str = "https://api.selahcue.example";

/// Reason codes the client may legitimately repeat (a closed list of its own). They appear in
/// the fixtures too, so the "no run of the body" check blanks them out before comparing.
const ALLOWED_REASONS: &[&str] = &[
    "invalid_api_key",
    "invalid_request_error",
    "rate_limit_exceeded",
    "insufficient_quota",
    "credit_balance_exhausted",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn consented() -> ConsentState {
    ConsentState {
        cloud_transcription: false,
        cloud_notes: true,
    }
}

fn config() -> ProvidersConfig {
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    cfg
}

fn note_request() -> NoteRequest {
    config()
        .build_note_request("the completed transcript", true)
        .unwrap()
}

fn client(status: u16, body: &str) -> SelahCueCloudClient<MockTransport> {
    SelahCueCloudClient::new(
        MockTransport::responding(status, body),
        BASE,
        Token::new(ACCOUNT_TOKEN),
    )
}

/// Run the same canned response through BOTH entry points that build an error from a response,
/// so neither can keep a path the other lost. Returns `(generate_with_quota, fetch_quota)`.
fn both_errors(status: u16, body: &str) -> [(&'static str, NoteError); 2] {
    let gen = client(status, body)
        .generate_with_quota(&note_request())
        .expect_err("a non-2xx response must be an error");
    let quota = client(status, body)
        .fetch_quota(&consented())
        .expect_err("a non-2xx response must be an error");
    [("generate_with_quota", gen), ("fetch_quota", quota)]
}

/// Every surface a log line or the UI could carry: `Display` and the derived `Debug`.
fn rendered(err: &NoteError) -> String {
    format!("{err}  ||  {err:?}")
}

/// Windows of this many characters are compared between body and error; see
/// [`assert_no_body_text`].
const WINDOW: usize = 12;

/// "No portion of the provider body": no `WINDOW`-character run of `body` appears in the error
/// text, after blanking out the values the allowlist legitimately emits (`allowed`).
///
/// Marker checks alone only prove that the markers the author thought of are absent; this proves
/// that no run of the body, including prose the author did not think of, was copied across.
fn assert_no_body_text(who: &str, label: &str, body: &str, err: &NoteError, allowed: &[&str]) {
    let mut text = rendered(err);
    for a in allowed {
        text = text.replace(a, "\u{0}");
    }
    let chars: Vec<char> = body.chars().collect();
    for w in chars.windows(WINDOW) {
        let run: String = w.iter().collect();
        assert!(
            !text.contains(&run),
            "{who} / {label}: a run of the provider body reached the error: {run:?} in {text:?}"
        );
    }
}

fn assert_markers_absent(who: &str, label: &str, err: &NoteError, markers: &[&str]) {
    let text = rendered(err);
    for m in markers {
        assert!(
            !text.contains(m),
            "{who} / {label}: credential-shaped material {m:?} reached the error: {text}"
        );
    }
}

/// A body in the OpenAI error envelope, with every position a proxy might forward settable.
fn envelope(
    message: &str,
    kind: &str,
    code: &str,
    request_id: Option<&str>,
    extra: Option<&str>,
) -> String {
    let mut error = serde_json::json!({
        "message": message,
        "type": kind,
        "code": code,
        "param": null,
    });
    if let Some(r) = request_id {
        error["request_id"] = serde_json::json!(r);
    }
    let mut root = serde_json::json!({ "error": error });
    if let Some(x) = extra {
        root["debug"] = serde_json::json!({ "authorization": format!("Bearer {x}") });
    }
    root.to_string()
}

struct Case {
    label: &'static str,
    body: String,
    markers: Vec<&'static str>,
}

/// Bodies carrying credential-shaped material at several positions. Each one's premise (the
/// markers really are in the body) is asserted by the test that consumes it.
fn hostile_cases() -> Vec<Case> {
    let long_filler = "x".repeat(600);
    vec![
        Case {
            label: "captured 401 (key fragment at the start of the message)",
            body: fixtures::ERR_401_INVALID_KEY.to_string(),
            markers: vec![CAPTURED_KEY_FRAGMENT, "sk-proj-", "platform.openai.com"],
        },
        Case {
            label: "key as the very first bytes of a non-JSON body",
            body: format!("{KEY_AT_START} was rejected by the upstream gateway"),
            markers: vec![KEY_AT_START, "sk-proj-"],
        },
        Case {
            label: "key in the middle of a JSON message",
            body: envelope(
                &format!("The key provided, {KEY_IN_MIDDLE}, is not valid for this project"),
                "invalid_request_error",
                "invalid_api_key",
                None,
                None,
            ),
            markers: vec![KEY_IN_MIDDLE, "sk-proj-"],
        },
        Case {
            label: "key beyond the first 200 characters (truncate(body, 200) cannot hide it)",
            body: envelope(
                &format!("{long_filler} {KEY_PAST_200}"),
                "invalid_request_error",
                "invalid_api_key",
                None,
                None,
            ),
            markers: vec![KEY_PAST_200, "sk-proj-"],
        },
        Case {
            label: "key at the very end of a non-JSON body",
            body: format!("Upstream error, request rejected. Credential seen: {KEY_AT_END}"),
            markers: vec![KEY_AT_END, "sk-proj-"],
        },
        Case {
            label: "key placed in error.code (an unlisted code must be dropped, not echoed)",
            body: envelope("bad", "invalid_request_error", KEY_AS_CODE, None, None),
            markers: vec![KEY_AS_CODE, "sk-proj-"],
        },
        Case {
            label: "key placed in error.type",
            body: envelope("bad", KEY_AS_TYPE, "invalid_api_key", None, None),
            markers: vec![KEY_AS_TYPE, "sk-proj-"],
        },
        Case {
            label: "key placed in error.request_id (a field the client never reads)",
            body: envelope(
                "bad",
                "invalid_request_error",
                "invalid_api_key",
                Some(KEY_AS_REQUEST_ID),
                None,
            ),
            markers: vec![KEY_AS_REQUEST_ID, "sk-proj-"],
        },
        Case {
            label: "key in an unknown extra field (echoed Authorization header)",
            body: envelope(
                "bad",
                "invalid_request_error",
                "invalid_api_key",
                None,
                Some(KEY_IN_EXTRA_FIELD),
            ),
            markers: vec![KEY_IN_EXTRA_FIELD, "sk-proj-"],
        },
        Case {
            label: "the account bearer token echoed back by a proxy",
            body: format!(
                r#"{{"error":{{"message":"unauthorized","detail":"Authorization: Bearer {ACCOUNT_TOKEN}"}}}}"#
            ),
            markers: vec![ACCOUNT_TOKEN, "LEAKBEARER"],
        },
        Case {
            label: "an HTML error page from an intermediary",
            body: format!(
                "<html><body><h1>Bad gateway</h1><pre>token={KEY_IN_MIDDLE}</pre></body></html>"
            ),
            markers: vec![KEY_IN_MIDDLE, "Bad gateway", "<html>"],
        },
    ]
}

// ---------------------------------------------------------------------------
// 1 - No portion of a provider body reaches an error
// ---------------------------------------------------------------------------

/// Statuses that reach `status_error`'s arms. 402 and 429 are included on purpose: the
/// hostile bodies carry no exhaustion code, so they exercise the quota-adjacent arms too.
const STATUSES: [u16; 14] = [
    300, 400, 401, 402, 403, 404, 409, 418, 422, 429, 500, 502, 503, 599,
];

#[test]
fn no_error_from_either_entry_point_contains_any_part_of_a_provider_body() {
    let cases = hostile_cases();
    assert_eq!(cases.len(), 11, "premise: every position is covered");

    for case in &cases {
        // PREMISE, per case: the body really carries each marker. Without this, tidying a
        // fixture silently turns every absence assertion below vacuous.
        for m in &case.markers {
            assert!(
                case.body.contains(m),
                "premise: case {:?} no longer contains {m:?}; its assertions would pass vacuously",
                case.label
            );
        }

        for status in STATUSES {
            for (who, err) in both_errors(status, &case.body) {
                let label = format!("{} / status {status}", case.label);
                assert_markers_absent(who, &label, &err, &case.markers);
                assert_no_body_text(who, &label, &case.body, &err, ALLOWED_REASONS);
            }
        }
    }
}

#[test]
fn the_captured_401_is_reported_in_our_own_words_and_says_what_failed() {
    // "Do not echo the body" is satisfiable by saying nothing. An error carrying no information
    // is useless to the operator, so pin the other half: our wording names the status.
    for (who, err) in both_errors(401, fixtures::ERR_401_INVALID_KEY) {
        let text = err.to_string();
        assert!(
            text.contains("401"),
            "{who}: the error must identify the status on its own: {text}"
        );
        // A known coded reason from the closed list is a safe, useful thing to keep.
        assert!(
            text.contains("invalid_api_key"),
            "{who}: the allowlisted reason code should be kept: {text}"
        );
        assert!(
            matches!(err, NoteError::Malformed(_)),
            "{who}: a 401 stays Malformed, as before: {err:?}"
        );
        assert_no_body_text(
            who,
            "captured 401",
            fixtures::ERR_401_INVALID_KEY,
            &err,
            &["invalid_api_key"],
        );
    }
}

#[test]
fn error_request_id_is_never_read_whatever_its_shape() {
    // There is deliberately no correlation-handle channel: nothing produces one today, and a
    // check on the SHAPE of a value cannot tell an identifier from an alphanumeric secret. So
    // `error.request_id` must not reach the error whether it looks like a handle or like a key.
    for value in [
        "req_0123456789abcdef0123456789abcdef",
        KEY_AS_REQUEST_ID,
        "0123456789abcdef0123456789abcdef",
    ] {
        let body = envelope(
            "bad",
            "invalid_request_error",
            "invalid_api_key",
            Some(value),
            None,
        );
        assert!(body.contains(value), "premise: the value is in the body");
        for (who, err) in both_errors(401, &body) {
            let text = rendered(&err);
            assert!(
                !text.contains(value) && !text.contains("sk-proj-") && !text.contains("request"),
                "{who}: error.request_id was read into the error: {text}"
            );
            // Positive control: the reason code beside it IS kept, so "absent" is not
            // "the error says nothing".
            assert!(text.contains("invalid_api_key"), "{who}: {text}");
        }
    }
}

#[test]
fn an_unlisted_reason_code_is_dropped_rather_than_echoed() {
    // The allowlist is of VALUES as well as fields: `error.code` is free text on the wire, and
    // only a code on the closed list may be repeated.
    let body = envelope(
        "bad",
        "invalid_request_error",
        "this_code_is_not_on_the_list",
        None,
        None,
    );
    for (who, err) in both_errors(400, &body) {
        let text = rendered(&err);
        assert!(
            !text.contains("this_code_is_not_on_the_list"),
            "{who}: an unlisted code was echoed: {text}"
        );
        assert!(
            err.to_string().contains("400"),
            "{who}: still names the status: {err}"
        );
    }
}

// ---------------------------------------------------------------------------
// 2 - A 2xx body that fails typed parsing must not echo the offending value either
// ---------------------------------------------------------------------------

#[test]
fn a_success_status_with_a_mistyped_field_does_not_echo_the_value() {
    // serde_json's type-mismatch text quotes the value it choked on. A 2xx body therefore leaks
    // exactly as a non-2xx one does, through `Malformed(e.to_string())`.
    let quota_body = format!(r#"{{"used":"{KEY_IN_MIDDLE}","limit":40,"resets_label":"Sep 1"}}"#);
    let generate_body = format!(
        r#"{{"draft":{{"title":"t","summary":null,"sections":[],"scriptures":[]}},
            "quota":{{"used":"{KEY_IN_MIDDLE}","limit":40,"resets_label":"Sep 1"}}}}"#
    );

    // CONTROL: serde_json itself really does quote the value. If a serde_json release stops
    // doing so, this fails loudly instead of the assertions below going vacuous.
    let raw = serde_json::from_str::<QuotaDto>(&quota_body)
        .unwrap_err()
        .to_string();
    assert!(
        raw.contains(KEY_IN_MIDDLE),
        "premise: serde_json no longer quotes the offending value ({raw}); this test is vacuous"
    );

    // The same control for the generate body, so the `generate_with_quota` site is not vacuous.
    let raw_generate = serde_json::from_str::<GenerateNotesResponse>(&generate_body)
        .unwrap_err()
        .to_string();
    assert!(
        raw_generate.contains(KEY_IN_MIDDLE),
        "premise: serde_json no longer quotes the offending value in the generate body \
         ({raw_generate}); the generate_with_quota half of this test is vacuous"
    );

    let from_quota = client(200, &quota_body)
        .fetch_quota(&consented())
        .unwrap_err();
    let from_generate = client(200, &generate_body)
        .generate_with_quota(&note_request())
        .unwrap_err();

    for (who, err) in [
        ("fetch_quota", from_quota),
        ("generate_with_quota", from_generate),
    ] {
        assert!(
            matches!(err, NoteError::Malformed(_)),
            "{who}: an unusable 2xx body is still Malformed: {err:?}"
        );
        assert_markers_absent(who, "2xx type mismatch", &err, &[KEY_IN_MIDDLE, "sk-proj-"]);
    }
}

// ---------------------------------------------------------------------------
// 3 - Two different 429s, and 402
// ---------------------------------------------------------------------------

fn run_generation(status: u16, body: &str) -> Result<GenerationOutcome, NoteError> {
    generate_sermon_notes(
        &config(),
        "the completed transcript",
        true,
        &client(status, body),
        &LocalNoteProvider::new(),
    )
}

/// Bodies that mean "the account is out of money" (terminal).
fn terminal_bodies() -> Vec<(&'static str, String)> {
    vec![
        (
            "captured 429 (type and code both terminal)",
            fixtures::ERR_429_NO_CREDITS.to_string(),
        ),
        (
            "type only: insufficient_quota",
            envelope("m", "insufficient_quota", "something_else", None, None),
        ),
        (
            "code only: credit_balance_exhausted",
            envelope("m", "other_type", "credit_balance_exhausted", None, None),
        ),
        (
            "code only: insufficient_quota",
            envelope("m", "other_type", "insufficient_quota", None, None),
        ),
        (
            "type only: credit_balance_exhausted",
            envelope("m", "credit_balance_exhausted", "other_code", None, None),
        ),
    ]
}

/// Bodies that mean "slow down" (transient), including shapes that are not an OpenAI envelope.
fn transient_bodies() -> Vec<(&'static str, String)> {
    vec![
        (
            "constructed rate limit",
            fixtures::ERR_429_RATE_LIMIT.to_string(),
        ),
        (
            "rate limit whose message carries a credential",
            envelope(
                &format!("Rate limit reached for {KEY_IN_MIDDLE}"),
                "requests",
                "rate_limit_exceeded",
                None,
                None,
            ),
        ),
        (
            "a rate limit whose FREE-TEXT message names both exhaustion codes (message is never read)",
            envelope(
                "Slow down. This is not insufficient_quota and not credit_balance_exhausted.",
                "requests",
                "rate_limit_exceeded",
                None,
                None,
            ),
        ),
        ("empty body", String::new()),
        ("plain text", "Too Many Requests".to_string()),
        (
            "JSON without an error object",
            r#"{"status":429}"#.to_string(),
        ),
        (
            "an unlisted type and code",
            envelope("m", "tokens", "tokens_per_min", None, None),
        ),
        (
            "an HTML page from an intermediary",
            "<html>429</html>".to_string(),
        ),
    ]
}

#[test]
fn a_terminal_429_is_quota_exceeded_and_propagates_with_no_local_fallback() {
    for (label, body) in terminal_bodies() {
        let err = run_generation(429, &body)
            .expect_err(&format!("{label}: terminal exhaustion must not fall back"));
        assert_eq!(err, NoteError::QuotaExceeded, "{label}");

        // fetch_quota has no fallback to speak of, but the classification must be the same.
        let q = client(429, &body).fetch_quota(&consented()).unwrap_err();
        assert_eq!(q, NoteError::QuotaExceeded, "{label} (fetch_quota)");
        let g = client(429, &body)
            .generate_with_quota(&note_request())
            .unwrap_err();
        assert_eq!(g, NoteError::QuotaExceeded, "{label} (generate_with_quota)");
    }
}

#[test]
fn a_transient_429_is_retryable_transport_and_still_yields_the_degraded_local_draft() {
    for (label, body) in transient_bodies() {
        // Through the orchestrator: the operator gets a draft, flagged degraded.
        let outcome = run_generation(429, &body).unwrap_or_else(|e| {
            panic!("{label}: a rate limit must not be a dead end, got error {e:?}")
        });
        assert!(
            outcome.degraded,
            "{label}: the draft must be flagged degraded"
        );
        assert_eq!(outcome.provider_label, "Local (offline)", "{label}");
        assert!(
            outcome.quota.is_none(),
            "{label}: a degraded draft invents no quota"
        );
        let text = format!("{outcome:?}");
        assert!(
            !text.contains("sk-proj-") && !text.contains(KEY_IN_MIDDLE),
            "{label}: the outcome's Debug carries provider material: {text}"
        );

        // And at the client: it is Transport, never QuotaExceeded, on both entry points.
        let g = client(429, &body)
            .generate_with_quota(&note_request())
            .unwrap_err();
        let q = client(429, &body).fetch_quota(&consented()).unwrap_err();
        for (who, err) in [("generate_with_quota", g), ("fetch_quota", q)] {
            assert!(
                matches!(err, NoteError::Transport(_)),
                "{label} / {who}: a transient 429 must be Transport, got {err:?}"
            );
            assert_ne!(err, NoteError::QuotaExceeded, "{label} / {who}");
            assert_markers_absent(who, label, &err, &[KEY_IN_MIDDLE, "sk-proj-"]);
            assert_no_body_text(who, label, &body, &err, ALLOWED_REASONS);
        }
    }
}

#[test]
fn the_two_429s_produce_different_outcomes_and_differ_only_in_the_payload() {
    // The defect itself: same status, same message, same envelope; only the code differs. If the
    // status alone decides, both land in the same place and this fails.
    let terminal = envelope(
        "You exceeded your current quota",
        "x",
        "insufficient_quota",
        None,
        None,
    );
    let transient = envelope(
        "You exceeded your current quota",
        "x",
        "rate_limit_exceeded",
        None,
        None,
    );
    assert_eq!(
        terminal.replace("insufficient_quota", "rate_limit_exceeded"),
        transient,
        "premise: the pair differs only in the field the mapping reads"
    );

    let a = run_generation(429, &terminal);
    let b = run_generation(429, &transient);
    assert_eq!(a, Err(NoteError::QuotaExceeded), "terminal 429");
    assert!(
        matches!(&b, Ok(o) if o.degraded),
        "transient 429 must give the degraded draft, got {b:?}"
    );
    assert_ne!(a, b, "the two 429s must not produce the same outcome");
}

#[test]
fn a_402_is_terminal_whatever_its_body_says() {
    let mut bodies = terminal_bodies();
    bodies.extend(transient_bodies());
    for (label, body) in bodies {
        let err = run_generation(402, &body)
            .expect_err(&format!("{label}: 402 is terminal and must not fall back"));
        assert_eq!(err, NoteError::QuotaExceeded, "{label}");
        for (who, e) in both_errors(402, &body) {
            assert_eq!(e, NoteError::QuotaExceeded, "{label} / {who}");
        }
    }
}

#[test]
fn a_5xx_still_falls_back_locally_and_other_statuses_are_not_quota() {
    for status in [500u16, 502, 503, 599] {
        let outcome = run_generation(status, fixtures::ERR_401_INVALID_KEY).unwrap();
        assert!(outcome.degraded, "status {status} should degrade locally");
    }
    // Only 402 and a terminal 429 are quota; an exhaustion code on any other status is not.
    for status in [400u16, 401, 403, 404, 418] {
        let err = run_generation(status, fixtures::ERR_429_NO_CREDITS)
            .expect_err("a non-2xx, non-5xx status is not a fallback case");
        assert_ne!(
            err,
            NoteError::QuotaExceeded,
            "status {status} must not be read as quota on the payload alone"
        );
    }
}

#[test]
fn each_note_error_variant_the_client_returns_is_still_produced_by_its_original_path() {
    // The operator's `note_error_code` (selahcue-operator/src/main.rs) maps FIVE variants to the
    // codes the frontend switches on: consent_required, not_configured, quota_exceeded,
    // transport and malformed. This crate cannot see that function, and this test does not claim
    // to: it pins that no variant was added or removed and that the paths which produced the
    // first four still produce them. The fifth (Malformed) is pinned by the 401 and
    // 2xx-mistyped tests above.
    let cfg = ProvidersConfig::default(); // consent OFF
    let c = client(200, "{}");
    assert_eq!(
        generate_sermon_notes(&cfg, "t", true, &c, &LocalNoteProvider::new()).unwrap_err(),
        NoteError::ConsentRequired
    );
    assert_eq!(
        SelahCueCloudClient::unconfigured(MockTransport::responding(200, "{}"))
            .fetch_quota(&consented())
            .unwrap_err(),
        NoteError::NotConfigured
    );
    assert_eq!(
        client(402, "").fetch_quota(&consented()).unwrap_err(),
        NoteError::QuotaExceeded
    );
    assert!(matches!(
        SelahCueCloudClient::new(MockTransport::failing(), BASE, Token::new("t"))
            .fetch_quota(&consented())
            .unwrap_err(),
        NoteError::Transport(_)
    ));
}

// ---------------------------------------------------------------------------
// 4 - The parse is bounded, and what is (and is not) read
// ---------------------------------------------------------------------------

// PREMISE, pinned at compile time so changing a bound cannot silently turn the tests below
// vacuous: the cap sits well under the transport's own response cap (else it bounds nothing) and
// well over any real envelope (else it would blind the client to a real one).
const _: () = assert!(MAX_ERROR_BODY_PARSE_BYTES < MAX_TRANSPORT_RESPONSE_BYTES);
const _: () = assert!(MAX_ERROR_BODY_PARSE_BYTES >= 8 * 1024);
const _: () = assert!(MAX_ERROR_BODY_PARSE_BYTES <= 64 * 1024);

/// A terminal-exhaustion 429 body padded to exactly `total` bytes with an inert string field.
fn terminal_body_of_len(total: usize) -> String {
    let head = r#"{"error":{"code":"insufficient_quota"},"pad":""#;
    let tail = r#""}"#;
    assert!(
        total >= head.len() + tail.len(),
        "premise: room for the envelope"
    );
    let body = format!(
        "{head}{}{tail}",
        "x".repeat(total - head.len() - tail.len())
    );
    assert_eq!(
        body.len(),
        total,
        "premise: the body is exactly the size asked for"
    );
    body
}

#[test]
fn a_terminal_429_exactly_at_the_parse_cap_still_parses_and_one_byte_over_reads_as_transient() {
    // The boundary, both sides. At the cap the body is parsed and the code is seen (positive
    // control: the mechanism is live, so "transient" below is the cap, not a dead parser).
    let at_cap = terminal_body_of_len(MAX_ERROR_BODY_PARSE_BYTES);
    assert_eq!(
        run_generation(429, &at_cap),
        Err(NoteError::QuotaExceeded),
        "a body exactly at the cap must still be parsed"
    );

    // One byte over: never parsed, so the terminal code is not seen and the 429 reads as
    // transient. Nothing from the body reaches the error.
    let over = terminal_body_of_len(MAX_ERROR_BODY_PARSE_BYTES + 1);
    let outcome = run_generation(429, &over)
        .expect("an over-cap 429 must be treated as transient and serve the local draft");
    assert!(outcome.degraded);
    for (who, err) in both_errors(429, &over) {
        assert!(matches!(err, NoteError::Transport(_)), "{who}: {err:?}");
        assert_no_body_text(who, "over-cap 429", &over, &err, ALLOWED_REASONS);
    }
}

#[test]
fn a_transport_cap_sized_body_is_refused_before_it_is_parsed() {
    // The bound the cap exists for: a hostile peer can send up to the transport's 4 MiB. The
    // literal size (not the constant) is used here so that RAISING the cap above it, or removing
    // it, makes the terminal code visible and fails this test. The body is a huge array, the
    // shape that makes a parsed tree proportional to the body.
    let size = 4 * 1024 * 1024;
    assert_eq!(
        size, MAX_TRANSPORT_RESPONSE_BYTES,
        "premise: this IS the transport cap"
    );
    let head = r#"{"error":{"code":"insufficient_quota"},"pad":["#;
    let tail = "0]}";
    let filler = "0,".repeat((size - head.len() - tail.len()) / 2);
    let body = format!("{head}{filler}{tail}");
    assert!(
        body.len() > size - 4 && body.len() <= size,
        "premise: the body is at the transport cap, got {}",
        body.len()
    );

    let outcome = run_generation(429, &body)
        .expect("a cap-sized 429 body must read as transient, not be parsed");
    assert!(outcome.degraded);
    // 402 is decided before any parse, so it is unaffected by the size.
    assert_eq!(run_generation(402, &body), Err(NoteError::QuotaExceeded));
}

#[test]
fn the_free_text_message_is_never_read_for_the_terminal_decision() {
    // A message that merely MENTIONS an exhaustion code (a rate-limit saying "this is not
    // insufficient_quota") must not read as terminal. Any `contains` over the raw body would.
    let body = envelope(
        "Slow down: this is not insufficient_quota and not credit_balance_exhausted",
        "requests",
        "rate_limit_exceeded",
        None,
        None,
    );
    let outcome = run_generation(429, &body).expect("a rate limit serves the local draft");
    assert!(outcome.degraded);
    // And the converse: a terminal CODE with a message that says nothing of it IS terminal.
    let body = envelope("Slow down", "x", "insufficient_quota", None, None);
    assert_eq!(run_generation(429, &body), Err(NoteError::QuotaExceeded));
}

/// A deeply nested body: `{"error":{"code":"insufficient_quota"},"pad":[[[...]]]}` with `depth`
/// levels of array nesting.
fn terminal_body_nested(depth: usize) -> String {
    format!(
        r#"{{"error":{{"code":"insufficient_quota"}},"pad":{}0{}}}"#,
        "[".repeat(depth),
        "]".repeat(depth)
    )
}

#[test]
fn hostile_shapes_read_as_transient_and_a_malformed_terminal_body_is_not_terminal() {
    // Each of these is a 429 whose body a naive reader might take for terminal. None is: the
    // client reads `error.code` / `error.type` as exact, case-sensitive JSON strings in a
    // well-formed object, and nothing else. (Each is also fed through the leak assertions.)
    let bom = char::from_u32(0xFEFF).unwrap();
    let bodies: Vec<(&str, String)> = vec![
        (
            "error is a string",
            r#"{"error":"insufficient_quota"}"#.to_string(),
        ),
        (
            "numeric code",
            r#"{"error":{"code":402,"type":"requests"}}"#.to_string(),
        ),
        (
            "null code and type",
            r#"{"error":{"code":null,"type":null}}"#.to_string(),
        ),
        (
            "array-valued code",
            r#"{"error":{"code":["insufficient_quota"]}}"#.to_string(),
        ),
        (
            "BOM-prefixed terminal body (serde_json refuses a BOM)",
            format!("{bom}{}", fixtures::ERR_429_NO_CREDITS),
        ),
        (
            "capitalised code",
            envelope("m", "x", "Insufficient_Quota", None, None),
        ),
        (
            "upper-case code",
            envelope("m", "x", "INSUFFICIENT_QUOTA", None, None),
        ),
        (
            "platform-API style code (UPPER_SNAKE vocabulary)",
            envelope("m", "x", "QUOTA_EXHAUSTED", None, None),
        ),
        (
            "leading whitespace in the code",
            envelope("m", "x", " insufficient_quota", None, None),
        ),
        (
            "trailing whitespace in the code",
            envelope("m", "x", "insufficient_quota ", None, None),
        ),
        (
            "trailing newline in the code",
            envelope("m", "x", "insufficient_quota\n", None, None),
        ),
        (
            "top-level array",
            format!("[{}]", fixtures::ERR_429_NO_CREDITS),
        ),
        ("top-level string", r#""insufficient_quota""#.to_string()),
        ("top-level null", "null".to_string()),
        (
            "the code only at the top level, not under error",
            r#"{"code":"insufficient_quota","type":"insufficient_quota"}"#.to_string(),
        ),
        (
            "terminal body nested past serde_json's 128-level recursion limit",
            terminal_body_nested(200),
        ),
    ];
    for (label, body) in &bodies {
        let outcome = run_generation(429, body)
            .unwrap_or_else(|e| panic!("{label}: must read as transient, got error {e:?}"));
        assert!(outcome.degraded, "{label}");
        for (who, err) in both_errors(429, body) {
            assert!(
                matches!(err, NoteError::Transport(_)),
                "{label} / {who}: {err:?}"
            );
        }
    }

    // POSITIVE CONTROL for the nesting case: well inside the limit the SAME body is terminal, so
    // the 200-level case above is the recursion limit and not a dead parser. serde_json allows
    // 128 levels; this documents that a terminal 429 nested past it reads as transient.
    assert_eq!(
        run_generation(429, &terminal_body_nested(100)),
        Err(NoteError::QuotaExceeded),
        "a terminal body nested 100 levels deep still parses"
    );
    // And the plain well-formed terminal body is terminal (the baseline for every case above).
    assert_eq!(
        run_generation(429, fixtures::ERR_429_NO_CREDITS),
        Err(NoteError::QuotaExceeded)
    );
}

#[test]
fn exhaustion_in_either_field_wins_whatever_the_other_field_says() {
    // The rule in `ErrorFields::parse`: "exhaustion in EITHER field wins". A body whose `code`
    // is a known non-terminal reason and whose `type` is terminal (or the reverse) is terminal.
    // A reader that takes the FIRST known reason by field order reads one of these as transient.
    let cases = [
        (
            "code=rate_limit_exceeded, type=insufficient_quota",
            "rate_limit_exceeded",
            "insufficient_quota",
        ),
        (
            "type=rate_limit_exceeded, code=insufficient_quota",
            "insufficient_quota",
            "rate_limit_exceeded",
        ),
        (
            "code=server_error, type=credit_balance_exhausted",
            "server_error",
            "credit_balance_exhausted",
        ),
        (
            "type=requests, code=credit_balance_exhausted",
            "credit_balance_exhausted",
            "requests",
        ),
    ];
    for (label, code, kind) in cases {
        let body = envelope("m", kind, code, None, None);
        assert_eq!(
            run_generation(429, &body),
            Err(NoteError::QuotaExceeded),
            "{label}: exhaustion in either field must win"
        );
    }
    // CONTROL: with neither field terminal, two known reasons are just transient.
    let body = envelope("m", "requests", "rate_limit_exceeded", None, None);
    assert!(run_generation(429, &body).unwrap().degraded);
}

#[test]
fn a_5xx_carrying_an_exhaustion_code_is_transport_by_design() {
    // INTENDED. A 5xx is the server's own failure and serves the local draft whatever its body
    // says. A service that wants an upstream provider's exhaustion to reach the operator as
    // quota must answer 402 (or a 429 with a code); a service that translates upstream
    // exhaustion into a 5xx gets the local fallback, which is what it should want. See the
    // "Error responses" note in `contract.rs`.
    for status in [500u16, 502, 503, 599] {
        for body in [
            fixtures::ERR_429_NO_CREDITS.to_string(),
            envelope("m", "x", "insufficient_quota", None, None),
        ] {
            let outcome = run_generation(status, &body)
                .unwrap_or_else(|e| panic!("status {status}: expected the local draft, got {e:?}"));
            assert!(outcome.degraded, "status {status}");
            for (who, err) in both_errors(status, &body) {
                assert!(
                    matches!(err, NoteError::Transport(_)),
                    "status {status} / {who}: {err:?}"
                );
            }
        }
    }
}
