//! Token audit (story 86ajp0b3d): the canonical colours match UX-CANONICAL §4
//! exactly, every audited pairing meets WCAG-AA, and every surface (operator
//! webview, Flutter controller, stage display) carries the same values.

#![allow(clippy::unwrap_used)]

use selahcue_engine::scene::Rgba;
use selahcue_present::tokens::{
    self, contrast_ratio, BG_BASE, BG_PANEL, LIVE, NEUTRAL, PREVIEW, WARN,
};
use selahcue_present::StageTheme;

const AA_TEXT: f64 = 4.5;

#[test]
fn canonical_fills_match_ux_canonical_exactly() {
    // UX-CANONICAL §4 is authoritative: green #0f7b6c / red #a3283a / amber #9a5b00.
    assert_eq!(PREVIEW.fill_hex, "#0f7b6c");
    assert_eq!(LIVE.fill_hex, "#a3283a");
    assert_eq!(WARN.fill_hex, "#9a5b00");
    // The hex strings and the Rgba values are the same colour (no drift).
    for t in [PREVIEW, LIVE, WARN, NEUTRAL] {
        let parse = |h: &str| {
            let v = u32::from_str_radix(&h[1..], 16).unwrap();
            Rgba {
                r: (v >> 16) as u8,
                g: (v >> 8) as u8,
                b: v as u8,
                a: 255,
            }
        };
        assert_eq!(t.fill, parse(t.fill_hex));
        assert_eq!(t.ink, parse(t.ink_hex));
    }
    // Staged and warning are NEVER the same colour (§4).
    assert_ne!(PREVIEW.fill, WARN.fill);
    assert_ne!(PREVIEW.ink, WARN.ink);
}

#[test]
fn every_audited_pairing_meets_wcag_aa() {
    let white = Rgba::WHITE;
    // Chip/badge fills carry white text.
    for (name, t) in [("preview", PREVIEW), ("live", LIVE), ("warn", WARN)] {
        let c = contrast_ratio(white, t.fill);
        assert!(c >= AA_TEXT, "white on {name} fill = {c:.2} < {AA_TEXT}");
    }
    // Inks are text/glyphs on the dark surfaces: app base, panels, and the
    // stage-display background all must clear AA.
    let stage_bg = StageTheme::dark().background;
    for bg in [BG_BASE, BG_PANEL, stage_bg] {
        for (name, t) in [("preview", PREVIEW), ("live", LIVE), ("warn", WARN)] {
            let c = contrast_ratio(t.ink, bg);
            assert!(c >= AA_TEXT, "{name} ink on {bg:?} = {c:.2} < {AA_TEXT}");
        }
    }
    // Primary text on every dark surface.
    for bg in [BG_BASE, BG_PANEL] {
        assert!(contrast_ratio(tokens::TEXT_PRIMARY, bg) >= AA_TEXT);
    }
}

#[test]
fn stage_display_uses_the_semantic_inks() {
    // The stage timer's ok/warn/alert states ARE the semantic tokens — the same
    // colour never means two things across surfaces.
    let t = StageTheme::dark();
    assert_eq!(t.timer_ok, PREVIEW.ink);
    assert_eq!(t.timer_warn, WARN.ink);
    assert_eq!(t.timer_alert, LIVE.ink);
}

/// Read one file from the operator's `dist/`. The console is split into
/// `index.html` (structure) + `app.css` (styles) + `app.js` (logic), all served
/// locally; pinned needles may live in any of them.
fn operator_dist(file: &str) -> String {
    let path = format!(
        "{}/../selahcue-operator/dist/{}",
        env!("CARGO_MANIFEST_DIR"),
        file
    );
    std::fs::read_to_string(&path).unwrap_or_else(|_| panic!("operator dist/{file} exists"))
}

/// The three console sources concatenated — content pins run against this so the
/// split (structure/style/logic across files) doesn't hide a needle.
fn operator_console_sources() -> String {
    format!(
        "{}\n{}\n{}",
        operator_dist("index.html"),
        operator_dist("app.css"),
        operator_dist("app.js")
    )
}

