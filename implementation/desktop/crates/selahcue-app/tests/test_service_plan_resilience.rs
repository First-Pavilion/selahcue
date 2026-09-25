//! Wire-level coverage for ticket 86ajy0hxg: item Undo/Redo, autosave slots + restore, and the
//! crash-loop Resume/StartClean gate. Controller-only (no transport) — mirrors the style of
//! `test_publish.rs`/`test_health_view.rs`.

#![allow(clippy::unwrap_used)]

use selahcue_app::{
    AutosaveSlotSummary, AutosaveStore, ControllerReply, ControllerSnapshot, LiveController,
};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, ContentLinkView, DenyReason, ServerMessage};
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

fn scripture_link(reference: &str) -> ContentLinkView {
    ContentLinkView {
        kind: "scripture".into(),
        reference: Some(reference.into()),
        translation: Some("WEB".into()),
        verses_per_slide: Some(2),
        id: None,
        slide_count: None,
        verse_numbers: None,
        status: None,
        label: None,
    }
}

// ---------------------------------------------------------------------------------------------
// Item Undo (86ajy0hxg): Command::UndoPlan / Command::RedoPlan over the wire.
// ---------------------------------------------------------------------------------------------

#[test]
fn undo_plan_is_a_no_op_ack_on_an_empty_history() {
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::UndoPlan), ControllerReply::Ack);
    assert_eq!(c.plan().len(), 3, "nothing to undo — the plan is unchanged");
}

#[test]
fn redo_plan_is_a_no_op_ack_on_an_empty_history() {
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::RedoPlan), ControllerReply::Ack);
    assert_eq!(c.plan().len(), 3);
}

/// The core acceptance criterion: undoing a `RemoveItem` restores the item with its ORIGINAL id
/// and its content link intact — not a new id with a lost link, which is what re-adding via
/// `AddItem` would give.
#[test]
fn undo_plan_restores_a_removed_item_with_its_original_id_and_content_link() {
    let (mut c, ids) = controller();
    let scripture_id = ids[1];

    assert_eq!(
        c.apply(&Command::SetItemContent {
            item_id: scripture_id,
            link: Some(scripture_link("Romans 8:28-30")),
        }),
        ControllerReply::Ack
    );
    let before = c.operator_view();
    let linked = before
        .items
        .iter()
        .find(|i| i.id == scripture_id)
        .expect("item present before removal");
    assert!(
        linked.link.is_some(),
        "positive control: the link was really set"
    );

    assert_eq!(
        c.apply(&Command::RemoveItem {
            item_id: scripture_id
        }),
        ControllerReply::Ack
    );
    assert!(
        c.operator_view().items.iter().all(|i| i.id != scripture_id),
        "positive control: the item really was removed"
    );

    assert_eq!(c.apply(&Command::UndoPlan), ControllerReply::Ack);

    let restored = c.operator_view();
    let item = restored
        .items
        .iter()
        .find(|i| i.id == scripture_id)
        .expect("undo must restore the item under its ORIGINAL id, not a new one");
    let link = item
        .link
        .as_ref()
        .expect("undo must restore the item's content link, not just its title");
    assert_eq!(link.reference.as_deref(), Some("Romans 8:28-30"));
}

#[test]
fn redo_plan_reapplies_the_undone_removal() {
    let (mut c, ids) = controller();
    let item_id = ids[0];
    c.apply(&Command::RemoveItem { item_id });
    c.apply(&Command::UndoPlan);
    assert!(c.operator_view().items.iter().any(|i| i.id == item_id));

    assert_eq!(c.apply(&Command::RedoPlan), ControllerReply::Ack);
    assert!(
        c.operator_view().items.iter().all(|i| i.id != item_id),
        "redo must re-apply the removal"
    );
}

// ---------------------------------------------------------------------------------------------
// Autosave slots (FR-005 "last-3"; FR-079 integrity) — Command::ListAutosaveSlots /
// Command::RestoreAutosave.
// ---------------------------------------------------------------------------------------------

