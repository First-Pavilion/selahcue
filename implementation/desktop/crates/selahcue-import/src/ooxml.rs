//! The OOXML pull reader: the four part shapes the importer reads, and nothing else.
//!
//! # Why a dependency here, when ZIP is hand-rolled
//!
//! The asymmetry is the point. ZIP is narrow and stable; XML is neither. Namespaces, prefix
//! rebinding, entities, CDATA, character references, attribute normalisation, encoding
//! declarations — hand-rolling a parser for adversarial XML is how you get billion-laughs and
//! XXE, and the ways to be wrong are not visible from reading your own code. So `quick-xml` is
//! taken, configured, and then **pinned by tests rather than trusted to its defaults**.
//!
//! # The controls, each of which is a merge gate
//!
//! - **Any part whose first kilobyte contains `<!DOCTYPE` is dropped and reported**, before the
//!   parser ever sees the bytes. OOXML never legitimately contains a DTD, so this costs nothing,
//!   and failing closed on a marker is stronger than trusting a parser's entity configuration.
//!   It kills XXE — file disclosure *and* the offline-first privacy break of a document causing
//!   network I/O — and billion-laughs in the same move, since expansion attacks need
//!   DTD-declared entities.
//! - **The reader is iterative with an explicit depth counter**, capped at
//!   [`MAX_XML_DEPTH`](crate::limits::MAX_XML_DEPTH). A pull parser will happily stream a
//!   million-deep document; recursive descent over one is a stack overflow, which here is a
//!   console crash mid-service. *This is the trap a "safe parser" does not save you from.*
//! - **A per-part event budget**, so a legal but pathological part still terminates.
//! - **Matching is on `local_name()`, never a prefix.** Real files rebind `p:`, `a:` and `r:`
//!   freely, so a prefix match is a correctness bug waiting for a file that uses `x:` instead.
//! - Mismatched closing tags are an error, not a silent recovery.
//!
//! Like `zip.rs` and `pkgpath.rs`, this module reads untrusted input at computed offsets, so it
//! denies `indexing_slicing` and `arithmetic_side_effects` — the design names all three modules by
//! name and calls the pair its single most effective structural defence.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

use quick_xml::events::{BytesStart, Event};
use quick_xml::Reader;

use crate::limits::{MAX_XML_DEPTH, MAX_XML_EVENTS_PER_PART};
use crate::report::SkipKind;

/// Why a part could not be read. Every variant drops just that part and is reported.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum XmlError {
    /// The part declares a DTD. Refused on the marker, before parsing.
    Doctype,
    /// Nesting past the depth cap.
    DepthExceeded,
    /// The part used its whole event budget.
    BudgetExceeded,
    /// Not well-formed, or a mismatched end tag.
    Malformed,
}

impl XmlError {
    pub(crate) fn skip_kind(self) -> SkipKind {
        match self {
            XmlError::Doctype => SkipKind::DoctypeRejected,
            _ => SkipKind::UnreadablePart,
        }
    }
}

/// Whether the part declares a document type. Checked on the raw bytes, over the first kilobyte,
/// case-insensitively — before the parser is constructed.
pub(crate) fn has_doctype(bytes: &[u8]) -> bool {
    let head = bytes.get(..bytes.len().min(1024)).unwrap_or(bytes);
    let lowered: Vec<u8> = head.iter().map(u8::to_ascii_lowercase).collect();
    lowered.windows(9).any(|w| w == b"<!doctype")
}

/// One relationship from a `.rels` part.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Rel {
    pub id: String,
    pub target: String,
    /// `TargetMode="External"`. **Never fetched** — recorded as a drop instead. In an
    /// offline-first app a document that causes network I/O is a privacy defect as much as a
    /// security one.
    pub external: bool,
    pub rel_type: String,
}

impl Rel {
    /// Whether the relationship type ends with `segment` (types are long URIs; the tail is the
    /// discriminator).
    pub(crate) fn is_type(&self, segment: &str) -> bool {
        self.rel_type
            .rsplit('/')
            .next()
            .is_some_and(|s| s.eq_ignore_ascii_case(segment))
    }
}

