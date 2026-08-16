//! The `.pptx` path: the happy case, and the hostile battery the security review made a merge
//! gate. Every adversarial archive here is assembled in-test by `support`; none is committed.

#![allow(clippy::unwrap_used)]

mod support;

use support::{Entry, PptxBuilder, SlideSpec};

use selahcue_import::{
    build_deck, ImportError, ImportReport, ImportSource, ImportedDocument, LimitKind, MediaSlot,
    MemorySource, Notice, RecordingSink, RefusingSink, SkipKind,
};
use selahcue_present::{Element, MediaRef, Theme};

fn never() -> impl Fn() -> bool {
    || false
}

fn source() -> ImportSource {
    ImportSource::Pptx {
        name: "Sunday Service".into(),
    }
}

/// Read an archive with a recording sink, returning the document and the sink.
fn read(bytes: Vec<u8>) -> Result<(ImportedDocument, RecordingSink), ImportError> {
    let mut src = MemorySource::new(bytes);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(&mut src, source(), &mut sink, &never())?;
    Ok((doc, sink))
}

/// Read and finish, resolving every staged slot to a fake committed path.
fn import(bytes: Vec<u8>) -> Result<(selahcue_present::SlideDeck, ImportReport), ImportError> {
    let (doc, _) = read(bytes)?;
    Ok(build_deck(
        doc,
        &Theme::classic(),
        "Sunday Service",
        &|slot| MediaRef::new(&format!("/app/media/import-{}.png", slot.0)),
    ))
}

fn report_of(bytes: Vec<u8>) -> ImportReport {
    import(bytes).expect("import should succeed").1
}

fn kinds(report: &ImportReport) -> Vec<SkipKind> {
    report.skipped.iter().map(|s| s.kind).collect()
}

// --- the happy path --------------------------------------------------------------------

#[test]
fn a_three_slide_deck_imports_text_notes_and_images() {
    let png = support::png(4, 4);
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Welcome".into()),
            body: vec!["Please stand".into()],
            notes: Some("Greet the visitors".into()),
            ..Default::default()
        })
        .slide(SlideSpec::text(
            "Reading",
            &["John 3:16", "For God so loved"],
        ))
        .slide(SlideSpec {
            title: Some("Photo".into()),
            images: vec![("image1.png".into(), png.clone())],
            ..Default::default()
        })
        .build();

    let (deck, report) = import(bytes).unwrap();
    assert_eq!(deck.len(), 3);
    assert_eq!(report.slides_imported, 3);
    assert_eq!(report.slides_in_source, Some(3));
    assert_eq!(report.images_imported, 1);
    assert_eq!(report.notes_imported, 1);
    assert!(
        report.is_lossless(),
        "unexpected drops: {:?}",
        report.skipped
    );

    assert_eq!(deck.get_index(0).unwrap().notes, "Greet the visitors");
    let third = deck.get_index(2).unwrap();
    assert!(
        third
            .elements
            .iter()
            .any(|e| matches!(e, Element::Image { .. })),
        "the image element must be built"
    );
    assert!(deck.within_bounds());
}

#[test]
fn a_relationship_target_containing_dot_dot_resolves_rather_than_being_rejected() {
    // `../media/image1.png` is what EVERY real PowerPoint file writes. Rejecting `..` outright
    // breaks all of them; joining it to a directory is zip-slip. The rule that satisfies both is
    // normalisation inside the package namespace, with the result used ONLY as a lookup key into
    // the archive's own entry set.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Photo".into()),
            images: vec![("image1.png".into(), support::png(2, 2))],
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);
    assert_eq!(report.images_imported, 1);
    assert!(report.is_lossless());
}

#[test]
fn one_media_part_referenced_from_many_slides_is_staged_exactly_once() {
    let png = support::png(2, 2);
    let mut builder = PptxBuilder::new();
    for _ in 0..8 {
        builder = builder.slide(SlideSpec {
            title: Some("Same photo".into()),
            images: vec![("shared.png".into(), png.clone())],
            ..Default::default()
        });
    }
    let (doc, sink) = read(builder.build()).unwrap();
    assert_eq!(doc.slides.len(), 8);
    assert_eq!(
        sink.len(),
        1,
        "a shared part must be extracted, decoded and staged once — and count against the byte \
         budget once"
    );
    // Every slide still gets its picture, pointing at that one slot.
    for slide in &doc.slides {
        assert_eq!(slide.pictures.len(), 1);
        assert_eq!(slide.pictures[0].slot, MediaSlot(0));
    }
}

#[test]
fn grouped_shapes_keep_their_text() {
    // Many real decks group their content. Not descending into a group silently loses text —
    // the worst possible failure under a partial-import rule, because the report says nothing.
    let raw = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a" xmlns:r="r"><p:cSld><p:spTree>
      <p:grpSp><p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>Grouped title</a:t></a:r></a:p></p:txBody></p:sp>
      <p:grpSp><p:sp><p:txBody><a:p><a:r><a:t>Nested body</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp>
      </p:grpSp></p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(raw.into()),
            ..Default::default()
        })
        .build();
    let (deck, _) = import(bytes).unwrap();
    let text = deck_text(&deck);
    assert!(text.contains("Grouped title"), "{text}");
    assert!(text.contains("Nested body"), "{text}");
}

#[test]
fn a_line_break_inside_a_paragraph_becomes_a_real_line() {
    let raw = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree>
      <p:sp><p:txBody><a:p><a:r><a:t>first</a:t></a:r><a:br/><a:r><a:t>second</a:t></a:r></a:p></p:txBody></p:sp>
      </p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(raw.into()),
            ..Default::default()
        })
        .build();
    let (deck, _) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("first\nsecond"));
}

#[test]
fn prefixes_are_never_matched_only_local_names() {
    // Real files rebind `p:`/`a:`/`r:` freely; a prefix match is a correctness bug waiting for a
    // file that uses `x:` instead.
    let raw = r#"<?xml version="1.0"?><x:sld xmlns:x="p" xmlns:y="a"><x:cSld><x:spTree>
      <x:sp><x:nvSpPr><x:nvPr><x:ph type="title"/></x:nvPr></x:nvSpPr><x:txBody><y:p><y:r><y:t>Rebound</y:t></y:r></y:p></x:txBody></x:sp>
      </x:spTree></x:cSld></x:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(raw.into()),
            ..Default::default()
        })
        .build();
    let (deck, _) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("Rebound"));
}

