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

// --- console thumbnails: the true Preview/Live pixels, read-only (86ajtwq28) ---

#[test]
fn console_thumbnails_return_the_bounded_frames_and_never_touch_on_air() {
    let s = shell(); // 320x180 output
    s.next();
    s.go_live(); // put a real slide on Live so the frame is non-trivial

    // The full-resolution Live readback BEFORE any thumbnail render (320x180 >= bound -> no
    // downscale, so this IS the true live frame).
    let live_before = s.console_thumbnails(320, 180).1.bytes().to_vec();

    // A console refresh at monitor size: both frames fit within the bound.
    let (pv, lv) = s.console_thumbnails(160, 90);
    assert!(
        pv.width() <= 160 && pv.height() <= 90,
        "preview thumbnail within the bound"
    );
    assert!(
        lv.width() <= 160 && lv.height() <= 90,
        "live thumbnail within the bound"
    );
    assert_eq!(
        (lv.width(), lv.height()),
        (160, 90),
        "16:9 source -> 160x90"
    );

    // Read-only: rendering the thumbnails changed NEITHER the on-air view-model NOR the
    // true live output pixels (rendering the preview must never affect what is on air).
    assert_eq!(
        s.view().live_index,
        Some(0),
        "Live selection unchanged by a console render"
    );
    let live_after = s.console_thumbnails(320, 180).1.bytes().to_vec();
    assert_eq!(
        live_before, live_after,
        "a console render did not change the live output"
    );
}

#[test]
fn shell_ingest_detect_approve_stage_flow() {
    let s = shell();
    // Ingest a spoken reference — the transcript panel and detection queue populate.
    let view = s.ingest_transcript("open to John chapter 3 verse 16", 0, 2_000);
    assert_eq!(view.transcript.len(), 1);
    assert_eq!(view.detections.len(), 1);
    assert_eq!(view.detections[0].reference, "John 3:16");
    let id = view.detections[0].id;

    // Approve → the verse stages in Preview; the queue empties; Live is untouched.
    let after = s.approve_detection(id);
    assert_eq!(after.staged_scripture.as_deref(), Some("John 3:16"));
    assert!(after.detections.is_empty());
    assert_eq!(after.live_index, None, "approve stages Preview, never Live");
}

#[test]
fn shell_dismiss_removes_the_detection() {
    let s = shell();
    let view = s.ingest_transcript("as First Corinthians 13 says", 0, 1_000);
    let id = view.detections[0].id;
    let after = s.dismiss_detection(id);
    assert!(after.detections.is_empty());
    assert_eq!(after.staged_scripture, None, "dismiss stages nothing");
}
