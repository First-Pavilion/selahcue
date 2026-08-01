//! Bounded-memory (no-leak) tests: every buffer that a live, endless sermon feeds is
//! hard-capped, so no input volume grows memory without limit. These are the committed,
//! CI-gated guards the no-leak invariant requires.

use selahcue_core::transcript::TranscriptProvider;
use selahcue_stt::{
    AudioChunk, EnergyVad, EngineConfig, FakeRecognizer, FeedbackGuard, PcmRing, SttEngine,
    MAX_PCM_SAMPLES, MAX_PENDING_SEGMENTS,
};

const FRAME_16K: usize = 320;

#[test]
fn bounded_pcm_ring_caps_under_a_flood() {
    let mut ring = PcmRing::with_capacity(1_000);
    // Push far more than the cap in many bursts.
    for _ in 0..500 {
        ring.push(&vec![0.25_f32; 100]); // 50_000 samples total
    }
    assert_eq!(ring.len(), 1_000, "ring must hold at most its cap");
    assert!(
        ring.dropped() > 0,
        "excess samples must be counted as dropped"
    );
}

#[test]
fn bounded_pcm_ring_default_cap_is_finite() {
    let ring = PcmRing::new();
    // The default cap is a concrete finite bound (30 s @ 48 kHz stereo), never unbounded.
    assert_eq!(MAX_PCM_SAMPLES, 48_000 * 2 * 30);
    assert!(ring.is_empty());
}

#[test]
fn bounded_segment_queue_caps_when_host_never_polls() {
    // A recognizer with an effectively endless script + continuous speech and NO polling:
    // the pending-segment queue must not grow past its cap.
    let script: Vec<String> = (0..(MAX_PENDING_SEGMENTS * 4))
        .map(|i| format!("line {i}"))
        .collect();
    // Tiny max-utterance so each short speech burst force-closes into its own segment.
    let config = EngineConfig {
        hangover_frames: 2,
        min_utterance_frames: 1,
        max_utterance_samples: FRAME_16K, // 1 frame → each speech frame closes an utterance
    };
    let (mut engine, provider) = SttEngine::build(
        config,
        Box::new(EnergyVad::new()),
        Box::new(FakeRecognizer::with_script(script)),
        FeedbackGuard::new(),
    );

    // Feed many speech/silence cycles WITHOUT ever polling the provider.
    for _ in 0..(MAX_PENDING_SEGMENTS * 4) {
        engine.process(&AudioChunk::new(
            (0..FRAME_16K)
                .map(|i| if i % 2 == 0 { 0.5 } else { -0.5 })
                .collect(),
            16_000,
            1,
        ));
        engine.process(&AudioChunk::new(vec![0.0; FRAME_16K * 3], 16_000, 1)); // close it
    }

    // The provider's shared queue never exceeded its cap.
    let mut provider = provider;
    let drained = provider.poll();
    assert!(
        drained.len() <= MAX_PENDING_SEGMENTS,
        "pending queue grew to {} (cap {})",
        drained.len(),
        MAX_PENDING_SEGMENTS
    );
}

#[test]
fn bounded_utterance_accumulator_force_closes_continuous_speech() {
    // Continuous speech with NO pause must not let the utterance accumulator grow without
    // bound: it force-closes at max_utterance_samples, emitting bounded segments instead.
    let config = EngineConfig {
        hangover_frames: 100,
        min_utterance_frames: 1,
        max_utterance_samples: FRAME_16K * 4, // force-close every 4 frames
    };
    let (mut engine, mut provider) = SttEngine::build(
        config,
        Box::new(EnergyVad::new()),
        Box::new(FakeRecognizer::with_script(
            (0..1000).map(|i| format!("seg {i}")),
        )),
        FeedbackGuard::new(),
    );

    // One long continuous-speech chunk (200 frames), no silence at all.
    let long_speech: Vec<f32> = (0..(200 * FRAME_16K))
        .map(|i| if i % 2 == 0 { 0.5 } else { -0.5 })
        .collect();
    engine.process(&AudioChunk::new(long_speech, 16_000, 1));
    engine.flush();

    // Force-closing produced multiple bounded segments (≈ 200 / 4), and the queue stayed capped.
    let out = provider.poll();
    assert!(
        !out.is_empty(),
        "continuous speech must still produce segments"
    );
    assert!(out.len() <= MAX_PENDING_SEGMENTS);
}
