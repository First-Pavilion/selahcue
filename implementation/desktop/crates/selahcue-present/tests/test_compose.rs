//! Slide composition: deterministic layout of text over the theme background.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_present::{compose_slide, Element, FontName, Rgba, Slide, Theme};

/// A full-frame opaque shape element at draw order `z`.
fn full_shape(fill: Rgba, opacity: u8, z: i16) -> Element {
    Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        fill,
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity,
        z,
    }
}

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

/// Is the pixel amber-ish (the lower-third border / reference colour ≈ 242,181,60)?
fn is_amber(fb: &FrameBuffer, x: u32, y: u32) -> bool {
    fb.pixel(x, y)
        .map(|p| p.r > 200 && (150..=215).contains(&p.g) && p.b < 110)
        .unwrap_or(false)
}

#[test]
fn lower_third_renders_a_full_width_band_not_left_only() {
    // Figma 208-137 (owner refine): the lower-third is a FULL-WIDTH bottom band with
    // an amber border — its right edge reaches ~97% of the width, so the design is no
    // longer a narrow bottom-left column. Render at 1280×720 so the 5‰ border is ~3px.
    let (w, h) = (1280u32, 720u32);
    let fb = render(&compose_slide(
        &Slide::new("John 3:16", ["For God so loved the world"]),
        &Theme::lower_third(),
        w,
        h,
    ));
    // Band rect ≈ x[3%..97%]=[38..1203], y[66%..96%]=[475..691]. Sample a row inside
    // the band and confirm amber appears near BOTH the far-left and far-right edges —
    // the key proof the band spans the width (a left-only text never touches x≈97%).
    // Band spans x[3%..97%] = [38..1241] at 1280px; the amber border edges are ~3px.
    let mid_y = 560;
    let left = (25..55).any(|x| is_amber(&fb, x, mid_y));
    let right = (1225..1255).any(|x| is_amber(&fb, x, mid_y));
    assert!(left, "amber band border near the left edge (~3%)");
    assert!(
        right,
        "amber band border near the RIGHT edge (~97%) — proves full-width, not left-only"
    );
    // The reference (amber) + body (white) ink render inside the band.
    assert!(
        has_ink_in(&fb, 60, 490, 1200, 545),
        "reference line renders in the band"
    );
    assert!(
        has_ink_in(&fb, 60, 545, 1200, 675),
        "body renders in the band"
    );
    // A full-screen theme has NO band (no amber near the far-right edge, mid-frame).
    let classic = render(&compose_slide(
        &Slide::new("John 3:16", ["For God so loved the world"]),
        &Theme::classic(),
        w,
        h,
    ));
    assert!(
        !(1180..1215).any(|x| is_amber(&classic, x, mid_y)),
        "classic has no lower-third band"
    );
}

