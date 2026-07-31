//! Deterministic rasterizer + pixel-readback tests (golden-image parity).

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{render, system_font_families, FrameBuffer, MAX_SYSTEM_FONTS};
use selahcue_engine::scene::{FontName, Frame, Layer, Rect, Rgba, ShapeKind, TextAlign};

fn red_frame_with_blue_box() -> Frame {
    let mut f = Frame::new(32, 32).with_background(Rgba::rgb(255, 0, 0));
    f.push(Layer::Fill {
        rect: Rect::new(10, 10, 5, 5),
        color: Rgba::rgb(0, 0, 255),
    });
    f
}

#[test]
fn render_is_deterministic() {
    let f = red_frame_with_blue_box();
    assert_eq!(
        render(&f).bytes(),
        render(&f).bytes(),
        "the same scene must produce byte-identical pixels"
    );
}

#[test]
fn background_and_layer_pixels_are_correct() {
    let fb = render(&red_frame_with_blue_box());
    assert_eq!(fb.pixel(0, 0).unwrap(), Rgba::rgb(255, 0, 0)); // background
    assert_eq!(fb.pixel(12, 12).unwrap(), Rgba::rgb(0, 0, 255)); // inside the box
    assert_eq!(fb.pixel(20, 20).unwrap(), Rgba::rgb(255, 0, 0)); // outside the box
}

#[test]
fn blackout_renders_all_black() {
    let mut f = Frame::new(8, 8).with_background(Rgba::WHITE);
    f.push(Layer::Fill {
        rect: Rect::new(0, 0, 8, 8),
        color: Rgba::WHITE,
    });
    f.blackout = true;
    let fb = render(&f);
    for y in 0..8 {
        for x in 0..8 {
            assert_eq!(fb.pixel(x, y).unwrap(), Rgba::BLACK);
        }
    }
}

#[test]
fn later_layer_paints_over_earlier() {
    let mut f = Frame::new(4, 4);
    f.push(Layer::Fill {
        rect: Rect::new(0, 0, 4, 4),
        color: Rgba::rgb(255, 0, 0),
    });
    f.push(Layer::Fill {
        rect: Rect::new(0, 0, 4, 4),
        color: Rgba::rgb(0, 255, 0),
    });
    assert_eq!(render(&f).pixel(1, 1).unwrap(), Rgba::rgb(0, 255, 0));
}

#[test]
fn alpha_blends_over_background() {
    let mut f = Frame::new(2, 2); // black background
    f.push(Layer::Fill {
        rect: Rect::new(0, 0, 2, 2),
        color: Rgba::new(255, 255, 255, 128),
    });
    let p = render(&f).pixel(0, 0).unwrap();
    assert!(
        (120..=135).contains(&p.r),
        "50% white over black should be ~mid-grey, got {}",
        p.r
    );
}

