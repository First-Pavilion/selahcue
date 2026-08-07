//! The Preview→Live loop (FR-012/013/046).
//!
//! Two independent engine outputs: **Preview** (the operator's staging surface,
//! an offscreen readback per FR-013) and **Live** (the audience/program output).
//! The central invariant: **staging never changes Live — only [`go_live`] does**
//! (FR-012). Live changes are made by explicit forward actions (go-live, clear,
//! blackout), never by editing.
//!
//! [`go_live`]: Presenter::go_live

use crate::compose::{compose_authored_slide, compose_slide_masked, LayerMask};
use crate::deck::AuthoredSlide;
use crate::slide::Slide;
use crate::stage::compose_identify;
use crate::theme::Theme;
use selahcue_engine::engine::{Engine, EngineCommand, EngineEvent};
use selahcue_engine::raster::{self, FrameBuffer, MAX_DIMENSION};
use selahcue_engine::scene::{Frame, Rgba};

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
    /// The authored deck slide currently on the Live surface (Design 2.0, node 329:124), if any.
    /// Mutually exclusive with `live_slide`: `present_authored` sets this and clears `live_slide`;
    /// a plan/scripture `go_live` clears this. Retained so secondary screens / NDI can MIRROR the
    /// authored slide (see [`compose_screen_live`](Self::compose_screen_live)) instead of idle black.
    live_authored: Option<AuthoredSlide>,
    /// The `main` audience SCREEN's per-screen theme (86ajq321k). `None` = follow the
    /// per-item override / global. When set, it is the strongest signal for the physical
    /// `main` output: the effective theme is `main_screen_theme ?? item_theme ?? global`,
    /// so a global theme switch never overrides an explicitly per-screen-themed main and
    /// a `None` value leaves the S8-3d behaviour byte-identical. Secondary audience
    /// screens are composed on-demand (see [`Presenter::compose_screen_live`]).
    main_screen_theme: Option<Theme>,
    /// The `main` audience screen's per-output VISIBLE-LAYERS mask (Design 2.0). `ALL` by
    /// default, so the main output is byte-identical to the pre-mask behaviour. When a layer
    /// is hidden here, both the Preview and the Live main surfaces recompose without that
    /// category (hiding a layer never blanks the frame — NFR-024). Secondary audience screens
    /// carry their own mask, passed per call to [`Presenter::compose_screen_live`].
    main_layer_mask: LayerMask,
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
            live_authored: None,
            main_screen_theme: None,
            main_layer_mask: LayerMask::ALL,
        }
    }

    /// The effective theme for the physical `main` audience surface rendering content
    /// whose per-item override is `item_theme`: **per-screen (`main`) ?? per-item ?? global**
    /// (86ajq321k). With no per-screen theme this is exactly `item_theme ?? global` — the
    /// pre-per-screen behaviour, so the main output is unchanged by default.
    fn effective<'a>(&'a self, item_theme: Option<&'a Theme>) -> &'a Theme {
        self.main_screen_theme
            .as_ref()
            .or(item_theme)
            .unwrap_or(&self.theme)
    }

    /// Stage a slide in **Preview** with the global theme (also serves "Next").
    /// The Live output is untouched (FR-012).
    pub fn stage(&mut self, slide: Slide) {
        self.stage_themed(slide, None);
    }

    /// Stage a slide in **Preview** with an optional per-item theme override (S8-3d) —
    /// `None` uses the global theme. The Live output is untouched (FR-012).
    pub fn stage_themed(&mut self, slide: Slide, theme_override: Option<Theme>) {
        let frame = compose_slide_masked(
            &slide,
            self.effective(theme_override.as_ref()),
            self.width,
            self.height,
            self.main_layer_mask,
        );
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
        let frame = compose_slide_masked(
            &slide,
            self.effective(self.staged_theme.as_ref()),
            self.width,
            self.height,
            self.main_layer_mask,
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
        self.live_theme = self.staged_theme.clone();
        self.live_authored = None;
        true
    }

    /// **Present an authored deck slide** (Design 2.0, node 329:124) DIRECTLY on the Live
    /// audience output — its own z-ordered [`Element`](crate::theme::Element)s over its own
    /// [`Background`](crate::theme::Background), composed with the SAME compositor as the
    /// audience output, so the physical output is byte-identical to the operator's canvas
    /// preview ([`compose_authored_slide`]). `theme` supplies only the fallback background /
    /// default styling (the slide's own background overrides it).
    ///
    /// Unlike [`go_live`](Self::go_live) this bypasses the staged title+body [`Slide`] model:
    /// it **takes over** the Live surface (like [`identify`](Self::identify)), so `live_slide`
    /// / `live_theme` are cleared and a later plan/scripture [`go_live`](Self::go_live) cleanly
    /// replaces it. Returns `false` (Live unchanged) if the engine rejected the composed frame
    /// — never claiming live for a rejected frame. The composed frame is not blacked out, so a
    /// present reveals from blackout exactly as go-live does; blackout/clear stay orthogonal.
    ///
    /// Secondary audience screens / NDI ([`compose_screen_live`](Self::compose_screen_live))
    /// mirror only the title+body live slide, so while an authored slide is presented they show
    /// the idle black frame — deck mirroring to secondaries is a documented follow-up.
    pub fn present_authored(&mut self, slide: &AuthoredSlide, theme: &Theme) -> bool {
        let frame = compose_authored_slide(slide, theme, self.width, self.height);
        if matches!(
            self.live.apply(EngineCommand::SetScene { frame }),
            EngineEvent::Rejected { .. }
        ) {
            return false;
        }
        self.live_slide = None;
        self.live_theme = None;
        self.live_authored = Some(slide.clone());
        true
    }

    /// The id of the authored deck slide currently on Live, if an authored slide is presented
    /// (rather than plan/scripture content). Host-truth for the operator grid's LIVE ring.
    pub fn authored_live_id(&self) -> Option<u64> {
        self.live_authored.as_ref().map(|s| s.id.0)
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
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.staged_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.preview.apply(EngineCommand::SetScene { frame });
        }
        if let Some(slide) = self.live_slide.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.live_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// Set the `main` audience screen's per-screen theme (86ajq321k) and recompose
    /// Preview + Live from the retained slides — content unchanged (zero content loss).
    /// `None` clears it (main falls back to the per-item override / global). Blackout is
    /// orthogonal; the caller re-applies it (as with [`set_theme`]).
    pub fn set_main_screen_theme(&mut self, theme: Option<Theme>) {
        self.main_screen_theme = theme;
        if let Some(slide) = self.staged.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.staged_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.preview.apply(EngineCommand::SetScene { frame });
        }
        if let Some(slide) = self.live_slide.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.live_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// The `main` audience screen's per-screen theme, if one is set.
    pub fn main_screen_theme(&self) -> Option<Theme> {
        self.main_screen_theme.clone()
    }

    /// Set the `main` audience screen's per-output VISIBLE-LAYERS mask (Design 2.0) and
    /// recompose Preview + Live from the retained slides — content unchanged, only which layer
    /// categories render (hiding a layer never blanks the frame — NFR-024). `ALL` restores the
    /// full composition. Blackout is orthogonal; the caller re-applies it (as with
    /// [`set_main_screen_theme`]).
    pub fn set_main_layer_mask(&mut self, mask: LayerMask) {
        self.main_layer_mask = mask;
        if let Some(slide) = self.staged.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.staged_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.preview.apply(EngineCommand::SetScene { frame });
        }
        if let Some(slide) = self.live_slide.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.live_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// The `main` audience screen's current per-output layer mask.
    pub fn main_layer_mask(&self) -> LayerMask {
        self.main_layer_mask
    }

    /// Compose the current LIVE content for a SECONDARY audience screen (lower-third /
    /// stream) with its own per-screen theme, on-demand and WITHOUT a persistent engine
    /// (86ajq321k). Effective theme = **`screen_theme` ?? the live item override ?? global**
    /// — the same precedence the physical `main` surface uses, minus main's own per-screen
    /// theme (each screen renders its own design). A blank live surface yields a safe
    /// black frame (matching the main output when idle). Pure: content ⟂ theme, so calling
    /// it for N screens renders the SAME live item under N different themes at once. An authored
    /// deck slide (Design 2.0) mirrors here too, rendered from its own background/elements — the
    /// per-screen theme is only the fallback background and the layer mask does not apply.
    pub fn compose_screen_live(
        &self,
        screen_theme: Option<&Theme>,
        mask: LayerMask,
    ) -> FrameBuffer {
        // An authored deck slide takes over Live and mirrors to EVERY screen (Design 2.0). Its own
        // background overrides the theme; `screen_theme`/global is only the fallback. Layer masks do
        // not apply — an authored slide's elements ARE the content, not theme-layer categories.
        if let Some(slide) = self.live_authored.as_ref() {
            let theme = screen_theme.or(self.live_theme.as_ref()).unwrap_or(&self.theme);
            return raster::render(&compose_authored_slide(slide, theme, self.width, self.height));
        }
        let Some(slide) = self.live_slide.as_ref() else {
            return raster::render(&Frame::new(self.width, self.height));
        };
        let theme = screen_theme
            .or(self.live_theme.as_ref())
            .unwrap_or(&self.theme);
        raster::render(&compose_slide_masked(
            slide,
            theme,
            self.width,
            self.height,
            mask,
        ))
    }

    /// The active global audience theme.
    pub fn theme(&self) -> Theme {
        self.theme.clone()
    }

    /// Change the LIVE surface's per-item theme override in place and recompose it from
    /// the retained live slide (S8-3d — the operator edits the live item's theme). No-op
    /// when nothing is live. Content unchanged (zero content loss).
    pub fn set_live_theme(&mut self, theme_override: Option<Theme>) {
        self.live_theme = theme_override;
        if let Some(slide) = self.live_slide.clone() {
            let frame = compose_slide_masked(
                &slide,
                self.effective(self.live_theme.as_ref()),
                self.width,
                self.height,
                self.main_layer_mask,
            );
            self.live.apply(EngineCommand::SetScene { frame });
        }
    }

    /// **Clear** (`Esc Esc`): clear all Live layers to empty. Preview is untouched.
    pub fn clear_live(&mut self) {
        self.live.apply(EngineCommand::Clear);
        self.live_slide = None;
        self.live_theme = None;
        self.live_authored = None;
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
        self.live_authored = None;
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
