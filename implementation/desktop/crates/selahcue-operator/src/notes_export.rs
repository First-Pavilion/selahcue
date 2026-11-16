//! Offline export of one immutable, host-loaded accepted note. No WebView file/content input.
use printpdf::{
    Codepoint, Mm, Op, ParsedFont, PdfDocument, PdfFontHandle, PdfPage, PdfSaveOptions, Pt,
    TextItem, TextMatrix,
};
use selahcue_core::providers::{self, DraftCaveat};
use selahcue_lan::protocol::SermonNoteDraftView;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use unicode_normalization::UnicodeNormalization;
use unicode_segmentation::UnicodeSegmentation;

pub(crate) mod save;
const FONT: &[u8] = include_bytes!("../assets/notes-pdf/NotoSans-Regular.ttf");
pub(crate) const MAX_PAGES: usize = 500;
pub(crate) const MAX_PDF_BYTES: usize = 16 * 1024 * 1024;
const MAX_INPUT_BYTES: usize = 128 * 1024;
static EXPORTING: AtomicBool = AtomicBool::new(false);

/// Deliberately fixed diagnostics: never serialize stored content, backend errors or paths.
#[derive(Debug, PartialEq, Eq, Serialize)]
pub enum ExportError {
    NoSavedDraft,
    InvalidDraft,
    TooLarge,
    Cancelled,
    Io,
}
#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct ExportReceipt {
    pub transcript_id: i64,
    pub saved_edited_at_ms: i64,
    pub bytes: u64,
}
pub(crate) struct ExportPermit;
impl ExportPermit {
    pub(crate) fn acquire() -> Result<Self, ExportError> {
        EXPORTING
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map(|_| Self)
            .map_err(|_| ExportError::Io)
    }
}
impl Drop for ExportPermit {
    fn drop(&mut self) {
        EXPORTING.store(false, Ordering::Release);
    }
}

pub(crate) async fn load_snapshot(
    backend: &crate::Backend,
    transcript_id: i64,
) -> Result<SermonNoteDraftView, ExportError> {
    backend
        .load_sermon_note_draft(transcript_id)
        .await
        .map_err(|_| ExportError::Io)?
        .ok_or(ExportError::NoSavedDraft)
}

