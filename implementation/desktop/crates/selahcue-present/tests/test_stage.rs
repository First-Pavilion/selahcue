//! Stage/confidence monitor: templates (Worship / Scripture / Timer-only), timer state,
//! current/next regions, the production-message overlay, dual-output independence, and
//! display identification (FR-037/040; stage templates + message per Figma 373-375 / 375-139).

#![allow(clippy::unwrap_used)]

use selahcue_core::timer::Timer;
use selahcue_engine::raster::{render, FrameBuffer};
use selahcue_engine::scene::{Frame, Rgba};
// `StageTemplate`/`MAX_STAGE_MESSAGE_LEN` come via the public `stage` module path (rather than
// a crate-root re-export) so this feature stays isolated from the crate's shared `lib.rs`.
use selahcue_present::stage::{StageTemplate, MAX_STAGE_MESSAGE_LEN};
use selahcue_present::{
    compose_identify, compose_slide, compose_stage, Presenter, Slide, StageContext, StageDisplay,
    StageTheme, Theme, TimerView, WallClock,
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

fn timed_up() -> TimerView {
    TimerView {
        time_up: true,
        progress: 0.0,
        ..running(0.0)
    }
}

/// The default (Worship) template with no message — the shape most tests exercise.
fn ws(
    c: Option<&Slide>,
    n: Option<&Slide>,
    t: Option<&TimerView>,
    theme: &StageTheme,
    w: u32,
    h: u32,
) -> Frame {
    compose_stage(
        c,
        n,
        t,
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        theme,
        w,
        h,
    )
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
fn timer_readout_colour_reflects_state() {
    let theme = StageTheme::dark();
    // Worship's bottom timer bar carries the state colour (green / amber / red).
    let ok = render(&ws(None, None, Some(&running(1.0)), &theme, 200, 100));
    assert!(has_color(&ok, theme.timer_ok), "on-time renders green");

    let warn = TimerView {
        warn: true,
        progress: 0.2,
        ..running(0.2)
    };
    let wfb = render(&ws(None, None, Some(&warn), &theme, 200, 100));
    assert!(has_color(&wfb, theme.timer_warn), "warn renders amber");

    let ufb = render(&ws(None, None, Some(&timed_up()), &theme, 200, 100));
    assert!(
        has_color(&ufb, theme.alert_wash),
        "TIME UP washes the bar red"
    );
}

#[test]
fn stage_current_region_auto_fits_a_long_verse_without_truncation_or_clip() {
    // The confidence monitor must AUTO-FIT (wrap to width + shrink) so the speaker sees
    // the WHOLE verse — parity with the audience output, never truncated or clipped (owner
    // refine). Esther 8:9 is the longest KJV verse.
    use selahcue_engine::raster::{measure_line_width, STAGE_FONT};
    use selahcue_engine::scene::{FontName, Layer};
    // The confidence monitor shapes its text in the bundled stage face (Inter), so the
    // fit check must measure in that same face — not the default — to match what was drawn.
    let stage_font = FontName::new(STAGE_FONT).unwrap();
    let theme = StageTheme::dark();
    let verse = "Then were the king's scribes called at that time in the third month, that is, \
        the month Sivan, on the three and twentieth day thereof; and it was written according \
        to all that Mordecai commanded unto the Jews, and to the deputies and rulers of the \
        provinces which are from India unto Ethiopia, an hundred twenty and seven provinces.";
    let current = Slide::new("Esther 8:9 (KJV)", [verse]);
    let (w, h) = (960u32, 540u32);
    // No next slide + no timer -> the only Text layers are the current region (the idle
    // timer bar draws no caption).
    let frame = ws(Some(&current), None, None, &theme, w, h);
    let texts: Vec<(&String, u32, i32, u32)> = frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, px, rect, .. } => Some((text, *px, rect.y, rect.w)),
            _ => None,
        })
        .collect();
    // It WRAPPED into multiple lines (not one clipped line)...
    assert!(
        texts.len() >= 3,
        "the long verse should wrap into multiple lines, got {}",
        texts.len()
    );
    // ...every line fits the region width (no horizontal clip)...
    for (t, px, _, rw) in &texts {
        assert!(
            measure_line_width(t, *px, Some(&stage_font), 700) <= *rw as f32 + 1.0,
            "stage line clips the region width: {t:?}"
        );
    }
    // ...no word is dropped (the reference + full verse are present)...
    let joined = texts
        .iter()
        .map(|(t, _, _, _)| t.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    assert!(joined.contains("Esther"), "the reference renders");
    for word in verse.split_whitespace() {
        assert!(joined.contains(word), "stage dropped the word {word:?}");
    }
    // ...and nothing overflows the current lyric band (bottom ≈ 0.64·height — the band sits
    // below the song header pill and above the NEXT/footer rows, Figma 373-133).
    let current_bottom = (h as f64 * 0.65) as i32 + 2;
    for (_, px, y, _) in &texts {
        assert!(
            *y + *px as i32 <= current_bottom,
            "stage text overflows the current region (y={y}, px={px})"
        );
    }
}

