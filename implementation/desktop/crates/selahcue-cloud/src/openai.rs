//! Sermon-note generation from OpenAI GPT, direct from the desktop, behind a
//! **developer key** (R3; FR-122/123/128/135).
//!
//! # This is a throwaway posture, deliberately
//!
//! **The shipping path keeps note generation proxied through the SelahCue platform
//! API.** A desktop that talks to OpenAI directly needs the provider key on the
//! operator's machine, which means the key is as trustworthy as the least-locked-down
//! church laptop, cannot be rotated centrally, cannot be metered per account, and
//! cannot be revoked for one church without revoking it for all of them. None of that
//! is acceptable in a shipped product, and none of it is being fixed here.
//!
//! What this module buys is the ability to build and judge the *note quality* now,
//! against a real model, without waiting for the hosted service to exist. The
//! [`crate::client::SelahCueCloudClient`] beside it remains the destination; when the
//! hosted proxy lands, this module's prompt, schema and bounded parser move behind it
//! essentially unchanged and the direct path is deleted. Treat every use of
//! `OPENAI_API_KEY` here as scaffolding with a demolition date.
//!
//! # What is NOT relaxed
//!
//! The egress choke point is untouched. Nothing reaches this module that
//! [`selahcue_core::providers::ProvidersConfig::build_note_request`] did not build,
//! which means cloud-notes consent is set and Generate was actually pressed, and the
//! request carries the **completed transcript only** — there is no audio field to
//! populate. This module adds no second path to the network: it implements
//! [`NoteProvider`] and is reachable only through
//! [`crate::generate_sermon_notes`], exactly like the hosted client.
//!
//! # Disclosure
//!
//! Drafts from here are model output. [`NoteProvider::is_generative`] is `true`, so the
//! draft carries [`selahcue_core::providers::AI_GENERATED_LABEL`] and the
//! [`selahcue_core::providers::FABRICATION_DISCLOSURE`] (FR-123/128). The disclosure
//! speaks only to *accuracy* — what a language model gets wrong. It says nothing about
//! retention or data processing, because those claims need the DPA work behind them
//! (86akby942) and an unbacked promise is worse than silence.
//!
//! # Evidence for the wire format
//!
//! Request and response shapes, the `text.format` structured-output nesting, the
//! `max_output_tokens` parameter, and every error body this module maps were taken
//! from the live API on 2026-09-04 — the four error responses are reproduced verbatim
//! in `tests/test_openai.rs` rather than invented.

use crate::transport::HttpTransport;
use crate::CloudNoteProvider;
use selahcue_core::providers::{
    IncludeInNotes, NoteDraft, NoteError, NoteOptions, NotePoint, NoteProvider, NoteRequest,
    NoteSection, NotesTemplate, Quota,
};

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// The provider label shown for honest disclosure (FR-132: the disclosure names the
/// provider). This is the string the Providers & Privacy panel renders — the panel used
/// to say "SelahCue AI", which stops being true the moment this module serves a draft.
pub const PROVIDER_LABEL: &str = "OpenAI";

/// Machine-readable provider kind for the operator view (`notes_provider.kind`).
pub const PROVIDER_KIND: &str = "openai";

/// The environment variable overriding [`DEFAULT_MODEL`], so physical QA can switch model without
/// a rebuild. Read as a string literal for the same reason as [`API_KEY_ENV`].
///
/// **Not a credential**, which is the entire basis on which the loader's allowlist was widened to
/// carry it. Absent or blank means "use the default" — deliberately one meaning, not two: the
/// loader already leaves a blank value unset, so `env::var` reports `NotPresent` either way and
/// nothing here needs to distinguish them.
pub const MODEL_ENV: &str = "SELAHCUE_OPENAI_MODEL";

/// Upper bound on an env-supplied model id.
///
/// The same reasoning as `MAX_TRANSLATION_CODE_LEN` in the core: a value that arrives from outside
/// the binary is bounded before it is stored, so a wire-legal but absurd `.env` line cannot become
/// unbounded memory or an unbounded request field. Real ids are well under this — `gpt-5.6-terra`
/// is 13 characters — so the bound never bites in practice, which is exactly the shape a bound
/// should have.
pub const MAX_MODEL_LEN: usize = 64;

/// The environment variable carrying the developer key. Read as a **string literal**
/// rather than importing the operator's `dev_env::OPENAI_API_KEY` const: that const is
/// `#[cfg(any(feature = "dev-keys", test))]`, and depending on it would drag this crate
/// into another crate's feature gating for no gain. One variable name is the whole of
/// this module's coupling to the `.env` loader (86akby6yy), which is itself scaffolding.
pub const API_KEY_ENV: &str = "OPENAI_API_KEY";

