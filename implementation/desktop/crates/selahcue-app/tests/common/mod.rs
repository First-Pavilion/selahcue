//! Shared fixtures for the FR-082 reply-redaction tests (17tnw2axppb): one sample of EVERY
//! `ServerMessage` variant carrying a planted marker in every free-text field, and a hostile
//! control host whose handler the test supplies.
//!
//! Included by `tests/test_operator_reply_redaction.rs`, `tests/test_operator_reply_edge_cases.rs`
//! and (via `#[path]`) `src/operator_reply.rs`'s unit tests, so there is ONE copy of the fixture.

#![allow(dead_code, clippy::unwrap_used)]

use selahcue_lan::protocol::{
    AutosaveSlotView, DenyReason, RemoteDeviceView, ScriptureHitView, SermonNoteDraftView,
    ServerMessage, ThumbView, VerseView,
};
use selahcue_lan::server::Handler;
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlServer, Role, SelfSigned};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex as AsyncMutex;

pub const SECRET: &str = "SECRET-LIVE-TEXT-7f3a";

/// The number of `ServerMessage` variants. [`variant_index`] is an exhaustive `match` with no
/// wildcard, so adding a variant stops this file compiling until it has an index; bump this
/// constant with it, and [`every_reply`] then refuses to build until the sample list has an entry
/// for the new variant too.
pub const VARIANT_COUNT: usize = 15;

pub fn variant_index(m: &ServerMessage) -> usize {
    match m {
        ServerMessage::Ack { .. } => 0,
        ServerMessage::Denied { .. } => 1,
        ServerMessage::State { .. } => 2,
        ServerMessage::ScriptureResults { .. } => 3,
        ServerMessage::Chapter { .. } => 4,
        ServerMessage::OperatorState { .. } => 5,
        ServerMessage::ConsoleThumbnails { .. } => 6,
        ServerMessage::ScreenFrame { .. } => 7,
        ServerMessage::RemoteDevices { .. } => 8,
        ServerMessage::PairingCode { .. } => 9,
        ServerMessage::ActiveTranscriptId { .. } => 10,
        ServerMessage::SermonNoteDraft { .. } => 11,
        ServerMessage::SermonNoteRegenerationState { .. } => 12,
        ServerMessage::AutosaveSlots { .. } => 13,
        ServerMessage::Error { .. } => 14,
    }
}

