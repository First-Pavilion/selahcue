//! Slide model + serde (persistence / IPC ready).

#![allow(clippy::unwrap_used)]

use selahcue_present::{
    Background, Slide, SongAttribution, Theme, BACKGROUND_PRESETS, MAX_SONG_ATTRIBUTION_FIELD_LEN,
};

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
        &[
            "classic",
            "high-contrast",
            "lower-third",
            "scripture-full",
            "song-center",
        ],
        "OUT-009: two per-content-role built-ins added, none removed"
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

// --- OUT-002/003/004/009/016/017: per-content-role built-ins (Scripture — Full, Song — Center) ---

#[test]
fn scripture_full_and_song_center_differ_as_design_templates_not_just_colour() {
    let c = Theme::classic();
    let sf = Theme::scripture_full();
    let sc = Theme::song_center();

    // OUT-002: scripture-full is the first built-in to actually USE the (pre-existing)
    // gradient background capability — a real, code-visible structural difference from
    // every other built-in, all of which are `Background::Solid`.
    assert!(
        matches!(sf.background, Background::Gradient(_)),
        "OUT-002: scripture-full has a gradient background, got {:?}",
        sf.background
    );
    assert!(
        matches!(c.background, Background::Solid(_))
            && matches!(Theme::high_contrast().background, Background::Solid(_))
            && matches!(Theme::lower_third().background, Background::Solid(_))
            && matches!(sc.background, Background::Solid(_)),
        "every OTHER built-in stays a solid fill (scripture-full is the only gradient one)"
    );

    // OUT-016/017: scripture-full's reference + body are BOTH larger than classic's, and
    // the reference sits lower — a genuine geometry difference, not a recolour.
    assert!(
        sf.title.size_permille > c.title.size_permille,
        "OUT-016: scripture-full's reference is bigger than classic's"
    );
    assert!(
        sf.title.y_permille > c.title.y_permille,
        "OUT-016: scripture-full's reference sits lower than classic's"
    );
    assert!(
        sf.body.size_permille > c.body.size_permille,
        "OUT-017: scripture-full's body is bigger than classic's"
    );

    // OUT-005 (context for OUT-009/OUT-004): song-center hides its title/reference region —
    // the Song mock has no reference line, only stanza lyrics.
    assert!(
        !sc.title.visible,
        "song-center hides the reference region (no title line on a stanza slide)"
    );
    // OUT-004: song-center's body leading is looser than classic's (stanza breathing room).
    assert!(
        sc.body.line_height_permille > c.body.line_height_permille,
        "OUT-004: song-center's leading is looser than classic's"
    );
    // OUT-009: song-center is the first built-in to carry a footer (CCLI/attribution,
    // OUT-006/OUT-015's model wired to a real per-role template for the first time).
    assert!(
        sc.footer.is_some(),
        "OUT-009: song-center carries a footer region"
    );
    for name in ["classic", "high-contrast", "lower-third", "scripture-full"] {
        assert!(
            Theme::builtin(name).unwrap().footer.is_none(),
            "{name} has no CCLI obligation, so it ships with no footer"
        );
    }

    // Every new built-in still resolves + round-trips its name (S8-3b), matching every
    // other built-in.
    assert_eq!(sf.name_of(), Some("scripture-full"));
    assert_eq!(sc.name_of(), Some("song-center"));
}

#[test]
fn background_presets_are_five_distinct_design2_tokens() {
    // OUT-010: derived from tokens::design2 per Q-11's own recorded default (base / inset /
    // accent-soft / gold-soft / preview-soft) — no new colour invented.
    assert_eq!(BACKGROUND_PRESETS.len(), 5);
    let mut seen = std::collections::HashSet::new();
    for c in BACKGROUND_PRESETS {
        assert!(
            seen.insert((c.r, c.g, c.b, c.a)),
            "preset colours must be pairwise distinct, got a repeat: {c:?}"
        );
    }
    // Matches tokens::design2 exactly, in the documented order.
    use selahcue_present::tokens::design2;
    assert_eq!(
        BACKGROUND_PRESETS,
        [
            design2::BASE.rgba,
            design2::INSET.rgba,
            design2::ACCENT_SOFT.rgba,
            design2::GOLD_SOFT.rgba,
            design2::PREVIEW_SOFT.rgba,
        ]
    );
}

// --- OUT-006 / OUT-015: song attribution + theme footer (CCLI/attribution model gap) ---

#[test]
fn no_builtin_theme_or_plain_slide_emits_a_footer_or_song_key() {
    // Additive/backward-compatible (the ticket's explicit requirement): every BUILT-IN theme
    // WITH NO CCLI OBLIGATION keeps `footer` unset, so neither key appears in the serialized
    // JSON — pinned fixtures elsewhere stay byte-identical to before this field existed,
    // exactly like `band`/`font`/`letter_spacing_permille` before it. `song-center` (OUT-009)
    // is the one deliberate exception — see the next test.
    for name in ["classic", "high-contrast", "lower-third", "scripture-full"] {
        let theme = Theme::builtin(name).unwrap();
        assert_eq!(theme.footer, None, "{name} ships with no footer by default");
        let json = serde_json::to_string(&theme).unwrap();
        assert!(
            !json.contains("\"footer\""),
            "{name}'s JSON must omit the footer key when unset, got: {json}"
        );
    }

    let slide = Slide::new("Title", ["line 1", "line 2"]);
    assert_eq!(slide.song, None);
    let json = serde_json::to_string(&slide).unwrap();
    assert!(
        !json.contains("\"song\""),
        "a slide with no song metadata must omit the song key, got: {json}"
    );
}

