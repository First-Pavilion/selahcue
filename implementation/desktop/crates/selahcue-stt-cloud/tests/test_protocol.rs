//! Deepgram's wire format and the interim-versus-settled mapping.
//!
//! Fixtures are real `Results` frame shapes from Deepgram's streaming reference. The
//! provisional-versus-settled distinction is the one thing here that cannot be recovered
//! downstream if it is got wrong, so it is asserted in **both** directions and against the
//! specific way it is most likely to be got wrong — reading `speech_final` instead of
//! `is_final`.

#![allow(clippy::unwrap_used)]

use selahcue_stt_cloud::protocol::{parse_frame, MAX_FRAME_BYTES};
use selahcue_stt_cloud::{DeepgramError, DeepgramFrame};

/// A `Results` frame with the given transcript and the two settledness flags.
fn results_json(transcript: &str, is_final: bool, speech_final: bool) -> String {
    format!(
        r#"{{"type":"Results","channel_index":[0,1],"duration":1.5,"start":2.0,
             "is_final":{is_final},"speech_final":{speech_final},
             "channel":{{"alternatives":[{{"transcript":"{transcript}","confidence":0.99}}]}},
             "metadata":{{"request_id":"abc"}}}}"#
    )
}

fn expect_results(json: &str) -> selahcue_stt_cloud::ResultsFrame {
    match parse_frame(json) {
        Ok(DeepgramFrame::Results(r)) => r,
        other => panic!("expected a Results frame, got {other:?}"),
    }
}

#[test]
fn an_interim_result_maps_to_a_provisional_segment() {
    let frame = expect_results(&results_json("turn with me to", false, false));
    let segment = frame.to_segment();

    assert_eq!(segment.text, "turn with me to");
    assert!(
        !segment.is_final,
        "an interim result was mapped as settled; the console would style still-changing text \
         as confirmed, which is exactly the lie the provisional style exists to prevent"
    );
}

#[test]
fn a_final_result_maps_to_a_settled_segment() {
    // The positive half. Without it, "interim maps to provisional" is satisfied by a mapping
    // that marks everything provisional and never settles anything.
    let frame = expect_results(&results_json(
        "Turn with me to John chapter three.",
        true,
        true,
    ));
    let segment = frame.to_segment();

    assert!(
        segment.is_final,
        "a final result was mapped as provisional; nothing would ever settle in the panel"
    );
    assert_eq!(segment.text, "Turn with me to John chapter three.");
}

#[test]
fn settledness_comes_from_is_final_and_not_from_speech_final() {
    // The specific trap. `speech_final` means "the speaker paused here", which can be true of
    // a transcript Deepgram is still revising. Reading it as settledness styles changing text
    // as confirmed.
    let paused_but_unsettled = expect_results(&results_json("verse six", false, true));
    assert!(
        !paused_but_unsettled.to_segment().is_final,
        "settledness was read from speech_final: a transcript still subject to revision was \
         marked final because the speaker paused"
    );
    assert!(
        paused_but_unsettled.speech_final,
        "the fixture no longer sets speech_final, so this test is not exercising the trap"
    );

    let settled_without_pause = expect_results(&results_json("verse sixteen", true, false));
    assert!(
        settled_without_pause.to_segment().is_final,
        "settledness was read from speech_final: a settled transcript was marked provisional \
         because the speaker did not pause"
    );
}

#[test]
fn a_missing_settledness_flag_defaults_to_provisional() {
    let json = r#"{"type":"Results","start":0,"duration":1,
                   "channel":{"alternatives":[{"transcript":"hello"}]}}"#;
    let frame = expect_results(json);
    assert!(
        !frame.to_segment().is_final,
        "an absent is_final defaulted to settled; an unknown revision state must never be \
         rendered as confirmed"
    );
}

#[test]
fn timings_map_from_seconds_to_milliseconds() {
    let frame = expect_results(&results_json("hello", true, true));
    let segment = frame.to_segment();
    assert_eq!(segment.start_ms, 2_000, "start seconds were not converted");
    assert_eq!(
        segment.end_ms, 3_500,
        "end is not start + duration in milliseconds"
    );
    assert!(segment.end_ms >= segment.start_ms);
}

