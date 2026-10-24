//! FR-082 over a REAL pinned-TLS control link (17tnw2axppb): a host whose reply does not match the
//! request must never get its payload echoed into the operator's error.
//!
//! `RemoteOperator` used to report a non-conforming reply as
//! `TransportError::Protocol(format!("expected X, got: {other:?}"))` - a `Debug` dump of the
//! whole `ServerMessage`, which for `OperatorState` carries the live transcript, the partial
//! transcript and the detections verbatim. Every caller that logged the error or handed its
//! `to_string()` to the operator UI (the `update_sermon_note_draft` Tauri command's `message`
//! field) leaked it. `src/operator_reply.rs`'s unit tests prove each parsing branch with no
//! network; this file proves the same through the real server -> wire -> client -> public
//! `RemoteOperator` method path, which is the path the operator process actually takes.
//!
//! Not reachable here (the real `ControlServer` answers them itself and never consults the
//! handler, so a hostile reply cannot be injected): `new_pairing_code` and the device-management
//! family (`remote_devices`, `approve_pairing`, ...). Those branches are covered by the unit tests.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::RemoteOperator;
use selahcue_lan::protocol::{
    from_json, SermonNoteDraftInput, SermonNoteDraftView, SermonNoteEditInput, ServerMessage,
    VerseView,
};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlServer, Role, SelfSigned, TransportError};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::Mutex as AsyncMutex;

const SECRET: &str = "SECRET-LIVE-TEXT-91c4";

/// A host that answers EVERY (RBAC-permitted) command with whatever `reply` currently holds.
/// Own runtime, like `selahcue-lan`'s `test_client_timeout.rs`, so dropping it later severs the
/// connections for the connection-failure test.
fn spawn_hostile_host(
    reply: Arc<Mutex<ServerMessage>>,
) -> (SocketAddr, CertPin, tokio::runtime::Runtime) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let mut registry = SessionRegistry::new();
    let now = Instant::now();
    registry.offer_pairing("p", Role::Operator, now, Duration::from_secs(300));
    registry
        .redeem(
            "p",
            DeviceId("operator".into()),
            SessionToken::new("tok-op"),
            now,
        )
        .unwrap();
    let handler: Handler =
        Arc::new(move |_role, _cmd| Reply::Message(Box::new(reply.lock().unwrap().clone())));
    let server = Arc::new(
        ControlServer::new(&identity, Arc::new(AsyncMutex::new(registry)), handler).unwrap(),
    );
    let std_listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    std_listener.set_nonblocking(true).unwrap();
    let addr = std_listener.local_addr().unwrap();
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .unwrap();
    rt.spawn(async move {
        let listener = tokio::net::TcpListener::from_std(std_listener).unwrap();
        let _ = server.run(listener).await;
    });
    (addr, pin, rt)
}

fn draft_view() -> SermonNoteDraftView {
    SermonNoteDraftView {
        title: format!("{SECRET}-title"),
        summary: Some(format!("{SECRET}-summary")),
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: false,
        disclosure: None,
        provider: format!("{SECRET}-provider"),
        model: None,
        created_at_ms: 1,
        edited_at_ms: 2,
    }
}

