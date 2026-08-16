//! The partial-import report: what arrived, what was cut, and what was dropped.
//!
//! Three lists, kept separate on purpose, because collapsing them is how a loss gets buried:
//!
//! - **`skipped`** — content the user would notice missing. This is what *"2 charts skipped"*
//!   comes from.
//! - **`truncations`** — content that arrived but was cut to fit a cap. Silent truncation is the
//!   quietest way to be lossy and the easiest to miss in review, so it gets its own list and its
//!   own assertions.
//! - **`notices`** — facts that are not losses.
//!
//! A design attribute we deliberately replace is **not** a skipped item. Animations, transitions,
//! masters, layouts, fonts and colours are swapped for the SelahCue theme by intent, and
//! *"24 transitions skipped"* would bury the two dropped charts. One standing notice covers them.
//!
//! The report is **always returned, never `Option<ImportReport>`** — an `Option` invites
//! `if let Some(report)` and a silent path where a loss is never shown.

use serde::ser::{SerializeStruct, Serializer};
use serde::Serialize;

use crate::hygiene;
use crate::limits::{MAX_REPORT_DETAIL_LEN, MAX_REPORT_ITEMS};
use crate::model::ImportSource;

/// Which bound stopped the importer taking more.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LimitKind {
    Slides,
    Elements,
    Pictures,
    Images,
    Lines,
}

impl LimitKind {
    fn describe(self) -> &'static str {
        match self {
            LimitKind::Slides => "slides",
            LimitKind::Elements => "elements on a slide",
            LimitKind::Pictures => "pictures on a slide",
            LimitKind::Images => "images in the presentation",
            LimitKind::Lines => "lines on a slide",
        }
    }
}

/// Why one piece of content did not make it in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SkipKind {
    Chart,
    Table,
    SmartArt,
    OleObject,
    UnsupportedGraphic,
    HiddenSlide,
    NestedContainer,
    ExternalImage,
    DuplicatePart,
    /// An entry whose NAME the archive reader refused — over the length cap, or carrying a NUL.
    /// Deliberately not [`DuplicatePart`](SkipKind::DuplicatePart): these are not duplicates, and
    /// telling the operator "the first copy was used" when there was no first copy is a false
    /// statement about their file.
    MalformedEntryName,
    DoctypeRejected,
    ImageFormatUnsupported,
    ImageColourUnsupported,
    ImageVariantUnsupported,
    ImageUnreadable,
    ImageTooLarge,
    /// The import's whole-archive extraction budget was used up before this image was reached, so
    /// it — and every image after it — was not extracted. **The slides' text still imported.**
    ///
    /// Aborting here instead would contradict the partial-import rule the rest of this crate
    /// keeps: a deck whose photographs are collectively enormous is a big deck, not a hostile
    /// one, and the operator would rather have the words than nothing at all. The *bomb* budget is
    /// a different bound and still aborts.
    MediaBudgetExhausted,
    LibraryFull,
    MediaCommitFailed,
    UnreadablePart,
    /// The ingress backstop fired: a built slide fell outside the presentation layer's own bounds
    /// and was dropped rather than carried into the deck library. Unreachable while the parsers'
    /// clamps hold — which is the point of having it.
    SlideOutOfBounds,
    LimitReached(LimitKind),
}

