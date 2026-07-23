//! GPU-free deterministic rasterizer + pixel readback (ADR-0015).
//!
//! Renders a [`Frame`] to an RGBA8 [`FrameBuffer`] on the CPU. It is a pure
//! function of the scene — no clock, no randomness — so the same scene always
//! yields byte-identical pixels (deterministic mode / golden-image parity). The
//! wgpu backend renders the *same* [`Frame`]; cross-GPU parity is asserted
//! perceptually (SSIM ≥ 0.99), not by byte-equality.

use crate::scene::{Frame, Layer, Rect, Rgba};

/// Largest render dimension per side (covers 8K outputs with headroom). Frames
/// beyond this are rejected at the engine boundary rather than allocated, so a
/// bad/hostile resolution cannot exhaust memory or overflow (NFR-024).
pub const MAX_DIMENSION: u32 = 8192;

/// Whether a frame of these dimensions can be safely rendered (non-zero and within
/// [`MAX_DIMENSION`]).
pub fn is_renderable(width: u32, height: u32) -> bool {
    width > 0 && height > 0 && width <= MAX_DIMENSION && height <= MAX_DIMENSION
}

/// A rendered RGBA8 frame — the CPU-side pixel readback (row-major, 4 bytes/px).
#[derive(Clone, PartialEq, Eq)]
pub struct FrameBuffer {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl FrameBuffer {
    /// A framebuffer of `width×height` filled with `color`.
    ///
    /// Total by construction: dimensions outside [`is_renderable`] fall back to a
    /// safe 1×1 buffer instead of overflowing or attempting an unbounded allocation
    /// (the engine validates first, so this is a defensive backstop).
    pub fn filled(width: u32, height: u32, color: Rgba) -> Self {
        let (width, height) = if is_renderable(width, height) {
            (width, height)
        } else {
            (1, 1)
        };
        // width, height ≤ MAX_DIMENSION so this cannot overflow usize.
        let count = (width as usize) * (height as usize);
        let mut pixels = Vec::with_capacity(count * 4);
        for _ in 0..count {
            pixels.extend_from_slice(&[color.r, color.g, color.b, color.a]);
        }
        FrameBuffer {
            width,
            height,
            pixels,
        }
    }

    pub fn width(&self) -> u32 {
        self.width
    }
    pub fn height(&self) -> u32 {
        self.height
    }

    /// The raw RGBA8 bytes (row-major) — the readback a preview stream or a
    /// golden-image comparison consumes.
    pub fn bytes(&self) -> &[u8] {
        &self.pixels
    }

    /// Size of the readback in bytes — constant for a given resolution (used to
    /// assert the engine's output buffer does not grow).
    pub fn byte_len(&self) -> usize {
        self.pixels.len()
    }

    fn index(&self, x: u32, y: u32) -> Option<usize> {
        if x < self.width && y < self.height {
            // usize math — no u32 overflow even at the maximum resolution.
            Some((y as usize * self.width as usize + x as usize) * 4)
        } else {
            None
        }
    }

    /// The colour at `(x, y)` (opaque alpha for an on-screen buffer).
    pub fn pixel(&self, x: u32, y: u32) -> Option<Rgba> {
        let i = self.index(x, y)?;
        Some(Rgba {
            r: self.pixels[i],
            g: self.pixels[i + 1],
            b: self.pixels[i + 2],
            a: self.pixels[i + 3],
        })
    }

    /// Alpha-composite `color` over the pixel at `(x, y)` (src-over, integer math).
    fn blend(&mut self, x: u32, y: u32, color: Rgba) {
        let Some(i) = self.index(x, y) else {
            return;
        };
        let sa = color.a as u32;
        let ia = 255 - sa;
        // out = src*sa + dst*(255-sa), rounded, per channel.
        let mix = |src: u8, dst: u8| -> u8 {
            (((src as u32 * sa) + (dst as u32 * ia) + 127) / 255) as u8
        };
        self.pixels[i] = mix(color.r, self.pixels[i]);
        self.pixels[i + 1] = mix(color.g, self.pixels[i + 1]);
        self.pixels[i + 2] = mix(color.b, self.pixels[i + 2]);
        // Output is opaque; keep alpha at max.
        self.pixels[i + 3] = 255;
    }

