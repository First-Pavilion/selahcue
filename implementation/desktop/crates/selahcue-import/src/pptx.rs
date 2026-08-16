//! Orchestration: archive in, [`ImportedDocument`] out.
//!
//! This is where the partial-import rule is actually kept. Almost every failure below drops one
//! item and records why; only an inadmissible archive, an exhausted whole-archive budget, or a
//! cancellation ends the import. **If one slide survived, it is not an error.**

use std::collections::HashMap;

use crate::error::{ImportError, StoreError, ZipError};
use crate::hygiene;
use crate::limits::{
    MAX_IMAGE_ENCODED_BYTES, MAX_IMPORT_IMAGES, MAX_IMPORT_NOTES_LEN, MAX_IMPORT_SLIDES,
    MAX_LINE_LEN, MAX_PICTURES_PER_SLIDE, MAX_SLIDE_LINES, MAX_TITLE_LEN, MAX_XML_PART_BYTES,
};
use crate::model::{
    ImportSource, ImportedDocument, ImportedPicture, ImportedSlide, MediaSlot, PermilleRect,
};
use crate::ooxml::{self, PicRef, Rel, SlideContent};
use crate::pkgpath;
use crate::report::{LimitKind, Notice, ReportBuilder, SkipKind, TruncatedField};
use crate::sink::{ImageProbe, MediaSink};
use crate::source::ByteSource;
use crate::zip::{Archive, EntryMeta, ZipArchive};

/// The presentation part every real `.pptx` carries.
const PRESENTATION_PART: &str = "ppt/presentation.xml";
/// EMU per inch — the OOXML geometry unit.
const DEFAULT_SLIDE_EMU: (i64, i64) = (12_192_000, 6_858_000);

/// Parse a `.pptx` and stage its images. Commits nothing.
pub(crate) fn read(
    src: &mut dyn ByteSource,
    source: ImportSource,
    sink: &mut dyn MediaSink,
    cancel: &dyn Fn() -> bool,
) -> Result<ImportedDocument, ImportError> {
    let mut report = ReportBuilder::new();
    let mut archive = ZipArchive::open(src)?;
    // The entry table is READ, never cloned. A full-table clone bought its way out of a borrow
    // conflict at the price of a second copy of every name in the archive — up to a few mebibytes
    // of pure duplication on a hostile file, for a conflict that `Archive::find` removes outright
    // by doing the lookup inside the archive rather than beside it.
    survey_entries(archive.entries(), &mut report);
    let all_encrypted =
        !archive.entries().is_empty() && archive.entries().iter().all(|e| e.encrypted);
    if all_encrypted {
        return Err(ImportError::EncryptedArchive);
    }

    let (slide_parts, slide_emu) = slide_order(&mut archive, &mut report, cancel)?;
    report.set_slides_in_source(slide_parts.len());

    let mut slides: Vec<ImportedSlide> = Vec::new();
    let mut media = MediaState::default();

    // EVERY report index in this crate is a position in the SOURCE document, never in the built
    // deck. The two disagree the moment anything is dropped, and only one of them is stable: an
    // output position captured mid-parse is reused by the next slide as soon as this one turns out
    // to be hidden or empty, so "a chart was skipped on slide 12" would name a slide that has
    // nothing to do with the chart. The source position is also the number the operator can act
    // on, because it is the number PowerPoint shows them.
    for (source_index, part) in slide_parts.iter().enumerate() {
        if cancel() {
            return Err(ImportError::Cancelled);
        }
        if slides.len() >= MAX_IMPORT_SLIDES {
            report.skip(None, SkipKind::LimitReached(LimitKind::Slides), "");
            break;
        }
        let Some(content) = read_slide_part(&mut archive, part, source_index, &mut report, cancel)?
        else {
            continue;
        };
        if content.hidden {
            // Users hide slides deliberately; importing them puts unwanted content one arrow-key
            // from the audience screen.
            report.skip(Some(source_index), SkipKind::HiddenSlide, part);
            continue;
        }
        for skip in &content.skips {
            report.skip(Some(source_index), *skip, "");
        }

        let rels = read_rels(&mut archive, part, source_index, &mut report, cancel)?;
        let mut slide = assemble_text(source_index, &content, &mut report);
        slide.notes = read_notes(&mut archive, part, &rels, source_index, &mut report, cancel)?;

        slide.pictures = stage_pictures(
            &mut archive,
            part,
            &rels,
            &content.pictures,
            slide_emu,
            source_index,
            sink,
            &mut media,
            &mut report,
            cancel,
        )?;

        if slide.has_content() {
            slides.push(slide);
        }
    }

    if slides.is_empty() {
        return Err(ImportError::NothingToImport);
    }
    Ok(ImportedDocument {
        source,
        slides,
        report,
    })
}

