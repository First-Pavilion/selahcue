//! JPEG decode: the **B5-J admission profile**, EXIF orientation, and the pinned-version
//! determinism contract (ADR-0025; threat model §8.4).
//!
//! **No hostile fixture is ever committed.** Every adversarial input here is assembled from
//! bytes this file writes, so a reviewer reads the hostile shape in the diff instead of trusting
//! a filename, a malicious file never exists on disk for a scanner to flag, and a fixture cannot
//! silently rot. The builder below emits a real, decodable JPEG; each negative case is a
//! documented byte-patch of it at a fixed marker offset.

#![allow(clippy::unwrap_used)]

use selahcue_engine::{decode_image, sniff, DecodeError, DecodeLimits, ImageFormat};

// --- an in-test JPEG builder ----------------------------------------------------------

/// A built JPEG plus the offsets of the header fields the negative cases patch.
struct Jpeg {
    bytes: Vec<u8>,
    /// Index of the SOF **marker byte** (the `0xC0` of `FF C0`).
    sof: usize,
}

impl Jpeg {
    fn precision_at(&self) -> usize {
        self.sof + 3
    }
    fn height_at(&self) -> usize {
        self.sof + 4
    }
    fn width_at(&self) -> usize {
        self.sof + 6
    }
    fn ncomp_at(&self) -> usize {
        self.sof + 8
    }
    /// The sampling-factor byte of component 0 (`id, sampling, quant-table` triples follow).
    fn sampling_at(&self) -> usize {
        self.sof + 10
    }
}

/// Pack a string of `'0'`/`'1'` into bytes, padding the final byte with 1s (the JPEG
/// convention), then apply `FF 00` byte stuffing.
fn pack_bits(bits: &str) -> Vec<u8> {
    let mut raw = Vec::new();
    let (mut cur, mut n) = (0u8, 0u32);
    for c in bits.chars() {
        cur = (cur << 1) | u8::from(c == '1');
        n += 1;
        if n == 8 {
            raw.push(cur);
            cur = 0;
            n = 0;
        }
    }
    if n > 0 {
        let pad = 8 - n;
        cur = (cur << pad) | ((1u8 << pad) - 1);
        raw.push(cur);
    }
    let mut stuffed = Vec::with_capacity(raw.len());
    for b in raw {
        stuffed.push(b);
        if b == 0xFF {
            stuffed.push(0x00);
        }
    }
    stuffed
}

/// `(category, magnitude bits)` for a DC difference, per the JPEG DC coding rules.
fn dc_category(v: i32) -> (u8, String) {
    if v == 0 {
        return (0, String::new());
    }
    let (mut cat, mut t) = (0u8, v.unsigned_abs());
    while t > 0 {
        cat += 1;
        t >>= 1;
    }
    let encoded = if v > 0 { v } else { v + (1 << cat) - 1 };
    let bits = (0..cat)
        .rev()
        .map(|i| if (encoded >> i) & 1 == 1 { '1' } else { '0' })
        .collect();
    (cat, bits)
}

/// The DC Huffman code for a category: the table below gives every category a 4-bit canonical
/// code equal to its own index, which keeps the builder readable.
fn dc_code(cat: u8) -> String {
    (0..4)
        .rev()
        .map(|i| if (cat >> i) & 1 == 1 { '1' } else { '0' })
        .collect()
}

/// End-of-block: the only AC symbol the builder emits, coded `00`.
const EOB: &str = "00";

fn segment(marker: u8, payload: &[u8]) -> Vec<u8> {
    let len = (payload.len() + 2) as u16;
    let mut v = vec![0xFF, marker];
    v.extend_from_slice(&len.to_be_bytes());
    v.extend_from_slice(payload);
    v
}

/// A quantisation table where every entry is 16, so a DC difference of `d` reconstructs to a
/// flat block of `128 + 2*d`.
fn dqt() -> Vec<u8> {
    let mut p = vec![0x00];
    p.extend(std::iter::repeat_n(16u8, 64));
    segment(0xDB, &p)
}

