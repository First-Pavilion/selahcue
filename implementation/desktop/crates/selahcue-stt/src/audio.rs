//! Audio capture seam + a bounded PCM ring.
//!
//! [`AudioSource`] is the trait the engine pulls raw device audio from. The default,
//! always-available implementation is [`FakeAudioSource`] (fixture PCM), so the whole
//! pipeline is testable with no microphone. [`CpalSource`] (feature `capture`) is the real
//! device implementation.
//!
//! [`PcmRing`] is a hard-capped ring buffer for raw samples: the capture callback pushes
//! into it and the worker drains it, and a burst that outpaces the worker drops the oldest
//! samples rather than growing without bound (no-leak invariant).

use std::collections::VecDeque;

/// A chunk of interleaved PCM samples straight off a device (before resample/downmix).
#[derive(Debug, Clone, PartialEq)]
pub struct AudioChunk {
    /// Interleaved `f32` samples in `[-1, 1]`, `channels`-interleaved.
    pub samples: Vec<f32>,
    /// The device sample rate this chunk was captured at (Hz).
    pub sample_rate: u32,
    /// Channel count (1 = mono, 2 = stereo, …).
    pub channels: u16,
}

impl AudioChunk {
    /// A chunk with the given interleaved samples and format.
    pub fn new(samples: Vec<f32>, sample_rate: u32, channels: u16) -> Self {
        AudioChunk {
            samples,
            sample_rate,
            channels: channels.max(1),
        }
    }
}

/// A pull-based source of device audio. `next_chunk` is non-blocking: it returns whatever
/// audio is available since the last call, or `None` when there is nothing new. The engine
/// polls it on the worker thread; it never blocks the host/render thread.
pub trait AudioSource {
    /// A stable, human-readable source name (e.g. `"cpal:default"` or `"fake"`).
    fn label(&self) -> &str;

    /// Return the next available chunk, or `None` if no new audio is ready.
    fn next_chunk(&mut self) -> Option<AudioChunk>;
}

/// Upper bound on samples retained in a [`PcmRing`]. The capture callback and the worker
/// run at different rates; this caps the buffer so a stalled worker cannot let the ring
/// grow without limit (30 s at 48 kHz stereo ≈ this bound).
pub const MAX_PCM_SAMPLES: usize = 48_000 * 2 * 30;

/// A hard-capped ring of raw interleaved samples. `push` appends and evicts the oldest
/// samples once [`MAX_PCM_SAMPLES`] is exceeded, so `len()` is bounded for any input volume.
#[derive(Debug, Clone, Default)]
pub struct PcmRing {
    samples: VecDeque<f32>,
    cap: usize,
    /// Samples dropped to stay within the cap (observability; a nonzero value means the
    /// worker is not keeping up).
    dropped: u64,
}

impl PcmRing {
    /// A ring bounded to [`MAX_PCM_SAMPLES`].
    pub fn new() -> Self {
        PcmRing::with_capacity(MAX_PCM_SAMPLES)
    }

    /// A ring bounded to `cap` samples (`cap` is forced to at least 1).
    pub fn with_capacity(cap: usize) -> Self {
        PcmRing {
            samples: VecDeque::new(),
            cap: cap.max(1),
            dropped: 0,
        }
    }

    /// Append `chunk`, evicting the oldest samples to stay within the cap.
    pub fn push(&mut self, chunk: &[f32]) {
        self.samples.extend(chunk.iter().copied());
        while self.samples.len() > self.cap {
            self.samples.pop_front();
            self.dropped = self.dropped.saturating_add(1);
        }
    }

    /// Drain and return every retained sample, in order, leaving the ring empty.
    pub fn drain(&mut self) -> Vec<f32> {
        self.samples.drain(..).collect()
    }

    /// Number of retained samples (never exceeds the cap).
    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    /// Total samples dropped to stay within the cap since construction.
    pub fn dropped(&self) -> u64 {
        self.dropped
    }
}

/// A deterministic, always-available [`AudioSource`] that replays pre-supplied chunks.
///
/// This is the default source for tests and any offline/headless run: `next_chunk` returns
/// each queued chunk once, in order, then `None`. No device, no clock, fully reproducible.
#[derive(Debug, Clone, Default)]
pub struct FakeAudioSource {
    chunks: VecDeque<AudioChunk>,
}

impl FakeAudioSource {
    /// An empty source.
    pub fn new() -> Self {
        FakeAudioSource {
            chunks: VecDeque::new(),
        }
    }

    /// A source pre-loaded with `chunks`, returned in order.
    pub fn with_chunks(chunks: impl IntoIterator<Item = AudioChunk>) -> Self {
        FakeAudioSource {
            chunks: chunks.into_iter().collect(),
        }
    }

