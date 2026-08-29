//! Service-plan publish / hand-off (FR-006) and the plan lifecycle actions (FR-005).
//!
//! Two properties carry the weight here and both are asserted with a positive control beside
//! them, because "Live did not change" and "the command was refused" are each indistinguishable
//! from "the command did nothing at all":
//!
//! - publishing and replacing the plan never change the LIVE audience output (FR-012, NFR-024);
//! - the change badge reports that the plan DIFFERS from what was published, never merely that
//!   it was touched.

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan, MAX_PLAN_ITEMS, MAX_PLAN_NAME_LEN};
use selahcue_lan::protocol::{Command, DenyReason, ImportItemView};
use selahcue_present::Theme;

/// The battery below distinguishes "at the cap" from "one over the cap", which is only a real
/// distinction while the cap leaves room for both. Pinned at compile time so shrinking the cap
/// to 0 or 1 fails the build instead of quietly turning the test vacuous.
const _: () = assert!(
    MAX_PLAN_ITEMS >= 2,
    "the import cap test needs a cap with room below it"
);
/// Likewise the name battery builds a name of exactly `MAX_PLAN_NAME_LEN + 1` characters and
/// expects it refused while `MAX_PLAN_NAME_LEN` is accepted.
const _: () = assert!(
    MAX_PLAN_NAME_LEN >= 2,
    "the name-length test needs a bound with room below it"
);

fn controller() -> (LiveController, Vec<u64>) {
    let mut plan = ServicePlan::new("Sunday");
    let a = plan.add_item(ItemKind::Song, "Opening Song");
    let b = plan.add_item(ItemKind::Scripture, "Romans 8:28");
    (
        LiveController::new(plan, 320, 180, Theme::dark()),
        vec![a.0, b.0],
    )
}

/// Put the plan item at `item_id` on the LIVE audience output.
fn go_live(c: &mut LiveController, item_id: u64) {
    assert_eq!(
        c.apply(&Command::SelectItem { item_id }),
        ControllerReply::Ack
    );
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
}

fn item(kind: &str, title: &str) -> ImportItemView {
    ImportItemView {
        kind: kind.into(),
        title: title.into(),
        owner: None,
        planned_secs: None,
    }
}

fn publish(c: &LiveController) -> selahcue_lan::protocol::PublishStateView {
    c.publish_state()
}

// ---------------------------------------------------------------------------------------------
// The change badge
// ---------------------------------------------------------------------------------------------

#[test]
fn a_plan_that_was_never_published_reports_no_badge_and_no_version() {
    let (mut c, _) = controller();
    let before = publish(&c);
    assert_eq!(before.published_revision, None, "a fresh plan is a draft");
    assert_eq!(before.version, 0, "a draft has no version number");
    assert!(!before.changed, "a draft has nothing to compare against");

    assert_eq!(
        c.apply(&Command::RenameItem {
            item_id: 1,
            title: "Renamed".into()
        }),
        ControllerReply::Ack
    );
    let after = publish(&c);
    // POSITIVE CONTROL: without this the assertion below passes on a controller where editing
    // silently did nothing, which is exactly the state that makes "no badge" meaningless.
    assert!(
        after.revision > before.revision,
        "the edit did not move the revision, so the no-badge claim below was never exercised"
    );
    assert!(
        !after.changed,
        "an unpublished plan must never show \"Plan updated\" — there is no baseline to review \
         against, so the badge would describe a comparison that never happened"
    );
    assert_eq!(after.version, 0, "editing is not publishing");
}

#[test]
fn publishing_sets_the_baseline_and_a_later_edit_raises_the_badge() {
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);

    let published = publish(&c);
    assert_eq!(published.version, 1, "the first hand-off is v1");
    assert_eq!(
        published.published_revision,
        Some(published.revision),
        "publishing marks the revision that is current"
    );
    assert!(
        !published.changed,
        "nothing has changed since a fresh publish"
    );

    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "song".into(),
            title: "Extra".into(),
            content: None
        }),
        ControllerReply::Ack
    );
    let edited = publish(&c);
    assert!(
        edited.changed,
        "an edit after publish must raise \"Plan updated · Review changes\""
    );
    assert_eq!(
        edited.published_revision, published.published_revision,
        "an edit must not move the published baseline — only publishing does"
    );

    assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);
    let republished = publish(&c);
    assert!(!republished.changed, "republishing clears the badge");
    assert_eq!(republished.version, 2, "each hand-off counts a version");
}

