//! Scene-model tests: luminance and serde (IPC-ready).

#![allow(clippy::unwrap_used)]

use selahcue_engine::scene::{
    Frame, ImageFit, Layer, MediaRef, Rect, Rgba, ShapeKind, TextAlign, TextStyle,
};

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
        fit: ImageFit::Stretch,
    };
    let json = serde_json::to_string(&img).unwrap();
    assert!(json.contains(r#""layer":"image""#), "got {json}");
    assert!(json.contains(r#""source":"/media/logo.png""#), "got {json}");
    // An opaque opacity is the default → skipped (minimal JSON); no pixel bytes ride here.
    assert!(
        !json.contains("opacity"),
        "opaque opacity is skipped: {json}"
    );
    // The default `Stretch` fit is skipped → an existing image layer is byte-identical.
    assert!(
        !json.contains("fit"),
        "default Stretch fit is skipped: {json}"
    );
    let back: Layer = serde_json::from_str(&json).unwrap();
    assert_eq!(back, img);

    // A translucent opacity IS serialized and round-trips.
    let translucent = Layer::Image {
        rect: Rect::new(0, 0, 2, 2),
        source: MediaRef::new("a.png").unwrap(),
        opacity: 128,
        fit: ImageFit::Stretch,
    };
    let j2 = serde_json::to_string(&translucent).unwrap();
    assert!(j2.contains(r#""opacity":128"#), "got {j2}");
    assert_eq!(serde_json::from_str::<Layer>(&j2).unwrap(), translucent);

    // A non-default fit IS serialized snake_case and round-trips (Fit=letterbox, Fill=cover).
    for (fit, needle) in [
        (ImageFit::Fit, r#""fit":"fit""#),
        (ImageFit::Fill, r#""fit":"fill""#),
    ] {
        let layer = Layer::Image {
            rect: Rect::new(1, 1, 8, 8),
            source: MediaRef::new("b.png").unwrap(),
            opacity: 255,
            fit,
        };
        let j = serde_json::to_string(&layer).unwrap();
        assert!(j.contains(needle), "fit serialises snake_case: {j}");
        assert_eq!(serde_json::from_str::<Layer>(&j).unwrap(), layer);
    }
}

#[test]
fn shape_layer_is_additive_and_tag_stable() {
    // Adding `Layer::Shape` (86ajtwq24) is additive: the existing Fill encoding is
    // byte-unchanged (internally-tagged enum), the new variant tags `"layer":"shape"`,
    // its `kind` serialises snake_case, and a zero border/corner is skipped.
    let fill = Layer::Fill {
        rect: Rect::new(0, 0, 1, 1),
        color: Rgba::BLACK,
    };
    assert_eq!(
        serde_json::to_string(&fill).unwrap(),
        r#"{"layer":"fill","rect":{"x":0,"y":0,"w":1,"h":1},"color":{"r":0,"g":0,"b":0,"a":255}}"#
    );

    let ellipse = Layer::Shape {
        rect: Rect::new(2, 3, 40, 30),
        kind: ShapeKind::Ellipse,
        fill: Rgba::WHITE,
        border: Rgba::new(0, 0, 0, 0),
        border_px: 0,
        corner_px: 0,
    };
    let json = serde_json::to_string(&ellipse).unwrap();
    assert!(json.contains(r#""layer":"shape""#), "got {json}");
    assert!(json.contains(r#""kind":"ellipse""#), "got {json}");
    // Zero border/corner are the defaults → skipped (minimal JSON).
    assert!(
        !json.contains("border_px"),
        "zero border_px skipped: {json}"
    );
    assert!(
        !json.contains("corner_px"),
        "zero corner_px skipped: {json}"
    );
    assert_eq!(serde_json::from_str::<Layer>(&json).unwrap(), ellipse);

    // A rounded-rect with a border DOES serialise both, and round-trips (Eq preserved).
    let rounded = Layer::Shape {
        rect: Rect::new(0, 0, 20, 20),
        kind: ShapeKind::RoundedRect,
        fill: Rgba::WHITE,
        border: Rgba::BLACK,
        border_px: 2,
        corner_px: 5,
    };
    let j2 = serde_json::to_string(&rounded).unwrap();
    assert!(j2.contains(r#""kind":"rounded_rect""#), "got {j2}");
    assert!(j2.contains(r#""border_px":2"#), "got {j2}");
    assert!(j2.contains(r#""corner_px":5"#), "got {j2}");
    assert_eq!(serde_json::from_str::<Layer>(&j2).unwrap(), rounded);
}

#[test]
fn shape_kind_default_is_rect_and_serde_snake_case() {
    assert_eq!(ShapeKind::default(), ShapeKind::Rect);
    assert!(ShapeKind::Rect.is_rect());
    assert!(!ShapeKind::Triangle.is_rect());
    for (kind, tag) in [
        (ShapeKind::Rect, "\"rect\""),
        (ShapeKind::Ellipse, "\"ellipse\""),
        (ShapeKind::RoundedRect, "\"rounded_rect\""),
        (ShapeKind::Triangle, "\"triangle\""),
    ] {
        let json = serde_json::to_string(&kind).unwrap();
        assert_eq!(json, tag);
        assert_eq!(serde_json::from_str::<ShapeKind>(&json).unwrap(), kind);
    }
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

#[test]
fn text_style_is_additive_and_default_skipped() {
    // 86ajq3225: a Text layer with no style (the historical case) omits `style` entirely, so
    // its JSON is byte-identical to before; a default-valued TextStyle serialises to `{}`.
    let plain = Layer::Text {
        rect: Rect::new(0, 0, 10, 10),
        text: "Hi".into(),
        px: 8,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
        style: None,
    };
    let json = serde_json::to_string(&plain).unwrap();
    assert!(!json.contains("style"), "a None style is omitted: {json}");
    assert_eq!(serde_json::from_str::<Layer>(&json).unwrap(), plain);
    assert_eq!(serde_json::to_string(&TextStyle::default()).unwrap(), "{}");

    // A weighted + spaced style serialises its fields and round-trips (Eq preserved).
    let styled = Layer::Text {
        rect: Rect::new(0, 0, 10, 10),
        text: "Hi".into(),
        px: 8,
        color: Rgba::WHITE,
        align: TextAlign::Left,
        font: None,
        style: Some(TextStyle {
            weight: 700,
            letter_spacing_px: 3,
        }),
    };
    let j2 = serde_json::to_string(&styled).unwrap();
    assert!(
        j2.contains(r#""weight":700"#) && j2.contains(r#""letter_spacing_px":3"#),
        "{j2}"
    );
    assert_eq!(serde_json::from_str::<Layer>(&j2).unwrap(), styled);
}