/// DC table 0: twelve categories, each a 4-bit code equal to its index.
fn dht_dc() -> Vec<u8> {
    let mut p = vec![0x00];
    let mut bits = [0u8; 16];
    bits[3] = 12; // twelve codes of length 4
    p.extend_from_slice(&bits);
    p.extend(0u8..12u8);
    segment(0xC4, &p)
}

/// AC table 0: one code of length 2 for end-of-block.
fn dht_ac() -> Vec<u8> {
    let mut p = vec![0x10];
    let mut bits = [0u8; 16];
    bits[1] = 1;
    p.extend_from_slice(&bits);
    p.push(0x00);
    segment(0xC4, &p)
}

/// An APP1 EXIF segment carrying **only** the orientation tag, little-endian.
fn app1_exif(orientation: u16) -> Vec<u8> {
    let mut tiff = vec![b'I', b'I', 0x2A, 0x00];
    tiff.extend_from_slice(&8u32.to_le_bytes()); // IFD0 at offset 8
    tiff.extend_from_slice(&1u16.to_le_bytes()); // one entry
    tiff.extend_from_slice(&0x0112u16.to_le_bytes()); // tag: Orientation
    tiff.extend_from_slice(&3u16.to_le_bytes()); // type: SHORT
    tiff.extend_from_slice(&1u32.to_le_bytes()); // count: 1
    tiff.extend_from_slice(&orientation.to_le_bytes());
    tiff.extend_from_slice(&[0, 0]); // value field padding
    tiff.extend_from_slice(&0u32.to_le_bytes()); // no next IFD
    let mut payload = b"Exif\0\0".to_vec();
    payload.extend_from_slice(&tiff);
    segment(0xE1, &payload)
}

/// Build a decodable JPEG.
///
/// `dc_diffs` supplies one DC difference per 8×8 block in raster order (`None` = a flat block);
/// `components` is 1 (grayscale) or 3 (YCbCr, all 1×1 sampled).
fn build(
    width: u16,
    height: u16,
    components: u8,
    dc_diffs: &[i32],
    exif: Option<u16>,
    sof_marker: u8,
) -> Jpeg {
    let mut bytes = vec![0xFF, 0xD8];
    if let Some(o) = exif {
        bytes.extend(app1_exif(o));
    }
    bytes.extend(dqt());

    // SOF: precision, height, width, component count, then (id, sampling, quant table) triples.
    let mut sof = vec![8u8];
    sof.extend_from_slice(&height.to_be_bytes());
    sof.extend_from_slice(&width.to_be_bytes());
    sof.push(components);
    for c in 0..components {
        sof.extend_from_slice(&[c + 1, 0x11, 0x00]);
    }
    let sof_at = bytes.len() + 1; // index of the marker byte itself
    bytes.extend(segment(sof_marker, &sof));

    bytes.extend(dht_dc());
    bytes.extend(dht_ac());

    // SOS: every component uses DC table 0 / AC table 0.
    let mut sos = vec![components];
    for c in 0..components {
        sos.extend_from_slice(&[c + 1, 0x00]);
    }
    sos.extend_from_slice(&[0x00, 0x3F, 0x00]);
    bytes.extend(segment(0xDA, &sos));

    // One MCU per 8×8 cell (all components are 1×1 sampled), each MCU carrying one block per
    // component.
    let mcus = width.div_ceil(8) as usize * height.div_ceil(8) as usize;
    let mut stream = String::new();
    for m in 0..mcus {
        for _ in 0..components {
            let diff = dc_diffs.get(m).copied().unwrap_or(0);
            let (cat, mag) = dc_category(diff);
            stream.push_str(&dc_code(cat));
            stream.push_str(&mag);
            stream.push_str(EOB);
        }
    }
    bytes.extend(pack_bits(&stream));
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    Jpeg { bytes, sof: sof_at }
}

/// A flat 8×8 grayscale baseline JPEG — the happy path every negative case is patched from.
fn gray8() -> Jpeg {
    build(8, 8, 1, &[], None, 0xC0)
}

