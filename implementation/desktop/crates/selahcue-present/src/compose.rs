//! Compose a [`Slide`] + [`Theme`] into an engine [`Frame`] (FR-009).
//!
//! Text is laid out as coloured bars within the safe area — consistent with the
//! engine seam's model (the headless backend reasons about coverage/luminance, not
//! glyph shapes; the wgpu backend renders real glyphs into the same layout later).

use crate::slide::{Slide, Theme};
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

/// Fraction of the reference height used per text line, and the gap between lines.
const LINE_HEIGHT_FRAC: f64 = 0.10;
const LINE_GAP_FRAC: f64 = 0.03;
/// Approximate glyph advance as a fraction of the line height (for bar width).
const GLYPH_ADVANCE: f64 = 0.5;

/// Line sizing derived from a reference height.
pub(crate) struct LineMetrics {
    pub line_h: u32,
    pub gap: u32,
    pub advance: u32,
}

impl LineMetrics {
    /// Metrics scaled to a reference height (a frame or a sub-region).
    pub(crate) fn for_height(reference: u32) -> Self {
        let line_h = ((reference as f64 * LINE_HEIGHT_FRAC) as u32).max(1);
        LineMetrics {
            line_h,
            gap: (reference as f64 * LINE_GAP_FRAC) as u32,
            advance: ((line_h as f64 * GLYPH_ADVANCE).max(1.0)) as u32,
        }
    }
}

/// Lay out text `lines` as bars within `region` (top-anchored), never crossing the
/// region's bottom edge. Shared by full-slide and confidence-region composition.
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
            let chars = trimmed.chars().count() as u32;
            let bar_w = chars.saturating_mul(metrics.advance).clamp(1, region.w);
            layers.push(Layer::Fill {
                rect: Rect::new(region.x, y, bar_w, metrics.line_h),
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
