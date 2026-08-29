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
use selahcue_core::plan::{ItemKind, ServicePlan, MAX_PLAN_ITEMS, MAX_PLAN_LABEL_LEN};
use selahcue_lan::protocol::{Command, DenyReason, ImportItemView};
use selahcue_present::Theme;

/// The battery below distinguishes "at the cap" from "one over the cap", which is only a real
/// distinction while the cap leaves room for both. Pinned at compile time so shrinking the cap
/// to 0 or 1 fails the build instead of quietly turning the test vacuous.
const _: () = assert!(
    MAX_PLAN_ITEMS >= 2,
    "the import cap test needs a cap with room below it"
);
/// Likewise the name battery builds a name of exactly `MAX_PLAN_LABEL_LEN + 1` characters and
/// expects it refused while `MAX_PLAN_LABEL_LEN` is accepted.
const _: () = assert!(
    MAX_PLAN_LABEL_LEN >= 2,
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
fn a_replacement_that_changes_the_run_sheet_keeps_the_live_slide_on_air() {
    // NFR-024 / FR-012: a coordinator starting next week's run sheet must not blank the service
    // that is running. These three bring a DIFFERENT run sheet, so the outgoing rows are gone and
    // the cursors cannot survive. `DuplicatePlan` is deliberately not here — its rows are the
    // same rows, and it has its own test below.
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
        // POSITIVE CONTROL: the run sheet really did change. Without it, "Live unchanged" is the
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
            "{label} left a plan row marked LIVE after bringing a different run sheet; the \
             incoming rows are unrelated to the outgoing ones, so a clamped index reports an \
             item the audience has never seen"
        );
        assert_eq!(
            view.live_free_text,
            Some(live_title),
            "{label} lost the on-air slide's identity — it must carry over as a free live slide, \
             the same way removing the live item does"
        );
    }
}