pub fn draft_view(marker: &str) -> SermonNoteDraftView {
    SermonNoteDraftView {
        title: format!("{marker}-title"),
        summary: Some(format!("{marker}-summary")),
        sections_json: format!(r#"[{{"heading":"{marker}"}}]"#),
        scriptures_json: "[]".into(),
        ai_generated: true,
        disclosure: Some(format!("{marker}-disclosure")),
        provider: format!("{marker}-provider"),
        model: Some(format!("{marker}-model")),
        created_at_ms: 1,
        edited_at_ms: 2,
    }
}

/// An `OperatorState` reply: the realistic worst case, with the live transcript, the partial
/// transcript and a detection (reference and verse text) all carrying `marker`. Built through
/// `serde_json` so `marker` may be any text (quotes, control characters, a very long string).
pub fn operator_state(marker: &str) -> ServerMessage {
    serde_json::from_value(serde_json::json!({
        "event": "operator_state",
        "view": {
            "plan_name": format!("{marker}-plan"),
            "items": [],
            "live_index": null,
            "staged_index": null,
            "blackout": false,
            "timer": null,
            "transcript": [{
                "id": 0, "start_ms": 0, "end_ms": 1,
                "text": format!("{marker}-transcript"),
            }],
            "partial_transcript": format!("{marker}-partial"),
            "detections": [{
                "id": 1,
                "reference": format!("{marker}-ref"),
                "text": format!("{marker}-detection"),
            }],
        }
    }))
    .unwrap()
}

/// One reply of EVERY `ServerMessage` variant, each carrying `marker` in every free-text field it
/// has. Panics if the list does not cover every variant exactly once.
pub fn every_reply(marker: &str) -> Vec<ServerMessage> {
    let replies = vec![
        ServerMessage::Ack { request_id: 1 },
        ServerMessage::Denied {
            request_id: 2,
            reason: DenyReason::Forbidden,
        },
        ServerMessage::State {
            live_item: Some(5),
            blackout: false,
        },
        ServerMessage::ScriptureResults {
            query: format!("{marker}-query"),
            references: vec![format!("{marker}-reference")],
            hits: vec![ScriptureHitView {
                reference: format!("{marker}-hit-ref"),
                text: format!("{marker}-hit-text"),
            }],
        },
        ServerMessage::Chapter {
            book_name: format!("{marker}-book"),
            chapter: 1,
            translation: "KJV".into(),
            verses: vec![VerseView {
                number: 1,
                text: format!("{marker}-verse"),
            }],
            prev_ref: None,
            next_ref: None,
        },
        operator_state(marker),
        ServerMessage::ConsoleThumbnails {
            preview: Some(ThumbView::from_rgba(1, 1, &[1, 2, 3, 4])),
            live: None,
        },
        ServerMessage::ScreenFrame {
            screen: format!("{marker}-screen"),
            frame: None,
        },
        ServerMessage::RemoteDevices {
            devices: vec![RemoteDeviceView {
                device_id: format!("{marker}-device"),
                name: format!("{marker}-name"),
                platform: "iOS".into(),
                role: Role::Viewer,
                idle_secs: 0,
                pinned: false,
            }],
            pending: vec![],
        },
        ServerMessage::PairingCode {
            code: format!("{marker}-code"),
            fingerprint: format!("{marker}-fingerprint"),
            expires_in_secs: 120,
            uri: Some(format!("selahcue://pair?code={marker}")),
        },
        ServerMessage::ActiveTranscriptId {
            transcript_id: Some(7),
        },
        ServerMessage::SermonNoteDraft {
            transcript_id: 7,
            draft: Some(draft_view(marker)),
        },
        ServerMessage::SermonNoteRegenerationState {
            transcript_id: 7,
            current: Some(draft_view(marker)),
            pending: Some(draft_view(marker)),
        },
        ServerMessage::AutosaveSlots {
            slots: vec![AutosaveSlotView {
                slot: 1,
                saved_at_ms: 1,
                label: Some(format!("{marker}-label")),
            }],
        },
        ServerMessage::Error {
            message: format!("{marker}-error"),
        },
    ];
    let mut seen = [0usize; VARIANT_COUNT];
    for m in &replies {
        seen[variant_index(m)] += 1;
    }
    assert_eq!(
        seen, [1; VARIANT_COUNT],
        "the sample list must hold exactly one reply per ServerMessage variant"
    );
    replies
}

/// The sample reply of the variant named `kind` (its wire label).
pub fn reply_of_kind(marker: &str, kind: &str) -> ServerMessage {
    every_reply(marker)
        .into_iter()
        .find(|m| m.kind() == kind)
        .unwrap_or_else(|| panic!("no ServerMessage variant labelled {kind}"))
}

/// A real pinned-TLS `ControlServer` on its OWN runtime (so dropping/shutting it down severs
/// connections, and a blocking handler cannot stall the client's own timers), answering every
/// RBAC-permitted command through `handler`. Each id in `devices` is paired as `Role::Operator`
/// with token `tok-<id>`.
pub fn spawn_host(
    handler: Handler,
    devices: &[&str],
) -> (SocketAddr, CertPin, tokio::runtime::Runtime) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let mut registry = SessionRegistry::new();
    let now = Instant::now();
    for id in devices {
        registry.offer_pairing(
            format!("p-{id}"),
            Role::Operator,
            now,
            Duration::from_secs(300),
        );
        registry
            .redeem(
                &format!("p-{id}"),
                DeviceId((*id).into()),
                SessionToken::new(format!("tok-{id}")),
                now,
            )
            .unwrap();
    }
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

/// The token for a device paired by [`spawn_host`].
pub fn token_for(device: &str) -> String {
    format!("tok-{device}")
}