impl SkipKind {
    /// A stable machine tag. The UI groups and counts on this; it must not drift.
    pub fn tag(self) -> &'static str {
        match self {
            SkipKind::Chart => "chart",
            SkipKind::Table => "table",
            SkipKind::SmartArt => "smart_art",
            SkipKind::OleObject => "ole_object",
            SkipKind::UnsupportedGraphic => "unsupported_graphic",
            SkipKind::HiddenSlide => "hidden_slide",
            SkipKind::NestedContainer => "nested_container",
            SkipKind::ExternalImage => "external_image",
            SkipKind::DuplicatePart => "duplicate_part",
            SkipKind::MalformedEntryName => "malformed_entry_name",
            SkipKind::DoctypeRejected => "doctype_rejected",
            SkipKind::ImageFormatUnsupported => "image_format_unsupported",
            SkipKind::ImageColourUnsupported => "image_colour_unsupported",
            SkipKind::ImageVariantUnsupported => "image_variant_unsupported",
            SkipKind::ImageUnreadable => "image_unreadable",
            SkipKind::ImageTooLarge => "image_too_large",
            SkipKind::MediaBudgetExhausted => "media_budget_exhausted",
            SkipKind::LibraryFull => "library_full",
            SkipKind::MediaCommitFailed => "media_commit_failed",
            SkipKind::UnreadablePart => "unreadable_part",
            SkipKind::SlideOutOfBounds => "slide_out_of_bounds",
            SkipKind::LimitReached(_) => "limit_reached",
        }
    }

    /// The operator-facing sentence, **carrying the recovery where one exists**. A report that
    /// says only what is gone teaches a volunteer to dismiss reports; one that says what to do
    /// about it gets acted on.
    pub fn message(self) -> String {
        match self {
            SkipKind::Chart => "A chart was skipped — charts aren't imported.".into(),
            SkipKind::Table => "A table was skipped — tables aren't imported.".into(),
            SkipKind::SmartArt => "A SmartArt graphic was skipped.".into(),
            SkipKind::OleObject => "An embedded object was skipped.".into(),
            SkipKind::UnsupportedGraphic => {
                "A graphic that SelahCue can't show was skipped.".into()
            }
            SkipKind::HiddenSlide => {
                "A hidden slide was skipped — unhide it in PowerPoint to include it.".into()
            }
            SkipKind::NestedContainer => {
                "An embedded file inside this presentation was skipped.".into()
            }
            SkipKind::ExternalImage => {
                "An image stored outside this file was skipped — SelahCue never fetches images \
                 over the network. Embed it in PowerPoint and import again."
                    .into()
            }
            SkipKind::DuplicatePart => {
                "A duplicated part of this file was skipped; the first copy was used.".into()
            }
            SkipKind::MalformedEntryName => {
                "A part of this file had an unusable name and was skipped.".into()
            }
            SkipKind::DoctypeRejected => {
                "Part of this file used a document type declaration, which SelahCue doesn't open."
                    .into()
            }
            SkipKind::ImageFormatUnsupported => {
                "An image in a format SelahCue can't read was skipped — re-save it as PNG or JPEG."
                    .into()
            }
            SkipKind::ImageColourUnsupported => {
                "A CMYK image was skipped — CMYK images aren't supported. Re-save the image as \
                 RGB (in most tools: export for web or screen)."
                    .into()
            }
            SkipKind::ImageVariantUnsupported => {
                "An unusual JPEG variant was skipped — re-save it as a standard JPEG or PNG.".into()
            }
            SkipKind::ImageUnreadable => "An image was skipped — its data is damaged.".into(),
            SkipKind::ImageTooLarge => {
                "An image was skipped because it is too large — resize it and import again.".into()
            }
            SkipKind::MediaBudgetExhausted => {
                "This presentation's images add up to more than SelahCue imports, so some were \
                 skipped — the slides' text was imported. Remove or shrink some images and import \
                 again."
                    .into()
            }
            SkipKind::LibraryFull => {
                "An image was skipped because your media library is full — remove unused media \
                 and import again."
                    .into()
            }
            SkipKind::MediaCommitFailed => {
                "An image couldn't be saved to your media library; the slide's text was imported."
                    .into()
            }
            SkipKind::UnreadablePart => {
                "Part of this presentation couldn't be read and was skipped.".into()
            }
            SkipKind::SlideOutOfBounds => {
                "A slide couldn't be built within SelahCue's limits and was skipped.".into()
            }
            SkipKind::LimitReached(k) => format!(
                "SelahCue's limit on {} was reached, so the rest were not imported.",
                k.describe()
            ),
        }
    }

    /// Whether this drop is an **image** loss, for the report-severity image-ratio test.
    fn is_image_loss(self) -> bool {
        matches!(
            self,
            SkipKind::ImageFormatUnsupported
                | SkipKind::ImageColourUnsupported
                | SkipKind::ImageVariantUnsupported
                | SkipKind::ImageUnreadable
                | SkipKind::ImageTooLarge
                | SkipKind::MediaBudgetExhausted
                | SkipKind::ExternalImage
                | SkipKind::LibraryFull
                | SkipKind::MediaCommitFailed
                | SkipKind::LimitReached(LimitKind::Images)
                | SkipKind::LimitReached(LimitKind::Pictures)
        )
    }

    /// Whether this drop means a slide the author meant to show never arrived — the losses a
    /// preview cannot reveal, and therefore the ones that escalate the report.
    fn is_missing_slide(self) -> bool {
        matches!(
            self,
            SkipKind::UnreadablePart
                | SkipKind::DoctypeRejected
                | SkipKind::SlideOutOfBounds
                | SkipKind::LimitReached(LimitKind::Slides)
        )
    }
}

