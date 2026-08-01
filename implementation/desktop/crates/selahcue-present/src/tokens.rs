//! Canonical design tokens — the single Rust source of truth for semantic colour
//! across every SelahCue surface (UX-CANONICAL §4; FR-014/NFR-019 companion).
//!
//! One meaning per colour family, everywhere: **green = preview/staged**,
//! **red = live/on-air**, **amber = warning**. Staged and warning are never the
//! same colour, and colour is never the only cue (LIVE/PREVIEW always carry a
//! text label — WCAG 1.4.1).
//!
//! Each semantic token has two audited forms:
//! - **fill** — the deep UX-CANONICAL hex, used as a chip/badge/panel-header fill
//!   with white text on it (AA-audited as text-on-fill);
//! - **ink** — the bright on-dark variant from the Figma design system
//!   (`accent/preview|live|warn` in file SYQn5hFY8YVQKm3c6rw0eJ), used for
//!   text/glyphs on the dark surfaces (AA-audited against [`BG_BASE`] and the
//!   stage-display background).
//!
//! The operator webview (`selahcue-operator/dist/index.html`) and the Flutter
//! controller (`lib/models/design_tokens.dart`) carry the same hex values;
//! `tests/test_tokens.rs` pins all three surfaces together and audits contrast —
//! change any of them together or the audit fails.

use selahcue_engine::scene::Rgba;

/// A semantic colour token: the canonical fill + its on-dark ink variant.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SemanticToken {
    /// Chip/badge fill (white text goes on top). UX-CANONICAL §4 hex, exact.
    pub fill: Rgba,
    /// Text/glyph colour on the dark surfaces (Figma `accent/*`).
    pub ink: Rgba,
    /// CSS hex of `fill`, lowercase (e.g. `"#0f7b6c"`).
    pub fill_hex: &'static str,
    /// CSS hex of `ink`, lowercase.
    pub ink_hex: &'static str,
}

const fn rgb(r: u8, g: u8, b: u8) -> Rgba {
    Rgba { r, g, b, a: 255 }
}

/// Preview / staged (not on air) — green. The green family means "safe /
/// positive" everywhere (staged content; a timer on track); it never marks
/// something as on-air.
pub const PREVIEW: SemanticToken = SemanticToken {
    fill: rgb(0x0f, 0x7b, 0x6c),
    ink: rgb(0x2b, 0xb6, 0x73),
    fill_hex: "#0f7b6c",
    ink_hex: "#2bb673",
};

/// Live / Program (on air) — red. The red family means "on air / alarm"
/// everywhere (live content; TIME UP); always paired with a text label.
pub const LIVE: SemanticToken = SemanticToken {
    fill: rgb(0xa3, 0x28, 0x3a),
    ink: rgb(0xef, 0x44, 0x44),
    fill_hex: "#a3283a",
    ink_hex: "#ef4444",
};

/// Warning / threshold (e.g. timer nearing zero) — amber. Never the staged colour.
pub const WARN: SemanticToken = SemanticToken {
    fill: rgb(0x9a, 0x5b, 0x00),
    ink: rgb(0xf2, 0xb5, 0x3c),
    fill_hex: "#9a5b00",
    ink_hex: "#f2b53c",
};

/// Idle / inactive — neutral grey (Figma `text/muted`).
pub const NEUTRAL: SemanticToken = SemanticToken {
    fill: rgb(0x2b, 0x32, 0x3d),
    ink: rgb(0x9a, 0xa4, 0xb2),
    fill_hex: "#2b323d",
    ink_hex: "#9aa4b2",
};

/// Base app background (Figma `bg/base`) — what inks are audited against.
pub const BG_BASE: Rgba = rgb(0x0e, 0x11, 0x16);
/// Panel background (Figma `bg/panel`).
pub const BG_PANEL: Rgba = rgb(0x17, 0x1b, 0x22);
/// Hairline border (Figma `border`).
pub const BORDER: Rgba = rgb(0x2b, 0x32, 0x3d);
/// Primary text on dark surfaces (Figma `text/primary`).
pub const TEXT_PRIMARY: Rgba = rgb(0xee, 0xf1, 0xf6);

/// WCAG 2.x relative luminance of an sRGB colour (alpha ignored).
pub fn relative_luminance(c: Rgba) -> f64 {
    fn channel(v: u8) -> f64 {
        let s = v as f64 / 255.0;
        if s <= 0.04045 {
            s / 12.92
        } else {
            ((s + 0.055) / 1.055).powf(2.4)
        }
    }
    0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b)
}

/// WCAG contrast ratio between two colours (order-independent, 1.0..=21.0).
pub fn contrast_ratio(a: Rgba, b: Rgba) -> f64 {
    let (la, lb) = (relative_luminance(a), relative_luminance(b));
    let (hi, lo) = if la >= lb { (la, lb) } else { (lb, la) };
    (hi + 0.05) / (lo + 0.05)
}

/// SelahCue **"Design 2.0"** palette (Figma node `310:124`, file
/// `SYQn5hFY8YVQKm3c6rw0eJ`) — the redesign token set.
///
/// This is an **additive** token layer for the Design 2.0 re-skin: the canonical
/// status tokens above ([`PREVIEW`]/[`LIVE`]/[`WARN`]) are *white-on-deep-fill* and
/// stay until components migrate, whereas Design 2.0 uses a **bright ink on a
/// same-hue soft tint** (see `docs/design/DESIGN-2.0-HANDOFF.md` §3). Mirrored in
/// the operator webview (`dist/app.css`, `--sc-*`) and the Flutter controller
/// (`design_tokens.dart`, `d2*`); every surface + the WCAG-AA pairings are pinned
/// by `tests/test_tokens.rs` — change them together or the audit fails.
pub mod design2 {
    use super::{rgb, Rgba};

