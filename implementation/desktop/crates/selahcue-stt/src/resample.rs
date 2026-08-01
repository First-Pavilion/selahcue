//! Downmix + resample device audio to the recognizer's 16 kHz mono `f32` format.
//!
//! whisper.cpp consumes 16 kHz mono. Device audio is typically 44.1/48 kHz and often
//! stereo, so each chunk is (1) downmixed to mono by averaging channels, then (2)
//! linearly resampled to [`crate::TARGET_SAMPLE_RATE`]. Linear interpolation is cheap,
//! deterministic, and good enough for speech VAD/recognition; a higher-quality resampler
//! is a drop-in later. The function is pure — same input, same output — so it is exhaustively
//! unit-testable with no audio hardware.

use crate::TARGET_SAMPLE_RATE;

/// Downmix interleaved `samples` (`channels`-interleaved, at `in_rate` Hz) to mono and
/// resample to 16 kHz. Returns 16 kHz mono `f32`.
///
/// Edge cases handled without panicking: empty input → empty output; `channels` 0 treated
/// as 1; `in_rate` 0 treated as the target rate (pass-through mono). A trailing partial
/// frame (fewer than `channels` samples) is ignored.
pub fn resample_to_16k_mono(samples: &[f32], in_rate: u32, channels: u16) -> Vec<f32> {
    let channels = channels.max(1) as usize;
    let mono = downmix(samples, channels);
    let in_rate = if in_rate == 0 {
        TARGET_SAMPLE_RATE
    } else {
        in_rate
    };
    resample_linear(&mono, in_rate, TARGET_SAMPLE_RATE)
}

/// Average `channels`-interleaved samples down to mono. A trailing partial frame is dropped.
fn downmix(samples: &[f32], channels: usize) -> Vec<f32> {
    if channels <= 1 {
        return samples.to_vec();
    }
    let frames = samples.len() / channels;
    let mut mono = Vec::with_capacity(frames);
    for f in 0..frames {
        let base = f * channels;
        let sum: f32 = samples[base..base + channels].iter().sum();
        mono.push(sum / channels as f32);
    }
    mono
}

/// Linear-interpolate `input` from `in_rate` to `out_rate`. Deterministic and allocation-
/// bounded (output length ≈ `input.len() * out_rate / in_rate`).
fn resample_linear(input: &[f32], in_rate: u32, out_rate: u32) -> Vec<f32> {
    if input.is_empty() {
        return Vec::new();
    }
    if in_rate == out_rate || input.len() == 1 {
        return input.to_vec();
    }
    let ratio = out_rate as f64 / in_rate as f64;
    // Number of output samples spanning the same duration.
    let out_len = ((input.len() as f64) * ratio).round() as usize;
    if out_len == 0 {
        return Vec::new();
    }
    let mut out = Vec::with_capacity(out_len);
    let last = input.len() - 1;
    for i in 0..out_len {
        // Source position for output sample i.
        let src = i as f64 / ratio;
        let idx = src.floor() as usize;
        if idx >= last {
            out.push(input[last]);
            continue;
        }
        let frac = (src - idx as f64) as f32;
        let a = input[idx];
        let b = input[idx + 1];
        out.push(a + (b - a) * frac);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn downmix_averages_stereo_to_mono() {
        // L=1.0 R=0.0 → 0.5, per frame.
        let stereo = vec![1.0, 0.0, 1.0, 0.0];
        assert_eq!(downmix(&stereo, 2), vec![0.5, 0.5]);
    }

    #[test]
    fn same_rate_mono_is_passthrough() {
        let mono = vec![0.1, 0.2, 0.3];
        assert_eq!(resample_to_16k_mono(&mono, TARGET_SAMPLE_RATE, 1), mono);
    }

    #[test]
    fn downsample_halves_length_roughly() {
        // 32 kHz → 16 kHz should roughly halve the sample count.
        let input: Vec<f32> = (0..320).map(|i| (i as f32) / 320.0).collect();
        let out = resample_to_16k_mono(&input, 32_000, 1);
        assert!((out.len() as i64 - 160).abs() <= 1, "len was {}", out.len());
        // Endpoints preserved.
        assert!((out[0] - 0.0).abs() < 1e-4);
    }

    #[test]
    fn empty_input_is_empty_output() {
        assert!(resample_to_16k_mono(&[], 48_000, 2).is_empty());
    }

    #[test]
    fn zero_channels_treated_as_mono() {
        let s = vec![0.5, 0.5];
        assert_eq!(resample_to_16k_mono(&s, TARGET_SAMPLE_RATE, 0), s);
    }
}