/// One dropped item.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SkippedItem {
    /// The slide it came from, if it came from one: **0-based in the SOURCE document** — the
    /// slide's own number in PowerPoint, or the block's number in a pasted text.
    ///
    /// Deliberately not the position the slide takes in the built deck. Those two spaces diverge
    /// the moment anything is dropped, and only this one is stable while parsing: an output
    /// position captured before a slide turns out to be hidden or empty is handed straight to the
    /// next slide, so the drop would end up naming a slide it has nothing to do with. Every index
    /// in this report — here and in [`Truncation`] — is in this one space.
    pub slide_index: Option<usize>,
    pub kind: SkipKind,
    /// A short, already-hygienised detail — an archive entry name, a sniffed format. Never raw
    /// attacker text: it passed [`hygiene::clean_single_line`] before it got here.
    pub detail: String,
}

impl Serialize for SkippedItem {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut st = s.serialize_struct("SkippedItem", 5)?;
        st.serialize_field("slide_index", &self.slide_index)?;
        st.serialize_field("kind", self.kind.tag())?;
        if let SkipKind::LimitReached(k) = self.kind {
            st.serialize_field("limit", &k)?;
        } else {
            st.skip_field("limit")?;
        }
        st.serialize_field("detail", &self.detail)?;
        st.serialize_field("message", &self.kind.message())?;
        st.end()
    }
}

/// Which field was cut to fit a cap.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TruncatedField {
    Title,
    BodyLine,
    BodyLines,
    Notes,
}

/// Content that arrived but did not arrive whole.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Truncation {
    /// 0-based in the **source** document, exactly as [`SkippedItem::slide_index`].
    pub slide_index: usize,
    pub what: TruncatedField,
    /// How much was kept (characters, or lines for [`TruncatedField::BodyLines`]).
    pub kept: usize,
    /// How much was dropped, in the same unit.
    pub dropped: usize,
}

/// A fact about the import that is not a loss.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Notice {
    /// The standing one: layout, fonts and colours were replaced by the SelahCue theme.
    ThemeReplaced,
    /// The presentation embedded its own font files. They are never extracted or parsed — font
    /// parsing is its own decoder surface and this importer does not open one — and the imported
    /// slides use the SelahCue theme's font instead.
    ///
    /// **One notice, not one item per file.** These used to be skipped items, and a real deck
    /// produced thirty-five drops of which twenty-five were embedded fonts, itemised one per file
    /// — consuming the hundred-item budget that real losses need and burying them. A design
    /// attribute SelahCue replaces on purpose is not a skipped item; one standing notice covers
    /// them, exactly as it does for transitions, masters and colours.
    EmbeddedFontsReplaced,
    /// The presentation's slide order could not be read, so natural filename order was used.
    /// **This is the loudest notice there is** — twenty-four slides in the wrong order is worse
    /// than a dropped chart, and it is invisible in a preview.
    SlideOrderInferred,
    /// The slide size was missing, so 16:9 was assumed.
    SlideSizeAssumed,
    /// A picture carried no geometry (it inherited a layout placeholder's), so it was centred.
    PictureGeometryAssumed,
    /// Bytes that were not valid UTF-8 were replaced with U+FFFD.
    EncodingReplaced { count: usize },
    /// Control or bidi characters were removed by string hygiene.
    ControlCharsStripped { count: usize },
    /// The pasted text was longer than the clipboard cap and was cut.
    ClipboardTruncated { dropped_bytes: usize },
}

