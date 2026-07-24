//! Stage/confidence monitor: timer state, current/next regions, dual-output
//! independence, and display identification (FR-037/040).

#![allow(clippy::unwrap_used)]

use selahcue_core::timer::Timer;
use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_engine::scene::Rgba;
use selahcue_present::{
    compose_identify, compose_slide, compose_stage, Presenter, Slide, StageDisplay, StageTheme,
    Theme, TimerView,
};
use std::time::{Duration, Instant};

fn running(progress: f64) -> TimerView {
    TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(100),
        time_up: false,
        warn: false,
        progress,
    }
}

fn has_color(fb: &FrameBuffer, color: Rgba) -> bool {
    (0..fb.height()).any(|y| (0..fb.width()).any(|x| fb.pixel(x, y) == Some(color)))
}

#[test]
fn timer_view_derives_state_from_a_countdown() {
    let base = Instant::now();
    let total = Duration::from_secs(300);
    let mut t = Timer::count_down(total);
    t.start(base);

    let ok = TimerView::from_timer(&t, base + Duration::from_secs(60), Some(total), 30);
    assert!(!ok.time_up && !ok.warn);
    assert_eq!(ok.remaining_secs, Some(240));
    assert!((ok.progress - 240.0 / 300.0).abs() < 1e-9);

    let warn = TimerView::from_timer(&t, base + Duration::from_secs(280), Some(total), 30);
    assert!(warn.warn && !warn.time_up, "20s left should warn (<=30)");

    let up = TimerView::from_timer(&t, base + Duration::from_secs(300), Some(total), 30);
    assert!(up.time_up);
}

#[test]
fn timer_bar_colour_reflects_state() {
    let theme = StageTheme::dark();
    // OK (green), full fill.
    let ok = render(&compose_stage(
        None,
        None,
        Some(&running(1.0)),
        &theme,
        200,
        100,
    ));
    assert_eq!(ok.pixel(5, 5).unwrap(), theme.timer_ok);

    // Warn (amber), partial fill.
    let warn = TimerView {
        warn: true,
        progress: 0.2,
        ..running(0.2)
    };
    let fb = render(&compose_stage(None, None, Some(&warn), &theme, 200, 100));
    assert_eq!(fb.pixel(5, 5).unwrap(), theme.timer_warn); // inside the fill
    assert_eq!(fb.pixel(180, 5).unwrap(), theme.track); // beyond the 20% fill

    // TIME UP (red), full alert bar.
    let up = TimerView {
        time_up: true,
        progress: 0.0,
        ..running(0.0)
    };
    let fb = render(&compose_stage(None, None, Some(&up), &theme, 200, 100));
    assert_eq!(fb.pixel(5, 5).unwrap(), theme.timer_alert);
    assert_eq!(
        fb.pixel(180, 5).unwrap(),
        theme.timer_alert,
        "TIME UP fills the whole bar"
    );
}

#[test]
fn current_and_next_regions_show_text_when_present() {
    let theme = StageTheme::dark();
    let current = Slide::title("CURRENT LINE");
    let next = Slide::title("NEXT LINE");
    let fb = render(&compose_stage(
        Some(&current),
        Some(&next),
        Some(&running(1.0)),
        &theme,
        320,
        240,
    ));
    assert!(
        has_color(&fb, theme.text),
        "stage should render the current/next text"
    );
}

#[test]
fn empty_state_shows_no_text() {
    let theme = StageTheme::dark();
    let fb = render(&compose_stage(None, None, None, &theme, 320, 240));
    assert!(
        !has_color(&fb, theme.text),
        "with no content and no timer there is no text"
    );
}

#[test]
fn a_running_timer_renders_a_numeric_readout() {
    // The speaker must be able to READ the remaining time, not just see a bar
    // (regression: the strip once rendered only a fill, no numbers).
    let theme = StageTheme::dark();
    let with_timer = render(&compose_stage(
        None,
        None,
        Some(&running(1.0)),
        &theme,
        320,
        240,
    ));
    assert!(
        has_color(&with_timer, theme.text),
        "a running countdown renders its M:SS readout in the strip"
    );
    // TIME UP renders its label over the alert bar.
    let up = TimerView {
        time_up: true,
        progress: 0.0,
        ..running(0.0)
    };
    let up_fb = render(&compose_stage(None, None, Some(&up), &theme, 320, 240));
    assert!(has_color(&up_fb, theme.text), "TIME UP renders its label");
}

#[test]
fn idle_monitor_shows_an_empty_track_not_a_full_bar() {
    // No running timer -> the strip is the dim track only; it must not be mistakable
    // for a full (just-started) countdown.
    let theme = StageTheme::dark();
    let idle = render(&compose_stage(None, None, None, &theme, 200, 100));
    assert_eq!(
        idle.pixel(5, 5).unwrap(),
        theme.track,
        "idle strip shows the track"
    );
    assert!(
        !has_color(&idle, theme.timer_ok),
        "no green fill when no timer runs"
    );
}

#[test]
fn main_and_stage_show_different_scenes_from_one_state() {
    // Acceptance: main + stage run concurrently showing different content.
    let slide = Slide::title("Song 1");
    let main = render(&compose_slide(&slide, &Theme::dark(), 320, 240));

    let mut stage = StageDisplay::new(320, 240, StageTheme::dark());
    stage.update(Some(&slide), None, Some(&running(1.0)));

    assert_ne!(
        main.bytes(),
        stage.output().bytes(),
        "main and stage outputs must differ for the same live slide"
    );
}

#[test]
fn identify_renders_a_distinct_screen_per_display() {
    let theme = StageTheme::dark();
    let one = render(&compose_identify(
        1,
        theme.identify_bg,
        theme.identify_marker,
        200,
        100,
    ));
    let three = render(&compose_identify(
        3,
        theme.identify_bg,
        theme.identify_marker,
        200,
        100,
    ));
    assert_ne!(
        one.bytes(),
        three.bytes(),
        "different display numbers must differ"
    );
    // Distinctive identify background + markers.
    assert_eq!(one.pixel(0, 0).unwrap(), theme.identify_bg);
    assert!(
        has_color(&one, theme.identify_marker),
        "identify draws markers"
    );
}

#[test]
fn presenter_identify_overlays_the_main_output() {
    let mut p = Presenter::new(200, 120, Theme::dark());
    p.stage(Slide::title("A"));
    p.go_live();
    p.identify(2);
    // The live output is now the identify screen, not a slide.
    assert!(p.live_slide().is_none());
    assert_eq!(p.live_output().pixel(0, 0).unwrap(), Rgba::rgb(20, 60, 140));
}

#[test]
fn stage_display_state_is_bounded_over_many_updates() {
    // No-leak: the stage output holds O(1) state across unbounded updates.
    let mut sd = StageDisplay::new(160, 90, StageTheme::dark());
    let expected = sd.output().byte_len();
    for i in 0..1000u32 {
        sd.update(
            Some(&Slide::title(format!("Line {i}"))),
            None,
            Some(&running(1.0)),
        );
    }
    assert_eq!(sd.output().byte_len(), expected);
    sd.identify(3); // still works, no panic
    assert_eq!(sd.output().byte_len(), expected);
}
