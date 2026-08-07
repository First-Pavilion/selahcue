//! Preview→Live playback over a deck: staging isolation, navigation, and injected-clock
//! auto-advance (Design 2.0 node 329:124).

#![allow(clippy::unwrap_used)]

use std::time::{Duration, Instant};

use selahcue_engine::raster::render;
use selahcue_present::{Background, DeckSession, Rgba, SlideDeck, Theme};

/// A deck whose slide `i` has a distinct solid background `(i*40, 0, 0)` and the given
/// auto-advance seconds — so composed frames differ per slide and dwell can be driven.
fn deck(auto: &[Option<u32>]) -> SlideDeck {
    let mut d = SlideDeck::new("Deck");
    for (i, a) in auto.iter().enumerate() {
        let id = d.add_slide().unwrap();
        let s = d.get_mut(id).unwrap();
        s.background = Some(Background::Solid(Rgba::rgb((i as u8) * 40, 0, 0)));
        s.auto_advance_secs = *a;
    }
    d
}

fn session(auto: &[Option<u32>]) -> DeckSession {
    DeckSession::new(deck(auto), Theme::classic(), 32, 18)
}

#[test]
fn staging_and_navigation_never_change_live() {
    // The central invariant (FR-012): only go_live changes Live.
    let mut s = session(&[None, None, None]);
    assert_eq!(s.preview_index(), Some(0));
    assert_eq!(s.live_index(), None, "nothing is live at first");

    assert!(s.stage(1));
    assert_eq!(s.preview_index(), Some(1));
    assert_eq!(s.live_index(), None, "staging did NOT touch Live");

    assert!(s.go_live());
    assert_eq!(s.live_index(), Some(1), "go_live commits the staged slide");

    // Navigating Preview after going live must not move Live.
    assert!(s.next());
    assert_eq!(s.preview_index(), Some(2));
    assert_eq!(
        s.live_index(),
        Some(1),
        "Preview navigation left Live alone"
    );
}

#[test]
fn navigation_stops_at_the_ends() {
    let mut s = session(&[None, None]);
    assert!(!s.previous(), "already at the start");
    assert!(s.next());
    assert!(!s.next(), "already at the last slide");
    assert_eq!(s.preview_index(), Some(1));
    assert_eq!(s.len(), 2, "N of M reports the slide count");
}

#[test]
fn preview_and_live_frames_track_their_cursors() {
    let mut s = session(&[None, None]);
    assert!(s.live_frame().is_none(), "nothing live → no live frame");
    let preview0 = render(&s.preview_frame().unwrap());
    assert!(s.stage(1));
    s.go_live();
    let live1 = render(&s.live_frame().unwrap());
    // Slide 0 and slide 1 have distinct backgrounds, so their frames differ.
    assert_ne!(
        preview0.bytes(),
        live1.bytes(),
        "distinct slides render differently"
    );
}

#[test]
fn auto_advance_fires_only_after_the_dwell_elapses() {
    // Slide 0 dwells 5s then advances; slide 1 is "Off" (holds).
    let mut s = session(&[Some(5), None]);
    s.go_live();
    assert_eq!(s.live_index(), Some(0));
    let t0 = Instant::now();
    assert!(!s.tick(t0), "first tick starts the dwell, does not advance");
    assert!(!s.tick(t0 + Duration::from_secs(4)), "4s < 5s → hold");
    assert_eq!(s.live_index(), Some(0));
    assert!(s.tick(t0 + Duration::from_secs(5)), "5s → advance");
    assert_eq!(s.live_index(), Some(1), "advanced to the next slide");
    // Slide 1 has no auto-advance → it holds forever.
    assert!(!s.tick(t0 + Duration::from_secs(100)));
    assert_eq!(s.live_index(), Some(1));
}

#[test]
fn auto_advance_stops_at_the_last_slide_no_wrap() {
    let mut s = session(&[None, Some(1)]);
    assert!(s.stage(1));
    s.go_live();
    assert_eq!(s.live_index(), Some(1));
    let t0 = Instant::now();
    assert!(!s.tick(t0), "start the dwell");
    // Even long past the dwell, the last slide does not wrap around.
    assert!(!s.tick(t0 + Duration::from_secs(10)));
    assert_eq!(s.live_index(), Some(1), "the last slide holds");
}

