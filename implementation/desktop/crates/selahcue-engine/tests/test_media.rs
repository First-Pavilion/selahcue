//! Image-decode foundation tests (S8-6, 86ajpzhbc): bounded/bomb-safe PNG decode,
//! `Layer::Image` blit (scale + opacity + z-order + determinism), the missing-media
//! placeholder + decoder-fault isolation (FR-070/NFR-024), and the bounded decode cache
//! (no-leak). PNG is the only decoded format this batch (deterministic, cross-OS).

#![allow(clippy::unwrap_used)]

use selahcue_engine::media::{
    image_cache_stats, reset_image_cache, MAX_IMAGE_CACHE_BYTES, MAX_IMAGE_CACHE_ENTRIES,
};
use selahcue_engine::{
    decode_png, render, DecodeError, DecodeLimits, EngineCommand, EngineEvent, Fault, Frame, Layer,
    MediaRef, Rect, Rgba,
};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

// --- fixtures -------------------------------------------------------------------------

/// Encode `data` (w*h*channels bytes) as an 8-bit PNG of the given colour type.
fn encode_png(w: u32, h: u32, color: png::ColorType, data: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut out, w, h);
        encoder.set_color(color);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().unwrap();
        writer.write_image_data(data).unwrap();
    }
    out
}

/// A solid-colour RGBA PNG.
fn solid_rgba_png(w: u32, h: u32, c: Rgba) -> Vec<u8> {
    let mut data = Vec::with_capacity((w * h * 4) as usize);
    for _ in 0..(w * h) {
        data.extend_from_slice(&[c.r, c.g, c.b, c.a]);
    }
    encode_png(w, h, png::ColorType::Rgba, &data)
}

/// A 2×2 RGBA PNG with four distinct corner colours (row-major: TL, TR, BL, BR).
fn quad_png(tl: Rgba, tr: Rgba, bl: Rgba, br: Rgba) -> Vec<u8> {
    let mut d = Vec::with_capacity(16);
    for c in [tl, tr, bl, br] {
        d.extend_from_slice(&[c.r, c.g, c.b, c.a]);
    }
    encode_png(2, 2, png::ColorType::Rgba, &d)
}

static COUNTER: AtomicU64 = AtomicU64::new(0);

/// Write `bytes` to a unique temp file with the given extension and return its path.
fn temp_file(tag: &str, ext: &str, bytes: &[u8]) -> PathBuf {
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let mut p = std::env::temp_dir();
    p.push(format!(
        "selahcue_media_{}_{}_{}.{}",
        std::process::id(),
        tag,
        n,
        ext
    ));
    std::fs::write(&p, bytes).unwrap();
    p
}

fn image_layer(path: &std::path::Path, rect: Rect, opacity: u8) -> Layer {
    Layer::Image {
        rect,
        source: MediaRef::new(path.to_str().unwrap()).unwrap(),
        opacity,
    }
}

// --- C-002: bounded, bomb-safe, deterministic decode ----------------------------------

#[test]
fn a_valid_rgba_png_decodes_to_the_expected_pixels() {
    let bytes = quad_png(
        Rgba::rgb(255, 0, 0),
        Rgba::rgb(0, 255, 0),
        Rgba::rgb(0, 0, 255),
        Rgba::WHITE,
    );
    let img = decode_png(&bytes, &DecodeLimits::default()).unwrap();
    assert_eq!((img.width(), img.height()), (2, 2));
    assert_eq!(
        img.rgba(),
        &[255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255]
    );
}

#[test]
fn grayscale_rgb_and_rgba_all_normalize_to_straight_rgba8() {
    let def = DecodeLimits::default();
    // Grayscale 1×1 (value 100) → (100,100,100,255).
    let gray = encode_png(1, 1, png::ColorType::Grayscale, &[100]);
    assert_eq!(
        &decode_png(&gray, &def).unwrap().rgba()[..4],
        &[100, 100, 100, 255]
    );
    // RGB → opaque.
    let rgb = encode_png(1, 1, png::ColorType::Rgb, &[10, 20, 30]);
    assert_eq!(
        &decode_png(&rgb, &def).unwrap().rgba()[..4],
        &[10, 20, 30, 255]
    );
    // RGBA → alpha preserved (straight, not premultiplied).
    let rgba = encode_png(1, 1, png::ColorType::Rgba, &[10, 20, 30, 128]);
    assert_eq!(
        &decode_png(&rgba, &def).unwrap().rgba()[..4],
        &[10, 20, 30, 128]
    );
}

