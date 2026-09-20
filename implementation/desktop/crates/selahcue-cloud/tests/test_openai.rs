//! The OpenAI note provider (86akby7d8; FR-122/123/128/135).
//!
//! **Nothing here touches the network.** Every case runs against a stub transport: a
//! suite that needs a paid third party and a live connection is a suite that gets
//! skipped, and a skipped suite guards nothing.
//!
//! The four error bodies in [`fixtures`] are **verbatim captures from the live OpenAI
//! API on 2026-09-04**, not invented shapes. That matters most for the 401: its message
//! contains a partially masked copy of the key that was sent, and the test that asserts
//! we never leak it is only worth anything if it is fed the real thing.

#![cfg(feature = "openai")]
// Same convention as every other test file in this crate: a panic in a test IS the failure
// report, so `unwrap` is the right tool here even though the crate forbids it in `src/`.
#![allow(clippy::unwrap_used)]

use selahcue_cloud::openai::{
    bounded_transcript, direct_key_permitted, draft_schema, map_error_status, model_from_env,
    parse_draft, Bound, OpenAiNoteProvider, API_KEY_ENV, DEFAULT_MODEL, MAX_ITEM_CHARS,
    MAX_OUTPUT_TOKENS, MAX_PARSED_RESPONSE_BYTES, MAX_POINTS, MAX_SCRIPTURES, MAX_SECTION_ITEMS,
    MAX_SUB_POINTS, MAX_TRANSCRIPT_CHARS, MODEL_ENV, OUTLINE_HEADING, PROVIDER_LABEL,
};
use selahcue_cloud::transport::{HttpResponse, HttpTransport, TransportError};
use selahcue_cloud::{
    generate_sermon_notes, CloudNoteProvider, LocalNoteProvider, MockTransport, Token,
};
use selahcue_core::providers::{
    ConsentState, DraftCaveat, IncludeInNotes, NoteError, NoteProvider, NoteRequest, NotesTemplate,
    ProvidersConfig, ProvidersSettings, AI_GENERATED_LABEL, FABRICATION_DISCLOSURE,
};

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

mod fixtures {
    /// Verbatim from the live API, 2026-09-04. Note `sk-proj-` and the trailing `-key`
    /// survive the masking — this body is why `map_error_status` never echoes a body.
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

    /// Verbatim from the live API, 2026-09-04.
    pub const ERR_404_NO_MODEL: &str = r#"{
  "error": {
    "message": "The model `gpt-9-does-not-exist` does not exist or you do not have access to it.",
    "type": "invalid_request_error",
    "param": null,
    "code": "model_not_found"
  }
}"#;

    /// Verbatim from the live API, 2026-09-04.
    pub const ERR_400_MISSING_PARAM: &str = r#"{
  "error": {
    "message": "Missing required parameter: 'model'.",
    "type": "invalid_request_error",
    "param": "model",
    "code": "missing_required_parameter"
  }
}"#;

    /// A rate-limit 429. Documented shape; the account could not be made to emit one
    /// while it had no credits, so this is the one body here that is constructed rather
    /// than captured — and it is constructed to differ from the captured 429 in exactly
    /// the field the mapping reads.
    pub const ERR_429_RATE_LIMIT: &str = r#"{
  "error": {
    "message": "Rate limit reached for requests",
    "type": "requests",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}"#;
}

/// The fragment of the key that survives OpenAI's masking in the 401 body.
const LEAKED_KEY_FRAGMENT: &str = "sk-proj-********************-key";

// ---------------------------------------------------------------------------
// Test doubles
// ---------------------------------------------------------------------------

/// A transport that **fails the test if it is called at all**.
///
/// This is the whole strength of the consent assertion. Asserting `request_count() == 0`
/// on a recording transport proves nothing if the code under test never reached the
/// transport for some unrelated reason; a transport that panics on contact turns "no
/// network call" from a claim into something the test cannot pass without.
struct ForbiddenTransport;

impl HttpTransport for ForbiddenTransport {
    fn post_json(
        &self,
        url: &str,
        _body: &str,
        _bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        panic!("egress! a request left the device: POST {url} — the consent gate did not hold");
    }
    fn get(&self, url: &str, _bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        panic!("egress! a request left the device: GET {url} — the consent gate did not hold");
    }
}

/// Shares one `MockTransport` between the test and the provider, so the test can inspect
/// what was actually sent after the call. Same wrapper `test_client.rs` uses.
#[derive(Clone)]
struct ArcTransport(std::sync::Arc<MockTransport>);

impl HttpTransport for ArcTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        self.0.post_json(url, body, bearer)
    }
    fn get(&self, url: &str, bearer: Option<&str>) -> Result<HttpResponse, TransportError> {
        self.0.get(url, bearer)
    }
}

/// A model id that is deliberately **not** [`DEFAULT_MODEL`].
///
/// Constructing the test provider with the default made the model assertion weak: hard-coding
/// `"model": DEFAULT_MODEL` into the request body and ignoring `self.model` entirely passed,
/// because the expected and the accidental value were the same string. A sentinel separates
/// "the configured model reaches the wire" from "the default happens to be right".
const SENTINEL_MODEL: &str = "sentinel-model-not-the-default";

/// A provider over a shared, inspectable transport, plus the handle to inspect it.
fn inspectable_provider() -> (
    OpenAiNoteProvider<ArcTransport>,
    std::sync::Arc<MockTransport>,
) {
    let t = std::sync::Arc::new(MockTransport::responding(200, envelope(&full_draft_json())));
    let p = OpenAiNoteProvider::new(
        ArcTransport(t.clone()),
        Token::new("sk-test-not-a-real-key"),
        SENTINEL_MODEL,
    );
    (p, t)
}

fn envelope(draft_json: &str) -> String {
    serde_json::json!({
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": draft_json}]
        }]
    })
    .to_string()
}

/// A complete, well-formed draft with every FR-122 element and real sub-points.
fn full_draft_json() -> String {
    serde_json::json!({
        "title": "The Bread of Life",
        "main_scripture": "John 6:35",
        "supporting_scriptures": ["John 6:26", "Isaiah 55:1"],
        "introduction": ["Hunger that eating does not settle."],
        "points": [
            {"text": "The crowd came back for the wrong reason",
             "sub_points": ["They ate of the loaves and were filled", "A full church is not the same as a fed one"]},
            {"text": "Jesus does not shame the hunger",
             "sub_points": ["He redirects it rather than scolding it"]}
        ],
        "illustrations": ["The mill closed after nineteen years."],
        "quotes": ["I am the bread of life"],
        "prayer_points": ["For those out of work"],
        "calls_to_action": ["Come to him before anything else this week"],
        "key_lessons": ["The provision and the provider are the same"],
        "chapter_markers": ["Opening prayer", "First point"],
        "podcast_show_notes": [
            "Title: The Bread of Life",
            "Blurb: What it means to be fed by grace, not by our own striving.",
            "Key discussion point: the crowd came back for the wrong reason",
            "Scripture referenced: John 6:35"
        ],
        "short_description": ["A sermon on the bread of life and provision, from John 6."],
        "summary": "A sermon on provision and grace."
    })
    .to_string()
}

fn all_on() -> IncludeInNotes {
    IncludeInNotes {
        prayer_points: true,
        scripture_extraction: true,
        social_excerpts: true,
        chapter_markers: true,
        notable_quotations: true,
        short_summary: true,
        podcast_show_notes: true,
        short_description: true,
    }
}

fn config_with_consent(include: IncludeInNotes) -> ProvidersConfig {
    let defaults = ProvidersSettings::default();
    ProvidersConfig {
        consent: ConsentState {
            cloud_transcription: false,
            cloud_notes: true,
        },
        settings: ProvidersSettings {
            include,
            notes_template: NotesTemplate::FullOutlineWithScriptures,
            ..defaults
        },
    }
}

fn request_with(include: IncludeInNotes, transcript: &str) -> NoteRequest {
    config_with_consent(include)
        .build_note_request(transcript, true)
        .expect("consent is granted in this fixture")
}

fn provider(transport: MockTransport) -> OpenAiNoteProvider<MockTransport> {
    OpenAiNoteProvider::new(
        transport,
        Token::new("sk-test-not-a-real-key"),
        DEFAULT_MODEL,
    )
}

const TRANSCRIPT: &str = "Turn with me to John six. I am the bread of life. \
                          The mill closed after nineteen years.";

// ===========================================================================
// 1 · The consent gate — the most important assertion in this file
// ===========================================================================