#[test]
fn current_and_next_regions_show_text_when_present() {
    let theme = StageTheme::dark();
    let current = Slide::title("CURRENT LINE");
    let next = Slide::title("NEXT LINE");
    // A larger frame so the muted NEXT region is big enough to leave exact-colour pixels.
    let fb = render(&ws(
        Some(&current),
        Some(&next),
        Some(&running(1.0)),
        &theme,
        640,
        400,
    ));
    assert!(
        has_color(&fb, theme.text),
        "stage should render the current text"
    );
    assert!(
        has_color(&fb, theme.muted),
        "the NEXT chip + line render in the muted ink"
    );
}

#[test]
fn empty_state_shows_no_text() {
    let theme = StageTheme::dark();
    let fb = render(&ws(None, None, None, &theme, 320, 240));
    assert!(
        !has_color(&fb, theme.text),
        "with no content and no timer there is no primary text"
    );
}

#[test]
fn a_running_timer_renders_a_numeric_readout() {
    // The speaker must be able to READ the remaining time, not just see a bar (regression:
    // the strip once rendered only a fill). The readout carries the state colour.
    let theme = StageTheme::dark();
    let with_timer = render(&ws(None, None, Some(&running(1.0)), &theme, 320, 240));
    assert!(
        has_color(&with_timer, theme.timer_ok),
        "a running countdown renders its M:SS readout in the on-time colour"
    );
    let up_fb = render(&ws(None, None, Some(&timed_up()), &theme, 320, 240));
    assert!(
        has_color(&up_fb, theme.alert_wash),
        "TIME UP washes the timer bar red"
    );
}

#[test]
fn idle_monitor_shows_no_timer_colour_and_no_text() {
    // No running timer -> the bar is bare (no state fill, no caption); it must not be
    // mistakable for a full (just-started) countdown.
    let theme = StageTheme::dark();
    let idle = render(&ws(None, None, None, &theme, 200, 100));
    assert!(
        !has_color(&idle, theme.timer_ok),
        "no green fill when no timer runs"
    );
    assert!(
        !has_color(&idle, theme.text),
        "an idle monitor shows no text"
    );
}

#[test]
fn stage_templates_render_differently() {
    // The operator picks one of three templates; each lays the same state out differently.
    let theme = StageTheme::dark();
    let cur = Slide::title("A VERSE OF SCRIPTURE");
    let t = running(0.5);
    let worship = render(&compose_stage(
        Some(&cur),
        None,
        Some(&t),
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        &theme,
        400,
        240,
    ));
    let scripture = render(&compose_stage(
        Some(&cur),
        None,
        Some(&t),
        StageTemplate::Scripture,
        None,
        &StageContext::default(),
        &theme,
        400,
        240,
    ));
    let timer_only = render(&compose_stage(
        Some(&cur),
        None,
        Some(&t),
        StageTemplate::TimerOnly,
        None,
        &StageContext::default(),
        &theme,
        400,
        240,
    ));
    assert_ne!(worship.bytes(), scripture.bytes(), "worship != scripture");
    assert_ne!(worship.bytes(), timer_only.bytes(), "worship != timer-only");
    assert_ne!(
        scripture.bytes(),
        timer_only.bytes(),
        "scripture != timer-only"
    );
}

