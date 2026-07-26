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
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};
use std::time::{Duration, Instant};

/// Colours for the stage monitor (high-contrast; the timer colours signal state).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StageTheme {
    pub background: Rgba,
    pub text: Rgba,
    /// Dim track behind the timer progress bar.
    pub track: Rgba,
    /// Timer running with comfortable time remaining.
    pub timer_ok: Rgba,
    /// Timer within the warning threshold.
    pub timer_warn: Rgba,
    /// Timer at/over TIME UP.
    pub timer_alert: Rgba,
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
            track: Rgba::rgb(30, 34, 44),
            // Semantic inks from the canonical token set (one meaning per colour
            // on every surface): green = on track, amber = warning, red = up.
            timer_ok: crate::tokens::PREVIEW.ink,
            timer_warn: crate::tokens::WARN.ink,
            timer_alert: crate::tokens::LIVE.ink,
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

/// Compose the stage/confidence scene from the current live state. `timer` is the
/// active timer (`None` when none is running — the strip then shows an empty track,
/// so an idle monitor can never be mistaken for a full countdown).
pub fn compose_stage(
    current: Option<&Slide>,
    next: Option<&Slide>,
    timer: Option<&TimerView>,
    theme: &StageTheme,
    width: u32,
    height: u32,
) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if width == 0 || height == 0 {
        return frame;
    }

    // --- Timer strip (top): dim track + a state-coloured progress fill + a large
    // numeric readout the speaker can read at a distance. ---
    let bar_h = ((height as f64 * 0.15) as u32).max(1);
    frame.push(Layer::Fill {
        rect: Rect::new(0, 0, width, bar_h),
        color: theme.track,
    });
    if let Some(timer) = timer {
        // Countdown drains the fill as time runs out; TIME UP fills the whole bar in
        // the alert colour so it is unmissable (overrun).
        let fill_w = if timer.time_up {
            width
        } else {
            ((width as f64 * timer.progress).round() as u32).min(width)
        };
        if fill_w > 0 {
            frame.push(Layer::Fill {
                rect: Rect::new(0, 0, fill_w, bar_h),
                color: timer.color(theme),
            });
        }
        // The readout: remaining time (countdown), elapsed (count-up), or TIME UP.
        let label = if timer.time_up {
            "TIME UP".to_string()
        } else {
            format_clock(timer.remaining_secs.unwrap_or(timer.elapsed_secs))
        };
        let px = ((bar_h as f64 * 0.6) as u32).max(1).min(bar_h);
        let ty = ((bar_h.saturating_sub(px)) / 2) as i32;
        frame.push(Layer::Text {
            rect: Rect::new((width as f64 * 0.03) as i32, ty, width, px),
            text: label,
            px,
            color: theme.text,
            align: selahcue_engine::scene::TextAlign::Left,
            // The confidence monitor always uses the bundled default font (deterministic).
            font: None,
        });
    }

    // --- Current line (large centre band). ---
    let current_top = bar_h as i32;
    let current_h = ((height as f64 * 0.50) as u32).max(1);
    push_region(&mut frame, current, theme, width, current_top, current_h);

    // --- Next line (smaller band below). ---
    let next_top = current_top + current_h as i32;
    let next_h = ((height as f64 * 0.25) as u32).max(1);
    push_region(&mut frame, next, theme, width, next_top, next_h);

    // --- Clock strip (bottom): a placeholder bar; the wgpu backend draws the time. ---
    let clock_top = (height as i32) - ((height as f64 * 0.08) as i32).max(1);
    let clock_h = (height - clock_top.max(0) as u32).max(1);
    frame.push(Layer::Fill {
        rect: Rect::new(0, clock_top.max(0), width, clock_h),
        color: theme.track,
    });

    frame
}

fn push_region(
    frame: &mut Frame,
    slide: Option<&Slide>,
    theme: &StageTheme,
    width: u32,
    top: i32,
    height: u32,
) {
    let Some(slide) = slide else {
        return; // empty region: background only
    };
    let margin = (width as f64 * 0.06) as u32;
    let region = Rect::new(
        margin as i32,
        top + (height as f64 * 0.1) as i32,
        width.saturating_sub(margin.saturating_mul(2)).max(1),
        ((height as f64 * 0.8) as u32).max(1),
    );
    // Auto-fit the whole slide (reference + full verse / all stanza lines) into the
    // confidence region — word-wrap to the width + shrink the font so the speaker sees
    // EVERYTHING, never truncated or clipped (parity with the audience output).
    let lines: Vec<&str> = slide.lines().collect();
    let max_cell = region_max_cell(region);
    for layer in autofit_layers(
        &lines,
        region,
        max_cell,
        STAGE_LINE_HEIGHT,
        selahcue_engine::scene::TextAlign::Left,
        VAlign::Top,
        theme.text,
        Fit::ShrinkToFit,
        None, // the confidence monitor always uses the bundled default font
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

/// A stage/confidence output surface (its own engine + readback).
pub struct StageDisplay {
    width: u32,
    height: u32,
    theme: StageTheme,
    engine: Engine,
}

impl StageDisplay {
    pub fn new(width: u32, height: u32, theme: StageTheme) -> Self {
        StageDisplay {
            width: width.clamp(1, selahcue_engine::raster::MAX_DIMENSION),
            height: height.clamp(1, selahcue_engine::raster::MAX_DIMENSION),
            theme,
            engine: Engine::new(width, height),
        }
    }

    /// Update the monitor from the current live state (`timer` = `None` when no timer
    /// is running — the strip shows an empty track).
    pub fn update(
        &mut self,
        current: Option<&Slide>,
        next: Option<&Slide>,
        timer: Option<&TimerView>,
    ) {
        let frame = compose_stage(current, next, timer, &self.theme, self.width, self.height);
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