#[test]
fn with_consent_off_generate_makes_no_network_call_and_says_consent_is_required() {
    let cfg = ProvidersConfig::default(); // cloud_notes consent is false by default
    assert!(
        !cfg.consent.cloud_notes,
        "premise: this test is only meaningful while consent defaults to OFF"
    );

    let cloud = OpenAiNoteProvider::new(
        ForbiddenTransport,
        Token::new("sk-test-not-a-real-key"),
        DEFAULT_MODEL,
    );
    let local = LocalNoteProvider::new();

    // ForbiddenTransport panics on contact, so reaching the network fails this test
    // outright rather than being caught by an assertion afterwards.
    let err = generate_sermon_notes(&cfg, TRANSCRIPT, true, &cloud, &local)
        .expect_err("consent is off — this must not produce a draft");
    assert_eq!(err, NoteError::ConsentRequired);
}

#[test]
fn without_an_explicit_generate_no_network_call_is_made_even_with_consent_granted() {
    let cfg = config_with_consent(IncludeInNotes::default());
    assert!(
        cfg.consent.cloud_notes,
        "premise: consent IS granted here, so the refusal below can only come from \
         the missing Generate press"
    );

    let cloud = OpenAiNoteProvider::new(
        ForbiddenTransport,
        Token::new("sk-test-not-a-real-key"),
        DEFAULT_MODEL,
    );
    let local = LocalNoteProvider::new();

    let err = generate_sermon_notes(&cfg, TRANSCRIPT, false, &cloud, &local)
        .expect_err("Generate was not pressed");
    assert_eq!(err, NoteError::ConsentRequired);
}

#[test]
fn build_note_request_is_the_only_way_to_reach_the_provider() {
    // Precise about what this proves. `NoteRequest`'s fields are public, so a caller
    // COULD hand-roll one — the guarantee is not type-level and it would be dishonest to
    // claim it is. What is guaranteed is that `build_note_request` is the only *producer*
    // in the codebase, that it refuses without consent + an explicit Generate, and that
    // the provider adds no second route to the network of its own: it implements
    // `NoteProvider` and is reached only through `generate_sermon_notes`, which calls the
    // gate first. The two halves are asserted below.
    let cfg = ProvidersConfig::default();
    for pressed in [true, false] {
        assert_eq!(
            cfg.build_note_request(TRANSCRIPT, pressed).unwrap_err(),
            NoteError::ConsentRequired,
            "no consent → no NoteRequest exists to hand a provider"
        );
    }

    // And a NoteRequest, however obtained, carries the transcript and nothing else that
    // could be audio. Asserted on the serialised body actually sent.
    let req = request_with(IncludeInNotes::default(), TRANSCRIPT);
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let (body, _) = p.build_body(&req);
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    let serialised = v.to_string();
    for forbidden in ["audio", "pcm", "wav", "samples", "waveform"] {
        assert!(
            !serialised.contains(forbidden),
            "the request body mentions {forbidden:?} — NoteRequest has no audio field \
             by construction and the body must not acquire one"
        );
    }
    assert!(
        serialised.contains("Sermon transcript"),
        "the body must actually carry the completed transcript"
    );
}

// ===========================================================================
// 1b · What actually leaves the machine
//
// The suite used to assert nothing about the outgoing request — it drove the transport
// and then only ever looked at what came back. Five separate mutations survived that
// gap: swapping the model, deleting `max_output_tokens`, flipping `strict` to false,
// dropping the bearer, and pointing at the wrong endpoint. Model identity is this
// change's headline verified fact, and nothing checked that the request names it.
//
// `MockTransport::recorded()` was there the whole time and `test_client.rs` already
// uses it exactly this way.
// ===========================================================================

/// The single recorded request, parsed. Fails loudly if egress did not happen at all,
/// so an assertion below can never pass vacuously against a transport that was skipped.
fn sole_request(t: &MockTransport) -> (selahcue_cloud::mock::RecordedRequest, serde_json::Value) {
    let recorded = t.recorded();
    assert_eq!(
        recorded.len(),
        1,
        "expected exactly one outgoing request, got {}",
        recorded.len()
    );
    let req = recorded[0].clone();
    let body: serde_json::Value =
        serde_json::from_str(&req.body).expect("the request body must be valid JSON");
    (req, body)
}

#[test]
fn the_outgoing_request_names_the_model_it_is_documented_to_use() {
    // `gpt-5.6-terra` is confirmed against the account and written into three documents.
    // Without this assertion, none of that reaches the wire.
    let (p, t) = inspectable_provider();
    p.generate(&request_with(all_on(), TRANSCRIPT)).unwrap();
    let (_req, body) = sole_request(&t);

    // Two separate claims, deliberately not conflated.
    //
    // (1) The CONFIGURED model reaches the wire. The sentinel differs from the default, so
    //     this fails if the body hard-codes a constant instead of reading `self.model`.
    assert_eq!(
        body["model"].as_str(),
        Some(SENTINEL_MODEL),
        "the request must ask for the model the provider was configured with"
    );
    assert_ne!(
        SENTINEL_MODEL, DEFAULT_MODEL,
        "premise: the sentinel must differ from the default, or the assertion above cannot \
         distinguish reading `self.model` from hard-coding the constant"
    );

    // (2) The DEFAULT is the model confirmed against the account and written into the docs.
    assert_eq!(
        DEFAULT_MODEL, "gpt-5.6-terra",
        "the documented model changed; update PROVIDER-TRADEOFFS.md and the openai.rs docs \
         in the SAME change"
    );

    // And the production constructor uses that default rather than anything else.
    let from_default = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    assert_eq!(from_default.model(), DEFAULT_MODEL);
}

#[test]
fn the_model_resolves_from_an_env_value_and_falls_back_to_the_default() {
    use selahcue_cloud::openai::{resolve_model, MAX_MODEL_LEN};

    // Absent and blank mean the same thing — deliberately one meaning for "unset", not two.
    for none_ish in [None, Some(""), Some("   "), Some("\t\n")] {
        assert_eq!(
            resolve_model(none_ish),
            DEFAULT_MODEL,
            "{none_ish:?} must fall back to the shipped default"
        );
    }

    // A supplied value is used verbatim, trimmed. This is what QA actually does.
    assert_eq!(resolve_model(Some("gpt-5.6-luna")), "gpt-5.6-luna");
    assert_eq!(resolve_model(Some("  gpt-5.6-luna  ")), "gpt-5.6-luna");

    // NOT validated against a known-model list: OpenAI's catalogue moves, and a stale allowlist
    // would reject a model the account can call. An unknown one is passed through and surfaces as
    // a visible 404 -> NotConfigured rather than a silent fallback.
    assert_eq!(
        resolve_model(Some("gpt-9-not-yet-invented")),
        "gpt-9-not-yet-invented"
    );

    // Bounded before it is stored, so an absurd `.env` line cannot become an unbounded field.
    let absurd = "m".repeat(MAX_MODEL_LEN * 10);
    assert_eq!(resolve_model(Some(&absurd)).chars().count(), MAX_MODEL_LEN);

    // PREMISE: the bound is above any real id, so it never bites in practice.
    assert!(DEFAULT_MODEL.chars().count() < MAX_MODEL_LEN);
}

#[test]
fn the_environment_actually_reaches_model_selection() {
    // Sana F-4. The chain is: environment -> model_from_env -> resolve_model -> request body.
    // The last two links were pinned; the FIRST was not. Mutating `model_from_env` to feed
    // `resolve_model(None)` — the env value ignored entirely — survived BOTH suites, because the
    // wire test drives `resolve_model(Some(..))`: the copy, not the path production takes.
    //
    // Under that mutation QA sets SELAHCUE_OPENAI_MODEL=gpt-5.6-luna, the loader exports it, terra
    // runs anyway, and nothing goes red — the exact silent no-op the standing rule cites as the
    // reason this name was admitted to the allowlist at all. The capability's whole justification
    // was unguarded.
    //
    // Only this test touches MODEL_ENV, and the lock keeps that true if another ever does.
    static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    let _guard = LOCK.lock().unwrap_or_else(|p| p.into_inner());

    std::env::set_var(MODEL_ENV, "sentinel-model-from-env");
    let got = model_from_env();
    std::env::remove_var(MODEL_ENV);

    assert_eq!(
        got, "sentinel-model-from-env",
        "SELAHCUE_OPENAI_MODEL was exported but ignored — QA switches models and silently gets \
         the default"
    );
    // POSITIVE CONTROL: with the variable unset it falls back, so the assertion above is not
    // satisfied by a function that returns its argument regardless.
    assert_eq!(model_from_env(), DEFAULT_MODEL);
    assert_ne!(
        "sentinel-model-from-env", DEFAULT_MODEL,
        "premise: the sentinel must differ from the default"
    );
}

