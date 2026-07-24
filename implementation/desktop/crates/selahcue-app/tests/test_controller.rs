//! LiveController command→presentation logic (no transport).

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, DenyReason, ServerMessage};
use selahcue_present::Theme;

fn controller() -> (LiveController, Vec<u64>) {
    let mut plan = ServicePlan::new("Sunday");
    let a = plan.add_item(ItemKind::Song, "Opening Song");
    let b = plan.add_item(ItemKind::Scripture, "Romans 8:28");
    let c = plan.add_item(ItemKind::Section, "Sermon");
    (
        LiveController::new(plan, 320, 180, Theme::dark()),
        vec![a.0, b.0, c.0],
    )
}

fn live_is_black(c: &LiveController) -> bool {
    c.presenter().live_output().average_luminance() < 1e-6
}

#[test]
fn navigation_stages_preview_without_touching_live() {
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::Next), ControllerReply::Ack);
    assert_eq!(c.staged_index(), Some(0));
    assert_eq!(c.live_index(), None, "Next must not change Live (FR-012)");
    assert!(live_is_black(&c), "Live stays black until Go Live");
}

#[test]
fn go_live_commits_preview_to_live() {
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(c.live_index(), Some(0));
    assert!(!live_is_black(&c), "Live shows content after Go Live");
}

#[test]
fn next_advances_and_clamps_at_the_end() {
    let (mut c, _) = controller(); // 3 items
    for expected in [0, 1, 2, 2] {
        c.apply(&Command::Next);
        assert_eq!(c.staged_index(), Some(expected));
    }
}

#[test]
fn select_item_by_id_stages_it_and_unknown_is_denied() {
    let (mut c, ids) = controller();
    assert_eq!(
        c.apply(&Command::SelectItem { item_id: ids[2] }),
        ControllerReply::Ack
    );
    assert_eq!(c.staged_index(), Some(2));
    assert_eq!(
        c.apply(&Command::SelectItem { item_id: 9999 }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn clear_and_blackout_act_on_live() {
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    assert!(!live_is_black(&c));

    assert_eq!(c.apply(&Command::Blackout { on: true }), ControllerReply::Ack);
    assert!(c.is_blackout() && live_is_black(&c));

    assert_eq!(c.apply(&Command::Clear), ControllerReply::Ack);
    assert!(live_is_black(&c));
    assert_eq!(c.live_index(), None);
    assert!(!c.is_blackout());
}

#[test]
fn get_state_reports_live_item_and_blackout() {
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    match c.apply(&Command::GetState) {
        ControllerReply::Message(ServerMessage::State { live_item, blackout }) => {
            assert_eq!(live_item, Some(ids[0]));
            assert!(!blackout);
        }
        other => panic!("expected State, got {other:?}"),
    }
}

#[test]
fn scripture_search_parses_references() {
    let (mut c, _) = controller();
    match c.apply(&Command::ScriptureSearch {
        query: "John 3:16; Rom 8:28".into(),
    }) {
        ControllerReply::Message(ServerMessage::ScriptureResults { references, .. }) => {
            assert_eq!(references, vec!["John 3:16", "Romans 8:28"]);
        }
        other => panic!("expected ScriptureResults, got {other:?}"),
    }
}

#[test]
fn staged_scripture_can_go_live() {
    // A staged scripture (not a plan item) must be committable to Live.
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::StageScripture { reference: "John 3:16".into() }),
        ControllerReply::Ack
    );
    assert!(live_is_black(&c), "still preview-only before Go Live");
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert!(!live_is_black(&c), "scripture reaches Live on Go Live");
    assert_eq!(c.live_index(), None, "a scripture is not a plan index");
}

#[test]
fn staging_a_scripture_preserves_plan_navigation() {
    // Navigate to item 1, stage a scripture, then Next must resume near the cursor
    // (item 2) — not snap back to item 0.
    let (mut c, _) = controller();
    c.apply(&Command::Next); // -> 0
    c.apply(&Command::Next); // -> 1
    assert_eq!(c.staged_index(), Some(1));
    c.apply(&Command::StageScripture { reference: "Ps 23".into() });
    assert_eq!(c.staged_index(), None, "preview now holds a scripture");
    c.apply(&Command::Next);
    assert_eq!(c.staged_index(), Some(2), "Next resumes from the plan cursor, not 0");
}

#[test]
fn go_live_with_nothing_staged_is_denied() {
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::GoLive),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn timer_counts_down_reaches_time_up_and_stops() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    let t0 = Instant::now();

    // No timer initially.
    c.tick(t0);
    assert!(c.operator_view().timer.is_none());

    // Start a 60s countdown — it begins on the next tick (injected start instant).
    assert_eq!(
        c.apply(&Command::StartTimer { seconds: 60 }),
        ControllerReply::Ack
    );
    c.tick(t0);
    let snap = c.operator_view().timer.expect("timer running after start + tick");
    assert_eq!(snap.remaining_secs, Some(60));
    assert!(snap.running && !snap.time_up && !snap.warn);

    // 45s in: 15s remain, within the 30s warning threshold.
    c.tick(t0 + Duration::from_secs(45));
    let snap = c.operator_view().timer.unwrap();
    assert_eq!(snap.remaining_secs, Some(15));
    assert!(snap.warn && !snap.time_up);

    // Past the end: TIME UP, zero remaining.
    c.tick(t0 + Duration::from_secs(65));
    let snap = c.operator_view().timer.unwrap();
    assert!(snap.time_up);
    assert_eq!(snap.remaining_secs, Some(0));

    // Stop clears it.
    assert_eq!(c.apply(&Command::StopTimer), ControllerReply::Ack);
    assert!(c.operator_view().timer.is_none());
}

