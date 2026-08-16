//! The structural half of the B5-J caps: a **counting global allocator** proving that a refused
//! JPEG allocates essentially nothing — that the caps run at SOF parse, *before* any pixel or
//! coefficient buffer exists, rather than after the allocation they were meant to prevent
//! (threat model §8.4; repo bounded-memory rule).
//!
//! This is a separate test binary holding exactly **one** test, on purpose: a global allocator
//! is per-binary and its counters are process-wide, so a second concurrently-running test would
//! make the measurement meaningless.

#![allow(clippy::unwrap_used)]

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

use selahcue_engine::{decode_image, probe_image, DecodeError, DecodeLimits};

/// Total bytes handed out since the last reset (never decremented) — a peak-pressure proxy that
/// cannot be flattered by a free.
static ALLOCATED: AtomicUsize = AtomicUsize::new(0);

struct Counting;

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATED.fetch_add(layout.size(), Ordering::Relaxed);
        System.alloc(layout)
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        System.dealloc(ptr, layout)
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATED.fetch_add(new_size.saturating_sub(layout.size()), Ordering::Relaxed);
        System.realloc(ptr, layout, new_size)
    }
}

#[global_allocator]
static ALLOC: Counting = Counting;

/// Bytes allocated while running `f`.
fn allocated_by<R>(f: impl FnOnce() -> R) -> (R, usize) {
    let before = ALLOCATED.load(Ordering::Relaxed);
    let out = f();
    (out, ALLOCATED.load(Ordering::Relaxed) - before)
}

