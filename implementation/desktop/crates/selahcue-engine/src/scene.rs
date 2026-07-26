//! The backend-independent scene model — the description of *what* to render.
//!
//! The same `Frame` is consumed by the GPU-free [`raster`](crate::raster) backend
//! (for tests and offscreen readback) and, later, by the wgpu on-screen backend,
//! so there is no test-only render path (ADR-0015). It is `serde`-serializable so
//! it can cross the render↔control IPC boundary.

use serde::{Deserialize, Serialize};

/// A straight (non-premultiplied) 8-bit RGBA colour.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rgba {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Rgba {
    pub const BLACK: Rgba = Rgba {
        r: 0,
        g: 0,
        b: 0,
        a: 255,
    };
    pub const WHITE: Rgba = Rgba {
        r: 255,
        g: 255,
        b: 255,
        a: 255,
    };

    /// Opaque colour from RGB.
    pub const fn rgb(r: u8, g: u8, b: u8) -> Self {
        Rgba { r, g, b, a: 255 }
    }

    /// Colour with an explicit alpha.
    pub const fn new(r: u8, g: u8, b: u8, a: u8) -> Self {
        Rgba { r, g, b, a }
    }

    /// Relative luminance in `0.0..=1.0` (Rec. 709 coefficients) — the basis for
    /// the seizure-safe flash analysis (FR-175).
    pub fn luminance(self) -> f64 {
        let r = self.r as f64 / 255.0;
        let g = self.g as f64 / 255.0;
        let b = self.b as f64 / 255.0;
        0.2126 * r + 0.7152 * g + 0.0722 * b
    }
}

/// An integer pixel rectangle, top-left origin. `w`/`h` are extents.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: u32,
    pub h: u32,
}

impl Rect {
    pub const fn new(x: i32, y: i32, w: u32, h: u32) -> Self {
        Rect { x, y, w, h }
    }
}

/// Horizontal alignment of a text line WITHIN its layer rect. `Left` reproduces
/// the historical top-left anchoring (the serde default, so older scenes still
/// deserialize); `Center`/`Right` offset the shaped line by its measured width so
/// themes can centre/right-align content (FR-010 layout).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum TextAlign {
    #[default]
    Left,
    Center,
    Right,
}

/// One drawable layer, painted in list order (painter's algorithm).
///
/// The MVP seam models everything as coloured rectangles: the headless analyzers
/// reason about coverage/luminance/red, not glyph shapes, so text and media blocks
/// are represented by their bounding fills here. Richer layer kinds extend this
/// enum without changing the seam.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "layer", rename_all = "snake_case")]
pub enum Layer {
    /// A solid-colour rectangle (alpha-composited over what is beneath it).
    Fill { rect: Rect, color: Rgba },
    /// A line of shaped text drawn within `rect`, `px` tall (the line-box cell),
    /// clipped to `rect`, aligned per `align`. Rasterized by the CPU compositor
    /// (cosmic-text/rustybuzz over the bundled OFL font, ADR-0014); the wgpu backend
    /// composites the same text on the CPU and presents via blit.
    Text {
        rect: Rect,
        text: String,
        px: u32,
        color: Rgba,
        /// Horizontal alignment within `rect`. Additive (`#[serde(default)]` = Left).
        #[serde(default)]
        align: TextAlign,
        /// The font family to shape with (86ajq6fxt). `None` = the bundled default
        /// (Noto Sans) — the deterministic, cross-OS-identical path (NFR-014). `Some`
        /// selects a SYSTEM font installed on the render machine (per-machine; a missing
        /// family falls back to the bundled font). Additive (`skip_serializing_if`).
        #[serde(default, skip_serializing_if = "Option::is_none")]
        font: Option<FontName>,
    },
}

/// A bounded, `Copy` font-family name (86ajq6fxt). A fixed-capacity stack string (not a
/// heap `String`) so [`Layer`] and `Theme` stay fixed-size `Copy` PODs and every name is
/// bounded (no-leak). A name that is empty / whitespace-only / over [`FontName::CAP`]
/// bytes is rejected — on BOTH the constructor AND deserialization (a hand-edited /
/// externally-supplied theme JSON cannot smuggle an empty or untrimmed family through the
/// wire, which would otherwise masquerade as a themed non-deterministic default).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FontName(arrayvec::ArrayString<{ FontName::CAP }>);

impl FontName {
    /// Maximum family-name length in bytes (font family names are short).
    pub const CAP: usize = 64;

    /// A font name from a trimmed, non-empty, ≤[`CAP`](Self::CAP)-byte string; `None`
    /// otherwise (empty / whitespace-only / too long / not representable).
    pub fn new(s: &str) -> Option<Self> {
        let s = s.trim();
        if s.is_empty() || s.len() > Self::CAP {
            return None;
        }
        arrayvec::ArrayString::from(s).ok().map(FontName)
    }

    /// The family name as a string slice.
    pub fn as_str(&self) -> &str {
        self.0.as_str()
    }
}

impl serde::Serialize for FontName {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(self.as_str())
    }
}

impl<'de> serde::Deserialize<'de> for FontName {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        // Route through the constructor so the wire enforces the SAME invariant (trim +
        // reject empty/over-long) — never a derived pass-through that bypasses it.
        let s = String::deserialize(d)?;
        FontName::new(&s).ok_or_else(|| {
            serde::de::Error::custom("empty, whitespace-only, or over-long font family name")
        })
    }
}

/// A single frame's scene: resolution, background, ordered layers, and the
/// emergency blackout flag.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Frame {
    pub width: u32,
    pub height: u32,
    pub background: Rgba,
    pub layers: Vec<Layer>,
    /// Emergency blackout — when set, the frame renders fully black regardless of
    /// its layers (a deliberate output state, not a fault).
    pub blackout: bool,
}

impl Frame {
    /// A black frame of the given size (the safe default output).
    pub fn new(width: u32, height: u32) -> Self {
        Frame {
            width,
            height,
            background: Rgba::BLACK,
            layers: Vec::new(),
            blackout: false,
        }
    }

    /// Set the background colour (builder style).
    pub fn with_background(mut self, color: Rgba) -> Self {
        self.background = color;
        self
    }

    /// Append a layer.
    pub fn push(&mut self, layer: Layer) {
        self.layers.push(layer);
    }
}