/// A header-only stream: valid down to the frame header, with no scan. Enough to exercise every
/// admission check, which is the point — those all run before a decoder is constructed.
fn header_only(width: u16, height: u16, sof_marker: u8) -> Vec<u8> {
    let mut bytes = vec![0xFF, 0xD8];
    bytes.extend(dqt());
    let mut sof = vec![8u8];
    sof.extend_from_slice(&height.to_be_bytes());
    sof.extend_from_slice(&width.to_be_bytes());
    sof.push(1);
    sof.extend_from_slice(&[1, 0x11, 0x00]);
    bytes.extend(segment(sof_marker, &sof));
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    bytes
}

fn be16(bytes: &mut [u8], at: usize, v: u16) {
    bytes[at..at + 2].copy_from_slice(&v.to_be_bytes());
}

// --- the seam -------------------------------------------------------------------------

#[test]
fn sniff_identifies_by_magic_bytes_and_nothing_else() {
    assert_eq!(sniff(&gray8().bytes), Some(ImageFormat::Jpeg));
    assert_eq!(
        sniff(&[0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a, 0, 0]),
        Some(ImageFormat::Png)
    );
    // Every other real pptx media format fails the allowlist and is never handed to a decoder.
    for stub in [
        &b"GIF89a"[..],
        &b"BM\x00\x00"[..],
        &b"II\x2a\x00"[..],            // TIFF
        &[0xd7, 0xcd, 0xc6, 0x9a][..], // WMF
        &[0x01, 0x00, 0x00, 0x00][..], // EMF
        &b"<svg xmlns=\"http://www.w3.org/2000/svg\">"[..],
        &[0x00, 0x00, 0x00, 0x0c, b'j', b'P', b' ', b' '][..], // JPEG 2000
    ] {
        assert_eq!(sniff(stub), None, "format stub must not be admitted");
        assert_eq!(
            decode_image(stub, &DecodeLimits::default()),
            Err(DecodeError::Unsupported)
        );
    }
    // A JPEG's own magic must not be inferred from an extension — there is no path that takes
    // one. Two bytes of SOI without a following marker is not admitted.
    assert_eq!(sniff(&[0xFF, 0xD8, 0x00]), None);
}

#[test]
fn baseline_grayscale_decodes_to_rgba() {
    let img = decode_image(&gray8().bytes, &DecodeLimits::default()).unwrap();
    assert_eq!((img.width(), img.height()), (8, 8));
    assert_eq!(img.rgba().len(), 8 * 8 * 4);
    // A flat DC-only block reconstructs to mid grey, fully opaque.
    for px in img.rgba().chunks_exact(4) {
        assert_eq!(px[0], px[1], "grayscale expands to equal channels");
        assert_eq!(px[1], px[2]);
        assert_eq!(px[3], 255, "opaque alpha");
    }
}

#[test]
fn baseline_ycbcr_and_extended_sequential_decode() {
    let ycbcr = build(8, 8, 3, &[], None, 0xC0);
    let img = decode_image(&ycbcr.bytes, &DecodeLimits::default()).unwrap();
    assert_eq!((img.width(), img.height()), (8, 8));
    // SOF1 (extended sequential) is the same coding with a different marker.
    let sof1 = build(8, 8, 1, &[], None, 0xC1);
    assert!(decode_image(&sof1.bytes, &DecodeLimits::default()).is_ok());
}

#[test]
#[allow(deprecated)]
fn decode_png_is_now_a_thin_wrapper_over_decode_image() {
    // DELIBERATE BEHAVIOUR CHANGE (ADR-0025 decision 3): `decode_png` is retained under its
    // historical name so callers do not churn, but it now routes through the format-agnostic
    // seam. A JPEG reaching it decodes instead of being rejected as `Unsupported`.
    let jpeg = gray8();
    assert_eq!(
        selahcue_engine::decode_png(&jpeg.bytes, &DecodeLimits::default()),
        decode_image(&jpeg.bytes, &DecodeLimits::default())
    );
}

// --- B5-J: the refused variants -------------------------------------------------------