#[test]
fn a_slide_number_a_footer_and_a_date_never_reach_the_audience_screen() {
    // Found only by running genuinely PowerPoint-authored decks: real files carry a
    // `<p:ph type="sldNum"/>` on very nearly every slide and often a `<p:ph type="ftr"/>` too —
    // 124 and 5 respectively across seven real decks, about one per slide. Treating every
    // non-title shape as body imported them, so a slide arrived as
    // `2026 Market Report | 2 | The market is moving from…`: the footer and the page number on
    // the congregation's screen.
    //
    // The whole suite was blind to this because `PptxBuilder` emitted no such placeholder. It
    // does now, so removing the furniture filter from `assemble_text` fails HERE.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("2026 Market Report".into()),
            body: vec!["The market is moving from print to projection.".into()],
            slide_number: Some("2".into()),
            footer: Some("2026 Market Report".into()),
            date: Some("14/08/2026".into()),
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();
    let text = deck_text(&deck);

    assert!(text.contains("The market is moving"), "{text}");
    assert_eq!(
        text.lines()
            .filter(|l| l.trim() == "2" || l.trim() == "14/08/2026")
            .count(),
        0,
        "the page number and the date are page furniture, never body text: {text:?}"
    );
    // The footer text here is deliberately the SAME string as the title, which is what a real deck
    // does — so "the footer is gone" has to be counted, not merely searched for.
    assert_eq!(
        text.matches("2026 Market Report").count(),
        1,
        "the footer repeats the title; only the title may survive: {text:?}"
    );

    // And it is dropped in SILENCE. A design attribute SelahCue replaces on purpose is not a
    // skipped item — one per slide across a real deck would consume the whole report budget and
    // bury the drops that matter.
    assert!(
        report.is_lossless(),
        "furniture is replaced by intent, not skipped: {:?} {:?}",
        report.skipped,
        report.truncations
    );
    assert_eq!(report.severity(), selahcue_import::Severity::Lossless);
}

#[test]
fn furniture_does_not_spend_the_body_budget_that_real_content_needs() {
    // The knock-on the reviewers measured: the junk consumed the joined-body element budget and
    // forced real content into truncation, which escalates an ordinary deck to `Material`. Two of
    // seven real decks hit that tier largely because of this.
    //
    // The body here is sized to fit the element budget EXACTLY, so any extra text at all pushes it
    // over — which is what a slide number, a footer and a date did.
    let line = "x".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN);
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Sermon notes".into()),
            body: vec![line.clone()],
            slide_number: Some("12".into()),
            footer: Some("Sunday service".into()),
            date: Some("14/08/2026".into()),
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);
    assert!(
        report.truncations.is_empty(),
        "a body that fits exactly must not be cut to make room for furniture: {:?}",
        report.truncations
    );
    assert_eq!(report.severity(), selahcue_import::Severity::Lossless);
}

// --- partial import: what is dropped, and reported ------------------------------------

#[test]
fn charts_tables_smartart_and_hidden_slides_are_skipped_and_reported() {
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("With a chart".into()),
            graphic_uri: Some("http://schemas.openxmlformats.org/drawingml/2006/chart".into()),
            ..Default::default()
        })
        .slide(SlideSpec {
            title: Some("With a table".into()),
            graphic_uri: Some("http://schemas.openxmlformats.org/drawingml/2006/table".into()),
            ..Default::default()
        })
        .slide(SlideSpec {
            title: Some("Hidden".into()),
            hidden: true,
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);
    let k = kinds(&report);
    assert!(k.contains(&SkipKind::Chart));
    assert!(k.contains(&SkipKind::Table));
    assert!(k.contains(&SkipKind::HiddenSlide));
    assert_eq!(
        report.slides_imported, 2,
        "the hidden slide is not imported"
    );
    // The recovery is in the copy, because a report that only says what is gone teaches a
    // volunteer to dismiss reports.
    let hidden = report
        .skipped
        .iter()
        .find(|s| s.kind == SkipKind::HiddenSlide)
        .unwrap();
    assert!(
        hidden.kind.message().contains("unhide"),
        "{}",
        hidden.kind.message()
    );
}

#[test]
fn a_report_index_names_the_source_slide_not_the_position_it_lands_in() {
    // Slide 1 is hidden, so it is dropped; slide 2 carries a chart. The chart's entry must say
    // slide 1 — 0-based, the source's SECOND slide — because that is the number PowerPoint shows
    // the operator when they go looking for it.
    //
    // Recording the output position instead says slide 0, which is the position the chart's slide
    // inherits once the hidden one is dropped. Two different source slides then carry the same
    // index, and "a chart was skipped on slide 12" points somewhere it has nothing to do with.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Hidden".into()),
            hidden: true,
            ..Default::default()
        })
        .slide(SlideSpec {
            title: Some("With a chart".into()),
            // Three lines, each comfortably UNDER the per-line cap, whose joined length is half
            // as much again as one text element may hold. The parser therefore cuts nothing and
            // `build_deck` does all the cutting — which is the point. The previous fixture used a
            // single over-long line, so the PARSER's truncation satisfied the assertion below and
            // the builder's own index could be changed to 999 without failing anything.
            body: (0..3)
                .map(|_| "x".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN / 2))
                .collect(),
            graphic_uri: Some("http://schemas.openxmlformats.org/drawingml/2006/chart".into()),
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);

    let chart = report
        .skipped
        .iter()
        .find(|s| s.kind == SkipKind::Chart)
        .expect("the chart is reported");
    assert_eq!(
        chart.slide_index,
        Some(1),
        "the chart is on the SOURCE's second slide, whatever position it ends up in"
    );
    let hidden = report
        .skipped
        .iter()
        .find(|s| s.kind == SkipKind::HiddenSlide)
        .expect("the hidden slide is reported");
    assert_eq!(hidden.slide_index, Some(0));
    assert_eq!(report.slides_imported, 1);

    // And the BUILDER's truncations live in the SAME space — they used to be recorded against a
    // different one, so a report could carry two indices meaning two different things.
    assert_eq!(
        report.truncations.len(),
        1,
        "exactly one cut, and `build_deck` is the only thing that could have made it: {:?}",
        report.truncations
    );
    assert_eq!(
        report.truncations[0].what,
        selahcue_import::TruncatedField::BodyLine
    );
    assert_eq!(
        report.truncations[0].slide_index, 1,
        "the builder's cut is on the SOURCE's second slide, like every other index in the report"
    );
}