// 86akcmzyq (Cody's High finding, PR #24): `from_env` read `API_KEY_ENV` with no profile check
// at all, so `cargo build --release --features openai-notes` — bypassing `make` and without
// `dev-keys` — built a working direct-to-OpenAI provider from whatever key happened to already
// be exported. `direct_key_permitted` closes that; these three tests prove it, the same shape
// as `dev_env.rs`'s `should_load_env_file` pair plus its own wiring test.

/// The pure predicate's release branch, tested directly since `cfg!(debug_assertions)` cannot be
/// varied within one compiled test binary.
#[test]
fn a_release_profile_input_refuses_the_direct_key() {
    assert!(
        !direct_key_permitted(false),
        "a release-profile (debug_assertions=false) input must refuse the direct developer key \
         — this is the guard standing between `--features openai-notes --release` and a shipped \
         binary that reads OPENAI_API_KEY from whatever happens to be exported"
    );
}

/// The positive control: an ordinary debug/test profile must still permit it, so "refuses" above
/// is the release branch actually firing rather than the predicate refusing unconditionally.
#[test]
fn a_debug_profile_input_still_permits_the_direct_key() {
    assert!(
        direct_key_permitted(true),
        "a debug-profile (debug_assertions=true) input was refused — openai-notes would stop \
         working in ordinary `cargo run`/`cargo test`, not just in --release"
    );
}

/// The wiring test: proves `from_env` ITSELF takes the branch this profile compiled, not just
/// that the extracted predicate above is correct in isolation. Mirrors `selahcue-operator`'s
/// `dev_env::load()` wiring test and `selahcue-licensing`'s `..._iff_it_is_a_debug_build`: one
/// test, run once per profile by `make ci`/CI (`cargo test -p selahcue-cloud --features openai`
/// and the `--release` sibling added alongside this fix), asserting whichever branch that
/// profile actually compiled. Only this test touches `API_KEY_ENV`; the lock keeps that true if
/// another ever does.
#[test]
fn from_env_permits_the_direct_key_iff_this_is_a_debug_build() {
    static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    let _guard = LOCK.lock().unwrap_or_else(|p| p.into_inner());

    std::env::set_var(API_KEY_ENV, "sk-proj-test-key");
    let built = OpenAiNoteProvider::from_env(MockTransport::responding(200, "{}"));
    std::env::remove_var(API_KEY_ENV);

    if cfg!(debug_assertions) {
        assert!(
            built.is_some(),
            "a debug build must build a provider from an exported OPENAI_API_KEY, or \
             openai-notes stops working in ordinary development"
        );
    } else {
        assert!(
            built.is_none(),
            "a RELEASE build built a working OpenAI provider from an exported OPENAI_API_KEY — \
             direct_key_permitted stopped being wired into from_env (inverted, hardcoded, or the \
             early return was removed)"
        );
    }
}

#[test]
fn an_env_supplied_model_reaches_the_request_body() {
    // R4 sentinel discipline, now that the model has two legitimate values: drive it BY VALUE so
    // hardcoding either one stays RED.
    for model in ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-9-not-yet-invented"] {
        let t = std::sync::Arc::new(MockTransport::responding(200, envelope(&full_draft_json())));
        let p = OpenAiNoteProvider::new(
            ArcTransport(t.clone()),
            Token::new("sk-test-not-a-real-key"),
            selahcue_cloud::openai::resolve_model(Some(model)),
        );
        p.generate(&request_with(all_on(), TRANSCRIPT)).unwrap();
        let (_req, body) = sole_request(&t);
        assert_eq!(
            body["model"].as_str(),
            Some(model),
            "the env-supplied model must reach the wire; QA cannot verify a switch otherwise"
        );
    }
}

#[test]
fn an_unknown_model_is_a_visible_terminal_state_not_a_silent_fallback() {
    // The failure QA will actually hit after a typo in `.env`. It must be told the model was
    // rejected, not quietly served worse notes by the offline scaffold.
    let cfg = config_with_consent(all_on());
    let err = generate_sermon_notes(
        &cfg,
        TRANSCRIPT,
        true,
        &provider(MockTransport::responding(404, fixtures::ERR_404_NO_MODEL)),
        &LocalNoteProvider::new(),
    )
    .expect_err("a rejected model must surface, not degrade");
    assert_eq!(
        err,
        NoteError::NotConfigured,
        "404 model_not_found must be terminal — falling back would hide a typo indefinitely"
    );
    // And it still does not echo the provider's body, which names the model.
    let rendered = format!("{err}  {err:?}");
    assert!(!rendered.contains("gpt-9-does-not-exist"), "{rendered}");
}

#[test]
fn the_outgoing_request_carries_auth_and_goes_to_the_responses_endpoint() {
    let (p, t) = inspectable_provider();
    p.generate(&request_with(all_on(), TRANSCRIPT)).unwrap();
    let (req, _body) = sole_request(&t);

    assert_eq!(req.method, "POST");
    assert!(
        req.had_bearer,
        "the request went out with NO Authorization header — it would 401 in production \
         and no other test in this file would notice"
    );
    assert_eq!(
        req.url, "https://api.openai.com/v1/responses",
        "the Responses API is not interchangeable with /v1/chat/completions: the request \
         shape (`input`, `text.format`, `max_output_tokens`) and the response shape \
         (`output[].content[]`) both differ, so a wrong endpoint fails at runtime only"
    );
}

#[test]
fn the_outgoing_request_pins_strict_structured_output_and_an_output_cap() {
    let (p, t) = inspectable_provider();
    p.generate(&request_with(all_on(), TRANSCRIPT)).unwrap();
    let (_req, body) = sole_request(&t);

    // `strict: true` is what makes the include-flags actually determine the response
    // shape. With it false the model may return whatever it likes, and the toggle
    // guarantee quietly degrades to a request rather than a contract.
    assert_eq!(
        body["text"]["format"]["strict"],
        serde_json::json!(true),
        "structured output must be STRICT, or the toggles stop being enforceable"
    );
    assert_eq!(
        body["text"]["format"]["type"],
        serde_json::json!("json_schema")
    );
    assert_eq!(
        body["text"]["format"]["name"],
        serde_json::json!("sermon_notes")
    );

    // Without an output cap a runaway generation bills and buffers without end.
    assert_eq!(
        body["max_output_tokens"].as_u64(),
        Some(u64::from(MAX_OUTPUT_TOKENS)),
        "the output cap must reach the wire"
    );

    // The schema on the wire is the one built from the operator's flags, not a stub.
    let props = body["text"]["format"]["schema"]["properties"]
        .as_object()
        .expect("the schema must carry properties");
    assert!(props.contains_key("points") && props.contains_key("prayer_points"));
}

#[test]
fn the_outgoing_request_carries_the_transcript_and_no_audio() {
    let (p, t) = inspectable_provider();
    p.generate(&request_with(all_on(), "the completed transcript text"))
        .unwrap();
    let (req, body) = sole_request(&t);

    assert!(
        req.body.contains("the completed transcript text"),
        "the request must carry the completed transcript"
    );
    // FR-132, asserted on the bytes that actually left rather than on the type.
    for forbidden in ["audio", "pcm", "wav", "waveform", "samples"] {
        assert!(
            !req.body.contains(forbidden),
            "the outgoing body mentions {forbidden:?}"
        );
    }
    let roles: Vec<&str> = body["input"]
        .as_array()
        .expect("input is an array")
        .iter()
        .filter_map(|m| m["role"].as_str())
        .collect();
    assert_eq!(roles, vec!["developer", "user"]);
}

// ===========================================================================
// 2 · FR-122 structure, including genuine sub-points
// ===========================================================================

#[test]
fn a_generated_draft_carries_every_fr122_element_the_toggles_ask_for() {
    let inc = all_on();
    let req = request_with(inc, TRANSCRIPT);
    let mut json: serde_json::Value = serde_json::from_str(&full_draft_json()).unwrap();
    json["social_excerpts"] = serde_json::json!(["A full church is not the same as a fed one"]);
    let p = provider(MockTransport::responding(200, envelope(&json.to_string())));

    let draft = p.generate(&req).expect("a well-formed response");

    assert_eq!(draft.title, "The Bread of Life");
    assert_eq!(
        draft.summary.as_deref(),
        Some("A sermon on provision and grace.")
    );
    assert_eq!(
        draft.scriptures,
        vec!["John 6:35", "John 6:26", "Isaiah 55:1"],
        "main scripture first, then supporting"
    );

    let headings: Vec<&str> = draft.sections.iter().map(|s| s.heading.as_str()).collect();
    for expected in [
        OUTLINE_HEADING,
        "Introduction",
        "Illustrations",
        "Notable quotations",
        "Prayer points",
        "Calls to action",
        "Key lessons",
        "Chapter markers",
        "Social excerpts",
        "Podcast show notes",
        "Short description",
    ] {
        assert!(
            headings.contains(&expected),
            "FR-122 element {expected:?} missing from the draft; got {headings:?}"
        );
    }
}

