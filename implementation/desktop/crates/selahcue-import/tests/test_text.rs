//! The shared text path: encoding, line endings, the blank-line splitter, the clamps, and the
//! deck the builder produces from them.
//!
//! Every rule about what "blank line" means has a plausible wrong answer, so every one of them is
//! pinned here rather than left to the reader of the splitter.

#![allow(clippy::unwrap_used)]

use selahcue_import::{
    build_deck, deck_name_for, decode, hygiene, import_text, import_txt_bytes, ImportError,
    ImportSource, Notice, Severity, TextLayout, TextOptions,
};
use selahcue_present::{Element, Theme};

fn theme() -> Theme {
    Theme::classic()
}

fn opts() -> TextOptions {
    TextOptions::default()
}

fn clipboard(text: &str) -> (selahcue_present::SlideDeck, selahcue_import::ImportReport) {
    import_text(text, ImportSource::Clipboard, &theme(), "Pasted", &opts()).unwrap()
}

// --- what "blank line" means -----------------------------------------------------------

#[test]
fn a_blank_line_separates_slides() {
    let (deck, report) = clipboard("First slide\nline two\n\nSecond slide\nline two");
    assert_eq!(deck.len(), 2);
    assert_eq!(report.slides_imported, 2);
    assert!(report.is_lossless());
}

#[test]
fn a_line_of_whitespace_is_blank_because_that_is_what_the_user_meant() {
    let (deck, _) = clipboard("One\n   \t \nTwo");
    assert_eq!(deck.len(), 2, "a whitespace-only line separates slides");
}

#[test]
fn consecutive_blank_lines_are_one_separator_not_several_empty_slides() {
    let (deck, _) = clipboard("One\n\n\n\n\nTwo");
    assert_eq!(deck.len(), 2);
}

#[test]
fn leading_and_trailing_blank_runs_produce_no_empty_slides() {
    let (deck, _) = clipboard("\n\n\nOne\n\nTwo\n\n\n");
    assert_eq!(deck.len(), 2);
    // A trailing newline is the single most common shape of a text file and must not add a slide.
    let (deck, _) = clipboard("Only\n");
    assert_eq!(deck.len(), 1);
}

#[test]
fn entirely_blank_input_is_the_one_text_case_that_is_genuinely_an_error() {
    for blank in ["", "\n", "   ", "\n\n\n", " \t \n \t "] {
        let r = import_text(blank, ImportSource::Clipboard, &theme(), "P", &opts());
        assert_eq!(r.unwrap_err(), ImportError::NothingToImport, "{blank:?}");
    }
}

// --- line endings and encoding ---------------------------------------------------------

#[test]
fn crlf_is_normalised_once_before_splitting() {
    // Without this every line keeps a trailing '\r' that becomes a rendered glyph on the audience
    // screen. The split still works either way, which is exactly why it is easy to miss.
    let (deck, _) = clipboard("Title\r\nBody line\r\n\r\nSecond\r\nMore");
    assert_eq!(deck.len(), 2);
    for slide in deck.slides() {
        for element in &slide.elements {
            if let Element::Text { text, .. } = element {
                assert!(!text.contains('\r'), "a carriage return survived: {text:?}");
            }
        }
    }
    // A lone CR (classic Mac line ending) is normalised too.
    let (deck, _) = clipboard("One\rTwo\r\rThree");
    assert_eq!(deck.len(), 2);
}

#[test]
fn a_utf8_bom_is_stripped_and_utf16_is_transcoded() {
    let bom = [&[0xEF, 0xBB, 0xBF][..], "Title\nBody".as_bytes()].concat();
    let (deck, report) = import_txt_bytes(
        &bom,
        ImportSource::TxtFile { name: "s".into() },
        &theme(),
        "S",
        &opts(),
    )
    .unwrap();
    assert_eq!(deck.len(), 1);
    assert!(report.is_lossless());

    let mut utf16 = vec![0xFF, 0xFE];
    for u in "Título\nCuerpo".encode_utf16() {
        utf16.extend_from_slice(&u.to_le_bytes());
    }
    let (deck, _) = import_txt_bytes(
        &utf16,
        ImportSource::TxtFile { name: "s".into() },
        &theme(),
        "S",
        &opts(),
    )
    .unwrap();
    let text = all_text(&deck);
    assert!(
        text.contains("Título"),
        "UTF-16 was not transcoded: {text:?}"
    );
}

