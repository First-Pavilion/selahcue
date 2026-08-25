/// The Design 2.0 component primitives (MOBILE-2.0-SPEC §3) — built once here,
/// reused by every surface. Nothing in this file knows about the live session;
/// these are pure presentation, driven by a semantic [SelahTone] rather than a
/// raw colour, so a caller cannot invent a fifth meaning for green.
///
/// Colour comes exclusively from the `DesignTokens.d2*` layer via [SelahTheme].
/// Where the frames reach for a colour the pinned palette does not carry, it is
/// DERIVED here from the palette's own pair (spec §2.6) — never added to
/// `design_tokens.dart`, whose `d2<Camel> = Color(0xFF<HEX>)` lines are grepped
/// cross-surface by `test_tokens.rs`.
///
/// Where the frames themselves fail WCAG AA, this file builds the fix and not
/// the frame; each one is commented with its measured ratio (spec §6.1–§6.2).
library;

import 'package:flutter/material.dart';

import '../../models/design_tokens.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import '../../models/settings.dart';

/// A semantic colour role (spec §2.5). One meaning per family (UX-CANONICAL §4,
/// handoff §2): green = staged/safe and never "on air", red = live/alarm, amber
/// = warning, blue = neutral-informational, violet = brand/selection, gold =
/// SCRIPTURE only — gold never means status.
enum SelahTone { live, preview, warn, gold, info, brand, neutral }

/// The tone a granted role wears — the app-bar chip, and the `ROLES THAT CAN …`
/// chips on the permission sheet (spec §4.10), which must agree with it or the
/// same role would appear in two colours on two screens.
///
/// The most-capable remote role takes brand violet, the content roles take the
/// gold/green pair, and a view-only role is neutral. Presentation only — the
/// desktop remains the RBAC authority.
SelahTone roleTone(MobileRole role) {
  switch (role) {
    case MobileRole.operator:
      return SelahTone.brand;
    case MobileRole.producer:
      return SelahTone.preview;
    // Gold means Scripture, and `assistant` IS the Scripture Operator on this
    // backend (spec §5.3).
    case MobileRole.assistant:
      return SelahTone.gold;
    case MobileRole.viewer:
    case MobileRole.unknown:
      return SelahTone.neutral;
  }
}

/// The three colours a tone resolves to: an ink on a same-hue soft tint with a
/// border. This replaces Design 1.0's white-on-saturated-fill chips.
@immutable
class SelahToneStyle {
  /// Text and glyph colour.
  final Color ink;

  /// The soft same-hue tint behind [ink].
  final Color fill;

  /// The 1px hairline around [fill].
  final Color border;

  /// The leading dot's colour. Equal to [ink] for every tone except `brand`,
  /// where the label had to give up the violet to clear AA but the dot did not
  /// (it carries no reading).
  final Color dot;

  const SelahToneStyle({
    required this.ink,
    required this.fill,
    required this.border,
    Color? dot,
  }) : dot = dot ?? ink;

  /// `d2Info` ships an ink and a soft tint but no border member, while
  /// live/preview/warn all have one (spec §2.6/Q1). Deriving it with the
  /// palette's own construction reproduces `d2PreviewBorder` from its pair to
  /// within 6/255, so this is the palette's rule rather than an invention.
  /// Escalating to a real `d2InfoBorder` is a four-surface story, not a mobile
  /// change.
  static final Color infoBorder = Color.lerp(
    DesignTokens.d2InfoSoft,
    DesignTokens.d2Info,
    0.16,
  )!;

  /// The brand chip's border — violet at half strength over its own tint.
  static final Color brandBorder = Color.lerp(
    DesignTokens.d2AccentSoft,
    DesignTokens.d2PrimaryHover,
    0.5,
  )!;

