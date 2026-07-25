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

/// The operator webview carries the same canonical values (and the emergency
/// chrome + reduced-motion invariants) — pinned by content, like wire fixtures.
#[test]
fn operator_webview_is_pinned_to_the_canonical_tokens() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../selahcue-operator/dist/index.html"
    );
    let html = std::fs::read_to_string(path).expect("operator dist/index.html exists");
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
