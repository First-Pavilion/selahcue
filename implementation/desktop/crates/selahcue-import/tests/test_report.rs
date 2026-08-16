//! The report's own predicates: the severity tiers and the two overflow counters.
//!
//! `severity()` is the product decision made concrete — which losses are loud enough to open a
//! panel and which are not — and it is deliberately computed once here rather than re-derived in
//! the webview. Three of its five thresholds had no test at all, so a boundary could move by one
//! and nothing would notice.
//!
//! The reports are built directly rather than parsed out of an archive, on purpose: a threshold is
//! a boundary, and a boundary is only tested by sitting on both sides of it. Driving a `.pptx`
//! that drops exactly a quarter of its images and then exactly one more is theatre around an
//! arithmetic comparison.

#![allow(clippy::unwrap_used)]

use selahcue_import::{
    ImportReport, ImportSource, Notice, Severity, SkipKind, SkippedItem, TruncatedField, Truncation,
};

fn report() -> ImportReport {
    ImportReport {
        source: ImportSource::Pptx {
            name: "Report".into(),
        },
        slides_imported: 10,
        slides_in_source: Some(10),
        images_imported: 0,
        notes_imported: 0,
        skipped: Vec::new(),
        skipped_overflow: 0,
        truncations: Vec::new(),
        truncations_overflow: 0,
        notices: vec![Notice::ThemeReplaced],
    }
}

fn dropped_image() -> SkippedItem {
    SkippedItem {
        slide_index: Some(0),
        kind: SkipKind::ImageUnreadable,
        detail: String::new(),
    }
}

#[test]
fn nothing_lost_is_lossless_and_a_clean_import_feels_clean() {
    let r = report();
    assert!(r.is_lossless());
    assert_eq!(r.severity(), Severity::Lossless);
    // The standing theme notice is not a loss and must never make one.
    assert_eq!(r.notices, vec![Notice::ThemeReplaced]);
}

#[test]
fn a_quarter_of_the_imagery_is_partial_and_more_than_a_quarter_is_material() {
    // The threshold is "more than a quarter", tested on both sides of the boundary — the only way
    // an off-by-one in `dropped * 4 > referenced` can be caught. Twelve dropped of forty-eight
    // referenced is exactly a quarter and stays `Partial`; thirteen is over and escalates.
    let mut at = report();
    at.images_imported = 36;
    at.skipped = std::iter::repeat_with(dropped_image).take(12).collect();
    assert_eq!(
        at.severity(),
        Severity::Partial,
        "exactly a quarter of the imagery is a visible loss, not a hidden one"
    );

    let mut over = report();
    over.images_imported = 35;
    over.skipped = std::iter::repeat_with(dropped_image).take(13).collect();
    assert_eq!(
        over.severity(),
        Severity::Material,
        "past a quarter the deck is not the deck the author made"
    );

    // And the ratio is over IMAGERY, not over the whole report: a deck that drops thirteen charts
    // and no images is still Partial, or every chart-heavy deck would open a panel.
    let mut charts = report();
    charts.images_imported = 35;
    charts.skipped = std::iter::repeat_with(|| SkippedItem {
        slide_index: Some(0),
        kind: SkipKind::Chart,
        detail: String::new(),
    })
    .take(13)
    .collect();
    assert_eq!(charts.severity(), Severity::Partial);
}

#[test]
fn a_deck_with_no_imagery_at_all_never_divides_by_its_absence() {
    let mut r = report();
    r.skipped = vec![SkippedItem {
        slide_index: Some(0),
        kind: SkipKind::Table,
        detail: String::new(),
    }];
    assert_eq!(r.severity(), Severity::Partial);
}

#[test]
fn both_overflow_counters_are_losses_and_both_escalate() {
    // `skipped_overflow` had a test; `truncations_overflow` had none — zero hits across the whole
    // suite — even though it exists for the case that is easier to miss: a deck that cut text on
    // more than a hundred slides used to report the first hundred and drop the rest in silence.
    for (label, r) in [
        (
            "skipped",
            ImportReport {
                skipped_overflow: 1,
                ..report()
            },
        ),
        (
            "truncations",
            ImportReport {
                truncations_overflow: 1,
                ..report()
            },
        ),
    ] {
        assert!(
            !r.is_lossless(),
            "{label}: an overflowed counter is a loss, whatever the lists say"
        );
        assert_eq!(
            r.severity(),
            Severity::Material,
            "{label}: past the cap we can no longer even say WHICH slides lost content"
        );
    }
}

#[test]
fn cut_body_text_is_material_and_cut_notes_are_not() {
    // Body text is on the audience screen; notes are not. The tiers spend intrusiveness only where
    // a preview is blind, so this pair has to stay apart.
    let cut = |what| ImportReport {
        truncations: vec![Truncation {
            slide_index: 0,
            what,
            kept: 10,
            dropped: 10,
        }],
        ..report()
    };
    assert_eq!(cut(TruncatedField::BodyLine).severity(), Severity::Material);
    assert_eq!(
        cut(TruncatedField::BodyLines).severity(),
        Severity::Material
    );
    assert_eq!(cut(TruncatedField::Notes).severity(), Severity::Partial);
    assert_eq!(cut(TruncatedField::Title).severity(), Severity::Partial);
}

#[test]
fn an_inferred_slide_order_is_material_even_when_nothing_was_lost() {
    // The one Material predicate that is a NOTICE rather than a drop, and the reason the tier is
    // computed before the lossless short-circuit. Twenty-four slides in the wrong order loses
    // nothing and is still the most dangerous outcome here, because a preview cannot reveal it.
    let mut r = report();
    r.notices.push(Notice::SlideOrderInferred);
    assert!(r.is_lossless(), "premise: nothing was dropped or cut");
    assert_eq!(r.severity(), Severity::Material);
}

#[test]
fn every_skip_kind_carries_a_stable_tag_and_a_sentence() {
    // The UI groups and counts on the tag, so a collision would silently merge two different
    // losses into one line — and a drop with no sentence is a drop the operator cannot act on.
    let kinds = [
        SkipKind::Chart,
        SkipKind::Table,
        SkipKind::SmartArt,
        SkipKind::OleObject,
        SkipKind::UnsupportedGraphic,
        SkipKind::HiddenSlide,
        SkipKind::NestedContainer,
        SkipKind::ExternalImage,
        SkipKind::DuplicatePart,
        SkipKind::MalformedEntryName,
        SkipKind::DoctypeRejected,
        SkipKind::ImageFormatUnsupported,
        SkipKind::ImageColourUnsupported,
        SkipKind::ImageVariantUnsupported,
        SkipKind::ImageUnreadable,
        SkipKind::ImageTooLarge,
        SkipKind::MediaBudgetExhausted,
        SkipKind::LibraryFull,
        SkipKind::MediaCommitFailed,
        SkipKind::UnreadablePart,
        SkipKind::SlideOutOfBounds,
        SkipKind::LimitReached(selahcue_import::LimitKind::Slides),
    ];
    let mut tags: Vec<&str> = kinds.iter().map(|k| k.tag()).collect();
    tags.sort_unstable();
    let before = tags.len();
    tags.dedup();
    assert_eq!(before, tags.len(), "two kinds share a tag: {tags:?}");
    for k in kinds {
        assert!(!k.message().trim().is_empty(), "{:?} has no sentence", k);
    }
}