#[test]
fn publishing_twice_over_never_raises_its_own_badge() {
    // Publish is idempotent as far as the operator is concerned: handing the same plan off
    // again counts another version and still reports nothing to review.
    //
    // This test does NOT pin the `is_plan_edit` exclusion, and an earlier version of this comment
    // wrongly claimed it did. Adding `Command::PublishPlan` to `is_plan_edit` leaves the entire
    // `selahcue-app` suite green, because the block consuming that predicate also requires
    // `self.plan != before` and publishing changes no item — the exclusion is subsumed and no
    // input exists that only it rejects. What this test does pin is `refresh_published_delta`'s
    // document comparison and the explicit clear in the publish handler (mutations M2 and M10
    // both fail here), which is what the property actually rests on.
    let (mut c, _) = controller();
    for round in 1..=3u32 {
        assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);
        let p = publish(&c);
        assert_eq!(p.version, round, "every publish counts");
        assert!(
            !p.changed,
            "publish {round} raised a badge against itself — publishing is not an edit"
        );
    }
}

#[test]
fn undoing_back_to_the_published_plan_clears_the_badge() {
    // The control for comparing the published DOCUMENT rather than revision counters. Undo moves
    // the revision but restores the content, so a counter-derived flag leaves "Review changes"
    // standing over a plan identical to the published one. Replacing `refresh_published_delta`'s
    // comparison with `published_revision != Some(revision)` fails this.
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);
    let at_publish = publish(&c);

    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "song".into(),
            title: "Oops".into(),
            content: None
        }),
        ControllerReply::Ack
    );
    assert!(publish(&c).changed, "the edit must raise the badge first");

    c.undo_plan();

    let undone = publish(&c);
    // POSITIVE CONTROL: the undo really did move the document, so "no badge" below is a verdict
    // about a comparison that ran, not about a controller where undo is a no-op.
    assert!(
        undone.revision > at_publish.revision,
        "undo did not move the revision, so the exact-comparison claim was never exercised"
    );
    assert_eq!(
        c.plan().len(),
        2,
        "undo must have restored the published run sheet"
    );
    assert!(
        !undone.changed,
        "an edit that was undone leaves nothing to review, so the badge must clear even though \
         the revision has moved past the published one"
    );
}

// ---------------------------------------------------------------------------------------------
// Publish and the live output
// ---------------------------------------------------------------------------------------------

#[test]
fn publishing_never_changes_the_live_output() {
    let (mut c, ids) = controller();
    go_live(&mut c, ids[0]);
    let pixels_before = c.presenter().live_output().bytes().to_vec();
    let live_before = c.live_index();

    assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);

    // POSITIVE CONTROL: publishing actually did something, so "Live unchanged" is not just the
    // reading you get from a command that was silently dropped.
    assert_eq!(publish(&c).version, 1, "the publish did not take effect");
    assert_eq!(
        c.presenter().live_output().bytes(),
        pixels_before.as_slice(),
        "publishing must not change a single pixel of the audience output — it is a statement \
         about the document, not a cue"
    );
    assert_eq!(c.live_index(), live_before, "publishing must not re-cue");
}