  static SelahToneStyle of(SelahTone tone) => switch (tone) {
    SelahTone.live => const SelahToneStyle(
      ink: DesignTokens.d2Live,
      fill: DesignTokens.d2LiveSoft,
      border: DesignTokens.d2LiveBorder,
    ),
    SelahTone.preview => const SelahToneStyle(
      ink: DesignTokens.d2Preview,
      fill: DesignTokens.d2PreviewSoft,
      border: DesignTokens.d2PreviewBorder,
    ),
    SelahTone.warn => const SelahToneStyle(
      ink: DesignTokens.d2Warn,
      fill: DesignTokens.d2WarnSoft,
      border: DesignTokens.d2WarnBorder,
    ),
    // Gold and warn share a tint hex (`#2A2415`) and, per spec §2.4, a border —
    // the palette has no separate gold border and the frames use `#4A3A15`
    // behind gold. Only the INK separates scripture from warning.
    SelahTone.gold => const SelahToneStyle(
      ink: DesignTokens.d2Gold,
      fill: DesignTokens.d2GoldSoft,
      border: DesignTokens.d2WarnBorder,
    ),
    SelahTone.info => SelahToneStyle(
      ink: DesignTokens.d2Info,
      fill: DesignTokens.d2InfoSoft,
      border: infoBorder,
    ),
    // A11Y-FIX (spec §6.5): the frames draw this chip as `d2PrimaryHover` on
    // `d2AccentSoft`, which measures 4.22:1 — below AA for an 11px label. The
    // chip stays visually violet (tint, border and dot); only the letters change
    // to `d2Text` (14.73:1).
    SelahTone.brand => SelahToneStyle(
      ink: DesignTokens.d2Text,
      fill: DesignTokens.d2AccentSoft,
      border: brandBorder,
      dot: DesignTokens.d2PrimaryHover,
    ),
    // `d2TextMuted` is AA-large only (3.45:1 on `d2Elevated`), so a neutral
    // chip's LABEL uses `d2TextSecondary` (7.40:1).
    SelahTone.neutral => const SelahToneStyle(
      ink: DesignTokens.d2TextSecondary,
      fill: DesignTokens.d2Elevated,
      border: DesignTokens.d2Border,
    ),
  };
}

/// Whether the operator asked for less motion — the OS setting or the in-app
/// preference, either one (spec §6.7).
///
/// Exposed as its own predicate because not every reduced-motion accommodation
/// is a duration: §4.12 replaces the reconnecting spinner with a *static ring*,
/// which is a different widget rather than a shorter animation. Deriving that
/// from `selahMotion(...) == Duration.zero` would work by accident and read as a
/// trick.
bool selahReduceMotion(BuildContext context) =>
    MediaQuery.maybeOf(context)?.disableAnimations == true ||
    (SettingsScope.maybeOf(context)?.reduceMotion ?? false);

/// Zero-length when the operator asked for less motion (OS setting or the in-app
/// preference), otherwise [full]. Any new animation goes through here.
Duration selahMotion(BuildContext context, Duration full) =>
    selahReduceMotion(context) ? Duration.zero : full;

/// A status chip (spec §2.5 — the "StatusChip" of the component inventory; the
/// name `StatusBadge` is kept because it is the shipped symbol every call site
/// and widget test already reaches for, and the spec explicitly leaves naming to
/// the engineer while pinning the *shape*).
///
/// The text label is REQUIRED and never optional — LIVE/PREVIEW/ON-AIR must
/// never be carried by colour alone (WCAG 1.4.1, spec §6.3). The dot is
/// decoration on top of the word, not a substitute for it.
class StatusBadge extends StatelessWidget {
  final String text;
  final SelahTone tone;

  /// Show the leading dot (the design's "with dot" variant).
  final bool dot;

  /// The role-chip step up: 27 tall, 12/w700/+0.2, 8px dot (*measured*
  /// `364:130`) instead of 23 / 11/w800/+0.6 / 7px.
  final bool large;

  /// Spoken instead of [text] — e.g. "Role: Producer" rather than "PRODUCER".
  final String? semanticLabel;

  const StatusBadge({
    super.key,
    required this.text,
    required this.tone,
    this.dot = false,
    this.large = false,
    this.semanticLabel,
  });

