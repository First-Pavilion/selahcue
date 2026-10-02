//! The pipeline orchestrator: raw audio → resample → VAD-bracketed utterances → recognizer
//! → bounded segment queue. No RNG, and reads no OS wall clock unprompted (the only I/O —
//! microphone, model, real time — lives behind the [`crate::audio`] / [`crate::recognizer`] /
//! [`Clock`] seams), so the whole flow stays reproducible with fakes.
//!
//! Timekeeping has TWO separate clocks, deliberately not conflated (86akcfpbj):
//! - **The transcript clock is audio position, not wall time.** A segment's `start_ms`/
//!   `end_ms` come from counting processed VAD frames (20 ms each), not from [`Clock`]. Audio
//!   dropped by the feedback guard does not advance it (nothing was transcribed then), keeping
//!   the timeline aligned to real speech regardless of how fast or slow this call happened to
//!   run.
//! - **The streaming-interim CADENCE is wall time**, via an injected [`Clock`] — mirroring
//!   `selahcue_core::timer::Timer`'s "the caller supplies `now`" discipline rather than this
//!   engine reading `Instant::now()` unprompted. This existed as a raw *frame* counter
//!   (`frames_since_interim`) until 86akcfpbj: once the recognizer falls behind real time (the
//!   dominant cause, Phase 1 — 86akcfp3u), draining a backlog feeds frames through FASTER than
//!   real time, so a frame-counted gate fired interims more often, not less, exactly when the
//!   system was already behind — a positive-feedback loop that made the lag self-reinforcing.
//!   Gating on wall-clock elapsed time since the last interim removes that feedback loop: no
//!   matter how many frames a single `process()` call burns through, only real elapsed time
//!   advances the gate. [`SystemClock`] (default, real monotonic clock) and [`ManualClock`]
//!   (test double, advanced explicitly) are the two implementations.
//!
//! Buffers are reused, not reallocated: `frame_buf` is a `VecDeque` (O(1) front-pop, so a
//! large catch-up chunk is O(n), never O(n²)), and both the per-frame scratch and the
//! utterance accumulator keep their capacity across utterances — no per-frame or
//! per-utterance heap churn on the steady-state hot path.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

use selahcue_core::transcript::ProviderSegment;

use crate::audio::AudioChunk;
use crate::guard::FeedbackGuard;
use crate::provider::{SegmentSink, SttProvider};
use crate::recognizer::Recognizer;
use crate::repetition::trim_trailing_repeat;
use crate::resample::resample_to_16k_mono;
use crate::vad::{Vad, FRAME_SAMPLES};
use crate::TARGET_SAMPLE_RATE;

/// Milliseconds represented by one processed VAD frame (20 ms @ 16 kHz).
const MS_PER_FRAME: u64 = (FRAME_SAMPLES as u64) * 1000 / (TARGET_SAMPLE_RATE as u64);

/// Where [`SttEngine`] gets "now" from for the interim wall-clock gate (86akcfpbj) — injected
/// so production reads the real monotonic clock and a test can control it deterministically,
/// the same reason `selahcue_core::timer::Timer` takes an injected `Instant` rather than
/// reading one itself. `Send` because the engine (and therefore this) runs on a host worker
/// thread (see the `assert_send::<SttEngine>()` check below).
pub trait Clock: Send {
    fn now(&self) -> Instant;
}

/// The real monotonic clock. What [`SttEngine::build`] uses — every production caller gets
/// this without needing to know the seam exists.
#[derive(Debug, Default, Clone, Copy)]
struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}

/// A [`Clock`] a test holds and advances explicitly — `Instant` has no public constructor from
/// an arbitrary value, so this starts from a real `Instant::now()` and moves forward only when
/// [`advance`](Self::advance) is called; it never advances on its own. `Clone`+`Arc`-backed so
/// a test can pass one handle (boxed) into [`SttEngine::build_with_clock`] and keep another to
/// drive time forward afterward, deterministically — no real `Duration::sleep` anywhere.
///
/// Public (not test-only/`cfg(test)`) because at least one bounded-memory regression test lives
/// in `selahcue-stt`'s own `tests/` integration suite (an external crate from `engine.rs`'s own
/// `#[cfg(test)]` module) and needs deterministic interim firing to stay a genuine, non-vacuous
/// control rather than depending on how fast that test happens to run — the same reason
/// [`crate::recognizer::FakeRecognizer`] and [`crate::audio::FakeAudioSource`] are plain public
/// items rather than gated behind a test-only feature.
#[derive(Debug, Clone)]
pub struct ManualClock(std::sync::Arc<std::sync::Mutex<Instant>>);

impl ManualClock {
    /// A clock reading `start`.
    pub fn new(start: Instant) -> Self {
        ManualClock(std::sync::Arc::new(std::sync::Mutex::new(start)))
    }

    /// Move this clock forward by `by`. Every [`Clock::now`] read through this handle (or a
    /// clone of it) reflects the advance immediately.
    pub fn advance(&self, by: Duration) {
        let mut t = self.0.lock().unwrap_or_else(|e| e.into_inner());
        *t += by;
    }
}

impl Clock for ManualClock {
    fn now(&self) -> Instant {
        *self.0.lock().unwrap_or_else(|e| e.into_inner())
    }
}

/// Whisper.cpp's audio-context horizon, in SAMPLES at [`TARGET_SAMPLE_RATE`] — the longest
/// utterance the real on-device recognizer's encoder can see AT ALL (86akcgmvb). Mirrors
/// `recognizer::whisper_backend::WHISPER_AUDIO_CTX` (576 since 17tnw2b0nkq, 512 before — see
/// that constant's doc for why), which is gated behind the heavy
/// `whisper` feature (native toolchain) so this crate's default, fast test build never needs
/// it — this constant is defined unconditionally instead, and pinned EQUAL to the real one by a
/// compile-time assertion inside `recognizer.rs`'s `whisper` module, so the two values cannot
/// silently drift apart on any build that actually links whisper.cpp, while every other build
/// (including this crate's own default `cargo test`, which is the only gate `selahcue-stt` has
/// at all — see `implementation/desktop/CLAUDE.md`, 86ak5rjh7) can still exercise the runtime
/// guard below with no native toolchain.
///
/// Computed the same way whisper.cpp itself does: `audio_ctx` units are 20 ms each (30 s of
/// context / 1,500 positions), so `audio_ctx / 50` seconds of real audio, in samples at
/// [`TARGET_SAMPLE_RATE`], is `audio_ctx * TARGET_SAMPLE_RATE / 50`. `576 * 16_000 / 50 =
/// 184_320` samples = 11.52 s (at the original 512 it was 163_840 = 10.24 s, the horizon Phase
/// 1's review round, 86akcfp3u, measured). The 10.000 s default `max_utterance_samples` sits
/// 1.52 s under it.
pub(crate) const WHISPER_AUDIO_CTX_HORIZON_SAMPLES: usize = 576 * TARGET_SAMPLE_RATE as usize / 50;

