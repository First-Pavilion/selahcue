//! The **B5-J admission profile**: a bounded, hand-rolled JPEG marker walk that decides whether
//! a stream may be decoded at all, and hands back the frame geometry **before any pixel or
//! coefficient allocation** (ADR-0025 decision 1 steps 4–7; threat model B5-J).
//!
//! JPEG is not one format but a family, and several members produce *plausible but wrong* output
//! rather than an obvious failure. Every clause below is mandatory; a stream failing any of them
//! is dropped-and-reported like any other unsupported format — never "best-effort" decoded:
//!
//! 1. **Frame types:** SOF0 (baseline), SOF1 (extended sequential) and SOF2 (progressive) only.
//!    Lossless, hierarchical/differential and arithmetic-coded frames are refused — their
//!    patent-era rarity means a near-zero real-world corpus and therefore near-zero fuzzing
//!    attention on those decoder paths.
//! 2. **`height == 0` is refused.** That is the DNL mechanism, where the real height arrives in a
//!    marker *after* the first scan — a header cap on a deferred height is not a cap at all. A
//!    second SOF marker, and an explicit DNL marker, are refused for the same reason.
//! 3. **8-bit precision only**; 1-component grayscale or 3-component YCbCr only. 4-component
//!    CMYK/YCCK is refused as [`DecodeError::UnsupportedColour`]: correct conversion needs the
//!    embedded ICC profile, and Adobe's inverted-value convention makes photo-negative output a
//!    live possibility. An honest skip beats a wrong-coloured photograph on a congregation's
//!    screen.
//! 4. **Sampling factors restricted to {1×1, 1×2, 2×1, 2×2}** — unusual factors multiply
//!    upsampling buffers and have a history of decoder edge-case bugs.
//!
//! The walk also captures the first `Exif\0\0` APP1 payload so [`crate::exif`] can read the
//! orientation tag from it without a second scan of the file.
//!
//! Like [`crate::exif`], this module parses untrusted binary offsets and therefore denies
//! `indexing_slicing` and `arithmetic_side_effects`.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

use crate::media::DecodeError;

/// The JPEG signature used by the allowlist: SOI followed by the first marker's `0xFF`. Three
/// bytes rather than two, because a bare `FF D8` is a weaker discriminator than every real
/// encoder's `FF D8 FF`.
pub(crate) const JPEG_SIGNATURE: [u8; 3] = [0xFF, 0xD8, 0xFF];

/// How many leading bytes are searched for the EXIF APP1 segment (ADR-0025 decision 5).
const MAX_EXIF_SCAN: usize = 64 * 1024;

/// Pixel cap for a **sequential** frame (SOF0/SOF1) — matches the PNG path's budget.
pub(crate) const MAX_PIXELS_SEQUENTIAL: u64 = 40_000_000;

/// Pixel cap for a **progressive** frame (SOF2). Tighter on purpose: progressive decode holds
/// full-image coefficient planes (≈ W×H×components×2 bytes) *in addition to* the RGBA output and
/// the upsampling buffers, so the same pixel count costs materially more working set.
pub(crate) const MAX_PIXELS_PROGRESSIVE: u64 = 24_000_000;

/// What the marker walk established about a frame, before a single pixel was allocated.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct JpegProfile {
    pub width: u32,
    pub height: u32,
    /// `true` for SOF2 — the tighter [`MAX_PIXELS_PROGRESSIVE`] applies.
    pub progressive: bool,
    /// Component count: 1 (grayscale) or 3 (YCbCr). Nothing else is admitted.
    pub components: u8,
    /// EXIF orientation `1..=8`; `1` when absent or malformed.
    pub orientation: u8,
}

impl JpegProfile {
    /// The pixel cap this frame's coding process is subject to (clause 4 of B5-J).
    pub(crate) fn format_pixel_cap(&self) -> u64 {
        if self.progressive {
            MAX_PIXELS_PROGRESSIVE
        } else {
            MAX_PIXELS_SEQUENTIAL
        }
    }
}