#[test]
fn timer_only_shows_service_chrome_wall_clock_and_a_200px_readout() {
    // Figma 374-151: SERVICE TIMER (top-left) + wall clock (top-right), the live segment
    // label, a giant ~200px readout, and a "date · 12-hour time" footer.
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::title("SERMON");
    let ctx = StageContext {
        clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
        ..StageContext::default()
    };
    let t = TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(765), // 12:45
        time_up: false,
        warn: false,
        progress: 0.5,
    };
    let (w, h) = (1000u32, 563u32);
    let frame = compose_stage(
        Some(&cur),
        None,
        Some(&t),
        StageTemplate::TimerOnly,
        None,
        &ctx,
        &theme,
        w,
        h,
    );
    let texts: Vec<(&str, u32)> = frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, px, .. } => Some((text.as_str(), *px)),
            _ => None,
        })
        .collect();
    assert!(
        texts.iter().any(|(t, _)| *t == "SERVICE TIMER"),
        "the fixed screen label renders"
    );
    assert!(
        texts.iter().any(|(t, _)| *t == "SERMON"),
        "the live slide title labels the timer"
    );
    assert!(
        texts.iter().any(|(t, _)| *t == "10:42 AM"),
        "the header wall clock renders"
    );
    assert!(
        texts
            .iter()
            .any(|(t, _)| t.contains("Sunday · August 3, 2026") && t.contains("10:42 AM")),
        "the date + 12-hour time footer renders"
    );
    // The countdown is the giant readout — ~200px em (0.49·h line box × FONT_TO_LINE≈0.72).
    let readout = texts
        .iter()
        .find(|(t, _)| *t == "12:45")
        .expect("the running readout renders as M:SS");
    let want = (h as f64 * 0.49) as u32;
    assert!(
        readout.1.abs_diff(want) <= 2,
        "readout line-box {} px should be ≈0.49·h ({want} px) for a ~200px em",
        readout.1
    );
}

#[test]
fn timer_only_omits_clock_chrome_when_no_wall_clock_is_set() {
    // The wall clock is optional (composition stays clock-free): with no `WallClock`, the
    // header time and the date footer are simply absent — the timer still renders.
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let t = TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(765),
        time_up: false,
        warn: false,
        progress: 0.5,
    };
    let with_clock = compose_stage(
        None,
        None,
        Some(&t),
        StageTemplate::TimerOnly,
        None,
        &StageContext {
            clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
            ..StageContext::default()
        },
        &theme,
        400,
        240,
    );
    let without = compose_stage(
        None,
        None,
        Some(&t),
        StageTemplate::TimerOnly,
        None,
        &StageContext::default(),
        &theme,
        400,
        240,
    );
    let count_text = |f: &Frame| {
        f.layers
            .iter()
            .filter(|l| matches!(l, Layer::Text { .. }))
            .count()
    };
    assert!(
        count_text(&with_clock) > count_text(&without),
        "the wall clock adds the header time + date footer text layers"
    );
    // Still a valid timer screen without a clock: the readout is present.
    assert!(
        without
            .layers
            .iter()
            .any(|l| matches!(l, Layer::Text { text, .. } if text == "12:45")),
        "the readout renders even with no wall clock"
    );
}