impl Notice {
    pub fn tag(self) -> &'static str {
        match self {
            Notice::ThemeReplaced => "theme_replaced",
            Notice::EmbeddedFontsReplaced => "embedded_fonts_replaced",
            Notice::SlideOrderInferred => "slide_order_inferred",
            Notice::SlideSizeAssumed => "slide_size_assumed",
            Notice::PictureGeometryAssumed => "picture_geometry_assumed",
            Notice::EncodingReplaced { .. } => "encoding_replaced",
            Notice::ControlCharsStripped { .. } => "control_chars_stripped",
            Notice::ClipboardTruncated { .. } => "clipboard_truncated",
        }
    }

    pub fn message(self) -> String {
        match self {
            Notice::ThemeReplaced => {
                "Layout, fonts and colours were replaced by your SelahCue theme.".into()
            }
            Notice::EmbeddedFontsReplaced => {
                "This presentation carried its own fonts. SelahCue doesn't open font files, so \
                 the imported slides use your SelahCue theme's font."
                    .into()
            }
            Notice::SlideOrderInferred => {
                "The slide order couldn't be read from this file, so slides were ordered by name \
                 — check the order before you go live."
                    .into()
            }
            Notice::SlideSizeAssumed => {
                "This presentation didn't state its slide size, so 16:9 was assumed.".into()
            }
            Notice::PictureGeometryAssumed => {
                "A picture didn't state where it sits on the slide, so it was centred.".into()
            }
            Notice::EncodingReplaced { count } => format!(
                "{count} character(s) couldn't be decoded and were replaced — the file may not be \
                 UTF-8 text."
            ),
            Notice::ControlCharsStripped { count } => {
                format!("{count} hidden or formatting character(s) were removed from the text.")
            }
            Notice::ClipboardTruncated { dropped_bytes } => format!(
                "The pasted text was too long, so {dropped_bytes} byte(s) at the end were not \
                 imported."
            ),
        }
    }
}

impl Serialize for Notice {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut st = s.serialize_struct("Notice", 3)?;
        st.serialize_field("kind", self.tag())?;
        match self {
            Notice::EncodingReplaced { count } | Notice::ControlCharsStripped { count } => {
                st.serialize_field("count", count)?
            }
            Notice::ClipboardTruncated { dropped_bytes } => {
                st.serialize_field("count", dropped_bytes)?
            }
            _ => st.skip_field("count")?,
        }
        st.serialize_field("message", &self.message())?;
        st.end()
    }
}

/// How loudly the report should be presented. The predicate lives here, in the pure crate, so it
/// is tested once rather than re-derived in the webview.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// Nothing was lost. A clean import must feel clean: a status toast, no panel, no warning.
    Lossless,
    /// Something was lost, but a preview would reveal it. Toast plus a collapsed panel that does
    /// not auto-dismiss — a missable loss may not time out on its own.
    Partial,
    /// Something was lost that **a preview cannot reveal**. The panel opens expanded and needs an
    /// explicit dismissal. Still never a modal between the operator and their deck.
    Material,
}

/// The report. Always returned.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImportReport {
    pub source: ImportSource,
    pub slides_imported: usize,
    /// How many slides the source held, where that is meaningful. `None` for text sources, where
    /// "slides in the source" is not a thing that exists.
    pub slides_in_source: Option<usize>,
    pub images_imported: usize,
    pub notes_imported: usize,
    pub skipped: Vec<SkippedItem>,
    /// Drops beyond [`MAX_REPORT_ITEMS`] — counted, not listed, so the report cannot itself
    /// become an unbounded buffer.
    pub skipped_overflow: usize,
    pub truncations: Vec<Truncation>,
    /// Truncations beyond [`MAX_REPORT_ITEMS`], counted rather than listed — the same bound
    /// `skipped` has, and now the same honesty.
    ///
    /// Only `skipped` used to carry an overflow counter, so a deck that cut text on more than a
    /// hundred slides reported the first hundred and dropped the rest **in silence**. Silent
    /// truncation is the quietest way to be lossy; silently truncating the record OF truncation is
    /// the same defect one level up, and it lands on the list that already exists because losses
    /// here are the easiest to miss.
    pub truncations_overflow: usize,
    pub notices: Vec<Notice>,
}

