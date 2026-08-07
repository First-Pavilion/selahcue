//! Authored slide **decks** and their playback (Design 2.0 "Presentation & Media", Figma node
//! 329:124). A [`SlideDeck`] is an ordered list of [`AuthoredSlide`]s — the reusable
//! "presentation document" (FR-003) the operator builds in the slide editor (S8-4). Unlike a
//! scripture/song [`Slide`](crate::slide::Slide) (a transient title+body pair), an authored
//! slide **owns its own layered content**: a list of [`Element`]s (text boxes / shapes /
//! images — reusing the Canvas-Editing model), an optional per-slide [`Background`], speaker
//! notes, a per-slide [`Transition`], and optional auto-advance.
//!
//! Playback is [`DeckSession`]: the same **Preview→Live** discipline as [`Presenter`] — staging
//! a slide never changes Live; only [`go_live`](DeckSession::go_live) does — plus deck
//! navigation and injected-clock **auto-advance**. Content is orthogonal to the audience theme:
//! the theme supplies the fallback background + default styling, exactly as for a `Slide`.
//!
//! Bounded by [`MAX_DECK_SLIDES`] and [`MAX_NOTES_LEN`] (no-leak). Transitions render through a
//! deterministic [`crossfade`]; live video/audio playback is deferred (ADR-0020).
//!
//! [`Presenter`]: crate::present::Presenter

use std::collections::HashSet;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

use crate::compose::compose_authored_slide;
use crate::theme::{Background, Element, Theme, MAX_ELEMENTS};
use selahcue_core::media::{MediaId, MediaLibrary};
use selahcue_engine::raster::FrameBuffer;
use selahcue_engine::scene::Frame;

/// Upper bound on the slides in one deck (no-leak): the deck, its persistence, and any
/// playback scan stay bounded regardless of how many slides the operator authors.
pub const MAX_DECK_SLIDES: usize = 500;

/// Upper bound on a slide's speaker-notes length in characters (no-leak).
pub const MAX_NOTES_LEN: usize = 4000;

/// A stable per-deck slide id, assigned on insert and never reused within a deck (mirrors
/// `ItemId`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct SlideId(pub u64);

/// A stable **deck** id — the library's handle for a presentation, independent of its display
/// `name` (so a rename or a duplicate name never loses the deck's identity). `DeckId(0)` is the
/// **unassigned** sentinel: a deck created before this field existed (or a fresh `SlideDeck::new`)
/// carries `0` until the owning library mints a real id — the library self-heals every deck to a
/// unique non-zero id on load (mirrors the slide `mint_id` self-heal).
#[derive(
    Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Default, Serialize, Deserialize,
)]
pub struct DeckId(pub u64);

impl DeckId {
    /// serde `skip_serializing_if`: the unassigned `0` is omitted, so a deck that has never been
    /// assigned an id serialises byte-identically to the pre-`id` format (`{name,slides,next_id}`).
    fn is_unassigned(&self) -> bool {
        self.0 == 0
    }
}

/// How a slide enters the Live output. Additive; `Cut` (the default) omits the JSON key so a
/// plain slide's JSON stays minimal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Transition {
    /// Instant replace (no animation) — the default.
    #[default]
    Cut,
    /// A crossfade from the outgoing frame to this slide (see [`crossfade`]).
    Fade,
}

impl Transition {
    /// serde `skip_serializing_if`: a `Cut` (the default) omits the `transition` key.
    fn is_cut(t: &Transition) -> bool {
        matches!(t, Transition::Cut)
    }
}

