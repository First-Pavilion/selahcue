//! Bounded-memory tests for the outbound audio ring.
//!
//! Same bar and same shape as `test_queue.rs`: per-entity accessors, the control asserted to
//! have been exercised before the contract, the premise pinned at compile time, and both the
//! ring's own bound verdict and the entities asserted independently.
//!
//! This direction is the easier one to forget. A microphone callback does not stop when the
//! network does, and 16 kHz mono PCM is 32 KB per second — so an unbounded ring during a
//! five-minute outage is roughly ten megabytes of audio nobody will ever want.

#![allow(clippy::unwrap_used)]

use selahcue_stt_cloud::audio::MAX_AUDIO_CHUNK_BYTES;
use selahcue_stt_cloud::{AudioChunk, AudioRing, MAX_QUEUED_AUDIO_BYTES, MAX_QUEUED_AUDIO_CHUNKS};

/// A chunk of `samples` 16-bit samples, tagged in its first sample so it is identifiable by
/// name rather than only by count.
fn chunk(tag: i16, samples: usize) -> AudioChunk {
    let mut pcm = vec![tag];
    pcm.resize(samples.max(1), 0);
    AudioChunk::from_pcm_i16(&pcm)
}

#[test]
fn a_chunk_count_flood_stays_within_the_chunk_bound_and_drops_the_oldest() {
    const _: () = assert!(
        MAX_QUEUED_AUDIO_CHUNKS <= 4096,
        "the flood in this test is 4x the cap; past this it stops being a flood in reasonable \
         time and the chunk bound goes untested"
    );

    let ring = AudioRing::new();
    let oldest = chunk(i16::MIN, 1);
    let newest = chunk(i16::MAX, 1);

    ring.push(oldest.clone());
    for i in 0..(MAX_QUEUED_AUDIO_CHUNKS * 4) {
        ring.push(chunk((i % 1000) as i16, 2));
    }
    ring.push(newest.clone());

    assert!(
        ring.dropped_for_bound() > 0,
        "the ring dropped nothing, so MAX_QUEUED_AUDIO_CHUNKS never bound anything and every \
         assertion below this line is vacuous"
    );
    assert_eq!(
        ring.admitted(),
        (MAX_QUEUED_AUDIO_CHUNKS * 4 + 2) as u64,
        "the ring did not admit every chunk this test pushed, so the flood did not happen"
    );

    assert_eq!(
        ring.len(),
        MAX_QUEUED_AUDIO_CHUNKS,
        "the ring holds {} chunks against a cap of {MAX_QUEUED_AUDIO_CHUNKS}",
        ring.len()
    );
    assert!(
        ring.is_within_bounds(),
        "the ring reports itself out of bounds after dropping"
    );

    assert!(
        !ring.retains_chunk(&oldest),
        "the oldest chunk survived a 4x flood — the drop policy is not oldest-first, so a \
         reconnection would send minutes-old audio and the transcript would never catch up"
    );
    assert!(
        ring.retains_chunk(&newest),
        "the newest chunk was dropped — the ring is keeping stale audio over current audio"
    );
}

#[test]
fn a_byte_flood_stays_within_the_byte_bound_before_the_chunk_cap_is_reached() {
    // The premise: maximum-size chunks exhaust the BYTE budget while the chunk count is still
    // inside its own cap, so this distinguishes the two bounds rather than re-testing one.
    const CHUNKS_TO_FILL_BYTES: usize = MAX_QUEUED_AUDIO_BYTES / MAX_AUDIO_CHUNK_BYTES + 2;
    const _: () = assert!(
        CHUNKS_TO_FILL_BYTES < MAX_QUEUED_AUDIO_CHUNKS,
        "filling the byte budget also reaches the chunk cap, so this test cannot tell the two \
         bounds apart and the byte bound is untested"
    );

    let ring = AudioRing::new();
    let samples = MAX_AUDIO_CHUNK_BYTES / 2; // 2 bytes per 16-bit sample
    let oldest = chunk(i16::MIN, samples);

    ring.push(oldest.clone());
    for i in 0..CHUNKS_TO_FILL_BYTES {
        ring.push(chunk(i as i16, samples));
    }

    assert!(
        ring.dropped_for_bound() > 0,
        "nothing was dropped, so MAX_QUEUED_AUDIO_BYTES never bound anything"
    );
    assert!(
        ring.len() < MAX_QUEUED_AUDIO_CHUNKS,
        "the chunk cap was reached ({} of {MAX_QUEUED_AUDIO_CHUNKS}), so this test is \
         measuring the chunk bound, not the byte bound",
        ring.len()
    );

    assert!(
        ring.retained_bytes() <= MAX_QUEUED_AUDIO_BYTES,
        "the ring retains {} bytes against a budget of {MAX_QUEUED_AUDIO_BYTES}",
        ring.retained_bytes()
    );
    assert!(ring.is_within_bounds());
    assert!(
        !ring.retains_chunk(&oldest),
        "the oldest chunk survived a byte flood"
    );
    // ADMISSIBILITY, and the reason this line exists: every assertion above is satisfied
    // trivially by an EMPTY ring. If `MAX_AUDIO_CHUNK_BYTES` ever exceeds the byte budget, the
    // ring evicts each chunk the instant it admits it, no audio reaches the socket, and this
    // test would still pass. A bounded-memory suite that is green while the feature transmits
    // nothing is the worst possible version of a green test.
    assert!(
        !ring.is_empty(),
        "the ring is empty after a flood of admissible chunks — it is dropping everything it \
         accepts, so no audio would ever reach Deepgram while every bound reports success"
    );
    assert!(
        ring.retained_bytes() > 0,
        "the ring retains no bytes after a flood of admissible chunks"
    );
}