#[test]
fn an_external_image_is_reported_and_never_fetched() {
    // In an offline-first app a document that triggers network I/O is a privacy defect as much as
    // a security one — and the structural guarantee is the crate's dependency graph, asserted in
    // CI, not this test.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Linked".into()),
            external_image: Some("https://example.invalid/track.png".into()),
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);
    assert!(kinds(&report).contains(&SkipKind::ExternalImage));
    assert_eq!(report.images_imported, 0);
}

#[test]
fn embedded_fonts_macros_and_nested_packages_are_never_opened() {
    let mut builder = PptxBuilder::new()
        .slide(SlideSpec::text("Title", &["body"]))
        .entry(Entry::deflated("ppt/vbaProject.bin", &[0u8; 64]))
        .entry(Entry::deflated("ppt/embeddings/inner.xlsx", &[0u8; 64]));
    // Twenty-five embedded fonts, which is what a real deck carried. Itemising one drop per file
    // consumed a quarter of the whole report budget and buried the drops that matter, so they
    // collapse to ONE standing notice — a design attribute SelahCue replaces on purpose is not a
    // skipped item, exactly as it is not for transitions, masters and colours.
    for i in 0..25 {
        builder = builder.entry(Entry::deflated(
            &format!("ppt/fonts/font{i}.fntdata"),
            &[0u8; 64],
        ));
    }
    let report = report_of(builder.build());
    let k = kinds(&report);
    assert_eq!(
        report
            .notices
            .iter()
            .filter(|n| **n == Notice::EmbeddedFontsReplaced)
            .count(),
        1,
        "twenty-five font files, one notice: {:?}",
        report.notices
    );
    assert_eq!(
        k.len(),
        2,
        "and not one skipped item among them — the report budget is for real losses: {:?}",
        report.skipped
    );
    assert_eq!(
        k.iter()
            .filter(|x| **x == SkipKind::NestedContainer)
            .count(),
        2,
        "a macro project and an embedded package are both nested containers"
    );
}

#[test]
fn a_jpeg_photograph_imports_through_the_pptx_path_upright() {
    // JPEG is what real decks embed — ADR-0025 exists because "text + images" is not true on a
    // real `.pptx` without it — and until now NO test drove a JPEG through this path at all. Every
    // image case here used PNG, so the whole sniff → probe → decode → stage chain was unproven for
    // the dominant format.
    let photo = support::jpeg(16, 8, None);
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Photo".into()),
            body: vec!["and its caption".into()],
            images: vec![("photo.jpg".into(), Vec::new())],
            ..Default::default()
        })
        // Stored, as a real package holds an already-compressed photograph.
        .replacing(Entry::stored("ppt/media/photo.jpg", &photo))
        .build();

    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(sink.len(), 1, "the JPEG was staged");
    let (staged_bytes, probe) = &sink.staged()[0];
    assert_eq!(
        probe.format,
        selahcue_engine::ImageFormat::Jpeg,
        "sniffed as JPEG by magic bytes, not by the `.jpg` in its name"
    );
    assert_eq!((probe.width, probe.height), (16, 8));
    assert_eq!(
        staged_bytes, &photo,
        "the ORIGINAL encoded bytes are staged, not the decoded pixels"
    );

    let (deck, report) = build_deck(doc, &Theme::classic(), "P", &|slot| {
        MediaRef::new(&format!("/app/media/import-{}.jpg", slot.0))
    });
    assert_eq!(report.images_imported, 1);
    assert!(report.is_lossless(), "{:?}", report.skipped);
    assert!(deck_text(&deck).contains("and its caption"));
    assert!(deck
        .get_index(0)
        .unwrap()
        .elements
        .iter()
        .any(|e| matches!(e, Element::Image { .. })));

    // A rotated photograph reports its POST-orientation dimensions, because that is what the
    // per-mille rect and the media row both want — and importing phone photographs sideways is the
    // failure ADR-0025's EXIF reader exists to prevent.
    let rotated = support::jpeg(16, 8, Some(6));
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Rotated".into()),
            images: vec![("rot.jpg".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(Entry::stored("ppt/media/rot.jpg", &rotated))
        .build();
    let (_, sink) = read(bytes).unwrap();
    assert_eq!(
        (sink.staged()[0].1.width, sink.staged()[0].1.height),
        (8, 16),
        "a transposing EXIF orientation is applied before the probe reports its dimensions"
    );
}

#[test]
fn unsupported_image_formats_are_dropped_and_never_handed_to_a_decoder() {
    for (name, magic) in [
        ("gif.gif", &b"GIF89a\0\0\0\0"[..]),
        ("bmp.bmp", &b"BM\0\0\0\0\0\0"[..]),
        ("tiff.tif", &b"II\x2a\0\0\0\0\0"[..]),
        ("meta.wmf", &[0xd7, 0xcd, 0xc6, 0x9a, 0, 0, 0, 0][..]),
        ("vector.svg", &b"<svg xmlns=\"x\"></svg>"[..]),
    ] {
        let bytes = PptxBuilder::new()
            .slide(SlideSpec {
                title: Some("Media".into()),
                images: vec![(name.to_string(), magic.to_vec())],
                ..Default::default()
            })
            .build();
        let report = report_of(bytes);
        assert!(
            kinds(&report).contains(&SkipKind::ImageFormatUnsupported),
            "{name} must be dropped and reported"
        );
        assert_eq!(report.images_imported, 0);
    }
}

#[test]
fn an_oversized_or_corrupt_image_costs_its_picture_and_not_its_slide() {
    let mut corrupt = support::png(4, 4);
    let n = corrupt.len();
    for b in corrupt.iter_mut().take(n - 12).skip(16) {
        *b ^= 0xFF;
    }
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Damaged photo".into()),
            body: vec!["the text still arrives".into()],
            images: vec![("bad.png".into(), corrupt)],
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert_eq!(deck.len(), 1, "the slide survives its unreadable image");
    assert!(deck_text(&deck).contains("the text still arrives"));
    assert!(kinds(&report).contains(&SkipKind::ImageUnreadable));
}

#[test]
fn a_full_media_library_refuses_the_image_and_not_the_import() {
    // Two house rules meet here — "refuse at the cap, never truncate" and "never refuse a whole
    // import over one unsupported element" — and both are satisfied by scoping the refusal to the
    // item.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Photo".into()),
            images: vec![("image1.png".into(), support::png(2, 2))],
            ..Default::default()
        })
        .build();
    let mut src = MemorySource::new(bytes);
    let mut sink = RefusingSink;
    let doc = selahcue_import::read_pptx(&mut src, source(), &mut sink, &never()).unwrap();
    let (deck, report) = build_deck(doc, &Theme::classic(), "P", &|_| None);
    assert_eq!(deck.len(), 1, "a text-only deck, not a failed import");
    assert!(kinds(&report).contains(&SkipKind::LibraryFull));
}

