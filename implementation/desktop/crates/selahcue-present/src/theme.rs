//! The audience-output **theme** — a slide-design template (FR-010).
//!
//! A theme is NOT a light/dark colour mode: it is a reusable design (background +
//! positioned **regions**, each with alignment + typography) that the audience
//! output uses to render scriptures, songs, and lower-thirds. Content is stored on
//! the [`Slide`](crate::slide::Slide), orthogonal to the theme, so **switching a
//! theme restyles content without losing it** (the S8-3a spec:
//! `docs/design/THEME-MODEL-spec.md`).
//!
//! MVP cut (this batch): a **solid** background, the single bundled font family,
//! and real H+V alignment + per-region size/colour. Gradient/image backgrounds,
//! per-role templates + per-item override, and multi-weight fonts are later slices.

use selahcue_engine::scene::{
    FontName, GradientDirection, ImageFit, MediaRef, Rect, Rgba, ShapeKind, TextAlign,
};
use serde::{Deserialize, Serialize};

/// Vertical alignment of a region's text block within the region rect.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum VAlign {
    Top,
    #[default]
    Middle,
    Bottom,
}

/// How a region handles content taller than it fits (FR-010; the Theme Designer's
/// **Fit** control). `ShrinkToFit` (the default for all built-ins, owner direction)
/// scales the text down so **every** line fits — a long verse never drops lines;
/// `Clip` keeps the design size and drops overflow; `Paginate` is a later slice
/// (treated as `Clip` until then).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum Fit {
    #[default]
    ShrinkToFit,
    Clip,
    Paginate,
}

/// One positioned, styled text region of a theme. Geometry is **per-mille of the
/// output frame** (resolution-independent → identical layout on 1080p and 4K).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct RegionStyle {
    /// Rect origin/size as per-mille of frame width/height (each 0..=1000).
    pub x_permille: u16,
    pub y_permille: u16,
    pub w_permille: u16,
    pub h_permille: u16,
    /// Horizontal alignment of each line within the region.
    pub align_h: TextAlign,
    /// Vertical alignment of the whole text block within the region.
    pub align_v: VAlign,
    /// Line-box (cell) height as per-mille of frame HEIGHT.
    pub size_permille: u16,
    /// Line-height multiplier in per-mille (1000 = 1.0×, 1150 = 1.15×).
    pub line_height_permille: u16,
    /// Text colour.
    pub color: Rgba,
    /// Overflow policy — how content taller than the region is handled.
    pub fit: Fit,
    /// When `false`, the region is not rendered (e.g. a template that hides the title).
    pub visible: bool,
}

/// A decorative **band** drawn behind a theme's text — a filled rect (use a
/// non-opaque `fill` alpha to let video/background show through) with a border.
/// It composes *before* the text regions, so the reference/body sit on top of it.
/// The lower-third's full-width bottom bar (Figma 208-137) is a band; full-screen
/// themes carry `None`. Geometry is per-mille of the frame, like [`RegionStyle`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Band {
    pub x_permille: u16,
    pub y_permille: u16,
    pub w_permille: u16,
    pub h_permille: u16,
    /// Fill colour — a non-opaque alpha reads as a translucent panel over the
    /// background/video (the engine's `fill_rect` blends src-over).
    pub fill: Rgba,
    /// Border colour (the amber outline that delineates the lower-third bar).
    pub border: Rgba,
    /// Border thickness as per-mille of frame HEIGHT (`0` = no border).
    pub border_permille: u16,
}

impl Band {
    /// The band's pixel rect within a `width×height` frame.
    pub fn rect(&self, width: u32, height: u32) -> Rect {
        let map = |dim: u32, permille: u16| (dim as u64 * permille as u64 / 1000) as u32;
        Rect::new(
            map(width, self.x_permille) as i32,
            map(height, self.y_permille) as i32,
            map(width, self.w_permille).max(1),
            map(height, self.h_permille).max(1),
        )
    }
    /// Border thickness in pixels for a `height`-tall frame (`0` when no border).
    pub fn border_px(&self, height: u32) -> u32 {
        if self.border_permille == 0 {
            0
        } else {
            (height as u64 * self.border_permille as u64 / 1000).max(1) as u32
        }
    }
}

