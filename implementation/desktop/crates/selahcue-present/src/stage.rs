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
use selahcue_engine::scene::{FontName, Frame, Layer, Rect, Rgba, TextAlign, TextStyle};
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

/// Format a whole-second count as `M:SS` for the timer readout.
fn format_clock(secs: u32) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
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
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct StageContext {
    /// The local wall clock (date line + 12-hour time). `None` until the backend feeds it.
    pub clock: Option<WallClock>,
    /// The live stanza position as 1-based `(index, total)` → `Verse 2 of 4`. `None` for a
    /// non-song item or a single-slide item.
    pub song_position: Option<(u16, u16)>,
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

/// The stage/confidence typeface — the bundled **Inter** face (Figma 373-375). Always `Some`
/// (a valid, bundled family name); it resolves deterministically in the named-font shaper.
fn stage_font() -> Option<FontName> {
    FontName::new(selahcue_engine::raster::STAGE_FONT)
}

/// A single line of stage CHROME — labels, the timer readout, the scripture reference, the
/// message chip. All of it is **bold** (weight 700) Inter to match the confidence-monitor
/// design (Figma 373-375): heavy, legible at a distance.
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
        font: stage_font(),
        style: Some(TextStyle {
            weight: 700,
            letter_spacing_px: 0,
        }),
    });
}

