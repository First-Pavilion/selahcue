//! Voice-activity detection (FR-102): decide, per fixed-length 16 kHz frame, whether it
//! contains speech, so the recognizer only ever runs on speech and silence never produces
//! empty/garbage segments.
//!
//! [`Vad`] is the seam; [`EnergyVad`] is a pure-Rust energy + zero-crossing gate — no model,
//! no dependency, deterministic. A better VAD (WebRTC/Silero) is a drop-in behind the trait
//! later. The engine consults it frame-by-frame to bracket utterances (see
//! [`crate::engine`]).

/// One VAD frame length at 16 kHz. 20 ms is the standard analysis frame for speech VAD.
pub const FRAME_SAMPLES: usize = 320; // 20 ms @ 16 kHz

/// The speech/non-speech decision seam. Given one 16 kHz mono frame, return whether it is
/// speech. Implementations must be deterministic (same frame → same answer).
pub trait Vad {
    /// `true` if `frame` (16 kHz mono `f32`) is judged to contain speech.
    fn is_speech(&self, frame: &[f32]) -> bool;
}

/// Tunables for [`EnergyVad`].
#[derive(Debug, Clone, Copy)]
pub struct VadConfig {
    /// RMS energy above which a frame is considered voiced. Speech RMS is typically well
    /// above room-tone; 0.01 (~ -40 dBFS) is a conservative default.
    pub energy_threshold: f32,
    /// Minimum zero-crossing rate (fraction of adjacent-sample sign changes). Rejects a
    /// steady DC offset or a very-low-frequency hum/feedback tone that clears the energy
    /// floor but barely oscillates — such a frame is not speech. The default (0.02) is a
    /// conservative floor that passes ordinary speech; the exact value is a VAD-accuracy
    /// tuning concern carried by the spike (S8/S11).
    pub min_zero_crossing_rate: f32,
}

impl Default for VadConfig {
    fn default() -> Self {
        VadConfig {
            energy_threshold: 0.01,
            min_zero_crossing_rate: 0.02,
        }
    }
}

/// A dependency-free energy + zero-crossing VAD. A frame is speech when its RMS energy
/// exceeds [`VadConfig::energy_threshold`] and its zero-crossing rate is at least
/// [`VadConfig::min_zero_crossing_rate`].
#[derive(Debug, Clone, Copy, Default)]
pub struct EnergyVad {
    config: VadConfig,
}

impl EnergyVad {
    /// A VAD with the default config.
    pub fn new() -> Self {
        EnergyVad {
            config: VadConfig::default(),
        }
    }

    /// A VAD with an explicit config.
    pub fn with_config(config: VadConfig) -> Self {
        EnergyVad { config }
    }

    /// Root-mean-square energy of a frame.
    fn rms(frame: &[f32]) -> f32 {
        if frame.is_empty() {
            return 0.0;
        }
        let sum_sq: f32 = frame.iter().map(|s| s * s).sum();
        (sum_sq / frame.len() as f32).sqrt()
    }

    /// Zero-crossing rate: fraction of adjacent-sample sign changes.
    fn zero_crossing_rate(frame: &[f32]) -> f32 {
        if frame.len() < 2 {
            return 0.0;
        }
        let crossings = frame
            .windows(2)
            .filter(|w| (w[0] >= 0.0) != (w[1] >= 0.0))
            .count();
        crossings as f32 / (frame.len() - 1) as f32
    }
}

impl Vad for EnergyVad {
    fn is_speech(&self, frame: &[f32]) -> bool {
        if frame.is_empty() {
            return false;
        }
        let energy = Self::rms(frame);
        if energy < self.config.energy_threshold {
            return false;
        }
        Self::zero_crossing_rate(frame) >= self.config.min_zero_crossing_rate
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tone(len: usize, amp: f32) -> Vec<f32> {
        // A simple alternating waveform: nonzero energy + zero-crossings (speech-like).
        (0..len)
            .map(|i| if i % 2 == 0 { amp } else { -amp })
            .collect()
    }

    #[test]
    fn silence_is_not_speech() {
        let vad = EnergyVad::new();
        assert!(!vad.is_speech(&vec![0.0; FRAME_SAMPLES]));
    }

    #[test]
    fn loud_tone_is_speech() {
        let vad = EnergyVad::new();
        assert!(vad.is_speech(&tone(FRAME_SAMPLES, 0.5)));
    }

    #[test]
    fn very_quiet_tone_is_not_speech() {
        let vad = EnergyVad::new();
        // Below the 0.01 RMS floor.
        assert!(!vad.is_speech(&tone(FRAME_SAMPLES, 0.001)));
    }

    #[test]
    fn empty_frame_is_not_speech() {
        assert!(!EnergyVad::new().is_speech(&[]));
    }

    #[test]
    fn loud_dc_offset_is_not_speech() {
        // A constant (DC) frame clears the energy floor (RMS 0.5 ≫ 0.01) but has zero
        // crossings — the ZCR guard must reject it (FR-102), so the recognizer never runs
        // on a hum/feedback offset. This exercises the ZCR dimension of the gate.
        let vad = EnergyVad::new();
        assert!(!vad.is_speech(&vec![0.5; FRAME_SAMPLES]));
    }

    #[test]
    fn oscillating_speech_passes_the_zcr_floor() {
        // An alternating (max-ZCR) loud frame is speech under the default ZCR floor.
        let vad = EnergyVad::new();
        assert!(vad.is_speech(&tone(FRAME_SAMPLES, 0.5)));
    }
}