#[test]
fn decode_is_deterministic() {
    let bytes = quad_png(
        Rgba::rgb(1, 2, 3),
        Rgba::rgb(4, 5, 6),
        Rgba::rgb(7, 8, 9),
        Rgba::WHITE,
    );
    let def = DecodeLimits::default();
    assert_eq!(
        decode_png(&bytes, &def).unwrap(),
        decode_png(&bytes, &def).unwrap()
    );
}

#[test]
fn empty_and_non_png_inputs_are_rejected_without_panicking() {
    let def = DecodeLimits::default();
    assert_eq!(decode_png(&[], &def), Err(DecodeError::Empty));
    assert_eq!(
        decode_png(b"not a png at all", &def),
        Err(DecodeError::Unsupported)
    );
    // A JPEG magic number is not PNG → Unsupported (the later-format seam), not a decode.
    assert_eq!(
        decode_png(&[0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0, 0, 0], &def),
        Err(DecodeError::Unsupported)
    );
}

#[test]
fn truncated_and_corrupt_pngs_error_without_panicking() {
    let full = solid_rgba_png(8, 8, Rgba::WHITE);
    let def = DecodeLimits::default();
    // Truncated mid-stream → Malformed, never a panic.
    let mut truncated = full.clone();
    truncated.truncate(full.len() / 2);
    assert_eq!(decode_png(&truncated, &def), Err(DecodeError::Malformed));
    // Corrupt the IHDR-CRC + IDAT body (bytes after the 8-byte signature, before IEND),
    // keeping the signature so it still passes the allowlist → a decode error, never a
    // panic. This is the compressed-pixel region, whose CRC/inflate checks must catch it.
    let mut corrupt = full.clone();
    let n = corrupt.len();
    for b in corrupt.iter_mut().take(n.saturating_sub(12)).skip(16) {
        *b ^= 0xFF;
    }
    assert!(
        decode_png(&corrupt, &def).is_err(),
        "corrupt PNG must error, not panic"
    );
}

#[test]
fn oversize_dimensions_are_rejected_before_allocation() {
    // A valid 4×4 image against tight dimension/pixel caps → Oversize BEFORE the output
    // buffer is allocated (decompression-bomb defense, FR-173).
    let bytes = solid_rgba_png(4, 4, Rgba::WHITE);
    let tight = DecodeLimits {
        max_width: 2,
        max_height: 2,
        max_pixels: 4,
        max_encoded_bytes: 1 << 20,
    };
    assert_eq!(decode_png(&bytes, &tight), Err(DecodeError::Oversize));
}

#[test]
fn an_over_budget_encoded_file_is_rejected() {
    let bytes = solid_rgba_png(4, 4, Rgba::WHITE);
    let small = DecodeLimits {
        max_encoded_bytes: 4,
        ..DecodeLimits::default()
    };
    assert_eq!(decode_png(&bytes, &small), Err(DecodeError::TooLarge));
    // And within a generous cap the same image decodes fine (no false rejection).
    assert!(decode_png(&bytes, &DecodeLimits::default()).is_ok());
}

// --- C-003: Layer::Image blit — scale, opacity, z-order, determinism ------------------

#[test]
fn an_image_layer_blits_the_decoded_pixels_scaled_into_its_rect() {
    // 2×2 four-colour source → nearest-scaled into a 4×4 frame: each source pixel fills
    // a 2×2 destination quadrant (pure integer nearest → deterministic, cross-OS).
    let (red, green, blue, white) = (
        Rgba::rgb(255, 0, 0),
        Rgba::rgb(0, 255, 0),
        Rgba::rgb(0, 0, 255),
        Rgba::WHITE,
    );
    let path = temp_file("quad", "png", &quad_png(red, green, blue, white));
    let mut f = Frame::new(4, 4);
    f.push(image_layer(&path, Rect::new(0, 0, 4, 4), 255));
    let fb = render(&f);
    assert_eq!(fb.pixel(0, 0).unwrap(), red, "TL quadrant");
    assert_eq!(fb.pixel(3, 0).unwrap(), green, "TR quadrant");
    assert_eq!(fb.pixel(0, 3).unwrap(), blue, "BL quadrant");
    assert_eq!(fb.pixel(3, 3).unwrap(), white, "BR quadrant");
    assert_eq!(fb.pixel(1, 1).unwrap(), red, "still inside the TL quadrant");
}

#[test]
fn image_render_is_deterministic() {
    let path = temp_file("det", "png", &solid_rgba_png(3, 3, Rgba::rgb(12, 34, 56)));
    let mut f = Frame::new(9, 9);
    f.push(image_layer(&path, Rect::new(0, 0, 9, 9), 255));
    reset_image_cache();
    let a = render(&f).bytes().to_vec();
    let b = render(&f).bytes().to_vec();
    assert_eq!(a, b, "the same image scene renders byte-identically");
}