/// Walk `bytes` and admit — or refuse — the frame, **without decoding it**.
///
/// Total and panic-free on any input: every read is bounds-checked, every offset is `checked_*`,
/// and the walk always terminates (each step consumes at least one byte).
pub(crate) fn probe(bytes: &[u8]) -> Result<JpegProfile, DecodeError> {
    if bytes.get(..2) != Some(&[0xFF, 0xD8][..]) {
        return Err(DecodeError::Unsupported);
    }
    let mut pos: usize = 2;
    let mut frame: Option<(u32, u32, bool, u8)> = None;
    let mut orientation = crate::exif::ORIENTATION_IDENTITY;
    // Whether an `Exif\0\0` APP1 payload has already been consumed. A flag, not
    // `orientation == ORIENTATION_IDENTITY`: orientation 1 is both "upright" and the fallback for
    // an absent tag, so testing it lets a LATER APP1 segment override the first one whenever the
    // first legitimately said "upright" — the opposite of the documented "first payload wins", and
    // a way for a crafted trailing segment to rotate a photograph the file itself declared
    // correct.
    let mut seen_exif = false;

    while let Some(marker) = next_marker(bytes, &mut pos)? {
        match marker {
            // End of image — stop.
            0xD9 => break,
            // Standalone markers with no payload.
            0x01 | 0xD0..=0xD7 => continue,
            // A second SOI inside the stream is malformed, not a nested image.
            0xD8 => return Err(DecodeError::Malformed),
            // DNL carries a deferred height — refused for the same reason as `height == 0`.
            0xDC => return Err(DecodeError::UnsupportedVariant),
            // Arithmetic-conditioning tables imply arithmetic coding.
            0xCC => return Err(DecodeError::UnsupportedVariant),
            // Frame headers.
            0xC0..=0xC3 | 0xC5..=0xC7 | 0xC9..=0xCB | 0xCD..=0xCF => {
                if !matches!(marker, 0xC0..=0xC2) {
                    // Lossless (C3), differential/hierarchical (C5–C7, CD–CF) and
                    // arithmetic-coded (C9–CB) frames. Refused on the marker alone, before the
                    // payload is even read, so a truncated one is still an honest "unsupported
                    // variant" rather than a generic "malformed".
                    return Err(DecodeError::UnsupportedVariant);
                }
                let payload = segment_payload(bytes, &mut pos)?;
                if frame.is_some() {
                    // A second frame header would move the goalposts after admission.
                    return Err(DecodeError::Malformed);
                }
                frame = Some(parse_sof(payload, marker == 0xC2)?);
            }
            // Start of scan: entropy-coded data follows, which `next_marker` skips.
            0xDA => {
                let _ = segment_payload(bytes, &mut pos)?;
                skip_entropy(bytes, &mut pos);
            }
            // APP1 — the EXIF carrier. First `Exif\0\0` payload wins.
            0xE1 => {
                // The scan limit is on where the segment BEGINS, not on where it ends. ADR-0025
                // bounds how far into the file we look FOR an APP1 marker; testing `pos` after
                // the segment has been consumed silently demands that the whole segment also fit
                // inside 64 KiB, which a real photograph routinely fails: an embedded EXIF
                // thumbnail pushes the segment's end past 65 536 while its marker sits at byte 2.
                // The orientation was then dropped and the photograph reached the audience screen
                // rotated ninety degrees — the exact failure this reader was added to prevent.
                let segment_start = pos;
                let payload = segment_payload(bytes, &mut pos)?;
                if !seen_exif && segment_start <= MAX_EXIF_SCAN {
                    if let Some(tiff) = payload
                        .get(..6)
                        .filter(|sig| *sig == b"Exif\0\0")
                        .and_then(|_| payload.get(6..))
                    {
                        seen_exif = true;
                        orientation = crate::exif::orientation_from_tiff(tiff);
                    }
                }
            }
            // Everything else (quantisation/Huffman tables, other APPn, comments) is
            // length-skipped, never parsed. ICC, XMP and EXIF thumbnails are inert here.
            _ => {
                let _ = segment_payload(bytes, &mut pos)?;
            }
        }
    }

    let Some((width, height, progressive, components)) = frame else {
        return Err(DecodeError::Malformed);
    };
    Ok(JpegProfile {
        width,
        height,
        progressive,
        components,
        orientation,
    })
}