/// The hostile replies: each carries `SECRET` and none is the right answer to any of the
/// requests below (except by coincidence, filtered per request).
fn hostile_replies() -> Vec<ServerMessage> {
    let operator_state: ServerMessage = from_json(&format!(
        r#"{{"event":"operator_state","view":{{"plan_name":"{SECRET}-plan","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{{"id":0,"start_ms":0,"end_ms":1,"text":"{SECRET}-transcript"}}],"partial_transcript":"{SECRET}-partial","detections":[{{"id":1,"reference":"{SECRET}-ref","text":"{SECRET}-detection"}}]}}}}"#
    ))
    .unwrap();
    vec![
        operator_state,
        ServerMessage::Error {
            message: format!("{SECRET}-host-error"),
        },
        ServerMessage::PairingCode {
            code: format!("{SECRET}-code"),
            fingerprint: format!("{SECRET}-fingerprint"),
            expires_in_secs: 120,
            uri: Some(format!("selahcue://pair?code={SECRET}")),
        },
        ServerMessage::SermonNoteDraft {
            transcript_id: 1,
            draft: Some(draft_view()),
        },
        ServerMessage::Chapter {
            book_name: format!("{SECRET}-book"),
            chapter: 1,
            translation: "KJV".into(),
            verses: vec![VerseView {
                number: 1,
                text: format!("{SECRET}-verse"),
            }],
            prev_ref: None,
            next_ref: None,
        },
    ]
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

/// Reduce any `RemoteOperator` result to its error, if any.
fn err_of<T>(r: Result<T, TransportError>) -> Option<TransportError> {
    r.err()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn every_reachable_method_refuses_a_hostile_reply_without_echoing_it() {
    let shared = Arc::new(Mutex::new(ServerMessage::Ack { request_id: 0 }));
    let (addr, pin, host) = spawn_hostile_host(shared.clone());
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap();

    let mut checked = 0;
    for hostile in hostile_replies() {
        let got = hostile.kind();
        *shared.lock().unwrap() = hostile;

        // (method, the label its error must name as expected, its outcome). A reply that IS
        // the right answer for a method is skipped for that method only.
        let outcomes: Vec<(&str, &str, Option<TransportError>)> = vec![
            (
                "active_transcript_id",
                "active_transcript_id",
                err_of(op.active_transcript_id().await),
            ),
            (
                "load_sermon_note_draft",
                "sermon_note_draft",
                err_of(op.load_sermon_note_draft(1).await),
            ),
            (
                "save_sermon_note_draft",
                "sermon_note_draft",
                err_of(op.save_sermon_note_draft(1, draft_input()).await),
            ),
            (
                "update_sermon_note_draft",
                "sermon_note_draft",
                err_of(op.update_sermon_note_draft(1, edit_input()).await),
            ),
            (
                "stage_sermon_note_regeneration",
                "sermon_note_regeneration_state",
                err_of(op.stage_sermon_note_regeneration(1, draft_input()).await),
            ),
            (
                "confirm_sermon_note_regeneration",
                "sermon_note_regeneration_state",
                err_of(op.confirm_sermon_note_regeneration(1).await),
            ),
            (
                "discard_sermon_note_regeneration",
                "sermon_note_regeneration_state",
                err_of(op.discard_sermon_note_regeneration(1).await),
            ),
            (
                "scripture_search",
                "scripture_results",
                err_of(op.scripture_search("grace", None).await),
            ),
            (
                "console_thumbnails",
                "console_thumbnails",
                err_of(op.console_thumbnails(8, 8).await),
            ),
            (
                "screen_frame",
                "screen_frame",
                err_of(op.screen_frame("main", 8, 8).await),
            ),
            (
                "list_autosave_slots",
                "autosave_slots",
                err_of(op.list_autosave_slots().await),
            ),
            // `view` -> request_state.
            ("view", "operator_state", err_of(op.view().await)),
            // A mutating command (`act`): the FIRST reply is checked against "ack or denied".
            ("select", "ack or denied", err_of(op.select(1).await)),
        ];

        for (method, expected, err) in outcomes {
            let accepted_by_method = matches!(
                (method, got),
                ("load_sermon_note_draft", "sermon_note_draft")
                    | ("save_sermon_note_draft", "sermon_note_draft")
                    | ("update_sermon_note_draft", "sermon_note_draft")
                    | ("view", "operator_state")
            );
            if accepted_by_method {
                assert!(
                    err.is_none(),
                    "{method} must accept its own reply kind {got}"
                );
                continue;
            }
            let err = err.unwrap_or_else(|| panic!("{method} accepted a {got} reply"));
            assert!(
                matches!(err, TransportError::Protocol(_)),
                "{method} / {got}: expected a protocol error, got {err}"
            );
            for (how, text) in [("Display", err.to_string()), ("Debug", format!("{err:?}"))] {
                assert!(
                    !text.contains(SECRET) && !text.contains("SECRET"),
                    "{method} / {got}: {how} leaked the host's reply: {text}"
                );
                assert!(
                    text.contains(&format!("got: {got}")),
                    "{method} / {got}: {how} must name the variant received: {text}"
                );
                assert!(
                    text.contains(expected),
                    "{method} / {got}: {how} must name what was expected ({expected}): {text}"
                );
            }
            checked += 1;
        }
    }
    // 5 hostile replies x 13 methods, minus the 4 (method, reply) pairs that are the right answer.
    assert_eq!(checked, 5 * 13 - 4, "no (method, reply) pair was skipped");
    host.shutdown_background();
}

/// `act` is two round trips: the command (expects an ack) then a state read. A host that acks
/// but then answers the state read with something else must fail at the SECOND step with the
/// second step's label - and an unrelated-but-harmless `Ack` is not an error on the first.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_mutating_command_checks_both_of_its_round_trips() {
    let shared = Arc::new(Mutex::new(ServerMessage::Ack { request_id: 0 }));
    let (addr, pin, host) = spawn_hostile_host(shared.clone());
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "operator", "tok-op")
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
    let (addr, pin, host) = spawn_hostile_host(shared.clone());
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap();
    assert_eq!(op.active_transcript_id().await.unwrap(), Some(42));

    *shared.lock().unwrap() = ServerMessage::SermonNoteDraft {
        transcript_id: 42,
        draft: Some(draft_view()),
    };
    let loaded = op.load_sermon_note_draft(42).await.unwrap().unwrap();
    assert_eq!(loaded.title, format!("{SECRET}-title"));

    *shared.lock().unwrap() = ServerMessage::SermonNoteDraft {
        transcript_id: 42,
        draft: None,
    };
    assert!(op.load_sermon_note_draft(42).await.unwrap().is_none());

    *shared.lock().unwrap() = hostile_replies().remove(0); // the OperatorState
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
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let refused = RemoteOperator::connect(free, "localhost", identity.pin, "operator", "tok-op")
        .await
        .err()
        .expect("connecting to a closed port must fail");
    assert!(!refused.to_string().contains("SECRET"), "{refused}");

    // 2. The host dies after the link is up (and after it had sent a payload carrying SECRET).
    let shared = Arc::new(Mutex::new(hostile_replies().remove(0)));
    let (addr, pin, host) = spawn_hostile_host(shared);
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap();
    let first = op.active_transcript_id().await.expect_err("hostile reply");
    assert!(first.to_string().contains("got: operator_state"), "{first}");
    host.shutdown_background();
    // Give the severed sockets a moment to be observed by the client side.
    tokio::time::sleep(Duration::from_millis(300)).await;
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