#[test]
fn duplicating_mid_service_keeps_the_on_air_row_marked_and_navigable() {
    // `ServicePlan::duplicate` clones every item and changes only the name, so the incoming rows
    // ARE the outgoing rows. Treating that as an unrelated document un-marks the row that is on
    // air, demotes it to a free slide, and resets `live_slide` to 0 — after which `Next` stops
    // advancing the song the audience is hearing. Found by code review of PR #14; the earlier
    // version of this suite asserted the broken behaviour as correct.
    let (mut c, ids) = controller();
    go_live(&mut c, ids[0]);
    let pixels_before = c.presenter().live_output().bytes().to_vec();

    assert_eq!(
        c.apply(&Command::DuplicatePlan {
            name: "Next Week".into()
        }),
        ControllerReply::Ack
    );

    let view = c.operator_view();
    // POSITIVE CONTROL: this really was a replacement, not a no-op short-circuited by the
    // identity guard — the name changed.
    assert_eq!(view.plan_name, "Next Week", "the duplicate did not install");
    assert_eq!(
        c.presenter().live_output().bytes(),
        pixels_before.as_slice(),
        "duplicating changed the audience output"
    );
    assert_eq!(
        view.live_index,
        Some(0),
        "duplicating un-marked the row that is on air, over a run sheet identical to the one it \
         replaced"
    );
    assert_eq!(
        view.live_free_text, None,
        "the live item was demoted to a free slide even though it is still a plan row"
    );
    assert_eq!(
        c.plan().items()[0].title,
        "Opening Song",
        "the duplicate must carry the same rows in the same order"
    );
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
    let too_long: String = "x".repeat(MAX_PLAN_LABEL_LEN + 1);
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
            "control character in an owner",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "song".into(),
                    title: "Opening".into(),
                    // Non-blank, so it is not skipped as unassigned, and on a triggerable item,
                    // so the divider rule cannot pre-empt the label rule.
                    owner: Some("A\u{7}da".into()),
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
        // The three below are one rule — invisible formatting (Cf) — reached on both the plan
        // name and the item title. `char::is_control` is Cc only and lets every one of them
        // through, which is the gap security review found. Each is otherwise well-formed:
        // non-blank, in bounds, valid kind.
        (
            "right-to-left override in the plan name",
            Command::NewPlan {
                name: "Sun\u{202E}day".into(),
            },
        ),
        (
            "an item title that is only a zero-width space",
            Command::ImportPlan {
                name: "Valid Name".into(),
                // Not blank by `trim` — U+200B is not White_Space — so the non-blank check
                // passes it and only the invisible-formatting rule refuses it. It would render
                // as an empty row.
                items: vec![item("song", "\u{200B}")],
            },
        ),
        (
            "zero-width joiner homograph in an item title",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", "Open\u{200D}ing")],
            },
        ),
        (
            // A THIRD category: U+2028 is Zl, so neither `is_control` (Cc) nor
            // `is_invisible_formatting` (Cf) covers it. It is `White_Space`, so `trim` strips it
            // at the edges — which is why it has to be embedded here to be exercised at all.
            "line separator embedded in an item title",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", "Sun\u{2028}day")],
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
    let at_bound: String = "x".repeat(MAX_PLAN_LABEL_LEN);
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
            // A spreadsheet export has empty owner cells as a matter of course; the row imports
            // unassigned rather than failing the whole file. Matches `set_item_owner`, which
            // filters a blank owner to `None`.
            "a blank owner cell, meaning unassigned",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![ImportItemView {
                    kind: "song".into(),
                    title: "Opening".into(),
                    owner: Some("   ".into()),
                    planned_secs: None,
                }],
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
        // The spoofing rule must not have swept up legitimate international text. Without this,
        // rejecting the three Cf cases above is indistinguishable from a rule that refuses
        // anything non-ASCII — which would be a worse bug than the one it fixes.
        (
            "a non-Latin plan name",
            Command::NewPlan {
                name: "主日崇拜".into(),
            },
        ),
        (
            "an Arabic plan name with genuine right-to-left text",
            Command::NewPlan {
                name: "خدمة الأحد".into(),
            },
        ),
        (
            "a single emoji, which carries no joiner",
            Command::ImportPlan {
                name: "Valid Name".into(),
                items: vec![item("song", "Opening 🎉")],
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

    // POSITIVE CONTROL: the guard is not simply disabling the command. A duplicate under a
    // DIFFERENT name still installs — the name changes — and a replacement that brings a
    // different run sheet still drops the cursors.
    assert_eq!(
        c.apply(&Command::DuplicatePlan {
            name: "Sunday (copy)".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(c.plan().name, "Sunday (copy)", "the rename did not install");
    assert_eq!(
        c.live_index(),
        Some(0),
        "the rows did not move, so the on-air row must stay marked"
    );
    assert_eq!(
        c.apply(&Command::NewPlan {
            name: "Next Week".into()
        }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.live_index(),
        None,
        "a replacement that DOES change the run sheet must still drop the cursors"
    );
}

#[test]
fn a_replaced_plan_is_a_draft_again_and_never_inherits_the_old_ones_publish_state() {
    // Found by code review of PR #14. Every replacement used to leave the DISCARDED plan's
    // baseline in place, so publishing and then starting a new plan reported `version: 1` and
    // `changed: true` over a run sheet nobody had ever been handed — contradicting what
    // `PublishStateView` says about itself.
    //
    // `DuplicatePlan` is included deliberately: its rows are the same rows, but the copy has
    // never been published under its new name, so it is a draft too.
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
                name: "Next Week".into(),
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
        let (mut c, _) = controller();
        assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);
        // POSITIVE CONTROL: there really is a published baseline to inherit, so "draft" below is
        // a verdict about state that existed rather than state that was never set.
        let published = publish(&c);
        assert_eq!(
            published.version, 1,
            "{label}: nothing was published to inherit"
        );
        assert_eq!(published.published_revision, Some(published.revision));

        assert_eq!(c.apply(&command), ControllerReply::Ack, "{label} refused");

        let after = publish(&c);
        assert_eq!(
            after.published_revision, None,
            "{label}: the discarded plan's baseline outlived it — the new plan reports as having \
             been published when nobody has ever been handed it"
        );
        assert_eq!(
            after.version, 0,
            "{label}: the new plan inherited a version number it never earned"
        );
        assert!(
            !after.changed,
            "{label}: a brand-new plan reports changes to review against a baseline that is not \
             its own"
        );
        assert!(
            after.revision >= published.revision,
            "{label}: the revision went backwards, which would make an up-to-date client believe \
             it was ahead of the host"
        );
    }
}

#[test]
fn an_edit_that_is_reversed_by_a_second_edit_clears_the_badge() {
    // The undo path already proved the badge compares documents. This is the OTHER route to the
    // same place, and `==` got it wrong: adding an item and removing it again leaves the run
    // sheet exactly as published while `next_id` has advanced for good, so a value comparison
    // latched the badge on permanently with nothing behind it for the operator to review.
    let (mut c, _) = controller();
    assert_eq!(c.apply(&Command::PublishPlan), ControllerReply::Ack);

    assert_eq!(
        c.apply(&Command::AddItem {
            kind: "song".into(),
            title: "Temporary".into(),
            content: None
        }),
        ControllerReply::Ack
    );
    let added = publish(&c);
    assert!(added.changed, "the add must raise the badge first");

    let temp_id = c.plan().items().last().unwrap().id.0;
    assert_eq!(
        c.apply(&Command::RemoveItem { item_id: temp_id }),
        ControllerReply::Ack
    );

    let reversed = publish(&c);
    // POSITIVE CONTROL: the removal really moved the document, so "no badge" is a verdict about
    // a comparison that ran.
    assert!(
        reversed.revision > added.revision,
        "the removal did not move the revision, so the comparison was never exercised"
    );
    assert_eq!(
        c.plan().len(),
        2,
        "the run sheet is back to what was published"
    );
    assert!(
        !reversed.changed,
        "the run sheet matches the published one exactly, so there is nothing to review — a \
         badge here is the same empty badge the document comparison exists to prevent"
    );
}

#[test]
fn the_console_shell_can_reach_every_publish_and_lifecycle_action() {
    // The Tauri console drives `OperatorShell`, not `LiveController` directly, so a command with
    // no wrapper here is a command the operator surface cannot invoke however well the protocol
    // and RBAC layers work. Found by code review of PR #14: the wire and the controller were
    // complete while the console seam was missing, which would have left the frontend ticket
    // blocked on a backend that reported itself finished.
    use selahcue_app::OperatorShell;
    use std::sync::{Arc, Mutex};

    let (c, _) = controller();
    let sh = OperatorShell::new(Arc::new(Mutex::new(c)));

    let v = sh.publish_plan();
    let p = v.publish.expect("the shell view must carry publish state");
    assert_eq!(p.version, 1, "publish did not reach the controller");

    let v = sh.new_plan("Next Week");
    assert_eq!(v.plan_name, "Next Week");
    assert_eq!(v.items.len(), 0);
    assert_eq!(
        v.publish.expect("publish state").version,
        0,
        "a replaced plan is a draft again, through the shell as through the wire"
    );

    let template = v.plan_templates.first().expect("templates offered").clone();
    let v = sh.template_plan(&template.id, "From Template");
    assert_eq!(v.plan_name, "From Template");
    assert_eq!(v.items.len() as u32, template.items);

    let v = sh.duplicate_plan("A Copy");
    assert_eq!(v.plan_name, "A Copy");
    assert_eq!(
        v.items.len() as u32,
        template.items,
        "the duplicate carries the same rows"
    );

    let v = sh.import_plan(
        "Imported",
        vec![item("song", "One"), item("section", "Two")],
    );
    assert_eq!(v.plan_name, "Imported");
    assert_eq!(v.items.len(), 2);

    // A refused action returns the unchanged view rather than erroring — the shell's convention
    // for every other command, and what lets the UI simply re-render.
    let v = sh.new_plan("   ");
    assert_eq!(
        v.plan_name, "Imported",
        "a refused lifecycle action must leave the plan alone"
    );
}
