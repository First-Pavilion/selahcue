//! GPU-free deterministic rasterizer + pixel readback (ADR-0015).
//!
//! Renders a [`Frame`] to an RGBA8 [`FrameBuffer`] on the CPU. It is a pure
//! function of the scene — no clock, no randomness — so the same scene always
//! yields byte-identical pixels (deterministic mode / golden-image parity). The
//! wgpu backend renders the *same* [`Frame`]; cross-GPU parity is asserted
//! perceptually (SSIM ≥ 0.99), not by byte-equality.

use crate::media::{self, DecodedImage};
use crate::scene::FontName;
use crate::scene::{
    Frame, GradientDirection, ImageFit, Layer, MediaRef, Rect, Rgba, ShapeKind, TextAlign,
};
use cosmic_text::{
    Attrs, Buffer, Color as CtColor, Family, FontSystem, Metrics, Shaping, SwashCache, Weight,
};
use std::cell::RefCell;
use std::sync::Mutex;

/// The single BUNDLED output font (Noto Sans, Regular, Latin subset — OFL, see
/// `assets/fonts/OFL.txt`). Compiled into the binary so text shapes and
/// rasterizes IDENTICALLY on every OS (no system-font divergence → NFR-014) with
/// a memory-safe pure-Rust parser (FR-173). Covers the FR-017 diacritic set
/// (Yoruba/Hausa/Igbo/French/Spanish).
static FONT_BYTES: &[u8] = include_bytes!("../assets/fonts/NotoSans-Latin.ttf");

/// A second BUNDLED family — Inter (OFL, a Latin subset). It is loaded only into the
/// named-font `FontSystem` (never the default), so a Layer requesting `Family::Name("Inter")`
/// resolves to this bundled face deterministically — used by the stage/confidence monitor
/// (Figma 373-375) — while the default (`font: None`, e.g. the audience output) stays exactly
/// on the bundled Noto Sans, byte-identical as before (NFR-014).
static INTER_BYTES: &[u8] = include_bytes!("../assets/fonts/Inter-Latin.ttf");

/// The bundled Inter **Bold** (700) static face. A named-font request never falls back to a
/// system font for a heavier weight when the exact weight is present: with only a single
/// Regular face loaded, cosmic-text resolves `(Inter, 700)` to a *system monospace* once
/// system fonts are in the DB — so the stage's bold text must have a real 700 face bundled.
static INTER_BOLD_BYTES: &[u8] = include_bytes!("../assets/fonts/Inter-Bold-Latin.ttf");

/// The bundled family name to request a Layer in the Inter face (`Family::Name(STAGE_FONT)`).
pub const STAGE_FONT: &str = "Inter";

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
    // Bundled Noto Sans first, for the same reason as Inter below: a bundled face loaded BEFORE
    // `load_system_fonts()` wins the family-name tie-break, so `Family::Name("Noto Sans")` gets
    // the face we ship rather than a machine-installed one. For Noto Sans specifically this
    // currently makes no measurable difference — the bundled file is a Latin subset of the same
    // design, so either face yields the same advances at weight 400 (measured against
    // `fonts-noto-core` in a container). That is a property of Noto Sans, not of this function:
    // see the Inter note below, where it does NOT hold.
    db.load_font_data(FONT_BYTES.to_vec());
    // Bundled Inter Regular + Bold (loaded before the system fonts so `Family::Name("Inter")`
    // resolves to the bundled faces, not a machine-installed Inter) — the stage/confidence
    // typeface. Both weights are bundled so `(Inter, 700)` has an exact face and never falls
    // back to a system monospace once system fonts are in the DB. Unlike Noto Sans above, the
    // ORDER IS LOAD-BEARING here and nothing tests it: a machine-installed Inter may be v3 or
    // v4, and Inter 4.0 changed default metrics, so if a system Inter won the tie-break the
    // stage/confidence advances would move on that host alone.
    db.load_font_data(INTER_BYTES.to_vec());
    db.load_font_data(INTER_BOLD_BYTES.to_vec());
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
fn attrs_for(font: Option<&FontName>, weight: u16) -> Attrs<'_> {
    let base = match font {
        None => Attrs::new(),
        Some(f) => Attrs::new().family(Family::Name(f.as_str())),
    };
    // The numeric font weight (86ajq3225): cosmic-text/swash synthesizes a heavier weight for
    // the single-weight bundled font (a deterministic embolden) or selects a real bold face of
    // a system font. Weight 400 is Regular (the historical path).
    base.weight(Weight(weight))
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

