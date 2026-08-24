//! Owner decision aid: the audience scripture slide, rendered twice — as it ships today, and
//! re-skinned to Design 2.0. Same slide, same geometry, same fit; **only the palette differs**.
//!
//! This renders; it changes nothing. The Design 2.0 variant is a local `Theme` value built
//! here, so `theme.rs`'s shipped defaults and every token are untouched — nothing about what
//! the congregation sees moves until the owner decides.
//!
//! Writes PNGs only when `SELAHCUE_PALETTE_OUT=<dir>` is set, so an ordinary test run stays
//! side-effect free. The contrast figures print either way.

#![allow(clippy::unwrap_used)]

use png::{BitDepth, ColorType, Encoder};
use selahcue_present::tokens::{contrast_ratio, design2 as d2};
use selahcue_present::{compose_slide, Background, FrameBuffer, Rgba, Slide, Theme};
use std::fs::{self, File};
use std::io::BufWriter;
use std::path::Path;

const W: u32 = 1920;
const H: u32 = 1080;

/// A real verse with a reference line — the reference is what carries the gold/amber accent,
/// so a slide without one would render the two palettes almost identically and prove nothing.
fn scripture_slide() -> Slide {
    Slide::new(
        "Isaiah 61:5 · KJV",
        [
            "And strangers shall stand and feed your flocks,",
            "and the sons of the alien shall be your plowmen",
            "and your vinedressers.",
        ],
    )
}

fn solid(theme: &Theme) -> Rgba {
    match theme.background {
        Background::Solid(c) => c,
        _ => panic!("the audience scripture theme is not a solid fill"),
    }
}

fn hex(c: Rgba) -> String {
    format!("#{:02x}{:02x}{:02x}", c.r, c.g, c.b)
}

fn write_png(fb: &FrameBuffer, path: &Path) {
    let file = File::create(path).expect("create png");
    let mut enc = Encoder::new(BufWriter::new(file), fb.width(), fb.height());
    enc.set_color(ColorType::Rgba);
    enc.set_depth(BitDepth::Eight);
    let mut w = enc.write_header().expect("png header");
    w.write_image_data(fb.bytes()).expect("png data");
}

#[test]
fn render_the_audience_scripture_slide_in_both_palettes() {
    let slide = scripture_slide();

    // 1. As it ships. `Theme::classic()` IS what the compositor renders the audience output
    //    with — read from the shipped constructor rather than transcribed, so this cannot
    //    drift from the build.
    let shipped = Theme::classic();

    // 2. Re-skinned. The SAME theme with only the three colour roles moved onto `design2`.
    //    Every geometry field — region rects, sizes, line heights, alignment, fit — is
    //    inherited, so the two renders differ in nothing but palette.
    let mut d2_skin = Theme::classic();
    d2_skin.background = Background::Solid(d2::BASE.rgba);
    d2_skin.title.color = d2::GOLD.rgba;
    d2_skin.body.color = d2::TEXT.rgba;

    for (name, a, b) in [
        ("background", solid(&shipped), solid(&d2_skin)),
        (
            "accent (reference line)",
            shipped.title.color,
            d2_skin.title.color,
        ),
        ("verse ink", shipped.body.color, d2_skin.body.color),
    ] {
        println!("{name:<26} shipped {}  ->  design2 {}", hex(a), hex(b));
    }
    // Everything else must be identical, or the comparison is not isolating the palette.
    assert_eq!(shipped.title.x_permille, d2_skin.title.x_permille);
    assert_eq!(shipped.body.h_permille, d2_skin.body.h_permille);
    assert_eq!(shipped.body.size_permille, d2_skin.body.size_permille);
    assert_eq!(shipped.title.fit, d2_skin.title.fit);
    assert_eq!(shipped.body.fit, d2_skin.body.fit);

    let acc_ship = contrast_ratio(shipped.title.color, solid(&shipped));
    let acc_d2 = contrast_ratio(d2_skin.title.color, solid(&d2_skin));
    let ink_ship = contrast_ratio(shipped.body.color, solid(&shipped));
    let ink_d2 = contrast_ratio(d2_skin.body.color, solid(&d2_skin));
    println!("accent contrast   shipped {acc_ship:.2}:1   design2 {acc_d2:.2}:1");
    println!("verse  contrast   shipped {ink_ship:.2}:1   design2 {ink_d2:.2}:1");
    for (n, c) in [("shipped accent", acc_ship), ("design2 accent", acc_d2)] {
        assert!(c >= 4.5, "{n} = {c:.2}:1 fails AA");
    }

    let ship_fb = selahcue_engine::raster::render(&compose_slide(&slide, &shipped, W, H));
    let d2_fb = selahcue_engine::raster::render(&compose_slide(&slide, &d2_skin, W, H));

    // If the palettes rendered near-identically the comparison would be worthless, so
    // quantify the difference rather than asserting it exists.
    let mut changed = 0u64;
    for y in 0..H {
        for x in 0..W {
            if ship_fb.pixel(x, y) != d2_fb.pixel(x, y) {
                changed += 1;
            }
        }
    }
    let pct = changed as f64 / (W as f64 * H as f64) * 100.0;
    println!("pixels differing between the two renders: {pct:.2}%");

    if let Ok(dir) = std::env::var("SELAHCUE_PALETTE_OUT") {
        let dir = Path::new(&dir);
        fs::create_dir_all(dir).expect("create out dir");
        write_png(&ship_fb, &dir.join("audience-scripture-shipped.png"));
        write_png(&d2_fb, &dir.join("audience-scripture-design2.png"));
        println!("wrote {}", dir.display());
    }
}
