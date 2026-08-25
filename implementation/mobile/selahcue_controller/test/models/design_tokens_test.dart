import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/design_tokens.dart';

/// Token audit (story 86ajp0b3d), mobile side: the values match UX-CANONICAL §4
/// exactly and mirror the Rust source of truth (`selahcue-present/src/tokens.rs`,
/// which pins THIS file's literals from its own test — change together).
double lum(Color c) {
  double ch(double v) =>
      v <= 0.04045 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
  return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
}

double contrast(Color a, Color b) {
  final la = lum(a), lb = lum(b);
  final hi = math.max(la, lb), lo = math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  test('canonical fills match UX-CANONICAL exactly', () {
    expect(DesignTokens.previewFill, const Color(0xFF0F7B6C));
    expect(DesignTokens.liveFill, const Color(0xFFA3283A));
    expect(DesignTokens.warnFill, const Color(0xFF9A5B00));
  });

  test('on-dark inks match the Figma design system', () {
    expect(DesignTokens.previewInk, const Color(0xFF2BB673));
    expect(DesignTokens.liveInk, const Color(0xFFEF4444));
    expect(DesignTokens.warnInk, const Color(0xFFF2B53C));
  });

  test('staged and warning are never the same colour', () {
    expect(DesignTokens.previewFill, isNot(DesignTokens.warnFill));
    expect(DesignTokens.previewInk, isNot(DesignTokens.warnInk));
  });

  test('audited pairings meet WCAG-AA (4.5:1)', () {
    const white = Color(0xFFFFFFFF);
    for (final fill in [
      DesignTokens.previewFill,
      DesignTokens.liveFill,
      DesignTokens.warnFill,
    ]) {
      expect(contrast(white, fill), greaterThanOrEqualTo(4.5),
          reason: 'white text on $fill');
    }
    for (final ink in [
      DesignTokens.previewInk,
      DesignTokens.liveInk,
      DesignTokens.warnInk,
      DesignTokens.textPrimary,
    ]) {
      expect(contrast(ink, DesignTokens.bgBase), greaterThanOrEqualTo(4.5),
          reason: '$ink on the base background');
    }
  });

  // — "Design 2.0" layer ------------------------------------------------------
  //
  // These literals are ALSO pinned from Rust: `test_tokens.rs`
  // (`design2_palette_is_pinned_across_surfaces`) greps THIS package's
  // `design_tokens.dart` for the textual form `d2<Camel> = Color(0xFF<HEX>)`.
  // Reformatting those declarations breaks a Rust test, not a Dart one — so the
  // mirror is asserted here too, where the failure names the surface it broke.

  test('design 2.0 palette matches the pinned cross-surface manifest', () {
    // Neutral ramp.
    expect(DesignTokens.d2Base, const Color(0xFF0B0D12));
    expect(DesignTokens.d2Surface, const Color(0xFF14161D));
    expect(DesignTokens.d2Elevated, const Color(0xFF1C1F28));
    expect(DesignTokens.d2Inset, const Color(0xFF0F1116));
    expect(DesignTokens.d2Border, const Color(0xFF262A34));
    expect(DesignTokens.d2BorderStrong, const Color(0xFF363B47));
    // Text scale.
    expect(DesignTokens.d2Text, const Color(0xFFF4F6FB));
    expect(DesignTokens.d2TextSecondary, const Color(0xFFA7AEBE));
    expect(DesignTokens.d2TextMuted, const Color(0xFF6B7383));
    // Brand.
    expect(DesignTokens.d2Primary, const Color(0xFF6E5CF0));
    expect(DesignTokens.d2PrimaryHover, const Color(0xFF7E6EFF));
    expect(DesignTokens.d2AccentSoft, const Color(0xFF201F3A));
    // Scripture gold.
    expect(DesignTokens.d2Gold, const Color(0xFFF2B84B));
    expect(DesignTokens.d2GoldSoft, const Color(0xFF2A2415));
    // Broadcast status triples.
    expect(DesignTokens.d2Live, const Color(0xFFFF4D4D));
    expect(DesignTokens.d2LiveSoft, const Color(0xFF2A1416));
    expect(DesignTokens.d2LiveBorder, const Color(0xFF5A2327));
    expect(DesignTokens.d2Preview, const Color(0xFF35C08A));
    expect(DesignTokens.d2PreviewSoft, const Color(0xFF10231C));
    expect(DesignTokens.d2PreviewBorder, const Color(0xFF1C3A2E));
    expect(DesignTokens.d2Warn, const Color(0xFFF5A524));
    expect(DesignTokens.d2WarnSoft, const Color(0xFF2A2415));
    expect(DesignTokens.d2WarnBorder, const Color(0xFF4A3A15));
    expect(DesignTokens.d2Info, const Color(0xFF38BDF8));
    expect(DesignTokens.d2InfoSoft, const Color(0xFF10222B));
  });

  test('design 2.0 keeps one meaning per colour family', () {
    // Green may never be mistaken for amber, nor staged for on-air.
    expect(DesignTokens.d2Preview, isNot(DesignTokens.d2Warn));
    expect(DesignTokens.d2Preview, isNot(DesignTokens.d2Live));
    // Gold is scripture identity, never status — it must not equal the warning
    // ink even though both read as "amber" to the eye.
    expect(DesignTokens.d2Gold, isNot(DesignTokens.d2Warn));
  });

  test('design 2.0 body text meets WCAG-AA on every neutral surface', () {
    for (final bg in [
      DesignTokens.d2Base,
      DesignTokens.d2Surface,
      DesignTokens.d2Elevated,
      DesignTokens.d2Inset,
    ]) {
      for (final fg in [DesignTokens.d2Text, DesignTokens.d2TextSecondary]) {
        expect(contrast(fg, bg), greaterThanOrEqualTo(4.5),
            reason: '$fg on $bg');
      }
    }
  });

  // The redesign inverts the fill/ink split: status is now BRIGHT INK on a
  // same-hue soft tint, not white on a saturated fill. That is a different
  // audit, so it is measured rather than assumed.
  test('design 2.0 status ink meets WCAG-AA on its own soft tint', () {
    const pairs = <(String, Color, Color)>[
      ('live', DesignTokens.d2Live, DesignTokens.d2LiveSoft),
      ('preview', DesignTokens.d2Preview, DesignTokens.d2PreviewSoft),
      ('warn', DesignTokens.d2Warn, DesignTokens.d2WarnSoft),
      ('info', DesignTokens.d2Info, DesignTokens.d2InfoSoft),
      ('gold', DesignTokens.d2Gold, DesignTokens.d2GoldSoft),
    ];
    for (final (name, ink, soft) in pairs) {
      expect(contrast(ink, soft), greaterThanOrEqualTo(4.5),
          reason: '$name ink on its soft tint');
    }
  });

  // Guards the trap the re-skin walked into: `d2TextMuted` looks like the
  // natural heir to the old `textMuted`, but it is a TERTIARY/decorative value
  // that fails AA for body text on every Design 2.0 surface. If a future palette
  // change lifts it above the line, this test fails loudly — at which point the
  // ban in `token_drift_test.dart` can be relaxed deliberately, not by accident.
  test('d2TextMuted is decorative only — it does NOT meet AA for text', () {
    for (final bg in [
      DesignTokens.d2Base,
      DesignTokens.d2Surface,
      DesignTokens.d2Elevated,
    ]) {
      expect(contrast(DesignTokens.d2TextMuted, bg), lessThan(4.5),
          reason: 'if this now passes, revisit the d2TextMuted ban');
    }
  });
}
