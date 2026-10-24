//! FR-082 over a REAL pinned-TLS control link (17tnw2axppb): a host whose reply does not match the
//! request must never get its payload echoed into the operator's error.
//!
//! `RemoteOperator` used to report a non-conforming reply as
//! `TransportError::Protocol(format!("expected X, got: {other:?}"))` - a `Debug` dump of the
//! whole `ServerMessage`, which for `OperatorState` carries the live transcript, the partial
//! transcript and the detections verbatim. Every caller that logged the error or handed its
//! `to_string()` to the operator UI leaked it. `src/operator_reply.rs`'s unit tests prove each
//! parsing branch with no network; this file proves the same through the real server -> wire ->
//! client -> public `RemoteOperator` method path, which is the path the operator process takes,
//! AND pins which methods tolerate a host refusal (`Denied`) and which treat it as an error: the
//! parsers are same-typed, so only a test through the public method can catch a swap.
//!
//! Not reachable here (the real `ControlServer` answers them itself and never consults the
//! handler, so a hostile reply cannot be injected): `new_pairing_code` and the device-management
//! family. Their parsers are covered by the unit tests and their happy paths by
//! `test_operator_remote_management.rs`.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

mod common;

use common::{every_reply, spawn_host, token_for, SECRET, VARIANT_COUNT};
use selahcue_app::RemoteOperator;
use selahcue_lan::protocol::{SermonNoteDraftInput, SermonNoteEditInput, ServerMessage};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::TransportError;
use std::sync::{Arc, Mutex};

/// One public `RemoteOperator` method under test: what its error must name as expected, and for
/// each reply kind it ACCEPTS what shape the `Ok` value has ("some"/"none" for an `Option`,
/// "ok" for a value). Any other reply kind must be a `Protocol` error.
struct Method {
    name: &'static str,
    expected: &'static str,
    accepts: &'static [(&'static str, &'static str)],
}

/// The expectation table. The `denied` rows are the point: save, update and the three
/// regeneration calls fail SOFT (`Ok(None)`, the draft stays editable locally), every read fails
/// STRICT (an error naming `denied`), and `select` accepts a `Denied` on its first step only to
/// fail on the state read it makes next.
const METHODS: &[Method] = &[
    Method {
        name: "active_transcript_id",
        expected: "active_transcript_id",
        accepts: &[("active_transcript_id", "ok")],
    },
    Method {
        name: "load_sermon_note_draft",
        expected: "sermon_note_draft",
        accepts: &[("sermon_note_draft", "some")],
    },
    Method {
        name: "save_sermon_note_draft",
        expected: "sermon_note_draft",
        accepts: &[("sermon_note_draft", "some"), ("denied", "none")],
    },
    Method {
        name: "update_sermon_note_draft",
        expected: "sermon_note_draft",
        accepts: &[("sermon_note_draft", "some"), ("denied", "none")],
    },
    Method {
        name: "stage_sermon_note_regeneration",
        expected: "sermon_note_regeneration_state",
        accepts: &[
            ("sermon_note_regeneration_state", "some"),
            ("denied", "none"),
        ],
    },
    Method {
        name: "confirm_sermon_note_regeneration",
        expected: "sermon_note_regeneration_state",
        accepts: &[
            ("sermon_note_regeneration_state", "some"),
            ("denied", "none"),
        ],
    },
    Method {
        name: "discard_sermon_note_regeneration",
        expected: "sermon_note_regeneration_state",
        accepts: &[
            ("sermon_note_regeneration_state", "some"),
            ("denied", "none"),
        ],
    },
    Method {
        name: "scripture_search",
        expected: "scripture_results",
        accepts: &[("scripture_results", "ok")],
    },
    Method {
        name: "console_thumbnails",
        expected: "console_thumbnails",
        accepts: &[("console_thumbnails", "ok")],
    },
    Method {
        name: "screen_frame",
        expected: "screen_frame",
        // The sample `ScreenFrame` carries `frame: None`.
        accepts: &[("screen_frame", "none")],
    },
    Method {
        name: "list_autosave_slots",
        expected: "autosave_slots",
        accepts: &[("autosave_slots", "ok")],
    },
    Method {
        name: "view",
        expected: "operator_state",
        accepts: &[("operator_state", "ok")],
    },
    // `select` is two round trips and ONE fixed reply cannot satisfy both: an ack/denied passes
    // the first and fails the state read, anything else fails the first. No kind is accepted.
    Method {
        name: "select",
        expected: "ack or denied",
        accepts: &[],
    },
];

