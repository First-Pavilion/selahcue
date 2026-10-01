//! Resolving a plan's scripture links on the operator view-build path must not decode a bible
//! (86ak84fbd).
//!
//! `OperatorShell::act()` rebuilds the operator view after EVERY command — Blackout and Clear
//! included — and `GetOperatorState` (the mobile controller's snapshot) builds the same view.
//! The view resolves each linked item. When that probe decoded the bundled corpus, the first
//! press of an emergency control paid for one whole translation per distinct translation the
//! plan names (≈68 ms for one, ≈260 ms for five, debug build) against a 200 ms budget, while the
//! controller mutex was held.
//!
//! Correctness is the other half and is NOT negotiable: the probe exists because a link that
//! parses but names no verse (`Jude 2:1`) used to be reported healthy. So this file asserts the
//! verdicts as hard as it asserts the laziness — a "fix" that stopped probing would pass the
//! second and fail the first.
//!
//! One test, in its own binary, on purpose: the verse indices are process-wide `OnceLock`s, so
//! "was this translation decoded?" only means something if nothing else in the process touched
//! it. The final phase deliberately presents a linked passage as the positive control.

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController, OperatorShell};
use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_present::Theme;
use selahcue_scripture::{is_index_loaded, Translation};
use std::sync::{Arc, Mutex};

const BUNDLED: [Translation; 5] = [
    Translation::Kjv,
    Translation::Web,
    Translation::Asv,
    Translation::Webbe,
    Translation::Dby,
];

/// `(title, reference, translation code, expected status tag on the wire)`. `None` is the
/// healthy case: `Resolved` is the absent status, so a good link stays byte-identical to a
/// pre-status host's frame.
const LINKS: &[(&str, &str, &str, Option<&str>)] = &[
    // One real passage in each bundled translation — the plan the ticket measured.
    ("john-kjv", "John 3:16", "KJV", None),
    ("john-web", "John 3:16", "WEB", None),
    ("john-asv", "John 3:16", "ASV", None),
    ("john-webbe", "John 3:16", "WEBBE", None),
    ("john-dby", "John 3:16", "DBY", None),
    // Well-formed, names nothing — the defect 1840f1c fixed must stay fixed.
    ("jude-2", "Jude 2:1", "KJV", Some("missing")),
    ("romans-99", "Romans 99:1", "WEB", Some("missing")),
    ("ps-151", "Psalm 151:1", "ASV", Some("missing")),
    // Does not even parse.
    ("nonsense", "Hezekiah 4:4", "KJV", Some("missing")),
    // Versification differs by translation: Luke 17:36 is in the KJV and not in the WEB.
    ("luke-kjv", "Luke 17:36", "KJV", None),
    ("luke-web", "Luke 17:36", "WEB", Some("missing")),
    // The verse AFTER the WEB's gap is real — a verse-count probe (36) would call it missing.
    ("luke-web-37", "Luke 17:37", "WEB", None),
];

fn shell() -> (OperatorShell, Arc<Mutex<LiveController>>, Vec<u64>) {
    let mut plan = ServicePlan::new("Sunday");
    let mut ids = Vec::new();
    for (title, reference, translation, _) in LINKS {
        let id = plan.add_item(ItemKind::Scripture, *title);
        plan.set_item_content(
            id,
            Some(ItemContent::Scripture {
                reference: (*reference).into(),
                translation: Some((*translation).into()),
                verses_per_slide: None,
                verse_numbers: None,
            }),
        )
        .unwrap();
        ids.push(id.0);
    }
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    )));
    (OperatorShell::new(Arc::clone(&controller)), controller, ids)
}

fn statuses(view: &selahcue_app::OperatorView) -> Vec<Option<String>> {
    view.items
        .iter()
        .map(|i| {
            i.link
                .as_ref()
                .expect("every item here is linked")
                .status
                .clone()
        })
        .collect()
}

fn assert_no_translation_decoded(when: &str) {
    for t in BUNDLED {
        assert!(
            !is_index_loaded(t),
            "{when}: the {} corpus was decoded — resolving a plan's links must not decompress a bible",
            t.code()
        );
    }
}

#[test]
fn the_operator_view_resolves_every_link_without_decoding_a_translation() {
    // Premise: a cold process. Without it every "still not decoded" below is vacuous.
    assert_no_translation_decoded("before anything ran");

    let (shell, controller, ids) = shell();
    assert_no_translation_decoded("after building the plan and the controller");

    let expected: Vec<Option<String>> = LINKS
        .iter()
        .map(|(_, _, _, status)| status.map(str::to_string))
        .collect();
    let expected_missing = expected.iter().flatten().count() as u32;
    assert!(
        expected_missing >= 5 && (expected_missing as usize) < LINKS.len(),
        "premise: the plan mixes healthy and broken links"
    );

    // 1. The plain view (initial render / refresh / `GetOperatorState`).
    let view = shell.view();
    assert_eq!(
        statuses(&view),
        expected,
        "link verdicts on the initial view"
    );
    assert_eq!(
        view.summary.as_ref().unwrap().missing,
        expected_missing,
        "the plan summary's missing count must agree with the rows beside it"
    );
    assert_no_translation_decoded("after the first operator view");

    // 2. The emergency controls — the path the ticket measured. Each rebuilds the view.
    let after_blackout = shell.blackout(true);
    assert_eq!(
        statuses(&after_blackout),
        expected,
        "verdicts after Blackout"
    );
    assert_no_translation_decoded("after the first Blackout");
    let after_clear = shell.clear();
    assert_eq!(statuses(&after_clear), expected, "verdicts after Clear");
    shell.blackout(false);
    assert_no_translation_decoded("after Blackout and Clear");

    // 3. The mobile controller's snapshot builds the very same view, through the very same path.
    let reply = controller.lock().unwrap().apply(&Command::GetOperatorState);
    let ControllerReply::Message(ServerMessage::OperatorState { view: wire }) = reply else {
        panic!("GetOperatorState must answer with the operator state");
    };
    assert_eq!(wire.summary.as_ref().unwrap().missing, expected_missing);
    assert_no_translation_decoded("after GetOperatorState");

    // 4. Staging an item composes its preview. A link that does not even PARSE presents a bare
    //    title and needs no corpus, so it is safe to stage here. (Staging a link that parses —
    //    even `Jude 2:1` — looks the passage up to render it, which legitimately decodes that
    //    translation; presenting one is the positive control below.)
    let nonsense = ids[8];
    shell.select(nonsense);
    assert_no_translation_decoded("after staging a link that does not parse");

    // Positive control: PRESENTING a linked passage is what legitimately decodes its translation,
    // and only that one. If this failed, `is_index_loaded` would be blind and everything above
    // would prove nothing.
    shell.select(ids[1]); // John 3:16 in the WEB
    let live = shell.go_live();
    assert!(
        is_index_loaded(Translation::Web),
        "staging + going live on a WEB link must decode the WEB (positive control)"
    );
    for t in [
        Translation::Kjv,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
    ] {
        assert!(
            !is_index_loaded(t),
            "presenting a WEB passage must not decode the {} corpus",
            t.code()
        );
    }
    // …and the verdicts are unchanged by the passage now being loaded.
    assert_eq!(
        statuses(&live),
        expected,
        "verdicts after presenting a passage"
    );
}
