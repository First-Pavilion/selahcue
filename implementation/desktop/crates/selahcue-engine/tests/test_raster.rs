//! Deterministic rasterizer + pixel-readback tests (golden-image parity).

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{
    measure_line_width, render, system_font_families, FrameBuffer, MAX_SYSTEM_FONTS, STAGE_FONT,
};
use selahcue_engine::scene::{FontName, Frame, Layer, Rect, Rgba, ShapeKind, TextAlign, TextStyle};

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
        style: None,
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
        style: None,
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
        style: None,
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
        style: None,
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
        style: None,
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
            style: None,
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
        style: None,
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
            style: None,
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
        style: None,
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
            style: None,
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
        style: None,
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
fn the_bundled_stage_font_resolves_proportionally_at_both_weights() {
    // The stage/confidence monitor requests the bundled Inter at Regular AND Bold. Inter is a
    // PROPORTIONAL face; a regression where only one weight is bundled makes cosmic-text fall
    // back to a system MONOSPACE for the missing weight once system fonts are in the DB — a
    // narrow 'i' and a wide 'W' then measure equal. Assert both weights shape proportionally,
    // and that Bold is a real heavier face (wider advances), not the Regular reused.
    let inter = FontName::new(STAGE_FONT).unwrap();
    for weight in [400u16, 700] {
        let narrow = measure_line_width("iiiiiiiiii", 100, Some(&inter), weight);
        let wide = measure_line_width("WWWWWWWWWW", 100, Some(&inter), weight);
        assert!(
            narrow > 0.0 && wide > 0.0,
            "the stage font draws ink at weight {weight}"
        );
        assert!(
            wide > narrow * 1.5,
            "Inter must shape PROPORTIONALLY at weight {weight} (W ≫ i), not fall back to a \
             monospace (narrow={narrow:.0}, wide={wide:.0})"
        );
    }
    let reg = measure_line_width("Weight", 100, Some(&inter), 400);
    let bold = measure_line_width("Weight", 100, Some(&inter), 700);
    assert!(
        bold > reg,
        "bundled Inter Bold (700) is a real heavier face — wider than Regular (400) \
         (reg={reg:.0}, bold={bold:.0}), not a fallback that reuses Regular"
    );
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

// --- Font weight + letter-spacing (86ajq3225) ---

fn styled_text_frame(text: &str, w: u32, style: Option<TextStyle>) -> Frame {
    let mut f = Frame::new(w, 40).with_background(Rgba::BLACK);
    f.push(Layer::Text {
        rect: Rect::new(4, 4, w - 8, 32),
        text: text.into(),
        px: 28,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
        style,
    });
    f
}
fn total_ink(fb: &FrameBuffer) -> u64 {
    let mut t = 0u64;
    for y in 0..fb.height() {
        for x in 0..fb.width() {
            t += fb.pixel(x, y).unwrap().r as u64;
        }
    }
    t
}
fn rightmost_ink_x(fb: &FrameBuffer) -> u32 {
    let mut rm = 0;
    for y in 0..fb.height() {
        for x in 0..fb.width() {
            if fb.pixel(x, y).unwrap().r > 40 {
                rm = rm.max(x);
            }
        }
    }
    rm
}

#[test]
fn bold_weight_renders_more_ink_than_regular() {
    let regular = total_ink(&render(&styled_text_frame("HELLO", 200, None)));
    let bold = total_ink(&render(&styled_text_frame(
        "HELLO",
        200,
        Some(TextStyle {
            weight: 700,
            letter_spacing_px: 0,
        }),
    )));
    assert!(
        bold > regular,
        "BOLD (700) inks more than Regular (400): bold={bold} regular={regular}"
    );
    assert_eq!(
        render(&styled_text_frame(
            "HELLO",
            200,
            Some(TextStyle {
                weight: 700,
                letter_spacing_px: 0
            })
        ))
        .bytes(),
        render(&styled_text_frame(
            "HELLO",
            200,
            Some(TextStyle {
                weight: 700,
                letter_spacing_px: 0
            })
        ))
        .bytes(),
    );
}

#[test]
fn letter_spacing_widens_and_default_is_byte_identical() {
    let tight = rightmost_ink_x(&render(&styled_text_frame("HELLO", 300, None)));
    let spaced = rightmost_ink_x(&render(&styled_text_frame(
        "HELLO",
        300,
        Some(TextStyle {
            weight: 400,
            letter_spacing_px: 6,
        }),
    )));
    assert!(
        spaced > tight,
        "letter-spacing widens the line: spaced={spaced} tight={tight}"
    );
    assert_eq!(
        render(&styled_text_frame("HELLO", 200, None)).bytes(),
        render(&styled_text_frame("HELLO", 200, Some(TextStyle::default()))).bytes(),
        "default TextStyle renders identically to no style"
    );
}

#[test]
fn extreme_letter_spacing_is_bounded_no_panic() {
    for ls in [i32::MIN, i32::MAX, -100_000, 100_000] {
        let fb = render(&styled_text_frame(
            "SELAHCUE",
            120,
            Some(TextStyle {
                weight: 700,
                letter_spacing_px: ls,
            }),
        ));
        assert_eq!(fb.bytes().len(), 120 * 40 * 4, "frame stays bounded");
    }
}

#[test]
fn extreme_px_text_does_not_overflow_panic() {
    // A crafted/deserialized Text layer can carry any u32 `px`. The letter-spacing clamp
    // derives its bound from `px`; that bound MUST be computed in wide/saturating arithmetic
    // so `px` near/above 2^30 cannot overflow i32 (a regression the font batch introduced and
    // this pins). `draw_text`'s contract is bounded/no-panic for ANY input — even the default
    // style (ls == 0) hit the panic because the bound is evaluated unconditionally.
    for px in [1_073_741_824u32, 1_500_000_000, u32::MAX] {
        for style in [
            None,
            Some(TextStyle {
                weight: 700,
                letter_spacing_px: 40,
            }),
        ] {
            let mut f = Frame::new(64, 64);
            f.push(Layer::Text {
                rect: Rect::new(0, 0, 200_000, 200_000),
                text: "ABCDEFGH".into(),
                px,
                color: Rgba::WHITE,
                align: TextAlign::Left,
                font: None,
                style,
            });
            let fb = render(&f); // must not panic
            assert_eq!(fb.bytes().len(), 64 * 64 * 4, "frame stays bounded");
        }
    }
}

// ---- Gradient layer (86ajq3225): a deterministic two-stop linear ramp ----

#[test]
fn rgba_lerp_is_deterministic_integer_interpolation() {
    let a = Rgba::new(0, 0, 0, 255);
    let b = Rgba::new(100, 200, 40, 255);
    assert_eq!(a.lerp(b, 0), a, "t=0 is the from colour");
    assert_eq!(a.lerp(b, 1000), b, "t=1000 is the to colour");
    assert_eq!(a.lerp(b, 2000), b, "t clamps to 1000");
    // Midpoint: exact integer half.
    assert_eq!(a.lerp(b, 500), Rgba::new(50, 100, 20, 255));
    // A downward ramp (to < from) is exact too.
    assert_eq!(
        Rgba::new(200, 0, 0, 255).lerp(Rgba::new(0, 0, 0, 255), 500),
        Rgba::new(100, 0, 0, 255)
    );
}

#[test]
fn a_vertical_gradient_renders_a_black_to_white_ramp() {
    use selahcue_engine::scene::GradientDirection;
    let (w, h) = (16u32, 64u32);
    let mut f = Frame::new(w, h).with_background(Rgba::BLACK);
    f.push(Layer::Gradient {
        rect: Rect::new(0, 0, w, h),
        from: Rgba::BLACK,
        to: Rgba::WHITE,
        direction: GradientDirection::Vertical,
    });
    let fb = render(&f);
    let lum = |y: u32| fb.pixel(w / 2, y).unwrap().r as u32;
    // Top is black, bottom is white, and it increases monotonically down the frame.
    assert_eq!(lum(0), 0, "top row is the from colour (black)");
    assert_eq!(lum(h - 1), 255, "bottom row is the to colour (white)");
    assert!(
        lum(h / 2) > 100 && lum(h / 2) < 160,
        "middle is mid-grey, got {}",
        lum(h / 2)
    );
    for y in 1..h {
        assert!(
            lum(y) >= lum(y - 1),
            "the vertical ramp is monotonic non-decreasing at row {y}"
        );
    }
    // A horizontal sample row is constant (the vertical ramp does not vary across x).
    let row_mid = fb.pixel(0, h / 2).unwrap();
    assert_eq!(
        fb.pixel(w - 1, h / 2).unwrap(),
        row_mid,
        "a vertical ramp is constant across a row"
    );

    // Deterministic: two renders are byte-identical.
    let fb2 = render(&f);
    assert_eq!(
        fb.bytes(),
        fb2.bytes(),
        "a gradient renders byte-identically"
    );
}

#[test]
fn a_horizontal_gradient_ramps_across_x() {
    use selahcue_engine::scene::GradientDirection;
    let (w, h) = (64u32, 16u32);
    let mut f = Frame::new(w, h).with_background(Rgba::BLACK);
    f.push(Layer::Gradient {
        rect: Rect::new(0, 0, w, h),
        from: Rgba::BLACK,
        to: Rgba::WHITE,
        direction: GradientDirection::Horizontal,
    });
    let fb = render(&f);
    assert_eq!(fb.pixel(0, h / 2).unwrap().r, 0, "left is from (black)");
    assert_eq!(
        fb.pixel(w - 1, h / 2).unwrap().r,
        255,
        "right is to (white)"
    );
    // A vertical sample column is constant (the horizontal ramp does not vary across y).
    let col = fb.pixel(w / 2, 0).unwrap();
    assert_eq!(
        fb.pixel(w / 2, h - 1).unwrap(),
        col,
        "a horizontal ramp is constant down a column"
    );
}

#[test]
fn a_gradient_is_bounded_on_extreme_rects_without_panic() {
    use selahcue_engine::scene::GradientDirection;
    // An UNVALIDATED Layer::Gradient rect (via the public `render`) must not overflow-panic —
    // the clip is derived in i64, mirroring fill_rect/draw_shape (86ajq3225 review fix).
    for rect in [
        Rect::new(i32::MAX, i32::MAX, u32::MAX, u32::MAX),
        Rect::new(1_200_000_000, 0, 1_200_000_000, 10),
        Rect::new(-5, -5, u32::MAX, u32::MAX),
        Rect::new(0, 0, 3_000_000_000, 20),
    ] {
        let mut f = Frame::new(32, 24).with_background(Rgba::BLACK);
        f.push(Layer::Gradient {
            rect,
            from: Rgba::BLACK,
            to: Rgba::WHITE,
            direction: GradientDirection::Horizontal,
        });
        let fb = render(&f); // must not panic
        assert_eq!((fb.width(), fb.height()), (32, 24));
    }
    // A rect wider than i32::MAX must still FILL the visible frame (the i64 clip), not be
    // silently dropped by an i32 cast going negative. `from` is red (≠ the black background),
    // so a drawn frame reads red near the from-edge; a dropped one would stay black.
    let mut f = Frame::new(64, 8).with_background(Rgba::BLACK);
    f.push(Layer::Gradient {
        rect: Rect::new(0, 0, 3_000_000_000, 8),
        from: Rgba::rgb(255, 0, 0),
        to: Rgba::WHITE,
        direction: GradientDirection::Horizontal,
    });
    let fb = render(&f);
    let p = fb.pixel(0, 4).unwrap();
    assert!(
        p.r > 200 && p.g < 40,
        "an oversized (w > i32::MAX) gradient still fills the frame, not silently dropped: {p:?}"
    );
}

// --- Per-output geometric transforms (Screens inspector): mirror / rotate / fit. Pure
// integer, deterministic (NFR-014) — the same transforms serve BOTH the on-screen blit and
// the operator preview thumbnails, so they are exercised headlessly here. ---

/// Build a `w×h` buffer from a per-pixel `(x,y) -> Rgba` closure (row-major RGBA8).
fn grid(w: u32, h: u32, f: impl Fn(u32, u32) -> Rgba) -> FrameBuffer {
    let mut px = Vec::with_capacity((w * h) as usize * 4);
    for y in 0..h {
        for x in 0..w {
            let c = f(x, y);
            px.extend_from_slice(&[c.r, c.g, c.b, c.a]);
        }
    }
    FrameBuffer::from_rgba(w, h, px).unwrap()
}

#[test]
fn mirror_horizontal_reverses_each_row_and_is_its_own_inverse() {
    // A distinct colour per column so a flip is observable.
    let src = grid(4, 2, |x, _| Rgba::rgb((x as u8 + 1) * 10, 0, 0));
    let m = src.mirrored_horizontal();
    assert_eq!((m.width(), m.height()), (4, 2));
    for y in 0..2 {
        for x in 0..4 {
            assert_eq!(m.pixel(x, y).unwrap(), src.pixel(3 - x, y).unwrap());
        }
    }
    // Mirroring twice is the identity (byte-identical).
    assert!(m.mirrored_horizontal() == src);
}

#[test]
fn rotate_90_swaps_dimensions_and_maps_corners_clockwise() {
    // Top-left pixel is unique; after a 90° CW turn it must land at the top-RIGHT.
    let src = grid(3, 2, |x, y| Rgba::rgb(x as u8, y as u8, 0));
    let r = src.rotated(1);
    assert_eq!((r.width(), r.height()), (2, 3)); // 90°/270° swap w/h
                                                 // Source (0,0) -> dest (h-1, 0) = (1, 0) for a clockwise turn.
    assert_eq!(r.pixel(1, 0).unwrap(), src.pixel(0, 0).unwrap());
    // Four quarter-turns return to the original, byte-identical.
    assert!(src.rotated(1).rotated(1).rotated(1).rotated(1) == src);
    // 180° twice is the identity; a 0-turn is an unchanged clone.
    assert!(src.rotated(2).rotated(2) == src);
    assert!(src.rotated(0) == src);
    // `quarter_turns` is taken mod 4.
    assert!(src.rotated(5) == src.rotated(1));
}

#[test]
fn fit_stretch_hits_exact_surface_size() {
    let src = grid(2, 2, |x, y| Rgba::rgb(x as u8 * 100, y as u8 * 100, 0));
    let out = src.fitted(6, 4, selahcue_engine::raster::Fit::Stretch);
    assert_eq!((out.width(), out.height()), (6, 4));
}

#[test]
fn fit_contain_letterboxes_with_black_bars_and_exact_size() {
    // A wide (4:1) source into a square surface must letterbox top+bottom with black.
    let src = grid(8, 2, |_, _| Rgba::WHITE);
    let out = src.fitted(8, 8, selahcue_engine::raster::Fit::Fit);
    assert_eq!((out.width(), out.height()), (8, 8));
    // Top and bottom rows are black bars; the middle band carries the (white) image.
    assert_eq!(out.pixel(4, 0).unwrap(), Rgba::BLACK);
    assert_eq!(out.pixel(4, 7).unwrap(), Rgba::BLACK);
    assert_eq!(out.pixel(4, 4).unwrap(), Rgba::WHITE);
}

#[test]
fn fit_cover_fills_every_pixel_no_black_bars_and_exact_size() {
    // Cover a square surface from a wide source: no black bars — every pixel is image.
    let src = grid(8, 2, |_, _| Rgba::WHITE);
    let out = src.fitted(8, 8, selahcue_engine::raster::Fit::Fill);
    assert_eq!((out.width(), out.height()), (8, 8));
    for y in 0..8 {
        for x in 0..8 {
            assert_eq!(
                out.pixel(x, y).unwrap(),
                Rgba::WHITE,
                "cover leaves no bars"
            );
        }
    }
}

#[test]
fn transforms_preserve_buffer_byte_length_invariant() {
    // A rotate/mirror never changes the pixel COUNT (w*h*4) — bounded-memory sanity.
    let src = grid(5, 3, |x, y| Rgba::rgb(x as u8, y as u8, 7));
    assert_eq!(src.mirrored_horizontal().byte_len(), src.byte_len());
    assert_eq!(src.rotated(1).byte_len(), src.byte_len());
    assert_eq!(src.rotated(2).byte_len(), src.byte_len());
    // A fit to an explicit size has exactly that many bytes.
    let fit = src.fitted(10, 10, selahcue_engine::raster::Fit::Stretch);
    assert_eq!(fit.byte_len(), 10 * 10 * 4);
}

// --- Static-prefix cache (scripture-select latency fix) --------------------------------
// Slide navigation re-renders the same theme background (image/gradient/band) with only
// the text layers changing; `render` caches that static prefix in a GLOBAL, mutex-guarded
// store bounded by a byte budget (PREFIX_CACHE_MAX_RESIDENT_BYTES, LRU-evicted to fit),
// an entry cap (PREFIX_CACHE_MAX_ENTRIES) and a per-entry cap (PREFIX_CACHE_BYTE_CAP),
// so the bound holds no matter how many threads render. These tests pin three contracts:
// byte-identical output (a PROVEN cache hit must be indistinguishable from a cold
// render), bounded memory, and multi-surface hit retention (three+ distinct surface
// prefixes must coexist — the fixed 2-slot store thrashed to a 0% hit rate there).
// The store is process-global: the tests in this module serialize on a lock, and the
// bounded-memory assertions are written to hold under interference from the rest of
// the binary (invariants, not exact snapshots of the shared store).

mod prefix_cache {
    use super::*;
    use selahcue_engine::raster::{
        prefix_cache_clear, prefix_cache_hits_for, prefix_cache_resident_bytes,
        PREFIX_CACHE_BYTE_CAP, PREFIX_CACHE_MAX_RESIDENT_BYTES,
    };
    use selahcue_engine::scene::{ImageFit, MediaRef};
    use std::time::{Duration, Instant};

    /// Serializes the tests in THIS module. The cache is process-global and these tests
    /// assert on per-key hit counts and clear the store — interleaved, one test's
    /// `prefix_cache_clear`/evictions would invalidate another's hit signal (measured:
    /// the byte-identity test silently degenerated to `render(x) == render(x)` when its
    /// warm entry was evicted by a sibling running concurrently). Poisoning is recovered
    /// so one failing test cannot mask the others.
    static CACHE_TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    fn serialize_cache_tests() -> std::sync::MutexGuard<'static, ()> {
        CACHE_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// The residency invariant the no-leak rule demands: the global byte budget itself.
    /// Exact, no allowance — eviction uses the SAME accounting the reporter sums (pixels
    /// plus prefix keys), so an insert can never push the reported total past the budget.
    fn residency_bound() -> usize {
        PREFIX_CACHE_MAX_RESIDENT_BYTES
    }

    /// A tiny valid RGBA PNG on disk (the decode cache resolves by path).
    fn png_file(dir: &std::path::Path, name: &str, c: Rgba) -> std::path::PathBuf {
        let mut data = Vec::new();
        for _ in 0..(4 * 4) {
            data.extend_from_slice(&[c.r, c.g, c.b, c.a]);
        }
        let mut out = Vec::new();
        {
            let mut enc = png::Encoder::new(&mut out, 4, 4);
            enc.set_color(png::ColorType::Rgba);
            enc.set_depth(png::BitDepth::Eight);
            enc.write_header().unwrap().write_image_data(&data).unwrap();
        }
        let p = dir.join(name);
        std::fs::write(&p, out).unwrap();
        p
    }

    /// A themed frame: image background + band fill (the static prefix) + a verse text.
    fn themed_frame(img: &std::path::Path, verse: &str) -> Frame {
        let mut f = Frame::new(320, 180).with_background(Rgba::rgb(10, 10, 20));
        f.push(Layer::Image {
            rect: Rect::new(0, 0, 320, 180),
            source: MediaRef::new(img.to_str().unwrap()).unwrap(),
            opacity: 255,
            fit: ImageFit::Fill,
        });
        f.push(Layer::Fill {
            rect: Rect::new(0, 140, 320, 40),
            color: Rgba::new(0, 0, 0, 160),
        });
        f.push(Layer::Text {
            rect: Rect::new(10, 40, 300, 100),
            text: verse.into(),
            px: 24,
            color: Rgba::rgb(240, 240, 240),
            align: TextAlign::Center,
            font: None,
            style: None,
        });
        f
    }

    #[test]
    fn a_cache_hit_is_byte_identical_to_a_cold_render() {
        let _serial = serialize_cache_tests();
        let dir =
            std::env::temp_dir().join(format!("selahcue-prefix-cache-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let img = png_file(&dir, "bg.png", Rgba::rgb(60, 90, 120));

        // Warm the cache with verse one, then render verse two THROUGH the cache…
        prefix_cache_clear();
        let _ = render(&themed_frame(&img, "For God so loved the world"));
        let warm = render(&themed_frame(&img, "that he gave his only Son"));
        // …and PROVE that render hit (insert on verse one = 0 hits, verse two = 1).
        // Without this the assertion below degenerates to `render(x) == render(x)` —
        // true for any deterministic renderer, cache present or not — whenever the
        // warm entry was silently evicted. This test guards the SSIM ≥ 0.99 GPU parity
        // oracle: a hit must be indistinguishable from a cold render, so first show a
        // hit actually happened.
        assert_eq!(
            prefix_cache_hits_for(&themed_frame(&img, "that he gave his only Son")),
            Some(1),
            "the warm render bypassed the prefix cache; the byte-identity contract was not exercised"
        );

        // …then drop every cached prefix and render verse two COLD.
        prefix_cache_clear();
        let cold = render(&themed_frame(&img, "that he gave his only Son"));

        assert_eq!(
            warm.bytes(),
            cold.bytes(),
            "a prefix-cache hit must produce byte-identical pixels to a cold render"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_cache_stays_bounded_under_many_threads_and_prefixes() {
        let _serial = serialize_cache_tests();
        // The no-leak contract, asserted against the GLOBAL accounting: distinct prefixes
        // hammered from many threads at once (the LAN server renders on tokio workers;
        // the desktop main thread composes too) must never grow total residency past
        // the byte budget — eviction, not accumulation.
        let workers: Vec<_> = (0..8u32)
            .map(|w| {
                std::thread::spawn(move || {
                    for i in 0..25u32 {
                        let mut f = Frame::new(320, 180).with_background(Rgba::rgb(
                            (w * 40 % 255) as u8,
                            (i % 255) as u8,
                            0,
                        ));
                        f.push(Layer::Fill {
                            rect: Rect::new(0, 0, 320, 20),
                            color: Rgba::rgb(0, (i % 255) as u8, (w % 255) as u8),
                        });
                        f.push(Layer::Text {
                            rect: Rect::new(10, 40, 300, 100),
                            text: format!("verse {w}/{i}"),
                            px: 24,
                            color: Rgba::rgb(240, 240, 240),
                            align: TextAlign::Left,
                            font: None,
                            style: None,
                        });
                        let _ = render(&f);
                        let resident = prefix_cache_resident_bytes();
                        assert!(
                            resident <= super::prefix_cache::residency_bound(),
                            "global prefix-cache residency {resident} exceeded its bound"
                        );
                    }
                })
            })
            .collect();
        for w in workers {
            w.join().unwrap();
        }
        let resident = prefix_cache_resident_bytes();
        // POSITIVE CONTROL. `resident <= bound` is trivially true of an EMPTY cache, so
        // on its own this test passes against an implementation that never caches
        // anything — the bound would be "held" by a mechanism that does not run.
        assert!(
            resident > 0,
            "positive control: the hammer must leave prefixes resident, else the bound \
             below is satisfied by an empty cache rather than by eviction"
        );
        assert!(
            resident <= residency_bound(),
            "global prefix-cache residency {resident} exceeded its bound after the hammer"
        );
    }

    #[test]
    fn an_over_cap_frame_renders_correctly_and_bypasses_the_cache() {
        // A frame past the per-entry byte cap must render correctly and must NOT be
        // cached — asserted on the entry itself (a residency-total comparison cannot
        // see it: 4100×2200 RGBA ≈ 36 MB fits under the global bound on its own).
        let _serial = serialize_cache_tests();
        // Compile-time premise: the frame must exceed the per-entry cap, so the test
        // cannot silently rot into an under-cap (vacuous) frame if the cap ever grows.
        const _: () = assert!(4100 * 2200 * 4 > PREFIX_CACHE_BYTE_CAP);
        let mut big = Frame::new(4100, 2200).with_background(Rgba::rgb(9, 9, 9));
        big.push(Layer::Fill {
            rect: Rect::new(0, 0, 4100, 60),
            color: Rgba::rgb(20, 20, 20),
        });
        // POSITIVE CONTROL. Asserting only that `big` is absent passes just as well
        // when NOTHING caches at all — the test would then be measuring a dead
        // mechanism and reporting it as a refusal. So first prove caching is live in
        // this very test, on an under-cap frame, and only then read `None` as "refused".
        let mut small = Frame::new(320, 180).with_background(Rgba::rgb(9, 9, 9));
        small.push(Layer::Fill {
            rect: Rect::new(0, 0, 320, 20),
            color: Rgba::rgb(20, 20, 20),
        });
        let _ = render(&small);
        let _ = render(&small);
        assert!(
            prefix_cache_hits_for(&small).is_some(),
            "positive control: an under-cap prefix must be cached, else this test's \
             `None` below proves nothing about the over-cap path"
        );

        // Render TWICE: were the frame ever inserted, the second render would find it.
        let fb = render(&big);
        assert_eq!(fb.bytes().len(), 4100 * 2200 * 4);
        let again = render(&big);
        assert_eq!(
            again.bytes(),
            fb.bytes(),
            "the uncached path must stay deterministic"
        );
        assert_eq!(
            prefix_cache_hits_for(&big),
            None,
            "an over-cap frame's prefix must never become resident in the cache"
        );
    }

    /// A themed FULL-RESOLUTION surface frame: image background + a per-surface mask
    /// band (the static prefix) + a verse text. Three surfaces → three DISTINCT
    /// prefixes (different image, size, background and mask), like the shipped
    /// configuration: audience output + an NDI-enabled screen (composed every frame)
    /// + the stage/confidence output.
    fn surface_frame(imgs: &[std::path::PathBuf], s: usize, verse: &str) -> Frame {
        let (w, h) = [(1920u32, 1080u32), (1280, 720), (1920, 1080)][s];
        let mut f = Frame::new(w, h).with_background(Rgba::rgb(8 + 30 * s as u8, 10, 20));
        f.push(Layer::Image {
            rect: Rect::new(0, 0, w, h),
            source: MediaRef::new(imgs[s].to_str().unwrap()).unwrap(),
            opacity: 255,
            fit: ImageFit::Fill,
        });
        f.push(Layer::Fill {
            rect: Rect::new(0, (h - 120 - 20 * s as u32) as i32, w, 120),
            color: Rgba::new(0, 0, 0, 140 + s as u8),
        });
        f.push(Layer::Text {
            rect: Rect::new(40, 200, w - 80, 400),
            text: verse.into(),
            px: 48,
            color: Rgba::rgb(240, 240, 240),
            align: TextAlign::Center,
            font: None,
            style: None,
        });
        f
    }

    #[test]
    fn a_multi_surface_verse_burst_keeps_every_surface_prefix_cached() {
        // Regression guard for the multi-surface eviction cliff. A fixed 2-slot store
        // round-robins three distinct prefixes through two slots, so EVERY compose
        // misses and re-scales its background at full output resolution — the shipped
        // product reaches exactly that shape (per-screen NDI composes every frame +
        // the audience theme + stage/confidence). Two teeth, so a fast machine cannot
        // hide thrashing: a wall-clock budget on the warmed burst, and a per-surface
        // hit-count check that fails DETERMINISTICALLY when any surface's prefix was
        // evicted mid-burst. Budgets mirror the slide-trigger NFR convention: release
        // enforces the real budget (`make nfr` runs this test); debug keeps a generous
        // tripwire that still fails the thrashing store by a wide margin.
        let budget = if cfg!(debug_assertions) {
            Duration::from_millis(2500)
        } else {
            Duration::from_millis(300)
        };
        let _serial = serialize_cache_tests();
        let dir =
            std::env::temp_dir().join(format!("selahcue-prefix-burst-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let imgs = vec![
            png_file(&dir, "a.png", Rgba::rgb(60, 90, 120)),
            png_file(&dir, "b.png", Rgba::rgb(120, 60, 90)),
            png_file(&dir, "c.png", Rgba::rgb(90, 120, 60)),
        ];

        // Warm every surface once OUTSIDE the timed burst (the one-off cold compose is
        // the slide-trigger budget; the burst is the steady navigation path).
        prefix_cache_clear();
        for s in 0..3 {
            let _ = render(&surface_frame(&imgs, s, "warm"));
        }

        let start = Instant::now();
        for i in 2..10 {
            for s in 0..3 {
                let f = surface_frame(&imgs, s, &format!("verse {i} of the reading"));
                let fb = render(&f);
                assert_eq!(
                    fb.bytes().len(),
                    (f.width as usize) * (f.height as usize) * 4,
                    "every surface compose must produce a full frame"
                );
            }
        }
        let elapsed = start.elapsed();
        let _ = std::fs::remove_dir_all(&dir);
        eprintln!("3-surface 24-compose warmed burst: {elapsed:?} (budget {budget:?})");
        assert!(
            elapsed <= budget,
            "24-compose 3-surface burst exceeded {budget:?}: {elapsed:?} — the prefix \
             cache is thrashing across surfaces"
        );
        // Deterministic tooth: after the burst each surface's prefix must still be
        // resident and must have served all eight of its composes as hits.
        for s in 0..3 {
            let hits = prefix_cache_hits_for(&surface_frame(&imgs, s, "probe"));
            assert!(
                hits.unwrap_or(0) >= 8,
                "surface {s} prefix served {hits:?} hits (expected >= 8) — it was \
                 evicted mid-burst by the other surfaces"
            );
        }
    }
}