#[test]
fn song_center_ships_with_a_footer_that_round_trips() {
    // OUT-009: song-center is the ONE built-in that intentionally sets a footer region (a
    // deliberate exception to the rule the previous test pins for the other four) — verified
    // both at the Rust level and on the wire (the JSON key IS present, unlike every other
    // built-in).
    let theme = Theme::builtin("song-center").unwrap();
    assert!(theme.footer.is_some(), "song-center ships with a footer");
    let json = serde_json::to_string(&theme).unwrap();
    assert!(
        json.contains("\"footer\""),
        "song-center's JSON must include the footer key, got: {json}"
    );
    let back: Theme = serde_json::from_str(&json).unwrap();
    assert_eq!(back, theme, "song-center round-trips through JSON");
}

#[test]
fn theme_footer_and_slide_song_serde_round_trip() {
    let mut theme = Theme::classic();
    theme.footer = Some(theme.title); // any RegionStyle works; reuse an existing one
    let back: Theme = serde_json::from_str(&serde_json::to_string(&theme).unwrap()).unwrap();
    assert_eq!(back, theme);

    let song = SongAttribution {
        author: Some("Sinach".to_string()),
        ccli_number: Some("7115744".to_string()),
        copyright_year: Some("2015".to_string()),
        publisher: Some("Integrity Music".to_string()),
    };
    let slide = Slide::title("Way Maker").with_song(song.clone());
    assert_eq!(slide.song, Some(song));
    let back: Slide = serde_json::from_str(&serde_json::to_string(&slide).unwrap()).unwrap();
    assert_eq!(back, slide);
}

#[test]
fn song_attribution_footer_line_formats_ccli_and_author() {
    let both = SongAttribution {
        author: Some("Sinach".to_string()),
        ccli_number: Some("7115744".to_string()),
        ..Default::default()
    };
    assert_eq!(both.footer_line(), "CCLI #7115744 \u{b7} Sinach");
    assert!(!both.is_blank());

    let ccli_only = SongAttribution {
        ccli_number: Some("7115744".to_string()),
        ..Default::default()
    };
    assert_eq!(ccli_only.footer_line(), "CCLI #7115744");

    let author_only = SongAttribution {
        author: Some("Sinach".to_string()),
        ..Default::default()
    };
    assert_eq!(author_only.footer_line(), "Sinach");

    // Whitespace-only fields count as absent (trimmed), same as blank title/body elsewhere.
    let whitespace = SongAttribution {
        author: Some("   ".to_string()),
        ccli_number: Some("".to_string()),
        ..Default::default()
    };
    assert_eq!(whitespace.footer_line(), "");
    assert!(whitespace.is_blank());

    let empty = SongAttribution::default();
    assert_eq!(empty.footer_line(), "");
    assert!(empty.is_blank());
}

#[test]
fn slide_footer_line_needs_both_song_metadata_and_it_being_non_blank() {
    // No song metadata at all.
    let slide = Slide::new("Title", ["body"]);
    assert_eq!(slide.footer_line(), None);

    // Song metadata present but entirely blank (e.g. an operator cleared every field).
    let slide = Slide::title("Song").with_song(SongAttribution::default());
    assert_eq!(slide.footer_line(), None);

    // Real song metadata.
    let slide = Slide::title("Song").with_song(SongAttribution {
        ccli_number: Some("7115744".to_string()),
        author: Some("Sinach".to_string()),
        ..Default::default()
    });
    assert_eq!(
        slide.footer_line().as_deref(),
        Some("CCLI #7115744 \u{b7} Sinach")
    );
}

#[test]
fn song_attribution_alone_does_not_make_a_slide_non_blank() {
    // `is_blank` still governs whether the slide renders as background-only — song
    // attribution is metadata for a footer, not visible title/body content.
    let slide = Slide::title("").with_song(SongAttribution {
        ccli_number: Some("7115744".to_string()),
        ..Default::default()
    });
    assert!(slide.is_blank());
}

#[test]
fn song_attribution_within_bounds_rejects_an_over_length_field_and_accepts_a_boundary_one() {
    let ok = SongAttribution {
        author: Some("a".repeat(MAX_SONG_ATTRIBUTION_FIELD_LEN)),
        ..Default::default()
    };
    assert!(ok.within_bounds(), "exactly at the cap is accepted");

    let over = SongAttribution {
        author: Some("a".repeat(MAX_SONG_ATTRIBUTION_FIELD_LEN + 1)),
        ..Default::default()
    };
    assert!(!over.within_bounds(), "one char over the cap is rejected");

    // Every field is checked independently, not just the first.
    let over_ccli = SongAttribution {
        ccli_number: Some("1".repeat(MAX_SONG_ATTRIBUTION_FIELD_LEN + 1)),
        ..Default::default()
    };
    assert!(!over_ccli.within_bounds());
    let over_year = SongAttribution {
        copyright_year: Some("2".repeat(MAX_SONG_ATTRIBUTION_FIELD_LEN + 1)),
        ..Default::default()
    };
    assert!(!over_year.within_bounds());
    let over_publisher = SongAttribution {
        publisher: Some("p".repeat(MAX_SONG_ATTRIBUTION_FIELD_LEN + 1)),
        ..Default::default()
    };
    assert!(!over_publisher.within_bounds());

    assert!(
        SongAttribution::default().within_bounds(),
        "all-absent is within bounds"
    );
}