#[test]
fn a_commit_failure_costs_the_image_element_and_leaves_the_text() {
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Photo".into()),
            body: vec!["still here".into()],
            images: vec![("image1.png".into(), support::png(2, 2))],
            ..Default::default()
        })
        .build();
    let (doc, _) = read(bytes).unwrap();
    // Every slot fails to resolve: the commit succeeded for nothing.
    let (deck, report) = build_deck(doc, &Theme::classic(), "P", &|_| None);
    assert!(deck_text(&deck).contains("still here"));
    assert!(kinds(&report).contains(&SkipKind::MediaCommitFailed));
    assert!(!deck
        .get_index(0)
        .unwrap()
        .elements
        .iter()
        .any(|e| matches!(e, Element::Image { .. })));
}

#[test]
fn slide_order_falls_back_to_natural_numeric_order_and_says_so_loudly() {
    // Importing twenty-four slides in the WRONG ORDER is worse than dropping a chart, and unlike
    // a dropped chart it is invisible in a preview. So the fallback is a notice that escalates
    // the whole report to its loudest tier.
    let mut builder = PptxBuilder::new();
    for i in 1..=12 {
        builder = builder.slide(SlideSpec::text(&format!("Slide {i}"), &["body"]));
    }
    builder.presentation_override = Some(None); // presentation.xml deliberately absent
    let (deck, report) = import(builder.build()).unwrap();
    assert_eq!(deck.len(), 12);
    assert!(report.notices.contains(&Notice::SlideOrderInferred));
    assert_eq!(report.severity(), selahcue_import::Severity::Material);
    // slide10 must follow slide9, not slide1 — a plain lexical sort gets this wrong.
    let titles: Vec<String> = deck
        .slides()
        .iter()
        .map(|s| match s.elements.first() {
            Some(Element::Text { text, .. }) => text.clone(),
            _ => String::new(),
        })
        .collect();
    assert_eq!(titles[8], "Slide 9");
    assert_eq!(titles[9], "Slide 10");
}

// --- B1: nothing an archive says ever becomes a path ----------------------------------

#[test]
fn hostile_entry_names_are_inert_because_they_are_only_ever_lookup_keys() {
    // Traversal, absolute paths, drive-relative paths, backslash separators, Windows reserved
    // device names, and a symlink-shaped entry. None of them can influence a path, because no
    // path is ever constructed from archive content — no filesystem primitive is reachable from
    // this crate's own code, which a CI grep asserts structurally.
    let png = support::png(2, 2);
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Safe".into()),
            images: vec![("image1.png".into(), png)],
            ..Default::default()
        })
        .entry(Entry::deflated(
            "../../../../etc/cron.d/evil",
            b"* * * * * root sh",
        ))
        .entry(Entry::deflated("/etc/passwd", b"root:x:0:0"))
        .entry(Entry::deflated("C:\\Windows\\System32\\evil.dll", b"MZ"))
        .entry(Entry::deflated("..\\..\\evil.bat", b"@echo off"))
        .entry(Entry::deflated("CON", b"device"))
        .entry(Entry::deflated("nul", b"device"))
        .entry(support::symlink_entry("link", "../../../../etc/passwd"))
        .build();
    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(doc.slides.len(), 1);
    // Exactly one thing was staged: the real image. Nothing named by a hostile entry reached the
    // sink, and the sink is the ONLY way bytes leave this crate.
    assert_eq!(sink.len(), 1);
    assert_eq!(sink.staged()[0].1.format, selahcue_engine::ImageFormat::Png);
}

#[test]
fn a_relationship_target_cannot_climb_out_of_the_package() {
    let raw_rels = r#"<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdImg0" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../../../../../../etc/passwd"/></Relationships>"#;
    let slide = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a" xmlns:r="r"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>text</a:t></a:r></a:p></p:txBody></p:sp><p:pic><p:blipFill><a:blip r:embed="rIdImg0"/></p:blipFill><p:spPr/></p:pic></p:spTree></p:cSld></p:sld>"#;
    // `replacing`, because the builder generates this slide's rels part itself. Appending a second
    // one leaves the GENERATED (empty) rels in force, so nothing is staged for the trivial reason
    // that there was no relationship to follow — and the test passes without `pkgpath` refusing
    // anything at all. It would pass with the whole refusal deleted.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(slide.into()),
            ..Default::default()
        })
        .replacing(Entry::deflated(
            "ppt/slides/_rels/slide1.xml.rels",
            raw_rels.as_bytes(),
        ))
        .build();
    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(doc.slides.len(), 1, "the slide's text still imports");
    assert!(sink.is_empty(), "nothing outside the package was ever read");

    let (_, report) = build_deck(doc, &Theme::classic(), "P", &|_| None);
    // The relationship was READ and REFUSED — which is the whole claim. An empty relationship list
    // would instead report `UnsupportedGraphic` (a picture whose r:embed resolves to nothing), so
    // the two situations this test has to tell apart are distinguishable from the outside.
    let refused = report
        .skipped
        .iter()
        .find(|s| s.kind == SkipKind::UnreadablePart)
        .expect("the climbing target must be reported as an unreadable part");
    assert!(
        refused.detail.contains("etc/passwd"),
        "the refusal must name the target it refused, got {:?}",
        refused.detail
    );
    assert!(
        !kinds(&report).contains(&SkipKind::UnsupportedGraphic),
        "an UnsupportedGraphic here means the hostile rels never reached the resolver"
    );

    // And the case that separates REFUSING the climb from silently CLAMPING it at the root. A
    // target naming something that does not exist looks identical either way — both end up
    // reporting an unreadable part — so the archive is given a part the clamp would land on. With
    // the refusal it is unreachable; with a clamp `../../../decoy.png` resolves to `decoy.png`,
    // the entry is found, and a part the slide was never entitled to name is decoded and staged.
    let climb = r#"<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdImg0" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../../../decoy.png"/></Relationships>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(slide.into()),
            ..Default::default()
        })
        .replacing(Entry::deflated(
            "ppt/slides/_rels/slide1.xml.rels",
            climb.as_bytes(),
        ))
        .entry(Entry::deflated("decoy.png", &support::png(2, 2)))
        .build();
    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(doc.slides.len(), 1, "the slide's text still imports");
    assert!(
        sink.is_empty(),
        "a target that climbs above the package root is REFUSED, never clamped back onto a part \
         that happens to exist"
    );
    assert!(doc.slides[0].pictures.is_empty());
}

