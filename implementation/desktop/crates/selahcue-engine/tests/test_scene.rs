//! Scene-model tests: luminance and serde (IPC-ready).

#![allow(clippy::unwrap_used)]

use selahcue_engine::scene::{Frame, Layer, MediaRef, Rect, Rgba};

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

#[test]
fn image_layer_is_additive_and_tag_stable() {
    // Adding `Layer::Image` (S8-6) is additive: Fill/Text encodings are byte-unchanged
    // (an internally-tagged enum), and the new variant tags `"layer":"image"`, carries a
    // bounded REFERENCE (not pixels), and round-trips. A default opacity is skipped.
    let fill = Layer::Fill {
        rect: Rect::new(0, 0, 1, 1),
        color: Rgba::BLACK,
    };
    // The exact Fill JSON is unchanged by the presence of the Image variant.
    assert_eq!(
        serde_json::to_string(&fill).unwrap(),
        r#"{"layer":"fill","rect":{"x":0,"y":0,"w":1,"h":1},"color":{"r":0,"g":0,"b":0,"a":255}}"#
    );

    let img = Layer::Image {
        rect: Rect::new(4, 5, 6, 7),
        source: MediaRef::new("/media/logo.png").unwrap(),
        opacity: 255,
    };
    let json = serde_json::to_string(&img).unwrap();
    assert!(json.contains(r#""layer":"image""#), "got {json}");
    assert!(json.contains(r#""source":"/media/logo.png""#), "got {json}");
    // An opaque opacity is the default → skipped (minimal JSON); no pixel bytes ride here.
    assert!(
        !json.contains("opacity"),
        "opaque opacity is skipped: {json}"
    );
    let back: Layer = serde_json::from_str(&json).unwrap();
    assert_eq!(back, img);

    // A translucent opacity IS serialized and round-trips.
    let translucent = Layer::Image {
        rect: Rect::new(0, 0, 2, 2),
        source: MediaRef::new("a.png").unwrap(),
        opacity: 128,
    };
    let j2 = serde_json::to_string(&translucent).unwrap();
    assert!(j2.contains(r#""opacity":128"#), "got {j2}");
    assert_eq!(serde_json::from_str::<Layer>(&j2).unwrap(), translucent);
}

#[test]
fn media_ref_validates_on_construction_and_deserialization() {
    // Constructor: trims, rejects empty/whitespace/over-long/NUL.
    assert_eq!(MediaRef::new("  a.png  ").unwrap().as_str(), "a.png");
    assert!(MediaRef::new("").is_none());
    assert!(MediaRef::new("   ").is_none());
    assert!(MediaRef::new("a\0b.png").is_none());
    assert!(MediaRef::new(&"x".repeat(MediaRef::CAP + 1)).is_none());
    assert!(MediaRef::new(&"x".repeat(MediaRef::CAP)).is_some());

    // Deserialization routes through the SAME invariant — a hostile theme JSON that
    // smuggles an empty / over-long / NUL reference is REJECTED (not a silent pass-through).
    let bad = format!(
        r#"{{"layer":"image","rect":{{"x":0,"y":0,"w":1,"h":1}},"source":"{}"}}"#,
        "x".repeat(MediaRef::CAP + 1)
    );
    assert!(
        serde_json::from_str::<Layer>(&bad).is_err(),
        "over-long ref rejected on the wire"
    );
    assert!(
        serde_json::from_str::<Layer>(
            r#"{"layer":"image","rect":{"x":0,"y":0,"w":1,"h":1},"source":""}"#
        )
        .is_err(),
        "empty ref rejected on the wire"
    );
}
