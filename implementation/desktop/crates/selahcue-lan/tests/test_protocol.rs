//! Wire-protocol serialization tests — the JSON shapes are a compatibility contract.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{
    from_json, to_json, AuthRequest, AuthResponse, Command, DenyReason, LayerVisibility,
    OutputConfigView, RemoteDeviceView, RemotePendingView, Request, ScaleFit, ScreenView,
    ServerMessage, ThumbView, VerseView, VERSION,
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
    // SelectSlide (Live Console slide picker) — additive; pinned cross-language (protocol_test.dart).
    assert_eq!(
        to_json(&Command::SelectSlide {
            item_id: 7,
            slide_index: 2
        })
        .unwrap(),
        r#"{"cmd":"select_slide","item_id":7,"slide_index":2}"#
    );
    assert_eq!(
        from_json::<Command>(r#"{"cmd":"select_slide","item_id":7,"slide_index":2}"#).unwrap(),
        Command::SelectSlide {
            item_id: 7,
            slide_index: 2
        },
        "wire form round-trips back to the command"
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
fn screen_frame_round_trips_and_is_additive() {
    // 86ajq321k: the GetScreenFrame command + ScreenFrame reply round-trip with stable tags;
    // additive (VERSION unchanged); a None frame is skipped.
    assert_eq!(
        to_json(&Command::GetScreenFrame {
            screen: "lower-third".into(),
            max_w: 96,
            max_h: 54
        })
        .unwrap(),
        r#"{"cmd":"get_screen_frame","screen":"lower-third","max_w":96,"max_h":54}"#
    );
    let thumb = ThumbView::from_rgba(2, 1, &[9, 8, 7, 6, 5, 4, 3, 2]);
    let msg = ServerMessage::ScreenFrame {
        screen: "stream".into(),
        frame: Some(thumb.clone()),
    };
    let json = to_json(&msg).unwrap();
    assert!(json.contains(r#""event":"screen_frame""#), "{json}");
    assert!(json.contains(r#""screen":"stream""#), "{json}");
    assert!(json.contains(r#""rgba":"#), "{json}");
    assert_eq!(from_json::<ServerMessage>(&json).unwrap(), msg);
    // A None frame is skipped on the wire.
    let empty = ServerMessage::ScreenFrame {
        screen: "main".into(),
        frame: None,
    };
    let ej = to_json(&empty).unwrap();
    assert!(!ej.contains("\"frame\""), "a None frame is skipped: {ej}");
    assert_eq!(from_json::<ServerMessage>(&ej).unwrap(), empty);
    assert_eq!(VERSION, 2);
}

#[test]
fn screen_registry_commands_round_trip_and_are_additive() {
    // Screens page — dynamic registry: the three management commands + the ScreenView
    // registry entry round-trip with stable snake_case tags; additive (VERSION unchanged).
    assert_eq!(
        to_json(&Command::SetScreenEnabled {
            screen: "lower-third".into(),
            enabled: false,
        })
        .unwrap(),
        r#"{"cmd":"set_screen_enabled","screen":"lower-third","enabled":false}"#
    );
    assert_eq!(
        to_json(&Command::AddScreen {
            role: "stream".into()
        })
        .unwrap(),
        r#"{"cmd":"add_screen","role":"stream"}"#
    );
    assert_eq!(
        to_json(&Command::RemoveScreen {
            screen: "stream-2".into()
        })
        .unwrap(),
        r#"{"cmd":"remove_screen","screen":"stream-2"}"#
    );
    for cmd in [
        Command::SetScreenEnabled {
            screen: "main".into(),
            enabled: true,
        },
        Command::AddScreen {
            role: "lower-third".into(),
        },
        Command::RemoveScreen { screen: "x".into() },
    ] {
        let json = to_json(&cmd).unwrap();
        assert_eq!(from_json::<Command>(&json).unwrap(), cmd, "{json}");
    }

    // ScreenView (the registry entry in OperatorStateView.screens) round-trips; the theme
    // is skipped when None so a stage/global-following screen stays compact.
    let audience = ScreenView {
        screen: "lower-third".into(),
        role: "lower-third".into(),
        enabled: true,
        deletable: false,
        theme: Some("high-contrast".into()),
        config: OutputConfigView::default(),
    };
    let aj = to_json(&audience).unwrap();
    assert!(aj.contains(r#""deletable":false"#), "{aj}");
    assert!(aj.contains(r#""theme":"high-contrast""#), "{aj}");
    // A DEFAULT per-output config is omitted on the wire (byte-identical to a pre-config
    // peer / the pinned v2 fixtures).
    assert!(
        !aj.contains("\"config\""),
        "default config is skipped: {aj}"
    );
    assert_eq!(from_json::<ScreenView>(&aj).unwrap(), audience);
    let stage = ScreenView {
        screen: "stage".into(),
        role: "stage".into(),
        enabled: false,
        deletable: false,
        theme: None,
        config: OutputConfigView::default(),
    };
    let sj = to_json(&stage).unwrap();
    assert!(!sj.contains("\"theme\""), "a None theme is skipped: {sj}");
    assert!(
        !sj.contains("\"config\""),
        "default config is skipped: {sj}"
    );
    assert_eq!(from_json::<ScreenView>(&sj).unwrap(), stage);
    assert_eq!(VERSION, 2);

    // A NON-default per-output config round-trips and IS carried on the wire (additive).
    let configured = ScreenView {
        screen: "main".into(),
        role: "main".into(),
        enabled: true,
        deletable: false,
        theme: None,
        config: OutputConfigView {
            orientation: 1,
            scale_fit: ScaleFit::Fit,
            mirror: true,
            delay_ms: 40,
            frame_rate: 30,
            safe_area_guides: true,
            layers: LayerVisibility {
                lower_third: false,
                ..LayerVisibility::default()
            },
            ndi_enabled: true,
            ndi_name: "SelahCue Program".into(),
        },
    };
    let cj = to_json(&configured).unwrap();
    assert!(
        cj.contains("\"config\""),
        "a non-default config is carried: {cj}"
    );
    assert!(cj.contains("\"scale_fit\":\"fit\""), "{cj}");
    assert_eq!(from_json::<ScreenView>(&cj).unwrap(), configured);
    assert_eq!(VERSION, 2);
}

#[test]
fn follow_scripture_round_trips_and_is_additive() {
    // 86ajtwq2b: the follow command round-trips with a stable tag; additive (VERSION 2, a
    // pre-existing command byte-identical); skip-if-none translation keeps fixtures lean.
    assert_eq!(
        to_json(&Command::FollowScripture {
            reference: "John 3:16".into(),
            translation: None
        })
        .unwrap(),
        r#"{"cmd":"follow_scripture","reference":"John 3:16"}"#
    );
    let with_t = Command::FollowScripture {
        reference: "Ps 23:1".into(),
        translation: Some("WEB".into()),
    };
    assert_eq!(
        from_json::<Command>(&to_json(&with_t).unwrap()).unwrap(),
        with_t
    );
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
fn present_authored_slide_round_trips_and_is_additive() {
    // Deck "Present" (Design 2.0): a slide + theme carried as opaque JSON, mirroring
    // SetCustomTheme so the wire layer never depends on the presentation crate.
    let cmd = Command::PresentAuthoredSlide {
        slide_json: r#"{"id":1}"#.into(),
        theme_json: "{}".into(),
        next_slide_json: None,
    };
    let json = to_json(&cmd).unwrap();
    // Byte-stable: `next_slide_json` is skip-if-none, so a present WITHOUT a coming deck slide
    // serialises byte-identically to the pinned v2 fixture (existing operators/hosts unaffected).
    assert_eq!(
        json,
        r#"{"cmd":"present_authored_slide","slide_json":"{\"id\":1}","theme_json":"{}"}"#
    );
    assert_eq!(from_json::<Command>(&json).unwrap(), cmd);

    // Additive: a present WITH the next deck slide carries it as opaque JSON (for the
    // confidence/stage monitor's "next" line) and round-trips.
    let with_next = Command::PresentAuthoredSlide {
        slide_json: r#"{"id":1}"#.into(),
        theme_json: "{}".into(),
        next_slide_json: Some(r#"{"id":2}"#.into()),
    };
    let jn = to_json(&with_next).unwrap();
    assert_eq!(
        jn,
        r#"{"cmd":"present_authored_slide","slide_json":"{\"id\":1}","theme_json":"{}","next_slide_json":"{\"id\":2}"}"#
    );
    assert_eq!(from_json::<Command>(&jn).unwrap(), with_next);

    // A pre-existing command stays byte-identical (the pinned v2 fixtures hold).
    assert_eq!(to_json(&Command::GoLive).unwrap(), r#"{"cmd":"go_live"}"#);
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
        Command::AdjustTimer { delta_secs: 60 },
        Command::PauseTimer,
        Command::ResumeTimer,
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
        // Live transcript + scripture detection (R3/R4). Timestamps skip-serialize when None.
        Command::IngestTranscript {
            text: "turn to John chapter 3 verse 16".into(),
            start_ms: Some(1_500),
            end_ms: Some(3_200),
            is_final: true,
        },
        Command::IngestTranscript {
            text: "no timestamps".into(),
            start_ms: None,
            end_ms: None,
            is_final: true,
        },
        Command::ApproveDetection { detection_id: 7 },
        Command::DismissDetection { detection_id: 7 },
        Command::PresentAuthoredSlide {
            slide_json: r#"{"id":1}"#.into(),
            theme_json: "{}".into(),
            next_slide_json: Some(r#"{"id":2}"#.into()),
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
    // IngestTranscript: timestamps skip-serialize when absent (additive, lean peers).
    assert_eq!(
        to_json(&Command::IngestTranscript {
            text: "hi".into(),
            start_ms: None,
            end_ms: None,
            is_final: true,
        })
        .unwrap(),
        r#"{"cmd":"ingest_transcript","text":"hi"}"#
    );
    assert_eq!(
        to_json(&Command::ApproveDetection { detection_id: 3 }).unwrap(),
        r#"{"cmd":"approve_detection","detection_id":3}"#
    );
}

/// The transcript + detection view fields are additive: empty omits them entirely
/// (pinned bytes above unchanged), non-empty serializes under these exact names the
/// operator webview reads.
#[test]
fn transcript_and_detection_view_fields_are_additive() {
    use selahcue_lan::protocol::{DetectionView, OperatorStateView, TranscriptSegmentView};
    let view = OperatorStateView {
        plan_name: "Sunday".into(),
        items: vec![],
        live_index: None,
        staged_index: None,
        blackout: false,
        timer: None,
        staged_scripture: None,
        live_scripture: None,
        live_free_text: None,
        live_authored_id: None,
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![],
        screen_themes: vec![],
        screens: vec![],
        transcript: vec![TranscriptSegmentView {
            id: 0,
            start_ms: 0,
            end_ms: 1_500,
            text: "turn to John 3:16".into(),
        }],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![DetectionView {
            id: 4,
            reference: "John 3:16".into(),
            text: "For God so loved the world".into(),
            confidence: None,
            translation: String::new(),
            source_segment: None,
        }],
    };
    assert_eq!(
        to_json(&ServerMessage::OperatorState { view }).unwrap(),
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{"id":0,"start_ms":0,"end_ms":1500,"text":"turn to John 3:16"}],"detections":[{"id":4,"reference":"John 3:16","text":"For God so loved the world"}]}}"#
    );
    // A detection with no resolved verse text omits `text` (skip-if-empty).
    let bare = DetectionView {
        id: 1,
        reference: "Jude 3".into(),
        text: String::new(),
        confidence: None,
        translation: String::new(),
        source_segment: None,
    };
    assert_eq!(to_json(&bare).unwrap(), r#"{"id":1,"reference":"Jude 3"}"#);
}

/// The detection `confidence` (match %) is additive: `None` is omitted (older frames +
/// today's honest-empty detector stay byte-identical), `Some(pct)` serializes under the
/// exact name the operator webview reads, and an older host's frame (no key) parses to `None`.
#[test]
fn detection_confidence_is_additive() {
    use selahcue_lan::protocol::DetectionView;
    let scored = DetectionView {
        id: 7,
        reference: "Romans 8:28".into(),
        text: "And we know".into(),
        confidence: Some(94),
        translation: String::new(),
        source_segment: None,
    };
    assert_eq!(
        to_json(&scored).unwrap(),
        r#"{"id":7,"reference":"Romans 8:28","text":"And we know","confidence":94}"#
    );
    // An older host omits the key entirely — it must parse to None (serde default).
    let legacy: DetectionView =
        from_json(r#"{"id":7,"reference":"Romans 8:28","text":"And we know"}"#).unwrap();
    assert_eq!(legacy.confidence, None);
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
        platform: String::new(),
    });
    // An omitted platform is skipped — byte-identical to the pinned cross-language fixture.
    assert_eq!(
        to_json(&pair).unwrap(),
        r#"{"hello":"pair","v":2,"code":"ABCD2345","device_name":"Phone"}"#
    );
    // With a platform present it is appended LAST (the additive, optional field).
    let pair_p = Hello::Pair(PairRequest {
        v: 2,
        code: "ABCD2345".into(),
        device_name: "Phone".into(),
        platform: "ios".into(),
    });
    assert_eq!(
        to_json(&pair_p).unwrap(),
        r#"{"hello":"pair","v":2,"code":"ABCD2345","device_name":"Phone","platform":"ios"}"#
    );
    // Interim pairing frame (86ajxhv0q): additive `parked` — Granted/Rejected fixtures unchanged.
    assert_eq!(
        to_json(&PairResponse::Parked).unwrap(),
        r#"{"pair":"parked"}"#
    );
    assert_eq!(
        selahcue_lan::protocol::from_json::<PairResponse>(r#"{"pair":"parked"}"#).unwrap(),
        PairResponse::Parked
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
        live_authored_id: None,
        outputs: vec![],
        displays: vec![],
        translations: vec![],
        // Empty theme/themes (S8-3b) + saved_themes (86ajq4xmy) are skip-if-empty —
        // the pinned bytes below are UNCHANGED, proving the new fields are additive.
        theme: String::new(),
        themes: vec![],
        saved_themes: vec![],
        screen_themes: vec![],
        screens: vec![],
        transcript: vec![],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![],
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
        live_authored_id: None,
        outputs: vec![selahcue_lan::protocol::OutputStatusView {
            role: "main".into(),
            display: Some("Projector".into()),
            width: 1920,
            height: 1080,
            assigned: true,
            assigned_key: Some("Projector|1920x1080".into()),
            fps: None,
            dropped_frames: None,
            signal: None,
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
        screens: vec![],
        transcript: vec![],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![],
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
        live_authored_id: None,
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
        screens: vec![],
        transcript: vec![],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![],
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
        live_authored_id: None,
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
        screens: vec![],
        transcript: vec![],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![],
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
        live_authored_id: None,
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
        screens: vec![],
        transcript: vec![],
        partial_transcript: None,
        stage_template: String::new(),
        stage_message: None,
        detections: vec![],
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
        to_json(&Command::PauseTimer).unwrap(),
        r#"{"cmd":"pause_timer"}"#
    );
    assert_eq!(
        to_json(&Command::ResumeTimer).unwrap(),
        r#"{"cmd":"resume_timer"}"#
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
        staged_slide_index: None,
        theme: None,
        link: None,
        owner: None,
        planned_secs: None,
    };
    assert_eq!(
        to_json(&title_only).unwrap(),
        r#"{"id":1,"kind":"scripture","title":"Romans 8:28","is_live":false,"is_staged":true}"#,
        "no slide/theme/link/owner/duration fields emitted → byte-identical to a v5 host's item"
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
        staged_slide_index: None,
        theme: Some("lower-third".into()),
        link: None,
        owner: None,
        planned_secs: None,
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

// --- Linked content reference on a plan item (ADR-0020 follow-up) ---

#[test]
fn plan_item_view_carries_a_content_link_additively() {
    use selahcue_lan::protocol::{ContentLinkView, PlanItemView};
    // A scripture-linked item emits the nested `link` object (skip-if-none inner fields).
    let scr = PlanItemView {
        id: 3,
        kind: "scripture".into(),
        title: "Romans 8:28-30".into(),
        is_live: false,
        is_staged: false,
        slide_count: None,
        slide_index: None,
        staged_slide_index: None,
        theme: None,
        link: Some(ContentLinkView {
            kind: "scripture".into(),
            reference: Some("Romans 8:28-30".into()),
            translation: Some("WEB".into()),
            verses_per_slide: Some(2),
            id: None,
            slide_count: None,
        }),
        owner: None,
        planned_secs: None,
    };
    assert_eq!(
        to_json(&scr).unwrap(),
        r#"{"id":3,"kind":"scripture","title":"Romans 8:28-30","is_live":false,"is_staged":false,"link":{"kind":"scripture","reference":"Romans 8:28-30","translation":"WEB","verses_per_slide":2}}"#,
    );
    assert_eq!(
        from_json::<PlanItemView>(&to_json(&scr).unwrap()).unwrap(),
        scr
    );
    // A deck link carries just kind + id.
    let deck = ContentLinkView {
        kind: "deck".into(),
        reference: None,
        translation: None,
        verses_per_slide: None,
        id: Some(17),
        slide_count: None,
    };
    assert_eq!(to_json(&deck).unwrap(), r#"{"kind":"deck","id":17}"#);
}

#[test]
fn plan_item_view_carries_owner_and_duration_additively() {
    use selahcue_lan::protocol::PlanItemView;
    // Unassigned/unplanned → the fields are omitted (byte-stable for an old client).
    let bare = PlanItemView {
        id: 5,
        kind: "song".into(),
        title: "Hymn".into(),
        is_live: false,
        is_staged: false,
        slide_count: None,
        slide_index: None,
        staged_slide_index: None,
        theme: None,
        link: None,
        owner: None,
        planned_secs: None,
    };
    assert_eq!(
        to_json(&bare).unwrap(),
        r#"{"id":5,"kind":"song","title":"Hymn","is_live":false,"is_staged":false}"#,
    );
    // Assigned + planned → both ride along and round-trip.
    let full = PlanItemView {
        id: 6,
        kind: "scripture".into(),
        title: "Call to Worship".into(),
        is_live: false,
        is_staged: true,
        slide_count: None,
        slide_index: None,
        staged_slide_index: None,
        theme: None,
        link: None,
        owner: Some("Grace".into()),
        planned_secs: Some(180),
    };
    let json = to_json(&full).unwrap();
    assert!(json.contains(r#""owner":"Grace""#), "{json}");
    assert!(json.contains(r#""planned_secs":180"#), "{json}");
    assert_eq!(from_json::<PlanItemView>(&json).unwrap(), full);
}

#[test]
fn set_item_content_command_round_trips_and_clears() {
    use selahcue_lan::protocol::ContentLinkView;
    // Setting a deck link.
    let set = Command::SetItemContent {
        item_id: 4,
        link: Some(ContentLinkView {
            kind: "deck".into(),
            reference: None,
            translation: None,
            verses_per_slide: None,
            id: Some(17),
            slide_count: None,
        }),
    };
    assert_eq!(
        to_json(&set).unwrap(),
        r#"{"cmd":"set_item_content","item_id":4,"link":{"kind":"deck","id":17}}"#,
    );
    assert_eq!(from_json::<Command>(&to_json(&set).unwrap()).unwrap(), set);
    // Clearing a link omits the `link` key entirely.
    let clear = Command::SetItemContent {
        item_id: 4,
        link: None,
    };
    assert_eq!(
        to_json(&clear).unwrap(),
        r#"{"cmd":"set_item_content","item_id":4}"#,
    );
    assert_eq!(
        from_json::<Command>(&to_json(&clear).unwrap()).unwrap(),
        clear
    );
}

#[test]
fn set_item_owner_and_duration_commands_round_trip_and_clear() {
    // Owner: set carries the string; clear omits the key.
    let set_owner = Command::SetItemOwner {
        item_id: 4,
        owner: Some("Grace".into()),
    };
    assert_eq!(
        to_json(&set_owner).unwrap(),
        r#"{"cmd":"set_item_owner","item_id":4,"owner":"Grace"}"#,
    );
    assert_eq!(
        from_json::<Command>(&to_json(&set_owner).unwrap()).unwrap(),
        set_owner
    );
    assert_eq!(
        to_json(&Command::SetItemOwner {
            item_id: 4,
            owner: None,
        })
        .unwrap(),
        r#"{"cmd":"set_item_owner","item_id":4}"#,
    );
    // Duration: set carries the seconds; clear omits the key.
    let set_dur = Command::SetItemDuration {
        item_id: 7,
        secs: Some(240),
    };
    assert_eq!(
        to_json(&set_dur).unwrap(),
        r#"{"cmd":"set_item_duration","item_id":7,"secs":240}"#,
    );
    assert_eq!(
        from_json::<Command>(&to_json(&set_dur).unwrap()).unwrap(),
        set_dur
    );
    assert_eq!(
        to_json(&Command::SetItemDuration {
            item_id: 7,
            secs: None,
        })
        .unwrap(),
        r#"{"cmd":"set_item_duration","item_id":7}"#,
    );
}

#[test]
fn set_ndi_output_round_trips_and_is_additive() {
    // NDI output config: the command round-trips with a stable snake_case tag; additive
    // (VERSION unchanged, a new tag not in any pinned fixture).
    assert_eq!(
        to_json(&Command::SetNdiOutput {
            screen: "stream".into(),
            name: "SelahCue Program".into(),
            enabled: true,
        })
        .unwrap(),
        r#"{"cmd":"set_ndi_output","screen":"stream","name":"SelahCue Program","enabled":true}"#
    );
    let cmd = Command::SetNdiOutput {
        screen: "stream-2".into(),
        name: "".into(),
        enabled: false,
    };
    assert_eq!(from_json::<Command>(&to_json(&cmd).unwrap()).unwrap(), cmd);

    // The NDI fields on OutputConfigView are additive: default (off/empty) is skipped, a
    // configured NDI output is carried.
    let mut cfg = OutputConfigView::default();
    assert!(
        !to_json(&cfg).unwrap().contains("ndi_"),
        "default NDI is off the wire"
    );
    cfg.ndi_enabled = true;
    cfg.ndi_name = "Cam 1".into();
    let j = to_json(&cfg).unwrap();
    assert!(
        j.contains(r#""ndi_enabled":true"#) && j.contains(r#""ndi_name":"Cam 1""#),
        "{j}"
    );
    assert_eq!(from_json::<OutputConfigView>(&j).unwrap(), cfg);
    assert_eq!(VERSION, 2);
}

#[test]
fn remote_device_management_wire_is_stable() {
    // Operator→host device-management commands (86ajxer8n). These are operator-only and never sent
    // by the Dart controller, but the operator client depends on these exact tags/fields.
    assert_eq!(
        to_json(&Command::ListRemoteDevices).unwrap(),
        r#"{"cmd":"list_remote_devices"}"#
    );
    assert_eq!(
        to_json(&Command::ApprovePairing {
            device_id: "dev-ab12".into(),
            role: Role::Assistant,
        })
        .unwrap(),
        r#"{"cmd":"approve_pairing","device_id":"dev-ab12","role":"assistant"}"#
    );
    assert_eq!(
        to_json(&Command::DenyPairing {
            device_id: "dev-ab12".into()
        })
        .unwrap(),
        r#"{"cmd":"deny_pairing","device_id":"dev-ab12"}"#
    );
    assert_eq!(
        to_json(&Command::RevokeSession {
            device_id: "dev-ab12".into()
        })
        .unwrap(),
        r#"{"cmd":"revoke_session","device_id":"dev-ab12"}"#
    );
    assert_eq!(
        to_json(&Command::SetSessionRole {
            device_id: "dev-ab12".into(),
            role: Role::Producer,
        })
        .unwrap(),
        r#"{"cmd":"set_session_role","device_id":"dev-ab12","role":"producer"}"#
    );
    assert_eq!(
        to_json(&Command::NewPairingCode).unwrap(),
        r#"{"cmd":"new_pairing_code"}"#
    );

    // Replies round-trip and carry the `event` discriminator.
    let devices = ServerMessage::RemoteDevices {
        devices: vec![RemoteDeviceView {
            device_id: "dev-ab12".into(),
            name: "Booth iPad".into(),
            platform: "iPadOS".into(),
            role: Role::Producer,
            idle_secs: 4,
            pinned: false,
        }],
        pending: vec![RemotePendingView {
            device_id: "dev-cd34".into(),
            name: "Anna's iPhone".into(),
            platform: "iOS".into(),
            fingerprint: "A1 · B2 · C3 · D4".into(),
            waiting_secs: 12,
        }],
    };
    let json = to_json(&devices).unwrap();
    assert!(json.contains(r#""event":"remote_devices""#), "{json}");
    assert_eq!(
        from_json::<ServerMessage>(&json).unwrap(),
        devices,
        "{json}"
    );

    let code = ServerMessage::PairingCode {
        code: "ab12cd34".into(),
        fingerprint: "A1 · B2".into(),
        expires_in_secs: 120,
        uri: Some("selahcue://pair?host=192.168.1.5&port=8443&pin=abcd&code=ab12cd34".into()),
    };
    let cj = to_json(&code).unwrap();
    assert!(cj.contains(r#""event":"pairing_code""#), "{cj}");
    assert_eq!(from_json::<ServerMessage>(&cj).unwrap(), code, "{cj}");
    // The `uri` is omitted from the wire when absent (older hosts stay forward-compatible).
    let no_uri = ServerMessage::PairingCode {
        code: "ab12cd34".into(),
        fingerprint: "A1 · B2".into(),
        expires_in_secs: 120,
        uri: None,
    };
    let nj = to_json(&no_uri).unwrap();
    assert!(
        !nj.contains("uri"),
        "absent invite must not serialize a uri field: {nj}"
    );
    assert_eq!(from_json::<ServerMessage>(&nj).unwrap(), no_uri, "{nj}");
    assert_eq!(VERSION, 2);
}
