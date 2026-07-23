//! RBAC policy tests — the security-critical authorization matrix. Public API only.

#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::Command;
use selahcue_lan::rbac::{authorize, Permission, Role};

fn navigate_cmds() -> Vec<Command> {
    vec![
        Command::Next,
        Command::Previous,
        Command::Clear,
        Command::SelectItem { item_id: 3 },
    ]
}

fn all_roles() -> [Role; 4] {
    [Role::Operator, Role::Producer, Role::Assistant, Role::Viewer]
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
        Command::ScriptureSearch { query: "love".into() },
        Command::StageScripture { reference: "John 3:16".into() },
        Command::GetState,
    ];
    for c in &cmds {
        assert!(authorize(Role::Operator, c), "operator denied {c:?}");
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
fn blackout_and_timer_are_producer_and_up() {
    for cmd in [
        Command::Blackout { on: true },
        Command::StartTimer { seconds: 60 },
        Command::StopTimer,
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
        &Command::ScriptureSearch { query: "grace".into() }
    ));
    assert!(authorize(
        Role::Assistant,
        &Command::StageScripture { reference: "Ps 23".into() }
    ));
    assert!(!authorize(Role::Assistant, &Command::GoLive));
    assert!(!authorize(Role::Assistant, &Command::Blackout { on: true }));
}

#[test]
fn viewer_can_only_monitor() {
    assert!(authorize(Role::Viewer, &Command::GetState));
    // Everything else is denied.
    for cmd in navigate_cmds() {
        assert!(!authorize(Role::Viewer, &cmd), "viewer nav {cmd:?}");
    }
    assert!(!authorize(Role::Viewer, &Command::GoLive));
    assert!(!authorize(
        Role::Viewer,
        &Command::ScriptureSearch { query: "x".into() }
    ));
}

#[test]
fn every_role_can_get_state() {
    for role in all_roles() {
        assert!(authorize(role, &Command::GetState), "{role:?} cannot monitor");
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
        Command::ScriptureSearch { query: "hope".into() },
        Command::StageScripture { reference: "Jer 29:11".into() },
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
    let chain = [Role::Viewer, Role::Assistant, Role::Producer, Role::Operator];
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
