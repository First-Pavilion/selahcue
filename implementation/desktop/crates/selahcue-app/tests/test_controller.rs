//! LiveController command→presentation logic (no transport).

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, DenyReason, ServerMessage};
use selahcue_present::{
    Element, Fit, MediaRef, Rgba, ShapeKind, TextAlign, Theme, VAlign, MAX_ELEMENTS,
    MAX_TEXT_ELEMENT_LEN,
};

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
fn blackout_and_clear_are_local_and_act_within_200ms() {
    // FR-076/077 (story 86ajp0awx): the operator's emergency controls act on the
    // in-process presenter — there is NO LAN round-trip on this path (the server
    // is a separate layer, only for remote clients), so they work with the
    // network disabled and well inside the 200ms budget. The margin here is
    // ~1000x (a sub-millisecond in-memory engine op), so this is a locality +
    // latency sanity check, not a tight timing race.
    use std::time::Instant;
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive); // put content on Live
    assert!(!live_is_black(&c));

    let t = Instant::now();
    let reply = c.apply(&Command::Blackout { on: true });
    let blackout_ms = t.elapsed().as_millis();
    assert_eq!(reply, ControllerReply::Ack);
    assert!(
        live_is_black(&c),
        "blackout darkens the audience output immediately"
    );
    assert!(
        blackout_ms < 200,
        "blackout took {blackout_ms}ms (>200ms budget)"
    );

    let t = Instant::now();
    let reply = c.apply(&Command::Clear);
    let clear_ms = t.elapsed().as_millis();
    assert_eq!(reply, ControllerReply::Ack);
    assert_eq!(c.live_index(), None, "clear removes the live item");
    assert!(clear_ms < 200, "clear took {clear_ms}ms (>200ms budget)");
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

    assert_eq!(
        c.apply(&Command::Blackout { on: true }),
        ControllerReply::Ack
    );
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
        ControllerReply::Message(ServerMessage::State {
            live_item,
            blackout,
        }) => {
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
        translation: None,
    }) {
        ControllerReply::Message(ServerMessage::ScriptureResults { references, .. }) => {
            assert_eq!(references, vec!["John 3:16", "Romans 8:28"]);
        }
        other => panic!("expected ScriptureResults, got {other:?}"),
    }
}

#[test]
fn get_chapter_returns_numbered_verses_and_neighbours() {
    // The mobile verse-list browser fetches a whole chapter over the wire.
    let (mut c, _) = controller();
    match c.apply(&Command::GetChapter {
        reference: "Romans 8".into(),
        translation: None,
    }) {
        ControllerReply::Message(ServerMessage::Chapter {
            book_name,
            chapter,
            translation,
            verses,
            prev_ref,
            next_ref,
        }) => {
            assert_eq!(book_name, "Romans");
            assert_eq!(chapter, 8);
            assert_eq!(translation, "KJV");
            assert_eq!(verses.first().map(|v| v.number), Some(1));
            assert!(verses.len() > 30, "Romans 8 has 39 verses");
            assert!(verses.iter().all(|v| !v.text.is_empty()));
            assert_eq!(prev_ref.as_deref(), Some("Romans 7"));
            assert_eq!(next_ref.as_deref(), Some("Romans 9"));
        }
        other => panic!("expected Chapter, got {other:?}"),
    }
}

#[test]
fn get_chapter_clamps_at_the_ends_of_the_canon() {
    let (mut c, _) = controller();
    // Genesis 1 has no previous chapter; Revelation 22 has no next.
    match c.apply(&Command::GetChapter {
        reference: "Genesis 1".into(),
        translation: None,
    }) {
        ControllerReply::Message(ServerMessage::Chapter { prev_ref, .. }) => {
            assert_eq!(prev_ref, None, "nothing before Genesis 1");
        }
        other => panic!("expected Chapter, got {other:?}"),
    }
    match c.apply(&Command::GetChapter {
        reference: "Revelation 22".into(),
        translation: None,
    }) {
        ControllerReply::Message(ServerMessage::Chapter { next_ref, .. }) => {
            assert_eq!(next_ref, None, "nothing after Revelation 22");
        }
        other => panic!("expected Chapter, got {other:?}"),
    }
}

#[test]
fn get_chapter_rejects_garbage_and_unknown_translations() {
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::GetChapter {
            reference: "not a book".into(),
            translation: None,
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
    );
    assert_eq!(
        c.apply(&Command::GetChapter {
            reference: "Romans 8".into(),
            translation: Some("NOPE".into()),
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
    );
}

#[test]
fn staged_scripture_can_go_live() {
    // A staged scripture (not a plan item) must be committable to Live.
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::StageScripture {
            reference: "John 3:16".into(),
            translation: None,
        }),
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
    c.apply(&Command::StageScripture {
        reference: "Ps 23".into(),
        translation: None,
    });
    assert_eq!(c.staged_index(), None, "preview now holds a scripture");
    c.apply(&Command::Next);
    assert_eq!(
        c.staged_index(),
        Some(2),
        "Next resumes from the plan cursor, not 0"
    );
}

#[test]
fn stage_output_is_a_distinct_confidence_surface() {
    use std::time::Instant;
    let (mut c, _) = controller();
    c.tick(Instant::now());
    // The confidence monitor is never blank — it always shows a timer/clock strip.
    assert!(
        c.stage_output().average_luminance() > 1e-6,
        "stage always shows a monitor scene"
    );
    // Go live — the stage composes current/next lines, distinct from the main output.
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    c.tick(Instant::now());
    assert_ne!(
        c.stage_output().bytes(),
        c.presenter().live_output().bytes(),
        "stage composes a different scene than the main audience output (FR-037)"
    );
}

#[test]
fn pairing_qr_shows_on_stage_only_and_expires() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let t0 = Instant::now();
    c.tick(t0);
    let audience_before = c.presenter().live_output().bytes().to_vec();
    let stage_before = c.stage_output().bytes().to_vec();

    // Pairing mode: the STAGE output becomes the (white-background) QR; the audience
    // output is untouched.
    c.show_pairing_qr(
        "selahcue://pair?host=10.0.0.5&port=1234&pin=ab&code=ABCD2345".into(),
        t0 + Duration::from_secs(120),
    );
    c.tick(t0 + Duration::from_secs(1));
    assert!(c.pairing_qr_active());
    assert_ne!(
        c.stage_output().bytes(),
        stage_before.as_slice(),
        "stage shows the QR"
    );
    assert!(
        c.stage_output().average_luminance() > 0.5,
        "QR is white-backed (unmistakable vs the dark scene)"
    );
    assert_eq!(
        c.presenter().live_output().bytes(),
        audience_before.as_slice(),
        "the audience output never shows pairing"
    );

    // The QR auto-expires with its code's TTL and the speaker scene returns.
    c.tick(t0 + Duration::from_secs(121));
    assert!(!c.pairing_qr_active());
    assert_eq!(
        c.stage_output().bytes(),
        stage_before.as_slice(),
        "scene restored"
    );
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
    let snap = c
        .operator_view()
        .timer
        .expect("timer running after start + tick");
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
fn timer_shows_on_the_confidence_monitor_not_the_audience_output() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let t0 = Instant::now();
    c.tick(t0);
    let audience_before = c.presenter().live_output().bytes().to_vec();
    let stage_before = c.stage_output().bytes().to_vec();

    // Run a short countdown to TIME UP.
    c.apply(&Command::StartTimer { seconds: 1 });
    c.tick(t0);
    c.tick(t0 + Duration::from_secs(2)); // past the target → TIME UP

    // The audience/program output is UNCHANGED — the countdown is a speaker aid.
    assert_eq!(
        c.presenter().live_output().bytes(),
        audience_before.as_slice(),
        "the timer must NOT appear on the audience output"
    );
    // The confidence monitor DID change — it carries the timer (now TIME UP).
    assert_ne!(
        c.stage_output().bytes(),
        stage_before.as_slice(),
        "the timer appears on the stage/confidence output (FR-037)"
    );
}

#[test]
fn session_snapshot_restores_exact_live_state() {
    use selahcue_app::ControllerSnapshot;
    use std::time::{Duration, Instant};
    let t0 = Instant::now();

    // Drive a session: item 1 live, item 2 staged, a countdown 37s in.
    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    a.apply(&Command::Next); // stage item 2 in Preview
    a.apply(&Command::StartTimer { seconds: 300 });
    a.tick(t0);
    a.tick(t0 + Duration::from_secs(37));
    let snap = a.snapshot(t0 + Duration::from_secs(37));

    // A fresh controller (same plan) restores to the exact live state.
    let (mut b, _) = controller();
    b.restore(&snap);
    let t1 = t0 + Duration::from_secs(40); // relaunch happens a little later
    b.tick(t1);

    assert_eq!(b.live_index(), Some(1), "live item recovered");
    assert_eq!(b.staged_index(), Some(2), "preview item recovered");
    assert!(!b.is_blackout());
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "the audience output re-renders identically"
    );
    // The countdown resumed from its persisted elapsed (37s in => 263s remain).
    let timer = b.operator_view().timer.expect("timer resumed");
    assert!(timer.running);
    assert_eq!(timer.remaining_secs, Some(263));

    // Round-trip sanity: snapshotting B yields the same persisted state.
    let again = b.snapshot(t1);
    assert_eq!(
        ControllerSnapshot {
            timer_elapsed_secs: snap.timer_elapsed_secs,
            ..again.clone()
        },
        snap,
        "snapshot(B) matches snapshot(A) apart from timer drift"
    );
}

#[test]
fn restore_recovers_blackout_and_survives_stale_indices() {
    use selahcue_app::ControllerSnapshot;
    use std::time::Instant;
    let (mut c, _) = controller();
    // A snapshot from some other/older plan: indices out of range + blackout on.
    c.restore(&ControllerSnapshot {
        live_idx: Some(99),
        staged_idx: Some(42),
        plan_cursor: Some(7),
        blackout: true,
        ..Default::default()
    });
    c.tick(Instant::now());
    assert_eq!(c.live_index(), None, "stale live index ignored, no panic");
    assert!(
        c.is_blackout(),
        "blackout restored (safety: come back dark)"
    );
    assert!(live_is_black(&c), "output is actually black");
}

#[test]
fn restore_with_nothing_staged_leaves_preview_truly_empty() {
    use selahcue_app::ControllerSnapshot;
    use std::time::Instant;
    // Review 7u finding: go_live leaves its input in the staged slot, so a restore of
    // {live: Some, staged: None} used to leave a PHANTOM staged item — the monitor
    // showed a "next" that was never staged, and a later GoLive desynced live_idx.
    let (mut c, _) = controller();
    c.restore(&ControllerSnapshot {
        live_idx: Some(1),
        staged_idx: None,
        ..Default::default()
    });
    c.tick(Instant::now());
    assert_eq!(c.live_index(), Some(1));
    assert_eq!(c.staged_index(), None);
    assert!(
        c.presenter().staged().is_none(),
        "the presenter's staged slot must be empty too — no phantom next"
    );
    assert!(
        c.presenter().preview_output().average_luminance() < 1e-6,
        "the preview readback is blank"
    );
    // And GoLive with nothing staged stays DENIED after a restore.
    assert_eq!(
        c.apply(&Command::GoLive),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.live_index(),
        Some(1),
        "live is untouched by the denied GoLive"
    );
}

#[test]
fn a_live_scripture_survives_crash_recovery() {
    use std::time::Instant;
    // Review 7u finding: a scripture committed to LIVE has live_idx=None, so recovery
    // used to restore a BLANK audience surface. The reference is now persisted.
    let (mut a, _) = controller();
    a.apply(&Command::StageScripture {
        reference: "Psalm 23:1".into(),
        translation: None,
    });
    a.apply(&Command::GoLive);
    assert!(!live_is_black(&a), "scripture is on the live output");
    let snap = a.snapshot(Instant::now());
    assert_eq!(snap.live_scripture.as_deref(), Some("Psalm 23:1"));

    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(Instant::now());
    assert!(
        !live_is_black(&b),
        "the scripture is BACK on the audience output"
    );
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "recovered audience output is byte-identical"
    );
    assert_eq!(b.live_index(), None, "still honestly a non-plan slide");
}

