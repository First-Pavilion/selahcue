//! SelahCue presentation rendering (FR-009/012/013/036/037/040/046).
//!
//! The core live loop and output composition, built on the [`selahcue_engine`] test
//! seam so it is verifiable headlessly:
//! - [`slide`] — the static slide model and audience [`Theme`].
//! - [`compose`] — compose a slide into an engine frame.
//! - [`present`] — the [`Presenter`]: the Preview→Live loop whose central invariant
//!   is that staging never changes Live until Go Live.
//! - [`stage`] — the stage/confidence monitor (a second independent output) and the
//!   display-identify overlay.

#![forbid(unsafe_code)]

pub mod compose;
pub mod deck;
pub mod health;
pub mod measure;
pub mod present;
pub mod qr;
pub mod slide;
pub mod stage;
pub mod theme;
pub mod tokens;
pub mod trash;

pub use compose::{compose_authored_slide, compose_slide, compose_slide_masked, LayerMask};
pub use deck::{
    crossfade, media_usage, AuthoredSlide, DeckId, DeckSession, SlideDeck, SlideId, Transition,
    UsageReport, MAX_DECK_SLIDES, MAX_NOTES_LEN,
};
pub use health::{fault_tag, OutputHealth};
pub use present::Presenter;
pub use qr::{compose_qr, qr_modules};
pub use slide::Slide;
pub use stage::{
    compose_identify, compose_stage, StageContext, StageDisplay, StageTheme, TimerView, WallClock,
};
pub use theme::{
    Background, Band, Element, Fit, GradientBackground, ImageBackground, RegionStyle, Theme,
    VAlign, MAX_ELEMENTS, MAX_TEXT_ELEMENT_LEN,
};
pub use tokens::{contrast_ratio, SemanticToken, LIVE, NEUTRAL, PREVIEW, WARN};
pub use trash::{DeckTrash, MAX_TRASH_BYTES, MAX_TRASH_ENTRIES};

/// The sniffed still-image format, re-exported for the same reason as the engine types below: a
/// consumer that has to name the format an image turned out to be — the media store, deciding a
/// file extension — should name **this** type rather than declare a parallel one of its own. Two
/// enums with the same variants and no conversion between them agree only by the order they happen
/// to be written in, and the failure mode when they stop agreeing is a file saved under the wrong
/// extension, which nothing detects.
/// Re-exported so a consumer can name a fault kind — reporting one via
/// [`Presenter::inject_fault`](present::Presenter::inject_fault), or rendering the reason an
/// output is held — without depending on `selahcue-engine` directly.
pub use selahcue_engine::fault::Fault;
pub use selahcue_engine::media::ImageFormat;
/// Re-exported so consumers can name the output pixel buffer (and its pixel colour)
/// without depending on `selahcue-engine` directly.
pub use selahcue_engine::raster::{system_font_families, FrameBuffer};
pub use selahcue_engine::scene::{
    FontName, GradientDirection, ImageFit, MediaRef, Rgba, ShapeKind, TextAlign, TextStyle,
};

/// Render a canonical **sample scripture slide** with `theme` into a `width×height`
/// [`FrameBuffer`] (RGBA8) — a pure function used by the Theme Designer to preview a
/// theme exactly as the audience output would render it (same compose + rasterizer).
/// A consumer (e.g. the operator webview) can base64-encode the bytes and draw them.
pub fn render_sample(theme: &Theme, width: u32, height: u32) -> FrameBuffer {
    let slide = Slide::new(
        "John 3:16 (KJV)",
        [
            "For God so loved the world, that he gave",
            "his only begotten Son, that whosoever",
            "believeth in him should not perish.",
        ],
    );
    selahcue_engine::raster::render(&compose_slide(&slide, theme, width, height))
}

/// Compose an authored deck slide (Design 2.0, node 329:124) with `theme` and rasterise it to a
/// `width×height` [`FrameBuffer`] (RGBA8) — the operator console's slide-canvas preview. Same
/// native compositor as the audience output (never blank), so the webview draws real pixels
/// rather than laying the slide out itself (ADR-0002/0003). A thin wrapper over
/// [`compose_authored_slide`] + the deterministic rasteriser.
pub fn render_authored_slide(
    slide: &deck::AuthoredSlide,
    theme: &Theme,
    width: u32,
    height: u32,
) -> FrameBuffer {
    selahcue_engine::raster::render(&compose_authored_slide(slide, theme, width, height))
}
