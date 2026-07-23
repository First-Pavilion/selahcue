//! Frame-sequence analysis (ADR-0015): the seizure-safe flash-rate analyzer
//! (FR-175) and the input-to-photons latency proxy (NFR-004 / METRIC-002).
//!
//! These operate on captured [`FrameBuffer`] readbacks, so the same code measures
//! the headless test path and (streamed) on-screen output. This is a principled
//! *proxy* of the FR-175 method — the normative full analyzer is the performance
//! harness (ADR-0015 M6) — but it deliberately errs toward FAIL:
//!
//! - **Spatial:** each frame is split into a tile grid and every tile is analyzed
//!   independently, so a strobe confined to a sub-region is not diluted away.
//! - **Temporal:** the verdict is the WCAG worst-case — the maximum flashes in any
//!   one-second window, not an average over the whole capture.
//! - **Boundary:** flashes are counted fractionally (a dangling half-flash still
//!   contributes), so a strobe just over the limit is not rounded down to a pass.

use crate::raster::FrameBuffer;

/// A general flash = a pair of opposing relative-luminance changes of ≥10% of max
/// where the darker state is below 0.80 (WCAG general-flash definition).
const FLASH_AMPLITUDE: f64 = 0.10;
const FLASH_DARK_MAX: f64 = 0.80;
/// Flashes-per-second limit (both luminance and red).
const FLASH_LIMIT: f64 = 3.0;
/// Spatial tile grid — each tile is analyzed independently.
const TILE_COLS: u32 = 8;
const TILE_ROWS: u32 = 8;

/// The FR-175 flash-rate verdict over a captured sequence (worst tile, worst
/// one-second window).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct FlashReport {
    pub luminance_flashes_per_sec: f64,
    pub red_flashes_per_sec: f64,
    /// True iff both rates are within the ≤3 flashes/second limit.
    pub passes: bool,
}

/// Frame indices of each *alternating* significant opposing change in a per-tile
/// signal (each is a half-flash; a pair makes one flash).
fn transition_indices(signal: &[f64]) -> Vec<usize> {
    let mut anchor = match signal.first() {
        Some(&v) => v,
        None => return Vec::new(),
    };
    let mut out = Vec::new();
    let mut last_dir: i8 = 0;
    for (i, &v) in signal.iter().enumerate().skip(1) {
        let delta = v - anchor;
        if delta.abs() >= FLASH_AMPLITUDE && anchor.min(v) < FLASH_DARK_MAX {
            let dir: i8 = if delta > 0.0 { 1 } else { -1 };
            if dir != last_dir {
                out.push(i);
                last_dir = dir;
            }
            anchor = v;
        }
    }
    out
}

/// Maximum flashes within any one-second window over the transition indices.
/// Fractional: a lone trailing half-flash still counts, so the analyzer never
/// rounds a just-over-limit strobe down to a pass.
fn max_flashes_per_sec(transitions: &[usize], fps: f64) -> f64 {
    if fps <= 0.0 || transitions.is_empty() {
        return 0.0;
    }
    let window = fps; // one second, in frame-index units
    let mut best = 0usize;
    for (i, &start) in transitions.iter().enumerate() {
        let count = transitions[i..]
            .iter()
            .take_while(|&&idx| ((idx - start) as f64) < window)
            .count();
        best = best.max(count);
    }
    best as f64 / 2.0
}

/// Analyze a captured frame sequence for FR-175 compliance: the worst tile's
/// worst one-second window, for both luminance and red.
pub fn analyze_flashes(frames: &[FrameBuffer], fps: f64) -> FlashReport {
    let tiles = (TILE_COLS * TILE_ROWS) as usize;
    let mut lum_signals: Vec<Vec<f64>> = vec![Vec::with_capacity(frames.len()); tiles];
    let mut red_signals: Vec<Vec<f64>> = vec![Vec::with_capacity(frames.len()); tiles];
    for frame in frames {
        let (lum, red) = frame.tile_stats(TILE_COLS, TILE_ROWS);
        for t in 0..tiles {
            lum_signals[t].push(lum.get(t).copied().unwrap_or(0.0));
            red_signals[t].push(red.get(t).copied().unwrap_or(0.0));
        }
    }

    let worst = |signals: &[Vec<f64>]| -> f64 {
        signals
            .iter()
            .map(|s| max_flashes_per_sec(&transition_indices(s), fps))
            .fold(0.0, f64::max)
    };

    let luminance_flashes_per_sec = worst(&lum_signals);
    let red_flashes_per_sec = worst(&red_signals);
    FlashReport {
        luminance_flashes_per_sec,
        red_flashes_per_sec,
        passes: luminance_flashes_per_sec <= FLASH_LIMIT && red_flashes_per_sec <= FLASH_LIMIT,
    }
}

/// Input-to-photons proxy: the index of the first captured frame for which
/// `appears` holds (e.g. "the new content is now on screen"), or `None` if it
/// never appears within the capture.
pub fn frames_until<F>(frames: &[FrameBuffer], appears: F) -> Option<usize>
where
    F: Fn(&FrameBuffer) -> bool,
{
    frames.iter().position(appears)
}

/// Convert a frame count to seconds at `fps` (the latency in real time).
pub fn frames_to_secs(frames: usize, fps: f64) -> f64 {
    if fps > 0.0 {
        frames as f64 / fps
    } else {
        0.0
    }
}