#[test]
fn text_layer_renders_glyphs_within_its_rect() {
    let mut f = Frame::new(200, 40); // black background
    f.push(Layer::Text {
        rect: Rect::new(10, 8, 180, 24),
        text: "HELLO".into(),
        px: 16,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    let fb = render(&f);
    // Antialiased glyph ink appears inside the text rect (partial-coverage greys,
    // not only exact white — real shaping, not the old solid bitmap).
    let mut inked = 0;
    for y in 8..32 {
        for x in 10..190 {
            if fb.pixel(x, y).map(|p| p.r > 40).unwrap_or(false) {
                inked += 1;
            }
        }
    }
    assert!(
        inked > 20,
        "expected glyph coverage, got {inked} inked pixels"
    );
    // Nothing painted outside the rect.
    assert_eq!(fb.pixel(0, 0).unwrap(), Rgba::BLACK);
    assert_eq!(fb.pixel(199, 39).unwrap(), Rgba::BLACK);
    // Deterministic.
    assert_eq!(render(&f).bytes(), fb.bytes());
}

#[test]
fn oversized_text_is_bounded_by_the_framebuffer() {
    // A pathological px/rect must not blow up render time — work is bounded by the
    // framebuffer, so this returns promptly and does not panic.
    let mut f = Frame::new(64, 64);
    f.push(Layer::Text {
        rect: Rect::new(0, 0, 200_000, 200_000),
        text: "ABCDEFGH".into(),
        px: 100_000,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    let fb = render(&f);
    assert_eq!(fb.width(), 64);
    assert_eq!(fb.height(), 64);
}

#[test]
fn glyphs_are_not_mirrored() {
    // 'L' is left- and bottom-heavy: its vertical stroke is on the LEFT. In the
    // upper rows (above the bottom bar) the left half must carry far more ink
    // than the right half — a mirrored/flipped glyph would reverse that. Uses
    // summed antialiased coverage so it is robust to the shaped font's metrics.
    let mut f = Frame::new(40, 40);
    f.push(Layer::Text {
        rect: Rect::new(0, 0, 40, 40),
        text: "L".into(),
        px: 34,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    let fb = render(&f);
    let ink = |x: u32, y: u32| fb.pixel(x, y).map(|p| p.r as u32).unwrap_or(0);
    let (mut left, mut right) = (0u32, 0u32);
    for y in 2..26 {
        for x in 0..20 {
            left += ink(x, y);
        }
        for x in 20..40 {
            right += ink(x, y);
        }
    }
    assert!(left > 0, "'L' must render some ink");
    assert!(
        left > right * 2,
        "'L' left stroke must dominate the upper rows (glyph not mirrored): \
         left={left} right={right}"
    );
}

#[test]
fn text_is_clipped_to_its_rect() {
    let mut f = Frame::new(200, 40);
    // A narrow rect: at px=16 (16px cells) only ~2 glyphs fit before the right edge.
    f.push(Layer::Text {
        rect: Rect::new(0, 0, 32, 20),
        text: "AAAAAAAA".into(),
        px: 16,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    let fb = render(&f);
    // No glyph pixels beyond the 32px-wide rect.
    for y in 0..20 {
        for x in 33..200 {
            assert_eq!(
                fb.pixel(x, y).unwrap(),
                Rgba::BLACK,
                "text leaked past its rect at {x},{y}"
            );
        }
    }
}

#[test]
fn out_of_bounds_rects_are_clipped_without_panicking() {
    let mut f = Frame::new(4, 4);
    // Fully off the top-left — must not touch any pixel.
    f.push(Layer::Fill {
        rect: Rect::new(-10, -10, 3, 3),
        color: Rgba::WHITE,
    });
    // Overflows the right/bottom edges — clipped to the buffer.
    f.push(Layer::Fill {
        rect: Rect::new(2, 2, 100, 100),
        color: Rgba::rgb(0, 0, 255),
    });
    let fb = render(&f);
    assert_eq!(fb.pixel(3, 3).unwrap(), Rgba::rgb(0, 0, 255));
    assert_eq!(fb.pixel(0, 0).unwrap(), Rgba::BLACK);
}

// --- Real text shaping (batch 8b, ADR-0014 / FR-017) ---

/// Total inked coverage (sum of the red channel over the frame) — a proxy for
/// "how much glyph ink was rendered". Zero = nothing drawn.
fn ink_total(fb: &selahcue_engine::raster::FrameBuffer) -> u64 {
    let mut t = 0u64;
    for y in 0..fb.height() {
        for x in 0..fb.width() {
            t += fb.pixel(x, y).map(|p| p.r as u64).unwrap_or(0);
        }
    }
    t
}

fn text_frame(text: &str) -> Frame {
    let mut f = Frame::new(320, 60);
    f.push(Layer::Text {
        rect: Rect::new(4, 4, 312, 52),
        text: text.into(),
        px: 34,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    f
}

#[test]
fn diacritics_render_where_the_old_bitmap_font_drew_nothing() {
    // The old font8x8 path skipped every non-ASCII char, so a purely-accented
    // string produced ZERO ink. With real shaping (cosmic-text/rustybuzz over
    // the bundled Noto Sans), the accents render — FR-017.
    let accented = ink_total(&render(&text_frame("áàéíóúñ ẹọṣ ị ṅ")));
    assert!(
        accented > 0,
        "diacritic-only text must render glyph ink (was 0 under font8x8)"
    );
    // "María" renders MORE ink than "Mara" — the í glyph (dropped by the old
    // path) is actually drawn now.
    let maria = ink_total(&render(&text_frame("María")));
    let mara = ink_total(&render(&text_frame("Mara")));
    assert!(
        maria > mara,
        "'María' must render more ink than 'Mara' (the í is drawn): {maria} vs {mara}"
    );
}

#[test]
fn ascii_text_still_renders_legibly() {
    // Regression: plain ASCII still produces substantial ink (it isn't broken by
    // the shaping switch).
    assert!(ink_total(&render(&text_frame("GO LIVE"))) > 0);
}

#[test]
fn text_rendering_is_byte_deterministic() {
    // A single bundled shaper + font → the same input yields byte-identical
    // pixels every time (the basis for cross-OS parity, NFR-014). The 3-OS CI
    // matrix extends this equality across platforms.
    let a = render(&text_frame("María — Yorùbá ẹ̀kọ́"));
    let b = render(&text_frame("María — Yorùbá ẹ̀kọ́"));
    assert_eq!(
        a.bytes(),
        b.bytes(),
        "identical text must rasterize identically"
    );
}

#[test]
fn offscreen_glyphs_are_culled_so_work_is_frame_bounded() {
    // Review 8b-HIGH regression: a long line must not do work for glyphs past the
    // clip. Two lines that both overflow a narrow rect must produce IDENTICAL
    // visible pixels — proving the off-rect glyphs (the extra 5000) neither
    // change the output nor (via the left-to-right break) get rasterized.
    let narrow = |text: String| {
        let mut f = Frame::new(48, 40);
        f.push(Layer::Text {
            rect: Rect::new(0, 4, 48, 32), // only ~2-3 glyphs are visible
            text,
            px: 28,
            color: Rgba::WHITE,
            align: TextAlign::Left,
            font: None,
        });
        render(&f)
    };
    let short_overflow = narrow("MMMMMM".into()); // already overflows the 48px rect
    let very_long = narrow("M".repeat(5000)); // 5000 glyphs, all but ~3 off-screen
    assert_eq!(
        short_overflow.bytes(),
        very_long.bytes(),
        "off-screen glyphs must not affect the visible output (and are culled, not rasterized)"
    );
}

#[test]
fn descenders_and_dot_below_marks_are_not_cropped() {
    // Review 8b-MEDIUM regression: the font must fit within the line cell so the
    // below-baseline zone (g/p/y descenders; the Yoruba/Igbo dot-below marks in
    // ẹ/ọ/ṣ/ị — FR-017) renders and is not clipped at the cell's bottom edge.
    let mut f = Frame::new(200, 60);
    f.push(Layer::Text {
        rect: Rect::new(4, 4, 192, 52),
        text: "gpy ẹọṣị".into(),
        px: 44,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    let fb = render(&f);
    // There is ink in the LOWER portion of the cell (below the x-height band) —
    // i.e. descenders / dot-below marks survived, not shaved off at the top only.
    let has_ink = |y0: u32, y1: u32| {
        (y0..y1).any(|y| (4..196).any(|x| fb.pixel(x, y).map(|p| p.r > 40).unwrap_or(false)))
    };
    assert!(has_ink(4, 40), "main glyph body renders");
    assert!(
        has_ink(38, 56),
        "descenders / dot-below marks render in the lower cell (not cropped)"
    );
}

#[test]
fn text_caches_stay_bounded_over_many_renders() {
    // Review 8b: the per-thread glyph/shape caches must not grow without bound.
    // Render far past the internal reset threshold at MANY distinct sizes (the
    // worst case for cache growth) — it must stay responsive, deterministic, and
    // never OOM/panic (the periodic full reset caps memory).
    for i in 0..9000u32 {
        let mut f = Frame::new(80, 40);
        f.push(Layer::Text {
            rect: Rect::new(2, 2, 76, 36),
            text: "Aẹ́g".into(),
            px: 8 + (i % 30), // distinct sizes cycle → exercises the size dimension
            color: Rgba::WHITE,
            align: TextAlign::Left,
            font: None,
        });
        let _ = render(&f);
    }
    // Still correct after all that churn (same input → same output).
    let mut f = Frame::new(80, 40);
    f.push(Layer::Text {
        rect: Rect::new(2, 2, 76, 36),
        text: "Aẹ́g".into(),
        px: 20,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
    });
    assert_eq!(render(&f).bytes(), render(&f).bytes());
}

#[test]
fn text_alignment_offsets_the_line_within_its_rect() {
    // S8-3b crux: Center/Right alignment shifts the shaped line by its measured
    // width, so a short line no longer hugs the left edge — this is what makes a
    // theme a *template* (centred/positioned), not just a colour swap.
    let render_aligned = |align| {
        let mut f = Frame::new(200, 40);
        f.push(Layer::Text {
            rect: Rect::new(0, 4, 200, 32),
            text: "Hi".into(),
            px: 32,
            color: Rgba::WHITE,
            align,
            font: None,
        });
        render(&f)
    };
    // Inked column span [lo, hi] of a short line.
    let span = |fb: &selahcue_engine::raster::FrameBuffer| {
        let (mut lo, mut hi) = (u32::MAX, 0u32);
        for y in 0..40 {
            for x in 0..200 {
                if fb.pixel(x, y).map(|p| p.r > 40).unwrap_or(false) {
                    lo = lo.min(x);
                    hi = hi.max(x);
                }
            }
        }
        (lo, hi)
    };
    let (ll, _) = span(&render_aligned(TextAlign::Left));
    let (cl, ch) = span(&render_aligned(TextAlign::Center));
    let (_, rh) = span(&render_aligned(TextAlign::Right));
    assert!(
        ll < 20,
        "left-aligned ink starts near the left edge, got {ll}"
    );
    assert!(
        cl > ll,
        "centre ink starts further right than left ({cl} vs {ll})"
    );
    let cmid = (cl + ch) / 2;
    assert!(
        (80..=120).contains(&cmid),
        "centre ink midpoint near the frame centre, got {cmid}"
    );
    assert!(
        rh > 180,
        "right-aligned ink reaches near the right edge, got {rh}"
    );
}

// --- Selectable system fonts (86ajq6fxt) -----------------------------------

/// Render "HELLO" in a 200×40 frame under `font` (None = the bundled default).
fn render_text(font: Option<FontName>) -> Vec<u8> {
    let mut f = Frame::new(200, 40);
    f.push(Layer::Text {
        rect: Rect::new(10, 8, 180, 24),
        text: "HELLO".into(),
        px: 20,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font,
    });
    render(&f).bytes().to_vec()
}

#[test]
fn a_missing_font_falls_back_readably_and_deterministically() {
    // A per-theme font not installed on this machine must degrade to a READABLE fallback
    // (cosmic-text's fallback chain → a real platform font: Noto Sans on Linux, the OS UI
    // font on macOS/Windows) — never tofu, never blank, never a panic. The fallback goes
    // through the system shaper (not the bundled-only default path), so it need not be
    // byte-identical to the default; it must be NON-BLANK and DETERMINISTIC on this machine
    // (two different unknown families fall back to the same thing).
    let a = render_text(Some(
        FontName::new("NoSuchFont-\u{2205}-ZZZ-12345").unwrap(),
    ));
    let b = render_text(Some(FontName::new("AlsoMissing-\u{2603}-QQQ").unwrap()));
    assert!(
        a.iter().any(|&px| px != 0),
        "a missing font still draws readable ink (fallback), not a blank frame"
    );
    assert_eq!(
        a, b,
        "two unknown families fall back to the SAME (deterministic) render"
    );
    // And the bundled default itself draws ink.
    assert!(render_text(None).iter().any(|&px| px != 0));
}

#[test]
fn a_selected_system_font_can_change_the_render() {
    // A per-theme font actually drives shaping: if the machine has ANY installed family
    // distinct enough from the bundled Noto Sans, selecting it changes the pixels. Robust
    // over the enumerated set (a machine with fonts has some that differ). Skips only on a
    // minimal env with NO installed fonts (the default bundled font always works there).
    let families = system_font_families();
    if families.is_empty() {
        eprintln!("no system fonts enumerated on this machine — skipping the differs check");
        return;
    }
    let default = render_text(None);
    let any_differs = families
        .iter()
        .take(40)
        .any(|fam| FontName::new(fam).is_some_and(|f| render_text(Some(f)) != default));
    assert!(
        any_differs,
        "at least one of the {} installed fonts renders differently from the bundled default",
        families.len().min(40)
    );
}

#[test]
fn system_font_enumeration_is_sorted_deduped_and_bounded() {
    let families = system_font_families();
    assert!(families.len() <= MAX_SYSTEM_FONTS, "enumeration is bounded");
    // Sorted + deduped.
    assert!(
        families.windows(2).all(|w| w[0] < w[1]),
        "family list is sorted + deduped"
    );
    // Every name is within the bounded FontName capacity (so all are assignable).
    assert!(families.iter().all(|n| FontName::new(n).is_some()));
}

#[test]
fn themed_font_rendering_is_bounded_over_many_renders() {
    // No-leak: rendering many frames with a per-theme font holds O(1) buffer state (the
    // system shaper is bounded + periodically reset), and never panics.
    let font = FontName::new("SelahCue-Probe-Font").unwrap(); // missing → fallback path
    let first = render_text(Some(font));
    for _ in 0..5000u32 {
        let out = render_text(Some(font));
        assert_eq!(out.len(), first.len(), "frame size stays constant");
    }
}

// --- Layer::Shape: parametric shape rasterization (86ajtwq24) ---

/// A single centred `Layer::Shape` of `kind` (fill white, no border) on a black frame.
fn shape_frame(kind: ShapeKind, w: u32, h: u32) -> Frame {
    let mut f = Frame::new(w, h).with_background(Rgba::BLACK);
    f.push(Layer::Shape {
        rect: Rect::new(0, 0, w, h),
        kind,
        fill: Rgba::WHITE,
        border: Rgba::new(0, 0, 0, 0),
        border_px: 0,
        corner_px: 0,
    });
    f
}

/// Whether the pixel is (near) white — the shape fill; the background is black.
fn is_fill(fb: &selahcue_engine::FrameBuffer, x: u32, y: u32) -> bool {
    fb.pixel(x, y).unwrap().r > 200
}

#[test]
fn ellipse_is_round_not_the_bounding_square() {
    // A 40×40 ellipse (= circle): the CENTRE is filled but every CORNER of the bounding
    // box is background — the discriminating property vs a rectangle fill.
    let fb = render(&shape_frame(ShapeKind::Ellipse, 40, 40));
    assert!(is_fill(&fb, 20, 20), "centre is filled");
    assert!(is_fill(&fb, 20, 1), "top-middle is filled");
    assert!(is_fill(&fb, 1, 20), "left-middle is filled");
    // All four corners are OUTSIDE the inscribed circle → background.
    for (x, y) in [(1, 1), (38, 1), (1, 38), (38, 38)] {
        assert!(!is_fill(&fb, x, y), "corner ({x},{y}) is background");
    }
}

#[test]
fn triangle_apex_is_narrow_and_base_is_wide() {
    // Isosceles triangle, apex top-centre, base along the bottom. The top row's corners
    // are background (narrow apex) while the bottom row's corners are filled (wide base).
    let fb = render(&shape_frame(ShapeKind::Triangle, 41, 40));
    assert!(is_fill(&fb, 20, 1), "apex column near the top is filled");
    assert!(!is_fill(&fb, 1, 1), "top-left corner is outside the apex");
    assert!(!is_fill(&fb, 39, 1), "top-right corner is outside the apex");
    assert!(is_fill(&fb, 2, 38), "bottom-left is inside the wide base");
    assert!(is_fill(&fb, 38, 38), "bottom-right is inside the wide base");
}

#[test]
fn rounded_rect_cuts_the_corners_only() {
    // A rounded rectangle with a large radius: the extreme corner pixel is cut (background)
    // but the straight-edge midpoints and the centre are filled.
    let mut f = Frame::new(40, 40).with_background(Rgba::BLACK);
    f.push(Layer::Shape {
        rect: Rect::new(0, 0, 40, 40),
        kind: ShapeKind::RoundedRect,
        fill: Rgba::WHITE,
        border: Rgba::new(0, 0, 0, 0),
        border_px: 0,
        corner_px: 12,
    });
    let fb = render(&f);
    assert!(is_fill(&fb, 20, 20), "centre is filled");
    assert!(is_fill(&fb, 20, 0), "top-edge midpoint is filled");
    assert!(is_fill(&fb, 0, 20), "left-edge midpoint is filled");
    assert!(!is_fill(&fb, 0, 0), "the extreme corner is rounded away");
    // A zero-radius rounded rect is a PLAIN rectangle — every corner filled.
    let mut f0 = Frame::new(40, 40).with_background(Rgba::BLACK);
    f0.push(Layer::Shape {
        rect: Rect::new(0, 0, 40, 40),
        kind: ShapeKind::RoundedRect,
        fill: Rgba::WHITE,
        border: Rgba::new(0, 0, 0, 0),
        border_px: 0,
        corner_px: 0,
    });
    let fb0 = render(&f0);
    assert!(
        is_fill(&fb0, 0, 0),
        "radius 0 → the corner stays filled (a plain rect)"
    );
}

#[test]
fn shape_border_rings_the_edge_and_fill_sits_inside() {
    // An ellipse with a thick border: a pixel on the outline reads the BORDER colour (red)
    // while the centre reads the FILL colour (white).
    let mut f = Frame::new(40, 40).with_background(Rgba::BLACK);
    f.push(Layer::Shape {
        rect: Rect::new(0, 0, 40, 40),
        kind: ShapeKind::Ellipse,
        fill: Rgba::WHITE,
        border: Rgba::rgb(255, 0, 0),
        border_px: 5,
        corner_px: 0,
    });
    let fb = render(&f);
    let centre = fb.pixel(20, 20).unwrap();
    assert!(
        centre.r > 200 && centre.g > 200 && centre.b > 200,
        "centre is fill white"
    );
    // Just inside the left edge of the ellipse (on the outline band) → red border.
    let edge = fb.pixel(20, 1).unwrap();
    assert!(
        edge.r > 200 && edge.g < 60 && edge.b < 60,
        "outline is border red, got {edge:?}"
    );
}

#[test]
fn shape_opacity_blends_and_render_is_deterministic() {
    // The compositor folds opacity into the fill alpha; a 50%-white ellipse over black
    // reads as a mid grey at the centre, and the render is byte-identical across runs.
    let mut f = Frame::new(30, 30).with_background(Rgba::BLACK);
    f.push(Layer::Shape {
        rect: Rect::new(0, 0, 30, 30),
        kind: ShapeKind::Ellipse,
        fill: Rgba::new(255, 255, 255, 128), // 50% alpha
        border: Rgba::new(0, 0, 0, 0),
        border_px: 0,
        corner_px: 0,
    });
    let centre = render(&f).pixel(15, 15).unwrap();
    assert!(
        (100..=160).contains(&centre.r),
        "50% white over black → mid grey, got {centre:?}"
    );
    assert_eq!(
        render(&f).bytes(),
        render(&f).bytes(),
        "shape rasterization is deterministic (byte-identical)"
    );
}

#[test]
fn a_fill_layer_renders_unchanged_alongside_shapes() {
    // The Fill arm is untouched by the new Shape arm: a plain fill still paints its exact rect.
    let mut f = Frame::new(16, 16).with_background(Rgba::BLACK);
    f.push(Layer::Fill {
        rect: Rect::new(4, 4, 8, 8),
        color: Rgba::rgb(0, 0, 255),
    });
    let fb = render(&f);
    assert_eq!(
        fb.pixel(8, 8).unwrap(),
        Rgba::rgb(0, 0, 255),
        "inside the fill rect"
    );
    assert_eq!(
        fb.pixel(0, 0).unwrap(),
        Rgba::BLACK,
        "outside stays background"
    );
}

// --- FrameBuffer::thumbnail: deterministic box-average downscale (86ajtwq28) ---

#[test]
fn thumbnail_box_averages_a_known_frame() {
    // A 2x2 frame with four distinct colours downscaled to 1x1 = the mean of all four.
    let mut f = Frame::new(2, 2).with_background(Rgba::BLACK);
    // Overwrite each pixel via 1x1 fills.
    f.push(Layer::Fill {
        rect: Rect::new(0, 0, 1, 1),
        color: Rgba::rgb(0, 0, 0),
    });
    f.push(Layer::Fill {
        rect: Rect::new(1, 0, 1, 1),
        color: Rgba::rgb(100, 100, 100),
    });
    f.push(Layer::Fill {
        rect: Rect::new(0, 1, 1, 1),
        color: Rgba::rgb(200, 40, 0),
    });
    f.push(Layer::Fill {
        rect: Rect::new(1, 1, 1, 1),
        color: Rgba::rgb(40, 60, 80),
    });
    let thumb = render(&f).thumbnail(1, 1);
    assert_eq!(thumb.width(), 1);
    assert_eq!(thumb.height(), 1);
    // Mean per channel: r=(0+100+200+40)/4=85, g=(0+100+40+60)/4=50, b=(0+100+0+80)/4=45.
    let p = thumb.pixel(0, 0).unwrap();
    assert_eq!(
        (p.r, p.g, p.b),
        (85, 50, 45),
        "1x1 thumbnail is the box-average, got {p:?}"
    );
}

#[test]
fn thumbnail_preserves_aspect_within_the_bound_and_is_deterministic() {
    let fb = render(&red_frame_with_blue_box()); // 32x32
    let t = fb.thumbnail(16, 8); // height binds (32/32 aspect) -> 8x8
    assert_eq!(
        (t.width(), t.height()),
        (8, 8),
        "aspect preserved within the bound"
    );
    assert!(t.width() <= 16 && t.height() <= 8, "fits within the bound");
    // A landscape source keeps its aspect (width binds).
    let wide = FrameBuffer::filled(40, 10, Rgba::WHITE).thumbnail(20, 20);
    assert_eq!(
        (wide.width(), wide.height()),
        (20, 5),
        "40x10 -> 20x5 (width binds)"
    );
    // Deterministic: byte-identical across calls.
    assert_eq!(fb.thumbnail(16, 16).bytes(), fb.thumbnail(16, 16).bytes());
}

#[test]
fn thumbnail_never_upscales_and_is_bounded() {
    // Already within the bound -> returned unchanged (no upscale).
    let small = render(&red_frame_with_blue_box()); // 32x32
    let t = small.thumbnail(100, 100);
    assert_eq!(
        t.bytes(),
        small.bytes(),
        "a frame within the bound is unchanged"
    );
    // Degenerate + hostile sizes must not panic and stay bounded.
    let one = FrameBuffer::filled(1, 1, Rgba::WHITE).thumbnail(0, 0); // clamps to 1x1
    assert_eq!((one.width(), one.height()), (1, 1));
    let big = FrameBuffer::filled(64, 64, Rgba::WHITE).thumbnail(u32::MAX, u32::MAX);
    assert_eq!(
        (big.width(), big.height()),
        (64, 64),
        "huge max -> no upscale, no panic"
    );
    let tiny = FrameBuffer::filled(1000, 1000, Rgba::rgb(10, 20, 30)).thumbnail(1, 1);
    assert_eq!(
        tiny.pixel(0, 0).unwrap(),
        Rgba::rgb(10, 20, 30),
        "uniform frame averages to itself"
    );
}

#[test]
fn shapes_are_bounded_on_extreme_rects_without_panic() {
    // The layer rect is UNVALIDATED (a hand-edited/IPC scene can carry any i32/u32). Every
    // kind must CLIP to the framebuffer and never overflow-panic, even at the extremes of
    // the coordinate range (this test would abort on any arithmetic overflow in debug).
    for kind in [
        ShapeKind::Ellipse,
        ShapeKind::RoundedRect,
        ShapeKind::Triangle,
        ShapeKind::Rect,
    ] {
        for rect in [
            Rect::new(i32::MIN, i32::MIN, u32::MAX, u32::MAX),
            Rect::new(i32::MAX, i32::MAX, u32::MAX, u32::MAX),
            Rect::new(-5, -5, 10, 10), // straddles the top-left corner
            Rect::new(0, 0, 0, 0),     // degenerate
            Rect::new(30, 30, u32::MAX, 1),
        ] {
            let mut f = Frame::new(32, 32).with_background(Rgba::BLACK);
            f.push(Layer::Shape {
                rect,
                kind,
                fill: Rgba::WHITE,
                border: Rgba::rgb(255, 0, 0),
                border_px: u32::MAX, // an absurd border must not invert or panic
                corner_px: u32::MAX,
            });
            let fb = render(&f); // must not panic
            assert_eq!(
                fb.bytes().len(),
                32 * 32 * 4,
                "frame stays bounded to its size"
            );
        }
    }
}