/// Utterance-segmentation tunables.
#[derive(Debug, Clone, Copy)]
pub struct EngineConfig {
    /// Consecutive non-speech frames that close an open utterance (end-of-speech hangover).
    pub hangover_frames: usize,
    /// Minimum voiced frames for an utterance to be worth recognizing (drops lone blips).
    pub min_utterance_frames: usize,
    /// Hard cap on an utterance's samples; unbroken speech is force-closed here so the
    /// accumulator can never grow without bound (no-leak) AND so a sustained monologue still
    /// produces transcript within a bounded delay. Default 10 s gives the recognizer context;
    /// [`interim_interval`](Self::interim_interval) is what gets latency low.
    ///
    /// **Validated at [`SttEngine::build`]/[`SttEngine::build_with_clock`] time (86akcgmvb):** a
    /// value above [`WHISPER_AUDIO_CTX_HORIZON_SAMPLES`] is CLAMPED down to it, because
    /// whisper.cpp's encoder cannot see past that horizon at all — past it, decode cost jumps
    /// ~5x AND the extra audio is silently NOT transcribed (identical output for any input at
    /// or beyond the horizon; see `recognizer.rs`'s `WHISPER_AUDIO_CTX` doc comment for the
    /// measured numbers). See the horizon constant's own doc comment for why this crate can
    /// enforce that without the `whisper` feature's native toolchain.
    pub max_utterance_samples: usize,
    /// Streaming interims: while an utterance is still open, wait AT LEAST this much WALL-CLOCK
    /// time since the last interim's decode COMPLETED (86akcfpbj), then re-transcribe the
    /// growing buffer and emit the result as a NON-final segment (`is_final = false`) — the
    /// "words appearing as you speak" preview. The final on close supersedes it.
    /// `Duration::ZERO` disables interims (the utterance only transcribes once, on close). The
    /// default on-device wiring uses `Duration::from_millis(800)` (`selahcue-operator`'s
    /// `listening.rs`). Costs extra recognizer passes on the open buffer, so it is off in this
    /// struct's own default and enabled by the host that wants it.
    ///
    /// **The REAL steady-state cadence is `interim_interval + decode_time`, not a flat
    /// `interim_interval` (Vera, PR #124 review round 2, corrected from an earlier, wrong
    /// characterization).** The gate is measured from when the PREVIOUS decode finished, not
    /// from when it started — see [`Clock`]'s doc and `process_current_frame`'s stamp site — so
    /// any real decode cost is additive to the wait, for every utterance, not only during a
    /// backlog. This is the direct, honest consequence of closing 86akcfpbj's feedback loop
    /// correctly (a decode that hasn't finished yet cannot be "the last interim" the next wait
    /// counts from) and was chosen deliberately over a hybrid stamp that would preserve a flat
    /// cadence for a fast decode at the cost of reintroducing conditional complexity for a
    /// marginal latency win: it also caps the fraction of wall time spent decoding interims at
    /// `decode_time / (interim_interval + decode_time)` — at most 50% for any `decode_time <=
    /// interim_interval` — versus the pre-86akcfpbj design's measured 82-91% duty cycle right
    /// below the force-close cliff.
    ///
    /// **Wall-clock, not a frame/sample count (86akcfpbj — corrected from the prior design).** A
    /// frame-counted gate fires once N frames of AUDIO POSITION have been processed, which is
    /// only equal to N frames of real time when the recognizer is keeping up. Once it falls
    /// behind (draining a backlog), frames are processed faster than real time, so a frame-
    /// counted gate fires interims MORE often exactly when the system is already behind — a
    /// positive-feedback loop. Gating on [`SttEngine`]'s injected [`Clock`] instead removes that
    /// loop: a burst of frames processed in one call, with no real time elapsing, cannot trigger
    /// more than the interims that real elapsed time actually allows.
    pub interim_interval: Duration,
    /// Cap on the samples an INTERIM re-transcribes: `0` = the whole open utterance (each interim
    /// re-decodes from the utterance start, so cost grows with the utterance — O(n²) over a long
    /// monologue). When `> 0`, an interim decodes only the most-recent this-many samples (a
    /// sliding window), so each interim is BOUNDED work regardless of how long the speaker has
    /// been talking — keeping the live line near real time. The FINAL on close still decodes the
    /// whole utterance for accuracy. Only affects interims; `0` preserves the prior behaviour.
    pub interim_max_samples: usize,
}

impl Default for EngineConfig {
    fn default() -> Self {
        EngineConfig {
            hangover_frames: 15,     // ~300 ms of trailing silence closes an utterance
            min_utterance_frames: 3, // ~60 ms of speech minimum
            max_utterance_samples: 10 * TARGET_SAMPLE_RATE as usize, // 10 s force-close
            interim_interval: Duration::ZERO, // interims off by default (opt-in; see the field docs)
            interim_max_samples: 0, // 0 = whole utterance (prior behaviour); host may bound it
        }
    }
}