  @override
  Widget build(BuildContext context) {
    final s = SelahToneStyle.of(tone);
    final chip = Container(
      constraints: BoxConstraints(minHeight: large ? 27 : 23),
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: s.fill,
        borderRadius: BorderRadius.circular(SelahRadius.pill),
        border: Border.all(color: s.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (dot) ...[
            Container(
              width: large ? 8 : 7,
              height: large ? 8 : 7,
              decoration: BoxDecoration(color: s.dot, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
          ],
          Text(
            text,
            style: (large ? SelahType.roleChip : SelahType.chip).copyWith(
              color: s.ink,
            ),
          ),
        ],
      ),
    );
    if (semanticLabel == null) return chip;
    return Semantics(
      label: semanticLabel,
      excludeSemantics: true,
      child: chip,
    );
  }
}

/// A plan-item kind badge (spec §3.3): SONG violet · SCRIPTURE gold · SECTION
/// muted · ANNOUNCEMENT info, on an `inset` well with a `d2Border` hairline.
class KindBadge extends StatelessWidget {
  /// The wire kind string (`song`, `scripture`, …); rendered upper-case.
  final String kind;
  const KindBadge({super.key, required this.kind});

  /// Gold means scripture — and only scripture (handoff §2).
  static Color inkFor(String kind) => switch (kind.trim().toLowerCase()) {
    'song' || 'hymn' => DesignTokens.d2PrimaryHover,
    'scripture' || 'reading' => DesignTokens.d2Gold,
    'announcement' || 'notice' => DesignTokens.d2Info,
    _ => DesignTokens.d2TextSecondary,
  };

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
    decoration: BoxDecoration(
      color: DesignTokens.d2Inset,
      borderRadius: BorderRadius.circular(6),
      border: Border.all(color: DesignTokens.d2Border),
    ),
    child: Text(
      kind.toUpperCase(),
      style: SelahType.chip.copyWith(
        fontSize: 10,
        letterSpacing: 0.8,
        color: inkFor(kind),
      ),
    ),
  );
}

/// A section overline (spec §3.10: 11 / w800 / +0.8 in `d2TextSecondary` —
/// A11Y-FIX, the frames use `d2TextMuted` at 3.45–4.08:1), optionally with a
/// trailing count chip or action.
class SectionLabel extends StatelessWidget {
  final String text;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;

  const SectionLabel(
    this.text, {
    super.key,
    this.trailing,
    this.padding = EdgeInsets.zero,
  });

  @override
  Widget build(BuildContext context) => Padding(
    padding: padding,
    child: Row(
      children: [
        Expanded(
          child: Text(
            text,
            style: SelahType.overline.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
        ?trailing,
      ],
    ),
  );
}

/// A surface card/panel (spec §3.4): `surface`, radius 14, 1px border, padding
/// 12. [gradient] replaces the flat fill for the on-air wash.
class SelahCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;
  final Color borderColor;
  final double borderWidth;
  final Gradient? gradient;
  final double radius;

  const SelahCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(SelahSpace.md),
    this.color = DesignTokens.d2Surface,
    this.borderColor = DesignTokens.d2Border,
    this.borderWidth = 1,
    this.gradient,
    this.radius = SelahRadius.card,
  });

  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: gradient == null ? color : null,
      gradient: gradient,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: borderColor, width: borderWidth),
    ),
    child: child,
  );
}

/// Which state a [SelahListRow] is in (spec §3.5).
enum SelahRowState {
  /// Default — `surface` with a hairline.
  normal,

  /// On the audience screen right now.
  live,

  /// Staged in Preview, not on air.
  staged,

  /// Picked/selected — the violet border (e.g. the paired host).
  selected,
}

/// A tappable list row. The four states are colour AND border-weight distinct,
/// but no row relies on colour alone — every caller pairs the tint with a chip
/// or a glyph carrying the same word (spec §6.3).
class SelahListRow extends StatelessWidget {
  final Widget child;
  final SelahRowState state;
  final VoidCallback? onTap;
  final VoidCallback? onDoubleTap;
  final EdgeInsetsGeometry padding;

  /// Announced instead of the row's inner text when set.
  final String? semanticLabel;

  const SelahListRow({
    super.key,
    required this.child,
    this.state = SelahRowState.normal,
    this.onTap,
    this.onDoubleTap,
    this.padding = const EdgeInsets.symmetric(
      horizontal: SelahSpace.md,
      vertical: SelahSpace.sm,
    ),
    this.semanticLabel,
  });

  /// The row's fill for [state] — exposed so tests and callers can assert the
  /// tint without duplicating the table.
  static Color fillFor(SelahRowState state) => switch (state) {
    SelahRowState.normal => DesignTokens.d2Surface,
    SelahRowState.live => DesignTokens.d2LiveSoft,
    SelahRowState.staged => DesignTokens.d2PreviewSoft,
    SelahRowState.selected => DesignTokens.d2Surface,
  };