impl RegionStyle {
    /// The region's pixel rect within a `width×height` frame.
    pub fn rect(&self, width: u32, height: u32) -> Rect {
        let map = |dim: u32, permille: u16| (dim as u64 * permille as u64 / 1000) as u32;
        Rect::new(
            map(width, self.x_permille) as i32,
            map(height, self.y_permille) as i32,
            map(width, self.w_permille).max(1),
            map(height, self.h_permille).max(1),
        )
    }
    /// The line-box (cell) height in pixels for a `height`-tall frame.
    pub fn cell_px(&self, height: u32) -> u32 {
        (height as u64 * self.size_permille as u64 / 1000).max(1) as u32
    }
    /// Line-height multiplier (clamped to a sane range).
    pub fn line_height(&self) -> f64 {
        (self.line_height_permille.max(1) as f64 / 1000.0).clamp(0.8, 3.0)
    }
}

/// A layered design **element** on the canvas (Canvas Editing epic, 86ajq6j2q): a
/// positioned, opacity-blended, z-ordered item composited over the background. Additive,
/// internally-tagged enum — the `Text` (free text box) kind lands in a dependent story
/// without a wire break.
///
/// `Element` is `Clone` but NOT `Copy`: the [`Image`](Element::Image) kind carries a
/// heap-backed [`MediaRef`]. `RegionStyle`/`Band`/`FontName` stay `Copy`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Element {
    /// A decorative shape — a fill rect + optional border, at a per-mille rect, blended at
    /// `opacity`, ordered by `z` relative to the text (`z < 0` = behind, `z >= 0` = in
    /// front). Generalises [`Band`] to an arbitrary, arrangeable element.
    Shape {
        x_permille: u16,
        y_permille: u16,
        w_permille: u16,
        h_permille: u16,
        fill: Rgba,
        border: Rgba,
        /// Border thickness as per-mille of frame HEIGHT (`0` = no border).
        border_permille: u16,
        /// Whole-shape opacity, `0..=255`, multiplied into the fill + border alpha.
        opacity: u8,
        /// Draw order relative to the text regions: `< 0` behind the text, `>= 0` in front.
        z: i16,
        /// The shape geometry (86ajtwq24): rectangle (the default), ellipse, rounded-rect,
        /// or triangle. Additive (`skip_serializing_if` → a plain rectangle OMITS the field,
        /// so an existing rectangle shape's JSON is byte-identical to before this batch, and
        /// it still composes to the unchanged [`Layer::Fill`](selahcue_engine::scene::Layer)
        /// path).
        #[serde(default, skip_serializing_if = "ShapeKind::is_rect")]
        variant: ShapeKind,
        /// Rounded-rectangle corner radius as per-mille of the SHORTER side (`0` = square
        /// corners; ignored for non-rounded kinds). Additive (`skip_serializing_if` → omitted
        /// when unset, keeping older/rectangle JSON byte-identical).
        #[serde(default, skip_serializing_if = "is_zero_u16")]
        corner_permille: u16,
        /// Whether this element is drawn (Design 2.0 LAYERS visibility). `true` = shown (the
        /// default); `false` = hidden from the composed frame (no layer emitted), exactly like
        /// a region's `visible`. Additive (`skip_serializing_if` → a shown shape's JSON is
        /// byte-identical to before this batch).
        #[serde(default = "default_true", skip_serializing_if = "is_true")]
        visible: bool,
    },
    /// A raster **image** (86ajq6j49) at a per-mille rect, blended at `opacity`, ordered by
    /// `z` relative to the text (`z < 0` = behind, `z >= 0` = in front). `source` is a
    /// bounded reference to a host-local media file the engine decodes (PNG this batch)
    /// through its size-capped decode cache — the decoded pixels never ride the theme JSON.
    /// A missing / corrupt / unsupported source draws the missing-media placeholder
    /// (FR-070), never a blank rect or a crash. `fit` chooses how the decoded image is scaled
    /// into its rect (Design 2.0 Inspector Fit): `Stretch` (the default) distorts to fill,
    /// `Fit` letterboxes (aspect kept; the gap shows the slide behind), `Fill` covers + crops.
    Image {
        x_permille: u16,
        y_permille: u16,
        w_permille: u16,
        h_permille: u16,
        /// A bounded, validated reference to the image file (resolved on the render host).
        source: MediaRef,
        /// Whole-image opacity, `0..=255`.
        opacity: u8,
        /// Draw order relative to the text regions: `< 0` behind the text, `>= 0` in front.
        z: i16,
        /// Whether this element is drawn (Design 2.0 LAYERS visibility). `true` = shown (the
        /// default); `false` = hidden from the composed frame. Additive (`skip_serializing_if`
        /// → a shown image's JSON is byte-identical to before this batch).
        #[serde(default = "default_true", skip_serializing_if = "is_true")]
        visible: bool,
        /// How the decoded image is scaled into its rect (Design 2.0 Inspector Fit). Additive:
        /// `Stretch` (the default) is omitted from JSON, so an existing image element stays
        /// byte-identical; `Fit`/`Fill` are the aspect-preserving modes the raster honours.
        #[serde(default, skip_serializing_if = "ImageFit::is_stretch")]
        fit: ImageFit,
    },
    /// A free **text box** (86ajq6j64): the operator's own `text`, wrapped + auto-fit into a
    /// per-mille rect exactly like the theme's title/body regions (same [`autofit_layers`]
    /// path — word-wrap, shrink-to-fit, letter-spacing, weight), blended at `opacity`, ordered
    /// by `z` relative to the slide text (`z < 0` = behind, `z >= 0` = in front). The last
    /// `Element` kind — the ProPresenter-style "add a text box". Bounded by
    /// [`MAX_TEXT_ELEMENT_LEN`]. Renders to `Layer::Text`, which the GPU skips (a documented
    /// seam, like `Shape`/`Image`), so the deterministic CPU raster is the real render path and
    /// the parity oracle is untouched.
    Text {
        x_permille: u16,
        y_permille: u16,
        w_permille: u16,
        h_permille: u16,
        /// The text content (plain; blank lines separate paragraphs — the auto-fit wraps each
        /// to the rect width). Bounded by [`MAX_TEXT_ELEMENT_LEN`].
        text: String,
        /// Text colour (the whole-element `opacity` multiplies its alpha).
        color: Rgba,
        /// Design cell (font) size as per-mille of frame HEIGHT; the auto-fit shrinks it so the
        /// WHOLE text shows (zero content loss) when `fit` is `ShrinkToFit`.
        size_permille: u16,
        /// Line-height multiplier in per-mille (1000 = 1.0x).
        line_height_permille: u16,
        /// Horizontal alignment of each wrapped line.
        align_h: TextAlign,
        /// Vertical alignment of the text block within the rect.
        align_v: VAlign,
        /// Overflow policy — `ShrinkToFit` (the UI default) shows the whole text.
        fit: Fit,
        /// Whole-element opacity, `0..=255`, multiplied into the text-colour alpha.
        opacity: u8,
        /// Draw order relative to the text regions: `< 0` behind the slide text, `>= 0` in front.
        z: i16,
        /// Optional SYSTEM font (`None` = the bundled default, Noto Sans — deterministic). A
        /// missing family falls back to the bundled font. Additive (`skip_serializing_if`).
        #[serde(default, skip_serializing_if = "Option::is_none")]
        font: Option<FontName>,
        /// Font weight (400 = Regular, the default). Additive (`skip_serializing_if`).
        #[serde(default = "weight_normal", skip_serializing_if = "is_weight_normal")]
        weight: u16,
        /// Letter-spacing as per-mille of the font size (`0` = none, may be negative). Additive.
        #[serde(default, skip_serializing_if = "is_zero_i16")]
        letter_spacing_permille: i16,
        /// Whether this element is drawn (Design 2.0 LAYERS visibility). `true` = shown (the
        /// default); `false` = hidden from the composed frame. Additive (`skip_serializing_if`
        /// → a shown text box's JSON is byte-identical to before this batch).
        #[serde(default = "default_true", skip_serializing_if = "is_true")]
        visible: bool,
    },
}

