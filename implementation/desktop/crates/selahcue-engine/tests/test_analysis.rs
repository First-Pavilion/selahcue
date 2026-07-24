//! Flash-rate analyzer (FR-175) and latency proxy (NFR-004) tests.

#![allow(clippy::unwrap_used)]

use selahcue_engine::analysis::{analyze_flashes, frames_to_secs, frames_until};
use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

fn solid(color: Rgba) -> FrameBuffer {
    render(&Frame::new(16, 16).with_background(color))
}

#[test]
fn strobe_exceeds_the_flash_limit() {
    // Alternating black/white at 10 fps — well over 3 flashes/sec.
    let frames: Vec<_> = (0..10)
        .map(|i| solid(if i % 2 == 0 { Rgba::BLACK } else { Rgba::WHITE }))
        .collect();
    let report = analyze_flashes(&frames, 10.0);
    assert!(
        report.luminance_flashes_per_sec > 3.0,
        "strobe should trip the limit: {report:?}"
    );
    assert!(!report.passes);
}

#[test]
fn calm_sequence_passes() {
    // A single slow transition — nowhere near the limit.
    let frames = vec![
        solid(Rgba::BLACK),
        solid(Rgba::BLACK),
        solid(Rgba::rgb(40, 40, 40)),
        solid(Rgba::rgb(40, 40, 40)),
    ];
    let report = analyze_flashes(&frames, 10.0);
    assert!(report.passes, "calm sequence should pass: {report:?}");
}

#[test]
fn red_flashes_are_detected() {
    let frames: Vec<_> = (0..10)
        .map(|i| {
            solid(if i % 2 == 0 {
                Rgba::BLACK
            } else {
                Rgba::rgb(255, 0, 0)
            })
        })
        .collect();
    let report = analyze_flashes(&frames, 10.0);
    assert!(
        report.red_flashes_per_sec > 3.0,
        "red strobe should trip the red-flash limit: {report:?}"
    );
    assert!(!report.passes);
}

#[test]
fn latency_proxy_finds_first_content_frame() {
    // The new content (bright) first appears at index 3.
    let mut frames = vec![solid(Rgba::BLACK), solid(Rgba::BLACK), solid(Rgba::BLACK)];
    frames.push(solid(Rgba::WHITE));
    let idx = frames_until(&frames, |f| f.average_luminance() > 0.5).unwrap();
    assert_eq!(idx, 3);
    // At 60 fps, 3 frames ≈ 50 ms of input-to-photons latency.
    assert!((frames_to_secs(idx, 60.0) - 0.05).abs() < 1e-9);
}

#[test]
fn no_content_returns_none() {
    let frames = vec![solid(Rgba::BLACK), solid(Rgba::BLACK)];
    assert!(frames_until(&frames, |f| f.average_luminance() > 0.5).is_none());
}

#[test]
fn ssim_of_identical_is_one_and_diverges_for_different() {
    use selahcue_engine::analysis::ssim;
    let black = solid(Rgba::BLACK);
    let white = solid(Rgba::WHITE);
    assert!((ssim(&black, &black) - 1.0).abs() < 1e-9, "identical → 1.0");
    assert!(ssim(&black, &white) < 0.1, "black vs white → very low");
    // Mismatched dimensions → 0.0.
    let small = render(&Frame::new(4, 4));
    assert_eq!(ssim(&black, &small), 0.0);
}

#[test]
fn framebuffer_from_rgba_round_trips_and_validates() {
    let fb = solid(Rgba::rgb(10, 20, 30));
    let copy = FrameBuffer::from_rgba(fb.width(), fb.height(), fb.bytes().to_vec()).unwrap();
    assert_eq!(copy.bytes(), fb.bytes());
    // Wrong length is rejected.
    assert!(FrameBuffer::from_rgba(16, 16, vec![0u8; 10]).is_none());
}

#[test]
fn strobe_burst_then_long_static_still_fails() {
    // A short strobe followed by 9s of static black, at 60 fps. A whole-capture
    // average would dilute this to a pass; the worst-1-second-window rule fails it.
    let mut frames = Vec::new();
    for i in 0..12 {
        frames.push(solid(if i % 2 == 0 { Rgba::BLACK } else { Rgba::WHITE }));
    }
    for _ in 0..540 {
        frames.push(solid(Rgba::BLACK));
    }
    let report = analyze_flashes(&frames, 60.0);
    assert!(
        !report.passes,
        "a strobe burst must fail even amid static frames: {report:?}"
    );
    assert!(report.luminance_flashes_per_sec > 3.0);
}

#[test]
fn localized_subregion_strobe_fails_despite_small_area() {
    // A ~6%-area strobe (8×8 in a 32×32 frame). The whole-frame mean luminance swing
    // is below the 10% amplitude gate and would dilute to a pass; per-tile analysis
    // catches the localized flashing.
    let mut frames = Vec::new();
    for i in 0..20 {
        let mut f = Frame::new(32, 32); // black background
        if i % 2 == 1 {
            f.push(Layer::Fill {
                rect: Rect::new(0, 0, 8, 8),
                color: Rgba::WHITE,
            });
        }
        frames.push(render(&f));
    }
    let report = analyze_flashes(&frames, 60.0);
    assert!(
        !report.passes,
        "a localized sub-area strobe must fail: {report:?}"
    );
}

#[test]
fn strobe_just_over_three_hz_fails_at_the_boundary() {
    // 8 frames alternating at 7 fps = 3.5 flashes/sec, a >3/sec hazard that a
    // floor(count/2) would report as exactly 3.0 and pass.
    let frames: Vec<_> = (0..8)
        .map(|i| solid(if i % 2 == 0 { Rgba::BLACK } else { Rgba::WHITE }))
        .collect();
    let report = analyze_flashes(&frames, 7.0);
    assert!(!report.passes, "3.5 flashes/sec must fail: {report:?}");
    assert!(report.luminance_flashes_per_sec > 3.0);
}