// --- B2: no DTD, no network -----------------------------------------------------------

#[test]
fn a_doctype_part_is_dropped_and_reported_before_the_parser_sees_it() {
    // XXE is doubly disqualifying here: classic file disclosure, and — because the fetch itself is
    // the exfiltration channel — a document causing network I/O in an offline-first app. OOXML
    // never legitimately contains a DTD, so failing closed on the marker is free, and it is
    // stronger than trusting a parser's entity configuration.
    for payload in [
        r#"<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/hosts">]>"#,
        r#"<!DOCTYPE r [<!ENTITY % p SYSTEM "http://example.invalid/e"> %p;]>"#,
        r#"<!doctype r []>"#,
    ] {
        let raw = format!(
            r#"<?xml version="1.0"?>{payload}<p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>&x;</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#
        );
        let bytes = PptxBuilder::new()
            .slide(SlideSpec::text("Good", &["body"]))
            .slide(SlideSpec {
                raw_xml: Some(raw),
                ..Default::default()
            })
            .build();
        let report = report_of(bytes);
        assert!(
            kinds(&report).contains(&SkipKind::DoctypeRejected),
            "the DOCTYPE part must be dropped and reported"
        );
        assert_eq!(report.slides_imported, 1, "the good slide still imports");
        // A missing slide is a loss a preview cannot reveal, so the report escalates.
        assert_eq!(report.severity(), selahcue_import::Severity::Material);
    }
}

#[test]
fn the_doctype_refusal_is_on_the_raw_bytes_before_a_parser_exists() {
    // The claim in `ooxml.rs` is specific: the marker is found in the first kilobyte of the RAW
    // BYTES, "before the parser is constructed". The test above cannot see that — quick-xml
    // surfaces a real DTD as `Event::DocType`, which the walker refuses identically, so every
    // payload there passes with `has_doctype()` deleted outright and the stated property untested.
    //
    // This is the case that separates them: `<!DOCTYPE` inside an XML COMMENT. There is no
    // `Event::DocType` to catch — quick-xml sees a comment and reads happily on — so the part is
    // refused if and only if the raw-byte check ran. Refusing it is deliberate and is what
    // "failing closed on a marker" means: OOXML never legitimately carries a DTD, so a part that
    // merely mentions one is not worth the argument.
    let raw = format!(
        r#"<?xml version="1.0"?><!-- {} --><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>COMMENTED</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#,
        r#"<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/hosts">]>"#
    );
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Good", &["body"]))
        .slide(SlideSpec {
            raw_xml: Some(raw),
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(
        !deck_text(&deck).contains("COMMENTED"),
        "a part carrying the marker is dropped whether or not the parser would have flagged it"
    );
    assert!(
        kinds(&report).contains(&SkipKind::DoctypeRejected),
        "and dropped as a DOCTYPE refusal, not as a generic unreadable part: {:?}",
        report.skipped
    );

    // The other half of the same property: the check reads the first kilobyte and stops, so a
    // marker pushed past it is NOT what refuses the part. Without this the test above would also
    // pass with the window widened to the whole file, which is a different (unbounded) control.
    let padded = format!(
        r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{}</a:t></a:r></a:p><a:p><a:r><a:t>PAST THE WINDOW</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#,
        "z".repeat(1200)
    );
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(padded),
            ..Default::default()
        })
        .build();
    let (deck, _) = import(bytes).unwrap();
    assert!(
        deck_text(&deck).contains("PAST THE WINDOW"),
        "the window is a kilobyte of raw bytes, and an ordinary long part is not refused for it"
    );
}

#[test]
fn only_the_xml_built_in_entities_are_expanded() {
    let raw = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Q&amp;A &lt;live&gt; &#65; &unknown;</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            raw_xml: Some(raw.into()),
            ..Default::default()
        })
        .build();
    let (deck, _) = import(bytes).unwrap();
    let text = deck_text(&deck);
    assert!(text.contains("Q&A <live> A"), "{text}");
    // An unknown name resolves to NOTHING rather than to its own text, so a hostile file cannot
    // smuggle markup back in through a name we did not expect.
    assert!(!text.contains("unknown"), "{text}");
}

// --- B3: caps on ACTUAL inflated bytes -------------------------------------------------

