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

use selahcue_engine::scene::{Rect, Rgba, TextAlign};
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
    /// When `false`, the region is not rendered (e.g. a template that hides the title).
    pub visible: bool,
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
                visible: true,
            },
            body: RegionStyle {
                x_permille: 60,
                y_permille: 280,
                w_permille: 880,
                // Sized so a full 6-line wrapped verse (the controller cap,
                // SCRIPTURE_MAX_LINES) fits, and a 7th line clips — keeping the
                // engine's line capacity aligned with the cap.
                h_permille: 560,
                align_h: TextAlign::Center,
                align_v: VAlign::Middle,
                size_permille: 78,
                line_height_permille: 1150,
                color: Rgba::WHITE,
                visible: true,
            },
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
                visible: true,
            },
        }
    }

    /// **Lower-third** — content in the bottom band, left-aligned (for keyed /
    /// stream lower-thirds). The reference sits above the body in the band.
    ///
    /// This is a **short-form** template by design: the band body fits ~2 lines at
    /// every resolution, so a long (e.g. 6-line) verse switched into it **clips**
    /// to the first lines on the audience output (MVP overflow = clip; content is
    /// retained on the `Slide`, so switching back restores it — a data guarantee,
    /// not a visual one). Shrink-to-fit / pagination is a later slice (S8-3a §4).
    pub fn lower_third() -> Self {
        Theme {
            background: Rgba::rgb(2, 10, 7),
            title: RegionStyle {
                x_permille: 60,
                y_permille: 700,
                w_permille: 880,
                h_permille: 80,
                align_h: TextAlign::Left,
                align_v: VAlign::Middle,
                size_permille: 40,
                line_height_permille: 1100,
                color: AMBER,
                visible: true,
            },
            body: RegionStyle {
                x_permille: 60,
                y_permille: 778,
                w_permille: 880,
                h_permille: 170,
                align_h: TextAlign::Left,
                align_v: VAlign::Top,
                size_permille: 62,
                line_height_permille: 1100,
                color: Rgba::WHITE,
                visible: true,
            },
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