impl ImportReport {
    /// Whether nothing was dropped or cut.
    pub fn is_lossless(&self) -> bool {
        self.skipped.is_empty()
            && self.skipped_overflow == 0
            && self.truncations.is_empty()
            && self.truncations_overflow == 0
    }

    /// How many image drops the report holds, itemised.
    fn images_dropped(&self) -> usize {
        self.skipped
            .iter()
            .filter(|s| s.kind.is_image_loss())
            .count()
    }

    /// The presentation tier (product decision §4). Intrusiveness is spent only where a preview
    /// is blind, because a volunteer who sees a warning panel for every skipped transition learns
    /// to dismiss all of them.
    pub fn severity(&self) -> Severity {
        // The Material predicates are tested FIRST, before the lossless short-circuit, because
        // one of them is a NOTICE rather than a drop: an import whose slide order had to be
        // inferred loses nothing and is still the most dangerous outcome here. Twenty-four slides
        // in the wrong order is invisible in a preview and worse than any single dropped chart.
        if self.notices.contains(&Notice::SlideOrderInferred) {
            return Severity::Material;
        }
        if self.is_lossless() {
            return Severity::Lossless;
        }
        // A slide the author meant to show never arrived.
        if self.skipped.iter().any(|s| s.kind.is_missing_slide()) {
            return Severity::Material;
        }
        // Visible slide text was cut.
        if self
            .truncations
            .iter()
            .any(|t| matches!(t.what, TruncatedField::BodyLine | TruncatedField::BodyLines))
        {
            return Severity::Material;
        }
        // More than a hundred drops, or more than a hundred cuts, means the deck is grossly
        // unrepresentable — and past the cap we can no longer even say WHICH slides lost text.
        if self.skipped_overflow > 0 || self.truncations_overflow > 0 {
            return Severity::Material;
        }
        // A quarter or more of the deck's imagery is gone.
        let dropped = self.images_dropped();
        let referenced = dropped + self.images_imported;
        if referenced > 0 && dropped * 4 > referenced {
            return Severity::Material;
        }
        Severity::Partial
    }
}

/// Accumulates a report **during** the parse, not afterwards — only the parser knows which slide
/// a dropped chart was on.
#[derive(Debug, Clone, Default)]
pub struct ReportBuilder {
    skipped: Vec<SkippedItem>,
    skipped_overflow: usize,
    truncations: Vec<Truncation>,
    truncations_overflow: usize,
    notices: Vec<Notice>,
    stripped_chars: usize,
    replaced_chars: usize,
    images_imported: usize,
    notes_imported: usize,
    slides_in_source: Option<usize>,
}