/// What `ppt/presentation.xml` tells us.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct Presentation {
    /// Relationship ids of the slides, in presentation order.
    pub slide_rids: Vec<String>,
    /// `<p:sldSz cx cy>` in EMU.
    pub slide_size: Option<(i64, i64)>,
}

/// One text-bearing shape from a slide.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct Shape {
    /// The `<p:ph type>` value, when the shape is a placeholder. **Placeholder type decides title
    /// versus body — nothing else does**, because position and order are not reliable.
    pub placeholder: Option<String>,
    pub lines: Vec<String>,
}

/// A picture reference and its geometry, in EMU.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct PicRef {
    pub embed: String,
    /// `(x, y, cx, cy)`; `None` when the picture inherits geometry from a layout placeholder we
    /// do not read.
    pub emu: Option<(i64, i64, i64, i64)>,
}

/// Everything one slide part yields.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct SlideContent {
    /// `<p:sld show="0">`.
    pub hidden: bool,
    pub shapes: Vec<Shape>,
    pub pictures: Vec<PicRef>,
    /// Content we recognised and deliberately did not import.
    pub skips: Vec<SkipKind>,
}

/// A bounded pull reader: depth counter, event budget, and no DOM.
struct Pull<'a> {
    reader: Reader<&'a [u8]>,
    buf: Vec<u8>,
    depth: usize,
    events: usize,
}

impl<'a> Pull<'a> {
    fn new(bytes: &'a [u8]) -> Result<Self, XmlError> {
        if has_doctype(bytes) {
            return Err(XmlError::Doctype);
        }
        let mut reader = Reader::from_reader(bytes);
        let config = reader.config_mut();
        // Mismatched close tags are an error, not a silent recovery.
        config.allow_unmatched_ends = false;
        config.trim_text(false);
        Ok(Pull {
            reader,
            buf: Vec::with_capacity(4096),
            depth: 0,
            events: 0,
        })
    }

    /// The next event, with the depth and budget enforced around it. Returns `Ok(None)` at EOF.
    fn next(&mut self) -> Result<Option<Owned>, XmlError> {
        self.events = self.events.saturating_add(1);
        if self.events > MAX_XML_EVENTS_PER_PART {
            return Err(XmlError::BudgetExceeded);
        }
        self.buf.clear();
        let event = self
            .reader
            .read_event_into(&mut self.buf)
            .map_err(|_| XmlError::Malformed)?;
        let out = match event {
            Event::Eof => return Ok(None),
            Event::Start(e) => {
                self.depth = self.depth.saturating_add(1);
                if self.depth > MAX_XML_DEPTH {
                    return Err(XmlError::DepthExceeded);
                }
                Owned::Start(local(&e), attrs(&e), false)
            }
            Event::Empty(e) => Owned::Start(local(&e), attrs(&e), true),
            Event::End(e) => {
                self.depth = self.depth.saturating_sub(1);
                Owned::End(String::from_utf8_lossy(e.local_name().as_ref()).into_owned())
            }
            Event::Text(e) => {
                Owned::Text(e.decode().map_err(|_| XmlError::Malformed)?.into_owned())
            }
            Event::CData(e) => {
                Owned::Text(String::from_utf8_lossy(e.into_inner().as_ref()).into_owned())
            }
            // quick-xml surfaces `&entity;` as its own event. Only the XML built-ins and numeric
            // references can appear, because a DTD-declared entity would have needed a DOCTYPE,
            // which is refused above — so this resolver is total and cannot amplify.
            Event::GeneralRef(e) => {
                let name = e.decode().map_err(|_| XmlError::Malformed)?;
                Owned::Text(resolve_entity(&name))
            }
            Event::DocType(_) => return Err(XmlError::Doctype),
            _ => Owned::Other,
        };
        Ok(Some(out))
    }
}

/// An owned, prefix-stripped view of one event — owning it keeps the borrow of the reader's
/// buffer from fighting the walker's state machine.
enum Owned {
    /// `(local name, attributes as (local name, value), is_empty_element)`
    Start(String, Vec<(String, String)>, bool),
    End(String),
    Text(String),
    Other,
}

