//! RBAC policy tests — the security-critical authorization matrix. Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::Command;
use selahcue_lan::rbac::{authorize, can_edit_plan, required_permission, Permission, Role};

fn navigate_cmds() -> Vec<Command> {
    // Preview navigation only — `Clear` is a live-output change, not navigation.
    vec![
        Command::Next,
        Command::Previous,
        Command::SelectItem { item_id: 3 },
        Command::SelectSlide {
            item_id: 3,
            slide_index: 0,
        },
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
        Command::PresentAuthoredSlide {
            slide_json: "{}".into(),
            theme_json: "{}".into(),
            next_slide_json: None,
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
fn present_authored_slide_is_go_live_privilege() {
    // Presenting a deck slide changes the LIVE audience output, so it carries the GoLive
    // privilege (Producer+) — never an escalation path for Assistant/Viewer.
    let present = Command::PresentAuthoredSlide {
        slide_json: "{}".into(),
        theme_json: "{}".into(),
        next_slide_json: None,
    };
    assert!(authorize(Role::Operator, &present));
    assert!(authorize(Role::Producer, &present));
    assert!(!authorize(Role::Assistant, &present));
    assert!(!authorize(Role::Viewer, &present));
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
fn transcript_session_boundaries_require_the_same_permission_as_ingest() {
    // StartTranscript/EndTranscript (86akcfftu) are session-boundary siblings of
    // IngestTranscript above — same RBAC tier, same reasoning: whoever may feed the
    // transcript stream may also open/close the durable session around it.
    let start = Command::StartTranscript {
        label: "Sunday Service".into(),
        provider: "on-device-whisper".into(),
    };
    let end = Command::EndTranscript;
    for cmd in [start, end] {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(
            !authorize(Role::Assistant, &cmd),
            "assistant must NOT open/close a transcript session: {cmd:?}"
        );
        assert!(
            !authorize(Role::Viewer, &cmd),
            "viewer must NOT open/close a transcript session: {cmd:?}"
        );
    }
}

#[test]
fn sermon_note_read_and_edit_commands_require_the_same_permission_as_transcribe() {
    // Sermon-note draft LOAD/UPDATE persistence (86akgqdv0; PR #33 review, Sana F1
    // remediation) reads/writes AI-derived content generated from congregation speech — the
    // same RBAC tier as IngestTranscript/StartTranscript/EndTranscript, never a narrower or
    // wider one. `SaveSermonNoteDraft` is DELIBERATELY EXCLUDED from this group — see
    // `save_sermon_note_draft_requires_operator_not_merely_transcribe` below (PR #33 review,
    // Sana N2 — Medium).
    let cmds = [
        Command::GetActiveTranscriptId,
        Command::LoadSermonNoteDraft { transcript_id: 7 },
        Command::UpdateSermonNoteDraft {
            transcript_id: 7,
            edit: selahcue_lan::protocol::SermonNoteEditInput {
                title: "Faith that Endures".into(),
                summary: None,
                sections_json: "[]".into(),
                scriptures_json: "[]".into(),
            },
        },
    ];
    for cmd in cmds {
        assert!(authorize(Role::Operator, &cmd), "operator {cmd:?}");
        assert!(authorize(Role::Producer, &cmd), "producer {cmd:?}");
        assert!(
            !authorize(Role::Assistant, &cmd),
            "assistant must NOT touch a sermon-note draft: {cmd:?}"
        );
        assert!(
            !authorize(Role::Viewer, &cmd),
            "viewer must NOT touch a sermon-note draft: {cmd:?}"
        );
        assert_eq!(
            required_permission(&cmd),
            Permission::Transcribe,
            "sermon-note read/edit commands must require the SAME permission as \
             IngestTranscript: {cmd:?}"
        );
    }
}

#[test]
fn save_sermon_note_draft_requires_operator_not_merely_transcribe() {
    // PR #33 review, Sana N2 — Medium: `SaveSermonNoteDraft` (unlike Load/Update) can attach
    // a fresh, validly-labelled but fabricated `ai_generated`/`disclosure` pairing, or
    // wholesale-replace an already-persisted (possibly operator-edited) draft, so it is
    // narrowed to Operator-only — a Producer holds `Transcribe` (and so may Load/Update) but
    // must NOT be able to Save.
    let cmd = Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: selahcue_lan::protocol::SermonNoteDraftInput {
            title: "Faith that Endures".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
            ai_generated: true,
            disclosure: Some("AI-generated. Check every reference.".into()),
            provider: "SelahCue AI".into(),
            model: None,
        },
    };
    assert!(
        authorize(Role::Operator, &cmd),
        "operator must be able to save a draft"
    );
    assert!(
        !authorize(Role::Producer, &cmd),
        "a Producer holds Transcribe but must NOT be able to save/replace a draft"
    );
    assert!(
        !authorize(Role::Assistant, &cmd),
        "assistant must NOT save a sermon-note draft"
    );
    assert!(
        !authorize(Role::Viewer, &cmd),
        "viewer must NOT save a sermon-note draft"
    );
    assert_eq!(
        required_permission(&cmd),
        Permission::SaveSermonNotes,
        "SaveSermonNoteDraft must require its own, narrower permission, not Transcribe"
    );
}

#[test]
fn regenerate_with_retention_commands_require_operator_not_merely_transcribe() {
    // FR-129 (86akgqdx8): the regenerate-with-retention trio is the SAME tier as
    // `SaveSermonNoteDraft` and for the identical reason (see that command's own RBAC
    // test above and `Permission::SaveSermonNotes`'s doc comment) — a Producer holds
    // `Transcribe` (and so may Load/Update) but must NOT be able to Stage/Confirm/
    // Discard a regeneration.
    let draft = selahcue_lan::protocol::SermonNoteDraftInput {
        title: "Faith that Endures (regenerated)".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    };
    let cmds = [
        Command::StageSermonNoteRegeneration {
            transcript_id: 7,
            draft,
        },
        Command::ConfirmSermonNoteRegeneration { transcript_id: 7 },
        Command::DiscardSermonNoteRegeneration { transcript_id: 7 },
    ];
    for cmd in cmds {
        assert!(
            authorize(Role::Operator, &cmd),
            "operator must be able to {cmd:?}"
        );
        assert!(
            !authorize(Role::Producer, &cmd),
            "a Producer holds Transcribe but must NOT be able to: {cmd:?}"
        );
        assert!(
            !authorize(Role::Assistant, &cmd),
            "assistant must NOT: {cmd:?}"
        );
        assert!(!authorize(Role::Viewer, &cmd), "viewer must NOT: {cmd:?}");
        assert_eq!(
            required_permission(&cmd),
            Permission::SaveSermonNotes,
            "regenerate-with-retention commands must require the SAME permission as \
             SaveSermonNoteDraft, not Transcribe: {cmd:?}"
        );
    }
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

#[test]
fn manage_devices_is_operator_only() {
    // The device-management authority (pair / revoke / re-role controllers — the Remote Control
    // surface, ClickUp 86ajxer8n) is held ONLY by Operator. This is the gate the forthcoming
    // List/Approve/Deny/Revoke/SetRole device commands map to (deny-by-default for everyone below).
    assert!(Role::Operator.can(Permission::ManageDevices));
    assert!(!Role::Producer.can(Permission::ManageDevices));
    assert!(!Role::Assistant.can(Permission::ManageDevices));
    assert!(!Role::Viewer.can(Permission::ManageDevices));
}

#[test]
fn device_management_commands_are_operator_only() {
    // Every Remote Control device command maps to ManageDevices through the single authorize()
    // choke point → Operator alone is allowed; everyone below is denied by default (86ajxer8n).
    let cmds = [
        Command::ListRemoteDevices,
        Command::ApprovePairing {
            device_id: "dev-1".into(),
            role: Role::Assistant,
        },
        Command::DenyPairing {
            device_id: "dev-1".into(),
        },
        Command::RevokeSession {
            device_id: "dev-1".into(),
        },
        Command::SetSessionRole {
            device_id: "dev-1".into(),
            role: Role::Producer,
        },
        Command::NewPairingCode,
    ];
    for c in &cmds {
        assert!(
            authorize(Role::Operator, c),
            "operator must be allowed {c:?}"
        );
        assert!(
            !authorize(Role::Producer, c),
            "producer must be denied {c:?}"
        );
        assert!(
            !authorize(Role::Assistant, c),
            "assistant must be denied {c:?}"
        );
        assert!(!authorize(Role::Viewer, c), "viewer must be denied {c:?}");
    }
}

/// Every command that edits the plan DOCUMENT, including the lifecycle actions.
///
/// One list, consumed by both tests below: the "Operator only" check and the check that
/// `can_edit_plan` speaks for all of them. Two hand-kept lists would drift, and the drift would
/// be silent because each list would still pass its own test.
fn plan_edit_cmds() -> Vec<Command> {
    vec![
        Command::AddItem {
            kind: "song".into(),
            title: "Opening".into(),
            content: None,
        },
        Command::RemoveItem { item_id: 1 },
        Command::MoveItem { item_id: 1, to: 0 },
        Command::RenameItem {
            item_id: 1,
            title: "Renamed".into(),
        },
        Command::SetItemOwner {
            item_id: 1,
            owner: Some("Ada".into()),
        },
        Command::SetItemDuration {
            item_id: 1,
            secs: Some(300),
        },
        // Publish / hand-off (FR-006) and the plan lifecycle actions (FR-005).
        Command::PublishPlan,
        Command::NewPlan {
            name: "Next Week".into(),
        },
        Command::TemplatePlan {
            template: "sunday-morning".into(),
            name: "Next Week".into(),
        },
        Command::DuplicatePlan {
            name: "Sunday (copy)".into(),
        },
        Command::ImportPlan {
            name: "Imported".into(),
            items: vec![],
        },
    ]
}

#[test]
fn plan_publish_and_lifecycle_commands_are_operator_only_plan_editing() {
    // Publishing, creating, templating, duplicating and importing are all statements about the
    // plan DOCUMENT, so they carry the same `EditPlan` privilege as any other plan edit — and
    // like every plan edit, nobody below Operator holds it. In particular an Assistant, who may
    // stage scripture and navigate Preview, may not hand a plan off to the operator.
    for cmd in plan_edit_cmds() {
        assert_eq!(
            required_permission(&cmd),
            Permission::EditPlan,
            "{cmd:?} is not gated as plan editing"
        );
        assert!(authorize(Role::Operator, &cmd), "operator denied {cmd:?}");
        assert!(!authorize(Role::Producer, &cmd), "producer allowed {cmd:?}");
        assert!(
            !authorize(Role::Assistant, &cmd),
            "assistant allowed {cmd:?}"
        );
        assert!(!authorize(Role::Viewer, &cmd), "viewer allowed {cmd:?}");
    }
}

#[test]
fn can_edit_plan_agrees_with_the_choke_point_for_every_plan_edit_command() {
    // `can_edit_plan` is what the operator view reports as `can_edit`, and it answers by probing
    // ONE representative plan-edit command. This is the control that the probe is representative:
    // if a plan-edit command is moved onto a different permission, or the probe is changed to a
    // command that is not a plan edit, the affordance stops speaking for the commands it claims
    // to describe and this fails.
    //
    // KNOWN LIMIT, stated rather than implied: `plan_edit_cmds()` is hand-maintained. Rust
    // cannot enumerate `Command`'s variants without a derive this crate does not carry, so a NEW
    // plan-edit command added to `required_permission`'s `EditPlan` arm and not added to that
    // list is simply not covered here, and nothing fails. The exhaustive `match` in
    // `required_permission` forces the author to think about the permission; it cannot force
    // them to think about this list. Adding a plan-edit command means adding it there too.
    //
    // Repointing `PLAN_EDIT_PROBE` at `Command::GoLive` fails here on Producer, who may go live
    // but may not edit the plan.
    for role in [
        Role::Operator,
        Role::Producer,
        Role::Assistant,
        Role::Viewer,
    ] {
        let verdict = can_edit_plan(role);
        for cmd in plan_edit_cmds() {
            assert_eq!(
                authorize(role, &cmd),
                verdict,
                "{role:?}: can_edit_plan says {verdict} but the choke point disagrees about \
                 {cmd:?} — the affordance the UI renders no longer matches the gate the host \
                 enforces"
            );
        }
    }
    // The verdict is not a constant in either direction: without both of these, a `can_edit_plan`
    // hardwired to `true` or to `false` would satisfy the loop above for the roles that happen to
    // agree with it.
    assert!(
        can_edit_plan(Role::Operator),
        "the Operator may edit the plan"
    );
    assert!(
        !can_edit_plan(Role::Viewer),
        "a Viewer may not edit the plan"
    );
}

#[test]
fn the_view_only_verdict_never_widens_what_a_role_may_do() {
    // `can_edit` is an affordance, not a gate. Whatever the view reports, the choke point still
    // refuses a plan edit from a role that does not hold `EditPlan` — a client that ignores the
    // field entirely gains nothing.
    for role in [Role::Producer, Role::Assistant, Role::Viewer] {
        assert!(!can_edit_plan(role), "{role:?} must read as view-only");
        for cmd in plan_edit_cmds() {
            assert!(
                !authorize(role, &cmd),
                "{role:?} was allowed {cmd:?} despite reading as view-only"
            );
        }
    }
}
