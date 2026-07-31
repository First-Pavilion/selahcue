//! Wire-protocol serialization tests — the JSON shapes are a compatibility contract.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{
    from_json, to_json, AuthRequest, AuthResponse, Command, DenyReason, Request, ServerMessage,
    ThumbView, VerseView, VERSION,
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
fn console_thumbnails_round_trip_and_additive() {
    // 86ajtwq28: the command + reply serde round-trip with stable tags, and the addition is
    // ADDITIVE — VERSION is unchanged and existing messages encode byte-identically.
    assert_eq!(
        to_json(&Command::GetConsoleThumbnails {
            max_w: 480,
            max_h: 270
        })
        .unwrap(),
        r#"{"cmd":"get_console_thumbnails","max_w":480,"max_h":270}"#
    );
    // ThumbView base64-encodes the raw RGBA (8 bytes → 12 base64 chars).
    let thumb = ThumbView::from_rgba(2, 1, &[1, 2, 3, 4, 5, 6, 7, 8]);
    assert_eq!((thumb.w, thumb.h), (2, 1));
    assert_eq!(
        thumb.rgba.len(),
        12,
        "8 RGBA bytes → 12 base64 chars: {}",
        thumb.rgba
    );

    let msg = ServerMessage::ConsoleThumbnails {
        preview: Some(thumb.clone()),
        live: None,
    };
    let json = to_json(&msg).unwrap();
    assert!(json.contains(r#""event":"console_thumbnails""#), "{json}");
    assert!(
        json.contains(r#""w":2"#) && json.contains(r#""rgba":"#),
        "{json}"
    );
    assert!(
        !json.contains("\"live\""),
        "a None live surface is skipped: {json}"
    );
    assert_eq!(from_json::<ServerMessage>(&json).unwrap(), msg);

    // Additive: the wire VERSION is unchanged and a pre-existing command is byte-identical.
    assert_eq!(VERSION, 2);
    assert_eq!(to_json(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
}

#[test]
fn request_round_trips_and_stamps_version() {
    let req = Request::new(
        42,
        Command::ScriptureSearch {
            query: "love".into(),
            translation: None,
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
            translation: None,
        },
        Command::StageScripture {
            reference: "Rom 8:28".into(),
            translation: None,
        },
        Command::GetChapter {
            reference: "Romans 8".into(),
            translation: None,
        },
        Command::GetChapter {
            reference: "Romans 8".into(),
            translation: Some("WEB".into()),
        },
        Command::GetState,
        Command::SetTheme {
            name: "classic".into(),
        },
        Command::SetCustomTheme {
            theme_json: r#"{"background":{"r":1,"g":2,"b":3,"a":255}}"#.into(),
        },
        Command::SetItemTheme {
            item_id: 3,
            theme: Some("lower-third".into()),
        },
        // Clearing an override (theme: None) skip-serializes the field.
        Command::SetItemTheme {
            item_id: 5,
            theme: None,
        },
        Command::SaveTheme {
            name: "Sermon Bold".into(),
            theme_json: r#"{"background":{"r":1,"g":2,"b":3,"a":255}}"#.into(),
        },
        Command::DeleteTheme {
            name: "Sermon Bold".into(),
        },
        Command::SetScreenTheme {
            screen: "lower-third".into(),
            name: "lower-third".into(),
        },
        // The clear form (empty name) still round-trips.
        Command::SetScreenTheme {
            screen: "main".into(),
            name: String::new(),
        },
    ];
    for c in cmds {
        let json = to_json(&c).unwrap();
        let back: Command = from_json(&json).unwrap();
        assert_eq!(back, c, "round-trip failed for {json}");
    }
    // SetScreenTheme is pinned serialize-side (the Screens page emits this exact shape).
    assert_eq!(
        to_json(&Command::SetScreenTheme {
            screen: "stream".into(),
            name: "high-contrast".into(),
        })
        .unwrap(),
        r#"{"cmd":"set_screen_theme","screen":"stream","name":"high-contrast"}"#
    );
    // The clear form omits `theme` entirely (additive skip-if-none — keeps peers lean).
    assert_eq!(
        to_json(&Command::SetItemTheme {
            item_id: 5,
            theme: None
        })
        .unwrap(),
        r#"{"cmd":"set_item_theme","item_id":5}"#
    );
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
            hits: vec![],
        },
        ServerMessage::Chapter {
            book_name: "Romans".into(),
            chapter: 8,
            translation: "KJV".into(),
            verses: vec![VerseView {
                number: 28,
                text: "And we know that all things work together for good…".into(),
            }],
            prev_ref: Some("Romans 7".into()),
            next_ref: Some("Romans 9".into()),
        },
        // A canon-edge chapter: no neighbours, empty verse fixture allowed.
        ServerMessage::Chapter {
            book_name: "Genesis".into(),
            chapter: 1,
            translation: "KJV".into(),
            verses: vec![],
            prev_ref: None,
            next_ref: Some("Genesis 2".into()),
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
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        // Empty theme/themes (S8-3b) + saved_themes (86ajq4xmy) are skip-if-empty —
        // the pinned bytes below are UNCHANGED, proving the new fields are additive.
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![],
        screen_themes: vec![],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"staged_scripture":"Romans 8:28","live_scripture":"John 3:16","live_free_text":"Removed Song"}}"#
    );

    // The outputs/displays wire surface (batch 7aa): pinned serialize-side; the
    // operator webview reads these exact field names.
    let view = selahcue_lan::protocol::OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: None,
        live_scripture: None,
        live_free_text: None,
        outputs: vec![selahcue_lan::protocol::OutputStatusView {
            role: "main".into(),
            display: Some("Projector".into()),
            width: 1920,
            height: 1080,
            assigned: true,
            assigned_key: Some("Projector|1920x1080".into()),
        }],
        displays: vec![selahcue_lan::protocol::DisplayView {
            key: "Projector|1920x1080".into(),
            name: "Projector".into(),
            width: 1920,
            height: 1080,
        }],
        translations: vec![],
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![],
        screen_themes: vec![],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"outputs":[{"role":"main","display":"Projector","width":1920,"height":1080,"assigned":true,"assigned_key":"Projector|1920x1080"}],"displays":[{"key":"Projector|1920x1080","name":"Projector","width":1920,"height":1080}]}}"#
    );

    // The theme wire surface (S8-3b): the SetTheme command + a view carrying the
    // active theme + offered themes. Pinned serialize-side; the Dart test mirrors
    // BOTH strings exactly.
    assert_eq!(
        to_json(&Command::SetTheme {
            name: "high-contrast".into()
        })
        .unwrap(),
        r#"{"cmd":"set_theme","name":"high-contrast"}"#
    );
    let themed = selahcue_lan::protocol::OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: None,
        live_scripture: None,
        live_free_text: None,
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        theme: "lower-third".into(),
        themes: vec![
            "classic".into(),
            "high-contrast".into(),
            "lower-third".into(),
        ],
        saved_themes: vec![],
        screen_themes: vec![],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view: themed }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"theme":"lower-third","themes":["classic","high-contrast","lower-third"]}}"#
    );
    // The saved-theme LIBRARY (86ajq4xmy) on the wire: when non-empty it serializes
    // as `saved_themes: [{name, theme_json}]`. Pinned serialize-side; the Theme
    // Designer parses these exact field names to list + load the library.
    let library = selahcue_lan::protocol::OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: None,
        live_scripture: None,
        live_free_text: None,
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![selahcue_lan::protocol::SavedThemeView {
            name: "Sermon Bold".into(),
            theme_json: r#"{"background":{"r":1,"g":2,"b":3,"a":255}}"#.into(),
        }],
        screen_themes: vec![],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view: library }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"saved_themes":[{"name":"Sermon Bold","theme_json":"{\"background\":{\"r\":1,\"g\":2,\"b\":3,\"a\":255}}"}]}}"#
    );
    // The per-SCREEN theme map (86ajq321k) on the wire: when non-empty it serializes as
    // `screen_themes: [{screen, theme}]`. Pinned serialize-side; the Screens page parses
    // these exact field names to show a distinct theme per screen.
    let screens = selahcue_lan::protocol::OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: None,
        live_scripture: None,
        live_free_text: None,
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![],
        screen_themes: vec![
            selahcue_lan::protocol::ScreenThemeView {
                screen: "main".into(),
                theme: "classic".into(),
            },
            selahcue_lan::protocol::ScreenThemeView {
                screen: "lower-third".into(),
                theme: "lower-third".into(),
            },
        ],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view: screens }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"screen_themes":[{"screen":"main","theme":"classic"},{"screen":"lower-third","theme":"lower-third"}]}}"#
    );
    // The output-config commands, pinned like every other command.
    assert_eq!(
        to_json(&Command::AdjustTimer { delta_secs: -60 }).unwrap(),
        r#"{"cmd":"adjust_timer","delta_secs":-60}"#
    );
    assert_eq!(
        to_json(&Command::IdentifyOutputs).unwrap(),
        r#"{"cmd":"identify_outputs"}"#
    );
    assert_eq!(
        to_json(&Command::AssignOutput {
            role: "stage".into(),
            display_key: "Projector|1920x1080".into()
        })
        .unwrap(),
        r#"{"cmd":"assign_output","role":"stage","display_key":"Projector|1920x1080"}"#
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
    // The chapter-fetch command (batch 7al refine) — the Dart client sends THESE
    // exact shapes; translation is skip-if-none.
    assert_eq!(
        to_json(&Command::GetChapter {
            reference: "Romans 8".into(),
            translation: None,
        })
        .unwrap(),
        r#"{"cmd":"get_chapter","reference":"Romans 8"}"#
    );
    assert_eq!(
        to_json(&Command::GetChapter {
            reference: "Romans 8".into(),
            translation: Some("WEB".into()),
        })
        .unwrap(),
        r#"{"cmd":"get_chapter","reference":"Romans 8","translation":"WEB"}"#
    );
    // The chapter reply the Dart client parses — verses + neighbour refs.
    assert_eq!(
        to_json(&ServerMessage::Chapter {
            book_name: "Romans".into(),
            chapter: 8,
            translation: "KJV".into(),
            verses: vec![VerseView {
                number: 28,
                text: "And we know…".into(),
            }],
            prev_ref: Some("Romans 7".into()),
            next_ref: Some("Romans 9".into()),
        })
        .unwrap(),
        r#"{"event":"chapter","book_name":"Romans","chapter":8,"translation":"KJV","verses":[{"number":28,"text":"And we know…"}],"prev_ref":"Romans 7","next_ref":"Romans 9"}"#
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

// --- Songs: additive PlanItemView slide fields + AddItem content (S8-1) ---

#[test]
fn plan_item_view_omits_slide_fields_when_none_keeping_old_fixtures() {
    use selahcue_lan::protocol::PlanItemView;
    // A title-only item serializes EXACTLY as the pre-8a shape (skip-if-none).
    let title_only = PlanItemView {
        id: 1,
        kind: "scripture".into(),
        title: "Romans 8:28".into(),
        is_live: false,
        is_staged: true,
        slide_count: None,
        slide_index: None,
        theme: None,
    };
    assert_eq!(
        to_json(&title_only).unwrap(),
        r#"{"id":1,"kind":"scripture","title":"Romans 8:28","is_live":false,"is_staged":true}"#,
        "no slide/theme fields emitted → byte-identical to a v5 host's item"
    );
    // A multi-slide song emits the two fields.
    let song = PlanItemView {
        id: 2,
        kind: "song".into(),
        title: "Way Maker".into(),
        is_live: true,
        is_staged: false,
        slide_count: Some(6),
        slide_index: Some(2),
        theme: Some("lower-third".into()),
    };
    let json = to_json(&song).unwrap();
    assert!(json.contains(r#""theme":"lower-third""#), "{json}");
    assert!(json.contains(r#""slide_count":6"#), "{json}");
    assert!(json.contains(r#""slide_index":2"#), "{json}");
    // Round-trips.
    let back: PlanItemView = from_json(&json).unwrap();
    assert_eq!(back, song);
}

#[test]
fn old_plan_item_json_without_slide_fields_still_parses() {
    use selahcue_lan::protocol::PlanItemView;
    // A pre-8a host's item JSON (no slide fields) must parse via serde(default).
    let v: PlanItemView =
        from_json(r#"{"id":9,"kind":"song","title":"Old","is_live":false,"is_staged":false}"#)
            .unwrap();
    assert_eq!(v.slide_count, None);
    assert_eq!(v.slide_index, None);
}

#[test]
fn add_item_command_carries_optional_song_content() {
    // Without content: identical to the pre-8a AddItem wire form.
    assert_eq!(
        to_json(&Command::AddItem {
            kind: "section".into(),
            title: "Sermon".into(),
            content: None,
        })
        .unwrap(),
        r#"{"cmd":"add_item","kind":"section","title":"Sermon"}"#,
    );
    // With content: the stanza text rides along and round-trips.
    let cmd = Command::AddItem {
        kind: "song".into(),
        title: "Hymn".into(),
        content: Some("v1\n\nv2".into()),
    };
    let back: Command = from_json(&to_json(&cmd).unwrap()).unwrap();
    assert_eq!(back, cmd);
}