/// Whether this build profile is permitted to source the developer key from the process
/// environment **at all**.
///
/// A pure predicate over an injected `debug_assertions` value, for the same reason
/// `selahcue-operator`'s `dev_env::should_load_env_file` is one: `cfg!(debug_assertions)` is
/// fixed for the whole lifetime of one compiled test binary, so a test that only calls
/// [`OpenAiNoteProvider::from_env`] observes whichever profile `cargo test` happened to run in
/// and can never reach the other branch. Taking the profile as a parameter makes both branches
/// reachable, so a test can assert the release-profile refusal directly rather than trusting
/// that a `!` somewhere was typed the right way round.
///
/// # The gap this closes (86akcmzyq / 86akcmzrd, Cody's High finding on PR #24)
///
/// `dev_env::load()` already refuses to read the repo-root `.env` in a release profile, even
/// when `dev-keys` is compiled in — closing the `cargo build --release --features dev-keys`
/// bypass of the Makefile's `release-ai-guard`. But [`OpenAiNoteProvider::from_env`] reads
/// [`API_KEY_ENV`] straight from the process environment regardless of whether `dev-keys` put it
/// there, and until this predicate existed had **no equivalent check anywhere**: a
/// `cargo build --release --features openai-notes` — `openai-notes` alone, no `dev-keys` at all,
/// bypassing `make` entirely — produced a fully working direct-to-OpenAI release binary
/// whenever `OPENAI_API_KEY` happened to already be exported in the shell, which is
/// unremarkable on a developer or IT-managed machine that also runs OpenAI's own CLI. This
/// predicate makes that release build refuse the same way `dev_env::load()` does, so the claim
/// "the release boundary holds through make or a bare cargo build" (CLAUDE.md) is true for BOTH
/// features 86akcmzrd pairs together, not just `dev-keys`.
///
/// # Stated limit, same as `dev_env::should_load_env_file` and `selahcue-licensing`'s analogous
/// development-entitlement-key guard
///
/// An explicit `[profile.release] debug-assertions = true`, or a `RUSTFLAGS` override, turns
/// `cfg!(debug_assertions)` back on under `--release` and defeats this exactly as it defeats
/// those two — nothing in-repo can observe either. This narrows the gap; it does not close every
/// route through it. `scripts/installer_secret_scan.py` (86akc041v) is the independent,
/// byte-level backstop on artefacts this repo actually ships.
pub fn direct_key_permitted(debug_assertions: bool) -> bool {
    debug_assertions
}

/// The default model.
///
/// **Confirmed callable on the owner's account** via `GET /v1/models` on 2026-09-04
/// (HTTP 200, 118 models), not inferred from documentation — `gpt-6-astra` is in the
/// public docs but is *not* on this account, which is exactly why the account is the
/// authority here.
///
/// Why the middle tier of the current family, and not the cheap one: for a ~45-minute
/// sermon (~9,300 input tokens, ~2,500 output) the run costs roughly **$0.05** on
/// `gpt-5.6-terra` against **$0.005** on `gpt-5.6-luna` — about $2.50 a year versus 26
/// cents for a church generating notes weekly. At that scale cost is not a real axis,
/// and the task *is* the axis: FR-122 asks for a full hierarchical outline reasoned
/// over an hour of speech, and `docs/research/PROVIDER-TRADEOFFS.md` records that
/// cheaper tiers are "good for simple summarization" while structure and long-context
/// reasoning are where the better models actually separate. Paying two dollars a year
/// to be on the right side of that is not a trade worth agonising over.
///
/// **Benchmarked against `gpt-5.6-luna` on real output, 2026-09-04** — on **one 1,431-word
/// sermon, one run each**, through this exact prompt and schema. That is enough to confirm a
/// default and **not** enough to call it a general result; treat it as the reason the default
/// is what it is, not as a measurement of either model.
///
/// Structurally the two tied: both returned 4 points, 13 sub-points and all 8 enabled sections,
/// both honoured the disabled `social_excerpts` toggle, and every scripture reference either
/// produced verified against the bundled KJV. Terra won on the thing that matters for
/// presentation: its point headings are short, slide-usable lines with the reference appended
/// consistently, whereas luna returned **manually numbered** headings ("1. ", "2. ") — which
/// render as "1. 1." inside an ordered list — and packed each point's explanation into its
/// heading, blurring the very point / sub-point separation FR-122 asks for. Luna was faster
/// (14.6s vs 17.8s) and is 10× cheaper, so it is a real option if cost ever becomes an axis;
/// on this evidence terra is the better default and the original reasoning holds.
///
/// **Section population is not deterministic, and the "all 8 sections" figure above is one
/// run.** An *earlier* terra run on the same transcript with the same flags returned an empty
/// `chapter_markers` despite the toggle being on, and the empty section was dropped — so that
/// run produced 7. Quoting only the clean run would overstate what was observed. This is not a
/// correctness bug (an empty section is correctly not rendered) but it does mean "the toggles
/// asked for it" and "the draft contains it" are different statements. Tracked as 86akc0tua.
///
/// # The default, and how it is overridden
///
/// This is the **default**, not the only possibility: [`MODEL_ENV`] overrides it, so physical QA
/// can switch between tiers without a rebuild.
///
/// That override was originally rejected here, and the reasoning is worth keeping because it was
/// right at the time: the `.env` loader (86akby6yy) allowlisted exactly two names and discarded
/// every other assignment, so `SELAHCUE_OPENAI_MODEL` in `.env` would have been read and thrown
/// away — a silent no-op looking exactly like success, which is the worst possible outcome for a
/// QA operator with no way to tell the difference. The conclusion drawn was "do not offer it".
///
/// The owner then asked for it, so **the footgun was fixed rather than avoided**: the allowlist
/// was widened to admit this one name, deliberately and under security review, and it is the only
/// entry there that is not a credential. `selahcue-operator/src/dev_env.rs` carries the standing
/// rule for that list — categorically no further credential names, and no numeric cap because a
/// maximum invites filling to it.
///
/// **This remains scaffolding.** Model choice is properly an operator preference, the same kind of
/// thing as `notes_template`, and belongs on [`selahcue_core::providers::ProvidersSettings`] where
/// it is persisted and surfaced in the UI — 86akbzxyc. The `.env` override is physical-QA
/// convenience for the developer-key phase and dies with the loader.
pub const DEFAULT_MODEL: &str = "gpt-5.6-terra";