#[test]
fn a_lossy_decode_counts_and_reports_its_substitutions() {
    // Windows-1252 lyric files are common in churches, so this is the normal path, not the edge
    // case — and replacing bytes with U+FFFD silently would break the partial-import rule at the
    // encoding layer, which is the layer where people forget to apply it.
    let cp1252 = b"Caf\xe9 song\nsecond line";
    let (_, report) = import_txt_bytes(
        cp1252,
        ImportSource::TxtFile { name: "s".into() },
        &theme(),
        "S",
        &opts(),
    )
    .unwrap();
    let replaced = report.notices.iter().find_map(|n| match n {
        Notice::EncodingReplaced { count } => Some(*count),
        _ => None,
    });
    assert_eq!(
        replaced,
        Some(1),
        "the substitution must be counted and reported"
    );
}

#[test]
fn nul_bytes_never_reach_the_deck() {
    let with_nul = b"Ti\x00tle\nBo\x00dy";
    let (deck, _) = import_txt_bytes(
        with_nul,
        ImportSource::TxtFile { name: "s".into() },
        &theme(),
        "S",
        &opts(),
    )
    .unwrap();
    assert!(!all_text(&deck).contains('\0'));
}

// --- string hygiene --------------------------------------------------------------------

#[test]
fn bidi_controls_are_stripped_but_joiners_survive() {
    // Bidi overrides can visually reverse or splice text, and this is presentation software: what
    // is imported gets projected to a congregation.
    let cleaned = hygiene::clean("safe\u{202E}reversed\u{2069}", 100);
    assert_eq!(cleaned.text, "safereversed");
    assert_eq!(cleaned.stripped, 2);

    // ZWJ and ZWNJ are load-bearing for Arabic, Persian and Indic scripts and for emoji
    // sequences. Blanket-stripping the zero-width block would silently corrupt legitimate text.
    let joined = hygiene::clean("\u{200D}\u{200C}family\u{200D}", 100);
    assert_eq!(joined.stripped, 0, "ZWJ/ZWNJ must survive");
    assert!(joined.text.contains('\u{200D}'));
    assert!(joined.text.contains('\u{200C}'));

    // C0 (minus \n and \t), C1 and DEL go.
    let controls = hygiene::clean("a\u{1B}[31mb\u{0}c\u{7F}d\u{85}e\nf\tg", 100);
    assert_eq!(controls.text, "a[31mbcde\nf\tg");
    assert_eq!(controls.stripped, 4);
}

#[test]
fn stripping_is_reported_so_it_is_never_silent() {
    let (_, report) = clipboard("Title\u{202E}\nBody");
    let stripped = report.notices.iter().find_map(|n| match n {
        Notice::ControlCharsStripped { count } => Some(*count),
        _ => None,
    });
    assert_eq!(stripped, Some(1));
}

#[test]
fn a_deck_name_is_single_line_and_capped() {
    let cleaned = hygiene::clean_single_line("  Sunday\nService\t2026  ", 200);
    assert_eq!(cleaned.text, "Sunday Service 2026");
    assert_eq!(
        deck_name_for(&ImportSource::TxtFile { name: "   ".into() }, "x"),
        "Imported presentation"
    );
    assert_eq!(
        deck_name_for(&ImportSource::Clipboard, "3 August"),
        "Pasted presentation — 3 August"
    );
    let long = "x".repeat(500);
    assert_eq!(
        deck_name_for(&ImportSource::Pptx { name: long }, "x")
            .chars()
            .count(),
        200
    );
    // A hostile name is inert text, not markup, by the time it leaves this crate — but the
    // ANGLE BRACKETS are deliberately preserved, because escaping is the renderer's job and
    // silently mangling a legitimate name like "Q&A <live>" would be its own defect.
    let hostile = deck_name_for(
        &ImportSource::Pptx {
            name: "<img src=x onerror=alert(1)>".into(),
        },
        "x",
    );
    assert_eq!(hostile, "<img src=x onerror=alert(1)>");
    assert!(!hostile.contains('\n'), "a name is always one line");
}