#[test]
fn set_clock_round_trips_and_bounds_each_field() {
    let mut sd = StageDisplay::new(160, 90, StageTheme::dark());
    assert!(sd.clock().is_none());
    sd.set_clock(Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")));
    assert_eq!(sd.clock().map(|c| c.time()), Some("10:42 AM"));
    let long = "x".repeat(500);
    let wc = WallClock::new(&long, &long);
    assert!(
        wc.date().chars().count() <= WallClock::MAX_LEN
            && wc.time().chars().count() <= WallClock::MAX_LEN,
        "each wall-clock field is length-bounded (no-leak)"
    );
    sd.set_clock(None);
    assert!(sd.clock().is_none());
}

#[test]
fn worship_renders_song_header_verse_position_lyrics_and_footer_timer() {
    // Figma 373-133: a song-title pill (violet dot) + stanza position + clock header, big
    // centred lyrics (the BODY, not the title), a NEXT line, and a footer timer band.
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::new(
        "Amazing Grace",
        [
            "Amazing grace, how sweet the sound",
            "that saved a wretch like me",
        ],
    );
    let next = Slide::new("", ["I once was lost, but now am found"]);
    let ctx = StageContext {
        clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
        song_position: Some((2, 4)),
    };
    let t = TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(765), // 12:45
        time_up: false,
        warn: false,
        progress: 0.5,
    };
    let (w, h) = (1000u32, 563u32);
    let frame = compose_stage(
        Some(&cur),
        Some(&next),
        Some(&t),
        StageTemplate::Worship,
        None,
        &ctx,
        &theme,
        w,
        h,
    );
    let texts: Vec<&str> = frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, .. } => Some(text.as_str()),
            _ => None,
        })
        .collect();
    assert!(
        texts.contains(&"Amazing Grace"),
        "the song title labels the header pill"
    );
    assert!(
        texts.contains(&"Verse 2 of 4"),
        "the stanza position renders from the context"
    );
    assert!(texts.contains(&"10:42 AM"), "the header wall clock renders");
    assert!(
        texts.contains(&"SERVICE TIMER"),
        "the footer timer caption renders"
    );
    assert!(
        texts.contains(&"12:45"),
        "the footer countdown readout renders"
    );
    assert!(
        texts.iter().any(|s| s.contains("Amazing grace, how sweet")),
        "the stanza LYRIC (body) renders in the centre band"
    );
    assert!(
        texts.contains(&"I once was lost, but now am found"),
        "the NEXT line renders"
    );
    // The violet 'live song' accent dot (Figma 373-136) is present.
    let fb = render(&frame);
    assert!(
        has_color(&fb, Rgba::rgb(0x8b, 0x5c, 0xf6)),
        "the song pill shows the violet live-song dot"
    );
    // No stanza position when the context has none (honest — never a fabricated count).
    let ctx2 = StageContext {
        song_position: None,
        ..ctx.clone()
    };
    let f2 = compose_stage(
        Some(&cur),
        Some(&next),
        Some(&t),
        StageTemplate::Worship,
        None,
        &ctx2,
        &theme,
        w,
        h,
    );
    assert!(
        !f2.layers
            .iter()
            .any(|l| matches!(l, Layer::Text { text, .. } if text.starts_with("Verse "))),
        "no stanza position label when the context has none"
    );
}

#[test]
fn scripture_renders_gold_reference_left_verse_and_countdown_panel() {
    // Figma 374-128: header + clock, a GOLD reference over a left-aligned verse, a NEXT line,
    // and a right panel with a status pill + TIME LEFT + the readout.
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::new(
        "Isaiah 61:5 · KJV",
        ["And strangers shall stand and feed your flocks, and the sons of the alien."],
    );
    let next = Slide::new(
        "Isaiah 61:6",
        ["But ye shall be named the Priests of the Lord"],
    );
    let ctx = StageContext {
        clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
        song_position: None,
    };
    let t = TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(765), // 12:45
        time_up: false,
        warn: false,
        progress: 0.5,
    };
    let (w, h) = (1000u32, 563u32);
    let frame = compose_stage(
        Some(&cur),
        Some(&next),
        Some(&t),
        StageTemplate::Scripture,
        None,
        &ctx,
        &theme,
        w,
        h,
    );
    let texts: Vec<&str> = frame
        .layers
        .iter()
        .filter_map(|l| match l {
            Layer::Text { text, .. } => Some(text.as_str()),
            _ => None,
        })
        .collect();
    assert!(
        texts.contains(&"STAGE · SCRIPTURE"),
        "the header label renders"
    );
    assert!(
        texts.iter().any(|s| s.contains("ISAIAH 61:5")),
        "the reference renders UPPERCASED"
    );
    assert!(texts.contains(&"10:42 AM"), "the header wall clock renders");
    assert!(
        texts.contains(&"ON TIME"),
        "the status pill shows ON TIME while comfortably running"
    );
    assert!(texts.contains(&"TIME LEFT"), "the panel caption renders");
    assert!(
        texts.contains(&"12:45"),
        "the panel countdown readout renders"
    );
    assert!(
        texts.iter().any(|s| s.contains("And strangers shall")),
        "the verse body renders"
    );
    assert!(
        texts.iter().any(|s| s.contains("Isaiah 61:6")),
        "the NEXT reference renders"
    );
    // The reference renders in the gold accent (the only accent-coloured element here).
    let fb = render(&frame);
    assert!(
        has_color(&fb, theme.accent),
        "the scripture reference renders in gold"
    );
}