/// One authored slide: its own layered [`Element`]s over an optional per-slide [`Background`],
/// with speaker notes, a [`Transition`], and optional auto-advance. All non-id fields default
/// to empty/`Cut`/`None` and are **omitted from JSON** when defaulted (byte-stable, additive) —
/// so a brand-new empty slide serialises as just its `id`, and older JSON missing a field
/// deserialises to that field's default.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuthoredSlide {
    /// Stable id within the owning deck.
    pub id: SlideId,
    /// The slide's own z-ordered layered elements (text boxes / shapes / images).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub elements: Vec<Element>,
    /// A per-slide background override; `None` falls back to the audience theme's background.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub background: Option<Background>,
    /// Speaker notes (bounded by [`MAX_NOTES_LEN`]); shown on the stage/confidence monitor,
    /// never on the audience output.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub notes: String,
    /// How this slide enters Live.
    #[serde(default, skip_serializing_if = "Transition::is_cut")]
    pub transition: Transition,
    /// Auto-advance dwell in seconds; `None` = off (the design's "Auto-advance: Off").
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub auto_advance_secs: Option<u32>,
}

impl AuthoredSlide {
    /// An empty slide with the given id (no elements, theme background, no notes, `Cut`, no
    /// auto-advance).
    pub fn new(id: SlideId) -> Self {
        AuthoredSlide {
            id,
            elements: Vec::new(),
            background: None,
            notes: String::new(),
            transition: Transition::Cut,
            auto_advance_secs: None,
        }
    }

    /// Whether the slide is within its content bounds (no-leak): element count within
    /// [`MAX_ELEMENTS`], notes within [`MAX_NOTES_LEN`], and every element within its own bound.
    pub fn within_bounds(&self) -> bool {
        self.elements.len() <= MAX_ELEMENTS
            && self.notes.chars().count() <= MAX_NOTES_LEN
            && self.elements.iter().all(Element::within_bounds)
    }
}

/// An ordered, bounded deck of [`AuthoredSlide`]s with stable ids — the reusable presentation
/// document. Serialises whole (name + slides + id counter) for JSON-blob persistence.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SlideDeck {
    /// The deck's display name ("Sermon: Grace That Feeds").
    pub name: String,
    /// The stable library id (see [`DeckId`]). Additive: the unassigned `0` is omitted, so a deck
    /// that has never been assigned an id keeps the byte-identical pre-`id` JSON; a deck the library
    /// has persisted carries its real id and round-trips it.
    #[serde(default, skip_serializing_if = "DeckId::is_unassigned")]
    id: DeckId,
    slides: Vec<AuthoredSlide>,
    /// The next id to assign — monotonic, never reused (mirrors `ServicePlan::next_id`).
    next_id: u64,
}

impl SlideDeck {
    /// A new empty deck (unassigned [`DeckId`] — the owning library mints one). The first inserted
    /// slide gets id `1`.
    pub fn new(name: impl Into<String>) -> Self {
        SlideDeck {
            name: name.into(),
            id: DeckId(0),
            slides: Vec::new(),
            next_id: 1,
        }
    }

    /// The stable deck id (`DeckId(0)` = not yet assigned by a library).
    pub fn id(&self) -> DeckId {
        self.id
    }

    /// Set the stable deck id (the owning library assigns it on create / self-heal on load).
    pub fn set_id(&mut self, id: DeckId) {
        self.id = id;
    }

    /// The slides in order.
    pub fn slides(&self) -> &[AuthoredSlide] {
        &self.slides
    }

    /// The number of slides.
    pub fn len(&self) -> usize {
        self.slides.len()
    }

    /// Whether the deck has no slides.
    pub fn is_empty(&self) -> bool {
        self.slides.is_empty()
    }

    /// Append a new empty slide, returning its id — or `None` if the deck is full
    /// ([`MAX_DECK_SLIDES`]).
    pub fn add_slide(&mut self) -> Option<SlideId> {
        self.insert_slide(self.slides.len())
    }

