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
        // Always-on emergency chrome (UX-CANONICAL §3) and its canonical keys.
        "id=\"emergency\"",
        "BLACKOUT",
        "CLEAR ALL",
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
        // Forward-looking panels — present but HONEST: they carry an explicit
        // "arrives with R3/R4" empty state, never fabricated transcript/detections.
        "id=\"transcript\"",
        "id=\"detections\"",
        "arrives with R3",
        "arrive with R4",
    ] {
        assert!(html.contains(needle), "webview missing {needle:?}");
    }
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
        // line-height/Fit + the region selector + background. Pinned so a future edit
        // cannot strip the authoring half while leaving preview + Apply green.
        "id=\"td-region\"",
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
        // selection box + resize handles, numeric X/Y/W/H, vertical alignment, and
        // host-sourced built-ins (no hand-mirrored JS drift).
        "id=\"td-canvas-box\"",
        "id=\"td-sel\"",
        "data-h=\"nw\"",
        "id=\"td-x\"",
        "id=\"td-valign\"",
        "builtin_themes",
        // Refine 2 (Figma 204-124 alignment): header actions, tabs, add-content, lock,
        // and honest 'later' affordances (present but not fake). Save routes to 86ajq4xmy.
        "class=\"td-header\"",
        "id=\"td-save\"",
        "id=\"td-tab-scriptures\"",
        "id=\"td-tab-slides\"",
        "data-add=\"text\"",
        "id=\"td-lock\"",
        "id=\"td-font\"",
        "td-later",
        // Per-item theme override (S8-3d): a picker on each plan row → set_item_theme.
        "set_item_theme",
        "item-theme",
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
