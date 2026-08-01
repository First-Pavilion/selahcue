//! End-to-end pipeline tests through the public API: a `FakeAudioSource` at a real device
//! rate/channel count → resample → VAD → `FakeRecognizer` → `SttProvider::poll`. No
//! microphone, no model — fully deterministic.

use selahcue_core::transcript::TranscriptProvider;
use selahcue_stt::{
    AudioChunk, EnergyVad, EngineConfig, FakeAudioSource, FakeRecognizer, FeedbackGuard, SttEngine,
};

const FRAME_16K: usize = 320; // 20 ms @ 16 kHz

/// `frames` worth of 48 kHz **stereo** speech (loud alternating waveform) — exercises both
/// downmix and downsample on the way to the recognizer.
fn speech_48k_stereo(frames_16k: usize) -> AudioChunk {
    // 48 kHz is 3× 16 kHz; stereo doubles the interleaved length.
    let samples_16k = frames_16k * FRAME_16K;
    let mut s = Vec::with_capacity(samples_16k * 3 * 2);
    for i in 0..(samples_16k * 3) {
        let v = if i % 2 == 0 { 0.5 } else { -0.5 };
        s.push(v); // L
        s.push(v); // R
    }
    AudioChunk::new(s, 48_000, 2)
}

fn silence_48k_stereo(frames_16k: usize) -> AudioChunk {
    AudioChunk::new(vec![0.0; frames_16k * FRAME_16K * 3 * 2], 48_000, 2)
}

#[test]
fn pipeline_transcribes_speech_and_gates_silence() {
    let (mut engine, mut provider) = SttEngine::build(
        EngineConfig::default(),
        Box::new(EnergyVad::new()),
        Box::new(FakeRecognizer::with_script(["in the beginning"])),
        FeedbackGuard::new(),
    );

    // Drive the engine from a device-shaped source: leading silence, speech, trailing
    // silence (the trailing silence closes the utterance via the hangover).
    let mut source = FakeAudioSource::with_chunks([
        silence_48k_stereo(5),
        speech_48k_stereo(12),
        silence_48k_stereo(20),
    ]);
    engine.drain_source(&mut source);

    let out = provider.poll();
    assert_eq!(out.len(), 1, "expected exactly one recognized segment");
    assert_eq!(out[0].text, "in the beginning");
    assert!(out[0].is_final);
    assert!(out[0].end_ms >= out[0].start_ms);
    // Honest provider disclosure (FR-120).
    assert_eq!(provider.label(), "stt:fake");

    // A second poll after draining returns nothing (no double-delivery).
    assert!(provider.poll().is_empty());
}

#[test]
fn pipeline_yields_nothing_for_pure_silence() {
    let (mut engine, mut provider) = SttEngine::build(
        EngineConfig::default(),
        Box::new(EnergyVad::new()),
        Box::new(FakeRecognizer::with_script(["should-not-appear"])),
        FeedbackGuard::new(),
    );
    let mut source = FakeAudioSource::with_chunks([silence_48k_stereo(60)]);
    engine.drain_source(&mut source);
    assert!(provider.poll().is_empty());
}
