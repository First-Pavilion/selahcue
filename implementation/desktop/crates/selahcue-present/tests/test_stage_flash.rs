//! FR-175 flash-safety measurement for the stage TIME-UP state.
//!
//! The TIME-UP word alternates bright/dim once per elapsed second (`stage::time_up_ink`),
//! which is a deliberate, owner-approved deviation from FR-059's "solid-inverted (static)"
//! default. `ARCH-UX-REVIEW-stage5.md` M4 allows exactly two ways to discharge the finding —
//! make the default static, **or** show that the flashing default satisfies the red-flash
//! and flash-**area** sub-criteria. The project took the first route; keeping the pulse means
//! discharging under the second, and this file is that evidence.
//!
//! It measures rather than argues: every TIME-UP template is rendered as a real frame
//! sequence and put through `selahcue_engine::analysis::analyze_flashes`, which is WCAG
//! worst-case over an 8×8 tile grid — so a small pulsing word inside a large tile dilutes
//! that tile's luminance and is correctly *not* counted as a full-area flash. That tiling is
//! the area sub-criterion; a bare frequency argument would not cover it.

use selahcue_engine::analysis::analyze_flashes;
use selahcue_engine::raster::FrameBuffer;
use selahcue_present::stage::StageTemplate;
use selahcue_present::{Slide, StageDisplay, StageTheme, TimerView, WallClock};

/// Capture rate. The pulse has a 2-second period (one flip per elapsed second), so 12 fps
/// is ~24× Nyquist for it — far finer than the signal, while keeping the captured sequence
/// small enough to hold in memory at once (the analyzer takes the whole slice).
const FPS: f64 = 12.0;
/// 10 seconds — five full pulse cycles, so the worst one-second window is a real maximum
/// and not an artefact of a short capture.
const SECONDS: u32 = 10;
const FRAMES: usize = (FPS as u32 * SECONDS) as usize;

/// Capture resolution. The composer is fully proportional (every position and size is a
/// fraction of the frame), and `tile_stats` divides into 8×8 *fractional* tiles, so the
/// per-tile luminance and the flashing-**area** fraction are identical at any 16:9 size.
/// 640×360 keeps the whole 120-frame capture near 110 MB instead of 1 GB at 1080p; the
/// area figures are re-confirmed at true 1920×1080 in `pulsing_area_fraction`.
const CAP_W: u32 = 640;
const CAP_H: u32 = 360;

// A capture that does not span at least two full pulse cycles could report a low rate
// simply by ending early — the premise this whole measurement rests on.
const _: () = assert!(SECONDS >= 4);

fn slide(title: &str, body: &[&str]) -> Slide {
    Slide::new(title, body.iter().copied())
}

fn timed_up(elapsed: u32) -> TimerView {
    TimerView {
        elapsed_secs: elapsed,
        remaining_secs: Some(0),
        time_up: true,
        warn: false,
        progress: 0.0,
        // The value under test: the TIME-UP screens read `OVER 0:32` from here.
        overrun_secs: 32,
    }
}

fn stage_at(template: StageTemplate, w: u32, h: u32) -> StageDisplay {
    let mut sd = StageDisplay::new(w, h, StageTheme::dark());
    sd.set_template(template);
    sd.set_clock(Some(WallClock::new("Sunday · August 3, 2026", "10:56 AM")));
    sd.set_song_position(Some((2, 4)));
    sd
}

/// Render `FRAMES` frames of a TIME-UP `template` at `FPS`, advancing the elapsed second
/// exactly as the live controller does.
fn capture(template: StageTemplate) -> Vec<FrameBuffer> {
    let cur = slide("Sermon", &["Amazing grace, how sweet the sound"]);
    let next = slide(
        "Isaiah 61:6",
        &["But ye shall be named the Priests of the LORD"],
    );
    let mut sd = stage_at(template, CAP_W, CAP_H);
    let mut frames = Vec::with_capacity(FRAMES);
    for i in 0..FRAMES {
        let elapsed = 900 + (i as f64 / FPS) as u32;
        sd.update(Some(&cur), Some(&next), Some(&timed_up(elapsed)));
        frames.push(sd.output().clone());
    }
    frames
}

/// The exact fraction of the screen whose pixels change between the two pulse phases,
/// measured at true 1920×1080. This is the flashing **area** in the WCAG sense.
fn pulsing_area_fraction(template: StageTemplate) -> f64 {
    let cur = slide("Sermon", &["Amazing grace, how sweet the sound"]);
    let next = slide(
        "Isaiah 61:6",
        &["But ye shall be named the Priests of the LORD"],
    );
    let mut sd = stage_at(template, 1920, 1080);
    sd.update(Some(&cur), Some(&next), Some(&timed_up(900))); // even second: bright
    let bright = sd.output().clone();
    sd.update(Some(&cur), Some(&next), Some(&timed_up(901))); // odd second: base
    let base = sd.output();

    let mut changed = 0u64;
    for y in 0..1080 {
        for x in 0..1920 {
            if bright.pixel(x, y) != base.pixel(x, y) {
                changed += 1;
            }
        }
    }
    changed as f64 / (1920.0 * 1080.0)
}

