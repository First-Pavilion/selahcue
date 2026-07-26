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
/// Upper bound on words wrapped per region — far above any real verse or stanza (the
/// longest KJV verse is ~90 words), so real content is never truncated, but a
/// pathological free-text paste cannot make the SYNCHRONOUS Go-Live compose shape an
/// unbounded number of glyphs (a mid-service stall). Overflow → pagination (a later slice).
const MAX_WRAP_WORDS: usize = 1000;

/// Per-line vertical advance: the cell scaled by the line-height multiplier.
fn advance_of(cell: u32, lh: f64) -> u32 {
    ((cell as f64) * lh).round().max(cell as f64) as u32
}

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

    // Word-wrap every input paragraph (a song stanza line, or a whole verse) to the
    // region WIDTH at `cell`, returning the display lines + whether they ALL fit `rect.w`.
    // Each word is measured ONCE (memoized per cell) and lines are filled by summed
    // advances — O(words), so a large paste can't trigger the O(words²) re-shaping a
    // per-line measure would (mid-service Go-Live stall). A single unbreakable token
    // wider than the region (e.g. a space-less CJK verse, since `split_whitespace` makes
    // it one token) sets `fits_w = false`, so the auto-fit shrinks the cell until even it
    // fits — never clipping. `line_cap` (a block taller than the region never fits) and
    // `MAX_WRAP_WORDS` bound the work for a pathological passage.
    let line_cap = rect.h as usize + 1;
    let max_w = rect.w as f32;
    let wrap_at = |cell: u32| -> (Vec<String>, bool) {
        // Space advance at this cell (shaping trims a bare " ", so difference it out);
        // floored so an under-measured space can't over-pack a line into a clip.
        let space_w = (selahcue_engine::raster::measure_line_width("x x", cell)
            - selahcue_engine::raster::measure_line_width("xx", cell))
        .max((cell as f32) * 0.15);
        let mut memo: std::collections::HashMap<&str, f32> = std::collections::HashMap::new();
        let mut out: Vec<String> = Vec::new();
        let mut fits_w = true;
        let mut budget = MAX_WRAP_WORDS;
        'paras: for para in &non_empty {
            let mut line = String::new();
            let mut line_w = 0.0f32;
            for word in para.split_whitespace() {
                if budget == 0 || out.len() > line_cap {
                    break 'paras;
                }
                budget -= 1;
                let ww = *memo
                    .entry(word)
                    .or_insert_with(|| selahcue_engine::raster::measure_line_width(word, cell));
                if ww > max_w {
                    fits_w = false; // an unbreakable token wider than the region
                }
                if line.is_empty() {
                    line.push_str(word);
                    line_w = ww;
                } else if line_w + space_w + ww > max_w {
                    out.push(std::mem::take(&mut line));
                    line.push_str(word);
                    line_w = ww;
                } else {
                    line.push(' ');
                    line.push_str(word);
                    line_w += space_w + ww;
                }
            }
            if !line.is_empty() {
                out.push(line);
            }
        }
        (out, fits_w)
    };
    // Height of an `n`-line block at `cell`: (n-1) advances + one cell.
    let block_h = |n: usize, cell: u32| -> u32 {
        if n == 0 {
            0
        } else {
            (n as u32 - 1) * advance_of(cell, lh) + cell
        }
    };

    // Auto-fit: pick the cell + wrapped lines.
    let (cell, display) = match style.fit {
        // ShrinkToFit fills the box: the LARGEST cell (≤ the design size) at which every
        // wrapped line fits BOTH rect.h (height) AND rect.w (width) — so a long verse
        // shrinks so the WHOLE passage shows (zero content loss, FR-010) and a short one
        // keeps the design size. Both conditions become true only as the cell shrinks
        // (fewer/narrower lines, shorter line-height), so the predicate is monotone in
        // the cell → binary search for the largest cell that satisfies it.
        Fit::ShrinkToFit => {
            let mut lo = 1u32;
            let mut hi = design_cell;
            let mut best = 1u32;
            let (mut best_disp, _) = wrap_at(1);
            while lo <= hi {
                let mid = lo + (hi - lo) / 2;
                let (disp, fits_w) = wrap_at(mid);
                if fits_w && block_h(disp.len(), mid) <= rect.h {
                    best = mid;
                    best_disp = disp;
                    lo = mid + 1;
                } else if mid <= 1 {
                    break;
                } else {
                    hi = mid - 1;
                }
            }
            (best, best_disp)
        }
        // Clip/Paginate keep the design size + wrap to width; overflow past rect.h is
        // dropped (Clip) — full pagination is a later slice.
        Fit::Clip | Fit::Paginate => (design_cell, wrap_at(design_cell).0),
    };

    let advance = advance_of(cell, lh);
    // Lines that fit vertically (== display.len() under ShrinkToFit; a cap under Clip).
    let max_lines = ((rect.h.saturating_sub(cell) / advance) + 1).max(1) as usize;
    let n = display.len().min(max_lines);
    let free = rect.h.saturating_sub(block_h(n, cell));
    let offset = match style.align_v {
        VAlign::Top => 0,
        VAlign::Middle => (free / 2) as i32,
        VAlign::Bottom => free as i32,
    };
    let mut layers = Vec::with_capacity(n);
    for (i, line) in display.iter().take(n).enumerate() {
        let y = rect.y + offset + (i as u32 * advance) as i32;
        layers.push(Layer::Text {
            rect: Rect::new(rect.x, y, rect.w, cell),
            text: line.clone(),
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
