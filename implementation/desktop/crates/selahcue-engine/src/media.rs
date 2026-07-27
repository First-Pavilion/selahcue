//! Bounded, deterministic, panic-contained still-image decode + a size-capped decode
//! cache for [`Layer::Image`](crate::scene::Layer::Image) (S8-6 image foundation).
//!
//! **PNG only** this batch: PNG is lossless + spec-defined, so the pure-Rust decoder
//! yields **byte-identical** RGBA8 on Windows/macOS/Linux (NFR-014) — the property the
//! deterministic CPU raster path + golden tests depend on. Other formats (JPEG/WebP/GIF/
//! BMP) are rejected here and degrade to the missing-media placeholder (FR-070), a
//! documented later-format seam.
//!
//! **Bomb-safe (FR-173):** header/type/size validation + a hard dimension AND
//! decoded-byte budget are enforced BEFORE any pixel buffer is allocated, so a crafted
//! image with huge declared dimensions cannot exhaust memory. Decode is `Result`-based
//! and never panics on malformed input, so a hostile image *contains to the placeholder*,
//! never crashes the render (the S8-6 acceptance; NFR-024).
//!
//! **Bounded (no-leak):** decoded pixels live ONLY in a thread-local cache capped by both
//! an entry count and a total-byte budget; when adding an image would exceed either bound
//! the cache is cleared (a simple bounded reset — a full LRU is NFR-013/R2). Decoded
//! pixels never enter the serde [`Frame`](crate::scene::Frame).
//!
//! Seam: decode runs IN-PROCESS now; the out-of-process sandboxed decoder worker
//! (ADR-0016) is the deferred end-state that this same reference→pixels boundary later
//! plugs into unchanged (a decoded surface arrives from the worker instead of here).

use crate::scene::{MediaRef, Rgba};
use std::cell::RefCell;
use std::collections::HashMap;
use std::io::Read;

/// The 8-byte PNG signature — a fast, cheap allowlist check that also rejects every
/// non-PNG format up front (honest: only PNG is decoded this batch).
const PNG_SIGNATURE: [u8; 8] = [0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];

/// Hard limits enforced BEFORE allocation (decompression-bomb / OOM defense, FR-173).
#[derive(Debug, Clone, Copy)]
pub struct DecodeLimits {
    /// Maximum decoded width in pixels.
    pub max_width: u32,
    /// Maximum decoded height in pixels.
    pub max_height: u32,
    /// Maximum decoded pixel count (`width * height`) — bounds `width*height*4` RGBA bytes.
    pub max_pixels: u64,
    /// Maximum ENCODED file size read from disk (bounds the read before decode).
    pub max_encoded_bytes: usize,
}

impl Default for DecodeLimits {
    fn default() -> Self {
        DecodeLimits {
            // Match the raster frame bound so an image can fill an 8K output.
            max_width: crate::raster::MAX_DIMENSION,
            max_height: crate::raster::MAX_DIMENSION,
            // 40 MP covers 8K (33 MP) with headroom → ≤ 160 MiB RGBA per image.
            max_pixels: 40_000_000,
            // A 64 MiB PNG is already far larger than any real slide image.
            max_encoded_bytes: 64 * 1024 * 1024,
        }
    }
}

/// Why a decode did not yield an image (all contain to the placeholder — never a panic).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecodeError {
    /// Empty input.
    Empty,
    /// The referenced file could not be opened (missing / unreadable).
    Missing,
    /// The encoded input exceeds [`DecodeLimits::max_encoded_bytes`].
    TooLarge,
    /// Not a PNG (the only format decoded this batch) — the later-format seam.
    Unsupported,
    /// Declared dimensions / pixel count exceed the limits (bomb defense).
    Oversize,
    /// Malformed / truncated / corrupt PNG data.
    Malformed,
}

/// A decoded image: straight (non-premultiplied) 8-bit RGBA, row-major, `width*height*4`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedImage {
    width: u32,
    height: u32,
    rgba: Vec<u8>,
}