// ===========================================================================
// 3c · Podcast show notes / short description (86akgqdwc, FR-126)
// ===========================================================================

#[test]
fn podcast_show_notes_and_short_description_are_distinct_from_summary_and_social_excerpts() {
    // Structural/labelling distinctness, per the ticket's own acceptance bar — not prose
    // quality. Turn OFF short_summary and social_excerpts, turn ON only the two new
    // toggles, and confirm the two new artifacts still populate on their own fields.
    let mut inc = all_on();
    inc.short_summary = false;
    inc.social_excerpts = false;

    let req = request_with(inc, TRANSCRIPT);
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let draft = p.generate(&req).unwrap();

    assert_eq!(draft.summary, None, "short_summary was off");
    let headings: Vec<&str> = draft.sections.iter().map(|s| s.heading.as_str()).collect();
    assert!(
        !headings.contains(&"Social excerpts"),
        "social_excerpts was off"
    );
    // POSITIVE CONTROL + distinctness: both new artifacts are present, on their own
    // headings, with the content this fixture put under their own (distinct) JSON
    // fields — never merged into or read from `summary`/`social_excerpts`.
    let podcast = draft
        .sections
        .iter()
        .find(|s| s.heading == "Podcast show notes")
        .expect("Podcast show notes must be present when its own toggle is on");
    assert!(podcast.items().iter().any(|i| i.contains("Bread of Life")));
    let short_desc = draft
        .sections
        .iter()
        .find(|s| s.heading == "Short description")
        .expect("Short description must be present when its own toggle is on");
    assert!(short_desc.items().iter().any(|i| i.contains("provision")));
}

#[test]
fn the_podcast_prompt_never_asks_for_scripture_when_extraction_is_off() {
    // Security review finding (Sana F1 on PR #48): the podcast prompt clause used to ask
    // for "the scripture referenced" regardless of `scripture_extraction`, so a reference
    // could reach the one artifact meant for external publication with NO verification
    // pass ever run over it (`generate_sermon_notes` in main.rs only calls
    // `verify_scriptures` when `scripture_extraction` is on). Asserted on the actual
    // outgoing developer instruction, not on a private helper.
    let mut inc = all_on();
    inc.scripture_extraction = false;
    let req = request_with(inc, TRANSCRIPT);
    let (p, t) = inspectable_provider();
    p.generate(&req).unwrap();
    let (_req, body) = sole_request(&t);
    let developer_msg = body["input"]
        .as_array()
        .expect("input is an array")
        .iter()
        .find(|m| m["role"] == "developer")
        .and_then(|m| m["content"].as_str())
        .expect("a developer message with string content");

    assert!(
        developer_msg.contains("podcast_show_notes"),
        "premise: the podcast clause is still present at all"
    );
    assert!(
        !developer_msg
            .to_lowercase()
            .contains("scripture referenced"),
        "scripture_extraction is off, so the podcast clause must not ask for scripture \
         either — the draft can never verify it: {developer_msg}"
    );
}

#[test]
fn the_podcast_prompt_asks_for_scripture_when_extraction_is_also_on() {
    // POSITIVE CONTROL for the fix above: with `scripture_extraction` genuinely on (so
    // `verify_scriptures` WILL run over every section, including this one), the podcast
    // clause still asks for the scripture referenced — otherwise the fix above could have
    // been satisfied by deleting the clause outright rather than gating it correctly.
    let inc = all_on();
    assert!(inc.scripture_extraction, "premise: all_on() means all on");
    let req = request_with(inc, TRANSCRIPT);
    let (p, t) = inspectable_provider();
    p.generate(&req).unwrap();
    let (_req, body) = sole_request(&t);
    let developer_msg = body["input"]
        .as_array()
        .expect("input is an array")
        .iter()
        .find(|m| m["role"] == "developer")
        .and_then(|m| m["content"].as_str())
        .expect("a developer message with string content");

    assert!(
        developer_msg
            .to_lowercase()
            .contains("scripture referenced"),
        "scripture_extraction is on, so the podcast clause should still ask for the \
         scripture referenced: {developer_msg}"
    );
}

#[test]
fn podcast_show_notes_and_short_description_toggle_off_independently() {
    let mut inc = all_on();
    inc.podcast_show_notes = false;
    inc.short_description = false;

    let req = request_with(inc, TRANSCRIPT);
    // The response deliberately still contains both fields — layer two must drop them
    // anyway, the same "we did not ask is not a guarantee" rule every other toggle
    // already gets.
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let draft = p.generate(&req).unwrap();

    let headings: Vec<&str> = draft.sections.iter().map(|s| s.heading.as_str()).collect();
    for off in ["Podcast show notes", "Short description"] {
        assert!(
            !headings.contains(&off),
            "{off:?} was switched off but reached the draft; got {headings:?}"
        );
    }
    assert!(
        draft.caveats.is_empty(),
        "a section never requested must never carry a caveat; got {:?}",
        draft.caveats
    );

    // POSITIVE CONTROL: the schema itself never asked for either field.
    let schema = draft_schema(&inc);
    let props = schema["properties"].as_object().unwrap();
    assert!(!props.contains_key("podcast_show_notes"));
    assert!(!props.contains_key("short_description"));
    assert!(
        props.contains_key("quotes"),
        "premise: other enabled sections are still in the schema"
    );
}

#[test]
fn sub_points_are_subordinate_to_their_parent_point_and_not_flattened() {
    let req = request_with(all_on(), TRANSCRIPT);
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let draft = p.generate(&req).unwrap();

    let outline = draft
        .sections
        .iter()
        .find(|s| s.heading == OUTLINE_HEADING)
        .expect("the outline section must exist");

    // The hierarchy is a fact about the structure, not a rendering convention: sub-points
    // live INSIDE their parent point, and the flat `items` list is empty, so nothing
    // downstream can mistake a sub-point for a point.
    assert!(
        outline.items().is_empty(),
        "the outline must not ALSO flatten its points into `items` — that is exactly \
         the shortcut that makes the hierarchy unassertable"
    );
    assert_eq!(outline.points().len(), 2);
    assert_eq!(
        outline.points()[0].text,
        "The crowd came back for the wrong reason"
    );
    assert_eq!(
        outline.points()[0].sub_points,
        vec![
            "They ate of the loaves and were filled",
            "A full church is not the same as a fed one"
        ],
        "point 1's sub-points must be attached to point 1"
    );
    assert_eq!(
        outline.points()[1].sub_points,
        vec!["He redirects it rather than scolding it"],
        "point 2's sub-points must be attached to point 2, not merged with point 1's"
    );
    assert_eq!(outline.sub_point_count(), 3);
}

// ===========================================================================
// 3 · The include-flags actually gate the draft
// ===========================================================================

#[test]
fn a_section_the_operator_switched_off_does_not_appear_even_when_the_model_returns_it() {
    let mut inc = all_on();
    inc.prayer_points = false;
    inc.notable_quotations = false;
    inc.short_summary = false;
    inc.scripture_extraction = false;

    let req = request_with(inc, TRANSCRIPT);
    // The response DELIBERATELY contains every disabled section. Layer one (the schema)
    // never asked for them; this test is about layer two, which must drop them anyway —
    // "we did not ask" is not a guarantee about a third party's output.
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let draft = p.generate(&req).unwrap();

    let headings: Vec<&str> = draft.sections.iter().map(|s| s.heading.as_str()).collect();
    for off in ["Prayer points", "Notable quotations"] {
        assert!(
            !headings.contains(&off),
            "{off:?} was switched off but reached the draft; got {headings:?}"
        );
    }
    assert_eq!(draft.summary, None, "short_summary was off");
    assert!(
        draft.scriptures.is_empty(),
        "scripture_extraction was off, so no references may be extracted"
    );

    // POSITIVE CONTROL. Without this, "absent" is indistinguishable from a parser that
    // returns nothing at all, and the test above would pass against dead code.
    assert!(
        headings.contains(&"Illustrations") && headings.contains(&OUTLINE_HEADING),
        "the ungated sections must still be produced — otherwise the assertions above \
         prove only that parsing failed; got {headings:?}"
    );
}

