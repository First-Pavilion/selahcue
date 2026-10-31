//! Public helpers must not require callers to remember transport-specific redaction.
//! Ungated: this boundary also exists when the server/TLS feature is disabled.
#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{from_json, to_json, Command, Hello, Request, ServerMessage};
use serde::Serialize;
use std::error::Error;

const SECRET: &str = "PRIVATE-SERMON-9f3a-PAIR-TOKEN";
const NUMBER: &str = "4815162342";

struct ParseCase {
    name: &'static str,
    text: String,
    secret: &'static str,
    raw: fn(&str) -> serde_json::Error,
    shown: fn(&str) -> Vec<String>,
}

fn renderings(error: &dyn Error) -> Vec<String> {
    let mut out = vec![
        error.to_string(),
        format!("{error:?}"),
        format!("{error:#?}"),
    ];
    let mut cause = error.source();
    for _ in 0..8 {
        let Some(next) = cause else { return out };
        out.extend([next.to_string(), format!("{next:?}"), format!("{next:#?}")]);
        cause = next.source();
    }
    assert!(
        cause.is_none(),
        "the JSON failure source chain must terminate"
    );
    out
}

fn raw<T: serde::de::DeserializeOwned + std::fmt::Debug>(text: &str) -> serde_json::Error {
    serde_json::from_str::<T>(text).unwrap_err()
}

fn shown<T: serde::de::DeserializeOwned + std::fmt::Debug>(text: &str) -> Vec<String> {
    renderings(&from_json::<T>(text).unwrap_err())
}

