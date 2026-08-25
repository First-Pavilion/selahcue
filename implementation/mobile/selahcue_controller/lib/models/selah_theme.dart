/// SelahTheme — the Design 2.0 theme foundation for the mobile controller.
///
/// Colour, type, radius and spacing stop being applied ad-hoc per widget and
/// come from here. Every colour is a `DesignTokens.d2*` constant: that layer is
/// the mobile mirror of `selahcue-present::tokens::design2`, pinned
/// cross-surface by `test_tokens.rs::design2_palette_is_pinned_across_surfaces`
/// and WCAG-audited by `design2_palette_meets_wcag_aa`. Staying inside it is
/// what keeps the re-skin auditable — a raw hex here would be a colour no
/// surface test knows about.
///
/// Sources: `docs/design/DESIGN-2.0-HANDOFF.md` §2 (language), §3.1 (tokens,
/// radii, spacing, type), §4 (components), §5.8 (Mobile Remote), §6 (a11y);
/// Figma `SYQn5hFY8YVQKm3c6rw0eJ` frames `342:124` and `363:124`.
///
/// Two deliberate departures from the frames, both documented where they occur:
/// the primary button is a FLAT violet (not a gradient) because white on the
/// gradient's top stop is AA-large only, and the violet chip's label sits on
/// `surface` rather than `accent-soft` for the same reason. See §6.
library;

import 'package:flutter/material.dart';

import 'design_tokens.dart';

/// Corner radii (handoff §3.1: cards 14–16, controls/rows 8–12, pills 999).
abstract final class SelahRadius {
  /// Cards and panels.
  static const double card = 14;

  /// List rows and inner cards.
  static const double row = 12;

  /// Buttons, inputs, selects.
  static const double control = 10;

  /// Small badges.
  static const double badge = 8;

  /// Fully-round pills (chips, toggles).
  static const double pill = 999;
}

/// The spacing rhythm (handoff §3.1: `8 / 11–16 / 20–24`), named for what each
/// step is for rather than by number, so call sites read as intent.
abstract final class SelahSpace {
  /// Tight internal spacing (icon↔label, stacked label lines).
  static const double xs = 8;

  /// Between paired controls in a row (Figma: Prev/Next, ±1:00).
  static const double sm = 10;

  /// Inside a card.
  static const double md = 12;

  /// Between cards / list rows (Figma: 14 between host rows and verse rows).
  static const double lg = 14;

  /// Section spacing.
  static const double xl = 16;

  /// Page gutter — every mobile surface in the frames is inset 20 from the edge.
  static const double gutter = 20;

  /// Between major sections.
  static const double section = 24;
}

/// The type scale (handoff §3.1). The family is deliberately left null: Inter is
/// not bundled with this app and naming a font that resolves to nothing would be
/// a lie in code, so the scale (sizes/weights/letter-spacing — the load-bearing
/// part) rides the platform face. Bundling Inter is an asset/licensing decision,
/// not a re-skin one; when it lands, set [fontFamily] and nothing else changes.
abstract final class SelahType {
  static const String? fontFamily = null;

  /// The timer readout (MOBILE-2.0-SPEC §3.10: 68 / w800 / tabular).
  static const TextStyle display = TextStyle(
    fontSize: 68,
    fontWeight: FontWeight.w800,
    height: 1.05,
    fontFeatures: [FontFeature.tabularFigures()],
  );

  /// Full-screen headings (Access removed) — 22 / w700.
  static const TextStyle h1 = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    height: 1.25,
  );

  /// App-bar / sheet-identity title — 20 / w700 (*measured*).
  static const TextStyle appBar = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w700,
    height: 1.25,
  );

  /// Section heading — 17 / w700.
  static const TextStyle h2 = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w700,
    height: 1.25,
  );

  /// The on-air verse/slide text — 18 / w700 / 1.35 (*measured* `342:204`).
  static const TextStyle slide = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w700,
    height: 1.35,
  );

  /// Row title — 15 / w600.
  static const TextStyle rowTitle = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
  );

  /// Body / verse — 14 / w400 / 1.35.
  static const TextStyle body = TextStyle(fontSize: 14, height: 1.35);

  /// Secondary body — 13 / w400.
  static const TextStyle bodySmall = TextStyle(fontSize: 13, height: 1.4);

  /// Caption / hint / footnote — 12 / w400.
  static const TextStyle caption = TextStyle(fontSize: 12, height: 1.35);

  /// Standard button label — 15 / w600.
  static const TextStyle label = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
  );

  /// The full-width primary CTA label — 17 / w800 / +0.4.
  static const TextStyle cta = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w800,
    letterSpacing: 0.4,
  );

  /// Section overline — 11 / w800 / +0.8.
  static const TextStyle overline = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w800,
    letterSpacing: 0.8,
  );

  /// Status-chip label — 11 / w800 / +0.6.
  static const TextStyle chip = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w800,
    letterSpacing: 0.6,
  );

  /// Role-chip label — one step up from [chip]: 12 / w700 / +0.2 (*measured*
  /// `364:130`).
  static const TextStyle roleChip = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w700,
    letterSpacing: 0.2,
  );
}

