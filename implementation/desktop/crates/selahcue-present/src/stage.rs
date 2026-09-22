//! The stage / confidence monitor — a second independent output (FR-037/040).
//!
//! Driven from the same live state as the main output but composing a *different*
//! scene: the current line, the next line, the active timer, and a clock — laid out
//! large and high-contrast for a speaker at a distance. Also composes the
//! display-**identify** overlay (a number on each physical output, FR-040).

use crate::compose::autofit_layers;
use crate::slide::Slide;
use crate::theme::{Fit, VAlign};
use selahcue_core::timer::Timer;
use selahcue_engine::engine::{Engine, EngineCommand};
use selahcue_engine::raster::FrameBuffer;
use selahcue_engine::scene::{FontName, Frame, Layer, Rect, Rgba, ShapeKind, TextAlign, TextStyle};
use std::time::{Duration, Instant};

/// A stage/confidence template (the operator picks one per stage screen). Each lays the
/// same live state out differently and behaves differently at TIME UP (behaviour spec,
/// Figma 375-139). This is the stage analogue of an audience *theme* — a layout template,
/// not a light/dark colour mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum StageTemplate {
    /// Lyric now / next + timer bar. TIME UP tints the **timer bar only**. The default.
    #[default]
    Worship,
    /// Scripture + next + a right-hand countdown panel. TIME UP tints the **panel only**.
    Scripture,
    /// A big centred countdown + nothing else. TIME UP takes over the **whole screen**.
    TimerOnly,
}

impl StageTemplate {
    /// The stable wire/persist tag.
    pub fn as_tag(self) -> &'static str {
        match self {
            StageTemplate::Worship => "worship",
            StageTemplate::Scripture => "scripture",
            StageTemplate::TimerOnly => "timer-only",
        }
    }

    /// Parse a wire tag; unknown → the default (`Worship`), never a panic (untrusted input).
    pub fn from_tag(tag: &str) -> Self {
        match tag {
            "scripture" => StageTemplate::Scripture,
            "timer-only" => StageTemplate::TimerOnly,
            _ => StageTemplate::Worship,
        }
    }
}

/// The longest a stage message may be (bounded — the confidence monitor shows a short
/// production note, not a paragraph; also keeps the wire/state bounded, no-leak).
pub const MAX_STAGE_MESSAGE_LEN: usize = 120;

/// Stage text scale (permille) that reproduces the Design 2.0 sizes exactly.
pub const STAGE_TEXT_SCALE_DEFAULT: u16 = 1000;
/// The smallest stage text scale an operator can select (75 %).
pub const STAGE_TEXT_SCALE_MIN: u16 = 750;
/// The largest stage text scale an operator can select (175 %).
///
/// NFR-020 asks that stage text support a **configurable large size (≥48px-equivalent)**.
/// At the Design 2.0 sizes and a 1920×1080 stage output the smallest chrome role (the
/// scripture status-pill label, Figma 13px) renders at 24.9px-equivalent, so the scale has
/// to reach at least `48 / 24.9 ≈ 1.93`… which the *fixed* chrome positions cannot absorb.
/// 175 % is the largest scale at which every role still sits inside its band, and it lifts
/// every role that carries **words** — the next line, the reference, the screen label, the
/// captions — past 48px-equivalent at 1080. The two sub-48px roles that remain at 175 %
/// are the two chip/pill labels, which are 4–5-character state badges next to a readout
/// that is 170–360px-equivalent.
pub const STAGE_TEXT_SCALE_MAX: u16 = 1750;

// The scale window has to be a real window with the design size inside it — a min or max
// that collapsed onto the default would make every scale test below vacuously green.
const _: () = assert!(STAGE_TEXT_SCALE_MIN < STAGE_TEXT_SCALE_DEFAULT);
const _: () = assert!(STAGE_TEXT_SCALE_DEFAULT < STAGE_TEXT_SCALE_MAX);

/// Colours for the stage monitor (high-contrast; the timer colours signal state).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StageTheme {
    pub background: Rgba,
    pub text: Rgba,
    /// Secondary / label ink (the "NEXT" chip, the timer caption, the next line).
    pub muted: Rgba,
    /// Accent ink (scripture reference + the production-message frame). Gold.
    pub accent: Rgba,
    /// Soft gold tint behind the production-message card (Figma 375-134).
    pub accent_soft: Rgba,
    /// A slightly-raised panel fill (the scripture countdown panel, the message box).
    pub panel: Rgba,
    /// Dim chip / pill fill (the song pill, the NEXT chips).
    pub track: Rgba,
    /// Hairline border on the raised surfaces — the song pill, the worship timer band and
    /// the scripture countdown panel all carry one in Design 2.0 (Figma: `1px #262a34`).
    pub border: Rgba,
    /// Border on a TIME-UP region and on the overrun pill (Figma: `#5a2327`).
    pub alert_border: Rgba,
    /// Timer running with comfortable time remaining.
    pub timer_ok: Rgba,
    /// Soft tint + border of the on-time status pill (Figma 374-141).
    pub ok_soft: Rgba,
    pub ok_border: Rgba,
    /// Timer within the warning threshold.
    pub timer_warn: Rgba,
    /// Soft tint + border of the status pill in the warning state.
    pub warn_soft: Rgba,
    pub warn_border: Rgba,
    /// Timer at/over TIME UP.
    pub timer_alert: Rgba,
    /// A soft red wash for the TIME-UP region (the worship timer band, the scripture panel).
    pub alert_wash: Rgba,
    /// The three stops of the timer-only TIME-UP **vignette** (Figma 374-166): an elliptical
    /// radial ramp from `core` at the centre through `mid` at half-radius to `edge` at the
    /// frame border. Approximated by concentric ellipses — see [`push_alert_vignette`].
    pub alert_vignette_core: Rgba,
    pub alert_vignette_mid: Rgba,
    pub alert_vignette_edge: Rgba,
    /// The live-song indicator on the worship header pill (Figma 373-137).
    pub song_accent: Rgba,
    /// Background of the identify overlay.
    pub identify_bg: Rgba,
    /// Marker colour on the identify overlay.
    pub identify_marker: Rgba,
}

impl StageTheme {
    /// A dark, high-contrast default (green/amber/red timer per the design tokens).
    ///
    /// The status inks, their soft tints and the borders are the **Design 2.0** swatches
    /// (`tokens::design2`), so the same colour means the same thing on the console, the
    /// mobile controller and this monitor. No token *value* lives here — every semantic
    /// ink is a reference into the pinned palette.
    pub fn dark() -> Self {
        use crate::tokens::design2 as d2;
        StageTheme {
            background: Rgba::rgb(6, 8, 14),
            text: Rgba::WHITE,
            muted: Rgba::rgb(0x8a, 0x93, 0xa3),
            accent: d2::GOLD.rgba, // gold #f2b84b
            accent_soft: d2::GOLD_SOFT.rgba,
            panel: Rgba::rgb(0x10, 0x14, 0x1e),
            track: Rgba::rgb(30, 34, 44),
            border: d2::BORDER.rgba,
            alert_border: d2::LIVE_BORDER.rgba,
            // Semantic inks from the Design 2.0 token set (one meaning per colour
            // on every surface): green = on track, amber = warning, red = up.
            timer_ok: d2::PREVIEW.rgba,
            ok_soft: d2::PREVIEW_SOFT.rgba,
            ok_border: d2::PREVIEW_BORDER.rgba,
            timer_warn: d2::WARN.rgba,
            warn_soft: d2::WARN_SOFT.rgba,
            warn_border: d2::WARN_BORDER.rgba,
            timer_alert: d2::LIVE.rgba,
            alert_wash: d2::LIVE_SOFT.rgba,
            alert_vignette_core: Rgba::rgb(0x2a, 0x0e, 0x12),
            alert_vignette_mid: Rgba::rgb(0x19, 0x0c, 0x10),
            alert_vignette_edge: Rgba::rgb(0x08, 0x09, 0x0d),
            song_accent: d2::PRIMARY_HOVER.rgba,
            identify_bg: Rgba::rgb(20, 60, 140),
            identify_marker: Rgba::WHITE,
        }
    }

    /// The **high-contrast** stage palette (NFR-020) — for a platform lit for stage, where
    /// the dark palette's soft tints and hairlines wash out. Everything sits on pure black:
    /// text is pure white (21:1) and every remaining ink is a Design 2.0 status swatch,
    /// which on black is at least as legible as the same ink on the dark palette's own
    /// surfaces. Raised fills collapse to black and the shapes are separated by **white
    /// hairlines** instead of tint, so nothing depends on distinguishing two near-blacks.
    ///
    /// Additive on purpose: [`dark`](Self::dark) is cross-checked by
    /// `test_tokens.rs`, so a second constructor carries no blast radius.
    pub fn high_contrast() -> Self {
        use crate::tokens::design2 as d2;
        let black = Rgba::BLACK;
        StageTheme {
            background: black,
            text: Rgba::WHITE,
            // Secondary ink, not a dim one: `text-secondary` on black is ~9.7:1 (AAA),
            // where the dark palette's `muted` on its own background is 6.5:1.
            muted: d2::TEXT_SECONDARY.rgba,
            accent: d2::GOLD.rgba,
            accent_soft: black,
            panel: black,
            track: black,
            border: Rgba::WHITE,
            alert_border: Rgba::WHITE,
            timer_ok: d2::PREVIEW.rgba,
            ok_soft: black,
            ok_border: d2::PREVIEW.rgba,
            timer_warn: d2::WARN.rgba,
            warn_soft: black,
            warn_border: d2::WARN.rgba,
            timer_alert: d2::LIVE.rgba,
            alert_wash: black,
            alert_vignette_core: black,
            alert_vignette_mid: black,
            alert_vignette_edge: black,
            song_accent: d2::PRIMARY_HOVER.rgba,
            identify_bg: Rgba::rgb(20, 60, 140),
            identify_marker: Rgba::WHITE,
        }
    }
}

impl Default for StageTheme {
    fn default() -> Self {
        StageTheme::dark()
    }
}

/// A snapshot of a timer for display — decoupled from the clock so composition
/// stays pure and testable.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TimerView {
    pub elapsed_secs: u32,
    /// Seconds remaining (countdown only); `None` for a count-up timer.
    pub remaining_secs: Option<u32>,
    pub time_up: bool,
    /// Within the warning threshold (and not yet up).
    pub warn: bool,
    /// Fraction of the bar to fill, `0.0..=1.0` (1.0 for count-up / no target).
    pub progress: f64,
    /// How far a countdown has run **past** zero, in whole seconds (`0` when it has not) —
    /// the `OVER 0:32` readout both TIME-UP frames carry (Figma 373-182 / 374-172), so the
    /// speaker can tell five seconds over from five minutes over.
    ///
    /// It lives here, on the snapshot the stage is handed every tick, and not on
    /// [`StageContext`]: a value routed into a separate setter is a value nothing on the
    /// live path calls, which is exactly how this readout shipped frozen at `OVER 0:00`.
    /// [`from_timer`](Self::from_timer) fills it from [`Timer::overrun`], so any caller
    /// already building a view gets it for free.
    pub overrun_secs: u32,
}

