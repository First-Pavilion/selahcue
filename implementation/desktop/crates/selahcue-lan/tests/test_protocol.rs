//! Wire-protocol serialization tests — the JSON shapes are a compatibility contract.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{
    from_json, to_json, AuthRequest, AuthResponse, Command, DenyReason, Request, ServerMessage,
    VERSION,
};
use selahcue_lan::rbac::Role;

#[test]
fn command_tag_encoding_is_stable() {
    // The `cmd` discriminator and snake_case names are a wire contract.
    assert_eq!(to_json(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
    assert_eq!(
        to_json(&Command::Blackout { on: true }).unwrap(),
        r#"{"cmd":"blackout","on":true}"#
    );
    assert_eq!(
        to_json(&Command::SelectItem { item_id: 7 }).unwrap(),
        r#"{"cmd":"select_item","item_id":7}"#
    );
}

#[test]
fn request_round_trips_and_stamps_version() {
    let req = Request::new(42, Command::ScriptureSearch { query: "love".into() });
    assert_eq!(req.v, VERSION);
    let json = to_json(&req).unwrap();
    let back: Request = from_json(&json).unwrap();
    assert_eq!(back, req);
    assert_eq!(back.request_id, 42);
}

#[test]
fn every_command_round_trips() {
    let cmds = [
        Command::GoLive,
        Command::Next,
        Command::Previous,
        Command::Clear,
        Command::SelectItem { item_id: 9 },
        Command::Blackout { on: false },
        Command::StartTimer { seconds: 300 },
        Command::StopTimer,
        Command::ScriptureSearch { query: "grace".into() },
        Command::StageScripture { reference: "Rom 8:28".into() },
        Command::GetState,
    ];
    for c in cmds {
        let json = to_json(&c).unwrap();
        let back: Command = from_json(&json).unwrap();
        assert_eq!(back, c, "round-trip failed for {json}");
    }
}

#[test]
fn server_messages_round_trip() {
    let msgs = [
        ServerMessage::Ack { request_id: 1 },
        ServerMessage::Denied {
            request_id: 2,
            reason: DenyReason::Forbidden,
        },
        ServerMessage::State {
            live_item: Some(5),
            blackout: true,
        },
        ServerMessage::ScriptureResults {
            query: "peace".into(),
            references: vec!["John 14:27".into(), "Phil 4:7".into()],
        },
        ServerMessage::Error {
            message: "boom".into(),
        },
    ];
    for m in msgs {
        let json = to_json(&m).unwrap();
        let back: ServerMessage = from_json(&json).unwrap();
        assert_eq!(back, m, "round-trip failed for {json}");
    }
}

#[test]
fn auth_frames_round_trip() {
    let req = AuthRequest {
        v: VERSION,
        device_id: "ipad-01".into(),
        token: "deadbeef".into(),
    };
    let back: AuthRequest = from_json(&to_json(&req).unwrap()).unwrap();
    assert_eq!(back, req);

    let granted = AuthResponse::Granted {
        role: Role::Producer,
    };
    assert_eq!(
        to_json(&granted).unwrap(),
        r#"{"auth":"granted","role":"producer"}"#
    );
    let rejected = AuthResponse::Rejected {
        reason: DenyReason::Unauthenticated,
    };
    let back: AuthResponse = from_json(&to_json(&rejected).unwrap()).unwrap();
    assert_eq!(back, rejected);
}

#[test]
fn unknown_command_tag_is_rejected() {
    // Forward-compat/robustness: an unknown command must fail to parse, not panic.
    let res: Result<Command, _> = from_json(r#"{"cmd":"launch_missiles"}"#);
    assert!(res.is_err());
}

#[test]
fn auth_request_debug_redacts_the_token() {
    // The auth frame carries a live credential — its Debug must not leak it.
    let req = AuthRequest {
        v: VERSION,
        device_id: "ipad-01".into(),
        token: "super-secret-bearer-token".into(),
    };
    let shown = format!("{req:?}");
    assert!(
        !shown.contains("super-secret-bearer-token"),
        "auth token leaked via Debug: {shown}"
    );
    // Non-secret fields are still visible for diagnostics.
    assert!(shown.contains("ipad-01"));
}

#[test]
fn version_support_check() {
    assert!(Request::new(1, Command::GoLive).version_supported());
    let stale = Request {
        v: VERSION + 1,
        request_id: 1,
        command: Command::GoLive,
    };
    assert!(!stale.version_supported());
    let auth = AuthRequest {
        v: VERSION,
        device_id: "d".into(),
        token: "t".into(),
    };
    assert!(auth.version_supported());
}
