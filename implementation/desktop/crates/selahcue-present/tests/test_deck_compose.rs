//! Composing an authored deck slide to a frame, the Fade crossfade, and media-usage
//! correlation (Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use selahcue_core::media::{MediaKind, MediaLibrary};
use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_present::deck::media_usage;
use selahcue_present::{
    compose_authored_slide, crossfade, AuthoredSlide, Background, Element, ImageBackground,
    ImageFit, MediaRef, Rgba, ShapeKind, SlideDeck, SlideId, Theme,
};

/// A full-frame shape filling the whole slide with `fill` at draw order `z`.
fn full_shape(fill: Rgba, z: i16, visible: bool) -> Element {
    Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        fill,
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 255,
        z,
        variant: ShapeKind::Rect,
        corner_permille: 0,
        visible,
    }
}

fn slide_with(elements: Vec<Element>, background: Option<Background>) -> AuthoredSlide {
    let mut s = AuthoredSlide::new(SlideId(1));
    s.elements = elements;
    s.background = background;
    s
}

#[test]
fn an_empty_slide_is_never_blank_it_fills_with_its_background() {
    // NFR-024: a slide with zero elements composes to a valid, non-failing frame whose pixels
    // are the slide's background — never nothing.
    let bg = Rgba::rgb(10, 20, 30);
    let slide = slide_with(vec![], Some(Background::Solid(bg)));
    let fb = render(&compose_authored_slide(&slide, &Theme::classic(), 64, 36));
    for (x, y) in [(0u32, 0u32), (32, 18), (63, 35)] {
        assert_eq!(fb.pixel(x, y).unwrap(), bg, "every pixel is the background");
    }
}

#[test]
fn a_slide_without_a_background_falls_back_to_the_theme() {
    let theme = Theme::classic();
    let slide = slide_with(vec![], None);
    let fb = render(&compose_authored_slide(&slide, &theme, 32, 18));
    assert_eq!(
        fb.pixel(16, 9).unwrap(),
        theme.background.base_color(),
        "no per-slide background → the theme's background fills the frame"
    );
}

#[test]
fn slide_elements_render_and_hidden_elements_are_gated() {
    let bg = Rgba::rgb(0, 0, 0);
    let red = Rgba::rgb(220, 20, 20);
    // A full-frame red shape paints the whole frame red.
    let shown = slide_with(vec![full_shape(red, 0, true)], Some(Background::Solid(bg)));
    let fb = render(&compose_authored_slide(&shown, &Theme::classic(), 32, 18));
    assert_eq!(fb.pixel(16, 9).unwrap(), red, "a visible element renders");

    // The same shape hidden paints nothing → the background shows through (never-blank).
    let hidden = slide_with(vec![full_shape(red, 0, false)], Some(Background::Solid(bg)));
    let fb = render(&compose_authored_slide(&hidden, &Theme::classic(), 32, 18));
    assert_eq!(
        fb.pixel(16, 9).unwrap(),
        bg,
        "a hidden element emits no layer"
    );
}

#[test]
fn elements_composite_in_z_order_regardless_of_list_order() {
    let bg = Rgba::rgb(0, 0, 0);
    let red = Rgba::rgb(220, 20, 20);
    let blue = Rgba::rgb(20, 20, 220);
    // Blue has the higher z, so it wins — even when listed BEFORE red.
    let slide = slide_with(
        vec![full_shape(blue, 1, true), full_shape(red, 0, true)],
        Some(Background::Solid(bg)),
    );
    let fb = render(&compose_authored_slide(&slide, &Theme::classic(), 32, 18));
    assert_eq!(
        fb.pixel(16, 9).unwrap(),
        blue,
        "higher z composites in front"
    );
}

#[test]
fn compose_is_deterministic() {
    let slide = slide_with(
        vec![full_shape(Rgba::rgb(120, 200, 40), 0, true)],
        Some(Background::Solid(Rgba::rgb(5, 5, 5))),
    );
    let a = render(&compose_authored_slide(&slide, &Theme::classic(), 128, 72));
    let b = render(&compose_authored_slide(&slide, &Theme::classic(), 128, 72));
    assert_eq!(
        a.bytes(),
        b.bytes(),
        "the same slide always renders identically"
    );
}

#[test]
fn crossfade_endpoints_are_exact_and_the_midpoint_blends() {
    let from = FrameBuffer::filled(8, 8, Rgba::rgb(0, 0, 0));
    let to = FrameBuffer::filled(8, 8, Rgba::rgb(200, 100, 40));
    // progress 0 → exactly `from`; 255 → exactly `to`.
    assert_eq!(crossfade(&from, &to, 0).bytes(), from.bytes());
    assert_eq!(crossfade(&from, &to, 255).bytes(), to.bytes());
    // A mid blend sits strictly between the two per channel.
    let mid = crossfade(&from, &to, 128);
    let p = mid.pixel(4, 4).unwrap();
    assert!(p.r > 0 && p.r < 200, "red is partway between 0 and 200");
    assert!(p.g > 0 && p.g < 100, "green is partway between 0 and 100");
    // Deterministic: the same blend twice is byte-identical.
    assert_eq!(mid.bytes(), crossfade(&from, &to, 128).bytes());
}

#[test]
fn crossfade_returns_from_on_a_size_mismatch() {
    let from = FrameBuffer::filled(8, 8, Rgba::rgb(10, 10, 10));
    let to = FrameBuffer::filled(4, 4, Rgba::rgb(200, 200, 200));
    let out = crossfade(&from, &to, 128);
    assert_eq!(
        out.width(),
        8,
        "mismatched sizes → the outgoing frame, unchanged"
    );
    assert_eq!(out.bytes(), from.bytes());
}

#[test]
fn media_usage_splits_referenced_from_orphan_assets() {
    // Two imported assets; one deck references only "harvest.jpg" (as an image element) and
    // "particles.mov" (as a background) — so "sunrise.jpg" is unused.
    let mut lib = MediaLibrary::new();
    let harvest = lib
        .import("harvest.jpg", MediaKind::Image, 1, None, None, None, 0)
        .unwrap();
    let sunrise = lib
        .import("sunrise.jpg", MediaKind::Image, 1, None, None, None, 0)
        .unwrap();
    let particles = lib
        .import(
            "particles.mov",
            MediaKind::Video,
            1,
            None,
            None,
            Some(30_000),
            0,
        )
        .unwrap();

    let mut deck = SlideDeck::new("Deck");
    let s1 = deck.add_slide().unwrap();
    deck.get_mut(s1).unwrap().elements.push(Element::Image {
        x_permille: 0,
        y_permille: 0,
        w_permille: 500,
        h_permille: 500,
        source: MediaRef::new("harvest.jpg").unwrap(),
        opacity: 255,
        z: 0,
        visible: true,
        fit: ImageFit::default(),
    });
    let s2 = deck.add_slide().unwrap();
    deck.get_mut(s2).unwrap().background = Some(Background::Image(ImageBackground {
        source: MediaRef::new("particles.mov").unwrap(),
    }));

    let report = media_usage(&lib, &[&deck]);
    assert_eq!(
        report.used,
        vec![harvest, particles],
        "referenced assets are used"
    );
    assert_eq!(report.unused, vec![sunrise], "the orphan asset is unused");
}
