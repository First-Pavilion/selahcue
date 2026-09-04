//! Deepgram's wire format, and the mapping onto the core's [`ProviderSegment`].
//!
//! Pure and synchronous, so the wire contract is pinned by tests in the default build rather
//! than discovered against a paid third party at run time. Everything here treats its input
//! as **hostile**: a frame arrives from a network peer, so parsing returns a
//! [`DeepgramError::Protocol`] on anything unexpected and never panics, in the same spirit as
//! the core's scripture parser.
//!
//! # `is_final` is the settledness signal, not `speech_final`
//!
//! Deepgram sends two booleans and they mean different things. `is_final` says *this
//! transcript will not change* — the service has stopped revising it. `speech_final` says
//! *the speaker paused here*, an utterance boundary, which can be true of a transcript still
//! subject to revision and false of one already settled.
//!
//! The console's provisional-versus-confirmed styling (FR-103) is a question about revision,
//! so [`ProviderSegment::is_final`] is mapped from **`is_final`**. Mapping it from
//! `speech_final` would style still-changing text as settled, which is precisely the lie the
//! provisional style exists to prevent. `speech_final` is preserved on [`ResultsFrame`] so a
//! caller that wants utterance grouping has it, and the distinction cannot be recovered later
//! if it is dropped here.

use selahcue_core::transcript::ProviderSegment;
use serde_json::Value;

use crate::error::DeepgramError;

/// Largest frame this client will parse.
///
/// A transcript frame is a sentence and some metadata — kilobytes. Refusing anything larger
/// stops a hostile or broken peer from making this client allocate without limit on the
/// network path, which is the same class of risk the two buffers guard against.
pub const MAX_FRAME_BYTES: usize = 256 * 1024;

const _: () = assert!(
    MAX_FRAME_BYTES > selahcue_core::transcript::MAX_SEGMENT_TEXT_LEN,
    "the frame cap must leave room for a maximum-length segment plus its JSON envelope, or \
     legitimate transcripts would be refused"
);

/// A Deepgram `Results` message, reduced to the fields this client uses.
#[derive(Debug, Clone, PartialEq)]
pub struct ResultsFrame {
    /// The best alternative's transcript. May be empty — Deepgram emits empty interim
    /// results during silence.
    pub transcript: String,
    /// **The settledness signal.** `true` once Deepgram will not revise this transcript.
    pub is_final: bool,
    /// An utterance boundary — the speaker paused here. Not the same question as `is_final`;
    /// preserved for callers that want to group utterances.
    pub speech_final: bool,
    /// Start offset in seconds from the beginning of the stream.
    pub start_s: f64,
    /// Length of this transcript's audio in seconds.
    pub duration_s: f64,
}

impl ResultsFrame {
    /// Map onto the core's provider segment, **preserving the provisional-versus-settled
    /// distinction** the console needs and cannot recover later.
    pub fn to_segment(&self) -> ProviderSegment {
        let start_ms = seconds_to_ms(self.start_s);
        let end_ms = seconds_to_ms(self.start_s + self.duration_s).max(start_ms);
        ProviderSegment {
            text: self.transcript.clone(),
            start_ms,
            end_ms,
            is_final: self.is_final,
        }
    }
}

/// Seconds to milliseconds, defensive about a hostile peer's floats.
///
/// Rust's float-to-integer casts saturate rather than wrap, and produce `0` for `NaN`, so
/// this cannot panic or produce a wrapped-around timestamp; the explicit clamp says so rather
/// than leaving a reader to remember it.
fn seconds_to_ms(seconds: f64) -> u64 {
    if !seconds.is_finite() || seconds <= 0.0 {
        return 0;
    }
    (seconds * 1000.0).round() as u64
}

/// Every Deepgram message shape this client recognises.
#[derive(Debug, Clone, PartialEq)]
pub enum DeepgramFrame {
    /// A transcript, interim or final.
    Results(ResultsFrame),
    /// Stream metadata, sent on open and close.
    Metadata { request_id: String },
    /// The service detected the end of an utterance (needs `utterance_end_ms`).
    UtteranceEnd { last_word_end_ms: u64 },
    /// Voice activity began (needs `vad_events`).
    SpeechStarted,
    /// A message type this client does not act on. Kept rather than refused so a new Deepgram
    /// message type is forward-compatible instead of a stream-ending protocol error.
    Other { kind: String },
}

/// Parse one text frame.
///
/// Returns [`DeepgramError::Protocol`] for a frame that is too large, is not JSON, has no
/// `type`, or is a `Results` message whose shape this client cannot read. An *unknown*
/// message type is not an error — it becomes [`DeepgramFrame::Other`], so Deepgram adding a
/// message type does not stop a service mid-sermon.
pub fn parse_frame(text: &str) -> Result<DeepgramFrame, DeepgramError> {
    if text.len() > MAX_FRAME_BYTES {
        return Err(DeepgramError::Protocol {
            detail: format!(
                "frame of {} bytes exceeds the {MAX_FRAME_BYTES}-byte cap",
                text.len()
            ),
        });
    }
    let value: Value = serde_json::from_str(text).map_err(|e| DeepgramError::Protocol {
        detail: format!("frame is not valid JSON: {e}"),
    })?;
    let kind =
        value
            .get("type")
            .and_then(Value::as_str)
            .ok_or_else(|| DeepgramError::Protocol {
                detail: "frame has no \"type\" field".to_string(),
            })?;
    match kind {
        "Results" => Ok(DeepgramFrame::Results(parse_results(&value)?)),
        "Metadata" => Ok(DeepgramFrame::Metadata {
            request_id: value
                .get("request_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
        }),
        "UtteranceEnd" => Ok(DeepgramFrame::UtteranceEnd {
            last_word_end_ms: seconds_to_ms(
                value
                    .get("last_word_end")
                    .and_then(Value::as_f64)
                    .unwrap_or(0.0),
            ),
        }),
        "SpeechStarted" => Ok(DeepgramFrame::SpeechStarted),
        other => Ok(DeepgramFrame::Other {
            kind: other.to_string(),
        }),
    }
}

fn parse_results(value: &Value) -> Result<ResultsFrame, DeepgramError> {
    let transcript = value
        .get("channel")
        .and_then(|c| c.get("alternatives"))
        .and_then(Value::as_array)
        .and_then(|alts| alts.first())
        .and_then(|alt| alt.get("transcript"))
        .and_then(Value::as_str)
        .ok_or_else(|| DeepgramError::Protocol {
            detail: "Results frame has no channel.alternatives[0].transcript".to_string(),
        })?
        .to_string();
    Ok(ResultsFrame {
        transcript,
        // Absent means "not settled". Defaulting a missing settledness flag to `true` would
        // style still-changing text as confirmed, so the safe default is the provisional one.
        is_final: value
            .get("is_final")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        speech_final: value
            .get("speech_final")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        start_s: value.get("start").and_then(Value::as_f64).unwrap_or(0.0),
        duration_s: value.get("duration").and_then(Value::as_f64).unwrap_or(0.0),
    })
}

/// The `KeepAlive` control message. Deepgram closes an idle stream; this holds it open
/// through a silent passage without sending audio.
pub const KEEP_ALIVE: &str = r#"{"type":"KeepAlive"}"#;

/// The `CloseStream` control message — asks Deepgram to flush and close cleanly, so the last
/// words of a sermon are not lost to an abrupt socket drop.
pub const CLOSE_STREAM: &str = r#"{"type":"CloseStream"}"#;

// Tests live in `tests/test_protocol.rs` (public-API integration tests).