/// API root. Overridable so a test or a proxy can point elsewhere; never carries a key.
pub const DEFAULT_BASE_URL: &str = "https://api.openai.com";

/// The Responses API path. Structured output lives at `text.format` here (it is
/// `response_format` on the older Chat Completions endpoint) — confirmed against the
/// live API reference on 2026-09-04.
pub const RESPONSES_PATH: &str = "/v1/responses";

// ---------------------------------------------------------------------------
// Bounds
//
// Every bound below caps a COUNT as well as a length. A byte budget on its own admits
// unboundedly many tiny entries, which leaves the memory bounded and the work not.
// ---------------------------------------------------------------------------

/// The most transcript text ever sent in one request.
///
/// **Moved to [`crate::transcript_bounds`] (86akcffy0)** — re-exported here unchanged so every
/// existing call site and test in this module/crate keeps working via `openai::MAX_TRANSCRIPT_CHARS`.
/// See that module's docs for why: the from-history Generate command needs this clamp reachable
/// without the `openai` feature compiled in at all.
pub use crate::transcript_bounds::MAX_TRANSCRIPT_CHARS;

/// The most response body this module will **parse**. Anything larger is rejected before
/// `serde_json` allocates a tree for it.
///
/// Distinct from [`crate::transport::MAX_TRANSPORT_RESPONSE_BYTES`] (4 MB), which bounds the
/// **socket read**. Two caps at two layers, named for what each bounds — they were both
/// called `MAX_PARSED_RESPONSE_BYTES` and whichever happened to be in scope was the one you got.
pub const MAX_PARSED_RESPONSE_BYTES: usize = 512 * 1024;

/// Outline points kept from one response.
pub const MAX_POINTS: usize = 32;
/// Sub-points kept per point.
pub const MAX_SUB_POINTS: usize = 16;
/// Entries kept in any one flat section.
pub const MAX_SECTION_ITEMS: usize = 64;
/// Scripture references kept.
pub const MAX_SCRIPTURES: usize = 128;
/// Characters kept in any single list entry or point.
pub const MAX_ITEM_CHARS: usize = 2_000;
/// Characters kept in the title.
pub const MAX_TITLE_CHARS: usize = 200;
/// Characters kept in the summary.
pub const MAX_SUMMARY_CHARS: usize = 4_000;
/// Ceiling on model output, so a runaway generation cannot bill or buffer without end.
pub const MAX_OUTPUT_TOKENS: u32 = 8_000;

// The premises the bounded-response tests rest on, pinned at COMPILE time. If someone
// widens a cap past the fixtures those tests feed in, the build fails here and they go
// and look — rather than the tests quietly passing while exercising nothing, which is
// how a bounded-memory test becomes decoration.
const _: () = assert!(
    MAX_POINTS < 100,
    "test_openai feeds a 100-point response to prove the point cap bites; \
     raising MAX_POINTS to 100+ makes that test vacuous"
);
const _: () = assert!(
    MAX_SUB_POINTS < 100,
    "test_openai feeds 100 sub-points to prove the sub-point cap bites"
);
const _: () = assert!(
    MAX_SECTION_ITEMS < 200,
    "test_openai feeds a 200-entry section to prove the item cap bites"
);
const _: () = assert!(
    MAX_SCRIPTURES < 500,
    "test_openai feeds 500 scriptures to prove the scripture cap bites"
);
const _: () = assert!(
    MAX_ITEM_CHARS < MAX_PARSED_RESPONSE_BYTES,
    "an entry cap at or above the whole-body cap could never be reached"
);

// ---------------------------------------------------------------------------
// Clamp reporting
// ---------------------------------------------------------------------------

/// Which bound was reached. Named individually so a test can assert that **the bound it
/// is about** is the one that bit, instead of reading a global "something was clamped"
/// counter that a sibling assertion could satisfy on its behalf.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Bound {
    TranscriptChars,
    Points,
    SubPoints,
    SectionItems,
    Scriptures,
    ItemChars,
    TitleChars,
    SummaryChars,
}

