//! Bounded, deterministic, panic-contained still-image decode + a size-capped decode
//! cache for [`Layer::Image`](crate::scene::Layer::Image) (S8-6 image foundation).
//!
//! **PNG and JPEG** (ADR-0018, amended by **ADR-0025**). Everything else — GIF, BMP, TIFF,
//! WMF/EMF, SVG, JPEG 2000, HEIC — is rejected at the signature allowlist and degrades to the
//! missing-media placeholder (FR-070). Format detection is by **magic bytes only**, never an
//! extension.
//!
//! **The determinism contract, restated (ADR-0025 decision 3).** ADR-0018's argument was that
//! PNG is lossless and spec-defined, so *any* conformant decoder agrees. That argument does not
//! transfer to JPEG and no crate choice can make it: the JPEG specification defines the
//! bitstream, not an exact inverse DCT, so two conformant decoders may legitimately differ by
//! ±1. What SelahCue actually needs is narrower:
//!
//! > For a **pinned decoder version**, decoding the same bytes yields byte-identical RGBA8 on
//! > every supported OS and CPU. For PNG this is guaranteed by the format; for JPEG it is a
//! > property of the pin.
//!
//! That is why `jpeg-decoder` is pinned to an exact version and built with
//! `default-features = false, features = ["platform_independent"]`: `platform_independent`
//! compiles out the SSSE3/NEON kernels *and* their runtime `is_x86_feature_detected!` dispatch,
//! so one scalar code path runs everywhere. Without it the same binary would produce different
//! pixels on an AVX2-capable machine than without — a cross-CPU divergence that reproduces on
//! only some CI runners. A version bump is therefore a golden-test-affecting change, gated like
//! the wgpu pin, and `tests/test_jpeg.rs` pins a decode hash across the CI matrix so a
//! divergence fails on the day it becomes true.
//!
//! **The B5-J admission profile** (threat model) is enforced by [`crate::jpeg::probe`] before a
//! single pixel *or coefficient* is allocated; [`crate::exif`] applies the orientation tag so
//! photographs do not import sideways.
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
//!
//! Like [`crate::jpeg`], [`crate::exif`] and the importer's ZIP and package-path readers, this
//! module denies `indexing_slicing` and `arithmetic_side_effects`. It reads untrusted input at
//! computed offsets — and since ADR-0025 it holds the largest amount of arithmetic on
//! DECODER-REPORTED values anywhere in the chain: the per-pixel channel walks and the EXIF
//! orientation map, whose indices are built from a width, a height and a component count that a
//! third-party decoder handed back. Every other module in the chain carries the pair; this one
//! carried none of it, which is the wrong way round.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

use crate::scene::{MediaRef, Rgba};
use std::cell::RefCell;
use std::collections::HashMap;
use std::io::Read;

/// The 8-byte PNG signature.
const PNG_SIGNATURE: [u8; 8] = [0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];

/// Floor for the JPEG decoder's own working-memory budget (step 8 of [`decode_image`]).
///
/// The budget is derived from the frame's pixel count, and an 8×8 thumbnail's derived figure is a
/// few hundred bytes — below the decoder's fixed overhead, which would refuse a perfectly good
/// image for being small. The floor is far under any bomb and exists only so the budget never
/// becomes an accidental minimum size.
const MIN_DECODE_BUFFER_BYTES: u64 = 1024 * 1024;

/// A still-image format this seam can decode. The allowlist is closed: adding a format means
/// adding a signature here *and* a header-validated admission profile, never a fallthrough.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ImageFormat {
    Png,
    Jpeg,
}

impl ImageFormat {
    /// The file extension to store this format under. Derived from the **sniffed** format, never
    /// from an archive entry name or a user-supplied filename.
    pub fn extension(self) -> &'static str {
        match self {
            ImageFormat::Png => "png",
            ImageFormat::Jpeg => "jpg",
        }
    }

    /// A short human name for a drop report ("PNG", "JPEG").
    pub fn label(self) -> &'static str {
        match self {
            ImageFormat::Png => "PNG",
            ImageFormat::Jpeg => "JPEG",
        }
    }
}

