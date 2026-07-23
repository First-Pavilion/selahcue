//! The Preview→Live loop (FR-012/013/046).
//!
//! Two independent engine outputs: **Preview** (the operator's staging surface,
//! an offscreen readback per FR-013) and **Live** (the audience/program output).
//! The central invariant: **staging never changes Live — only [`go_live`] does**
//! (FR-012). Live changes are made by explicit forward actions (go-live, clear,
//! blackout), never by editing.
//!
//! [`go_live`]: Presenter::go_live

use crate::compose::compose_slide;
use crate::slide::{Slide, Theme};
use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent};
use selahcue_engine::raster::{FrameBuffer, MAX_DIMENSION};

/// Drives the preview and live outputs for basic slide presentation.
pub struct Presenter {
    width: u32,
    height: u32,
    theme: Theme,
    preview: Engine,
    live: Engine,
    staged: Option<Slide>,
    live_slide: Option<Slide>,
}

impl Presenter {
    /// A presenter for the given output resolution and theme. Both surfaces start
    /// blank (safe black).
    ///
    /// Dimensions are clamped into the engine's renderable range (matching
    /// [`Engine::new`]) and the clamped values are used for composition, so a
    /// composed frame is always accepted — the tracked staged/live slide can never
    /// claim content the engine actually rejected.
    pub fn new(width: u32, height: u32, theme: Theme) -> Self {
        let width = width.clamp(1, MAX_DIMENSION);
        let height = height.clamp(1, MAX_DIMENSION);
        Presenter {
            width,
            height,
            theme,
            preview: Engine::new(width, height),
            live: Engine::new(width, height),
            staged: None,
            live_slide: None,
        }
    }

    /// Stage a slide in **Preview** (also serves "Next" — advancing what is queued).
    /// The Live output is untouched (FR-012).
    pub fn stage(&mut self, slide: Slide) {
        let frame = compose_slide(&slide, &self.theme, self.width, self.height);
        // Only track the slide if the engine actually rendered it (defensive — the
        // clamped dimensions make rejection unreachable in normal use).
        if !matches!(
            self.preview.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            self.staged = Some(slide);
        }
    }

    /// **Go Live** (`Enter`): push the staged preview slide to the Live output.
    /// Returns `false` (no-op) if nothing is staged.
    pub fn go_live(&mut self) -> bool {
        let Some(slide) = self.staged.clone() else {
            return false;
        };
        let frame = compose_slide(&slide, &self.theme, self.width, self.height);
        // Report success (and record the live slide) only if the frame actually
        // reached the output — never claim "live" for a rejected frame.
        if matches!(
            self.live.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            return false;
        }
        self.live_slide = Some(slide);
        true
    }

    /// **Clear** (`Esc Esc`): clear all Live layers to empty. Preview is untouched.
    pub fn clear_live(&mut self) {
        self.live.apply(EngineCommand::Clear);
        self.live_slide = None;
    }

    /// **Blackout** (`B`): toggle the audience output to black. Un-blackout restores
    /// the prior live content (the slide is retained, only hidden).
    pub fn blackout(&mut self, on: bool) {
        self.live.apply(EngineCommand::Blackout { on });
    }

    /// The Preview readback (offscreen, FR-013).
    pub fn preview_output(&self) -> &FrameBuffer {
        self.preview.output()
    }

    /// The Live/program readback (what the audience sees).
    pub fn live_output(&self) -> &FrameBuffer {
        self.live.output()
    }

    /// The slide currently staged in Preview, if any.
    pub fn staged(&self) -> Option<&Slide> {
        self.staged.as_ref()
    }

    /// The slide currently on the Live output, if any.
    pub fn live_slide(&self) -> Option<&Slide> {
        self.live_slide.as_ref()
    }
}
