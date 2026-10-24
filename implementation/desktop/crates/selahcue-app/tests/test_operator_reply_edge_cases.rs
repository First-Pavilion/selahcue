//! Edge cases for the redacting reply path (17tnw2axppb), over a real pinned-TLS control link:
//! the error text must be INDEPENDENT of the payload, a mismatch must cost exactly one round trip,
//! a connection must survive any number of mismatches and then serve a conforming reply, parallel
//! connections must not see each other's replies, and a stalled host must produce the transport's
//! own timeout errors (not a reply-shaped one).

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

mod common;

use common::{operator_state, spawn_host, token_for, SECRET};
use selahcue_app::RemoteOperator;
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::{CertPin, TransportError};
use std::net::SocketAddr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

async fn connect(addr: SocketAddr, pin: CertPin, device: &str) -> RemoteOperator {
    RemoteOperator::connect(addr, "localhost", pin, device, &token_for(device))
        .await
        .unwrap()
}

fn fixed_reply_handler(reply: ServerMessage) -> Handler {
    Arc::new(move |_role, _cmd| Reply::Message(Box::new(reply.clone())))
}

/// The error text is a function of (what was expected, which variant arrived) and NOTHING else:
/// an empty payload, unicode with control and bidi-override characters, and a payload near the
/// frame cap all produce byte-identical errors. A format that interpolated any payload (Debug or
/// Display) would differ between them.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn the_error_text_is_independent_of_the_payload() {
    let payloads = [
        String::new(),
        "caf\u{e9} \u{4e16}\u{754c} \u{202e}rtl\u{202c} \u{0} \u{7} \n\t \"quoted\" {braces} \\"
            .to_string(),
        "A".repeat(40_000),
    ];
    for (reply_name, make) in [
        (
            "error",
            (|m: &str| ServerMessage::Error { message: m.into() }) as fn(&str) -> ServerMessage,
        ),
        ("operator_state", |m: &str| operator_state(m)),
    ] {
        let mut texts = Vec::new();
        for payload in &payloads {
            let (addr, pin, host) = spawn_host(fixed_reply_handler(make(payload)), &["operator"]);
            let mut op = connect(addr, pin, "operator").await;
            let err = op.active_transcript_id().await.expect_err("a mismatch");
            texts.push((err.to_string(), format!("{err:?}")));
            host.shutdown_background();
        }
        let expected = format!("protocol error: expected active_transcript_id, got: {reply_name}");
        for (display, debug) in &texts {
            assert_eq!(display, &expected);
            assert_eq!(
                debug,
                &format!("Protocol(\"expected active_transcript_id, got: {reply_name}\")")
            );
        }
    }
}

/// A mismatch on the FIRST step of a mutating command costs exactly one round trip: the host
/// sees the command and no follow-up state read. (Control: a conforming first step IS followed by
/// the state read.)
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_first_step_mismatch_sends_one_round_trip_and_no_state_read() {
    let seen: Arc<Mutex<Vec<Command>>> = Arc::new(Mutex::new(Vec::new()));
    let log = seen.clone();
    let conforming = Arc::new(AtomicBool::new(false));
    let flag = conforming.clone();
    let handler: Handler = Arc::new(move |_role, cmd| {
        log.lock().unwrap().push(cmd.clone());
        match (cmd, flag.load(Ordering::SeqCst)) {
            (Command::GetOperatorState, true) => Reply::Message(Box::new(operator_state("fine"))),
            (_, true) => Reply::Ack,
            (_, false) => Reply::Message(Box::new(ServerMessage::Error {
                message: SECRET.into(),
            })),
        }
    });
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op = connect(addr, pin, "operator").await;

    let err = op.select(7).await.expect_err("the first step mismatched");
    assert!(
        err.to_string()
            .ends_with("expected ack or denied, got: error"),
        "{err}"
    );
    {
        let sent = seen.lock().unwrap();
        assert_eq!(sent.len(), 1, "exactly one round trip: {sent:?}");
        assert!(matches!(sent[0], Command::SelectItem { item_id: 7 }));
    }

    // Control: with a conforming ack the SAME call makes the second (state read) round trip.
    seen.lock().unwrap().clear();
    conforming.store(true, Ordering::SeqCst);
    op.select(7).await.expect("conforming ack + state");
    let sent = seen.lock().unwrap();
    assert_eq!(sent.len(), 2, "{sent:?}");
    assert!(matches!(sent[1], Command::GetOperatorState));
    drop(sent);
    host.shutdown_background();
}

