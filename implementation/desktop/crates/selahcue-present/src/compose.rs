//! Compose a [`Slide`] + [`Theme`] into an engine [`Frame`] (FR-009).
//!
//! Text is laid out as coloured bars within the safe area — consistent with the
//! engine seam's model (the headless backend reasons about coverage/luminance, not
//! glyph shapes; the wgpu backend renders real glyphs into the same layout later).

use crate::slide::{Slide, Theme};
use crate::stage::TimerView;
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

// Timer-bar colours (match the stage monitor's green/amber/red state tokens).
const TIMER_TRACK: Rgba = Rgba::rgb(30, 34, 44);
const TIMER_OK: Rgba = Rgba::rgb(31, 176, 122);
const TIMER_WARN: Rgba = Rgba::rgb(224, 168, 0);
const TIMER_ALERT: Rgba = Rgba::rgb(224, 32, 32);

/// Fraction of the reference height used per text line, and the gap between lines.
const LINE_HEIGHT_FRAC: f64 = 0.10;
const LINE_GAP_FRAC: f64 = 0.03;

/// Line sizing derived from a reference height.
pub(crate) struct LineMetrics {
    pub line_h: u32,
    pub gap: u32,
}

impl LineMetrics {
    /// Metrics scaled to a reference height (a frame or a sub-region).
    pub(crate) fn for_height(reference: u32) -> Self {
        LineMetrics {
            line_h: ((reference as f64 * LINE_HEIGHT_FRAC) as u32).max(1),
            gap: (reference as f64 * LINE_GAP_FRAC) as u32,
        }
    }
}

/// Lay out text `lines` as [`Layer::Text`] within `region` (top-anchored), never
/// crossing the region's bottom edge. Shared by full-slide and confidence-region
/// composition; the rasterizer draws real glyphs, clipped to each line's rect.
pub(crate) fn layout_lines<'a>(
    lines: impl Iterator<Item = &'a str>,
    text: Rgba,
    region: Rect,
    metrics: &LineMetrics,
) -> Vec<Layer> {
    let mut layers = Vec::new();
    if region.w == 0 || region.h == 0 || metrics.line_h == 0 {
        return layers;
    }
    let bottom = region.y.saturating_add(region.h as i32);
    let mut y = region.y;
    for line in lines {
        // Stop before a line would cross the region's bottom (symmetric insets).
        if y.saturating_add(metrics.line_h as i32) > bottom {
            break;
        }
        let trimmed = line.trim();
        if !trimmed.is_empty() {
            layers.push(Layer::Text {
                rect: Rect::new(region.x, y, region.w, metrics.line_h),
                text: trimmed.to_string(),
                px: metrics.line_h,
                color: text,
            });
        }
        y = y.saturating_add((metrics.line_h + metrics.gap) as i32);
    }
    layers
}

/// Render a slide over its theme into a frame of `width×height`.
pub fn compose_slide(slide: &Slide, theme: &Theme, width: u32, height: u32) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if slide.is_blank() {
        return frame; // background only
    }
    let margin_x = (width as f64 * theme.safe_margin()) as u32;
    let margin_y = (height as f64 * theme.safe_margin()) as u32;
    let safe_w = width.saturating_sub(margin_x.saturating_mul(2)).max(1);
    let safe_h = height.saturating_sub(margin_y.saturating_mul(2));
    let region = Rect::new(margin_x as i32, margin_y as i32, safe_w, safe_h);
    let metrics = LineMetrics::for_height(height);
    for layer in layout_lines(slide.lines(), theme.text, region, &metrics) {
        frame.push(layer);
    }
    frame
}

/// A convenience: the safe-area text colour a composed slide uses.
pub fn text_color(theme: &Theme) -> Rgba {
    theme.text
}

/// Format a whole-second count as `M:SS`.
fn format_clock(secs: u32) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
}

fn timer_color(view: &TimerView) -> Rgba {
    if view.time_up {
        TIMER_ALERT
    } else if view.warn {
        TIMER_WARN
    } else {
        TIMER_OK
    }
}

/// Layers for a timer bar across the **bottom** strip of a `width×height` output: a dim
/// track, a state-coloured progress fill (drains as a countdown runs; full-width alert on
/// TIME UP), and the remaining/elapsed time (or `TIME UP`) as text.
pub(crate) fn timer_bar_layers(view: &TimerView, width: u32, height: u32) -> Vec<Layer> {
    let mut layers = Vec::new();
    if width == 0 || height == 0 {
        return layers;
    }
    let bar_h = ((height as f64 * 0.07) as u32).max(1);
    let top = (height - bar_h) as i32;

    layers.push(Layer::Fill {
        rect: Rect::new(0, top, width, bar_h),
        color: TIMER_TRACK,
    });
    let fill_w = if view.time_up {
        width
    } else {
        ((width as f64 * view.progress).round() as u32).min(width)
    };
    if fill_w > 0 {
        layers.push(Layer::Fill {
            rect: Rect::new(0, top, fill_w, bar_h),
            color: timer_color(view),
        });
    }

    let label = if view.time_up {
        "TIME UP".to_string()
    } else {
        format_clock(view.remaining_secs.unwrap_or(view.elapsed_secs))
    };
    let px = ((bar_h as f64 * 0.7) as u32).max(1).min(bar_h);
    let ty = top + ((bar_h.saturating_sub(px)) / 2) as i32;
    layers.push(Layer::Text {
        rect: Rect::new((width as f64 * 0.04) as i32, ty, width, px),
        text: label,
        px,
        color: Rgba::WHITE,
    });
    layers
}

/// Compose the **live** output: the (optional) live slide over the theme, plus a timer
/// bar overlay when a timer is active. Used by the presenter so a running countdown ticks
/// onto the audience/program output without disturbing the staged Preview.
pub fn compose_live(
    slide: Option<&Slide>,
    theme: &Theme,
    width: u32,
    height: u32,
    timer: Option<&TimerView>,
) -> Frame {
    let mut frame = match slide {
        Some(s) => compose_slide(s, theme, width, height),
        None => Frame::new(width, height).with_background(theme.background),
    };
    if let Some(view) = timer {
        for layer in timer_bar_layers(view, width, height) {
            frame.push(layer);
        }
    }
    frame
}