/// Upper bound on a single [`Element::Text`] box's content length (chars) so a design cannot
/// carry an unbounded string (no-leak). Generous for a slide text box; the auto-fit render is
/// separately bounded (`MAX_WRAP_WORDS`), and the persisted/snapshotted theme stays small.
pub const MAX_TEXT_ELEMENT_LEN: usize = 2000;

/// serde `skip_serializing_if` for a `u16` that is zero (an absent corner radius) — keeps a
/// rectangle/older shape's JSON byte-identical (no `corner_permille` key emitted).
fn is_zero_u16(v: &u16) -> bool {
    *v == 0
}

/// The serde default for [`Theme::weight`]: 400 (Regular) — keeps a default-weight theme's
/// JSON byte-stable (no `weight` key emitted).
fn weight_normal() -> u16 {
    400
}
fn is_weight_normal(w: &u16) -> bool {
    *w == 400
}
/// serde `skip_serializing_if` for a zero `i16` (no letter-spacing).
fn is_zero_i16(v: &i16) -> bool {
    *v == 0
}

/// The serde default for an [`Element`]'s `visible` flag: `true` (shown) — so older theme
/// JSON without the field deserializes to a shown element (paired with `is_true` below).
fn default_true() -> bool {
    true
}
/// serde `skip_serializing_if` for a `visible: true` element (the default) — the key is
/// OMITTED for a shown element, so an existing element's JSON stays byte-identical to before
/// the Design 2.0 LAYERS-visibility batch.
fn is_true(v: &bool) -> bool {
    *v
}