#[test]
fn a_staged_scripture_survives_crash_recovery() {
    use std::time::Instant;
    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    a.apply(&Command::StageScripture {
        reference: "John 3:16".into(),
        translation: None,
    });
    let snap = a.snapshot(Instant::now());

    let (mut b, _) = controller();
    b.restore(&snap);
    assert_eq!(b.live_index(), Some(0));
    assert_eq!(b.staged_index(), None, "preview holds a non-plan slide");
    assert_eq!(
        b.presenter().preview_output().bytes(),
        a.presenter().preview_output().bytes(),
        "the staged scripture is back in Preview"
    );
    // Going live commits the recovered scripture, exactly as it would have pre-crash.
    assert_eq!(b.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(b.live_index(), None);
}

#[test]
fn plan_edits_add_remove_move_rename_with_index_fixup() {
    let (mut c, ids) = controller(); // 3 items
                                     // Live = item 1 (idx 1), staged = item 2 (idx 2).
    c.apply(&Command::Next);
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    c.apply(&Command::Next);
    assert_eq!((c.live_index(), c.staged_index()), (Some(1), Some(2)));

    // Add appends.
    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "song".into(),
            title: "New Song".into(),
            content: None,
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().len(), 4);
    assert!(c.take_plan_dirty());

    // Remove item 0: everything shifts down; Live/staged indices follow their items.
    assert_eq!(
        c.apply(&Command::RemoveItem { item_id: ids[0] }),
        ControllerReply::Ack
    );
    assert_eq!((c.live_index(), c.staged_index()), (Some(0), Some(1)));

    // Move the staged item (now idx 1) to the end: indices follow.
    let staged_id = c.plan().items()[1].id.0;
    assert_eq!(
        c.apply(&Command::MoveItem {
            item_id: staged_id,
            to: 2
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.staged_index(), Some(2));
    assert_eq!(c.live_index(), Some(0), "live item did not move");

    // Rename a staged item re-renders Preview; bad edits are denied.
    assert_eq!(
        c.apply(&Command::RenameItem {
            item_id: staged_id,
            title: "Renamed".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "nonsense".into(),
            title: "x".into(),
            content: None,
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::RemoveItem { item_id: 9999 }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn removing_the_live_item_never_blanks_the_audience_output() {
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    assert!(!live_is_black(&c));
    let before = c.presenter().live_output().bytes().to_vec();

    // Removing the item that is LIVE keeps its rendered slide on screen (an edit
    // never changes the audience output); only the bookkeeping clears.
    assert_eq!(
        c.apply(&Command::RemoveItem { item_id: ids[0] }),
        ControllerReply::Ack
    );
    assert_eq!(c.live_index(), None);
    assert_eq!(
        c.presenter().live_output().bytes(),
        before.as_slice(),
        "audience output unchanged by the edit"
    );
}

#[test]
fn removing_the_live_item_survives_crash_recovery() {
    use std::time::Instant;
    // Go live on the first item, then remove it: the slide stays on screen. A crash
    // right after must recover THAT screen — the snapshot tracks the removed item's
    // text as a free live slide (it is no longer a plan index).
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    c.apply(&Command::RemoveItem { item_id: ids[0] });
    assert!(!live_is_black(&c));

    let snap = c.snapshot(Instant::now());
    assert_eq!(snap.live_idx, None, "removed item is not a plan index");
    assert_eq!(
        snap.live_free_text.as_deref(),
        Some("Opening Song"),
        "the on-screen slide is persisted as FREE text (not a scripture)"
    );

    // A fresh controller over the post-edit plan restores a non-blank live output.
    let (mut fresh, _) = controller();
    fresh.apply(&Command::RemoveItem { item_id: ids[0] });
    fresh.restore(&snap);
    assert!(
        !live_is_black(&fresh),
        "recovery shows the removed item's slide, not a blank surface"
    );
}

#[test]
fn staged_scripture_composes_verse_text_and_survives_recovery() {
    use std::time::Instant;
    let (mut c, _) = controller();
    // Staging a reference composes the bundled translation's verse text.
    assert_eq!(
        c.apply(&Command::StageScripture {
            reference: "Romans 8:28".into(),
            translation: None,
        }),
        ControllerReply::Ack
    );
    c.apply(&Command::GoLive);
    let body = c.presenter().live_slide().expect("live").body.join(" ");
    assert!(
        body.contains("all things work together for good"),
        "verse text on the live output: {body}"
    );

    // Crash recovery re-composes the same verse text from the reference.
    let snap = c.snapshot(Instant::now());
    let (mut fresh, _) = controller();
    fresh.restore(&snap);
    let restored = fresh
        .presenter()
        .live_slide()
        .expect("restored")
        .body
        .join(" ");
    assert!(restored.contains("all things work together for good"));

    // A free-slide text (not a reference) still falls back to a title slide —
    // the 7v removed-live-item recovery path is unchanged.
    let (mut other, _) = controller();
    other.apply(&Command::StageScripture {
        reference: "Announcements".into(),
        translation: None,
    });
    let staged = other.presenter().staged().expect("staged");
    assert_eq!(staged.title, "Announcements");
    assert!(staged.body.is_empty());
}

#[test]
fn scripture_search_falls_back_to_keyword_hits() {
    let (mut c, _) = controller();
    // A reference query parses (and is confirmed against the bundle).
    let r = c.apply(&Command::ScriptureSearch {
        query: "Rom 8:28".into(),
        translation: None,
    });
    let refs = match r {
        ControllerReply::Message(ServerMessage::ScriptureResults { references, .. }) => references,
        other => panic!("expected results, got {other:?}"),
    };
    assert_eq!(refs, vec!["Romans 8:28".to_string()]);

    // A keyword query scans the verse text.
    let r = c.apply(&Command::ScriptureSearch {
        query: "my shepherd I shall not want".into(),
        translation: None,
    });
    let refs = match r {
        ControllerReply::Message(ServerMessage::ScriptureResults { references, .. }) => references,
        other => panic!("expected results, got {other:?}"),
    };
    assert!(
        refs.contains(&"Psalms 23:1".to_string()) || refs.iter().any(|r| r.contains("23:1")),
        "keyword hits: {refs:?}"
    );
}

#[test]
fn removed_live_item_with_a_reference_title_recovers_verbatim() {
    use std::time::Instant;
    // A plan item whose TITLE parses as a reference ("Romans 8:28") renders as a
    // title-only slide. Removing it while live keeps that slide; recovery must
    // restore it VERBATIM — never recompose it into verse text (review 7y-B).
    let (mut c, ids) = controller();
    c.apply(&Command::SelectItem { item_id: ids[1] }); // "Romans 8:28" item
    c.apply(&Command::GoLive);
    let before = c.presenter().live_output().bytes().to_vec();
    c.apply(&Command::RemoveItem { item_id: ids[1] });

    let snap = c.snapshot(Instant::now());
    assert_eq!(
        snap.live_scripture, None,
        "a removed ITEM is not a scripture"
    );
    assert_eq!(snap.live_free_text.as_deref(), Some("Romans 8:28"));

    let (mut fresh, _) = controller();
    fresh.apply(&Command::RemoveItem { item_id: ids[1] });
    fresh.restore(&snap);
    assert_eq!(
        fresh.presenter().live_output().bytes(),
        before.as_slice(),
        "recovery re-renders the exact pre-crash surface (no verse recompose)"
    );
    // ...while a REAL scripture recomposes its verse text (distinct field).
    let live = fresh.presenter().live_slide().expect("live");
    assert!(live.body.is_empty(), "title-only slide restored");
}

#[test]
fn scripture_slides_keep_the_full_passage_never_truncating() {
    // Zero content loss (FR-010, owner refine): a scripture slide carries the FULL
    // passage — one paragraph per verse, NEVER truncated with an ellipsis. The
    // compositor word-wraps + auto-sizes so the whole thing fits + fills the box.
    let (mut c, _) = controller();

    // The longest KJV verse (Esther 8:9) is kept in full — no "…", tail words present.
    c.apply(&Command::StageScripture {
        reference: "Esther 8:9".into(),
        translation: None,
    });
    let slide = c.presenter().staged().expect("staged");
    let joined = slide.body.join(" ");
    assert!(
        !joined.contains('\u{2026}'),
        "no ellipsis truncation: {joined:?}"
    );
    assert!(
        joined.contains("provinces"),
        "the FULL verse is kept (tail not dropped): {joined:?}"
    );

    // A whole chapter (Psalm 119, 176 verses) keeps EVERY verse as its own paragraph.
    c.apply(&Command::StageScripture {
        reference: "Psalm 119".into(),
        translation: None,
    });
    let slide = c.presenter().staged().expect("staged");
    assert_eq!(
        slide.body.len(),
        176,
        "one paragraph per verse, none dropped"
    );
    assert!(
        !slide.body.iter().any(|l| l.contains('\u{2026}')),
        "no ellipsis anywhere"
    );

    // A short verse is a single paragraph (unchanged).
    c.apply(&Command::StageScripture {
        reference: "John 11:35".into(),
        translation: None,
    });
    let slide = c.presenter().staged().expect("staged");
    assert_eq!(
        slide.body.len(),
        1,
        "a single-verse passage is one paragraph"
    );
    assert!(!slide.body[0].contains('\u{2026}'));
}

#[test]
fn identify_overlay_arms_expires_and_never_touches_presentation_state() {
    use selahcue_app::IDENTIFY_TTL;
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let t0 = Instant::now();
    c.tick(t0);
    let live_before = c.presenter().live_output().bytes().to_vec();

    // The command arms; the next tick starts the window (injected clock).
    assert_eq!(c.apply(&Command::IdentifyOutputs), ControllerReply::Ack);
    assert!(c.identify_until().is_none(), "starts on tick, not on apply");
    c.tick(t0 + Duration::from_millis(16));
    let until = c.identify_until().expect("identify active");
    assert!(until > t0 + IDENTIFY_TTL - Duration::from_secs(1));

    // Presentation state is untouched the whole time (the overlay is a
    // window-level blit in the shell) — the audience output never changed.
    assert_eq!(c.presenter().live_output().bytes(), live_before.as_slice());
    assert_eq!(c.live_index(), Some(0));

    // Auto-expiry.
    c.tick(t0 + IDENTIFY_TTL + Duration::from_secs(1));
    assert!(c.identify_until().is_none(), "expired");
    assert_eq!(c.presenter().live_output().bytes(), live_before.as_slice());
}

#[test]
fn output_assignments_are_bounded_and_latest_per_role_wins() {
    let (mut c, _) = controller();
    // Repeated assignment commands never grow state past one entry per role.
    for i in 0..100 {
        c.apply(&Command::AssignOutput {
            role: "main".into(),
            display_key: format!("D{i}|1x1"),
        });
    }
    c.apply(&Command::AssignOutput {
        role: "stage".into(),
        display_key: "S|2x2".into(),
    });
    let pending = c.take_pending_assignments();
    assert_eq!(pending.len(), 2, "one pending entry per role");
    assert!(pending.contains(&("main".into(), "D99|1x1".into())));
    assert!(c.take_pending_assignments().is_empty(), "drained");
    // Unknown roles are rejected outright.
    assert_eq!(
        c.apply(&Command::AssignOutput {
            role: "disco".into(),
            display_key: "X|1x1".into()
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn assignment_keys_are_validated_against_the_advertised_displays() {
    use selahcue_lan::protocol::DisplayView;
    let (mut c, _) = controller();
    // With no display list injected (tests/headless), any key passes through —
    // the desktop shell re-validates against live monitors before applying.
    assert_eq!(
        c.apply(&Command::AssignOutput {
            role: "main".into(),
            display_key: "anything".into()
        }),
        ControllerReply::Ack
    );
    c.take_pending_assignments();
    // Once displays are advertised, unknown keys are denied at the controller
    // (the client sees the rejection instead of a silent no-op).
    c.set_output_status(
        vec![],
        vec![DisplayView {
            key: "Projector|1920x1080".into(),
            name: "Projector".into(),
            width: 1920,
            height: 1080,
        }],
    );
    assert_eq!(
        c.apply(&Command::AssignOutput {
            role: "main".into(),
            display_key: "Gone|1x1".into()
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::AssignOutput {
            role: "main".into(),
            display_key: "Projector|1920x1080".into()
        }),
        ControllerReply::Ack
    );
}

#[test]
fn adjust_timer_extends_reduces_and_survives_recovery() {
    use std::time::{Duration, Instant};
    let (mut c, _) = controller();
    // No timer -> nothing to adjust.
    assert_eq!(
        c.apply(&Command::AdjustTimer { delta_secs: 60 }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );

    let t0 = Instant::now();
    c.apply(&Command::StartTimer { seconds: 300 });
    c.tick(t0);
    // At 1:20 elapsed, +1:00 -> remaining grows from 3:00 to 4:00.
    let at = t0 + Duration::from_secs(80);
    assert_eq!(
        c.apply(&Command::AdjustTimer { delta_secs: 60 }),
        ControllerReply::Ack
    );
    c.tick(at);
    let t = c.operator_view().timer.expect("timer");
    assert_eq!(t.remaining_secs, Some(280), "300 - 80 + 60");
    assert!(!t.time_up);

    // The adjusted total persists through crash recovery.
    let snap = c.snapshot(at);
    assert_eq!(snap.timer_total_secs, Some(360));
    let (mut fresh, _) = controller();
    fresh.restore(&snap);
    fresh.tick(at);
    let t = fresh.operator_view().timer.expect("restored timer");
    assert_eq!(t.remaining_secs, Some(280), "adjustment survived recovery");

    // Subtracting past the elapsed lands in TIME UP (never underflows).
    assert_eq!(
        c.apply(&Command::AdjustTimer { delta_secs: -9_999 }),
        ControllerReply::Ack
    );
    c.tick(at + Duration::from_secs(1));
    assert!(c.operator_view().timer.expect("timer").time_up);
}

// --- Songs: multi-slide in-item navigation, stage next-line, recovery (S8-1) ---

use selahcue_core::plan::{stanzas_from_text, Stanza};

/// A plan whose first item is a 3-stanza song, then a scripture, then a section.
fn song_controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday");
    let s = plan.add_item(ItemKind::Song, "Way Maker");
    plan.get_mut(s).unwrap().stanzas = vec![
        Stanza {
            lines: vec!["Way maker".into()],
        },
        Stanza {
            lines: vec!["Miracle worker".into()],
        },
        Stanza {
            lines: vec!["Promise keeper".into()],
        },
    ];
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    LiveController::new(plan, 320, 180, Theme::dark())
}

fn staged_body(c: &LiveController) -> Vec<String> {
    c.presenter().staged().unwrap().body.clone()
}

#[test]
fn next_advances_slide_within_a_song_before_crossing_items() {
    let mut c = song_controller();
    // Next enters the song at stanza 0.
    c.apply(&Command::Next);
    assert_eq!(c.staged_index(), Some(0));
    assert_eq!(staged_body(&c), vec!["Way maker"]);
    // Next again advances WITHIN the song, not to the scripture.
    c.apply(&Command::Next);
    assert_eq!(c.staged_index(), Some(0), "still on the song");
    assert_eq!(staged_body(&c), vec!["Miracle worker"]);
    c.apply(&Command::Next);
    assert_eq!(staged_body(&c), vec!["Promise keeper"]);
    // Song exhausted → Next crosses to the scripture (item 1).
    c.apply(&Command::Next);
    assert_eq!(c.staged_index(), Some(1), "now on the next plan item");
}

#[test]
fn previous_steps_back_within_the_song_then_crosses_at_the_last_slide() {
    let mut c = song_controller();
    for _ in 0..3 {
        c.apply(&Command::Next); // land on stanza 2 (Promise keeper)
    }
    assert_eq!(staged_body(&c), vec!["Promise keeper"]);
    c.apply(&Command::Previous);
    assert_eq!(
        staged_body(&c),
        vec!["Miracle worker"],
        "step back a stanza"
    );
    // From item 1 (scripture) going back enters the song at its LAST stanza.
    c.apply(&Command::Next); // Promise keeper
    c.apply(&Command::Next); // cross to scripture (item 1)
    assert_eq!(c.staged_index(), Some(1));
    c.apply(&Command::Previous); // back into the song
    assert_eq!(c.staged_index(), Some(0));
    assert_eq!(
        staged_body(&c),
        vec!["Promise keeper"],
        "enters at last stanza"
    );
}

#[test]
fn a_six_stanza_song_walks_end_to_end_and_go_live_commits_the_current_slide() {
    let mut plan = ServicePlan::new("Sunday");
    let s = plan.add_item(ItemKind::Song, "Hymn");
    plan.get_mut(s).unwrap().stanzas = stanzas_from_text("s1\n\ns2\n\ns3\n\ns4\n\ns5\n\ns6")
        .into_iter()
        .collect();
    let mut c = LiveController::new(plan, 320, 180, Theme::dark());
    // Walk all six with Next, then Go Live on stanza 3.
    c.apply(&Command::Next); // s1
    c.apply(&Command::Next); // s2
    c.apply(&Command::Next); // s3
    assert_eq!(staged_body(&c), vec!["s3"]);
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(c.live_index(), Some(0));
    assert_eq!(
        c.presenter().live_slide().unwrap().body,
        vec!["s3"],
        "Go Live commits the CURRENT slide, not stanza 0"
    );
    // Preview/Live isolation still holds: advancing Preview leaves Live on s3.
    c.apply(&Command::Next); // s4 in Preview
    assert_eq!(staged_body(&c), vec!["s4"]);
    assert_eq!(c.presenter().live_slide().unwrap().body, vec!["s3"]);
}

#[test]
fn the_stage_next_line_follows_the_song_sequence_not_preview() {
    // After Go Live mid-song, the confidence monitor's "next" is the song's
    // NEXT stanza even after the operator stages something else in Preview.
    let mut c = song_controller();
    c.apply(&Command::Next); // stage stanza 0
    c.apply(&Command::GoLive); // live = stanza 0
                               // The stage "next" is stanza 1 of the LIVE song.
    assert_eq!(
        c.stage_next_slide().unwrap().body,
        vec!["Miracle worker"],
        "next line = the song's next stanza"
    );
    // Stage a scripture in Preview — the song's next is UNCHANGED (the speaker
    // still needs the coming lyric, not the operator's unrelated Preview).
    c.apply(&Command::StageScripture {
        reference: "Romans 8:28".into(),
        translation: None,
    });
    assert_eq!(
        c.stage_next_slide().unwrap().body,
        vec!["Miracle worker"],
        "still the song's next stanza, not the staged scripture"
    );
    // On the LAST stanza there is no next stanza, so the stage falls back to
    // whatever Preview holds (the general, non-song case).
    c.apply(&Command::Next); // preview stanza 1
    c.apply(&Command::Next); // preview stanza 2 (last)
    c.apply(&Command::GoLive); // live = last stanza; no stanza after it
    assert_eq!(
        c.stage_next_slide(),
        c.presenter().staged().cloned(),
        "past the last stanza, next falls back to Preview"
    );
}

#[test]
fn mid_song_live_position_survives_force_kill_recovery() {
    let mut c = song_controller();
    c.apply(&Command::Next); // stanza 0
    c.apply(&Command::Next); // stanza 1
    c.apply(&Command::GoLive); // LIVE = song stanza 1
    assert_eq!(
        c.presenter().live_slide().unwrap().body,
        vec!["Miracle worker"]
    );
    let snap = c.snapshot(std::time::Instant::now());
    assert_eq!(snap.live_slide, Some(1), "snapshot records the stanza");

    // Fresh controller (as after a crash) restores from the snapshot.
    let mut restored = song_controller();
    restored.restore(&snap);
    assert_eq!(restored.live_index(), Some(0));
    assert_eq!(
        restored.presenter().live_slide().unwrap().body,
        vec!["Miracle worker"],
        "recovery lands on the SAME stanza, not stanza 0"
    );
}

#[test]
fn recovery_clamps_an_out_of_range_slide_to_a_valid_one() {
    // A snapshot whose slide index exceeds the (edited) song's stanza count must
    // fall back to slide 0, never index past the stanza list.
    let mut c = song_controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let mut snap = c.snapshot(std::time::Instant::now());
    snap.live_slide = Some(99); // pretend the song was shortened since the save
    let mut restored = song_controller();
    restored.restore(&snap);
    assert_eq!(
        restored.presenter().live_slide().unwrap().body,
        vec!["Way maker"],
        "clamped to stanza 0"
    );
}

#[test]
fn add_item_with_content_creates_a_multi_slide_song() {
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Section, "Sermon");
    let mut c = LiveController::new(plan, 320, 180, Theme::dark());
    let reply = c.apply(&Command::AddItem {
        kind: "song".into(),
        title: "New Song".into(),
        content: Some("verse one\n\nverse two".into()),
    });
    assert_eq!(reply, ControllerReply::Ack);
    // The new song is the last item; navigate to it and confirm two slides.
    let view = c.operator_view();
    let song = view.items.iter().find(|i| i.title == "New Song").unwrap();
    assert_eq!(song.slide_count, Some(2), "wire count reflects two stanzas");
}

#[test]
fn removing_a_live_song_recovers_its_lyric_body_verbatim() {
    // 8a review fix: a removed live song keeps its lyrics on screen (a free
    // slide with a body) and recovery must restore the BODY, not just the title.
    let mut c = song_controller();
    c.apply(&Command::Next); // stage stanza 0
    c.apply(&Command::Next); // stage stanza 1
    c.apply(&Command::GoLive); // LIVE = "Way Maker" / "Miracle worker"
    assert_eq!(
        c.presenter().live_slide().unwrap().body,
        vec!["Miracle worker"]
    );
    // Remove the live song — the lyric slide stays on the audience output.
    let song_id = c.operator_view().items[0].id;
    c.apply(&Command::RemoveItem { item_id: song_id });
    assert_eq!(
        c.presenter().live_slide().unwrap().body,
        vec!["Miracle worker"],
        "the removed song's lyrics stay on Live (FR-012)"
    );
    // Force-kill + recover from the snapshot on a fresh controller.
    let snap = c.snapshot(std::time::Instant::now());
    let mut restored = song_controller();
    restored.restore(&snap);
    let live = restored.presenter().live_slide().unwrap();
    assert_eq!(live.title, "Way Maker");
    assert_eq!(
        live.body,
        vec!["Miracle worker"],
        "recovery restores the lyric BODY verbatim, not a bare title"
    );
}

#[test]
fn set_theme_restyles_the_output_and_reports_it_without_losing_content() {
    // Switching to "high-contrast" yields the SAME audience output as if the
    // session had STARTED there — content untouched, only its design (FR-010).
    let (mut a, _) = controller();
    a.apply(&Command::Next); // stage item 0 (a song)
    a.apply(&Command::GoLive);

    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    let mut hc = LiveController::new(plan, 320, 180, Theme::high_contrast());
    hc.apply(&Command::Next);
    hc.apply(&Command::GoLive);

    assert_eq!(
        a.operator_view().theme,
        "classic",
        "starts on the default design"
    );
    assert_eq!(
        a.apply(&Command::SetTheme {
            name: "high-contrast".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        a.operator_view().theme,
        "high-contrast",
        "active theme reported"
    );
    assert_eq!(
        a.operator_view().themes,
        vec!["classic", "high-contrast", "lower-third"],
        "the picker's option list"
    );
    assert_eq!(
        a.presenter().live_output().bytes(),
        hc.presenter().live_output().bytes(),
        "switching == having started in that theme (content preserved)"
    );
    assert_eq!(
        a.live_index(),
        Some(0),
        "the live item is unchanged by a restyle"
    );

    // An unknown built-in name is a bad request and leaves the theme unchanged.
    assert_eq!(
        a.apply(&Command::SetTheme {
            name: "neon-disco".into()
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        a.operator_view().theme,
        "high-contrast",
        "unknown name is a no-op"
    );
}

#[test]
fn a_theme_switch_preserves_blackout() {
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    c.apply(&Command::Blackout { on: true });
    assert!(c.is_blackout());
    assert!(live_is_black(&c), "live is black before the switch");
    assert_eq!(
        c.apply(&Command::SetTheme {
            name: "lower-third".into()
        }),
        ControllerReply::Ack
    );
    assert!(c.is_blackout(), "the blackout flag survives a theme switch");
    // The RENDERED live output must still be black — set_theme re-issues SetScene
    // (which resets the engine's blackout), so the controller MUST re-apply it.
    // Asserting the flag alone would miss a dropped re-apply (review S8-3b).
    assert!(
        live_is_black(&c),
        "the audience output stays black after a mid-blackout theme switch"
    );
}

#[test]
fn the_active_theme_survives_snapshot_restore() {
    use std::time::Instant;
    let t0 = Instant::now();
    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    a.apply(&Command::SetTheme {
        name: "high-contrast".into(),
    });
    let snap = a.snapshot(t0);
    assert_eq!(
        snap.theme,
        Some("high-contrast".into()),
        "a non-default theme is persisted"
    );

    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(b.operator_view().theme, "high-contrast", "theme recovered");
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "the themed audience output re-renders identically after recovery"
    );
}

#[test]
fn a_default_theme_session_persists_the_pre_v8_shape() {
    use std::time::Instant;
    let (a, _) = controller();
    assert_eq!(
        a.snapshot(Instant::now()).theme,
        None,
        "classic => NULL theme"
    );

    let (mut b, _) = controller();
    let mut snap = b.snapshot(Instant::now());
    snap.theme = None;
    b.restore(&snap);
    assert_eq!(
        b.operator_view().theme,
        "classic",
        "absent theme => default"
    );
}

#[test]
fn set_custom_theme_applies_and_survives_recovery() {
    use std::time::Instant;
    let t0 = Instant::now();
    // A custom theme is a serialized Theme (here a tweaked built-in stands in for a
    // Theme-Designer-authored design). SetCustomTheme applies it in place.
    let json = serde_json::to_string(&Theme::high_contrast()).unwrap();
    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: json.clone()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        a.operator_view().theme,
        "custom",
        "reported as a custom theme"
    );

    // Malformed JSON is rejected and leaves the current theme unchanged.
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: "not-json".into()
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(a.operator_view().theme, "custom", "bad JSON is a no-op");

    // Persist + recover: the custom JSON round-trips and re-renders identically,
    // taking precedence over any built-in name.
    let snap = a.snapshot(t0);
    assert_eq!(
        snap.custom_theme,
        Some(json.clone()),
        "custom theme persisted"
    );
    assert_eq!(snap.theme, Some("custom".into()));
    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(b.operator_view().theme, "custom", "custom theme recovered");
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "the custom-themed audience output re-renders identically after recovery"
    );
}

#[test]
fn recovery_prefers_the_custom_theme_over_a_conflicting_built_in_name() {
    use std::time::Instant;
    let t0 = Instant::now();
    // A snapshot that carries BOTH a valid built-in NAME and a custom theme must restore
    // the operator's CUSTOM design, never the built-in. The normal path always writes
    // theme = "custom", so hand-craft the conflict the precedence branch (restore()) guards.
    // Use a custom theme (classic → navy) that visibly differs from the conflicting name
    // ("high-contrast" → black) so precedence is observable in pixels, not just a flag.
    let custom_json = serde_json::to_string(&Theme::classic()).unwrap();
    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    a.apply(&Command::SetCustomTheme {
        theme_json: custom_json.clone(),
    });

    let mut snap = a.snapshot(t0);
    snap.theme = Some("high-contrast".into()); // inject the conflicting built-in name
    assert_eq!(
        snap.custom_theme,
        Some(custom_json),
        "custom theme still persisted"
    );

    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.operator_view().theme,
        "custom",
        "custom theme must win over the conflicting built-in name"
    );
    // Pixels confirm it: the recovered output matches the CUSTOM (classic) design...
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "recovered the custom design, not the injected built-in"
    );
    // ...and is NOT the high-contrast built-in the name would have selected.
    let (mut hc, _) = controller();
    hc.apply(&Command::Next);
    hc.apply(&Command::GoLive);
    hc.apply(&Command::SetTheme {
        name: "high-contrast".into(),
    });
    hc.tick(t0);
    assert_ne!(
        b.presenter().live_output().bytes(),
        hc.presenter().live_output().bytes(),
        "the conflicting built-in name must NOT have taken precedence"
    );
}

#[test]
fn per_item_theme_override_renders_survives_a_global_switch_and_recovers() {
    use std::time::Instant;
    let t0 = Instant::now();
    // Reference: the item (ids[1], a scripture) rendered under the GLOBAL lower-third.
    let (mut d, dids) = controller();
    d.apply(&Command::SetTheme {
        name: "lower-third".into(),
    });
    d.apply(&Command::SelectItem { item_id: dids[1] });
    d.apply(&Command::GoLive);
    let live_lower_third = d.presenter().live_output().bytes().to_vec();

    // Per-item OVERRIDE: the GLOBAL stays classic, but the item overrides to lower-third.
    let (mut a, ids) = controller();
    assert_eq!(
        a.apply(&Command::SetItemTheme {
            item_id: ids[1],
            theme: Some("lower-third".into()),
        }),
        ControllerReply::Ack
    );
    // The override lives in the PLAN — it must mark the plan dirty so the desktop
    // persists it (otherwise it is silently lost on restart; the plan_repo round-trip
    // test covers the save/load itself). This is what makes recovery below real.
    assert!(
        a.take_plan_dirty(),
        "SetItemTheme must mark the plan for persistence"
    );
    a.apply(&Command::SelectItem { item_id: ids[1] });
    a.apply(&Command::GoLive);
    // The override renders the item on lower-third — identical to the global-lower-third render.
    assert_eq!(
        a.presenter().live_output().bytes(),
        live_lower_third.as_slice(),
        "the per-item override renders the item on its own template"
    );

    // A GLOBAL theme switch must NOT clobber the overridden live item (zero content loss).
    a.apply(&Command::SetTheme {
        name: "high-contrast".into(),
    });
    assert_eq!(
        a.presenter().live_output().bytes(),
        live_lower_third.as_slice(),
        "a global theme switch preserves the item's override"
    );

    // Unknown item id and unknown built-in name are rejected.
    assert_eq!(
        a.apply(&Command::SetItemTheme {
            item_id: 9999,
            theme: Some("classic".into())
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        a.apply(&Command::SetItemTheme {
            item_id: ids[0],
            theme: Some("not-a-theme".into())
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );

    // Recovery: the override survives snapshot→restore (the plan carries it, as the
    // desktop reloads it from plan_repo — simulated here by re-applying it to b's plan).
    let snap = a.snapshot(t0);
    let (mut b, bids) = controller();
    b.apply(&Command::SetItemTheme {
        item_id: bids[1],
        theme: Some("lower-third".into()),
    });
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "recovery restores the item's override on the live output"
    );
}

// --- Saved-theme library (86ajq4xmy) ---------------------------------------

#[test]
fn save_theme_stores_the_canonical_theme_and_marks_dirty() {
    use selahcue_app::MAX_THEME_NAME_LEN;
    let (mut c, _) = controller();
    assert!(!c.take_saved_themes_dirty(), "clean at start");

    // A saved theme is a serialized Theme (a built-in stands in for a designed one).
    let json = serde_json::to_string(&Theme::high_contrast()).unwrap();
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "  Sermon Bold  ".into(), // untrimmed on the wire
            theme_json: json.clone(),
        }),
        ControllerReply::Ack
    );
    assert!(
        c.take_saved_themes_dirty(),
        "a save marks the library dirty"
    );
    assert!(
        !c.take_saved_themes_dirty(),
        "the dirty flag clears on read (one persist per change)"
    );

    // Stored under the TRIMMED name, as the CANONICAL re-serialized form.
    let canonical = serde_json::to_string(&Theme::high_contrast()).unwrap();
    assert_eq!(c.saved_themes().get("Sermon Bold"), Some(&canonical));
    assert_eq!(c.saved_themes().len(), 1);

    // The operator view reports the library so the Theme Designer can list + load it.
    let view = c.operator_view();
    assert_eq!(view.saved_themes.len(), 1);
    assert_eq!(view.saved_themes[0].name, "Sermon Bold");
    assert_eq!(view.saved_themes[0].theme_json, canonical);
    // The Theme Designer reads `view.saved_themes[i].name / .theme_json` — so the JSON
    // Tauri hands the webview MUST be objects, not `[[name, json]]` tuples. Pin the shape.
    let serialized = serde_json::to_value(&view).unwrap();
    assert_eq!(
        serialized["saved_themes"][0]["name"],
        serde_json::json!("Sermon Bold"),
        "saved_themes must serialize as {{name, theme_json}} objects for the webview"
    );
    assert_eq!(
        serialized["saved_themes"][0]["theme_json"],
        serde_json::json!(canonical)
    );

    // Invalid JSON and an empty / over-long name are rejected without dirtying.
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "bad".into(),
            theme_json: "not-json".into(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "   ".into(),
            theme_json: json.clone(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "n".repeat(MAX_THEME_NAME_LEN + 1),
            theme_json: json.clone(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    // A BUILT-IN name is reserved (86ajq69ft) — a saved theme named like a built-in would
    // be shadowed (built-ins resolve first) and unreachable by name per-item/per-screen.
    for builtin in ["classic", "high-contrast", "lower-third"] {
        assert_eq!(
            c.apply(&Command::SaveTheme {
                name: builtin.into(),
                theme_json: json.clone(),
            }),
            ControllerReply::Deny(DenyReason::BadRequest),
            "saving under the built-in name {builtin:?} is rejected"
        );
    }
    assert!(
        !c.take_saved_themes_dirty(),
        "rejected saves never mark dirty"
    );
    assert_eq!(c.saved_themes().len(), 1, "library unchanged by rejects");
}

#[test]
fn save_theme_overwrites_by_name_then_delete_removes() {
    let (mut c, _) = controller();
    let classic = serde_json::to_string(&Theme::classic()).unwrap();
    let contrast = serde_json::to_string(&Theme::high_contrast()).unwrap();

    c.apply(&Command::SaveTheme {
        name: "Look".into(),
        theme_json: classic.clone(),
    });
    // Overwriting the same name replaces its JSON (rename/duplicate build on this).
    c.apply(&Command::SaveTheme {
        name: "Look".into(),
        theme_json: contrast.clone(),
    });
    assert_eq!(c.saved_themes().len(), 1, "overwrite, not a second entry");
    assert_eq!(c.saved_themes().get("Look"), Some(&contrast));

    // Delete removes it and marks dirty; deleting an absent name is a no-op Ack.
    let _ = c.take_saved_themes_dirty();
    assert_eq!(
        c.apply(&Command::DeleteTheme {
            name: "Look".into()
        }),
        ControllerReply::Ack
    );
    assert!(
        c.take_saved_themes_dirty(),
        "a delete marks the library dirty"
    );
    assert!(c.saved_themes().is_empty());
    assert_eq!(
        c.apply(&Command::DeleteTheme {
            name: "ghost".into()
        }),
        ControllerReply::Ack
    );
    assert!(
        !c.take_saved_themes_dirty(),
        "deleting an absent name never dirties"
    );
}

#[test]
fn saved_theme_library_is_bounded_and_load_drops_bad_entries() {
    use selahcue_app::{MAX_SAVED_THEMES, MAX_THEME_NAME_LEN};
    let (mut c, _) = controller();
    let json = serde_json::to_string(&Theme::classic()).unwrap();

    // Fill to the cap; the next NEW name is rejected, an overwrite still succeeds.
    for i in 0..MAX_SAVED_THEMES {
        assert_eq!(
            c.apply(&Command::SaveTheme {
                name: format!("t{i}"),
                theme_json: json.clone(),
            }),
            ControllerReply::Ack
        );
    }
    assert_eq!(c.saved_themes().len(), MAX_SAVED_THEMES);
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "one-too-many".into(),
            theme_json: json.clone(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "a new name past the cap is rejected (bounded memory)"
    );
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "t0".into(),
            theme_json: json.clone(),
        }),
        ControllerReply::Ack,
        "overwriting an existing name at the cap is allowed"
    );

    // load_saved_themes: startup filters invalid JSON / bad names and honours the cap
    // without dirtying (a corrupt store can never exceed the bound or crash).
    let mut incoming: Vec<(String, String)> = (0..MAX_SAVED_THEMES + 10)
        .map(|i| (format!("k{i}"), json.clone()))
        .collect();
    incoming.push(("bad-json".into(), "{not a theme}".into()));
    incoming.push((" ".into(), json.clone()));
    incoming.push(("n".repeat(MAX_THEME_NAME_LEN + 1), json.clone()));
    // Valid JSON + valid name but an OVER-CAP element list (a tampered / version-skewed
    // store row) — the one theme-with-elements ingress the write paths don't guard. It
    // must be dropped defensively so an unbounded element Vec never reaches compose.
    let mut over_cap = Theme::classic();
    for _ in 0..=MAX_ELEMENTS {
        over_cap.elements.push(Element::Shape {
            x_permille: 0,
            y_permille: 0,
            w_permille: 10,
            h_permille: 10,
            fill: Rgba::WHITE,
            border: Rgba::new(0, 0, 0, 0),
            border_permille: 0,
            opacity: 255,
            z: 0,
            variant: ShapeKind::Rect,
            corner_permille: 0,
        });
    }
    assert!(over_cap.elements.len() > MAX_ELEMENTS);
    incoming.push((
        "elements-over-cap".into(),
        serde_json::to_string(&over_cap).unwrap(),
    ));
    c.load_saved_themes(incoming);
    assert!(
        c.saved_themes().len() <= MAX_SAVED_THEMES,
        "load honours the cap"
    );
    assert!(
        c.saved_themes().keys().all(|k| k.starts_with('k')),
        "invalid entries dropped on load (bad name/JSON AND over-cap elements)"
    );
    assert!(
        !c.saved_themes().contains_key("elements-over-cap"),
        "an over-cap element list is dropped at load (bounded before compose)"
    );
    assert!(
        !c.take_saved_themes_dirty(),
        "loading from the store is not a change to persist"
    );
}

// --- Per-screen theme map (86ajq321k) --------------------------------------

/// Put a live scripture on the audience output so per-screen composition has content.
fn controller_live() -> LiveController {
    let (mut c, _) = controller();
    c.apply(&Command::Next); // stage the first item
    c.apply(&Command::GoLive);
    c
}

#[test]
fn set_screen_theme_validates_maps_and_recomposes_main() {
    let mut c = controller_live();
    assert!(!c.take_screen_themes_dirty(), "clean at start");

    // A per-screen theme for the physical `main` recomposes the live output + marks dirty.
    let main_before = c.presenter().live_output().bytes().to_vec();
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "main".into(),
            name: "high-contrast".into(),
        }),
        ControllerReply::Ack
    );
    assert!(c.take_screen_themes_dirty(), "a set marks the map dirty");
    assert_ne!(
        c.presenter().live_output().bytes(),
        main_before.as_slice(),
        "main's per-screen theme restyled the physical live output"
    );
    assert_eq!(
        c.screen_themes().get("main").map(String::as_str),
        Some("high-contrast")
    );

    // A secondary screen (no physical output) is stored without touching main's output.
    let main_after = c.presenter().live_output().bytes().to_vec();
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "lower-third".into(),
            name: "lower-third".into(),
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.presenter().live_output().bytes(),
        main_after.as_slice(),
        "a secondary screen's theme never touches the main output"
    );

    // The operator view reports the per-screen map so the Screens page can reflect it.
    let view = c.operator_view();
    assert_eq!(view.screen_themes.len(), 2);
    assert!(view
        .screen_themes
        .iter()
        .any(|s| s.screen == "main" && s.theme == "high-contrast"));

    // Unknown screen id and unknown theme name are rejected.
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "disco".into(),
            name: "classic".into(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "stream".into(),
            name: "no-such-theme".into(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    // A SAVED-library name IS assignable per-screen (86ajq69ft) — the cached theme is
    // kept fresh by resync_theme_overrides when the library changes (covered separately).
    let saved_json = serde_json::to_string(&Theme::high_contrast()).unwrap();
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "MyCustom".into(),
            theme_json: saved_json,
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "stream".into(),
            name: "MyCustom".into(),
        }),
        ControllerReply::Ack,
        "a saved-library theme is assignable per-screen"
    );
    assert_eq!(
        c.screen_themes().get("stream").map(String::as_str),
        Some("MyCustom")
    );
}

#[test]
fn compose_screen_renders_each_audience_screen_under_its_own_theme() {
    let mut c = controller_live();
    c.apply(&Command::SetScreenTheme {
        screen: "lower-third".into(),
        name: "lower-third".into(),
    });
    c.apply(&Command::SetScreenTheme {
        screen: "stream".into(),
        name: "high-contrast".into(),
    });

    let main = c.compose_screen("main").expect("main composes");
    let lower = c
        .compose_screen("lower-third")
        .expect("lower-third composes");
    let stream = c.compose_screen("stream").expect("stream composes");

    // main mirrors the physical live output; the three screens are three designs at once.
    assert_eq!(main.bytes(), c.presenter().live_output().bytes());
    assert_ne!(main.bytes(), lower.bytes(), "main ≠ lower-third");
    assert_ne!(lower.bytes(), stream.bytes(), "lower-third ≠ stream");

    // Isolation: changing `stream` leaves `main` + `lower-third` untouched.
    let main_b = main.bytes().to_vec();
    let lower_b = lower.bytes().to_vec();
    c.apply(&Command::SetScreenTheme {
        screen: "stream".into(),
        name: "classic".into(),
    });
    assert_eq!(c.compose_screen("main").unwrap().bytes(), main_b.as_slice());
    assert_eq!(
        c.compose_screen("lower-third").unwrap().bytes(),
        lower_b.as_slice()
    );

    // An unknown screen id has no composition.
    assert!(c.compose_screen("disco").is_none());

    // Clearing a screen (empty name) drops it back to the global.
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "lower-third".into(),
            name: String::new(),
        }),
        ControllerReply::Ack
    );
    assert!(c.screen_themes().get("lower-third").is_none());
    assert_eq!(
        c.compose_screen("lower-third").unwrap().bytes(),
        c.compose_screen("main").unwrap().bytes(),
        "a cleared screen follows the global (same as main)"
    );
}

#[test]
fn per_screen_theme_map_is_bounded_and_load_restores_main_dropping_stale() {
    let mut c = controller_live();
    // Only known screens are accepted, so the map is bounded to AUDIENCE_SCREENS.
    for s in selahcue_app::AUDIENCE_SCREENS {
        c.apply(&Command::SetScreenTheme {
            screen: s.into(),
            name: "classic".into(),
        });
    }
    assert_eq!(
        c.screen_themes().len(),
        selahcue_app::AUDIENCE_SCREENS.len()
    );

    // load_screen_themes (startup / recovery): keeps known+resolvable, drops the rest,
    // applies `main` to the physical output, and does not dirty.
    let mut d = controller_live();
    let main_before = d.presenter().live_output().bytes().to_vec();
    d.load_screen_themes([
        ("main".to_string(), "high-contrast".to_string()),
        ("stream".to_string(), "classic".to_string()),
        ("bogus-screen".to_string(), "classic".to_string()), // unknown screen → dropped
        ("lower-third".to_string(), "no-such-theme".to_string()), // stale name → dropped
    ]);
    assert_eq!(
        d.screen_themes().len(),
        2,
        "unknown screen + stale name dropped"
    );
    assert!(
        !d.take_screen_themes_dirty(),
        "load is not a change to persist"
    );
    assert_ne!(
        d.presenter().live_output().bytes(),
        main_before.as_slice(),
        "load restored main's per-screen theme onto the physical output"
    );
}

// --- Saved themes usable per-item + per-screen (86ajq69ft) ------------------

fn has_pixel(c: &LiveController, rgb: (u8, u8, u8)) -> bool {
    c.presenter()
        .live_output()
        .bytes()
        .chunks_exact(4)
        .any(|px| {
            let d = |a: u8, b: u8| (a as i32 - b as i32).pow(2);
            d(px[0], rgb.0) + d(px[1], rgb.1) + d(px[2], rgb.2) < 900
        })
}

#[test]
fn a_saved_theme_is_assignable_per_item_and_per_screen() {
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive); // item 0 live

    // Save a custom theme (high-contrast, black bg, stands in for a designed one).
    let hc = serde_json::to_string(&Theme::high_contrast()).unwrap();
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "Branded".into(),
            theme_json: hc,
        }),
        ControllerReply::Ack
    );

    // Assign it to the LIVE plan item — the physical live output restyles to it (black).
    let before = c.presenter().live_output().bytes().to_vec();
    assert_eq!(
        c.apply(&Command::SetItemTheme {
            item_id: ids[0],
            theme: Some("Branded".into()),
        }),
        ControllerReply::Ack
    );
    assert_ne!(
        c.presenter().live_output().bytes(),
        before.as_slice(),
        "a saved theme applied per-item restyles the live output"
    );
    assert!(
        has_pixel(&c, (0, 0, 0)),
        "the saved high-contrast (black) design renders"
    );

    // Assign a saved theme to the `main` screen too.
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "main".into(),
            name: "Branded".into(),
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.screen_themes().get("main").map(String::as_str),
        Some("Branded")
    );

    // A truly-unknown name is still rejected on both paths.
    assert_eq!(
        c.apply(&Command::SetItemTheme {
            item_id: ids[0],
            theme: Some("no-such".into()),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "stream".into(),
            name: "no-such".into(),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn editing_a_saved_theme_re_renders_every_place_it_is_used() {
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive); // item 0 live

    // Save v1 = classic (navy), assign to the live item + the main screen.
    let v1 = serde_json::to_string(&Theme::classic()).unwrap();
    c.apply(&Command::SaveTheme {
        name: "Look".into(),
        theme_json: v1,
    });
    c.apply(&Command::SetItemTheme {
        item_id: ids[0],
        theme: Some("Look".into()),
    });
    assert!(
        has_pixel(&c, (8, 10, 20)),
        "classic navy renders before the edit"
    );
    let before = c.presenter().live_output().bytes().to_vec();

    // EDIT: save v2 = high-contrast (black) under the SAME name → the LIVE output updates
    // WITHOUT re-assigning (the cached theme is re-synced, no stale frame).
    let v2 = serde_json::to_string(&Theme::high_contrast()).unwrap();
    assert_eq!(
        c.apply(&Command::SaveTheme {
            name: "Look".into(),
            theme_json: v2,
        }),
        ControllerReply::Ack
    );
    assert_ne!(
        c.presenter().live_output().bytes(),
        before.as_slice(),
        "editing the saved theme re-rendered the live item in place"
    );
    assert!(
        has_pixel(&c, (0, 0, 0)),
        "the live item now shows the edited (black) design"
    );
    // Content preserved (zero content loss).
    assert_eq!(c.plan().items()[0].theme.as_deref(), Some("Look"));
}

#[test]
fn deleting_a_saved_theme_drops_references_and_falls_back_to_global() {
    let (mut c, ids) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive); // item 0 live (global theme = dark)

    let hc = serde_json::to_string(&Theme::high_contrast()).unwrap();
    c.apply(&Command::SaveTheme {
        name: "Temp".into(),
        theme_json: hc,
    });
    c.apply(&Command::SetItemTheme {
        item_id: ids[0],
        theme: Some("Temp".into()),
    });
    c.apply(&Command::SetScreenTheme {
        screen: "main".into(),
        name: "Temp".into(),
    });
    assert!(has_pixel(&c, (0, 0, 0)), "the saved (black) theme is live");

    // DELETE the theme → both references drop, the outputs fall back to the GLOBAL theme
    // with NO stale frame (the black design is gone).
    let _ = c.take_plan_dirty();
    let _ = c.take_screen_themes_dirty();
    assert_eq!(
        c.apply(&Command::DeleteTheme {
            name: "Temp".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.plan().items()[0].theme,
        None,
        "the plan item's dangling theme reference is dropped"
    );
    assert!(
        c.screen_themes().get("main").is_none(),
        "the per-screen dangling reference is dropped"
    );
    assert!(
        c.take_plan_dirty() && c.take_screen_themes_dirty(),
        "dropping references marks the plan + screen map dirty to persist"
    );
    // The live output is no longer the deleted black design — it fell back to the global.
    let (mut ref_c, ref_ids) = controller();
    ref_c.apply(&Command::Next);
    ref_c.apply(&Command::GoLive);
    let _ = ref_ids;
    assert_eq!(
        c.presenter().live_output().bytes(),
        ref_c.presenter().live_output().bytes(),
        "after delete the live item renders exactly the global theme (no override, no stale frame)"
    );
}

#[test]
fn a_saved_per_item_theme_resolves_on_recovery_only_with_the_correct_load_order() {
    use selahcue_core::plan::ItemKind;
    use std::time::Instant;
    let t0 = Instant::now();
    let canonical = serde_json::to_string(&Theme::high_contrast()).unwrap();

    // A controller whose PLAN already carries a per-item SAVED-theme override on item 0
    // (as the desktop's plan_repo would restore it) — built directly so the seed does not
    // depend on the library being loaded (SetItemTheme would reject "Brand" while empty).
    let make = || {
        let mut plan = ServicePlan::new("Sunday");
        let a = plan.add_item(ItemKind::Song, "Opening Song");
        plan.add_item(ItemKind::Scripture, "Romans 8:28");
        plan.add_item(ItemKind::Section, "Sermon");
        plan.set_item_theme(a, Some("Brand".into())).unwrap();
        LiveController::new(plan, 320, 180, Theme::dark())
    };

    // Establish the reference live output: library loaded, item 0 live under "Brand".
    let mut a = make();
    a.load_saved_themes([("Brand".to_string(), canonical.clone())]);
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    let live = a.presenter().live_output().bytes().to_vec();
    let snap = a.snapshot(t0);

    // CORRECT order (mirrors the desktop): load the library FIRST, then restore. The
    // per-item saved theme resolves and the recovered live output matches.
    let mut good = make();
    good.load_saved_themes([("Brand".to_string(), canonical.clone())]);
    good.restore(&snap);
    good.tick(t0);
    assert_eq!(
        good.presenter().live_output().bytes(),
        live.as_slice(),
        "a per-item saved theme resolves on recovery when the library loads before restore"
    );

    // WRONG order (restore before the library loads) resolves "Brand" against an empty
    // library and falls back to the global — demonstrating why the order matters.
    let mut bad = make();
    bad.restore(&snap); // library not loaded yet
    bad.load_saved_themes([("Brand".to_string(), canonical)]);
    bad.tick(t0);
    assert_ne!(
        bad.presenter().live_output().bytes(),
        live.as_slice(),
        "restoring before the library loads loses the per-item saved theme (order matters)"
    );
}

// --- Layered elements: apply + recover + bounded (Canvas Editing, 86ajq6j2q) ---

#[test]
fn a_custom_theme_with_elements_applies_recovers_and_is_bounded() {
    use std::time::Instant;
    let t0 = Instant::now();
    let shape = |z: i16| Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        fill: Rgba::rgb(220, 20, 20),
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 255,
        z,
        variant: ShapeKind::Rect,
        corner_permille: 0,
    };
    // A custom theme with a full-frame opaque red shape IN FRONT (z=1).
    let mut theme = Theme::high_contrast();
    theme.elements.push(shape(1));
    let json = serde_json::to_string(&theme).unwrap();

    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: json.clone()
        }),
        ControllerReply::Ack
    );
    let is_red = |c: &LiveController| {
        c.presenter()
            .live_output()
            .bytes()
            .chunks_exact(4)
            .any(|p| p[0] > 200 && p[1] < 60 && p[2] < 60)
    };
    assert!(
        is_red(&a),
        "the custom theme's front element renders on the live output"
    );

    // Persist + recover: the element survives (recovered live output is identical).
    let snap = a.snapshot(t0);
    let live = a.presenter().live_output().bytes().to_vec();
    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.presenter().live_output().bytes(),
        live.as_slice(),
        "a custom theme + its elements recover after a restart"
    );

    // Over-cap: a theme with more than MAX_ELEMENTS elements is rejected (no-leak).
    let mut huge = Theme::classic();
    for _ in 0..=MAX_ELEMENTS {
        huge.elements.push(shape(0));
    }
    assert!(huge.elements.len() > MAX_ELEMENTS);
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::SetCustomTheme {
            theme_json: serde_json::to_string(&huge).unwrap()
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "an over-cap element list is rejected"
    );
}

