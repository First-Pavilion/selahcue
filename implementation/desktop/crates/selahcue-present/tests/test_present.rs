//! Preview→Live loop: the core isolation invariant, latency, and flash-safety.

#![allow(clippy::unwrap_used)]

use selahcue_engine::analysis::analyze_flashes;
use selahcue_engine::raster::FrameBuffer;
use selahcue_present::{Presenter, Slide, StageDisplay, StageTheme, Theme, TimerView};
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
    assert!(
        !is_black(p.preview_output()),
        "preview should show the staged slide"
    );
    assert!(
        is_black(p.live_output()),
        "staging must not change live (FR-012)"
    );
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
    assert!(
        !is_black(p.preview_output()),
        "clear must not touch preview"
    );
    assert!(p.live_slide().is_none());
}

#[test]
fn blackout_hides_then_restores_live() {
    let mut p = presenter();
    p.stage(Slide::title("Song 1"));
    p.go_live();
    let live_content = p.live_output().bytes().to_vec();
    p.blackout(true);
    assert!(
        is_black(p.live_output()),
        "blackout must black the audience output"
    );
    p.blackout(false);
    assert_eq!(
        p.live_output().bytes(),
        live_content.as_slice(),
        "un-blackout must restore the prior content"
    );
}

#[test]
fn go_live_slide_trigger_latency_is_within_budget() {
    // Time the synchronous compose+render of Go Live at a full-HD output. The 150 ms
    // slide-trigger budget is a RELEASE-build product NFR — enforcing it on an
    // unoptimized debug build running on oversubscribed CI shared runners measured the
    // runner, not the product (observed: 184–207 ms on GitHub's ubuntu/windows runners
    // vs well under budget locally). Debug builds keep a generous tripwire so a
    // catastrophic latency regression still fails everywhere; release builds enforce
    // the real budget.
    let budget = if cfg!(debug_assertions) {
        Duration::from_millis(1500)
    } else {
        Duration::from_millis(150)
    };
    let mut p = Presenter::new(1920, 1080, Theme::dark());
    p.stage(Slide::new(
        "Verse 1",
        ["Amazing grace, how sweet the sound"],
    ));
    let start = Instant::now();
    let went_live = p.go_live();
    let elapsed = start.elapsed();
    assert!(went_live);
    assert!(
        elapsed <= budget,
        "slide-trigger latency exceeded {budget:?}: {elapsed:?}"
    );
    // ...and the slide actually reached the live output.
    assert!(p.live_output().average_luminance() > 1e-6);
}

