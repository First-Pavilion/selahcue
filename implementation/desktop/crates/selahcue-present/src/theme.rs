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

use selahcue_engine::scene::{FontName, Rect, Rgba, TextAlign};
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

/// The audience-output theme: a solid background + a **title/reference** region and
/// a **body** region. One theme renders both a scripture (title = the reference
/// line) and a song (title = the song title) consistently. Per-role templates +
/// per-item override are S8-3d.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Theme {
    pub background: Rgba,
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
    /// so pinned theme fixtures stay byte-stable). Keeps `Theme` a fixed-size `Copy` POD.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub font: Option<FontName>,
}

const AMBER: Rgba = Rgba {
    r: 242,
    g: 181,
    b: 60,
    a: 255,
};

impl Theme {
    /// **Classic** — the default worship design: a dark navy background, an amber
    /// reference/title centred near the top, and white body text centred in the
    /// middle. (`dark()` keeps the historical constructor name callers use.)
    pub fn dark() -> Self {
        Theme::classic()
    }

    /// Alias for the default design (its stable built-in name is `"classic"`).
    pub fn classic() -> Self {
        Theme {
            background: Rgba::rgb(8, 10, 20),
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
        }
    }

    /// **High-contrast** — a pure-black background with larger text and tighter
    /// margins (a low-vision / glare-resistant design, NFR-020).
    pub fn high_contrast() -> Self {
        Theme {
            background: Rgba::rgb(0, 0, 0),
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
            background: Rgba::rgb(4, 12, 9),
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
