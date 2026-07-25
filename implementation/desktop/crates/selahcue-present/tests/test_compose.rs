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
fn slide_draws_text_in_the_safe_area_with_theme_colors() {
    let theme = Theme::dark(); // 5% margin, white text, dark background
    let fb = render(&compose_slide(&Slide::title("HELLO"), &theme, 200, 100));
    // Background shows in the margin / corner.
    assert_eq!(fb.pixel(2, 2).unwrap(), theme.background);
    // The title renders glyph ink in the top-left of the safe area (margin ~10px).
    assert!(
        has_ink_in(&fb, 10, 5, 90, 22),
        "title glyphs should render in the safe area"
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
    // Many lines at a small height would, without a bottom guard, paint into the
    // bottom overscan band. The bottom inset must be honored symmetrically.
    let theme = Theme::dark(); // 5% margin -> margin_y = 2 at height 50
    let slide = Slide::new("Title", (0..10).map(|i| format!("Body line number {i}")));
    let fb = render(&compose_slide(&slide, &theme, 200, 50));
    // Text renders in the top safe area...
    assert!(
        has_ink_in(&fb, 10, 2, 60, 12),
        "text should render in the top safe area"
    );
    // ...but never any INK in the bottom safe margin band (rows >= height -
    // margin_y = 48) — the real overscan invariant, now robust to antialiasing
    // (a shaped descender leaking down would trip this, unlike an exact-white
    // check that AA greys would slip past).
    assert!(
        !has_ink_in(&fb, 0, 48, 200, 50),
        "no text ink in the bottom safe margin / at the bottom edge"
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
    // The physical line capacity the scripture slide cap relies on
    // (selahcue-app::SCRIPTURE_MAX_LINES = 6 body lines): at 10% line height +
    // 3% gap inside the 5% safe margin, exactly 7 text lines fit — a 7th body
    // line must be dropped by the bottom-edge break, so content past the cap
    // would silently vanish. If these metrics change, retune the cap.
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