/// A rough single-line advance (≈ 0.6 em) — good enough to size a chip; exact glyph metrics
/// are not needed for a status pill. **Bounded**: a pathologically long (untrusted) title or
/// line can't saturate the `f64 → u32` cast to `u32::MAX` and overflow the width SUMS the
/// callers build from it — the composer must never panic on any input.
fn text_width(text: &str, px: u32) -> u32 {
    // 4 Mpx — far beyond any renderable width (MAX_DIMENSION is 8192), yet small enough that a
    // handful of these summed stay well under u32::MAX.
    const CAP: f64 = (1u32 << 22) as f64;
    ((text.chars().count() as f64) * (px as f64) * 0.6)
        .ceil()
        .min(CAP) as u32
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

/// The violet "live song" indicator on the worship header pill (Figma 373-136). A fixed
/// accent — the confidence monitor is single-theme, so this stays deterministic.
const SONG_ACCENT: Rgba = Rgba::rgb(0x8b, 0x5c, 0xf6);

/// Auto-fit explicit `lines` into `region` (word-wrap + shrink-to-fit so the speaker sees
/// EVERYTHING, never truncated — parity with the audience output), capped at `max_cell`
/// line-box height. Templates pass a larger cap for the big lyric / verse bands than for a
/// muted status line.
#[allow(clippy::too_many_arguments)]
fn fit_lines(
    f: &mut Frame,
    lines: &[&str],
    region: Rect,
    max_cell: u32,
    align: TextAlign,
    valign: VAlign,
    color: Rgba,
    weight: u16,
) {
    if lines.is_empty() {
        return;
    }
    for layer in autofit_layers(
        lines,
        region,
        max_cell.max(1),
        STAGE_LINE_HEIGHT,
        align,
        valign,
        color,
        Fit::ShrinkToFit,
        stage_font(),
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
fn header_clock(f: &mut Frame, ctx: &StageContext, theme: &StageTheme, w: u32, h: u32) {
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
        (h as f64 * 0.05) as i32,
        (w as f64 * 0.96) as u32,
        ((h as f64 * 0.062) as u32).max(1),
        time,
        theme.text,
        TextAlign::Right,
    );
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

    // Header pill: the live song (violet dot + title). Only a real song (has lyrics) gets the
    // pill; a title-only item shows its title as the centre text instead.
    if is_song {
        if let Some(title) = title {
            let pill_px = ((h as f64 * 0.044) as u32).max(1);
            let px0 = (w as f64 * 0.04) as i32;
            let py0 = (h as f64 * 0.052) as i32;
            let pad = ((pill_px as f64) * 0.55) as u32;
            let dot_d = ((pill_px as f64) * 0.36) as u32;
            let gap = ((pill_px as f64) * 0.4) as u32;
            let title_w = text_width(title, pill_px);
            let pill_w = pad + dot_d + gap + title_w + pad;
            let pill_h = pill_px + pad;
            fill(frame, px0, py0, pill_w, pill_h, theme.track);
            dot(
                frame,
                px0 + pad as i32,
                py0 + (pill_h.saturating_sub(dot_d) / 2) as i32,
                dot_d,
                SONG_ACCENT,
            );
            line(
                frame,
                px0 + (pad + dot_d + gap) as i32,
                py0 + (pad / 2) as i32,
                title_w + pill_px,
                pill_px,
                title,
                theme.text,
                TextAlign::Left,
            );
            // Stanza position after the pill, e.g. "Verse 2 of 4".
            if let Some((i, n)) = ctx.song_position {
                let vpx = ((h as f64 * 0.040) as u32).max(1);
                line(
                    frame,
                    px0 + pill_w as i32 + (w as f64 * 0.016) as i32,
                    py0 + (pill_h.saturating_sub(vpx) / 2) as i32,
                    (w as f64 * 0.4) as u32,
                    vpx,
                    &format!("Verse {i} of {n}"),
                    theme.muted,
                    TextAlign::Left,
                );
            }
        }
    }
    header_clock(frame, ctx, theme, w, h);

    // Centre band: the current stanza (or the title for a title-only item), big + centred.
    let content: Vec<&str> = if is_song {
        body
    } else {
        title.into_iter().collect()
    };
    fit_lines(
        frame,
        &content,
        Rect::new(
            (w as f64 * 0.05) as i32,
            (h as f64 * 0.19) as i32,
            (w as f64 * 0.90) as u32,
            (h as f64 * 0.45) as u32,
        ),
        (h as f64 * 0.17) as u32,
        TextAlign::Center,
        VAlign::Middle,
        theme.text,
        700,
    );

    // The coming line (muted), a NEXT chip + the first line of the next stanza, centred.
    if let Some(nl) = next
        .map(|s| s.body.first().map(String::as_str).unwrap_or(&s.title))
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        let ny = (h as f64 * 0.68) as i32;
        let chip_px = ((h as f64 * 0.030) as u32).max(1);
        let line_px = ((h as f64 * 0.034) as u32).max(1);
        let gap = (w as f64 * 0.015) as u32;
        // Centre the (chip + gap + line) group. `chip()` draws a width of text+px (pad·2).
        let chip_w = text_width("NEXT", chip_px) + chip_px;
        let line_w = text_width(nl, line_px);
        let group_w = chip_w + gap + line_w;
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
        );
        line(
            frame,
            start_x + cw as i32 + gap as i32,
            ny + (chip_h.saturating_sub(line_px) / 2) as i32,
            line_w + line_px,
            line_px,
            nl,
            theme.muted,
            TextAlign::Left,
        );
    }

    // Footer timer band: a state dot + SERVICE TIMER and the readout. TIME UP washes only
    // this band red (spec: worship flips the timer region only, not the whole screen).
    let band_h = ((h as f64 * 0.19) as u32).max(1);
    let band_y = (h - band_h) as i32;
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    fill(
        frame,
        0,
        band_y,
        w,
        band_h,
        if up { theme.alert_wash } else { theme.panel },
    );
    // Only an ACTIVE timer draws the caption + readout; an idle monitor shows a bare band.
    if let Some(t) = timer {
        let col = if up {
            theme.timer_alert
        } else {
            t.color(theme)
        };
        let cap_px = ((band_h as f64 * 0.22) as u32).max(1);
        let cy = band_y + (band_h.saturating_sub(cap_px) / 2) as i32;
        let dot_d = ((cap_px as f64) * 0.55) as u32;
        dot(
            frame,
            (w as f64 * 0.04) as i32,
            cy + (cap_px.saturating_sub(dot_d) / 2) as i32,
            dot_d,
            col,
        );
        line(
            frame,
            (w as f64 * 0.04) as i32 + dot_d as i32 + (w as f64 * 0.012) as i32,
            cy,
            (w as f64 * 0.5) as u32,
            cap_px,
            "SERVICE TIMER",
            theme.muted,
            TextAlign::Left,
        );
        let px = ((band_h as f64 * 0.42) as u32).max(1);
        // At TIME UP the readout word pulses (the dot + band stay steady).
        let readout_col = if up {
            time_up_ink(theme, t.elapsed_secs)
        } else {
            col
        };
        line(
            frame,
            (w as f64 * 0.50) as i32,
            band_y + (band_h.saturating_sub(px) / 2) as i32,
            (w as f64 * 0.46) as u32,
            px,
            &timer_readout(t),
            readout_col,
            TextAlign::Right,
        );
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
    let hx = (w as f64 * 0.048) as i32;
    let left_w = (w as f64 * 0.60) as u32;

    // Header: the screen label + the wall clock.
    line(
        frame,
        hx,
        (h as f64 * 0.058) as i32,
        left_w,
        ((h as f64 * 0.050) as u32).max(1),
        "STAGE · SCRIPTURE",
        theme.muted,
        TextAlign::Left,
    );
    header_clock(frame, ctx, theme, w, h);

    // Left column: the reference (gold) then the verse body (white, left-aligned + wrapped).
    if let Some(reference) = current.map(|s| s.title.trim()).filter(|t| !t.is_empty()) {
        line(
            frame,
            hx,
            (h as f64 * 0.185) as i32,
            left_w,
            ((h as f64 * 0.062) as u32).max(1),
            &reference.to_uppercase(),
            theme.accent,
            TextAlign::Left,
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
    fit_lines(
        frame,
        &verse,
        Rect::new(
            hx,
            (h as f64 * 0.28) as i32,
            left_w,
            (h as f64 * 0.50) as u32,
        ),
        (h as f64 * 0.115) as u32,
        TextAlign::Left,
        VAlign::Top,
        theme.text,
        700,
    );

    // NEXT row (left column): the coming reference · verse, clipped to the column with an
    // ellipsis (the panel must stay clear).
    if let Some(nl) = next.and_then(scripture_next_label) {
        let ny = (h as f64 * 0.85) as i32;
        let chip_px = ((h as f64 * 0.028) as u32).max(1);
        let line_px = ((h as f64 * 0.030) as u32).max(1);
        let gap = (w as f64 * 0.012) as u32;
        let cw = chip(frame, hx, ny, "NEXT", chip_px, theme.track, theme.muted);
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
        );
    }

    // Right countdown panel (full content height). TIME UP washes the panel only.
    let px0 = (w as f64 * 0.68) as i32;
    let pw = w.saturating_sub(px0.max(0) as u32);
    let py = (h as f64 * 0.142) as i32;
    let ph = h.saturating_sub(py.max(0) as u32);
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

    // Status pill (a filled chip: dot + label) centred in the panel.
    let (pill, pill_col) = if up {
        ("TIME UP", theme.timer_alert)
    } else if warn {
        ("HURRY", theme.timer_warn)
    } else {
        ("ON TIME", theme.timer_ok)
    };
    // At TIME UP the pill LABEL pulses each second; the dot + panel wash stay steady.
    let elapsed = timer.map(|t| t.elapsed_secs).unwrap_or(0);
    let pill_label_col = if up {
        time_up_ink(theme, elapsed)
    } else {
        pill_col
    };
    let pill_px = ((h as f64 * 0.028) as u32).max(1);
    let dot_d = ((pill_px as f64) * 0.5) as u32;
    let pgap = ((pill_px as f64) * 0.4) as u32;
    let hpad = ((pill_px as f64) * 0.7) as u32;
    let label_w = text_width(pill, pill_px);
    let pill_w = hpad + dot_d + pgap + label_w + hpad;
    let pill_h = pill_px + pill_px / 2;
    let pill_x = px0 + (pw.saturating_sub(pill_w) / 2) as i32;
    let pill_y = (h as f64 * 0.37) as i32;
    fill(frame, pill_x, pill_y, pill_w, pill_h, theme.track);
    dot(
        frame,
        pill_x + hpad as i32,
        pill_y + (pill_h.saturating_sub(dot_d) / 2) as i32,
        dot_d,
        pill_col,
    );
    line(
        frame,
        pill_x + (hpad + dot_d + pgap) as i32,
        pill_y + (pill_h.saturating_sub(pill_px) / 2) as i32,
        label_w + pill_px,
        pill_px,
        pill,
        pill_label_col,
        TextAlign::Left,
    );

    // "TIME LEFT" caption + the big readout, centred in the panel.
    line(
        frame,
        px0,
        (h as f64 * 0.45) as i32,
        pw,
        ((h as f64 * 0.030) as u32).max(1),
        "TIME LEFT",
        theme.muted,
        TextAlign::Center,
    );
    if let Some(t) = timer {
        // "TIME UP" is wider than "M:SS", so it drops to a size that clears the narrow panel.
        let (txt, read_px) = if up {
            ("TIME UP".to_string(), (h as f64 * 0.11) as u32)
        } else {
            (timer_readout(t), (h as f64 * 0.22) as u32)
        };
        line(
            frame,
            px0,
            (h as f64 * 0.50) as i32,
            pw,
            read_px.max(1),
            &txt,
            if up {
                time_up_ink(theme, t.elapsed_secs)
            } else {
                t.color(theme)
            },
            TextAlign::Center,
        );
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
    if text_width(text, px) <= max_w {
        return text.to_string();
    }
    let mut kept = String::new();
    for ch in text.chars() {
        let mut candidate = kept.clone();
        candidate.push(ch);
        if text_width(&format!("{candidate}..."), px) > max_w {
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
    let clock = ctx.clock.as_ref();
    let up = timer.map(|t| t.time_up).unwrap_or(false);
    if up {
        // Full-screen solid red wash (never flashing — WCAG 2.3.1).
        fill(frame, 0, 0, w, h, theme.alert_wash);
    }

    // Header, left: the fixed screen label.
    line(
        frame,
        (w as f64 * 0.04) as i32,
        (h as f64 * 0.052) as i32,
        w,
        ((h as f64 * 0.050) as u32).max(1),
        "SERVICE TIMER",
        theme.muted,
        TextAlign::Left,
    );
    // Header, right: the wall clock (time-of-day), right-aligned to a 0.04·w margin.
    if let Some(c) = clock.filter(|c| !c.time().is_empty()) {
        line(
            frame,
            0,
            (h as f64 * 0.045) as i32,
            (w as f64 * 0.96) as u32,
            ((h as f64 * 0.068) as u32).max(1),
            c.time(),
            theme.text,
            TextAlign::Right,
        );
    }

    // Segment label above the readout — the live slide's title (e.g. "SERMON"); omitted
    // when nothing is live so the template stays a clean timer.
    if let Some(title) = current.map(|s| s.title.trim()).filter(|t| !t.is_empty()) {
        line(
            frame,
            0,
            (h as f64 * 0.27) as i32,
            w,
            ((h as f64 * 0.060) as u32).max(1),
            title,
            theme.muted,
            TextAlign::Center,
        );
    }

    // The giant readout — Inter bold at ~200px (0.49·h line box → ~0.35·h em, ×FONT_TO_LINE).
    match timer {
        Some(t) if t.time_up => {
            line(
                frame,
                0,
                (h as f64 * 0.36) as i32,
                w,
                ((h as f64 * 0.34) as u32).max(1),
                "TIME UP",
                time_up_ink(theme, t.elapsed_secs),
                TextAlign::Center,
            );
        }
        Some(t) => {
            line(
                frame,
                0,
                (h as f64 * 0.30) as i32,
                w,
                ((h as f64 * 0.49) as u32).max(1),
                &timer_readout(t),
                t.color(theme),
                TextAlign::Center,
            );
        }
        None => {
            line(
                frame,
                0,
                (h as f64 * 0.30) as i32,
                w,
                ((h as f64 * 0.49) as u32).max(1),
                "--:--",
                theme.muted,
                TextAlign::Center,
            );
        }
    }

    // Footer: the date and 12-hour time-of-day, e.g. "Sunday · August 3, 2026 · 10:42 AM".
    if let Some(c) = clock.filter(|c| !c.date().is_empty()) {
        let footer = if c.time().is_empty() {
            c.date().to_string()
        } else {
            format!("{} · {}", c.date(), c.time())
        };
        line(
            frame,
            0,
            (h as f64 * 0.80) as i32,
            w,
            ((h as f64 * 0.072) as u32).max(1),
            &footer,
            theme.text,
            TextAlign::Center,
        );
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
        stage_font(),
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