#[test]
fn every_plan_replacement_keeps_the_live_slide_on_air() {
    // NFR-024 / FR-012: a coordinator starting next week's run sheet must not blank the service
    // that is running. All four lifecycle commands share `install_plan`, so each is exercised.
    let replacements: Vec<(&str, Command)> = vec![
        (
            "new_plan",
            Command::NewPlan {
                name: "Next Week".into(),
            },
        ),
        (
            "template_plan",
            Command::TemplatePlan {
                template: "sunday-morning".into(),
                name: "Next Week".into(),
            },
        ),
        (
            "duplicate_plan",
            Command::DuplicatePlan {
                name: "Sunday (copy)".into(),
            },
        ),
        (
            "import_plan",
            Command::ImportPlan {
                name: "Imported".into(),
                items: vec![item("song", "One")],
            },
        ),
    ];

    for (label, command) in replacements {
        let (mut c, ids) = controller();
        go_live(&mut c, ids[0]);
        let pixels_before = c.presenter().live_output().bytes().to_vec();
        let live_title = c.plan().items()[0].title.clone();

        assert_eq!(c.apply(&command), ControllerReply::Ack, "{label} refused");

        let view = c.operator_view();
        // POSITIVE CONTROL: the plan really was replaced. Without it, "Live unchanged" is the
        // reading you also get from a command that did nothing.
        assert_ne!(
            view.plan_name, "Sunday",
            "{label} did not replace the plan, so the never-blank claim was never exercised"
        );
        assert_eq!(
            c.presenter().live_output().bytes(),
            pixels_before.as_slice(),
            "{label} changed the audience output — replacing the plan is a document edit and \
             must never blank or re-render Live (NFR-024)"
        );
        assert_eq!(
            view.live_index, None,
            "{label} left a plan row marked LIVE after replacing the plan; the incoming rows are \
             unrelated to the outgoing ones, so a clamped index reports an item the audience has \
             never seen"
        );
        assert_eq!(
            view.live_free_text,
            Some(live_title),
            "{label} lost the on-air slide's identity — it must carry over as a free live slide, \
             the same way removing the live item does"
        );
    }
}

// ---------------------------------------------------------------------------------------------
// Lifecycle command behaviour
// ---------------------------------------------------------------------------------------------