#[test]
fn a_benign_chunk_flows_through_the_ring_and_out_of_drain() {
    // The positive control: a ring that discarded everything would pass both bound tests.
    let ring = AudioRing::new();
    let one = chunk(42, 160);

    ring.push(one.clone());

    assert!(
        ring.retains_chunk(&one),
        "a single benign chunk did not reach the ring at all — without this the bound tests \
         cannot distinguish a working ring from a dead one"
    );
    assert_eq!(ring.dropped_for_bound(), 0);

    let drained = ring.drain();
    assert_eq!(drained.len(), 1, "drain did not return the buffered chunk");
    assert_eq!(drained[0], one);
    assert!(ring.is_empty(), "drain did not empty the ring");
    assert_eq!(
        ring.retained_bytes(),
        0,
        "draining left the byte accounting behind; the byte budget would fill with audio that \
         is no longer there and start dropping live audio"
    );
}

#[test]
fn an_oversized_chunk_is_refused_and_a_normal_one_is_still_admitted() {
    let ring = AudioRing::new();
    let oversized = chunk(7, MAX_AUDIO_CHUNK_BYTES); // 2 bytes/sample, so 2x the cap
    let normal = chunk(8, 160);

    ring.push(oversized.clone());
    // The positive control sits in the same test as the refusal, because "refused" is
    // indistinguishable from "the whole push path is dead" without it.
    ring.push(normal.clone());

    assert_eq!(
        ring.refused_oversize(),
        1,
        "the oversized chunk was not refused; one buffer would own most of the byte budget"
    );
    assert!(
        !ring.retains_chunk(&oversized),
        "the oversized chunk was queued anyway"
    );
    assert!(
        ring.retains_chunk(&normal),
        "a normal chunk was refused too — the refusal is not size-dependent, the push path is \
         simply not working"
    );
    assert_eq!(ring.len(), 1);
}

#[test]
fn an_empty_chunk_is_ignored_without_being_counted_as_a_refusal() {
    let ring = AudioRing::new();
    ring.push(AudioChunk::from_pcm_bytes(Vec::new()));
    assert!(ring.is_empty(), "an empty chunk was queued");
    assert_eq!(
        ring.refused_oversize(),
        0,
        "an empty chunk was reported as an oversize refusal, which would send a reader looking \
         for a capture bug that is not there"
    );
    assert_eq!(ring.admitted(), 0);
}

#[test]
fn pcm_is_encoded_little_endian_as_deepgram_is_told_to_expect() {
    // `encoding=linear16` on the wire means signed 16-bit LITTLE-endian. Getting this
    // backwards produces a connection that works and a transcript that is noise.
    let encoded = AudioChunk::from_pcm_i16(&[1, -2]);
    assert_eq!(
        encoded.as_bytes(),
        &[0x01, 0x00, 0xFE, 0xFF],
        "PCM is not little-endian; Deepgram would receive byte-swapped audio"
    );
    assert_eq!(encoded.len(), 4);
}

#[test]
fn clones_share_one_ring() {
    let ring = AudioRing::new();
    let other = ring.clone();
    let one = chunk(3, 8);
    other.push(one.clone());
    assert!(
        ring.retains_chunk(&one),
        "clones do not share one ring, so captured audio would never reach the socket"
    );
}