// --- layout and clamps -----------------------------------------------------------------

#[test]
fn the_first_line_is_the_title_by_default_and_both_layouts_are_reachable() {
    let (deck, _) = clipboard("Amazing Grace\nhow sweet the sound");
    let slide = deck.get_index(0).unwrap();
    // Title and body are TWO text elements, not one per line — so a sixty-line slide is two
    // elements against the sixty-four-element budget, leaving room for pictures.
    assert_eq!(slide.elements.len(), 2);
    let theme = theme();
    match &slide.elements[0] {
        Element::Text {
            text,
            y_permille,
            color,
            ..
        } => {
            assert_eq!(text, "Amazing Grace");
            assert_eq!(
                *y_permille, theme.title.y_permille,
                "title takes the theme's title region"
            );
            assert_eq!(*color, theme.title.color);
        }
        other => panic!("expected a title text element, got {other:?}"),
    }
    match &slide.elements[1] {
        Element::Text {
            text, y_permille, ..
        } => {
            assert_eq!(text, "how sweet the sound");
            assert_eq!(*y_permille, theme.body.y_permille);
        }
        other => panic!("expected a body text element, got {other:?}"),
    }

    let all_body = TextOptions {
        layout: TextLayout::AllBody,
    };
    let (deck, _) = import_text(
        "Amazing Grace\nhow sweet the sound",
        ImportSource::Clipboard,
        &theme,
        "P",
        &all_body,
    )
    .unwrap();
    let slide = deck.get_index(0).unwrap();
    assert_eq!(slide.elements.len(), 1, "no title element under AllBody");
}

#[test]
fn embedded_newlines_render_as_line_breaks_so_one_element_carries_many_lines() {
    // VERIFIED, not assumed: `compose` splits an `Element::Text` on `text.lines()`, so joining
    // body lines with '\n' is a real multi-line render rather than one long line.
    let (deck, _) = clipboard("Title\nline one\nline two\nline three");
    let slide = deck.get_index(0).unwrap();
    match &slide.elements[1] {
        Element::Text { text, .. } => assert_eq!(text.lines().count(), 3),
        other => panic!("expected body text, got {other:?}"),
    }
}

#[test]
fn every_clamp_holds_and_is_reported() {
    use selahcue_import::limits::{MAX_LINE_LEN, MAX_SLIDE_LINES, MAX_TITLE_LEN};

    // Too many lines on one slide.
    let mut src = String::from("Title\n");
    for i in 0..(MAX_SLIDE_LINES + 20) {
        src.push_str(&format!("line {i}\n"));
    }
    let (deck, report) = clipboard(&src);
    assert!(!report.is_lossless());
    assert!(report
        .truncations
        .iter()
        .any(|t| t.what == selahcue_import::TruncatedField::BodyLines && t.dropped == 20));

    // An over-long title and an over-long line are cut by CHARS, not bytes — the deck bound
    // counts chars, and cutting by bytes would both fail the predicate and split a character.
    let long_title = "é".repeat(MAX_TITLE_LEN + 10);
    let long_line = "é".repeat(MAX_LINE_LEN + 10);
    let (deck2, report2) = clipboard(&format!("{long_title}\n{long_line}"));
    assert!(report2
        .truncations
        .iter()
        .any(|t| t.what == selahcue_import::TruncatedField::Title));
    assert!(
        deck2.within_bounds(),
        "a clamped deck is within the presentation bounds"
    );
    assert!(deck.within_bounds());
}