#[test]
fn theme_band_serde_is_additive_and_backward_compatible() {
    use selahcue_present::Band;
    // Full-screen themes omit `band` entirely (skip_serializing_if) → old readers +
    // compact JSON; the lower-third serializes WITH a band.
    let classic_json = serde_json::to_string(&Theme::classic()).unwrap();
    assert!(
        !classic_json.contains("band"),
        "classic must not serialize a band field"
    );
    let lt_json = serde_json::to_string(&Theme::lower_third()).unwrap();
    assert!(
        lt_json.contains("\"band\""),
        "lower-third serializes a band"
    );

    // Old custom-theme JSON WITHOUT a band field still deserializes (→ band: None).
    let no_band = serde_json::json!({
        "background": {"r":8,"g":10,"b":20,"a":255},
        "title": serde_json::from_str::<serde_json::Value>(
            &serde_json::to_string(&Theme::classic().title).unwrap()).unwrap(),
        "body": serde_json::from_str::<serde_json::Value>(
            &serde_json::to_string(&Theme::classic().body).unwrap()).unwrap(),
    });
    let t: Theme = serde_json::from_value(no_band).unwrap();
    assert_eq!(t.band, None, "absent band deserializes to None");

    // A theme WITH a band round-trips exactly.
    let rt: Theme = serde_json::from_str(&lt_json).unwrap();
    assert_eq!(rt, Theme::lower_third(), "band round-trips");
    assert!(matches!(
        rt.band,
        Some(Band {
            border_permille: 5,
            ..
        })
    ));
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

#[test]
fn auto_fit_wraps_a_long_paragraph_to_the_region_and_keeps_every_word() {
    // Owner bug (auto-fit): a long verse must WRAP to the region width + shrink to fit
    // the whole passage — never clip on the right, never truncate. The compositor wraps
    // each paragraph to rect.w and auto-sizes so all wrapped lines fit rect.h.
    use selahcue_engine::raster::measure_line_width;
    use selahcue_engine::scene::Layer;
    let long =
        "For God so loved the world that he gave his only begotten Son that whosoever believeth";
    let theme = Theme::classic();
    let (w, h) = (960u32, 540u32);
    let region = theme.body.rect(w, h);
    let frame = compose_slide(&Slide::new("John 3:16", [long]), &theme, w, h);
    let body: Vec<(String, u32, i32)> = frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, px, rect, .. } if !text.contains("John 3:16") => {
                Some((text.clone(), *px, rect.y))
            }
            _ => None,
        })
        .collect();
    assert!(body.len() > 1, "the long verse wraps into multiple lines");
    // EVERY wrapped line fits the region width (nothing clips on the right)...
    for (text, px, _) in &body {
        assert!(
            measure_line_width(text, *px, None) <= region.w as f32 + 1.0,
            "wrapped line wider than the region: {text:?}"
        );
    }
    // ...NO word is lost (the joined wrapped lines contain every original word)...
    let joined = body
        .iter()
        .map(|(t, _, _)| t.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    for word in long.split_whitespace() {
        assert!(joined.contains(word), "auto-fit dropped the word {word:?}");
    }
    assert!(!joined.contains('…'), "no ellipsis truncation");
    // ...and the whole block fits inside the region height (all lines on-screen).
    let (_, cell, _) = body[0];
    let advance = ((cell as f64) * theme.body.line_height())
        .round()
        .max(cell as f64) as u32;
    let block_h = (body.len() as u32 - 1) * advance + cell;
    assert!(
        block_h <= region.h,
        "the wrapped block ({block_h}px) must fit the region height ({}px)",
        region.h
    );
}

#[test]
fn auto_fit_shrinks_an_unbreakable_token_to_fit_the_width() {
    // An unbreakable token wider than the region — a very long word, or a space-less CJK
    // verse (`split_whitespace` yields ONE token) — must SHRINK the cell until it fits
    // rect.w, never clip on the right. The auto-fit predicate checks width, not only height.
    use selahcue_engine::raster::measure_line_width;
    use selahcue_engine::scene::Layer;
    let token = "Supercalifragilisticexpialidocioussupercalifragilisticexpialidociousandthenmore";
    let theme = Theme::classic();
    let (w, h) = (960u32, 540u32);
    let region = theme.body.rect(w, h);
    let frame = compose_slide(&Slide::new("T", [token]), &theme, w, h);
    let (text, px) = frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, px, .. } if text.contains("Supercali") => Some((text.clone(), *px)),
            _ => None,
        })
        .expect("the token renders");
    assert!(
        measure_line_width(&text, px, None) <= region.w as f32 + 1.0,
        "the unbreakable token must shrink to fit the region width, not clip: {}px > {}px",
        measure_line_width(&text, px, None),
        region.w
    );
    // It shrank below the design size (proving the WIDTH path engaged, not just height).
    assert!(
        px < theme.body.cell_px(h),
        "the cell shrank for width ({px} !< design {})",
        theme.body.cell_px(h)
    );
}

// --- Selectable system fonts (86ajq6fxt) -----------------------------------

