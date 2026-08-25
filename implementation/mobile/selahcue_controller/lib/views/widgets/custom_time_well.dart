/// The HH:MM:SS custom-time well (MOBILE-2.0-SPEC §4.6, Figma `367:126`).
///
/// Replaces the minutes-only field the app shipped with. The wire already takes
/// seconds (`cmdStartTimer(int seconds)`), so the minutes-only field was never a
/// protocol limit — it simply could not express an hour, which a sermon timer
/// obviously needs (DESIGN-2.0-HANDOFF §5.1).
///
/// Three two-digit fields separated by `:`, unit-labelled beneath, adding up to
/// ONE duration: "the whole well is one form". The value lives in a
/// [CustomTimeController] rather than in this widget's state so the Start button
/// — which the frame draws *outside* the well — can read it, enable on it, and
/// clear it after a successful start without reaching into a child's state.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../models/design_tokens.dart';
import '../../models/selah_theme.dart';

/// The largest value each pair accepts.
///
/// Minutes and seconds are sexagesimal, so 60 in either is a typo rather than an
/// intent — clamping is what a segmented time entry is for. Hours cap at 23
/// (*default* — the frames give two digits and no bound): a countdown longer
/// than a day is not a service timer, and leaving it at 99 would let a fat-finger
/// start an 80-hour clock that only `Stop` can end.
const int maxCustomHours = 23;
const int _maxSexagesimal = 59;

/// The three fields of the custom-time well, as one duration.
///
/// A [ChangeNotifier] so the Start button can enable and disable with the typed
/// value without the Timer tab rebuilding its whole list on every keystroke.
class CustomTimeController extends ChangeNotifier {
  final TextEditingController hours = TextEditingController();
  final TextEditingController minutes = TextEditingController();
  final TextEditingController seconds = TextEditingController();

  CustomTimeController() {
    for (final field in _fields) {
      field.addListener(notifyListeners);
    }
  }

  List<TextEditingController> get _fields => [hours, minutes, seconds];

  static int _read(TextEditingController c) => int.tryParse(c.text.trim()) ?? 0;

  /// The whole well as seconds — the unit `cmdStartTimer` already speaks.
  int get totalSeconds =>
      _read(hours) * 3600 + _read(minutes) * 60 + _read(seconds);

  /// Nothing worth starting has been typed.
  bool get isEmpty => totalSeconds == 0;

  void clear() {
    for (final field in _fields) {
      field.clear();
    }
  }

  @override
  void dispose() {
    // Detach before disposing: a TextEditingController that outlives this object
    // would otherwise call notifyListeners on a disposed ChangeNotifier.
    for (final field in _fields) {
      field.removeListener(notifyListeners);
      field.dispose();
    }
    super.dispose();
  }
}

/// Rejects an edit that would put the field above [max]. Applied on top of
/// `LengthLimitingTextInputFormatter(2)`, so "6" then "0" in a minutes field
/// simply leaves "6" rather than silently becoming "00" or "59" — a formatter
/// that rewrites what was typed is worse than one that declines it.
class _MaxValueFormatter extends TextInputFormatter {
  final int max;
  const _MaxValueFormatter(this.max);

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    if (newValue.text.isEmpty) return newValue;
    final parsed = int.tryParse(newValue.text);
    if (parsed == null || parsed > max) return oldValue;
    return newValue;
  }
}

/// The well itself: `d2Inset` fill, `d2Border`, r12 (*measured* 257 × 67).
class CustomTimeWell extends StatelessWidget {
  final CustomTimeController controller;

  /// False while the link is unsynced — the well greys out with everything else.
  final bool enabled;

  /// Fired by the keyboard's done key on any pair, so the whole well behaves as
  /// one submittable form.
  final VoidCallback? onSubmitted;

