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
}
