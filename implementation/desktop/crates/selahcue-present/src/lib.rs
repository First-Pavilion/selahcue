//! SelahCue presentation rendering (FR-009/012/013/036/046).
//!
//! The core live loop, built on the [`selahcue_engine`] test seam so it is
//! verifiable headlessly:
//! - [`slide`] — the static slide model and audience [`Theme`].
//! - [`compose`] — compose a slide into an engine frame.
//! - [`present`] — the [`Presenter`]: the Preview→Live loop whose central
//!   invariant is that staging never changes Live until Go Live.

#![forbid(unsafe_code)]

pub mod compose;
pub mod present;
pub mod slide;

pub use compose::compose_slide;
pub use present::Presenter;
pub use slide::{Slide, Theme};
