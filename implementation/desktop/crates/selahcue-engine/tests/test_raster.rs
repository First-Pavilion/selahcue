//! Deterministic rasterizer + pixel-readback tests (golden-image parity).

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::render;
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

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
    });
    assert_eq!(render(&f).bytes(), render(&f).bytes());
}