/// The operator webview carries the same canonical values (and the emergency
/// chrome + reduced-motion invariants) — pinned by content, like wire fixtures.
#[test]
fn operator_webview_is_pinned_to_the_canonical_tokens() {
    let html = operator_console_sources();
    for needle in [
        PREVIEW.fill_hex,
        LIVE.fill_hex,
        WARN.fill_hex,
        PREVIEW.ink_hex,
        LIVE.ink_hex,
        WARN.ink_hex,
        // Always-on emergency chrome (UX-CANONICAL §3) and its canonical keys. The clear
        // control is labelled "Clear Output" in Design 2.0 (Figma 312:156) — the emergency
        // clear is still present + labelled (non-colour redundancy); it stays the
        // double-Escape "clear all live layers" action (see #clear-all + its aria-label).
        "id=\"emergency\"",
        "BLACKOUT",
        "Clear Output",
        // Reduced-motion setting honoured (story scope).
        "prefers-reduced-motion",
        // Non-colour redundancy: the on-air/staged badges carry text labels
        // (exact construction calls — a bare "LIVE" would match "GO LIVE").
        "badge(\"live\", \"LIVE\")",
        "badge(\"preview\", \"PREVIEW\")",
        // Blackout engaged state is announced, not colour-only.
        "aria-pressed",
        // Key hints stay AA on token-filled buttons.
        "#clear-all.armed .key",
        // Console structure (batch 7x, Figma node 4:2): labelled output panels
        // (non-colour redundancy on the panel headers) + blackout overlay.
        "PREVIEW · STAGED",
        "LIVE · ON AIR",
        "id=\"preview-panel\"",
        "id=\"live-panel\"",
        "BLACKOUT — OUTPUT DARK",
        // Chapter browser + compact-thumbnail rebalance (batch 7ab, owner
        // request): translation picker (KJV default), verse list, 16:9 panels.
        "id=\"translation\"",
        "id=\"verse-list\"",
        "aspect-ratio: 16 / 9",
        "\"KJV\"",
        // OBS-studio layout (Figma 165:124): the three zones + the OBS Preview|Live row.
        "zone-left",
        "zone-center",
        "zone-right",
        "obs-row",
        // Live transcript (R3) + scripture-detection approval queue (R4): FUNCTIONAL —
        // they stream REAL host data (never fabricated). Live transcript is audio-based: a
        // Start/Stop listening toggle (#transcript-listen) drives the on-device STT source
        // and recognised lines render into #transcript-log — there is NO manual "type a
        // line" feed. The copy affirmatively states transcription is running (pinned so it
        // never regresses to a pre-STT "not yet wired" disclosure).
        "id=\"transcript\"",
        "id=\"transcript-log\"",
        "id=\"transcript-partial\"",
        "id=\"transcript-listen\"",
        // Live mic-level meter (86ajxepha): a role=meter bar driven by stt://level while listening.
        "id=\"transcript-meter\"",
        "role=\"meter\"",
        "On-device transcription",
        "id=\"detections\"",
        "id=\"detections-list\"",
        "detection (R4)",
        // Right column is tabbed (Figma 430:124): Service Timer | Detected Scriptures share the
        // column so ≥3 detections fit. A real tablist with a count badge on the Detected tab.
        "role=\"tablist\"",
        "id=\"rtab-timer\"",
        "id=\"rtab-detections\"",
        "role=\"tabpanel\"",
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
}

/// Audit M4: the transcript log is CLIENT-capped so `#transcript-log` stays bounded even if a
/// host ever returned an untailed transcript (defence-in-depth atop the host
/// `OPERATOR_TRANSCRIPT_TAIL=60`). The operator webview has no JS test runner in CI, so this
/// pins the cap by CONTENT — a committed, CI-gated guard that fails if the slice is ever
/// silently dropped. (The BEHAVIOURAL check — feed >120 segments → ≤120 DOM rows, newest kept
/// — is a dev-time headless harness; a follow-up tracks real operator JS/jsdom CI infra.)
#[test]
fn operator_transcript_log_is_client_capped() {
    let js = operator_dist("app.js");
    assert!(
        js.contains("MAX_TRANSCRIPT_ROWS = 120"),
        "the transcript DOM cap constant (audit M4) is missing from app.js"
    );
    assert!(
        js.contains("slice(-MAX_TRANSCRIPT_ROWS)"),
        "syncTranscript must slice to the newest MAX_TRANSCRIPT_ROWS (audit M4) before the prune/append"
    );
}

/// The app menu + Screens surface (86ajq321f) are present and the emergency
/// footer stays OUTSIDE the surface router (so it persists on every surface).
#[test]
fn operator_webview_has_the_app_menu_and_screens_surface() {
    let html = operator_console_sources();
    for needle in [
        // App menu (accessible): a role=menu with menuitems + accesskeys, F10 hint.
        "id=\"app-menu-btn\"",
        "id=\"app-menu\"",
        "role=\"menu\"",
        "role=\"menuitem\"",
        "data-surface=\"screens\"",
        "data-surface=\"console\"",
        "accesskey=\"1\"",
        // Surfaces: the console is wrapped as a routable surface; Screens exists.
        "id=\"surface-console\"",
        "class=\"surface-page active\"",
        "id=\"surface-screens\"",
        "id=\"screens-list\"",
        // Outputs are managed on the Screens surface (menu → Screens), not the
        // console — the console-side outputs panel + theme picker were removed.
        "id=\"screens-identify\"",
        // Theme Designer editor (S8-3c): a canvas preview + Apply.
        "id=\"surface-theme-designer\"",
        "id=\"td-preview\"",
        "id=\"td-apply\"",
        "preview_theme",
        "set_custom_theme",
        // The inspector's authoring controls (C-004): per-region colour/size/align/
        // line-height/Fit + background. Pinned so a future edit cannot strip the authoring
        // half while leaving preview + Apply green. (The explicit Region *picker* was removed
        // as redundant — a region is selected via the LAYERS rows / canvas click and named in
        // the inspector header; per-region editing + selection is preserved without it.)
        "id=\"td-bg\"",
        "id=\"td-color\"",
        "id=\"td-size\"",
        "id=\"td-align\"",
        "id=\"td-lh\"",
        "id=\"td-fit\"",
        // Segmented groups carry an accessible name + per-button pressed state (WCAG
        // 4.1.2) — not colour-only selection.
        "aria-labelledby=\"td-lbl-align\"",
        "aria-pressed",
        // Refine (Figma 204-124/208-137): a full-center canvas with an on-canvas
        // selection box + resize handles, vertical alignment, and host-sourced built-ins
        // (no hand-mirrored JS drift). (The numeric X/Y/W/H grid + Lock aspect were removed —
        // redundant with the on-canvas move/resize handles; position/size is edited on canvas.)
        "id=\"td-canvas-box\"",
        "id=\"td-sel\"",
        "data-h=\"nw\"",
        "id=\"td-valign\"",
        "builtin_themes",
        // Refine 2 (Figma 204-124 alignment): header actions, tabs, add-content, and honest
        // 'later' affordances (present but not fake). Save routes to 86ajq4xmy.
        "class=\"td-header\"",
        "id=\"td-save\"",
        "id=\"td-tab-scriptures\"",
        "id=\"td-tab-slides\"",
        "data-add=\"text\"",
        "id=\"td-font\"",
        "td-later",
        // (The per-item theme override + its `set_item_theme`/`item-theme` pins were
        // removed with the Service-plan declutter in 1108bc4; per-screen theme remains
        // — see `operator_webview_wires_per_screen_theme`.)
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
    // The emergency footer must be a SIBLING of <main> (outside every surface),
    // so it stays reachable on every surface. Assert </main> precedes the footer —
    // a DOM-structure invariant, checked on index.html specifically.
    let index = operator_dist("index.html");
    let main_close = index.find("</main>").expect("</main>");
    let footer = index.find("id=\"emergency\"").expect("emergency footer");
    assert!(
        main_close < footer,
        "the emergency footer must sit AFTER </main> (outside the surface router)"
    );
}

/// The saved-theme library (86ajq4xmy): the Theme Designer's Save-changes form + the
/// built-in/saved template list wired to the host `save_theme`/`delete_theme` commands.
/// Pinned so a future edit cannot strip the library half while leaving Apply green.
#[test]
fn operator_webview_has_the_saved_theme_library() {
    let html = operator_console_sources();
    for needle in [
        // The inline (WKWebView-safe) Save form — name input + Save/Cancel.
        "id=\"td-save-row\"",
        "id=\"td-save-name\"",
        "id=\"td-save-confirm\"",
        "id=\"td-save-cancel\"",
        // The template list carries built-ins (read-only tag) + deletable saved themes.
        "td-theme-name",
        "td-theme-del",
        // Wired to the real host library commands + the view field that feeds the list.
        "save_theme",
        "delete_theme",
        "saved_themes",
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
    // The Save flow uses the inline name form (never window.prompt, which WKWebView
    // blocks): the form's keydown handler commits on Enter — pin that wiring.
    assert!(
        operator_dist("app.js").contains("tdSaveName.addEventListener(\"keydown\""),
        "the Save name field must commit via its own inline keydown handler"
    );
}

/// The per-screen theme wiring (86ajq321k): the Screens page's audience Theme picker
/// sets a PER-SCREEN theme (not the global) + lists the virtual Audience-class screens.
/// Pinned so a future edit cannot silently revert the picker to the global `set_theme`.
#[test]
fn operator_webview_wires_per_screen_theme() {
    let js = operator_dist("app.js");
    for needle in [
        // The audience Theme picker invokes the PER-SCREEN command, not the global.
        "set_screen_theme",
        // The reusable per-screen picker + the map fed from the view.
        "themePickerFor",
        "screen_themes",
        // The addable Audience-class roles (added on demand via "+ Add virtual output") each
        // carry their own theme; the role picker offers them.
        "lower-third",
        "stream",
        // A "follow global" entry (empty value) so a set per-screen theme can be cleared
        // back to the global (mirrors the per-item picker; the backend's empty-name clear).
        "Follow global",
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // The audience Theme picker must NOT wire the GLOBAL set_theme any more (regression
    // guard: the placeholder that 86ajq321k replaces).
    assert!(
        !js.contains("invoke(\"set_theme\""),
        "the Screens audience picker must use set_screen_theme, not the global set_theme"
    );
}

/// Saved themes are offered on the per-SCREEN Theme picker (86ajq69ft): the picker lists
/// the library's saved themes (a "Saved" optgroup), not just built-ins. Pinned so a future
/// edit cannot silently drop the saved themes from the picker. (The per-ITEM theme dropdown
/// — and its `set_item_theme` pin — was removed in 1108bc4's Service-plan declutter.)
#[test]
fn operator_webview_offers_saved_themes_per_screen() {
    let js = operator_dist("app.js");
    // The per-screen picker + the change-detect key read the library from the view.
    assert!(
        js.matches("view.saved_themes").count() >= 2,
        "the per-screen picker (and the change-detect key) read view.saved_themes"
    );
    for needle in [
        "savedNames",
        "optgroup",
        "grp.label = \"Saved\"",
        // The per-screen Theme picker stays wired to its command.
        "set_screen_theme",
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
}

/// The Theme Designer font picker (86ajq6fxt) is a real, enabled control populated from
/// the host's installed fonts, wired to the theme's font — not the old disabled "later"
/// placeholder. Pinned so a future edit cannot silently re-disable it.
#[test]
fn operator_webview_wires_the_system_font_picker() {
    let html = operator_console_sources();
    let index = operator_dist("index.html");
    let js = operator_dist("app.js");
    for needle in [
        // The picker is present + has the default (bundled) entry.
        "id=\"td-font\"",
        "Noto Sans (default)",
        // Wired to the host enumeration + the theme's font.
        "system_fonts",
        "tdLoadFonts",
        "tdTheme.font",
        // A theme font NOT installed on this machine is still reflected (not blanked).
        "tdEnsureFontOption",
        "(not installed here)",
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
    // The Font control is no longer a disabled "later" placeholder.
    assert!(
        !index.contains(r#"<select id="td-font" class="td-later" disabled>"#),
        "the Font picker must be enabled (not the disabled 'later' placeholder)"
    );
    // The change handler drops the field for the default (byte-stable theme JSON).
    assert!(
        js.contains("delete tdTheme.font"),
        "selecting the default font clears the theme font field"
    );
}

/// The Theme Designer Design 2.0 shell (Figma 317:124): a topbar (Duplicate / Preview on
/// output / Save theme), a canvas zone with a preview zoom + a Templates strip, a sectioned
/// inspector, and a REAL LAYERS panel (select / reorder→z-order / per-layer visibility).
/// Pinned so a future edit cannot strip a 2.0 control or silently fake the visibility toggle.
#[test]
fn operator_theme_designer_is_design_2() {
    let html = operator_console_sources();
    let index = operator_dist("index.html");
    let js = operator_dist("app.js");
    let css = operator_dist("app.css");
    // Topbar actions: Duplicate (new clone), Preview on output (the re-homed #td-apply),
    // and the gradient Save-theme CTA (not the green go-live gradient).
    for needle in [
        "id=\"td-duplicate\"",
        "Preview on output",
        "Save theme",
        "class=\"td-save-cta\"",
        // Canvas zone: the audience resolution + a frontend-only preview zoom.
        "Audience · 1920×1080",
        "id=\"td-zoom-out\"",
        "id=\"td-zoom-in\"",
        "id=\"td-zoom-v\"",
        // Templates strip (the library re-homed as a horizontal card row).
        "class=\"td-templates\"",
        "td-themes-strip",
        // Sectioned inspector selection header.
        "id=\"td-insp-title\"",
        // LAYERS panel (the new real control) + its "+ Add layer".
        "id=\"td-layers\"",
        "id=\"td-layers-add\"",
        // Sectioned inspector (Figma 317:142): the background TYPE is a segmented control
        // (Solid/Gradient/Image), not a select; sections use D2 field labels.
        "data-bg=\"solid\"",
        "data-bg=\"gradient\"",
        "class=\"td-sect\"",
        "td-fieldlabel",
        // A collapsible Templates row (reclaim canvas space) — the toggle is present.
        "id=\"td-templates-toggle\"",
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
    // The LAYERS panel + zoom + Duplicate are wired for real (behaviour, not just markup).
    for needle in [
        "function tdLayers(",
        "function tdLayerRow(",
        "tdToggleVisible",
        "function tdSyncHead(",
        "--td-zoom",
        // Clicking the Body / Reference-Title text on the canvas auto-selects that region.
        "function tdRegionAt(",
        // The canvas fits (letterboxes) to the available area — resizes with the screen.
        "function tdFitCanvas(",
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // Per-layer visibility is REAL: an element omits the field when shown (byte-stable JSON)
    // and sets `visible = false` when hidden — never a fake/disabled toggle.
    assert!(
        js.contains("el.visible = false") && js.contains("delete el.visible"),
        "the layer eye toggles a real, byte-stable `visible` field"
    );
    // The LAYERS rows + preview-zoom transform are styled (the 2.0 shell CSS shipped).
    assert!(
        css.contains(".td-layer") && css.contains("var(--td-zoom"),
        "the Design 2.0 LAYERS + zoom CSS is present"
    );
    // Import/Export a theme FILE stay honest 'later' affordances (never faked).
    assert!(
        index.contains("id=\"td-import\"") && index.contains("id=\"td-export\""),
        "Import/Export remain present as honest 'later' affordances"
    );
}

/// The Flutter controller carries the same canonical values.
#[test]
fn mobile_tokens_are_pinned_to_the_canonical_tokens() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../mobile/selahcue_controller/lib/models/design_tokens.dart"
    );
    let dart = std::fs::read_to_string(path).expect("mobile design_tokens.dart exists");
    for (hex, name) in [
        (PREVIEW.fill_hex, "preview fill"),
        (LIVE.fill_hex, "live fill"),
        (WARN.fill_hex, "warn fill"),
        (PREVIEW.ink_hex, "preview ink"),
        (LIVE.ink_hex, "live ink"),
        (WARN.ink_hex, "warn ink"),
    ] {
        // Dart colour literals: #0f7b6c -> 0xFF0F7B6C.
        let literal = format!("0xFF{}", hex[1..].to_uppercase());
        assert!(
            dart.contains(&literal),
            "mobile tokens missing {name} {literal}"
        );
    }
}

/// The Design 2.0 palette (Figma node 310:124) is carried identically by the
/// operator webview (CSS `--sc-*`) and the Flutter controller (`0xFF..`), pinned to
/// the canonical Rust swatches (`tokens::design2`) so the redesign tokens can't
/// drift or drop across surfaces. Additive layer — see DESIGN-2.0-HANDOFF.md §3.
#[test]
fn design2_palette_is_pinned_across_surfaces() {
    let css = operator_dist("app.css");
    let dart_path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../mobile/selahcue_controller/lib/models/design_tokens.dart"
    );
    let dart = std::fs::read_to_string(dart_path).expect("mobile design_tokens.dart exists");
    let parse = |h: &str| {
        let v = u32::from_str_radix(&h[1..], 16).unwrap();
        Rgba {
            r: (v >> 16) as u8,
            g: (v >> 8) as u8,
            b: v as u8,
            a: 255,
        }
    };
    for &(name, sw) in tokens::design2::MANIFEST {
        // The canonical Rust hex and Rgba are the same colour (no internal drift).
        assert_eq!(sw.rgba, parse(sw.hex), "design2 {name}: hex != rgba");
        // Operator webview CSS custom property, exact.
        let css_needle = format!("--sc-{name}: {}", sw.hex);
        assert!(css.contains(&css_needle), "app.css missing {css_needle:?}");
        // Flutter const, NAME-bound (not a bare hex): `d2<Camel> = Color(0xFF<HEX>)`.
        // A value-only match would let a dropped/transposed const hide behind a
        // same-hex sibling (gold-soft & warn-soft both carry #2a2415) — so bind the
        // name to the value, mirroring the CSS `--sc-{name}: {hex}` above.
        let camel: String = name
            .split('-')
            .map(|p| {
                let mut ch = p.chars();
                match ch.next() {
                    Some(f) => f.to_uppercase().collect::<String>() + ch.as_str(),
                    None => String::new(),
                }
            })
            .collect();
        let dart_needle = format!("d2{camel} = Color(0xFF{})", sw.hex[1..].to_uppercase());
        assert!(
            dart.contains(&dart_needle),
            "design_tokens.dart missing `{dart_needle}` ({name})"
        );
    }
}

/// Design 2.0 pairings meet WCAG-AA on the new dark surfaces: body + secondary
/// text, scripture gold, and the bright status inks clear 4.5:1 on `base` +
/// `surface` and on their same-hue soft tints; white clears 4.5:1 on the primary
/// button. `text-muted` is tertiary/label-only and is audited at AA-large (3:1) —
/// it must NOT carry essential small body text (flagged in DESIGN-2.0-HANDOFF §6).
#[test]
fn design2_palette_meets_wcag_aa() {
    use tokens::design2 as d2;
    const AA_LARGE: f64 = 3.0;
    let (base, surface) = (d2::BASE.rgba, d2::SURFACE.rgba);
    for bg in [base, surface] {
        assert!(
            contrast_ratio(d2::TEXT.rgba, bg) >= AA_TEXT,
            "text on {bg:?}"
        );
        assert!(
            contrast_ratio(d2::TEXT_SECONDARY.rgba, bg) >= AA_TEXT,
            "text-secondary on {bg:?}"
        );
        let m = contrast_ratio(d2::TEXT_MUTED.rgba, bg);
        assert!(
            m >= AA_LARGE,
            "text-muted on {bg:?} = {m:.2} < AA-large {AA_LARGE}"
        );
    }
    // Bright inks + gold as text/glyphs on the dark surfaces.
    for (n, s) in [
        ("preview", d2::PREVIEW),
        ("live", d2::LIVE),
        ("warn", d2::WARN),
        ("info", d2::INFO),
        ("gold", d2::GOLD),
    ] {
        for bg in [base, surface] {
            let c = contrast_ratio(s.rgba, bg);
            assert!(c >= AA_TEXT, "{n} on {bg:?} = {c:.2} < {AA_TEXT}");
        }
    }
    // Status inks + gold on their own same-hue soft tint (the Design 2.0 chip pattern).
    for (n, ink, soft) in [
        ("preview", d2::PREVIEW, d2::PREVIEW_SOFT),
        ("live", d2::LIVE, d2::LIVE_SOFT),
        ("warn", d2::WARN, d2::WARN_SOFT),
        ("info", d2::INFO, d2::INFO_SOFT),
        ("gold", d2::GOLD, d2::GOLD_SOFT),
    ] {
        let c = contrast_ratio(ink.rgba, soft.rgba);
        assert!(c >= AA_TEXT, "{n} on its soft tint = {c:.2} < {AA_TEXT}");
    }
    // White label on the flat primary button (4.72:1, AA).
    let p = contrast_ratio(Rgba::WHITE, d2::PRIMARY.rgba);
    assert!(p >= AA_TEXT, "white on primary = {p:.2} < {AA_TEXT}");
    // Constraint: white on the primary GRADIENT TOP (primary-hover) is only ~3.78:1 —
    // AA-large, NOT AA-normal. So the primary gradient/hover must not carry small white
    // body text; small white labels sit on the flat `primary`. Pinned as AA-large here
    // so a future darkening of primary-hover can't silently drop below AA-large either.
    let ph = contrast_ratio(Rgba::WHITE, d2::PRIMARY_HOVER.rgba);
    assert!(
        ph >= AA_LARGE,
        "white on primary-hover = {ph:.2} < AA-large {AA_LARGE}"
    );
}

/// The Presentation & Media surface (Design 2.0, Figma node 329:124) is wired: the activated
/// nav item, the surface section, its load-bearing ids, and the deck/media bridge commands are
/// all present. Pinned so a future edit cannot silently drop a hook the surface depends on
/// (each is a real `getElementById`/`invoke` target). The compositor stays native — the canvas
/// is a base64 preview (`render_deck_slide` → `blitFrame`), never an HTML render (ADR-0002/0003).
#[test]
fn operator_presentation_media_surface_is_wired() {
    let html = operator_dist("index.html");
    let js = operator_dist("app.js");
    // The nav item is ACTIVATED (a real surface, no longer the disabled "later" affordance) but
    // carries `data-nodigit` so it never shifts the ⌘1–6 map.
    for needle in [
        "data-surface=\"presentation\"",
        "data-nodigit",
        "id=\"surface-presentation\"",
        "id=\"pm-slide-list\"",
        "id=\"pm-canvas\"",
        "id=\"pm-media-grid\"",
        "id=\"pm-notes\"",
        "id=\"pm-transition\"",
        "id=\"pm-autoadv\"",
        "id=\"pm-import\"",
        "id=\"pm-undo\"",
        "id=\"pm-grid\"",
        "id=\"pm-grid-edit\"",
        "id=\"pm-transport\"",
        "id=\"pm-done\"",
        // Scoped to the PM toolbar so it can't accidentally match the Theme Designer's add-bar.
        "class=\"pm-tool\" data-add=\"text\"",
        // The contextual right panel: Media ⟷ Inspector tabs + the two bodies (86ajvjtax).
        "id=\"pm-tab-media\"",
        "id=\"pm-tab-inspector\"",
        "id=\"pm-inspector-body\"",
        "id=\"pm-media-body\"",
    ] {
        assert!(html.contains(needle), "index.html missing {needle:?}");
    }
    // The webview→engine bridge commands + the own render loop.
    for needle in [
        // The exact APP_SURFACES + SURFACE_LABEL registration (a bare "presentation" would be a
        // tautology — the word appears many times; these prove the surface is really registered).
        "\"console\", \"presentation\"",
        "presentation: \"Presentation\"",
        "renderPresentation",
        "render_deck_slide", // native slide preview
        "deck_view",
        "deck_add_slide",
        "deck_add_element",
        "deck_move_element",
        "deck_set_transition",
        "deck_set_auto_advance",
        "deck_undo",
        "deck_go_live",
        "deck_add_image_element",
        // The per-element Inspector + its edit/replace bridge (86ajvjtax).
        "pmRenderInspector",
        "deck_update_element",
        "deck_replace_element_image",
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // The Presentation item must NOT be a disabled "later" affordance any more (regression guard).
    assert!(
        !html.contains("data-later=\"presentation\""),
        "the Presentation nav item is activated, not a disabled 'later' affordance"
    );
}

/// The Presentation & Media **remaining states** (TASK-presentation-remaining-states): destructive
/// confirms (delete-slide / remove-media / delete-element toast), the system loading/error states,
/// the Text font picker, and the live image Fit control. Pinned so a future edit cannot silently
/// drop one of these designed affordances (each is a real DOM/CSS/bridge hook).
#[test]
fn operator_presentation_remaining_states_are_wired() {
    let html = operator_dist("index.html");
    let js = operator_dist("app.js");
    let css = operator_dist("app.css");
    // Load-bearing markup: the error banner (role=alert) + the action toast (role=status).
    for needle in [
        "id=\"pm-error\"",
        "role=\"alert\"",
        "id=\"pm-error-retry\"",
        "id=\"pm-error-dismiss\"",
        "id=\"pm-toast\"",
        "role=\"status\"",
    ] {
        assert!(html.contains(needle), "index.html missing {needle:?}");
    }
    // Behaviour hooks: the confirm dialog, toast, font picker, Fit control, and the destructive
    // bridge commands the affordances drive.
    for needle in [
        "function pmConfirm",       // the role=alertdialog confirm (focus-trap + Esc)
        "\"alertdialog\"",          // the confirm's ARIA role
        "function pmToast",         // the "Element deleted — Undo" toast
        "function pmDeleteElement", // routes delete → toast + undo
        "function pmFontSelect",    // the Text Font-family picker (C-006)
        "function pmShowError",     // the error banner (C-004)
        "function pmSetBusy",       // the aria-busy loading state (C-004)
        "deck_remove_slide",        // the delete-slide confirm target (C-001)
        "deck_remove_media",        // the remove-media confirm target (C-002)
        "\"imgfit\"",               // the live image Fit control (C-008)
        "pm-slide-del",             // the delete-slide affordance (C-001)
        "pm-asset-del",             // the remove-media affordance (C-002)
        "aria-busy",                // the loading state toggled on the canvas
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // The Image Fit control is a LIVE three-way select, not the old disabled "later render seam".
    assert!(
        js.contains("Fit (letterbox)") && js.contains("Fill (cover)"),
        "the Image inspector Fit control offers the letterbox/cover modes (C-008)"
    );
    assert!(
        !js.contains("Aspect-fit (letterbox) is a later render seam"),
        "the Fit control is live now, not a later-seam placeholder note"
    );
    // Styles for each new affordance (so a re-skin can't drop them silently).
    for needle in [
        ".pm-error",
        ".pm-toast",
        ".pm-confirm",
        ".pm-btn-danger",
        ".pm-slide-del",
        ".pm-asset-del",
        ".pm-canvas-box.busy",
    ] {
        assert!(css.contains(needle), "app.css missing {needle:?}");
    }
}

/// The Presentation canvas-editing extensions: on-canvas RESIZE handles + Alt-arrow resize, the
/// LAYERS panel (drag-reorder, replacing the old Arrange buttons), and double-click-to-edit text.
/// Pinned so a future edit cannot silently drop one of these interactive affordances.
#[test]
fn operator_presentation_canvas_editing_is_wired() {
    let html = operator_dist("index.html");
    let js = operator_dist("app.js");
    let css = operator_dist("app.css");
    // Markup: the 8 resize handles on the selection box.
    for needle in [
        "class=\"pm-h\" data-h=\"nw\"",
        "data-h=\"se\"",
        "data-h=\"w\"",
    ] {
        assert!(html.contains(needle), "index.html missing {needle:?}");
    }
    // Behaviour hooks: resize (handles + keyboard), the Layers panel + its reorder bridge, and the
    // inline text editor (double-click) + its text bridge.
    for needle in [
        "function pmRenderLayers",    // the LAYERS panel (replaces Arrange)
        "function pmLayerDragCommit", // drag-reorder commit
        "deck_reorder_elements",      // the reorder bridge command
        "function pmStartTextEdit",   // double-click inline text editor
        "deck_set_element_text",      // the inline-edit bridge command
        "\"dblclick\"",               // the double-click trigger
        "pmLayerDragStart",           // layer drag start (handle pointerdown)
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // The old Arrange button block must be gone (regression guard — it was replaced by Layers).
    assert!(
        !js.contains("pm-insp-arrange") && !js.contains("\"arr-\" + dir"),
        "the Arrange button block was replaced by the Layers panel"
    );
    // Styles for the new affordances.
    for needle in [".pm-h[data-h=", ".pm-layers", ".pm-text-edit"] {
        assert!(css.contains(needle), "app.css missing {needle:?}");
    }
}

/// The Presentations Library (86ajvt8q7): the deck-switcher breadcrumb opens a library view of the
/// deck set, wired to the deck_list/new/open/rename/duplicate/delete commands. Pinned so a future
/// edit cannot silently drop the browse/create/manage affordances or their bridge commands.
#[test]
fn operator_presentations_library_is_wired() {
    let html = operator_dist("index.html");
    let js = operator_dist("app.js");
    let css = operator_dist("app.css");
    // Load-bearing markup: the switcher + the library view container + its states.
    for needle in [
        "id=\"pm-deckswitch\"",
        "id=\"pm-library\"",
        "id=\"pm-lib-grid\"",
        "id=\"pm-lib-new\"",
        "id=\"pm-lib-q\"",
        "id=\"pm-lib-empty\"",
        "id=\"pm-lib-error\"",
        "id=\"pm-lib-nopersist\"",
    ] {
        assert!(html.contains(needle), "index.html missing {needle:?}");
    }
    // The bridge commands + the behaviour hooks.
    for needle in [
        "deck_list",
        "deck_new",
        "deck_open",
        "deck_rename",
        "deck_duplicate",
        "deck_delete",
        "function pmShowLibrary",
        "function pmRenderLibGrid",
        "function pmPrompt",       // the New/Rename name dialog
        "function pmLibOpenMenu",  // the card ⋯ menu
        "function pmLibFocusDeck", // a11y: restore focus after a mutating action (WCAG 2.4.3)
    ] {
        assert!(js.contains(needle), "app.js missing {needle:?}");
    }
    // The dead "Add to plan" stub is replaced by the deck-switcher (regression guard).
    assert!(
        !html.contains("id=\"pm-addplan\""),
        "the disabled 'Add to plan' stub was replaced by the deck-switcher"
    );
    // Styles for the library affordances.
    for needle in [
        ".pm-library",
        ".pm-lib-card",
        ".pm-lib-menu",
        ".pm-deckswitch",
        ".pm-lib-menu button:focus-visible", // a11y: a visible keyboard-focus outline (WCAG 2.4.7)
    ] {
        assert!(css.contains(needle), "app.css missing {needle:?}");
    }
}