#[test]
fn a_theme_font_is_additive_serde_and_byte_stable_by_default() {
    // A default-font theme's JSON has NO "font" field (skip-if-none) → pinned theme
    // fixtures stay byte-stable; a themed theme includes it + round-trips; old JSON
    // without the field deserializes to the default (None).
    let classic_json = serde_json::to_string(&Theme::classic()).unwrap();
    assert!(
        !classic_json.contains("\"font\""),
        "a default-font theme omits the font field (byte-stable JSON)"
    );

    let mut themed = Theme::classic();
    themed.font = FontName::new("Arial");
    let themed_json = serde_json::to_string(&themed).unwrap();
    assert!(
        themed_json.contains("\"font\":\"Arial\""),
        "a themed theme serializes its font family: {themed_json}"
    );
    let back: Theme = serde_json::from_str(&themed_json).unwrap();
    assert_eq!(
        back.font.map(|f| f.as_str().to_string()),
        Some("Arial".into())
    );

    // Old (pre-font) JSON deserializes to the default font.
    let old: Theme = serde_json::from_str(&classic_json).unwrap();
    assert_eq!(old.font, None);
}

#[test]
fn a_theme_font_changes_the_composed_slide() {
    // A per-theme system font actually drives the composed output (threaded through
    // compose → the Text layers). Robust over the enumerated set; skips only when the
    // machine has no installed fonts (the default bundled font always composes).
    let families = selahcue_engine::raster::system_font_families();
    if families.is_empty() {
        eprintln!("no system fonts — skipping the themed-compose differs check");
        return;
    }
    let slide = Slide::new("John 3:16", ["For God so loved the world"]);
    let default = render(&compose_slide(&slide, &Theme::classic(), 320, 180))
        .bytes()
        .to_vec();
    let differs = families.iter().take(40).any(|fam| {
        let mut t = Theme::classic();
        t.font = FontName::new(fam);
        render(&compose_slide(&slide, &t, 320, 180))
            .bytes()
            .to_vec()
            != default
    });
    assert!(
        differs,
        "a per-theme system font changes the composed slide vs the bundled default"
    );
}

#[test]
fn a_theme_font_is_validated_on_deserialization() {
    // The wire path (SetCustomTheme/SaveTheme run serde_json::from_str::<Theme>) must
    // enforce the SAME invariant as FontName::new — an empty/whitespace font cannot
    // masquerade as a themed (non-deterministic) default, and a spaced name is trimmed.
    let with_font = |fv: serde_json::Value| {
        let mut v = serde_json::to_value(Theme::classic()).unwrap();
        v["font"] = fv;
        serde_json::from_str::<Theme>(&v.to_string())
    };
    assert!(
        with_font(serde_json::json!("")).is_err(),
        "empty font rejected"
    );
    assert!(
        with_font(serde_json::json!("   ")).is_err(),
        "whitespace font rejected"
    );
    assert!(
        with_font(serde_json::json!("n".repeat(65))).is_err(),
        "over-long font (>64 bytes) rejected"
    );
    // A spaced name trims to the canonical family (so it matches the installed font).
    let t = with_font(serde_json::json!(" Arial ")).unwrap();
    assert_eq!(t.font.map(|f| f.as_str().to_string()), Some("Arial".into()));
}

// --- Layered elements: z-order + opacity (Canvas Editing, 86ajq6j2q) --------

#[test]
fn a_theme_with_no_elements_composes_identically_to_before() {
    // Determinism guard: adding the `elements` field must not change the default render.
    let slide = Slide::new("John 3:16", ["For God so loved the world"]);
    let theme = Theme::classic();
    assert!(theme.elements.is_empty());
    let a = render(&compose_slide(&slide, &theme, 320, 180));
    // A theme with an explicitly-empty element list renders byte-identically.
    let mut b_theme = Theme::classic();
    b_theme.elements = Vec::new();
    let b = render(&compose_slide(&slide, &b_theme, 320, 180));
    assert_eq!(
        a.bytes(),
        b.bytes(),
        "an empty element list is a no-op (determinism)"
    );
}