/// A minimal but genuinely DECODABLE baseline JPEG: `w`×`h` grayscale, flat blocks. The control
/// case needs one — see below.
fn decodable(w: u16, h: u16) -> Vec<u8> {
    fn segment(marker: u8, payload: &[u8]) -> Vec<u8> {
        let len = (payload.len() + 2) as u16;
        let mut v = vec![0xFF, marker];
        v.extend_from_slice(&len.to_be_bytes());
        v.extend_from_slice(payload);
        v
    }
    let mut bytes = vec![0xFF, 0xD8];
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
        stream.push_str("000000");
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

/// A tiny PNG, for the probe section.
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

/// A frame header with no scan data: everything the admission profile reads, and nothing more.
fn header_only(width: u16, height: u16, sof_marker: u8) -> Vec<u8> {
    let mut bytes = vec![0xFF, 0xD8];
    // DQT
    let mut dqt = vec![0xFF, 0xDB, 0x00, 0x43, 0x00];
    dqt.extend(std::iter::repeat_n(16u8, 64));
    bytes.extend(dqt);
    // SOF
    bytes.extend_from_slice(&[0xFF, sof_marker, 0x00, 0x0B, 8]);
    bytes.extend_from_slice(&height.to_be_bytes());
    bytes.extend_from_slice(&width.to_be_bytes());
    bytes.extend_from_slice(&[1, 1, 0x11, 0x00]);
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    bytes
}

/// Well under the smallest buffer any of these images would need: 65500×65500 RGBA is 16 TiB,
/// and its coefficient planes alone would be 8 TiB. Anything near this bound means the caps ran
/// after an allocation, not before it.
const REFUSAL_BUDGET: usize = 64 * 1024;

#[test]
fn refused_frames_allocate_nothing_and_admitted_ones_do() {
    let limits = DecodeLimits::default();

    // Warm any one-time lazy allocation so the measurements below are the decode's own.
    let _ = decode_image(&header_only(8, 8, 0xC0), &limits);

    // 1. Dimensions far past the caps: refused at SOF parse.
    let (r, bytes) = allocated_by(|| decode_image(&header_only(65_500, 65_500, 0xC0), &limits));
    assert_eq!(r, Err(DecodeError::Oversize));
    assert!(
        bytes < REFUSAL_BUDGET,
        "an oversize frame allocated {bytes} bytes — the cap ran after allocation, not before"
    );

    // 2. A progressive frame over the 24 MP progressive cap but under the 40 MP sequential one:
    //    refused before a single coefficient plane exists, which is the whole point of the split.
    let (r, bytes) = allocated_by(|| decode_image(&header_only(6000, 5000, 0xC2), &limits));
    assert_eq!(r, Err(DecodeError::Oversize));
    assert!(
        bytes < REFUSAL_BUDGET,
        "a 30 MP progressive frame allocated {bytes} bytes before refusal"
    );

    // 3. Refused variants never reach a decoder either.
    for marker in [0xC9u8, 0xC3, 0xC5] {
        let (r, bytes) = allocated_by(|| decode_image(&header_only(4000, 4000, marker), &limits));
        assert_eq!(r, Err(DecodeError::UnsupportedVariant));
        assert!(
            bytes < REFUSAL_BUDGET,
            "variant {marker:#04x} allocated {bytes}"
        );
    }

    // 4. Control: an ADMITTED frame does allocate a PIXEL BUFFER, so the assertions above are
    //    measuring something real rather than a decoder that never runs.
    //
    //    `bytes > 0` was not that control. The previous case fed the decoder a header with no scan
    //    and asserted only that *something* was allocated — and `jpeg_decoder::Error::Format`
    //    carries an owned `String`, so the assertion passed on the error message alone, with no
    //    pixel buffer anywhere. The control has to decode a real frame and be weighed against that
    //    frame's own output.
    let w = 512u16;
    let h = 512u16;
    let plane = usize::from(w) * usize::from(h);
    let (r, bytes) = allocated_by(|| decode_image(&decodable(w, h), &limits));
    let image = r.expect("the control frame must really decode");
    assert_eq!(
        (image.width(), image.height()),
        (u32::from(w), u32::from(h))
    );
    assert!(
        bytes > plane,
        "an admitted frame allocated only {bytes} bytes for a {plane}-pixel image — the control \
         is not exercising a decode, so the refusal budgets above prove nothing"
    );

    // 5. And the header PROBE, on the same admitted frame and on a four-megapixel PNG: it makes
    //    every admission decision the decode makes and allocates no pixel buffer at all. This is
    //    the property the presentation importer now rests on — validating an image used to mean
    //    decoding it and discarding the pixels, over 99 % of import time — and only a weighing
    //    machine can see it, because the probe and the decode report identical dimensions.
    let (r, bytes) = allocated_by(|| probe_image(&decodable(w, h), &limits));
    assert_eq!(r.map(|i| (i.width, i.height)), Ok((512, 512)));
    assert!(
        bytes < REFUSAL_BUDGET,
        "probing a {plane}-pixel JPEG allocated {bytes} bytes — it decoded"
    );

    // PNG gets its own budget, and a larger one, for an honest reason: the JPEG side is a
    // hand-rolled marker walk that allocates literally nothing, while the PNG side constructs the
    // `png` crate's streaming reader, which holds a row-sized buffer and a zlib window. Those are
    // fixed working buffers, not pixels — which is exactly what the scaling assertion below
    // establishes, and what a byte count alone could not.
    const PNG_HEADER_BUDGET: usize = 256 * 1024;
    let four_mpx = png(2048, 2048);
    let (r, small) = allocated_by(|| probe_image(&four_mpx, &limits));
    assert_eq!(r.map(|i| (i.width, i.height)), Ok((2048, 2048)));
    assert!(
        small < PNG_HEADER_BUDGET,
        "probing a 4 Mpx PNG allocated {small} bytes against a 16 MiB RGBA plane — it decoded"
    );

    // Four times the pixels for roughly the same cost. A probe that had started decoding would
    // scale with the image; a header read does not.
    let sixteen_mpx = png(4096, 4096);
    let (r, large) = allocated_by(|| probe_image(&sixteen_mpx, &limits));
    assert_eq!(r.map(|i| (i.width, i.height)), Ok((4096, 4096)));
    assert!(
        large < small.saturating_mul(3),
        "quadrupling the pixels took {small} bytes to {large} — the cost is tracking the image, \
         so something is decoding it"
    );
}
