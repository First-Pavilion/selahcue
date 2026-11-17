//! Scratch, offline adapter for the real native parser. All frames are synthetic test input.
use selahcue_cloud::contract::OptionsDto;
use selahcue_cloud::mock::MockTransport;
use selahcue_cloud::openai::{
    MAX_PARSED_RESPONSE_BYTES, OpenAiNoteProvider, draft_schema, parse_draft,
};
use selahcue_cloud::secret::Token;
use selahcue_cloud::transport::{HttpResponse, HttpTransport, TransportError};
use selahcue_core::providers::{
    DraftCaveat, NoteError, NoteOptions, NoteRequest, ProvidersConfig, link_timestamps,
    verify_scriptures,
};
use selahcue_core::transcript::TranscriptSegment;
use selahcue_scripture::Translation;
use serde::Deserialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::io::{self, BufRead, Read, Write};

const PUBLIC_BYTES: usize = 262_144;
const FRAME_BYTES: usize = 1_100_000;
const MAX_SEGMENTS: usize = 32;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Frame {
    options: OptionsDto,
    draft_json: String,
    result_digest: String,
    #[serde(default)]
    envelope_suffix_spaces: usize,
    #[serde(default)]
    segments: Vec<Segment>,
    #[serde(default)]
    observe_helpers: bool,
    #[serde(default)]
    observe_body: bool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Segment {
    id: u64,
    start_ms: u64,
    end_ms: u64,
    text: String,
}

fn digest(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

struct BorrowedMock<'a>(&'a MockTransport);

impl HttpTransport for BorrowedMock<'_> {
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

fn build_body_observation(options: &NoteOptions) -> Value {
    let transport = MockTransport::failing();
    let provider = OpenAiNoteProvider::new(
        BorrowedMock(&transport),
        Token::new("synthetic-native-golden"),
        "inert-native-golden",
    );
    let (body, log) = provider.build_body(&NoteRequest {
        transcript: "Synthetic native parity fixture.".into(),
        options: options.clone(),
    });
    let body: Value = serde_json::from_str(&body).expect("native build_body must emit JSON");
    json!({
        "developer": body["input"][0]["content"],
        "schema": body["text"]["format"]["schema"],
        "clamped": !log.is_empty(),
        "transport_calls": transport.recorded().len(),
    })
}

fn observe(frame: Frame) -> Value {
    let raw = frame.draft_json;
    if digest(raw.as_bytes()) != frame.result_digest {
        return json!({"status": "digest_mismatch"});
    }
    if raw.len() > PUBLIC_BYTES {
        return json!({"status": "public_byte_limit"});
    }
    if frame.envelope_suffix_spaces > MAX_PARSED_RESPONSE_BYTES
        || frame.segments.len() > MAX_SEGMENTS
    {
        return json!({"status": "invalid_frame"});
    }

    let mut envelope =
        json!({"output": [{"content": [{"type": "output_text", "text": raw}]}]}).to_string();
    envelope.extend(std::iter::repeat_n(' ', frame.envelope_suffix_spaces));
    // Guard the integrity of the wrapper without replacing the raw embedded text by its object.
    let extracted: Value = serde_json::from_str(&envelope).expect("synthetic wrapper must be JSON");
    assert_eq!(
        extracted["output"][0]["content"][0]["text"].as_str(),
        Some(raw.as_str())
    );
    let options = frame.options.to_core();
    let mut result = json!({
        "envelope_bytes": envelope.len(),
        "envelope_sha256": digest(envelope.as_bytes()),
        "raw_bytes": raw.len(),
        "raw_sha256": frame.result_digest,
    });
    let (draft, clamped) = match parse_draft(&envelope, &options.include) {
        Ok(parsed) => parsed,
        Err(NoteError::Malformed(message))
            if message == "provider response exceeded the 524288-byte cap" =>
        {
            result["status"] = json!("native_byte_limit");
            return result;
        }
        Err(_) => {
            result["status"] = json!("native_rejected");
            return result;
        }
    };

    let sections: Vec<Value> = draft
        .sections
        .iter()
        .map(|section| {
            let points: Vec<Value> = section
                .points()
                .iter()
                .map(|point| json!({"text": point.text, "sub_points": point.sub_points}))
                .collect();
            json!({"heading": section.heading, "items": section.items(), "points": points})
        })
        .collect();
    let caveats: Vec<Value> = draft
        .caveats
        .iter()
        .map(|caveat| match caveat {
            DraftCaveat::SectionRequestedEmpty { heading } => json!(heading),
            DraftCaveat::ScriptureUnverified { .. } => {
                json!({"unexpected": "scripture_unverified"})
            }
            DraftCaveat::ScriptureVerificationIncomplete => {
                json!({"unexpected": "scripture_incomplete"})
            }
        })
        .collect();

    let mut config = ProvidersConfig::default();
    config
        .settings
        .preferred_translation
        .clone_from(&options.preferred_translation);
    let reloaded = ProvidersConfig::from_kv(config.to_kv());
    let from_settings = NoteOptions::from_settings(&reloaded.settings);

    result["status"] = json!("parsed");
    result["clamped"] = json!(!clamped.is_empty());
    result["options"] = json!(OptionsDto::from_core(&options));
    result["schema"] = draft_schema(&options.include);
    result["title"] = json!(draft.title);
    result["summary"] = json!(draft.summary);
    result["scriptures"] = json!(draft.scriptures);
    result["sections"] = json!(sections);
    result["caveats"] = json!(caveats);
    result["attached_scripture_verdict_count"] = json!(draft.scripture_verdicts.len());
    result["attached_timestamp_count"] = json!(draft.timestamps.len());
    result["picker_translations"] = json!(Translation::ALL.map(Translation::code));
    result["persisted_translation"] = json!(from_settings.preferred_translation);
    if frame.observe_body {
        result["legacy_build_body"] = build_body_observation(&options);
    }
    if frame.observe_helpers {
        let segments: Vec<TranscriptSegment> = frame
            .segments
            .into_iter()
            .map(|segment| TranscriptSegment {
                id: segment.id,
                start_ms: segment.start_ms,
                end_ms: segment.end_ms,
                text: segment.text,
            })
            .collect();
        let timestamps: Vec<Value> = link_timestamps(&draft.sections, &segments)
            .into_iter()
            .map(|timestamp| json!({"heading": timestamp.heading, "text": timestamp.text, "offset_ms": timestamp.offset_ms}))
            .collect();
        let (verdicts, truncated) =
            verify_scriptures(&draft.scriptures, &draft.sections, |reference| {
                !selahcue_scripture::verses(reference).is_empty()
            });
        let verdicts: Vec<Value> = verdicts
            .into_iter()
            .map(|verdict| json!({"reference": verdict.reference, "verified": verdict.verified}))
            .collect();
        result["helper_timestamps"] = json!(timestamps);
        result["helper_scripture_verdicts"] = json!(verdicts);
        result["helper_scripture_scan_truncated"] = json!(truncated);
    }
    result
}

fn main() -> io::Result<()> {
    let input = io::stdin();
    let mut reader = input.lock();
    let mut output = io::BufWriter::new(io::stdout().lock());
    let mut line = Vec::new();
    loop {
        line.clear();
        if reader
            .by_ref()
            .take((FRAME_BYTES + 1) as u64)
            .read_until(b'\n', &mut line)?
            == 0
        {
            break;
        }
        if line.len() > FRAME_BYTES || line.last() != Some(&b'\n') {
            writeln!(output, "{{\"status\":\"frame_byte_limit\"}}")?;
            break;
        }
        let observation = match serde_json::from_slice(&line) {
            Ok(frame) => observe(frame),
            Err(_) => json!({"status": "invalid_frame"}),
        };
        serde_json::to_writer(&mut output, &observation)?;
        writeln!(output)?;
    }
    output.flush()
}
