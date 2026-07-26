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
fn scripture_slides_never_exceed_the_compositor_line_capacity() {
    // Psalm 119 (176 verses) truncates INSIDE the renderable region: at most 6
    // body lines, the last being the ellipsis marker — pinned against the
    // compositor capacity test in selahcue-present (title + 6 body lines).
    let (mut c, _) = controller();
    c.apply(&Command::StageScripture {
        reference: "Psalm 119".into(),
        translation: None,
    });
    let slide = c.presenter().staged().expect("staged");
    assert!(slide.body.len() <= 6, "body lines: {}", slide.body.len());
    assert_eq!(slide.body.last().map(String::as_str), Some("\u{2026}"));

    // A short verse is untouched (no marker).
    c.apply(&Command::StageScripture {
        reference: "John 11:35".into(),
        translation: None,
    });
    let slide = c.presenter().staged().expect("staged");
    assert!(slide.body.len() <= 6);
    assert_ne!(slide.body.last().map(String::as_str), Some("\u{2026}"));
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