impl TimerView {
    /// Derive a view from a [`Timer`] at `now`. `total` is the countdown target
    /// (used only for the progress fraction); pass `None` for a count-up timer.
    pub fn from_timer(
        timer: &Timer,
        now: Instant,
        total: Option<Duration>,
        warn_secs: u32,
    ) -> Self {
        let elapsed = timer.elapsed(now);
        let remaining = timer.remaining(now);
        let time_up = timer.is_time_up(now);
        // Ceil the remaining seconds (broadcast convention): the start value shows for the
        // full first second, and 0:00 / TIME UP lands exactly at expiry — rather than the
        // display reading one second ahead and showing "0:00" for the whole final second.
        let remaining_secs = remaining.map(|d| {
            let whole = d.as_secs();
            (if d.subsec_nanos() > 0 {
                whole + 1
            } else {
                whole
            }) as u32
        });
        let warn = !time_up && remaining_secs.is_some_and(|r| r <= warn_secs);
        let progress = match (total, remaining) {
            (Some(t), Some(r)) if t.as_secs_f64() > 0.0 => {
                (r.as_secs_f64() / t.as_secs_f64()).clamp(0.0, 1.0)
            }
            _ => 1.0,
        };
        TimerView {
            elapsed_secs: elapsed.as_secs() as u32,
            remaining_secs,
            time_up,
            warn,
            progress,
            overrun_secs: timer.overrun(now).as_secs() as u32,
        }
    }

    fn color(&self, theme: &StageTheme) -> Rgba {
        if self.time_up {
            theme.timer_alert
        } else if self.warn {
            theme.timer_warn
        } else {
            theme.timer_ok
        }
    }
}

/// Line-height multiplier for the confidence-monitor **chrome** and the lyric band —
/// Inter's `leading-[normal]`, confirmed on Figma 373-143 (a 56px run occupies a 68px
/// line box ⇒ 1.214).
const STAGE_LINE_HEIGHT: f64 = 1.21;
/// Line-height for the scripture verse — the one region the design sets explicitly
/// (Figma 374-135, `leading-[1.24]`).
const VERSE_LINE_HEIGHT: f64 = 1.24;

/// The Design 2.0 stage reference frame. Every Figma value quoted in
/// `docs/design/DESIGN-2.0-PARITY-AUDIT-stage.md` is measured at this size, and 16:9 is
/// within 0.1 % of it (1000/563 = 1.7762, 1920/1080 = 1.7778), so scaling reproduces the
/// design on any real output.
const REF_W: f64 = 1000.0;
const REF_H: f64 = 563.0;

/// The rasterizer's line-box → glyph-size ratio: `line()` is handed a **line-box height**
/// and both the draw path and the measure path derive `font_size = line_h × FONT_TO_LINE`.
/// So a Figma font size `em` is requested by passing a line box of `em / FONT_TO_LINE`.
///
/// This mirrors a **private** constant in `selahcue-engine::raster` (`FONT_TO_LINE`), which
/// cannot be imported. `type_sizes_match_the_design_2_0_reference` re-derives the expected
/// line boxes from this same ratio, so a drift here is caught; a drift in `raster`'s copy
/// would need the engine to export it, which is left as a follow-up.
const FONT_TO_LINE: f64 = 0.72;

/// Frame-relative metrics for one compose: Design 2.0 reference values in, device pixels
/// out. Vertical geometry and **type** scale with the frame height (uniform 16:9 scaling,
/// audit §6.3); horizontal geometry stays a fraction of the width so full-bleed bands stay
/// edge-to-edge at any aspect. Only *type* — line boxes and their tracking — takes the
/// operator's [`StageContext::text_scale_permille`]; positions do not move, so the layout
/// the design specifies is what an operator enlarges the text inside of.
#[derive(Clone, Copy)]
struct Metrics {
    w: f64,
    h: f64,
    scale: f64,
}

impl Metrics {
    fn new(w: u32, h: u32, ctx: &StageContext) -> Self {
        Metrics {
            w: w as f64,
            h: h as f64,
            scale: ctx.clamped_text_scale() as f64 / 1000.0,
        }
    }

    /// The line-box height (px) to pass [`line`] / `max_cell` for a Figma font size `em`.
    fn cell(&self, em: f64) -> u32 {
        ((em / FONT_TO_LINE / REF_H) * self.h * self.scale).max(1.0) as u32
    }

    /// A vertical Figma coordinate (a `y` measured at 563) in device px.
    fn vy(&self, ref_y: f64) -> i32 {
        ((ref_y / REF_H) * self.h) as i32
    }

    /// A vertical Figma extent (a height measured at 563) in device px, never 0.
    fn vh(&self, ref_h: f64) -> u32 {
        (((ref_h / REF_H) * self.h) as u32).max(1)
    }

    /// A horizontal Figma coordinate (an `x` measured at 1000) in device px.
    fn hx(&self, ref_x: f64) -> i32 {
        ((ref_x / REF_W) * self.w) as i32
    }

    /// A horizontal Figma extent (a width measured at 1000) in device px, never 0.
    fn hw(&self, ref_w: f64) -> u32 {
        (((ref_w / REF_W) * self.w) as u32).max(1)
    }

    /// A hairline / corner radius (a Figma stroke width or radius) in device px. Scales
    /// with the frame but **not** with the text scale — a border is not type — and never
    /// rounds away to nothing.
    fn stroke(&self, ref_px: f64) -> u32 {
        (((ref_px / REF_H) * self.h).round() as u32).max(1)
    }

    /// Letter-spacing in device px for a Figma tracking value. Tracking is optical spacing
    /// *between glyphs*, so it scales with the type it belongs to — frame **and** text
    /// scale — or a 175 % run would come out visibly tighter than the design.
    fn track(&self, ref_track: f64) -> i32 {
        ((ref_track / REF_H) * self.h * self.scale).round() as i32
    }
}

/// The Design 2.0 stage measurements, transcribed from
/// `docs/design/DESIGN-2.0-PARITY-AUDIT-stage.md` §6.4 at the 1000×563 reference frame.
///
/// `EM_*` are Figma **font sizes** (passed through [`Metrics::cell`], which converts them
/// to the line boxes `line()` wants); `Y_*` are absolute tops; `X_*`/`W_*` are horizontal
/// positions and widths; `TRACK_*` are letter-spacing values; `R_*` are corner radii and
/// `B_*` stroke widths. Keeping them together — rather than as bare fractions at each call
/// site — is what makes the substitution checkable against the audit table by eye.
mod design {
    // — Worship, Figma 373:133 (running) / 373:159 (TIME UP) —
    pub const EM_SONG_TITLE: f64 = 22.0;
    pub const EM_STANZA: f64 = 20.0;
    pub const EM_WORSHIP_CLOCK: f64 = 30.0;
    /// The lyric's size in the design. Since owner direction made the live band GROW to
    /// fill its region, this is no longer a ceiling — it survives as the reference the NEXT
    /// row's ratio is expressed against (30/56), which is what keeps the row's proportions
    /// the design's at any content length.
    pub const EM_LYRIC_REF: f64 = 56.0;
    pub const EM_NEXT_CHIP: f64 = 16.0;
    pub const EM_NEXT_LINE: f64 = 30.0;
    pub const EM_SERVICE_TIMER: f64 = 20.0;
    pub const EM_TIMER_READOUT: f64 = 52.0;
    pub const EM_WORSHIP_TIME_UP: f64 = 46.0;
    pub const EM_WORSHIP_OVER: f64 = 22.0;
    pub const Y_SONG_PILL: f64 = 28.0;
    pub const Y_WORSHIP_CLOCK: f64 = 30.5;
    pub const Y_LYRIC: f64 = 131.5;
    pub const H_LYRIC: f64 = 212.0;
    pub const Y_NEXT_ROW: f64 = 377.5;
    pub const Y_TIMER_BAND: f64 = 456.0;
    pub const H_TIMER_BAND: f64 = 107.0;
    pub const D_SONG_DOT: f64 = 9.0;
    /// The song pill's height. Reserved whether or not a pill is drawn, so the live band
    /// does not jump size between a song and a title-only item.
    pub const H_SONG_PILL: f64 = 41.0;
    pub const D_TIMER_DOT: f64 = 11.0;

    // — Scripture, Figma 374:128 —
    pub const EM_SCREEN_LABEL: f64 = 20.0;
    pub const EM_SCRIPTURE_CLOCK: f64 = 28.0;
    pub const EM_REFERENCE: f64 = 30.0;
    /// As [`EM_LYRIC_REF`], for the scripture verse column (26/48).
    pub const EM_VERSE_REF: f64 = 48.0;
    pub const EM_SCRIPTURE_NEXT_CHIP: f64 = 15.0;
    pub const EM_SCRIPTURE_NEXT_LINE: f64 = 26.0;
    pub const EM_PILL_LABEL: f64 = 13.0;
    pub const EM_TIME_LEFT: f64 = 15.0;
    pub const EM_BIG_READOUT: f64 = 96.0;
    pub const Y_SCREEN_LABEL: f64 = 33.0;
    pub const Y_SCRIPTURE_CLOCK: f64 = 28.0;
    pub const Y_REFERENCE: f64 = 103.0;
    pub const Y_VERSE: f64 = 159.0;
    pub const H_VERSE: f64 = 300.0;
    pub const Y_SCRIPTURE_NEXT_ROW: f64 = 480.5;
    pub const Y_PANEL: f64 = 80.0;
    pub const X_PANEL: f64 = 680.0;
    pub const X_BODY: f64 = 48.0;
    pub const W_BODY: f64 = 596.0;
    pub const Y_PILL: f64 = 213.0;
    pub const H_PILL: f64 = 28.0;
    pub const Y_TIME_LEFT: f64 = 253.0;
    pub const Y_BIG_READOUT: f64 = 283.0;
    pub const D_PILL_DOT: f64 = 9.0;

    // — Timer-only, Figma 374:151 (running) / 374:166 (TIME UP) —
    pub const EM_TIMER_HEADER: f64 = 20.0;
    pub const EM_TIMER_CLOCK: f64 = 28.0;
    pub const EM_SEGMENT: f64 = 26.0;
    pub const EM_GIANT_READOUT: f64 = 190.0;
    pub const EM_FOOTER: f64 = 30.0;
    pub const EM_TIMER_TIME_UP: f64 = 130.0;
    pub const EM_TIMER_OVER: f64 = 28.0;
    pub const EM_TIME_UP_DATE: f64 = 22.0;
    pub const Y_TIMER_HEADER: f64 = 33.0;
    pub const Y_TIMER_CLOCK: f64 = 28.0;
    pub const Y_SEGMENT: f64 = 163.0;
    pub const Y_GIANT_READOUT: f64 = 200.0;
    pub const Y_FOOTER: f64 = 436.0;
    pub const Y_TIMER_TIME_UP: f64 = 182.5;
    pub const Y_TIMER_OVER: f64 = 359.5;
    pub const H_TIMER_OVER: f64 = 54.0;
    pub const Y_TIME_UP_DATE: f64 = 433.5;