/// Gradients — the only two colours in the mobile layer that are not `d2*`
/// members, both isolated here rather than added to the pinned palette
/// (MOBILE-2.0-SPEC §2.6: a Dart-only `DesignTokens` member would create exactly
/// the cross-surface drift the project forbids).
///
/// * [onAirWash] is built the token-only way the spec recommends: the frames
///   measure its top stop at `#231B48`, 14/255 off `d2AccentSoft` in the blue
///   channel and invisible behind the text that sits on it.
/// * [goLive] keeps the frame's measured stops, because a gradient's ENDS are
///   what the label has to survive and the spec audits those two exact values
///   (8.50:1 / 5.21:1 against [goLiveInk]). Both ends are re-asserted in
///   `test/models/selah_theme_test.dart` — a gradient can pass contrast at one
///   end and fail at the other, so auditing a midpoint would be worthless.
abstract final class SelahGradient {
  /// The audience-content wash behind a Preview/Live monitor card
  /// (*measured* `342:202`, `363:155`, `363:162`).
  static const LinearGradient onAirWash = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [DesignTokens.d2AccentSoft, DesignTokens.d2Base],
  );

  /// The light (leading) stop of [goLive] — *measured* `342:215`.
  static const Color goLiveLight = Color(0xFF3DD299);

  /// The deep (trailing) stop of [goLive] — *measured* `342:215`.
  static const Color goLiveDeep = Color(0xFF27A478);

  /// GO LIVE — the one green gradient in the app.
  static const LinearGradient goLive = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [goLiveLight, goLiveDeep],
  );

  /// The label ink on [goLive]. Dark-on-bright, not white-on-bright: white over
  /// the light stop measures 1.93:1 and fails AA outright (spec §6.1).
  static const Color goLiveInk = DesignTokens.d2PreviewSoft;

  /// The label ink on a solid `d2Live` fill (armed emergency, TIME UP). White
  /// there is 3.27:1; this is 5.31:1 (spec §6.1).
  static const Color onLiveInk = DesignTokens.d2LiveSoft;
}

