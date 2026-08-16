//! Turning an [`ImportedDocument`] into a real [`SlideDeck`].
//!
//! **How a slide's text becomes elements.** An `AuthoredSlide` has no title/body fields — its
//! content is a list of elements. So "imported decks adopt the SelahCue theme" becomes concrete
//! as: *copy geometry, colour and typography from the active theme's `title` and `body` regions
//! into the created text elements*. That is the theme's own statement of where a title and a body
//! sit, so an imported slide lands exactly where an authored one would.
//!
//! **Two text elements, not one per line.** A sixty-line slide is then two elements against the
//! sixty-four-element budget, leaving room for pictures. (Verified, not assumed: `Element::Text`
//! splits its content on `text.lines()` in `compose`, so an embedded `\n` is a real line break.)
//!
//! **A consequence worth stating plainly, because it is user-visible.** An imported deck is an
//! *authored* deck, so its text geometry is frozen at import time from whichever theme was
//! active. Changing theme afterwards changes the background but does not reflow the text, unlike
//! a scripture or song slide. That is inherent to a deck holding authored slides and cannot be
//! avoided here; it belongs in the release note.

use selahcue_present::{Element, ImageFit, MediaRef, RegionStyle, SlideDeck, Theme};

use crate::limits::{
    MAX_DECK_NAME_LEN, MAX_IMPORT_NOTES_LEN, MAX_IMPORT_SLIDES, MAX_SLIDE_ELEMENTS,
};
use crate::model::{ImportSource, ImportedDocument, ImportedSlide, MediaSlot, PermilleRect};
use crate::report::{ImportReport, LimitKind, ReportBuilder, SkipKind, TruncatedField};
use selahcue_present::MAX_TEXT_ELEMENT_LEN;

/// The fallback name for a file whose stem is empty or entirely whitespace.
pub const FALLBACK_DECK_NAME: &str = "Imported presentation";

/// The deck name an import should propose: the source file's stem, hygienised to a single line
/// and capped. A path separator cannot appear because the shell passes a stem, not a path.
///
/// `date` is supplied by the caller because this crate takes no clock — the same discipline the
/// rest of the tree uses to stay deterministic and testable.
pub fn deck_name_for(source: &ImportSource, date: &str) -> String {
    let proposed = match source {
        ImportSource::TxtFile { name } | ImportSource::Pptx { name } => name.clone(),
        ImportSource::Clipboard => format!("Pasted presentation — {date}"),
    };
    let cleaned = crate::hygiene::clean_single_line(&proposed, MAX_DECK_NAME_LEN);
    if cleaned.text.trim().is_empty() {
        FALLBACK_DECK_NAME.to_string()
    } else {
        cleaned.text
    }
}

/// Build the deck.
///
/// `resolve` maps a staged [`MediaSlot`] to the media reference it was committed under. A slot
/// that resolves to `None` — its commit failed — becomes a `MediaCommitFailed` report entry and
/// its image element is simply not emitted. **The slide keeps its text**: a disk filling
/// mid-import degrades to a text-only deck plus an honest report, never to a failed import.
pub fn build_deck(
    doc: ImportedDocument,
    theme: &Theme,
    name: &str,
    resolve: &dyn Fn(MediaSlot) -> Option<MediaRef>,
) -> (SlideDeck, ImportReport) {
    let ImportedDocument {
        source,
        slides,
        mut report,
    } = doc;

    let mut deck = SlideDeck::new(name);
    // The cap is REPORTED, not merely applied. `build_deck` is public and takes a caller-built
    // document, so a caller that hands it more slides than the deck admits used to have the
    // surplus vanish in silence — the exact lossiness the report exists to prevent, on the one
    // seam where the parsers' own reporting does not run.
    if slides.len() > MAX_IMPORT_SLIDES {
        report.skip(None, SkipKind::LimitReached(LimitKind::Slides), "");
    }
    for slide in slides.iter().take(MAX_IMPORT_SLIDES) {
        // Every report index below is the slide's position in the SOURCE document, never its
        // position in this deck — one index space for the whole crate (see `ImportedSlide`).
        let index = slide.source_index;
        let Some(id) = deck.add_slide() else {
            report.skip(None, SkipKind::LimitReached(LimitKind::Slides), "");
            break;
        };
        let elements = elements_for(index, slide, theme, resolve, &mut report);
        let (notes, dropped) = fit_notes(&slide.notes);
        report.truncate(index, TruncatedField::Notes, notes.chars().count(), dropped);
        if !notes.trim().is_empty() {
            report.count_notes();
        }
        if let Some(target) = deck.get_mut(id) {
            target.elements = elements;
            target.notes = notes;
        }
        // THE INGRESS RE-CHECK, AND IT IS ALWAYS ON. It used to be a `debug_assert!`, which is
        // compiled out of exactly the build the operator ships — so the one build where a limits
        // bug could reach persistence was the one build with no backstop.
        //
        // A live `assert!` is not the fix either: this crate denies `clippy::panic`, and a panic
        // here would take the operator console down over a file the user merely opened, which is
        // the failure mode the partial-import rule exists to prevent. So the backstop **repairs
        // and reports**: a slide the builder somehow produced outside the presentation layer's
        // bounds is dropped rather than carried into the deck library and the database.
        if deck.get(id).is_some_and(|s| !s.within_bounds()) {
            deck.remove(id);
            report.skip(Some(index), SkipKind::SlideOutOfBounds, "");
        }
    }
    // The deck-level half of the same check: the slide count. `add_slide` already refuses past the
    // cap, so this can only fire if that changes underneath us — which is the drift a backstop
    // exists to catch rather than trust.
    //
    // Termination does not rest on `remove` succeeding. A repair loop whose progress depends on a
    // call it does not check is a hang, and a hang in the import path is the operator console
    // frozen mid-service — a worse outcome than the out-of-bounds deck this is repairing. So the
    // loop stops the moment a pass fails to shrink the deck.
    while !deck.within_bounds() {
        let before = deck.len();
        let Some(last) = deck.slides().last().map(|s| s.id) else {
            break;
        };
        deck.remove(last);
        report.skip(None, SkipKind::LimitReached(LimitKind::Slides), "");
        if deck.len() >= before {
            break;
        }
    }

    // Counted from the deck rather than tallied as we go, so a slide the backstop removed cannot
    // still be counted as imported.
    let built = deck.len();
    let report = report.finish(source, built);
    (deck, report)
}