#[test]
fn hostile_timings_never_panic_and_never_invert() {
    // A network peer's floats are untrusted input. Negative, enormous and absent values must
    // all produce a sane segment rather than a panic or a wrapped-around timestamp.
    for (start, duration) in [
        ("-5.0", "1.0"),
        ("1e308", "1e308"),
        ("0", "-1000"),
        ("0.0", "0.0"),
    ] {
        let json = format!(
            r#"{{"type":"Results","start":{start},"duration":{duration},
                 "is_final":true,
                 "channel":{{"alternatives":[{{"transcript":"x"}}]}}}}"#
        );
        let segment = expect_results(&json).to_segment();
        assert!(
            segment.end_ms >= segment.start_ms,
            "start={start} duration={duration} produced an inverted segment \
             ({} > {})",
            segment.start_ms,
            segment.end_ms
        );
    }
}

#[test]
fn an_empty_interim_transcript_parses_rather_than_erroring() {
    // Deepgram sends these constantly during silence. Treating them as protocol errors would
    // end a stream every time the preacher paused; the queue is what refuses them.
    let frame = expect_results(&results_json("", false, false));
    assert_eq!(frame.transcript, "");
}

#[test]
fn an_unknown_message_type_is_forward_compatible_rather_than_fatal() {
    let frame = parse_frame(r#"{"type":"SomethingDeepgramAddedLater","x":1}"#);
    match frame {
        Ok(DeepgramFrame::Other { kind }) => assert_eq!(kind, "SomethingDeepgramAddedLater"),
        other => panic!(
            "an unknown message type was not forward-compatible: {other:?} — Deepgram adding a \
             message type would end a service's transcription"
        ),
    }
}

#[test]
fn the_other_recognised_message_types_parse() {
    assert!(matches!(
        parse_frame(r#"{"type":"Metadata","request_id":"req-1"}"#),
        Ok(DeepgramFrame::Metadata { ref request_id }) if request_id == "req-1"
    ));
    assert!(matches!(
        parse_frame(r#"{"type":"UtteranceEnd","last_word_end":4.25}"#),
        Ok(DeepgramFrame::UtteranceEnd {
            last_word_end_ms: 4_250
        })
    ));
    assert!(matches!(
        parse_frame(r#"{"type":"SpeechStarted"}"#),
        Ok(DeepgramFrame::SpeechStarted)
    ));
}

#[test]
fn malformed_input_is_a_protocol_error_rather_than_a_panic() {
    for hostile in [
        "",
        "not json at all",
        "{}",
        r#"{"type":123}"#,
        r#"{"type":"Results"}"#,
        r#"{"type":"Results","channel":{"alternatives":[]}}"#,
        r#"{"type":"Results","channel":{"alternatives":[{"transcript":42}]}}"#,
    ] {
        match parse_frame(hostile) {
            Err(DeepgramError::Protocol { .. }) => {}
            other => panic!("hostile input {hostile:?} was not refused: {other:?}"),
        }
    }
}

#[test]
fn an_oversized_frame_is_refused_and_a_normal_one_is_still_accepted() {
    let huge = format!(
        r#"{{"type":"Results","channel":{{"alternatives":[{{"transcript":"{}"}}]}}}}"#,
        "a".repeat(MAX_FRAME_BYTES)
    );
    assert!(huge.len() > MAX_FRAME_BYTES);
    match parse_frame(&huge) {
        Err(DeepgramError::Protocol { detail }) => assert!(
            detail.contains("exceeds"),
            "the oversized frame was refused for the wrong reason: {detail}"
        ),
        other => panic!(
            "an oversized frame was parsed: {other:?} — a hostile peer could make this client \
             allocate without limit"
        ),
    }

    // The positive control, in the same test: without it, "refused" is indistinguishable from
    // a parser that refuses everything.
    let ordinary = results_json("still parses", true, true);
    assert!(
        ordinary.len() < MAX_FRAME_BYTES,
        "the control frame is itself over the cap, so it proves nothing"
    );
    assert!(
        parse_frame(&ordinary).is_ok(),
        "an ordinary frame was refused too; the size guard is not size-dependent"
    );
}
