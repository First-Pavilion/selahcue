//! `probe_image`: the header-only admission path the presentation importer validates through.
//!
//! The importer used to validate every embedded image by fully decoding it and discarding the
//! pixels — over 99 % of import time, on a decoder deliberately pinned to a single scalar code
//! path, only for the render path to decode the same bytes again later. `probe_image` runs steps
//! 1–7 of the decode contract and stops before step 9 allocates.
//!
//! **The property that makes this safe is not "it is faster".** It is that the probe and the
//! decode make the SAME admission decision, on the SAME header-derived numbers, before any
//! allocation. So every case here is asserted against `decode_image` rather than against a
//! hard-coded expectation: a probe that admitted something the decoder refuses would be a hole in
//! the caps, and a probe that refused something the decoder accepts would silently drop real
//! images out of real decks.

#![allow(clippy::unwrap_used)]

use selahcue_engine::{decode_image, probe_image, DecodeError, DecodeLimits, ImageFormat};

// --- fixtures, assembled in-test; nothing hostile is ever committed --------------------

fn png(w: u32, h: u32) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut enc = png::Encoder::new(&mut out, w, h);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(png::BitDepth::Eight);
        let mut writer = enc.write_header().unwrap();
        let data: Vec<u8> = (0..(w * h))
            .flat_map(|i| [(i % 251) as u8, 0x40, 0x80, 0xFF])
            .collect();
        writer.write_image_data(&data).unwrap();
    }
    out
}

fn segment(marker: u8, payload: &[u8]) -> Vec<u8> {
    let len = (payload.len() + 2) as u16;
    let mut v = vec![0xFF, marker];
    v.extend_from_slice(&len.to_be_bytes());
    v.extend_from_slice(payload);
    v
}

/// A minimal but genuinely decodable baseline JPEG: `w`×`h` grayscale, flat blocks, optionally
/// carrying an EXIF orientation tag. Same construction as the importer's own fixture builder.
fn jpeg(w: u16, h: u16, orientation: Option<u16>) -> Vec<u8> {
    let mut bytes = vec![0xFF, 0xD8];
    if let Some(o) = orientation {
        let mut tiff = vec![b'I', b'I', 0x2A, 0x00];
        tiff.extend_from_slice(&8u32.to_le_bytes());
        tiff.extend_from_slice(&1u16.to_le_bytes());
        tiff.extend_from_slice(&0x0112u16.to_le_bytes());
        tiff.extend_from_slice(&3u16.to_le_bytes());
        tiff.extend_from_slice(&1u32.to_le_bytes());
        tiff.extend_from_slice(&o.to_le_bytes());
        tiff.extend_from_slice(&[0, 0]);
        tiff.extend_from_slice(&0u32.to_le_bytes());
        let mut payload = b"Exif\0\0".to_vec();
        payload.extend_from_slice(&tiff);
        bytes.extend(segment(0xE1, &payload));
    }
    let mut dqt = vec![0x00];
    dqt.extend(std::iter::repeat_n(16u8, 64));
    bytes.extend(segment(0xDB, &dqt));
    let mut sof = vec![8u8];
    sof.extend_from_slice(&h.to_be_bytes());
    sof.extend_from_slice(&w.to_be_bytes());
    sof.extend_from_slice(&[1, 1, 0x11, 0x00]);
    bytes.extend(segment(0xC0, &sof));
    let mut dc = vec![0x00];
    let mut bits = [0u8; 16];
    bits[3] = 12;
    dc.extend_from_slice(&bits);
    dc.extend(0u8..12u8);
    bytes.extend(segment(0xC4, &dc));
    let mut ac = vec![0x10];
    let mut bits = [0u8; 16];
    bits[1] = 1;
    ac.extend_from_slice(&bits);
    ac.push(0x00);
    bytes.extend(segment(0xC4, &ac));
    bytes.extend(segment(0xDA, &[1, 1, 0x00, 0x00, 0x3F, 0x00]));
    let mcus = (w.div_ceil(8) as usize) * (h.div_ceil(8) as usize);
    let mut stream = String::new();
    for _ in 0..mcus {
        stream.push_str("0000");
        stream.push_str("00");
    }
    while !stream.len().is_multiple_of(8) {
        stream.push('1');
    }
    for chunk in stream.as_bytes().chunks(8) {
        let mut byte = 0u8;
        for (i, c) in chunk.iter().enumerate() {
            if *c == b'1' {
                byte |= 1 << (7 - i);
            }
        }
        bytes.push(byte);
        if byte == 0xFF {
            bytes.push(0x00);
        }
    }
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    bytes
}

/// A frame header with no scan data: everything the admission profile reads, and nothing more.
fn jpeg_header_only(width: u16, height: u16, sof_marker: u8) -> Vec<u8> {
    let mut bytes = vec![0xFF, 0xD8];
    let mut dqt = vec![0xFF, 0xDB, 0x00, 0x43, 0x00];
    dqt.extend(std::iter::repeat_n(16u8, 64));
    bytes.extend(dqt);
    bytes.extend_from_slice(&[0xFF, sof_marker, 0x00, 0x0B, 8]);
    bytes.extend_from_slice(&height.to_be_bytes());
    bytes.extend_from_slice(&width.to_be_bytes());
    bytes.extend_from_slice(&[1, 1, 0x11, 0x00]);
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    bytes
}

// --- the probe and the decode make the same decision ----------------------------------