/// Record the parts we deliberately never open, before any of them can be reached by accident.
///
/// Nested containers are never recursed into (which is what makes a zip quine just one bounded
/// entry) and macro/OLE bytes stay inert. Embedded fonts are never extracted or parsed — font
/// parsing is its own decoder surface, and this importer does not open one.
fn survey_entries(entries: &[EntryMeta], report: &mut ReportBuilder) {
    for entry in entries {
        let folded = entry.folded.as_str();
        // Reported BEFORE the duplicate check and with its own kind: an over-long or NUL-bearing
        // name is not a duplicate, and telling the operator "the first copy was used" when there
        // was no first copy is simply untrue.
        if entry.bad_name {
            report.skip(None, SkipKind::MalformedEntryName, &entry.name);
            continue;
        }
        if entry.duplicate {
            report.skip(None, SkipKind::DuplicatePart, &entry.name);
            continue;
        }
        if entry.encrypted {
            report.skip(None, SkipKind::UnreadablePart, &entry.name);
            continue;
        }
        if folded.ends_with(".fntdata") || folded.starts_with("ppt/fonts/") {
            // ONE standing notice, however many font files there are. A real deck carried
            // twenty-five of them and itemising each consumed a quarter of the whole report
            // budget, burying the drops an operator actually needs to see. The notice de-duplicates
            // itself, so the count does not matter.
            report.notice(Notice::EmbeddedFontsReplaced);
            continue;
        }
        if folded.contains("vbaproject")
            || folded.starts_with("ppt/embeddings/")
            || folded.ends_with(".zip")
            || folded.ends_with(".pptx")
            || folded.ends_with(".docx")
            || folded.ends_with(".xlsx")
        {
            report.skip(None, SkipKind::NestedContainer, &entry.name);
        }
    }
}