impl ReportBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a drop. Past [`MAX_REPORT_ITEMS`] the item is counted rather than listed.
    pub fn skip(&mut self, slide_index: Option<usize>, kind: SkipKind, detail: &str) {
        if self.skipped.len() >= MAX_REPORT_ITEMS {
            self.skipped_overflow += 1;
            return;
        }
        // The detail is attacker-chosen on the archive paths. It is sanitised HERE, at the
        // producer, so no downstream renderer has to remember to.
        let cleaned = hygiene::clean_single_line(detail, MAX_REPORT_DETAIL_LEN);
        self.stripped_chars += cleaned.stripped;
        self.skipped.push(SkippedItem {
            slide_index,
            kind,
            detail: cleaned.text,
        });
    }

    /// Record content that arrived but was cut. `dropped == 0` records nothing, so callers can
    /// call this unconditionally.
    pub fn truncate(
        &mut self,
        slide_index: usize,
        what: TruncatedField,
        kept: usize,
        dropped: usize,
    ) {
        if dropped == 0 {
            return;
        }
        if self.truncations.len() >= MAX_REPORT_ITEMS {
            // Counted, not listed — never simply forgotten.
            self.truncations_overflow = self.truncations_overflow.saturating_add(1);
            return;
        }
        self.truncations.push(Truncation {
            slide_index,
            what,
            kept,
            dropped,
        });
    }

    /// Record a notice, keeping the list free of duplicates for the parameterless kinds.
    pub fn notice(&mut self, notice: Notice) {
        let dup = matches!(
            notice,
            Notice::ThemeReplaced
                | Notice::EmbeddedFontsReplaced
                | Notice::SlideOrderInferred
                | Notice::SlideSizeAssumed
                | Notice::PictureGeometryAssumed
        ) && self.notices.contains(&notice);
        if !dup && self.notices.len() < MAX_REPORT_ITEMS {
            self.notices.push(notice);
        }
    }

    /// Fold in the counts from a [`hygiene::clean`] call so stripping is never silent.
    pub fn record_hygiene(&mut self, cleaned: &hygiene::Cleaned) {
        self.stripped_chars += cleaned.stripped;
    }

    /// Record U+FFFD substitutions from a lossy text decode.
    pub fn record_replacements(&mut self, count: usize) {
        self.replaced_chars += count;
    }

    pub fn count_image(&mut self) {
        self.images_imported += 1;
    }

    pub fn count_notes(&mut self) {
        self.notes_imported += 1;
    }

    pub fn set_slides_in_source(&mut self, n: usize) {
        self.slides_in_source = Some(n);
    }

    /// How many drops have been recorded (itemised plus overflowed) — the parsers use this to
    /// decide whether a further probe is worth the work.
    pub fn skipped_count(&self) -> usize {
        self.skipped.len() + self.skipped_overflow
    }

    /// Seal the builder into a report for `slides_imported` slides from `source`.
    pub fn finish(mut self, source: ImportSource, slides_imported: usize) -> ImportReport {
        // The standing notice: replaced design attributes are deliberate, so they are ONE notice
        // rather than one skipped item per transition, which would bury the real drops.
        self.notice(Notice::ThemeReplaced);
        if self.replaced_chars > 0 {
            let count = self.replaced_chars;
            self.notice(Notice::EncodingReplaced { count });
        }
        if self.stripped_chars > 0 {
            let count = self.stripped_chars;
            self.notice(Notice::ControlCharsStripped { count });
        }
        ImportReport {
            source,
            slides_imported,
            slides_in_source: self.slides_in_source,
            images_imported: self.images_imported,
            notes_imported: self.notes_imported,
            skipped: self.skipped,
            skipped_overflow: self.skipped_overflow,
            truncations: self.truncations,
            truncations_overflow: self.truncations_overflow,
            notices: self.notices,
        }
    }
}

/// Map a decode failure onto its report entry. `DecodeError` carries no `Display` — deliberately,
/// so nobody `format!("{:?}")`s an internal enum into operator-facing text. This is the one place
/// that translation happens.
pub(crate) fn skip_kind_for_decode(e: selahcue_engine::DecodeError) -> SkipKind {
    use selahcue_engine::DecodeError as D;
    match e {
        D::Empty | D::Malformed => SkipKind::ImageUnreadable,
        D::Unsupported => SkipKind::ImageFormatUnsupported,
        D::UnsupportedColour => SkipKind::ImageColourUnsupported,
        D::UnsupportedVariant => SkipKind::ImageVariantUnsupported,
        D::TooLarge | D::Oversize => SkipKind::ImageTooLarge,
        // `Missing` belongs to the engine's file-path decode, which this crate never calls — it
        // reaches the decoder only through a byte slice. Unreachable here; mapped, not assumed
        // away.
        D::Missing => SkipKind::ImageUnreadable,
    }
}