#[test]
fn scripture_panel_pill_and_wash_reflect_the_timer_state() {
    // The right panel signals state: ON TIME (green) / HURRY (amber) / TIME UP (red pill +
    // a panel-only red wash that never touches the verse column).
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::new("Isaiah 61:5", ["And strangers shall stand."]);
    let (w, h) = (1000u32, 563u32);
    let texts = |f: &Frame| {
        f.layers
            .iter()
            .filter_map(|l| match l {
                Layer::Text { text, .. } => Some(text.clone()),
                _ => None,
            })
            .collect::<Vec<_>>()
    };
    // WARN → HURRY (amber readout).
    let warn = TimerView {
        warn: true,
        ..running(0.2)
    };
    let fw = compose_stage(
        Some(&cur),
        None,
        Some(&warn),
        StageTemplate::Scripture,
        None,
        &StageContext::default(),
        &theme,
        w,
        h,
    );
    assert!(texts(&fw).iter().any(|s| s == "HURRY"), "warn shows HURRY");
    assert!(
        has_color(&render(&fw), theme.timer_warn),
        "the warn readout is amber"
    );
    // TIME UP → a TIME UP pill + a panel-only red wash (the LEFT verse column stays dark).
    let up = compose_stage(
        Some(&cur),
        None,
        Some(&timed_up()),
        StageTemplate::Scripture,
        None,
        &StageContext::default(),
        &theme,
        w,
        h,
    );
    let fbu = render(&up);
    assert!(texts(&up).iter().any(|s| s == "TIME UP"), "TIME UP pill");
    assert!(
        has_color(&fbu, theme.alert_wash),
        "the panel washes red at TIME UP"
    );
    assert_eq!(
        fbu.pixel(3, 3).unwrap(),
        theme.background,
        "the LEFT column is NOT washed (panel only, Figma 374-128)"
    );
}

#[test]
fn scripture_next_line_is_truncated_with_an_ellipsis_when_it_overflows() {
    // The NEXT reference/verse is clipped to the left column with an ASCII ellipsis so it can
    // never spill into the timer panel (the bundled Latin face has no `…` glyph).
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::new("Isaiah 61:5", ["verse"]);
    let long = "But ye shall be named the Priests of the Lord: men shall call you the \
                Ministers of our God: ye shall eat the riches of the Gentiles"
        .to_string();
    let next = Slide::new("Isaiah 61:6", [long.clone()]);
    let t = TimerView {
        elapsed_secs: 0,
        remaining_secs: Some(765),
        time_up: false,
        warn: false,
        progress: 0.5,
    };
    let frame = compose_stage(
        Some(&cur),
        Some(&next),
        Some(&t),
        StageTemplate::Scripture,
        None,
        &StageContext::default(),
        &theme,
        1000,
        563,
    );
    let next_line = frame
        .layers
        .iter()
        .find_map(|l| match l {
            Layer::Text { text, .. } if text.starts_with("Isaiah 61:6") => Some(text.clone()),
            _ => None,
        })
        .expect("the NEXT line renders");
    assert!(
        next_line.ends_with("..."),
        "an overflowing NEXT line is clipped with an ellipsis: {next_line:?}"
    );
    let full = format!("Isaiah 61:6 · {long}");
    assert!(
        next_line.chars().count() < full.chars().count(),
        "the ellipsized line is shorter than the full label"
    );
}

