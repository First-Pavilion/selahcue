//! The operator view's verdict on a scripture link must equal what the renderer ACTUALLY
//! presents for that link (86ak84fbd; differential adapted from QA's end-to-end sweep on PR #141).
//!
//! The probe behind the verdict (`host_resolution` → `passage_exists_in`) and the renderer
//! (`item_slide` → `scripture_slide_in` → `verses_in`) each map a link's translation code to a
//! `Translation` on their own, and they must map it the SAME way — in particular for the codes
//! that are not a bundled translation: an absent code, an empty one, and one nobody has heard of
//! all fall back to the product default (KJV), in both places. If the probe's fallback drifted to
//! another translation, a link would be reported healthy while presenting nothing (or missing
//! while presenting fine), and no other test here would notice, because every other test names a
//! real translation. `Luke 17:36` and `Acts 8:37` are the discriminating references: the KJV has
//! them and the WEB, ASV and WEBBE do not.
//!
//! The dangerous direction is HEALTHY-BUT-BLANK: the operator is told the passage is fine and
//! the audience gets a title card.

#![allow(clippy::unwrap_used)]

use selahcue_app::{LiveController, OperatorShell};
use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};

/// The translation codes a plan can carry. The first three are the "unknown" ones the host must
/// resolve to the default; `kjv` is a lower-case spelling of a real code.
const TRANSLATIONS: &[Option<&str>] = &[
    None,
    Some(""),
    Some("BOGUS"),
    Some("kjv"),
    Some("KJV"),
    Some("WEB"),
    Some("ASV"),
    Some("WEBBE"),
    Some("DBY"),
    // Downloadable and, in this build, not downloaded: nothing presents, nothing resolves.
    Some("YLT"),
];

const REFS: &[&str] = &[
    // Healthy in every bundled translation.
    "John 3:16",
    "Psalm 23",
    "Jude 1:1",
    // Present in some translations and absent in others (versification gaps).
    "Luke 17:36",
    "Luke 17:36-37",
    "Acts 8:37",
    "Matthew 17:21",
    // Well-formed but naming nothing — what the corpus probe exists to catch.
    "Jude 2:1",
    "Romans 99:1",
    "Psalm 151:1",
    "John 3:99",
    // Does not even parse.
    "not a reference",
];

/// Build a one-item plan linking `reference` in `translation`, put that item live, and return
/// `(the view's status for it, whether the live slide has verse text in its body)`.
fn verdict_and_presentation(reference: &str, translation: Option<&str>) -> (Option<String>, bool) {
    let mut plan = ServicePlan::new("Sunday");
    let id = plan.add_item(ItemKind::Scripture, "item");
    plan.set_item_content(
        id,
        Some(ItemContent::Scripture {
            reference: reference.into(),
            translation: translation.map(str::to_string),
            verses_per_slide: None,
            verse_numbers: None,
        }),
    )
    .unwrap();
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    )));
    let shell = OperatorShell::new(Arc::clone(&controller));

    // The verdict is read BEFORE anything is presented, so it cannot lean on a loaded index.
    let status = shell
        .view()
        .items
        .iter()
        .find(|i| i.id == id.0)
        .and_then(|i| i.link.as_ref())
        .expect("the item is linked")
        .status
        .clone();

    shell.select(id.0);
    shell.go_live();
    let has_body = controller
        .lock()
        .unwrap()
        .presenter()
        .live_slide()
        .map(|s| !s.body.is_empty())
        .expect("something is live");
    (status, has_body)
}

#[test]
fn the_view_verdict_equals_what_the_renderer_presents_for_every_case() {
    let mut healthy_but_blank = Vec::new();
    let mut missing_but_renders = Vec::new();
    let (mut healthy, mut missing) = (0usize, 0usize);

    for translation in TRANSLATIONS {
        for reference in REFS {
            let (status, has_body) = verdict_and_presentation(reference, *translation);
            let is_healthy = status.is_none();
            if is_healthy {
                healthy += 1;
            } else {
                assert_eq!(
                    status.as_deref(),
                    Some("missing"),
                    "{reference:?} {translation:?}: a scripture link is healthy or missing, never unknown"
                );
                missing += 1;
            }
            if is_healthy && !has_body {
                healthy_but_blank.push(format!("{reference:?} {translation:?}"));
            }
            if !is_healthy && has_body {
                missing_but_renders.push(format!("{reference:?} {translation:?}"));
            }
        }
    }

    assert!(
        healthy_but_blank.is_empty(),
        "the view says healthy but the renderer shows a bare title for:\n{}",
        healthy_but_blank.join("\n")
    );
    assert!(
        missing_but_renders.is_empty(),
        "the view says missing but the renderer shows verse text for:\n{}",
        missing_but_renders.join("\n")
    );
    // Both outcomes were exercised, or "they agreed" could mean "both said nothing".
    assert!(
        healthy >= 40 && missing >= 40,
        "the sweep must exercise both verdicts (healthy {healthy}, missing {missing})"
    );
}

#[test]
fn an_unknown_translation_code_resolves_to_the_default_in_both_the_view_and_the_renderer() {
    // Luke 17:36 and Acts 8:37 exist in the KJV (the default) and not in the WEB, ASV or WEBBE,
    // so a host that fell back to any of those would call them missing — while the renderer,
    // falling back to the KJV, presents them. Pin BOTH halves, by name.
    for translation in [None, Some(""), Some("BOGUS")] {
        for reference in ["Luke 17:36", "Acts 8:37"] {
            let (status, has_body) = verdict_and_presentation(reference, translation);
            assert_eq!(
                status, None,
                "{reference} with translation {translation:?} falls back to the KJV, which has it, so the view must call it healthy"
            );
            assert!(
                has_body,
                "{reference} with translation {translation:?} falls back to the KJV, so the renderer must present verse text, not a bare title"
            );
        }
    }
    // Control: the same references in a translation that really lacks them are missing AND blank,
    // so the assertions above are not satisfied by a probe that says "healthy" to everything.
    for reference in ["Luke 17:36", "Acts 8:37"] {
        let (status, has_body) = verdict_and_presentation(reference, Some("WEB"));
        assert_eq!(
            status.as_deref(),
            Some("missing"),
            "{reference} is absent from the WEB"
        );
        assert!(
            !has_body,
            "{reference} is absent from the WEB, so it is title-only"
        );
    }
}