    // — Production message overlay, Figma 375:128 —
    pub const EM_MESSAGE_CHIP: f64 = 18.0;
    pub const EM_MESSAGE_BODY_CAP: f64 = 56.0;
    pub const X_CARD: f64 = 142.0;
    pub const W_CARD: f64 = 716.0;
    pub const Y_CARD: f64 = 278.5;
    pub const H_CARD: f64 = 160.0;
    /// The card's own paddings and internal gap (Figma 375:134: `pt 28 pb 30 px 52`, gap 12).
    pub const PT_CARD: f64 = 28.0;
    pub const PX_CARD: f64 = 52.0;
    pub const GAP_CARD: f64 = 12.0;
    /// The chip row's height (Figma 375:135).
    pub const H_MESSAGE_CHIP: f64 = 22.0;

    // — Shared margins, strokes and radii —
    /// The 4 % header/footer margin both output edges use.
    pub const X_MARGIN: f64 = 40.0;
    /// Hairline border (song pill, timer band, countdown panel, status pill).
    pub const B_HAIRLINE: f64 = 1.0;
    /// The worship TIME-UP band's heavier border.
    pub const B_TIME_UP_BAND: f64 = 2.0;
    /// The timer-only overrun pill's border.
    pub const B_OVER_PILL: f64 = 1.5;
    /// The production-message card's border.
    pub const B_CARD: f64 = 2.0;
    /// The bottom margin the scripture NEXT row sits on (the frame's own 40px margin).
    pub const Y_BOTTOM_MARGIN: f64 = 40.0;
    /// The clear gap kept between an **elastic** content band and the fixed chrome above and
    /// below it, so growth can never collide with the clock, the NEXT row or the timer band.
    pub const BAND_SAFE_GAP: f64 = 12.0;
    /// The NEXT chips' corner radius.
    pub const R_CHIP: f64 = 7.0;
    /// The production-message card's corner radius.
    pub const R_CARD: f64 = 18.0;

    // — Letter-spacing (STG-011). Nine distinct values across the frames. —
    pub const TRACK_1: f64 = 1.0;
    pub const TRACK_1_5: f64 = 1.5;
    pub const TRACK_2: f64 = 2.0;
    pub const TRACK_4: f64 = 4.0;
    pub const TRACK_READOUT: f64 = -2.0;
    pub const TRACK_GIANT_READOUT: f64 = -4.0;
    /// Runs the design sets no tracking on.
    pub const TRACK_NONE: f64 = 0.0;

    // — Font weight (STG-012). The design draws three weights (Bold for labels/readouts,
    // Semi Bold for the wall clock, Medium for the stanza position, both NEXT lines and the
    // timer-only footer), but this crate can only safely REQUEST two: `Family::Name("Inter")`
    // has a bundled face at exactly 400 and 700 (`selahcue-engine/src/raster.rs`'s
    // `INTER_BYTES`/`INTER_BOLD_BYTES`), and asking that family for anything else does not
    // fall back to the nearest bundled weight — it falls OUT of the family entirely, onto
    // whatever the host happens to have installed. Measured directly
    // (`measure_line_width(text, px, Some(Inter), weight)`, same text/px, weight swept
    // 400..=700): 400 and 700 land on the two bundled faces as expected, but 500 and 600 each
    // measure a DIFFERENT width from 400, from 700, and from EACH OTHER — i.e. distinct,
    // host-dependent system faces, not "close enough to Bold" and not "close enough to
    // Regular". So Semi Bold and Medium both collapse to Regular here — not because the
    // difference doesn't matter, but because rendering it safely needs either a bundled
    // Inter Medium/Semi Bold static face or an engine change that keeps weight fallback
    // inside the requested family, and this crate has neither today.
    //
    // Why Regular and not Bold, given 600 (Semi Bold) is numerically CLOSER to 700 than to
    // 400 — a real question, raised in review, answered here so it is a decision and not an
    // accident. Numeric distance between weight VALUES does not track visual distance once
    // the only two achievable outcomes are "looks like Regular" and "looks like Bold": the
    // design puts the wall clock, stanza position and NEXT lines at a LIGHTER weight than the
    // Bold labels/readouts specifically so they read as visually subordinate to them. Mapping
    // those roles to `WEIGHT_BOLD` would render them IDENTICAL to the Bold labels — the exact
    // pre-STG-012 defect (uniform Bold) reintroduced for six roles, not a closer approximation
    // of Semi Bold/Medium. `WEIGHT_REGULAR` overshoots how much lighter, but preserves the
    // qualitative hierarchy the design is using weight for; `WEIGHT_BOLD` would erase it.
    pub const WEIGHT_BOLD: u16 = 700;
    /// Regular — the bundled Inter face used for every chrome role Design 2.0 draws Semi
    /// Bold or Medium (see the module doc above for why those two collapse into this one).
    pub const WEIGHT_REGULAR: u16 = 400;
}

// The premise the elastic bands rest on: the design's own fixed rects leave real space
// between the live band and the chrome below it. If a constant ever closed those gaps, the
// elastic band would silently equal the fixed one and every "it grew" test would go vacuous
// while still passing. `Y_LYRIC`/`H_LYRIC`/`Y_VERSE`/`H_VERSE` are kept for exactly this —
// they record the **two-line case** Figma 373:133 was drawn against, not normative geometry.
const _: () = assert!(design::Y_LYRIC + design::H_LYRIC < design::Y_NEXT_ROW);
const _: () = assert!(design::Y_NEXT_ROW < design::Y_TIMER_BAND);
const _: () = assert!(design::Y_VERSE + design::H_VERSE < design::Y_SCRIPTURE_NEXT_ROW);
const _: () = assert!(design::Y_SCRIPTURE_NEXT_ROW < REF_H - design::Y_BOTTOM_MARGIN);

// STG-012's premise: the two weight constants must actually be different numbers, or
// `chrome_runs_carry_the_designed_font_weight` would assert a distinction between values
// that collapse to the same constant. Also pins them to the two weights proven safe for the
// bundled `Inter` family above (400/700) — changing either away from those reintroduces the
// host-dependent font substitution this batch found and backed out.
const _: () = assert!(design::WEIGHT_BOLD != design::WEIGHT_REGULAR);
const _: () = assert!(design::WEIGHT_BOLD == 700);
const _: () = assert!(design::WEIGHT_REGULAR == 400);

/// Format a whole-second count as `M:SS` for the timer readout.
fn format_clock(secs: u32) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
}

/// The overrun label both TIME-UP frames carry — `OVER 0:32` (Figma 373-182) and
/// `OVER BY 0:32` (Figma 374-172, which pairs it with a `▲`). Without it "TIME UP" alone
/// cannot tell the speaker five seconds over from five minutes over (STG-038 / STG-065).
fn overrun_label(prefix: &str, secs: u32) -> String {
    format!("{prefix} {}", format_clock(secs))
}

/// A wall-clock snapshot for the stage chrome — a pre-formatted date line and 12-hour
/// time-of-day (Figma 374-151: `Sunday · August 3, 2026` / `10:42 AM`). Supplied by the
/// desktop backend so composition stays **clock-free and deterministic** (parity with the
/// injected [`Timer`]): the composer never reads the OS clock, it only lays out strings.
/// Both fields are length-bounded on construction (no-leak — a fixed two-string snapshot,
/// replaced not accumulated).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct WallClock {
    date: String,
    time: String,
}

impl WallClock {
    /// Longest wall-clock field kept — a formatted date/time never approaches this; the cap
    /// only defends the no-leak invariant against a pathological caller.
    pub const MAX_LEN: usize = 48;

    /// A snapshot from a pre-formatted `date` (e.g. `"Sunday · August 3, 2026"`) and 12-hour
    /// `time` (e.g. `"10:42 AM"`). Both are truncated to [`MAX_LEN`](Self::MAX_LEN) chars.
    pub fn new(date: &str, time: &str) -> Self {
        WallClock {
            date: date.chars().take(Self::MAX_LEN).collect(),
            time: time.chars().take(Self::MAX_LEN).collect(),
        }
    }

    /// The formatted date line (weekday · month day, year).
    pub fn date(&self) -> &str {
        &self.date
    }

    /// The formatted 12-hour time-of-day.
    pub fn time(&self) -> &str {
        &self.time
    }
}

/// Extra live context for the confidence-monitor chrome that the current/next [`Slide`]s do
/// not carry — the wall clock and the live song's stanza position (Figma 373-375: the header
/// `10:42 AM` clock, `Verse 2 of 4`). Supplied by the controller/desktop so composition stays
/// deterministic and clock-free; every field is optional and the templates degrade gracefully
/// when a value is unknown. Cheap to clone (a small snapshot, replaced not accumulated).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StageContext {
    /// The local wall clock (date line + 12-hour time). `None` until the backend feeds it.
    pub clock: Option<WallClock>,
    /// The live stanza position as 1-based `(index, total)` → `Verse 2 of 4`. `None` for a
    /// non-song item or a single-slide item.
    pub song_position: Option<(u16, u16)>,
    /// Stage text size, in **permille** of the Design 2.0 reference sizes (1000 = 100 %).
    /// NFR-020 asks for a configurable large size (≥48px-equivalent) for stage-lighting
    /// readability; this is that control. Read through
    /// [`clamped_text_scale`](Self::clamped_text_scale), so any value a caller writes into
    /// this public field still renders inside
    /// [`STAGE_TEXT_SCALE_MIN`]..=[`STAGE_TEXT_SCALE_MAX`] — text can never be scaled to
    /// nothing, or past the point where the fixed chrome positions stop making sense.
    pub text_scale_permille: u16,
}

impl Default for StageContext {
    fn default() -> Self {
        StageContext {
            clock: None,
            song_position: None,
            text_scale_permille: STAGE_TEXT_SCALE_DEFAULT,
        }
    }
}

impl StageContext {
    /// The text scale actually applied by the composer — the public field clamped to
    /// [`STAGE_TEXT_SCALE_MIN`]..=[`STAGE_TEXT_SCALE_MAX`].
    pub fn clamped_text_scale(&self) -> u16 {
        self.text_scale_permille
            .clamp(STAGE_TEXT_SCALE_MIN, STAGE_TEXT_SCALE_MAX)
    }
}

/// Compose the stage/confidence scene from the current live state, laid out by the chosen
/// [`StageTemplate`] and with an optional operator `message` overlaid (Figma 373-375 / spec
/// 375-139). `timer` is the active timer (`None` when none is running); `context` carries the
/// wall clock + stanza position. The confidence monitor shapes its text in the bundled Inter
/// face (deterministic — it is the speaker's view, not the themed audience output).
#[allow(clippy::too_many_arguments)]
pub fn compose_stage(
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    template: StageTemplate,
    message: Option<&str>,
    context: &StageContext,
    theme: &StageTheme,
    width: u32,
    height: u32,
) -> Frame {
    // Clamp to the renderable bound so the per-template geometry (fractions of w/h cast to
    // i32/u32) can't overflow on a pathological size — the composer must never panic. A frame
    // beyond this can't rasterize anyway (the engine rejects it at readback).
    let width = width.min(selahcue_engine::raster::MAX_DIMENSION);
    let height = height.min(selahcue_engine::raster::MAX_DIMENSION);
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if width == 0 || height == 0 {
        return frame;
    }
    match template {
        StageTemplate::Worship => compose_worship(
            &mut frame, current, next, timer, context, theme, width, height,
        ),
        StageTemplate::Scripture => compose_scripture(
            &mut frame, current, next, timer, context, theme, width, height,
        ),
        StageTemplate::TimerOnly => {
            compose_timer_only(&mut frame, current, timer, context, theme, width, height)
        }
    }
    // The production message is a stage-only overlay (never the audience) — it dims the
    // scene behind a gold-framed note so the speaker cannot miss it.
    if let Some(msg) = message {
        let msg = msg.trim();
        if !msg.is_empty() {
            let m = Metrics::new(width, height, context);
            push_message_overlay(&mut frame, msg, theme, &m, width, height);
        }
    }
    frame
}