#[test]
fn new_plan_empties_the_run_sheet_and_is_undoable() {
    let (mut c, _) = controller();
    assert_eq!(
        c.apply(&Command::NewPlan {
            name: "  Next Week  ".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().len(), 0, "a new plan starts empty");
    assert_eq!(c.plan().name, "Next Week", "the name is trimmed");

    c.undo_plan();
    assert_eq!(
        c.plan().len(),
        2,
        "replacing the plan is the largest edit there is and must be undoable"
    );
}

#[test]
fn template_plan_builds_the_hosts_own_template() {
    let (mut c, _) = controller();
    let offered = c.operator_view().plan_templates;
    assert!(
        !offered.is_empty(),
        "the host must report the templates it offers, or the picker has nothing to render"
    );
    let first = offered[0].clone();

    assert_eq!(
        c.apply(&Command::TemplatePlan {
            template: first.id.clone(),
            name: "Next Week".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.plan().len() as u32,
        first.items,
        "the run sheet must match the item count the host advertised for that template, or the \
         picker's \"{} items\" is a number the host cannot honour",
        first.items
    );
    assert_eq!(c.plan().name, "Next Week", "the caller's name wins");
}

#[test]
fn duplicate_plan_copies_the_loaded_plan_independently() {
    let (mut c, _) = controller();
    let original_titles: Vec<String> = c.plan().items().iter().map(|i| i.title.clone()).collect();

    assert_eq!(
        c.apply(&Command::DuplicatePlan {
            name: "Sunday (copy)".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().name, "Sunday (copy)");
    let copied: Vec<String> = c.plan().items().iter().map(|i| i.title.clone()).collect();
    assert_eq!(copied, original_titles, "a duplicate carries the run sheet");

    // Independent: editing the copy must not be visible in the undo snapshot of the original.
    assert_eq!(
        c.apply(&Command::RenameItem {
            item_id: c.plan().items()[0].id.0,
            title: "Changed".into()
        }),
        ControllerReply::Ack
    );
    c.undo_plan(); // undo the rename
    c.undo_plan(); // undo the duplicate
    assert_eq!(c.plan().name, "Sunday", "the original is restored intact");
    let restored: Vec<String> = c.plan().items().iter().map(|i| i.title.clone()).collect();
    assert_eq!(
        restored, original_titles,
        "editing the copy reached back into the original — the copy was not independent"
    );
}

#[test]
fn import_plan_builds_the_run_sheet_with_owner_and_duration() {
    let (mut c, _) = controller();
    let items = vec![
        ImportItemView {
            kind: "song".into(),
            title: "Opening".into(),
            owner: Some("Ada".into()),
            planned_secs: Some(300),
        },
        item("section", "Sermon"),
        item("scripture", "John 3:16"),
    ];
    assert_eq!(
        c.apply(&Command::ImportPlan {
            name: "Imported".into(),
            items
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().len(), 3);
    assert_eq!(c.plan().items()[0].owner.as_deref(), Some("Ada"));
    assert_eq!(c.plan().items()[0].planned_secs, Some(300));
    assert_eq!(c.plan().items()[1].kind, ItemKind::Section);
}

// ---------------------------------------------------------------------------------------------
// The rejection battery
// ---------------------------------------------------------------------------------------------

#[test]
fn each_lifecycle_guard_refuses_an_input_only_it_rejects() {
    // Every case below is chosen so that exactly ONE guard rejects it; a case malformed in two
    // ways would still pass with the guard it is named for deleted. The two divider cases are
    // where that matters most: the `planned_secs` case carries NO owner, because with one the
    // owner guard fires first and the duration guard is never reached.
    let too_long: String = "x".repeat(MAX_PLAN_NAME_LEN + 1);
    let over_cap: Vec<ImportItemView> = (0..=MAX_PLAN_ITEMS)
        .map(|i| item("song", &format!("Item {i}")))
        .collect();

    let cases: Vec<(&str, Command)> = vec![
        ("blank plan name", Command::NewPlan { name: "   ".into() }),
        (
            "plan name one character over the bound",
            Command::NewPlan {
                name: too_long.clone(),
            },
        ),
        (
            "control character in the plan name",
            Command::NewPlan {
                name: "Sun\u{7}day".into(),
            },
        ),
        (
            "unknown template id",
            Command::TemplatePlan {
                template: "no-such-template".into(),
                name: "Valid Name".into(),
            },
        ),
        (
            "blank name on duplicate",
            Command::DuplicatePlan { name: "".into() },
        ),
        (
            "unknown item kind",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("not_a_kind", "Opening")],
            },
        ),
        (
            "blank item title",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", "   ")],
            },
        ),
        (
            "item title over the bound",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", &too_long)],
            },
        ),
        (
            "present but blank owner",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "song".into(),
                    title: "Opening".into(),
                    owner: Some("  ".into()),
                    planned_secs: None,
                }],
            },
        ),
        (
            "owner on a section divider",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "section".into(),
                    title: "Sermon".into(),
                    // A perfectly valid owner name: this case must be rejected by the divider
                    // rule, not by the owner-validity rule.
                    owner: Some("Ada".into()),
                    planned_secs: None,
                }],
            },
        ),
        (
            "duration on a section divider",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "section".into(),
                    title: "Sermon".into(),
                    // Deliberately no owner — with one, the owner guard rejects this first and
                    // the duration guard is never exercised.
                    owner: None,
                    planned_secs: Some(300),
                }],
            },
        ),
        (
            "one item over the plan cap",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: over_cap,
            },
        ),
    ];

    for (label, command) in cases {
        let (mut c, _) = controller();
        let before = c.plan().clone();
        let revision_before = publish(&c).revision;

        assert_eq!(
            c.apply(&command),
            ControllerReply::Deny(DenyReason::BadRequest),
            "{label} was accepted"
        );
        assert_eq!(
            c.plan(),
            &before,
            "{label} was refused but still changed the plan — a rejected lifecycle command must \
             leave the run sheet exactly as it was, never half-applied"
        );
        assert_eq!(
            publish(&c).revision,
            revision_before,
            "{label} was refused but still moved the revision, which would raise a change badge \
             for an edit that never happened"
        );
    }
}

#[test]
fn the_benign_counterpart_of_every_refused_case_still_works() {
    // Without this, "refused" above is indistinguishable from a dead code path that refuses
    // everything. Each case here is the same command with the one offending detail corrected.
    let at_bound: String = "x".repeat(MAX_PLAN_NAME_LEN);
    let at_cap: Vec<ImportItemView> = (0..MAX_PLAN_ITEMS)
        .map(|i| item("song", &format!("Item {i}")))
        .collect();
    let template = "sunday-morning";

    let cases: Vec<(&str, Command)> = vec![
        (
            "a plain plan name",
            Command::NewPlan {
                name: "Next Week".into(),
            },
        ),
        (
            "a name exactly at the bound",
            Command::NewPlan {
                name: at_bound.clone(),
            },
        ),
        (
            "a known template",
            Command::TemplatePlan {
                template: template.into(),
                name: "Next Week".into(),
            },
        ),
        (
            "a named duplicate",
            Command::DuplicatePlan {
                name: "Sunday (copy)".into(),
            },
        ),
        (
            "a known item kind",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", "Opening")],
            },
        ),
        (
            "an owner on a triggerable item",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "song".into(),
                    title: "Opening".into(),
                    owner: Some("Ada".into()),
                    planned_secs: None,
                }],
            },
        ),
        (
            "a duration on a triggerable item",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "song".into(),
                    title: "Opening".into(),
                    owner: None,
                    planned_secs: Some(300),
                }],
            },
        ),
        (
            "an import exactly at the plan cap",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: at_cap,
            },
        ),
    ];

    for (label, command) in cases {
        let (mut c, _) = controller();
        assert_eq!(
            c.apply(&command),
            ControllerReply::Ack,
            "{label} was refused — the guard it neighbours is refusing legitimate input, so the \
             matching rejection above proves nothing"
        );
    }
}