#[test]
fn a_front_element_paints_over_the_text() {
    // A z>=0 opaque shape covering the frame occludes the text (in front).
    let slide = Slide::new("Ref", ["Body text"]);
    let mut theme = Theme::classic();
    let baseline = render(&compose_slide(&slide, &theme, 200, 100));
    theme
        .elements
        .push(full_shape(Rgba::rgb(255, 0, 0), 255, 1));
    let fb = render(&compose_slide(&slide, &theme, 200, 100));
    assert_ne!(
        fb.bytes(),
        baseline.bytes(),
        "a front element changes the render"
    );
    // The centre (where the text was) is now the opaque red shape.
    let p = fb.pixel(100, 50).unwrap();
    assert!(
        p.r > 200 && p.g < 60 && p.b < 60,
        "the front shape paints over the text, got {p:?}"
    );
}

#[test]
fn a_behind_element_keeps_the_text_visible_on_top() {
    // A z<0 opaque shape covers the background, but the text renders ON TOP of it.
    let slide = Slide::new("Ref", ["Body"]);
    let mut theme = Theme::classic();
    theme
        .elements
        .push(full_shape(Rgba::rgb(0, 130, 0), 255, -1));
    let fb = render(&compose_slide(&slide, &theme, 200, 100));
    // A corner (no text): the behind shape covers the background (green, not navy).
    let corner = fb.pixel(2, 2).unwrap();
    assert!(
        corner.g > 100 && corner.r < 40 && corner.b < 40,
        "the behind shape covers the background, got {corner:?}"
    );
    // The WHITE body text still shows ON TOP of the green shape (near-white pixels in the
    // body region — green alone has b≈0, so a high-blue pixel proves text over the shape).
    let text_on_top = (28..84).any(|y| {
        (12u32..188).any(|x| {
            fb.pixel(x, y)
                .map(|p| p.r > 150 && p.b > 150)
                .unwrap_or(false)
        })
    });
    assert!(text_on_top, "the text renders on top of the behind element");
}

#[test]
fn a_shape_element_opacity_blends_over_what_is_beneath() {
    // A 50%-opacity white shape in the top-left corner blends with the background.
    let slide = Slide::new("R", ["B"]);
    let mut theme = Theme::classic(); // dark background
    theme.elements.push(Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 100, // 20px wide at 200px
        h_permille: 100, // 10px tall at 100px
        fill: Rgba::WHITE,
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 128, // 50%
        z: 1,
    });
    let fb = render(&compose_slide(&slide, &theme, 200, 100));
    // Inside the shape (top-left): 50% white over the dark bg → a mid grey, not full white.
    let inside = fb.pixel(2, 2).unwrap();
    assert!(
        (100..=175).contains(&inside.r) && (100..=175).contains(&inside.b),
        "50% white over dark blends to mid grey, got {inside:?}"
    );
    // Outside the shape (bottom-right corner): the dark background is untouched.
    let outside = fb.pixel(198, 98).unwrap();
    assert!(
        outside.r < 40 && outside.b < 60,
        "outside the shape stays the dark background, got {outside:?}"
    );
}

#[test]
fn a_translucent_element_border_paints_its_corners_uniformly() {
    // A shape with a TRANSLUCENT border (opacity < 255, opaque border colour): every
    // border pixel must be blended exactly once, so the four corners read the SAME as
    // the straight edges. Before the edge split they double-blended and rendered brighter.
    let slide = Slide::new("R", ["B"]);
    let mut theme = Theme::classic(); // dark background
    theme.elements.push(Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 800,     // 160px wide at 200px
        h_permille: 800,     // 80px tall at 100px
        fill: Rgba::WHITE,   // transparent below (opacity applies to alpha) — isolate the border
        border: Rgba::WHITE, // opaque white border
        border_permille: 50, // 5px thick at 100px
        opacity: 128,        // 50% → border alpha 128
        z: 1,
    });
    let fb = render(&compose_slide(&slide, &theme, 200, 100));
    let corner = fb.pixel(1, 1).unwrap(); // top-left corner square
    let top_edge = fb.pixel(80, 1).unwrap(); // straight top edge (past the corner)
    let left_edge = fb.pixel(1, 40).unwrap(); // straight left edge (below the corner)
    assert_eq!(
        (corner.r, corner.g, corner.b),
        (top_edge.r, top_edge.g, top_edge.b),
        "the corner blends the same as the straight top edge (no double-blend), got corner={corner:?} edge={top_edge:?}"
    );
    assert_eq!(
        (corner.r, corner.g, corner.b),
        (left_edge.r, left_edge.g, left_edge.b),
        "the corner blends the same as the straight left edge, got corner={corner:?} edge={left_edge:?}"
    );
    // Proof it is genuinely translucent (a single blend, not the opaque-white corner):
    assert!(
        corner.r < 255,
        "a 50% border reads as a single blend, not full white, got {corner:?}"
    );
}

