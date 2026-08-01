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

  // — SelahCue "Design 2.0" palette (Figma node 310:124) — additive redesign token
  //   layer, mirrored from `tokens::design2` (Rust canonical) and the operator
  //   webview `--sc-*` vars; pinned + WCAG-audited by test_tokens.rs. The canonical
  //   tokens above stay until the mobile re-skin migrates to these.
  // Neutral surface ramp.
  static const Color d2Base = Color(0xFF0B0D12);
  static const Color d2Surface = Color(0xFF14161D);
  static const Color d2Elevated = Color(0xFF1C1F28);
  static const Color d2Inset = Color(0xFF0F1116);
  static const Color d2Border = Color(0xFF262A34);
  static const Color d2BorderStrong = Color(0xFF363B47);
  // Text scale.
  static const Color d2Text = Color(0xFFF4F6FB);
  static const Color d2TextSecondary = Color(0xFFA7AEBE);
  static const Color d2TextMuted = Color(0xFF6B7383);
  // Brand (indigo → violet).
  static const Color d2Primary = Color(0xFF6E5CF0);
  static const Color d2PrimaryHover = Color(0xFF7E6EFF);
  static const Color d2AccentSoft = Color(0xFF201F3A);
  // Scripture gold.
  static const Color d2Gold = Color(0xFFF2B84B);
  static const Color d2GoldSoft = Color(0xFF2A2415);
  // Broadcast status: bright ink + same-hue soft tint + border.
  static const Color d2Live = Color(0xFFFF4D4D);
  static const Color d2LiveSoft = Color(0xFF2A1416);
  static const Color d2LiveBorder = Color(0xFF5A2327);
  static const Color d2Preview = Color(0xFF35C08A);
  static const Color d2PreviewSoft = Color(0xFF10231C);
  static const Color d2PreviewBorder = Color(0xFF1C3A2E);
  static const Color d2Warn = Color(0xFFF5A524);
  static const Color d2WarnSoft = Color(0xFF2A2415);
  static const Color d2WarnBorder = Color(0xFF4A3A15);
  static const Color d2Info = Color(0xFF38BDF8);
  static const Color d2InfoSoft = Color(0xFF10222B);
}