// --- small drawing helpers (percent geometry; the default font, no theme typography) ---

fn fill(f: &mut Frame, x: i32, y: i32, w: u32, h: u32, color: Rgba) {
    if w == 0 || h == 0 {
        return;
    }
    f.push(Layer::Fill {
        rect: Rect::new(x, y, w, h),
        color,
    });
}

/// The stage/confidence typeface — the bundled **Inter** face (Figma 373-375). Always `Some`
/// (a valid, bundled family name); it resolves deterministically in the named-font shaper.
fn stage_font() -> Option<FontName> {
    FontName::new(selahcue_engine::raster::STAGE_FONT)
}

/// A single line of stage CHROME — labels, the timer readout, the scripture reference, the
/// message chip. `weight` is a CSS-style numeric weight (STG-012): the design uses three —
/// **Bold** (700) for labels/readouts, **Semi Bold** (600) for the wall clock, and
/// **Medium** (500) for the stanza position, both NEXT lines and the timer-only footer — but
/// only `design::WEIGHT_BOLD` (700) and `design::WEIGHT_REGULAR` (400) are ever passed here;
/// see the `design` module's font-weight doc comment for why 600/500 are unsafe to request
/// with this crate's bundled `Inter` asset (they resolve to a DIFFERENT, host-installed
/// typeface, not to a lighter Inter). This is **not** the faux-bold embolden path — that one
/// lives in `selahcue-engine::raster::draw_text` (not `attrs_for`), triggers above weight 550,
/// and is gated on `font.is_none()`, which is never true here: `line()` always passes
/// `stage_font()` (`Some("Inter")`), so chrome always takes the real-face path, never the
/// synthesised-embolden one. `track` is letter-spacing in device px (already scaled by
/// [`Metrics::track`]); the design tracks nine of these runs.
///
/// Chrome runs go through this path, which pushes a `Layer::Text` **directly** — they never
/// reach `compose::autofit_layers` and so never reach `measure`'s memo, whose key is
/// `{text, cell, font, weight}` and carries no tracking. That is what makes it safe to add
/// tracking here: a tracked run measured against an untracked cached width would silently
/// shrink-to-fit wrong. Keep it that way — a tracked run must not be routed through an
/// auto-fit region unless the memo key is extended first.
#[allow(clippy::too_many_arguments)]
fn line(
    f: &mut Frame,
    x: i32,
    y: i32,
    w: u32,
    px: u32,
    text: &str,
    color: Rgba,
    align: TextAlign,
    track: i32,
    weight: u16,
) {
    if text.is_empty() {
        return;
    }
    let px = px.max(1);
    f.push(Layer::Text {
        rect: Rect::new(x, y, w.max(1), px),
        text: text.to_string(),
        px,
        color,
        align,
        font: stage_font(),
        style: Some(TextStyle {
            weight,
            letter_spacing_px: track,
        }),
    });
}

/// A rough single-line advance (≈ 0.6 em plus tracking) — good enough to size a chip; exact
/// glyph metrics are not needed for a status pill. `track` must be the same letter-spacing
/// the run is drawn with, or a tracked label outgrows the pill drawn around it.
/// **Bounded**: a pathologically long (untrusted) title or line can't saturate the
/// `f64 → u32` cast to `u32::MAX` and overflow the width SUMS the callers build from it —
/// the composer must never panic on any input.
fn text_width(text: &str, px: u32, track: i32) -> u32 {
    // 4 Mpx — far beyond any renderable width (MAX_DIMENSION is 8192), yet small enough that a
    // handful of these summed stay well under u32::MAX.
    const CAP: f64 = (1u32 << 22) as f64;
    let n = text.chars().count() as f64;
    (n * ((px as f64) * 0.6 + track as f64))
        .ceil()
        .clamp(0.0, CAP) as u32
}

/// A filled rectangle with an optional hairline border and corner radius — the Design 2.0
/// raised surface (pills, chips, the timer band, the countdown panel, the message card).
/// A radius of 0 and a border of 0 is just [`fill`]; anything else needs the engine's
/// parametric `Layer::Shape`, which is what draws the border ring and the rounded corners.
#[allow(clippy::too_many_arguments)]
fn surface(
    f: &mut Frame,
    x: i32,
    y: i32,
    w: u32,
    h: u32,
    color: Rgba,
    border: Rgba,
    border_px: u32,
    corner_px: u32,
) {
    if w == 0 || h == 0 {
        return;
    }
    if border_px == 0 && corner_px == 0 {
        fill(f, x, y, w, h, color);
        return;
    }
    f.push(Layer::Shape {
        rect: Rect::new(x, y, w, h),
        kind: ShapeKind::RoundedRect,
        fill: color,
        border,
        border_px,
        corner_px,
    });
}

/// A **pill** — a surface whose corners are fully rounded (the design's `radius: 999`).
#[allow(clippy::too_many_arguments)]
fn pill(f: &mut Frame, x: i32, y: i32, w: u32, h: u32, color: Rgba, border: Rgba, border_px: u32) {
    surface(f, x, y, w, h, color, border, border_px, h / 2);
}

/// A small filled chip with a left label; returns its total width so the caller can flow
/// content after it. `corner` is the design's chip radius in device px.
#[allow(clippy::too_many_arguments)]
fn chip(
    f: &mut Frame,
    x: i32,
    y: i32,
    text: &str,
    px: u32,
    bg: Rgba,
    fg: Rgba,
    track: i32,
    corner: u32,
) -> u32 {
    let px = px.max(1);
    let pad = (px as f64 * 0.5) as u32;
    let w = text_width(text, px, track) + pad * 2;
    let h = px + pad;
    surface(f, x, y, w, h, bg, bg, 0, corner.min(h / 2));
    line(
        f,
        x + pad as i32,
        y + (pad / 2) as i32,
        w,
        px,
        text,
        fg,
        TextAlign::Left,
        track,
        design::WEIGHT_BOLD,
    );
    w
}

/// A small **round** status dot (font-safe — avoids relying on a `●` glyph in the bundled
/// font). Every dot in the design is a circle, so this draws an ellipse inscribed in a
/// square, not the square itself.
fn dot(f: &mut Frame, x: i32, y: i32, d: u32, color: Rgba) {
    let d = d.max(1);
    f.push(Layer::Shape {
        rect: Rect::new(x, y, d, d),
        kind: ShapeKind::Ellipse,
        fill: color,
        border: color,
        border_px: 0,
        corner_px: 0,
    });
}

/// The `▲` on the timer-only overrun pill (Figma 374-172), drawn as a shape rather than a
/// glyph — the bundled Latin face has no `▲`, exactly as it has no `…` (see [`ellipsize`]),
/// and a missing glyph on a TIME-UP alert would render as tofu.
fn up_triangle(f: &mut Frame, x: i32, y: i32, w: u32, h: u32, color: Rgba) {
    if w == 0 || h == 0 {
        return;
    }
    f.push(Layer::Shape {
        rect: Rect::new(x, y, w, h),
        kind: ShapeKind::Triangle,
        fill: color,
        border: color,
        border_px: 0,
        corner_px: 0,
    });
}

/// Auto-fit explicit `lines` into `region` (word-wrap + shrink-to-fit so the speaker sees
/// EVERYTHING, never truncated — parity with the audience output), capped at `max_cell`
/// line-box height. Templates pass a larger cap for the big lyric / verse bands than for a
/// muted status line, and the leading the design sets for that region.
///
/// The tracking the auto-fit regions are laid out with: **none**. Design 2.0 sets no
/// letter-spacing on any of the three (lyric, verse, message body), so this is the design
/// value, not a shortcut.
///
/// Note the unit: `autofit_layers` takes tracking in **permille of the cell**, not px like
/// [`line`]'s `TextStyle::letter_spacing_px` — it converts on the way out, because it has to
/// budget the wrap for the widening (`compose.rs`'s `ls_add`). That budgeting is why a
/// tracked auto-fit region would still be safe despite `measure`'s memo key
/// (`{text, cell, font, weight}`) carrying no tracking: the memo holds the untracked shaped
/// width and the spacing is added on top, deliberately, rather than being keyed. Anything
/// added here must keep that property — a shaping attribute that changes the *shaped* width
/// (a different weight, a different family, a stretch) does NOT have that escape hatch and
/// would need the key extended first.
const AUTOFIT_TRACKING: i16 = 0;

#[allow(clippy::too_many_arguments)]
fn fit_lines(
    f: &mut Frame,
    lines: &[&str],
    region: Rect,
    max_cell: u32,
    line_height: f64,
    align: TextAlign,
    valign: VAlign,
    color: Rgba,
    weight: u16,
) -> Option<u32> {
    if lines.is_empty() {
        return None;
    }
    let mut resolved = None;
    for layer in autofit_layers(
        lines,
        region,
        max_cell.max(1),
        line_height,
        align,
        valign,
        color,
        Fit::ShrinkToFit,
        stage_font(),
        weight,
        AUTOFIT_TRACKING,
    ) {
        if let Layer::Text { px, .. } = &layer {
            resolved = Some(resolved.map_or(*px, |r: u32| r.max(*px)));
        }
        f.push(layer);
    }
    resolved
}

/// The live-content band **fills** its region: the largest size at which every line still
/// fits, in BOTH directions.
///
/// `autofit_layers`'s `ShrinkToFit` already binary-searches for the largest cell that fits
/// the region; it only ever looked like a shrink because the stage handed it the design size
/// as the ceiling, so a short stanza could never reach past it and left most of the band
/// empty. Passing the **region height** as the ceiling instead makes the region drive the
/// size — grow and shrink from one search, with the never-truncate guarantee unchanged
/// (every candidate cell is still required to fit every wrapped line).
///
/// Owner direction, scoped to the confidence monitor: a speaker at the back of a room needs
/// the live line as large as the band allows. The audience output keeps its own default.
fn fill_cell(region: Rect) -> u32 {
    region.h.max(1)
}

