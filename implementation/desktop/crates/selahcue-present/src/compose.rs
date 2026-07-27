//! Compose a [`Slide`] + [`Theme`] into an engine [`Frame`] (FR-009/FR-010).
//!
//! A theme is a slide-design template: a background plus positioned **regions**
//! (title/reference + body), each with alignment + typography. `compose_slide`
//! lays the slide's title into the title region and its body lines into the body
//! region — content is orthogonal to the theme, so re-composing the *same* slide
//! under a different theme restyles it without loss.

use crate::slide::Slide;
use crate::theme::{Band, Element, Fit, RegionStyle, Theme, VAlign};
use selahcue_engine::scene::{FontName, Frame, Layer, Rect, Rgba, TextAlign};

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

/// Lay out `lines` (each a paragraph) into `rect` with AUTO-FIT: word-wrap to the region
/// width + size the font so the block fits, per `fit`. Shared by the themed audience
/// regions ([`layout_region`]) and the confidence monitor (`stage::push_region`), so the
/// speaker's stage output shrinks-to-fit the FULL verse exactly like the audience output.
/// `max_cell` is the design-size ceiling; `lh` the line-height multiplier; `align_h`/
/// `align_v` + `color` style the text. Zero content loss under `ShrinkToFit`.
#[allow(clippy::too_many_arguments)]
pub(crate) fn autofit_layers(
    lines: &[&str],
    rect: Rect,
    max_cell: u32,
    lh: f64,
    align_h: TextAlign,
    align_v: VAlign,
    color: Rgba,
    fit: Fit,
    font: Option<FontName>,
) -> Vec<Layer> {
    let non_empty: Vec<&str> = lines
        .iter()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();
    if non_empty.is_empty() || rect.w == 0 || rect.h == 0 {
        return Vec::new();
    }
    let design_cell = max_cell.min(rect.h).max(1);

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
        let space_w = (selahcue_engine::raster::measure_line_width("x x", cell, font.as_ref())
            - selahcue_engine::raster::measure_line_width("xx", cell, font.as_ref()))
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
                let ww = *memo.entry(word).or_insert_with(|| {
                    selahcue_engine::raster::measure_line_width(word, cell, font.as_ref())
                });
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
    let (cell, display) = match fit {
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
    let offset = match align_v {
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
            color,
            align: align_h,
            font,
        });
    }
    layers
}

/// Lay out `lines` into a themed [`RegionStyle`] region (the audience output) — a thin
/// wrapper over [`autofit_layers`] that derives the geometry/typography from the theme.
fn layout_region(
    lines: &[&str],
    style: &RegionStyle,
    width: u32,
    height: u32,
    font: Option<FontName>,
) -> Vec<Layer> {
    autofit_layers(
        lines,
        style.rect(width, height),
        style.cell_px(height),
        style.line_height(),
        style.align_h,
        style.align_v,
        style.color,
        style.fit,
        font,
    )
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

/// The [`Layer::Fill`] rects for a design [`Element`] (Canvas Editing, 86ajq6j2q). A
/// `Shape` is a fill rect + up to four border edges (like [`band_layers`]), with the
/// element's `opacity` multiplied into the fill + border alpha (the engine blends fills
/// src-over, so a translucent shape reads as a panel over what is beneath). Positions +
/// sizes are per-mille of the frame, matching [`Band`].
fn element_layers(element: &Element, width: u32, height: u32) -> Vec<Layer> {
    match element {
        Element::Shape {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            fill,
            border,
            border_permille,
            opacity,
            z: _,
        } => {
            let map = |dim: u32, permille: u16| (dim as u64 * permille as u64 / 1000) as u32;
            let rect = Rect::new(
                map(width, *x_permille) as i32,
                map(height, *y_permille) as i32,
                map(width, *w_permille).max(1),
                map(height, *h_permille).max(1),
            );
            // Multiply the whole-shape opacity into each colour's alpha (0 = fully hidden).
            let apply =
                |c: Rgba| Rgba::new(c.r, c.g, c.b, ((c.a as u16 * *opacity as u16) / 255) as u8);
            let mut layers = Vec::new();
            let f = apply(*fill);
            if f.a > 0 {
                layers.push(Layer::Fill { rect, color: f });
            }
            let bt = if *border_permille == 0 {
                0
            } else {
                (height as u64 * *border_permille as u64 / 1000).max(1) as i32
            };
            let b = apply(*border);
            if bt > 0 && b.a > 0 {
                let (x, y, w, h) = (rect.x, rect.y, rect.w as i32, rect.h as i32);
                let bt = bt.min(w).min(h);
                let edge = |x: i32, y: i32, w: i32, h: i32| Layer::Fill {
                    rect: Rect::new(x, y, w.max(0) as u32, h.max(0) as u32),
                    color: b,
                };
                // Left/right span the FULL height and own the four corners; top/bottom
                // cover only the interior width (w - 2*bt) so no pixel is painted by two
                // edges. Overlapping edges are idempotent for an OPAQUE border, but this
                // batch multiplies the shape opacity into the border alpha — a translucent
                // border would double-blend (brighter) at the corners without this split.
                let iw = (w - 2 * bt).max(0); // interior width (0 when the border fills the box)
                layers.push(edge(x, y, bt, h)); // left (full height)
                layers.push(edge(x + w - bt, y, bt, h)); // right (full height)
                layers.push(edge(x + bt, y, iw, bt)); // top (interior)
                layers.push(edge(x + bt, y + h - bt, iw, bt)); // bottom (interior)
            }
            layers
        }
    }
}

pub fn compose_slide(slide: &Slide, theme: &Theme, width: u32, height: u32) -> Frame {
    let mut frame = Frame::new(width, height).with_background(theme.background);
    if slide.is_blank() {
        return frame; // background only
    }
    // A decorative band (e.g. the lower-third bar) sits behind everything else.
    if let Some(band) = &theme.band {
        for layer in band_layers(band, width, height) {
            frame.push(layer);
        }
    }
    // Design elements (Canvas Editing, 86ajq6j2q) composite by z-order relative to the
    // text: `z < 0` BEHIND the text, `z >= 0` IN FRONT. A stable sort by z gives a
    // well-defined order (list order within equal z). Rendered here (behind pass) + after
    // the text (front pass). Absent for every current built-in → a no-op → determinism.
    let mut ordered: Vec<&Element> = theme.elements.iter().collect();
    ordered.sort_by_key(|e| e.z());
    for e in ordered.iter().filter(|e| e.z() < 0) {
        for layer in element_layers(e, width, height) {
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
            for layer in layout_region(&[title], &theme.body, width, height, theme.font) {
                frame.push(layer);
            }
        }
    } else {
        // Content slide: the title is the reference/heading (title region) and the
        // body lines fill the body region.
        if theme.title.visible && !title.is_empty() {
            for layer in layout_region(&[title], &theme.title, width, height, theme.font) {
                frame.push(layer);
            }
        }
        if theme.body.visible {
            for layer in layout_region(&body, &theme.body, width, height, theme.font) {
                frame.push(layer);
            }
        }
    }
    // Front pass: design elements with `z >= 0` composite IN FRONT of the text.
    for e in ordered.iter().filter(|e| e.z() >= 0) {
        for layer in element_layers(e, width, height) {
            frame.push(layer);
        }
    }
    frame
}