/// The slide parts in order, and the slide size in EMU.
///
/// If `presentation.xml` or its relationships are missing or malformed, fall back to a
/// natural-numeric sort of `ppt/slides/slideN.xml` and say so loudly. **Importing twenty-four
/// slides in the wrong order is worse than dropping a chart**, and unlike a dropped chart it is
/// invisible in a preview — which is why it is a notice that escalates the whole report.
fn slide_order(
    archive: &mut ZipArchive<'_>,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<(Vec<String>, (i64, i64)), ImportError> {
    let mut emu = DEFAULT_SLIDE_EMU;
    let mut size_known = false;
    let mut ordered: Vec<String> = Vec::new();

    if let Some(bytes) = read_xml(archive, PRESENTATION_PART, None, report, cancel)? {
        if let Ok(pres) = ooxml::parse_presentation(&bytes) {
            if let Some(size) = pres.slide_size {
                emu = size;
                size_known = true;
            }
            if let Some(rels_part) = pkgpath::rels_for(PRESENTATION_PART) {
                if let Some(rels_bytes) = read_xml(archive, &rels_part, None, report, cancel)? {
                    if let Ok(rels) = ooxml::parse_rels(&rels_bytes) {
                        let by_id: HashMap<&str, &Rel> =
                            rels.iter().map(|r| (r.id.as_str(), r)).collect();
                        for rid in &pres.slide_rids {
                            let Some(rel) = by_id.get(rid.as_str()) else {
                                continue;
                            };
                            if rel.external {
                                report.skip(None, SkipKind::UnreadablePart, &rel.target);
                                continue;
                            }
                            if let Some(part) = pkgpath::resolve(PRESENTATION_PART, &rel.target) {
                                if archive.find(&part).is_some() {
                                    ordered.push(part);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if !size_known {
        report.notice(Notice::SlideSizeAssumed);
    }
    if ordered.is_empty() {
        ordered = natural_slide_order(archive.entries());
        if ordered.is_empty() {
            return Err(ImportError::NothingToImport);
        }
        report.notice(Notice::SlideOrderInferred);
    }
    Ok((ordered, emu))
}

/// Every `ppt/slides/slideN.xml`, sorted by N numerically — so `slide10` follows `slide9` rather
/// than `slide1`, which a plain lexical sort would get wrong.
fn natural_slide_order(entries: &[EntryMeta]) -> Vec<String> {
    let mut found: Vec<(u64, String)> = entries
        .iter()
        .filter(|e| {
            e.usable() && e.folded.starts_with("ppt/slides/slide") && e.folded.ends_with(".xml")
        })
        .filter_map(|e| {
            let stem = e
                .folded
                .strip_prefix("ppt/slides/slide")?
                .strip_suffix(".xml")?;
            Some((stem.parse::<u64>().unwrap_or(u64::MAX), e.name.clone()))
        })
        .collect();
    found.sort();
    found.into_iter().map(|(_, name)| name).collect()
}

/// Read an XML part under the tighter per-part cap, reporting anything that stops it.
fn read_xml(
    archive: &mut ZipArchive<'_>,
    part: &str,
    slide: Option<usize>,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<Option<Vec<u8>>, ImportError> {
    let Some(idx) = archive.find(part) else {
        return Ok(None);
    };
    match archive.read_entry(idx, MAX_XML_PART_BYTES, cancel) {
        Ok(bytes) => Ok(Some(bytes)),
        Err(ZipError::ArchiveTooLarge) => Err(ImportError::ArchiveTooLarge {
            limit: crate::limits::MAX_TOTAL_INFLATED_BYTES,
        }),
        Err(ZipError::Cancelled) => Err(ImportError::Cancelled),
        Err(ZipError::Source(e)) => Err(ImportError::Source(e)),
        Err(_) => {
            report.skip(slide, SkipKind::UnreadablePart, part);
            Ok(None)
        }
    }
}

fn read_slide_part(
    archive: &mut ZipArchive<'_>,
    part: &str,
    index: usize,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<Option<SlideContent>, ImportError> {
    let Some(bytes) = read_xml(archive, part, Some(index), report, cancel)? else {
        return Ok(None);
    };
    match ooxml::parse_slide(&bytes) {
        Ok(content) => Ok(Some(content)),
        Err(e) => {
            report.skip(Some(index), e.skip_kind(), part);
            Ok(None)
        }
    }
}

fn read_rels(
    archive: &mut ZipArchive<'_>,
    part: &str,
    index: usize,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<Vec<Rel>, ImportError> {
    let Some(rels_part) = pkgpath::rels_for(part) else {
        return Ok(Vec::new());
    };
    let Some(bytes) = read_xml(archive, &rels_part, Some(index), report, cancel)? else {
        return Ok(Vec::new());
    };
    match ooxml::parse_rels(&bytes) {
        Ok(rels) => Ok(rels),
        Err(e) => {
            report.skip(Some(index), e.skip_kind(), &rels_part);
            Ok(Vec::new())
        }
    }
}

/// Title, body and their clamps.
fn assemble_text(
    index: usize,
    content: &SlideContent,
    report: &mut ReportBuilder,
) -> ImportedSlide {
    let mut title: Option<String> = None;
    let mut body: Vec<String> = Vec::new();
    let mut dropped_lines = 0usize;

    for shape in &content.shapes {
        // Page furniture — the slide number, the footer, the date — is not body text. Real decks
        // carry a `sldNum` placeholder on very nearly every slide and often a `ftr` too, and
        // treating them as body put the page number in front of the congregation AND spent the
        // joined-body budget on them, which cut real content and escalated the report tier.
        //
        // Dropped in silence, deliberately: a design attribute SelahCue replaces on purpose is
        // not a skipped item, and "124 slide numbers skipped" would bury the two dropped charts
        // the report exists to surface. The standing theme notice covers them.
        if ooxml::is_furniture(shape) {
            continue;
        }
        if ooxml::is_title(shape) && title.is_none() {
            let joined = shape.lines.join(" ");
            let cleaned = hygiene::clean_single_line(&joined, MAX_TITLE_LEN);
            report.record_hygiene(&cleaned);
            report.truncate(
                index,
                TruncatedField::Title,
                cleaned.text.chars().count(),
                cleaned.truncated,
            );
            if !cleaned.text.trim().is_empty() {
                title = Some(cleaned.text);
            }
            continue;
        }
        for line in &shape.lines {
            if body.len() >= MAX_SLIDE_LINES {
                dropped_lines = dropped_lines.saturating_add(1);
                continue;
            }
            let cleaned = hygiene::clean(line, MAX_LINE_LEN);
            report.record_hygiene(&cleaned);
            report.truncate(
                index,
                TruncatedField::BodyLine,
                cleaned.text.chars().count(),
                cleaned.truncated,
            );
            body.push(cleaned.text);
        }
    }
    report.truncate(index, TruncatedField::BodyLines, body.len(), dropped_lines);

    ImportedSlide {
        source_index: index,
        title,
        body,
        notes: String::new(),
        pictures: Vec::new(),
    }
}

fn read_notes(
    archive: &mut ZipArchive<'_>,
    part: &str,
    rels: &[Rel],
    index: usize,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<String, ImportError> {
    let Some(rel) = rels.iter().find(|r| r.is_type("notesSlide") && !r.external) else {
        return Ok(String::new());
    };
    let Some(notes_part) = pkgpath::resolve(part, &rel.target) else {
        return Ok(String::new());
    };
    let Some(bytes) = read_xml(archive, &notes_part, Some(index), report, cancel)? else {
        return Ok(String::new());
    };
    let Ok(content) = ooxml::parse_slide(&bytes) else {
        report.skip(Some(index), SkipKind::UnreadablePart, &notes_part);
        return Ok(String::new());
    };
    let cleaned = hygiene::clean(&ooxml::notes_text(&content), MAX_IMPORT_NOTES_LEN);
    report.record_hygiene(&cleaned);
    report.truncate(
        index,
        TruncatedField::Notes,
        cleaned.text.chars().count(),
        cleaned.truncated,
    );
    Ok(cleaned.text)
}

/// Extract, validate and stage one slide's pictures.
///
/// The chain per picture is fixed: resolve the relationship to a part **inside this archive**,
/// stream it under the byte caps, sniff the format by magic bytes, run a bounded decode probe,
/// and only then hand the ORIGINAL encoded bytes to the sink. Any failure is a report entry, never
/// an import failure.
#[allow(clippy::too_many_arguments)]
fn stage_pictures(
    archive: &mut ZipArchive<'_>,
    part: &str,
    rels: &[Rel],
    pictures: &[PicRef],
    slide_emu: (i64, i64),
    index: usize,
    sink: &mut dyn MediaSink,
    media: &mut MediaState,
    report: &mut ReportBuilder,
    cancel: &dyn Fn() -> bool,
) -> Result<Vec<ImportedPicture>, ImportError> {
    let mut out: Vec<ImportedPicture> = Vec::new();
    for pic in pictures {
        if cancel() {
            return Err(ImportError::Cancelled);
        }
        if out.len() >= MAX_PICTURES_PER_SLIDE {
            report.skip(Some(index), SkipKind::LimitReached(LimitKind::Pictures), "");
            break;
        }
        let Some(rel) = rels.iter().find(|r| r.id == pic.embed) else {
            report.skip(Some(index), SkipKind::UnsupportedGraphic, &pic.embed);
            continue;
        };
        if rel.external {
            // Never fetched. In an offline-first app a document that triggers network I/O is a
            // privacy defect as much as a security one.
            report.skip(Some(index), SkipKind::ExternalImage, &rel.target);
            continue;
        }
        let Some(media_part) = pkgpath::resolve(part, &rel.target) else {
            report.skip(Some(index), SkipKind::UnreadablePart, &rel.target);
            continue;
        };
        let rect = permille_rect(pic.emu, slide_emu, report);

        // Already staged from another slide: reuse the slot, extract nothing. Checked before the
        // budget flag, because a slot that already exists costs nothing to reuse.
        if let Some(slot) = media.staged.get(&media_part) {
            out.push(ImportedPicture { slot: *slot, rect });
            continue;
        }
        // The budget is already gone: report this picture without another read attempt, which
        // would fail identically and cost a seek per image for the rest of the deck.
        if media.budget_exhausted {
            report.skip(Some(index), SkipKind::MediaBudgetExhausted, &media_part);
            continue;
        }
        if media.images_staged >= MAX_IMPORT_IMAGES {
            report.skip(Some(index), SkipKind::LimitReached(LimitKind::Images), "");
            continue;
        }
        let Some(entry_idx) = archive.find(&media_part) else {
            report.skip(Some(index), SkipKind::UnreadablePart, &media_part);
            continue;
        };
        let bytes = match archive.read_entry(entry_idx, MAX_IMAGE_ENCODED_BYTES, cancel) {
            Ok(b) => b,
            Err(ZipError::ArchiveTooLarge) => {
                return Err(ImportError::ArchiveTooLarge {
                    limit: crate::limits::MAX_TOTAL_INFLATED_BYTES,
                })
            }
            Err(ZipError::Cancelled) => return Err(ImportError::Cancelled),
            Err(ZipError::Source(e)) => return Err(ImportError::Source(e)),
            Err(ZipError::EntryTooLarge) | Err(ZipError::RatioExceeded) => {
                report.skip(Some(index), SkipKind::ImageTooLarge, &media_part);
                continue;
            }
            // DEGRADE, do not abort. The extraction budget counts bytes an archive merely
            // CARRIED, so reaching it means a deck whose photographs are collectively enormous —
            // a big deck, not a hostile one. Aborting would contradict the partial-import rule
            // every other failure here keeps, and would hand the operator nothing on a Sunday
            // morning rather than the words. The bomb budget is a different bound and still
            // aborts, on the arm above this one.
            Err(ZipError::ExtractionBudgetExhausted) => {
                media.budget_exhausted = true;
                report.skip(Some(index), SkipKind::MediaBudgetExhausted, &media_part);
                continue;
            }
            Err(_) => {
                report.skip(Some(index), SkipKind::ImageUnreadable, &media_part);
                continue;
            }
        };

        // HEADER PROBE, NOT A DECODE. The signature allowlist (magic bytes, never an extension —
        // the archive supplies both and only one is evidence), the format's own header walk, and
        // every dimension and pixel cap run inside `probe_image`, all of it before any allocation.
        // What does NOT happen is a pixel decode: the importer used to decode every image purely
        // to validate it and then throw the pixels away, on a decoder pinned to one scalar code
        // path for determinism, only for the render path to decode the same bytes again later.
        // That was over 99 % of import time — around fifteen seconds at the cap on a fast machine,
        // far more on church hardware, against a thirty-second timeout that then keeps nothing.
        //
        // One thing is given up on purpose: an image with a sound header and a corrupt payload is
        // now staged and shows the missing-media placeholder at render time, instead of being
        // reported at import time. A structurally bad header is still refused and still reported.
        let probe =
            match selahcue_engine::probe_image(&bytes, &crate::limits::image_decode_limits()) {
                Ok(info) => ImageProbe {
                    width: info.width,
                    height: info.height,
                    byte_len: bytes.len(),
                    format: info.format,
                },
                Err(e) => {
                    report.skip(
                        Some(index),
                        crate::report::skip_kind_for_decode(e),
                        &media_part,
                    );
                    continue;
                }
            };
        match sink.stage(&bytes, &probe) {
            Ok(slot) => {
                media.staged.insert(media_part, slot);
                media.images_staged = media.images_staged.saturating_add(1);
                report.count_image();
                out.push(ImportedPicture { slot, rect });
            }
            Err(StoreError::LibraryFull) => {
                // Two house rules meet here and both are satisfied by scoping the refusal to the
                // ITEM: the image is refused, the import proceeds.
                report.skip(Some(index), SkipKind::LibraryFull, &media_part);
            }
            Err(_) => report.skip(Some(index), SkipKind::MediaCommitFailed, &media_part),
        }
    }
    Ok(out)
}

/// The media-staging state that spans the whole import.
#[derive(Debug, Default)]
struct MediaState {
    /// Shared media parts, deduplicated by RESOLVED part name before anything is staged, so one
    /// image referenced from two hundred slides is extracted, probed and staged exactly once —
    /// and counts against the byte budget exactly once.
    staged: HashMap<String, MediaSlot>,
    images_staged: usize,
    /// Set once the whole-archive extraction budget is used up. Every picture from here on is
    /// dropped and reported without another read attempt, and the import carries on with text.
    budget_exhausted: bool,
}

/// EMU geometry to per-mille of the frame. A picture with no `<a:xfrm>` inherited it from a layout
/// placeholder we do not read, so it is centred and the assumption is stated in the report.
fn permille_rect(
    emu: Option<(i64, i64, i64, i64)>,
    slide: (i64, i64),
    report: &mut ReportBuilder,
) -> PermilleRect {
    let Some((x, y, cx, cy)) = emu else {
        report.notice(Notice::PictureGeometryAssumed);
        return PermilleRect::CENTRED;
    };
    let (sw, sh) = slide;
    if sw <= 0 || sh <= 0 {
        return PermilleRect::CENTRED;
    }
    let to_permille = |v: i64, total: i64| -> u16 {
        v.saturating_mul(1000)
            .checked_div(total)
            .unwrap_or(0)
            .clamp(0, 1000) as u16
    };
    PermilleRect {
        x: to_permille(x, sw),
        y: to_permille(y, sh),
        w: to_permille(cx, sw).max(1),
        h: to_permille(cy, sh).max(1),
    }
    .clamped()
}
