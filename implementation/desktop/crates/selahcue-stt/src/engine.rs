//! The pipeline orchestrator: raw audio → resample → VAD-bracketed utterances → recognizer
//! → bounded segment queue. Pure and deterministic (no wall clock, no RNG) so the whole
//! flow is reproducible with fakes; the only I/O (microphone, model) lives behind the
//! [`crate::audio`] / [`crate::recognizer`] seams.
//!
//! Timekeeping: the engine reads no clock. Time advances one VAD frame (20 ms) per
//! *processed* frame, so a segment's `start_ms`/`end_ms` come from the audio position, not
//! wall time. Audio dropped by the feedback guard does not advance the transcript clock
//! (nothing was transcribed then), keeping the timeline aligned to real speech.
//!
//! Buffers are reused, not reallocated: `frame_buf` is a `VecDeque` (O(1) front-pop, so a
//! large catch-up chunk is O(n), never O(n²)), and both the per-frame scratch and the
//! utterance accumulator keep their capacity across utterances — no per-frame or
//! per-utterance heap churn on the steady-state hot path.

use std::collections::VecDeque;

use selahcue_core::transcript::ProviderSegment;

use crate::audio::AudioChunk;
use crate::guard::FeedbackGuard;
use crate::provider::{SegmentSink, SttProvider};
use crate::recognizer::Recognizer;
use crate::resample::resample_to_16k_mono;
use crate::vad::{Vad, FRAME_SAMPLES};
use crate::TARGET_SAMPLE_RATE;

/// Milliseconds represented by one processed VAD frame (20 ms @ 16 kHz).
const MS_PER_FRAME: u64 = (FRAME_SAMPLES as u64) * 1000 / (TARGET_SAMPLE_RATE as u64);

/// Utterance-segmentation tunables.
#[derive(Debug, Clone, Copy)]
pub struct EngineConfig {
    /// Consecutive non-speech frames that close an open utterance (end-of-speech hangover).
    pub hangover_frames: usize,
    /// Minimum voiced frames for an utterance to be worth recognizing (drops lone blips).
    pub min_utterance_frames: usize,
    /// Hard cap on an utterance's samples; unbroken speech is force-closed here so the
    /// accumulator can never grow without bound (no-leak) AND so a sustained monologue still
    /// produces transcript within a bounded delay. Default 10 s balances the ≤2 s latency
    /// target (streaming interims to get fully under 2 s are a spike-gated follow-up, S8/S11)
    /// against giving the recognizer enough context.
    pub max_utterance_samples: usize,
}

impl Default for EngineConfig {
    fn default() -> Self {
        EngineConfig {
            hangover_frames: 15,     // ~300 ms of trailing silence closes an utterance
            min_utterance_frames: 3, // ~60 ms of speech minimum
            max_utterance_samples: 10 * TARGET_SAMPLE_RATE as usize, // 10 s force-close
        }
    }
}

/// The STT pipeline. Feed it device audio with [`process`](SttEngine::process) (or
/// [`drain_source`](SttEngine::drain_source)); it pushes finished [`ProviderSegment`]s into
/// the shared [`SegmentSink`] a paired [`SttProvider`] drains.
pub struct SttEngine {
    vad: Box<dyn Vad + Send>,
    recognizer: Box<dyn Recognizer + Send>,
    guard: FeedbackGuard,
    sink: SegmentSink,
    config: EngineConfig,

    // --- pipeline state (all buffers are reused across calls; see the module docs) ---
    /// 16 kHz mono samples not yet formed into a full VAD frame (carried across calls).
    frame_buf: VecDeque<f32>,
    /// Reusable scratch for the current VAD frame (avoids a per-frame allocation).
    frame_scratch: Vec<f32>,
    /// The current utterance's accumulated 16 kHz samples (capacity retained across closes).
    utterance: Vec<f32>,
    in_speech: bool,
    silence_run: usize,
    speech_frames: usize,
    /// Processed-frame counter (the transcript clock).
    frame_index: u64,
    /// Frame index at which the current utterance started.
    utt_start_frame: u64,
}