/// Called only after the permission-checked host load. The owned A snapshot survives dialog
/// waits and subsequent host edits. A cancelled/failed export cannot call a store mutation.
pub(crate) fn export_snapshot(
    draft: SermonNoteDraftView,
    transcript_id: i64,
    choose: impl FnOnce() -> Result<Option<std::path::PathBuf>, ExportError>,
) -> Result<ExportReceipt, ExportError> {
    let pdf = render_saved_note_pdf(&draft, transcript_id)?;
    let path = choose()?.ok_or(ExportError::Cancelled)?;
    save::save_pdf(&path, &pdf)?;
    Ok(ExportReceipt {
        transcript_id,
        saved_edited_at_ms: draft.edited_at_ms,
        bytes: pdf.len() as u64,
    })
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StoredPoint {
    text: String,
    #[serde(default)]
    sub_points: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StoredSection {
    heading: String,
    #[serde(default)]
    items: Vec<String>,
    #[serde(default)]
    points: Vec<StoredPoint>,
    #[serde(default)]
    requested_empty: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StoredEnvelope {
    sections: Vec<StoredSection>,
    #[serde(default)]
    requested_empty: Vec<String>,
}

struct ValidatedNote {
    sections: Vec<providers::NoteSection>,
    requested: Vec<String>,
    scriptures: Vec<String>,
}
fn validate(d: &SermonNoteDraftView) -> Result<ValidatedNote, ExportError> {
    // Bound allocations/scanning before JSON decode; legacy saved rows may exceed today's
    // write caps, but never this explicit export bound. The database is never rewritten.
    let size = d
        .title
        .len()
        .saturating_add(d.summary.as_ref().map_or(0, String::len))
        .saturating_add(d.sections_json.len())
        .saturating_add(d.scriptures_json.len())
        .saturating_add(d.disclosure.as_ref().map_or(0, String::len));
    if size > MAX_INPUT_BYTES {
        return Err(ExportError::TooLarge);
    }
    if d.title.trim().is_empty() {
        return Err(ExportError::InvalidDraft);
    }
    let (sections, mut headings) = if d.sections_json.trim_start().starts_with('[') {
        (
            serde_json::from_str::<Vec<StoredSection>>(&d.sections_json)
                .map_err(|_| ExportError::InvalidDraft)?,
            Vec::new(),
        )
    } else {
        let e: StoredEnvelope =
            serde_json::from_str(&d.sections_json).map_err(|_| ExportError::InvalidDraft)?;
        (e.sections, e.requested_empty)
    };
    // No silently ignored mixed outline/items or caveat-window truncation.
    if headings.len() > 256
        || sections.iter().enumerate().any(|(i, s)| {
            (!s.items.is_empty() && !s.points.is_empty())
                || s.requested_empty.len() > 256
                || (i != 0 && !s.requested_empty.is_empty())
        })
    {
        return Err(ExportError::InvalidDraft);
    }
    if let Some(first) = sections.first() {
        headings.extend(first.requested_empty.iter().cloned());
    }
    if headings.len() > 256 {
        return Err(ExportError::InvalidDraft);
    }
    let sections = sections
        .into_iter()
        .map(|s| {
            if s.points.is_empty() {
                providers::NoteSection::flat(s.heading, s.items)
            } else {
                providers::NoteSection::outline(
                    s.heading,
                    s.points
                        .into_iter()
                        .map(|p| providers::NotePoint {
                            text: p.text,
                            sub_points: p.sub_points,
                        })
                        .collect(),
                )
            }
        })
        .collect();
    let scriptures = serde_json::from_str::<Vec<String>>(&d.scriptures_json)
        .map_err(|_| ExportError::InvalidDraft)?;
    Ok(ValidatedNote {
        sections,
        requested: headings,
        scriptures,
    })
}

pub fn render_saved_note_pdf(
    draft: &SermonNoteDraftView,
    transcript_id: i64,
) -> Result<Vec<u8>, ExportError> {
    render_with_limits(draft, transcript_id, MAX_PAGES, MAX_PDF_BYTES)
}

pub(crate) fn render_with_limits(
    d: &SermonNoteDraftView,
    _transcript_id: i64,
    max_pages: usize,
    max_bytes: usize,
) -> Result<Vec<u8>, ExportError> {
    let ValidatedNote {
        sections,
        requested,
        scriptures,
    } = validate(d)?;
    let (verdicts, truncated) = providers::verify_scriptures(&scriptures, &sections, |r| {
        selahcue_scripture::passage_exists_in(selahcue_scripture::Translation::default(), r)
    });
    let caveats = crate::sermon_note_caveats::reloaded_caveats(
        &requested,
        d.summary.as_deref(),
        &sections,
        &scriptures,
    );
    let mut warnings = Vec::new();
    let font = ParsedFont::from_bytes(FONT, 0, &mut warnings).ok_or(ExportError::InvalidDraft)?;
    if !warnings.is_empty() {
        return Err(ExportError::InvalidDraft);
    }
    let font_ref = harfrust::FontRef::new(FONT).map_err(|_| ExportError::InvalidDraft)?;
    let shaper_data = harfrust::ShaperData::new(&font_ref);
    let face = shaper_data.shaper(&font_ref).build();
    let mut doc = PdfDocument::new("Saved sermon notes");
    let handle = PdfFontHandle::External(doc.add_font(&font));
    let mut layout = Layout {
        font: &font,
        face,
        handle,
        pages: Vec::new(),
        ops: Vec::new(),
        y: 790.0,
        max_pages,
        unicode: std::collections::BTreeMap::new(),
    };
    layout.paragraph("SELAHCUE / SAVED SERMON NOTES", 9.0, 0.0)?;
    layout.paragraph(&d.title, 20.0, 0.0)?;
    layout.paragraph("Saved English notes", 9.0, 0.0)?;
    if d.ai_generated {
        layout.paragraph(providers::AI_GENERATED_LABEL, 11.0, 0.0)?;
    }
    layout.paragraph("Review these notes before use. Scripture checks verify addresses only, not quotations or interpretation.", 10.0, 0.0)?;
    if let Some(text) = &d.disclosure {
        layout.paragraph(text, 10.0, 0.0)?;
    }
    if let Some(text) = &d.summary {
        layout.paragraph("Summary", 14.0, 0.0)?;
        layout.paragraph(text, 11.0, 0.0)?;
    }
    for section in &sections {
        layout.paragraph(&section.heading, 14.0, 0.0)?;
        for item in section.items() {
            layout.paragraph(&format!("- {item}"), 11.0, 12.0)?;
        }
        for (index, point) in section.points().iter().enumerate() {
            layout.paragraph(&format!("{}. {}", index + 1, point.text), 11.0, 12.0)?;
            for child in &point.sub_points {
                layout.paragraph(&format!("- {child}"), 11.0, 28.0)?;
            }
        }
    }
    for caveat in caveats {
        if let DraftCaveat::SectionRequestedEmpty { heading } = caveat {
            layout.paragraph(&format!("Warning: {heading} was requested but returned empty. Review the source transcript."), 10.0, 0.0)?;
        }
    }
    if !scriptures.is_empty() {
        layout.paragraph("Referenced passages", 14.0, 0.0)?;
    }
    // Keep every listed address even if the shared verifier's verdict budget is exhausted.
    for reference in &scriptures {
        let verdict = verdicts.iter().find(|v| v.reference == reference.trim());
        layout.paragraph(
            &format!(
                "{} - {}",
                reference,
                verdict_label(verdict.map(|v| v.verified))
            ),
            10.0,
            0.0,
        )?;
    }
    let embedded: Vec<_> = verdicts
        .iter()
        .filter(|v| !scriptures.iter().any(|s| s.trim() == v.reference))
        .collect();
    if !embedded.is_empty() {
        layout.paragraph("References found in the notes", 14.0, 0.0)?;
    }
    for v in embedded {
        layout.paragraph(
            &format!("{} - {}", v.reference, verdict_label(Some(v.verified))),
            10.0,
            0.0,
        )?;
    }
    if !verdicts.is_empty() {
        layout.paragraph(providers::SCRIPTURE_VERIFICATION_WORDING, 10.0, 0.0)?;
    }
    if truncated
        || scriptures
            .iter()
            .any(|s| !verdicts.iter().any(|v| v.reference == s.trim()))
    {
        layout.paragraph("Warning: scripture verification is incomplete. Some references were not checked; review all references against the actual Bible text.", 10.0, 0.0)?;
    }
    layout.finish_page()?;
    doc.with_pages(layout.pages);
    let mut warnings = Vec::new();
    // Vec-returning API: save_writer does not propagate I/O failures. Full font is reused.
    let bytes = doc.save(
        &PdfSaveOptions {
            subset_fonts: false,
            ..Default::default()
        },
        &mut warnings,
    );
    if bytes.len() > max_bytes {
        return Err(ExportError::TooLarge);
    }
    if !warnings.is_empty() || !bytes.starts_with(b"%PDF-") {
        return Err(ExportError::InvalidDraft);
    }
    Ok(bytes)
}
fn verdict_label(v: Option<bool>) -> &'static str {
    match v {
        Some(true) => "Verified address",
        Some(false) => "UNVERIFIED - check this reference",
        None => "NOT CHECKED",
    }
}

struct Glyph {
    gid: u16,
    text: String,
    x: f32,
    y: f32,
}
struct Cluster {
    glyphs: Vec<Glyph>,
    width: f32,
}
struct Layout<'a> {
    font: &'a ParsedFont,
    face: harfrust::Shaper<'a>,
    handle: PdfFontHandle,
    pages: Vec<PdfPage>,
    ops: Vec<Op>,
    y: f32,
    max_pages: usize,
    unicode: std::collections::BTreeMap<u16, String>,
}
impl Layout<'_> {
    fn cluster(&self, text: &str, size: f32) -> Result<Cluster, ExportError> {
        // Each grapheme shapes once, with marks attached by OpenType GPOS. No repeated
        // growing-prefix shaping, and no font/line split inside a grapheme. Cross-grapheme
        // kerning/ligatures are deliberately unnecessary in this English notes layout.
        if text.chars().count() > 64
            || text
                .chars()
                .any(|c| c.is_control() || self.font.lookup_glyph_index(c as u32).is_none())
        {
            return Err(ExportError::InvalidDraft);
        }
        let mut buffer = harfrust::UnicodeBuffer::new();
        buffer.push_str(text);
        buffer.guess_segment_properties();
        let shaped = self.face.shape(buffer, &[]);
        let scale = size / self.face.units_per_em() as f32;
        let mut x = 0.0;
        let mut glyphs = Vec::new();
        let mut mapped = String::new();
        for (info, pos) in shaped.glyph_infos().iter().zip(shaped.glyph_positions()) {
            let gid = u16::try_from(info.glyph_id).map_err(|_| ExportError::InvalidDraft)?;
            if gid == 0 {
                return Err(ExportError::InvalidDraft);
            }
            // Prefer an actual input scalar. Canonical composition may select a different
            // cmap glyph; reverse lookup is accepted only if the whole result is equivalent.
            let ch = text
                .chars()
                .find(|c| self.font.lookup_glyph_index(*c as u32) == Some(gid))
                .or_else(|| {
                    self.font
                        .codepoint_to_glyph
                        .iter()
                        .find_map(|(&cp, &g)| (g == gid).then(|| char::from_u32(cp)).flatten())
                })
                .ok_or(ExportError::InvalidDraft)?;
            mapped.push(ch);
            glyphs.push(Glyph {
                gid,
                text: ch.to_string(),
                x: x + pos.x_offset as f32 * scale,
                y: pos.y_offset as f32 * scale,
            });
            x += pos.x_advance as f32 * scale;
        }
        if mapped.nfc().collect::<String>() != text.nfc().collect::<String>() {
            return Err(ExportError::InvalidDraft);
        }
        Ok(Cluster { glyphs, width: x })
    }
    fn finish_page(&mut self) -> Result<(), ExportError> {
        if self.pages.len() >= self.max_pages {
            return Err(ExportError::TooLarge);
        }
        let footer = format!("Page {}", self.pages.len() + 1);
        let clusters = footer
            .graphemes(true)
            .map(|g| self.cluster(g, 9.0))
            .collect::<Result<Vec<_>, _>>()?;
        self.y = 28.0;
        self.draw_line(&clusters, 9.0, 0.0)?;
        self.pages.push(PdfPage::new(
            Mm(210.0),
            Mm(297.0),
            std::mem::take(&mut self.ops),
        ));
        self.y = 790.0;
        Ok(())
    }
    fn line(&mut self, clusters: &[Cluster], size: f32, indent: f32) -> Result<(), ExportError> {
        if self.y - size * 1.5 < 48.0 {
            self.finish_page()?;
        }
        // Enforce the page budget before allocating operations for another page.
        if self.pages.len() >= self.max_pages {
            return Err(ExportError::TooLarge);
        }
        self.draw_line(clusters, size, indent)
    }
    fn draw_line(
        &mut self,
        clusters: &[Cluster],
        size: f32,
        indent: f32,
    ) -> Result<(), ExportError> {
        self.ops.push(Op::StartTextSection);
        self.ops.push(Op::SetFont {
            font: self.handle.clone(),
            size: Pt(size),
        });
        let mut x = 48.0 + indent;
        for c in clusters {
            for g in &c.glyphs {
                if let Some(previous) = self.unicode.insert(g.gid, g.text.clone()) {
                    if previous != g.text {
                        return Err(ExportError::InvalidDraft);
                    }
                }
                self.ops.push(Op::SetTextMatrix {
                    matrix: TextMatrix::Translate(Pt(x + g.x), Pt(self.y + g.y)),
                });
                self.ops.push(Op::ShowText {
                    items: vec![TextItem::GlyphIds(vec![Codepoint::with_cid(
                        g.gid,
                        0.0,
                        g.text.clone(),
                    )])],
                });
            }
            x += c.width;
        }
        self.ops.push(Op::EndTextSection);
        self.y -= size * 1.5;
        Ok(())
    }
    fn paragraph(&mut self, text: &str, size: f32, indent: f32) -> Result<(), ExportError> {
        let normalized: String = text.nfc().collect();
        let available = 499.0 - indent;
        for hard_line in normalized.split('\n') {
            let mut line = Vec::new();
            let mut width = 0.0;
            for word in hard_line.split_inclusive(' ') {
                let clusters: Vec<_> = word
                    .graphemes(true)
                    .map(|g| self.cluster(g, size))
                    .collect::<Result<_, _>>()?;
                let word_width: f32 = clusters.iter().map(|c| c.width).sum();
                if width > 0.0 && width + word_width > available {
                    self.line(&line, size, indent)?;
                    line.clear();
                    width = 0.0;
                }
                for c in clusters {
                    if c.width > available {
                        return Err(ExportError::InvalidDraft);
                    }
                    if width + c.width > available {
                        self.line(&line, size, indent)?;
                        line.clear();
                        width = 0.0;
                    }
                    width += c.width;
                    line.push(c);
                }
            }
            self.line(&line, size, indent)?;
        }
        self.y -= 6.0;
        Ok(())
    }
}
