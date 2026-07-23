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