    /// Queue one more chunk to be returned by a later `next_chunk`.
    pub fn push_chunk(&mut self, chunk: AudioChunk) {
        self.chunks.push_back(chunk);
    }
}

impl AudioSource for FakeAudioSource {
    fn label(&self) -> &str {
        "fake"
    }

    fn next_chunk(&mut self) -> Option<AudioChunk> {
        self.chunks.pop_front()
    }
}

/// Peak amplitude (max `|sample|`, in `0..=1`) of a raw f32 buffer. Used as a live
/// microphone-level readout so the operator can tell "listening but no audio arriving"
/// (peak stays 0 — e.g. denied mic permission, which yields silence, not an error) from
/// "audio arriving but nothing recognised yet". Pure + always compiled (testable without a
/// device).
pub fn frame_peak(samples: &[f32]) -> f32 {
    samples.iter().fold(0.0f32, |m, &s| m.max(s.abs()))
}

#[cfg(feature = "capture")]
pub use cpal_source::CpalSource;

#[cfg(feature = "capture")]
mod cpal_source {
    //! Real microphone capture via `cpal`. Compiled only under the `capture` feature so the
    //! default build/tests need no audio device or platform audio libraries.

    use super::{frame_peak, AudioChunk, AudioSource, PcmRing};
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::{Arc, Mutex};

    use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

    /// Live capture from the default input device. The cpal callback pushes samples into a
    /// shared [`PcmRing`] (bounded — a stalled consumer drops oldest, never grows); the
    /// engine pulls them via [`AudioSource::next_chunk`].
    pub struct CpalSource {
        label: String,
        sample_rate: u32,
        channels: u16,
        ring: Arc<Mutex<PcmRing>>,
        // Running peak amplitude since the last `peak_level()` read (f32 bits), updated by the
        // capture callback — a live "is the mic actually delivering audio?" signal.
        peak: Arc<AtomicU32>,
        // Held to keep the stream alive; dropping it stops capture.
        _stream: cpal::Stream,
    }

    impl CpalSource {
        /// Open the default input device and start capturing.
        pub fn new() -> Result<Self, String> {
            let host = cpal::default_host();
            let device = host
                .default_input_device()
                .ok_or_else(|| "no default input device".to_string())?;
            let name = device.name().unwrap_or_else(|_| "input".to_string());
            let config = device
                .default_input_config()
                .map_err(|e| format!("default input config: {e}"))?;
            let sample_rate = config.sample_rate().0;
            let channels = config.channels();
            let ring = Arc::new(Mutex::new(PcmRing::new()));
            let cb_ring = Arc::clone(&ring);
            let peak = Arc::new(AtomicU32::new(0));
            let cb_peak = Arc::clone(&peak);
            let err_fn = |e| eprintln!("cpal stream error: {e}");
            // Only the f32 sample format is wired here; other formats fall through as an
            // honest error rather than silently mis-decoding.
            let stream = match config.sample_format() {
                cpal::SampleFormat::F32 => device.build_input_stream(
                    &config.into(),
                    move |data: &[f32], _| {
                        // Accumulate the peak since the last read (max), so a level poll can
                        // never miss a transient between polls.
                        let p = frame_peak(data);
                        if p > f32::from_bits(cb_peak.load(Ordering::Relaxed)) {
                            cb_peak.store(p.to_bits(), Ordering::Relaxed);
                        }
                        if let Ok(mut r) = cb_ring.lock() {
                            r.push(data);
                        }
                    },
                    err_fn,
                    None,
                ),
                other => return Err(format!("unsupported sample format: {other:?}")),
            }
            .map_err(|e| format!("build_input_stream: {e}"))?;
            stream.play().map_err(|e| format!("stream play: {e}"))?;
            Ok(CpalSource {
                label: format!("cpal:{name}"),
                sample_rate,
                channels,
                ring,
                peak,
                _stream: stream,
            })
        }

        /// Peak input amplitude (`0..=1`) observed since the previous call, then reset — a
        /// live mic-level readout for the operator's "waiting for speech…" diagnostic.
        pub fn peak_level(&self) -> f32 {
            f32::from_bits(self.peak.swap(0, Ordering::Relaxed))
        }
    }

    impl AudioSource for CpalSource {
        fn label(&self) -> &str {
            &self.label
        }

        fn next_chunk(&mut self) -> Option<AudioChunk> {
            let mut ring = self.ring.lock().unwrap_or_else(|e| e.into_inner());
            if ring.is_empty() {
                return None;
            }
            let samples = ring.drain();
            Some(AudioChunk::new(samples, self.sample_rate, self.channels))
        }
    }
}
