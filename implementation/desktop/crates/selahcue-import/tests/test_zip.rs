//! The archive layer's controls, observed through the only door they have — `read_pptx`.
//!
//! Every constant here previously had **no test at all**: `MAX_TOTAL_INFLATED_BYTES`,
//! `MAX_COMPRESSION_RATIO`, `MAX_ENTRY_INFLATED_BYTES` and `MAX_IMPORT_IMAGES` were enforced in
//! code and asserted nowhere, and a grep for `ArchiveTooLarge`, `RatioExceeded`, `EntryTooLarge`
//! or `UnsupportedMethod` across `tests/` returned nothing. A cap nobody tests is a cap that gets
//! deleted in a refactor and noticed on a church PC.
//!
//! **The bar every test here is written to:** it must FAIL if the control it names is removed.
//! That is harder than it sounds, because most of these controls share a report entry with some
//! other refusal — an over-large image and an unreadable one both come back as "an image was
//! skipped". So each case is constructed so that *removing the control produces a different,
//! observable outcome*: a stream that would otherwise decode, a part that would otherwise be
//! found, an import that would otherwise succeed. Where two controls genuinely collapse to one
//! outcome, the case is built so only one of them can fire.

#![allow(clippy::unwrap_used)]

mod support;

use support::{Entry, PptxBuilder, SlideSpec};

use selahcue_import::{
    build_deck, limits, ImportError, ImportReport, ImportSource, MemorySource, RecordingSink,
    SkipKind,
};
use selahcue_present::Theme;

fn never() -> impl Fn() -> bool {
    || false
}

fn source() -> ImportSource {
    ImportSource::Pptx {
        name: "Hostile".into(),
    }
}

fn read(bytes: Vec<u8>) -> Result<(selahcue_import::ImportedDocument, RecordingSink), ImportError> {
    let mut src = MemorySource::new(bytes);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(&mut src, source(), &mut sink, &never())?;
    Ok((doc, sink))
}

fn import(bytes: Vec<u8>) -> Result<(selahcue_present::SlideDeck, ImportReport), ImportError> {
    let (doc, _) = read(bytes)?;
    Ok(build_deck(doc, &Theme::classic(), "Hostile", &|_| None))
}

fn kinds(report: &ImportReport) -> Vec<SkipKind> {
    report.skipped.iter().map(|s| s.kind).collect()
}