/// Why an utterance closed — decides whether its finals get the trailing-repeat trim
/// (17tnw2b0nkq; see `SttEngine::close_utterance`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CloseReason {
    /// The hangover elapsed: the speaker paused (including when the cap was reached on the
    /// same frame — they had already stopped, so nothing was cut off).
    Paused,
    /// [`EngineConfig::max_utterance_samples`] was reached before the hangover had elapsed — the
    /// engine's test is `capped && silence_run < hangover_frames`. That is not the same as "the
    /// speaker was still talking": the trailing `silence_run` may be anywhere from 0 up to
    /// `hangover_frames - 1` frames of silence (a pause shorter than the hangover). What it does
    /// mean is that the cap, not a pause, ended the utterance, so the cut usually lands mid-word.
    /// The only reason whose finals are trimmed.
    ForceClosed,
    /// Closed from outside the VAD loop: [`SttEngine::flush`] (stop) or feedback-guard
    /// suppression. Never trimmed.
    Flushed,
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
    /// Wall-clock source for the interim gate (86akcfpbj) — [`SystemClock`] in production,
    /// swappable in tests. See the module doc's "TWO separate clocks" section.
    clock: Box<dyn Clock + Send>,

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
    /// Processed-frame counter (the transcript clock — audio position, NOT `clock`; see the
    /// module doc).
    frame_index: u64,
    /// Frame index at which the current utterance started.
    utt_start_frame: u64,
    /// Wall-clock instant of the last interim emission for the OPEN utterance (or the instant
    /// it started, if none has fired yet) — drives the interim cadence via `self.clock`
    /// (86akcfpbj). `None` while no utterance is open.
    last_interim_at: Option<Instant>,
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
    /// Uses the real monotonic clock for the interim gate — see [`build_with_clock`](Self::build_with_clock)
    /// to inject a deterministic one (tests).
    pub fn build(
        config: EngineConfig,
        vad: Box<dyn Vad + Send>,
        recognizer: Box<dyn Recognizer + Send>,
        guard: FeedbackGuard,
    ) -> (SttEngine, SttProvider) {
        Self::build_with_clock(config, vad, recognizer, guard, Box::new(SystemClock))
    }

    /// As [`build`](Self::build), with an explicit [`Clock`] for the interim wall-clock gate
    /// (86akcfpbj) — the seam that lets a test control time deterministically instead of this
    /// engine reading `Instant::now()` itself.
    pub fn build_with_clock(
        mut config: EngineConfig,
        vad: Box<dyn Vad + Send>,
        recognizer: Box<dyn Recognizer + Send>,
        guard: FeedbackGuard,
        clock: Box<dyn Clock + Send>,
    ) -> (SttEngine, SttProvider) {
        // 86akcgmvb: a `max_utterance_samples` configured ABOVE whisper.cpp's own audio-context
        // horizon cannot be honoured — the encoder cannot see that far — so the utterance would
        // force-close at a length past the point where more audio produces more text at all,
        // silently. Clamp (not refuse: this is a construction-time invariant to protect, not a
        // caller-supplied resource that might legitimately not exist) so the configured value
        // can never exceed what the recognizer can actually decode. A compile-time-only check
        // cannot do this: `max_utterance_samples` is a RUNTIME field a host (`listening.rs`)
        // sets, not a constant — see `WHISPER_AUDIO_CTX_HORIZON_SAMPLES`'s doc comment.
        if config.max_utterance_samples > WHISPER_AUDIO_CTX_HORIZON_SAMPLES {
            eprintln!(
                "SelahCue STT: configured max_utterance_samples ({}) exceeds the whisper.cpp \
                 audio-context horizon ({WHISPER_AUDIO_CTX_HORIZON_SAMPLES} samples) — clamping \
                 to the horizon so utterances never silently lose trailing words past the \
                 recognizer's own encoder ceiling (86akcgmvb).",
                config.max_utterance_samples
            );
            config.max_utterance_samples = WHISPER_AUDIO_CTX_HORIZON_SAMPLES;
        }
        let sink = SegmentSink::new();
        let label = format!("stt:{}", recognizer.label());
        let engine = SttEngine {
            vad,
            recognizer,
            guard,
            sink: sink.clone(),
            config,
            clock,
            frame_buf: VecDeque::new(),
            frame_scratch: Vec::with_capacity(FRAME_SAMPLES),
            utterance: Vec::new(),
            in_speech: false,
            silence_run: 0,
            speech_frames: 0,
            frame_index: 0,
            utt_start_frame: 0,
            last_interim_at: None,
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
            self.close_utterance(CloseReason::Flushed);
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
        // `now` here is "when this frame arrived" — used for the utterance-start stamp and for
        // the elapsed-time COMPARISON below. It must NOT be reused as the timestamp recorded
        // AFTER an interim fires: that decode can itself take real time, and stamping with the
        // pre-decode `now` was exactly the bug Vera's PR #124 review (F1) found — see the fresh
        // `self.clock.now()` read at the actual stamp site below.
        let now = self.clock.now();
        self.frame_index += 1;
        let speech = self.vad.is_speech(&self.frame_scratch);
        if speech {
            if !self.in_speech {
                self.in_speech = true;
                self.utt_start_frame = self.frame_index - 1;
                self.utterance.clear();
                self.speech_frames = 0;
                self.last_interim_at = Some(now);
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
        let paused = self.silence_run >= self.config.hangover_frames;
        let capped = self.utterance.len() >= self.config.max_utterance_samples;
        if self.in_speech && (paused || capped) {
            // FORCE-closed means the cap, not a pause, ended the utterance: the cap was reached
            // while the trailing silence was still shorter than the hangover
            // (`capped && silence_run < hangover_frames`). That is not literally "still
            // talking" — up to `hangover_frames - 1` frames of the run may be silence. If the
            // hangover elapsed on the same frame, the speaker had already paused, so there is
            // no mid-sentence cut — that is a pause close (17tnw2b0nkq).
            self.close_utterance(if capped && !paused {
                CloseReason::ForceClosed
            } else {
                CloseReason::Paused
            });
        } else if self.in_speech
            && self.config.interim_interval > Duration::ZERO
            && self.speech_frames >= self.config.min_utterance_frames
            && self.last_interim_at.is_some_and(|since| {
                now.saturating_duration_since(since) >= self.config.interim_interval
            })
        {
            // Not closing this frame → emit a streaming interim of the utterance so far. Gated
            // on WALL-CLOCK elapsed time since the last interim (86akcfpbj), not a frame count —
            // see the module doc for why a frame count reintroduces a positive-feedback loop
            // once the recognizer falls behind real time.
            self.emit_interim();
            // Stamp with a FRESH clock read taken AFTER the decode, never the `now` captured at
            // the top of this function before `emit_interim()` ran (Vera, PR #124 review, F1 —
            // blocking). Reusing the pre-decode `now` here is the exact same bug shape 86akcfpbj
            // exists to remove, just moved one line down: once a real decode takes longer than
            // `interim_interval`, that stale timestamp already reads as "overdue" on the very
            // next frame, so a slow decode retriggers immediately, and again, and again — a
            // STRONGER positive-feedback loop than the frame-counted one this ticket replaced,
            // because now each retrigger costs a full decode, not just a cheap counter increment.
            // See `a_slow_decode_does_not_retrigger_before_it_actually_completes` below.
            self.last_interim_at = Some(self.clock.now());
        }
    }

    /// Transcribe the still-open utterance and push it as ONE non-final segment (`is_final =
    /// false`) — the live "words as you speak" line. Re-run on the growing buffer at the config
    /// cadence; the final on close supersedes it. Empty transcripts are dropped.
    fn emit_interim(&mut self) {
        // Decode only the recent window when the host bounds it (interim_max_samples), so each
        // interim is fixed work no matter how long the utterance has grown — the live line stays
        // near real time. `0` decodes the whole open utterance (prior behaviour). The window's
        // start is aligned to a frame boundary so its `start_ms` matches the decoded audio.
        let cap = self.config.interim_max_samples;
        let win_start = if cap > 0 && self.utterance.len() > cap {
            (self.utterance.len() - cap) / FRAME_SAMPLES * FRAME_SAMPLES
        } else {
            0
        };
        let start_ms = (self.utt_start_frame + (win_start / FRAME_SAMPLES) as u64) * MS_PER_FRAME;
        let end_ms = self.frame_index * MS_PER_FRAME;
        let text = self
            .recognizer
            .transcribe(&self.utterance[win_start..], start_ms, end_ms)
            .into_iter()
            .map(|s| s.text)
            .collect::<Vec<_>>()
            .join(" ");
        let text = text.trim();
        if !text.is_empty() {
            self.sink.push(ProviderSegment {
                text: text.to_string(),
                start_ms,
                end_ms,
                is_final: false,
            });
        }
    }

    /// Close the open utterance: recognize it (if long enough) and push its finals to the
    /// sink, then reset speech state, retaining the accumulator's capacity. No-op when not
    /// in speech.
    ///
    /// A [`CloseReason::ForceClosed`] final — one the sample cap closed before the hangover had
    /// elapsed (`capped && silence_run < hangover_frames`, not necessarily "while the speaker was
    /// still talking") — has any trailing back-to-back repeat collapsed by
    /// [`trim_trailing_repeat`] (17tnw2b0nkq). Only there: the cap usually cuts the audio
    /// mid-word, and that abrupt end is where whisper.cpp says the preceding phrase again
    /// (86akcgmuh measured 7.8% of force-closed windows looping vs 0.7% of pause-closed finals).
    /// A pause-closed or flushed final ends where the speaker stopped, so a repeat there is far
    /// more likely to be something they actually said twice — the trim's one known false
    /// positive ("…we worship you, we worship you") — and interims are replaced by the final
    /// anyway. Both are left verbatim.
    ///
    /// ASSUMES ONE SEGMENT PER UTTERANCE. The trim runs on every segment the recognizer returns
    /// for a force-closed utterance, which is only right because the one production recognizer
    /// sets whisper.cpp's `single_segment`, so "per segment" and "per utterance" are the same
    /// thing and the one segment is the one that ends at the cut. If a recognizer ever returns
    /// several segments for one utterance (that setting dropped, or a second backend), only the
    /// LAST of them ends at the cut: restrict the trim to it, or the earlier segments — which
    /// end where the model chose, not where the cap fell — would be trimmed too. (A
    /// `debug_assert!` was considered and rejected: the failure is an over-eager trim, not a
    /// crash, and dev builds must not panic the transcript path over it.)
    fn close_utterance(&mut self, reason: CloseReason) {
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
        self.last_interim_at = None;
        if long_enough {
            // Borrow the accumulator (never move it) so its capacity survives for reuse.
            for seg in self
                .recognizer
                .transcribe(&self.utterance, start_ms, end_ms)
            {
                if seg.text.trim().is_empty() {
                    continue; // never surface an empty transcript line
                }
                let text = match reason {
                    CloseReason::ForceClosed => match trim_trailing_repeat(&seg.text) {
                        Some(trimmed) => {
                            // Counts only — never the transcript text itself.
                            eprintln!(
                                "SelahCue STT: trimmed a trailing repeat from a force-closed \
                                 final ({} -> {} words, 17tnw2b0nkq)",
                                seg.text.split_whitespace().count(),
                                trimmed.split_whitespace().count()
                            );
                            trimmed
                        }
                        None => seg.text,
                    },
                    CloseReason::Paused | CloseReason::Flushed => seg.text,
                };
                self.sink.push(ProviderSegment {
                    text,
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
        self.close_utterance(CloseReason::Flushed);
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
    use crate::recognizer::{FakeRecognizer, RecognizedSegment, Recognizer};
    use crate::vad::EnergyVad;
    use selahcue_core::transcript::TranscriptProvider;
    use std::sync::{Arc, Mutex};

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

    /// As [`engine_with`], with an explicit [`Clock`] — for tests exercising the wall-clock
    /// interim gate (86akcfpbj) deterministically rather than against the real `SystemClock`,
    /// which a fast synthetic test would very likely never advance far enough to trigger at all.
    fn engine_with_clock(
        script: &[&str],
        config: EngineConfig,
        clock: Box<dyn Clock + Send>,
    ) -> (SttEngine, crate::provider::SttProvider) {
        SttEngine::build_with_clock(
            config,
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::with_script(script.iter().copied())),
            FeedbackGuard::new(),
            clock,
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
    fn interims_stream_while_speaking_then_a_final_on_close() {
        // With interims enabled, a still-open utterance emits NON-final previews at the config
        // cadence; the final on close supersedes them. (FakeRecognizer pops one line per call,
        // so script generously — extra calls just return nothing.)
        //
        // Driven ONE FRAME AT A TIME with a `ManualClock` advanced by exactly `MS_PER_FRAME` of
        // real time per frame (86akcfpbj) — mirroring one real capture/recognition cycle at real
        // time — so the wall-clock interim gate fires deterministically. Feeding all 12 frames
        // in a SINGLE `process()` call against the real `SystemClock` (the prior shape of this
        // test, when the gate was a raw frame counter) would very likely never trigger an
        // interim at all: the whole burst executes in well under a millisecond of actual wall
        // time, nowhere near the 100 ms cadence below.
        let script = vec!["a partial line"; 20];
        let clock = ManualClock::new(Instant::now());
        let (mut engine, mut provider) = engine_with_clock(
            &script,
            EngineConfig {
                interim_interval: Duration::from_millis(5 * MS_PER_FRAME), // ~100 ms cadence
                ..EngineConfig::default()
            },
            Box::new(clock.clone()),
        );
        for _ in 0..12 {
            // continuous speech, no pause → interims stream
            engine.process(&speech_chunk(1));
            clock.advance(Duration::from_millis(MS_PER_FRAME));
        }
        let mid = provider.poll();
        assert!(
            !mid.is_empty() && mid.iter().all(|s| !s.is_final),
            "streaming interims (non-final) arrive while still speaking: {mid:?}"
        );
        engine.process(&silence_chunk(20)); // trailing silence → close
        let end = provider.poll();
        assert!(
            end.iter().any(|s| s.is_final),
            "a final (is_final) segment is emitted when the utterance closes: {end:?}"
        );
    }

    #[test]
    fn interim_window_bounds_the_decoded_samples_but_the_final_sees_the_whole_utterance() {
        // The real-time fix: with `interim_max_samples` set, each interim decodes at most the
        // recent window (bounded work no matter how long the speaker talks); the final on close
        // still decodes the whole utterance for accuracy.
        #[derive(Clone)]
        struct Recording(Arc<Mutex<Vec<usize>>>);
        impl Recognizer for Recording {
            fn label(&self) -> &str {
                "recording"
            }
            fn transcribe(&mut self, samples: &[f32], s: u64, e: u64) -> Vec<RecognizedSegment> {
                self.0
                    .lock()
                    .unwrap_or_else(|x| x.into_inner())
                    .push(samples.len());
                vec![RecognizedSegment::final_text("x", s, e)]
            }
        }

        let seen = Arc::new(Mutex::new(Vec::<usize>::new()));
        let window = 4 * FRAME_SAMPLES; // a small 4-frame sliding window for the test
        let clock = ManualClock::new(Instant::now());
        let (mut engine, mut provider) = SttEngine::build_with_clock(
            EngineConfig {
                min_utterance_frames: 1,
                interim_interval: Duration::from_millis(2 * MS_PER_FRAME), // fires every ~2 frames
                interim_max_samples: window,
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(Recording(Arc::clone(&seen))),
            FeedbackGuard::new(),
            Box::new(clock.clone()),
        );
        // Long, unbroken speech, fed ONE FRAME AT A TIME with the clock advanced a real frame's
        // worth of time between each (86akcfpbj) — a single `process(&speech_chunk(30))` call
        // against a real clock would burn through all 30 frames in well under a millisecond of
        // actual wall time, so the wall-clock interim gate would never fire; see
        // `interims_stream_while_speaking_then_a_final_on_close`'s doc comment for the same
        // reasoning in more detail.
        for _ in 0..30 {
            engine.process(&speech_chunk(1));
            clock.advance(Duration::from_millis(MS_PER_FRAME));
        }
        let _ = provider.poll();
        {
            let lens = seen.lock().unwrap();
            assert!(!lens.is_empty(), "interims fired while speaking");
            assert!(
                lens.iter().all(|&n| n <= window),
                "every interim decodes at most the {window}-sample window, got {lens:?}"
            );
        }
        engine.process(&silence_chunk(20)); // close → the final decodes the WHOLE utterance
        let _ = provider.poll();
        let lens = seen.lock().unwrap();
        assert!(
            *lens.last().unwrap() > window,
            "the final decodes the whole utterance (> the interim window): {lens:?}"
        );
    }

    #[test]
    fn a_backlog_burst_fires_zero_interims_when_zero_real_time_elapses() {
        // 86akcfpbj, the bug this whole fix exists for. A recognizer that has fallen behind
        // real time drains buffered audio FASTER than real time in bursts: many frames
        // processed per call, with almost no real wall-clock time elapsing. Under the OLD
        // frame-counted gate this fired interims MORE often, not less, exactly when the system
        // was already behind (positive feedback: falling behind demanded MORE decode work per
        // real second, not less). Simulated here as the limit case — a 100-frame burst with the
        // clock held FIXED throughout (representing zero real time passing during the burst,
        // the same shape as a recognizer catching up on backlog far faster than real time).
        let script = vec!["late line"; 200];
        let clock = ManualClock::new(Instant::now());
        let (mut engine, mut provider) = engine_with_clock(
            &script,
            EngineConfig {
                interim_interval: Duration::from_millis(100),
                ..EngineConfig::default()
            },
            Box::new(clock.clone()),
        );
        engine.process(&speech_chunk(100)); // one burst, clock never advanced during it
        let interims = provider.poll();
        assert!(
            interims.is_empty(),
            "REMOVING the wall-clock gate (reverting to a frame-count gate) must fail this \
             test: with zero real time elapsed during this burst, zero interims may fire — got \
             {} instead: {interims:?}",
            interims.len()
        );
    }

    #[test]
    fn a_slow_decode_does_not_retrigger_before_it_actually_completes() {
        // Vera, PR #124 review (F1, BLOCKING, found by simulation). `last_interim_at` was being
        // stamped with the `now` captured at the TOP of `process_current_frame` — BEFORE
        // `emit_interim()`'s decode ran — not a fresh read taken AFTER the decode completed.
        // Once a real decode takes longer than `interim_interval`, that stale timestamp already
        // reads as "overdue" on the very next frame, so a slow decode retriggers immediately —
        // and does it again, and again — a STRONGER positive-feedback loop than the frame-
        // counted one 86akcfpbj replaced, because now every retrigger costs a full decode, not
        // just a cheap counter increment. Vera's own empirical finding: "a 50-frame backlog
        // after a 1s decode fires 50 more decodes" on the pre-fix code.
        //
        // Reproduced with a recognizer double that advances the SAME `ManualClock` during its
        // own `transcribe()` call — standing in for real decode latency with no actual sleep.
        // Phase 1 (realistic pacing, clock advanced ~20ms/frame): drive the FIRST interim to
        // fire naturally, whose "decode" costs 1s on the shared clock. Phase 2 (a true backlog
        // burst, mirroring the test above — the clock is NOT advanced independently for the
        // rest of this test): feed 50 more frames. On correct code, nothing has happened in
        // real time since the first decode finished, so zero further decodes may fire; on the
        // pre-fix code, the stale pre-decode timestamp makes every one of those 50 frames look
        // overdue, cascading into ~50 more decodes.
        use std::sync::{Arc, Mutex};

        #[derive(Clone)]
        struct SlowRecognizer {
            clock: ManualClock,
            decode_cost: Duration,
            calls: Arc<Mutex<usize>>,
        }
        impl Recognizer for SlowRecognizer {
            fn label(&self) -> &str {
                "slow"
            }
            fn transcribe(
                &mut self,
                _samples: &[f32],
                start_ms: u64,
                end_ms: u64,
            ) -> Vec<RecognizedSegment> {
                *self.calls.lock().unwrap_or_else(|e| e.into_inner()) += 1;
                self.clock.advance(self.decode_cost); // the decode itself taking real time
                vec![RecognizedSegment::final_text("partial", start_ms, end_ms)]
            }
        }

        let clock = ManualClock::new(Instant::now());
        let calls = Arc::new(Mutex::new(0usize));
        let recognizer = SlowRecognizer {
            clock: clock.clone(),
            decode_cost: Duration::from_secs(1),
            calls: Arc::clone(&calls),
        };
        let (mut engine, _provider) = SttEngine::build_with_clock(
            EngineConfig {
                min_utterance_frames: 1,
                interim_interval: Duration::from_millis(100), // short: the first interim fires fast
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(recognizer),
            FeedbackGuard::new(),
            Box::new(clock.clone()),
        );

        // Phase 1: realistic pacing until the first interim fires (~5 frames at 100ms/20ms).
        for _ in 0..6 {
            engine.process(&speech_chunk(1));
            clock.advance(Duration::from_millis(MS_PER_FRAME));
        }
        let fired_after_phase_1 = *calls.lock().unwrap_or_else(|e| e.into_inner());
        assert_eq!(
            fired_after_phase_1, 1,
            "premise: exactly one interim (and its 1s-costing decode) must have fired before \
             this test can prove anything about what happens after it"
        );

        // Phase 2: a true backlog burst — 50 more frames, the clock NOT advanced independently
        // between them (matching `a_backlog_burst_fires_zero_interims_when_zero_real_time_elapses`
        // above). No real time passes beyond what the first decode itself already consumed.
        for _ in 0..50 {
            engine.process(&speech_chunk(1));
        }
        let fired_in_phase_2 =
            *calls.lock().unwrap_or_else(|e| e.into_inner()) - fired_after_phase_1;
        assert_eq!(
            fired_in_phase_2, 0,
            "REMOVING the post-decode timestamp fix must fail this test: with no real time \
             passing beyond what the first 1s decode itself consumed, zero further decodes may \
             fire over the next 50 frames — got {fired_in_phase_2} instead (the pre-fix bug \
             fires ~50, one per frame, because the stale pre-decode timestamp reads every \
             subsequent frame as already overdue)"
        );
    }

    #[test]
    fn steady_state_cadence_is_interim_interval_plus_decode_time() {
        // 86akcfpbj CORRECTED characterization (Vera, PR #124 review round 2, N2). The
        // post-decode stamp (F1's fix — see `process_current_frame`'s stamp site) means the
        // REAL steady-state interim spacing is `interim_interval + decode_time`, not a flat
        // `interim_interval`, for ANY decode_time > 0 — not only during a backlog. This is the
        // direct, honest consequence of correctly closing 86akcfpbj's feedback loop: the
        // interim decode itself is real elapsed time that must pass before the next wait
        // begins. The PRIOR version of this test used `FakeRecognizer` (zero decode time),
        // which cannot see this effect at all — it stayed green whether the stamp was pre- or
        // post-decode, silently leaving the actual cadence formula unverified by any test.
        //
        // Chosen deliberately (Vera + coordinator, PR #124 review round 2) over a hybrid stamp
        // that would preserve a flat cadence for a fast decode at the cost of reintroducing
        // conditional complexity for a marginal latency win: this is the simpler, more honest
        // design, and it caps interim-decode wall-time duty at <= 50% for any `decode_time <=
        // interim_interval`, versus the pre-86akcfpbj design's measured 82-91% duty right below
        // the force-close cliff.
        use std::sync::{Arc, Mutex};

        #[derive(Clone)]
        struct TimestampingRecognizer {
            clock: ManualClock,
            decode_cost: Duration,
            fired_at: Arc<Mutex<Vec<Instant>>>,
        }
        impl Recognizer for TimestampingRecognizer {
            fn label(&self) -> &str {
                "timestamping"
            }
            fn transcribe(
                &mut self,
                _samples: &[f32],
                start_ms: u64,
                end_ms: u64,
            ) -> Vec<RecognizedSegment> {
                self.fired_at
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .push(self.clock.now());
                self.clock.advance(self.decode_cost); // the decode itself taking real time
                vec![RecognizedSegment::final_text("partial", start_ms, end_ms)]
            }
        }

        let clock = ManualClock::new(Instant::now());
        let fired_at = Arc::new(Mutex::new(Vec::new()));
        let decode_cost = Duration::from_millis(50);
        let interim_interval = Duration::from_millis(800);
        let recognizer = TimestampingRecognizer {
            clock: clock.clone(),
            decode_cost,
            fired_at: Arc::clone(&fired_at),
        };
        let (mut engine, _provider) = SttEngine::build_with_clock(
            EngineConfig {
                interim_interval,
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(recognizer),
            FeedbackGuard::new(),
            Box::new(clock.clone()),
        );

        // Real-time-paced speech for comfortably more than the cycle length (interim_interval +
        // decode_cost each), so at least a few gaps between consecutive decodes can be measured.
        let cycle = interim_interval + decode_cost; // 850ms
        let frames = (cycle.as_millis() as u64 * 5) / MS_PER_FRAME;
        for _ in 0..frames {
            engine.process(&speech_chunk(1));
            clock.advance(Duration::from_millis(MS_PER_FRAME));
        }

        let stamps = fired_at.lock().unwrap_or_else(|e| e.into_inner());
        assert!(
            stamps.len() >= 3,
            "premise: need at least 3 decodes to measure 2 gaps, got {}",
            stamps.len()
        );
        // ±1 frame of slack for the discrete 20ms frame-pacing granularity.
        let slack = Duration::from_millis(MS_PER_FRAME);
        let low = cycle.saturating_sub(slack);
        let high = cycle + slack;
        for w in stamps.windows(2) {
            let gap = w[1].duration_since(w[0]);
            assert!(
                gap >= low && gap <= high,
                "REMOVING the post-decode stamp (F1's fix) must fail this test: consecutive \
                 interim decodes must be spaced interim_interval + decode_time (~{cycle:?} \
                 here), got {gap:?} (expected {low:?}..={high:?}) — a gap near \
                 {interim_interval:?} instead means the OLD, pre-fix flat-cadence behaviour \
                 came back"
            );
        }
    }

    #[test]
    fn interims_off_by_default_only_a_final_on_close() {
        let (mut engine, mut provider) = engine_with(&["the whole line"], EngineConfig::default());
        engine.process(&speech_chunk(30)); // long speech, but interims are OFF by default
        assert!(
            provider.poll().is_empty(),
            "no interims stream with the default config (nothing until close)"
        );
        engine.process(&silence_chunk(20));
        let out = provider.poll();
        assert_eq!(out.len(), 1);
        assert!(out[0].is_final);
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

    // --- 17tnw2b0nkq: the trailing-repeat trim applies ONLY to force-closed finals -----------

    /// A trailing loop exactly as whisper.cpp produced it on a force-closed window (86akcgmuh
    /// repro fixture A), and the single-copy form the trim must turn it into.
    const LOOPED: &str =
        "Ask them how they are really doing, and then wait long and then wait long \
                          and then wait";
    const TRIMMED: &str = "Ask them how they are really doing, and then wait long";

    /// Speech frames that make an utterance exactly reach the default force-close cap.
    fn frames_to_force_close() -> usize {
        EngineConfig::default().max_utterance_samples / FRAME_SAMPLES
    }

    /// The one final a single utterance produced, asserting it is the only segment.
    fn only_final(provider: &mut crate::provider::SttProvider, case: &str) -> ProviderSegment {
        let mut out = provider.poll();
        assert_eq!(
            out.len(),
            1,
            "{case}: expected exactly one segment, got {out:?}"
        );
        let seg = out.remove(0);
        assert!(seg.is_final, "{case}: expected a final, got {seg:?}");
        seg
    }

    /// 17tnw2b0nkq: a final the engine FORCE-CLOSED at its sample cap has a trailing
    /// back-to-back repeat collapsed to its first copy — and nothing else is touched: the same
    /// looped text on a final closed by the pause (hangover), by `flush()`, or by the hangover and
    /// the cap on the same frame, and on an interim, comes through verbatim; and legitimate
    /// repetition on a force-closed final comes through verbatim too.
    #[test]
    fn the_trailing_repeat_trim_applies_only_to_force_closed_finals() {
        let cap_frames = frames_to_force_close();

        // Force-closed final: continuous speech straight to the cap → trimmed.
        let (mut engine, mut provider) = engine_with(&[LOOPED], EngineConfig::default());
        engine.process(&speech_chunk(cap_frames));
        let seg = only_final(&mut provider, "force-closed");
        assert_eq!(
            seg.end_ms - seg.start_ms,
            (cap_frames as u64) * MS_PER_FRAME,
            "premise: this final must have been closed by the sample cap, not a pause"
        );
        assert_eq!(
            seg.text, TRIMMED,
            "a force-closed final's trailing loop must be trimmed"
        );

        // (a) Pause-closed final with identical text → untouched.
        let (mut engine, mut provider) = engine_with(&[LOOPED], EngineConfig::default());
        engine.process(&speech_chunk(100));
        engine.process(&silence_chunk(20));
        let seg = only_final(&mut provider, "pause-closed");
        assert_eq!(
            seg.text, LOOPED,
            "a pause-closed final must never be trimmed"
        );

        // (a') The hangover and the cap on the SAME frame: the speaker had already paused, so
        // there is no mid-word cut — treated as pause-closed → untouched.
        let hangover = EngineConfig::default().hangover_frames;
        let (mut engine, mut provider) = engine_with(&[LOOPED], EngineConfig::default());
        engine.process(&speech_chunk(cap_frames - hangover));
        engine.process(&silence_chunk(hangover));
        let seg = only_final(&mut provider, "hangover+cap");
        assert_eq!(
            seg.end_ms - seg.start_ms,
            (cap_frames as u64) * MS_PER_FRAME,
            "premise: the cap must be reached on the very frame the hangover elapses"
        );
        assert_eq!(
            seg.text, LOOPED,
            "a final whose speaker had already paused must not be trimmed"
        );

        // (a'') Closed by `flush()` (stop) → untouched.
        let (mut engine, mut provider) = engine_with(&[LOOPED], EngineConfig::default());
        engine.process(&speech_chunk(100));
        engine.flush();
        let seg = only_final(&mut provider, "flush-closed");
        assert_eq!(
            seg.text, LOOPED,
            "a flush()-closed final must not be trimmed"
        );

        // (b) Interims with identical text → untouched.
        let clock = ManualClock::new(Instant::now());
        let script = vec![LOOPED; 20];
        let (mut engine, mut provider) = engine_with_clock(
            &script,
            EngineConfig {
                interim_interval: Duration::from_millis(5 * MS_PER_FRAME),
                ..EngineConfig::default()
            },
            Box::new(clock.clone()),
        );
        for _ in 0..12 {
            engine.process(&speech_chunk(1));
            clock.advance(Duration::from_millis(MS_PER_FRAME));
        }
        let interims = provider.poll();
        assert!(
            !interims.is_empty() && interims.iter().all(|s| !s.is_final),
            "premise: interims must have been emitted, got {interims:?}"
        );
        for s in &interims {
            assert_eq!(s.text, LOOPED, "an interim must never be trimmed");
        }

        // (c) Legitimate repetition on a FORCE-CLOSED final → untouched.
        for legit in [
            "Holy, holy, holy is the Lord God Almighty, who was and who is and who is to come.",
            "Give thanks to the God of gods; for his loving kindness endures forever. Give thanks \
             to the Lord of lords; for his loving kindness endures forever.",
            "He is faithful when the harvest is plentiful, and he is faithful when the field is bare.",
            "so we say amen, amen",
        ] {
            let (mut engine, mut provider) = engine_with(&[legit], EngineConfig::default());
            engine.process(&speech_chunk(cap_frames));
            let seg = only_final(&mut provider, "force-closed legitimate");
            assert_eq!(seg.text, legit, "legitimate repetition was altered on a force-closed final");
        }
    }

    /// 17tnw2b0nkq review: the close that feedback-guard suppression triggers
    /// (`CloseReason::Flushed`, in `process`) is not a force-close and must not be trimmed. The
    /// `flush()` case above never reaches that call site, and it is the close most easily
    /// mistaken for a forced one: the audio stops partway through a long utterance, so the text
    /// ends at the point of the cut. Mutation check: passing `CloseReason::ForceClosed` at that
    /// call site makes this test fail on the verbatim assertion.
    #[test]
    fn a_feedback_guard_suppression_close_is_never_trimmed() {
        let cap_frames = frames_to_force_close();
        let guard = FeedbackGuard::new();
        let (mut engine, mut provider) = SttEngine::build(
            EngineConfig::default(),
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::with_script([LOOPED])),
            guard.clone(),
        );
        // Premise: this is exactly the text the trim collapses on a force-closed final, so
        // "comes through verbatim" below is the engine's choice, not an untrimmable string.
        assert_eq!(
            crate::repetition::trim_trailing_repeat(LOOPED).as_deref(),
            Some(TRIMMED)
        );

        // Long speech that stops one frame short of the cap: nothing has closed yet.
        engine.process(&speech_chunk(cap_frames - 1));
        assert!(
            provider.poll().is_empty(),
            "premise: the utterance must still be open"
        );

        // The app starts playing on the shared output: the next chunk is dropped and the open
        // utterance is closed by the suppression, not by the cap or a pause.
        guard.set_output_active(true);
        engine.process(&speech_chunk(1));
        let seg = only_final(&mut provider, "suppression-closed");
        assert_eq!(
            seg.end_ms - seg.start_ms,
            (cap_frames as u64 - 1) * MS_PER_FRAME,
            "premise: this final must have been closed by the suppression, one frame short of \
             the cap"
        );
        assert_eq!(
            seg.text, LOOPED,
            "a final closed by feedback-guard suppression must never be trimmed"
        );
    }

    /// 17tnw2b0nkq review: the trim's word comparison used to delete every non-ASCII letter, so
    /// a force-closed final of different Yoruba words could read as a loop and lose real words.
    /// Through the engine: a line of alternating distinct non-ASCII words and a line of tone-only
    /// minimal pairs come through verbatim, while a real code-switched Yoruba loop is trimmed
    /// (the positive control: "never trims non-ASCII" would otherwise pass vacuously). Texts are
    /// written with \u escapes so the test pins which Unicode form reaches the engine.
    #[test]
    fn the_trailing_repeat_trim_does_not_mistake_distinct_non_ascii_words_for_a_loop() {
        let cap_frames = frames_to_force_close();
        let run = |text: &str| {
            let (mut engine, mut provider) = engine_with(&[text], EngineConfig::default());
            engine.process(&speech_chunk(cap_frames));
            only_final(&mut provider, "force-closed non-ASCII").text
        };

        // The review's reproduction: "ọlọ ẹlẹ ọlọ ẹlẹ ọlọ ẹlẹ" (it used to come back as
        // "ọlọ ẹlẹ ọlọ"), in precomposed form and in decomposed form.
        for distinct in [
            "\u{1ECD}l\u{1ECD} \u{1EB9}l\u{1EB9} \u{1ECD}l\u{1ECD} \u{1EB9}l\u{1EB9} \u{1ECD}l\u{1ECD} \u{1EB9}l\u{1EB9}",
            "o\u{323}lo\u{323} e\u{323}le\u{323} o\u{323}lo\u{323} e\u{323}le\u{323} o\u{323}lo\u{323} e\u{323}le\u{323}",
            // six different words that differ only in their tone mark
            "ba\u{300} ba\u{301} be\u{300} bi\u{300} bo\u{300} bu\u{300}",
        ] {
            assert_eq!(run(distinct), distinct, "distinct non-ASCII words were trimmed");
        }

        // A real loop, with the repeated copies spelled in different normalisation forms.
        let phrase = "\u{1ECD}l\u{1ECD}\u{301}run ni \u{1ECD}ba wa";
        let phrase_nfd = "o\u{323}lo\u{323}\u{301}run ni o\u{323}ba wa";
        let looped =
            format!("Let us say it together, {phrase} {phrase_nfd} o\u{323}lo\u{323}\u{301}run ni");
        assert_eq!(
            run(&looped),
            format!("Let us say it together, {phrase}"),
            "a real Yoruba loop must still be trimmed to its first copy"
        );
    }

    // --- 86akcgmvb: max_utterance_samples vs the whisper.cpp audio-context horizon ----------

    /// A recognizer double reproducing whisper.cpp's REAL ctx-cliff failure mode: content past
    /// a fixed sample horizon is invisible to the (real) encoder, so any input AT or BEYOND the
    /// horizon decodes to the exact same output as an input of exactly the horizon's length —
    /// a plateau, not a gradual truncation. Also records every input length it was actually
    /// called with, so a test can assert on what the engine handed it, not just on the text
    /// that came back.
    #[derive(Clone)]
    struct CtxLimitedFakeRecognizer {
        horizon: usize,
        seen_lens: Arc<Mutex<Vec<usize>>>,
    }

    impl CtxLimitedFakeRecognizer {
        fn new(horizon: usize) -> Self {
            CtxLimitedFakeRecognizer {
                horizon,
                seen_lens: Arc::new(Mutex::new(Vec::new())),
            }
        }
    }

    impl Recognizer for CtxLimitedFakeRecognizer {
        fn label(&self) -> &str {
            "ctx-limited-fake"
        }
        fn transcribe(
            &mut self,
            samples: &[f32],
            start_ms: u64,
            end_ms: u64,
        ) -> Vec<RecognizedSegment> {
            self.seen_lens
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .push(samples.len());
            let effective_len = samples.len().min(self.horizon);
            vec![RecognizedSegment::final_text(
                format!("len={effective_len}"),
                start_ms,
                end_ms,
            )]
        }
    }

    #[test]
    fn the_ctx_limited_fake_reproduces_the_real_truncation_plateau() {
        // Proves the double's fidelity to the REAL bug before relying on it below — "the
        // guard's target is proven, not assumed" (86akcgmvb's acceptance criteria). Calls the
        // recognizer directly, no `SttEngine` involved, mirroring the ticket's own measured
        // finding: whisper.cpp's real 10.24s/10.5s/11.0s inputs returned an IDENTICAL 183
        // characters — content past the horizon produces zero additional text, silently.
        let horizon = 1_000;
        let mut rec = CtxLimitedFakeRecognizer::new(horizon);
        let at_horizon = rec.transcribe(&vec![0.0; horizon], 0, 1);
        let past_horizon = rec.transcribe(&vec![0.0; horizon + 500], 0, 1);
        let far_past_horizon = rec.transcribe(&vec![0.0; horizon * 3], 0, 1);
        assert_eq!(
            at_horizon[0].text, past_horizon[0].text,
            "content past the horizon must produce IDENTICAL output to content at exactly the \
             horizon — a plateau, not a gradual truncation — matching the real whisper.cpp \
             finding this double stands in for"
        );
        assert_eq!(at_horizon[0].text, far_past_horizon[0].text);
        assert_eq!(at_horizon[0].text, format!("len={horizon}"));
    }

    #[test]
    fn the_default_max_utterance_samples_stays_under_the_whisper_ctx_horizon() {
        // 86akcgmvb's "sooner, weaker guard" (Cody, re-review): unlike the construction-time
        // clamp below, this touches ZERO lines of production code and guards the DEFAULT
        // specifically — not a synthetic over/under value picked by the test — so a future edit
        // that raises `EngineConfig::default().max_utterance_samples` (or shrinks
        // `WHISPER_AUDIO_CTX_HORIZON_SAMPLES`) without noticing the margin has closed is caught
        // here directly. Its own stated limit (from the ticket): this guards only the DEFAULT,
        // not a host override such as `listening.rs`'s own `EngineConfig` construction — the
        // clamp tests below are what cover a runtime-configured value.
        let default_cap = EngineConfig::default().max_utterance_samples;
        assert!(
            default_cap < WHISPER_AUDIO_CTX_HORIZON_SAMPLES,
            "the default max_utterance_samples ({default_cap}) must stay under the whisper.cpp \
             audio-context horizon ({WHISPER_AUDIO_CTX_HORIZON_SAMPLES} samples), or \
             production's own DEFAULT configuration would already be silently dropping \
             trailing words even before any host applies an override"
        );
    }

    #[test]
    fn max_utterance_samples_above_the_horizon_is_clamped_at_construction() {
        let over = WHISPER_AUDIO_CTX_HORIZON_SAMPLES + 16_000; // comfortably above the horizon
        let (engine, _provider) = SttEngine::build(
            EngineConfig {
                max_utterance_samples: over,
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::new()),
            FeedbackGuard::new(),
        );
        assert_eq!(
            engine.config.max_utterance_samples, WHISPER_AUDIO_CTX_HORIZON_SAMPLES,
            "REMOVING the construction-time clamp must fail this test: a configured ceiling \
             above the whisper.cpp audio-context horizon must never reach the running engine \
             unchanged (86akcgmvb)"
        );
    }

    #[test]
    fn a_benign_max_utterance_samples_passes_through_unclamped() {
        // POSITIVE CONTROL: without this, the clamp test above could be satisfied by a
        // constructor that clamps EVERY value, not just over-horizon ones.
        let benign = WHISPER_AUDIO_CTX_HORIZON_SAMPLES - 16_000;
        let (engine, _provider) = SttEngine::build(
            EngineConfig {
                max_utterance_samples: benign,
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(FakeRecognizer::new()),
            FeedbackGuard::new(),
        );
        assert_eq!(
            engine.config.max_utterance_samples, benign,
            "an in-bounds max_utterance_samples must pass through UNCHANGED, not be clamped"
        );
    }

    #[test]
    fn the_clamp_keeps_every_utterance_handed_to_the_recognizer_at_or_under_the_horizon() {
        // End to end: build an engine with `max_utterance_samples` requested WELL above the
        // horizon (pre-clamp), feed it much more than the horizon's worth of continuous speech
        // with no pause, and confirm the recognizer NEVER sees an input longer than the horizon
        // — proving the clamp actually reaches the force-close boundary, not just the stored
        // config value.
        let horizon = WHISPER_AUDIO_CTX_HORIZON_SAMPLES;
        let rec = CtxLimitedFakeRecognizer::new(horizon);
        let seen_lens = Arc::clone(&rec.seen_lens);
        let (mut engine, mut provider) = SttEngine::build(
            EngineConfig {
                hangover_frames: 1_000, // effectively disables hangover-triggered close here
                min_utterance_frames: 1,
                max_utterance_samples: horizon * 4, // requested well above the horizon
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(rec),
            FeedbackGuard::new(),
        );
        // Continuous speech totalling well over 2x the horizon, no pause — force-closes only on
        // the (clamped) sample cap, three times exactly at the horizon, plus a trailing partial
        // utterance `flush()` closes below.
        let total_samples = horizon * 3;
        let frames = total_samples / FRAME_SAMPLES + 1;
        engine.process(&speech_chunk(frames));
        engine.flush();
        let _ = provider.poll();

        let lens = seen_lens.lock().unwrap_or_else(|e| e.into_inner());
        assert!(
            !lens.is_empty(),
            "premise: the recognizer must have been called at least once"
        );
        assert!(
            lens.iter().all(|&n| n <= horizon),
            "REMOVING the construction-time clamp must fail this test: an utterance longer than \
             the whisper.cpp audio-context horizon reached the recognizer — got lengths {lens:?} \
             against horizon {horizon}"
        );
    }
}