/// A run that must stay visually **subordinate** to the live content — the NEXT line and its
/// chip. Derived from the size the content actually resolved to rather than from a constant,
/// because a constant inverts the hierarchy: with the design's fixed 30px NEXT against a
/// lyric that shrinks to fit, a stanza of six lines or more rendered the *coming* line larger
/// than the line being sung.
///
/// The ratio is the design's own at its reference size (Figma 373-148: 30px NEXT against a
/// 56px lyric), so through the shrinking range this reproduces the design's proportions.
///
/// Two ceilings apply. `design_cell` is the size the design gives this run: the defect was a
/// *shrinking* live line falling below a fixed NEXT, so coupling only ever needs to pull
/// NEXT **down**. Letting the ratio push it *up* when the live band grows would trade one
/// defect for another — the scripture NEXT line is ellipsized to keep the countdown panel
/// clear, and an inflated one ellipsizes away to almost nothing, while the worship one does
/// not ellipsize at all and would simply overflow the frame. `row_h` bounds it to the space
/// between the row and whatever sits below it.
fn subordinate_cell(
    content_cell: u32,
    numer: f64,
    denom: f64,
    design_cell: u32,
    row_h: u32,
) -> u32 {
    let scaled = ((content_cell as f64) * numer / denom) as u32;
    scaled.min(design_cell).clamp(1, row_h.max(1))
}

/// The timer readout for a template: `TIME UP` when over, else `M:SS` remaining / elapsed.
fn timer_readout(t: &TimerView) -> String {
    if t.time_up {
        "TIME UP".to_string()
    } else {
        format_clock(t.remaining_secs.unwrap_or(t.elapsed_secs))
    }
}

/// The pulsing ink for the TIME UP **words** — a calm one-second bright/dim alternation
/// (a 0.5 Hz pulse keyed off the elapsed second, which the stage already re-renders each
/// second). Only the text pulses; the red wash behind it stays steady. Deliberately slow and
/// small-area: well below the WCAG 2.3.1 flash threshold, so the alert draws the eye without a
/// seizure-risk strobe.
fn time_up_ink(theme: &StageTheme, elapsed_secs: u32) -> Rgba {
    if elapsed_secs.is_multiple_of(2) {
        theme.timer_alert.lerp(Rgba::WHITE, 350) // brightened "glow" second
    } else {
        theme.timer_alert // base alert red
    }
}

/// The top-right header wall clock shared by the worship + scripture templates (Figma
/// 373-140 / 374-131): the 12-hour time-of-day, right-aligned to a 0.04·w margin. A no-op
/// until the backend feeds a clock.
fn header_clock(
    f: &mut Frame,
    ctx: &StageContext,
    theme: &StageTheme,
    m: &Metrics,
    em: f64,
    ref_y: f64,
) {
    let Some(time) = ctx
        .clock
        .as_ref()
        .map(|c| c.time())
        .filter(|s| !s.is_empty())
    else {
        return;
    };
    line(
        f,
        0,
        m.vy(ref_y),
        m.hw(REF_W - design::X_MARGIN),
        m.cell(em),
        time,
        theme.text,
        TextAlign::Right,
        m.track(design::TRACK_NONE),
        design::WEIGHT_REGULAR,
    );
}

/// How many concentric ellipses approximate the timer-only TIME-UP vignette.
///
/// The engine has **no radial gradient**: `Layer::Gradient` is a two-stop *linear* ramp
/// (`GradientDirection` is vertical / horizontal / diagonal), and `selahcue-engine` is
/// another session's tree, so a `RadialGradient` layer is not this batch's to add. The
/// closest faithful approximation with the primitives that exist is a stack of filled
/// `ShapeKind::Ellipse` layers, each painted the ramp colour at its radius.
///
/// 12 bands is chosen from the ramp itself, not from taste: the whole gradient spans 34
/// steps of red and 5 of green/blue (`#2a0e12` → `#08090d`), so 12 bands step red by ~3/255
/// and green/blue by well under 1 — below the visible-banding threshold on a near-black
/// field — while keeping the layer count and the fill cost bounded (each band's cost is its
/// own bounding box, so the stack totals ~4.5 frames' worth of pixel tests, paid once and
/// then served from the static-prefix cache, since every band precedes the first text run).
const ALERT_VIGNETTE_BANDS: u32 = 12;

// A one-band "ramp" would be a flat fill wearing a gradient's name — the test that asserts
// the centre is redder than the edge has to have something to measure.
const _: () = assert!(ALERT_VIGNETTE_BANDS >= 3);

/// The vignette colour at radius `t` (0 = centre, 1000‰ = frame edge): a piecewise ramp
/// through the design's three stops — `core` → `mid` at the half-radius → `edge`.
fn vignette_stop(theme: &StageTheme, t_permille: u32) -> Rgba {
    let t = t_permille.min(1000);
    if t <= 500 {
        theme
            .alert_vignette_core
            .lerp(theme.alert_vignette_mid, t * 2)
    } else {
        theme
            .alert_vignette_mid
            .lerp(theme.alert_vignette_edge, (t - 500) * 2)
    }
}

/// Paint the timer-only TIME-UP background: the Design 2.0 **vignette** (Figma 374-166) —
/// an elliptical ramp centred on the frame, darkest-red at the centre and falling to the
/// stage background at the edge. Replaces the legacy solid-inverted treatment (white on a
/// flat red field, legacy frame 13:15).
///
/// Drawn outermost-first so each band covers the one before it; the outer fill guarantees
/// the frame is fully painted whatever the rounding does to the largest ellipse.
fn push_alert_vignette(f: &mut Frame, theme: &StageTheme, w: u32, h: u32) {
    fill(f, 0, 0, w, h, theme.alert_vignette_edge);
    for band in (1..=ALERT_VIGNETTE_BANDS).rev() {
        // The band spans radii [(band-1)/N, band/N] and is painted the ramp colour at its
        // INNER edge — so the innermost band is the exact `core` stop rather than a value
        // 1/2N of the way along the ramp, and the centre of the screen is the colour the
        // design names.
        let t = ((band - 1) * 1000) / ALERT_VIGNETTE_BANDS;
        let bw = ((w as u64 * band as u64) / ALERT_VIGNETTE_BANDS as u64) as u32;
        let bh = ((h as u64 * band as u64) / ALERT_VIGNETTE_BANDS as u64) as u32;
        if bw == 0 || bh == 0 {
            continue;
        }
        f.push(Layer::Shape {
            rect: Rect::new(((w - bw) / 2) as i32, ((h - bh) / 2) as i32, bw, bh),
            kind: ShapeKind::Ellipse,
            fill: vignette_stop(theme, t),
            border: vignette_stop(theme, t),
            border_px: 0,
            corner_px: 0,
        });
    }
}

