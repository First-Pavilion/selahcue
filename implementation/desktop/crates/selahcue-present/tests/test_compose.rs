//! Slide composition: deterministic layout of text over the theme background.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_present::{compose_slide, FontName, Slide, Theme};

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
