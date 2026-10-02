//! Bounded-memory (no-leak) tests: every buffer that a live, endless sermon feeds is
//! hard-capped, so no input volume grows memory without limit. These are the committed,
//! CI-gated guards the no-leak invariant requires.

use selahcue_core::transcript::TranscriptProvider;
use selahcue_stt::{
    AudioChunk, EnergyVad, EngineConfig, FakeRecognizer, FeedbackGuard, ManualClock, PcmRing,
    SttEngine, MAX_PCM_SAMPLES, MAX_PENDING_SEGMENTS,
};
use std::time::{Duration, Instant};

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
        interim_interval: Duration::ZERO,
        interim_max_samples: 0,
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
    //
    // Interims are deliberately on at an aggressive cadence (fires roughly every processed
    // frame) so this test also proves the no-leak guarantee holds when BOTH finals and interims
    // are being pushed into the shared segment queue, not just finals alone (86akcfpbj). Driven
    // through `build_with_clock` with a `ManualClock` advanced one frame's worth of real time
    // per processed frame — the interim gate is now wall-clock-based, so a real `SttEngine::build`
    // fed this whole 200-frame burst in one synchronous call would very likely never fire an
    // interim at all (the burst executes in well under a millisecond of real time), which would
    // silently stop this test from exercising what its own comment claims.
    let config = EngineConfig {
        hangover_frames: 100,
        min_utterance_frames: 1,
        max_utterance_samples: FRAME_16K * 4, // force-close every 4 frames
        interim_interval: Duration::from_millis(20), // fires ~every processed frame (1 * MS_PER_FRAME)
        interim_max_samples: 0,
    };
    let clock = ManualClock::new(Instant::now());
    let (mut engine, mut provider) = SttEngine::build_with_clock(
        config,
        Box::new(EnergyVad::new()),
        Box::new(FakeRecognizer::with_script(
            (0..5000).map(|i| format!("seg {i}")),
        )),
        FeedbackGuard::new(),
        Box::new(clock.clone()),
    );

    // 200 frames of continuous speech, no silence at all, fed one frame at a time with the
    // clock advanced a real frame's worth (20 ms) between each — the same pace a live
    // capture/recognition loop runs at when it is keeping up.
    let one_frame: Vec<f32> = (0..FRAME_16K)
        .map(|i| if i % 2 == 0 { 0.5 } else { -0.5 })
        .collect();
    for _ in 0..200 {
        engine.process(&AudioChunk::new(one_frame.clone(), 16_000, 1));
        clock.advance(Duration::from_millis(20));
    }
    engine.flush();

    // Force-close on the sample cap must chop 200 frames of unbroken speech into MANY bounded
    // FINAL utterances (≈ 200 / 4 = 50), plus roughly two interims per 4-frame group at this
    // cadence (≈ 150 segments total pushed into the shared, bounded queue).
    //
    // **Counted on FINALS ONLY (Vera, PR #124 review, F3 — the prior version of this assertion
    // counted `out.len()` over EVERY segment, finals and interims together, which made it
    // vacuous with respect to the claim in its own name and comment.** With interims firing on
    // their own wall-clock cadence regardless of whether the sample cap does anything, a
    // regression that removed `max_utterance_samples` entirely — the whole 200 frames staying
    // in ONE utterance, closed only by the final `flush()` — would still leave `out.len()` in
    // the hundreds from interims alone, and the old `out.len() >= 40` assertion would not
    // notice. Counting `is_final` segments specifically measures what this test is actually
    // named for: verified failing (1 final, from `flush()` alone) against `main`'s equivalent
    // scenario with the cap effectively disabled, and passing on the real code.
    let out = provider.poll();
    let finals = out.iter().filter(|s| s.is_final).count();
    assert!(
        finals >= 40,
        "expected the sample cap to force-close many FINAL segments (~50), got {finals} \
         finals ({} total incl. interims) — cap not enforced?",
        out.len()
    );
    assert!(out.len() <= MAX_PENDING_SEGMENTS);
}
