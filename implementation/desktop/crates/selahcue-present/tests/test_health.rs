//! Output health (NFR-024 observability): a held live output must be distinguishable
//! from a healthy one, and a recovery must be visible to a polling reader.
//!
//! These tests exist because the guarantee was already correct and entirely invisible.
//! `selahcue-engine` returned `OutputHeld`/`Recovered` from every `apply`; `Presenter`
//! dropped them at all thirteen call sites; nothing above could tell a held output from
//! a healthy one. So each test here drives the **real** producer (`Presenter::inject_fault`
//! — the same method the host calls when wgpu reports surface loss) and asserts the value
//! reaches the reader and *changes*.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::FrameBuffer;
use selahcue_present::{fault_tag, Fault, OutputHealth, Presenter, Slide, Theme};

fn presenter() -> Presenter {
    Presenter::new(320, 180, Theme::dark())
}

fn is_black(fb: &FrameBuffer) -> bool {
    fb.average_luminance() < 1e-6
}

/// Put real content on Live so a later hold has a good frame to hold ONTO. A fault over a
/// black output would pass a "did not blank" assertion trivially — the output was already
/// black — so every hold test starts from visible content.
fn with_live_content(title: &str) -> Presenter {
    let mut p = presenter();
    p.stage(Slide::title(title));
    assert!(p.go_live(), "test setup: go_live must succeed");
    assert!(
        !is_black(p.live_output()),
        "test setup: live must show real content, or a hold test proves nothing"
    );
    p
}

#[test]
fn a_healthy_presenter_reports_no_fault() {
    let p = with_live_content("Opening Song");
    let h = p.output_health();
    assert!(!h.held, "a healthy output is not held");
    assert_eq!(h.fault, None, "a healthy output names no fault");
    assert_eq!(h.holds, 0);
    assert_eq!(h.recoveries, 0);
}

/// The acceptance bar, stated directly: *a dead detector and a silent room must not render
/// identically*. Its output-side analogue is that a HELD output and a HEALTHY one must not
/// report identically — and the strong form of that is proving it while the two are
/// **pixel-for-pixel the same**, because holding means the audience still sees the last
/// good frame. If health were derived from the framebuffer it could not tell these apart;
/// the whole point is that it carries information the pixels do not.
#[test]
fn a_held_output_is_distinguishable_from_a_healthy_one_with_identical_pixels() {
    let healthy = with_live_content("Opening Song");
    let mut held = with_live_content("Opening Song");
    held.inject_fault(Fault::GpuDeviceLost);

    assert_eq!(
        held.live_output().bytes(),
        healthy.live_output().bytes(),
        "a held output must still show the last good frame — identical pixels (NFR-024)"
    );
    assert_ne!(
        held.output_health(),
        healthy.output_health(),
        "a held output and a healthy one show the SAME pixels, so if health does not \
         distinguish them nothing can — this is the acceptance bar"
    );
    assert!(held.output_health().held);
    assert!(!healthy.output_health().held);
}

#[test]
fn a_fault_holds_the_live_output_without_blanking_it() {
    let mut p = with_live_content("Opening Song");
    let before = p.live_output().bytes().to_vec();

    p.inject_fault(Fault::DecoderFault);

    let h = p.output_health();
    assert!(h.held, "the output must report itself held");
    assert_eq!(h.fault, Some(Fault::DecoderFault), "and name the reason");
    assert_eq!(h.holds, 1, "the hold must be counted");
    assert_eq!(h.recoveries, 0, "nothing has recovered yet");
    assert_eq!(
        p.live_output().bytes(),
        before.as_slice(),
        "the live output must HOLD its last good frame, never blank (NFR-024)"
    );
    assert!(!is_black(p.live_output()), "and it must not be black");
}

#[test]
fn recovery_clears_the_hold_and_names_no_stale_reason() {
    let mut p = with_live_content("Opening Song");
    p.inject_fault(Fault::IpcStall);
    assert!(p.output_health().held, "premise: the output is held");

    // Recovery is implicit: the next successful compose presents a good frame.
    p.stage(Slide::title("Second Song"));
    assert!(p.go_live());

    let h = p.output_health();
    assert!(!h.held, "a good frame must clear the hold");
    assert_eq!(
        h.fault, None,
        "a recovered output must name NO fault — a stale reason beside a healthy \
         output is exactly the kind of lie this seam exists to prevent"
    );
    assert_eq!(h.holds, 1);
    assert_eq!(h.recoveries, 1, "the recovery must be counted");
}

/// Every fault kind must survive the trip distinctly. Collapsing them to a bare "faulted"
/// bool would let a full disk and a lost GPU render identically — the same class of defect
/// as the acceptance bar, one layer down. Runs the engine's own exhaustive matrix, so a new
/// `Fault` variant is covered the day it is added.
#[test]
fn every_fault_kind_is_reported_distinctly() {
    let mut seen: Vec<&str> = Vec::new();
    for fault in Fault::ALL {
        let mut p = with_live_content("Opening Song");
        p.inject_fault(fault);
        let h = p.output_health();
        assert!(h.held, "{fault:?} must hold the output");
        assert_eq!(h.fault, Some(fault), "{fault:?} must be reported as itself");
        seen.push(fault_tag(fault));
    }
    let mut unique = seen.clone();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(
        unique.len(),
        seen.len(),
        "every fault kind needs its OWN wire tag, else two causes render alike: {seen:?}"
    );
}