#[test]
fn go_live_restarts_the_dwell() {
    // A slide re-staged and re-lived restarts its dwell from the next tick (no stale deadline).
    let mut s = session(&[Some(5), None]);
    s.go_live();
    let t0 = Instant::now();
    assert!(!s.tick(t0)); // dwell starts at t0
                          // Re-go-live the same slide 0: the dwell must restart, so a tick at t0+3 (only 3s since the
                          // FIRST start) still holds rather than firing off a stale 5s deadline.
    assert!(s.stage(0));
    s.go_live();
    assert!(
        !s.tick(t0 + Duration::from_secs(3)),
        "restarted dwell → not yet elapsed"
    );
    assert!(
        s.tick(t0 + Duration::from_secs(8)),
        "5s after the restart → advance"
    );
    assert_eq!(s.live_index(), Some(1));
}

#[test]
fn a_backwards_clock_tick_holds_and_never_panics() {
    // Monotonic-clock defence: a `now` earlier than when the slide went live must saturate to
    // zero elapsed (hold), not panic. Arm the dwell at a LATER instant, then tick at an earlier
    // (but still valid) instant.
    let mut s = session(&[Some(5), None]);
    s.go_live();
    let base = Instant::now();
    let armed = base + Duration::from_secs(10);
    assert!(!s.tick(armed), "arm the dwell at the later instant");
    assert!(
        !s.tick(base),
        "an earlier 'now' → zero elapsed, hold (no panic)"
    );
    assert_eq!(
        s.live_index(),
        Some(0),
        "Live is unchanged by the backwards tick"
    );
}

#[test]
fn auto_advance_chains_across_consecutive_slides() {
    // Two auto-advance slides in a row: the advance resets the dwell so the NEXT slide's timer
    // arms from the advance instant — Live steps 0 → 1 → 2.
    let mut s = session(&[Some(5), Some(5), None]);
    s.go_live();
    let t0 = Instant::now();
    assert!(!s.tick(t0), "arm slide 0's dwell");
    assert!(s.tick(t0 + Duration::from_secs(5)), "0 → 1");
    assert_eq!(s.live_index(), Some(1));
    assert!(
        !s.tick(t0 + Duration::from_secs(6)),
        "only 1s into slide 1 → hold"
    );
    assert!(
        s.tick(t0 + Duration::from_secs(10)),
        "5s into slide 1 → 1 → 2"
    );
    assert_eq!(s.live_index(), Some(2));
}

#[test]
fn set_theme_restyles_live_without_moving_the_cursors() {
    // A theme switch restyles the retained live slide (content ⟂ theme, zero content loss) and
    // leaves the staged/live cursors alone. The slide has no per-slide background, so the theme's
    // background drives the pixels and a theme change is visible.
    let mut d = SlideDeck::new("Deck");
    d.add_slide().unwrap();
    let mut s = DeckSession::new(d, Theme::classic(), 16, 9);
    s.go_live();
    let (pv, lv) = (s.preview_index(), s.live_index());
    let before = render(&s.live_frame().unwrap());
    s.set_theme(Theme::high_contrast());
    assert_eq!(
        (s.preview_index(), s.live_index()),
        (pv, lv),
        "cursors are unchanged by a theme switch"
    );
    let after = render(&s.live_frame().unwrap());
    assert_ne!(
        before.bytes(),
        after.bytes(),
        "the live frame restyles under the new theme"
    );
}

#[test]
fn an_empty_deck_session_is_inert() {
    let mut s = DeckSession::new(SlideDeck::new("Empty"), Theme::classic(), 32, 18);
    assert!(s.is_empty());
    assert_eq!(s.preview_index(), None);
    assert!(!s.stage(0));
    assert!(!s.next());
    assert!(!s.previous());
    assert!(!s.go_live());
    assert!(s.preview_frame().is_none());
    assert!(s.live_frame().is_none());
    assert!(!s.tick(Instant::now()));
}
