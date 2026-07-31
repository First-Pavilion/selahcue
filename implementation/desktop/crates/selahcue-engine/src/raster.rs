//! GPU-free deterministic rasterizer + pixel readback (ADR-0015).
//!
//! Renders a [`Frame`] to an RGBA8 [`FrameBuffer`] on the CPU. It is a pure
//! function of the scene — no clock, no randomness — so the same scene always
//! yields byte-identical pixels (deterministic mode / golden-image parity). The
//! wgpu backend renders the *same* [`Frame`]; cross-GPU parity is asserted
//! perceptually (SSIM ≥ 0.99), not by byte-equality.

use crate::media::{self, DecodedImage};
use crate::scene::FontName;
use crate::scene::{Frame, Layer, MediaRef, Rect, Rgba, ShapeKind, TextAlign};
use cosmic_text::{
    Attrs, Buffer, Color as CtColor, Family, FontSystem, Metrics, Shaping, SwashCache,
};
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
    /// The DEFAULT shaper: the bundled font ONLY, system fonts never loaded — so text
    /// with no per-theme font shapes byte-identically on every OS (NFR-014).
    fs: FontSystem,
    /// The shaper for a per-theme SYSTEM font (86ajq6fxt): the bundled font PLUS the
    /// machine's installed fonts. Lazily built on the first themed render (scanning the
    /// OS font dirs is not free) and dropped on reset. `None` until a themed font is used.
    system_fs: Option<FontSystem>,
    cache: SwashCache,
    renders: u32,
}

/// Rebuild the (bounded but ever-appending) glyph/shape caches this often.
const RESET_EVERY: u32 = 4096;

/// A `FontSystem` holding only the bundled font — the deterministic default shaper.
fn build_bundled_fs() -> FontSystem {
    let mut db = cosmic_text::fontdb::Database::new();
    db.load_font_data(FONT_BYTES.to_vec());
    // A fixed locale so segmentation/line-breaking is identical everywhere.
    FontSystem::new_with_locale_and_db("en-US".to_string(), db)
}

/// Upper bound on the enumerated system-font list (86ajq6fxt) — a machine rarely has
/// this many distinct families; bounds the picker + the IPC payload (no unbounded growth).
pub const MAX_SYSTEM_FONTS: usize = 2048;

/// The distinct family names of the fonts installed on THIS machine, sorted + deduped +
/// bounded — for the Theme Designer's font picker (86ajq6fxt). Scans the OS font
/// directories (not free); call once when the picker opens. Empty on a machine with no
/// installed fonts (a minimal headless container); the default bundled font always works.
pub fn system_font_families() -> Vec<String> {
    let mut db = cosmic_text::fontdb::Database::new();
    db.load_system_fonts();
    let mut names: Vec<String> = db
        .faces()
        .flat_map(|face| face.families.iter().map(|(name, _lang)| name.clone()))
        .filter(|n| !n.trim().is_empty() && n.len() <= FontName::CAP)
        .collect();
    names.sort_unstable();
    names.dedup();
    names.truncate(MAX_SYSTEM_FONTS);
    names
}

/// A `FontSystem` holding the bundled font PLUS the machine's installed fonts (86ajq6fxt).
/// A per-theme font is requested by `Family::Name`; when that family is absent, cosmic-text
/// falls through its own fallback chain to a READABLE platform default (Noto Sans on Linux,
/// the OS UI font on macOS/Windows) — never tofu, blank, or a panic, and deterministic on a
/// given machine. (We do NOT set the generic sans-serif/serif families: those are only
/// consulted for `Family::SansSerif`/`Serif`/… which this path never emits, so they would be
/// dead code — the honest guarantee is "a readable platform font", not "always Noto Sans".)
fn build_system_fs() -> FontSystem {
    let mut db = cosmic_text::fontdb::Database::new();
    db.load_font_data(FONT_BYTES.to_vec());
    db.load_system_fonts();
    FontSystem::new_with_locale_and_db("en-US".to_string(), db)
}