/// Identify `bytes` by **magic bytes only** — never by an extension, which is attacker-supplied
/// on every path that reaches here. `None` = not a format this seam decodes.
pub fn sniff(bytes: &[u8]) -> Option<ImageFormat> {
    if bytes.starts_with(&PNG_SIGNATURE) {
        return Some(ImageFormat::Png);
    }
    if bytes.starts_with(&crate::jpeg::JPEG_SIGNATURE) {
        return Some(ImageFormat::Jpeg);
    }
    None
}

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
    /// Not a format on the signature allowlist — the later-format seam.
    Unsupported,
    /// Declared dimensions / pixel count exceed the limits (bomb defense).
    Oversize,
    /// Malformed / truncated / corrupt image data.
    Malformed,
    /// A colour model this seam deliberately does not convert — today, 4-component CMYK/YCCK
    /// JPEG. Correct conversion needs the embedded ICC profile, and Adobe's inverted-value
    /// convention makes photo-negative output a live possibility; an honest skip beats a
    /// wrong-coloured photograph on a congregation's screen (ADR-0025 decision 4).
    UnsupportedColour,
    /// A structurally valid but refused variant — arithmetic-coded, lossless, hierarchical or
    /// 12/16-bit JPEG, an unusual sampling factor, or a deferred (DNL) height. Refused on risk
    /// grounds, not effort: each multiplies rarely-exercised decoder paths while contributing
    /// approximately nothing to real-deck coverage.
    UnsupportedVariant,
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
        // Transparent black rather than a panic if the index ever falls out of range: this runs
        // per pixel on the render path, where a crash is a blank audience screen (NFR-024) and a
        // missing pixel is not. `from_rgba` makes it unreachable; the fallback keeps it that way
        // if the invariant ever moves.
        let i = (y as usize)
            .checked_mul(self.width as usize)
            .and_then(|row| row.checked_add(x as usize))
            .and_then(|p| p.checked_mul(4));
        let px = i
            .and_then(|i| i.checked_add(4).and_then(|end| self.rgba.get(i..end)))
            .unwrap_or(&[0, 0, 0, 0]);
        Rgba::new(
            px.first().copied().unwrap_or(0),
            px.get(1).copied().unwrap_or(0),
            px.get(2).copied().unwrap_or(0),
            px.get(3).copied().unwrap_or(0),
        )
    }
}

/// Decode `bytes` to RGBA8 within `limits` — the **one** entry point every format passes
/// through, in one fixed order (ADR-0025 decision 1):
///
/// 1. non-empty · 2. encoded-byte cap · 3. signature allowlist · 4. **header-only read, no pixel
///    allocation** · 5. reject unsupported variants from the header · 6. dimension caps ·
/// 7. megapixel cap · 8. the decoder's own second-line buffer budget · 9. allocate and decode ·
/// 10. normalise to RGBA8 · 11. apply EXIF orientation.
///
/// Steps 4–7 are what stop a format bypassing the pre-allocation cap by learning its dimensions
/// later: both back-ends expose width, height and pixel format *before* any pixel work. Step 8
/// is the belt to step 7's braces and matters most for progressive JPEG, whose intermediate
/// coefficient planes scale with image size during decode and can exceed the output buffer.
///
/// Pure, deterministic and panic-contained: any corrupt, oversize, unsupported or hostile input
/// returns `Err`, never panics.
pub fn decode_image(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    if bytes.is_empty() {
        return Err(DecodeError::Empty);
    }
    if bytes.len() > limits.max_encoded_bytes {
        return Err(DecodeError::TooLarge);
    }
    match sniff(bytes).ok_or(DecodeError::Unsupported)? {
        ImageFormat::Png => decode_png_inner(bytes, limits),
        ImageFormat::Jpeg => decode_jpeg_inner(bytes, limits),
    }
}

/// Retained under its historical name so out-of-tree callers do not break at once. It is now a
/// thin wrapper over [`decode_image`] and therefore decodes **any** allowlisted format, not only
/// PNG — the behaviour change ADR-0025 flagged as this change's real blast radius, and the reason
/// the name had to go: a function called `decode_png` that also decodes JPEG is a trap for the
/// next reader, and the render path calling it is why decks referencing `.jpg` silently started
/// rendering instead of showing the placeholder.
#[deprecated(
    since = "0.1.0",
    note = "renamed to `decode_image`: it decodes every allowlisted format, not only PNG (ADR-0025)"
)]
pub fn decode_png(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    decode_image(bytes, limits)
}