#[test]
fn go_live_latency_holds_for_the_longest_verse_auto_fit() {
    // The auto-fit path (wrap-to-width + binary-search font sizing) shapes text many
    // times per compose. A long verse (Esther 8:9, the longest KJV verse — the case the
    // owner hit) must still trigger within budget — the short-verse test above would
    // otherwise hide an auto-fit latency regression. Debug keeps a generous tripwire.
    let budget = if cfg!(debug_assertions) {
        Duration::from_millis(1500)
    } else {
        Duration::from_millis(150)
    };
    let verse = "Then were the king's scribes called at that time in the third month, that \
        is, the month Sivan, on the three and twentieth day thereof; and it was written \
        according to all that Mordecai commanded unto the Jews, and to the lieutenants, and \
        the deputies and rulers of the provinces which are from India unto Ethiopia, an \
        hundred twenty and seven provinces, unto every province according to the writing \
        thereof, and unto every people after their language, and to the Jews according to \
        their writing, and according to their language.";
    let mut p = Presenter::new(1920, 1080, Theme::classic());
    p.stage(Slide::new("Esther 8:9 (KJV)", [verse]));
    let start = Instant::now();
    assert!(p.go_live());
    let elapsed = start.elapsed();
    assert!(
        elapsed <= budget,
        "long-verse auto-fit latency exceeded {budget:?}: {elapsed:?}"
    );
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

// --- Timer on the stage/confidence monitor (a speaker aid — NOT on the audience
// output). ---

fn timer_view(remaining: u32, total: u32, time_up: bool, warn: bool) -> TimerView {
    TimerView {
        elapsed_secs: total.saturating_sub(remaining),
        remaining_secs: Some(remaining),
        time_up,
        warn,
        progress: if total == 0 {
            1.0
        } else {
            remaining as f64 / total as f64
        },
    }
}

/// Does the framebuffer contain a pixel close to `target` (per-channel tolerance)?
fn has_color(fb: &FrameBuffer, target: (u8, u8, u8)) -> bool {
    fb.bytes().chunks_exact(4).any(|px| {
        let d = |a: u8, b: u8| (a as i32 - b as i32).pow(2);
        d(px[0], target.0) + d(px[1], target.1) + d(px[2], target.2) < 900
    })
}

// The semantic token inks (tokens::PREVIEW.ink / tokens::LIVE.ink).
const TIMER_OK: (u8, u8, u8) = (0x2b, 0xb6, 0x73);
const TIMER_ALERT: (u8, u8, u8) = (0xef, 0x44, 0x44);

#[test]
fn stage_monitor_shows_the_timer_state() {
    let mut s = StageDisplay::new(320, 180, StageTheme::dark());
    // A running countdown → ok-green on the confidence monitor.
    s.update(
        Some(&Slide::title("Sermon")),
        None,
        Some(&timer_view(120, 300, false, false)),
    );
    assert!(
        has_color(s.output(), TIMER_OK),
        "ok-green timer on the stage monitor"
    );
    // TIME UP → the bar goes alert red.
    s.update(None, None, Some(&timer_view(0, 300, true, false)));
    assert!(
        has_color(s.output(), TIMER_ALERT),
        "TIME UP red on the stage monitor"
    );
}

#[test]
fn the_audience_output_never_shows_a_timer() {
    // The countdown is a speaker aid: the audience/program output shows the slide only.
    let mut p = presenter();
    p.stage(Slide::title("Sermon"));
    p.go_live();
    assert!(
        !has_color(p.live_output(), TIMER_OK),
        "no timer bar on the audience output"
    );
    assert!(
        !has_color(p.live_output(), TIMER_ALERT),
        "no TIME UP bar on the audience output"
    );
}

#[test]
fn set_theme_restyles_both_outputs_without_losing_content() {
    // Switching a theme re-styles Preview + Live from the RETAINED slides — the
    // content is untouched, only its design (FR-010, zero content loss).
    let mut p = Presenter::new(320, 180, Theme::classic());
    p.stage(Slide::new("Grace", ["Amazing grace"]));
    assert!(p.go_live());
    assert!(has_color(p.live_output(), (8, 10, 20)), "classic navy bg");
    let staged_before = p.staged().cloned();
    let live_before = p.live_slide().cloned();

    p.set_theme(Theme::high_contrast());

    // CONTENT preserved — same staged + live slides, only the look changed.
    assert_eq!(
        p.staged().cloned(),
        staged_before,
        "staged content preserved"
    );
    assert_eq!(
        p.live_slide().cloned(),
        live_before,
        "live content preserved"
    );
    assert_eq!(p.theme(), Theme::high_contrast(), "active theme updated");
    // Both surfaces restyled to the high-contrast (pure black) background.
    assert!(
        has_color(p.live_output(), (0, 0, 0)),
        "live restyled to black bg"
    );
    assert!(
        has_color(p.preview_output(), (0, 0, 0)),
        "preview restyled too"
    );
}

#[test]
fn render_sample_previews_a_theme_deterministically() {
    // The Theme Designer preview (S8-3c) renders a sample slide with the theme via
    // this exact path — so the webview preview matches the audience output.
    let fb = selahcue_present::render_sample(&Theme::classic(), 480, 270);
    assert_eq!((fb.width(), fb.height()), (480, 270));
    // The classic background is present and some glyph ink renders (not blank).
    assert!(has_color(&fb, (8, 10, 20)), "classic background rendered");
    assert!(
        fb.average_luminance() > 1e-6,
        "sample text renders (not blank)"
    );
    // Deterministic + theme-sensitive: high-contrast (black bg) differs.
    let a = selahcue_present::render_sample(&Theme::classic(), 480, 270);
    let b = selahcue_present::render_sample(&Theme::classic(), 480, 270);
    assert_eq!(a.bytes(), b.bytes(), "preview is deterministic");
    let hc = selahcue_present::render_sample(&Theme::high_contrast(), 480, 270);
    assert_ne!(
        hc.bytes(),
        a.bytes(),
        "a different theme previews differently"
    );
}

#[test]
fn per_item_theme_override_is_independent_per_surface_and_survives_a_global_switch() {
    // S8-3d: Preview + Live can carry DIFFERENT per-item themes at once, and switching
    // the GLOBAL theme recomposes each surface with its own effective theme — never
    // clobbering an overridden item (FR-010, zero content loss).
    let mut p = Presenter::new(320, 180, Theme::classic());
    // A live item OVERRIDDEN to lower-third.
    p.stage_themed(
        Slide::new("John 3:16", ["For God so loved"]),
        Some(Theme::lower_third()),
    );
    assert!(p.go_live());
    let live_override = p.live_output().bytes().to_vec();
    // A staged item with NO override → the global (classic). Two themes on screen at once.
    p.stage(Slide::new("Psalm 23", ["The LORD is my shepherd"]));
    assert_ne!(
        p.preview_output().bytes(),
        p.live_output().bytes(),
        "Preview (global) and Live (override) show different themes at once"
    );

    // Switch the GLOBAL theme → the overridden LIVE surface is unchanged...
    p.set_theme(Theme::high_contrast());
    assert_eq!(
        p.live_output().bytes(),
        live_override.as_slice(),
        "a global theme switch must NOT clobber the live item's override"
    );
    // ...while the un-overridden PREVIEW follows the new global theme (high-contrast).
    let mut reference = Presenter::new(320, 180, Theme::high_contrast());
    reference.stage(Slide::new("Psalm 23", ["The LORD is my shepherd"]));
    assert_eq!(
        p.preview_output().bytes(),
        reference.preview_output().bytes(),
        "the un-overridden preview follows the global theme"
    );
    // The live content is preserved (zero content loss) — still the overridden verse.
    assert_eq!(p.live_slide().unwrap().title, "John 3:16");
}

#[test]
fn set_theme_does_not_fabricate_content_on_a_blank_output() {
    let mut p = Presenter::new(320, 180, Theme::classic());
    p.set_theme(Theme::lower_third());
    assert!(p.staged().is_none(), "no phantom staged slide");
    assert!(p.live_slide().is_none(), "no phantom live slide");
    assert!(is_black(p.live_output()), "blank live stays blank");
}