/// How many distinct [`Bound`] variants exist. [`ClampLog`] merges by key, so its
/// storage can never exceed this many entries however hostile the response is.
pub const BOUND_COUNT: usize = 8;

/// What a single parse had to cut, per bound.
///
/// Deliberately **not** a single counter. A global tally lets one bound's hits stand in
/// for another's, so a test asserting "the sub-point cap bit" would pass on a response
/// that only tripped the item cap — and the control would then survive removal of the
/// thing it claims to guard.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ClampLog {
    /// At most one entry per [`Bound`]; [`ClampLog::record`] merges rather than pushes,
    /// so this vector is bounded by [`BOUND_COUNT`] and cannot grow with input size.
    hits: Vec<(Bound, usize)>,
}

impl ClampLog {
    /// How much was dropped at `bound`, or `None` if that bound was never reached.
    ///
    /// The per-key `Option` is the point: `None` is a positive statement that this
    /// specific bound did not bite.
    pub fn clamped(&self, bound: Bound) -> Option<usize> {
        self.hits.iter().find(|(b, _)| *b == bound).map(|(_, n)| *n)
    }

    /// True when nothing was cut — the shape a well-behaved response produces, and the
    /// positive control for every clamp test.
    pub fn is_empty(&self) -> bool {
        self.hits.is_empty()
    }

    /// Distinct bounds reached. Never exceeds [`BOUND_COUNT`].
    pub fn len(&self) -> usize {
        self.hits.len()
    }

    fn record(&mut self, bound: Bound, dropped: usize) {
        if dropped == 0 {
            return;
        }
        match self.hits.iter_mut().find(|(b, _)| *b == bound) {
            Some((_, n)) => *n += dropped,
            None => self.hits.push((bound, dropped)),
        }
    }
}

// ---------------------------------------------------------------------------
// Bounded input
// ---------------------------------------------------------------------------

/// The slice of `transcript` that may be sent, plus how many characters were dropped.
///
/// **Moved to [`crate::transcript_bounds`] (86akcffy0)**, re-exported here unchanged — see that
/// module's doc comment for the full reasoning (borrowed-slice rationale, head-vs-tail choice)
/// and [`crate::transcript_bounds`] for why this had to become reachable without `openai`.
pub use crate::transcript_bounds::bounded_transcript;

fn clamp_chars(s: &str, max: usize) -> (String, usize) {
    let n = s.chars().count();
    if n <= max {
        return (s.to_string(), 0);
    }
    (s.chars().take(max).collect(), n - max)
}

// ---------------------------------------------------------------------------
// Section identity
// ---------------------------------------------------------------------------

/// One FR-122 section: the response field it comes from, the heading it renders as, and
/// the include-flag that governs it.
///
/// The table exists so "which sections may appear" has **one** definition. The schema is
/// built from it and the response is filtered through it, so the request and the
/// enforcement cannot drift apart — the failure mode where a section is dropped from the
/// prompt but still accepted on the way back in.
struct SectionSpec {
    /// JSON field in the model's response.
    field: &'static str,
    /// Heading in the resulting [`NoteDraft`].
    heading: &'static str,
    /// Reads the governing include-flag; `None` for sections FR-122 always requires.
    gate: Option<fn(&IncludeInNotes) -> bool>,
}

impl SectionSpec {
    fn enabled(&self, inc: &IncludeInNotes) -> bool {
        match self.gate {
            None => true,
            Some(f) => f(inc),
        }
    }
}

/// Every flat section, in the order FR-122 lists them. The hierarchical outline
/// ("points") is handled separately because it is the one section with sub-points.
const FLAT_SECTIONS: &[SectionSpec] = &[
    SectionSpec {
        field: "introduction",
        heading: "Introduction",
        gate: None,
    },
    SectionSpec {
        field: "illustrations",
        heading: "Illustrations",
        gate: None,
    },
    SectionSpec {
        field: "quotes",
        heading: "Notable quotations",
        gate: Some(|i| i.notable_quotations),
    },
    SectionSpec {
        field: "prayer_points",
        heading: "Prayer points",
        gate: Some(|i| i.prayer_points),
    },
    SectionSpec {
        field: "calls_to_action",
        heading: "Calls to action",
        gate: None,
    },
    SectionSpec {
        field: "key_lessons",
        heading: "Key lessons",
        gate: None,
    },
    SectionSpec {
        field: "chapter_markers",
        heading: "Chapter markers",
        gate: Some(|i| i.chapter_markers),
    },
    SectionSpec {
        field: "social_excerpts",
        heading: "Social excerpts",
        gate: Some(|i| i.social_excerpts),
    },
];

/// The heading of the one hierarchical section (FR-122 "points/sub-points").
pub const OUTLINE_HEADING: &str = "Main points";

// ---------------------------------------------------------------------------
// Request building
// ---------------------------------------------------------------------------

fn string_schema() -> serde_json::Value {
    serde_json::json!({"type": "string"})
}