fn shape<T>(o: &Option<T>) -> &'static str {
    if o.is_none() {
        "none"
    } else {
        "some"
    }
}

fn draft_input() -> SermonNoteDraftInput {
    SermonNoteDraftInput {
        title: "t".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: false,
        disclosure: None,
        provider: "p".into(),
        model: None,
    }
}

fn edit_input() -> SermonNoteEditInput {
    SermonNoteEditInput {
        title: "t".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
    }
}

async fn call(op: &mut RemoteOperator, method: &str) -> Result<&'static str, TransportError> {
    match method {
        "active_transcript_id" => op.active_transcript_id().await.map(|_| "ok"),
        "load_sermon_note_draft" => op.load_sermon_note_draft(1).await.map(|d| shape(&d)),
        "save_sermon_note_draft" => op
            .save_sermon_note_draft(1, draft_input())
            .await
            .map(|d| shape(&d)),
        "update_sermon_note_draft" => op
            .update_sermon_note_draft(1, edit_input())
            .await
            .map(|d| shape(&d)),
        "stage_sermon_note_regeneration" => op
            .stage_sermon_note_regeneration(1, draft_input())
            .await
            .map(|s| shape(&s)),
        "confirm_sermon_note_regeneration" => op
            .confirm_sermon_note_regeneration(1)
            .await
            .map(|s| shape(&s)),
        "discard_sermon_note_regeneration" => op
            .discard_sermon_note_regeneration(1)
            .await
            .map(|s| shape(&s)),
        "scripture_search" => op.scripture_search("grace", None).await.map(|_| "ok"),
        "console_thumbnails" => op.console_thumbnails(8, 8).await.map(|_| "ok"),
        "screen_frame" => op.screen_frame("main", 8, 8).await.map(|f| shape(&f)),
        "list_autosave_slots" => op.list_autosave_slots().await.map(|_| "ok"),
        "view" => op.view().await.map(|_| "ok"),
        "select" => op.select(1).await.map(|_| "ok"),
        other => panic!("unknown method {other}"),
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn every_reachable_method_x_every_reply_variant_over_the_wire() {
    let shared = Arc::new(Mutex::new(ServerMessage::Ack { request_id: 0 }));
    let reply = shared.clone();
    let handler: Handler =
        Arc::new(move |_role, _cmd| Reply::Message(Box::new(reply.lock().unwrap().clone())));
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op =
        RemoteOperator::connect(addr, "localhost", pin, "operator", &token_for("operator"))
            .await
            .unwrap();

    let (mut oks, mut errs) = (0, 0);
    for hostile in every_reply(SECRET) {
        let got = hostile.kind();
        *shared.lock().unwrap() = hostile;
        for m in METHODS {
            let outcome = call(&mut op, m.name).await;
            if let Some((_, want_shape)) = m.accepts.iter().find(|(k, _)| *k == got) {
                assert_eq!(
                    outcome.as_ref().ok(),
                    Some(want_shape),
                    "{} / {got}: wrong outcome {outcome:?}",
                    m.name
                );
                oks += 1;
                continue;
            }
            // `select` fails on its SECOND step when the first accepted a Ack/Denied.
            let expected = if m.name == "select" && matches!(got, "ack" | "denied") {
                "operator_state"
            } else {
                m.expected
            };
            let err = outcome.expect_err(&format!("{} accepted a {got} reply", m.name));
            assert!(
                matches!(err, TransportError::Protocol(_)),
                "{} / {got}: expected a protocol error, got {err}",
                m.name
            );
            for (how, text) in [("Display", err.to_string()), ("Debug", format!("{err:?}"))] {
                assert!(
                    !text.contains(SECRET) && !text.contains("SECRET"),
                    "{} / {got}: {how} leaked the host's reply: {text}",
                    m.name
                );
                assert!(
                    text.contains(&format!("got: {got}")),
                    "{} / {got}: {how} must name the variant received: {text}",
                    m.name
                );
                assert!(
                    text.contains(expected),
                    "{} / {got}: {how} must name what was expected ({expected}): {text}",
                    m.name
                );
                // Short and plain: a payload (or a Debug dump of one) cannot fit in this.
                assert!(
                    text.is_ascii() && text.len() < 120,
                    "{} / {got}: {how} is not a short ASCII label: {text}",
                    m.name
                );
            }
            errs += 1;
        }
    }
    let accepted: usize = METHODS.iter().map(|m| m.accepts.len()).sum();
    assert_eq!(oks, accepted, "every accepted (method, reply) pair was run");
    assert_eq!(
        oks + errs,
        METHODS.len() * VARIANT_COUNT,
        "no (method, reply) pair was skipped"
    );
    host.shutdown_background();
}

/// `act` is two round trips: the command (expects an ack) then a state read. A host that acks
/// but then answers the state read with something else must fail at the SECOND step with the
/// second step's label.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_mutating_command_checks_both_of_its_round_trips() {
    let handler: Handler = Arc::new(|_role, _cmd| Reply::Ack);
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op =
        RemoteOperator::connect(addr, "localhost", pin, "operator", &token_for("operator"))
            .await
            .unwrap();
    // Ack for the command, then the state read also gets an Ack (not operator_state).
    let err = op.select(1).await.expect_err("state read got an ack");
    let text = format!("{err} / {err:?}");
    assert!(text.contains("expected operator_state, got: ack"), "{text}");
    host.shutdown_background();
}