/// Upper bound on a theme's element list (86ajq6j2q) so the design can't grow without
/// limit (no-leak). A canvas rarely needs more; the compositor + persistence are bounded.
pub const MAX_ELEMENTS: usize = 64;

impl Element {
    /// Draw order relative to the text regions: `< 0` = behind the text, `>= 0` = in front.
    pub fn z(&self) -> i16 {
        match self {
            Element::Shape { z, .. } => *z,
            Element::Image { z, .. } => *z,
            Element::Text { z, .. } => *z,
        }
    }

    /// Whether this element is drawn (Design 2.0 LAYERS visibility). Mirrors a region's
    /// `visible`: a hidden element contributes NO layer to the composed frame (never a blank
    /// rect), so hiding one layer leaves the background + every other visible layer intact.
    pub fn visible(&self) -> bool {
        match self {
            Element::Shape { visible, .. } => *visible,
            Element::Image { visible, .. } => *visible,
            Element::Text { visible, .. } => *visible,
        }
    }

    /// Whether this element is within its per-element content bounds (no-leak): a
    /// [`Text`](Element::Text) box's content is capped at [`MAX_TEXT_ELEMENT_LEN`]; a
    /// `Shape`/`Image` is all-scalar (a `MediaRef` is separately bounded) and always ok.
    pub fn within_bounds(&self) -> bool {
        match self {
            Element::Text { text, .. } => text.chars().count() <= MAX_TEXT_ELEMENT_LEN,
            Element::Shape { .. } | Element::Image { .. } => true,
        }
    }
}

/// A two-stop linear **gradient background** (86ajq3225): the colour ramps from `from` to
/// `to` along `direction`. Rendered deterministically by the CPU raster (a full-frame
/// [`Layer::Gradient`](selahcue_engine::scene::Layer)).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct GradientBackground {
    pub from: Rgba,
    pub to: Rgba,
    #[serde(default)]
    pub direction: GradientDirection,
}

/// A full-frame **image background** (86ajq3225): the `source` image FILLS the frame (behind
/// everything). A bounded, validated [`MediaRef`] resolved through the engine's size-capped
/// decode cache — the decoded pixels never ride the theme JSON; a missing/corrupt/unsupported
/// source draws the missing-media placeholder (FR-070), never a blank frame or a crash.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImageBackground {
    pub source: MediaRef,
}

/// The theme **background** (86ajq3225): a solid colour (the default), a two-stop gradient, or
/// a full-frame image. An **untagged** enum whose `Solid` serialises as the bare `{r,g,b,a}`
/// colour — so an existing solid-background theme's JSON is **byte-identical** (backward
/// compatible; pinned fixtures stay stable). The three shapes are disjoint (a solid
/// `{r,g,b,a}`, a gradient `{from,to,direction}`, an image `{source}`), so the untagged
/// discrimination is unambiguous.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Background {
    /// A solid colour — serialises as the bare `{r,g,b,a}` (the historical shape).
    Solid(Rgba),
    /// A two-stop linear gradient.
    Gradient(GradientBackground),
    /// A full-frame image.
    Image(ImageBackground),
}

impl Background {
    /// The base/fallback colour: the solid colour, the gradient's `from`, or black behind an
    /// image. Used as the frame clear colour (the GPU clear + the CPU base fill).
    pub fn base_color(&self) -> Rgba {
        match self {
            Background::Solid(c) => *c,
            Background::Gradient(g) => g.from,
            Background::Image(_) => Rgba::BLACK,
        }
    }
}