impl DecodedImage {
    /// Wrap raw RGBA8 bytes (row-major, 4 bytes/px); `None` if the length or dimensions
    /// are inconsistent. Used by tests and by [`decode_png`].
    pub fn from_rgba(width: u32, height: u32, rgba: Vec<u8>) -> Option<Self> {
        let expected = (width as usize)
            .checked_mul(height as usize)?
            .checked_mul(4)?;
        if width > 0 && height > 0 && rgba.len() == expected {
            Some(DecodedImage {
                width,
                height,
                rgba,
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
    /// The raw RGBA8 bytes (row-major).
    pub fn rgba(&self) -> &[u8] {
        &self.rgba
    }
    /// Decoded size in bytes (the value the cache budgets against).
    pub fn byte_len(&self) -> usize {
        self.rgba.len()
    }

    /// The RGBA pixel at `(x, y)`; clamped to the image bounds (callers pass in-range
    /// coordinates from the nearest-neighbour map, but clamp defensively).
    pub(crate) fn sample(&self, x: u32, y: u32) -> Rgba {
        let x = x.min(self.width.saturating_sub(1));
        let y = y.min(self.height.saturating_sub(1));
        let i = (y as usize * self.width as usize + x as usize) * 4;
        Rgba::new(
            self.rgba[i],
            self.rgba[i + 1],
            self.rgba[i + 2],
            self.rgba[i + 3],
        )
    }
}

/// Decode PNG `bytes` to RGBA8 within `limits`. Pure + deterministic + panic-contained:
/// header/type/size validation + a dimension AND pixel-count cap BEFORE allocation, then a
/// pure-Rust decode normalised to straight 8-bit RGBA (no gamma/ICC/premultiply → the same
/// bytes on every OS). Any non-PNG / corrupt / oversize input returns `Err`, never panics.
pub fn decode_png(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    if bytes.is_empty() {
        return Err(DecodeError::Empty);
    }
    if bytes.len() > limits.max_encoded_bytes {
        return Err(DecodeError::TooLarge);
    }
    // Allowlist: only PNG is decoded this batch — reject everything else up front.
    if bytes.len() < PNG_SIGNATURE.len() || bytes[..PNG_SIGNATURE.len()] != PNG_SIGNATURE {
        return Err(DecodeError::Unsupported);
    }

    let mut decoder = png::Decoder::new(bytes);
    // Normalise to straight 8-bit and expand palette/low-bit-gray/tRNS so the output is
    // one of Grayscale / GrayscaleAlpha / Rgb / Rgba at 8 bits — deterministic, no gamma.
    decoder.set_transformations(png::Transformations::normalize_to_color8());
    decoder.set_ignore_text_chunk(true);
    // Second line of defence: cap the decoder's own working memory (bomb defense).
    decoder.set_limits(png::Limits {
        bytes: limits.max_pixels.saturating_mul(4).min(usize::MAX as u64) as usize,
    });

    let mut reader = decoder.read_info().map_err(|_| DecodeError::Malformed)?;
    // Validate declared dimensions BEFORE allocating the output buffer.
    let info = reader.info();
    let (w, h) = (info.width, info.height);
    if w == 0 || h == 0 || w > limits.max_width || h > limits.max_height {
        return Err(DecodeError::Oversize);
    }
    let pixels = (w as u64) * (h as u64);
    if pixels > limits.max_pixels {
        return Err(DecodeError::Oversize);
    }

    let mut buf = vec![0u8; reader.output_buffer_size()];
    let out = reader
        .next_frame(&mut buf)
        .map_err(|_| DecodeError::Malformed)?;
    if out.bit_depth != png::BitDepth::Eight {
        // normalize_to_color8 should guarantee 8-bit; anything else is unexpected.
        return Err(DecodeError::Unsupported);
    }
    // Clamp defensively: never slice past the buffer we allocated (no panic even if the
    // reported frame size ever disagreed with `output_buffer_size`).
    let src = &buf[..out.buffer_size().min(buf.len())];
    let channels: usize = match out.color_type {
        png::ColorType::Grayscale => 1,
        png::ColorType::GrayscaleAlpha => 2,
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        // Indexed is expanded away by EXPAND; anything else we don't map.
        png::ColorType::Indexed => return Err(DecodeError::Unsupported),
    };
    let px = (w as usize) * (h as usize);
    if src.len() < px * channels {
        return Err(DecodeError::Malformed);
    }
    let mut rgba = Vec::with_capacity(px * 4);
    for p in 0..px {
        let o = p * channels;
        let (r, g, b, a) = match channels {
            1 => (src[o], src[o], src[o], 255),
            2 => (src[o], src[o], src[o], src[o + 1]),
            3 => (src[o], src[o + 1], src[o + 2], 255),
            _ => (src[o], src[o + 1], src[o + 2], src[o + 3]),
        };
        rgba.extend_from_slice(&[r, g, b, a]);
    }
    DecodedImage::from_rgba(w, h, rgba).ok_or(DecodeError::Malformed)
}

// --- bounded decode cache -------------------------------------------------------------

/// Maximum distinct images held in the decode cache.
pub const MAX_IMAGE_CACHE_ENTRIES: usize = 64;
/// Maximum total decoded bytes held in the decode cache (256 MiB).
pub const MAX_IMAGE_CACHE_BYTES: usize = 256 * 1024 * 1024;

/// A thread-local, size-capped cache mapping a [`MediaRef`] to its decode OUTCOME. A
/// failed decode is cached as `None` so a missing/corrupt reference is not re-read from
/// disk every frame; it still resolves to the placeholder. Bounded by entry count AND a
/// total-byte budget — exceeding either clears the cache (bounded reset; full LRU = R2).
struct ImageCache {
    map: HashMap<String, Option<DecodedImage>>,
    total_bytes: usize,
    limits: DecodeLimits,
}

impl ImageCache {
    fn new() -> Self {
        ImageCache {
            map: HashMap::new(),
            total_bytes: 0,
            limits: DecodeLimits::default(),
        }
    }

    /// Resolve `source` to its decoded image, decoding (and caching the outcome) on a
    /// miss. `None` = the source failed to decode / is missing → the caller draws the
    /// placeholder.
    fn resolve(&mut self, source: &MediaRef) -> Option<&DecodedImage> {
        let key = source.as_str();
        if !self.map.contains_key(key) {
            let outcome = load_and_decode(source, &self.limits).ok();
            let incoming = outcome.as_ref().map(|d| d.byte_len()).unwrap_or(0);
            // Bound BEFORE inserting: clear if this entry would breach either cap.
            if self.map.len() + 1 > MAX_IMAGE_CACHE_ENTRIES
                || self.total_bytes.saturating_add(incoming) > MAX_IMAGE_CACHE_BYTES
            {
                self.map.clear();
                self.total_bytes = 0;
            }
            self.total_bytes = self.total_bytes.saturating_add(incoming);
            self.map.insert(key.to_string(), outcome);
        }
        self.map.get(key).and_then(|o| o.as_ref())
    }
}

/// Read the referenced file (capped) and decode it. The read is bounded to
/// `max_encoded_bytes + 1` so an enormous file cannot be slurped into memory.
fn load_and_decode(source: &MediaRef, limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    let file = std::fs::File::open(source.as_str()).map_err(|_| DecodeError::Missing)?;
    let mut buf = Vec::new();
    file.take(limits.max_encoded_bytes as u64 + 1)
        .read_to_end(&mut buf)
        .map_err(|_| DecodeError::Malformed)?;
    if buf.len() > limits.max_encoded_bytes {
        return Err(DecodeError::TooLarge);
    }
    decode_png(&buf, limits)
}

thread_local! {
    static IMAGE_CACHE: RefCell<ImageCache> = RefCell::new(ImageCache::new());
}

/// Resolve `source` through the thread-local decode cache and hand the result (borrowed
/// for the duration) to `f`. `Some` = a decoded image to blit; `None` = draw the
/// placeholder. Keeping the borrow inside `f` avoids leaking cache internals.
pub(crate) fn with_resolved<R>(source: &MediaRef, f: impl FnOnce(Option<&DecodedImage>) -> R) -> R {
    IMAGE_CACHE.with(|cell| {
        let cache = &mut *cell.borrow_mut();
        f(cache.resolve(source))
    })
}

/// Current `(entries, total_bytes)` in the decode cache — for the bounded-memory test.
pub fn image_cache_stats() -> (usize, usize) {
    IMAGE_CACHE.with(|cell| {
        let c = cell.borrow();
        (c.map.len(), c.total_bytes)
    })
}

/// Clear the decode cache (test isolation + an explicit free hook).
pub fn reset_image_cache() {
    IMAGE_CACHE.with(|cell| {
        let c = &mut *cell.borrow_mut();
        c.map.clear();
        c.total_bytes = 0;
    });
}
