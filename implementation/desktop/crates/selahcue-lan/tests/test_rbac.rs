//! RBAC policy tests — the security-critical authorization matrix. Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::Command;
use selahcue_lan::rbac::{authorize, Permission, Role};

fn navigate_cmds() -> Vec<Command> {
    // Preview navigation only — `Clear` is a live-output change, not navigation.
    vec![
        Command::Next,
        Command::Previous,
        Command::SelectItem { item_id: 3 },
    ]
}

fn all_roles() -> [Role; 4] {
    [
        Role::Operator,
        Role::Producer,
        Role::Assistant,
        Role::Viewer,
    ]
}

#[test]
fn operator_can_do_every_command() {
    let cmds = [
        Command::GoLive,
        Command::Next,
        Command::Previous,
        Command::Clear,
        Command::SelectItem { item_id: 1 },
        Command::Blackout { on: true },
        Command::StartTimer { seconds: 300 },
        Command::StopTimer,
        Command::AdjustTimer { delta_secs: 60 },
        Command::PauseTimer,
        Command::ResumeTimer,
        Command::ScriptureSearch {
            query: "love".into(),
            translation: None,
        },
        Command::StageScripture {
            reference: "John 3:16".into(),
            translation: None,
        },
        Command::GetState,
        Command::SetTheme {
            name: "classic".into(),
        },
    ];
    for c in &cmds {
        assert!(authorize(Role::Operator, c), "operator denied {c:?}");
    }
}

