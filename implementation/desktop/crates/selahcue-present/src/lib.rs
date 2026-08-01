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
pub mod present;
pub mod qr;
pub mod slide;
pub mod stage;
pub mod theme;
pub mod tokens;

pub use compose::compose_slide;
pub use present::Presenter;
pub use qr::{compose_qr, qr_modules};
pub use slide::Slide;
pub use stage::{compose_identify, compose_stage, StageDisplay, StageTheme, TimerView};
pub use theme::{
    Background, Band, Element, Fit, GradientBackground, ImageBackground, RegionStyle, Theme,
    VAlign, MAX_ELEMENTS, MAX_TEXT_ELEMENT_LEN,
};
pub use tokens::{contrast_ratio, SemanticToken, LIVE, NEUTRAL, PREVIEW, WARN};

/// Re-exported so consumers can name the output pixel buffer (and its pixel colour)
/// without depending on `selahcue-engine` directly.
pub use selahcue_engine::raster::{system_font_families, FrameBuffer};
pub use selahcue_engine::scene::{
    FontName, GradientDirection, MediaRef, Rgba, ShapeKind, TextAlign, TextStyle,
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