#[test]
fn a_custom_theme_with_an_ellipse_element_applies_and_recovers() {
    use std::time::Instant;
    let t0 = Instant::now();
    // A full-frame red ELLIPSE in front of the text (86ajtwq24). It routes through the new
    // Layer::Shape path; the live output must show the fill AND leave the corners as the
    // theme background (proving it is an ellipse, not a rect), and recover byte-identically.
    let ellipse = Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        fill: Rgba::rgb(220, 20, 20),
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 255,
        z: 1,
        variant: ShapeKind::Ellipse,
        corner_permille: 0,
    };
    let mut theme = Theme::classic(); // dark background
    theme.elements.push(ellipse);
    let json = serde_json::to_string(&theme).unwrap();
    assert!(
        json.contains("\"variant\":\"ellipse\""),
        "the ellipse variant persists: {json}"
    );

    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: json.clone()
        }),
        ControllerReply::Ack
    );
    let out = a.presenter().live_output();
    let (w, h) = (out.width(), out.height());
    assert!(
        out.bytes()
            .chunks_exact(4)
            .any(|p| p[0] > 200 && p[1] < 60 && p[2] < 60),
        "the ellipse fill renders on the live output"
    );
    // The top-left CORNER is outside the inscribed ellipse → the dark background, not red.
    let corner = out.pixel(1, 1).unwrap();
    assert!(
        corner.r < 80,
        "the ellipse leaves the frame corner as the dark background, got {corner:?} ({w}x{h})"
    );

    // Persist + recover: the ellipse survives a restart (recovered output is identical).
    let snap = a.snapshot(t0);
    let live = a.presenter().live_output().bytes().to_vec();
    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.presenter().live_output().bytes(),
        live.as_slice(),
        "a custom theme + its ellipse element recover after a restart"
    );
}

