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
//! it. The final phase deliberately presents each translation's linked passage in turn as the
//! positive control, one per bundled translation.

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController, OperatorShell};
use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_present::Theme;
use selahcue_scripture::{is_index_loaded, Translation};
use std::sync::{Arc, Mutex};

/// Every translation compiled into the binary, derived rather than listed: a sixth bundled
/// translation joins this plan, this laziness check, and the per-translation positive control
/// automatically.
fn bundled() -> Vec<Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
        .collect()
}

/// One link in the plan under test: `(title, reference, translation code, expected status tag on
/// the wire)`. `None` is the healthy case — `Resolved` is the absent status, so a good link stays
/// byte-identical to a pre-status host's frame.
type Link = (String, &'static str, String, Option<&'static str>);

fn links() -> Vec<Link> {
    let mut v: Vec<Link> = Vec::new();
    // One real passage in each bundled translation — the plan the ticket measured. These come
    // FIRST and in `bundled()` order: the positive control below presents them in that order.
    for t in bundled() {
        v.push((
            format!("john-{}", t.code().to_lowercase()),
            "John 3:16",
            t.code().to_string(),
            None,
        ));
    }
    let tail: &[(&str, &'static str, &str, Option<&'static str>)] = &[
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
    for (title, reference, code, status) in tail {
        v.push((
            (*title).to_string(),
            *reference,
            (*code).to_string(),
            *status,
        ));
    }
    v
}

fn shell(links: &[Link]) -> (OperatorShell, Arc<Mutex<LiveController>>, Vec<u64>) {
    let mut plan = ServicePlan::new("Sunday");
    let mut ids = Vec::new();
    for (title, reference, translation, _) in links {
        let id = plan.add_item(ItemKind::Scripture, title.as_str());
        plan.set_item_content(
            id,
            Some(ItemContent::Scripture {
                reference: (*reference).into(),
                translation: Some(translation.clone()),
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
    for t in bundled() {
        assert!(
            !is_index_loaded(t),
            "{when}: the {} corpus was decoded — resolving a plan's links must not decompress a bible",
            t.code()
        );
    }
}

#[test]
fn the_operator_view_resolves_every_link_without_decoding_a_translation() {
    let bundled = bundled();
    let links = links();
    assert!(
        bundled.len() >= 5,
        "premise: the five bundled translations are all in the plan"
    );

    // Premise: a cold process. Without it every "still not decoded" below is vacuous.
    assert_no_translation_decoded("before anything ran");

    let (shell, controller, ids) = shell(&links);
    assert_no_translation_decoded("after building the plan and the controller");

    let expected: Vec<Option<String>> = links
        .iter()
        .map(|(_, _, _, status)| status.map(str::to_string))
        .collect();
    let expected_missing = expected.iter().flatten().count() as u32;
    assert!(
        expected_missing >= 5 && (expected_missing as usize) < links.len(),
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
    let nonsense = links.iter().position(|l| l.0 == "nonsense").unwrap();
    shell.select(ids[nonsense]);
    assert_no_translation_decoded("after staging a link that does not parse");

    // Positive control, ONE PER BUNDLED TRANSLATION: PRESENTING a linked passage is what
    // legitimately decodes its translation, and only that one. Present each translation's
    // `John 3:16` in turn and require `is_index_loaded` to flip for exactly that translation. If
    // this failed for any translation, `is_index_loaded` would be blind to it and every "not
    // decoded" above would prove nothing about it — a copy-paste slip in one arm must not hide.
    for (i, t) in bundled.iter().enumerate() {
        assert_eq!(
            links[i].2,
            t.code(),
            "premise: link #{i} is {}'s John 3:16",
            t.code()
        );
        shell.select(ids[i]);
        let live = shell.go_live();
        for (j, u) in bundled.iter().enumerate() {
            assert_eq!(
                is_index_loaded(*u),
                j <= i,
                "after presenting {}'s passage, is_index_loaded({}) is wrong — presenting decodes \
                 exactly the translation shown",
                t.code(),
                u.code()
            );
        }
        // …and the verdicts are unchanged by a passage having been loaded.
        assert_eq!(
            statuses(&live),
            expected,
            "verdicts after presenting a {} passage",
            t.code()
        );
    }
}