/// One fake slot's payload: what `load_slot` returns when asked for it, if anything.
type FakeSlotPayload = Option<(ServicePlan, ControllerSnapshot)>;

/// A test double standing in for the real `selahcue-data`-backed store, exactly the way
/// `RealAutosaveStore` would in the desktop binary — this crate cannot depend on `selahcue-data`
/// (the whole point of the trait seam), so the fake is the only way to exercise the wire
/// commands without a transitive dependency inversion.
struct FakeAutosaveStore {
    slots: Vec<(i64, AutosaveSlotSummary, FakeSlotPayload)>,
    /// When set, `load_slot` returns this error for EVERY slot — simulates an integrity-check
    /// failure (FR-079) independent of which slot id was asked for.
    fail_integrity: bool,
}

impl AutosaveStore for FakeAutosaveStore {
    fn list_slots(&mut self) -> Result<Vec<AutosaveSlotSummary>, String> {
        Ok(self.slots.iter().map(|(_, s, _)| s.clone()).collect())
    }

    fn load_slot(
        &mut self,
        slot: i64,
    ) -> Result<Option<(ServicePlan, ControllerSnapshot)>, String> {
        if self.fail_integrity {
            return Err("PRAGMA integrity_check failed (simulated)".to_string());
        }
        Ok(self
            .slots
            .iter()
            .find(|(id, _, _)| *id == slot)
            .and_then(|(_, _, payload)| payload.clone()))
    }
}

fn plan_with_one_live_item() -> (ServicePlan, u64) {
    let mut plan = ServicePlan::new("Slot plan");
    let id = plan.add_item(ItemKind::Song, "Doxology");
    (plan, id.0)
}

#[test]
fn list_autosave_slots_reports_whatever_the_injected_store_holds() {
    let (mut c, _) = controller();
    c.set_autosave_store(Box::new(FakeAutosaveStore {
        slots: vec![
            (
                2,
                AutosaveSlotSummary {
                    slot: 2,
                    saved_at_ms: 2_000,
                    label: None,
                },
                None,
            ),
            (
                1,
                AutosaveSlotSummary {
                    slot: 1,
                    saved_at_ms: 1_000,
                    label: Some("before sermon".into()),
                },
                None,
            ),
        ],
        fail_integrity: false,
    }));

    let reply = c.apply(&Command::ListAutosaveSlots);
    let ControllerReply::Message(ServerMessage::AutosaveSlots { slots }) = reply else {
        panic!("expected an autosave_slots reply, got {reply:?}");
    };
    assert_eq!(slots.len(), 2);
    assert_eq!(slots[0].slot, 2);
    assert_eq!(slots[1].label.as_deref(), Some("before sermon"));
}

#[test]
fn list_autosave_slots_is_empty_with_no_store_configured() {
    // The default `NullAutosaveStore` — never wired in this test — must answer honestly with
    // an empty list, not deny or panic.
    let (mut c, _) = controller();
    let reply = c.apply(&Command::ListAutosaveSlots);
    let ControllerReply::Message(ServerMessage::AutosaveSlots { slots }) = reply else {
        panic!("expected an autosave_slots reply, got {reply:?}");
    };
    assert!(slots.is_empty());
}

