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
pub mod slide;
pub mod stage;

pub use compose::compose_slide;
pub use present::Presenter;
pub use slide::{Slide, Theme};
pub use stage::{compose_identify, compose_stage, StageDisplay, StageTheme, TimerView};

/// Re-exported so consumers can name the output pixel buffer without depending on
/// `selahcue-engine` directly.
pub use selahcue_engine::raster::FrameBuffer;