    /// Mint a fresh, collision-free [`SlideId`]. **Self-healing:** it advances `next_id` past
    /// every existing slide id before minting, so even a rehydrated deck whose `next_id` was
    /// loaded verbatim from a stale/tampered persisted blob can never mint an id that collides
    /// with a live slide (which would make `remove` delete two slides at once). Saturating —
    /// `core`/`present` never panic (an overflow at u64::MAX is unreachable under the 500-slide
    /// cap but is handled anyway).
    fn mint_id(&mut self) -> SlideId {
        if let Some(highest) = self.slides.iter().map(|s| s.id.0).max() {
            self.next_id = self.next_id.max(highest.saturating_add(1));
        }
        let id = SlideId(self.next_id);
        self.next_id = self.next_id.saturating_add(1);
        id
    }

    /// Insert a new empty slide at `index` (clamped to the end), returning its id — or `None`
    /// if the deck is full. Ids are monotonic and never reused.
    pub fn insert_slide(&mut self, index: usize) -> Option<SlideId> {
        if self.slides.len() >= MAX_DECK_SLIDES {
            return None;
        }
        let id = self.mint_id();
        let index = index.min(self.slides.len());
        self.slides.insert(index, AuthoredSlide::new(id));
        Some(id)
    }

    /// The slide with `id`, if present.
    pub fn get(&self, id: SlideId) -> Option<&AuthoredSlide> {
        self.slides.iter().find(|s| s.id == id)
    }

    /// A mutable handle to the slide with `id`, for editing its content.
    pub fn get_mut(&mut self, id: SlideId) -> Option<&mut AuthoredSlide> {
        self.slides.iter_mut().find(|s| s.id == id)
    }

    /// The slide at ordinal `index` (0-based), if in range.
    pub fn get_index(&self, index: usize) -> Option<&AuthoredSlide> {
        self.slides.get(index)
    }

    /// The ordinal position of `id`, if present.
    pub fn index_of(&self, id: SlideId) -> Option<usize> {
        self.slides.iter().position(|s| s.id == id)
    }

    /// Remove the slide with `id`; returns `true` if one was removed. Ids stay retired.
    pub fn remove(&mut self, id: SlideId) -> bool {
        let before = self.slides.len();
        self.slides.retain(|s| s.id != id);
        self.slides.len() != before
    }

    /// Move the slide at `from` to `to` (both clamped into range), shifting the others — the
    /// SLIDES-list drag reorder. Returns `false` (no-op) if the deck is empty.
    pub fn reorder(&mut self, from: usize, to: usize) -> bool {
        if self.slides.is_empty() {
            return false;
        }
        let from = from.min(self.slides.len() - 1);
        let to = to.min(self.slides.len() - 1);
        if from == to {
            return false;
        }
        let slide = self.slides.remove(from);
        self.slides.insert(to, slide);
        true
    }

    /// Duplicate the slide with `id` — a deep copy inserted directly after the original, with a
    /// fresh id. Returns the new id, or `None` if `id` is unknown or the deck is full.
    pub fn duplicate(&mut self, id: SlideId) -> Option<SlideId> {
        if self.slides.len() >= MAX_DECK_SLIDES {
            return None;
        }
        let index = self.index_of(id)?;
        let mut copy = self.slides[index].clone();
        let new_id = self.mint_id();
        copy.id = new_id;
        self.slides.insert(index + 1, copy);
        Some(new_id)
    }

    /// Whether the deck is within its bounds (no-leak): slide count within [`MAX_DECK_SLIDES`]
    /// and every slide within its own content bounds.
    pub fn within_bounds(&self) -> bool {
        self.slides.len() <= MAX_DECK_SLIDES && self.slides.iter().all(AuthoredSlide::within_bounds)
    }
}