// The engine is designed to run on a host worker thread; make that a compile-time
// guarantee so a future non-Send field is caught here, not at the host's spawn site.
const _: fn() = || {
    fn assert_send<T: Send>() {}
    assert_send::<SttEngine>();
};

impl SttEngine {
    /// Build an engine and its paired [`SttProvider`], sharing one bounded segment queue.
    /// The provider's label discloses the recognizer (FR-120), e.g. `"stt:whisper-…"`.
    pub fn build(
        config: EngineConfig,
        vad: Box<dyn Vad + Send>,
        recognizer: Box<dyn Recognizer + Send>,
        guard: FeedbackGuard,
    ) -> (SttEngine, SttProvider) {
        let sink = SegmentSink::new();
        let label = format!("stt:{}", recognizer.label());
        let engine = SttEngine {
            vad,
            recognizer,
            guard,
            sink: sink.clone(),
            config,
            frame_buf: VecDeque::new(),
            frame_scratch: Vec::with_capacity(FRAME_SAMPLES),
            utterance: Vec::new(),
            in_speech: false,
            silence_run: 0,
            speech_frames: 0,
            frame_index: 0,
            utt_start_frame: 0,
        };
        (engine, SttProvider::new(sink, label))
    }

    /// Pull and process every currently-available chunk from `source` (non-blocking).
    /// A host worker calls this on a loop; a test drives it once from a [`FakeAudioSource`].
    pub fn drain_source(&mut self, source: &mut dyn crate::audio::AudioSource) {
        while let Some(chunk) = source.next_chunk() {
            self.process(&chunk);
        }
    }

    /// Process one device chunk. While the feedback guard suppresses (app audio on a shared
    /// output, FR-172), the chunk is dropped *before* any work — SelahCue never transcribes
    /// itself — and any open utterance is flushed. Otherwise downmix/resample to 16 kHz mono
    /// and VAD-frame it.
    pub fn process(&mut self, chunk: &AudioChunk) {
        if self.guard.is_suppressed() {
            // Close any real speech captured before suppression, then discard this audio and
            // any partial frame — do not advance the clock across suppressed (untranscribed)
            // time. Skip the resample entirely (no wasted work while suppressed).
            self.close_utterance();
            self.frame_buf.clear();
            return;
        }
        let mono = resample_to_16k_mono(&chunk.samples, chunk.sample_rate, chunk.channels);
        self.frame_buf.extend(mono);
        while self.frame_buf.len() >= FRAME_SAMPLES {
            // Pop one frame into the reused scratch (O(1) front-pops — no O(n) memmove).
            self.frame_scratch.clear();
            for _ in 0..FRAME_SAMPLES {
                match self.frame_buf.pop_front() {
                    Some(s) => self.frame_scratch.push(s),
                    None => break,
                }
            }
            self.process_current_frame();
        }
    }

    /// Advance one VAD frame (held in `self.frame_scratch`), updating utterance state and
    /// closing the utterance on end-of-speech hangover or the hard sample cap.
    fn process_current_frame(&mut self) {
        self.frame_index += 1;
        let speech = self.vad.is_speech(&self.frame_scratch);
        if speech {
            if !self.in_speech {
                self.in_speech = true;
                self.utt_start_frame = self.frame_index - 1;
                self.utterance.clear();
                self.speech_frames = 0;
            }
            self.utterance.extend_from_slice(&self.frame_scratch);
            self.speech_frames += 1;
            self.silence_run = 0;
        } else if self.in_speech {
            // Trailing silence is part of the utterance span until the hangover elapses.
            self.utterance.extend_from_slice(&self.frame_scratch);
            self.silence_run += 1;
        }
        // Close on hangover OR the hard sample cap (checked after any append, so the
        // accumulator is bounded regardless of which branch grew it — no-leak).
        if self.in_speech
            && (self.silence_run >= self.config.hangover_frames
                || self.utterance.len() >= self.config.max_utterance_samples)
        {
            self.close_utterance();
        }
    }