    /// A palette swatch: the colour and its lowercase CSS hex, kept in lockstep.
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub struct Swatch {
        /// The colour.
        pub rgba: Rgba,
        /// Its CSS hex, lowercase (e.g. `"#0b0d12"`).
        pub hex: &'static str,
    }
    const fn sw(r: u8, g: u8, b: u8, hex: &'static str) -> Swatch {
        Swatch {
            rgba: rgb(r, g, b),
            hex,
        }
    }

    // — Neutral surface ramp (app background → darkest well) —
    /// App background.
    pub const BASE: Swatch = sw(0x0b, 0x0d, 0x12, "#0b0d12");
    /// Panels / cards.
    pub const SURFACE: Swatch = sw(0x14, 0x16, 0x1d, "#14161d");
    /// Rows, inner cards, controls.
    pub const ELEVATED: Swatch = sw(0x1c, 0x1f, 0x28, "#1c1f28");
    /// Wells, inputs, monitor mattes.
    pub const INSET: Swatch = sw(0x0f, 0x11, 0x16, "#0f1116");
    /// Hairline border.
    pub const BORDER: Swatch = sw(0x26, 0x2a, 0x34, "#262a34");
    /// Emphasis border.
    pub const BORDER_STRONG: Swatch = sw(0x36, 0x3b, 0x47, "#363b47");

    // — Text scale —
    /// Primary text.
    pub const TEXT: Swatch = sw(0xf4, 0xf6, 0xfb, "#f4f6fb");
    /// Secondary text.
    pub const TEXT_SECONDARY: Swatch = sw(0xa7, 0xae, 0xbe, "#a7aebe");
    /// Tertiary / hint text (label-only; see the WCAG note in `test_tokens.rs`).
    pub const TEXT_MUTED: Swatch = sw(0x6b, 0x73, 0x83, "#6b7383");

    // — Brand (indigo → violet) —
    /// Primary action / selection.
    pub const PRIMARY: Swatch = sw(0x6e, 0x5c, 0xf0, "#6e5cf0");
    /// Hover / gradient top.
    pub const PRIMARY_HOVER: Swatch = sw(0x7e, 0x6e, 0xff, "#7e6eff");
    /// Soft brand tint (chips/selection fills on dark).
    pub const ACCENT_SOFT: Swatch = sw(0x20, 0x1f, 0x3a, "#201f3a");

    // — Scripture gold (worship accent; never a status) —
    /// Scripture references / verse numbers.
    pub const GOLD: Swatch = sw(0xf2, 0xb8, 0x4b, "#f2b84b");
    /// Gold soft tint.
    pub const GOLD_SOFT: Swatch = sw(0x2a, 0x24, 0x15, "#2a2415");

    // — Broadcast status: bright ink + same-hue soft tint + border —
    /// Live / on-air / alarm ink.
    pub const LIVE: Swatch = sw(0xff, 0x4d, 0x4d, "#ff4d4d");
    /// Live soft tint (chip/panel background).
    pub const LIVE_SOFT: Swatch = sw(0x2a, 0x14, 0x16, "#2a1416");
    /// Live border.
    pub const LIVE_BORDER: Swatch = sw(0x5a, 0x23, 0x27, "#5a2327");
    /// Preview / staged / safe ink.
    pub const PREVIEW: Swatch = sw(0x35, 0xc0, 0x8a, "#35c08a");
    /// Preview soft tint.
    pub const PREVIEW_SOFT: Swatch = sw(0x10, 0x23, 0x1c, "#10231c");
    /// Preview border.
    pub const PREVIEW_BORDER: Swatch = sw(0x1c, 0x3a, 0x2e, "#1c3a2e");
    /// Warning / threshold ink.
    pub const WARN: Swatch = sw(0xf5, 0xa5, 0x24, "#f5a524");
    /// Warning soft tint.
    pub const WARN_SOFT: Swatch = sw(0x2a, 0x24, 0x15, "#2a2415");
    /// Warning border.
    pub const WARN_BORDER: Swatch = sw(0x4a, 0x3a, 0x15, "#4a3a15");
    /// Neutral-informational ink (stage role, opt-in badges).
    pub const INFO: Swatch = sw(0x38, 0xbd, 0xf8, "#38bdf8");
    /// Info soft tint.
    pub const INFO_SOFT: Swatch = sw(0x10, 0x22, 0x2b, "#10222b");

    /// The ordered palette manifest: `(token-name, swatch)`. The name maps to the
    /// CSS custom property `--sc-<name>` and the Flutter `d2<Camel>` const — the
    /// pin test iterates this so no surface can drift or drop a token.
    pub const MANIFEST: &[(&str, Swatch)] = &[
        ("base", BASE),
        ("surface", SURFACE),
        ("elevated", ELEVATED),
        ("inset", INSET),
        ("border", BORDER),
        ("border-strong", BORDER_STRONG),
        ("text", TEXT),
        ("text-secondary", TEXT_SECONDARY),
        ("text-muted", TEXT_MUTED),
        ("primary", PRIMARY),
        ("primary-hover", PRIMARY_HOVER),
        ("accent-soft", ACCENT_SOFT),
        ("gold", GOLD),
        ("gold-soft", GOLD_SOFT),
        ("live", LIVE),
        ("live-soft", LIVE_SOFT),
        ("live-border", LIVE_BORDER),
        ("preview", PREVIEW),
        ("preview-soft", PREVIEW_SOFT),
        ("preview-border", PREVIEW_BORDER),
        ("warn", WARN),
        ("warn-soft", WARN_SOFT),
        ("warn-border", WARN_BORDER),
        ("info", INFO),
        ("info-soft", INFO_SOFT),
    ];
}