#[test]
fn oversized_dimensions_are_refused_at_the_header() {
    let mut j = gray8();
    let (h_at, w_at) = (j.height_at(), j.width_at());
    be16(&mut j.bytes, h_at, 65_500);
    be16(&mut j.bytes, w_at, 65_500);
    assert_eq!(
        decode_image(&j.bytes, &DecodeLimits::default()),
        Err(DecodeError::Oversize)
    );
}

#[test]
fn zero_height_dnl_deferred_size_is_refused() {
    // `height == 0` means the real height arrives in a DNL marker AFTER the first scan, so a
    // header-time cap would be meaningless. Refused outright.
    let mut j = gray8();
    let h_at = j.height_at();
    be16(&mut j.bytes, h_at, 0);
    assert_eq!(
        decode_image(&j.bytes, &DecodeLimits::default()),
        Err(DecodeError::Malformed)
    );
    // ... and an explicit DNL marker is refused too, even with a non-zero SOF height.
    let mut with_dnl = gray8().bytes;
    let eoi = with_dnl.len() - 2;
    with_dnl.splice(eoi..eoi, [0xFF, 0xDC, 0x00, 0x04, 0x00, 0x08]);
    assert_eq!(
        decode_image(&with_dnl, &DecodeLimits::default()),
        Err(DecodeError::UnsupportedVariant)
    );
}

#[test]
fn a_second_frame_header_is_refused() {
    let j = gray8();
    let mut bytes = j.bytes.clone();
    // Append a whole second frame header before EOI: admission decided on the first frame's
    // numbers must not be reopened by a second.
    let second = header_only(8, 8, 0xC0);
    let eoi = bytes.len() - 2;
    bytes.splice(eoi..eoi, second[2..second.len() - 2].to_vec());
    assert_eq!(
        decode_image(&bytes, &DecodeLimits::default()),
        Err(DecodeError::Malformed)
    );
}

#[test]
fn arithmetic_lossless_and_hierarchical_frames_are_refused() {
    for (marker, what) in [
        (0xC9u8, "arithmetic baseline"),
        (0xCAu8, "arithmetic extended"),
        (0xCBu8, "arithmetic progressive"),
        (0xC3u8, "lossless"),
        (0xC5u8, "differential sequential"),
        (0xC7u8, "differential lossless"),
        (0xCDu8, "differential arithmetic sequential"),
    ] {
        let mut j = gray8();
        let at = j.sof;
        j.bytes[at] = marker;
        assert_eq!(
            decode_image(&j.bytes, &DecodeLimits::default()),
            Err(DecodeError::UnsupportedVariant),
            "{what} must be refused"
        );
    }
    // Arithmetic conditioning tables imply arithmetic coding even without an arithmetic SOF.
    let mut with_dac = gray8().bytes;
    with_dac.splice(2..2, [0xFF, 0xCC, 0x00, 0x03, 0x00]);
    assert_eq!(
        decode_image(&with_dac, &DecodeLimits::default()),
        Err(DecodeError::UnsupportedVariant)
    );
}

#[test]
fn twelve_bit_precision_is_refused() {
    let mut j = gray8();
    let at = j.precision_at();
    j.bytes[at] = 12;
    assert_eq!(
        decode_image(&j.bytes, &DecodeLimits::default()),
        Err(DecodeError::UnsupportedVariant)
    );
    j.bytes[at] = 16;
    assert_eq!(
        decode_image(&j.bytes, &DecodeLimits::default()),
        Err(DecodeError::UnsupportedVariant)
    );
}

