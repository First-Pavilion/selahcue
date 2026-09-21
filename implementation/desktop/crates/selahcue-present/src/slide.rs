//! The presentation slide model (content). The output *theme* (how content is
//! styled) lives in [`crate::theme`] — content is orthogonal to the theme.

use serde::{Deserialize, Serialize};

/// Upper bound (chars) on each [`SongAttribution`] string field (no-leak): generous for any
/// real CCLI catalogue number, artist credit, or publisher name, while keeping a
/// hostile/hand-edited payload from growing a slide's content without limit.
pub const MAX_SONG_ATTRIBUTION_FIELD_LEN: usize = 200;

/// Song licensing/copyright attribution (PRD `SelahCue-PRD.md` FR-021), captured per song so
/// a themed [`footer`](crate::theme::Theme::footer) region can render it on the audience
/// output — CCLI reporting is a legal obligation for licensed song use, not a nicety
/// (OUT-006/OUT-015). Distinct from `Slide::body`, so the footer composes without polluting
/// the sung lyric content; distinct from `Slide::title` (which already carries the song
/// title — FR-021's remaining field), so a theme can style the two independently.
///
/// `copyright_year` and `publisher` complete FR-021's field set (title, author, copyright
/// year, publisher, CCLI#) for compliance capture; only `ccli_number` and `author` feed the
/// footer line the Figma `208:135` mock draws today ([`footer_line`](Self::footer_line)) — a
/// richer footer format is a follow-up, not blocked by this shape.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct SongAttribution {
    /// Author/artist attribution (e.g. `"Sinach"`).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub author: Option<String>,
    /// CCLI song number (e.g. `"7115744"`). A `String`, not a numeric type: CCLI numbers are
    /// opaque catalogue identifiers — some sources carry a leading "CCLI Song #" a caller may
    /// hand-trim — and modelling them as an integer risks losing leading formatting or
    /// overflowing on hand-entry, neither of which this compositor needs to parse or compute.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ccli_number: Option<String>,
    /// Copyright year (e.g. `"2015"`). PRD FR-021 field; not part of the footer string today.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub copyright_year: Option<String>,
    /// Publisher (e.g. `"Integrity Music"`). PRD FR-021 field; not part of the footer string
    /// today.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub publisher: Option<String>,
}

impl SongAttribution {
    /// Whether every populated field is within [`MAX_SONG_ATTRIBUTION_FIELD_LEN`] (no-leak).
    /// There is no ingress path today that deserializes an untrusted `Slide` directly (unlike
    /// `AuthoredSlide`/`Theme`, `Slide` is only ever built internally — see `slide.rs`'s
    /// module doc and `selahcue-app::controller`), so nothing calls this yet; it exists so a
    /// future ingress (e.g. a song-import path) has a ready, tested bound to enforce, matching
    /// the `Element::within_bounds` / `MediaAsset::within_bounds` convention.
    pub fn within_bounds(&self) -> bool {
        [
            &self.author,
            &self.ccli_number,
            &self.copyright_year,
            &self.publisher,
        ]
        .iter()
        .all(|f| {
            f.as_deref()
                .map(|s| s.chars().count() <= MAX_SONG_ATTRIBUTION_FIELD_LEN)
                .unwrap_or(true)
        })
    }

    /// True when nothing here is worth rendering (every field absent or blank) — the signal a
    /// composer uses to decide whether a themed footer region has anything to draw, so a
    /// theme WITH a footer region never draws an empty line for a slide with no song metadata.
    pub fn is_blank(&self) -> bool {
        [
            &self.author,
            &self.ccli_number,
            &self.copyright_year,
            &self.publisher,
        ]
        .iter()
        .all(|f| f.as_deref().map(str::trim).unwrap_or("").is_empty())
    }

    /// The footer line Figma `208:135` draws: `"CCLI #<number> · <author>"`, degrading to
    /// whichever of the two is present, and empty when neither is (in which case the caller
    /// should treat this as [`is_blank`](Self::is_blank) and render no footer at all).
    pub fn footer_line(&self) -> String {
        let ccli = self
            .ccli_number
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let author = self
            .author
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty());
        match (ccli, author) {
            (Some(c), Some(a)) => format!("CCLI #{c} \u{b7} {a}"),
            (Some(c), None) => format!("CCLI #{c}"),
            (None, Some(a)) => a.to_string(),
            (None, None) => String::new(),
        }
    }
}

/// A basic static slide: a title and zero or more body lines rendered over the
/// theme background (FR-009). Richer content (media, columns) extends this later.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Slide {
    pub title: String,
    pub body: Vec<String>,
    /// Optional song licensing/attribution metadata (FR-021, OUT-006/OUT-015) — feeds a
    /// themed [`footer`](crate::theme::Theme::footer) region when the active theme has one.
    /// Additive and backward-compatible: existing `Slide` JSON without this field
    /// deserializes to `None`, and a slide with no song metadata serialises without the key
    /// (byte-stable, the same pattern `Theme::band`/`Theme::footer` follow).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub song: Option<SongAttribution>,
}

impl Slide {
    /// A slide with a title and no body lines.
    pub fn title(title: impl Into<String>) -> Self {
        Slide {
            title: title.into(),
            body: Vec::new(),
            song: None,
        }
    }

    /// A slide with a title and body lines.
    pub fn new(
        title: impl Into<String>,
        body: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        Slide {
            title: title.into(),
            body: body.into_iter().map(Into::into).collect(),
            song: None,
        }
    }

    /// This slide with song attribution metadata attached (builder-style; FR-021).
    pub fn with_song(mut self, song: SongAttribution) -> Self {
        self.song = Some(song);
        self
    }

    /// Every text line, title first.
    pub fn lines(&self) -> impl Iterator<Item = &str> {
        std::iter::once(self.title.as_str()).chain(self.body.iter().map(String::as_str))
    }

    /// True if the slide has no visible text (renders as background only). Song attribution
    /// alone does not count as visible content — a slide with only `song` set and a blank
    /// title/body still renders as background only, exactly like before this field existed.
    pub fn is_blank(&self) -> bool {
        self.title.trim().is_empty() && self.body.iter().all(|l| l.trim().is_empty())
    }

    /// The footer line to render for this slide, or `None` when there is no song attribution
    /// (or it is entirely blank) — the composer's single check for "does a footer region have
    /// anything to draw".
    pub fn footer_line(&self) -> Option<String> {
        self.song
            .as_ref()
            .filter(|s| !s.is_blank())
            .map(SongAttribution::footer_line)
    }
}