fn string_list_schema() -> serde_json::Value {
    serde_json::json!({"type": "array", "items": {"type": "string"}})
}

/// The strict JSON schema for the draft, built from the operator's include-flags.
///
/// A disabled section is **not in the schema at all**, so the model is never asked for
/// it. Strict mode additionally requires every declared property to be `required` with
/// `additionalProperties: false`, which means the response shape is fully determined by
/// the toggles rather than by what the model felt like returning.
///
/// This is only the first of two layers. [`parse_draft`] independently drops any
/// disabled section that arrives anyway, because "we did not ask for it" is not the same
/// guarantee as "it cannot appear", and the acceptance criterion is about the draft.
pub fn draft_schema(inc: &IncludeInNotes) -> serde_json::Value {
    let mut props = serde_json::Map::new();
    let mut required: Vec<serde_json::Value> = Vec::new();
    let mut add = |name: &str, spec: serde_json::Value| {
        props.insert(name.to_string(), spec);
        required.push(serde_json::Value::String(name.to_string()));
    };

    add("title", string_schema());
    if inc.scripture_extraction {
        add("main_scripture", string_schema());
        add("supporting_scriptures", string_list_schema());
    }
    add(
        "points",
        serde_json::json!({
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "sub_points": {"type": "array", "items": {"type": "string"}}},
                "required": ["text", "sub_points"],
                "additionalProperties": false
            }
        }),
    );
    for spec in FLAT_SECTIONS {
        // "introduction" is a flat section but must precede points in the schema for
        // readability only; order in a JSON object is not semantic, so the table order
        // is used as-is.
        if spec.field != "introduction" && spec.enabled(inc) {
            add(spec.field, string_list_schema());
        }
    }
    add("introduction", string_list_schema());
    if inc.short_summary {
        add("summary", string_schema());
    }

    serde_json::json!({
        "type": "object",
        "properties": serde_json::Value::Object(props),
        "required": serde_json::Value::Array(required),
        "additionalProperties": false
    })
}

fn template_guidance(t: NotesTemplate) -> &'static str {
    match t {
        NotesTemplate::FullOutlineWithScriptures => {
            "Produce a full outline and cite the scripture behind each point inline."
        }
        NotesTemplate::FullOutline => {
            "Produce a full outline. Keep scripture citation to the scripture fields; \
             do not interleave references into every point."
        }
        NotesTemplate::Summary => "Keep it concise: few points, short sub-points, no padding.",
        NotesTemplate::Devotional => {
            "Treat it devotionally: reflective and personal in tone, applied to the \
             reader's week rather than structured for re-preaching."
        }
    }
}

/// The developer instruction.
///
/// Most of it is anti-fabrication. That is not decoration: FR-128 makes us disclose that
/// the model can invent things, and the disclosure is a great deal more defensible when
/// the prompt has already told it not to and given it somewhere to put "the sermon did
/// not say".
fn instruction(options: &NoteOptions, truncated: bool) -> String {
    let mut s = String::with_capacity(1_400);
    s.push_str(
        "You turn a completed sermon transcript into a structured sermon-note draft for \
         a church media operator.\n\n\
         Ground every field in the transcript. Do not invent quotations, scripture \
         references, statistics, names or stories that are not in it. Quote only words \
         that actually appear in the transcript. If the sermon does not supply \
         something a field asks for, return an empty list or an empty string — a blank \
         field is correct and useful, a plausible invention is not.\n\n\
         'points' is the sermon's own outline. Each point carries its own 'sub_points', \
         which must be genuinely subordinate to that point — its supporting moves, \
         evidence or applications — and must not restate the point or belong to a \
         different one.\n",
    );
    s.push_str(&format!(
        "\nCite scripture as 'Book chapter:verse' using the naming of the {} \
         translation.\n",
        options.preferred_translation
    ));
    s.push('\n');
    s.push_str(template_guidance(options.template));
    if truncated {
        s.push_str(
            "\n\nThe transcript below was truncated and does not contain the end of the \
             sermon. Work only from what is present and do not supply a conclusion the \
             text does not contain.",
        );
    }
    s
}

// ---------------------------------------------------------------------------
// Response parsing
// ---------------------------------------------------------------------------

fn take_strings(
    v: Option<&serde_json::Value>,
    max: usize,
    count_bound: Bound,
    log: &mut ClampLog,
) -> Vec<String> {
    let Some(arr) = v.and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    if arr.len() > max {
        log.record(count_bound, arr.len() - max);
    }
    arr.iter()
        .take(max)
        .filter_map(|e| e.as_str())
        .map(|s| {
            let (t, dropped) = clamp_chars(s, MAX_ITEM_CHARS);
            log.record(Bound::ItemChars, dropped);
            t
        })
        .filter(|s| !s.trim().is_empty())
        .collect()
}