#[test]
fn cmyk_four_component_frames_are_dropped_as_a_colour_problem() {
    // Four components with an Adobe APP14 transform marker: the print-oriented case. It is
    // reported as a COLOUR refusal, not a generic "unsupported", so the drop report can offer
    // the recovery ("re-save the image as RGB") rather than a shrug.
    let mut j = build(8, 8, 3, &[], None, 0xC0);
    let at = j.ncomp_at();
    j.bytes[at] = 4;
    // Extend the SOF length and append a fourth component spec so the header stays self-consistent.
    let len_at = j.sof + 1;
    let len = u16::from_be_bytes([j.bytes[len_at], j.bytes[len_at + 1]]) + 3;
    be16(&mut j.bytes, len_at, len);
    let insert_at = j.sof + 9 + 9;
    j.bytes.splice(insert_at..insert_at, [4u8, 0x11, 0x00]);
    assert_eq!(
        decode_image(&j.bytes, &DecodeLimits::default()),
        Err(DecodeError::UnsupportedColour)
    );
}

#[test]
fn unusual_sampling_factors_are_refused() {
    for sampling in [0x44u8, 0x41, 0x14, 0x33, 0x00] {
        let mut j = gray8();
        let at = j.sampling_at();
        j.bytes[at] = sampling;
        assert_eq!(
            decode_image(&j.bytes, &DecodeLimits::default()),
            Err(DecodeError::UnsupportedVariant),
            "sampling {sampling:#04x} must be refused"
        );
    }
    // The four admitted factors still decode.
    for sampling in [0x11u8, 0x12, 0x21, 0x22] {
        let mut j = gray8();
        let at = j.sampling_at();
        j.bytes[at] = sampling;
        assert!(
            !matches!(
                decode_image(&j.bytes, &DecodeLimits::default()),
                Err(DecodeError::UnsupportedVariant)
            ),
            "sampling {sampling:#04x} must be admitted by the profile"
        );
    }
}

#[test]
fn progressive_frames_get_the_tighter_pixel_cap() {
    let limits = DecodeLimits::default();
    // 6000x5000 = 30 MP: inside the 40 MP sequential cap, outside the 24 MP progressive one.
    // Progressive decode holds full-image coefficient planes on top of the output buffer, which
    // is exactly what the tighter cap is budgeting for.
    let progressive = header_only(6000, 5000, 0xC2);
    assert_eq!(
        decode_image(&progressive, &limits),
        Err(DecodeError::Oversize),
        "30 MP progressive must be refused before any coefficient plane is allocated"
    );
    // The same geometry as a sequential frame passes the caps and fails later, on the absent
    // scan data — proving the refusal above was the cap and not the missing entropy.
    let sequential = header_only(6000, 5000, 0xC0);
    assert_eq!(
        decode_image(&sequential, &limits),
        Err(DecodeError::Malformed)
    );
}

#[test]
fn the_pixel_cap_is_exact_at_the_boundary() {
    // Small caps make the boundary cheap to test; the mechanism is identical at 40 MP.
    let limits = DecodeLimits {
        max_pixels: 64,
        ..DecodeLimits::default()
    };
    assert!(
        decode_image(&gray8().bytes, &limits).is_ok(),
        "64 px is at the cap"
    );
    let one_over = build(9, 8, 1, &[], None, 0xC0); // 72 px
    assert_eq!(
        decode_image(&one_over.bytes, &limits),
        Err(DecodeError::Oversize)
    );
}

#[test]
fn truncated_entropy_data_never_yields_a_partial_image() {
    // Some decoders return what they got. A photograph correct on top and grey on the bottom is
    // worse on an audience screen than a placeholder, so a truncated stream is a typed error.
    let full = build(64, 64, 3, &[], None, 0xC0).bytes;
    for cut in [full.len() - 4, full.len() / 2, full.len() / 4] {
        let truncated = &full[..cut];
        assert!(
            decode_image(truncated, &DecodeLimits::default()).is_err(),
            "a stream truncated at {cut} must not decode to a partial image"
        );
    }
}

#[test]
fn the_encoded_byte_cap_precedes_every_parse() {
    let j = gray8();
    let limits = DecodeLimits {
        max_encoded_bytes: j.bytes.len() - 1,
        ..DecodeLimits::default()
    };
    assert_eq!(decode_image(&j.bytes, &limits), Err(DecodeError::TooLarge));
}

// --- EXIF orientation -----------------------------------------------------------------

