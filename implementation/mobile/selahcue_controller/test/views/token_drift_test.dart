/// Design 2.0 drift guard.
///
/// The re-skin moved every surface onto the `d2*` token layer. The legacy
/// (Design 1.0) constants deliberately REMAIN in `design_tokens.dart` — they are
/// still the canonical mirror pinned by `selahcue-present/tests/test_tokens.rs`
/// and are still used by the desktop surfaces — so nothing stops a new widget
/// from reaching for `DesignTokens.bgPanel` again and quietly reintroducing the
/// old navy. A colour regression is invisible in a diff and invisible in a
/// passing widget test; it is only visible on a phone. So it is asserted here,
/// against the source itself.
///
/// The scan covers the whole of `lib/`, not just `lib/views/`. A views-only scan
/// is what let `main.dart` keep an inline Design 1.0 `ThemeData` — the single
/// most consequential legacy reference in the app, since it set the AMBIENT
/// theme for every widget that does not colour itself — through a green suite.
/// The palette a screen inherits is as much a drift surface as the palette it
/// paints.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Legacy palette members no Dart source in this app may reference.
/// `outputBlack` is intentionally absent: the audience-output black is not a
/// themed surface and does not change between design generations.
const _legacy = <String>[
  'bgBase',
  'bgPanel',
  'border',
  'textPrimary',
  'textMuted',
  'accentBrand',
  'previewInk',
  'liveInk',
  'warnInk',
  'previewFill',
  'liveFill',
  'warnFill',
];

/// `d2TextMuted` measures 3.45–4.08:1 on the Design 2.0 surfaces and fails
/// AA-normal (see `design_tokens_test.dart`). It is legitimate for non-text
/// decoration only, and **nothing in the app currently needs it** — the nav
/// bar's view-only dot, once described here as the sanctioned use, is
/// `d2TextSecondary` (`controller_view.dart`). So the budget is the true count,
/// zero: any first use has to arrive with a deliberate, argued raise rather than
/// slipping into a slot that was already open.
const _mutedBudget = 0;

List<File> _librarySources() {
  final dir = Directory('lib');
  expect(dir.existsSync(), isTrue, reason: 'run this test from the app root');
  return dir
      .listSync(recursive: true)
      .whereType<File>()
      .where((f) => f.path.endsWith('.dart'))
      .toList();
}

void main() {
  test('no source reaches back for the Design 1.0 palette', () {
    final offenders = <String>[];
    for (final file in _librarySources()) {
      final source = file.readAsStringSync();
      for (final name in _legacy) {
        // Word-bounded so `DesignTokens.border` never matches `d2Border`, and
        // `textMuted` never matches `d2TextMuted`. Matching on the qualified
        // `DesignTokens.<name>` form also means the DECLARATIONS in
        // `design_tokens.dart` are not hits — the legacy layer must stay, it
        // just must not be reached for.
        final hit = RegExp('DesignTokens\\.$name\\b').firstMatch(source);
        if (hit != null) {
          final line = '\n'.allMatches(source.substring(0, hit.start)).length + 1;
          offenders.add('${file.path}:$line → DesignTokens.$name');
        }
      }
    }
    expect(offenders, isEmpty,
        reason: 'Design 2.0 uses the d2* layer. Legacy tokens found:\n'
            '${offenders.join('\n')}');
  });

  test('d2TextMuted stays a decorative exception, not a habit', () {
    var uses = 0;
    for (final file in _librarySources()) {
      uses += RegExp(r'DesignTokens\.d2TextMuted\b')
          .allMatches(file.readAsStringSync())
          .length;
    }
    expect(uses, lessThanOrEqualTo(_mutedBudget),
        reason: 'd2TextMuted fails AA for text. Use d2TextSecondary unless the '
            'element carries no text at all; if a new decorative use is right, '
            'raise the budget deliberately and say why.');
  });
}