/// How a composed frame fits its output surface — the per-output "scaling / fit" transform
/// ([`FrameBuffer::fitted`]). Mirrors the wire `ScaleFit` (the protocol crate does not depend
/// on the engine, so the desktop host maps one to the other).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Fit {
    /// Cover the surface, centre-cropping overflow (preserve aspect). The default.
    #[default]
    Fill,
    /// Contain within the surface, letterboxing (preserve aspect, no crop).
    Fit,
    /// Stretch to the exact surface, distorting aspect.
    Stretch,
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

    /// A **downscaled thumbnail** that fits within `max_w × max_h` while preserving the
    /// source aspect ratio (86ajtwq28 — the operator console preview/live monitors). Each
    /// destination pixel is the **box-average** (integer mean) of the source block it
    /// covers, so it is a deterministic, byte-identical-cross-OS still of the true output
    /// (NFR-014) that keeps thin text/borders visible where nearest-neighbour would drop
    /// them. Never UPSCALES: a buffer already within the bound is returned unchanged.
    /// Bounded + total: `max_w`/`max_h` are clamped to `1..=MAX_DIMENSION`, so it never
    /// panics or over-allocates on a degenerate or hostile size.
    pub fn thumbnail(&self, max_w: u32, max_h: u32) -> FrameBuffer {
        let max_w = max_w.clamp(1, MAX_DIMENSION);
        let max_h = max_h.clamp(1, MAX_DIMENSION);
        // Never upscale — a buffer already within the bound is faithful as-is.
        if self.width <= max_w && self.height <= max_h {
            return self.clone();
        }
        // The largest (tw, th) within the bound that keeps the SOURCE aspect ratio.
        let (w, h) = (self.width as u64, self.height as u64);
        let (mw, mh) = (max_w as u64, max_h as u64);
        let (tw, th) = if w * mh <= h * mw {
            (((w * mh) / h).max(1), mh) // height binds
        } else {
            (mw, ((h * mw) / w).max(1)) // width binds
        };
        let (tw, th) = (tw.min(mw).max(1), th.min(mh).max(1));
        let mut pixels = Vec::with_capacity((tw * th) as usize * 4);
        for ty in 0..th {
            let sy0 = (ty * h / th) as u32;
            let sy1 = (((ty + 1) * h / th) as u32).max(sy0 + 1).min(self.height);
            for tx in 0..tw {
                let sx0 = (tx * w / tw) as u32;
                let sx1 = (((tx + 1) * w / tw) as u32).max(sx0 + 1).min(self.width);
                // Box-average the covered source block. `u64` sums: a 1×1 target covers the
                // whole image, so a per-channel sum can exceed `u32`.
                let (mut r, mut g, mut b, mut a, mut n) = (0u64, 0u64, 0u64, 0u64, 0u64);
                for sy in sy0..sy1 {
                    let row = sy as usize * self.width as usize;
                    for sx in sx0..sx1 {
                        let i = (row + sx as usize) * 4;
                        r += self.pixels[i] as u64;
                        g += self.pixels[i + 1] as u64;
                        b += self.pixels[i + 2] as u64;
                        a += self.pixels[i + 3] as u64;
                        n += 1;
                    }
                }
                let n = n.max(1);
                pixels.extend_from_slice(&[
                    (r / n) as u8,
                    (g / n) as u8,
                    (b / n) as u8,
                    (a / n) as u8,
                ]);
            }
        }
        FrameBuffer {
            width: tw as u32,
            height: th as u32,
            pixels,
        }
    }

    /// A horizontally MIRRORED copy (each row reversed) — the per-output "mirror
    /// horizontally" transform (Screens inspector). Pure integer, deterministic + byte-
    /// identical cross-OS (NFR-014), like [`thumbnail`](Self::thumbnail). Same dimensions.
    pub fn mirrored_horizontal(&self) -> FrameBuffer {
        let w = self.width as usize;
        let h = self.height as usize;
        let mut pixels = vec![0u8; self.pixels.len()];
        for y in 0..h {
            let row = y * w;
            for x in 0..w {
                let src = (row + x) * 4;
                let dst = (row + (w - 1 - x)) * 4;
                pixels[dst..dst + 4].copy_from_slice(&self.pixels[src..src + 4]);
            }
        }
        FrameBuffer {
            width: self.width,
            height: self.height,
            pixels,
        }
    }

    /// A copy ROTATED clockwise by `quarter_turns` (`0`=none, `1`=90°, `2`=180°, `3`=270°;
    /// any value is taken mod 4) — the per-output orientation transform. A 90°/270° turn
    /// swaps width and height. Pure integer index-remap, deterministic + byte-identical
    /// cross-OS (NFR-014). `0` returns an unchanged clone.
    pub fn rotated(&self, quarter_turns: u8) -> FrameBuffer {
        let turns = quarter_turns % 4;
        if turns == 0 {
            return self.clone();
        }
        let (sw, sh) = (self.width as usize, self.height as usize);
        let (dw, dh) = if turns == 2 { (sw, sh) } else { (sh, sw) };
        let mut pixels = vec![0u8; self.pixels.len()];
        for sy in 0..sh {
            let srow = sy * sw;
            for sx in 0..sw {
                // Destination (dx, dy) for a clockwise turn of the source pixel (sx, sy).
                let (dx, dy) = match turns {
                    1 => (sh - 1 - sy, sx),          // 90° CW
                    2 => (sw - 1 - sx, sh - 1 - sy), // 180°
                    _ => (sy, sw - 1 - sx),          // 270° CW
                };
                let s = (srow + sx) * 4;
                let d = (dy * dw + dx) * 4;
                pixels[d..d + 4].copy_from_slice(&self.pixels[s..s + 4]);
            }
        }
        FrameBuffer {
            width: dw as u32,
            height: dh as u32,
            pixels,
        }
    }

    /// Resample to exactly `dst_w × dst_h` (no aspect preservation): a generalization of
    /// [`thumbnail`](Self::thumbnail) that also UPSCALES (nearest-source for an expanded
    /// axis, box-average for a contracted one). Integer + deterministic. The building block
    /// for [`fitted`](Self::fitted). Bounds `dst_*` to `1..=MAX_DIMENSION`.
    fn resampled(&self, dst_w: u32, dst_h: u32) -> FrameBuffer {
        let dst_w = dst_w.clamp(1, MAX_DIMENSION);
        let dst_h = dst_h.clamp(1, MAX_DIMENSION);
        if dst_w == self.width && dst_h == self.height {
            return self.clone();
        }
        let (w, h) = (self.width as u64, self.height as u64);
        let (dw, dh) = (dst_w as u64, dst_h as u64);
        let mut pixels = Vec::with_capacity((dw * dh) as usize * 4);
        for ty in 0..dh {
            let sy0 = (ty * h / dh) as u32;
            let sy1 = (((ty + 1) * h / dh) as u32).max(sy0 + 1).min(self.height);
            for tx in 0..dw {
                let sx0 = (tx * w / dw) as u32;
                let sx1 = (((tx + 1) * w / dw) as u32).max(sx0 + 1).min(self.width);
                let (mut r, mut g, mut b, mut a, mut n) = (0u64, 0u64, 0u64, 0u64, 0u64);
                for sy in sy0..sy1 {
                    let row = sy as usize * self.width as usize;
                    for sx in sx0..sx1 {
                        let i = (row + sx as usize) * 4;
                        r += self.pixels[i] as u64;
                        g += self.pixels[i + 1] as u64;
                        b += self.pixels[i + 2] as u64;
                        a += self.pixels[i + 3] as u64;
                        n += 1;
                    }
                }
                let n = n.max(1);
                pixels.extend_from_slice(&[
                    (r / n) as u8,
                    (g / n) as u8,
                    (b / n) as u8,
                    (a / n) as u8,
                ]);
            }
        }
        FrameBuffer {
            width: dst_w,
            height: dst_h,
            pixels,
        }
    }

    /// Fit this frame into a `dst_w × dst_h` surface under `fit` — the per-output
    /// "scaling / fit" transform (Screens inspector). Always returns exactly `dst_w × dst_h`:
    /// [`Fit::Stretch`] distorts to fill, [`Fit::Fit`] letterboxes (black bars, no crop),
    /// [`Fit::Fill`] covers and centre-crops. Pure integer, deterministic (NFR-014).
    pub fn fitted(&self, dst_w: u32, dst_h: u32, fit: Fit) -> FrameBuffer {
        let dst_w = dst_w.clamp(1, MAX_DIMENSION);
        let dst_h = dst_h.clamp(1, MAX_DIMENSION);
        match fit {
            Fit::Stretch => self.resampled(dst_w, dst_h),
            Fit::Fit => {
                // Contain: the largest aspect-preserving size within the surface, letterboxed.
                let (w, h) = (self.width as u64, self.height as u64);
                let (dw, dh) = (dst_w as u64, dst_h as u64);
                let (sw, sh) = if w * dh <= h * dw {
                    (((w * dh) / h).max(1), dh) // height binds
                } else {
                    (dw, ((h * dw) / w).max(1)) // width binds
                };
                let scaled = self.resampled(sw as u32, sh as u32);
                let mut out = FrameBuffer::filled(dst_w, dst_h, Rgba::BLACK);
                let ox = (dst_w - scaled.width) / 2;
                let oy = (dst_h - scaled.height) / 2;
                out.blit_opaque(&scaled, ox, oy);
                out
            }
            Fit::Fill => {
                // Cover: the smallest aspect-preserving size that covers the surface, then
                // centre-crop to the surface.
                let (w, h) = (self.width as u64, self.height as u64);
                let (dw, dh) = (dst_w as u64, dst_h as u64);
                let (sw, sh) = if w * dh >= h * dw {
                    (((w * dh) / h).max(1), dh) // height binds (source relatively wider)
                } else {
                    (dw, ((h * dw) / w).max(1)) // width binds
                };
                let scaled = self.resampled(sw as u32, sh as u32);
                let ox = (scaled.width - dst_w) / 2;
                let oy = (scaled.height - dst_h) / 2;
                scaled.cropped(ox, oy, dst_w, dst_h)
            }
        }
    }

    /// Copy `src` opaquely onto `self` at `(ox, oy)`, clipped to bounds (no blending — a
    /// letterbox paste). Used by [`fitted`](Self::fitted).
    fn blit_opaque(&mut self, src: &FrameBuffer, ox: u32, oy: u32) {
        for sy in 0..src.height {
            let dy = oy + sy;
            if dy >= self.height {
                break;
            }
            for sx in 0..src.width {
                let dx = ox + sx;
                if dx >= self.width {
                    break;
                }
                let s = (sy as usize * src.width as usize + sx as usize) * 4;
                let d = (dy as usize * self.width as usize + dx as usize) * 4;
                self.pixels[d..d + 4].copy_from_slice(&src.pixels[s..s + 4]);
            }
        }
    }

    /// A `w × h` crop of this frame starting at `(x, y)`, clamped so the window stays in
    /// bounds. Used by [`fitted`](Self::fitted)'s cover mode.
    fn cropped(&self, x: u32, y: u32, w: u32, h: u32) -> FrameBuffer {
        let w = w.clamp(1, self.width);
        let h = h.clamp(1, self.height);
        let x = x.min(self.width - w);
        let y = y.min(self.height - h);
        let mut pixels = Vec::with_capacity((w * h) as usize * 4);
        for ry in 0..h {
            let row = ((y + ry) as usize * self.width as usize + x as usize) * 4;
            pixels.extend_from_slice(&self.pixels[row..row + (w as usize) * 4]);
        }
        FrameBuffer {
            width: w,
            height: h,
            pixels,
        }
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
        for px in self.pixels.as_chunks::<4>().0 {
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
        for px in self.pixels.as_chunks::<4>().0 {
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

/// Process-wide cache of the rendered **static prefix** of a scene — every layer BEFORE
/// the first [`Layer::Text`] (theme background image/gradient/fill, band, behind-text
/// elements), composited onto the base fill. Slide navigation re-renders the SAME static
/// prefix with only the text layers changing (a verse click, a follow, a lyric advance),
/// and profiling showed that prefix — dominated by re-scaling a background image at full
/// output resolution — was ~78% of every compose on the live command path. A hit replaces
/// all of that with one `FrameBuffer` clone (a memcpy), byte-identically: the cached
/// buffer is the deterministic raster of the same ops it replaces.
///
/// Storage is **global** (one `Mutex`, not per-thread) because `render` runs on whatever
/// thread reaches it — the LAN server's tokio workers, the desktop main thread, operator
/// command handlers — and a per-thread slot would multiply the bound by the thread count.
/// Bounds (no-leak), all hard by construction: total accounted residency never exceeds
/// [`PREFIX_CACHE_MAX_RESIDENT_BYTES`] (an entry is inserted only after evicting
/// least-recently-used entries until it fits, measured by the same accounting that
/// [`prefix_cache_resident_bytes`] reports); the store never holds more than
/// [`PREFIX_CACHE_MAX_ENTRIES`] entries (bounding the per-render lookup scan and the
/// per-entry bookkeeping the byte accounting does not count); and one entry's
/// framebuffer is capped at [`PREFIX_CACHE_MAX_BYTES`] (a 4K RGBA frame; larger frames
/// render uncached). The store is sized by BYTES rather than a fixed slot count because
/// the shipped product renders several distinct prefixes concurrently — the audience
/// theme, every NDI-enabled screen (composed each frame, each with its own theme/mask),
/// the stage/confidence output — and a fixed 2-slot store thrashed to a 0% hit rate the
/// moment a third prefix entered the rotation (measured: ~230 ms per compose vs ~0.5 ms
/// warm, debug, three 1080p surfaces). Under the byte budget many sub-4K prefixes
/// coexist (eight full-HD prefixes fit) while 4K frames self-limit to two; anything
/// past the budget degrades to the uncached path — it never grows.
/// An entry is re-rendered after [`PREFIX_CACHE_MAX_REUSES`] hits so a changed media file
/// behind an unchanged `MediaRef` is picked up at least as promptly as the decode cache
/// would today.
struct PrefixEntry {
    width: u32,
    height: u32,
    background: Rgba,
    prefix: Vec<Layer>,
    fb: FrameBuffer,
    hits: u32,
    /// Recency stamp for LRU replacement (monotonic per-cache clock).
    stamp: u64,
}

impl PrefixEntry {
    /// Approximate bytes this entry keeps resident (framebuffer + prefix key).
    fn resident_bytes(&self) -> usize {
        self.fb.bytes().len() + self.prefix.capacity() * std::mem::size_of::<Layer>()
    }

    /// Whether this entry is the cached raster of `frame`'s static prefix.
    fn matches(&self, frame: &Frame, prefix: &[Layer]) -> bool {
        self.width == frame.width
            && self.height == frame.height
            && self.background == frame.background
            && self.prefix.as_slice() == prefix
    }
}

/// The bounded slot store behind [`PREFIX_CACHE`].
struct PrefixSlots {
    entries: Vec<PrefixEntry>,
    clock: u64,
}

/// Byte cap for one cacheable prefix framebuffer (RGBA at 4K). Larger frames render uncached.
const PREFIX_CACHE_MAX_BYTES: usize = 3840 * 2160 * 4;
/// A cached prefix is re-rendered after this many hits (bounded staleness, see above).
const PREFIX_CACHE_MAX_REUSES: u32 = 64;

/// Per-entry allowance for the KEY an entry keeps resident alongside its framebuffer
/// (the cloned prefix `Vec<Layer>`, and the `MediaRef` paths those layers own).
/// [`PrefixEntry::resident_bytes`] charges the key against the same budget as the
/// pixels, so a budget of exactly N framebuffers holds only N-1 entries — measured:
/// a 4K one-layer entry is 33,177,736 bytes, and two of them overran a
/// `2 * PREFIX_CACHE_MAX_BYTES` budget by 272 bytes, evicting on every alternation and
/// restoring the very thrash this cache exists to prevent. The headroom makes the
/// budget mean what its name says: N FULL-SIZE ENTRIES, not N bare framebuffers.
const PREFIX_CACHE_ENTRY_KEY_HEADROOM: usize = 64 * 1024;

/// Hard global byte budget for the whole store (public for the bounded-memory test).
/// Entries are inserted only after LRU eviction makes the new accounted total fit, so
/// [`prefix_cache_resident_bytes`] can never exceed this. Sized at two FULL 4K entries
/// — the same proven ceiling as the previous 2-slot × 4K-cap design, plus the key
/// allowance above — so smaller prefixes coexist within the SAME memory bound: eight
/// full-HD surfaces (8 × 8,294,672 = 66,357,376) or two 4K ones both fit.
pub const PREFIX_CACHE_MAX_RESIDENT_BYTES: usize =
    2 * (PREFIX_CACHE_MAX_BYTES + PREFIX_CACHE_ENTRY_KEY_HEADROOM);

// The budget must admit two FULL 4K entries, not two bare framebuffers — the defect
// this headroom fixes. A compile-time premise so a future cap change cannot silently
// reintroduce the off-by-one (the run-time symptom is a 0% hit rate, not a failure).
const _: () = assert!(
    2 * (PREFIX_CACHE_MAX_BYTES + std::mem::size_of::<Layer>()) <= PREFIX_CACHE_MAX_RESIDENT_BYTES
);
/// Hard cap on resident entries (public for the bounded-memory test): bounds the
/// per-render linear lookup and the per-entry bookkeeping bytes the residency
/// accounting does not count.
pub const PREFIX_CACHE_MAX_ENTRIES: usize = 32;
/// The per-entry byte cap (public for the bounded-memory test): one 4K RGBA frame.
/// Frames larger than this render uncached.
pub const PREFIX_CACHE_BYTE_CAP: usize = PREFIX_CACHE_MAX_BYTES;

static PREFIX_CACHE: Mutex<PrefixSlots> = Mutex::new(PrefixSlots {
    entries: Vec::new(),
    clock: 0,
});

/// Lock the cache, recovering from a poisoned mutex: the cache holds only whole,
/// already-built entries (inserted by single assignment), so a panic elsewhere cannot
/// leave it half-written — and the render path must never panic over a cache (NFR-024).
fn lock_prefix_cache() -> std::sync::MutexGuard<'static, PrefixSlots> {
    PREFIX_CACHE.lock().unwrap_or_else(|e| e.into_inner())
}

/// Total bytes currently resident in the prefix cache across ALL threads (diagnostics:
/// the bounded-memory test and NFR tooling assert against this). Never exceeds
/// [`PREFIX_CACHE_MAX_RESIDENT_BYTES`]: insertion evicts least-recently-used entries
/// until this same accounting fits the budget, and over-cap frames bypass the store.
pub fn prefix_cache_resident_bytes() -> usize {
    lock_prefix_cache()
        .entries
        .iter()
        .map(PrefixEntry::resident_bytes)
        .sum()
}

/// Drop every cached prefix (diagnostics / tests / an explicit media-invalidation hook).
/// Purely an optimization reset: the next renders re-rasterize and re-populate.
pub fn prefix_cache_clear() {
    lock_prefix_cache().entries.clear();
}

/// The static prefix of `frame`: every layer before the first [`Layer::Text`] (slide
/// navigation only changes text, so this prefix repeats verbatim across composes).
fn static_prefix(frame: &Frame) -> &[Layer] {
    let split = frame
        .layers
        .iter()
        .position(|l| matches!(l, Layer::Text { .. }))
        .unwrap_or(frame.layers.len());
    &frame.layers[..split]
}

/// Test-visible HIT signal: how many cache hits the resident entry matching `frame`'s
/// static prefix has served since it was (re)inserted, or `None` when that prefix is
/// not resident at all. The byte-identity and over-cap-bypass tests assert on this so
/// a test that means to exercise a hit FAILS loudly when the cache actually missed,
/// was evicted, or was bypassed — instead of silently degenerating to comparing two
/// cold renders (which any deterministic renderer passes).
pub fn prefix_cache_hits_for(frame: &Frame) -> Option<u32> {
    let prefix = static_prefix(frame);
    lock_prefix_cache()
        .entries
        .iter()
        .find(|e| e.matches(frame, prefix))
        .map(|e| e.hits)
}

/// Rasterize one layer onto `fb` (the shared per-layer dispatch for `render`).
fn raster_layer(fb: &mut FrameBuffer, layer: &Layer) {
    match layer {
        Layer::Fill { rect, color } => fill_rect(fb, *rect, *color),
        Layer::Text {
            rect,
            text,
            px,
            color,
            align,
            font,
            style,
        } => {
            let s = style.unwrap_or_default();
            draw_text(
                fb,
                *rect,
                text,
                *px,
                *color,
                *align,
                font.as_ref(),
                s.weight,
                s.letter_spacing_px,
            );
        }
        Layer::Image {
            rect,
            source,
            opacity,
            fit,
        } => draw_image(fb, *rect, source, *opacity, *fit),
        Layer::Shape {
            rect,
            kind,
            fill,
            border,
            border_px,
            corner_px,
        } => draw_shape(fb, *rect, *kind, *fill, *border, *border_px, *corner_px),
        Layer::Gradient {
            rect,
            from,
            to,
            direction,
        } => draw_gradient(fb, *rect, *from, *to, *direction),
    }
}

/// Render a scene to an RGBA8 framebuffer — deterministic and GPU-free. Byte-identical
/// with or without a prefix-cache hit (the cache stores the raster of the same ops).
pub fn render(frame: &Frame) -> FrameBuffer {
    if frame.blackout {
        // Blackout is a deliberate, safe output state (not a fault).
        return FrameBuffer::filled(frame.width, frame.height, Rgba::BLACK);
    }
    // The static prefix: every layer before the first Text layer (slide navigation only
    // changes text, so this prefix repeats verbatim across consecutive composes).
    let (prefix, suffix) = frame.layers.split_at(static_prefix(frame).len());
    let bytes = (frame.width as usize)
        .saturating_mul(frame.height as usize)
        .saturating_mul(4);
    let render_prefix = || {
        let mut fb = FrameBuffer::filled(frame.width, frame.height, frame.background);
        for layer in prefix {
            raster_layer(&mut fb, layer);
        }
        fb
    };
    let mut fb = if bytes <= PREFIX_CACHE_MAX_BYTES {
        // Hit: clone the cached prefix framebuffer (a memcpy) under the lock.
        let hit = {
            let mut slots = lock_prefix_cache();
            slots.clock += 1;
            let now = slots.clock;
            slots
                .entries
                .iter_mut()
                .find(|e| e.hits < PREFIX_CACHE_MAX_REUSES && e.matches(frame, prefix))
                .map(|e| {
                    e.hits += 1;
                    e.stamp = now;
                    e.fb.clone()
                })
        };
        match hit {
            Some(fb) => fb,
            None => {
                // Miss: rasterize the prefix OUTSIDE the lock, then claim residency —
                // refresh the same key in place (same dimensions and key, so residency
                // is unchanged), or insert after evicting least-recently-used entries
                // until BOTH global bounds hold. Hard bound by construction: an entry
                // is pushed only once the store fits it, and one that could never fit
                // is simply not cached.
                let fb = render_prefix();
                let mut slots = lock_prefix_cache();
                slots.clock += 1;
                let entry = PrefixEntry {
                    width: frame.width,
                    height: frame.height,
                    background: frame.background,
                    prefix: prefix.to_vec(),
                    fb: fb.clone(),
                    hits: 0,
                    stamp: slots.clock,
                };
                let entry_bytes = entry.resident_bytes();
                if let Some(existing) = slots.entries.iter_mut().find(|e| e.matches(frame, prefix))
                {
                    *existing = entry;
                } else if entry_bytes <= PREFIX_CACHE_MAX_RESIDENT_BYTES {
                    let mut resident: usize =
                        slots.entries.iter().map(PrefixEntry::resident_bytes).sum();
                    while slots.entries.len() >= PREFIX_CACHE_MAX_ENTRIES
                        || resident + entry_bytes > PREFIX_CACHE_MAX_RESIDENT_BYTES
                    {
                        let Some(lru) = slots
                            .entries
                            .iter()
                            .enumerate()
                            .min_by_key(|(_, e)| e.stamp)
                            .map(|(i, _)| i)
                        else {
                            break; // the store is empty; the outer guard fits the entry
                        };
                        resident -= slots.entries[lru].resident_bytes();
                        slots.entries.swap_remove(lru);
                    }
                    slots.entries.push(entry);
                }
                // else: a prefix whose key alone outweighs the whole budget is not
                // cacheable — render it uncached every time (bounded, never grows).
                fb
            }
        }
    } else {
        // Over the byte cap: render uncached (and leave the cache alone).
        render_prefix()
    };
    for layer in suffix {
        raster_layer(&mut fb, layer);
    }
    fb
}

/// Draw a [`Layer::Gradient`](crate::scene::Layer::Gradient): a deterministic two-stop linear
/// ramp filling `rect` (clipped to the frame). The parameter `t` runs `0..=1000` along
/// `direction` (measured over the LAYER rect so it is stable regardless of clipping); each
/// pixel is `from.lerp(to, t)`, alpha-composited src-over (a translucent stop blends over what
/// is beneath). Pure integer → byte-identical cross-OS (NFR-014).
fn draw_gradient(
    fb: &mut FrameBuffer,
    rect: Rect,
    from: Rgba,
    to: Rgba,
    direction: GradientDirection,
) {
    // Clip to the buffer in i64 — the layer rect is UNVALIDATED, so every coordinate is derived
    // in i64 (mirrors `fill_rect`/`draw_shape`); no raw i32 arithmetic can overflow-panic or
    // mis-clip on an extreme rect reaching the public `render`.
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width() as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height() as i64) as u32;
    if x1 <= x0 || y1 <= y0 {
        return;
    }
    // Ramp spans measured over the LAYER rect (i64), guarded `>= 1` (a 1px rect → t=0).
    let w = (rect.w as i64).max(1);
    let h = (rect.h as i64).max(1);
    let span_v = (h - 1).max(1);
    let span_h = (w - 1).max(1);
    let span_d = (w + h - 2).max(1);
    for y in y0..y1 {
        for x in x0..x1 {
            // Position within the LAYER rect (i64, clamped), so the ramp is clip-stable.
            let lx = ((x as i64) - rect.x as i64).clamp(0, w - 1);
            let ly = ((y as i64) - rect.y as i64).clamp(0, h - 1);
            let t = match direction {
                GradientDirection::Vertical => (ly * 1000 / span_v) as u32,
                GradientDirection::Horizontal => (lx * 1000 / span_h) as u32,
                GradientDirection::DiagonalDown => ((lx + ly) * 1000 / span_d) as u32,
                GradientDirection::DiagonalUp => ((lx + (h - 1 - ly)) * 1000 / span_d) as u32,
            };
            fb.blend(x, y, from.lerp(to, t));
        }
    }
}

/// Draw a [`Layer::Image`](crate::scene::Layer::Image): resolve `source` through the
/// bounded decode cache and blit the decoded image scaled into `rect` at `opacity`; on a
/// missing / corrupt / unsupported / over-budget source, draw the missing-media
/// placeholder instead (FR-070) — never a blank rect, never a crash.
fn draw_image(fb: &mut FrameBuffer, rect: Rect, source: &MediaRef, opacity: u8, fit: ImageFit) {
    media::with_resolved(source, |resolved| match resolved {
        Some(img) => blit_image(fb, rect, img, opacity, fit),
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

/// Blit `img` into `rect` per `fit`, with **integer nearest-neighbour** sampling (a pure
/// integer function → deterministic, cross-OS byte-identical; no bilinear divergence), each
/// source pixel alpha-composited (src-over) at the whole-layer `opacity`. Clipped to the
/// on-screen intersection of `rect` and the frame, exactly like [`fill_rect`].
///
/// - **`Stretch`** (default) distorts to fill the whole rect (the historical, byte-identical path).
/// - **`Fit`** preserves aspect and letterboxes WITHIN the rect: the scaled image is centred and
///   the surrounding gap is left untouched, so the slide background shows through (not black bars —
///   this is an *element*, not a full-frame surface).
/// - **`Fill`** preserves aspect and covers the rect, centre-cropping the overflow.
fn blit_image(fb: &mut FrameBuffer, rect: Rect, img: &DecodedImage, opacity: u8, fit: ImageFit) {
    if rect.w == 0 || rect.h == 0 || img.width() == 0 || img.height() == 0 || opacity == 0 {
        return;
    }
    let x0 = rect.x.max(0) as u32;
    let y0 = rect.y.max(0) as u32;
    let x1 = ((rect.x as i64) + rect.w as i64).clamp(0, fb.width as i64) as u32;
    let y1 = ((rect.y as i64) + rect.h as i64).clamp(0, fb.height as i64) as u32;
    // All the scale math below is in i64. `iw`/`ih` are decoder-bounded to [1, MAX_DIMENSION]
    // and `rw`/`rh` to `u32`; the dominating intermediate is `ry * ih < sh * ih ≤ ih² · rw / iw`,
    // which peaks near ih = MAX_DIMENSION, iw = 1 at ~2.9e17 — ~32× under i64::MAX at the current
    // 8192 cap. If `MAX_DIMENSION` is ever raised past ~46340, this product needs i128 or a bound.
    let (iw, ih) = (img.width() as i64, img.height() as i64);
    let (rw, rh) = (rect.w as i64, rect.h as i64);
    // The scaled image size (sw × sh) and its top-left offset within the rect (ox, oy). For
    // `Fit` the image is smaller-or-equal and centred (positive offsets → a gap); for `Fill` it is
    // larger-or-equal and centred (negative offsets → crop). Aspect is preserved by fixing the
    // constrained axis to the rect and scaling the other proportionally (integer, deterministic).
    let (sw, sh, ox, oy) = match fit {
        ImageFit::Stretch => (rw, rh, 0, 0),
        ImageFit::Fit => {
            // contain: fit within → the axis where rw*ih <= rh*iw is width-constrained.
            let (sw, sh) = if rw * ih <= rh * iw {
                (rw, (ih * rw / iw).max(1))
            } else {
                ((iw * rh / ih).max(1), rh)
            };
            (sw, sh, (rw - sw) / 2, (rh - sh) / 2)
        }
        ImageFit::Fill => {
            // cover: fill beyond → the axis where rw*ih >= rh*iw is width-covering.
            let (sw, sh) = if rw * ih >= rh * iw {
                (rw, (ih * rw / iw).max(1))
            } else {
                ((iw * rh / ih).max(1), rh)
            };
            (sw, sh, (rw - sw) / 2, (rh - sh) / 2)
        }
    };
    for y in y0..y1 {
        let dy = (y as i64 - rect.y as i64).max(0); // 0..rh across the clipped span
                                                    // Position within the scaled image; skip the letterbox gap (Fit) so the bg shows.
        let ry = dy - oy;
        if ry < 0 || ry >= sh {
            continue;
        }
        let sy = ((ry * ih) / sh).clamp(0, ih - 1) as u32;
        for x in x0..x1 {
            let dx = (x as i64 - rect.x as i64).max(0);
            let rx = dx - ox;
            if rx < 0 || rx >= sw {
                continue;
            }
            let sx = ((rx * iw) / sw).clamp(0, iw - 1) as u32;
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
pub fn measure_line_width(text: &str, px: u32, font: Option<&FontName>, weight: u16) -> f32 {
    if px == 0 || text.is_empty() {
        return 0.0;
    }
    let line_h = (px as f32).max(1.0);
    let font_size = (line_h * FONT_TO_LINE).max(1.0);
    let attrs = attrs_for(font, weight);
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
    weight: u16,
    letter_spacing_px: i32,
) {
    if px == 0 || rect.w == 0 || rect.h == 0 || text.is_empty() {
        return;
    }
    // Bound the tracking so a hostile/extreme value can't invert the left-to-right glyph
    // cull (which assumes monotonically increasing pen positions) or blow up the layout;
    // ±2 line-boxes per glyph is far beyond any real typographic tracking. The bound is
    // computed in i64 and saturated to i32 so a pathological `px` (u32, straight from a
    // crafted/deserialized `Layer::Text.px`) can't overflow the multiply here — `draw_text`
    // must never panic on any input, even before the `px == 0` guard's cousins downstream.
    let bound = ((px as i64) * 2).min(i32::MAX as i64) as i32;
    let ls = letter_spacing_px.clamp(-bound, bound);
    // Faux-bold amount for the BUNDLED font (86ajq3225): its single Regular face can't
    // render a real bold, so a heavier `weight` thickens each glyph by this many px (a
    // deterministic smear). A SYSTEM font (font.is_some()) uses its real weight face instead
    // — the Attrs weight in `attrs_for` — so it is not smeared. 700→1 px, ~850+→2 px.
    let embolden: i32 = if font.is_none() && weight > 550 {
        ((weight.saturating_sub(550) / 300) as i32 + 1).min(2)
    } else {
        0
    };
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

    let attrs = attrs_for(font, weight);
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
            // Letter-spacing (86ajq3225) is applied per glyph as `i·ls` (tracking between
            // glyphs, none after the last), so the line's total added width is
            // `(glyphs−1)·ls` — fold that into the alignment so centre/right stay correct.
            let extra = (run.glyphs.len().saturating_sub(1) as i32).saturating_mul(ls);
            // Horizontal alignment: offset the whole line by its measured shaped
            // width (`line_w` + the tracking) within the rect. Clamped ≥ 0 so an over-wide
            // line still starts at the left edge (then the clip trims the overflow).
            let line_w = run.line_w + extra as f32;
            let align_x = match align {
                TextAlign::Left => 0,
                TextAlign::Center => (((rect.w as f32) - line_w) * 0.5).max(0.0) as i32,
                TextAlign::Right => ((rect.w as f32) - line_w).max(0.0) as i32,
            };
            let origin_x = rect.x.saturating_add(align_x);
            for (gi, glyph) in run.glyphs.iter().enumerate() {
                let pg = glyph.physical((0.0, 0.0), 1.0);
                let pen_x = origin_x
                    .saturating_add(pg.x)
                    .saturating_add((gi as i32).saturating_mul(ls));
                // Glyphs are laid out left-to-right: once one starts at/after the
                // clip, every later glyph does too — stop. This bounds the work
                // to the VISIBLE glyphs, not the whole line (a long/pasted line
                // must not stall the frame — the old bitmap path broke here too).
                // Only valid when pen positions are monotonic (ls ≥ 0); NEGATIVE tracking
                // moves later glyphs LEFT, so fall back to the per-glyph clip below.
                if ls >= 0 && pen_x >= clip_right {
                    break;
                }
                // A glyph spans at most ~one em; skip those wholly left of the rect.
                if pen_x + line_h as i32 + 2 < rect.x {
                    continue;
                }
                let gcolor = glyph.color_opt.unwrap_or(ink);
                cache.with_pixels(fs, pg.cache_key, gcolor, |ox, oy, c| {
                    // Fold the layer text-colour ALPHA into the glyph COVERAGE (`c.a()` is the
                    // antialiasing coverage; the glyph cache tints RGB but does not apply the
                    // ink alpha). Opaque text (`color.a == 255`) is byte-identical (·255/255,
                    // integer-exact), so every existing region render is unchanged; a
                    // TRANSLUCENT text Element (its `opacity` folded into `color.a`, 86ajq6j64)
                    // dims uniformly. Determinism preserved (pure integer, same rounding as
                    // `blend`/`scale_alpha`); the GPU skips `Layer::Text` so parity is untouched.
                    let a = ((c.a() as u32 * color.a as u32 + 127) / 255) as u8;
                    if a == 0 {
                        return;
                    }
                    // Saturating so an extreme rect origin + glyph offset can
                    // never i32-overflow-panic (the clip below discards them).
                    let x0 = pen_x.saturating_add(ox);
                    let y = base_y.saturating_add(pg.y).saturating_add(oy);
                    if y < rect.y || y >= clip_bottom {
                        return;
                    }
                    // Faux-bold (86ajq3225): the single-weight BUNDLED font has no bold face
                    // (cosmic-text/swash does not synthesise one here), so a heavier weight
                    // smears each glyph `embolden` px to the right — a deterministic integer
                    // horizontal thickening. A SYSTEM font uses its real weight face (via the
                    // Attrs weight above), so it is NOT double-emboldened.
                    for dx in 0..=embolden {
                        let x = x0.saturating_add(dx);
                        if x < rect.x || x >= clip_right {
                            continue; // clip to the layer rect + frame (protects the safe margin)
                        }
                        fb.blend(x as u32, y as u32, Rgba::new(c.r(), c.g(), c.b(), a));
                    }
                });
            }
        }
    });
}
