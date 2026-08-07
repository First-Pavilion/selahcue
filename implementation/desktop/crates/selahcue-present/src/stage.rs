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
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba, TextAlign, TextStyle};
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

/// Colours for the stage monitor (high-contrast; the timer colours signal state).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StageTheme {
    pub background: Rgba,
    pub text: Rgba,
    /// Secondary / label ink (the "NEXT" chip, the timer caption, the next line).
    pub muted: Rgba,
    /// Accent ink (scripture reference + the production-message frame). Gold.
    pub accent: Rgba,
    /// A slightly-raised panel fill (the scripture countdown panel, the message box).
    pub panel: Rgba,
    /// Dim track behind the timer progress bar.
    pub track: Rgba,
    /// Timer running with comfortable time remaining.
    pub timer_ok: Rgba,
    /// Timer within the warning threshold.
    pub timer_warn: Rgba,
    /// Timer at/over TIME UP.
    pub timer_alert: Rgba,
    /// A soft red wash for the TIME-UP region/screen (solid, never flashing — WCAG 2.3.1).
    pub alert_wash: Rgba,
    /// Background of the identify overlay.
    pub identify_bg: Rgba,
    /// Marker colour on the identify overlay.
    pub identify_marker: Rgba,
}

impl StageTheme {
    /// A dark, high-contrast default (green/amber/red timer per the design tokens).
    pub fn dark() -> Self {
        StageTheme {
            background: Rgba::rgb(6, 8, 14),
            text: Rgba::WHITE,
            muted: Rgba::rgb(0x8a, 0x93, 0xa3),
            accent: Rgba::rgb(0xf2, 0xb8, 0x4b), // gold #f2b84b
            panel: Rgba::rgb(0x10, 0x14, 0x1e),
            track: Rgba::rgb(30, 34, 44),
            // Semantic inks from the canonical token set (one meaning per colour
            // on every surface): green = on track, amber = warning, red = up.
            timer_ok: crate::tokens::PREVIEW.ink,
            timer_warn: crate::tokens::WARN.ink,
            timer_alert: crate::tokens::LIVE.ink,
            alert_wash: Rgba::rgb(0x2a, 0x14, 0x16), // LIVE_SOFT
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

/// Line-height multiplier for the confidence monitor (≈ the historical line+gap ratio,
/// 0.13 / 0.10), so a short line keeps the familiar spacing and a long verse still fits.
const STAGE_LINE_HEIGHT: f64 = 1.3;

/// The design (ceiling) cell height for a confidence region — a few large lines (≈ 20% of
/// the region height, the historical `line_h`); auto-fit shrinks below this for longer content.
fn region_max_cell(region: Rect) -> u32 {
    ((region.h as f64 * 0.2) as u32).max(1)
}

/// Format a whole-second count as `M:SS` for the timer readout.
fn format_clock(secs: u32) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
}

/// Compose the stage/confidence scene from the current live state, laid out by the chosen
/// [`StageTemplate`] and with an optional operator `message` overlaid (Figma 373-375 / spec
/// 375-139). `timer` is the active timer (`None` when none is running). The confidence
/// monitor always uses the bundled default font (deterministic — it is the speaker's view,
/// not the themed audience output). The time-of-day clock is drawn by the desktop backend.
#[allow(clippy::too_many_arguments)]
pub fn compose_stage(
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    template: StageTemplate,
    message: Option<&str>,
    theme: &StageTheme,
    width: u32,
    height: u32,
) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if width == 0 || height == 0 {
        return frame;
    }
    match template {
        StageTemplate::Worship => {
            compose_worship(&mut frame, current, next, timer, theme, width, height)
        }
        StageTemplate::Scripture => {
            compose_scripture(&mut frame, current, next, timer, theme, width, height)
        }
        StageTemplate::TimerOnly => compose_timer_only(&mut frame, timer, theme, width, height),
    }
    // The production message is a stage-only overlay (never the audience) — it dims the
    // scene behind a gold-framed note so the speaker cannot miss it.
    if let Some(msg) = message {
        let msg = msg.trim();
        if !msg.is_empty() {
            push_message_overlay(&mut frame, msg, theme, width, height);
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

/// A single line of stage CHROME — labels, the timer readout, the scripture reference, the
/// message chip. All of it is **bold** (weight 700) to match the confidence-monitor design
/// (Figma 373-375): heavy, legible at a distance. The bundled Noto Sans is single-weight, so
/// this is a deterministic embolden — the same face the themed audience output uses for bold.
#[allow(clippy::too_many_arguments)]
fn line(f: &mut Frame, x: i32, y: i32, w: u32, px: u32, text: &str, color: Rgba, align: TextAlign) {
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
        font: None,
        style: Some(TextStyle {
            weight: 700,
            letter_spacing_px: 0,
        }),
    });
}

/// A rough single-line advance for the bundled default font (≈ 0.6 em) — good enough to
/// size a chip; exact glyph metrics are not needed for a status pill.
fn text_width(text: &str, px: u32) -> u32 {
    ((text.chars().count() as f64) * (px as f64) * 0.6).ceil() as u32
}

/// A small filled pill with a left label; returns its total width so the caller can flow
/// content after it.
fn chip(f: &mut Frame, x: i32, y: i32, text: &str, px: u32, bg: Rgba, fg: Rgba) -> u32 {
    let px = px.max(1);
    let pad = (px as f64 * 0.5) as u32;
    let w = text_width(text, px) + pad * 2;
    let h = px + pad;
    fill(f, x, y, w, h, bg);
    line(
        f,
        x + pad as i32,
        y + (pad / 2) as i32,
        w,
        px,
        text,
        fg,
        TextAlign::Left,
    );
    w
}

/// A small solid status dot (font-safe — avoids relying on a `●` glyph in the bundled font).
fn dot(f: &mut Frame, x: i32, y: i32, d: u32, color: Rgba) {
    fill(f, x, y, d.max(1), d.max(1), color);
}

/// Auto-fit a slide's full text into `region` (word-wrap + shrink-to-fit so the speaker
/// sees EVERYTHING, never truncated — parity with the audience output).
fn content_region(
    f: &mut Frame,
    slide: Option<&Slide>,
    region: Rect,
    align: TextAlign,
    color: Rgba,
    weight: u16,
) {
    let Some(slide) = slide else {
        return;
    };
    let lines: Vec<&str> = slide.lines().collect();
    let max_cell = region_max_cell(region);
    for layer in autofit_layers(
        &lines,
        region,
        max_cell,
        STAGE_LINE_HEIGHT,
        align,
        VAlign::Top,
        color,
        Fit::ShrinkToFit,
        None,
        weight,
        0,
    ) {
        f.push(layer);
    }
}

/// The timer readout for a template: `TIME UP` when over, else `M:SS` remaining / elapsed.
fn timer_readout(t: &TimerView) -> String {
    if t.time_up {
        "TIME UP".to_string()
    } else {
        format_clock(t.remaining_secs.unwrap_or(t.elapsed_secs))
    }
}

// --- Worship: lyric now / next + a bottom timer bar. TIME UP tints the bar only. ---
fn compose_worship(
    frame: &mut Frame,
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    // Current lyric — the large centre band.
    let cur = Rect::new(
        (w as f64 * 0.06) as i32,
        (h as f64 * 0.10) as i32,
        (w as f64 * 0.88) as u32,
        (h as f64 * 0.48) as u32,
    );
    content_region(frame, current, cur, TextAlign::Center, theme.text, 700);

    // NEXT chip + the coming line (muted).
    if next.is_some() {
        let ny = (h as f64 * 0.62) as i32;
        let chip_px = ((h as f64 * 0.030) as u32).max(1);
        let cw = chip(
            frame,
            (w as f64 * 0.06) as i32,
            ny,
            "NEXT",
            chip_px,
            theme.track,
            theme.muted,
        );
        let nx = (w as f64 * 0.06) as i32 + cw as i32 + (w as f64 * 0.015) as i32;
        let nrect = Rect::new(
            nx,
            ny,
            (w as f64 * 0.94) as u32 - (nx.max(0) as u32),
            (h as f64 * 0.18) as u32,
        );
        content_region(frame, next, nrect, TextAlign::Left, theme.muted, 400);
    }

    // Bottom timer bar. TIME UP washes only this region red (spec: worship = region only).
    let bar_h = ((h as f64 * 0.15) as u32).max(1);
    let bar_y = (h - bar_h) as i32;
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    fill(
        frame,
        0,
        bar_y,
        w,
        bar_h,
        if up { theme.alert_wash } else { theme.panel },
    );
    // Only an ACTIVE timer draws the caption + readout; an idle monitor shows a bare bar
    // (never mistakable for a full countdown, and no stray text over an empty stage).
    if let Some(t) = timer {
        if !t.time_up {
            // A thin progress ribbon along the top of the bar (drains as time runs out).
            let fw = ((w as f64 * t.progress).round() as u32).min(w);
            fill(
                frame,
                0,
                bar_y,
                fw,
                ((bar_h as f64 * 0.10) as u32).max(1),
                t.color(theme),
            );
        }
        let cap_px = ((bar_h as f64 * 0.26) as u32).max(1);
        line(
            frame,
            (w as f64 * 0.03) as i32,
            bar_y + (bar_h as f64 * 0.30) as i32,
            (w as f64 * 0.5) as u32,
            cap_px,
            "SERVICE TIMER",
            theme.muted,
            TextAlign::Left,
        );
        let px = ((bar_h as f64 * 0.48) as u32).max(1);
        let ty = bar_y + ((bar_h.saturating_sub(px)) / 2) as i32;
        line(
            frame,
            (w as f64 * 0.53) as i32,
            ty,
            (w as f64 * 0.44) as u32,
            px,
            &timer_readout(t),
            t.color(theme),
            TextAlign::Right,
        );
    }
}

// --- Scripture: verse + next on the left, a countdown panel on the right. TIME UP tints
// the panel only. ---
fn compose_scripture(
    frame: &mut Frame,
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    let hx = (w as f64 * 0.04) as i32;
    let left_w = (w as f64 * 0.58) as u32;
    let lbl_px = ((h as f64 * 0.030) as u32).max(1);
    line(
        frame,
        hx,
        (h as f64 * 0.06) as i32,
        left_w,
        lbl_px,
        "STAGE · SCRIPTURE",
        theme.muted,
        TextAlign::Left,
    );

    let cur = Rect::new(
        hx,
        (h as f64 * 0.16) as i32,
        left_w,
        (h as f64 * 0.54) as u32,
    );
    content_region(frame, current, cur, TextAlign::Left, theme.text, 700);

    if next.is_some() {
        let ny = (h as f64 * 0.76) as i32;
        let chip_px = ((h as f64 * 0.028) as u32).max(1);
        let cw = chip(frame, hx, ny, "NEXT", chip_px, theme.track, theme.muted);
        let nx = hx + cw as i32 + (w as f64 * 0.012) as i32;
        let nrect = Rect::new(
            nx,
            ny,
            left_w.saturating_sub(cw + (w as f64 * 0.012) as u32),
            (h as f64 * 0.16) as u32,
        );
        content_region(frame, next, nrect, TextAlign::Left, theme.muted, 400);
    }

    // Right countdown panel.
    let px0 = (w as f64 * 0.64) as i32;
    let pw = (w as f64 * 0.32) as u32;
    let py = (h as f64 * 0.14) as i32;
    let ph = (h as f64 * 0.72) as u32;
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    let warn = timer.map(|t| t.warn).unwrap_or(false);
    fill(
        frame,
        px0,
        py,
        pw,
        ph,
        if up { theme.alert_wash } else { theme.panel },
    );

    // Status pill (dot + label), centred near the top of the panel.
    let (pill, pill_col) = if up {
        ("TIME UP", theme.timer_alert)
    } else if warn {
        ("HURRY", theme.timer_warn)
    } else {
        ("ON TIME", theme.timer_ok)
    };
    let pill_px = ((h as f64 * 0.024) as u32).max(1);
    let pill_w = text_width(pill, pill_px) + pill_px;
    let pill_x = px0 + (pw as i32 - pill_w as i32) / 2;
    dot(
        frame,
        pill_x,
        py + (ph as f64 * 0.12) as i32,
        (pill_px as f64 * 0.7) as u32,
        pill_col,
    );
    line(
        frame,
        pill_x + pill_px as i32,
        py + (ph as f64 * 0.11) as i32,
        pill_w,
        pill_px,
        pill,
        pill_col,
        TextAlign::Left,
    );

    line(
        frame,
        px0,
        py + (ph as f64 * 0.26) as i32,
        pw,
        ((h as f64 * 0.020) as u32).max(1),
        "TIME LEFT",
        theme.muted,
        TextAlign::Center,
    );
    if let Some(t) = timer {
        let big = ((h as f64 * 0.16) as u32).max(1);
        line(
            frame,
            px0,
            py + (ph as f64 * 0.40) as i32,
            pw,
            big,
            &timer_readout(t),
            t.color(theme),
            TextAlign::Center,
        );
    }
}

// --- Timer-only: a big centred countdown, nothing else. TIME UP takes the whole screen. ---
fn compose_timer_only(
    frame: &mut Frame,
    timer: Option<&TimerView>,
    theme: &StageTheme,
    w: u32,
    h: u32,
) {
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    if up {
        // Full-screen solid red wash (never flashing — WCAG 2.3.1).
        fill(frame, 0, 0, w, h, theme.alert_wash);
    }
    line(
        frame,
        (w as f64 * 0.04) as i32,
        (h as f64 * 0.06) as i32,
        w,
        ((h as f64 * 0.030) as u32).max(1),
        "SERVICE TIMER",
        theme.muted,
        TextAlign::Left,
    );
    match timer {
        Some(t) if t.time_up => {
            line(
                frame,
                0,
                (h as f64 * 0.34) as i32,
                w,
                ((h as f64 * 0.28) as u32).max(1),
                "TIME UP",
                theme.timer_alert,
                TextAlign::Center,
            );
        }
        Some(t) => {
            line(
                frame,
                0,
                (h as f64 * 0.31) as i32,
                w,
                ((h as f64 * 0.36) as u32).max(1),
                &timer_readout(t),
                t.color(theme),
                TextAlign::Center,
            );
        }
        None => {
            line(
                frame,
                0,
                (h as f64 * 0.37) as i32,
                w,
                ((h as f64 * 0.20) as u32).max(1),
                "--:--",
                theme.muted,
                TextAlign::Center,
            );
        }
    }
}

// --- Production message: a stage-only overlay (dim + a gold-framed note). ---
fn push_message_overlay(frame: &mut Frame, msg: &str, theme: &StageTheme, w: u32, h: u32) {
    // Dim the scene behind the note (solid, non-flashing).
    fill(frame, 0, 0, w, h, Rgba::new(4, 6, 12, 190));

    let bx = (w as f64 * 0.10) as i32;
    let bw = (w as f64 * 0.80) as u32;
    let by = (h as f64 * 0.34) as i32;
    let bh = (h as f64 * 0.30) as u32;
    let border = ((w as f64 * 0.004) as u32).max(2);
    fill(frame, bx, by, bw, bh, theme.accent); // gold frame
    fill(
        frame,
        bx + border as i32,
        by + border as i32,
        bw.saturating_sub(border * 2),
        bh.saturating_sub(border * 2),
        theme.panel,
    ); // inner

    // Gold chip: MESSAGE FROM PRODUCTION.
    let chip_px = ((h as f64 * 0.030) as u32).max(1);
    let ctxt = "MESSAGE FROM PRODUCTION";
    let cw = text_width(ctxt, chip_px) + chip_px;
    let cx = bx + (bw as i32 - cw as i32) / 2;
    let cy = by + (bh as f64 * 0.14) as i32;
    fill(frame, cx, cy, cw, chip_px + chip_px / 2, theme.accent);
    line(
        frame,
        cx,
        cy + (chip_px / 4) as i32,
        cw,
        chip_px,
        ctxt,
        theme.background,
        TextAlign::Center,
    );

    // The message text — bold, LARGE (a production note the speaker cannot miss), auto-fit
    // within the box. The ceiling is the region height itself (not the usual 20% cap), so a
    // short message fills the box the way the design shows; a long one shrinks to fit.
    let mrect = Rect::new(
        bx + (bw as f64 * 0.06) as i32,
        by + (bh as f64 * 0.40) as i32,
        (bw as f64 * 0.88) as u32,
        (bh as f64 * 0.48) as u32,
    );
    let max_cell = mrect.h;
    for layer in autofit_layers(
        &[msg],
        mrect,
        max_cell,
        STAGE_LINE_HEIGHT,
        TextAlign::Center,
        VAlign::Top,
        theme.text,
        Fit::ShrinkToFit,
        None,
        700,
        0,
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