/// The design claim that justifies keeping counters at all, rather than only `held`.
///
/// The operator console polls at 1 Hz and has no health event channel. A hold that begins
/// and ends between two polls is invisible to a *level* — both samples read "not held" —
/// so recovery could never be shown. The monotonic counter turns that level into an edge.
/// **This test fails if someone decides `held` alone is enough and drops the counters**,
/// which is the likeliest future simplification.
#[test]
fn a_recovery_between_two_polls_is_still_visible_to_the_reader() {
    let mut p = with_live_content("Opening Song");

    // Poll #1 — healthy.
    let first = p.output_health();
    assert!(!first.held);

    // Between polls: the output faults and fully recovers.
    p.inject_fault(Fault::GpuDeviceLost);
    p.stage(Slide::title("Second Song"));
    assert!(p.go_live());

    // Poll #2 — the LEVEL shows nothing happened...
    let second = p.output_health();
    assert!(
        !second.held && !first.held,
        "premise: the level reads the same at both polls, so it carries no evidence"
    );
    // ...but the EDGE is still there.
    assert!(
        second.recoveries > first.recoveries,
        "a recovery that happened entirely between two polls must still be visible; \
         this is why the record keeps counters and not just a bool"
    );
    assert!(
        second.holds > first.holds,
        "and so must the hold that caused it"
    );
}

/// Preview is an offscreen operator surface; NFR-024 is a guarantee about the AUDIENCE
/// output. Counting a preview hold as a broadcast fault would raise a false alarm on the
/// console, so preview deliberately does not record. The positive control in the same test
/// keeps that from silently becoming "nothing records at all".
#[test]
fn preview_activity_is_not_counted_as_an_audience_fault() {
    let mut p = with_live_content("Opening Song");
    for i in 0..5 {
        p.stage(Slide::title(format!("Staged {i}")));
    }
    assert_eq!(
        p.output_health().holds,
        0,
        "staging into Preview must never be reported as an audience fault"
    );
    // Positive control: the mechanism is alive — a real LIVE fault still registers.
    p.inject_fault(Fault::DiskFull);
    assert_eq!(
        p.output_health().holds,
        1,
        "a LIVE fault must still be counted, else the assertion above only proves \
         the mechanism is dead"
    );
}

/// The premise for the bounded test below, pinned at compile time so that raising the
/// cycle count can never quietly make the test prove less than it claims.
const CYCLES: u64 = 10_000;
const _: () = assert!(CYCLES >= 1_000);

/// Health must not grow with the number of faults. The type is counters-only, so this is
/// really a guard against a future "let's keep a fault log" edit: such a log would make
/// `OutputHealth` non-`Copy` and unbounded. Asserting the counters stay EXACT over ten
/// thousand cycles also proves nothing is being dropped or coalesced along the way.
#[test]
fn health_stays_bounded_and_exact_under_repeated_fault_cycles() {
    let mut p = with_live_content("Opening Song");
    for i in 0..CYCLES {
        p.inject_fault(Fault::GpuDeviceLost);
        p.stage(Slide::title(format!("Slide {i}")));
        assert!(p.go_live());
    }
    let h = p.output_health();
    assert_eq!(h.holds, CYCLES, "every hold counted, none coalesced");
    assert_eq!(h.recoveries, CYCLES, "every recovery counted");
    assert!(!h.held, "the last compose recovered the output");
    assert_eq!(h.fault, None);

    // The record is a fixed-size value type: it is `Copy`, and its size does not depend on
    // how many faults it has seen. A `Vec`/`VecDeque` fault log would break both.
    let copied: OutputHealth = h;
    assert_eq!(copied, h);
    assert!(
        std::mem::size_of::<OutputHealth>() <= 32,
        "OutputHealth must stay a small fixed-size record; a heap fault log here would \
         be the unbounded queue CLAUDE.md forbids"
    );
}

/// The pairing invariant every reader downstream relies on: **a reason is reported only
/// while the output is actually held.** Consumers map the record straight onto the wire
/// without re-checking it, so this is its single enforcement point. It is stated over the
/// whole fault matrix and over both transitions, so a future change that clears `held`
/// without clearing the reason — for instance a new live-apply call site that bypasses
/// `apply_live` — fails here rather than shipping a stale reason to the operator.
#[test]
fn output_health_never_names_a_reason_when_not_held() {
    let p = with_live_content("Opening Song");
    let h = p.output_health();
    assert!(
        !h.held && h.fault.is_none(),
        "fresh output: no hold, no reason"
    );

    for fault in Fault::ALL {
        let mut p = with_live_content("Opening Song");

        p.inject_fault(fault);
        let held = p.output_health();
        assert!(
            held.held && held.fault.is_some(),
            "held output names its reason"
        );

        p.stage(Slide::title("Next"));
        assert!(p.go_live());
        let done = p.output_health();
        assert!(
            !done.held,
            "premise: a good frame recovers the output after {fault:?}"
        );
        assert!(
            done.fault.is_none(),
            "a recovered output must name NO reason, but still reported {:?} after {fault:?}",
            done.fault
        );
    }
}
