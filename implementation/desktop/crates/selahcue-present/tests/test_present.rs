//! Preview→Live loop: the core isolation invariant, latency, and flash-safety.

#![allow(clippy::unwrap_used)]

use selahcue_engine::analysis::analyze_flashes;
use selahcue_engine::raster::FrameBuffer;
use selahcue_present::{Presenter, Slide, Theme};
use std::time::{Duration, Instant};

fn presenter() -> Presenter {
    Presenter::new(320, 180, Theme::dark())
}

fn is_black(fb: &FrameBuffer) -> bool {
    fb.average_luminance() < 1e-6
}

#[test]
fn staging_never_changes_live() {
    let mut p = presenter();
    assert!(is_black(p.live_output()), "live starts black");
    p.stage(Slide::title("Song 1"));
    // Preview shows the staged slide; LIVE stays black — staging must not touch it.
    assert!(!is_black(p.preview_output()), "preview should show the staged slide");
    assert!(is_black(p.live_output()), "staging must not change live (FR-012)");
    assert!(p.live_slide().is_none());
}

#[test]
fn go_live_pushes_preview_to_live() {
    let mut p = presenter();
    p.stage(Slide::title("Song 1"));
    let preview_before = p.preview_output().bytes().to_vec();
    assert!(p.go_live());
    assert_eq!(
        p.live_output().bytes(),
        preview_before.as_slice(),
        "live must match what preview was showing"
    );
    assert_eq!(p.live_slide().unwrap().title, "Song 1");
}

#[test]
fn go_live_with_nothing_staged_is_a_noop() {
    let mut p = presenter();
    assert!(!p.go_live());
    assert!(is_black(p.live_output()));
}

#[test]
fn staging_next_while_live_does_not_disturb_live() {
    let mut p = presenter();
    p.stage(Slide::title("Slide A"));
    p.go_live();
    let live_a = p.live_output().bytes().to_vec();
    // Stage the next slide — live must keep showing A until Go Live.
    p.stage(Slide::title("Slide BBBB"));
    assert_eq!(
        p.live_output().bytes(),
        live_a.as_slice(),
        "live changed while only staging the next slide"
    );
    assert_eq!(p.staged().unwrap().title, "Slide BBBB");
    // Go Live -> live becomes B.
    p.go_live();
    assert_ne!(p.live_output().bytes(), live_a.as_slice());
    assert_eq!(p.live_slide().unwrap().title, "Slide BBBB");
}

#[test]
fn clear_blanks_live_but_not_preview() {
    let mut p = presenter();
    p.stage(Slide::title("Song 1"));
    p.go_live();
    assert!(!is_black(p.live_output()));
    p.clear_live();
    assert!(is_black(p.live_output()), "clear must blank live");
    assert!(!is_black(p.preview_output()), "clear must not touch preview");
    assert!(p.live_slide().is_none());
}

#[test]
fn blackout_hides_then_restores_live() {
    let mut p = presenter();
    p.stage(Slide::title("Song 1"));
    p.go_live();
    let live_content = p.live_output().bytes().to_vec();
    p.blackout(true);
    assert!(is_black(p.live_output()), "blackout must black the audience output");
    p.blackout(false);
    assert_eq!(
        p.live_output().bytes(),
        live_content.as_slice(),
        "un-blackout must restore the prior content"
    );
}

#[test]
fn go_live_slide_trigger_latency_is_within_budget() {
    // Time the synchronous compose+render of Go Live at a full-HD output — it must
    // complete within the 150 ms slide-trigger budget (a real measurement that a
    // genuine latency regression in go_live would fail).
    let mut p = Presenter::new(1920, 1080, Theme::dark());
    p.stage(Slide::new("Verse 1", ["Amazing grace, how sweet the sound"]));
    let start = Instant::now();
    let went_live = p.go_live();
    let elapsed = start.elapsed();
    assert!(went_live);
    assert!(
        elapsed <= Duration::from_millis(150),
        "slide-trigger latency exceeded 150 ms: {elapsed:?}"
    );
    // ...and the slide actually reached the live output.
    assert!(p.live_output().average_luminance() > 1e-6);
}

#[test]
fn degenerate_dimensions_keep_tracked_state_consistent() {
    // Created before the output size is known (0×0): dimensions clamp to a valid
    // range, so go_live still projects and live_slide truthfully reflects it.
    let mut p = Presenter::new(0, 0, Theme::dark());
    p.stage(Slide::title("Song 1"));
    assert!(p.go_live(), "go_live must project after dimension clamping");
    assert_eq!(p.live_slide().unwrap().title, "Song 1");
}

#[test]
fn normal_slide_sequence_is_flash_safe() {
    // Advancing live through a few slides is not a seizure risk (FR-175 sanity).
    let mut p = presenter();
    let mut captures = Vec::new();
    for title in ["", "Slide 1", "Slide 2", "Slide 3"] {
        if !title.is_empty() {
            p.stage(Slide::title(title));
            p.go_live();
        }
        captures.push(p.live_output().clone());
    }
    assert!(
        analyze_flashes(&captures, 1.0).passes,
        "a normal slide sequence should be flash-safe"
    );
}

#[test]
fn presenter_state_is_bounded_over_many_cycles() {
    // No-leak: cycling many slides holds O(1) state (two output buffers + at most
    // one staged/live slide), never a growing history.
    let mut p = presenter();
    let expected = p.live_output().byte_len();
    for i in 0..2000u32 {
        p.stage(Slide::title(format!("Slide {i}")));
        p.go_live();
    }
    assert_eq!(p.live_output().byte_len(), expected);
    assert_eq!(p.preview_output().byte_len(), expected);
}