#[test]
fn set_song_position_round_trips() {
    let mut sd = StageDisplay::new(160, 90, StageTheme::dark());
    assert_eq!(sd.song_position(), None);
    sd.set_song_position(Some((2, 4)));
    assert_eq!(sd.song_position(), Some((2, 4)));
    sd.set_song_position(None);
    assert_eq!(sd.song_position(), None);
}

#[test]
fn worship_title_only_item_shows_the_title_as_content_without_a_song_pill() {
    // A title-only item (no lyrics) is not a "song": it shows its title as the centre content
    // and gets NO violet song pill (which is reserved for a real song with stanzas).
    use selahcue_engine::scene::Layer;
    let theme = StageTheme::dark();
    let cur = Slide::title("WELCOME");
    let frame = compose_stage(
        Some(&cur),
        None,
        None,
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        &theme,
        1000,
        563,
    );
    assert!(
        frame
            .layers
            .iter()
            .any(|l| matches!(l, Layer::Text { text, .. } if text.contains("WELCOME"))),
        "the title renders as the centre content"
    );
    assert!(
        !has_color(&render(&frame), Rgba::rgb(0x8b, 0x5c, 0xf6)),
        "a title-only item shows no violet song pill"
    );
}

#[test]
fn the_composer_never_panics_on_pathological_input() {
    // The confidence monitor renders UNTRUSTED slide content (imported plans, remote
    // controllers). It must NEVER panic — a colossal title/verse/next line (which would once
    // saturate the width estimate and overflow the pill/next SUMS) and extreme dimensions
    // (which would once overflow the i32 panel geometry) must both compose safely.
    let theme = StageTheme::dark();
    let huge = "x".repeat(30_000_000); // beyond the pre-cap u32 overflow threshold
    let cur = Slide::new(huge.clone(), ["a short verse line"]);
    let next = Slide::new(huge.clone(), ["short"]);
    let ctx = StageContext {
        clock: Some(WallClock::new("Sunday · August 3, 2026", "10:42 AM")),
        song_position: Some((u16::MAX, 1)),
    };
    let t = TimerView {
        elapsed_secs: u32::MAX,
        remaining_secs: Some(u32::MAX),
        time_up: false,
        warn: true,
        progress: 2.0,
    };
    for tmpl in [
        StageTemplate::Worship,
        StageTemplate::Scripture,
        StageTemplate::TimerOnly,
    ] {
        for (w, h) in [(1u32, 1u32), (u32::MAX, u32::MAX), (1920, 1080)] {
            // Returns a frame; the assertion is simply that this does not panic.
            let _ = compose_stage(
                Some(&cur),
                Some(&next),
                Some(&t),
                tmpl,
                Some("Wrap up now"),
                &ctx,
                &theme,
                w,
                h,
            );
        }
    }
}

#[test]
fn time_up_words_pulse_between_two_inks_while_the_wash_stays_steady() {
    // At TIME UP only the WORDS pulse — a calm one-second bright/dim alternation (0.5 Hz, far
    // below the WCAG 2.3.1 flash threshold). The red wash behind them is identical every
    // second; a rapid full-screen strobe would be a seizure risk.
    let theme = StageTheme::dark();
    let even = TimerView {
        elapsed_secs: 4,
        remaining_secs: Some(0),
        time_up: true,
        warn: false,
        progress: 0.0,
    };
    let odd = TimerView {
        elapsed_secs: 5,
        ..even
    };
    let up = |t: &TimerView, tmpl| {
        compose_stage(
            None,
            None,
            Some(t),
            tmpl,
            None,
            &StageContext::default(),
            &theme,
            400,
            240,
        )
    };
    for tmpl in [
        StageTemplate::TimerOnly,
        StageTemplate::Worship,
        StageTemplate::Scripture,
    ] {
        let fe = render(&up(&even, tmpl));
        let fo = render(&up(&odd, tmpl));
        assert_ne!(
            fe.bytes(),
            fo.bytes(),
            "the TIME UP words differ between an even and odd second ({tmpl:?})"
        );
        assert_eq!(
            fe.pixel(3, 3),
            fo.pixel(3, 3),
            "the wash/background is identical second-to-second ({tmpl:?})"
        );
    }
    // The two inks are the brightened glow (even second) and the base alert red (odd second).
    let bright = theme.timer_alert.lerp(Rgba::WHITE, 350);
    assert!(
        has_color(&render(&up(&even, StageTemplate::TimerOnly)), bright),
        "the even second glows brighter than the base alert red"
    );
    assert!(
        has_color(
            &render(&up(&odd, StageTemplate::TimerOnly)),
            theme.timer_alert
        ),
        "the odd second is the base alert red"
    );
}