  static Color borderFor(SelahRowState state) => switch (state) {
    SelahRowState.normal => DesignTokens.d2Border,
    // The live row gets the full ink at 1.5px, not the soft border: it is the
    // one row state that says "this is on the audience screen right now".
    SelahRowState.live => DesignTokens.d2Live,
    SelahRowState.staged => DesignTokens.d2PreviewBorder,
    SelahRowState.selected => DesignTokens.d2PrimaryHover,
  };

  static double borderWidthFor(SelahRowState state) => switch (state) {
    SelahRowState.live => 1.5,
    SelahRowState.selected => 2,
    _ => 1,
  };

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(SelahRadius.row);
    final row = Material(
      color: fillFor(state),
      borderRadius: radius,
      child: InkWell(
        borderRadius: radius,
        onTap: onTap,
        onDoubleTap: onDoubleTap,
        child: Container(
          constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
          padding: padding,
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(
              color: borderFor(state),
              width: borderWidthFor(state),
            ),
          ),
          child: child,
        ),
      ),
    );
    if (semanticLabel == null) return row;
    return Semantics(
      button: onTap != null,
      label: semanticLabel,
      child: row,
    );
  }
}

/// Button prominence (spec §3.1).
enum SelahButtonVariant {
  /// Flat violet + white. Deliberately NOT the gradient the handoff sketches:
  /// white on the gradient's top stop (`d2PrimaryHover`) is 3.78:1 — AA-large
  /// only — while white on flat `d2Primary` is 4.72:1. The mobile frames draw
  /// the compact Connect button flat too (`342:158`), so flat is inside the
  /// design's own vocabulary (spec §3.1 A11Y-FIX / Q2).
  primary,

  /// `elevated` + `d2Border` — the workhorse (Prev/Next, Pause, Reject).
  secondary,

  /// No fill, no border (dialog Cancel).
  ghost,

  /// Audience-affecting / destructive: `live-soft` fill, live border, live ink.
  danger,

  /// Destructive but not the primary destructive control on its row: a neutral
  /// `elevated` fill keeping the red ink and border, so two red blocks never
  /// compete side by side (spec §4.2 — Clear All).
  dangerQuiet,

  /// Destructive on a sheet, where a tinted block would read as an alert:
  /// transparent fill, live border, live ink (spec §4.8 — Disconnect).
  dangerOutline,

  /// The armed/engaged alarm state — solid `d2Live` with `d2LiveSoft` ink.
  /// White on `d2Live` is 3.27:1 and fails; this pairing is 5.31:1 (spec §3.1
  /// "danger-armed", §6.1).
  alarm,

  /// GO LIVE and Approve — the green gradient, with dark ink. White on the
  /// gradient's light stop is 1.93:1 (spec §6.1).
  success,
}

/// A button. Disabled state is uniform across the app: dimmed to 40%,
/// non-tappable, and announced WITH ITS REASON rather than silently inert — a
/// greyed control that will not say why is the same dead end as one that does
/// nothing.
class SelahButton extends StatelessWidget {
  final String label;
  final SelahButtonVariant variant;

  /// Null = not tappable. Kept separate from a `disabled` flag so a null callback
  /// can never render as an enabled-looking control.
  final VoidCallback? onPressed;

  /// Spoken instead of [label] (so "◀ Prev" announces as "Previous item").
  final String? semanticLabel;

  /// Appended to the announcement while disabled, e.g. "unavailable while
  /// reconnecting". Null → the button is simply not offered as enabled.
  final String? disabledReason;

  /// Announced as a pressed/unpressed toggle (Blackout's engaged state — the
  /// `aria-pressed` equivalent, spec §6.3).
  final bool? toggled;

  /// A leading glyph drawn with the label (■ ✕). Text rather than an icon only
  /// where the exact glyph is part of the label contract; arrows use [icon]
  /// because U+25B6/U+25C0 pick up an emoji presentation on iOS that ignores the
  /// ink colour.
  final String? glyph;

  final IconData? icon;