/// What a **header-only** probe established about an image: enough to admit it under every cap
/// and to fill a media row's width/height columns, with no pixel buffer ever allocated.
///
/// The dimensions are **post-orientation**, exactly as [`decode_image`] reports them, so a
/// caller that probes and a caller that decodes agree about a rotated photograph.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ImageInfo {
    pub width: u32,
    pub height: u32,
    pub format: ImageFormat,
}

/// Validate `bytes` and yield their geometry **without decoding a single pixel** — steps 1–7 of
/// [`decode_image`]'s fixed order, stopping before step 9 allocates.
///
/// # Why this exists
///
/// The presentation importer validated every embedded image by fully decoding it and throwing the
/// pixels away, on a decoder deliberately pinned to one scalar code path for determinism, and then
/// the render path decoded the same bytes again later. Measured: over 99 % of import time, 11.0 s
/// for 150 × 16 MP images on a fast machine and around 15 s at the cap — extrapolating to 45–75 s
/// on church hardware, against a 30 s import timeout that would then keep *nothing*.
///
/// **No cap is weakened.** Every admission decision is made on header-derived dimensions, before
/// any allocation, which is the B5-J requirement — the profile walk was always header-only, and
/// the PNG side reads IHDR and stops. What is given up is exactly one thing, deliberately: an
/// image whose *payload* is corrupt but whose *header* is sound is now staged, and shows the
/// missing-media placeholder at render time instead of being reported at import time. A structural
/// header failure — a bad IHDR, a bad CRC, a refused JPEG variant, a frame past the caps — is
/// still caught here and still reported.
pub fn probe_image(bytes: &[u8], limits: &DecodeLimits) -> Result<ImageInfo, DecodeError> {
    // Steps 1–3, shared with `decode_image` so the two cannot disagree about admission.
    if bytes.is_empty() {
        return Err(DecodeError::Empty);
    }
    if bytes.len() > limits.max_encoded_bytes {
        return Err(DecodeError::TooLarge);
    }
    match sniff(bytes).ok_or(DecodeError::Unsupported)? {
        ImageFormat::Png => probe_png(bytes, limits),
        ImageFormat::Jpeg => probe_jpeg(bytes, limits),
    }
}

/// PNG steps 4–7: read the header chunk (which validates the signature, IHDR and its CRC) and
/// apply the caps. `read_info` stops at the first `IDAT` header, so no pixel buffer exists.
fn probe_png(bytes: &[u8], limits: &DecodeLimits) -> Result<ImageInfo, DecodeError> {
    let reader = png_header(bytes, limits)?;
    let info = reader.info();
    let (width, height) = (info.width, info.height);
    // PNG carries no EXIF orientation on this path and has no per-coding-process ceiling, so the
    // caller's `max_pixels` is the only cap that applies.
    admit_dimensions(width, height, limits, u64::MAX, false)?;
    Ok(ImageInfo {
        width,
        height,
        format: ImageFormat::Png,
    })
}

/// JPEG steps 4–7: the B5-J marker walk plus the caps. No `jpeg_decoder::Decoder` is constructed,
/// so not one coefficient plane is allocated.
fn probe_jpeg(bytes: &[u8], limits: &DecodeLimits) -> Result<ImageInfo, DecodeError> {
    let profile = crate::jpeg::probe(bytes)?;
    let transposes = crate::exif::transposes(profile.orientation);
    admit_dimensions(
        profile.width,
        profile.height,
        limits,
        profile.format_pixel_cap(),
        transposes,
    )?;
    // Post-orientation, matching what `decode_image` returns for the same bytes.
    let (width, height) = if transposes {
        (profile.height, profile.width)
    } else {
        (profile.width, profile.height)
    };
    Ok(ImageInfo {
        width,
        height,
        format: ImageFormat::Jpeg,
    })
}

/// Construct a PNG reader positioned after the header chunks — the one place the decoder's
/// configuration lives, so the probe and the decode cannot be configured differently.
fn png_header<'a>(
    bytes: &'a [u8],
    limits: &DecodeLimits,
) -> Result<png::Reader<&'a [u8]>, DecodeError> {
    let mut decoder = png::Decoder::new(bytes);
    // Normalise to straight 8-bit and expand palette/low-bit-gray/tRNS so the output is
    // one of Grayscale / GrayscaleAlpha / Rgb / Rgba at 8 bits — deterministic, no gamma.
    decoder.set_transformations(png::Transformations::normalize_to_color8());
    decoder.set_ignore_text_chunk(true);
    // Second line of defence: cap the decoder's own working memory (bomb defense).
    decoder.set_limits(png::Limits {
        bytes: limits.max_pixels.saturating_mul(4).min(usize::MAX as u64) as usize,
    });
    decoder.read_info().map_err(|_| DecodeError::Malformed)
}