    /// Mean relative luminance over all pixels — the per-frame signal the flash
    /// analyzer differences (FR-175).
    pub fn average_luminance(&self) -> f64 {
        let count = (self.width as usize) * (self.height as usize);
        if count == 0 {
            return 0.0;
        }
        let mut sum = 0.0;
        for px in self.pixels.chunks_exact(4) {
            sum += Rgba {
                r: px[0],
                g: px[1],
                b: px[2],
                a: px[3],
            }
            .luminance();
        }
        sum / count as f64
    }

    /// Per-tile mean `(luminance, redness)` over a `cols×rows` grid (row-major).
    ///
    /// The flash analyzer runs per tile so a strobe confined to a sub-region is not
    /// diluted below the detection threshold by the static rest of the frame
    /// (FR-175 spatial locality).
    pub fn tile_stats(&self, cols: u32, rows: u32) -> (Vec<f64>, Vec<f64>) {
        let cols = cols.max(1);
        let rows = rows.max(1);
        let n = (cols as usize) * (rows as usize);
        let mut lum = vec![0.0f64; n];
        let mut red = vec![0.0f64; n];
        let mut count = vec![0u32; n];
        if self.width == 0 || self.height == 0 {
            return (lum, red);
        }
        for y in 0..self.height {
            let ty = (y * rows / self.height).min(rows - 1);
            for x in 0..self.width {
                let tx = (x * cols / self.width).min(cols - 1);
                let t = (ty * cols + tx) as usize;
                let i = (y as usize * self.width as usize + x as usize) * 4;
                let (r, g, b) = (self.pixels[i], self.pixels[i + 1], self.pixels[i + 2]);
                lum[t] += Rgba { r, g, b, a: 255 }.luminance();
                let rf = r as f64 / 255.0;
                let gf = g as f64 / 255.0;
                let bf = b as f64 / 255.0;
                red[t] += (rf - (gf + bf) / 2.0).max(0.0);
                count[t] += 1;
            }
        }
        for t in 0..n {
            if count[t] > 0 {
                lum[t] /= count[t] as f64;
                red[t] /= count[t] as f64;
            }
        }
        (lum, red)
    }

    /// Mean "redness" (red minus the other channels, clamped) — the basis for the
    /// FR-175 red-flash sub-criterion.
    pub fn average_redness(&self) -> f64 {
        let count = (self.width as usize) * (self.height as usize);
        if count == 0 {
            return 0.0;
        }
        let mut sum = 0.0;
        for px in self.pixels.chunks_exact(4) {
            let r = px[0] as f64 / 255.0;
            let g = px[1] as f64 / 255.0;
            let b = px[2] as f64 / 255.0;
            sum += (r - (g + b) / 2.0).max(0.0);
        }
        sum / count as f64
    }
}

impl std::fmt::Debug for FrameBuffer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("FrameBuffer")
            .field("width", &self.width)
            .field("height", &self.height)
            .field("avg_luminance", &self.average_luminance())
            .finish()
    }
}

fn fill_rect(fb: &mut FrameBuffer, rect: Rect, color: Rgba) {
    // Clip to the buffer; iterate the visible span only.
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height as i64) as u32;
    for y in y0..y1 {
        for x in x0..x1 {
            fb.blend(x, y, color);
        }
    }
}

/// Render a scene to an RGBA8 framebuffer — deterministic and GPU-free.
pub fn render(frame: &Frame) -> FrameBuffer {
    if frame.blackout {
        // Blackout is a deliberate, safe output state (not a fault).
        return FrameBuffer::filled(frame.width, frame.height, Rgba::BLACK);
    }
    let mut fb = FrameBuffer::filled(frame.width, frame.height, frame.background);
    for layer in &frame.layers {
        match layer {
            Layer::Fill { rect, color } => fill_rect(&mut fb, *rect, *color),
        }
    }
    fb
}