#[test]
fn restore_autosave_swaps_the_plan_and_repositions_live() {
    let (mut c, _) = controller();
    let (slot_plan, item_id) = plan_with_one_live_item();
    let snap = ControllerSnapshot {
        live_idx: Some(0),
        ..Default::default()
    };
    c.set_autosave_store(Box::new(FakeAutosaveStore {
        slots: vec![(
            7,
            AutosaveSlotSummary {
                slot: 7,
                saved_at_ms: 5_000,
                label: None,
            },
            Some((slot_plan, snap)),
        )],
        fail_integrity: false,
    }));

    assert_eq!(
        c.apply(&Command::RestoreAutosave { slot: 7 }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.plan().len(),
        1,
        "the DIFFERENT slot plan must be installed"
    );
    let item = c.operator_view().items.into_iter().next().unwrap();
    assert_eq!(item.id, item_id);
    assert!(
        item.is_live,
        "the restored snapshot's live index must apply"
    );
}

#[test]
fn restore_autosave_denies_an_unknown_slot() {
    let (mut c, _) = controller();
    c.set_autosave_store(Box::new(FakeAutosaveStore {
        slots: Vec::new(),
        fail_integrity: false,
    }));
    assert_eq!(
        c.apply(&Command::RestoreAutosave { slot: 999 }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

/// FR-079: a failed integrity check must refuse the restore, not hand back a plausible-looking
/// but unreliable snapshot.
#[test]
fn restore_autosave_denies_on_a_failed_integrity_check() {
    let (mut c, _) = controller();
    let original_len = c.plan().len();
    c.set_autosave_store(Box::new(FakeAutosaveStore {
        slots: vec![(
            1,
            AutosaveSlotSummary {
                slot: 1,
                saved_at_ms: 1_000,
                label: None,
            },
            Some(plan_with_one_live_item_as_snapshot()),
        )],
        fail_integrity: true,
    }));
    assert_eq!(
        c.apply(&Command::RestoreAutosave { slot: 1 }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.plan().len(),
        original_len,
        "a refused restore must not have swapped the plan"
    );
}

fn plan_with_one_live_item_as_snapshot() -> (ServicePlan, ControllerSnapshot) {
    let (plan, _) = plan_with_one_live_item();
    (plan, ControllerSnapshot::default())
}

// ---------------------------------------------------------------------------------------------
// Crash-loop Resume/StartClean (FR-169, FR-074/075) — Command::Resume / Command::StartClean.
// ---------------------------------------------------------------------------------------------

#[test]
fn resume_is_denied_when_the_host_has_not_reported_a_crash_loop() {
    let (mut c, _) = controller();
    // No `set_session_health` call at all — mirrors a build/host that never reports health.
    assert_eq!(
        c.apply(&Command::Resume),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert!(c.take_pending_crash_decision().is_none());
}

#[test]
fn start_clean_is_denied_when_crash_loop_is_false() {
    let (mut c, _) = controller();
    c.set_session_health(true, false, None, None, false);
    assert_eq!(
        c.apply(&Command::StartClean),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
}

#[test]
fn resume_is_accepted_and_recorded_while_crash_loop_is_true() {
    let (mut c, _) = controller();
    c.set_session_health(false, true, Some(3), None, true);
    assert_eq!(c.apply(&Command::Resume), ControllerReply::Ack);
    assert_eq!(
        c.take_pending_crash_decision(),
        Some(selahcue_app::CrashDecision::Resume)
    );
    // Draining is destructive — a second read finds nothing pending.
    assert!(c.take_pending_crash_decision().is_none());
}

#[test]
fn start_clean_is_accepted_and_recorded_while_crash_loop_is_true() {
    let (mut c, _) = controller();
    c.set_session_health(false, true, Some(3), None, false);
    assert_eq!(c.apply(&Command::StartClean), ControllerReply::Ack);
    assert_eq!(
        c.take_pending_crash_decision(),
        Some(selahcue_app::CrashDecision::StartClean)
    );
}

/// `resume_preserved` (the host-tick-driven "Resume" implementation) must never leave the
/// audience output blank (NFR-024) — it reuses `restore`'s own tested reconciliation, this
/// pins that the composition survives a PLAN swap too, not just an index restore.
#[test]
fn resume_preserved_never_blanks_the_live_output() {
    let (mut c, _) = controller();
    c.apply(&Command::Next);
    c.apply(&Command::GoLive);
    assert!(
        c.presenter().live_output().average_luminance() > 1e-6,
        "positive control: live has content"
    );

    let (slot_plan, _) = plan_with_one_live_item();
    let snap = ControllerSnapshot {
        live_idx: Some(0),
        ..Default::default()
    };
    c.resume_preserved(slot_plan, &snap);

    assert!(
        c.presenter().live_output().average_luminance() > 1e-6,
        "resuming a preserved session must never blank the live output"
    );
}