#[test]
fn an_import_is_bounded_by_the_plan_item_cap() {
    // No-leak. Asserts the ENTITY — how many items the plan actually holds — rather than a
    // byte-size proxy, and bounds the whole chain: the plan bounds each `plan_undo` snapshot and
    // the single published baseline clone, all of which are plan-sized.
    let (mut c, _) = controller();
    let at_cap: Vec<ImportItemView> = (0..MAX_PLAN_ITEMS)
        .map(|i| item("song", &format!("Item {i}")))
        .collect();
    assert_eq!(
        c.apply(&Command::ImportPlan {
            name: "At Cap".into(),
            items: at_cap
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.plan().len(),
        MAX_PLAN_ITEMS,
        "an import at the cap must land in full"
    );

    let over: Vec<ImportItemView> = (0..=MAX_PLAN_ITEMS)
        .map(|i| item("song", &format!("Over {i}")))
        .collect();
    assert_eq!(
        c.apply(&Command::ImportPlan {
            name: "Over Cap".into(),
            items: over
        }),
        ControllerReply::Deny(DenyReason::BadRequest)
    );
    assert_eq!(
        c.plan().len(),
        MAX_PLAN_ITEMS,
        "an over-cap import must leave the previous run sheet in place, not truncate into it"
    );
    assert_eq!(
        c.plan().name,
        "At Cap",
        "the refused import must not even have renamed the plan"
    );
}

// ---------------------------------------------------------------------------------------------
// The view
// ---------------------------------------------------------------------------------------------

#[test]
fn a_bare_controller_does_not_claim_to_know_who_is_asking() {
    // `None` here is the honest answer — this layer holds the plan, not a session — and a client
    // must render it as "not reported", never as view-only.
    let (c, _) = controller();
    let view = c.operator_view();
    assert!(
        view.viewer.is_none(),
        "the controller invented a viewer identity it has no way to know"
    );
    assert!(
        view.publish.is_some(),
        "the controller owns the plan document, so it can always report publish state"
    );
}

#[test]
fn the_console_shell_reports_itself_as_the_operator() {
    // The Tauri shell drives the controller in-process, so no session stands between it and the
    // plan; naming it Operator records what is already true. `can_edit` still comes from the RBAC
    // verdict rather than a hardcoded `true`, so if the Operator role ever lost plan editing the
    // console's own affordances would follow.
    use selahcue_app::OperatorShell;
    use std::sync::{Arc, Mutex};

    let (c, _) = controller();
    let shell = OperatorShell::new(Arc::new(Mutex::new(c)));
    let viewer = shell
        .view()
        .viewer
        .expect("the console must report who is driving it");
    assert_eq!(viewer.role, selahcue_lan::Role::Operator);
    assert!(viewer.can_edit, "the console operator may edit the plan");
}

#[cfg(feature = "server")]
#[test]
fn the_lan_handler_stamps_the_authenticated_role_onto_the_operator_view() {
    // The handler is the only layer that knows both the view and who asked for it. This is what
    // makes a remote session's `can_edit` the HOST's verdict instead of a client's guess.
    //
    // Deleting the stamp leaves `viewer: None`, which fails on the `expect` below; stamping a
    // fixed role fails on the role comparison; deriving `can_edit` from anything other than the
    // choke point fails the last assertion for at least one role.
    use selahcue_lan::protocol::ServerMessage;
    use selahcue_lan::rbac::can_edit_plan;
    use selahcue_lan::server::Reply;
    use selahcue_lan::Role;
    use std::sync::{Arc, Mutex};

    let (c, _) = controller();
    let handler = selahcue_app::handler_for(Arc::new(Mutex::new(c)));

    // Every role holds `Monitor`, so every role can fetch the view — which is the point: a
    // Viewer must be able to SEE the plan and be told, on the same frame, that it may not edit it.
    for role in [
        Role::Operator,
        Role::Producer,
        Role::Assistant,
        Role::Viewer,
    ] {
        let Reply::Message(message) = handler(role, &Command::GetOperatorState) else {
            panic!("{role:?}: expected the operator view");
        };
        let ServerMessage::OperatorState { view } = *message else {
            panic!("{role:?}: expected an operator_state frame");
        };
        let viewer = view
            .viewer
            .unwrap_or_else(|| panic!("{role:?}: the handler did not stamp the session identity"));
        assert_eq!(
            viewer.role, role,
            "the stamped role must be the granted one"
        );
        assert_eq!(
            viewer.can_edit,
            can_edit_plan(role),
            "{role:?}: the view's can_edit disagrees with the choke point that will refuse the \
             command, so the UI would offer a control the host rejects (or hide one it allows)"
        );
    }
}

#[cfg(feature = "server")]
#[test]
fn a_view_only_role_is_still_refused_a_plan_edit_by_the_handler() {
    // `can_edit` is an affordance, never a gate. RBAC is enforced by the server BEFORE the
    // handler runs, so this asserts the property at the layer a client actually meets: a Viewer
    // that ignores the field and sends a plan edit is refused by `authorize`, and the handler
    // never sees it.
    use selahcue_lan::rbac::authorize;
    use selahcue_lan::Role;

    for role in [Role::Producer, Role::Assistant, Role::Viewer] {
        for cmd in [
            Command::PublishPlan,
            Command::NewPlan {
                name: "Next Week".into(),
            },
            Command::ImportPlan {
                name: "Imported".into(),
                items: vec![item("song", "Opening")],
            },
        ] {
            assert!(
                !authorize(role, &cmd),
                "{role:?} was authorized {cmd:?} — the view-only affordance is not a substitute \
                 for the gate, and the gate is what actually protects the plan"
            );
        }
    }
}

#[test]
fn duplicating_to_the_same_name_is_a_true_no_op_and_keeps_the_live_row_marked() {
    // Reachable by clicking Duplicate and leaving the pre-filled name alone: the copy equals the
    // current plan in every field, so the command must do nothing at all.
    //
    // Without the identity guard in `install_plan` the cursors would still be reset — dropping
    // the LIVE row marking and clearing Preview — while `apply`'s undo block skipped the
    // snapshot, because it asks `self.plan != before` and the plan did not change. The operator
    // would lose the marking with no undo entry to take it back.
    let (mut c, ids) = controller();
    go_live(&mut c, ids[0]);
    let live_before = c.live_index();
    assert_eq!(
        live_before,
        Some(0),
        "the fixture must have a live row to lose"
    );
    let revision_before = publish(&c).revision;

    assert_eq!(
        c.apply(&Command::DuplicatePlan {
            name: c.plan().name.clone()
        }),
        ControllerReply::Ack,
        "an identical duplicate is accepted — it is a no-op, not an error"
    );

    assert_eq!(
        c.live_index(),
        live_before,
        "the live row marking was dropped by a replacement that changed nothing"
    );
    assert_eq!(
        c.operator_view().live_free_text,
        None,
        "the live item was demoted to a free slide even though it is still a plan row"
    );
    assert_eq!(
        publish(&c).revision,
        revision_before,
        "a no-op replacement must not move the revision, or it would raise a change badge for \
         an edit that did not happen"
    );

    // POSITIVE CONTROL: a duplicate under a DIFFERENT name is still a real replacement, so the
    // guard above is not simply disabling the command.
    assert_eq!(
        c.apply(&Command::DuplicatePlan {
            name: "Sunday (copy)".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().name, "Sunday (copy)");
    assert_eq!(
        c.live_index(),
        None,
        "a real replacement still drops the cursors"
    );
}