fn local(e: &BytesStart<'_>) -> String {
    String::from_utf8_lossy(e.local_name().as_ref()).into_owned()
}

fn attrs(e: &BytesStart<'_>) -> Vec<(String, String)> {
    e.attributes()
        .flatten()
        .map(|a| {
            let key = String::from_utf8_lossy(a.key.local_name().as_ref()).into_owned();
            // Attribute-value normalisation per XML 1.0 — quick-xml resolves the built-in
            // entities and folds whitespace; a DTD-declared entity cannot appear, because a
            // DOCTYPE is refused before the parser is constructed.
            let value = a
                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                .map(|v| v.into_owned())
                .unwrap_or_default();
            (key, value)
        })
        .collect()
}

fn attr<'b>(attrs: &'b [(String, String)], name: &str) -> Option<&'b str> {
    attrs
        .iter()
        .find(|(k, _)| k.eq_ignore_ascii_case(name))
        .map(|(_, v)| v.as_str())
}

/// Resolve one entity reference. Unknown names resolve to nothing rather than to their own text,
/// so a hostile file cannot smuggle markup back in through a name we did not expect.
fn resolve_entity(name: &str) -> String {
    match name {
        "amp" => "&".into(),
        "lt" => "<".into(),
        "gt" => ">".into(),
        "apos" => "'".into(),
        "quot" => "\"".into(),
        other => {
            let Some(digits) = other.strip_prefix('#') else {
                return String::new();
            };
            let code = match digits.strip_prefix(['x', 'X']) {
                Some(hex) => u32::from_str_radix(hex, 16).ok(),
                None => digits.parse::<u32>().ok(),
            };
            code.and_then(char::from_u32)
                .map(String::from)
                .unwrap_or_default()
        }
    }
}

/// Read `ppt/presentation.xml`: slide order and slide size.
pub(crate) fn parse_presentation(bytes: &[u8]) -> Result<Presentation, XmlError> {
    let mut pull = Pull::new(bytes)?;
    let mut out = Presentation::default();
    let mut in_slide_list = false;
    while let Some(event) = pull.next()? {
        match event {
            Owned::Start(name, a, empty) => match name.as_str() {
                "sldIdLst" => in_slide_list = !empty,
                "sldId" if in_slide_list => {
                    // `<p:sldId id="256" r:id="rId2"/>` carries TWO attributes whose local name is
                    // `id` — the numeric slide id and the relationship id. Matching on local names
                    // is non-negotiable (real files rebind `r:` freely), so the two are told apart
                    // by shape: a relationship id is `rIdN`, a slide id is a number.
                    if let Some(rid) = a
                        .iter()
                        .filter(|(k, _)| k.eq_ignore_ascii_case("id"))
                        .map(|(_, v)| v.as_str())
                        .find(|v| {
                            v.len() > 3 && v.get(..3).is_some_and(|p| p.eq_ignore_ascii_case("rid"))
                        })
                    {
                        out.slide_rids.push(rid.to_string());
                    }
                }
                "sldSz" => {
                    let cx = attr(&a, "cx").and_then(|v| v.parse::<i64>().ok());
                    let cy = attr(&a, "cy").and_then(|v| v.parse::<i64>().ok());
                    if let (Some(cx), Some(cy)) = (cx, cy) {
                        if cx > 0 && cy > 0 {
                            out.slide_size = Some((cx, cy));
                        }
                    }
                }
                _ => {}
            },
            Owned::End(name) if name == "sldIdLst" => in_slide_list = false,
            _ => {}
        }
    }
    Ok(out)
}

/// Read a `.rels` part.
pub(crate) fn parse_rels(bytes: &[u8]) -> Result<Vec<Rel>, XmlError> {
    let mut pull = Pull::new(bytes)?;
    let mut out = Vec::new();
    while let Some(event) = pull.next()? {
        if let Owned::Start(name, a, _) = event {
            if name != "Relationship" {
                continue;
            }
            let (Some(id), Some(target)) = (attr(&a, "Id"), attr(&a, "Target")) else {
                continue;
            };
            out.push(Rel {
                id: id.to_string(),
                target: target.to_string(),
                external: attr(&a, "TargetMode")
                    .is_some_and(|m| m.eq_ignore_ascii_case("External")),
                rel_type: attr(&a, "Type").unwrap_or_default().to_string(),
            });
        }
    }
    Ok(out)
}