#[test]
fn the_slide_cap_stops_the_import_rather_than_growing_an_unbounded_vec() {
    use selahcue_import::limits::MAX_IMPORT_SLIDES;
    let src = (0..(MAX_IMPORT_SLIDES + 50))
        .map(|i| format!("Slide {i}\n\n"))
        .collect::<String>();
    let (deck, report) = clipboard(&src);
    assert_eq!(deck.len(), MAX_IMPORT_SLIDES);
    assert!(report
        .skipped
        .iter()
        .any(|s| s.kind
            == selahcue_import::SkipKind::LimitReached(selahcue_import::LimitKind::Slides)));
    assert!(deck.within_bounds());
}

// --- the report ------------------------------------------------------------------------

#[test]
fn a_clean_import_is_lossless_and_a_cut_one_is_material() {
    let (_, clean) = clipboard("Title\nbody");
    assert!(clean.is_lossless());
    assert_eq!(clean.severity(), Severity::Lossless);
    // The standing notice is present even on a lossless import: replaced design attributes are
    // deliberate, so they are ONE notice rather than one skipped item per transition.
    assert!(clean.notices.contains(&Notice::ThemeReplaced));

    // Visible slide text was cut → the loudest tier, because a preview will not reveal it.
    let long_line = "a".repeat(selahcue_import::limits::MAX_LINE_LEN + 5);
    let (_, cut) = clipboard(&format!("Title\n{long_line}"));
    assert_eq!(cut.severity(), Severity::Material);
}

#[test]
fn the_report_serialises_with_a_stable_shape_for_the_console() {
    let (_, report) = clipboard("Title\nbody");
    let json = serde_json::to_value(&report).unwrap();
    assert_eq!(json["slides_imported"], 1);
    assert!(json["skipped"].as_array().unwrap().is_empty());
    // Every notice carries a machine tag AND the already-hygienised sentence the console shows,
    // so the renderer never has to compose operator-facing copy from an internal enum.
    let notices = json["notices"].as_array().unwrap();
    assert!(notices
        .iter()
        .any(|n| n["kind"] == "theme_replaced" && n["message"].is_string()));
}

#[test]
fn a_clipboard_paste_over_the_cap_is_truncated_on_a_character_boundary_and_reported() {
    use selahcue_import::limits::MAX_CLIPBOARD_BYTES;
    let mut builder = selahcue_import::report::ReportBuilder::new();
    let huge = "é".repeat(MAX_CLIPBOARD_BYTES); // two bytes per char → twice the cap
    let clamped = selahcue_import::clamp_clipboard(&huge, &mut builder);
    assert!(clamped.len() <= MAX_CLIPBOARD_BYTES);
    assert!(
        std::str::from_utf8(clamped.as_bytes()).is_ok(),
        "truncation must land on a character boundary"
    );
    let report = builder.finish(ImportSource::Clipboard, 0);
    assert!(report
        .notices
        .iter()
        .any(|n| matches!(n, Notice::ClipboardTruncated { .. })));
}

// --- determinism -----------------------------------------------------------------------

#[test]
fn importing_the_same_text_twice_yields_identical_decks() {
    // No hash-map iteration order in the output, no timestamps in the deck: two imports of the
    // same bytes must serialise identically apart from the library-assigned id.
    let a = clipboard("Title\nbody\n\nSecond\nmore").0;
    let b = clipboard("Title\nbody\n\nSecond\nmore").0;
    assert_eq!(
        serde_json::to_string(&a).unwrap(),
        serde_json::to_string(&b).unwrap()
    );
}