/// A deterministic per-pixel **crossfade** between two rendered frames for a [`Transition::Fade`]
/// — `progress` 0 yields `from`, 255 yields `to`, linear per channel. Same-size only: a size
/// mismatch returns `from` unchanged (defensive; a deck composes every slide at the same output
/// resolution). Pure and deterministic — the same inputs always yield byte-identical output.
pub fn crossfade(from: &FrameBuffer, to: &FrameBuffer, progress: u8) -> FrameBuffer {
    if from.width() != to.width() || from.height() != to.height() {
        return from.clone();
    }
    let a = from.bytes();
    let b = to.bytes();
    let p = progress as u32;
    let inv = 255 - p;
    let mut out = Vec::with_capacity(a.len());
    for i in 0..a.len() {
        // Integer round-free lerp: at p=0 → a[i]; at p=255 → b[i] (exact endpoints).
        out.push(((a[i] as u32 * inv + b[i] as u32 * p) / 255) as u8);
    }
    FrameBuffer::from_rgba(from.width(), from.height(), out).unwrap_or_else(|| from.clone())
}

/// The used/unused split of a [`MediaLibrary`] against one or more decks.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsageReport {
    /// Assets referenced by at least one slide (an `Element::Image` or an image background).
    pub used: Vec<MediaId>,
    /// Imported assets no slide references (the design's "· 3 unused").
    pub unused: Vec<MediaId>,
}

/// Correlate a media library with the decks that might reference it: an asset is **used** when
/// some slide references its `path` (via an [`Element::Image`] source or an image
/// [`Background`]), otherwise **unused**. Pure and deterministic; ids come out in library order.
pub fn media_usage(lib: &MediaLibrary, decks: &[&SlideDeck]) -> UsageReport {
    let mut referenced: HashSet<&str> = HashSet::new();
    for deck in decks {
        for slide in deck.slides() {
            for el in &slide.elements {
                if let Element::Image { source, .. } = el {
                    referenced.insert(source.as_str());
                }
            }
            if let Some(Background::Image(bg)) = &slide.background {
                referenced.insert(bg.source.as_str());
            }
        }
    }
    let mut used = Vec::new();
    let mut unused = Vec::new();
    for asset in lib.assets() {
        if referenced.contains(asset.path.as_str()) {
            used.push(asset.id);
        } else {
            unused.push(asset.id);
        }
    }
    UsageReport { used, unused }
}

/// Preview→Live playback over a [`SlideDeck`] (Design 2.0 Present mode). Holds a **staged**
/// (Preview) slide cursor and an independent **live** cursor: navigating/staging moves only the
/// preview cursor; [`go_live`](DeckSession::go_live) is the sole action that changes Live
/// (mirrors [`Presenter`](crate::present::Presenter)). Auto-advance is driven by an injected
/// clock via [`tick`](DeckSession::tick), so it is fully deterministic.
pub struct DeckSession {
    deck: SlideDeck,
    theme: Theme,
    width: u32,
    height: u32,
    /// Preview (staged) slide ordinal. Meaningful only when the deck is non-empty.
    preview_idx: usize,
    /// Live slide ordinal; `None` = nothing is live yet.
    live_idx: Option<usize>,
    /// When the current live slide started, for auto-advance; `None` until the next tick sets it
    /// (so `go_live` needs no clock).
    live_since: Option<Instant>,
}

impl DeckSession {
    /// A session over `deck` rendered with `theme` at `width×height`. Preview starts on the
    /// first slide (if any); nothing is live.
    pub fn new(deck: SlideDeck, theme: Theme, width: u32, height: u32) -> Self {
        DeckSession {
            deck,
            theme,
            width,
            height,
            preview_idx: 0,
            live_idx: None,
            live_since: None,
        }
    }

    /// The deck being presented.
    pub fn deck(&self) -> &SlideDeck {
        &self.deck
    }

    /// The number of slides (the `M` in "Slide N / M").
    pub fn len(&self) -> usize {
        self.deck.len()
    }

    /// Whether the deck has no slides.
    pub fn is_empty(&self) -> bool {
        self.deck.is_empty()
    }

    /// The staged (Preview) slide ordinal, or `None` if the deck is empty.
    pub fn preview_index(&self) -> Option<usize> {
        if self.deck.is_empty() {
            None
        } else {
            Some(self.preview_idx.min(self.deck.len() - 1))
        }
    }

