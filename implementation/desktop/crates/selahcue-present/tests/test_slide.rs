//! Slide model + serde (persistence / IPC ready).

#![allow(clippy::unwrap_used)]

use selahcue_present::{Slide, Theme};

#[test]
fn blank_detection() {
    assert!(Slide::title("").is_blank());
    assert!(Slide::title("   ").is_blank());
    assert!(Slide::new("", [" ", ""]).is_blank());
    assert!(!Slide::title("Hi").is_blank());
    assert!(!Slide::new("", ["body"]).is_blank());
}

#[test]
fn lines_iterates_title_then_body() {
    let slide = Slide::new("Title", ["a", "b"]);
    let lines: Vec<_> = slide.lines().collect();
    assert_eq!(lines, ["Title", "a", "b"]);
}

#[test]
fn slide_and_theme_serde_round_trip() {
    let slide = Slide::new("Title", ["line 1", "line 2"]);
    let back: Slide = serde_json::from_str(&serde_json::to_string(&slide).unwrap()).unwrap();
    assert_eq!(back, slide);

    let theme = Theme::dark();
    let back: Theme = serde_json::from_str(&serde_json::to_string(&theme).unwrap()).unwrap();
    assert_eq!(back, theme);
}

#[test]
fn builtin_themes_are_distinct_designs_and_names_round_trip() {
    // Every built-in resolves by name, and its name round-trips (so a Presenter
    // built from a Theme value can report its picker selection — S8-3b).
    for name in Theme::BUILTIN_NAMES {
        let t = Theme::builtin(name).expect("known built-in resolves");
        assert_eq!(t.name_of(), Some(*name), "name round-trips for {name}");
    }
    assert_eq!(Theme::builtin("does-not-exist"), None);
    assert_eq!(
        Theme::BUILTIN_NAMES,
        &["classic", "high-contrast", "lower-third"]
    );
    assert_eq!(
        Theme::default().name_of(),
        Some("classic"),
        "default = classic"
    );

    // The three differ as DESIGN TEMPLATES, not just colours: lower-third is
    // left-aligned and lower on the frame (position + alignment), not merely a
    // recoloured classic.
    let c = Theme::classic();
    let l = Theme::lower_third();
    assert_ne!(c.background, l.background);
    assert_ne!(
        c.body.align_h, l.body.align_h,
        "lower-third is left-aligned, classic is centred"
    );
    assert!(
        l.body.y_permille > c.body.y_permille,
        "lower-third body sits lower (bottom band)"
    );
}
