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
    pub const BLACK: Rgba = Rgba { r: 0, g: 0, b: 0, a: 255 };
    pub const WHITE: Rgba = Rgba { r: 255, g: 255, b: 255, a: 255 };

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
    /// A line of monospaced text drawn left-to-right from the rect's top-left,
    /// `px` tall, clipped to `rect`. Rendered with a bundled 8×8 bitmap font by the
    /// CPU rasterizer; the wgpu compositor's GPU-native glyphs are a later batch, so
    /// today the on-screen path composites text on the CPU and presents via blit.
    Text {
        rect: Rect,
        text: String,
        px: u32,
        color: Rgba,
    },
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