fn cases() -> Vec<ParseCase> {
    vec![
        ParseCase {
            name: "transcript shape",
            text: format!(
                r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":"{SECRET}"}}}}"#
            ),
            secret: SECRET,
            raw: raw::<ServerMessage>,
            shown: shown::<ServerMessage>,
        },
        ParseCase {
            name: "command tag",
            text: format!(r#"{{"cmd":"{SECRET}"}}"#),
            secret: SECRET,
            raw: raw::<Command>,
            shown: shown::<Command>,
        },
        ParseCase {
            name: "pairing code numeric",
            text: format!(
                r#"{{"hello":"pair","v":2,"code":{NUMBER},"device_name":"phone","platform":"android"}}"#
            ),
            secret: NUMBER,
            raw: raw::<Hello>,
            shown: shown::<Hello>,
        },
        ParseCase {
            name: "token numeric",
            text: format!(r#"{{"hello":"auth","v":2,"device_id":"phone","token":{NUMBER}}}"#),
            secret: NUMBER,
            raw: raw::<Hello>,
            shown: shown::<Hello>,
        },
        ParseCase {
            name: "request id",
            text: format!(r#"{{"v":2,"request_id":"{SECRET}","command":{{"cmd":"get_state"}}}}"#),
            secret: SECRET,
            raw: raw::<Request>,
            shown: shown::<Request>,
        },
    ]
}

fn assert_safe(label: &str, text: &str, secret: &str) {
    let fragments: &[&str] = if secret == NUMBER {
        &[NUMBER, "4815", "162342"]
    } else {
        &[SECRET, "PRIV", "SERMON", "9f3a", "PAIR", "TOKEN"]
    };
    for piece in fragments {
        assert!(
            !text.contains(piece),
            "{label}: public JSON error leaked `{piece}`: {text}"
        );
    }
}

#[derive(Debug)]
struct SensitiveSerializeFailure;
impl Serialize for SensitiveSerializeFailure {
    fn serialize<S: serde::Serializer>(&self, _serializer: S) -> Result<S::Ok, S::Error> {
        Err(serde::ser::Error::custom(SECRET))
    }
}

#[test]
fn raw_parse_premises_really_quote_each_sensitive_value() {
    let all = cases();
    assert_eq!(all.len(), 5);
    for case in all {
        let error = (case.raw)(&case.text);
        assert!(error.is_data(), "{}", case.name);
        assert!(error.to_string().contains(case.secret), "{}", case.name);
        assert!(format!("{error:?}").contains(case.secret), "{}", case.name);
    }
}

#[test]
fn raw_serialize_premise_really_quotes_the_custom_sensitive_message() {
    let raw = serde_json::to_string(&SensitiveSerializeFailure).unwrap_err();
    assert!(raw.is_data());
    assert!(raw.to_string().contains(SECRET));
    assert!(format!("{raw:?}").contains(SECRET));
}

#[test]
fn public_parse_display_never_quotes_sensitive_values() {
    for case in cases() {
        assert_safe(case.name, &(case.shown)(&case.text)[0], case.secret);
    }
}
#[test]
fn public_parse_debug_never_quotes_sensitive_values() {
    for case in cases() {
        assert_safe(case.name, &(case.shown)(&case.text)[1], case.secret);
    }
}
#[test]
fn public_parse_alternate_debug_never_quotes_sensitive_values() {
    for case in cases() {
        assert_safe(case.name, &(case.shown)(&case.text)[2], case.secret);
    }
}
#[test]
fn public_parse_source_chain_has_no_sensitive_cause() {
    for case in cases() {
        for cause in (case.shown)(&case.text).iter().skip(3) {
            assert_safe(case.name, cause, case.secret);
        }
    }
}
#[test]
fn public_serialize_display_never_quotes_sensitive_values() {
    let error = to_json(&SensitiveSerializeFailure).unwrap_err();
    assert_safe("serialize Display", &error.to_string(), SECRET);
}
#[test]
fn public_serialize_debug_never_quotes_sensitive_values() {
    let error = to_json(&SensitiveSerializeFailure).unwrap_err();
    assert_safe("serialize Debug", &format!("{error:?}"), SECRET);
}
#[test]
fn public_serialize_alternate_debug_never_quotes_sensitive_values() {
    let error = to_json(&SensitiveSerializeFailure).unwrap_err();
    assert_safe("serialize alternate Debug", &format!("{error:#?}"), SECRET);
}
#[test]
fn public_serialize_source_chain_has_no_sensitive_cause() {
    let error = to_json(&SensitiveSerializeFailure).unwrap_err();
    for cause in renderings(&error).iter().skip(3) {
        assert_safe("serialize source", cause, SECRET);
    }
}
#[test]
fn valid_wire_and_borrowed_decode_remain_exact() {
    assert_eq!(to_json(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
    assert_eq!(
        from_json::<Command>(r#"{"cmd":"go_live"}"#).unwrap(),
        Command::GoLive
    );
    let text = r#""borrowed transcript""#;
    let decoded: &str = from_json(text).unwrap();
    assert_eq!(decoded, "borrowed transcript");
    assert_eq!(decoded.as_ptr(), text[1..].as_ptr());
    let request = r#"{"v":2,"request_id":7,"command":{"cmd":"get_state"}}"#;
    let decoded: Request = from_json(request).unwrap();
    assert_eq!(to_json(&decoded).unwrap(), request);
}
#[test]
fn parse_positions_still_match_real_serde_syntax_eof_and_data_errors() {
    for text in ["{", "{\n broken", "\n 42", r#"{"cmd":"unknown-command"}"#] {
        let raw = serde_json::from_str::<Command>(text).unwrap_err();
        let public = from_json::<Command>(text).unwrap_err();
        assert_eq!((public.line(), public.column()), (raw.line(), raw.column()));
    }
}

#[test]
fn public_helper_return_types_are_the_ungated_safe_type() {
    use selahcue_lan::JsonFailure;
    let decode: fn(&str) -> Result<Command, JsonFailure> = from_json::<Command>;
    let encode: fn(&Command) -> Result<String, JsonFailure> = to_json::<Command>;
    assert_eq!(decode(r#"{"cmd":"go_live"}"#).unwrap(), Command::GoLive);
    assert_eq!(encode(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
    fn safe_error_bounds<T: Error + Send + Sync + Copy + Eq>() {}
    safe_error_bounds::<JsonFailure>();
}

#[test]
fn safe_kind_position_wording_and_conversion_remain_exact_for_all_categories() {
    use selahcue_lan::{JsonFailure, JsonFailureKind};
    struct FailedReader;
    impl std::io::Read for FailedReader {
        fn read(&mut self, _buffer: &mut [u8]) -> std::io::Result<usize> {
            Err(std::io::Error::other(SECRET))
        }
    }
    let errors = [
        (
            serde_json::from_str::<Command>("not JSON").unwrap_err(),
            JsonFailureKind::Syntax,
            "the message was not valid JSON",
        ),
        (
            serde_json::from_str::<Command>("{").unwrap_err(),
            JsonFailureKind::Eof,
            "the message ended early",
        ),
        (
            serde_json::to_string(&SensitiveSerializeFailure).unwrap_err(),
            JsonFailureKind::Data,
            "the message did not have the shape the protocol defines",
        ),
        (
            serde_json::from_reader::<_, Command>(FailedReader).unwrap_err(),
            JsonFailureKind::Io,
            "the message could not be read",
        ),
    ];
    for (raw, kind, words) in errors {
        let borrowed = JsonFailure::from(&raw);
        assert_eq!(borrowed.kind(), kind);
        assert_eq!(
            (borrowed.line(), borrowed.column()),
            (raw.line(), raw.column())
        );
        let expected = if raw.line() == 0 {
            format!("{words} (no position)")
        } else {
            format!("{words} at line {} column {}", raw.line(), raw.column())
        };
        assert_eq!(borrowed.to_string(), expected);
        let owned = JsonFailure::from(raw);
        assert_eq!(owned, borrowed);
        assert!(Error::source(&owned).is_none());
        for text in renderings(&owned) {
            assert_safe("safe category conversion", &text, SECRET);
        }
        #[cfg(feature = "server")]
        {
            let old_path: selahcue_lan::tls::JsonFailure = owned;
            let old_kind: selahcue_lan::tls::JsonFailureKind = kind;
            assert_eq!(old_kind, old_path.kind());
            let transport = selahcue_lan::TransportError::from(owned);
            match &transport {
                selahcue_lan::TransportError::Json(actual) => assert_eq!(*actual, owned),
                other => panic!("safe conversion changed transport variant: {other:?}"),
            }
            for text in renderings(&transport) {
                assert_safe("transport conversion", &text, SECRET);
            }
        }
    }
}