#[test]
fn over_long_notes_are_clamped_at_the_ingress_rather_than_reaching_the_deck() {
    // `build_deck` is public and takes a caller-built document, so "the parser clamped it already"
    // is not a bound — this is the ingress, and it has to hold on its own.
    //
    // The re-check here used to be a `debug_assert!`, which is the worst of both worlds: compiled
    // OUT of the release the operator ships, so the one build where an out-of-bounds deck could
    // reach the deck library and the database was the one build with no check at all — and in a
    // debug build it did the opposite, panicking and taking the console down over a document.
    // Neither is a bound. Clamping the notes and reporting the cut is.
    let mut doc = selahcue_import::text::parse(
        "Title\nbody",
        ImportSource::Clipboard,
        &opts(),
        selahcue_import::report::ReportBuilder::new(),
    )
    .unwrap();
    doc.slides[0].notes = "n".repeat(selahcue_present::MAX_NOTES_LEN + 500);

    let (deck, report) = build_deck(doc, &theme(), "P", &|_| None);
    assert_eq!(deck.len(), 1, "the slide is kept, its notes cut to fit");
    assert!(
        deck.within_bounds(),
        "a deck leaving the importer is ALWAYS within the presentation layer's bounds"
    );
    assert_eq!(
        deck.get_index(0).unwrap().notes.chars().count(),
        selahcue_present::MAX_NOTES_LEN
    );
    assert!(
        report
            .truncations
            .iter()
            .any(|t| t.what == selahcue_import::TruncatedField::Notes && t.dropped == 500),
        "and the cut is reported, never silent: {:?}",
        report.truncations
    );
}

#[test]
fn a_slot_that_never_committed_costs_its_image_and_not_its_slide() {
    // The resolver contract, exercised with a slot that actually EXISTS.
    //
    // This test used to run on a plain text document, which carries no pictures at all: the
    // resolver was never called once, `is_lossless()` was trivially true, and it passed just as
    // happily with the entire unresolved-slot branch — the one that keeps the slide and drops only
    // the image — deleted from `build_deck`.
    let doc = || {
        let mut doc = selahcue_import::text::parse(
            "Title\nbody",
            ImportSource::Clipboard,
            &opts(),
            selahcue_import::report::ReportBuilder::new(),
        )
        .unwrap();
        doc.slides[0].pictures = vec![selahcue_import::ImportedPicture {
            slot: selahcue_import::MediaSlot(7),
            rect: selahcue_import::PermilleRect::CENTRED,
        }];
        doc
    };

    // The commit failed for this slot: the image goes, the slide and its text stay.
    let (deck, report) = build_deck(doc(), &theme(), "P", &|_| None);
    assert_eq!(deck.len(), 1, "the slide is not taken down with its image");
    let elements = &deck.get_index(0).unwrap().elements;
    assert!(
        elements
            .iter()
            .any(|e| matches!(e, Element::Text { text, .. } if text.contains("body"))),
        "the slide keeps its text"
    );
    assert!(
        !elements.iter().any(|e| matches!(e, Element::Image { .. })),
        "no image element is emitted for a slot that never committed"
    );
    assert!(
        report
            .skipped
            .iter()
            .any(|s| s.kind == selahcue_import::SkipKind::MediaCommitFailed),
        "and the loss is reported rather than silent: {:?}",
        report.skipped
    );
    assert!(!report.is_lossless());

    // The positive control: the SAME slot, resolving. Without this the assertions above would be
    // satisfied by a builder that never emits an image element under any circumstances.
    let (deck, report) = build_deck(doc(), &theme(), "P", &|slot| {
        selahcue_present::MediaRef::new(&format!("/app/media/import-{}.png", slot.0))
    });
    assert!(
        deck.get_index(0)
            .unwrap()
            .elements
            .iter()
            .any(|e| matches!(e, Element::Image { .. })),
        "a slot that resolves DOES produce an image element"
    );
    assert!(report.is_lossless());
}

fn all_text(deck: &selahcue_present::SlideDeck) -> String {
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

#[test]
fn newline_normalisation_and_decoding_are_independently_correct() {
    assert_eq!(decode::normalise_newlines("a\r\nb\rc\nd"), "a\nb\nc\nd");
    let d = decode::to_text(b"plain");
    assert_eq!(d.text, "plain");
    assert_eq!(d.replacements, 0);
}