/// The audience-output theme: a **background** (solid / gradient / image, 86ajq3225) + a
/// **title/reference** region and a **body** region. One theme renders both a scripture
/// (title = the reference line) and a song (title = the song title) consistently. Per-role
/// templates + per-item override are S8-3d.
///
/// NOTE: `Theme` is `Clone` but NOT `Copy` (it carries a `Vec<Element>` for the Canvas
/// Editing epic, 86ajq6j2q). `RegionStyle`/`Band`/`FontName` stay `Copy`; `Element` is
/// `Clone` (its `Image` kind carries a heap-backed `MediaRef`, 86ajq6j49).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Theme {
    pub background: Background,
    pub title: RegionStyle,
    pub body: RegionStyle,
    /// An optional decorative band behind the text (the lower-third bar). Additive and
    /// backward-compatible: older custom-theme JSON without this field deserializes to
    /// `None`, and full-screen themes serialize without it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub band: Option<Band>,
    /// The font family to shape ALL of this theme's text with (86ajq6fxt). `None` = the
    /// bundled default (Noto Sans) — deterministic, cross-OS-identical. `Some` selects a
    /// SYSTEM font on the render machine (a missing family falls back to the bundled
    /// font). Additive (`skip_serializing_if` → a default-font theme's JSON is unchanged,
    /// so pinned theme fixtures stay byte-stable).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub font: Option<FontName>,
    /// Font weight for ALL of this theme's text (86ajq3225): a CSS-style numeric weight
    /// (400 = Regular, the default). Heavier weights render as a real bold FACE for a system
    /// `font`, or a deterministic faux-bold smear for the single-weight bundled default.
    /// Additive (`skip_serializing_if` = 400 → a default-weight theme's JSON is byte-stable).
    #[serde(default = "weight_normal", skip_serializing_if = "is_weight_normal")]
    pub weight: u16,
    /// Letter-spacing (tracking) as per-mille of the font SIZE (86ajq3225); `0` = none, may be
    /// negative for tighter set. Scales with the text size. Additive (`skip_serializing_if`).
    #[serde(default, skip_serializing_if = "is_zero_i16")]
    pub letter_spacing_permille: i16,
    /// Layered design elements composited over the background (Canvas Editing, 86ajq6j2q):
    /// each positioned + opacity-blended + z-ordered relative to the text. Additive
    /// (`skip_serializing_if` empty → a default theme's JSON is byte-identical). Bounded
    /// by [`MAX_ELEMENTS`].
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub elements: Vec<Element>,
}

const AMBER: Rgba = Rgba {
    r: 242,
    g: 181,
    b: 60,
    a: 255,
};

impl Theme {
    /// Whether the design element list is within bounds (no-leak): the COUNT is capped by
    /// [`MAX_ELEMENTS`] and each [`Text`](Element::Text) box's content by
    /// [`MAX_TEXT_ELEMENT_LEN`]. Callers ingesting an (Operator-authored) theme JSON reject a
    /// theme that fails this, so a hand-edited/hostile payload cannot grow the design without
    /// limit.
    pub fn elements_bounded(&self) -> bool {
        self.elements.len() <= MAX_ELEMENTS && self.elements.iter().all(Element::within_bounds)
    }

    /// **Classic** — the default worship design: a dark navy background, an amber
    /// reference/title centred near the top, and white body text centred in the
    /// middle. (`dark()` keeps the historical constructor name callers use.)
    pub fn dark() -> Self {
        Theme::classic()
    }