  /// Trailing icon (the frames put the chevron after the word on "Next ▶").
  final IconData? trailingIcon;

  /// Fire the haptic on press. Spec §6.7: haptics fire on audience-affecting
  /// COMMITS (GO LIVE, emergency confirm, Approve) and never on navigation, so
  /// this is opt-in rather than automatic.
  final bool haptic;

  final double height;
  final TextStyle? textStyle;

  bool get _disabled => onPressed == null;

  const SelahButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = SelahButtonVariant.secondary,
    this.semanticLabel,
    this.disabledReason,
    this.toggled,
    this.glyph,
    this.icon,
    this.trailingIcon,
    this.haptic = false,
    this.height = kSelahMinTouchTarget,
    this.textStyle,
  });

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(SelahRadius.row);
    final (Color? fill, Gradient? gradient, Color border, Color ink) =
        switch (variant) {
          SelahButtonVariant.primary => (
            DesignTokens.d2Primary,
            null,
            DesignTokens.d2Primary,
            Colors.white,
          ),
          SelahButtonVariant.secondary => (
            DesignTokens.d2Elevated,
            null,
            DesignTokens.d2Border,
            DesignTokens.d2Text,
          ),
          SelahButtonVariant.ghost => (
            Colors.transparent,
            null,
            Colors.transparent,
            DesignTokens.d2TextSecondary,
          ),
          SelahButtonVariant.danger => (
            DesignTokens.d2LiveSoft,
            null,
            DesignTokens.d2LiveBorder,
            DesignTokens.d2Live,
          ),
          SelahButtonVariant.dangerQuiet => (
            DesignTokens.d2Elevated,
            null,
            DesignTokens.d2LiveBorder,
            DesignTokens.d2Live,
          ),
          SelahButtonVariant.dangerOutline => (
            Colors.transparent,
            null,
            DesignTokens.d2Live,
            DesignTokens.d2Live,
          ),
          SelahButtonVariant.alarm => (
            DesignTokens.d2Live,
            null,
            DesignTokens.d2Live,
            SelahGradient.onLiveInk,
          ),
          SelahButtonVariant.success => (
            null,
            SelahGradient.goLive,
            Colors.transparent,
            SelahGradient.goLiveInk,
          ),
        };

    final style = (textStyle ?? SelahType.label).copyWith(color: ink);
    final spoken = semanticLabel ?? label;

    return Semantics(
      button: true,
      enabled: !_disabled,
      toggled: toggled,
      label: (_disabled && disabledReason != null)
          ? '$spoken, $disabledReason'
          : spoken,
      excludeSemantics: true,
      child: Opacity(
        opacity: _disabled ? 0.4 : 1,
        child: Material(
          color: fill,
          borderRadius: radius,
          child: InkWell(
            borderRadius: radius,
            onTap: onPressed == null
                ? null
                : () {
                    if (haptic) SettingsScope.maybeOf(context)?.haptic();
                    onPressed!();
                  },
            child: Container(
              height: height,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: SelahSpace.md),
              decoration: BoxDecoration(
                gradient: gradient,
                borderRadius: radius,
                border: Border.all(color: border),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icon != null) Icon(icon, size: 18, color: ink),
                  // An empty label is an icon-only button (the ◀ ▶ transport):
                  // it still announces via [semanticLabel], so it is named for
                  // assistive tech even though it draws no word.
                  if (label.isNotEmpty) ...[
                    if (icon != null) const SizedBox(width: SelahSpace.xs),
                    Flexible(
                      child: Text(
                        glyph == null ? label : '$glyph $label',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.center,
                        style: style,
                      ),
                    ),
                  ],
                  if (trailingIcon != null) ...[
                    const SizedBox(width: SelahSpace.xs),
                    Icon(trailingIcon, size: 18, color: ink),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A text field on the Design 2.0 surface (spec §3.6). Thin on purpose — the
/// colours live in `SelahTheme.inputDecorationTheme`, so this only carries the
/// per-field content.
class SelahInput extends StatelessWidget {
  final TextEditingController controller;
  final String? hint;
  final String? label;
  final Widget? prefix;
  final Widget? suffix;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final TextCapitalization textCapitalization;
  final ValueChanged<String>? onSubmitted;
  final bool enabled;

  /// `d2Inset` instead of `d2Surface` — for a field that sits INSIDE a card,
  /// where surface-on-surface would vanish (spec §3.6).
  final bool inset;

  const SelahInput({
    super.key,
    required this.controller,
    this.hint,
    this.label,
    this.prefix,
    this.suffix,
    this.keyboardType,
    this.textInputAction,
    this.textCapitalization = TextCapitalization.none,
    this.onSubmitted,
    this.enabled = true,
    this.inset = false,
  });

  @override
  Widget build(BuildContext context) => TextField(
    controller: controller,
    enabled: enabled,
    keyboardType: keyboardType,
    textInputAction: textInputAction,
    textCapitalization: textCapitalization,
    onSubmitted: onSubmitted,
    style: SelahType.rowTitle.copyWith(
      fontWeight: FontWeight.w400,
      color: DesignTokens.d2Text,
    ),
    cursorColor: DesignTokens.d2PrimaryHover,
    decoration: InputDecoration(
      isDense: true,
      hintText: hint,
      labelText: label,
      prefixIcon: prefix,
      suffixIcon: suffix,
      fillColor: inset ? DesignTokens.d2Inset : DesignTokens.d2Surface,
      // ≥48dp even when the field is dense (spec §6.6).
      constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
    ),
  );
}

/// An on/off toggle (spec §3.7). Wraps Material's [Switch] rather than
/// hand-drawing the 42×24 pill from the frames: the platform control brings the
/// drag gesture and the screen-reader semantics with it, and the spec's own
/// §3.7 note is that the whole 50-dp ROW is the tap target — which this
/// provides. Colour comes from `SelahTheme.switchTheme` (violet on, `elevated`
/// off).
class SelahToggle extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  const SelahToggle({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) => InkWell(
    // "The whole row toggles" (spec §4.8).
    onTap: () => onChanged(!value),
    child: Container(
      constraints: const BoxConstraints(minHeight: 50),
      padding: const EdgeInsets.symmetric(horizontal: SelahSpace.lg),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: SelahType.rowTitle.copyWith(
                fontWeight: FontWeight.w400,
                color: DesignTokens.d2Text,
              ),
            ),
          ),
          // `excludeSemantics` on the row would swallow the switch's own state,
          // so the Switch keeps its semantics and the row is only a hit target.
          Switch(value: value, onChanged: onChanged),
        ],
      ),
    ),
  );
}

/// One option in a [SelahSegmentedControl].
@immutable
class SelahSegment<T> {
  final T value;
  final String label;
  const SelahSegment({required this.value, required this.label});
}

/// A 2–4 option segmented control (spec §3.8): `inset` track + `d2Border`, 3px
/// inset, track radius 9 / segment 7, active segment flat `d2Primary`. Honours
/// reduce-motion via [selahMotion].
///
/// Built as a primitive now because it is part of the component inventory; its
/// first placement (the Detected-Scriptures Live/History tabs and the "More"
/// surfaces) belongs to the batch that builds those screens. It is deliberately
/// not dropped onto a Batch-A screen just to have a consumer — a control that
/// switches nothing would be exactly the fake affordance the brief forbids.
class SelahSegmentedControl<T> extends StatelessWidget {
  final List<SelahSegment<T>> segments;
  final T value;
  final ValueChanged<T> onChanged;

  const SelahSegmentedControl({
    super.key,
    required this.segments,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final duration = selahMotion(context, const Duration(milliseconds: 140));
    return Container(
      height: kSelahMinTouchTarget,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: DesignTokens.d2Inset,
        borderRadius: BorderRadius.circular(9),
        border: Border.all(color: DesignTokens.d2Border),
      ),
      child: Row(
        children: [
          for (final seg in segments)
            Expanded(
              child: Semantics(
                button: true,
                selected: seg.value == value,
                label: seg.label,
                excludeSemantics: true,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onChanged(seg.value),
                  child: AnimatedContainer(
                    duration: duration,
                    height: 42,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: seg.value == value
                          ? DesignTokens.d2Primary
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Text(
                      seg.label,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: seg.value == value
                            ? FontWeight.w700
                            : FontWeight.w600,
                        color: seg.value == value
                            ? Colors.white
                            : DesignTokens.d2TextSecondary,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