#[test]
fn image_layer_opacity_blends_over_what_is_beneath() {
    // A 50%-opacity white image over a black background → mid-grey (single src-over blend).
    let path = temp_file("op", "png", &solid_rgba_png(1, 1, Rgba::WHITE));
    let mut f = Frame::new(2, 2); // black background
    f.push(image_layer(&path, Rect::new(0, 0, 2, 2), 128));
    let p = render(&f).pixel(0, 0).unwrap();
    assert!(
        (120..=136).contains(&p.r) && (120..=136).contains(&p.g) && (120..=136).contains(&p.b),
        "50% white over black blends to mid grey, got {p:?}"
    );
}

#[test]
fn image_layer_z_order_relative_to_fills() {
    let path = temp_file("z", "png", &solid_rgba_png(1, 1, Rgba::WHITE));
    let img = |op| image_layer(&path, Rect::new(0, 0, 4, 4), op);
    let red_fill = |rect| Layer::Fill {
        rect,
        color: Rgba::rgb(255, 0, 0),
    };

    // Image BEHIND: a later opaque fill paints over the image where they overlap.
    let mut behind = Frame::new(4, 4);
    behind.push(img(255));
    behind.push(red_fill(Rect::new(0, 0, 2, 2)));
    let fb = render(&behind);
    assert_eq!(
        fb.pixel(0, 0).unwrap(),
        Rgba::rgb(255, 0, 0),
        "fill occludes the image"
    );
    assert_eq!(
        fb.pixel(3, 3).unwrap(),
        Rgba::WHITE,
        "image shows where the fill is not"
    );

    // Image IN FRONT: the image paints over the fill.
    let mut front = Frame::new(4, 4);
    front.push(red_fill(Rect::new(0, 0, 4, 4)));
    front.push(img(255));
    assert_eq!(
        render(&front).pixel(0, 0).unwrap(),
        Rgba::WHITE,
        "image occludes the fill"
    );
}

#[test]
fn out_of_frame_image_rect_is_clipped_without_panicking() {
    // A rect straddling the frame edge must clip, not panic (mirrors the Fill/Text clip).
    let path = temp_file("clip", "png", &solid_rgba_png(4, 4, Rgba::WHITE));
    let mut f = Frame::new(4, 4);
    f.push(image_layer(&path, Rect::new(-2, -2, 8, 8), 255));
    let fb = render(&f);
    assert_eq!(
        fb.pixel(0, 0).unwrap(),
        Rgba::WHITE,
        "the visible portion still draws"
    );
}

// --- C-004: placeholder + decoder-fault isolation (FR-070, NFR-024) -------------------

fn assert_placeholder_drawn(f: &Frame) {
    let fb = render(f); // must not panic
                        // The muted purple-grey placeholder base (never black) fills the interior.
    assert_eq!(
        fb.pixel(6, 1).unwrap(),
        Rgba::rgb(64, 54, 74),
        "a decode failure draws the non-black placeholder, never a blank rect"
    );
    assert_ne!(fb.pixel(6, 1).unwrap(), Rgba::BLACK);
}

#[test]
fn a_missing_image_draws_the_placeholder_not_a_crash() {
    let mut f = Frame::new(8, 8);
    f.push(Layer::Image {
        rect: Rect::new(0, 0, 8, 8),
        source: MediaRef::new("/no/such/file/anywhere.png").unwrap(),
        opacity: 255,
    });
    assert_placeholder_drawn(&f);
}

#[test]
fn a_corrupt_or_unsupported_image_draws_the_placeholder() {
    // Corrupt bytes that carry the PNG signature but are otherwise garbage.
    let mut corrupt = vec![0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];
    corrupt.extend_from_slice(&[0u8; 32]);
    let cpath = temp_file("corrupt", "png", &corrupt);
    let mut f1 = Frame::new(8, 8);
    f1.push(image_layer(&cpath, Rect::new(0, 0, 8, 8), 255));
    assert_placeholder_drawn(&f1);

    // A non-PNG file (unsupported format) → placeholder, not a decode, not a crash.
    let upath = temp_file("gif", "gif", b"GIF89a fake gif payload that is not a png");
    let mut f2 = Frame::new(8, 8);
    f2.push(Layer::Image {
        rect: Rect::new(0, 0, 8, 8),
        source: MediaRef::new(upath.to_str().unwrap()).unwrap(),
        opacity: 255,
    });
    assert_placeholder_drawn(&f2);
}