/// Parse a model response body into a bounded [`NoteDraft`], honouring the operator's
/// include-flags.
///
/// Public and free-standing so the bounded-response tests can drive it directly with a
/// hostile fixture, rather than reaching it through a transport and a provider and
/// hoping the bound is what refused.
///
/// Every input here is untrusted: it is whatever a third party put on the wire. Missing
/// fields degrade to empty, wrong types degrade to empty, and nothing panics.
pub fn parse_draft(body: &str, inc: &IncludeInNotes) -> Result<(NoteDraft, ClampLog), NoteError> {
    if body.len() > MAX_PARSED_RESPONSE_BYTES {
        // Refused BEFORE serde_json builds a tree, so an oversized body costs one
        // length check rather than a proportional allocation.
        return Err(NoteError::Malformed(format!(
            "provider response exceeded the {MAX_PARSED_RESPONSE_BYTES}-byte cap"
        )));
    }
    let root: serde_json::Value =
        serde_json::from_str(body).map_err(|e| NoteError::Malformed(e.to_string()))?;

    let text = extract_output_text(&root)?;
    if text.len() > MAX_PARSED_RESPONSE_BYTES {
        return Err(NoteError::Malformed(format!(
            "provider output text exceeded the {MAX_PARSED_RESPONSE_BYTES}-byte cap"
        )));
    }
    let d: serde_json::Value =
        serde_json::from_str(&text).map_err(|e| NoteError::Malformed(e.to_string()))?;

    let mut log = ClampLog::default();

    let (title, dropped) = clamp_chars(
        d.get("title").and_then(|v| v.as_str()).unwrap_or(""),
        MAX_TITLE_CHARS,
    );
    log.record(Bound::TitleChars, dropped);
    let title = if title.trim().is_empty() {
        "Sermon notes".to_string()
    } else {
        title
    };

    let summary = if inc.short_summary {
        d.get("summary")
            .and_then(|v| v.as_str())
            .map(|s| {
                let (t, dropped) = clamp_chars(s, MAX_SUMMARY_CHARS);
                log.record(Bound::SummaryChars, dropped);
                t
            })
            .filter(|s| !s.trim().is_empty())
    } else {
        // The operator switched the summary off; an arriving one is discarded rather
        // than rendered.
        None
    };

    // --- scriptures: main first, then supporting, capped as one list ---
    let mut scriptures: Vec<String> = Vec::new();
    if inc.scripture_extraction {
        if let Some(main) = d.get("main_scripture").and_then(|v| v.as_str()) {
            let (t, dropped) = clamp_chars(main, MAX_ITEM_CHARS);
            log.record(Bound::ItemChars, dropped);
            if !t.trim().is_empty() {
                scriptures.push(t);
            }
        }
        let supporting = take_strings(
            d.get("supporting_scriptures"),
            MAX_SCRIPTURES.saturating_sub(scriptures.len()),
            Bound::Scriptures,
            &mut log,
        );
        scriptures.extend(supporting);
    }

    // --- the one hierarchical section (FR-122 points/sub-points) ---
    let mut sections: Vec<NoteSection> = Vec::new();
    let points = parse_points(d.get("points"), &mut log);
    if !points.is_empty() {
        sections.push(NoteSection::outline(OUTLINE_HEADING, points));
    }

    // --- flat sections, filtered by the SAME table the schema was built from ---
    for spec in FLAT_SECTIONS {
        if !spec.enabled(inc) {
            // Second layer. The schema never asked for this field, but a response is a
            // third party's output and "we did not ask" is not a guarantee. A section
            // the operator switched off does not reach the draft, whatever arrives.
            continue;
        }
        let items = take_strings(
            d.get(spec.field),
            MAX_SECTION_ITEMS,
            Bound::SectionItems,
            &mut log,
        );
        if !items.is_empty() {
            sections.push(NoteSection::flat(spec.heading, items));
        }
    }

    Ok((
        NoteDraft {
            title,
            summary,
            sections,
            scriptures,
        },
        log,
    ))
}

fn parse_points(v: Option<&serde_json::Value>, log: &mut ClampLog) -> Vec<NotePoint> {
    let Some(arr) = v.and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    if arr.len() > MAX_POINTS {
        log.record(Bound::Points, arr.len() - MAX_POINTS);
    }
    arr.iter()
        .take(MAX_POINTS)
        .filter_map(|p| {
            let text = p.get("text").and_then(|t| t.as_str())?;
            let (text, dropped) = clamp_chars(text, MAX_ITEM_CHARS);
            log.record(Bound::ItemChars, dropped);
            if text.trim().is_empty() {
                return None;
            }
            let sub_points =
                take_strings(p.get("sub_points"), MAX_SUB_POINTS, Bound::SubPoints, log);
            Some(NotePoint { text, sub_points })
        })
        .collect()
}