#[test]
fn a_lying_header_does_not_get_past_the_streaming_counter() {
    // THE PRIMARY BOMB TEST. The member declares one kilobyte and actually inflates to sixty-four
    // mebibytes, four times the per-entry image cap. A reader that trusted the declared size would
    // admit it; only counting what actually comes out of the inflater stops this.
    //
    // Note `replacing`, not `entry`. Appending the bomb makes the archive hold TWO
    // `ppt/media/bomb.png` entries; the reader then (correctly) drops the later one as a duplicate,
    // the bomb is never inflated at all, and the assertions below run over an empty sink. That is
    // what this test did before, and it stayed green with the entire streaming counter deleted.
    //
    // And note `deflate_lowish_ratio`, not `deflate_zeros`. Pure zeros compress at roughly 1000:1,
    // so the RATIO guard refuses such a member after one mebibyte and the byte counter this test
    // names is never reached at all — the test passed with `account`'s caps removed entirely,
    // proving a control it does not mention. Diluting the stream to about 50:1 keeps the ratio
    // guard out of range and leaves the produced-byte counter as the only thing that can fire.
    let bomb = support::deflate_lowish_ratio(64 * 1024 * 1024);
    const { assert!(64 * 1024 * 1024 > selahcue_import::limits::MAX_IMAGE_ENCODED_BYTES) };
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Text survives".into()),
            body: vec!["and so does this line".into()],
            images: vec![("bomb.png".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(Entry::raw_deflated("ppt/media/bomb.png", bomb, 1024))
        .build();

    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(doc.slides.len(), 1, "the slide's text survives the bomb");
    assert!(sink.is_empty(), "the bomb never reached the sink");
    let (deck, report) = build_deck(doc, &Theme::classic(), "P", &|_| None);
    assert!(deck_text(&deck).contains("and so does this line"));
    // The SPECIFIC outcome, not merely "something was skipped": a reader that trusted the declared
    // 1 KiB would have inflated the lot and then failed the signature sniff, reporting
    // `ImageFormatUnsupported` instead — which is how you tell the two apart from the outside.
    assert_eq!(
        kinds(&report),
        vec![SkipKind::ImageTooLarge],
        "the produced-byte counter is what must stop this: {:?}",
        report.skipped
    );
}

#[test]
fn a_hostile_central_directory_is_walked_rather_than_slurped() {
    // The directory's size and every entry name in it are attacker-chosen, so neither may size an
    // allocation. Here the archive claims 4 000 entries whose names are each 65 000 bytes: a reader
    // that buffers the directory holds a quarter of a gigabyte, and one that builds a `String` per
    // name before consulting the length cap holds half a gigabyte more.
    //
    // This asserts the OUTCOME (every over-long name refused, honestly, with its own kind); the
    // allocation itself is bounded under a counting allocator in `test_memory.rs`, because a
    // functional assertion cannot see a buffer.
    let long = "n".repeat(65_000);
    let mut builder = PptxBuilder::new().slide(SlideSpec::text("Real", &["body"]));
    for i in 0..64 {
        builder = builder.entry(Entry::stored(&format!("{long}{i}"), b"x"));
    }
    let (deck, report) = import(builder.build()).unwrap();
    assert_eq!(deck.len(), 1, "the real slide still imports");
    assert_eq!(
        kinds(&report)
            .iter()
            .filter(|k| **k == SkipKind::MalformedEntryName)
            .count(),
        64,
        "every over-long name is refused — and NOT as a duplicate, which it is not"
    );
    assert!(
        !kinds(&report).contains(&SkipKind::DuplicatePart),
        "an over-long name is not a duplicate; reporting it as one tells the operator something \
         untrue about their file"
    );
    // The truncated quote is bounded too — the report detail is a fixed cap, never the name.
    let item = report
        .skipped
        .iter()
        .find(|s| s.kind == SkipKind::MalformedEntryName)
        .unwrap();
    assert!(
        item.detail.chars().count() <= selahcue_import::limits::MAX_REPORT_DETAIL_LEN,
        "detail was {} chars",
        item.detail.chars().count()
    );
}

#[test]
fn an_entry_over_the_per_entry_cap_is_dropped_and_the_import_continues() {
    let big = vec![7u8; 20 * 1024 * 1024]; // over MAX_IMAGE_ENCODED_BYTES (16 MiB)
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Huge photo".into()),
            body: vec!["text survives".into()],
            images: vec![("huge.png".into(), big)],
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("text survives"));
    assert!(kinds(&report).contains(&SkipKind::ImageTooLarge));
}

#[test]
fn an_entry_count_flood_is_refused_outright() {
    let mut builder = PptxBuilder::new().slide(SlideSpec::text("T", &["b"]));
    for i in 0..5000 {
        builder = builder.entry(Entry::stored(&format!("junk/{i}"), b""));
    }
    let err = read(builder.build()).unwrap_err();
    assert!(
        matches!(err, ImportError::TooManyEntries { .. }),
        "got {err:?}"
    );
}

#[test]
fn an_entry_flood_that_under_declares_itself_is_still_stopped_inside_the_walk() {
    // There are TWO entry-count controls: a cheap refusal on the count the end-of-central-directory
    // record declares, and a cap inside the directory walk itself. While the EOCD number is honest
    // the first one always fires, so the second is unreachable — the test above passes with the
    // in-walk cap deleted, proving a control it does not name.
    //
    // A hostile archive has no reason to be honest. This one declares ONE entry and carries five
    // thousand records, which is exactly how the cheap check is slipped past, and only the in-walk
    // cap is left to stop it.
    let mut builder = PptxBuilder::new().slide(SlideSpec::text("T", &["b"]));
    for i in 0..5000 {
        builder = builder.entry(Entry::stored(&format!("junk/{i}"), b""));
    }
    builder.declared_entries = Some(1);
    let err = read(builder.build()).unwrap_err();
    assert!(
        matches!(
            err,
            ImportError::TooManyEntries {
                limit: selahcue_import::limits::MAX_ZIP_ENTRIES
            }
        ),
        "the walk itself must stop at the cap, whatever the record claims: got {err:?}"
    );
}

#[test]
fn zip64_and_encrypted_archives_are_refused_with_an_honest_error() {
    // ZIP64: the end-of-central-directory locator signature, appended where the reader scans.
    let mut z = PptxBuilder::new()
        .slide(SlideSpec::text("T", &["b"]))
        .build();
    z.extend_from_slice(&0x0706_4b50u32.to_le_bytes());
    z.extend_from_slice(&[0u8; 16]);
    assert_eq!(read(z).unwrap_err(), ImportError::Zip64Unsupported);

    // An entry with the encryption flag set cannot be inspected, so the part is dropped; a
    // wholly-encrypted archive is refused.
    let all_encrypted = support::zip(&[Entry::stored("a", b"x").encrypted()]);
    assert_eq!(
        read(all_encrypted).unwrap_err(),
        ImportError::EncryptedArchive
    );
}

#[test]
fn a_single_encrypted_part_costs_that_part_and_never_reaches_the_inflater() {
    // The whole-archive `all_encrypted` check above answers the case where EVERY entry is flagged,
    // and it fired first for the one-entry fixture — so the PER-ENTRY refusal in `read_entry`, the
    // one that matters for a partially encrypted archive, had no test at all.
    //
    // Observable only because the refused part's payload is a perfectly good deflate stream that
    // WOULD decode: with the per-entry check the entry is refused unread; without it the reader
    // falls through to the inflater, the stream decodes, and "ENCRYPTED PAYLOAD" reaches the
    // audience screen. A flag is not a cipher, which is precisely why it must be honoured.
    let smuggled = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>ENCRYPTED PAYLOAD</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Real", &["body"]))
        .slide(SlideSpec::text("Hostile", &["replaced below"]))
        .replacing(Entry::deflated("ppt/slides/slide2.xml", smuggled.as_bytes()).encrypted())
        .build();
    let (deck, report) = import(bytes).unwrap();

    assert!(
        !deck_text(&deck).contains("ENCRYPTED PAYLOAD"),
        "an entry flagged encrypted must never be handed to the inflater"
    );
    assert_eq!(report.slides_imported, 1, "the good slide still imports");
    assert!(
        kinds(&report).contains(&SkipKind::UnreadablePart),
        "the refused part is reported, not silently missing: {:?}",
        report.skipped
    );
}

#[test]
fn an_unsupported_compression_method_drops_the_entry() {
    // The method allowlist is only observable if the payload WOULD have read successfully without
    // it. So the hostile part carries a perfectly good deflate stream and merely claims method 93
    // (zstd): with the allowlist the entry is refused unread; without it the reader falls through
    // to the inflater, the stream decodes, and "ZSTD PAYLOAD" reaches the audience screen.
    let smuggled = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>ZSTD PAYLOAD</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Real", &["body"]))
        .slide(SlideSpec::text("Hostile", &["replaced below"]))
        .replacing(Entry::deflated("ppt/slides/slide2.xml", smuggled.as_bytes()).with_method(93))
        .build();
    let (deck, report) = import(bytes).unwrap();

    assert!(
        !deck_text(&deck).contains("ZSTD PAYLOAD"),
        "an entry in a compression method we do not admit must never be decoded"
    );
    assert_eq!(report.slides_imported, 1, "the good slide still imports");
    assert!(
        kinds(&report).contains(&SkipKind::UnreadablePart),
        "the refused part is reported, not silently missing: {:?}",
        report.skipped
    );

    // And the same on the media path, where the refusal costs a picture rather than a slide.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Photo".into()),
            body: vec!["text survives".into()],
            images: vec![("image1.png".into(), support::png(2, 2))],
            ..Default::default()
        })
        .replacing(
            Entry::deflated("ppt/media/image1.png", &support::png(2, 2)).with_method(93), // zstd
        )
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("text survives"));
    assert_eq!(report.images_imported, 0);
    assert!(kinds(&report).contains(&SkipKind::ImageUnreadable));
}