/// The 8×8 tile with the largest luminance swing across the capture — "where" the analyzer
/// found its worst case, which its scalar report does not say.
fn worst_tile(frames: &[FrameBuffer]) -> (usize, usize, f64) {
    const COLS: u32 = 8;
    const ROWS: u32 = 8;
    let n = (COLS * ROWS) as usize;
    let mut lo = vec![f64::MAX; n];
    let mut hi = vec![f64::MIN; n];
    for f in frames {
        let (lum, _red) = f.tile_stats(COLS, ROWS);
        for t in 0..n {
            let v = lum.get(t).copied().unwrap_or(0.0);
            lo[t] = lo[t].min(v);
            hi[t] = hi[t].max(v);
        }
    }
    let mut best = (0usize, 0.0f64);
    for t in 0..n {
        let swing = hi[t] - lo[t];
        if swing > best.1 {
            best = (t, swing);
        }
    }
    (best.0 % COLS as usize, best.0 / COLS as usize, best.1)
}

#[test]
fn time_up_pulse_is_within_the_fr175_flash_limits_on_every_template() {
    // The analyzer's own bound (FR-175 / WCAG 2.3.1): ≤3 general and ≤3 red flashes/sec.
    const LIMIT: f64 = 3.0;
    let mut all_pass = true;
    for (name, template) in [
        ("worship", StageTemplate::Worship),
        ("scripture", StageTemplate::Scripture),
        ("timer-only", StageTemplate::TimerOnly),
    ] {
        let frames = capture(template);
        assert_eq!(frames.len(), FRAMES, "{name}: capture short");
        // The capture must actually VARY. If it did not — a flattened `time_up_ink`, a
        // frozen elapsed second, a harness that re-pushed one frame — the analyzer would
        // report 0.000 flashes/sec and this test would pass while measuring nothing.
        assert!(
            frames.iter().any(|f| f != &frames[0]),
            "{name}: all {FRAMES} captured frames are identical — the rate below is vacuous"
        );
        let report = analyze_flashes(&frames, FPS);
        let (tx, ty, swing) = worst_tile(&frames);
        let area = pulsing_area_fraction(template);
        println!(
            "FR-175 {name:>11}: luminance={:.3}/s red={:.3}/s passes={} \
             worst_tile=({tx},{ty}) swing={swing:.4} pulsing_area={:.4}% ({:.2}% of a tile)",
            report.luminance_flashes_per_sec,
            report.red_flashes_per_sec,
            report.passes,
            area * 100.0,
            area * 64.0 * 100.0,
        );
        all_pass &= report.passes;
        assert!(
            report.luminance_flashes_per_sec <= LIMIT,
            "{name}: {} general flashes/sec exceeds the FR-175 limit of {LIMIT}",
            report.luminance_flashes_per_sec
        );
        assert!(
            report.red_flashes_per_sec <= LIMIT,
            "{name}: {} RED flashes/sec exceeds the FR-175 limit of {LIMIT}",
            report.red_flashes_per_sec
        );
    }
    assert!(all_pass, "at least one template failed the analyzer");
}

/// Positive control. Without this the test above cannot tell "the pulse is safe" from "the
/// harness renders 120 identical frames and measures nothing" — the failure mode that makes
/// a flash-safety test worthless. A synthetic 6 Hz full-screen strobe, pushed through the
/// SAME capture length and the SAME analyzer call, must be reported as over the limit.
#[test]
fn the_analyzer_would_have_caught_a_real_strobe_at_this_capture_length() {
    const LIMIT: f64 = 3.0;
    let mut sd = stage_at(StageTemplate::TimerOnly, CAP_W, CAP_H);
    let cur = slide("Sermon", &[]);
    let mut frames = Vec::with_capacity(FRAMES);
    for i in 0..FRAMES {
        // 6 Hz: flip the whole screen between the TIME-UP field and the running field
        // every frame at 12 fps. Same composer, same size, same frame count.
        let t = if i % 2 == 0 {
            timed_up(900)
        } else {
            TimerView {
                elapsed_secs: 100,
                remaining_secs: Some(765),
                time_up: false,
                warn: false,
                progress: 0.5,
                overrun_secs: 0,
            }
        };
        sd.update(Some(&cur), None, Some(&t));
        frames.push(sd.output().clone());
    }
    let report = analyze_flashes(&frames, FPS);
    println!(
        "FR-175 positive control (6 Hz strobe): luminance={:.3}/s red={:.3}/s passes={}",
        report.luminance_flashes_per_sec, report.red_flashes_per_sec, report.passes
    );
    assert!(
        report.luminance_flashes_per_sec > LIMIT || report.red_flashes_per_sec > LIMIT,
        "the analyzer did not flag a 6 Hz full-screen strobe — the measurement above proves \
         nothing (luminance={}, red={})",
        report.luminance_flashes_per_sec,
        report.red_flashes_per_sec
    );
    assert!(
        !report.passes,
        "a 6 Hz full-screen strobe reported as passing"
    );
}

