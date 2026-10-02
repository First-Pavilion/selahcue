//! Fitting a plan's scripture links to their chapters must not decode a bible (86ak84fbd).
//!
//! A whole-chapter link (`Psalms 1`) and a range (`Psalms 1:2-10`) are fitted to the chapter's real
//! last verse — when a stored plan loads (`LiveController::new`) and on every link edit
//! (`SetItemContent`). The fit only needs two numbers per chapter, but it used to read them by
//! decoding the whole translation (≈4 MB of text) per translation the plan names: a plan of five
//! translations paid ≈140 ms of CPU at controller start-up before the operator saw anything. The
//! fit now reads the compile-time verse-run table, the same one the operator view's link status
//! uses, so this file asserts the plan loads, edits and renders without ever touching the corpus.
//!
//! Correctness is the other half and is NOT negotiable: the last phase checks every fitted
//! reference against the corpus's own lookup, so a "fix" that stopped fitting would pass the
//! laziness half and fail this one.
//!
//! One test, in its own binary, on purpose: the verse indices are process-wide `OnceLock`s, so "was
//! this translation decoded?" only means something if nothing else in the process touched it. The
//! last phase decodes each translation in turn as the positive control (see
//! `test_scripture_link_resolution_is_lazy.rs`, whose shape this follows).

#![allow(clippy::unwrap_used)]

use selahcue_app::{ControllerReply, LiveController};
use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
use selahcue_core::scripture::parse_one;
use selahcue_lan::protocol::{Command, ContentLinkView};
use selahcue_present::Theme;
use selahcue_scripture::{is_index_loaded, verses_in, Translation};

/// Every translation compiled into the binary, derived rather than listed: a sixth bundled
/// translation joins this plan, this laziness check and the positive control automatically.
fn bundled() -> Vec<Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
        .collect()
}

/// A short chapter, a chapter with a verse missing in most translations, and a whole chapter that
/// is long enough that its explicit range is obviously not the verse the operator typed.
const CHAPTER: &str = "Psalms 1";
const GAPPED_CHAPTER: &str = "Luke 17";
const OVERLONG: &str = "Psalms 1:2-200";
const IN_RANGE: &str = "Romans 8:28-30";
const SINGLE_VERSE: &str = "John 3:16";

/// The stored shapes a plan can hold: `(reference, expects a rewrite)`.
const STORED: [(&str, bool); 5] = [
    (CHAPTER, true),
    (GAPPED_CHAPTER, true),
    (OVERLONG, true),
    (IN_RANGE, false),
    (SINGLE_VERSE, false),
];

fn assert_no_translation_decoded(when: &str) {
    for t in bundled() {
        assert!(
            !is_index_loaded(t),
            "{when}: the {} corpus was decoded — fitting a plan's links must not decompress a bible",
            t.code()
        );
    }
}

/// A plan as storage hands it over: every shape above in every bundled translation, none of it
/// fitted yet (written straight into the item, not through the controller).
fn stored_plan() -> ServicePlan {
    let mut plan = ServicePlan::new("Sunday");
    for t in bundled() {
        for (reference, _) in STORED {
            let id = plan.add_item(ItemKind::Scripture, format!("{} {reference}", t.code()));
            plan.get_mut(id).unwrap().content = Some(ItemContent::Scripture {
                reference: reference.into(),
                translation: Some(t.code().to_string()),
                verses_per_slide: None,
                verse_numbers: None,
            });
        }
    }
    plan
}

fn stored_reference(c: &LiveController, index: usize) -> String {
    match &c.plan().items()[index].content {
        Some(ItemContent::Scripture { reference, .. }) => reference.clone(),
        other => panic!("item {index} is not a scripture link: {other:?}"),
    }
}

fn link(reference: &str, translation: &str) -> ContentLinkView {
    ContentLinkView {
        kind: "scripture".into(),
        reference: Some(reference.into()),
        translation: Some(translation.into()),
        verses_per_slide: None,
        id: None,
        slide_count: None,
        verse_numbers: None,
        status: None,
        label: None,
    }
}

