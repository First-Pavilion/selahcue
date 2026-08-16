//! The neutral middle: what every source parses **into**, before anything becomes a slide.
//!
//! [`ImportedDocument`] exists so all three sources converge on one place that decides how a
//! slide's text becomes elements. Without it, pasted text and `.pptx` text would drift into
//! producing structurally different decks, and the difference would only ever be discovered by a
//! user, on a Sunday.

use serde::Serialize;

use crate::report::ReportBuilder;

/// Where an import came from. Carried into the report so the operator sees what they imported.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ImportSource {
    /// A `.txt` file, named by its hygienised file stem.
    TxtFile { name: String },
    /// A `.pptx` file, named by its hygienised file stem.
    Pptx { name: String },
    /// Pasted text.
    Clipboard,
}

impl ImportSource {
    /// The source's own name, where it has one.
    pub fn name(&self) -> Option<&str> {
        match self {
            ImportSource::TxtFile { name } | ImportSource::Pptx { name } => Some(name),
            ImportSource::Clipboard => None,
        }
    }
}

/// A rectangle in per-mille of the frame — the geometry unit the whole presentation layer uses,
/// so an imported picture lands identically at 1080p and 4K.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PermilleRect {
    pub x: u16,
    pub y: u16,
    pub w: u16,
    pub h: u16,
}

impl PermilleRect {
    /// A centred rect covering three-fifths of the frame — the fallback when a picture inherits
    /// its geometry from a layout placeholder we do not read.
    pub const CENTRED: PermilleRect = PermilleRect {
        x: 200,
        y: 200,
        w: 600,
        h: 600,
    };

    /// Clamp into the frame. A hostile `a:off`/`a:ext` can name any offset; the result must still
    /// be a rectangle that composes.
    pub fn clamped(self) -> PermilleRect {
        let x = self.x.min(1000);
        let y = self.y.min(1000);
        PermilleRect {
            x,
            y,
            w: self.w.clamp(1, 1000 - x.min(999)),
            h: self.h.clamp(1, 1000 - y.min(999)),
        }
    }
}

/// A handle to bytes the shell has **staged but not committed**. Resolved to a real `MediaRef`
/// only after the atomic commit, which is what makes "nothing is visible until the whole parse
/// passed bounds" achievable: at parse time there is no final path to leak.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct MediaSlot(pub u32);

/// One picture on an imported slide.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ImportedPicture {
    pub slot: MediaSlot,
    pub rect: PermilleRect,
}

/// One imported slide, before it becomes an `AuthoredSlide`.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ImportedSlide {
    /// This slide's 0-based position **in the source document** — the slide's number in
    /// PowerPoint, or the block's number in a pasted text.
    ///
    /// It is carried through the whole pipeline so that every index in the report lives in **one**
    /// space. The alternative — the position the slide ends up occupying in the built deck — is
    /// not stable during a parse: a slide that turns out to be hidden or empty gives its output
    /// position back to the next one, so a drop already recorded against it would end up naming an
    /// unrelated slide. The source position is also the only one the operator can act on, because
    /// it is the number their own file shows them.
    pub source_index: usize,
    /// The slide's title, if the source had one.
    pub title: Option<String>,
    /// Body lines, already clamped and hygienised.
    pub body: Vec<String>,
    /// Speaker notes, already clamped and hygienised.
    pub notes: String,
    /// Pictures (`.pptx` only), in the order they were found.
    pub pictures: Vec<ImportedPicture>,
}

impl ImportedSlide {
    /// Whether this slide carries anything worth importing. An empty slide is never produced.
    pub fn has_content(&self) -> bool {
        self.title.as_ref().is_some_and(|t| !t.trim().is_empty())
            || self.body.iter().any(|l| !l.trim().is_empty())
            || !self.notes.trim().is_empty()
            || !self.pictures.is_empty()
    }
}

/// The parsed document plus the report accumulated while parsing it.
#[derive(Debug, Clone)]
pub struct ImportedDocument {
    pub source: ImportSource,
    pub slides: Vec<ImportedSlide>,
    pub report: ReportBuilder,
}