/// The pulse must actually be happening. If `time_up_ink` were flattened to a constant the
/// rate test above would report 0.0 flashes/sec and pass — vacuously. This pins the premise:
/// consecutive elapsed seconds render DIFFERENT pixels, and the region that differs is small.
#[test]
fn the_time_up_pulse_is_present_and_small_area_on_every_template() {
    for (name, template) in [
        ("worship", StageTemplate::Worship),
        ("scripture", StageTemplate::Scripture),
        ("timer-only", StageTemplate::TimerOnly),
    ] {
        let area = pulsing_area_fraction(template);
        assert!(
            area > 0.0,
            "{name}: nothing changes between pulse phases — the flash measurement is vacuous"
        );
        // WCAG's small-safe area is 25 % of the visual field; the analyzer enforces it by
        // tiling, and this records the raw figure the tiling acts on.
        assert!(
            area < 0.25,
            "{name}: the pulsing region covers {:.2}% of the screen, past the WCAG \
             small-safe area limit",
            area * 100.0
        );
    }
}

/// `StageContext::overrun_secs` reaches the TIME-UP readout — without it the capture above
/// would be measuring a screen that never shows the value this batch added.
/// Sensitivity check: the figures above are measured on a build that already replaces the
/// timer-only TIME-UP background with this batch's dark vignette. If the verdict depended on
/// that change it would be evidence about the vignette, not about the pulse. Re-running the
/// worst template against the PRE-change background — the flat `#2a1416` wash, reconstructed
/// by collapsing all three vignette stops onto `alert_wash` — must reach the same verdict.
#[test]
fn the_flash_verdict_does_not_depend_on_the_new_vignette() {
    const LIMIT: f64 = 3.0;
    let mut legacy = StageTheme::dark();
    legacy.alert_vignette_core = legacy.alert_wash;
    legacy.alert_vignette_mid = legacy.alert_wash;
    legacy.alert_vignette_edge = legacy.alert_wash;

    let cur = slide("Sermon", &[]);
    let mut sd = StageDisplay::new(CAP_W, CAP_H, legacy);
    sd.set_template(StageTemplate::TimerOnly);
    sd.set_clock(Some(WallClock::new("Sunday · August 3, 2026", "10:56 AM")));
    let mut frames = Vec::with_capacity(FRAMES);
    for i in 0..FRAMES {
        sd.update(
            Some(&cur),
            None,
            Some(&timed_up(900 + (i as f64 / FPS) as u32)),
        );
        frames.push(sd.output().clone());
    }
    let report = analyze_flashes(&frames, FPS);
    println!(
        "FR-175 timer-only on the PRE-change flat wash: luminance={:.3}/s red={:.3}/s passes={}",
        report.luminance_flashes_per_sec, report.red_flashes_per_sec, report.passes
    );
    assert!(
        report.luminance_flashes_per_sec <= LIMIT && report.red_flashes_per_sec <= LIMIT,
        "the pre-change background exceeds the FR-175 limit (luminance={}, red={}) — the \
         measurement above is an artefact of the new vignette, not a property of the pulse",
        report.luminance_flashes_per_sec,
        report.red_flashes_per_sec
    );
}

/// The overrun readout is part of the screen these figures were measured on — without it the
/// capture would be of a screen that never shows the value this batch added.
#[test]
fn the_overrun_readout_is_part_of_the_measured_time_up_screen() {
    let mut sd = stage_at(StageTemplate::TimerOnly, 1920, 1080);
    let cur = slide("Sermon", &[]);
    sd.update(Some(&cur), None, Some(&timed_up(900)));
    let at_32 = sd.output().clone();
    let further = TimerView {
        overrun_secs: 300,
        ..timed_up(900)
    };
    sd.update(Some(&cur), None, Some(&further));
    assert_ne!(
        &at_32,
        sd.output(),
        "0:32 over and 5:00 over rendered the same screen"
    );
}