/// Pull the model's text out of a Responses-API envelope: `output[].content[]` where
/// `type == "output_text"`. A `refusal` content block is a real, documented outcome and
/// becomes a [`NoteError::Malformed`] carrying **our** wording, never the provider's.
fn extract_output_text(root: &serde_json::Value) -> Result<String, NoteError> {
    let Some(output) = root.get("output").and_then(|v| v.as_array()) else {
        return Err(NoteError::Malformed(
            "provider response had no output array".to_string(),
        ));
    };
    for item in output {
        let Some(content) = item.get("content").and_then(|v| v.as_array()) else {
            continue;
        };
        for c in content {
            match c.get("type").and_then(|t| t.as_str()) {
                Some("output_text") => {
                    if let Some(t) = c.get("text").and_then(|t| t.as_str()) {
                        return Ok(t.to_string());
                    }
                }
                Some("refusal") => {
                    return Err(NoteError::Malformed(
                        "the model declined to generate notes from this transcript".to_string(),
                    ));
                }
                _ => {}
            }
        }
    }
    Err(NoteError::Malformed(
        "provider response contained no output text".to_string(),
    ))
}

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

/// Map an HTTP status + error body onto the stable [`NoteError`]s the UI distinguishes.
///
/// **The response body is never echoed.** OpenAI's 401 body contains a partially masked
/// but still partly clear-text copy of the key that was sent — observed on the live API
/// on 2026-09-04:
///
/// ```text
/// {"error":{"message":"Incorrect API key provided: sk-proj-********************-key", ...}}
/// ```
///
/// The prefix and the trailing characters survive the masking. Anything that forwards
/// that body into an error message puts key material into the UI and into every log that
/// catches it — so this function reads only the machine-readable `error.type` /
/// `error.code` and returns wording of our own.
///
/// **429 is overloaded and must not be flattened.** `insufficient_quota` means the
/// account is out of money: terminal, and the operator has to be told, so it becomes
/// [`NoteError::QuotaExceeded`] and propagates. A plain rate-limit 429 is a transient
/// blip and becomes [`NoteError::Transport`], so [`crate::generate_sermon_notes`] serves
/// the degraded local draft instead of a dead end. Mapping both to `QuotaExceeded` — as
/// a bare `402 | 429` match would — turns a two-second throttle into "your monthly quota
/// is exhausted".
pub fn map_error_status(status: u16, body: &str) -> NoteError {
    let code = error_code(body);
    match status {
        401 | 403 => NoteError::NotConfigured,
        // A model id the account cannot reach is a misconfiguration, not a network
        // blip. Mapping it to Transport would silently serve local scaffolds for as
        // long as nobody looked at why the notes got worse.
        404 => NoteError::NotConfigured,
        402 => NoteError::QuotaExceeded,
        429 => {
            if matches!(
                code.as_deref(),
                Some("insufficient_quota") | Some("credit_balance_exhausted")
            ) {
                NoteError::QuotaExceeded
            } else {
                NoteError::Transport("provider rate limit".to_string())
            }
        }
        400 => NoteError::Malformed("the provider rejected the request as invalid".to_string()),
        500..=599 => NoteError::Transport(format!("provider server status {status}")),
        other => NoteError::Malformed(format!("unexpected provider status {other}")),
    }
}

/// `error.type` or `error.code` from an error body, if it parses. Only these two
/// machine-readable fields are ever read — never `error.message`, which is free text the
/// provider composes and has been observed to contain key material.
fn error_code(body: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(body).ok()?;
    let e = v.get("error")?;
    for key in ["type", "code"] {
        if let Some(s) = e.get(key).and_then(|x| x.as_str()) {
            if s == "insufficient_quota" || s == "credit_balance_exhausted" {
                return Some(s.to_string());
            }
        }
    }
    e.get("type")
        .or_else(|| e.get("code"))
        .and_then(|x| x.as_str())
        .map(str::to_string)
}

// ---------------------------------------------------------------------------
// The provider
// ---------------------------------------------------------------------------

/// Resolve the model id from `value`, falling back to [`DEFAULT_MODEL`].
///
/// Free-standing and taking the value, so a test can drive every case without mutating the process
/// environment under a parallel runner — the same shape the operator's `direct_provider_from_key`
/// takes, and for the same reason.
///
/// **Deliberately not validated against a hardcoded list of known models.** OpenAI's catalogue
/// moves faster than our releases; a stale allowlist here would reject a model the account can
/// actually call, which is a worse failure than passing an unknown one through. An unknown model
/// returns HTTP 404 `model_not_found`, which [`map_error_status`] maps to
/// [`NoteError::NotConfigured`] — a terminal, visible state, not a silent fall-back to the local
/// scaffold. That is the honest handling: the operator is told the configured model was rejected
/// rather than quietly getting worse notes.
pub fn resolve_model(value: Option<&str>) -> String {
    match value.map(str::trim).filter(|v| !v.is_empty()) {
        // Bounded before it is stored, not after.
        Some(v) => v.chars().take(MAX_MODEL_LEN).collect(),
        None => DEFAULT_MODEL.to_string(),
    }
}

/// The model this build will ask for, from the environment or the default.
pub fn model_from_env() -> String {
    resolve_model(std::env::var(MODEL_ENV).ok().as_deref())
}

