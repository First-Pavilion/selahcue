//! The Preview→Live loop (FR-012/013/046).
//!
//! Two independent engine outputs: **Preview** (the operator's staging surface,
//! an offscreen readback per FR-013) and **Live** (the audience/program output).
//! The central invariant: **staging never changes Live — only [`go_live`] does**
//! (FR-012). Live changes are made by explicit forward actions (go-live, clear,
//! blackout), never by editing.
//!
//! [`go_live`]: Presenter::go_live

use crate::compose::{compose_live, compose_slide};
use crate::slide::{Slide, Theme};
use crate::stage::{compose_identify, TimerView};
use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent};
use selahcue_engine::raster::{FrameBuffer, MAX_DIMENSION};
use selahcue_engine::scene::Rgba;

/// Identify-overlay colours for the main output (FR-040).
const IDENTIFY_BG: Rgba = Rgba::rgb(20, 60, 140);
const IDENTIFY_MARKER: Rgba = Rgba::WHITE;

/// The *displayed* value of a timer view (whole-second granularity + state), so the Live
/// output recomposes only when what the audience sees actually changes — not every frame
/// (the raw `progress` fraction moves continuously). `elapsed_secs` is ignored once timed
/// up, since the label is then the fixed "TIME UP" — so overrun sits truly idle instead of
/// re-rasterizing an identical frame every second.
fn timer_display_key(view: Option<&TimerView>) -> Option<(Option<u32>, u32, bool, bool)> {
    view.map(|v| {
        let elapsed = if v.time_up { 0 } else { v.elapsed_secs };
        (v.remaining_secs, elapsed, v.time_up, v.warn)
    })
}

/// Drives the preview and live outputs for basic slide presentation.
pub struct Presenter {
    width: u32,
    height: u32,
    theme: Theme,
    preview: Engine,
    live: Engine,
    staged: Option<Slide>,
    live_slide: Option<Slide>,
    /// Tracked so a per-frame timer recompose (`SetScene`) preserves an operator-set
    /// blackout — the engine stores blackout on the scene, and `SetScene` replaces it.
    live_blackout: bool,
    /// The timer view currently overlaid on Live (`None` when no timer is active).
    live_timer: Option<TimerView>,
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
            live_blackout: false,
            live_timer: None,
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

    /// **Go Live** (`Enter`): push the staged preview slide to the Live output (with the
    /// active timer overlay, if any). Returns `false` (no-op) if nothing is staged.
    /// Going live reveals the content (clears an operator blackout, per UX-STATE-MATRIX).
    pub fn go_live(&mut self) -> bool {
        let Some(slide) = self.staged.clone() else {
            return false;
        };
        let frame = compose_live(
            Some(&slide),
            &self.theme,
            self.width,
            self.height,
            self.live_timer.as_ref(),
        );
        // Report success (and record the live slide) only if the frame actually
        // reached the output — never claim "live" for a rejected frame.
        if matches!(
            self.live.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            return false;
        }
        self.live_slide = Some(slide);
        self.live_blackout = false;
        true
    }

    /// **Clear** (`Esc Esc`): clear all Live layers to empty. Preview is untouched. A
    /// running timer's overlay re-appears on the next `show_timer` tick.
    pub fn clear_live(&mut self) {
        self.live.apply(EngineCommand::Clear);
        self.live_slide = None;
        self.live_blackout = false;
        self.live_timer = None;
    }

    /// **Blackout** (`B`): toggle the audience output to black. Un-blackout restores
    /// the prior live content (the slide is retained, only hidden).
    pub fn blackout(&mut self, on: bool) {
        self.live_blackout = on;
        self.live.apply(EngineCommand::Blackout { on });
    }

    /// Overlay (or clear) the active-timer bar on the Live output. Recomposes only when
    /// the *displayed* value changes (whole-second / state), so a per-frame tick is cheap;
    /// the recompose preserves the current blackout state.
    pub fn show_timer(&mut self, view: Option<TimerView>) {
        if timer_display_key(view.as_ref()) == timer_display_key(self.live_timer.as_ref()) {
            return;
        }
        self.live_timer = view;
        self.recompose_live();
    }

    /// Recompose the Live scene from the tracked slide + timer, preserving blackout.
    fn recompose_live(&mut self) {
        if self.live_slide.is_none() && self.live_timer.is_none() {
            self.live.apply(EngineCommand::Clear);
            return;
        }
        let mut frame = compose_live(
            self.live_slide.as_ref(),
            &self.theme,
            self.width,
            self.height,
            self.live_timer.as_ref(),
        );
        frame.blackout = self.live_blackout;
        self.live.apply(EngineCommand::SetScene { frame });
    }

    /// Whether the audience output is currently blacked out.
    pub fn is_blackout(&self) -> bool {
        self.live_blackout
    }

    /// Overlay the display-identify number on the Live output (FR-040). This
    /// replaces the live content; the operator re-stages/go-lives to resume.
    pub fn identify(&mut self, number: u32) {
        let frame = compose_identify(number, IDENTIFY_BG, IDENTIFY_MARKER, self.width, self.height);
        self.live.apply(EngineCommand::SetScene { frame });
        self.live_slide = None;
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