    /// Close the open utterance: recognize it (if long enough) and push its finals to the
    /// sink, then reset speech state, retaining the accumulator's capacity. No-op when not
    /// in speech.
    fn close_utterance(&mut self) {
        if !self.in_speech {
            return;
        }
        let long_enough = self.speech_frames >= self.config.min_utterance_frames;
        let start_ms = self.utt_start_frame * MS_PER_FRAME;
        let end_ms = self.frame_index * MS_PER_FRAME;
        // Reset before recognizing so state is clean even if the recognizer re-enters.
        self.in_speech = false;
        self.silence_run = 0;
        self.speech_frames = 0;
        if long_enough {
            // Borrow the accumulator (never move it) so its capacity survives for reuse.
            for seg in self
                .recognizer
                .transcribe(&self.utterance, start_ms, end_ms)
            {
                if seg.text.trim().is_empty() {
                    continue; // never surface an empty transcript line
                }
                self.sink.push(ProviderSegment {
                    text: seg.text,
                    start_ms: seg.start_ms,
                    end_ms: seg.end_ms,
                    is_final: seg.is_final,
                });
            }
        }
        self.utterance.clear(); // keep capacity — the next utterance reuses it (no re-alloc)
    }

    /// Force-close any open utterance (e.g. on stop). Recognizes and flushes what's buffered.
    pub fn flush(&mut self) {
        self.close_utterance();
    }

    /// The engine's recognizer label (honest disclosure, FR-120).
    pub fn recognizer_label(&self) -> &str {
        self.recognizer.label()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::AudioChunk;
    use crate::guard::FeedbackGuard;
    use crate::recognizer::FakeRecognizer;
    use crate::vad::EnergyVad;
    use selahcue_core::transcript::TranscriptProvider;

    /// A 16 kHz mono chunk of `frames` speech frames (loud alternating waveform).
    fn speech_chunk(frames: usize) -> AudioChunk {
        let mut s = Vec::new();
        for i in 0..(frames * FRAME_SAMPLES) {
            s.push(if i % 2 == 0 { 0.5 } else { -0.5 });
        }
        AudioChunk::new(s, TARGET_SAMPLE_RATE, 1)
    }

    /// A 16 kHz mono chunk of `frames` silence frames.
    fn silence_chunk(frames: usize) -> AudioChunk {
        AudioChunk::new(vec![0.0; frames * FRAME_SAMPLES], TARGET_SAMPLE_RATE, 1)
    }

    fn engine_with(
        script: &[&str],
        config: EngineConfig,
    ) -> (SttEngine, crate::provider::SttProvider) {
        SttEngine::build(
            config,
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::with_script(script.iter().copied())),
            FeedbackGuard::new(),
        )
    }

    #[test]
    fn speech_then_silence_yields_one_segment() {
        let (mut engine, mut provider) =
            engine_with(&["and it came to pass"], EngineConfig::default());
        engine.process(&speech_chunk(10)); // 10 voiced frames
        engine.process(&silence_chunk(20)); // > hangover → closes the utterance
        let out = provider.poll();
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].text, "and it came to pass");
        assert!(out[0].is_final);
        assert!(out[0].end_ms >= out[0].start_ms);
    }

    #[test]
    fn pure_silence_yields_nothing() {
        let (mut engine, mut provider) =
            engine_with(&["should-not-appear"], EngineConfig::default());
        engine.process(&silence_chunk(50));
        assert!(provider.poll().is_empty());
    }

    #[test]
    fn feedback_guard_suppresses_ingestion() {
        let guard = FeedbackGuard::new();
        let (mut engine, mut provider) = SttEngine::build(
            EngineConfig::default(),
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::with_script(["after-resume"])),
            guard.clone(),
        );
        guard.set_output_active(true); // app audio on shared output
        engine.process(&speech_chunk(10));
        engine.process(&silence_chunk(20));
        assert!(
            provider.poll().is_empty(),
            "suppressed audio must not transcribe"
        );
        // After the app stops playing, capture resumes.
        guard.set_output_active(false);
        engine.process(&speech_chunk(10));
        engine.process(&silence_chunk(20));
        let out = provider.poll();
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].text, "after-resume");
    }
}