#[test]
fn duplicate_part_names_resolve_first_wins_and_report_the_rest() {
    // Otherwise a crafted archive can make the parser read one copy and the extractor take the
    // other.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Real", &["body"]))
        .entry(Entry::deflated(
            "ppt/slides/slide1.xml",
            br#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>IMPOSTOR</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#,
        ))
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("Real"));
    assert!(!deck_text(&deck).contains("IMPOSTOR"));
    assert!(kinds(&report).contains(&SkipKind::DuplicatePart));
}

// --- B4/C4: XML pathology --------------------------------------------------------------

#[test]
fn deeply_nested_xml_is_dropped_rather_than_overflowing_the_stack() {
    // Ten thousand deep, run on a SMALL stack on purpose: a recursion regression must fail here
    // rather than pass because the main thread's stack happens to be large.
    let mut xml =
        String::from(r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree>"#);
    for _ in 0..10_000 {
        xml.push_str("<p:grpSp>");
    }
    for _ in 0..10_000 {
        xml.push_str("</p:grpSp>");
    }
    xml.push_str("</p:spTree></p:cSld></p:sld>");
    // The archive is assembled on the NORMAL stack; only the parse runs on the small one, so
    // what this measures is the parser's stack use and nothing else.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Good", &["body"]))
        .slide(SlideSpec {
            raw_xml: Some(xml),
            ..Default::default()
        })
        .build();
    let deep = std::thread::Builder::new()
        .stack_size(128 * 1024)
        .spawn(move || report_of(bytes))
        .unwrap()
        .join()
        .expect("the parser must be iterative — a stack overflow would kill this thread");
    assert!(kinds(&deep).contains(&SkipKind::UnreadablePart));
    assert_eq!(deep.slides_imported, 1);
}

#[test]
fn a_legal_but_pathological_part_exhausts_its_event_budget_and_is_dropped() {
    // The depth cap does not bound this: the document is two levels deep and perfectly
    // well-formed, just endless. An element flood is individually tiny and collectively unbounded,
    // which is what the per-part event budget is for — and it had no test at all.
    //
    // The flood is followed by real text, so a build with the budget removed does not merely take
    // longer: it imports "PATHOLOGICAL", which is what the assertion looks for.
    let mut xml = String::from(
        r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody>"#,
    );
    for _ in 0..(selahcue_import::limits::MAX_XML_EVENTS_PER_PART + 10) {
        xml.push_str("<a:x/>");
    }
    xml.push_str(
        r#"<a:p><a:r><a:t>PATHOLOGICAL</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#,
    );
    // STORED, not deflated. An element flood compresses at hundreds to one, so a deflated
    // fixture is refused by the ZIP RATIO GUARD long before a single event is read — the part
    // came back as `UnreadablePart` either way, and this test passed with the event budget
    // deleted entirely. Storing it takes the ratio guard out of range and leaves the budget as
    // the only control that can stop the walk.
    let flood = xml.into_bytes();
    assert!(
        flood.len() < selahcue_import::limits::MAX_XML_PART_BYTES,
        "and the part must stay under the per-part byte cap, or THAT is what refuses it"
    );
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Good", &["body"]))
        .slide(SlideSpec {
            raw_xml: Some(String::new()),
            ..Default::default()
        })
        .replacing(Entry::stored("ppt/slides/slide2.xml", &flood))
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(
        !deck_text(&deck).contains("PATHOLOGICAL"),
        "the part must be abandoned at its event budget, not parsed to the end"
    );
    assert_eq!(report.slides_imported, 1, "the good slide still imports");
    assert!(kinds(&report).contains(&SkipKind::UnreadablePart));
}

#[test]
fn a_mismatched_end_tag_is_an_error_not_a_silent_recovery() {
    let raw = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>x</a:t></a:wrong></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Good", &["body"]))
        .slide(SlideSpec {
            raw_xml: Some(raw.into()),
            ..Default::default()
        })
        .build();
    let report = report_of(bytes);
    assert!(kinds(&report).contains(&SkipKind::UnreadablePart));
}

#[test]
fn a_truncated_or_garbage_archive_fails_cleanly() {
    let good = PptxBuilder::new()
        .slide(SlideSpec::text("T", &["b"]))
        .build();
    // A cut that removes the end-of-central-directory record leaves nothing to read.
    for cut in [0, 1, 21, good.len() / 3, good.len() / 2] {
        let r = read(good[..cut].to_vec());
        assert!(r.is_err(), "a truncation at {cut} must fail cleanly");
    }
    // Every OTHER truncation must still be a typed outcome rather than a panic. Some of them
    // legitimately succeed — losing the last byte of the archive comment costs nothing — and
    // that is the correct, forgiving behaviour, not a hole.
    for cut in 0..good.len() {
        let r = std::panic::catch_unwind(|| read(good[..cut].to_vec()).is_ok());
        assert!(r.is_ok(), "a truncation at {cut} panicked");
    }
    assert!(read(b"not a zip at all".to_vec()).is_err());
    assert!(read(Vec::new()).is_err());
}

// --- caps on content -------------------------------------------------------------------

#[test]
fn the_picture_and_image_caps_stop_the_walk_and_report() {
    use selahcue_import::limits::MAX_PICTURES_PER_SLIDE;
    let png = support::png(2, 2);
    let images: Vec<(String, Vec<u8>)> = (0..(MAX_PICTURES_PER_SLIDE + 5))
        .map(|i| (format!("image{i}.png"), png.clone()))
        .collect();
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Many".into()),
            images,
            ..Default::default()
        })
        .build();
    let (doc, _) = read(bytes).unwrap();
    assert_eq!(doc.slides[0].pictures.len(), MAX_PICTURES_PER_SLIDE);
    let (deck, report) = build_deck(doc, &Theme::classic(), "P", &|slot| {
        MediaRef::new(&format!("/app/media/import-{}.png", slot.0))
    });
    assert!(kinds(&report).contains(&SkipKind::LimitReached(LimitKind::Pictures)));
    assert!(deck.within_bounds());
}

