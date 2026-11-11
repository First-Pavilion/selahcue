//! Byte-level controls exercise the shared production encoder and borrowed decoder.
#[path = "../src/provider_source/payload.rs"]
mod payload;
use payload::{frame_json, json_from_frame, MAGIC, MAX_PAYLOAD, TRAILER};

const CANONICAL: &[u8] = include_bytes!("fixtures/pilot-canonical.json");
const GOLDEN: &[u8] = include_bytes!("fixtures/pilot-frame-v1.bin");

#[test]
fn encoder_and_borrowed_decoder_match_independent_python_golden() {
    assert_eq!(frame_json(CANONICAL).as_deref(), Some(GOLDEN));
    let body = json_from_frame(GOLDEN).expect("frozen frame is valid");
    assert_eq!(body.as_bytes(), CANONICAL);
    assert_eq!(body.as_ptr(), GOLDEN[MAGIC.len() + 4..].as_ptr());
}

#[test]
fn exact_payload_bounds_and_utf8_are_enforced() {
    for size in [1, MAX_PAYLOAD] {
        let raw = vec![b'a'; size];
        let frame = frame_json(&raw).expect("inclusive bounds");
        assert_eq!(
            json_from_frame(&frame).map(str::as_bytes),
            Some(raw.as_slice())
        );
        if size == MAX_PAYLOAD {
            assert_eq!(frame.len(), 16_430);
        }
    }
    assert!(frame_json(b"").is_none());
    assert!(frame_json(&vec![b'a'; MAX_PAYLOAD + 1]).is_none());
    assert!(frame_json(&[0xff]).is_none());
    assert_eq!(
        json_from_frame(&frame_json(b"{}").expect("structural JSON")),
        Some("{}")
    );
}

#[test]
fn malformed_frames_are_rejected_without_search_or_tolerance() {
    let mut cases = vec![Vec::new(), CANONICAL.to_vec()];
    // Every truncation exercises short magic, length, body and trailer boundaries.
    cases.extend((0..GOLDEN.len()).map(|end| GOLDEN[..end].to_vec()));
    for (offset, byte) in [(0, b'x'), (GOLDEN.len() - 1, b'x'), (MAGIC.len() + 4, 0xff)] {
        let mut frame = GOLDEN.to_vec();
        frame[offset] = byte;
        cases.push(frame);
    }
    for length in [
        0u32,
        16_385,
        u32::MAX,
        CANONICAL.len() as u32 - 1,
        CANONICAL.len() as u32 + 1,
    ] {
        let mut frame = GOLDEN.to_vec();
        frame[MAGIC.len()..MAGIC.len() + 4].copy_from_slice(&length.to_le_bytes());
        cases.push(frame);
    }
    let mut big_endian = GOLDEN.to_vec();
    big_endian[MAGIC.len()..MAGIC.len() + 4]
        .copy_from_slice(&(CANONICAL.len() as u32).to_be_bytes());
    cases.push(big_endian);
    cases.push([b"x".as_slice(), GOLDEN].concat());
    cases.push([GOLDEN, b"x".as_slice()].concat());
    cases.push([GOLDEN, GOLDEN].concat());
    // Complete, otherwise correctly framed empty and oversized bodies catch a
    // removed length-bound guard independently of the exact-total guard.
    for size in [0, MAX_PAYLOAD + 1] {
        cases.push(
            [
                MAGIC,
                &(size as u32).to_le_bytes(),
                &vec![b'a'; size],
                TRAILER,
            ]
            .concat(),
        );
    }
    for (index, frame) in cases.iter().enumerate() {
        assert!(json_from_frame(frame).is_none(), "malformed case {index}");
    }
}

#[cfg(feature = "pilot-credentials")]
#[test]
fn structural_framing_does_not_admit_credentials() {
    let frame = frame_json(b"{}").expect("valid structural frame");
    assert!(selahcue_cloud::pilot::PilotConfig::inspect(json_from_frame(&frame)).is_none());
}