#[test]
fn theme_elements_are_additive_serde_and_byte_stable_by_default() {
    // A no-element theme omits the field (byte-stable JSON); a theme with elements
    // round-trips; old JSON without the field deserializes to empty.
    let classic_json = serde_json::to_string(&Theme::classic()).unwrap();
    assert!(
        !classic_json.contains("\"elements\""),
        "a theme with no elements omits the field (byte-stable)"
    );
    let mut t = Theme::classic();
    t.elements.push(full_shape(Rgba::rgb(10, 20, 30), 200, -1));
    let jt = serde_json::to_string(&t).unwrap();
    assert!(
        jt.contains("\"elements\"") && jt.contains("\"kind\":\"shape\""),
        "an element serializes with its kind tag: {jt}"
    );
    assert_eq!(
        serde_json::from_str::<Theme>(&jt).unwrap(),
        t,
        "elements round-trip"
    );
    let old: Theme = serde_json::from_str(&classic_json).unwrap();
    assert!(
        old.elements.is_empty(),
        "absent elements deserialize to empty"
    );
}

// --- Image element (86ajq6j49) --------------------------------------------------------

use selahcue_present::MediaRef;
use std::sync::atomic::{AtomicU64, Ordering};

static IMG_COUNTER: AtomicU64 = AtomicU64::new(0);

/// An RAII temp-file guard: deletes the fixture on drop (incl. panic unwind) so tests
/// leave no PNGs accumulating in the system temp dir (no-leak, even on-disk).
struct TempImage(std::path::PathBuf);

impl TempImage {
    fn path(&self) -> &std::path::Path {
        &self.0
    }
}

impl Drop for TempImage {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

/// Encode a solid-colour RGBA PNG to a unique temp file; the returned guard removes it.
fn temp_image(w: u32, h: u32, c: Rgba) -> TempImage {
    let mut data = Vec::with_capacity((w * h * 4) as usize);
    for _ in 0..(w * h) {
        data.extend_from_slice(&[c.r, c.g, c.b, c.a]);
    }
    let mut out = Vec::new();
    {
        let mut enc = png::Encoder::new(&mut out, w, h);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(png::BitDepth::Eight);
        let mut wr = enc.write_header().unwrap();
        wr.write_image_data(&data).unwrap();
    }
    let n = IMG_COUNTER.fetch_add(1, Ordering::Relaxed);
    let mut p = std::env::temp_dir();
    p.push(format!("selahcue_imgel_{}_{}.png", std::process::id(), n));
    std::fs::write(&p, &out).unwrap();
    TempImage(p)
}

/// A full-frame image element referencing `path`, at draw order `z`.
fn full_image(path: &std::path::Path, opacity: u8, z: i16) -> Element {
    Element::Image {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        source: MediaRef::new(path.to_str().unwrap()).unwrap(),
        opacity,
        z,
    }
}

#[test]
fn an_image_element_composes_to_an_image_layer_with_the_mapped_rect() {
    use selahcue_engine::scene::Layer;
    let img = temp_image(2, 2, Rgba::WHITE);
    let mut theme = Theme::classic();
    theme.elements.push(Element::Image {
        x_permille: 100,
        y_permille: 200,
        w_permille: 500,
        h_permille: 250,
        source: MediaRef::new(img.path().to_str().unwrap()).unwrap(),
        opacity: 200,
        z: 1,
    });
    let frame = compose_slide(&Slide::new("R", ["B"]), &theme, 1000, 1000);
    let img = frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Image { rect, opacity, .. } => Some((*rect, *opacity)),
            _ => None,
        })
        .expect("an image element composes to a Layer::Image");
    // Per-mille → pixel at 1000×1000: x=100, y=200, w=500, h=250; opacity threaded.
    assert_eq!((img.0.x, img.0.y, img.0.w, img.0.h), (100, 200, 500, 250));
    assert_eq!(img.1, 200);
}

