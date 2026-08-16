//! A **bounded, single-tag** EXIF reader: the orientation tag (`0x0112`) and nothing else
//! (ADR-0025 decision 5).
//!
//! Ignoring orientation imports phone photographs sideways, which is common, obvious and
//! embarrassing on an audience screen. Applying it inside the decoder means every consumer —
//! presentation import, the canvas image element, `deck_import_image` — gets upright pixels with
//! no schema change and no per-callsite discipline to forget.
//!
//! **Why hand-rolled rather than an EXIF crate.** We need exactly one tag out of a large,
//! untrusted, historically exploit-adjacent format. A general EXIF crate brings an entire
//! TIFF/EXIF parser — every tag type, sub-IFDs, maker notes — as new untrusted-input surface for
//! about eighty lines of value. Same judgement, and the same answer, as the hand-rolled ZIP
//! reader in ADR-0024.
//!
//! **Bounds (all mandatory).** The TIFF header must be `II*\0` or `MM\0*`; only **IFD0** is
//! walked — sub-IFD and maker-note pointers are never followed; the entry count is capped at
//! [`MAX_IFD_ENTRIES`]; every offset is bounds-checked. Anything absent, malformed or out of
//! range yields orientation `1` **silently** — a broken EXIF block is not a report entry, it is
//! simply no rotation.
//!
//! This module parses untrusted binary offsets, so it denies `indexing_slicing` and
//! `arithmetic_side_effects`: `off + len` overflow is the classic bug here, and the lint forces
//! `checked_add` / `slice::get` exactly where it would happen.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

/// The upright, no-op orientation — also the fallback for anything absent or malformed.
pub(crate) const ORIENTATION_IDENTITY: u8 = 1;

/// Maximum IFD0 entries walked before giving up (a bound, not a format rule).
const MAX_IFD_ENTRIES: u16 = 512;

/// The EXIF orientation tag.
const TAG_ORIENTATION: u16 = 0x0112;
/// TIFF type 3 = SHORT (two bytes).
const TYPE_SHORT: u16 = 3;
/// Bytes per IFD entry: tag(2) + type(2) + count(4) + value/offset(4).
const IFD_ENTRY_LEN: usize = 12;

/// Whether an orientation swaps width and height (the four transposing values).
pub(crate) fn transposes(orientation: u8) -> bool {
    matches!(orientation, 5..=8)
}

/// Read the orientation tag from a TIFF block (the APP1 payload **after** the `Exif\0\0`
/// signature, starting at the TIFF header). Returns `1..=8`; [`ORIENTATION_IDENTITY`] for
/// anything absent, malformed, or out of range.
///
/// Total and panic-free on any input, including a hostile one: every read is bounds-checked and
/// every offset is `checked_*`.
pub(crate) fn orientation_from_tiff(tiff: &[u8]) -> u8 {
    let Some(header) = tiff.get(..8) else {
        return ORIENTATION_IDENTITY;
    };
    // Byte order + the 42 magic. Anything else is not a TIFF block we will read.
    let little = match header.get(..4) {
        Some([b'I', b'I', 0x2A, 0x00]) => true,
        Some([b'M', b'M', 0x00, 0x2A]) => false,
        _ => return ORIENTATION_IDENTITY,
    };
    let Some(ifd0_off) = read_u32(header, 4, little) else {
        return ORIENTATION_IDENTITY;
    };
    let Ok(ifd0_off) = usize::try_from(ifd0_off) else {
        return ORIENTATION_IDENTITY;
    };
    // The IFD0 offset is relative to the TIFF header and bounded by the payload length.
    let Some(count) = read_u16(tiff, ifd0_off, little) else {
        return ORIENTATION_IDENTITY;
    };
    let count = count.min(MAX_IFD_ENTRIES);
    let Some(first_entry) = ifd0_off.checked_add(2) else {
        return ORIENTATION_IDENTITY;
    };

    for i in 0..count {
        let Some(step) = usize::from(i).checked_mul(IFD_ENTRY_LEN) else {
            return ORIENTATION_IDENTITY;
        };
        let Some(at) = first_entry.checked_add(step) else {
            return ORIENTATION_IDENTITY;
        };
        // A short/absent entry ends the walk — never a panic.
        let (Some(tag), Some(kind), Some(n)) = (
            read_u16(tiff, at, little),
            read_u16(tiff, at.saturating_add(2), little),
            read_u32(tiff, at.saturating_add(4), little),
        ) else {
            return ORIENTATION_IDENTITY;
        };
        if tag != TAG_ORIENTATION {
            // Never follow a sub-IFD or maker-note pointer: IFD0 only, by construction.
            continue;
        }
        if kind != TYPE_SHORT || n != 1 {
            return ORIENTATION_IDENTITY;
        }
        // A SHORT fits in the 4-byte value field, so it is stored inline (never an offset).
        let Some(value_at) = at.checked_add(8) else {
            return ORIENTATION_IDENTITY;
        };
        let Some(value) = read_u16(tiff, value_at, little) else {
            return ORIENTATION_IDENTITY;
        };
        return match value {
            1..=8 => value as u8,
            _ => ORIENTATION_IDENTITY,
        };
    }
    ORIENTATION_IDENTITY
}

/// A bounds-checked big/little-endian `u16` read at `at`; `None` past the end.
fn read_u16(buf: &[u8], at: usize, little: bool) -> Option<u16> {
    let end = at.checked_add(2)?;
    let s = buf.get(at..end)?;
    let (a, b) = (*s.first()?, *s.get(1)?);
    Some(if little {
        u16::from_le_bytes([a, b])
    } else {
        u16::from_be_bytes([a, b])
    })
}

/// A bounds-checked big/little-endian `u32` read at `at`; `None` past the end.
fn read_u32(buf: &[u8], at: usize, little: bool) -> Option<u32> {
    let end = at.checked_add(4)?;
    let s = buf.get(at..end)?;
    let (a, b, c, d) = (*s.first()?, *s.get(1)?, *s.get(2)?, *s.get(3)?);
    Some(if little {
        u32::from_le_bytes([a, b, c, d])
    } else {
        u32::from_be_bytes([a, b, c, d])
    })
}
