//! Slide composition: deterministic layout of text over the theme background.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_present::{compose_slide, Slide, Theme};

/// Whether any glyph INK (a pixel meaningfully brighter than the dark theme
/// background) appears in the region. Real shaping antialiases glyph edges, so
/// most glyph pixels are partial-coverage greys — an exact-colour match would
/// miss them; this coverage check is the correct oracle for shaped text.
fn has_ink_in(fb: &FrameBuffer, x0: u32, y0: u32, x1: u32, y1: u32) -> bool {
    (y0..y1).any(|y| {
        (x0..x1).any(|x| {
            fb.pixel(x, y)
                .map(|p| p.r as u32 + p.g as u32 + p.b as u32 > 90)
                .unwrap_or(false)
        })
    })
}

#[test]
fn blank_slide_is_background_only() {
    let theme = Theme::dark();
    let fb = render(&compose_slide(&Slide::title(""), &theme, 64, 36));
    for y in [0u32, 18, 35] {
        for x in [0u32, 32, 63] {
            assert_eq!(fb.pixel(x, y).unwrap(), theme.background);
        }
    }
}

#[test]
fn title_only_slide_renders_centred_in_the_body_region() {
    // A title-only slide (e.g. a section header) is the MAIN content, so the
    // classic theme centres it in the body region — not a small top header.
    let theme = Theme::dark(); // classic: centred white body over a dark bg
    let fb = render(&compose_slide(&Slide::title("HELLO"), &theme, 200, 100));
    // Background shows in the corner (outside any region).
    assert_eq!(fb.pixel(2, 2).unwrap(), theme.background);
    // Ink appears in the body region (classic body ≈ x[12..188], y[28..84]),
    // and around the horizontal centre (centre alignment), not hugging the left.
    assert!(
        has_ink_in(&fb, 12, 28, 188, 84),
        "title renders in the body region"
    );
    assert!(
        has_ink_in(&fb, 70, 28, 130, 84),
        "centre-aligned text has ink near the horizontal centre"
    );
}

#[test]
fn text_stays_within_the_frame() {
    // A long multi-line slide must not panic or paint outside the frame.
    let theme = Theme::dark();
    let slide = Slide::new(
        "A very long title that would overflow the safe width many times over",
        (0..40).map(|i| format!("body line {i}")),
    );
    let fb = render(&compose_slide(&slide, &theme, 128, 72));
    // Corners remain background (safe-area inset respected; nothing overflowed).
    assert_eq!(fb.pixel(127, 71).unwrap(), theme.background);
    assert_eq!(fb.pixel(0, 0).unwrap(), theme.background);
}

#[test]
fn text_never_paints_into_the_bottom_safe_margin() {
    // The classic theme's regions sit inside the frame (body bottom ≈ 84% of the
    // height), so a long slide must never paint into the bottom overscan band.
    let theme = Theme::dark();
    let slide = Slide::new("Title", (0..10).map(|i| format!("Body line number {i}")));
    let fb = render(&compose_slide(&slide, &theme, 200, 100));
    // Something renders (the design is not blank)...
    assert!(has_ink_in(&fb, 0, 0, 200, 100), "the themed slide renders");
    // ...but no INK in the bottom overscan band (classic body ends at ≈84% →
    // rows ≥ 90 must stay background — robust to antialiased descenders).
    assert!(
        !has_ink_in(&fb, 0, 90, 200, 100),
        "no text ink in the bottom overscan band"
    );
}

#[test]
fn compose_is_deterministic() {
    let theme = Theme::dark();
    let slide = Slide::new("Verse 1", ["Amazing grace", "how sweet the sound"]);
    let a = render(&compose_slide(&slide, &theme, 320, 180));
    let b = render(&compose_slide(&slide, &theme, 320, 180));
    assert_eq!(a.bytes(), b.bytes());
}

#[test]
fn compose_slide_renders_title_plus_six_body_lines() {
    // The classic theme's body region is sized to the scripture cap
    // (selahcue-app::SCRIPTURE_MAX_LINES = 6): the title renders in the title
    // region (1 layer) and up to 6 body lines in the body region, so a 7th body
    // line clips. Keeps the engine's line capacity aligned with the cap.
    use selahcue_engine::scene::Layer;
    let count_text = |body: usize| {
        let slide = Slide::new(
            "Title",
            (0..body).map(|i| format!("line {i}")).collect::<Vec<_>>(),
        );
        compose_slide(&slide, &Theme::dark(), 1920, 1080)
            .layers
            .iter()
            .filter(|l| matches!(l, Layer::Text { .. }))
            .count()
    };
    assert_eq!(count_text(6), 7, "title + 6 body lines all render");
    assert_eq!(count_text(7), 7, "a 7th body line is clipped");
}