impl TextCtx {
    fn new() -> Self {
        TextCtx {
            fs: build_bundled_fs(),
            system_fs: None,
            cache: SwashCache::new(),
            renders: 0,
        }
    }
    /// Periodically drop the caches so long-running sessions can't accumulate
    /// glyph images / shaped runs without bound (no-leak rule). The system shaper is
    /// dropped too (re-loaded lazily only if a themed font is used again).
    fn tick(&mut self) {
        self.renders = self.renders.wrapping_add(1);
        if self.renders.is_multiple_of(RESET_EVERY) {
            self.cache = SwashCache::new();
            self.fs = build_bundled_fs();
            self.system_fs = None;
        }
    }
    /// Ensure the lazy system shaper exists when a per-theme font is requested.
    fn ensure_system_fs(&mut self, font: Option<&FontName>) {
        if font.is_some() && self.system_fs.is_none() {
            self.system_fs = Some(build_system_fs());
        }
    }
}

/// The cosmic-text `Attrs` for `font`: the default (bundled) family, or a named system
/// family. A tiny helper so `draw_text` + `measure_line_width` agree exactly.
fn attrs_for(font: Option<&FontName>) -> Attrs<'_> {
    match font {
        None => Attrs::new(),
        Some(f) => Attrs::new().family(Family::Name(f.as_str())),
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

/// Fixed-point precision for the ellipse inside-test — a power of two so the
/// division is exact-integer and identical on every platform (NFR-014), chosen so
/// `nx*nx + ny*ny` always stays inside `i64` for any `u32` extent (overflow-proof).
const SHAPE_FP: i64 = 1 << 15;

/// Whether pixel-local `(lx, ly)` is inside an **ellipse** inscribed in the `w×h`
/// box (centre `(w/2, h/2)`). Tested in fixed point (`nx² + ny² ≤ 1`, scaled by
/// [`SHAPE_FP`]) so it never overflows for any `u32` extent and is byte-identical
/// cross-OS — a degree-4 exact test would overflow even `i128` near `u32::MAX`.
fn ellipse_inside(lx: i64, ly: i64, w: i64, h: i64) -> bool {
    if w <= 0 || h <= 0 {
        return false;
    }
    let dx = 2 * lx + 1 - w; // 2·(pixel-centre − centre_x)
    let dy = 2 * ly + 1 - h;
    let cap = SHAPE_FP + 1; // a magnitude whose square already exceeds SHAPE_FP²
    let nx = (dx * SHAPE_FP / w).clamp(-cap, cap);
    let ny = (dy * SHAPE_FP / h).clamp(-cap, cap);
    nx * nx + ny * ny <= SHAPE_FP * SHAPE_FP
}

/// Whether `(lx, ly)` is inside an **isosceles triangle** (apex top-centre, base on
/// the bottom edge) inscribed in `w×h`. Exact integer test in `i128` — the half-width
/// grows linearly from the apex, i.e. `2·h·|Δx| ≤ w·(2y+1)` (overflow-proof for any
/// `u32` extent: the product is degree-2 in the extents).
fn triangle_inside(lx: i64, ly: i64, w: i64, h: i64) -> bool {
    if w <= 0 || h <= 0 {
        return false;
    }
    let dx = (2 * lx + 1 - w) as i128; // 2·(x − centre_x)
    let ty = (2 * ly + 1) as i128; // 2·y, apex (top edge) = 0
    2 * (h as i128) * dx.abs() <= (w as i128) * ty
}

/// Whether `(lx, ly)` is inside a **rounded rectangle** in `w×h` with corner radius
/// `r` px (clamped to half the shorter side). Clamp-SDF corner test in `i128`
/// (doubled coordinates so the pixel centre is integral): the point is inside iff it
/// is within `r` of the rectangle inset by `r` on every side.
fn rounded_inside(lx: i64, ly: i64, w: i64, h: i64, r: i64) -> bool {
    if w <= 0 || h <= 0 {
        return false;
    }
    let r = r.clamp(0, w.min(h) / 2);
    if r == 0 {
        return true; // a plain rectangle (no corners cut)
    }
    let x = (2 * lx + 1) as i128;
    let y = (2 * ly + 1) as i128;
    let (w2, h2, r2) = (2 * w as i128, 2 * h as i128, 2 * r as i128);
    let ddx = x - x.clamp(r2, w2 - r2); // 0 along the straight edges
    let ddy = y - y.clamp(r2, h2 - r2);
    ddx * ddx + ddy * ddy <= r2 * r2
}

/// Whether `(lx, ly)` is inside shape `kind` inscribed in `w×h` (corner radius `r`
/// px for rounded). `Rect` is the plain box (used for the inset ring; a real `Rect`
/// element composes to [`Layer::Fill`], never here).
fn shape_inside(kind: ShapeKind, lx: i64, ly: i64, w: i64, h: i64, r: i64) -> bool {
    match kind {
        ShapeKind::Rect => lx >= 0 && ly >= 0 && lx < w && ly < h,
        ShapeKind::Ellipse => ellipse_inside(lx, ly, w, h),
        ShapeKind::RoundedRect => rounded_inside(lx, ly, w, h, r),
        ShapeKind::Triangle => triangle_inside(lx, ly, w, h),
    }
}

/// Draw a [`Layer::Shape`](crate::scene::Layer::Shape): fill the parametric shape
/// (`kind`) inscribed in `rect` with `fill`, outlined by an inset ring of `border`
/// `border_px` px thick; `corner_px` is the rounded-rect radius. Pure integer
/// per-pixel tests over the ON-SCREEN clipped span — bounded exactly like
/// [`fill_rect`] (the layer rect is UNVALIDATED, so every coordinate is derived from
/// the clipped span in `i64`; no raw i32 arithmetic can overflow-panic) and
/// deterministic (NFR-014). Any layer opacity is already folded into `fill`/`border`
/// alpha by `compose`, so this just src-over blends.
fn draw_shape(
    fb: &mut FrameBuffer,
    rect: Rect,
    kind: ShapeKind,
    fill: Rgba,
    border: Rgba,
    border_px: u32,
    corner_px: u32,
) {
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height as i64) as u32;
    if x0 >= x1 || y0 >= y1 {
        return; // nothing of the shape is on-screen
    }
    let (w, h) = (rect.w as i64, rect.h as i64);
    let b = border_px as i64;
    let r = corner_px as i64;
    // The inner (fill) shape is the outer shrunk by `border_px` on every side; when
    // the border is thick enough to swallow the interior, everything drawn is border.
    let (iw, ih, ir) = (w - 2 * b, h - 2 * b, (r - b).max(0));
    let has_border = b > 0;
    for y in y0..y1 {
        let ly = y as i64 - rect.y as i64; // ∈ [0, h) within the clipped span
        for x in x0..x1 {
            let lx = x as i64 - rect.x as i64; // ∈ [0, w) within the clipped span
            if !shape_inside(kind, lx, ly, w, h, r) {
                continue; // outside the shape → leave the background untouched
            }
            let paint = if has_border && !shape_inside(kind, lx - b, ly - b, iw, ih, ir) {
                border
            } else {
                fill
            };
            fb.blend(x, y, paint);
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
                font,
            } => draw_text(&mut fb, *rect, text, *px, *color, *align, font.as_ref()),
            Layer::Image {
                rect,
                source,
                opacity,
            } => draw_image(&mut fb, *rect, source, *opacity),
            Layer::Shape {
                rect,
                kind,
                fill,
                border,
                border_px,
                corner_px,
            } => draw_shape(
                &mut fb, *rect, *kind, *fill, *border, *border_px, *corner_px,
            ),
        }
    }
    fb
}