/// Enforce the shared dimension and pixel caps on a header-declared size, **before** any buffer
/// is allocated. `format_pixel_cap` is the coding process's own ceiling (§B5-J); `transposes`
/// halves the pixel budget because an EXIF transpose needs a destination buffer alongside the
/// source.
fn admit_dimensions(
    w: u32,
    h: u32,
    limits: &DecodeLimits,
    format_pixel_cap: u64,
    transposes: bool,
) -> Result<u64, DecodeError> {
    if w == 0 || h == 0 || w > limits.max_width || h > limits.max_height {
        return Err(DecodeError::Oversize);
    }
    let mut effective = limits.max_pixels.min(format_pixel_cap);
    if transposes {
        effective = effective.saturating_div(2);
    }
    // `w` and `h` are both `u32` and both already checked non-zero and under their caps, so the
    // product cannot overflow a `u64` — stated as saturating anyway, because this is the one
    // multiplication in the file whose operands come straight out of a file header.
    let pixels = u64::from(w).saturating_mul(u64::from(h));
    if pixels > effective {
        return Err(DecodeError::Oversize);
    }
    Ok(effective)
}

fn decode_png_inner(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    // Steps 4–7 run through the SAME probe the importer uses. Sharing it is what stops the two
    // drifting: an admission decision made in two places is an admission decision made twice, and
    // the day they disagree is the day an image the importer accepted fails to render.
    let admitted = probe_png(bytes, limits)?;
    let (w, h) = (admitted.width, admitted.height);
    // A second header read, which is a chunk walk to the first `IDAT` and nothing more — the price
    // of having exactly one copy of the admission rule.
    let mut reader = png_header(bytes, limits)?;

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
    let src = buf
        .get(..out.buffer_size().min(buf.len()))
        .ok_or(DecodeError::Malformed)?;
    let channels: usize = match out.color_type {
        png::ColorType::Grayscale => 1,
        png::ColorType::GrayscaleAlpha => 2,
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        // Indexed is expanded away by EXPAND; anything else we don't map.
        png::ColorType::Indexed => return Err(DecodeError::Unsupported),
    };
    let px = (w as usize)
        .checked_mul(h as usize)
        .ok_or(DecodeError::Oversize)?;
    if src.len() < px.saturating_mul(channels) {
        return Err(DecodeError::Malformed);
    }
    let mut rgba = Vec::with_capacity(px.saturating_mul(4));
    // Chunked rather than indexed: the walk is over the decoder's own reported channel count, so
    // the slice is what bounds it, not arithmetic we have to get right per pixel.
    for chunk in src.chunks_exact(channels).take(px) {
        let c0 = chunk.first().copied().unwrap_or(0);
        let (r, g, b, a) = match channels {
            1 => (c0, c0, c0, 255),
            2 => (c0, c0, c0, chunk.get(1).copied().unwrap_or(255)),
            3 => (
                c0,
                chunk.get(1).copied().unwrap_or(0),
                chunk.get(2).copied().unwrap_or(0),
                255,
            ),
            _ => (
                c0,
                chunk.get(1).copied().unwrap_or(0),
                chunk.get(2).copied().unwrap_or(0),
                chunk.get(3).copied().unwrap_or(255),
            ),
        };
        rgba.extend_from_slice(&[r, g, b, a]);
    }
    DecodedImage::from_rgba(w, h, rgba).ok_or(DecodeError::Malformed)
}