    /// The Live slide ordinal, or `None` if nothing is live.
    pub fn live_index(&self) -> Option<usize> {
        self.live_idx
    }

    /// Stage the slide at `index` in **Preview** (clamped into range). The Live output is
    /// untouched. Returns `false` (no-op) if the deck is empty.
    pub fn stage(&mut self, index: usize) -> bool {
        if self.deck.is_empty() {
            return false;
        }
        self.preview_idx = index.min(self.deck.len() - 1);
        true
    }

    /// Advance the **Preview** cursor to the next slide (also "Next"). Returns `false` at the
    /// end of the deck. Live is untouched.
    // `next` is the operator's domain verb ("Next slide"); it is not an iterator (it returns a
    // moved/not-moved bool, takes no item), so the Iterator::next resemblance is a false positive.
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> bool {
        let Some(cur) = self.preview_index() else {
            return false;
        };
        if cur + 1 < self.deck.len() {
            self.preview_idx = cur + 1;
            true
        } else {
            false
        }
    }

    /// Move the **Preview** cursor to the previous slide. Returns `false` at the start. Live is
    /// untouched.
    pub fn previous(&mut self) -> bool {
        let Some(cur) = self.preview_index() else {
            return false;
        };
        if cur > 0 {
            self.preview_idx = cur - 1;
            true
        } else {
            false
        }
    }

    /// **Go Live** (`Enter`): push the staged Preview slide to Live. Restarts the auto-advance
    /// dwell. Returns `false` (no-op) if the deck is empty.
    pub fn go_live(&mut self) -> bool {
        let Some(idx) = self.preview_index() else {
            return false;
        };
        self.live_idx = Some(idx);
        self.live_since = None; // the next tick (re)starts the dwell for the new live slide
        true
    }

    /// Switch the audience theme, re-composing from the retained slides (content ⟂ theme, zero
    /// content loss). The staged/live cursors are unchanged.
    pub fn set_theme(&mut self, theme: Theme) {
        self.theme = theme;
    }

    /// The composed Preview frame (the staged slide over the theme), or `None` if the deck is
    /// empty.
    pub fn preview_frame(&self) -> Option<Frame> {
        let idx = self.preview_index()?;
        self.deck
            .get_index(idx)
            .map(|s| compose_authored_slide(s, &self.theme, self.width, self.height))
    }

    /// The composed Live frame (the live slide over the theme), or `None` if nothing is live.
    pub fn live_frame(&self) -> Option<Frame> {
        let idx = self.live_idx?;
        self.deck
            .get_index(idx)
            .map(|s| compose_authored_slide(s, &self.theme, self.width, self.height))
    }

    /// Drive **auto-advance** from an injected clock. Returns `true` iff the Live slide advanced
    /// this tick. A live slide with no `auto_advance_secs` never advances; the last slide stops
    /// (no wrap). Deterministic in `now` (monotonic; a backwards `now` yields a zero elapsed via
    /// saturating subtraction, never a panic).
    pub fn tick(&mut self, now: Instant) -> bool {
        let Some(live) = self.live_idx else {
            return false;
        };
        let Some(slide) = self.deck.get_index(live) else {
            self.live_idx = None;
            return false;
        };
        let Some(secs) = slide.auto_advance_secs else {
            self.live_since = None; // "Off" → hold indefinitely
            return false;
        };
        match self.live_since {
            None => {
                // First tick after the slide went live: start the dwell.
                self.live_since = Some(now);
                false
            }
            Some(since) => {
                if now.saturating_duration_since(since) >= Duration::from_secs(secs as u64) {
                    if live + 1 < self.deck.len() {
                        self.live_idx = Some(live + 1);
                        self.live_since = Some(now);
                        true
                    } else {
                        false // last slide: stop auto-advancing
                    }
                } else {
                    false
                }
            }
        }
    }
}