#[test]
fn a_custom_theme_with_an_image_element_applies_recovers_and_is_bounded() {
    use std::time::Instant;
    let t0 = Instant::now();
    // An image element pointing at a MISSING file → the engine draws the non-black
    // missing-media placeholder (FR-070). This exercises the full controller path (the
    // image element rides the theme JSON → compose → Layer::Image → engine) without
    // needing to encode a PNG here; the successful-image render is covered in test_compose.
    let image = |z: i16| Element::Image {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        source: MediaRef::new("/no/such/controller/image.png").unwrap(),
        opacity: 255,
        z,
    };
    let mut theme = Theme::high_contrast();
    theme.elements.push(image(1)); // in front of the text
    let json = serde_json::to_string(&theme).unwrap();
    assert!(
        json.contains("\"kind\":\"image\""),
        "the image element rides the theme JSON"
    );

    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: json.clone()
        }),
        ControllerReply::Ack
    );
    // The placeholder (base 64,54,74 — clearly not black) reaches the live output.
    let has_placeholder = |c: &LiveController| {
        c.presenter()
            .live_output()
            .bytes()
            .chunks_exact(4)
            .any(|p| p[0] == 64 && p[1] == 54 && p[2] == 74)
    };
    assert!(
        has_placeholder(&a),
        "a missing image element renders the non-black placeholder on the live output"
    );

    // Persist + recover: the image element survives (recovered live output is identical).
    let snap = a.snapshot(t0);
    let live = a.presenter().live_output().bytes().to_vec();
    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.presenter().live_output().bytes(),
        live.as_slice(),
        "a custom theme + its image element recover after a restart"
    );

    // Over-cap: image elements count toward MAX_ELEMENTS (no-leak).
    let mut huge = Theme::classic();
    for _ in 0..=MAX_ELEMENTS {
        huge.elements.push(image(0));
    }
    assert!(huge.elements.len() > MAX_ELEMENTS);
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::SetCustomTheme {
            theme_json: serde_json::to_string(&huge).unwrap()
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "an over-cap image element list is rejected"
    );
}