/// JPEG decode under the B5-J admission profile.
///
/// The bounded marker walk in [`crate::jpeg::probe`] runs first and decides *everything* that
/// gates allocation — frame type, precision, component count, sampling factors, a deferred
/// (`height == 0`) height, a second SOF — and yields the geometry the caps are applied to. Only
/// once those pass is a decoder constructed, so no coefficient plane, upsampling buffer or
/// output buffer is ever allocated for a refused stream.
fn decode_jpeg_inner(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError> {
    // Steps 4–5: header-only admission, no allocation.
    let profile = crate::jpeg::probe(bytes)?;
    // Steps 6–7: dimension and pixel caps, still before allocation. The coding process picks the
    // ceiling (40 MP sequential / 24 MP progressive) and a transposing orientation halves it.
    let effective_pixels = admit_dimensions(
        profile.width,
        profile.height,
        limits,
        profile.format_pixel_cap(),
        crate::exif::transposes(profile.orientation),
    )?;

    let mut decoder = jpeg_decoder::Decoder::new(bytes);
    // Step 8: the decoder's own working-memory budget — the belt to step 7's braces.
    //
    // Sized to **this frame**, not to the cap. Using the cap makes the belt the wrong size in both
    // directions at once: for a small photograph it allows hundreds of megabytes that frame could
    // never legitimately need, so the belt guards nothing; and for a legitimate 24 Mpx progressive
    // frame — which step 7 has just admitted — it allows fewer bytes than that frame's own
    // coefficient planes require, so a valid image is refused. A budget derived from a number the
    // image had no part in is not a budget for that image.
    //
    // The multiplier covers what a progressive decode actually holds: full-image coefficient
    // planes at two bytes per component sample, plus the component output, plus slack. The floor
    // keeps a tiny frame from being handed a budget smaller than the decoder's fixed overhead.
    //
    // **This belt cannot fire while step 7's braces hold, and that is arithmetic rather than
    // luck.** For the pinned decoder the budget is compared against `components × width × height`.
    // Steps 6–7 have already admitted `width × height ≤ effective_pixels` and `components ≤ 3`,
    // and the budget below is at least `width × height × components × 4` — four times the largest
    // requirement any admitted frame can present. So no admitted frame is ever refused here, and
    // no refused frame ever reaches here. Deleting it therefore fails no test, and re-introducing
    // the cap-sized defect described above fails no test either; both were checked, and neither is
    // a hole. It is kept for the case the caps cannot cover: a decoder version whose internal
    // requirement grows relative to the frame. `tests/test_jpeg_alloc.rs` pins the property that
    // actually binds — refused frames allocate nothing, admitted ones really do decode.
    let frame_pixels = u64::from(profile.width).saturating_mul(u64::from(profile.height));
    let frame_budget = frame_pixels
        .saturating_mul(u64::from(profile.components))
        .saturating_mul(4)
        .max(MIN_DECODE_BUFFER_BYTES)
        // Never above what the admitted pixel count could justify, so the cap still dominates.
        .min(effective_pixels.saturating_mul(4).saturating_mul(4));
    decoder.set_max_decoding_buffer_size(frame_budget.min(usize::MAX as u64) as usize);

    // The seam must never let a panic escape (B5-J clause 7): a third-party parser on untrusted
    // bytes is exactly where an unforeseen index or arithmetic panic would land, and in this app
    // that would take the operator console down mid-service. Nothing observable is mutated inside
    // the closure, so asserting unwind safety is sound.
    let decoded = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
        decoder.read_info()?;
        let info = decoder.info().ok_or(jpeg_decoder::Error::Format(
            "no frame after read_info".to_string(),
        ))?;
        let pixels = decoder.decode()?;
        Ok::<_, jpeg_decoder::Error>((info, pixels))
    }))
    .map_err(|_| DecodeError::Malformed)?;
    let (info, pixels) = decoded.map_err(|e| match e {
        // The crate's own refusals map onto ours rather than collapsing into "malformed", so the
        // drop report can say *why*.
        jpeg_decoder::Error::Unsupported(_) => DecodeError::UnsupportedVariant,
        _ => DecodeError::Malformed,
    })?;

    // Any dimension change after header acceptance is malformed by definition — the caps above
    // were applied to the header's numbers, so a decoder that reports different ones has just
    // invalidated them (B5-J clause 2).
    if u32::from(info.width) != profile.width || u32::from(info.height) != profile.height {
        return Err(DecodeError::Malformed);
    }

    // Step 10: normalise to straight 8-bit RGBA. `probe` already refused everything except
    // 1-component grayscale and 3-component YCbCr, so the other two pixel formats are
    // unreachable — mapped defensively rather than assumed away.
    let (w, h) = (profile.width, profile.height);
    let px = (w as usize)
        .checked_mul(h as usize)
        .ok_or(DecodeError::Oversize)?;
    let channels = match info.pixel_format {
        jpeg_decoder::PixelFormat::L8 => 1usize,
        jpeg_decoder::PixelFormat::RGB24 => 3usize,
        jpeg_decoder::PixelFormat::CMYK32 => return Err(DecodeError::UnsupportedColour),
        jpeg_decoder::PixelFormat::L16 => return Err(DecodeError::UnsupportedVariant),
    };
    if pixels.len() < px.saturating_mul(channels) {
        return Err(DecodeError::Malformed);
    }
    let mut rgba = Vec::with_capacity(px.saturating_mul(4));
    for chunk in pixels.chunks_exact(channels).take(px) {
        let c0 = chunk.first().copied().unwrap_or(0);
        let (r, g, b) = match channels {
            1 => (c0, c0, c0),
            _ => (
                c0,
                chunk.get(1).copied().unwrap_or(0),
                chunk.get(2).copied().unwrap_or(0),
            ),
        };
        rgba.extend_from_slice(&[r, g, b, 255]);
    }
    let image = DecodedImage::from_rgba(w, h, rgba).ok_or(DecodeError::Malformed)?;
    // Step 11: EXIF orientation. Only the decoded pixels are rotated — a caller staging the
    // original file keeps the original bytes, tag included, because re-encoding would be lossy
    // and pointless.
    Ok(apply_orientation(image, profile.orientation))
}

