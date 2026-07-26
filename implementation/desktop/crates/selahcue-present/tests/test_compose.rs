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
fn shrink_to_fit_renders_all_body_lines_by_scaling_not_clipping() {
    // Fit::ShrinkToFit is the default for every built-in (owner refine): the body
    // region renders the classic 6-line verse at its DESIGN size, and MORE lines
    // shrink to fit rather than clipping — no line is ever dropped.
    use selahcue_engine::scene::Layer;
    // (number of text layers, first BODY line's px). compose pushes the title
    // region first (layers[0]) then the body lines, so texts[1] is a body cell.
    let body = |lines: usize| -> (usize, u32) {
        let slide = Slide::new(
            "Title",
            (0..lines).map(|i| format!("line {i}")).collect::<Vec<_>>(),
        );
        let texts: Vec<u32> = compose_slide(&slide, &Theme::dark(), 1920, 1080)
            .layers
            .iter()
            .filter_map(|l| match l {
                Layer::Text { px, .. } => Some(*px),
                _ => None,
            })
            .collect();
        (texts.len(), texts.get(1).copied().unwrap_or(0))
    };
    let (n6, px6) = body(6);
    let (n12, px12) = body(12);
    assert_eq!(n6, 7, "title + 6 body lines render");
    assert_eq!(
        n12, 13,
        "title + 12 body lines ALL render (shrunk, not clipped)"
    );
    // Proof it SHRANK: 12 lines render smaller than 6 (which are at design size).
    assert!(
        px12 < px6,
        "more lines => smaller body text (shrink-to-fit): {px12} < {px6}"
    );
}