// --- Remote console thumbnails: the host serves its true Preview/Live pixels (86ajtwq28) ---

#[test]
fn get_console_thumbnails_returns_bounded_frames_and_is_read_only() {
    // A remote operator fetches the host's Preview + Live output as thumbnails so its console
    // monitors show the TRUE composited pixels. It MUST be a read — the audience (live) output
    // pixels and the operator view are byte-identical before/after.
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    let live_before = c.presenter().live_output().bytes().to_vec();
    let view_before = c.operator_view();

    let reply = c.apply(&Command::GetConsoleThumbnails {
        max_w: 160,
        max_h: 90,
    });
    match reply {
        ControllerReply::Message(ServerMessage::ConsoleThumbnails { preview, live }) => {
            let pv = preview.expect("a preview thumbnail");
            let lv = live.expect("a live thumbnail");
            assert!(
                pv.w <= 160 && pv.h <= 90 && !pv.rgba.is_empty(),
                "preview within the bound + non-empty: {}x{}",
                pv.w,
                pv.h
            );
            assert!(
                lv.w <= 160 && lv.h <= 90 && !lv.rgba.is_empty(),
                "live within the bound + non-empty: {}x{}",
                lv.w,
                lv.h
            );
        }
        other => panic!("expected ConsoleThumbnails, got {other:?}"),
    }
    // Read-only: fetching the thumbnails changed NEITHER the on-air output NOR the view.
    assert_eq!(
        c.presenter().live_output().bytes(),
        live_before.as_slice(),
        "GetConsoleThumbnails must not change the on-air (live) output"
    );
    assert_eq!(
        c.operator_view(),
        view_before,
        "GetConsoleThumbnails must not change the operator view"
    );
}

