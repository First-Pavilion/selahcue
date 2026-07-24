//! The operator control surface (view-model + shell) — verified independently of any
//! GUI. These exercise exactly the surface the Tauri operator shell binds to.

#![allow(clippy::unwrap_used)]

use selahcue_app::{LiveController, OperatorShell};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};

fn shell() -> OperatorShell {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    )));
    OperatorShell::new(controller)
}

#[test]
fn initial_view_reflects_the_plan_with_nothing_live() {
    let view = shell().view();
    assert_eq!(view.plan_name, "Sunday Service");
    assert_eq!(view.items.len(), 3);
    assert_eq!(view.items[0].kind, "song");
    assert_eq!(view.items[1].kind, "scripture");
    assert_eq!(view.items[1].title, "Romans 8:28");
    assert_eq!(view.live_index, None);
    assert_eq!(view.staged_index, None);
    assert!(!view.blackout);
    assert!(view.items.iter().all(|i| !i.is_live && !i.is_staged));
}

#[test]
fn next_stages_preview_without_going_live() {
    let s = shell();
    let view = s.next();
    assert_eq!(view.staged_index, Some(0));
    assert!(view.items[0].is_staged);
    assert_eq!(view.live_index, None, "Next must not change Live (FR-012)");
    assert!(view.items.iter().all(|i| !i.is_live));
}

#[test]
fn go_live_commits_the_staged_item() {
    let s = shell();
    s.next();
    let view = s.go_live();
    assert_eq!(view.live_index, Some(0));
    assert!(view.items[0].is_live);
}

#[test]
fn advancing_after_go_live_keeps_live_while_preview_moves() {
    let s = shell();
    s.next(); // stage 0
    s.go_live(); // live 0
    let view = s.next(); // stage 1
    assert_eq!(
        view.live_index,
        Some(0),
        "Live stays until the next Go Live"
    );
    assert_eq!(view.staged_index, Some(1));
    assert!(view.items[0].is_live && !view.items[0].is_staged);
    assert!(view.items[1].is_staged && !view.items[1].is_live);
}

#[test]
fn select_stages_a_specific_item_by_id() {
    let s = shell();
    let id = s.view().items[2].id; // the "Sermon" section
    let view = s.select(id);
    assert_eq!(view.staged_index, Some(2));
    assert!(view.items[2].is_staged);
}

#[test]
fn blackout_and_clear_are_reflected() {
    let s = shell();
    s.next();
    s.go_live();
    assert!(s.blackout(true).blackout);
    assert!(!s.blackout(false).blackout);
    let cleared = s.clear();
    assert_eq!(cleared.live_index, None);
    assert!(cleared.items.iter().all(|i| !i.is_live));
}

#[test]
fn view_serializes_to_json_for_the_ui() {
    let s = shell();
    s.next();
    s.go_live();
    let json = serde_json::to_string(&s.view()).unwrap();
    // The UI consumes these exact fields.
    assert!(json.contains("\"plan_name\":\"Sunday Service\""));
    assert!(json.contains("\"is_live\":true"));
    assert!(json.contains("\"live_index\":0"));
    assert!(json.contains("\"blackout\":false"));
    // Round-trips structurally.
    let back: serde_json::Value = serde_json::from_str(&json).unwrap();
    assert_eq!(back["items"].as_array().unwrap().len(), 3);
}

#[test]
fn shell_clones_share_one_controller() {
    let a = shell();
    let b = a.clone();
    a.next();
    a.go_live();
    // b sees a's change — they share the same controller.
    assert_eq!(b.view().live_index, Some(0));
}
