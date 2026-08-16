//! `build_deck` as a **public seam**, not as the tail of a parse.
//!
//! Everything here reaches `build_deck` with a hand-built [`ImportedDocument`], because that is
//! what its signature invites and what its own doc-comments claim to defend against: "the parsers
//! clamp this already; this is the ingress re-check for the seam a caller can reach directly".
//! Driving it only through `read_pptx` proves the parsers' clamps and nothing about the re-check
//! — which is how three of these controls came to ship with no test at all.
//!
//! **The bar, as `test_zip.rs` states it:** each test must FAIL if the control it names is removed.

#![allow(clippy::unwrap_used)]

use selahcue_import::{
    build_deck, ImportSource, ImportedDocument, ImportedSlide, LimitKind, SkipKind, TruncatedField,
};
use selahcue_present::{Element, Theme};

fn doc(slides: Vec<ImportedSlide>) -> ImportedDocument {
    ImportedDocument {
        source: ImportSource::Pptx {
            name: "Caller built".into(),
        },
        slides,
        report: selahcue_import::report::ReportBuilder::new(),
    }
}

fn slide(source_index: usize) -> ImportedSlide {
    ImportedSlide {
        source_index,
        ..Default::default()
    }
}

fn deck_text(deck: &selahcue_present::SlideDeck) -> String {
    deck.slides()
        .iter()
        .flat_map(|s| s.elements.iter())
        .filter_map(|e| match e {
            Element::Text { text, .. } => Some(text.clone()),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join("\n")
}

// --- one index space, on the builder's own truncations ---------------------------------

#[test]
fn the_builders_own_truncations_carry_the_source_index() {
    // The `.pptx` path cannot reach these two: the parser clamps titles to `MAX_TITLE_LEN` and
    // notes to `MAX_IMPORT_NOTES_LEN` before `build_deck` ever sees them, so the title and notes
    // arms of `elements_for`/`fit_notes` are ONLY reachable here. Their indices could be changed
    // to any number at all without failing a test.
    let mut only = slide(41);
    only.title = Some("T".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN + 10));
    only.notes = "N".repeat(selahcue_present::MAX_NOTES_LEN + 10);
    only.body = vec!["B".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN + 10)];

    let (deck, report) = build_deck(doc(vec![only]), &Theme::classic(), "P", &|_| None);
    assert!(deck.within_bounds());

    for what in [
        TruncatedField::Title,
        TruncatedField::BodyLine,
        TruncatedField::Notes,
    ] {
        let t = report
            .truncations
            .iter()
            .find(|t| t.what == what)
            .unwrap_or_else(|| {
                panic!("{what:?} must be recorded as cut: {:?}", report.truncations)
            });
        assert_eq!(
            t.slide_index, 41,
            "{what:?} must name the SOURCE slide, like every other index in the report"
        );
        assert_eq!(t.dropped, 10, "{what:?} lost exactly the overhang");
    }
}

// --- the ingress re-check ---------------------------------------------------------------

#[test]
fn a_caller_built_document_can_never_produce_an_out_of_bounds_deck() {
    // This is the guarantee `build.rs`'s backstop exists to make unconditional, and the reason
    // the backstop itself is unreachable: every value it would have to repair is clamped on the
    // way past. Asserted on a document that violates every content bound at once, because
    // `build_deck` is public and "the parser already did it" is not a bound.
    let mut slides: Vec<ImportedSlide> = Vec::new();
    for i in 0..(selahcue_import::limits::MAX_IMPORT_SLIDES + 25) {
        let mut s = slide(i);
        s.title = Some("t".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN * 2));
        s.body = (0..80)
            .map(|_| "b".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN))
            .collect();
        s.notes = "n".repeat(selahcue_present::MAX_NOTES_LEN * 3);
        slides.push(s);
    }
    let (deck, report) = build_deck(doc(slides), &Theme::classic(), "P", &|_| None);

    assert!(
        deck.within_bounds(),
        "the ingress must never hand the deck library a deck the presentation layer rejects"
    );
    assert_eq!(deck.len(), selahcue_import::limits::MAX_IMPORT_SLIDES);
    for s in deck.slides() {
        assert!(s.within_bounds());
        assert!(s.elements.len() <= selahcue_import::limits::MAX_SLIDE_ELEMENTS);
    }
    assert!(
        !report
            .skipped
            .iter()
            .any(|s| s.kind == SkipKind::SlideOutOfBounds),
        "nothing should need repairing — the clamps are what make the backstop unreachable, and \
         a repair here means one of them stopped holding"
    );
}

#[test]
fn slides_past_the_deck_cap_are_reported_rather_than_silently_dropped() {
    // `.take(MAX_IMPORT_SLIDES)` used to drop the surplus in silence on the one seam where the
    // parsers' own reporting does not run. A caller handing `build_deck` more slides than a deck
    // holds got a shorter deck and a report that said nothing was lost.
    let slides: Vec<ImportedSlide> = (0..(selahcue_import::limits::MAX_IMPORT_SLIDES + 3))
        .map(|i| {
            let mut s = slide(i);
            s.title = Some(format!("Slide {i}"));
            s
        })
        .collect();
    let (deck, report) = build_deck(doc(slides), &Theme::classic(), "P", &|_| None);
    assert_eq!(deck.len(), selahcue_import::limits::MAX_IMPORT_SLIDES);
    assert!(
        report
            .skipped
            .iter()
            .any(|s| s.kind == SkipKind::LimitReached(LimitKind::Slides)),
        "reaching the deck cap is reported, never silent: {:?}",
        report.skipped
    );
    // And a loss a preview cannot reveal escalates the report.
    assert_eq!(report.severity(), selahcue_import::Severity::Material);
}

#[test]
fn a_whitespace_only_body_is_neither_cut_in_silence_nor_reported_as_a_loss() {
    // The clamp used to run BEFORE the emptiness test, so a body of nothing but whitespace was cut
    // to fit an element that was then never emitted — a truncation with no report entry, which is
    // the one shape the truncation list must never have. Not cutting text nobody will see loses
    // nothing and leaves the list honest.
    let mut only = slide(0);
    only.title = Some("A title".into());
    only.body = vec![" ".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN * 2)];
    let (deck, report) = build_deck(doc(vec![only]), &Theme::classic(), "P", &|_| None);

    assert_eq!(
        deck_text(&deck),
        "A title",
        "no empty body element is emitted"
    );
    assert!(
        report.truncations.is_empty(),
        "nothing visible was lost, so nothing is claimed to have been: {:?}",
        report.truncations
    );
    assert!(deck.within_bounds());

    // The neighbouring case, so this is not satisfied by "the builder never truncates a body":
    // whitespace followed by real text IS cut, and IS reported.
    let mut mixed = slide(7);
    mixed.body = vec![format!(
        "{}{}",
        " ".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN),
        "visible".repeat(200)
    )];
    let (_, report) = build_deck(doc(vec![mixed]), &Theme::classic(), "P", &|_| None);
    assert_eq!(
        report
            .truncations
            .iter()
            .filter(|t| t.what == TruncatedField::BodyLine && t.slide_index == 7)
            .count(),
        1,
        "a body that really was cut must say so: {:?}",
        report.truncations
    );
}
