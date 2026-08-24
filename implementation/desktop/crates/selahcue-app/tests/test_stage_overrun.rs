//! The TIME-UP overrun readout, end to end through `LiveController`.
//!
//! The readout shipped frozen at `OVER 0:00`: every piece existed — the core `Timer::overrun`,
//! the field, the setter, the three render sites — but nothing on the live path ever called
//! the setter, so the value never left its default. A test that only checked the formatting,
//! or only that *something* rendered, would have passed throughout.
//!
//! So this drives the real controller across real ticks and asserts the readout **moves**.

#![allow(clippy::unwrap_used)]

use selahcue_app::LiveController;
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::Command;
use selahcue_present::FrameBuffer;
use selahcue_present::Theme;
use std::time::{Duration, Instant};

/// A countdown short enough to run past zero inside a test, long enough that the ticks below
/// are unambiguously in overrun.
const COUNTDOWN_SECS: u32 = 60;

fn controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    LiveController::new(plan, 320, 180, Theme::dark())
}

/// The stage output after ticking to `t`.
fn stage_at(c: &mut LiveController, t: Instant) -> FrameBuffer {
    c.tick(t);
    c.stage_output().clone()
}

/// Drive a countdown past zero and capture the confidence monitor at each of `offsets`
/// seconds after the start.
fn overrun_frames(offsets: &[u64]) -> Vec<FrameBuffer> {
    let mut c = controller();
    let t0 = Instant::now();
    c.apply(&Command::StartTimer {
        seconds: COUNTDOWN_SECS,
    });
    c.tick(t0);
    offsets
        .iter()
        .map(|s| stage_at(&mut c, t0 + Duration::from_secs(*s)))
        .collect()
}

/// The readout must **change** as the overrun grows, not merely be present. Asserting it is
/// non-zero at one instant would still pass with a value stuck at `0:05`; asserting it moves
/// is what catches a value that never arrives.
///
/// The sample instants are all at the **same pulse phase** (odd elapsed seconds, so
/// `time_up_ink` returns the base alert red at every one of them). That is deliberate: the
/// TIME-UP word alternates bright/dim once per second, so consecutive seconds differ whether
/// or not the overrun is wired. Holding the phase fixed removes the pulse from the picture
/// and leaves the overrun digits as the only thing that can make these frames differ.
#[test]
fn the_stage_overrun_readout_advances_across_ticks() {
    // 61s, 63s, 65s, 67s into a 60s countdown → 1, 3, 5 and 7 seconds over, every one of
    // them an odd elapsed second.
    let offsets = [61u64, 63, 65, 67];
    for o in offsets {
        assert!(
            o > COUNTDOWN_SECS as u64,
            "{o}s is not past the {COUNTDOWN_SECS}s countdown — this test would be measuring \
             the running state"
        );
        assert_eq!(
            o % 2,
            1,
            "{o}s is not the odd pulse phase the test relies on"
        );
    }

    let frames = overrun_frames(&offsets);
    assert_eq!(frames.len(), offsets.len());

    for (i, a) in frames.iter().enumerate() {
        for (j, b) in frames.iter().enumerate().skip(i + 1) {
            assert_ne!(
                a,
                b,
                "the confidence monitor is byte-identical at {}s over and {}s over — the \
                 overrun readout is not advancing (it reads a constant, almost certainly \
                 `OVER 0:00`)",
                offsets[i] - COUNTDOWN_SECS as u64,
                offsets[j] - COUNTDOWN_SECS as u64
            );
        }
    }
}

/// Positive control for the test above. If the stage recompose were gated shut, or the
/// monitor were showing something other than the TIME-UP scene, every frame would be
/// identical and `assert_ne!` would fail for a reason that has nothing to do with the
/// overrun. So: the same monitor, sampled twice at the SAME instant, must be stable — the
/// frames above differ because time moved, not because the output is nondeterministic.
#[test]
fn the_stage_output_is_stable_when_the_overrun_does_not_change() {
    let mut c = controller();
    let t0 = Instant::now();
    c.apply(&Command::StartTimer {
        seconds: COUNTDOWN_SECS,
    });
    c.tick(t0);
    let a = stage_at(&mut c, t0 + Duration::from_secs(63));
    let b = stage_at(&mut c, t0 + Duration::from_secs(63));
    assert_eq!(
        a, b,
        "the confidence monitor is not deterministic at a fixed instant, so the difference \
         test above cannot attribute a change to the overrun"
    );
}

/// The readout is an *overrun* readout: before zero there is nothing to report, and a reset
/// must not leave a stale value on screen.
#[test]
fn the_overrun_clears_when_the_timer_is_no_longer_over() {
    let mut c = controller();
    let t0 = Instant::now();
    c.apply(&Command::StartTimer {
        seconds: COUNTDOWN_SECS,
    });
    c.tick(t0);

    let running = stage_at(&mut c, t0 + Duration::from_secs(30));
    let over = stage_at(&mut c, t0 + Duration::from_secs(75));
    assert_ne!(
        running, over,
        "the monitor looks the same running and 15s over"
    );

    // Restarting the countdown puts it back in the running state; the overrun is derived
    // from the live timer rather than latched, so it cannot survive the reset.
    c.apply(&Command::StartTimer {
        seconds: COUNTDOWN_SECS,
    });
    let after_reset = stage_at(&mut c, t0 + Duration::from_secs(105));
    assert_ne!(
        after_reset, over,
        "the confidence monitor still shows the pre-reset TIME-UP screen"
    );
}