    /// Alias for the default design (its stable built-in name is `"classic"`).
    pub fn classic() -> Self {
        Theme {
            background: Background::Solid(Rgba::rgb(8, 10, 20)),
            title: RegionStyle {
                x_permille: 60,
                y_permille: 150,
                w_permille: 880,
                h_permille: 110,
                align_h: TextAlign::Center,
                align_v: VAlign::Middle,
                size_permille: 48,
                line_height_permille: 1200,
                color: AMBER,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            body: RegionStyle {
                x_permille: 60,
                y_permille: 280,
                w_permille: 880,
                // Sized so a full 6-line wrapped verse (the controller cap,
                // SCRIPTURE_MAX_LINES) renders at the DESIGN size; longer content
                // shrinks to fit (Fit::ShrinkToFit) rather than clipping.
                h_permille: 560,
                align_h: TextAlign::Center,
                align_v: VAlign::Middle,
                size_permille: 78,
                line_height_permille: 1150,
                color: Rgba::WHITE,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            band: None,
            font: None,
            weight: 400,
            letter_spacing_permille: 0,
            elements: Vec::new(),
        }
    }

    /// **High-contrast** — a pure-black background with larger text and tighter
    /// margins (a low-vision / glare-resistant design, NFR-020).
    pub fn high_contrast() -> Self {
        Theme {
            background: Background::Solid(Rgba::rgb(0, 0, 0)),
            title: RegionStyle {
                x_permille: 40,
                y_permille: 130,
                w_permille: 920,
                h_permille: 120,
                align_h: TextAlign::Center,
                align_v: VAlign::Middle,
                size_permille: 52,
                line_height_permille: 1150,
                color: AMBER,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            body: RegionStyle {
                x_permille: 40,
                y_permille: 250,
                w_permille: 920,
                h_permille: 640,
                align_h: TextAlign::Center,
                align_v: VAlign::Middle,
                size_permille: 95,
                line_height_permille: 1120,
                color: Rgba::WHITE,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            band: None,
            font: None,
            weight: 400,
            letter_spacing_permille: 0,
            elements: Vec::new(),
        }
    }

    /// **Lower-third** — a **full-width bottom band** (Figma 208-137): a translucent
    /// dark panel with a thin amber border, keyed over live video, carrying the
    /// reference (amber) above the body (white), left-aligned inside the band. The
    /// band spans nearly the full width (3%–97%) rather than a narrow left column
    /// (owner refine).
    ///
    /// Short-form by design: the band fits ~2 lines at the design size, so a long
    /// (e.g. 6-line) verse switched into it **shrinks to fit** the band
    /// (`Fit::ShrinkToFit`, the default) rather than dropping lines.
    pub fn lower_third() -> Self {
        Theme {
            // Dark backdrop stands in for the keyed video on opaque outputs + the
            // Designer preview; true NDI alpha-keying is a later slice.
            background: Background::Solid(Rgba::rgb(4, 12, 9)),
            title: RegionStyle {
                x_permille: 55,
                y_permille: 688,
                w_permille: 890,
                h_permille: 70,
                align_h: TextAlign::Left,
                align_v: VAlign::Middle,
                size_permille: 40,
                line_height_permille: 1100,
                color: AMBER,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            body: RegionStyle {
                x_permille: 55,
                y_permille: 762,
                w_permille: 890,
                h_permille: 175,
                align_h: TextAlign::Left,
                align_v: VAlign::Top,
                size_permille: 62,
                line_height_permille: 1100,
                color: Rgba::WHITE,
                fit: Fit::ShrinkToFit,
                visible: true,
            },
            band: Some(Band {
                x_permille: 30,
                y_permille: 660,
                w_permille: 940,
                h_permille: 300,
                // Translucent darkening panel; the amber border is what delineates
                // the bar over a dark backdrop (matches 208-137).
                fill: Rgba {
                    r: 0,
                    g: 0,
                    b: 0,
                    a: 150,
                },
                border: AMBER,
                border_permille: 5,
            }),
            font: None,
            weight: 400,
            letter_spacing_permille: 0,
            elements: Vec::new(),
        }
    }

    /// The stable names of the built-in themes, in picker order. The active theme
    /// is persisted + sent over the wire by NAME (a fixed set — no unbounded
    /// growth); custom authoring is a later slice.
    pub const BUILTIN_NAMES: &'static [&'static str] = &["classic", "high-contrast", "lower-third"];

    /// Resolve a built-in theme by its stable name (`None` for an unknown name).
    pub fn builtin(name: &str) -> Option<Theme> {
        match name {
            "classic" => Some(Theme::classic()),
            "high-contrast" => Some(Theme::high_contrast()),
            "lower-third" => Some(Theme::lower_third()),
            _ => None,
        }
    }

    /// The stable name of this theme if it equals a built-in (so a `Presenter`
    /// constructed from a `Theme` value can report its picker selection).
    pub fn name_of(&self) -> Option<&'static str> {
        Theme::BUILTIN_NAMES
            .iter()
            .copied()
            .find(|n| Theme::builtin(n).as_ref() == Some(self))
    }
}

impl Default for Theme {
    fn default() -> Self {
        Theme::classic()
    }
}