#[test]
fn an_image_element_renders_its_pixels_on_the_output() {
    // A full-frame red image renders red on the composed output (end-to-end through the
    // engine decode + blit) — the model half of the image vision is wired.
    let img = temp_image(1, 1, Rgba::rgb(220, 30, 30));
    let mut theme = Theme::classic();
    theme.elements.push(full_image(img.path(), 255, 1));
    let fb = render(&compose_slide(&Slide::new("R", ["B"]), &theme, 64, 64));
    let p = fb.pixel(32, 8).unwrap(); // near the top, away from the centred text
    assert!(
        p.r > 180 && p.g < 80 && p.b < 80,
        "the image element paints its red pixels, got {p:?}"
    );
}

#[test]
fn image_element_z_order_behind_and_in_front_of_the_text() {
    use selahcue_engine::scene::Layer;
    let img = temp_image(1, 1, Rgba::WHITE);
    let idx_of = |theme: &Theme| {
        let frame = compose_slide(&Slide::new("Title", ["Body"]), theme, 400, 400);
        let img = frame
            .layers
            .iter()
            .position(|l| matches!(l, Layer::Image { .. }));
        let text = frame
            .layers
            .iter()
            .position(|l| matches!(l, Layer::Text { .. }));
        (img, text)
    };
    // z < 0 → the image layer precedes the first text layer (painted behind).
    let mut behind = Theme::classic();
    behind.elements.push(full_image(img.path(), 255, -1));
    let (bi, bt) = idx_of(&behind);
    assert!(
        bi.unwrap() < bt.unwrap(),
        "a z<0 image composes BEFORE the text"
    );
    // z >= 0 → the image layer follows the text (painted in front).
    let mut front = Theme::classic();
    front.elements.push(full_image(img.path(), 255, 1));
    let (fi, ft) = idx_of(&front);
    assert!(
        fi.unwrap() > ft.unwrap(),
        "a z>=0 image composes AFTER the text"
    );
}

#[test]
fn a_missing_image_element_renders_the_non_black_placeholder() {
    // A missing source → the engine's non-black placeholder, never blank, never a crash.
    let mut theme = Theme::classic();
    theme.elements.push(Element::Image {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        source: MediaRef::new("/no/such/theme/image.png").unwrap(),
        opacity: 255,
        z: 1,
    });
    let fb = render(&compose_slide(&Slide::new("R", ["B"]), &theme, 64, 64));
    // The placeholder base (64,54,74) fills most of the frame — assert a non-black pixel.
    assert_ne!(
        fb.pixel(48, 6).unwrap(),
        Rgba::BLACK,
        "missing image → non-black placeholder"
    );
}

#[test]
fn an_image_element_is_additive_serde_and_round_trips() {
    let img = temp_image(1, 1, Rgba::WHITE);
    let mut t = Theme::classic();
    t.elements.push(full_image(img.path(), 128, -1));
    let json = serde_json::to_string(&t).unwrap();
    // Assert the kind tag + that a `source` field is emitted. (Do NOT substring-match the
    // raw path against the JSON: on Windows the path's backslashes are escaped as `\\`, so
    // the raw path is not a substring — the round-trip equality below proves the source
    // value persisted losslessly, cross-OS, regardless of the path separator.)
    assert!(
        json.contains("\"kind\":\"image\"") && json.contains("\"source\":"),
        "an image element serializes with its kind tag + source field: {json}"
    );
    assert_eq!(
        serde_json::from_str::<Theme>(&json).unwrap(),
        t,
        "an image element round-trips (source value preserved)"
    );
    // A no-image-element theme is still byte-stable (no elements field).
    assert!(!serde_json::to_string(&Theme::classic())
        .unwrap()
        .contains("\"elements\""));
}
