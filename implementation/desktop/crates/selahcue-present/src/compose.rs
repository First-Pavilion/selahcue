//! Compose a [`Slide`] + [`Theme`] into an engine [`Frame`] (FR-009/FR-010).
//!
//! A theme is a slide-design template: a background plus positioned **regions**
//! (title/reference + body), each with alignment + typography. `compose_slide`
//! lays the slide's title into the title region and its body lines into the body
//! region — content is orthogonal to the theme, so re-composing the *same* slide
//! under a different theme restyles it without loss.

use crate::slide::Slide;
use crate::theme::{Band, Fit, RegionStyle, Theme, VAlign};
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba, TextAlign};

/// Fraction of the reference height used per text line, and the gap between lines.
/// (Used by the stage/confidence monitor, which has its own fixed layout.)
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
/// crossing the region's bottom edge, aligned horizontally by `align`. Shared by
/// the confidence monitor (fixed layout); themed slides use [`layout_region`].
pub(crate) fn layout_lines<'a>(
    lines: impl Iterator<Item = &'a str>,
    text: Rgba,
    region: Rect,
    metrics: &LineMetrics,
    align: TextAlign,
) -> Vec<Layer> {
    let mut layers = Vec::new();
    if region.w == 0 || region.h == 0 || metrics.line_h == 0 {
        return layers;
    }
    let bottom = region.y.saturating_add(region.h as i32);
    let mut y = region.y;
    for line in lines {
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
                align,
            });
        }
        y = y.saturating_add((metrics.line_h + metrics.gap) as i32);
    }
    layers
}

/// Lay out `lines` into a themed [`RegionStyle`] — per-region cell size, line
/// height, colour, and H+V alignment, resolution-independent. The text block is
/// V-aligned within the region. Overflow follows the region's [`Fit`]:
/// **`ShrinkToFit`** (the default) shrinks the cell so *every* line fits — nothing
/// is dropped; `Clip`/`Paginate` keep the design size and drop what overflows
/// (`Paginate` is a later slice, treated as `Clip` for now).
fn layout_region(lines: &[&str], style: &RegionStyle, width: u32, height: u32) -> Vec<Layer> {
    let non_empty: Vec<&str> = lines
        .iter()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();
    if non_empty.is_empty() {
        return Vec::new();
    }
    let rect = style.rect(width, height);
    if rect.w == 0 || rect.h == 0 {
        return Vec::new();
    }
    let lh = style.line_height();
    let design_cell = style.cell_px(height).min(rect.h).max(1);
    // For `ShrinkToFit`, size the cell so ALL `want` lines fit the region height:
    // want lines occupy `cell·((want−1)·lh + 1)` ≤ rect.h → solve for the largest
    // cell, capped at the design size (never enlarge) and floored at 1px.
    let want = non_empty.len();
    let mut cell = match style.fit {
        Fit::ShrinkToFit => {
            // Largest cell where all `want` lines fit rect.h. `span` is the block
            // height in cell-units; `safety` absorbs the per-line advance rounding
            // (`round(cell·lh)` can add up to +0.5px each) so the discrete
            // `max_lines` below actually reaches `want`. Capped at the design size.
            let span = ((want as f64 - 1.0) * lh + 1.0).max(1.0);
            let safety = (want as f64 - 1.0) * 0.5;
            let fit_cell = (((rect.h as f64) - safety) / span).floor().max(1.0) as u32;
            design_cell.min(fit_cell)
        }
        Fit::Clip | Fit::Paginate => design_cell,
    };
    // Shrink-to-fit must also fit the region WIDTH: `draw_text` never wraps, so a line
    // wider than `rect.w` at this cell would clip on the right (owner bug — long verses
    // clipped). `line_w` scales ~linearly with the cell, so scale by the width ratio;
    // iterate a few times to absorb shaping/rounding non-linearity (converges fast).
    if matches!(style.fit, Fit::ShrinkToFit) {
        for _ in 0..4 {
            let max_w = non_empty
                .iter()
                .map(|l| selahcue_engine::raster::measure_line_width(l, cell))
                .fold(0.0_f32, f32::max);
            if max_w <= rect.w as f32 || max_w <= 0.0 || cell <= 1 {
                break;
            }
            let scaled = (((cell as f32) * (rect.w as f32) / max_w).floor() as u32).max(1);
            // Guarantee progress even when the floor() rounds back to the same cell.
            cell = if scaled >= cell { cell - 1 } else { scaled };
        }
    }
    // Per-line vertical advance (cell scaled by the line-height multiplier).
    let advance = ((cell as f64) * lh).round().max(cell as f64) as u32;
    // Lines that fit at this cell size (== want under ShrinkToFit; a cap under Clip).
    let max_lines = ((rect.h.saturating_sub(cell) / advance) + 1).max(1) as usize;
    let n = want.min(max_lines);
    // Height of the n-line block: (n-1) advances + one cell.
    let block_h = (n as u32 - 1) * advance + cell;
    let free = rect.h.saturating_sub(block_h);
    let offset = match style.align_v {
        VAlign::Top => 0,
        VAlign::Middle => (free / 2) as i32,
        VAlign::Bottom => free as i32,
    };
    let mut layers = Vec::with_capacity(n);
    for (i, line) in non_empty.iter().take(n).enumerate() {
        let y = rect.y + offset + (i as u32 * advance) as i32;
        layers.push(Layer::Text {
            rect: Rect::new(rect.x, y, rect.w, cell),
            text: (*line).to_string(),
            px: cell,
            color: style.color,
            align: style.align_h,
        });
    }
    layers
}