fn deck_text(deck: &selahcue_present::SlideDeck) -> String {
    deck.slides()
        .iter()
        .flat_map(|s| s.elements.iter())
        .filter_map(|e| match e {
            selahcue_present::Element::Text { text, .. } => Some(text.clone()),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join("\n")
}

// --- MAX_TOTAL_INFLATED_BYTES ----------------------------------------------------------

#[test]
fn the_whole_archive_budget_aborts_the_import_that_the_per_entry_cap_would_let_run_forever() {
    // **The load-bearing bound.** A per-entry cap alone, times four thousand entries, is not a
    // bound at all: each of these members is individually stopped at the 16 MiB image cap and
    // individually unremarkable, and seventeen of them still walk the process through a quarter of
    // a gigabyte. Only the running whole-archive total sees that.
    //
    // Removing it turns this into a successful import of seventeen text slides, which is precisely
    // the shape of the failure — nothing looks wrong from the outside while the memory goes.
    //
    // The members are deliberately only ~50:1 compressible. A bomb of pure zeros never reaches
    // either byte counter: the ratio guard refuses it after one mebibyte, so the archive total
    // would never be approached and the test would be asserting the wrong control.
    let bomb = support::deflate_lowish_ratio(17 * 1024 * 1024);
    let per_entry = limits::MAX_IMAGE_ENCODED_BYTES;
    let needed = limits::MAX_TOTAL_INFLATED_BYTES / per_entry + 1;

    let mut builder = PptxBuilder::new();
    for i in 0..needed {
        builder = builder.slide(SlideSpec {
            title: Some(format!("Slide {i}")),
            images: vec![(format!("bomb{i}.png"), Vec::new())],
            ..Default::default()
        });
    }
    for i in 0..needed {
        builder = builder.replacing(Entry::raw_deflated(
            &format!("ppt/media/bomb{i}.png"),
            bomb.clone(),
            1024,
        ));
    }

    let err = read(builder.build()).unwrap_err();
    assert_eq!(
        err,
        ImportError::ArchiveTooLarge {
            limit: limits::MAX_TOTAL_INFLATED_BYTES
        },
        "the running total across the archive must abort the import"
    );
}

#[test]
fn a_stored_photograph_is_not_charged_to_the_bomb_budget() {
    // The defect this pins: `MAX_TOTAL_INFLATED_BYTES` counted STORED members too, and a stored
    // member is an already-compressed photograph copied out byte for byte. It expands by nothing,
    // so it cannot be a bomb, and its total is bounded by the file the shell already admitted —
    // yet a legitimate 278 MiB photo deck was refused wholesale, zero slides in half a second,
    // while a 242 MiB one passed with 14 MiB to spare.
    //
    // Constructed so ONLY that distinction can decide the outcome: seventeen deflate members take
    // the inflation total to 255 MiB, one mebibyte under the cap, and then a two-mebibyte STORED
    // photograph asks to be read. Charging it to the inflate budget aborts the whole import;
    // charging it where it belongs stages the photograph.
    let filler = support::deflate_lowish_ratio(15 * 1024 * 1024);
    let inflating = 17;
    const { assert!(17 * 15 * 1024 * 1024 < limits::MAX_TOTAL_INFLATED_BYTES) };
    const { assert!(17 * 15 * 1024 * 1024 + 2 * 1024 * 1024 > limits::MAX_TOTAL_INFLATED_BYTES) };

    // A valid PNG followed by two mebibytes of padding: everything after `IEND` is ignored by the
    // format, so this probes as an 8×8 image while occupying a real two mebibytes on the way in.
    let mut photo = support::png(8, 8);
    photo.extend(std::iter::repeat_n(0u8, 2 * 1024 * 1024));

    let mut builder = PptxBuilder::new();
    for i in 0..inflating {
        builder = builder.slide(SlideSpec {
            title: Some(format!("Filler {i}")),
            images: vec![(format!("filler{i}.bin"), Vec::new())],
            ..Default::default()
        });
    }
    builder = builder.slide(SlideSpec {
        title: Some("The photograph".into()),
        body: vec!["and its caption".into()],
        images: vec![("photo.png".into(), Vec::new())],
        ..Default::default()
    });
    for i in 0..inflating {
        builder = builder.replacing(Entry::raw_deflated(
            &format!("ppt/media/filler{i}.bin"),
            filler.clone(),
            15 * 1024 * 1024,
        ));
    }
    builder = builder.replacing(Entry::stored("ppt/media/photo.png", &photo));

    let (doc, sink) = read(builder.build()).expect("a big photo deck is not a bomb");
    assert_eq!(
        sink.len(),
        1,
        "the stored photograph must still be extracted after 255 MiB of inflation"
    );
    assert_eq!(sink.staged()[0].1.width, 8);
    let (deck, _) = build_deck(doc, &Theme::classic(), "Hostile", &|_| None);
    assert!(deck_text(&deck).contains("and its caption"));
}

#[test]
fn an_archive_that_asks_to_be_read_many_times_its_own_size_degrades_to_text() {
    // The WORK budget, and the only shape that can reach it. Central-directory records each carry
    // a local offset and nothing in the format stops many of them naming the same one, so a
    // fifteen-mebibyte file can declare fifty-two distinct photographs and ask for七hundred and
    // eighty mebibytes of reads. The extraction budget is what bounds that.
    //
    // And its breach DEGRADES: the slides' text imports, every image that did not fit is reported,
    // and the operator gets their words. Aborting here would contradict the partial-import rule
    // every other failure in this crate keeps — a deck whose photographs are collectively enormous
    // is a big deck, not a hostile one. The *bomb* budget is a different bound and still aborts,
    // which the test above this one pins.
    let mut photo = support::png(8, 8);
    photo.extend(std::iter::repeat_n(0u8, 15 * 1024 * 1024));
    let size = photo.len() as u32;
    let per_read = photo.len();
    let needed = limits::MAX_TOTAL_EXTRACTED_BYTES / per_read + 2;

    // A sink that counts rather than keeps: fifty staged fifteen-mebibyte images retained would be
    // three quarters of a gigabyte of fixture, which is the test measuring itself.
    #[derive(Default)]
    struct CountingSink(usize);
    impl selahcue_import::MediaSink for CountingSink {
        fn stage(
            &mut self,
            _bytes: &[u8],
            _probe: &selahcue_import::ImageProbe,
        ) -> Result<selahcue_import::MediaSlot, selahcue_import::StoreError> {
            self.0 += 1;
            Ok(selahcue_import::MediaSlot(self.0 as u32))
        }
    }

    let per_slide = limits::MAX_PICTURES_PER_SLIDE;
    let slides = needed / per_slide + 1;
    let mut builder = PptxBuilder::new();
    for s in 0..slides {
        builder = builder.slide(SlideSpec {
            title: Some(format!("Photos {s}")),
            body: vec!["the text still arrives".into()],
            images: (0..per_slide)
                .map(|k| (format!("shot-{s}-{k}.png"), Vec::new()))
                .collect(),
            ..Default::default()
        });
    }
    // One real member; every other record borrows its local header and payload.
    builder = builder.replacing(Entry::stored("ppt/media/shot-0-0.png", &photo));
    for s in 0..slides {
        for k in 0..per_slide {
            if s == 0 && k == 0 {
                continue;
            }
            builder = builder.replacing(Entry::aliasing(
                &format!("ppt/media/shot-{s}-{k}.png"),
                "ppt/media/shot-0-0.png",
                size,
            ));
        }
    }

    let mut src = MemorySource::new(builder.build());
    let mut sink = CountingSink::default();
    let doc = selahcue_import::read_pptx(&mut src, source(), &mut sink, &never())
        .expect("an enormous deck degrades, it does not abort");
    let staged = sink.0;
    let (deck, report) = build_deck(doc, &Theme::classic(), "Hostile", &|_| None);

    assert!(
        deck_text(&deck).contains("the text still arrives"),
        "the slides' TEXT is what degrading preserves"
    );
    assert!(
        staged > 0 && staged < needed,
        "some images fit and some did not: staged {staged} of {needed}"
    );
    assert!(
        kinds(&report).contains(&SkipKind::MediaBudgetExhausted),
        "every image that did not fit must be reported: {:?}",
        report.skipped
    );
    // And the recovery is in the copy, as it is for every other drop.
    assert!(
        SkipKind::MediaBudgetExhausted
            .message()
            .contains("text was"),
        "{}",
        SkipKind::MediaBudgetExhausted.message()
    );
}

// --- MAX_COMPRESSION_RATIO -------------------------------------------------------------

#[test]
fn a_high_ratio_member_is_refused_even_though_it_never_approaches_the_byte_cap() {
    // Two mebibytes of zeros: an eighth of the per-entry cap, so the byte counter cannot be what
    // stops it — the ratio guard is the only control in range. Without it the member inflates
    // happily and is refused one step later for the unrelated reason that it is not an image, so
    // the two are told apart by WHICH refusal comes back.
    let zeros = support::deflate_zeros(2 * 1024 * 1024);
    // The premise, pinned: this member is well under the per-entry cap, so that cap cannot be what
    // refuses it. If the cap were ever lowered past this, the test would silently start proving a
    // different control than the one it names.
    const { assert!(2 * 1024 * 1024 < limits::MAX_IMAGE_ENCODED_BYTES) };

    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Compressible".into()),
            body: vec!["text survives".into()],
            images: vec![("flat.png".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(Entry::raw_deflated(
            "ppt/media/flat.png",
            zeros,
            2 * 1024 * 1024,
        ))
        .build();

    let (deck, report) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("text survives"));
    assert_eq!(
        kinds(&report),
        vec![SkipKind::ImageTooLarge],
        "the ratio guard refused it; `ImageFormatUnsupported` here would mean it inflated in full"
    );
}

#[test]
fn a_small_legitimately_compressible_part_does_not_trip_the_ratio_guard() {
    // The guard's floor exists so ordinary XML — which compresses superbly — is never refused for
    // being compressible. A guard that fires on real files gets turned off.
    let body: Vec<String> = (0..60).map(|i| format!("Verse line {i}")).collect();
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Very repetitive".into()),
            body: body.clone(),
            ..Default::default()
        })
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert_eq!(deck.len(), 1);
    assert!(
        report.is_lossless(),
        "an ordinary compressible slide must import cleanly: {:?}",
        report.skipped
    );
}

// --- MAX_ENTRY_INFLATED_BYTES ----------------------------------------------------------

/// `n` bytes of a cheap non-repeating sequence — incompressible enough that the ratio guard is
/// out of the picture, and not starting with any signature the allowlist would recognise.
fn incompressible(n: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(n);
    let mut state: u32 = 0x1234_5678;
    while out.len() < n {
        state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
        out.extend_from_slice(&state.to_le_bytes());
    }
    out.truncate(n);
    // Never let the sequence start with a real magic number.
    out[0] = b'Z';
    out
}

#[test]
fn a_stored_member_past_the_per_entry_cap_is_stopped_by_the_produced_byte_counter() {
    // Stored (method 0), so no inflation and no ratio to judge, AND declaring a kilobyte it is
    // not — so the cheap declared-size early abort cannot fire either. That leaves exactly one
    // control able to refuse this member: the counter on bytes actually produced.
    //
    // Its content is not a recognised signature, so deleting that counter produces
    // `ImageFormatUnsupported` (twenty mebibytes read, then not an image) rather than
    // `ImageTooLarge` — which is how the assertion tells "the cap fired" from "the cap is gone".
    let big = incompressible(limits::MAX_IMAGE_ENCODED_BYTES + 4 * 1024 * 1024);
    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Huge photo".into()),
            body: vec!["text survives".into()],
            images: vec![("huge.png".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(Entry::stored("ppt/media/huge.png", &big).claiming(1024))
        .build();

    let (deck, report) = import(bytes).unwrap();
    assert!(deck_text(&deck).contains("text survives"));
    assert_eq!(
        kinds(&report),
        vec![SkipKind::ImageTooLarge],
        "the per-entry byte cap must be what refused it"
    );
}

// --- the stored-entry extent -----------------------------------------------------------

#[test]
fn a_stored_members_extent_is_its_compressed_size_not_the_size_it_declares() {
    // For a stored member the on-disk extent IS the compressed size; `declared_size` is an
    // independent field the archive may set to anything. Reading `declared_size` bytes instead
    // means an UNDER-declaring member is silently truncated to the prefix it named, and an
    // OVER-declaring one is served the bytes of whatever follows it in the archive — the next
    // local header and the next member's payload — as its own content.
    let slide = r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>THE WHOLE PART ARRIVED</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#;

    // Under-declaring: ten bytes, against a part several hundred long.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("placeholder", &["replaced below"]))
        .replacing(Entry::stored("ppt/slides/slide1.xml", slide.as_bytes()).claiming(10))
        .build();
    let (deck, report) = import(bytes).unwrap();
    assert!(
        deck_text(&deck).contains("THE WHOLE PART ARRIVED"),
        "an under-declared stored member must not be truncated to what it claims: {:?}",
        report.skipped
    );

    // Over-declaring: five thousand bytes, which runs off the end of the part and into the
    // archive bytes that follow it.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("placeholder", &["replaced below"]))
        .replacing(Entry::stored("ppt/slides/slide1.xml", slide.as_bytes()).claiming(5000))
        .entry(Entry::stored("zz-trailing.bin", b"ADJACENT ARCHIVE BYTES"))
        .build();
    let (deck, report) = import(bytes).unwrap();
    let text = deck_text(&deck);
    assert!(
        text.contains("THE WHOLE PART ARRIVED"),
        "an over-declared stored member must still read exactly its own extent: {:?}",
        report.skipped
    );
    assert!(
        !text.contains("ADJACENT"),
        "the next member's bytes must never be served as this part's content: {text}"
    );
}

#[test]
fn a_deflate_member_is_never_served_its_neighbours_content() {
    // The stored path has this property tested; the DEFLATE path did not, and its failure mode is
    // worse. `read_deflate` advances the read cursor by what the inflater ACTUALLY consumed, not
    // by the size of the chunk it was handed, because the inner loop can leave early with input
    // still unread — and advancing by the chunk there would skip those bytes and resume in the
    // middle of a deflate block, quietly decoding a DIFFERENT member's content than the archive
    // holds. Quietly wrong content is the one outcome no cap catches.
    //
    // So: a deflate slide part, immediately followed in the archive by another deflate member
    // whose content is unmistakable. The slide's own text must arrive whole and the neighbour's
    // must not appear at all.
    // Padding that does NOT compress well, so the member really is several 64 KiB input chunks
    // long and the read cursor is advanced many times. A single-chunk member could not tell the
    // two advance rules apart at all.
    let mut state: u32 = 0x1234_5678;
    let mut padding = String::new();
    for _ in 0..3000 {
        let token: String = (0..40)
            .map(|_| {
                state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                char::from(b'a' + ((state >> 24) % 26) as u8)
            })
            .collect();
        padding.push_str(&format!("<a:p><a:r><a:t>{token}</a:t></a:r></a:p>"));
    }
    // The title sits at the very END of the part, after all of it. A cursor that skipped unread
    // input would resume mid-deflate-block, the XML would stop being well-formed, and the whole
    // part would come back as an unreadable one — so the marker arriving is the proof that every
    // chunk was decoded, in order, from this member and no other.
    let slide = format!(
        r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody>{padding}</p:txBody></p:sp><p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>TAIL MARKER</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#
    );
    let deflated = support::deflate(slide.as_bytes());
    assert!(
        deflated.len() > 64 * 1024,
        "the fixture must span several read chunks to exercise the cursor at all; it is {} bytes",
        deflated.len()
    );
    let neighbour = "NEIGHBOURING MEMBER PAYLOAD".repeat(4096);

    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("placeholder", &["replaced below"]))
        .replacing(Entry::deflated("ppt/slides/slide1.xml", slide.as_bytes()))
        .entry(Entry::deflated("zz-neighbour.bin", neighbour.as_bytes()))
        .build();

    let (deck, report) = import(bytes).unwrap();
    let text = deck_text(&deck);
    assert!(
        text.contains("TAIL MARKER"),
        "the member's LAST bytes must arrive, decoded in order: {:?}",
        report.skipped
    );
    assert!(
        !text.contains("NEIGHBOURING"),
        "and the next member's bytes must never be served as this part's content: {text}"
    );
}

// --- MAX_IMPORT_IMAGES -----------------------------------------------------------------

#[test]
fn the_whole_deck_image_cap_stops_staging_and_reports_rather_than_growing_the_media_store() {
    // The per-slide cap bounds one slide; this bounds the import. Thirteen slides at the per-slide
    // maximum reference two hundred and eight distinct images, and exactly the cap is staged.
    let png = support::png(2, 2);
    let per_slide = limits::MAX_PICTURES_PER_SLIDE;
    let slides = limits::MAX_IMPORT_IMAGES / per_slide + 1;

    let mut builder = PptxBuilder::new();
    for s in 0..slides {
        let images: Vec<(String, Vec<u8>)> = (0..per_slide)
            .map(|k| (format!("image-{s}-{k}.png"), png.clone()))
            .collect();
        builder = builder.slide(SlideSpec {
            title: Some(format!("Slide {s}")),
            images,
            ..Default::default()
        });
    }

    let (doc, sink) = read(builder.build()).unwrap();
    assert_eq!(
        sink.len(),
        limits::MAX_IMPORT_IMAGES,
        "exactly the cap is staged — no more, and not zero"
    );
    let (_, report) = build_deck(doc, &Theme::classic(), "Hostile", &|_| None);
    assert!(
        kinds(&report).contains(&SkipKind::LimitReached(selahcue_import::LimitKind::Images)),
        "reaching the cap is reported, never silent: {:?}",
        report.skipped
    );
}

// --- names -----------------------------------------------------------------------------

#[test]
fn a_nul_bearing_entry_name_is_refused_with_its_own_kind_not_as_a_duplicate() {
    // The two facts are different and the operator-facing sentences say different things. "The
    // first copy was used" is a false statement about a file that had no first copy.
    let bytes = PptxBuilder::new()
        .slide(SlideSpec::text("Real", &["body"]))
        .entry(Entry::stored("ppt/media/ev\0il.png", b"x"))
        .build();
    let report = import(bytes).unwrap().1;
    assert!(kinds(&report).contains(&SkipKind::MalformedEntryName));
    assert!(!kinds(&report).contains(&SkipKind::DuplicatePart));
    assert!(
        SkipKind::MalformedEntryName
            .message()
            .contains("unusable name"),
        "{}",
        SkipKind::MalformedEntryName.message()
    );
}

#[test]
fn a_refused_name_can_never_shadow_the_part_it_folds_onto() {
    // An entry the reader refuses must not enter the duplicate set: if it did, a hostile archive
    // could name a part badly ON PURPOSE and make the legitimate part that folds to the same key
    // read as "a duplicate", so it is never found and its content silently disappears. The refusal
    // must cost only the refused entry.
    //
    // The version this replaces could not observe that at all, and would have passed with the
    // whole `!bad_name &&` guard deleted. Two things made it vacuous:
    //
    //  * `slide1.xml` plus 512 `x`s truncates at the name cap to `ppt/slides/slide1.xmlxxx…`,
    //    which folds onto NOTHING in the archive. There was no victim, so no shadowing was
    //    possible whatever the code did.
    //  * it APPENDED the hostile entry, and first occurrence wins — an entry can only ever shadow
    //    one it precedes.
    //
    // So: a victim part whose name is EXACTLY the cap, reached through a relationship target so it
    // has to be looked up by name; and a hostile record that is that same name plus one character,
    // placed FIRST, so its truncated form folds precisely onto the victim's.
    let victim_stem = format!("{}.png", "v".repeat(limits::MAX_ZIP_NAME_LEN - 14));
    let victim = format!("ppt/media/{victim_stem}");
    assert_eq!(
        victim.len(),
        limits::MAX_ZIP_NAME_LEN,
        "the victim's name must sit exactly ON the cap, or the truncated hostile name folds \
         somewhere else and this proves nothing"
    );
    let hostile = format!("{victim}x");

    let bytes = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Real".into()),
            body: vec!["body".into()],
            images: vec![(victim_stem.clone(), support::png(2, 2))],
            ..Default::default()
        })
        .first(Entry::stored(&hostile, b"shadow"))
        .build();

    let (doc, sink) = read(bytes).unwrap();
    assert_eq!(
        sink.len(),
        1,
        "the victim part must still be found and staged — a refused name may not shadow it"
    );
    assert_eq!(doc.slides[0].pictures.len(), 1);

    let (deck, report) = build_deck(doc, &Theme::classic(), "Hostile", &|_| None);
    assert_eq!(deck.len(), 1, "the legitimate slide is untouched");
    assert!(deck_text(&deck).contains("Real"));
    // The hostile record is reported for what it is, and NOT as a duplicate: "the first copy was
    // used" is a false statement about a file that had no first copy.
    assert!(kinds(&report).contains(&SkipKind::MalformedEntryName));
    assert!(
        !kinds(&report).contains(&SkipKind::DuplicatePart),
        "{:?}",
        report.skipped
    );
}