#[test]
fn set_theme_is_operator_only_output_config() {
    // Switching the audience theme is host output-config (like AssignOutput /
    // IdentifyOutputs) — Operator-only, denied for everyone below (S8-3b).
    let cmd = Command::SetTheme {
        name: "high-contrast".into(),
    };
    assert!(authorize(Role::Operator, &cmd), "operator");
    assert!(!authorize(Role::Producer, &cmd), "producer");
    assert!(!authorize(Role::Assistant, &cmd), "assistant");
    assert!(!authorize(Role::Viewer, &cmd), "viewer");
    // Auth precedes the controller's name check — an unknown name is still gated.
    assert!(authorize(
        Role::Operator,
        &Command::SetTheme {
            name: "bogus".into()
        }
    ));
    // A custom theme (Theme Designer, S8-3c) is the same output-config permission.
    let custom = Command::SetCustomTheme {
        theme_json: "{}".into(),
    };
    assert!(authorize(Role::Operator, &custom), "operator custom");
    assert!(!authorize(Role::Producer, &custom), "producer custom");
    assert!(!authorize(Role::Viewer, &custom), "viewer custom");
    // A per-item theme override (S8-3d) is the same output-config permission.
    let per_item = Command::SetItemTheme {
        item_id: 1,
        theme: Some("lower-third".into()),
    };
    assert!(authorize(Role::Operator, &per_item), "operator per-item");
    assert!(!authorize(Role::Producer, &per_item), "producer per-item");
    assert!(!authorize(Role::Assistant, &per_item), "assistant per-item");
    assert!(!authorize(Role::Viewer, &per_item), "viewer per-item");
    // Saving/deleting a NAMED theme in the library (86ajq4xmy) is the same
    // output-config permission — Operator-only.
    for cmd in [
        Command::SaveTheme {
            name: "Look".into(),
            theme_json: "{}".into(),
        },
        Command::DeleteTheme {
            name: "Look".into(),
        },
        // A per-SCREEN theme (86ajq321k) is the same output-config permission.
        Command::SetScreenTheme {
            screen: "lower-third".into(),
            name: "lower-third".into(),
        },
        // The dynamic screen-registry management commands are the SAME output-config
        // permission — Operator-only, and in particular DENIED for a Monitor-only Viewer
        // (a disable/add/delete is a write, never a read).
        Command::SetScreenEnabled {
            screen: "lower-third".into(),
            enabled: false,
        },
        Command::AddScreen {
            role: "stream".into(),
        },
        Command::RemoveScreen {
            screen: "stream-2".into(),
        },
        // The per-output config commands (Screens page inspector: orientation / scaling /
        // mirror / delay / frame-rate / safe-area / layer visibility) are the SAME
        // output-config authority — Operator-only, denied for everyone below.
        Command::SetOutputOrientation {
            screen: "main".into(),
            quarter_turns: 1,
        },
        Command::SetOutputScaleFit {
            screen: "main".into(),
            fit: selahcue_lan::protocol::ScaleFit::Fit,
        },
        Command::SetOutputMirror {
            screen: "main".into(),
            on: true,
        },
        Command::SetOutputDelay {
            screen: "main".into(),
            ms: 40,
        },
        Command::SetOutputFrameRate {
            screen: "main".into(),
            fps: 30,
        },
        Command::SetOutputSafeArea {
            screen: "main".into(),
            on: true,
        },
        Command::SetScreenLayerVisible {
            screen: "main".into(),
            layer: "lower-third".into(),
            visible: false,
        },
        // Configuring an NDI output is the SAME output-config authority — Operator-only.
        Command::SetNdiOutput {
            screen: "stream".into(),
            name: "SelahCue Program".into(),
            enabled: true,
        },
    ] {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(!authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(!authorize(Role::Assistant, &cmd), "assistant {cmd:?}");
        assert!(!authorize(Role::Viewer, &cmd), "viewer {cmd:?}");
    }
}

#[test]
fn only_privileged_roles_can_go_live() {
    assert!(authorize(Role::Operator, &Command::GoLive));
    assert!(authorize(Role::Producer, &Command::GoLive));
    assert!(!authorize(Role::Assistant, &Command::GoLive));
    assert!(!authorize(Role::Viewer, &Command::GoLive));
}

#[test]
fn follow_scripture_is_go_live_privilege_not_search() {
    // 86ajtwq2b: FollowScripture can advance the LIVE output, so it needs the GoLive
    // permission (Producer+) — NEVER the Assistant-level SearchScripture, or an Assistant
    // could escalate to Live via the follow path. (Assistants keep Preview-only staging.)
    let follow = Command::FollowScripture {
        reference: "John 3:16".into(),
        translation: None,
    };
    assert!(authorize(Role::Operator, &follow), "operator follows");
    assert!(authorize(Role::Producer, &follow), "producer follows");
    assert!(
        !authorize(Role::Assistant, &follow),
        "an assistant must NOT change Live via follow"
    );
    assert!(!authorize(Role::Viewer, &follow), "viewer cannot follow");
}

#[test]
fn blackout_timer_and_clear_are_producer_and_up() {
    // Clear wipes the live output — an Assistant (who cannot push live) must not
    // be able to clear it (DEC-002 revised).
    for cmd in [
        Command::Blackout { on: true },
        Command::StartTimer { seconds: 60 },
        Command::StopTimer,
        Command::PauseTimer,
        Command::ResumeTimer,
        Command::Clear,
    ] {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(!authorize(Role::Assistant, &cmd), "assistant {cmd:?}");
        assert!(!authorize(Role::Viewer, &cmd), "viewer {cmd:?}");
    }
}

#[test]
fn assistant_can_navigate_and_search_but_not_go_live() {
    for cmd in navigate_cmds() {
        assert!(authorize(Role::Assistant, &cmd), "assistant nav {cmd:?}");
    }
    assert!(authorize(
        Role::Assistant,
        &Command::ScriptureSearch {
            query: "grace".into(),
            translation: None,
        }
    ));
    assert!(authorize(
        Role::Assistant,
        &Command::StageScripture {
            reference: "Ps 23".into(),
            translation: None,
        }
    ));
    assert!(!authorize(Role::Assistant, &Command::GoLive));
    assert!(!authorize(Role::Assistant, &Command::Blackout { on: true }));
    // An Assistant navigates/stages Preview but cannot wipe the live output.
    assert!(!authorize(Role::Assistant, &Command::Clear));
}

#[test]
fn viewer_can_only_monitor() {
    assert!(authorize(Role::Viewer, &Command::GetState));
    // Monitor-class reads are allowed for a Viewer — incl. the console thumbnails + the
    // per-screen preview (86ajq321k), which must be read-only (no write escalation).
    assert!(authorize(
        Role::Viewer,
        &Command::GetConsoleThumbnails {
            max_w: 96,
            max_h: 54
        }
    ));
    assert!(authorize(
        Role::Viewer,
        &Command::GetScreenFrame {
            screen: "main".into(),
            max_w: 96,
            max_h: 54
        }
    ));
    // Everything else is denied.
    for cmd in navigate_cmds() {
        assert!(!authorize(Role::Viewer, &cmd), "viewer nav {cmd:?}");
    }
    assert!(!authorize(Role::Viewer, &Command::GoLive));
    assert!(!authorize(Role::Viewer, &Command::Clear));
    assert!(!authorize(
        Role::Viewer,
        &Command::ScriptureSearch {
            query: "x".into(),
            translation: None
        }
    ));
}

#[test]
fn transcription_ingest_is_producer_and_up_not_assistant() {
    // Feeding the transcript stream needs the `Transcribe` permission (Operator +
    // Producer). An Assistant prepares content but does not drive live transcription;
    // a Viewer only monitors.
    let ingest = Command::IngestTranscript {
        text: "John chapter 3 verse 16".into(),
        start_ms: None,
        end_ms: None,
        is_final: true,
    };
    assert!(authorize(Role::Operator, &ingest), "operator ingest");
    assert!(authorize(Role::Producer, &ingest), "producer ingest");
    assert!(
        !authorize(Role::Assistant, &ingest),
        "assistant must NOT ingest transcript"
    );
    assert!(!authorize(Role::Viewer, &ingest), "viewer must not ingest");
}

#[test]
fn approving_or_dismissing_a_detection_is_scripture_staging_privilege() {
    // Approving stages a scripture candidate; dismissing drops one — both are the
    // SearchScripture privilege (Assistant and up), never GoLive.
    for cmd in [
        Command::ApproveDetection { detection_id: 1 },
        Command::DismissDetection { detection_id: 1 },
    ] {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(authorize(Role::Assistant, &cmd), "assistant {cmd:?}");
        assert!(!authorize(Role::Viewer, &cmd), "viewer {cmd:?}");
    }
}

#[test]
fn every_role_can_get_state() {
    for role in all_roles() {
        assert!(
            authorize(role, &Command::GetState),
            "{role:?} cannot monitor"
        );
    }
}

#[test]
fn every_role_can_fetch_console_thumbnails() {
    // GetConsoleThumbnails is a READ (Monitor capability), like GetState/GetOperatorState —
    // a remote operator's console monitors show the true output regardless of role (86ajtwq28).
    for role in all_roles() {
        assert!(
            authorize(
                role,
                &Command::GetConsoleThumbnails {
                    max_w: 480,
                    max_h: 270
                }
            ),
            "{role:?} cannot fetch console thumbnails"
        );
    }
}

#[test]
fn navigate_is_denied_only_to_viewer() {
    for cmd in navigate_cmds() {
        assert!(authorize(Role::Operator, &cmd));
        assert!(authorize(Role::Producer, &cmd));
        assert!(authorize(Role::Assistant, &cmd));
        assert!(!authorize(Role::Viewer, &cmd));
    }
}

#[test]
fn scripture_commands_allowed_for_assistant_and_up_denied_for_viewer() {
    for cmd in [
        Command::ScriptureSearch {
            query: "hope".into(),
            translation: None,
        },
        Command::StageScripture {
            reference: "Jer 29:11".into(),
            translation: None,
        },
    ] {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(authorize(Role::Assistant, &cmd), "assistant {cmd:?}");
        assert!(!authorize(Role::Viewer, &cmd), "viewer {cmd:?}");
    }
}

#[test]
fn permission_sets_are_strictly_ordered_supersets() {
    // Each lower role's permissions must be a subset of the next higher role's.
    let chain = [
        Role::Viewer,
        Role::Assistant,
        Role::Producer,
        Role::Operator,
    ];
    for pair in chain.windows(2) {
        let (lower, higher) = (pair[0], pair[1]);
        for p in lower.permissions() {
            assert!(
                higher.can(*p),
                "{higher:?} must hold every permission of {lower:?} (missing {p:?})"
            );
        }
    }
    // Sanity: Operator uniquely holds ManageDevices.
    assert!(Role::Operator.can(Permission::ManageDevices));
    assert!(!Role::Producer.can(Permission::ManageDevices));
}