#[test]
fn countdown_display_ceils_seconds() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    let t0 = Instant::now();
    c.apply(&Command::StartTimer { seconds: 10 });
    c.tick(t0);
    // 0.5s in: 9.5s remain -> ceil 10 (the start value holds for the full first second).
    c.tick(t0 + Duration::from_millis(500));
    assert_eq!(c.operator_view().timer.unwrap().remaining_secs, Some(10));
    // 9.5s in: 0.5s remain -> ceil 1 (the last second reads 0:01, not 0:00), not yet up.
    c.tick(t0 + Duration::from_millis(9500));
    let snap = c.operator_view().timer.unwrap();
    assert_eq!(snap.remaining_secs, Some(1));
    assert!(!snap.time_up);
    // Exactly at the target: TIME UP, zero remaining.
    c.tick(t0 + Duration::from_secs(10));
    assert!(c.operator_view().timer.unwrap().time_up);
}

#[test]
fn restarting_a_running_timer_does_not_report_stale_state() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    let t0 = Instant::now();
    c.apply(&Command::StartTimer { seconds: 60 });
    c.tick(t0);
    c.tick(t0 + Duration::from_secs(20));
    assert_eq!(c.operator_view().timer.unwrap().remaining_secs, Some(40));

    // Restart to 120 WITHOUT a StopTimer: the snapshot must not mix the old 0:40 /
    // running=false with the fresh timer.
    c.apply(&Command::StartTimer { seconds: 120 });
    assert!(
        c.operator_view().timer.is_none(),
        "no stale snapshot between a restart and the next tick"
    );
    c.tick(t0 + Duration::from_secs(21));
    let snap = c.operator_view().timer.unwrap();
    assert_eq!(snap.remaining_secs, Some(120));
    assert!(snap.running);
}

#[test]
fn timer_overlays_live_and_survives_blackout() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let t0 = Instant::now();
    c.apply(&Command::StartTimer { seconds: 300 });
    c.tick(t0);
    assert!(!live_is_black(&c), "slide + timer overlay on live");

    // Blackout, then a timer tick must NOT reveal the content (recompose preserves it).
    c.apply(&Command::Blackout { on: true });
    c.tick(t0 + Duration::from_secs(1));
    assert!(live_is_black(&c), "blackout preserved across a timer tick");
}