// --- Worship: a song header (title pill + stanza position + clock), big centred lyrics, the
// coming line, and a footer timer band. TIME UP flips only the footer (Figma 373-133/159). ---
#[allow(clippy::too_many_arguments)]
fn compose_worship(
    frame: &mut Frame,
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    ctx: &StageContext,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    let title = current.map(|s| s.title.trim()).filter(|t| !t.is_empty());
    let body: Vec<&str> = current
        .map(|s| {
            s.body
                .iter()
                .map(String::as_str)
                .filter(|l| !l.trim().is_empty())
                .collect()
        })
        .unwrap_or_default();
    let is_song = !body.is_empty();

    let m = Metrics::new(w, h, ctx);

    // Header pill: the live song (violet dot + title). Only a real song (has lyrics) gets the
    // pill; a title-only item shows its title as the centre text instead.
    if is_song {
        if let Some(title) = title {
            let pill_px = m.cell(design::EM_SONG_TITLE);
            let px0 = m.hx(design::X_MARGIN);
            let py0 = m.vy(design::Y_SONG_PILL);
            // The design's own paddings (pl 13 / pr 14 / gap 8), which are what put the
            // title at x 70 with the dot at x 53. `pad_y` is tuned so the pill stands 41px
            // tall at the reference frame and grows with the label at a larger text scale.
            let pad_l = m.hw(13.0);
            let pad_r = m.hw(14.0);
            let gap = m.hw(8.0);
            let pad_y = ((pill_px as f64) * 0.34) as u32;
            let dot_d = m.vh(design::D_SONG_DOT);
            let title_w = text_width(title, pill_px, m.track(design::TRACK_NONE));
            let pill_w = pad_l + dot_d + gap + title_w + pad_r;
            let pill_h = pill_px + pad_y * 2;
            pill(
                frame,
                px0,
                py0,
                pill_w,
                pill_h,
                theme.track,
                theme.border,
                m.stroke(design::B_HAIRLINE),
            );
            dot(
                frame,
                px0 + pad_l as i32,
                py0 + (pill_h.saturating_sub(dot_d) / 2) as i32,
                dot_d,
                theme.song_accent,
            );
            line(
                frame,
                px0 + (pad_l + dot_d + gap) as i32,
                py0 + pad_y as i32,
                title_w + pill_px,
                pill_px,
                title,
                theme.text,
                TextAlign::Left,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
            // Stanza position after the pill, e.g. "Verse 2 of 4".
            if let Some((i, n)) = ctx.song_position {
                let vpx = m.cell(design::EM_STANZA);
                line(
                    frame,
                    px0 + pill_w as i32 + m.hw(16.0) as i32,
                    py0 + (pill_h.saturating_sub(vpx) / 2) as i32,
                    (w as f64 * 0.4) as u32,
                    vpx,
                    &format!("Verse {i} of {n}"),
                    theme.muted,
                    TextAlign::Left,
                    m.track(design::TRACK_NONE),
                    design::WEIGHT_REGULAR,
                );
            }
        }
    }
    header_clock(
        frame,
        ctx,
        theme,
        &m,
        design::EM_WORSHIP_CLOCK,
        design::Y_WORSHIP_CLOCK,
    );

    // The band is bottom-anchored; the design's top and height sum to the full reference
    // height, so anchoring to the bottom edge reproduces `Y_TIMER_BAND` without letting a
    // rounding error leave a seam under the band. Computed here because the elastic lyric
    // band below is measured against it.
    const _: () = assert!(design::Y_TIMER_BAND + design::H_TIMER_BAND == REF_H);
    let band_h = m.vh(design::H_TIMER_BAND);
    let band_y = (h.saturating_sub(band_h)) as i32;

    // Centre band: the current stanza (or the title for a title-only item), big + centred.
    let content: Vec<&str> = if is_song {
        body
    } else {
        title.into_iter().collect()
    };
    // The live band is ELASTIC: it claims the vertical space nothing else needs, rather than
    // sitting in the fixed 212-unit rect Figma 373:133 draws. That frame was drawn with a
    // TWO-LINE lyric, which fills the rect at the design size and looks right; a real eight-
    // or nine-line stanza in the same rect shrinks to ~16px-equivalent while a third of the
    // screen stays empty. So the frame's band rect is read as *the two-line case*, not as
    // normative geometry.
    //
    // The band runs from the bottom of the header chrome to the top of the NEXT row, less a
    // named safe gap at each end — so growth can never collide with the clock above or the
    // row below. Both edges are derived from the chrome's own constants, so moving a piece
    // of chrome moves the band with it.
    let gap = m.vh(design::BAND_SAFE_GAP) as i32;
    let header_bottom = (m.vy(design::Y_SONG_PILL) + m.vh(design::H_SONG_PILL) as i32)
        .max(m.vy(design::Y_WORSHIP_CLOCK) + m.cell(design::EM_WORSHIP_CLOCK) as i32);
    // The NEXT row is reserved at its largest — the design size, which is also the ceiling
    // `subordinate_cell` clamps to — and parked just above the timer band, which is where
    // the rest of the space below the design's row position comes from.
    let next_row_h = m.cell(design::EM_NEXT_LINE) as i32;
    let next_row_top = band_y - gap - next_row_h;
    let lyric_top = header_bottom + gap;
    let lyric_region = Rect::new(
        m.hx(design::X_BODY),
        lyric_top,
        m.hw(REF_W - 2.0 * design::X_BODY),
        (next_row_top - gap - lyric_top).max(1) as u32,
    );
    let lyric_cell = fit_lines(
        frame,
        &content,
        lyric_region,
        fill_cell(lyric_region),
        STAGE_LINE_HEIGHT,
        TextAlign::Center,
        VAlign::Middle,
        theme.text,
        700,
    )
    .unwrap_or_else(|| m.cell(design::EM_LYRIC_REF));

    // The coming line (muted), a NEXT chip + the first line of the next stanza, centred.
    if let Some(nl) = next
        .map(|s| s.body.first().map(String::as_str).unwrap_or(&s.title))
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        // The row sits where the elastic band left it — just above the timer band.
        let ny = next_row_top;
        let row_h = (band_y - gap - ny).max(1) as u32;
        let line_px = subordinate_cell(
            lyric_cell,
            design::EM_NEXT_LINE,
            design::EM_LYRIC_REF,
            m.cell(design::EM_NEXT_LINE),
            row_h,
        );
        let chip_px = subordinate_cell(
            line_px,
            design::EM_NEXT_CHIP,
            design::EM_NEXT_LINE,
            m.cell(design::EM_NEXT_CHIP),
            row_h,
        );
        let chip_track = m.track(design::TRACK_1);
        // `gap_x`, not `gap`: the enclosing `gap` is the elastic band's vertical safe gap.
        let gap_x = m.hw(14.0);
        // Centre the (chip + gap + line) group. `chip()` draws a width of text+px (pad·2).
        let chip_w = text_width("NEXT", chip_px, chip_track) + chip_px;
        // Clip the coming line to what is left of the row between the frame margins, with a
        // trailing ellipsis — exactly as the scripture template does. Without this the row is
        // centred by `w.saturating_sub(group_w)`, which SATURATES to 0 once the group is wider
        // than the frame: the chip pins to the left margin and the line runs off the right
        // edge, where `draw_text` cuts it at the frame boundary with no indication anything is
        // missing. A speaker then reads a sentence sliced off mid-word and cannot tell.
        // `ellipsize` returns the string unchanged when it already fits, so a short line does
        // NOT gain an ellipsis.
        let avail = w.saturating_sub(m.hx(design::X_MARGIN).max(0) as u32 * 2 + chip_w + gap_x);
        let shown = ellipsize(nl, line_px, avail);
        let line_w = text_width(&shown, line_px, m.track(design::TRACK_NONE));
        let group_w = chip_w + gap_x + line_w;
        let start_x = (w.saturating_sub(group_w) / 2) as i32;
        let chip_h = chip_px + chip_px / 2;
        let cw = chip(
            frame,
            start_x,
            ny,
            "NEXT",
            chip_px,
            theme.track,
            theme.muted,
            chip_track,
            m.stroke(design::R_CHIP),
        );
        line(
            frame,
            start_x + cw as i32 + gap_x as i32,
            ny + (chip_h.saturating_sub(line_px) / 2) as i32,
            line_w + line_px,
            line_px,
            &shown,
            theme.muted,
            TextAlign::Left,
            m.track(design::TRACK_NONE),
            design::WEIGHT_REGULAR,
        );
    }

    // Footer timer band: a state dot + SERVICE TIMER and the readout. TIME UP washes only
    // this band red (spec: worship flips the timer region only, not the whole screen).
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    surface(
        frame,
        0,
        band_y,
        w,
        band_h,
        if up { theme.alert_wash } else { theme.panel },
        if up { theme.alert_border } else { theme.border },
        m.stroke(if up {
            design::B_TIME_UP_BAND
        } else {
            design::B_HAIRLINE
        }),
        0,
    );
    // Only an ACTIVE timer draws the caption + readout; an idle monitor shows a bare band.
    if let Some(t) = timer {
        let col = if up {
            theme.timer_alert
        } else {
            t.color(theme)
        };
        let cap_px = m.cell(design::EM_SERVICE_TIMER);
        let cy = band_y + (band_h.saturating_sub(cap_px) / 2) as i32;
        let dot_d = m.vh(design::D_TIMER_DOT);
        dot(
            frame,
            m.hx(design::X_MARGIN),
            cy + (cap_px.saturating_sub(dot_d) / 2) as i32,
            dot_d,
            col,
        );
        line(
            frame,
            m.hx(design::X_MARGIN) + dot_d as i32 + m.hw(12.0) as i32,
            cy,
            (w as f64 * 0.5) as u32,
            cap_px,
            "SERVICE TIMER",
            // The caption flips to the alert ink with the rest of the band at TIME UP
            // (Figma 373-159) — it is part of the region that changes state, not chrome
            // that stays muted through it.
            if up { theme.timer_alert } else { theme.muted },
            TextAlign::Left,
            m.track(design::TRACK_1),
            design::WEIGHT_BOLD,
        );
        // At TIME UP the readout word pulses (the dot + band stay steady).
        let readout_col = if up {
            time_up_ink(theme, t.elapsed_secs)
        } else {
            col
        };
        let right = m.hx(REF_W - design::X_MARGIN);
        if up {
            // TIME UP: the word, then an `OVER m:ss` pill right-aligned to the margin, so
            // the speaker reads how far over they are and not just that they are over.
            let over_px = m.cell(design::EM_WORSHIP_OVER);
            let label = overrun_label("OVER", t.overrun_secs);
            let pad_x = m.hw(13.0);
            let pad_y = ((over_px as f64) * 0.34) as u32;
            let over_w = text_width(&label, over_px, m.track(design::TRACK_NONE)) + pad_x * 2;
            let over_h = over_px + pad_y * 2;
            let over_x = right - over_w as i32;
            let over_y = band_y + (band_h.saturating_sub(over_h) / 2) as i32;
            pill(
                frame,
                over_x,
                over_y,
                over_w,
                over_h,
                theme.alert_wash,
                theme.alert_border,
                m.stroke(design::B_HAIRLINE),
            );
            line(
                frame,
                over_x + pad_x as i32,
                over_y + pad_y as i32,
                over_w,
                over_px,
                &label,
                theme.timer_alert,
                TextAlign::Left,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
            let word_px = m.cell(design::EM_WORSHIP_TIME_UP);
            let word_right = over_x - m.hw(16.0) as i32;
            line(
                frame,
                (w as f64 * 0.30) as i32,
                band_y + (band_h.saturating_sub(word_px) / 2) as i32,
                (word_right - (w as f64 * 0.30) as i32).max(1) as u32,
                word_px,
                "TIME UP",
                readout_col,
                TextAlign::Right,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
        } else {
            let px = m.cell(design::EM_TIMER_READOUT);
            line(
                frame,
                (w as f64 * 0.50) as i32,
                band_y + (band_h.saturating_sub(px) / 2) as i32,
                (right - (w as f64 * 0.50) as i32).max(1) as u32,
                px,
                &timer_readout(t),
                readout_col,
                TextAlign::Right,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
        }
    }
}

// --- Scripture: verse + next on the left, a countdown panel on the right. TIME UP tints
// the panel only. ---
#[allow(clippy::too_many_arguments)]
fn compose_scripture(
    frame: &mut Frame,
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    ctx: &StageContext,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    let m = Metrics::new(w, h, ctx);
    let hx = m.hx(design::X_BODY);
    let left_w = m.hw(design::W_BODY);

    // Header: the screen label + the wall clock. The label sits on the header band's own
    // 40px margin, not the body column's 48px inset (Figma 374-130).
    line(
        frame,
        m.hx(design::X_MARGIN),
        m.vy(design::Y_SCREEN_LABEL),
        left_w,
        m.cell(design::EM_SCREEN_LABEL),
        "STAGE · SCRIPTURE",
        theme.muted,
        TextAlign::Left,
        m.track(design::TRACK_2),
        design::WEIGHT_BOLD,
    );
    header_clock(
        frame,
        ctx,
        theme,
        &m,
        design::EM_SCRIPTURE_CLOCK,
        design::Y_SCRIPTURE_CLOCK,
    );

    // Left column: the reference (gold) then the verse body (white, left-aligned + wrapped).
    if let Some(reference) = current.map(|s| s.title.trim()).filter(|t| !t.is_empty()) {
        line(
            frame,
            hx,
            m.vy(design::Y_REFERENCE),
            left_w,
            m.cell(design::EM_REFERENCE),
            &reference.to_uppercase(),
            theme.accent,
            TextAlign::Left,
            m.track(design::TRACK_1),
            design::WEIGHT_BOLD,
        );
    }
    let verse: Vec<&str> = current
        .map(|s| {
            s.body
                .iter()
                .map(String::as_str)
                .filter(|l| !l.trim().is_empty())
                .collect()
        })
        .unwrap_or_default();
    // Elastic band, as in the worship template: from the bottom of the reference line to the
    // top of the NEXT row, less a safe gap at each end. Scripture's fixed rect is already
    // 1.42x the worship one and its content is shorter, so the gain here is smaller — but the
    // dead space below the NEXT row is the same class of waste.
    let gap = m.vh(design::BAND_SAFE_GAP) as i32;
    let verse_top = m.vy(design::Y_REFERENCE) + m.cell(design::EM_REFERENCE) as i32 + gap;
    let next_row_h = m.cell(design::EM_SCRIPTURE_NEXT_LINE) as i32;
    let next_row_top = h as i32 - m.vh(design::Y_BOTTOM_MARGIN) as i32 - next_row_h;
    let verse_region = Rect::new(
        hx,
        verse_top,
        left_w,
        (next_row_top - gap - verse_top).max(1) as u32,
    );
    let verse_cell = fit_lines(
        frame,
        &verse,
        verse_region,
        fill_cell(verse_region),
        VERSE_LINE_HEIGHT,
        TextAlign::Left,
        VAlign::Top,
        theme.text,
        700,
    )
    .unwrap_or_else(|| m.cell(design::EM_VERSE_REF));

    // NEXT row (left column): the coming reference · verse, clipped to the column with an
    // ellipsis (the panel must stay clear).
    if let Some(nl) = next.and_then(scripture_next_label) {
        let ny = next_row_top;
        let row_h = (h as i32 - ny).max(1) as u32;
        let line_px = subordinate_cell(
            verse_cell,
            design::EM_SCRIPTURE_NEXT_LINE,
            design::EM_VERSE_REF,
            m.cell(design::EM_SCRIPTURE_NEXT_LINE),
            row_h,
        );
        let chip_px = subordinate_cell(
            line_px,
            design::EM_SCRIPTURE_NEXT_CHIP,
            design::EM_SCRIPTURE_NEXT_LINE,
            m.cell(design::EM_SCRIPTURE_NEXT_CHIP),
            row_h,
        );
        let chip_track = m.track(design::TRACK_1);
        let gap = m.hw(12.0);
        let cw = chip(
            frame,
            hx,
            ny,
            "NEXT",
            chip_px,
            theme.track,
            theme.muted,
            chip_track,
            m.stroke(design::R_CHIP),
        );
        let nx = hx + cw as i32 + gap as i32;
        let avail = left_w.saturating_sub(cw + gap);
        let chip_h = chip_px + chip_px / 2;
        line(
            frame,
            nx,
            ny + (chip_h.saturating_sub(line_px) / 2) as i32,
            avail,
            line_px,
            &ellipsize(&nl, line_px, avail),
            theme.muted,
            TextAlign::Left,
            m.track(design::TRACK_NONE),
            design::WEIGHT_REGULAR,
        );
    }

    // Right countdown panel (full content height). TIME UP washes the panel only.
    let px0 = m.hx(design::X_PANEL);
    let pw = w.saturating_sub(px0.max(0) as u32);
    let py = m.vy(design::Y_PANEL);
    let ph = h.saturating_sub(py.max(0) as u32);
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    let warn = timer.map(|t| t.warn).unwrap_or(false);
    surface(
        frame,
        px0,
        py,
        pw,
        ph,
        if up { theme.alert_wash } else { theme.panel },
        if up { theme.alert_border } else { theme.border },
        m.stroke(design::B_HAIRLINE),
        0,
    );

    // Status pill (dot + label) centred in the panel. Design 2.0 draws it as the standard
    // status chip — the state's bright ink on its own soft tint, ringed by its own border.
    let (pill_label, pill_col, pill_fill, pill_border) = if up {
        (
            "TIME UP",
            theme.timer_alert,
            theme.alert_wash,
            theme.alert_border,
        )
    } else if warn {
        (
            "HURRY",
            theme.timer_warn,
            theme.warn_soft,
            theme.warn_border,
        )
    } else {
        ("ON TIME", theme.timer_ok, theme.ok_soft, theme.ok_border)
    };
    // At TIME UP the pill LABEL pulses each second; the dot + panel wash stay steady.
    let elapsed = timer.map(|t| t.elapsed_secs).unwrap_or(0);
    let pill_label_col = if up {
        time_up_ink(theme, elapsed)
    } else {
        pill_col
    };
    let pill_px = m.cell(design::EM_PILL_LABEL);
    let pill_track = m.track(design::TRACK_NONE);
    let dot_d = m.vh(design::D_PILL_DOT);
    let pgap = m.hw(8.0);
    let pad_l = m.hw(11.0);
    let pad_r = m.hw(12.0);
    let label_w = text_width(pill_label, pill_px, pill_track);
    let pill_w = pad_l + dot_d + pgap + label_w + pad_r;
    let pill_h = m.vh(design::H_PILL).max(pill_px + pill_px / 2);
    let pill_x = px0 + (pw.saturating_sub(pill_w) / 2) as i32;
    let pill_y = m.vy(design::Y_PILL);
    pill(
        frame,
        pill_x,
        pill_y,
        pill_w,
        pill_h,
        pill_fill,
        pill_border,
        m.stroke(design::B_HAIRLINE),
    );
    dot(
        frame,
        pill_x + pad_l as i32,
        pill_y + (pill_h.saturating_sub(dot_d) / 2) as i32,
        dot_d,
        pill_col,
    );
    line(
        frame,
        pill_x + (pad_l + dot_d + pgap) as i32,
        pill_y + (pill_h.saturating_sub(pill_px) / 2) as i32,
        label_w + pill_px,
        pill_px,
        pill_label,
        pill_label_col,
        TextAlign::Left,
        pill_track,
        design::WEIGHT_BOLD,
    );

    // "TIME LEFT" caption + the big readout, centred in the panel.
    line(
        frame,
        px0,
        m.vy(design::Y_TIME_LEFT),
        pw,
        m.cell(design::EM_TIME_LEFT),
        "TIME LEFT",
        theme.muted,
        TextAlign::Center,
        m.track(design::TRACK_1),
        design::WEIGHT_BOLD,
    );
    if let Some(t) = timer {
        // "TIME UP" is wider than "M:SS", so it drops to half the readout size to clear the
        // narrow panel — Figma draws no Scripture TIME-UP frame, so this keeps the code's
        // approved behaviour (audit Q5) at the corrected reference scale.
        let (txt, read_px, track) = if up {
            (
                "TIME UP".to_string(),
                m.cell(design::EM_BIG_READOUT / 2.0),
                m.track(design::TRACK_NONE),
            )
        } else {
            (
                timer_readout(t),
                m.cell(design::EM_BIG_READOUT),
                m.track(design::TRACK_READOUT),
            )
        };
        line(
            frame,
            px0,
            m.vy(design::Y_BIG_READOUT),
            pw,
            read_px,
            &txt,
            if up {
                time_up_ink(theme, t.elapsed_secs)
            } else {
                t.color(theme)
            },
            TextAlign::Center,
            track,
            design::WEIGHT_BOLD,
        );
        // The overrun, under the readout — the panel is the Scripture TIME-UP region, so
        // this is where "how far over" belongs (STG-038's counterpart for this template).
        if up {
            line(
                frame,
                px0,
                m.vy(design::Y_BIG_READOUT) + m.cell(design::EM_BIG_READOUT / 2.0) as i32,
                pw,
                m.cell(design::EM_PILL_LABEL * 2.0),
                &overrun_label("OVER", t.overrun_secs),
                theme.timer_alert,
                TextAlign::Center,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
        }
    }
}

/// The scripture NEXT label: the coming reference joined to the start of its verse
/// (`Isaiah 61:6 · But ye shall be named…`). `None` when there's nothing meaningful.
fn scripture_next_label(s: &Slide) -> Option<String> {
    let head = s.title.trim();
    let body = s.body.first().map(|l| l.trim()).filter(|l| !l.is_empty());
    match (head.is_empty(), body) {
        (false, Some(b)) => Some(format!("{head} · {b}")),
        (false, None) => Some(head.to_string()),
        (true, Some(b)) => Some(b.to_string()),
        (true, None) => None,
    }
}

/// Truncate `text` with a trailing `...` so its estimated width fits `max_w` at `px` (matches
/// the design's clipped NEXT line). Rough — uses [`text_width`]'s estimate — but never
/// overflows. Uses ASCII dots (the bundled Latin face has no `…` glyph).
fn ellipsize(text: &str, px: u32, max_w: u32) -> String {
    if text_width(text, px, 0) <= max_w {
        return text.to_string();
    }
    let mut kept = String::new();
    for ch in text.chars() {
        let mut candidate = kept.clone();
        candidate.push(ch);
        if text_width(&format!("{candidate}..."), px, 0) > max_w {
            break;
        }
        kept.push(ch);
    }
    kept.push_str("...");
    kept
}

// --- Timer-only: a big centred countdown with service chrome (Figma 374-151). Header row
// (SERVICE TIMER · wall clock), a segment label, the giant readout, and a date+time footer.
// TIME UP washes the whole screen. ---
fn compose_timer_only(
    frame: &mut Frame,
    current: Option<&Slide>,
    timer: Option<&TimerView>,
    ctx: &StageContext,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    let m = Metrics::new(w, h, ctx);
    let clock = ctx.clock.as_ref();
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    let segment = current.map(|s| s.title.trim()).filter(|t| !t.is_empty());
    if up {
        // The Design 2.0 TIME-UP field (Figma 374-166): a dark elliptical vignette, red ink
        // on it. This replaces the legacy solid-inverted treatment (white on flat red).
        push_alert_vignette(frame, theme, w, h);
    }

    // Header, left: the screen label — at TIME UP the design moves the SEGMENT name here
    // instead (Figma 374-166), and drops the separate body label, so the name appears once.
    let header_label = if up {
        segment.unwrap_or("SERVICE TIMER")
    } else {
        "SERVICE TIMER"
    };
    line(
        frame,
        m.hx(design::X_MARGIN),
        m.vy(design::Y_TIMER_HEADER),
        w,
        m.cell(design::EM_TIMER_HEADER),
        &header_label.to_uppercase(),
        theme.muted,
        TextAlign::Left,
        m.track(if up {
            design::TRACK_1_5
        } else {
            design::TRACK_2
        }),
        design::WEIGHT_BOLD,
    );
    // Header, right: the wall clock (time-of-day), right-aligned to the 40px margin.
    if let Some(c) = clock.filter(|c| !c.time().is_empty()) {
        line(
            frame,
            0,
            m.vy(design::Y_TIMER_CLOCK),
            m.hw(REF_W - design::X_MARGIN),
            m.cell(design::EM_TIMER_CLOCK),
            c.time(),
            theme.text,
            TextAlign::Right,
            m.track(design::TRACK_NONE),
            design::WEIGHT_REGULAR,
        );
    }

    // Segment label above the readout — the live slide's title (e.g. "SERMON"); omitted
    // when nothing is live, and at TIME UP, where it has moved into the header.
    if let (false, Some(title)) = (up, segment) {
        line(
            frame,
            0,
            m.vy(design::Y_SEGMENT),
            w,
            m.cell(design::EM_SEGMENT),
            &title.to_uppercase(),
            theme.muted,
            TextAlign::Center,
            m.track(design::TRACK_4),
            design::WEIGHT_BOLD,
        );
    }

    // The giant readout.
    match timer {
        Some(t) if t.time_up => {
            line(
                frame,
                0,
                m.vy(design::Y_TIMER_TIME_UP),
                w,
                m.cell(design::EM_TIMER_TIME_UP),
                "TIME UP",
                time_up_ink(theme, t.elapsed_secs),
                TextAlign::Center,
                m.track(design::TRACK_2),
                design::WEIGHT_BOLD,
            );
            // The `▲ OVER BY m:ss` pill (Figma 374-172) — how far over, not just that.
            let over_px = m.cell(design::EM_TIMER_OVER);
            let label = overrun_label("OVER BY", t.overrun_secs);
            let tri_w = m.cell(design::EM_TIMER_OVER * 0.6);
            let pad_l = m.hw(18.0);
            let pad_r = m.hw(20.0);
            let gap = m.hw(10.0);
            let label_w = text_width(&label, over_px, m.track(design::TRACK_NONE));
            let over_w = pad_l + tri_w + gap + label_w + pad_r;
            let over_h = m.vh(design::H_TIMER_OVER).max(over_px);
            let over_x = ((w.saturating_sub(over_w)) / 2) as i32;
            let over_y = m.vy(design::Y_TIMER_OVER);
            pill(
                frame,
                over_x,
                over_y,
                over_w,
                over_h,
                theme.alert_wash,
                theme.alert_border,
                m.stroke(design::B_OVER_PILL),
            );
            up_triangle(
                frame,
                over_x + pad_l as i32,
                over_y + (over_h.saturating_sub(tri_w) / 2) as i32,
                tri_w,
                tri_w,
                theme.timer_alert,
            );
            line(
                frame,
                over_x + (pad_l + tri_w + gap) as i32,
                over_y + (over_h.saturating_sub(over_px) / 2) as i32,
                label_w + over_px,
                over_px,
                &label,
                theme.timer_alert,
                TextAlign::Left,
                m.track(design::TRACK_NONE),
                design::WEIGHT_BOLD,
            );
        }
        Some(t) => {
            line(
                frame,
                0,
                m.vy(design::Y_GIANT_READOUT),
                w,
                m.cell(design::EM_GIANT_READOUT),
                &timer_readout(t),
                t.color(theme),
                TextAlign::Center,
                m.track(design::TRACK_GIANT_READOUT),
                design::WEIGHT_BOLD,
            );
        }
        None => {
            line(
                frame,
                0,
                m.vy(design::Y_GIANT_READOUT),
                w,
                m.cell(design::EM_GIANT_READOUT),
                "--:--",
                theme.muted,
                TextAlign::Center,
                m.track(design::TRACK_GIANT_READOUT),
                design::WEIGHT_BOLD,
            );
        }
    }

    // Footer: the date and 12-hour time-of-day, e.g. "Sunday · August 3, 2026 · 10:42 AM".
    // At TIME UP the design shows the DATE only, smaller and higher (Figma 374-175) — the
    // time-of-day is redundant next to an alert about the clock.
    if let Some(c) = clock.filter(|c| !c.date().is_empty()) {
        let footer = if up || c.time().is_empty() {
            c.date().to_string()
        } else {
            format!("{} · {}", c.date(), c.time())
        };
        line(
            frame,
            0,
            m.vy(if up {
                design::Y_TIME_UP_DATE
            } else {
                design::Y_FOOTER
            }),
            w,
            m.cell(if up {
                design::EM_TIME_UP_DATE
            } else {
                design::EM_FOOTER
            }),
            &footer,
            if up { theme.muted } else { theme.text },
            TextAlign::Center,
            m.track(design::TRACK_NONE),
            design::WEIGHT_REGULAR,
        );
    }
}

// --- Production message: a stage-only overlay (dim + a gold-framed note). ---
fn push_message_overlay(
    frame: &mut Frame,
    msg: &str,
    theme: &StageTheme,
    m: &Metrics,
    w: u32,
    h: u32,
) {
    // Dim the scene behind the note (solid, non-flashing).
    fill(frame, 0, 0, w, h, Rgba::new(4, 6, 12, 190));

    let bx = m.hx(design::X_CARD);
    let bw = m.hw(design::W_CARD);
    let by = m.vy(design::Y_CARD);
    let bh = m.vh(design::H_CARD);
    surface(
        frame,
        bx,
        by,
        bw,
        bh,
        theme.accent_soft,
        theme.accent,
        m.stroke(design::B_CARD),
        m.stroke(design::R_CARD),
    );

    // The MESSAGE FROM PRODUCTION chip. Figma draws it as gold-on-WHITE, which measures
    // 2.04:1 and fails AA at every size; the inversion below (near-black on the gold token)
    // is the accessible form of the same chip at 11.19:1, and is what ships. See the audit's
    // A11Y-CONFLICT row — the frame is what is wrong here, not this.
    let chip_px = m.cell(design::EM_MESSAGE_CHIP);
    let chip_track = m.track(design::TRACK_1_5);
    let ctxt = "MESSAGE FROM PRODUCTION";
    let cw = text_width(ctxt, chip_px, chip_track) + chip_px;
    let ch = m.vh(design::H_MESSAGE_CHIP).max(chip_px + chip_px / 4);
    let cx = bx + (bw as i32 - cw as i32) / 2;
    let cy = by + m.vh(design::PT_CARD) as i32;
    pill(frame, cx, cy, cw, ch, theme.accent, theme.accent, 0);
    line(
        frame,
        cx,
        cy + (chip_px / 4) as i32,
        cw,
        chip_px,
        ctxt,
        theme.background,
        TextAlign::Center,
        chip_track,
        design::WEIGHT_BOLD,
    );

    // The message text — bold, LARGE (a production note the speaker cannot miss), auto-fit
    // within the box. The ceiling is the region height itself (not the usual 20% cap), so a
    // short message fills the box the way the design shows; a long one shrinks to fit.
    // The body fills the card below the chip, inset by the design's 52px side padding.
    //
    // It deliberately runs to the card's bottom edge rather than stopping at the design's
    // `pb 30`. The frame allots the body a 68px text box for a 56px em, but this renderer is
    // handed a LINE BOX and derives the glyph size as `line_box × 0.72`, so the same 56px em
    // needs 78px — 10px more than the card's own arithmetic leaves. The extra is line-box
    // leading, not ink: the glyphs still sit inside the padded area. Clamping the region
    // instead would silently render the note at ~38px where the design says 56px.
    let body_top = cy + ch as i32 + m.vh(design::GAP_CARD) as i32;
    let mrect = Rect::new(
        bx + m.hw(design::PX_CARD) as i32,
        body_top,
        bw.saturating_sub(m.hw(design::PX_CARD) * 2),
        ((by + bh as i32) - body_top).max(1) as u32,
    );
    let max_cell = m.cell(design::EM_MESSAGE_BODY_CAP).min(mrect.h.max(1));
    for layer in autofit_layers(
        &[msg],
        mrect,
        max_cell,
        STAGE_LINE_HEIGHT,
        TextAlign::Center,
        VAlign::Top,
        theme.text,
        Fit::ShrinkToFit,
        stage_font(),
        700,
        AUTOFIT_TRACKING,
    ) {
        frame.push(layer);
    }
}

/// Compose the display-identify overlay: `number` high-contrast markers on a
/// distinctive `background`, so an operator can tell which physical display is which
/// (FR-040). Theme-agnostic so it can overlay any output.
pub fn compose_identify(
    number: u32,
    background: Rgba,
    marker: Rgba,
    width: u32,
    height: u32,
) -> Frame {
    let mut frame = Frame::new(width, height).with_background(background);
    if width == 0 || height == 0 {
        return frame;
    }
    let count = number.max(1);
    let marker_w = ((width as f64 * 0.05) as u32).max(1);
    let marker_h = ((height as f64 * 0.30) as u32).max(1);
    let gap = (marker_w / 2).max(1);
    let stride = marker_w + gap;
    let total_w = count.saturating_mul(stride).saturating_sub(gap);
    let start_x = (width.saturating_sub(total_w) / 2) as i32;
    let y = (height.saturating_sub(marker_h) / 2) as i32;
    for i in 0..count {
        let x = start_x + (i.saturating_mul(stride)) as i32;
        if (x.max(0) as u32).saturating_add(marker_w) > width {
            break; // ran out of room
        }
        frame.push(Layer::Fill {
            rect: Rect::new(x, y, marker_w, marker_h),
            color: marker,
        });
    }
    frame
}

/// A stage/confidence output surface (its own engine + readback). Owns the operator-chosen
/// [`StageTemplate`] and production message so [`update`](Self::update) — driven every
/// stage refresh from the controller — stays a simple `(current, next, timer)` call.
pub struct StageDisplay {
    width: u32,
    height: u32,
    theme: StageTheme,
    template: StageTemplate,
    message: Option<String>,
    context: StageContext,
    engine: Engine,
}

impl StageDisplay {
    pub fn new(width: u32, height: u32, theme: StageTheme) -> Self {
        StageDisplay {
            width: width.clamp(1, selahcue_engine::raster::MAX_DIMENSION),
            height: height.clamp(1, selahcue_engine::raster::MAX_DIMENSION),
            theme,
            template: StageTemplate::default(),
            message: None,
            context: StageContext::default(),
            engine: Engine::new(width, height),
        }
    }

    /// The stage template the confidence monitor is rendering.
    pub fn template(&self) -> StageTemplate {
        self.template
    }

    /// Choose the stage template (Worship / Scripture / Timer-only). The caller re-`update`s.
    pub fn set_template(&mut self, template: StageTemplate) {
        self.template = template;
    }

    /// The current production message shown on the confidence monitor, if any.
    pub fn message(&self) -> Option<&str> {
        self.message.as_deref()
    }

    /// Set (or clear, with a blank string) the production message. Bounded to
    /// [`MAX_STAGE_MESSAGE_LEN`] chars (no-leak); a blank message clears the overlay.
    pub fn set_message(&mut self, message: &str) {
        let m = message.trim();
        self.message = if m.is_empty() {
            None
        } else {
            Some(m.chars().take(MAX_STAGE_MESSAGE_LEN).collect())
        };
    }

    /// The wall-clock snapshot the confidence monitor renders (header/footer chrome), if any.
    /// Compared by the controller so the monitor only re-composes when the value changes.
    pub fn clock(&self) -> Option<&WallClock> {
        self.context.clock.as_ref()
    }

    /// Set (or clear, with `None`) the wall-clock snapshot. The desktop backend pushes the
    /// current local date/time here each refresh; composition itself stays clock-free.
    pub fn set_clock(&mut self, clock: Option<WallClock>) {
        self.context.clock = clock;
    }

    /// The live song's stanza position (1-based `(index, total)` → `Verse 2 of 4`), if any.
    /// Compared by the controller so the monitor only re-composes when it changes.
    pub fn song_position(&self) -> Option<(u16, u16)> {
        self.context.song_position
    }

    /// Set (or clear, with `None`) the live song's stanza position for the worship header.
    /// Derived by the controller from the live plan item; `None` for non-song items.
    pub fn set_song_position(&mut self, position: Option<(u16, u16)>) {
        self.context.song_position = position;
    }

    /// The stage text scale actually in effect (permille; 1000 = the Design 2.0 sizes),
    /// already clamped to [`STAGE_TEXT_SCALE_MIN`]..=[`STAGE_TEXT_SCALE_MAX`].
    pub fn text_scale(&self) -> u16 {
        self.context.clamped_text_scale()
    }

    /// Set the stage text scale (NFR-020's configurable large size). Out-of-range values are
    /// clamped rather than rejected — an operator dragging a slider past the end must not be
    /// able to render the confidence monitor unreadable, and the composer must never divide
    /// by a zero cell.
    pub fn set_text_scale(&mut self, permille: u16) {
        self.context.text_scale_permille =
            permille.clamp(STAGE_TEXT_SCALE_MIN, STAGE_TEXT_SCALE_MAX);
    }

    /// Update the monitor from the current live state (`timer` = `None` when no timer
    /// is running), laid out by the current template with any production message overlaid.
    pub fn update(
        &mut self,
        current: Option<&Slide>,
        next: Option<&Slide>,
        timer: Option<&TimerView>,
    ) {
        let frame = compose_stage(
            current,
            next,
            timer,
            self.template,
            self.message.as_deref(),
            &self.context,
            &self.theme,
            self.width,
            self.height,
        );
        self.engine.apply(EngineCommand::SetScene { frame });
    }

    /// Show a pairing-invite QR on this output (FR-086). Returns `false` (output
    /// unchanged) if the data cannot be encoded.
    pub fn show_qr(&mut self, data: &str) -> bool {
        match crate::qr::compose_qr(data, self.width, self.height) {
            Some(frame) => {
                self.engine.apply(EngineCommand::SetScene { frame });
                true
            }
            None => false,
        }
    }

    /// Show the display-identify overlay (FR-040).
    pub fn identify(&mut self, number: u32) {
        let frame = compose_identify(
            number,
            self.theme.identify_bg,
            self.theme.identify_marker,
            self.width,
            self.height,
        );
        self.engine.apply(EngineCommand::SetScene { frame });
    }

    /// The current readback.
    pub fn output(&self) -> &FrameBuffer {
        self.engine.output()
    }
}