// --- Live transcript + scripture detection (R3/R4; ADR-0010) ---------------------

#[test]
fn ingesting_transcript_streams_segments_and_detects_scripture() {
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::IngestTranscript {
            text: "please turn with me to John chapter 3 verse 16".into(),
            start_ms: Some(0),
            end_ms: Some(2_500),
        }),
        ControllerReply::Ack
    );
    let view = c.operator_view();
    assert_eq!(view.transcript.len(), 1, "the utterance is transcribed");
    assert_eq!(
        view.transcript[0].text,
        "please turn with me to John chapter 3 verse 16"
    );
    assert_eq!(view.detections.len(), 1, "the spoken reference is detected");
    assert_eq!(view.detections[0].reference, "John 3:16");
    assert!(
        view.detections[0]
            .text
            .to_lowercase()
            .contains("god so loved"),
        "the detection carries the verse text to stage: {:?}",
        view.detections[0].text
    );
}

#[test]
fn approving_a_detection_stages_the_verse_in_preview_not_live() {
    let (mut c, _) = controller();
    c.apply(&Command::IngestTranscript {
        text: "first Corinthians 13".into(),
        start_ms: None,
        end_ms: None,
    });
    let id = c.operator_view().detections[0].id;
    assert_eq!(
        c.apply(&Command::ApproveDetection { detection_id: id }),
        ControllerReply::Ack
    );
    let view = c.operator_view();
    assert_eq!(
        view.staged_scripture.as_deref(),
        Some("1 Corinthians 13"),
        "approve stages the verse in Preview"
    );
    assert!(
        view.detections.is_empty(),
        "the approved detection leaves the queue"
    );
    assert_eq!(c.live_index(), None, "approve never pushes Live (FR-115)");
    assert!(
        live_is_black(&c),
        "the audience output is untouched by an approval"
    );
    // A stale/second approve of the same id is a bad request.
    assert_eq!(
        c.apply(&Command::ApproveDetection { detection_id: id }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn dismissing_a_detection_removes_it_without_staging() {
    let (mut c, _) = controller();
    c.apply(&Command::IngestTranscript {
        text: "Romans eight twenty eight".into(),
        start_ms: None,
        end_ms: None,
    });
    let id = c.operator_view().detections[0].id;
    assert_eq!(
        c.apply(&Command::DismissDetection { detection_id: id }),
        ControllerReply::Ack
    );
    let view = c.operator_view();
    assert!(view.detections.is_empty());
    assert_eq!(view.staged_scripture, None, "dismiss stages nothing");
    assert_eq!(
        c.apply(&Command::DismissDetection { detection_id: id }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "dismissing an unknown id is a bad request"
    );
}

#[test]
fn transcription_never_blanks_the_live_output() {
    // The AI-assist invariant (FR-083/NFR-024): ingesting transcript — even a flood —
    // must never disturb what is on the audience output.
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    assert_eq!(c.live_index(), Some(0));
    assert!(!live_is_black(&c), "content is live");
    let live_before = c.presenter().live_output().bytes().to_vec();
    for i in 0..500 {
        c.apply(&Command::IngestTranscript {
            text: format!(
                "word {i} and Psalm {} verse {}",
                (i % 150) + 1,
                (i % 20) + 1
            ),
            start_ms: Some(i),
            end_ms: Some(i + 1),
        });
    }
    assert_eq!(
        c.live_index(),
        Some(0),
        "Live item unchanged by transcription"
    );
    assert_eq!(
        c.presenter().live_output().bytes(),
        live_before.as_slice(),
        "the audience pixels are byte-identical — AI never touches Live"
    );
    // Bounded (no-leak): the flood cannot grow the operator view without limit.
    let view = c.operator_view();
    assert!(
        view.transcript.len() <= 60,
        "transcript view is a bounded tail"
    );
    assert!(view.detections.len() <= 32, "detection queue is bounded");
}

// --- Scripture live-follow: verses follow Live only when a scripture is already live (86ajtwq2b) ---

#[test]
fn follow_scripture_advances_both_preview_and_live_when_a_scripture_is_live() {
    let (mut c, _) = controller();
    // Put a scripture live: stage John 3:16 then Go Live.
    c.apply(&Command::StageScripture {
        reference: "John 3:16".into(),
        translation: None,
    });
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(
        c.operator_view().live_scripture.as_deref(),
        Some("John 3:16")
    );

    // Now FOLLOW to the next verse — both Preview AND Live advance to it.
    assert_eq!(
        c.apply(&Command::FollowScripture {
            reference: "John 3:17".into(),
            translation: None,
        }),
        ControllerReply::Ack
    );
    let v = c.operator_view();
    assert_eq!(
        v.staged_scripture.as_deref(),
        Some("John 3:17"),
        "Preview follows"
    );
    assert_eq!(
        v.live_scripture.as_deref(),
        Some("John 3:17"),
        "Live follows (already live)"
    );
    assert!(!live_is_black(&c), "the live verse is showing");
}

#[test]
fn follow_scripture_stages_preview_only_when_nothing_is_live() {
    // preview⟂live isolation: with nothing on air, follow behaves like StageScripture.
    let (mut c, _) = controller();
    assert!(live_is_black(&c), "nothing live");
    assert_eq!(
        c.apply(&Command::FollowScripture {
            reference: "John 3:16".into(),
            translation: None,
        }),
        ControllerReply::Ack
    );
    let v = c.operator_view();
    assert_eq!(
        v.staged_scripture.as_deref(),
        Some("John 3:16"),
        "Preview staged"
    );
    assert_eq!(v.live_scripture, None, "Live NOT promoted");
    assert!(live_is_black(&c), "the audience output stays idle");
}

#[test]
fn follow_scripture_never_disturbs_non_scripture_live_content() {
    // A plan item is live; following a verse must NOT change the audience output.
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(c.live_index(), Some(0), "a plan item is live");
    assert!(!live_is_black(&c));
    let live_before = c.presenter().live_output().bytes().to_vec();

    assert_eq!(
        c.apply(&Command::FollowScripture {
            reference: "John 3:16".into(),
            translation: None,
        }),
        ControllerReply::Ack
    );
    let v = c.operator_view();
    assert_eq!(
        v.staged_scripture.as_deref(),
        Some("John 3:16"),
        "Preview staged the verse"
    );
    assert_eq!(c.live_index(), Some(0), "the live plan item is unchanged");
    assert_eq!(v.live_scripture, None, "no scripture is claimed live");
    assert_eq!(
        c.presenter().live_output().bytes(),
        live_before.as_slice(),
        "the audience pixels are byte-identical — follow never touched non-scripture Live"
    );
}

#[test]
fn follow_scripture_preserves_blackout() {
    // Following updates the live CONTENT, not the blackout state.
    let (mut c, _) = controller();
    c.apply(&Command::StageScripture {
        reference: "John 3:16".into(),
        translation: None,
    });
    c.apply(&Command::GoLive);
    c.apply(&Command::Blackout { on: true });
    assert!(c.is_blackout() && live_is_black(&c), "blacked out");

    assert_eq!(
        c.apply(&Command::FollowScripture {
            reference: "John 3:17".into(),
            translation: None,
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.operator_view().live_scripture.as_deref(),
        Some("John 3:17"),
        "live content followed"
    );
    assert!(c.is_blackout(), "blackout flag preserved");
    assert!(
        live_is_black(&c),
        "the output stays dark — follow did not reveal"
    );
}

#[test]
fn follow_scripture_rejects_an_unknown_translation() {
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::FollowScripture {
            reference: "John 3:16".into(),
            translation: Some("ZZ".into()),
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

// --- AUDIT: scripture → output latency (host-side compose + render) ---

#[test]
fn scripture_stage_to_live_latency_is_measured() {
    use std::time::{Duration, Instant};
    // Measure at the REAL audience resolution (1920x1080) — compose + raster::render scale with
    // pixel count, so the test helper's 320x180 would under-report the on-air latency.
    let mut plan = ServicePlan::new("Service");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    let mut c = LiveController::new(plan, 1920, 1080, Theme::dark());
    let refs = [
        "John 3:16",
        "Romans 8:28",
        "Psalm 23:1",
        "Genesis 1:1",
        "Isaiah 40:31",
    ];
    for r in &refs {
        c.apply(&Command::StageScripture {
            reference: (*r).into(),
            translation: None,
        });
        c.apply(&Command::GoLive); // warm-up (glyph cache, buffers) -> time steady state
    }
    let mut durs: Vec<Duration> = Vec::new();
    for i in 0..25usize {
        let r = refs[i % refs.len()];
        let t0 = Instant::now();
        c.apply(&Command::StageScripture {
            reference: r.into(),
            translation: None,
        });
        c.apply(&Command::GoLive);
        let _ = c.presenter().live_output().bytes().len(); // force the frame to materialize
        durs.push(t0.elapsed());
    }
    durs.sort();
    let median = durs[durs.len() / 2];
    let p90 = durs[(durs.len() * 9) / 10];
    let max = *durs.last().unwrap();
    println!(
        "[AUDIT] scripture stage->live compose+render @1920x1080: median={median:?} p90={p90:?} max={max:?} (n=25)"
    );
    // Profile-scaled ceiling (matches the `test_present` slide-trigger convention): this path
    // does TWO full 1080p compose+renders per sample (stage->preview, then go-live->live), so
    // its release NFR is ~2x the single-slide 150ms trigger budget. On an UNOPTIMIZED debug
    // build running on oversubscribed CI shared runners the raster is several-fold slower
    // (observed: ~247ms median / ~570ms max on GitHub ubuntu vs ~118ms locally) — enforcing the
    // release number there would measure the runner, not the product. Debug keeps a generous
    // tripwire so a catastrophic regression still fails everywhere; release enforces the real
    // budget. The actual median is printed above (that is the audit's measurement).
    let ceiling = if cfg!(debug_assertions) {
        Duration::from_millis(2000)
    } else {
        Duration::from_millis(300)
    };
    assert!(
        median < ceiling,
        "stage->live median {median:?} exceeds the {ceiling:?} sanity ceiling"
    );
}

#[test]
fn plan_is_bounded_under_add_item_flood() {
    // Audit M2: a remote AddItem loop must not grow the plan without bound. Flood well past
    // the cap; the plan must never exceed MAX_PLAN_ITEMS and every add past it is denied.
    use selahcue_core::plan::MAX_PLAN_ITEMS;
    let (mut c, _ids) = controller(); // starts with 3 items
    let mut denied = 0usize;
    for i in 0..(MAX_PLAN_ITEMS + 50) {
        let reply = c.apply(&Command::AddItem {
            kind: "song".into(),
            title: format!("Song {i}"),
            content: None,
        });
        if reply == ControllerReply::Deny(DenyReason::BadRequest) {
            denied += 1;
        }
    }
    assert_eq!(
        c.plan().len(),
        MAX_PLAN_ITEMS,
        "plan capped at MAX_PLAN_ITEMS"
    );
    assert!(
        denied >= 50,
        "adds past the cap are denied (denied={denied})"
    );
    // A further add is still denied (not silently accepted).
    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "song".into(),
            title: "one more".into(),
            content: None,
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn get_screen_frame_command_returns_a_themed_thumbnail_per_screen() {
    // 86ajq321k preview: the GetScreenFrame command exposes compose_screen over the wire so the
    // operator Screens page can PREVIEW each audience screen's own design (read-only, bounded).
    use selahcue_lan::protocol::ThumbView;
    fn thumb(c: &mut LiveController, screen: &str) -> Option<ThumbView> {
        match c.apply(&Command::GetScreenFrame {
            screen: screen.into(),
            max_w: 96,
            max_h: 54,
        }) {
            ControllerReply::Message(ServerMessage::ScreenFrame { screen: s, frame }) => {
                assert_eq!(s, screen, "the reply echoes the requested screen");
                frame
            }
            other => panic!("expected ScreenFrame, got {other:?}"),
        }
    }
    let mut c = controller_live();
    c.apply(&Command::SetScreenTheme {
        screen: "lower-third".into(),
        name: "lower-third".into(),
    });
    c.apply(&Command::SetScreenTheme {
        screen: "stream".into(),
        name: "high-contrast".into(),
    });

    let main = thumb(&mut c, "main").expect("main frame");
    let lower = thumb(&mut c, "lower-third").expect("lower frame");
    let stream = thumb(&mut c, "stream").expect("stream frame");
    // Bounded (host-clamped) thumbnail.
    assert!(
        main.w > 0 && main.w <= 96 && main.h > 0 && main.h <= 54,
        "thumbnail is clamped to the requested size"
    );
    // Three distinct designs at once (distinct base64 pixel payloads).
    assert_ne!(main.rgba, lower.rgba, "main != lower-third");
    assert_ne!(lower.rgba, stream.rgba, "lower-third != stream");
    // An unknown screen has no frame.
    assert!(
        thumb(&mut c, "disco").is_none(),
        "unknown screen -> no frame"
    );
    // Read-only: fetching a preview never changes the audience output.
    let live_before = c.presenter().live_output().bytes().to_vec();
    let _ = thumb(&mut c, "main");
    assert_eq!(
        c.presenter().live_output().bytes(),
        live_before.as_slice(),
        "a screen preview never changes the audience output"
    );
    // Blackout blacks EVERY screen -> the three previews are identical (black) + differ from themed.
    c.apply(&Command::Blackout { on: true });
    let mb = thumb(&mut c, "main").unwrap();
    let lb = thumb(&mut c, "lower-third").unwrap();
    let sb = thumb(&mut c, "stream").unwrap();
    assert_eq!(
        mb.rgba, lb.rgba,
        "blackout: main == lower-third (both black)"
    );
    assert_eq!(
        lb.rgba, sb.rgba,
        "blackout: lower-third == stream (both black)"
    );
    assert_ne!(mb.rgba, main.rgba, "blackout differs from the themed frame");
}

// ---- Screens page: dynamic screen registry (enable/disable + add/delete virtual) ----

/// The operator view exposes the four built-in screens (main/lower-third/stream/stage),
/// all enabled, none deletable — the default registry.
#[test]
fn registry_seeds_the_four_builtins_none_deletable() {
    let c = controller_live();
    let screens = c.operator_view().screens;
    let ids: Vec<&str> = screens.iter().map(|s| s.screen.as_str()).collect();
    assert_eq!(
        ids,
        ["main", "lower-third", "stream", "stage"],
        "order stable"
    );
    for s in &screens {
        assert!(s.enabled, "{} enabled by default", s.screen);
        assert!(!s.deletable, "{} is a built-in (not deletable)", s.screen);
    }
    // Roles are the stable tags; only the stage carries no theme slot.
    let stage = screens.iter().find(|s| s.screen == "stage").unwrap();
    assert_eq!(stage.role, "stage");
    assert_eq!(stage.theme, None);
}

/// Disabling a screen composes safe all-black (a per-screen mute); re-enabling restores
/// the themed frame. `is_screen_enabled` mirrors the state for the desktop window gate.
#[test]
fn disabling_a_screen_blacks_its_frame_and_reenabling_restores() {
    // RGB-black test (BLACK is opaque — the alpha byte is 255, so check the RGB triplets).
    let rgb_black = |fb: &selahcue_present::FrameBuffer| {
        fb.bytes()
            .chunks_exact(4)
            .all(|px| px[0] == 0 && px[1] == 0 && px[2] == 0)
    };
    let mut c = controller_live();
    let themed = c.compose_screen("lower-third").unwrap().bytes().to_vec();
    assert!(
        themed
            .chunks_exact(4)
            .any(|px| px[0] != 0 || px[1] != 0 || px[2] != 0),
        "the themed lower-third frame has visible (non-black) content"
    );

    assert_eq!(
        c.apply(&Command::SetScreenEnabled {
            screen: "lower-third".into(),
            enabled: false,
        }),
        ControllerReply::Ack
    );
    assert!(!c.is_screen_enabled("lower-third"));
    let disabled = c.compose_screen("lower-third").unwrap();
    assert!(rgb_black(&disabled), "a disabled screen composes all-black");
    // An enabled sibling is unaffected (per-screen, not global blackout).
    assert!(!rgb_black(&c.compose_screen("main").unwrap()));
    assert!(c.is_screen_enabled("main"));

    assert_eq!(
        c.apply(&Command::SetScreenEnabled {
            screen: "lower-third".into(),
            enabled: true,
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.compose_screen("lower-third").unwrap().bytes(),
        themed.as_slice(),
        "re-enabling restores the exact themed frame"
    );
    // An unknown screen cannot be toggled.
    assert_eq!(
        c.apply(&Command::SetScreenEnabled {
            screen: "disco".into(),
            enabled: false,
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

/// Adding a virtual audience screen mints a stable id, composes like a built-in, and can
/// carry its own theme; a bad/singleton role is rejected.
#[test]
fn add_virtual_screen_mints_a_composable_audience_feed() {
    let mut c = controller_live();
    assert_eq!(
        c.apply(&Command::AddScreen {
            role: "stream".into()
        }),
        ControllerReply::Ack
    );
    let screens = c.operator_view().screens;
    let added = screens
        .iter()
        .find(|s| s.screen == "stream-2")
        .expect("stream-2 minted");
    assert_eq!(added.role, "stream");
    assert!(added.enabled && added.deletable);
    // The virtual feed composes the live content (follows global until themed).
    assert!(c.compose_screen("stream-2").is_some());
    // It can carry its own theme (Audience-class).
    assert_eq!(
        c.apply(&Command::SetScreenTheme {
            screen: "stream-2".into(),
            name: "high-contrast".into(),
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.screen_themes().get("stream-2").map(String::as_str),
        Some("high-contrast")
    );

    // A second stream feed gets the next free id, deterministically.
    assert_eq!(
        c.apply(&Command::AddScreen {
            role: "stream".into()
        }),
        ControllerReply::Ack
    );
    assert!(c
        .operator_view()
        .screens
        .iter()
        .any(|s| s.screen == "stream-3"));
    // A lower-third virtual feed is independent.
    assert_eq!(
        c.apply(&Command::AddScreen {
            role: "lower-third".into()
        }),
        ControllerReply::Ack
    );
    assert!(c
        .operator_view()
        .screens
        .iter()
        .any(|s| s.screen == "lower-third-2"));

    // Singleton / unknown roles cannot be added.
    for bad in ["main", "stage", "bogus"] {
        assert_eq!(
            c.apply(&Command::AddScreen { role: bad.into() }),
            ControllerReply::Deny(DenyReason::BadRequest),
            "role {bad} is not addable"
        );
    }
}

/// Only a virtual screen can be deleted; a built-in delete is rejected server-side, an
/// absent id is idempotent, and deleting a screen drops its per-screen theme.
#[test]
fn delete_is_virtual_only_and_drops_the_theme() {
    let mut c = controller_live();
    c.apply(&Command::AddScreen {
        role: "stream".into(),
    });
    c.apply(&Command::SetScreenTheme {
        screen: "stream-2".into(),
        name: "classic".into(),
    });
    assert!(c.screen_themes().get("stream-2").is_some());

    // A built-in is never deletable — even though it exists.
    for builtin in ["main", "lower-third", "stream", "stage"] {
        assert_eq!(
            c.apply(&Command::RemoveScreen {
                screen: builtin.into()
            }),
            ControllerReply::Deny(DenyReason::BadRequest),
            "built-in {builtin} may be disabled but never deleted"
        );
        assert!(
            c.screen_registry().get(builtin).is_some(),
            "{builtin} still present"
        );
    }

    // The virtual screen deletes, and its theme override goes with it.
    assert_eq!(
        c.apply(&Command::RemoveScreen {
            screen: "stream-2".into()
        }),
        ControllerReply::Ack
    );
    assert!(c.screen_registry().get("stream-2").is_none());
    assert!(
        c.screen_themes().get("stream-2").is_none(),
        "theme dropped with the screen"
    );
    assert!(
        c.compose_screen("stream-2").is_none(),
        "a deleted screen no longer composes"
    );

    // A double-delete (already absent) is idempotent, not an error.
    assert_eq!(
        c.apply(&Command::RemoveScreen {
            screen: "stream-2".into()
        }),
        ControllerReply::Ack
    );
}

/// The registry is bounded: `AddScreen` is refused at `MAX_SCREENS`, and the registry
/// never grows past the cap however many adds are attempted (no-leak).
#[test]
fn registry_is_bounded_to_max_screens() {
    let mut c = controller_live();
    let start = c.screen_registry().len();
    // Hammer far more adds than the cap allows.
    let mut acks = 0usize;
    for _ in 0..(selahcue_app::MAX_SCREENS * 4) {
        if c.apply(&Command::AddScreen {
            role: "stream".into(),
        }) == ControllerReply::Ack
        {
            acks += 1;
        }
    }
    assert_eq!(
        c.screen_registry().len(),
        selahcue_app::MAX_SCREENS,
        "the registry is capped at MAX_SCREENS regardless of add pressure"
    );
    assert_eq!(
        acks,
        selahcue_app::MAX_SCREENS - start,
        "only cap-minus-builtins adds succeeded"
    );
    // Further adds keep being denied (bounded, deterministic).
    assert_eq!(
        c.apply(&Command::AddScreen {
            role: "stream".into()
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

/// `from_persisted` recovers robustly: the four built-ins are always present, a corrupt
/// (unknown-role) row and an over-cap row are dropped, and built-in enable flags restore.
#[test]
fn registry_from_persisted_recovers_and_bounds() {
    use selahcue_app::ScreenRegistry;
    // A tampered store: main disabled, one valid virtual, a corrupt role, and a bogus
    // "virtual" claiming a built-in id — plus far more rows than the cap.
    let mut rows: Vec<(String, String, bool, bool)> = vec![
        ("main".into(), "main".into(), false, false), // built-in, disabled
        ("stream-2".into(), "stream".into(), true, true), // valid virtual
        ("evil".into(), "not-a-role".into(), true, true), // corrupt role → dropped
        ("stage".into(), "stage".into(), false, false), // built-in stage, disabled
    ];
    for i in 0..100 {
        rows.push((format!("stream-{}", i + 10), "stream".into(), true, true));
    }
    let reg = ScreenRegistry::from_persisted(rows);
    assert!(reg.len() <= selahcue_app::MAX_SCREENS, "bounded on load");
    // The four built-ins survive exactly once each, in order.
    for b in ["main", "lower-third", "stream", "stage"] {
        assert_eq!(
            reg.iter().filter(|s| s.id == b).count(),
            1,
            "built-in {b} recovered exactly once (no clone)"
        );
    }
    assert!(
        !reg.is_enabled("main"),
        "built-in enable flag restored (disabled)"
    );
    assert!(
        !reg.is_enabled("stage"),
        "stage enable flag restored (disabled)"
    );
    assert!(reg.get("stream-2").is_some(), "the valid virtual restored");
    assert!(reg.get("evil").is_none(), "the corrupt-role row dropped");
    // An empty store still yields the safe default (never empty / crash).
    let empty = ScreenRegistry::from_persisted(std::iter::empty());
    assert_eq!(empty.len(), 4, "empty store recovers to the four built-ins");
}

/// Review fix (registry lens): the operator console LIVE monitor is the `main` audience
/// output, so a disabled `main` screen mutes it to black there too — matching the physical
/// window + the Screens preview. The Preview monitor (the staged feed) is unaffected.
#[test]
fn disabling_main_blacks_the_console_live_monitor_not_preview() {
    let console = |c: &mut LiveController| -> (String, String) {
        match c.apply(&Command::GetConsoleThumbnails {
            max_w: 64,
            max_h: 36,
        }) {
            ControllerReply::Message(ServerMessage::ConsoleThumbnails { preview, live }) => {
                (preview.unwrap().rgba, live.unwrap().rgba)
            }
            other => panic!("expected ConsoleThumbnails, got {other:?}"),
        }
    };
    let mut c = controller_live();
    let (pv_before, lv_before) = console(&mut c);

    // Disable main: the LIVE monitor blacks, the PREVIEW monitor is unchanged.
    c.apply(&Command::SetScreenEnabled {
        screen: "main".into(),
        enabled: false,
    });
    let (pv_after, lv_after) = console(&mut c);
    assert_eq!(
        pv_before, pv_after,
        "Preview (the staged feed) is unaffected by a main disable"
    );
    assert_ne!(
        lv_before, lv_after,
        "the Live monitor changed when main was disabled"
    );

    // Prove it is BLACK: it must equal the Live thumbnail produced under a global blackout
    // (the presenter's all-black frame) — same dims, same all-black pixels.
    c.apply(&Command::SetScreenEnabled {
        screen: "main".into(),
        enabled: true,
    });
    c.apply(&Command::Blackout { on: true });
    let (_pv_bo, lv_blackout) = console(&mut c);
    assert_eq!(
        lv_after, lv_blackout,
        "a disabled-main Live monitor equals the blackout (all-black) frame"
    );
}

/// A custom theme carrying a TEXT element (86ajq6j64) applies, survives recovery, and is
/// bounded — an over-cap Text box is rejected at every theme ingress (no unbounded growth).
#[test]
fn a_custom_theme_with_a_text_element_applies_recovers_and_is_bounded() {
    use std::time::Instant;
    let t0 = Instant::now();
    let text_box = |text: String, z: i16| Element::Text {
        x_permille: 100,
        y_permille: 700,
        w_permille: 800,
        h_permille: 200,
        text,
        color: Rgba::WHITE,
        size_permille: 80,
        line_height_permille: 1150,
        align_h: TextAlign::Center,
        align_v: VAlign::Middle,
        fit: Fit::ShrinkToFit,
        opacity: 255,
        z,
        font: None,
        weight: 400,
        letter_spacing_permille: 0,
    };
    let mut theme = Theme::classic();
    theme.elements.push(text_box("LIVE".into(), 1));
    let json = serde_json::to_string(&theme).unwrap();

    let (mut a, _) = controller();
    a.apply(&Command::Next);
    a.apply(&Command::GoLive);
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: json.clone()
        }),
        ControllerReply::Ack
    );

    // Persist + recover: the text element re-renders identically.
    let snap = a.snapshot(t0);
    let (mut b, _) = controller();
    b.restore(&snap);
    b.tick(t0);
    assert_eq!(
        b.presenter().live_output().bytes(),
        a.presenter().live_output().bytes(),
        "a text element re-renders identically after recovery"
    );

    // An over-cap text element is rejected at BOTH set_custom_theme + save_theme (no-leak).
    let mut over = Theme::classic();
    over.elements
        .push(text_box("x".repeat(MAX_TEXT_ELEMENT_LEN + 1), 0));
    assert!(!over.elements_bounded(), "the over-cap theme is unbounded");
    let over_json = serde_json::to_string(&over).unwrap();
    assert_eq!(
        a.apply(&Command::SetCustomTheme {
            theme_json: over_json.clone()
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "set_custom_theme rejects an over-cap text element"
    );
    assert_eq!(
        a.apply(&Command::SaveTheme {
            name: "big-text".into(),
            theme_json: over_json,
        }),
        ControllerReply::Deny(DenyReason::BadRequest),
        "save_theme rejects an over-cap text element"
    );
}

/// A custom theme with a GRADIENT or an IMAGE background (86ajq3225) applies, does not crash
/// on a missing image (the placeholder is deterministic), and re-renders identically after
/// recovery.
#[test]
fn a_custom_theme_with_a_gradient_or_image_background_applies_and_recovers() {
    use selahcue_present::{Background, GradientBackground, GradientDirection, ImageBackground};
    use std::time::Instant;
    let t0 = Instant::now();
    for bg in [
        Background::Gradient(GradientBackground {
            from: Rgba::rgb(10, 20, 40),
            to: Rgba::rgb(200, 120, 40),
            direction: GradientDirection::DiagonalDown,
        }),
        // A missing image resolves to the deterministic missing-media placeholder (FR-070),
        // so apply + recover still render identically (no crash, no blank).
        Background::Image(ImageBackground {
            source: MediaRef::new("/no/such/background.png").unwrap(),
        }),
    ] {
        let mut theme = Theme::classic();
        theme.background = bg;
        let json = serde_json::to_string(&theme).unwrap();

        let (mut a, _) = controller();
        a.apply(&Command::Next);
        a.apply(&Command::GoLive);
        assert_eq!(
            a.apply(&Command::SetCustomTheme {
                theme_json: json.clone()
            }),
            ControllerReply::Ack
        );
        let live = a.presenter().live_output().bytes().to_vec();

        let snap = a.snapshot(t0);
        let (mut b, _) = controller();
        b.restore(&snap);
        b.tick(t0);
        assert_eq!(
            b.presenter().live_output().bytes(),
            live.as_slice(),
            "the gradient/image background re-renders identically after recovery"
        );
    }
}