/// Draw a [`Layer::Image`](crate::scene::Layer::Image): resolve `source` through the
/// bounded decode cache and blit the decoded image scaled into `rect` at `opacity`; on a
/// missing / corrupt / unsupported / over-budget source, draw the missing-media
/// placeholder instead (FR-070) — never a blank rect, never a crash.
fn draw_image(fb: &mut FrameBuffer, rect: Rect, source: &MediaRef, opacity: u8) {
    media::with_resolved(source, |resolved| match resolved {
        Some(img) => blit_image(fb, rect, img, opacity),
        None => draw_placeholder(fb, rect, opacity),
    });
}

/// Multiply a whole-layer `opacity` into a colour's alpha (same rounding as [`blend`]).
fn scale_alpha(color: Rgba, opacity: u8) -> Rgba {
    Rgba::new(
        color.r,
        color.g,
        color.b,
        ((color.a as u32 * opacity as u32 + 127) / 255) as u8,
    )
}

/// Blit `img` scaled into `rect` with **integer nearest-neighbour** sampling (a pure
/// integer function → deterministic, cross-OS byte-identical; no bilinear divergence),
/// each source pixel alpha-composited (src-over) at the whole-layer `opacity`. Clipped to
/// the on-screen intersection of `rect` and the frame, exactly like [`fill_rect`].
fn blit_image(fb: &mut FrameBuffer, rect: Rect, img: &DecodedImage, opacity: u8) {
    if rect.w == 0 || rect.h == 0 || img.width() == 0 || img.height() == 0 || opacity == 0 {
        return;
    }
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height as i64) as u32;
    let (iw, ih) = (img.width() as u64, img.height() as u64);
    let (rw, rh) = (rect.w as u64, rect.h as u64);
    for y in y0..y1 {
        // Destination offset within the rect (≥ 0 across the clipped span).
        let dy = (y as i64 - rect.y as i64).max(0) as u64;
        let sy = ((dy * ih) / rh).min(ih - 1) as u32;
        for x in x0..x1 {
            let dx = (x as i64 - rect.x as i64).max(0) as u64;
            let sx = ((dx * iw) / rw).min(iw - 1) as u32;
            fb.blend(x, y, scale_alpha(img.sample(sx, sy), opacity));
        }
    }
}

