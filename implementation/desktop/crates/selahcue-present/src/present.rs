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
use crate::slide::Slide;
use crate::stage::compose_identify;
use crate::theme::Theme;
use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent};
use selahcue_engine::raster::{FrameBuffer, MAX_DIMENSION};
use selahcue_engine::scene::Rgba;

/// Identify-overlay colours for the main output (FR-040).
const IDENTIFY_BG: Rgba = Rgba::rgb(20, 60, 140);
const IDENTIFY_MARKER: Rgba = Rgba::WHITE;

/// Drives the preview and live outputs for basic slide presentation.
pub struct Presenter {
    width: u32,
    height: u32,
    theme: Theme,
    preview: Engine,
    live: Engine,
    staged: Option<Slide>,
    live_slide: Option<Slide>,
    /// Per-item theme override for the staged/live surface (S8-3d). `None` = use the
    /// global `theme`. Preview and Live can carry DIFFERENT overrides at once (two plan
    /// items with different templates), so a global theme switch recomposes each surface
    /// with its own effective theme and never clobbers an overridden one.
    staged_theme: Option<Theme>,
    live_theme: Option<Theme>,
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
            staged_theme: None,
            live_theme: None,
        }
    }

    /// Stage a slide in **Preview** with the global theme (also serves "Next").
    /// The Live output is untouched (FR-012).
    pub fn stage(&mut self, slide: Slide) {
        self.stage_themed(slide, None);
    }

    /// Stage a slide in **Preview** with an optional per-item theme override (S8-3d) —
    /// `None` uses the global theme. The Live output is untouched (FR-012).
    pub fn stage_themed(&mut self, slide: Slide, theme_override: Option<Theme>) {
        let theme = theme_override.as_ref().unwrap_or(&self.theme);
        let frame = compose_slide(&slide, theme, self.width, self.height);
        // Only track the slide if the engine actually rendered it (defensive — the
        // clamped dimensions make rejection unreachable in normal use).
        if !matches!(
            self.preview.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            self.staged = Some(slide);
            self.staged_theme = theme_override;
        }
    }

    /// **Go Live** (`Enter`): push the staged preview slide to the Live output, carrying
    /// its per-item theme override with it. Returns `false` (no-op) if nothing is staged.
    pub fn go_live(&mut self) -> bool {
        let Some(slide) = self.staged.clone() else {
            return false;
        };
        let theme = self.staged_theme.as_ref().unwrap_or(&self.theme);
        let frame = compose_slide(&slide, theme, self.width, self.height);
        // Report success (and record the live slide) only if the frame actually
        // reached the output — never claim "live" for a rejected frame.
        if matches!(
            self.live.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            return false;
        }
        self.live_slide = Some(slide);
        self.live_theme = self.staged_theme;
        true
    }

    /// Switch the **global** audience theme, re-composing **both** surfaces from the
    /// retained slides — the *content* is unchanged, only its styling (FR-010, zero
    /// content loss). Each surface keeps its own per-item override: a surface with an
    /// override recomposes with THAT theme (a global switch never clobbers an overridden
    /// item); an un-overridden surface follows the new global theme. A blank slot stays
    /// blank. The caller re-applies blackout (theme ⟂ blackout).
    pub fn set_theme(&mut self, theme: Theme) {
        self.theme = theme;
        if let Some(slide) = self.staged.clone() {
            let t = self.staged_theme.as_ref().unwrap_or(&self.theme);
            let frame = compose_slide(&slide, t, self.width, self.height);
            self.preview.apply(EngineCommand::SetScene { frame });
        }
        if let Some(slide) = self.live_slide.clone() {
            let t = self.live_theme.as_ref().unwrap_or(&self.theme);
            let frame = compose_slide(&slide, t, self.width, self.height);
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// The active global audience theme.
    pub fn theme(&self) -> Theme {
        self.theme
    }

    /// Change the LIVE surface's per-item theme override in place and recompose it from
    /// the retained live slide (S8-3d — the operator edits the live item's theme). No-op
    /// when nothing is live. Content unchanged (zero content loss).
    pub fn set_live_theme(&mut self, theme_override: Option<Theme>) {
        self.live_theme = theme_override;
        if let Some(slide) = self.live_slide.clone() {
            let t = self.live_theme.as_ref().unwrap_or(&self.theme);
            let frame = compose_slide(&slide, t, self.width, self.height);
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// **Clear** (`Esc Esc`): clear all Live layers to empty. Preview is untouched.
    pub fn clear_live(&mut self) {
        self.live.apply(EngineCommand::Clear);
        self.live_slide = None;
        self.live_theme = None;
    }

    /// Clear the Preview/staged slot (e.g. session restore establishing "nothing is
    /// staged" — go-live never clears it, so restores need an explicit reset).
    pub fn clear_preview(&mut self) {
        self.preview.apply(EngineCommand::Clear);
        self.staged = None;
        self.staged_theme = None;
    }

    /// **Blackout** (`B`): toggle the audience output to black. Un-blackout restores
    /// the prior live content (the slide is retained, only hidden).
    pub fn blackout(&mut self, on: bool) {
        self.live.apply(EngineCommand::Blackout { on });
    }

    /// Overlay the display-identify number on the Live output (FR-040). This
    /// replaces the live content; the operator re-stages/go-lives to resume.
    pub fn identify(&mut self, number: u32) {
        let frame = compose_identify(
            number,
            IDENTIFY_BG,
            IDENTIFY_MARKER,
            self.width,
            self.height,
        );
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