#[test]
fn time_up_is_full_screen_for_timer_only_but_region_only_for_worship() {
    // Behaviour spec (375-139): timer-only reddens the whole screen at TIME UP; worship
    // reddens only its bottom bar, leaving the content area untouched.
    let theme = StageTheme::dark();
    let to = render(&compose_stage(
        None,
        None,
        Some(&timed_up()),
        StageTemplate::TimerOnly,
        None,
        &StageContext::default(),
        &theme,
        200,
        120,
    ));
    assert_eq!(
        to.pixel(3, 3).unwrap(),
        theme.alert_wash,
        "timer-only TIME UP washes the whole screen"
    );
    let wsu = render(&compose_stage(
        None,
        None,
        Some(&timed_up()),
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        &theme,
        200,
        120,
    ));
    assert_eq!(
        wsu.pixel(3, 3).unwrap(),
        theme.background,
        "worship TIME UP does not touch the content area"
    );
    assert!(
        has_color(&wsu, theme.alert_wash),
        "worship TIME UP reddens the timer bar region"
    );
}

#[test]
fn a_production_message_overlays_and_frames_the_stage() {
    // A production message is a stage-only overlay: it dims the scene and draws a gold frame.
    let theme = StageTheme::dark();
    let cur = Slide::title("NOW LINE");
    let plain = render(&compose_stage(
        Some(&cur),
        None,
        None,
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        &theme,
        320,
        200,
    ));
    let with_msg = render(&compose_stage(
        Some(&cur),
        None,
        None,
        StageTemplate::Worship,
        Some("WRAP UP - 2 MIN LEFT"),
        &StageContext::default(),
        &theme,
        320,
        200,
    ));
    assert_ne!(
        plain.bytes(),
        with_msg.bytes(),
        "a message changes the stage output"
    );
    assert!(
        has_color(&with_msg, theme.accent),
        "the message frame renders in the gold accent"
    );
    // A blank message is a no-op (no overlay).
    let blank = render(&compose_stage(
        Some(&cur),
        None,
        None,
        StageTemplate::Worship,
        Some("   "),
        &StageContext::default(),
        &theme,
        320,
        200,
    ));
    assert_eq!(
        plain.bytes(),
        blank.bytes(),
        "a blank message draws no overlay"
    );
}

#[test]
fn set_message_bounds_and_a_blank_clears() {
    let mut sd = StageDisplay::new(160, 90, StageTheme::dark());
    assert!(sd.message().is_none());
    sd.set_message("WRAP UP");
    assert_eq!(sd.message(), Some("WRAP UP"));
    sd.set_message("   "); // blank clears the overlay
    assert!(sd.message().is_none());
    let long = "x".repeat(500);
    sd.set_message(&long);
    assert!(
        sd.message().unwrap().chars().count() <= MAX_STAGE_MESSAGE_LEN,
        "the message is bounded (no-leak)"
    );
}

#[test]
fn set_template_switches_the_layout() {
    let mut sd = StageDisplay::new(200, 120, StageTheme::dark());
    assert_eq!(sd.template(), StageTemplate::Worship, "default is Worship");
    let cur = Slide::title("X");
    sd.update(Some(&cur), None, Some(&running(0.5)));
    let worship_bytes = sd.output().bytes().to_vec();
    sd.set_template(StageTemplate::TimerOnly);
    sd.update(Some(&cur), None, Some(&running(0.5)));
    assert_ne!(
        sd.output().bytes(),
        &worship_bytes[..],
        "switching the template changes the output"
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