/// Read one slide (or notes-slide) part.
///
/// The walk is flat over the whole shape tree, which is how `<p:grpSp>` is handled: a grouped
/// shape's text is found exactly like an ungrouped one's. Many real decks group their content,
/// and not descending silently loses text — the worst possible failure under a partial-import
/// rule, because the report would say nothing was lost.
pub(crate) fn parse_slide(bytes: &[u8]) -> Result<SlideContent, XmlError> {
    let mut pull = Pull::new(bytes)?;
    let mut out = SlideContent::default();

    // Current text-bearing shape.
    let mut shape: Option<Shape> = None;
    let mut in_text_body = false;
    let mut paragraph: Option<String> = None;
    let mut in_t = false;

    // Current picture.
    let mut pic: Option<PicRef> = None;
    let mut pic_off: Option<(i64, i64)> = None;
    let mut pic_ext: Option<(i64, i64)> = None;

    while let Some(event) = pull.next()? {
        match event {
            Owned::Start(name, a, empty) => match name.as_str() {
                "sld" => {
                    if attr(&a, "show").is_some_and(|v| v == "0" || v.eq_ignore_ascii_case("false"))
                    {
                        out.hidden = true;
                    }
                }
                "sp" if !empty => shape = Some(Shape::default()),
                "ph" => {
                    if let Some(s) = shape.as_mut() {
                        s.placeholder = Some(attr(&a, "type").unwrap_or("body").to_string());
                    }
                }
                "txBody" => in_text_body = true,
                "p" if in_text_body => paragraph = Some(String::new()),
                "t" if in_text_body => in_t = true,
                "br" if in_text_body => {
                    if let Some(p) = paragraph.as_mut() {
                        p.push('\n');
                    }
                }
                "pic" if !empty => {
                    pic = Some(PicRef {
                        embed: String::new(),
                        emu: None,
                    });
                    pic_off = None;
                    pic_ext = None;
                }
                "blip" => {
                    if let Some(p) = pic.as_mut() {
                        if let Some(embed) = attr(&a, "embed") {
                            p.embed = embed.to_string();
                        } else if attr(&a, "link").is_some() {
                            // A linked (rather than embedded) image lives outside the file.
                            out.skips.push(SkipKind::ExternalImage);
                        }
                    }
                }
                "off" => {
                    if pic.is_some() {
                        let x = attr(&a, "x").and_then(|v| v.parse::<i64>().ok());
                        let y = attr(&a, "y").and_then(|v| v.parse::<i64>().ok());
                        if let (Some(x), Some(y)) = (x, y) {
                            pic_off.get_or_insert((x, y));
                        }
                    }
                }
                "ext" => {
                    if pic.is_some() {
                        let cx = attr(&a, "cx").and_then(|v| v.parse::<i64>().ok());
                        let cy = attr(&a, "cy").and_then(|v| v.parse::<i64>().ok());
                        if let (Some(cx), Some(cy)) = (cx, cy) {
                            if cx > 0 && cy > 0 {
                                pic_ext.get_or_insert((cx, cy));
                            }
                        }
                    }
                }
                "graphicData" => {
                    let uri = attr(&a, "uri").unwrap_or_default();
                    out.skips.push(classify_graphic(uri));
                }
                "cxnSp" => out.skips.push(SkipKind::UnsupportedGraphic),
                _ => {}
            },
            Owned::End(name) => match name.as_str() {
                "sp" => {
                    if let Some(s) = shape.take() {
                        if !s.lines.is_empty() {
                            out.shapes.push(s);
                        }
                    }
                    in_text_body = false;
                }
                "txBody" => in_text_body = false,
                "p" => {
                    if let (Some(p), Some(s)) = (paragraph.take(), shape.as_mut()) {
                        // A paragraph is one line; an explicit `<a:br/>` inside it makes more.
                        for line in p.split('\n') {
                            s.lines.push(line.to_string());
                        }
                    }
                }
                "t" => in_t = false,
                "pic" => {
                    if let Some(mut p) = pic.take() {
                        p.emu = match (pic_off, pic_ext) {
                            (Some((x, y)), Some((cx, cy))) => Some((x, y, cx, cy)),
                            _ => None,
                        };
                        if p.embed.is_empty() {
                            // A picture with no embedded relationship has nothing to import.
                            out.skips.push(SkipKind::UnsupportedGraphic);
                        } else {
                            out.pictures.push(p);
                        }
                    }
                }
                _ => {}
            },
            Owned::Text(text) => {
                if in_t {
                    if let Some(p) = paragraph.as_mut() {
                        p.push_str(&text);
                    }
                }
            }
            Owned::Other => {}
        }
    }
    Ok(out)
}

