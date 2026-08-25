/// The app actually INSTALLS the Design 2.0 theme.
///
/// `SelahTheme` shipped complete and unreferenced: `main.dart` built an inline
/// `ThemeData` seeded with the Design 1.0 brand blue on the Design 1.0 navy, so
/// every ambient consumer — Switch, dialogs, the text-field cursor and
/// selection, focus rings, snackbars, any Scaffold without an explicit
/// background — rendered the old palette while `selah_theme.dart`'s own doc
/// comments (and other files' comments referring to it) said otherwise. No
/// widget test could see it, because no widget test asserted on the AMBIENT
/// theme; they all asserted on colours the views paint by hand.
///
/// So this asserts the wiring itself, at the one place it happens.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/main.dart';
import 'package:selahcue_controller/models/design_tokens.dart';
import 'package:selahcue_controller/models/selah_theme.dart';
import 'package:selahcue_controller/models/settings.dart';

class _MemStore implements SettingsStore {
  String? _value;
  @override
  Future<String?> read() async => _value;
  @override
  Future<void> write(String value) async => _value = value;
}

class _NoWakelock implements WakelockControl {
  @override
  Future<void> toggle(bool enabled) async {}
}

SettingsController _settings({bool reduceMotion = false}) => SettingsController(
      store: _MemStore(),
      wakelock: _NoWakelock(),
      hapticSink: () async {},
      reduceMotion: reduceMotion,
    );

void main() {
  setUp(() {
    // The Launcher reads the stored profile from secure storage on its first
    // frame; without the plugin that read never resolves under the fake clock.
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async => null);
  });

  /// Mount the real app, read what it handed MaterialApp, then tear it back
  /// down and let the splash's 900 ms brand delay expire — the binding's
  /// pending-timer check runs before tearDown, so the flush has to happen here.
  ///
  /// The returned widget outlives its element on purpose: `theme` and `builder`
  /// are plain data, and reading them off the real `SelahCueApp` is the whole
  /// point — a copy assembled by the test would prove nothing about the app.
  Future<MaterialApp> mount(WidgetTester tester,
      {bool reduceMotion = false}) async {
    await tester
        .pumpWidget(SelahCueApp(settings: _settings(reduceMotion: reduceMotion)));
    await tester.pump();
    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 2));
    return app;
  }

  testWidgets('MaterialApp carries the d2 palette, not the Design 1.0 one',
      (tester) async {
    final theme = (await mount(tester)).theme;

    expect(theme, isNotNull, reason: 'the app must not fall back to defaults');
    expect(theme!.scaffoldBackgroundColor, DesignTokens.d2Base);
    expect(theme.colorScheme.primary, DesignTokens.d2Primary);
    expect(theme.colorScheme.surface, DesignTokens.d2Surface);
    expect(theme.colorScheme.onSurface, DesignTokens.d2Text);

    // The exact values the old inline theme used — named so a regression fails
    // with the reason written into it rather than as a bare colour mismatch.
    expect(theme.scaffoldBackgroundColor, isNot(DesignTokens.bgBase),
        reason: 'the Design 1.0 navy is gone from the app shell');
    expect(theme.colorScheme.primary, isNot(DesignTokens.accentBrand),
        reason: 'the Design 1.0 brand blue no longer seeds the scheme');
  });

  testWidgets('the ambient slots the views never set come from SelahTheme',
      (tester) async {
    final theme = (await mount(tester)).theme!;
    final expected = SelahTheme.dark();

    // Sampled rather than compared wholesale: ThemeData has no meaningful
    // equality, and these are the slots a hand-rolled ThemeData silently got
    // wrong.
    expect(theme.inputDecorationTheme.fillColor,
        expected.inputDecorationTheme.fillColor);
    expect(theme.switchTheme.trackColor?.resolve({WidgetState.selected}),
        DesignTokens.d2Primary);
    expect(theme.dialogTheme.backgroundColor, DesignTokens.d2Surface);
    expect(theme.cardTheme.color, DesignTokens.d2Surface);
    expect(theme.snackBarTheme.backgroundColor, DesignTokens.d2Elevated);
  });

  group('the reduced-motion builder still does its job', () {
    /// Run `MaterialApp.builder` the way MaterialApp does — below the theme,
    /// below SettingsScope, with a MediaQuery — and hand back what it produced.
    Future<Widget> run(
      WidgetTester tester,
      MaterialApp app, {
      required SettingsController settings,
      required bool osDisablesAnimations,
      required Widget child,
    }) async {
      late Widget produced;
      await tester.pumpWidget(
        MediaQuery(
          data: MediaQueryData.fromView(tester.view)
              .copyWith(disableAnimations: osDisablesAnimations),
          child: Theme(
            data: app.theme!,
            child: SettingsScope(
              settings: settings,
              child: Builder(
                builder: (context) => produced = app.builder!(context, child),
              ),
            ),
          ),
        ),
      );
      return produced;
    }

    testWidgets('the in-app preference strips page transitions and keeps the '
        'palette', (tester) async {
      final app = await mount(tester);
      const child = SizedBox(key: ValueKey('page'));
      final produced = await run(tester, app,
          settings: _settings(reduceMotion: true),
          osDisablesAnimations: false,
          child: child);

      expect(produced, isA<Theme>(),
          reason: 'reduced motion is applied by re-theming the subtree');
      final applied = (produced as Theme).data;
      // The copyWith must not lose the palette on its way past.
      expect(applied.scaffoldBackgroundColor, DesignTokens.d2Base);
      expect(applied.colorScheme.primary, DesignTokens.d2Primary);

      final builders = applied.pageTransitionsTheme.builders;
      expect(builders.keys, containsAll(TargetPlatform.values));
      final route = MaterialPageRoute<void>(builder: (_) => const SizedBox());
      for (final platform in TargetPlatform.values) {
        expect(
          builders[platform]!.buildTransitions<void>(
            route,
            tester.element(find.byKey(const ValueKey('page'))),
            kAlwaysCompleteAnimation,
            kAlwaysCompleteAnimation,
            child,
          ),
          same(child),
          reason: '$platform must render the page with no transition at all',
        );
      }
    });

    testWidgets('the OS accessibility setting counts too', (tester) async {
      final app = await mount(tester);
      final produced = await run(tester, app,
          settings: _settings(),
          osDisablesAnimations: true,
          child: const SizedBox(key: ValueKey('page')));
      expect(produced, isA<Theme>());
    });

    testWidgets('with motion allowed the child passes straight through',
        (tester) async {
      final app = await mount(tester);
      const child = SizedBox(key: ValueKey('page'));
      final produced = await run(tester, app,
          settings: _settings(),
          osDisablesAnimations: false,
          child: child);
      expect(produced, same(child),
          reason: 'no extra Theme, and therefore no changed transitions');
    });
  });
}