/// Apply an EXIF orientation (`1..=8`) to decoded pixels. `1` returns the image untouched;
/// `5..=8` transpose, so the result's width and height are swapped — which is what the per-mille
/// rect and the `media_asset` row both want.
fn apply_orientation(image: DecodedImage, orientation: u8) -> DecodedImage {
    if orientation <= 1 || orientation > 8 {
        return image;
    }
    let (w, h) = (image.width as usize, image.height as usize);
    let transposed = crate::exif::transposes(orientation);
    let (out_w, out_h) = if transposed { (h, w) } else { (w, h) };
    let src = image.rgba();
    let mut out = vec![0u8; out_w.saturating_mul(out_h).saturating_mul(4)];
    // `w` and `h` are both non-zero — `from_rgba` refuses a zero dimension — so the mirrored
    // coordinates below cannot underflow. Computed once rather than per pixel, and saturating so
    // the lint's guarantee holds without an unwrap inside the loop.
    let (w_last, h_last) = (w.saturating_sub(1), h.saturating_sub(1));
    for y in 0..out_h {
        for x in 0..out_w {
            // Map each destination pixel back to its source, so every destination byte is written
            // exactly once and no rounding or gap is possible.
            let (sx, sy) = match orientation {
                2 => (w_last.saturating_sub(x), y), // mirror horizontal
                3 => (w_last.saturating_sub(x), h_last.saturating_sub(y)), // rotate 180
                4 => (x, h_last.saturating_sub(y)), // mirror vertical
                5 => (y, x),                        // transpose
                6 => (y, h_last.saturating_sub(x)), // rotate 90 clockwise
                7 => (w_last.saturating_sub(y), h_last.saturating_sub(x)), // transverse
                _ => (w_last.saturating_sub(y), x), // 8: rotate 270 clockwise
            };
            let si = sy
                .checked_mul(w)
                .and_then(|r| r.checked_add(sx))
                .and_then(|p| p.checked_mul(4));
            let di = y
                .checked_mul(out_w)
                .and_then(|r| r.checked_add(x))
                .and_then(|p| p.checked_mul(4));
            // Both indices are in range by construction; clamp rather than index blindly so a
            // future edit to the mapping table degrades to a black pixel, never a panic.
            let s = si.and_then(|i| i.checked_add(4).and_then(|e| src.get(i..e)));
            let d = di.and_then(|i| i.checked_add(4).and_then(|e| out.get_mut(i..e)));
            if let (Some(s), Some(d)) = (s, d) {
                d.copy_from_slice(s);
            }
        }
    }
    DecodedImage::from_rgba(out_w as u32, out_h as u32, out).unwrap_or(image)
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
            if self.map.len().saturating_add(1) > MAX_IMAGE_CACHE_ENTRIES
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
    file.take((limits.max_encoded_bytes as u64).saturating_add(1))
        .read_to_end(&mut buf)
        .map_err(|_| DecodeError::Malformed)?;
    if buf.len() > limits.max_encoded_bytes {
        return Err(DecodeError::TooLarge);
    }
    decode_image(&buf, limits)
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