/// Classify a `<a:graphicData uri>` into the drop it becomes.
fn classify_graphic(uri: &str) -> SkipKind {
    let tail = uri.rsplit('/').next().unwrap_or_default();
    match tail {
        "table" => SkipKind::Table,
        "chart" => SkipKind::Chart,
        "diagram" => SkipKind::SmartArt,
        "ole" | "oleObject" => SkipKind::OleObject,
        _ => SkipKind::UnsupportedGraphic,
    }
}

/// The placeholder types that carry page **furniture** rather than the author's content: the
/// slide number, the footer, the date and the notes-page header.
///
/// These are design attributes SelahCue deliberately replaces, exactly like fonts and colours —
/// so they are neither imported nor reported as drops (one standing notice covers replaced
/// design, per the report module's own rule).
const FURNITURE_PLACEHOLDERS: [&str; 4] = ["sldNum", "ftr", "dt", "hdr"];

/// Whether a shape is page furniture. **Placeholder type decides, and nothing else does** — a
/// footer is not distinguishable from body text by position, size or order.
///
/// Measured on seven genuinely PowerPoint-authored decks: 124 `sldNum` placeholders carrying
/// text and 5 `ftr`, roughly one per slide. Treating them as body put the page number and the
/// footer on the audience screen (`2026 Market Report | 2 | The market is moving from…`) and
/// spent the joined-body budget on them, which pushed real content into truncation and escalated
/// ordinary decks to the loudest report tier.
///
/// Matched case-insensitively: the tag is `sldNum` in every file Microsoft writes, but a
/// third-party producer getting the case wrong must not put a page number in front of a
/// congregation.
pub(crate) fn is_furniture(shape: &Shape) -> bool {
    shape.placeholder.as_deref().is_some_and(|p| {
        FURNITURE_PLACEHOLDERS
            .iter()
            .any(|f| f.eq_ignore_ascii_case(p))
    })
}

/// The speaker-notes text of a notes-slide part: the body placeholder's shape if there is one,
/// otherwise every text shape that is not furniture. PowerPoint puts a slide-image placeholder and
/// usually a slide-number placeholder on the same part, and neither is speaker notes.
///
/// The furniture predicate is shared with the slide-body path on purpose. It used to be an
/// inline `!= Some("sldNum")` here and nothing at all there, so the notes were clean and the
/// audience-facing text was not — the two rules drifted precisely because there were two.
pub(crate) fn notes_text(content: &SlideContent) -> String {
    let body = content
        .shapes
        .iter()
        .find(|s| s.placeholder.as_deref() == Some("body"));
    let lines: Vec<&str> = match body {
        Some(s) => s.lines.iter().map(String::as_str).collect(),
        None => content
            .shapes
            .iter()
            .filter(|s| !is_furniture(s))
            .flat_map(|s| s.lines.iter().map(String::as_str))
            .collect(),
    };
    lines.join("\n").trim().to_string()
}

/// Whether a shape is the slide's title. **Placeholder type decides, and nothing else does.**
pub(crate) fn is_title(shape: &Shape) -> bool {
    matches!(
        shape.placeholder.as_deref(),
        Some("title") | Some("ctrTitle")
    )
}