#[test]
fn fitting_a_plans_links_decodes_no_translation_and_still_fits_them_exactly() {
    let bundled = bundled();
    assert!(
        bundled.len() >= 5,
        "premise: the five bundled translations are all in the plan"
    );
    // Premise: a cold process. Without it every "still not decoded" below is vacuous.
    assert_no_translation_decoded("before anything ran");

    // 1. A stored plan loads: the load-time fit rewrites the chapter and overlong links, and reads
    //    two numbers from the verse-run table to do it.
    let plan = stored_plan();
    let mut c = LiveController::new(plan, 320, 180, Theme::dark());
    assert_no_translation_decoded("after LiveController::new fitted a stored plan");

    // The fit really ran (so "nothing decoded" is not "nothing happened"): the load marked the
    // plan dirty. Whether each reference came out RIGHT is checked against the corpus at the end.
    assert!(
        c.take_plan_dirty(),
        "premise: the plan held links that needed fitting, so loading it queued a save"
    );
    assert_ne!(
        stored_reference(&c, 0),
        CHAPTER,
        "premise: a chapter link was rewritten"
    );

    // 2. The operator view and a Blackout, the emergency path.
    let view = c.operator_view();
    assert_eq!(view.items.len(), bundled.len() * STORED.len());
    assert_no_translation_decoded("after the operator view");

    // 3. Editing a link through the wire command: every shape, in every translation. The edit-time
    //    fit is the same function as the load-time one but a different call site.
    let first_item = c.plan().items()[0].id.0;
    for t in &bundled {
        for (reference, _) in STORED {
            let reply = c.apply(&Command::SetItemContent {
                item_id: first_item,
                link: Some(link(reference, t.code())),
            });
            assert_eq!(
                reply,
                ControllerReply::Ack,
                "linking {reference} in {}",
                t.code()
            );
        }
    }
    assert_no_translation_decoded("after linking every shape in every translation");

    // 4. Fitting is correct, and the corpus agrees. This is the positive control and the oracle in
    //    one: it decodes translations one at a time (the first thing in this file that may), and
    //    requires `is_index_loaded` to flip for exactly the translation just touched — a slip in
    //    any arm of that accessor would leave a translation reading "not loaded" after a real
    //    decode and the laziness assertions above would be blind to it.
    let last_verse = |t: Translation, chapter: &str| -> u16 {
        verses_in(t, &parse_one(chapter).unwrap())
            .last()
            .expect("the chapter exists")
            .verse
    };
    for (i, t) in bundled.iter().enumerate() {
        let psalm_last = last_verse(*t, CHAPTER);
        let luke_last = last_verse(*t, GAPPED_CHAPTER);
        for (j, u) in bundled.iter().enumerate() {
            assert_eq!(
                is_index_loaded(*u),
                j <= i,
                "after reading {}'s chapters: is_index_loaded({}) is wrong",
                t.code(),
                u.code()
            );
        }
        assert!(
            psalm_last < 200 && luke_last > 30,
            "premise: the chapters are what the test assumes"
        );

        let expected = [
            format!("Psalms 1:1-{psalm_last}"),
            format!("Luke 17:1-{luke_last}"),
            format!("Psalms 1:2-{psalm_last}"),
            IN_RANGE.to_string(),
            SINGLE_VERSE.to_string(),
        ];
        // Re-fit from the same stored shapes, now that the corpus is warm: the table-driven answer
        // given cold above must be the answer the corpus gives. Items were written in
        // (translation, shape) order, so a fresh controller's items line up with `expected`.
        let fresh = LiveController::new(stored_plan(), 320, 180, Theme::dark());
        for (k, want) in expected.iter().enumerate() {
            let index = i * STORED.len() + k;
            assert_eq!(
                &stored_reference(&fresh, index),
                want,
                "{}: stored {:?} must be fitted to {want}",
                t.code(),
                STORED[k].0
            );
        }
    }
}