#[test]
fn the_title_and_line_caps_cut_on_the_pptx_path_and_say_so() {
    use selahcue_import::limits::{MAX_SLIDE_LINES, MAX_TITLE_LEN};
    // Both caps shipped with no test on this path at all. A title is capped far tighter than a
    // body line — two hundred characters against two thousand — because it lands in a fixed-size
    // header pill that clips rather than wraps, so a silent cut there is a title the operator
    // never sees the end of.
    let overhang = 30;
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("T".repeat(MAX_TITLE_LEN + overhang)),
            body: (0..(MAX_SLIDE_LINES + overhang))
                .map(|i| format!("line {i}"))
                .collect(),
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();

    let title = report
        .truncations
        .iter()
        .find(|t| t.what == selahcue_import::TruncatedField::Title)
        .expect("the over-long title is reported as cut");
    assert_eq!((title.kept, title.dropped), (MAX_TITLE_LEN, overhang));

    let lines = report
        .truncations
        .iter()
        .find(|t| t.what == selahcue_import::TruncatedField::BodyLines)
        .expect("the surplus lines are reported as dropped");
    assert_eq!((lines.kept, lines.dropped), (MAX_SLIDE_LINES, overhang));

    let text = deck_text(&deck);
    assert!(
        text.lines().next().unwrap().chars().count() <= MAX_TITLE_LEN,
        "the title really was cut, not merely reported as cut"
    );
    assert!(
        !text.contains(&format!("line {}", MAX_SLIDE_LINES + 1)),
        "and the surplus lines really are absent"
    );
    // Cut body content is a loss a preview cannot reveal.
    assert_eq!(report.severity(), selahcue_import::Severity::Material);
}

#[test]
fn cutting_text_on_more_slides_than_the_report_can_list_is_counted_not_forgotten() {
    // `truncations_overflow` had zero hits anywhere in the suite. It exists for the case that is
    // easiest to miss: a deck that cut text on more than a hundred slides used to list the first
    // hundred and drop the rest IN SILENCE — silent truncation of the record of truncation.
    use selahcue_import::limits::{MAX_REPORT_ITEMS, MAX_TITLE_LEN};
    let mut builder = PptxBuilder::new();
    for i in 0..(MAX_REPORT_ITEMS + 20) {
        builder = builder.slide(SlideSpec {
            title: Some(format!("{i} {}", "T".repeat(MAX_TITLE_LEN))),
            ..Default::default()
        });
    }
    let report = report_of(builder.build());
    assert_eq!(
        report.truncations.len(),
        MAX_REPORT_ITEMS,
        "the list itself stays bounded — the report must not become an unbounded buffer"
    );
    assert!(
        report.truncations_overflow >= 20,
        "and everything past the cap is COUNTED: {}",
        report.truncations_overflow
    );
    assert!(!report.is_lossless());
    assert_eq!(report.severity(), selahcue_import::Severity::Material);
}

#[test]
fn cancellation_is_honoured_and_mutates_nothing() {
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("A", &["x"]))
        .slide(SlideSpec::text("B", &["y"]))
        .build();
    let mut src = MemorySource::new(bytes);
    let mut sink = RecordingSink::new();
    let err = selahcue_import::read_pptx(&mut src, source(), &mut sink, &|| true).unwrap_err();
    assert_eq!(err, ImportError::Cancelled);
    assert!(sink.is_empty(), "a cancelled import stages nothing");
}

#[test]
fn a_short_reading_or_lying_byte_source_produces_a_typed_error_never_a_panic() {
    /// A source that claims to be far longer than it is, and errors past the real end.
    struct Lying(Vec<u8>);
    impl selahcue_import::ByteSource for Lying {
        fn len(&self) -> u64 {
            u64::MAX / 2
        }
        fn read_exact_at(
            &mut self,
            offset: u64,
            buf: &mut [u8],
        ) -> Result<(), selahcue_import::SourceError> {
            let start =
                usize::try_from(offset).map_err(|_| selahcue_import::SourceError::OutOfRange)?;
            let end = start
                .checked_add(buf.len())
                .ok_or(selahcue_import::SourceError::OutOfRange)?;
            let src = self
                .0
                .get(start..end)
                .ok_or(selahcue_import::SourceError::OutOfRange)?;
            buf.copy_from_slice(src);
            Ok(())
        }
    }
    let mut src = Lying(
        PptxBuilder::new()
            .slide(SlideSpec::text("T", &["b"]))
            .build(),
    );
    let mut sink = RecordingSink::new();
    let r = selahcue_import::read_pptx(&mut src, source(), &mut sink, &never());
    assert!(r.is_err(), "a lying source must produce a typed error");
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