/// The app theme.
abstract final class SelahTheme {
  /// Design 2.0, dark. The controller has no light mode — it is used in a dim
  /// booth beside a live output, and a light surface beside the audience screen
  /// is a glare source, not a preference.
  static ThemeData dark() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: DesignTokens.d2Primary,
          brightness: Brightness.dark,
        ).copyWith(
          primary: DesignTokens.d2Primary,
          onPrimary: Colors.white,
          secondary: DesignTokens.d2PrimaryHover,
          surface: DesignTokens.d2Surface,
          onSurface: DesignTokens.d2Text,
          surfaceContainerHighest: DesignTokens.d2Elevated,
          surfaceContainerLowest: DesignTokens.d2Inset,
          error: DesignTokens.d2Live,
          onError: Colors.white,
          outline: DesignTokens.d2Border,
          outlineVariant: DesignTokens.d2BorderStrong,
        );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: SelahType.fontFamily,
      colorScheme: scheme,
      scaffoldBackgroundColor: DesignTokens.d2Base,
      canvasColor: DesignTokens.d2Base,
      dividerColor: DesignTokens.d2Border,
      textTheme: _textTheme,
      appBarTheme: const AppBarTheme(
        // The frames show a flat bar in the page colour, not a raised panel.
        backgroundColor: DesignTokens.d2Base,
        surfaceTintColor: Colors.transparent,
        foregroundColor: DesignTokens.d2Text,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleSpacing: SelahSpace.gutter,
        iconTheme: IconThemeData(color: DesignTokens.d2TextSecondary),
        actionsIconTheme: IconThemeData(color: DesignTokens.d2TextSecondary),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: DesignTokens.d2Surface,
        surfaceTintColor: Colors.transparent,
        indicatorColor: DesignTokens.d2AccentSoft,
        elevation: 0,
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => SelahType.caption.copyWith(
            fontWeight: FontWeight.w600,
            color: states.contains(WidgetState.selected)
                ? DesignTokens.d2PrimaryHover
                : DesignTokens.d2TextSecondary,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            size: 22,
            color: states.contains(WidgetState.selected)
                ? DesignTokens.d2PrimaryHover
                : DesignTokens.d2TextSecondary,
          ),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: DesignTokens.d2Border,
        thickness: 1,
        space: 1,
      ),
      // Fields read as RAISED here, not sunken: the page is `base`, so `surface`
      // is what separates a field from it. (`inset` is for wells inside a card.)
      // Measured off Figma `343:141` — the scripture search field is `#14161D`.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: DesignTokens.d2Surface,
        hintStyle: SelahType.body.copyWith(
          color: DesignTokens.d2TextSecondary,
        ),
        labelStyle: SelahType.body.copyWith(
          color: DesignTokens.d2TextSecondary,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: SelahSpace.lg,
          vertical: SelahSpace.md,
        ),
        border: _fieldBorder(DesignTokens.d2Border),
        enabledBorder: _fieldBorder(DesignTokens.d2Border),
        focusedBorder: _fieldBorder(DesignTokens.d2Primary, width: 2),
        errorBorder: _fieldBorder(DesignTokens.d2Live),
        focusedErrorBorder: _fieldBorder(DesignTokens.d2Live, width: 2),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: const WidgetStatePropertyAll(Colors.white),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? DesignTokens.d2Primary
              : DesignTokens.d2Elevated,
        ),
        trackOutlineColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? DesignTokens.d2Primary
              : DesignTokens.d2Border,
        ),
      ),
      // ≥44pt on every primary control (handoff §6 / NFR-026) — set on the
      // themes rather than per call site so a new button inherits it.
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: DesignTokens.d2Primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(0, kSelahMinTouchTarget),
          textStyle: SelahType.label,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SelahRadius.control),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: DesignTokens.d2Text,
          backgroundColor: DesignTokens.d2Elevated,
          side: const BorderSide(color: DesignTokens.d2Border),
          minimumSize: const Size(0, kSelahMinTouchTarget),
          textStyle: SelahType.label,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SelahRadius.control),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: DesignTokens.d2PrimaryHover,
          minimumSize: const Size(0, kSelahMinTouchTarget),
          textStyle: SelahType.label,
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: DesignTokens.d2Surface,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: SelahType.h2.copyWith(color: DesignTokens.d2Text),
        contentTextStyle: SelahType.body.copyWith(color: DesignTokens.d2Text),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SelahRadius.card),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        // The Config sheet sits on `base` and stacks `surface` cards inside it
        // (Figma `366:128`) — the same layering as a page, not a raised panel.
        backgroundColor: DesignTokens.d2Base,
        surfaceTintColor: Colors.transparent,
        dragHandleColor: DesignTokens.d2BorderStrong,
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: DesignTokens.d2Surface,
        surfaceTintColor: Colors.transparent,
        textStyle: SelahType.bodySmall.copyWith(color: DesignTokens.d2Text),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SelahRadius.control),
          side: const BorderSide(color: DesignTokens.d2Border),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: DesignTokens.d2Elevated,
        contentTextStyle: SelahType.bodySmall.copyWith(
          color: DesignTokens.d2Text,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SelahRadius.control),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: DesignTokens.d2Primary,
        linearTrackColor: DesignTokens.d2Elevated,
        circularTrackColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: DesignTokens.d2Surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SelahRadius.card),
          side: const BorderSide(color: DesignTokens.d2Border),
        ),
      ),
      listTileTheme: const ListTileThemeData(
        textColor: DesignTokens.d2Text,
        iconColor: DesignTokens.d2TextSecondary,
      ),
      iconTheme: const IconThemeData(color: DesignTokens.d2TextSecondary),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? DesignTokens.d2Primary
              : Colors.transparent,
        ),
        side: const BorderSide(color: DesignTokens.d2BorderStrong),
      ),
      expansionTileTheme: const ExpansionTileThemeData(
        textColor: DesignTokens.d2Text,
        collapsedTextColor: DesignTokens.d2TextSecondary,
        iconColor: DesignTokens.d2TextSecondary,
        collapsedIconColor: DesignTokens.d2TextSecondary,
      ),
    );
  }

  static OutlineInputBorder _fieldBorder(Color color, {double width = 1}) =>
      OutlineInputBorder(
        borderRadius: BorderRadius.circular(SelahRadius.control),
        borderSide: BorderSide(color: color, width: width),
      );

  static final TextTheme _textTheme = TextTheme(
    displayLarge: SelahType.display.copyWith(color: DesignTokens.d2Text),
    headlineSmall: SelahType.h1.copyWith(color: DesignTokens.d2Text),
    titleLarge: SelahType.h2.copyWith(color: DesignTokens.d2Text),
    titleMedium: SelahType.label.copyWith(color: DesignTokens.d2Text),
    bodyLarge: SelahType.body.copyWith(color: DesignTokens.d2Text),
    bodyMedium: SelahType.bodySmall.copyWith(color: DesignTokens.d2Text),
    bodySmall: SelahType.caption.copyWith(color: DesignTokens.d2TextSecondary),
    labelLarge: SelahType.label.copyWith(color: DesignTokens.d2Text),
    labelSmall: SelahType.overline.copyWith(
      color: DesignTokens.d2TextSecondary,
    ),
  );
}

/// The minimum side of any primary control (handoff §6 / NFR-026: ≥44×44pt).
const double kSelahMinTouchTarget = 48;
