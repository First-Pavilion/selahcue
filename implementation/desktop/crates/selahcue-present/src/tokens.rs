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