#[test]
fn exif_orientation_is_applied_and_transposing_values_swap_the_dimensions() {
    // Two horizontally-adjacent blocks with different DC values, so a rotation is observable in
    // the pixels and not only in the dimensions.
    let upright = decode_image(
        &build(16, 8, 1, &[4, -8], None, 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!((upright.width(), upright.height()), (16, 8));
    let left = upright.rgba()[0];
    let right = upright.rgba()[(15 * 4) as usize];
    assert_ne!(
        left, right,
        "the two blocks must differ for this test to mean anything"
    );

    // Orientation 1 is a no-op.
    let one = decode_image(
        &build(16, 8, 1, &[4, -8], Some(1), 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!(one, upright);

    // 6 = rotate 90° clockwise: dimensions swap and the left-hand block becomes the top.
    let six = decode_image(
        &build(16, 8, 1, &[4, -8], Some(6), 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!(
        (six.width(), six.height()),
        (8, 16),
        "5..=8 swap width and height"
    );
    assert_eq!(
        six.rgba()[0],
        left,
        "top row comes from the left-hand block"
    );
    let bottom_left = (15 * 8) * 4;
    assert_eq!(six.rgba()[bottom_left], right);

    // 2 = mirror horizontally: dimensions unchanged, the two ends exchange.
    let two = decode_image(
        &build(16, 8, 1, &[4, -8], Some(2), 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!((two.width(), two.height()), (16, 8));
    assert_eq!(two.rgba()[0], right);

    // 3 = rotate 180.
    let three = decode_image(
        &build(16, 8, 1, &[4, -8], Some(3), 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!(three.rgba()[0], right);

    // Every value 1..=8 must produce a well-formed image and never a panic.
    for o in 1..=8u16 {
        let img = decode_image(
            &build(16, 8, 1, &[4, -8], Some(o), 0xC0).bytes,
            &DecodeLimits::default(),
        )
        .unwrap();
        let expected = if (5..=8).contains(&o) {
            (8, 16)
        } else {
            (16, 8)
        };
        assert_eq!((img.width(), img.height()), expected, "orientation {o}");
        assert_eq!(img.rgba().len(), 16 * 8 * 4);
    }
}

/// An APP1 EXIF segment padded out to `payload_len` bytes with a filler block standing in for the
/// embedded thumbnail every phone camera writes.
///
/// The orientation tag still sits in IFD0 at the front; everything after the IFD is inert bytes a
/// correct reader never looks at. What varies is only where the SEGMENT ENDS.
fn app1_exif_padded(orientation: u16, payload_len: usize) -> Vec<u8> {
    let mut tiff = vec![b'I', b'I', 0x2A, 0x00];
    tiff.extend_from_slice(&8u32.to_le_bytes());
    tiff.extend_from_slice(&1u16.to_le_bytes());
    tiff.extend_from_slice(&0x0112u16.to_le_bytes());
    tiff.extend_from_slice(&3u16.to_le_bytes());
    tiff.extend_from_slice(&1u32.to_le_bytes());
    tiff.extend_from_slice(&orientation.to_le_bytes());
    tiff.extend_from_slice(&[0, 0]);
    tiff.extend_from_slice(&0u32.to_le_bytes());
    let mut payload = b"Exif\0\0".to_vec();
    payload.extend_from_slice(&tiff);
    payload.resize(payload_len, 0x5A);
    segment(0xE1, &payload)
}

#[test]
fn a_large_exif_thumbnail_does_not_cost_the_photograph_its_orientation() {
    // The scan limit is on how far into the file we look FOR an APP1 marker — not on where the
    // segment it finds happens to END. Testing the position AFTER the segment has been consumed
    // silently demands the whole segment fit inside 64 KiB too, and a real photograph routinely
    // fails that: an embedded EXIF thumbnail pushes the segment's end past 65 536 while its marker
    // sits at byte 2. The orientation was then dropped in silence and the photograph reached the
    // audience screen rotated ninety degrees — the exact failure the EXIF reader exists to prevent.
    //
    // 65 533 is the largest payload a `u16`-length segment can carry, so this segment begins at
    // byte 2 and ends at 65 539: three bytes past the limit, and entirely legal.
    let big_thumbnail = app1_exif_padded(6, 65_533);
    let mut bytes = vec![0xFF, 0xD8];
    bytes.extend(big_thumbnail);
    let rest = build(16, 8, 1, &[4, -8], None, 0xC0).bytes;
    bytes.extend_from_slice(&rest[2..]);

    let img = decode_image(&bytes, &DecodeLimits::default()).expect("a decodable photograph");
    assert_eq!(
        (img.width(), img.height()),
        (8, 16),
        "orientation 6 must still be applied when the APP1 segment ENDS past the scan limit — its \
         marker is at byte 2"
    );

    // And the limit still does its job: an APP1 segment that BEGINS past 64 KiB is ignored, so the
    // reader's work stays bounded however large the file is.
    let mut late = vec![0xFF, 0xD8];
    // Pad with whole comment segments until the next marker starts beyond the scan window.
    while late.len() <= 64 * 1024 {
        late.extend(segment(0xFE, &[0x20; 60_000]));
    }
    late.extend(app1_exif_padded(6, 64));
    late.extend_from_slice(&rest[2..]);
    let img = decode_image(&late, &DecodeLimits::default()).expect("a decodable photograph");
    assert_eq!(
        (img.width(), img.height()),
        (16, 8),
        "an APP1 segment beginning past the scan limit is not read"
    );
}

#[test]
fn the_first_exif_payload_wins_even_when_it_says_upright() {
    // "First `Exif\0\0` payload wins" was the documented rule and not what the code did: the guard
    // was `orientation == 1`, and 1 is both "upright" and the fallback for an absent tag. So a
    // second APP1 segment silently overrode the first whenever the first legitimately said
    // upright — letting a crafted trailing segment rotate a photograph the file itself declared
    // correct.
    let rest = build(16, 8, 1, &[4, -8], None, 0xC0).bytes;
    let mut bytes = vec![0xFF, 0xD8];
    bytes.extend(app1_exif(1)); // first: upright
    bytes.extend(app1_exif(6)); // second: rotate 90°, and it must NOT win
    bytes.extend_from_slice(&rest[2..]);

    let img = decode_image(&bytes, &DecodeLimits::default()).unwrap();
    assert_eq!(
        (img.width(), img.height()),
        (16, 8),
        "the first EXIF payload wins; a later one must not override it"
    );

    // The converse, so this is not just "the second is always ignored": first says rotate, and the
    // first is what applies.
    let mut bytes = vec![0xFF, 0xD8];
    bytes.extend(app1_exif(6));
    bytes.extend(app1_exif(1));
    bytes.extend_from_slice(&rest[2..]);
    let img = decode_image(&bytes, &DecodeLimits::default()).unwrap();
    assert_eq!((img.width(), img.height()), (8, 16));
}

#[test]
fn a_broken_exif_block_is_silently_no_rotation() {
    // A broken EXIF block is not a report entry — it is simply no rotation. Out-of-range values,
    // a wrong TIFF magic, and a truncated payload all fall back to upright.
    let upright = decode_image(&gray8().bytes, &DecodeLimits::default()).unwrap();
    for o in [0u16, 9, 255, 65535] {
        let img = decode_image(
            &build(8, 8, 1, &[], Some(o), 0xC0).bytes,
            &DecodeLimits::default(),
        )
        .unwrap();
        assert_eq!(img, upright, "orientation {o} is out of range → identity");
    }
    // Corrupt the TIFF byte-order mark inside the APP1 payload.
    let mut broken = build(8, 8, 1, &[], Some(6), 0xC0).bytes;
    let tiff = broken
        .windows(6)
        .position(|w| w == b"Exif\0\0")
        .expect("EXIF signature present")
        + 6;
    broken[tiff] = b'X';
    assert_eq!(
        decode_image(&broken, &DecodeLimits::default()).unwrap(),
        upright
    );
}

#[test]
fn a_transposing_orientation_halves_the_pixel_budget() {
    // Values 5..=8 need a destination buffer alongside the source, so the effective cap halves.
    let limits = DecodeLimits {
        max_pixels: 64,
        ..DecodeLimits::default()
    };
    assert!(decode_image(&build(8, 8, 1, &[], Some(1), 0xC0).bytes, &limits).is_ok());
    assert_eq!(
        decode_image(&build(8, 8, 1, &[], Some(6), 0xC0).bytes, &limits),
        Err(DecodeError::Oversize),
        "64 px is at the cap upright, but over it when transposing"
    );
}

// --- the determinism contract ---------------------------------------------------------

/// FNV-1a over the decoded RGBA. A pinned hash, not a cryptographic one — its job is to fail
/// loudly the day two platforms stop agreeing.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h = 0xcbf2_9ce4_8422_2325u64;
    for b in bytes {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

#[test]
fn jpeg_decode_is_byte_identical_across_the_ci_matrix() {
    // THE DETERMINISM CONTRACT (ADR-0025 decision 3). The JPEG spec permits IDCT
    // implementations within a tolerance, so byte-identical output is a property of the PINNED
    // decoder version, not of the format. This test is what makes that a fact rather than a
    // claim: it runs on every OS and CPU in the CI matrix, so an x86-64/aarch64 divergence
    // fails on the day it becomes true rather than months later in a golden diff.
    //
    // If this fails after a `jpeg-decoder` bump, that bump is a golden-test-affecting change
    // (gated like the wgpu pin) — re-run this battery deliberately, do not re-pin the hash to
    // make it green.
    let img = decode_image(
        &build(16, 16, 3, &[7, -3, 11, -9], None, 0xC0).bytes,
        &DecodeLimits::default(),
    )
    .unwrap();
    assert_eq!((img.width(), img.height()), (16, 16));
    assert_eq!(
        fnv1a(img.rgba()),
        0xbd1c_0166_518d_5525,
        "pinned RGBA hash for jpeg-decoder 0.3.2 with platform_independent"
    );
}

#[test]
fn the_same_bytes_decode_identically_every_time() {
    let j = build(24, 16, 3, &[3, -5, 9], None, 0xC0);
    let a = decode_image(&j.bytes, &DecodeLimits::default()).unwrap();
    let b = decode_image(&j.bytes, &DecodeLimits::default()).unwrap();
    assert_eq!(a, b);
}

// --- panic containment ----------------------------------------------------------------

#[test]
fn every_mutation_of_a_valid_jpeg_yields_a_typed_result_never_a_panic() {
    // A deterministic mini-fuzz: walk a valid stream and corrupt one byte at a time, plus a
    // fixed-seed random battery. Every input must produce `Ok` or a typed error — never a
    // panic, which in the operator process would take the console down mid-service.
    let base = build(24, 16, 3, &[3, -5, 9], None, 0xC0).bytes;
    let limits = DecodeLimits::default();

    for i in 0..base.len() {
        for delta in [0x01u8, 0x7F, 0xFF] {
            let mut m = base.clone();
            m[i] ^= delta;
            let r = std::panic::catch_unwind(|| decode_image(&m, &limits));
            assert!(r.is_ok(), "panic on byte {i} xor {delta:#04x}");
        }
    }
    for cut in 0..base.len() {
        let m = base[..cut].to_vec();
        let r = std::panic::catch_unwind(|| decode_image(&m, &limits));
        assert!(r.is_ok(), "panic on truncation at {cut}");
    }

    // Fixed-seed random inputs that still pass the signature allowlist, so the marker walk and
    // the decoder both see them.
    let mut seed = 0x2026_0815_u64;
    let mut next = move || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed
    };
    for _ in 0..2000 {
        let len = (next() % 512) as usize + 3;
        let mut buf = vec![0xFF, 0xD8, 0xFF];
        while buf.len() < len {
            buf.extend_from_slice(&next().to_le_bytes());
        }
        buf.truncate(len);
        let r = std::panic::catch_unwind(|| decode_image(&buf, &limits));
        assert!(r.is_ok(), "panic on random input {buf:?}");
    }
}
