//! GPU-free deterministic rasterizer + pixel readback (ADR-0015).
//!
//! Renders a [`Frame`] to an RGBA8 [`FrameBuffer`] on the CPU. It is a pure
//! function of the scene — no clock, no randomness — so the same scene always
//! yields byte-identical pixels (deterministic mode / golden-image parity). The
//! wgpu backend renders the *same* [`Frame`]; cross-GPU parity is asserted
//! perceptually (SSIM ≥ 0.99), not by byte-equality.

use crate::scene::{Frame, Layer, Rect, Rgba, TextAlign};
use cosmic_text::{Attrs, Buffer, Color as CtColor, FontSystem, Metrics, Shaping, SwashCache};
use std::cell::RefCell;

/// The single BUNDLED output font (Noto Sans, Regular, Latin subset — OFL, see
/// `assets/fonts/OFL.txt`). Compiled into the binary so text shapes and
/// rasterizes IDENTICALLY on every OS (no system-font divergence → NFR-014) with
/// a memory-safe pure-Rust parser (FR-173). Covers the FR-017 diacritic set
/// (Yoruba/Hausa/Igbo/French/Spanish).
static FONT_BYTES: &[u8] = include_bytes!("../assets/fonts/NotoSans-Latin.ttf");

/// Font size as a fraction of the line-box (`px`) height. The bundled Noto Sans
/// has an ascent+descent of ~1.36 em, so a font sized at ~0.72 of the cell keeps
/// the full glyph box — descenders and dot-below marks included — inside the cell
/// (leaving normal leading), rather than overflowing and being clipped.
const FONT_TO_LINE: f32 = 0.72;

/// Per-thread shaper + glyph-raster cache, built from ONLY the bundled font
/// (system fonts are never loaded, so shaping is deterministic and identical
/// across OSes). The caches are keyed by glyph/text + size + subpixel; the app's
/// output size is fixed so `px` takes only a few values in practice, but to keep
/// memory bounded even against a caller that renders at many distinct sizes, the
/// whole context is rebuilt from scratch every [`RESET_EVERY`] renders (cheap —
/// re-loading a 127 KB font — and it fully frees both caches; no unbounded growth).
struct TextCtx {
    fs: FontSystem,
    cache: SwashCache,
    renders: u32,
}

/// Rebuild the (bounded but ever-appending) glyph/shape caches this often.
const RESET_EVERY: u32 = 4096;

impl TextCtx {
    fn new() -> Self {
        let mut db = cosmic_text::fontdb::Database::new();
        db.load_font_data(FONT_BYTES.to_vec());
        // A fixed locale so segmentation/line-breaking is identical everywhere.
        let fs = FontSystem::new_with_locale_and_db("en-US".to_string(), db);
        TextCtx {
            fs,
            cache: SwashCache::new(),
            renders: 0,
        }
    }
    /// Periodically drop the caches so long-running sessions can't accumulate
    /// glyph images / shaped runs without bound (no-leak rule).
    fn tick(&mut self) {
        self.renders = self.renders.wrapping_add(1);
        if self.renders.is_multiple_of(RESET_EVERY) {
            self.cache = SwashCache::new();
            self.fs = {
                let mut db = cosmic_text::fontdb::Database::new();
                db.load_font_data(FONT_BYTES.to_vec());
                FontSystem::new_with_locale_and_db("en-US".to_string(), db)
            };
        }
    }
}

thread_local! {
    static TEXT: RefCell<TextCtx> = RefCell::new(TextCtx::new());
}

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

    /// Wrap raw RGBA8 bytes (row-major, 4 bytes/px) as a framebuffer — e.g. a GPU
    /// readback for cross-backend comparison. Returns `None` if the length or the
    /// dimensions are invalid.
    pub fn from_rgba(width: u32, height: u32, pixels: Vec<u8>) -> Option<Self> {
        let expected = (width as usize)
            .checked_mul(height as usize)?
            .checked_mul(4)?;
        if is_renderable(width, height) && pixels.len() == expected {
            Some(FrameBuffer {
                width,
                height,
                pixels,
            })
        } else {
            None
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
            Layer::Text {
                rect,
                text,
                px,
                color,
                align,
            } => draw_text(&mut fb, *rect, text, *px, *color, *align),
        }
    }
    fb
}