/// The distinct, non-black "media missing / failed" placeholder (FR-070). Deterministic
/// (drawn from fills), so a missing/corrupt image is HONEST — never a blank rect, never a
/// crash. A muted purple-grey panel with a lighter border and a diagonal slash.
fn draw_placeholder(fb: &mut FrameBuffer, rect: Rect, opacity: u8) {
    if rect.w == 0 || rect.h == 0 || opacity == 0 {
        return;
    }
    let base = scale_alpha(Rgba::rgb(64, 54, 74), opacity); // clearly not black
    let mark = scale_alpha(Rgba::rgb(150, 130, 170), opacity); // lighter accent
                                                               // Base panel — `fill_rect` clips the (unvalidated) rect safely in i64.
    fill_rect(fb, rect, base);

    // Border + diagonal are decoration ON TOP of the base. The layer rect is NOT
    // validated (only `frame.width/height` pass through the engine boundary — a scene
    // can carry any i32/u32 rect from a hand-edited/IPC theme), so every coordinate here
    // is derived from the ON-SCREEN clipped span (≤ frame dimension ≤ MAX_DIMENSION) and
    // computed in i64/i128 — no raw i32 rect arithmetic can overflow-panic (matching the
    // overflow-safe pattern of `fill_rect`/`blit_image`/`draw_text`).
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height as i64) as u32;
    if x0 >= x1 || y0 >= y1 {
        return; // nothing of the rect is on-screen
    }
    // Border thickness ∝ the smaller side (≥ 1). Rect edges in i64 (i32 + u32 fits i64).
    let bt = (rect.w.min(rect.h) / 16).max(1) as i64;
    let left = rect.x as i64;
    let right = left + rect.w as i64; // exclusive
    let top = rect.y as i64;
    let bottom = top + rect.h as i64; // exclusive
                                      // Diagonal-slash metric in i128 so `u*rh` can never i64-overflow for extreme rects.
    let (rw, rh) = (rect.w as i128, rect.h as i128);
    let tol = (rw + rh) * (bt as i128);
    for py in y0..y1 {
        let yy = py as i64; // in [0, fb.height) → bounded
        let v = yy - top; // ≥ 0 within the span; bounded by the frame dimension
        for px in x0..x1 {
            let xx = px as i64; // in [0, fb.width) → bounded
            let u = xx - left; // ≥ 0 within the span
            let near_border = u < bt || (right - 1 - xx) < bt || v < bt || (bottom - 1 - yy) < bt;
            let on_diagonal = ((u as i128) * rh - (v as i128) * rw).abs() <= tol;
            if near_border || on_diagonal {
                fb.blend(px, py, mark);
            }
        }
    }
}