#[test]
fn a_probe_reports_exactly_the_dimensions_a_decode_would() {
    let limits = DecodeLimits::default();
    for (label, bytes, format) in [
        ("png 4x4", png(4, 4), ImageFormat::Png),
        ("png 200x37", png(200, 37), ImageFormat::Png),
        ("jpeg 16x8", jpeg(16, 8, None), ImageFormat::Jpeg),
        ("jpeg 16x8 upright", jpeg(16, 8, Some(1)), ImageFormat::Jpeg),
        // A transposing orientation swaps the reported dimensions. If the probe reported the
        // header's numbers instead, a rotated phone photograph would be staged with its width and
        // height the wrong way round and land on the audience screen letterboxed sideways.
        ("jpeg 16x8 rot90", jpeg(16, 8, Some(6)), ImageFormat::Jpeg),
        ("jpeg 16x8 rot270", jpeg(16, 8, Some(8)), ImageFormat::Jpeg),
        (
            "jpeg 16x8 mirrored",
            jpeg(16, 8, Some(2)),
            ImageFormat::Jpeg,
        ),
    ] {
        let probed = probe_image(&bytes, &limits).unwrap_or_else(|e| panic!("{label}: {e:?}"));
        let decoded = decode_image(&bytes, &limits).unwrap_or_else(|e| panic!("{label}: {e:?}"));
        assert_eq!(probed.format, format, "{label}");
        assert_eq!(
            (probed.width, probed.height),
            (decoded.width(), decoded.height()),
            "{label}: the probe and the decode must agree, post-orientation"
        );
    }
}

#[test]
fn a_probe_admits_exactly_what_a_decode_admits() {
    // The load-bearing property: every cap still binds, on header-derived numbers, before any
    // allocation. A probe that admitted something the decoder refuses would be a hole in the caps;
    // one that refused something the decoder accepts would drop real images from real decks.
    let limits = DecodeLimits::default();
    let tight = DecodeLimits {
        max_width: 8,
        max_height: 8,
        max_pixels: 64,
        max_encoded_bytes: 64 * 1024,
    };
    let cases: Vec<(&str, Vec<u8>, DecodeLimits)> = vec![
        ("empty", Vec::new(), limits),
        ("gif", b"GIF89a\0\0\0\0".to_vec(), limits),
        ("bmp", b"BM\0\0\0\0\0\0".to_vec(), limits),
        ("svg", b"<svg xmlns=\"x\"></svg>".to_vec(), limits),
        ("truncated png", png(4, 4)[..20].to_vec(), limits),
        ("png over the dimension cap", png(64, 64), tight),
        ("jpeg over the dimension cap", jpeg(64, 64, None), tight),
        (
            "jpeg past the sequential pixel cap",
            jpeg_header_only(65_500, 65_500, 0xC0),
            limits,
        ),
        (
            "progressive past the tighter progressive cap",
            jpeg_header_only(6000, 5000, 0xC2),
            limits,
        ),
        (
            "arithmetic-coded frame",
            jpeg_header_only(64, 64, 0xC9),
            limits,
        ),
        ("lossless frame", jpeg_header_only(64, 64, 0xC3), limits),
        ("hierarchical frame", jpeg_header_only(64, 64, 0xC5), limits),
    ];
    for (label, bytes, l) in cases {
        let probed = probe_image(&bytes, &l);
        let decoded = decode_image(&bytes, &l);
        assert!(
            probed.is_err(),
            "{label}: the probe admitted something it must refuse"
        );
        assert!(decoded.is_err(), "{label}: premise — the decode refuses it");
        assert_eq!(
            probed.unwrap_err(),
            decoded.unwrap_err(),
            "{label}: the probe and the decode must refuse for the SAME stated reason, or a drop \
             report tells the operator something the render path disagrees with"
        );
    }
}

#[test]
fn the_encoded_byte_cap_precedes_the_header_walk() {
    let limits = DecodeLimits {
        max_encoded_bytes: 16,
        ..DecodeLimits::default()
    };
    assert_eq!(
        probe_image(&png(64, 64), &limits),
        Err(DecodeError::TooLarge)
    );
    assert_eq!(
        probe_image(&jpeg(64, 64, None), &limits),
        Err(DecodeError::TooLarge)
    );
}

#[test]
fn a_sound_header_over_a_corrupt_payload_is_admitted_and_says_so() {
    // The one thing the header probe gives up, stated as a test rather than left implicit: a PNG
    // whose IHDR is intact and whose IDAT is rubbish now PASSES the probe and FAILS the decode.
    // The importer stages it; the render path shows the missing-media placeholder. That is the
    // deliberate trade, and if it ever stops being true this test says so.
    let mut bytes = png(8, 8);
    let n = bytes.len();
    // Corrupt only the tail — the compressed image data — leaving the signature and IHDR alone.
    for b in bytes.iter_mut().take(n - 12).skip(60) {
        *b ^= 0xFF;
    }
    let probed = probe_image(&bytes, &DecodeLimits::default()).expect("the header is intact");
    assert_eq!((probed.width, probed.height), (8, 8));
    assert!(
        decode_image(&bytes, &DecodeLimits::default()).is_err(),
        "premise: the payload really is corrupt"
    );

    // A corrupt HEADER is still refused by the probe — the CRC on the IHDR chunk is what makes
    // that true, so this is not merely "we happen to read four bytes".
    let mut header_broken = png(8, 8);
    header_broken[18] ^= 0xFF; // inside IHDR's width field
    assert!(
        probe_image(&header_broken, &DecodeLimits::default()).is_err(),
        "a damaged IHDR must not pass the probe"
    );
}