/// Shape and rasterize `text` with the bundled OFL font (cosmic-text/rustybuzz →
/// swash), from `rect`'s top-left, at ≈`px` tall, in `color`, clipped to the
/// on-screen intersection of `rect` and the frame (ADR-0014). Unlike the old
/// bitmap path, Unicode + diacritics (Yoruba/Igbo tonal marks, French/Spanish
/// accents) shape and position correctly (FR-017). Deterministic: a single
/// bundled shaper+font renders byte-identically on every OS.
fn draw_text(fb: &mut FrameBuffer, rect: Rect, text: &str, px: u32, color: Rgba, align: TextAlign) {
    if px == 0 || rect.w == 0 || rect.h == 0 || text.is_empty() {
        return;
    }
    // Clip to the on-screen intersection of the layer rect and the frame.
    let clip_right = rect.x.saturating_add(rect.w as i32).min(fb.width as i32);
    let clip_bottom = rect.y.saturating_add(rect.h as i32).min(fb.height as i32);
    // `px` is the CELL height (a line box, from `compose`). The font size is a
    // fraction of it so the font's full ascent+descent box (~1.36 em for Noto
    // Sans) fits INSIDE the cell — otherwise cosmic-text centres a taller box in
    // the cell and the clip crops descenders and the Yoruba/Igbo dot-below marks
    // (ẹ/ọ/ṣ/ị) FR-017 targets. Capped at the framebuffer height for safety.
    let line_h = (px as f32).min(fb.height as f32).max(1.0);
    let font_size = (line_h * FONT_TO_LINE).max(1.0);

    TEXT.with(|cell| {
        let ctx = &mut *cell.borrow_mut();
        ctx.tick();
        let TextCtx { fs, cache, .. } = ctx;
        // The font at `font_size`, laid out in a `line_h`-tall line box, so a
        // glyph's ink stays inside the cell (see above). Unconstrained size → one
        // line, no wrap; horizontal culling below keeps the WORK frame-bounded.
        let mut buffer = Buffer::new(fs, Metrics::new(font_size, line_h));
        buffer.set_size(fs, None, None);
        buffer.set_text(fs, text, Attrs::new(), Shaping::Advanced);
        buffer.shape_until_scroll(fs, false);

        let ink = CtColor::rgba(color.r, color.g, color.b, color.a);
        for run in buffer.layout_runs() {
            let base_y = rect.y.saturating_add(run.line_y as i32);
            // Horizontal alignment: offset the whole line by its measured shaped
            // width (`line_w`) within the rect. Clamped ≥ 0 so an over-wide line
            // still starts at the left edge (then the clip trims the overflow).
            let align_x = match align {
                TextAlign::Left => 0,
                TextAlign::Center => (((rect.w as f32) - run.line_w) * 0.5).max(0.0) as i32,
                TextAlign::Right => ((rect.w as f32) - run.line_w).max(0.0) as i32,
            };
            let origin_x = rect.x.saturating_add(align_x);
            for glyph in run.glyphs.iter() {
                let pg = glyph.physical((0.0, 0.0), 1.0);
                let pen_x = origin_x.saturating_add(pg.x);
                // Glyphs are laid out left-to-right: once one starts at/after the
                // clip, every later glyph does too — stop. This bounds the work
                // to the VISIBLE glyphs, not the whole line (a long/pasted line
                // must not stall the frame — the old bitmap path broke here too).
                if pen_x >= clip_right {
                    break;
                }
                // A glyph spans at most ~one em; skip those wholly left of the rect.
                if pen_x + line_h as i32 + 2 < rect.x {
                    continue;
                }
                let gcolor = glyph.color_opt.unwrap_or(ink);
                cache.with_pixels(fs, pg.cache_key, gcolor, |ox, oy, c| {
                    let a = c.a();
                    if a == 0 {
                        return;
                    }
                    // Saturating so an extreme rect origin + glyph offset can
                    // never i32-overflow-panic (the clip below discards them).
                    let x = pen_x.saturating_add(ox);
                    let y = base_y.saturating_add(pg.y).saturating_add(oy);
                    if x < rect.x || x >= clip_right || y < rect.y || y >= clip_bottom {
                        return; // clip to the layer rect + frame (protects the safe margin)
                    }
                    fb.blend(x as u32, y as u32, Rgba::new(c.r(), c.g(), c.b(), a));
                });
            }
        }
    });
}