#[test]
fn the_placeholder_never_panics_on_an_adversarial_image_rect() {
    // A crafted/missing image with an EXTREME (unvalidated) layer rect must still
    // contain to the placeholder — never an integer-overflow panic (FR-173/NFR-024).
    // Regression for the draw_placeholder i32/i64 overflow the review caught.
    let missing = |rect: Rect| {
        let mut f = Frame::new(64, 64);
        f.push(Layer::Image {
            rect,
            source: MediaRef::new("/no/such/file/for/overflow.png").unwrap(),
            opacity: 255,
        });
        render(&f) // must not panic (dev/test builds have overflow-checks on)
    };

    // A rect spanning the whole i32/u32 range: old code did `x + w` (i32::MIN + -1) and
    // `u * rh` (i64) → overflow panic. It covers the whole 64×64 frame → base is drawn.
    let fb = missing(Rect::new(i32::MIN, 0, u32::MAX, u32::MAX));
    assert_ne!(
        fb.pixel(10, 10).unwrap(),
        Rgba::BLACK,
        "placeholder base is non-black"
    );

    // A rect whose `x + w` overflows i32 but is entirely off-screen → no draw, no panic.
    let _ = missing(Rect::new(2_000_000_000, 0, 2_000_000_000, 10));
    // A negative-origin rect partially on-screen → clips, draws, no panic.
    let fb3 = missing(Rect::new(-10, -10, 40, 40));
    assert_ne!(
        fb3.pixel(0, 0).unwrap(),
        Rgba::BLACK,
        "the visible corner draws the placeholder"
    );
}

#[test]
fn a_decoder_fault_holds_the_last_good_frame_and_never_blanks() {
    // The runtime decoder-failure path (NFR-024): a DecoderFault holds the last good
    // output rather than blanking it, and a second output is unaffected.
    let mut a = selahcue_engine::Engine::new(16, 16);
    let mut good = Frame::new(16, 16).with_background(Rgba::rgb(20, 40, 60));
    good.push(Layer::Fill {
        rect: Rect::new(2, 2, 6, 6),
        color: Rgba::rgb(200, 100, 50),
    });
    a.apply(EngineCommand::SetScene { frame: good });
    let held = a.output().bytes().to_vec();

    let b = selahcue_engine::Engine::new(16, 16);
    let b_before = b.output().bytes().to_vec();

    let ev = a.apply(EngineCommand::InjectFault {
        fault: Fault::DecoderFault,
    });
    assert_eq!(
        ev,
        EngineEvent::OutputHeld {
            fault: Fault::DecoderFault
        }
    );
    assert_eq!(
        a.output().bytes(),
        &held[..],
        "the faulted output holds its last good frame"
    );
    assert!(a.is_faulted());
    assert_eq!(
        b.output().bytes(),
        &b_before[..],
        "a fault on one output never affects another"
    );
}

// --- C-005: bounded decode cache (no-leak) + no pixels in the serde Frame --------------

#[test]
fn the_image_decode_cache_stays_bounded_over_many_distinct_images() {
    reset_image_cache();
    // Reference far more distinct images than the entry cap so the bound is exercised
    // repeatedly; the cache must never exceed either bound.
    let n = MAX_IMAGE_CACHE_ENTRIES as u32 * 3 + 7;
    for i in 0..n {
        let color = Rgba::rgb((i & 255) as u8, ((i >> 8) & 255) as u8, 0);
        let path = temp_file(&format!("bound{i}"), "png", &solid_rgba_png(2, 2, color));
        let mut f = Frame::new(4, 4);
        f.push(image_layer(&path, Rect::new(0, 0, 4, 4), 255));
        let _ = render(&f);
        let (entries, bytes) = image_cache_stats();
        assert!(
            entries <= MAX_IMAGE_CACHE_ENTRIES,
            "entries bounded: {entries}"
        );
        assert!(bytes <= MAX_IMAGE_CACHE_BYTES, "bytes bounded: {bytes}");
    }
    reset_image_cache();
    assert_eq!(image_cache_stats(), (0, 0), "reset frees the cache");
}

#[test]
fn decoded_pixels_never_ride_the_serde_frame() {
    // The scene carries a bounded REFERENCE, never pixels — so a Frame with an image
    // serializes tiny regardless of the referenced image's size (keeps IPC bounded).
    let mut f = Frame::new(64, 64);
    f.push(Layer::Image {
        rect: Rect::new(0, 0, 64, 64),
        source: MediaRef::new("/media/very/large/background.png").unwrap(),
        opacity: 255,
    });
    let json = serde_json::to_string(&f).unwrap();
    assert!(
        json.len() < 2048,
        "the scene carries only a bounded reference, not pixels ({} bytes)",
        json.len()
    );
    assert!(json.contains("/media/very/large/background.png"));
}