/// Clamp speaker notes to the presentation layer's own bound, returning what was kept and how many
/// characters were cut.
///
/// The parsers clamp notes already; this is the ingress re-check for the seam a caller can reach
/// directly — [`build_deck`] is public and takes a caller-built [`ImportedDocument`], so "the
/// parser already did it" is not a bound. By **chars**, because `AuthoredSlide::within_bounds`
/// counts chars and cutting by bytes would both fail that predicate on non-ASCII text and risk
/// splitting a character.
fn fit_notes(notes: &str) -> (String, usize) {
    let total = notes.chars().count();
    if total <= MAX_IMPORT_NOTES_LEN {
        return (notes.to_string(), 0);
    }
    (
        notes.chars().take(MAX_IMPORT_NOTES_LEN).collect(),
        total.saturating_sub(MAX_IMPORT_NOTES_LEN),
    )
}

/// The elements for one slide: title, body, then pictures, z-ordered so pictures sit in front.
fn elements_for(
    index: usize,
    slide: &ImportedSlide,
    theme: &Theme,
    resolve: &dyn Fn(MediaSlot) -> Option<MediaRef>,
    report: &mut ReportBuilder,
) -> Vec<Element> {
    let mut elements: Vec<Element> = Vec::new();

    if let Some(title) = slide.title.as_ref().filter(|t| !t.trim().is_empty()) {
        let (text, dropped) = fit_element_text(title);
        report.truncate(index, TruncatedField::Title, text.chars().count(), dropped);
        elements.push(text_element(&text, &theme.title, theme, 0));
    }
    // The per-LINE cap is not the per-ELEMENT cap. Sixty-four lines of two thousand characters
    // each are all individually legal and collectively far past `MAX_TEXT_ELEMENT_LEN`, so the
    // joined body has to be clamped in its own right — and reported, because a body silently cut
    // to fit is exactly the quiet lossiness the report exists to prevent.
    //
    // The emptiness test comes BEFORE the clamp, not after it. Clamping first meant a body of
    // nothing but whitespace was cut to fit an element that was then never emitted, so the cut
    // went unreported — a truncation with no entry, which is the one shape this list must never
    // have. Nothing is lost by not cutting text nobody will see, and every cut that does reach a
    // slide is now recorded.
    let joined = slide.body.join("\n");
    if !joined.trim().is_empty() {
        let (body, dropped) = fit_element_text(&joined);
        report.truncate(
            index,
            TruncatedField::BodyLine,
            body.chars().count(),
            dropped,
        );
        elements.push(text_element(&body, &theme.body, theme, 1));
    }

    for (n, picture) in slide.pictures.iter().enumerate() {
        if elements.len() >= MAX_SLIDE_ELEMENTS {
            report.skip(Some(index), SkipKind::LimitReached(LimitKind::Elements), "");
            break;
        }
        match resolve(picture.slot) {
            Some(source) => elements.push(image_element(source, picture.rect, 2 + n as i16)),
            None => report.skip(Some(index), SkipKind::MediaCommitFailed, ""),
        }
    }
    elements
}

/// Clamp text to one element's character budget, returning what was kept and how much was cut.
///
/// By CHARS, not bytes: `Element::within_bounds` counts chars, and cutting by bytes would both
/// fail that predicate on non-ASCII text and risk splitting a character.
fn fit_element_text(text: &str) -> (String, usize) {
    let total = text.chars().count();
    if total <= MAX_TEXT_ELEMENT_LEN {
        return (text.to_string(), 0);
    }
    (
        text.chars().take(MAX_TEXT_ELEMENT_LEN).collect(),
        total - MAX_TEXT_ELEMENT_LEN,
    )
}

/// A text element carrying a region's geometry, colour, typography and overflow policy — so
/// imported text has audience parity with the theme's own regions rather than an invented style.
fn text_element(text: &str, region: &RegionStyle, theme: &Theme, z: i16) -> Element {
    Element::Text {
        x_permille: region.x_permille,
        y_permille: region.y_permille,
        w_permille: region.w_permille,
        h_permille: region.h_permille,
        text: text.to_string(),
        color: region.color,
        size_permille: region.size_permille,
        line_height_permille: region.line_height_permille,
        align_h: region.align_h,
        align_v: region.align_v,
        fit: region.fit,
        opacity: 255,
        z,
        font: theme.font,
        weight: theme.weight,
        letter_spacing_permille: theme.letter_spacing_permille,
        visible: true,
    }
}

/// An image element. `Fit` letterboxes rather than stretching: an imported photograph distorted
/// to fill a rect is an obvious defect on an audience screen, and the source deck's own aspect
/// ratio is the only aspect information we have.
fn image_element(source: MediaRef, rect: PermilleRect, z: i16) -> Element {
    let rect = rect.clamped();
    Element::Image {
        x_permille: rect.x,
        y_permille: rect.y,
        w_permille: rect.w,
        h_permille: rect.h,
        source,
        opacity: 255,
        z,
        visible: true,
        fit: ImageFit::Fit,
    }
}