  const CustomTimeWell({
    super.key,
    required this.controller,
    this.enabled = true,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: enabled ? 1 : 0.4,
    child: Container(
      // *measured* 67 tall — as a MINIMUM, not a fixed box. A fixed height
      // clips the digits at a large text scale, and spec §6.7 requires scaling
      // to 3.0 without clipping. The well grows instead.
      constraints: const BoxConstraints(minHeight: 67),
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: DesignTokens.d2Inset,
        borderRadius: BorderRadius.circular(SelahRadius.row),
        border: Border.all(color: DesignTokens.d2Border),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _DigitPair(
            field: controller.hours,
            unit: 'HOURS',
            semanticLabel: 'Hours',
            max: maxCustomHours,
            enabled: enabled,
            onSubmitted: onSubmitted,
          ),
          const _Separator(),
          _DigitPair(
            field: controller.minutes,
            unit: 'MIN',
            semanticLabel: 'Minutes',
            max: _maxSexagesimal,
            enabled: enabled,
            onSubmitted: onSubmitted,
          ),
          const _Separator(),
          _DigitPair(
            field: controller.seconds,
            unit: 'SEC',
            semanticLabel: 'Seconds',
            max: _maxSexagesimal,
            enabled: enabled,
            onSubmitted: onSubmitted,
          ),
        ],
      ),
    ),
  );
}

/// The `:` between pairs — 28 px `d2TextSecondary` (*measured*).
///
/// Built with the SAME column shape as a [_DigitPair] (digits row, 2 gap, unit
/// row) carrying an empty unit label, so the colons stay on the digits' baseline
/// at every text scale. Padding tuned to one text size would drift the moment
/// the operator scales up.
class _Separator extends StatelessWidget {
  const _Separator();

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          ':',
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: DesignTokens.d2TextSecondary,
            height: 1.1,
          ),
        ),
        const SizedBox(height: 2),
        Text('', style: _unitStyle),
      ],
    ),
  );
}

/// The unit caption style — 10 / w700 / +0.8. **A11Y-FIX** (spec §6.2 item 3):
/// `d2TextSecondary`, never the frame's `d2TextMuted`, which measures 3.96:1 on
/// `d2Inset`.
final TextStyle _unitStyle = SelahType.overline.copyWith(
  fontSize: 10,
  fontWeight: FontWeight.w700,
  color: DesignTokens.d2TextSecondary,
);

/// One two-digit field with its unit label.
///
/// The 48-wide box is the *touch target*, not decoration: a bare dense TextField
/// is about 34 px of hit area, and the frame's own digits are narrower still
/// (spec §6.6 raises every sub-48 element). The tap handler is `translucent` so
/// a tap on the "HOURS" caption — visually part of the control — focuses the
/// field instead of falling through to the well.
class _DigitPair extends StatefulWidget {
  final TextEditingController field;
  final String unit;
  final String semanticLabel;
  final int max;
  final bool enabled;
  final VoidCallback? onSubmitted;

  const _DigitPair({
    required this.field,
    required this.unit,
    required this.semanticLabel,
    required this.max,
    required this.enabled,
    this.onSubmitted,
  });

  @override
  State<_DigitPair> createState() => _DigitPairState();
}

class _DigitPairState extends State<_DigitPair> {
  final _focus = FocusNode();

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
    behavior: HitTestBehavior.translucent,
    onTap: widget.enabled ? _focus.requestFocus : null,
    child: SizedBox(
      width: kSelahMinTouchTarget,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Semantics(
            label: widget.semanticLabel,
            child: TextField(
              controller: widget.field,
              focusNode: _focus,
              enabled: widget.enabled,
              keyboardType: TextInputType.number,
              textAlign: TextAlign.center,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => widget.onSubmitted?.call(),
              inputFormatters: [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(2),
                _MaxValueFormatter(widget.max),
              ],
              // 28 / w800 / tabular (spec §3.10) — tabular so the digits do not
              // shuffle sideways as they are typed.
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w800,
                height: 1.1,
                color: DesignTokens.d2Text,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
              cursorColor: DesignTokens.d2PrimaryHover,
              decoration: const InputDecoration(
                // The well is the field's frame; the theme's own filled+bordered
                // input decoration would draw a second box inside it.
                filled: false,
                isDense: true,
                contentPadding: EdgeInsets.zero,
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                disabledBorder: InputBorder.none,
                hintText: '00',
                hintStyle: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  height: 1.1,
                  color: DesignTokens.d2TextSecondary,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
                counterText: '',
                constraints: BoxConstraints(),
              ),
            ),
          ),
          const SizedBox(height: 2),
          // Shrink-to-fit rather than clip: at a 3.0 text scale "HOURS" is far
          // wider than the 48-dp pair. The caption is decoration — the field's
          // accessible name is on the field itself — so scaling it down loses
          // nothing a screen-reader user needs.
          ExcludeSemantics(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(widget.unit, style: _unitStyle),
            ),
          ),
        ],
      ),
    ),
  );
}