/// The matching reply still works end to end (the redaction did not break the happy path), with
/// its payload delivered to the caller untouched - the error text is redacted, the VALUE is not.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn matching_replies_still_succeed_over_the_wire() {
    let shared = Arc::new(Mutex::new(ServerMessage::ActiveTranscriptId {
        transcript_id: Some(42),
    }));
    let reply = shared.clone();
    let handler: Handler =
        Arc::new(move |_role, _cmd| Reply::Message(Box::new(reply.lock().unwrap().clone())));
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op =
        RemoteOperator::connect(addr, "localhost", pin, "operator", &token_for("operator"))
            .await
            .unwrap();
    assert_eq!(op.active_transcript_id().await.unwrap(), Some(42));

    *shared.lock().unwrap() = ServerMessage::SermonNoteDraft {
        transcript_id: 42,
        draft: Some(common::draft_view(SECRET)),
    };
    let loaded = op.load_sermon_note_draft(42).await.unwrap().unwrap();
    assert_eq!(loaded.title, format!("{SECRET}-title"));

    *shared.lock().unwrap() = ServerMessage::SermonNoteDraft {
        transcript_id: 42,
        draft: None,
    };
    assert!(op.load_sermon_note_draft(42).await.unwrap().is_none());

    *shared.lock().unwrap() = common::operator_state(SECRET);
    let view = op.view().await.unwrap();
    assert_eq!(view.plan_name, format!("{SECRET}-plan"));
    host.shutdown_background();
}

/// Connection-failure paths: a host that is not there, and a host that goes away mid-session.
/// Neither is a "non-conforming reply", so neither may be reported as one, and neither can carry
/// the host's last reply text.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn connection_failures_are_errors_that_carry_no_reply_text() {
    // 1. Nothing is listening: bind a port, then free it.
    let free = {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap()
    };
    let identity = selahcue_lan::SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let refused = RemoteOperator::connect(free, "localhost", identity.pin, "operator", "tok-op")
        .await
        .err()
        .expect("connecting to a closed port must fail");
    assert!(!refused.to_string().contains("SECRET"), "{refused}");

    // 2. The host dies after the link is up (and after it had sent a payload carrying SECRET).
    let hostile = common::operator_state(SECRET);
    let handler: Handler = Arc::new(move |_role, _cmd| Reply::Message(Box::new(hostile.clone())));
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op =
        RemoteOperator::connect(addr, "localhost", pin, "operator", &token_for("operator"))
            .await
            .unwrap();
    let first = op.active_transcript_id().await.expect_err("hostile reply");
    assert!(first.to_string().contains("got: operator_state"), "{first}");
    host.shutdown_background();
    // Give the severed sockets a moment to be observed by the client side.
    tokio::time::sleep(std::time::Duration::from_millis(300)).await;
    let after = op
        .active_transcript_id()
        .await
        .expect_err("a dead host must be an error, not a value");
    let text = format!("{after} / {after:?}");
    assert!(
        !text.contains("SECRET"),
        "a connection failure must not carry reply text: {text}"
    );
    assert!(
        !matches!(after, TransportError::Protocol(ref m) if m.starts_with("expected ")),
        "a dead connection is a transport failure, not a non-conforming reply: {text}"
    );
}
