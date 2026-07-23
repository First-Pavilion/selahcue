//! Scene-model tests: luminance and serde (IPC-ready).

#![allow(clippy::unwrap_used)]

use selahcue_engine::scene::{Frame, Layer, Rect, Rgba};

#[test]
fn luminance_extremes() {
    assert_eq!(Rgba::BLACK.luminance(), 0.0);
    assert!((Rgba::WHITE.luminance() - 1.0).abs() < 1e-9);
}

#[test]
fn frame_serde_round_trip() {
    let mut f = Frame::new(1920, 1080).with_background(Rgba::rgb(10, 20, 30));
    f.push(Layer::Fill {
        rect: Rect::new(1, 2, 3, 4),
        color: Rgba::new(5, 6, 7, 8),
    });
    f.blackout = true;
    let json = serde_json::to_string(&f).unwrap();
    let back: Frame = serde_json::from_str(&json).unwrap();
    assert_eq!(back, f);
}

#[test]
fn layer_tag_encoding_is_stable() {
    let layer = Layer::Fill {
        rect: Rect::new(0, 0, 1, 1),
        color: Rgba::BLACK,
    };
    let json = serde_json::to_string(&layer).unwrap();
    assert!(json.contains(r#""layer":"fill""#), "got {json}");
}
