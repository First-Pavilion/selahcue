//! Slide composition: deterministic layout of text over the theme background.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_engine::scene::Rgba;
use selahcue_present::{compose_slide, Slide, Theme};

/// Whether any pixel of `color` appears in the `[x0,x1) × [y0,y1)` region — glyph
/// coverage is sparse, so we scan a band rather than asserting an exact pixel.
fn has_color_in(fb: &FrameBuffer, x0: u32, y0: u32, x1: u32, y1: u32, color: Rgba) -> bool {
    (y0..y1).any(|y| (x0..x1).any(|x| fb.pixel(x, y) == Some(color)))
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
    // The title renders glyph pixels in the top-left of the safe area (margin ~10px).
    assert!(
        has_color_in(&fb, 10, 5, 90, 16, theme.text),
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
        has_color_in(&fb, 10, 2, 60, 8, theme.text),
        "text should render in the top safe area"
    );
    // ...but never in the bottom safe margin band (rows >= height - margin_y = 48).
    assert!(
        !has_color_in(&fb, 0, 48, 200, 50, theme.text),
        "no text in the bottom safe margin / at the bottom edge"
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
