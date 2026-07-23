//! Compose a [`Slide`] + [`Theme`] into an engine [`Frame`] (FR-009).
//!
//! Text is laid out as coloured bars within the safe area — consistent with the
//! engine seam's model (the headless backend reasons about coverage/luminance, not
//! glyph shapes; the wgpu backend renders real glyphs into the same layout later).

use crate::slide::{Slide, Theme};
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

/// Fraction of frame height used per text line, and the gap between lines.
const LINE_HEIGHT_FRAC: f64 = 0.10;
const LINE_GAP_FRAC: f64 = 0.03;
/// Approximate glyph advance as a fraction of the line height (for bar width).
const GLYPH_ADVANCE: f64 = 0.5;

/// Render a slide over its theme into a frame of `width×height`.
pub fn compose_slide(slide: &Slide, theme: &Theme, width: u32, height: u32) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if slide.is_blank() {
        return frame; // background only
    }

    let margin_x = (width as f64 * theme.safe_margin()) as u32;
    let margin_y = (height as f64 * theme.safe_margin()) as u32;
    let safe_w = width.saturating_sub(margin_x.saturating_mul(2)).max(1);
    // Bottom of the safe area — text must not paint below this into the overscan
    // band, symmetric with the top inset.
    let safe_bottom = height.saturating_sub(margin_y);
    let line_h = ((height as f64 * LINE_HEIGHT_FRAC) as u32).max(1);
    let gap = (height as f64 * LINE_GAP_FRAC) as u32;
    let advance = (line_h as f64 * GLYPH_ADVANCE).max(1.0) as u32;

    let mut y = margin_y;
    for line in slide.lines() {
        // Stop once the next line would cross the bottom safe boundary (or overflow).
        if y.saturating_add(line_h) > safe_bottom {
            break;
        }
        let trimmed = line.trim();
        if !trimmed.is_empty() {
            // Bar width proportional to the line length, clamped to the safe width.
            let chars = trimmed.chars().count() as u32;
            let bar_w = chars.saturating_mul(advance).clamp(1, safe_w);
            frame.push(Layer::Fill {
                rect: Rect::new(margin_x as i32, y as i32, bar_w, line_h),
                color: theme.text,
            });
        }
        y = y.saturating_add(line_h + gap);
    }
    frame
}

/// A convenience: the safe-area text colour a composed slide uses (for callers
/// that want to assert/inspect the composition).
pub fn text_color(theme: &Theme) -> Rgba {
    theme.text
}
