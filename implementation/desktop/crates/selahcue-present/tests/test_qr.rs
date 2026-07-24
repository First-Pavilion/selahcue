//! QR composition for the pairing invite (FR-086).

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::render;
use selahcue_engine::scene::Rgba;
use selahcue_present::{compose_qr, qr_modules};

const INVITE: &str =
    "selahcue://pair?host=192.168.1.20&port=53621&pin=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789&code=ABCD2345";

#[test]
fn invite_uri_encodes_to_modules() {
    let (side, modules) = qr_modules(INVITE).unwrap();
    assert!(side >= 21, "at least a version-1 code");
    assert_eq!(modules.len(), side * side);
    // A QR finder pattern makes the top-left module dark.
    assert!(modules[0], "finder pattern present");
    // Both colours occur (a QR is never all one colour).
    assert!(modules.iter().any(|m| !m));
}

#[test]
fn composed_qr_renders_black_on_white_with_quiet_zone() {
    let frame = compose_qr(INVITE, 360, 360).unwrap();
    let fb = render(&frame);
    // Quiet zone / background: corners are white.
    assert_eq!(fb.pixel(0, 0).unwrap(), Rgba::WHITE);
    assert_eq!(fb.pixel(359, 359).unwrap(), Rgba::WHITE);
    // Modules render black somewhere.
    let has_black = fb
        .bytes()
        .chunks_exact(4)
        .any(|p| p[0] == 0 && p[1] == 0 && p[2] == 0);
    assert!(has_black, "dark modules must render");
}

#[test]
fn degenerate_dimensions_do_not_panic() {
    assert!(compose_qr(INVITE, 0, 0).is_some());
    assert!(
        compose_qr(INVITE, 10, 10).is_some(),
        "tiny frame clips, never panics"
    );
}

#[test]
fn oversized_data_is_refused_not_panicked() {
    let huge = "x".repeat(20_000);
    assert!(qr_modules(&huge).is_none());
    assert!(compose_qr(&huge, 360, 360).is_none());
}
