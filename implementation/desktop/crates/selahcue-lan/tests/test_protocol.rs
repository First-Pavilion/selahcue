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
    let req = Request::new(
        42,
        Command::ScriptureSearch {
            query: "love".into(),
        },
    );
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
        Command::ScriptureSearch {
            query: "grace".into(),
        },
        Command::StageScripture {
            reference: "Rom 8:28".into(),
        },
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

#[test]
fn wire_fixtures_are_stable_for_cross_language_clients() {
    // These EXACT strings are mirrored by the Flutter client's protocol tests
    // (implementation/mobile/selahcue_controller/test/models/protocol_test.dart). If this
    // test needs changing, the Dart fixtures must change with it (and VERSION bump).
    use selahcue_lan::protocol::{to_json, AuthRequest, Hello, PairRequest, PairResponse};

    let auth = Hello::Auth(AuthRequest {
        v: 2,
        device_id: "dev-1".into(),
        token: "tok".into(),
    });
    assert_eq!(
        to_json(&auth).unwrap(),
        r#"{"hello":"auth","v":2,"device_id":"dev-1","token":"tok"}"#
    );

    let pair = Hello::Pair(PairRequest {
        v: 2,
        code: "ABCD2345".into(),
        device_name: "Phone".into(),
    });
    assert_eq!(
        to_json(&pair).unwrap(),
        r#"{"hello":"pair","v":2,"code":"ABCD2345","device_name":"Phone"}"#
    );

    // The operator_state frame WITH the batch-7y scripture fields, pinned on the
    // serialize side (the skip-if-none fields must keep these exact names — the
    // Dart test parses THIS string; review 7y-D).
    let view = selahcue_lan::protocol::OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: Some("Romans 8:28".into()),
        live_scripture: Some("John 3:16".into()),
        live_free_text: Some("Removed Song".into()),
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"staged_scripture":"Romans 8:28","live_scripture":"John 3:16","live_free_text":"Removed Song"}}"#
    );

    let req = Request::new(7, Command::SelectItem { item_id: 3 });
    assert_eq!(
        to_json(&req).unwrap(),
        r#"{"v":2,"request_id":7,"command":{"cmd":"select_item","item_id":3}}"#
    );

    // Every command the mobile app sends, pinned on THIS side too (symmetric with
    // the Dart `command shapes are internally tagged` test).
    assert_eq!(to_json(&Command::Next).unwrap(), r#"{"cmd":"next"}"#);
    assert_eq!(
        to_json(&Command::Previous).unwrap(),
        r#"{"cmd":"previous"}"#
    );
    assert_eq!(to_json(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
    assert_eq!(to_json(&Command::Clear).unwrap(), r#"{"cmd":"clear"}"#);
    assert_eq!(
        to_json(&Command::Blackout { on: true }).unwrap(),
        r#"{"cmd":"blackout","on":true}"#
    );
    assert_eq!(
        to_json(&Command::StartTimer { seconds: 300 }).unwrap(),
        r#"{"cmd":"start_timer","seconds":300}"#
    );
    assert_eq!(
        to_json(&Command::StopTimer).unwrap(),
        r#"{"cmd":"stop_timer"}"#
    );
    assert_eq!(
        to_json(&Command::GetOperatorState).unwrap(),
        r#"{"cmd":"get_operator_state"}"#
    );

    let granted: PairResponse = selahcue_lan::protocol::from_json(
        r#"{"pair":"granted","device_id":"dev-9","token":"t9","role":"producer"}"#,
    )
    .unwrap();
    assert!(matches!(granted, PairResponse::Granted { .. }));

    let denied: ServerMessage = selahcue_lan::protocol::from_json(
        r#"{"event":"denied","request_id":7,"reason":"forbidden"}"#,
    )
    .unwrap();
    assert!(matches!(
        denied,
        ServerMessage::Denied {
            request_id: 7,
            reason: DenyReason::Forbidden
        }
    ));

    let state: ServerMessage = selahcue_lan::protocol::from_json(
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[{"id":1,"kind":"song","title":"Opening","is_live":true,"is_staged":false}],"live_index":0,"staged_index":null,"blackout":false,"timer":{"remaining_secs":90,"elapsed_secs":30,"time_up":false,"warn":false,"running":true}}}"#,
    )
    .unwrap();
    match state {
        ServerMessage::OperatorState { view } => {
            assert_eq!(view.plan_name, "Sunday");
            assert_eq!(view.items.len(), 1);
            assert_eq!(view.timer.unwrap().remaining_secs, Some(90));
        }
        other => panic!("expected operator_state, got {other:?}"),
    }
}