#[test]
fn a_disabled_section_is_not_even_requested_in_the_schema() {
    let mut inc = all_on();
    inc.prayer_points = false;
    let schema = draft_schema(&inc);
    let props = schema["properties"].as_object().unwrap();

    assert!(
        !props.contains_key("prayer_points"),
        "a disabled section must not be asked for"
    );
    // Positive control: the schema is being built at all, and an ENABLED section is there.
    assert!(
        props.contains_key("quotes") && props.contains_key("points"),
        "enabled sections must be present — otherwise the assertion above passes on an \
         empty schema"
    );
    assert_eq!(
        schema["additionalProperties"],
        serde_json::json!(false),
        "strict mode requires additionalProperties:false, which is what stops the model \
         returning a section the toggles excluded"
    );
    let required: Vec<&str> = schema["required"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();
    assert!(!required.contains(&"prayer_points"));
    assert!(required.contains(&"points"));
}

// ===========================================================================
// 3b · Requested-but-empty sections carry a caveat, never silence (86akc0tua)
// ===========================================================================

/// [`full_draft_json`] with one or more top-level keys overridden — lets a test isolate
/// exactly the field(s) it wants empty/malformed while every other FR-122 element stays
/// populated, exactly as the reported live case did (only `chapter_markers` varied
/// between the two runs).
fn draft_json_with(overrides: serde_json::Value) -> String {
    let mut base: serde_json::Value = serde_json::from_str(&full_draft_json()).unwrap();
    let obj = base.as_object_mut().unwrap();
    for (k, v) in overrides.as_object().unwrap() {
        obj.insert(k.clone(), v.clone());
    }
    base.to_string()
}

#[test]
fn the_outline_is_flagged_requested_but_empty_when_points_comes_back_as_an_empty_array() {
    // The outline sits OUTSIDE the `FLAT_SECTIONS` loop — the ticket's own named risk is a
    // fix that only covers the loop and misses this, the most visible section on screen.
    let body = draft_json_with(serde_json::json!({ "points": [] }));
    let (draft, _log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    assert_eq!(
        draft.caveats,
        vec![DraftCaveat::SectionRequestedEmpty {
            heading: OUTLINE_HEADING.to_string()
        }],
    );
    // Positional control (Uma's design): the heading still appears in `sections`, empty,
    // in its natural place — never silently omitted.
    let outline = draft
        .sections
        .iter()
        .find(|s| s.heading == OUTLINE_HEADING)
        .expect("the outline heading must still appear, empty, not be omitted");
    assert!(outline.items().is_empty() && outline.points().is_empty());
}

#[test]
fn every_enabled_flat_section_is_flagged_requested_but_empty_when_it_comes_back_as_an_empty_array()
{
    // Table-driven over EVERY `FLAT_SECTIONS` field, not just the observed
    // `chapter_markers` case — the ticket's explicit bar for this criterion.
    for (field, heading) in [
        ("introduction", "Introduction"),
        ("illustrations", "Illustrations"),
        ("quotes", "Notable quotations"),
        ("prayer_points", "Prayer points"),
        ("calls_to_action", "Calls to action"),
        ("key_lessons", "Key lessons"),
        ("chapter_markers", "Chapter markers"),
        ("social_excerpts", "Social excerpts"),
        ("podcast_show_notes", "Podcast show notes"),
        ("short_description", "Short description"),
    ] {
        let body = draft_json_with(serde_json::json!({ field: [] }));
        let (draft, _log) = parse_draft(&envelope(&body), &all_on()).unwrap();
        assert!(
            draft.caveats.contains(&DraftCaveat::SectionRequestedEmpty {
                heading: heading.to_string()
            }),
            "{field} came back empty but was not flagged; caveats = {:?}",
            draft.caveats
        );
        let sec = draft
            .sections
            .iter()
            .find(|s| s.heading == heading)
            .unwrap_or_else(|| panic!("{heading} must still appear in sections, empty"));
        assert!(sec.items().is_empty());
    }
}

#[test]
fn summary_and_scriptures_are_flagged_requested_but_empty_too() {
    // Uma's Finding 2: two more drop sites behave identically and are gated on toggles
    // the operator really does switch on. Same wording covers all four unmodified.
    let body = draft_json_with(serde_json::json!({
        "summary": "",
        "main_scripture": "",
        "supporting_scriptures": [],
    }));
    let (draft, _log) = parse_draft(&envelope(&body), &all_on()).unwrap();
    assert_eq!(
        draft.summary, None,
        "premise: a blank summary is dropped as before"
    );
    assert!(
        draft.scriptures.is_empty(),
        "premise: nothing usable was extracted"
    );
    assert!(draft.caveats.contains(&DraftCaveat::SectionRequestedEmpty {
        heading: "Summary".to_string()
    }));
    assert!(draft.caveats.contains(&DraftCaveat::SectionRequestedEmpty {
        heading: "Scripture references".to_string()
    }));
}

#[test]
fn a_section_the_operator_switched_off_never_gets_a_caveat() {
    let mut inc = all_on();
    inc.chapter_markers = false;
    // A well-behaved model does not return a field the strict schema never asked for;
    // simulate that rather than testing the (already-covered) "model ignored the schema"
    // case here.
    let mut base: serde_json::Value = serde_json::from_str(&full_draft_json()).unwrap();
    base.as_object_mut().unwrap().remove("chapter_markers");
    let (draft, _log) = parse_draft(&envelope(&base.to_string()), &inc).unwrap();

    assert!(
        !draft.caveats.iter().any(|c| matches!(
            c,
            DraftCaveat::SectionRequestedEmpty { heading } if heading == "Chapter markers"
        )),
        "a section switched OFF must never carry a caveat — silence is the correct output"
    );
    assert!(!draft
        .sections
        .iter()
        .any(|s| s.heading == "Chapter markers"));
}

#[test]
fn a_degraded_local_fallback_carries_zero_caveats_even_though_its_placeholders_are_empty() {
    // Uma's Finding 3, promoted to its own acceptance criterion: `local.rs` deliberately
    // pushes empty placeholder sections for enabled toggles. A naive
    // "requested && empty -> caveat" computed generically over `sections` would fire on
    // every one of them, printing "nothing came back" directly beneath
    // `DEGRADED_FALLBACK_NOTICE`, which already explains the emptiness. This is exactly
    // the case the design (caveats populated ONLY in `openai.rs::parse_draft`, never in
    // `local.rs`) is built to make impossible without a special case.
    let cfg = config_with_consent(all_on());
    let local = LocalNoteProvider::new();
    let outcome = generate_sermon_notes(
        &cfg,
        TRANSCRIPT,
        true,
        &provider(MockTransport::failing()),
        &local,
    )
    .expect("a transport failure must serve the degraded local draft");
    assert!(outcome.degraded, "premise: this is the DEGRADED path");
    assert!(
        outcome.draft.caveats.is_empty(),
        "a degraded (offline scaffold) draft must never carry requested-but-empty caveats: {:?}",
        outcome.draft.caveats
    );
    // POSITIVE CONTROL: the scaffold really did push an empty placeholder for an enabled
    // toggle — otherwise the assertion above passes on dead code (no placeholders at all).
    assert!(
        outcome
            .draft
            .sections
            .iter()
            .any(|s| s.heading == "Prayer points" && s.items().is_empty()),
        "premise: the offline scaffold must still push its empty placeholder sections"
    );
}

#[test]
fn a_truncated_or_partial_response_is_never_read_as_legitimately_empty() {
    // Every field below is either MISSING or the WRONG type — the shape a response cut
    // off mid-stream, or garbled by a transport error, would actually take. None of this
    // may be read as "requested and legitimately empty": that reads a data problem as a
    // confirmed answer, which is the acceptance criterion this test guards.
    let body = serde_json::json!({
        "title": "Partial",
        "points": "not an array",  // wrong type
        "chapter_markers": null,   // present, not an array
        // "introduction" MISSING entirely, as if the body were cut off before it arrived
        "summary": 42,             // wrong type, not a string
        "main_scripture": null,    // wrong type
        // "supporting_scriptures" MISSING entirely
    })
    .to_string();
    let (draft, _log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    assert!(
        draft.caveats.is_empty(),
        "a malformed/partial response must never be read as confirmed-empty: {:?}",
        draft.caveats
    );
}

// ===========================================================================
// 4 · FR-123 / FR-128 — labelling, disclosure, and the untouched transcript
// ===========================================================================

#[test]
fn a_model_draft_is_labelled_ai_generated_and_carries_the_fabrication_disclosure() {
    let cfg = config_with_consent(all_on());
    let cloud = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let local = LocalNoteProvider::new();

    let outcome = generate_sermon_notes(&cfg, TRANSCRIPT, true, &cloud, &local).unwrap();

    assert_eq!(
        outcome.provider_label, PROVIDER_LABEL,
        "the provider is named"
    );
    assert!(outcome.ai_generated, "a model produced this draft");
    assert_eq!(
        outcome.disclosure,
        Some(FABRICATION_DISCLOSURE),
        "FR-128: the fabrication warning travels with the draft"
    );
    // The invariant, in the direction that matters: no AI draft without its disclosure.
    assert_eq!(outcome.disclosure.is_some(), outcome.ai_generated);
    assert!(
        FABRICATION_DISCLOSURE.contains("invent") && FABRICATION_DISCLOSURE.contains("Check"),
        "the disclosure must actually warn about fabrication and ask for review"
    );
    assert!(
        !AI_GENERATED_LABEL.is_empty(),
        "FR-123 requires a label to exist to attach"
    );
}

#[test]
fn the_offline_fallback_is_not_labelled_ai_generated() {
    // The other direction of the same invariant. The local scaffold slices sentences the
    // operator already has; calling it AI-generated would be a false statement on the one
    // screen whose job is being truthful.
    let cfg = config_with_consent(all_on());
    let cloud = provider(MockTransport::failing());
    let local = LocalNoteProvider::new();

    let outcome = generate_sermon_notes(&cfg, TRANSCRIPT, true, &cloud, &local).unwrap();

    assert!(outcome.degraded);
    assert!(!outcome.ai_generated, "the offline scaffold is not a model");
    assert_eq!(
        outcome.disclosure, None,
        "no fabrication warning on output that invents nothing"
    );
    assert_eq!(outcome.disclosure.is_some(), outcome.ai_generated);
}

// 86akgqdv0's companion to this test lives in
// `selahcue-data/tests/test_sermon_note_repo.rs`'s
// `generating_persisting_and_editing_a_draft_leaves_the_stored_transcript_byte_identical`
// — same invariant, proven at the PERSISTENCE layer once persisted drafts exist.
// It does not live here: this crate (`selahcue-cloud`) has no dependency on
// `selahcue-data` and gains none for this ticket (note generation and note
// persistence stay separate concerns), so this test below remains the pure
// in-memory half of the invariant — nothing here writes to or reads from a
// database.
#[test]
fn generation_and_draft_editing_leave_the_source_transcript_byte_identical() {
    let original = TRANSCRIPT.to_string();
    let before = original.clone();

    let cfg = config_with_consent(all_on());
    let cloud = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let local = LocalNoteProvider::new();

    let mut outcome = generate_sermon_notes(&cfg, &original, true, &cloud, &local).unwrap();
    assert_eq!(
        original.as_bytes(),
        before.as_bytes(),
        "FR-123: generating notes must not touch the transcript"
    );

    // Edit the draft the way an operator would.
    outcome.draft.title = "Edited by the operator".to_string();
    outcome.draft.sections.clear();
    outcome.draft.summary = Some("rewritten".to_string());

    assert_eq!(
        original.as_bytes(),
        before.as_bytes(),
        "FR-123: editing the draft must not write back into the transcript"
    );
    assert_eq!(original, TRANSCRIPT);
}

// ===========================================================================
// 5 · Error mapping — real bodies, and no key material anywhere
// ===========================================================================

#[test]
fn the_api_key_never_appears_in_an_error_a_draft_or_a_debug_rendering() {
    // The provider's OWN 401 body contains a masked-but-partly-clear copy of the key.
    // Anything that forwards a provider body into an error message leaks it.
    let err = map_error_status(401, fixtures::ERR_401_INVALID_KEY);
    let rendered = format!("{err}  {err:?}");
    assert!(
        !rendered.contains(LEAKED_KEY_FRAGMENT) && !rendered.contains("sk-proj-"),
        "the 401 body's key fragment reached the error: {rendered}"
    );
    assert_eq!(err, NoteError::NotConfigured);

    // The same property end to end, including the key we actually hold.
    let secret = "sk-proj-REALKEYMATERIAL-abcdef";
    let p = OpenAiNoteProvider::new(
        MockTransport::responding(401, fixtures::ERR_401_INVALID_KEY),
        Token::new(secret),
        DEFAULT_MODEL,
    );
    let req = request_with(all_on(), TRANSCRIPT);
    let e = p.generate(&req).unwrap_err();
    let rendered = format!("{e}  {e:?}");
    assert!(
        !rendered.contains(secret) && !rendered.contains("sk-proj-"),
        "key material reached the error rendering: {rendered}"
    );

    // The key belongs in the Authorization header and nowhere else — in particular not
    // in the request body.
    let (body, _) = p.build_body(&req);
    assert!(
        !body.contains(secret),
        "the API key was serialised into the request body"
    );

    // And a successful draft never carries it either.
    let p_ok = OpenAiNoteProvider::new(
        MockTransport::responding(200, envelope(&full_draft_json())),
        Token::new(secret),
        DEFAULT_MODEL,
    );
    let draft = p_ok.generate(&req).unwrap();
    assert!(
        !format!("{draft:?}").contains(secret),
        "key material reached the draft"
    );
}

#[test]
fn no_status_arm_anywhere_in_the_mapping_echoes_the_response_body() {
    // Sana, review round 2 (F-1). The no-echo property belongs to the WHOLE mapping, but the
    // tests pinned it only at the arms that happened to have a captured fixture — so echoing
    // the body in the `default` arm (and, at an earlier head, the 5xx arm) survived the entire
    // suite green. The doc on `map_error_status` claimed "never echoed"; the tests enforced it
    // where someone had thought to look.
    //
    // Feed the REAL 401 body — the one containing key material — to every arm, including the
    // ones that would never receive it in production. The property under test is "this function
    // does not echo bodies", not "these particular statuses do not".
    let body = fixtures::ERR_401_INVALID_KEY;

    // PREMISE: the fixture still carries the material whose absence every assertion
    // below claims to prove. Without this, re-capturing or tidying the fixture
    // silently turns the whole sweep vacuous.
    assert!(
        body.contains(LEAKED_KEY_FRAGMENT)
            && body.contains("sk-proj-")
            && body.contains("platform.openai.com"),
        "the 401 fixture no longer contains the leak markers; the sweep below would pass vacuously"
    );

    let statuses = [
        200, 301, 400, 401, 402, 403, 404, 418, 429, 500, 502, 503, 599,
    ];
    assert_eq!(
        statuses.len(),
        13,
        "premise: every arm of the match is covered"
    );

    for status in statuses {
        let err = map_error_status(status, body);
        let rendered = format!("{err}  {err:?}");
        assert!(
            !rendered.contains(LEAKED_KEY_FRAGMENT),
            "status {status} echoed the key fragment from the response body: {rendered}"
        );
        assert!(
            !rendered.contains("sk-proj-"),
            "status {status} echoed a key prefix: {rendered}"
        );
        assert!(
            !rendered.contains("platform.openai.com"),
            "status {status} echoed provider body text: {rendered}"
        );
    }

    // The control that used to sit here asserted `!map_error_status(418, body).to_string()
    // .is_empty()`. It was removed rather than kept, because it could not fail: `NoteError`'s
    // Display always prefixes its own wording, so `to_string()` is non-empty for every variant
    // and no mutation could redden it — gutting the `other` arm to `Malformed(String::new())`
    // passed the whole suite. It was added as a hedge against the sweep degenerating into
    // asserting emptiness, and that degeneration is unreachable, so it guarded nothing.
    //
    // The reachable vacuity is fixture drift, and the premise at the top of this function is
    // what catches it: stripping the markers from `ERR_401_INVALID_KEY` left all 31 tests green
    // while every absence assertion here exercised nothing.
    //
    // Replaced with a control that CAN fail. "Do not echo the body" is satisfiable by returning
    // nothing at all, and an error carrying no information is useless to the operator staring at
    // a failed generation. This pins the other half — our own wording is present and identifies
    // the status — and unlike its predecessor it reddens: gutting the arm to
    // `Malformed(String::new())` fails here.
    let rendered = map_error_status(418, body).to_string();
    assert!(
        rendered.contains("418"),
        "the mapping must say something of its own that identifies the failure, not merely \
         decline to quote the provider: {rendered:?}"
    );
}

#[test]
fn a_429_is_not_flattened_out_of_money_is_terminal_a_rate_limit_is_transient() {
    // OpenAI overloads 429. Mapping both to QuotaExceeded — as a bare `402 | 429` arm
    // would — turns a two-second throttle into "your monthly quota is exhausted".
    assert_eq!(
        map_error_status(429, fixtures::ERR_429_NO_CREDITS),
        NoteError::QuotaExceeded,
        "insufficient_quota is terminal and must be shown to the operator"
    );
    match map_error_status(429, fixtures::ERR_429_RATE_LIMIT) {
        NoteError::Transport(_) => {}
        other => {
            panic!("a rate-limit 429 must be transient so the local fallback runs, got {other:?}")
        }
    }
    // The two bodies differ ONLY in the field the mapping reads, so this pair fails if
    // the discrimination is removed and the status alone is used.
}

#[test]
fn misconfiguration_statuses_do_not_degrade_silently_to_the_local_scaffold() {
    // A wrong model id or a bad key must not look like a network blip: falling back
    // would serve worse notes indefinitely with nobody told why.
    assert_eq!(
        map_error_status(404, fixtures::ERR_404_NO_MODEL),
        NoteError::NotConfigured
    );
    assert_eq!(
        map_error_status(401, fixtures::ERR_401_INVALID_KEY),
        NoteError::NotConfigured
    );
    match map_error_status(400, fixtures::ERR_400_MISSING_PARAM) {
        NoteError::Malformed(m) => assert!(
            !m.contains("Missing required parameter"),
            "the provider's own message must not be echoed: {m}"
        ),
        other => panic!("400 should be Malformed, got {other:?}"),
    }
    match map_error_status(503, "upstream unavailable") {
        NoteError::Transport(_) => {}
        other => panic!("5xx must be transport so the fallback runs, got {other:?}"),
    }
}

#[test]
fn transport_failure_degrades_locally_while_not_configured_and_quota_propagate() {
    let cfg = config_with_consent(all_on());
    let local = LocalNoteProvider::new();

    let degraded = generate_sermon_notes(
        &cfg,
        TRANSCRIPT,
        true,
        &provider(MockTransport::failing()),
        &local,
    )
    .expect("a transport failure must serve the degraded local draft");
    assert!(degraded.degraded);
    assert_eq!(degraded.provider_label, "Local (offline)");

    let quota = generate_sermon_notes(
        &cfg,
        TRANSCRIPT,
        true,
        &provider(MockTransport::responding(429, fixtures::ERR_429_NO_CREDITS)),
        &local,
    )
    .expect_err("quota is an honest terminal state, not something to paper over");
    assert_eq!(quota, NoteError::QuotaExceeded);

    let unconfigured = generate_sermon_notes(
        &cfg,
        TRANSCRIPT,
        true,
        &provider(MockTransport::responding(
            401,
            fixtures::ERR_401_INVALID_KEY,
        )),
        &local,
    )
    .expect_err("a bad key must surface, not degrade");
    assert_eq!(unconfigured, NoteError::NotConfigured);

    // An empty key is refused before any request is issued.
    let no_key = OpenAiNoteProvider::new(ForbiddenTransport, Token::new(""), DEFAULT_MODEL);
    assert_eq!(
        no_key
            .generate_with_quota(&request_with(all_on(), TRANSCRIPT))
            .unwrap_err(),
        NoteError::NotConfigured
    );
}

#[test]
fn no_quota_is_ever_invented_from_a_successful_generation() {
    // There is no metering in this phase, so there is no number. The panel's honest
    // placeholder is the correct output and a fabricated "12 / 40" is the failure.
    let cfg = config_with_consent(all_on());
    let cloud = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let outcome =
        generate_sermon_notes(&cfg, TRANSCRIPT, true, &cloud, &LocalNoteProvider::new()).unwrap();
    assert!(!outcome.degraded, "premise: this is the SUCCESS path");
    assert_eq!(
        outcome.quota, None,
        "a successful generation must not manufacture a quota"
    );
}

// ===========================================================================
// 6 · Bounded memory
//
// Each test names ONE bound, asserts via the per-key accessor that THAT bound is what
// bit (before asserting the contract), and carries a positive control so "refused" is
// distinguishable from a dead mechanism.
// ===========================================================================

/// Compile-time premise: the fixtures below must actually exceed the caps they target.
/// If someone raises a cap past its fixture, this fails the build rather than letting
/// the test quietly stop exercising anything.
const HOSTILE_POINTS: usize = 100;
const HOSTILE_SUB_POINTS: usize = 100;
const HOSTILE_ITEMS: usize = 200;
const HOSTILE_SCRIPTURES: usize = 500;
const _: () = assert!(HOSTILE_POINTS > MAX_POINTS);
const _: () = assert!(HOSTILE_SUB_POINTS > MAX_SUB_POINTS);
const _: () = assert!(HOSTILE_ITEMS > MAX_SECTION_ITEMS);
const _: () = assert!(HOSTILE_SCRIPTURES > MAX_SCRIPTURES);

#[test]
fn an_oversized_transcript_is_bounded_before_it_is_sent() {
    let huge = "a".repeat(MAX_TRANSCRIPT_CHARS + 5_000);
    let (slice, dropped) = bounded_transcript(&huge);

    assert_eq!(
        dropped,
        Some(5_000),
        "the transcript bound must report exactly what it cut"
    );
    assert_eq!(slice.chars().count(), MAX_TRANSCRIPT_CHARS);

    // The bound reaches the wire: the request body carries the capped slice, not the
    // whole transcript.
    let req = request_with(all_on(), &huge);
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let (body, log) = p.build_body(&req);
    assert_eq!(
        log.clamped(Bound::TranscriptChars),
        Some(5_000),
        "the transcript bound is the one that bit"
    );
    assert!(
        body.len() < huge.len(),
        "the body must be smaller than the unbounded transcript"
    );

    // POSITIVE CONTROL: a normal transcript is passed through untouched and borrowed,
    // not copied — otherwise "bounded" would be indistinguishable from "always truncates".
    let (normal, none) = bounded_transcript(TRANSCRIPT);
    assert_eq!(none, None, "a normal transcript must not be clamped");
    assert_eq!(normal, TRANSCRIPT);
    assert!(
        std::ptr::eq(normal.as_ptr(), TRANSCRIPT.as_ptr()),
        "the unclamped path must borrow, not allocate a second copy of the transcript"
    );
}

#[test]
fn an_oversized_response_body_is_refused_before_it_is_parsed() {
    let huge = "x".repeat(MAX_PARSED_RESPONSE_BYTES + 1);
    let err = parse_draft(&huge, &all_on()).unwrap_err();
    match err {
        NoteError::Malformed(m) => assert!(m.contains("cap"), "{m}"),
        other => panic!("expected Malformed, got {other:?}"),
    }

    // POSITIVE CONTROL: a normal body parses. Without it, "refused" could be a parser
    // that refuses everything.
    let (draft, log) = parse_draft(&envelope(&full_draft_json()), &all_on()).unwrap();
    assert!(!draft.sections.is_empty());
    assert!(
        log.is_empty(),
        "a well-formed response must trip NO bound; got {log:?}"
    );
}

#[test]
fn the_point_count_is_bounded_and_the_point_bound_is_what_bit() {
    let points: Vec<serde_json::Value> = (0..HOSTILE_POINTS)
        .map(|i| serde_json::json!({"text": format!("point {i}"), "sub_points": []}))
        .collect();
    let body = serde_json::json!({"title": "t", "points": points}).to_string();

    let (draft, log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    // Assert the BOUND before the contract, naming what would otherwise go unexercised.
    assert_eq!(
        log.clamped(Bound::Points),
        Some(HOSTILE_POINTS - MAX_POINTS),
        "the point-count bound was not exercised — this test proves nothing without it"
    );
    assert!(
        log.clamped(Bound::SubPoints).is_none(),
        "no sub-point was supplied, so that bound must NOT have fired — a per-key \
         accessor is the only way to tell these apart"
    );

    let outline = draft
        .sections
        .iter()
        .find(|s| s.heading == OUTLINE_HEADING)
        .expect("outline present");
    // Assert the ENTITY — the number of points retained — not a proxy for its size.
    assert_eq!(outline.points().len(), MAX_POINTS);
}

#[test]
fn the_sub_point_count_is_bounded_per_point() {
    let subs: Vec<String> = (0..HOSTILE_SUB_POINTS)
        .map(|i| format!("sub {i}"))
        .collect();
    let body = serde_json::json!({
        "title": "t",
        "points": [
            {"text": "one", "sub_points": subs},
            {"text": "two", "sub_points": ["only one here"]}
        ]
    })
    .to_string();

    let (draft, log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    assert_eq!(
        log.clamped(Bound::SubPoints),
        Some(HOSTILE_SUB_POINTS - MAX_SUB_POINTS),
        "the sub-point bound was not exercised"
    );
    assert!(
        log.clamped(Bound::Points).is_none(),
        "two points is under the point cap, so THAT bound must not have fired"
    );

    let outline = &draft.sections[0];
    assert_eq!(outline.points()[0].sub_points.len(), MAX_SUB_POINTS);
    // POSITIVE CONTROL: the well-behaved sibling point keeps all of its sub-points, so
    // the cap is a cap and not a blanket truncation.
    assert_eq!(outline.points()[1].sub_points.len(), 1);
    assert_eq!(outline.sub_point_count(), MAX_SUB_POINTS + 1);
}

#[test]
fn flat_section_entries_and_scriptures_are_bounded_by_count() {
    let items: Vec<String> = (0..HOSTILE_ITEMS).map(|i| format!("item {i}")).collect();
    let scriptures: Vec<String> = (0..HOSTILE_SCRIPTURES)
        .map(|i| format!("John {i}:1"))
        .collect();
    let body = serde_json::json!({
        "title": "t",
        "main_scripture": "John 6:35",
        "supporting_scriptures": scriptures,
        "prayer_points": items,
        "illustrations": ["just the one"]
    })
    .to_string();

    let (draft, log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    assert_eq!(
        log.clamped(Bound::SectionItems),
        Some(HOSTILE_ITEMS - MAX_SECTION_ITEMS),
        "the section-item bound was not exercised"
    );
    assert!(
        log.clamped(Bound::Scriptures).is_some(),
        "the scripture bound was not exercised"
    );

    let prayer = draft
        .sections
        .iter()
        .find(|s| s.heading == "Prayer points")
        .unwrap();
    assert_eq!(prayer.items().len(), MAX_SECTION_ITEMS);
    assert_eq!(draft.scriptures.len(), MAX_SCRIPTURES);

    // POSITIVE CONTROL: a small sibling section is untouched.
    let illus = draft
        .sections
        .iter()
        .find(|s| s.heading == "Illustrations")
        .unwrap();
    assert_eq!(illus.items(), ["just the one"]);
}

#[test]
fn a_single_enormous_entry_is_bounded_by_length() {
    let giant = "z".repeat(MAX_ITEM_CHARS + 777);
    let body = serde_json::json!({
        "title": "t",
        "points": [{"text": giant.clone(), "sub_points": ["short"]}],
        "illustrations": ["short one"]
    })
    .to_string();

    let (draft, log) = parse_draft(&envelope(&body), &all_on()).unwrap();

    assert_eq!(
        log.clamped(Bound::ItemChars),
        Some(777),
        "the per-entry character bound was not exercised"
    );
    assert!(
        log.clamped(Bound::Points).is_none() && log.clamped(Bound::SectionItems).is_none(),
        "only ONE entry was oversized; the count bounds must not have fired"
    );
    assert_eq!(
        draft.sections[0].points()[0].text.chars().count(),
        MAX_ITEM_CHARS
    );
    // POSITIVE CONTROL: a short sibling entry survives whole.
    assert_eq!(draft.sections[0].points()[0].sub_points, ["short"]);
}

#[test]
fn a_hostile_response_can_trip_at_most_one_entry_per_bound() {
    // The clamp log merges by key, so its storage is bounded by the number of bounds
    // however many times each is hit — it cannot itself become the unbounded thing.
    let items: Vec<String> = (0..HOSTILE_ITEMS).map(|i| format!("item {i}")).collect();
    let body = serde_json::json!({
        "title": "t",
        "prayer_points": items.clone(),
        "illustrations": items.clone(),
        "key_lessons": items,
    })
    .to_string();
    let (_draft, log) = parse_draft(&envelope(&body), &all_on()).unwrap();
    assert_eq!(
        log.len(),
        1,
        "three separate sections overflowed the SAME bound; the log must hold one \
         merged entry, not three"
    );
    assert_eq!(
        log.clamped(Bound::SectionItems),
        Some(3 * (HOSTILE_ITEMS - MAX_SECTION_ITEMS)),
        "and the merged count must be the sum"
    );
}

// ===========================================================================
// 7 · Malformed and hostile responses degrade instead of panicking
// ===========================================================================

#[test]
fn every_section_is_a_flat_list_or_an_outline_and_never_both() {
    // The union is enforced structurally — `items` and `points` are private and the only
    // constructors populate one and empty the other — so this cannot fail today. It is here
    // because "cannot fail today" is a property of the current constructor set, and the cheap
    // way to notice a third constructor that breaks it is to assert the invariant on real output
    // rather than to trust that nobody adds one.
    let req = request_with(all_on(), TRANSCRIPT);
    let p = provider(MockTransport::responding(200, envelope(&full_draft_json())));
    let draft = p.generate(&req).unwrap();

    let mut saw_outline = false;
    let mut saw_flat = false;
    for s in &draft.sections {
        let flat = !s.items().is_empty();
        let outline = !s.points().is_empty();
        assert!(
            flat != outline,
            "section {:?} is both a flat list and an outline (or neither): {} items, {} points",
            s.heading,
            s.items().len(),
            s.points().len()
        );
        saw_outline |= outline;
        saw_flat |= flat;
    }
    // POSITIVE CONTROL: both kinds actually occurred, so the loop above was not vacuously
    // satisfied by a draft that happened to contain only one shape — or none.
    assert!(
        saw_outline && saw_flat,
        "this draft must contain BOTH an outline section and flat sections, or the invariant \
         above was never really exercised"
    );
}

#[test]
fn malformed_responses_never_panic_and_map_to_malformed() {
    for body in [
        "",
        "not json at all",
        "{}",
        r#"{"output": []}"#,
        r#"{"output": [{"content": []}]}"#,
        r#"{"output": [{"content": [{"type": "output_text", "text": "not json"}]}]}"#,
        r#"{"output": [{"content": [{"type": "output_text"}]}]}"#,
    ] {
        match parse_draft(body, &all_on()) {
            Err(NoteError::Malformed(_)) => {}
            other => panic!("body {body:?} should be Malformed, got {other:?}"),
        }
    }
}

#[test]
fn a_model_refusal_becomes_our_wording_not_the_providers() {
    let body = serde_json::json!({
        "output": [{"content": [{"type": "refusal", "refusal": "I can't help with that request about XYZ"}]}]
    })
    .to_string();
    match parse_draft(&body, &all_on()) {
        Err(NoteError::Malformed(m)) => {
            assert!(
                !m.contains("XYZ"),
                "the provider's refusal text was echoed: {m}"
            );
            assert!(m.contains("declined"));
        }
        other => panic!("expected Malformed, got {other:?}"),
    }
}

#[test]
fn wrong_types_and_missing_fields_degrade_to_empty_rather_than_failing() {
    let body = serde_json::json!({
        "title": 42,
        "points": "not an array",
        "illustrations": [1, 2, {"nested": true}],
        "prayer_points": null
    })
    .to_string();
    let (draft, _log) = parse_draft(&envelope(&body), &all_on()).unwrap();
    assert_eq!(draft.title, "Sermon notes", "a non-string title falls back");

    // `points` (wrong type: a string) and `prayer_points` (wrong type: null) are neither
    // arrays — 86akc0tua's guard reads that as a malformed/truncated field, not a
    // confirmed answer, so both stay silently absent exactly as before this ticket.
    assert!(
        !draft.sections.iter().any(|s| s.heading == OUTLINE_HEADING),
        "a wrong-typed points field must not be faked into an outline"
    );
    assert!(
        !draft.sections.iter().any(|s| s.heading == "Prayer points"),
        "a wrong-typed (null) field must not be faked into a section, and must not be \
         read as a confirmed empty answer either"
    );

    // `illustrations` IS well-typed (a JSON array) — the model returned something, just
    // nothing usable came out of it after filtering non-string entries. 86akc0tua treats
    // this the same as a genuinely empty array: a real, empty answer, not a data problem.
    // This is the ticket's own fix in action — before it, this section vanished with no
    // trace; now the operator sees it, empty, exactly where it belongs.
    let illustrations = draft
        .sections
        .iter()
        .find(|s| s.heading == "Illustrations")
        .expect("a well-typed-but-unusable array is a real empty answer, not dropped silently");
    assert!(illustrations.items().is_empty());
    assert_eq!(
        draft.caveats,
        vec![DraftCaveat::SectionRequestedEmpty {
            heading: "Illustrations".to_string()
        }],
        "illustrations is the only field here that is well-typed AND empty; points and \
         prayer_points are wrong-typed, not legitimate empty answers"
    );
}