/// Render a slide over its theme into a frame of `width×height`.
///
/// The slide's title renders in the theme's title/reference region (when visible +
/// non-empty) and its body lines in the body region — each styled + aligned per the
/// theme. A blank slide renders as background only.
/// The [`Layer::Fill`] rects for a decorative [`Band`]: the translucent panel fill
/// plus up to four border edges (top/bottom/left/right), in draw order (fill first,
/// border on top). The engine blends fills src-over, so a non-opaque `fill` reads as
/// a translucent panel over the background/video.
fn band_layers(band: &Band, width: u32, height: u32) -> Vec<Layer> {
    let rect = band.rect(width, height);
    let mut layers = vec![Layer::Fill {
        rect,
        color: band.fill,
    }];
    let bt = band.border_px(height) as i32;
    if bt > 0 && band.border.a > 0 {
        let (x, y, w, h) = (rect.x, rect.y, rect.w as i32, rect.h as i32);
        // Clamp each edge to the band so a thick border never inverts on a tiny band.
        let bt = bt.min(w).min(h);
        let edge = |x: i32, y: i32, w: i32, h: i32| Layer::Fill {
            rect: Rect::new(x, y, w.max(0) as u32, h.max(0) as u32),
            color: band.border,
        };
        layers.push(edge(x, y, w, bt)); // top
        layers.push(edge(x, y + h - bt, w, bt)); // bottom
        layers.push(edge(x, y, bt, h)); // left
        layers.push(edge(x + w - bt, y, bt, h)); // right
    }
    layers
}

pub fn compose_slide(slide: &Slide, theme: &Theme, width: u32, height: u32) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if slide.is_blank() {
        return frame; // background only
    }
    // A decorative band (e.g. the lower-third bar) sits behind the text regions.
    if let Some(band) = &theme.band {
        for layer in band_layers(band, width, height) {
            frame.push(layer);
        }
    }
    let body: Vec<&str> = slide
        .body
        .iter()
        .map(String::as_str)
        .filter(|l| !l.trim().is_empty())
        .collect();
    let title = slide.title.trim();
    if body.is_empty() {
        // A title-only slide (section header, song title): the title IS the main
        // content, so it renders large + centred in the BODY region — not as a
        // small header. (This matches the pre-theme "big centred title" behaviour.)
        if theme.body.visible && !title.is_empty() {
            for layer in layout_region(&[title], &theme.body, width, height) {
                frame.push(layer);
            }
        }
    } else {
        // Content slide: the title is the reference/heading (title region) and the
        // body lines fill the body region.
        if theme.title.visible && !title.is_empty() {
            for layer in layout_region(&[title], &theme.title, width, height) {
                frame.push(layer);
            }
        }
        if theme.body.visible {
            for layer in layout_region(&body, &theme.body, width, height) {
                frame.push(layer);
            }
        }
    }
    frame
}