/// Parse an admitted SOF payload (everything after the two length bytes).
fn parse_sof(payload: &[u8], progressive: bool) -> Result<(u32, u32, bool, u8), DecodeError> {
    let precision = *payload.first().ok_or(DecodeError::Malformed)?;
    if precision != 8 {
        // 12/16-bit precision would need a second precision path for approximately no real decks.
        return Err(DecodeError::UnsupportedVariant);
    }
    let height = be_u16(payload, 1).ok_or(DecodeError::Malformed)?;
    let width = be_u16(payload, 3).ok_or(DecodeError::Malformed)?;
    // `height == 0` is the DNL deferred-height mechanism: the real height would arrive after the
    // first scan, so a header-time cap would be meaningless. Refuse it outright.
    if height == 0 || width == 0 {
        return Err(DecodeError::Malformed);
    }
    let components = *payload.get(5).ok_or(DecodeError::Malformed)?;
    match components {
        1 | 3 => {}
        4 => return Err(DecodeError::UnsupportedColour),
        _ => return Err(DecodeError::UnsupportedVariant),
    }
    // Each component contributes id(1) + sampling(1) + quant-table(1).
    let per = usize::from(components)
        .checked_mul(3)
        .ok_or(DecodeError::Malformed)?;
    let end = 6usize.checked_add(per).ok_or(DecodeError::Malformed)?;
    let table = payload.get(6..end).ok_or(DecodeError::Malformed)?;
    for spec in table.chunks_exact(3) {
        let sampling = *spec.get(1).ok_or(DecodeError::Malformed)?;
        let h = sampling >> 4;
        let v = sampling & 0x0F;
        if !matches!((h, v), (1, 1) | (1, 2) | (2, 1) | (2, 2)) {
            return Err(DecodeError::UnsupportedVariant);
        }
    }
    Ok((u32::from(width), u32::from(height), progressive, components))
}

/// Advance `pos` to the next marker and return its type byte. `Ok(None)` = the stream ended
/// cleanly. Fill bytes (`0xFF` runs) are skipped, per the specification.
fn next_marker(bytes: &[u8], pos: &mut usize) -> Result<Option<u8>, DecodeError> {
    // Skip to the next 0xFF; anything else here is a structural break.
    match bytes.get(*pos) {
        None => return Ok(None),
        Some(0xFF) => {}
        Some(_) => return Err(DecodeError::Malformed),
    }
    // A run of 0xFF fill bytes may precede the marker.
    while bytes.get(*pos) == Some(&0xFF) {
        *pos = pos.checked_add(1).ok_or(DecodeError::Malformed)?;
    }
    match bytes.get(*pos) {
        None => Ok(None),
        Some(&m) => {
            *pos = pos.checked_add(1).ok_or(DecodeError::Malformed)?;
            Ok(Some(m))
        }
    }
}

/// Read a length-prefixed segment's payload at `pos` and advance past it.
fn segment_payload<'a>(bytes: &'a [u8], pos: &mut usize) -> Result<&'a [u8], DecodeError> {
    let len = be_u16(bytes, *pos).ok_or(DecodeError::Malformed)?;
    let len = usize::from(len);
    if len < 2 {
        return Err(DecodeError::Malformed);
    }
    let start = pos.checked_add(2).ok_or(DecodeError::Malformed)?;
    let end = pos.checked_add(len).ok_or(DecodeError::Malformed)?;
    let payload = bytes.get(start..end).ok_or(DecodeError::Malformed)?;
    *pos = end;
    Ok(payload)
}

/// Skip entropy-coded data, stopping at the next real marker. `0xFF 0x00` is a stuffed byte and
/// `0xFF 0xD0..0xD7` are restart markers — neither ends the scan.
fn skip_entropy(bytes: &[u8], pos: &mut usize) {
    while let Some(&b) = bytes.get(*pos) {
        if b != 0xFF {
            *pos = pos.saturating_add(1);
            continue;
        }
        match bytes.get(pos.saturating_add(1)) {
            // A trailing 0xFF with nothing after it: let the caller run off the end cleanly.
            None => {
                *pos = pos.saturating_add(1);
                return;
            }
            // Stuffed byte or a fill byte: still entropy data.
            Some(0x00) | Some(0xFF) => *pos = pos.saturating_add(1),
            // Restart markers punctuate the scan without ending it.
            Some(0xD0..=0xD7) => *pos = pos.saturating_add(2),
            // A real marker: leave `pos` on its 0xFF so `next_marker` reads it.
            Some(_) => return,
        }
    }
}

/// A bounds-checked big-endian `u16` read at `at`; `None` past the end.
fn be_u16(buf: &[u8], at: usize) -> Option<u16> {
    let end = at.checked_add(2)?;
    let s = buf.get(at..end)?;
    Some(u16::from_be_bytes([*s.first()?, *s.get(1)?]))
}
