/// `SelahTheme` — the Design 2.0 theme foundation, and the two colours that sit
/// just outside the pinned token layer.
///
/// Two things are asserted here that nothing else could:
///
/// 1. **The GO LIVE gradient stops.** `SelahGradient.goLiveLight` /
///    `goLiveDeep` are raw hexes by deliberate design — a Dart-only
///    `DesignTokens` member would be a colour the Rust surface test knows
///    nothing about, which is the cross-surface drift the project forbids
///    (MOBILE-2.0-SPEC §2.6). But "not in the pinned palette" was allowed to
///    mean "not pinned at all": `selah_theme.dart` claimed both ends were
///    re-asserted in THIS file, and this file did not exist. A gradient can pass
///    contrast at one end and fail at the other, so both ends are measured, not
///    a midpoint.
/// 2. **That they are the only two.** The guard below reads `lib/` and fails on
///    any new `Color(0x…)` outside `design_tokens.dart` — the same
///    source-text discipline as `token_drift_test.dart`, aimed at the other way
///    a colour escapes review.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/design_tokens.dart';
import 'package:selahcue_controller/models/selah_theme.dart';

// One WCAG implementation for the whole suite — two would be free to drift.
import 'design_tokens_test.dart' show contrast;

void main() {
  group('the GO LIVE gradient', () {
    test('both stops are the measured Figma values', () {
      expect(SelahGradient.goLiveLight, const Color(0xFF3DD299),
          reason: '*measured* 342:215, leading stop');
      expect(SelahGradient.goLiveDeep, const Color(0xFF27A478),
          reason: '*measured* 342:215, trailing stop');
      expect(SelahGradient.goLive.colors,
          [SelahGradient.goLiveLight, SelahGradient.goLiveDeep]);
    });

    test('the label survives BOTH ends, not just the flattering one', () {
      // The values the spec (§6.1) audits, to 2dp. A pin without the measured
      // number would let a stop drift to a still-passing but different colour.
      expect(contrast(SelahGradient.goLiveLight, SelahGradient.goLiveInk),
          closeTo(8.50, 0.01));
      expect(contrast(SelahGradient.goLiveDeep, SelahGradient.goLiveInk),
          closeTo(5.21, 0.01));
      for (final stop in SelahGradient.goLive.colors) {
        expect(contrast(stop, SelahGradient.goLiveInk),
            greaterThanOrEqualTo(4.5),
            reason: 'the GO LIVE label on $stop');
      }
    });

    test('white is why the ink is dark — it fails outright on the light stop',
        () {
      // Not a curiosity: white-on-green is the obvious thing to reach for, and
      // this is the measurement that says no (spec §6.1).
      expect(contrast(SelahGradient.goLiveLight, const Color(0xFFFFFFFF)),
          lessThan(3.0));
      expect(SelahGradient.goLiveInk, DesignTokens.d2PreviewSoft);
    });

    test('the solid-live ink clears AA on its fill', () {
      expect(contrast(DesignTokens.d2Live, SelahGradient.onLiveInk),
          closeTo(5.31, 0.01));
      expect(SelahGradient.onLiveInk, DesignTokens.d2LiveSoft);
    });

    test('the on-air wash stays entirely inside the pinned palette', () {
      expect(SelahGradient.onAirWash.colors,
          [DesignTokens.d2AccentSoft, DesignTokens.d2Base]);
    });
  });

  test('the gradient stops are the ONLY raw hexes outside the token layer', () {
    final dir = Directory('lib');
    expect(dir.existsSync(), isTrue, reason: 'run this test from the app root');
    final found = <String>{};
    for (final file in dir
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))) {
      if (file.path.endsWith('design_tokens.dart')) continue;
      for (final m in RegExp(r'Color\(0x([0-9A-Fa-f]{8})\)')
          .allMatches(file.readAsStringSync())) {
        found.add('${file.path} → 0x${m.group(1)!.toUpperCase()}');
      }
    }
    expect(found, {
      'lib/models/selah_theme.dart → 0xFF3DD299',
      'lib/models/selah_theme.dart → 0xFF27A478',
    }, reason: 'a raw hex outside design_tokens.dart is a colour no surface '
        'test knows about. Use a d2* token; if a measured literal is genuinely '
        'right, isolate it in SelahGradient and pin it above.');
  });

  group('SelahTheme.dark()', () {
    final theme = SelahTheme.dark();

    test('is built from the Design 2.0 palette, not the Design 1.0 one', () {
      expect(theme.brightness, Brightness.dark);
      expect(theme.scaffoldBackgroundColor, DesignTokens.d2Base);
      expect(theme.canvasColor, DesignTokens.d2Base);
      expect(theme.colorScheme.primary, DesignTokens.d2Primary);
      expect(theme.colorScheme.surface, DesignTokens.d2Surface);
      expect(theme.colorScheme.onSurface, DesignTokens.d2Text);
      expect(theme.colorScheme.error, DesignTokens.d2Live);
      expect(theme.colorScheme.outline, DesignTokens.d2Border);
      expect(theme.dividerColor, DesignTokens.d2Border);

      expect(theme.scaffoldBackgroundColor, isNot(DesignTokens.bgBase));
      expect(theme.colorScheme.primary, isNot(DesignTokens.accentBrand));
    });

    // The slots the views never set by hand — the whole reason installing the
    // theme matters. Each of these renders Design 1.0 under an inline
    // `ThemeData` and nothing in a widget test would say so.
    test('carries the ambient slots no widget colours for itself', () {
      expect(theme.inputDecorationTheme.fillColor, DesignTokens.d2Surface);
      expect(theme.dialogTheme.backgroundColor, DesignTokens.d2Surface);
      expect(theme.cardTheme.color, DesignTokens.d2Surface);
      expect(theme.snackBarTheme.backgroundColor, DesignTokens.d2Elevated);
      expect(theme.popupMenuTheme.color, DesignTokens.d2Surface);
      expect(theme.bottomSheetTheme.backgroundColor, DesignTokens.d2Base);
      expect(theme.progressIndicatorTheme.color, DesignTokens.d2Primary);
      expect(
        theme.switchTheme.trackColor?.resolve({WidgetState.selected}),
        DesignTokens.d2Primary,
      );
      expect(
        theme.switchTheme.trackColor?.resolve(const {}),
        DesignTokens.d2Elevated,
      );
    });
  });
}