/// 200 mismatches in a row on one connection leave it fully usable: the next conforming reply on
/// the SAME connection succeeds (a mismatch is not a poisoned connection and leaks nothing).
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn many_mismatches_then_a_conforming_reply_on_the_same_connection() {
    let shared = Arc::new(Mutex::new(operator_state(SECRET)));
    let reply = shared.clone();
    let handler: Handler =
        Arc::new(move |_role, _cmd| Reply::Message(Box::new(reply.lock().unwrap().clone())));
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op = connect(addr, pin, "operator").await;

    for i in 0..200 {
        let err = op
            .active_transcript_id()
            .await
            .expect_err("every one of these is a mismatch");
        assert_eq!(
            err.to_string(),
            "protocol error: expected active_transcript_id, got: operator_state",
            "mismatch #{i}"
        );
    }
    *shared.lock().unwrap() = ServerMessage::ActiveTranscriptId {
        transcript_id: Some(5),
    };
    assert_eq!(op.active_transcript_id().await.unwrap(), Some(5));
    host.shutdown_background();
}

/// Six connections, each hammering a DIFFERENT method 50 times against a host that answers each
/// command with a different wrong variant: every error names its own method's expectation and its
/// own wrong variant, so no connection ever saw another's reply.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn parallel_connections_do_not_see_each_others_replies() {
    let handler: Handler = Arc::new(|_role, cmd| {
        let reply = match cmd {
            Command::GetActiveTranscriptId => operator_state(SECRET),
            Command::LoadSermonNoteDraft { .. } => ServerMessage::Error {
                message: SECRET.into(),
            },
            Command::ScriptureSearch { .. } => ServerMessage::PairingCode {
                code: SECRET.into(),
                fingerprint: SECRET.into(),
                expires_in_secs: 1,
                uri: None,
            },
            Command::GetConsoleThumbnails { .. } => ServerMessage::State {
                live_item: None,
                blackout: false,
            },
            Command::GetScreenFrame { .. } => ServerMessage::AutosaveSlots { slots: vec![] },
            Command::ListAutosaveSlots => ServerMessage::ActiveTranscriptId {
                transcript_id: Some(1),
            },
            _ => ServerMessage::Error {
                message: "unexpected command".into(),
            },
        };
        Reply::Message(Box::new(reply))
    });
    let devices = ["d0", "d1", "d2", "d3", "d4", "d5"];
    let (addr, pin, host) = spawn_host(handler, &devices);

    let mut tasks = Vec::new();
    for (i, device) in devices.iter().enumerate() {
        let mut op = connect(addr, pin, device).await;
        tasks.push(tokio::spawn(async move {
            for n in 0..50 {
                let (err, want) = match i {
                    0 => (
                        op.active_transcript_id().await.err(),
                        "expected active_transcript_id, got: operator_state",
                    ),
                    1 => (
                        op.load_sermon_note_draft(1).await.err(),
                        "expected sermon_note_draft, got: error",
                    ),
                    2 => (
                        op.scripture_search("x", None).await.err(),
                        "expected scripture_results, got: pairing_code",
                    ),
                    3 => (
                        op.console_thumbnails(4, 4).await.err(),
                        "expected console_thumbnails, got: state",
                    ),
                    4 => (
                        op.screen_frame("main", 4, 4).await.err(),
                        "expected screen_frame, got: autosave_slots",
                    ),
                    _ => (
                        op.list_autosave_slots().await.err(),
                        "expected autosave_slots, got: active_transcript_id",
                    ),
                };
                let err = err.unwrap_or_else(|| panic!("connection {i} round {n}: no error"));
                assert_eq!(
                    err.to_string(),
                    format!("protocol error: {want}"),
                    "connection {i} round {n}"
                );
            }
        }));
    }
    for t in tasks {
        t.await.unwrap();
    }
    host.shutdown_background();
}

/// A host that stalls past the 2 s command timeout yields the TRANSPORT's own errors - first
/// "command timed out", then (the connection is poisoned because the abandoned reply could be
/// misread as the next answer) "desynchronized ... reconnect required" - never a reply-shaped
/// "expected X, got: Y". Own runtime: the host's blocking sleep must not stall the client timer.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_stalled_host_gives_the_transport_timeout_then_the_desync_refusal() {
    let first = Arc::new(AtomicBool::new(true));
    let handler: Handler = Arc::new(move |_role, _cmd| {
        if first.swap(false, Ordering::SeqCst) {
            std::thread::sleep(Duration::from_millis(2_600));
        }
        Reply::Message(Box::new(operator_state(SECRET)))
    });
    let (addr, pin, host) = spawn_host(handler, &["operator"]);
    let mut op = connect(addr, pin, "operator").await;

    let timed_out = op
        .active_transcript_id()
        .await
        .expect_err("the stalled first command must time out");
    assert!(
        matches!(&timed_out, TransportError::Protocol(m) if m == "command timed out"),
        "{timed_out}"
    );
    let refused = op
        .active_transcript_id()
        .await
        .expect_err("a connection that timed out refuses further commands");
    let text = refused.to_string();
    assert!(
        text.contains("desynchronized") && text.contains("reconnect required"),
        "{text}"
    );
    for e in [&timed_out, &refused] {
        let both = format!("{e} / {e:?}");
        assert!(
            !both.contains("SECRET") && !both.contains("got:"),
            "a transport error must not be reply-shaped or carry reply text: {both}"
        );
    }
    host.shutdown_background();
}
