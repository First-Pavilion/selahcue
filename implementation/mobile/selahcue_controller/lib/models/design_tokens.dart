import 'package:flutter/material.dart';

/// Canonical design tokens (UX-CANONICAL §4) — the mobile mirror of
/// `selahcue-present/src/tokens.rs`. One meaning per colour on every surface:
/// green = preview/staged, red = live/on-air, amber = warning; LIVE/PREVIEW
/// always carry a text label (never colour alone, WCAG 1.4.1).
///
/// Pinned by `selahcue-present/tests/test_tokens.rs` and
/// `test/models/design_tokens_test.dart` — change all surfaces together.
abstract final class DesignTokens {
  // Fills: chip/badge backgrounds carrying white text (UX-CANONICAL hexes, exact).
  static const Color previewFill = Color(0xFF0F7B6C);
  static const Color liveFill = Color(0xFFA3283A);
  static const Color warnFill = Color(0xFF9A5B00);

  // Inks: text/glyph colours on the dark surfaces (Figma accent/*).
  static const Color previewInk = Color(0xFF2BB673);
  static const Color liveInk = Color(0xFFEF4444);
  static const Color warnInk = Color(0xFFF2B53C);

  // Brand accent (Figma accent/brand) — seeds the Material scheme.
  static const Color accentBrand = Color(0xFF5B6BD6);

  // Surfaces (Figma bg/*, border, text/*).
  static const Color bgBase = Color(0xFF0E1116);
  static const Color bgPanel = Color(0xFF171B22);
  static const Color border = Color(0xFF2B323D);
  static const Color textPrimary = Color(0xFFEEF1F6);
  static const Color textMuted = Color(0xFF9AA4B2);

  // Audience output surface (the on-screen black behind slides).
  static const Color outputBlack = Color(0xFF000000);
}