/// The shaped pixel width of `text` at cell height `px` — using the SAME font sizing
/// [`draw_text`] does (`px·FONT_TO_LINE`, one unwrapped line). `compose`'s shrink-to-fit
/// uses this to scale the cell so the WIDEST line fits the region width, not only its
/// height: `draw_text` never wraps, so an over-wide line would otherwise clip on the
/// right. Uses the SAME font as `draw_text` (`font`: `None` = bundled default; `Some` =
/// the per-theme system font) so the width matches what is drawn. Returns `0.0` for
/// empty/zero input.
pub fn measure_line_width(text: &str, px: u32, font: Option<&FontName>) -> f32 {
    if px == 0 || text.is_empty() {
        return 0.0;
    }
    let line_h = (px as f32).max(1.0);
    let font_size = (line_h * FONT_TO_LINE).max(1.0);
    let attrs = attrs_for(font);
    TEXT.with(|cell| {
        let ctx = &mut *cell.borrow_mut();
        ctx.tick();
        ctx.ensure_system_fs(font);
        let TextCtx { fs, system_fs, .. } = ctx;
        let shaper: &mut FontSystem = match font {
            None => fs,
            Some(_) => system_fs.as_mut().expect("ensured above"),
        };
        let mut buffer = Buffer::new(shaper, Metrics::new(font_size, line_h));
        buffer.set_size(shaper, None, None);
        buffer.set_text(shaper, text, attrs, Shaping::Advanced);
        buffer.shape_until_scroll(shaper, false);
        buffer
            .layout_runs()
            .map(|r| r.line_w)
            .fold(0.0_f32, f32::max)
    })
}

/// Shape and rasterize `text` with the bundled OFL font (cosmic-text/rustybuzz →
/// swash), from `rect`'s top-left, at ≈`px` tall, in `color`, clipped to the
/// on-screen intersection of `rect` and the frame (ADR-0014). Unlike the old
/// bitmap path, Unicode + diacritics (Yoruba/Igbo tonal marks, French/Spanish
/// accents) shape and position correctly (FR-017). Deterministic: a single
/// bundled shaper+font renders byte-identically on every OS.
#[allow(clippy::too_many_arguments)]
fn draw_text(
    fb: &mut FrameBuffer,
    rect: Rect,
    text: &str,
    px: u32,
    color: Rgba,
    align: TextAlign,
    font: Option<&FontName>,
) {
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

    let attrs = attrs_for(font);
    TEXT.with(|cell| {
        let ctx = &mut *cell.borrow_mut();
        ctx.tick();
        ctx.ensure_system_fs(font);
        // Split-borrow: the chosen shaper (bundled default OR the system shaper) and the
        // glyph cache are independent fields of the context.
        let TextCtx {
            fs,
            system_fs,
            cache,
            ..
        } = ctx;
        let fs: &mut FontSystem = match font {
            None => fs,
            Some(_) => system_fs.as_mut().expect("ensured above"),
        };
        // The font at `font_size`, laid out in a `line_h`-tall line box, so a
        // glyph's ink stays inside the cell (see above). Unconstrained size → one
        // line, no wrap; horizontal culling below keeps the WORK frame-bounded.
        let mut buffer = Buffer::new(fs, Metrics::new(font_size, line_h));
        buffer.set_size(fs, None, None);
        buffer.set_text(fs, text, attrs, Shaping::Advanced);
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