/// A [`NoteProvider`] backed by OpenAI GPT over an injected [`HttpTransport`].
///
/// Holds the developer key in a [`crate::secret::Token`], which redacts itself in
/// `Debug`/`Display`, so the key cannot reach a log through a derived formatter. The
/// struct derives no `Debug` of its own for the same reason it would not need to: the
/// only secret it holds already refuses to print itself.
pub struct OpenAiNoteProvider<T: HttpTransport> {
    transport: T,
    api_key: crate::secret::Token,
    model: String,
    base_url: String,
}

impl<T: HttpTransport> OpenAiNoteProvider<T> {
    /// A provider with an explicit key and model.
    ///
    /// The `model` parameter is a **constructor seam**, not a configuration surface:
    /// it lets a test pin the model it asserts on. Production construction goes through
    /// [`OpenAiNoteProvider::from_env`], which resolves the model via [`model_from_env`] --
    /// [`MODEL_ENV`] when QA has set it, [`DEFAULT_MODEL`] otherwise.
    pub fn new(transport: T, api_key: crate::secret::Token, model: impl Into<String>) -> Self {
        OpenAiNoteProvider {
            transport,
            api_key,
            model: model.into(),
            base_url: DEFAULT_BASE_URL.to_string(),
        }
    }

    /// Point at a different API root (a proxy, or a test double).
    pub fn with_base_url(mut self, base_url: impl Into<String>) -> Self {
        self.base_url = base_url.into();
        self
    }

    /// Build from the process environment, or `None` when no usable key is present.
    ///
    /// `None` is a **first-class state**, not a failure: it is what a default build and
    /// any checkout without a populated `.env` reports, and the Providers & Privacy
    /// panel renders it as "a key is missing" rather than "the feature does not exist".
    /// An absent variable and an empty one are treated identically, so it does not
    /// matter whether the `.env` loader unsets a blank value or exports it empty.
    ///
    /// **Also refuses in a release profile**, via [`direct_key_permitted`] — see its doc
    /// comment for the gap this closes (86akcmzyq). The environment is not even read in that
    /// case: a release build must not construct a working provider from a key that happens to
    /// already be exported, not merely report one it declines to use.
    pub fn from_env(transport: T) -> Option<Self> {
        if !direct_key_permitted(cfg!(debug_assertions)) {
            return None;
        }
        let key = std::env::var(API_KEY_ENV).ok()?;
        if key.trim().is_empty() {
            return None;
        }
        Some(OpenAiNoteProvider::new(
            transport,
            crate::secret::Token::new(key),
            model_from_env(),
        ))
    }

    /// The model this provider will call. Never secret.
    pub fn model(&self) -> &str {
        &self.model
    }

    /// The request body for `req`, plus anything the input bound had to cut.
    ///
    /// Separated from the network call so a test can assert **what would be sent** —
    /// in particular that it carries the transcript and nothing resembling audio, and
    /// that the key is not in the body (it belongs in the header alone).
    pub fn build_body(&self, req: &NoteRequest) -> (String, ClampLog) {
        let mut log = ClampLog::default();
        let (transcript, dropped) = bounded_transcript(&req.transcript);
        if let Some(n) = dropped {
            log.record(Bound::TranscriptChars, n);
        }
        let body = serde_json::json!({
            "model": self.model,
            "input": [
                {"role": "developer", "content": instruction(&req.options, dropped.is_some())},
                {"role": "user", "content": format!("Sermon transcript:\n\n{transcript}")},
            ],
            "text": {"format": {
                "type": "json_schema",
                "name": "sermon_notes",
                "schema": draft_schema(&req.options.include),
                "strict": true
            }},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        });
        (body.to_string(), log)
    }

    fn url(&self) -> String {
        format!("{}{}", self.base_url.trim_end_matches('/'), RESPONSES_PATH)
    }
}

impl<T: HttpTransport> NoteProvider for OpenAiNoteProvider<T> {
    fn label(&self) -> &str {
        PROVIDER_LABEL
    }

    fn generate(&self, req: &NoteRequest) -> Result<NoteDraft, NoteError> {
        self.generate_with_quota(req).map(|(draft, _)| draft)
    }

    // `is_generative` keeps its `true` default: this IS a model, and its drafts carry
    // the AI-generated label and the fabrication disclosure.
}

impl<T: HttpTransport> CloudNoteProvider for OpenAiNoteProvider<T> {
    fn generate_with_quota(
        &self,
        req: &NoteRequest,
    ) -> Result<(NoteDraft, Option<Quota>), NoteError> {
        if self.api_key.is_empty() {
            return Err(NoteError::NotConfigured);
        }
        let (body, _clamped) = self.build_body(req);
        let resp = self
            .transport
            .post_json(&self.url(), &body, Some(self.api_key.expose()))
            .map_err(|e| NoteError::Transport(e.to_string()))?;

        if !(200..300).contains(&resp.status) {
            return Err(map_error_status(resp.status, &resp.body));
        }
        let (draft, _log) = parse_draft(&resp.body, &req.options.include)?;
        // `quota` stays None. OpenAI reports no note-generation quota, and there is no
        // metering in this phase — so there is no number, and the panel keeps its
        // honest placeholder rather than being handed an invented one.
        Ok((draft, None))
    }
}
