/// Shared mobile Producer widgets (revamp 86ajpx7bd): the design-system pieces
/// every tab reuses — status/output cards, badges, the persistent emergency
/// strip. Colours come from [DesignTokens] (bound to the same tokens the
/// desktop console and the Figma design use). Widgets only.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/settings.dart';

/// A LIVE / PREVIEW badge — colour + text label (never colour alone, WCAG 1.4.1).
class StatusBadge extends StatelessWidget {
  final String text;
  final Color color;
  const StatusBadge({super.key, required this.text, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration:
            BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
        child: Text(text,
            style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.6,
                color: Colors.white)),
      );
}

/// A labeled output card (PREVIEW · STAGED / ● LIVE · ON AIR) with its black
/// surface. `blackout` drapes the live card with an explicit text overlay.
class OutputCard extends StatelessWidget {
  final String header;
  final Color headerColor;
  final Color borderColor;
  final String? title;
  final String? caption;
  final String idle;
  final bool blackout;

  const OutputCard({
    super.key,
    required this.header,
    required this.headerColor,
    required this.borderColor,
    required this.title,
    required this.caption,
    required this.idle,
    this.blackout = false,
  });

  @override
  Widget build(BuildContext context) {
    final hasContent = title != null;
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: borderColor),
        borderRadius: BorderRadius.circular(12),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: headerColor,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Text(header,
                style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.7,
                    color: Colors.white)),
          ),
          Container(
            color: DesignTokens.outputBlack,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 22),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (blackout)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          border: Border.all(color: DesignTokens.liveInk),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('BLACKOUT — OUTPUT DARK',
                            style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.8,
                                color: Colors.white)),
                      ),
                    ),
                  Opacity(
                    opacity: blackout ? 0.3 : 1,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(hasContent ? title! : idle,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                                fontSize: hasContent ? 18 : 15,
                                fontWeight: hasContent
                                    ? FontWeight.w600
                                    : FontWeight.w500,
                                color: hasContent
                                    ? DesignTokens.textPrimary
                                    : DesignTokens.textMuted)),
                        if (caption != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(caption!,
                                style: const TextStyle(
                                    fontSize: 11,
                                    color: DesignTokens.textMuted)),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Which destructive emergency action is currently armed, if any.
enum _Armed { blackout, clear }

/// A destructive action the operator has armed: which control it was, and the
/// exact command their confirming tap will send.
///
/// Carrying the *command*, not just the control, is what makes arm-then-confirm
/// honest for an ABSOLUTE command. `blackout` takes a direction (`on: true` /
/// `on: false`) that used to be computed from `live.blackout` at BUILD time
/// while the arm-or-confirm decision was read at TAP time. The 1s poll rebuilds
/// this strip between the two taps, so a desktop operator blacking out in that
/// gap flipped the pending command: the confirming tap sent `on: false` and
/// UN-blacked-out the audience — the precise opposite of the armed intent, from
/// a gesture whose whole purpose is to confirm that intent.
///
/// Binding the command to the intent at the moment it is formed removes the
/// class of bug instead of narrowing its window.
class _Arm {
  final _Armed which;
  final Map<String, dynamic> cmd;
  const _Arm(this.which, this.cmd);
}

/// The always-on emergency strip (UX-CANONICAL §3): Blackout + Clear All,
/// present above the tab bar on every screen. Never scrolls away.
///
/// Both audience-facing actions are **arm-then-confirm**: the first tap morphs
/// the button in place, the second commits (COMPONENT-SPECS §12, "destructive/
/// audience actions get a brief press-and-hold or confirm on mobile — touch is
/// slip-prone"). The confirm is inline rather than a dialog because an emergency
/// control must never sit behind a modal (§1.2 invariant 2), and it disarms on
/// its own so an armed control can never lie in wait for a later stray tap.
///
/// Two deliberate asymmetries:
///  - **Un-blackout is one tap.** It is the recovery direction; putting a
///    confirmation between the operator and restoring the audience screen would
///    invert the safety this whole mechanism exists for.
///  - **Everything is disabled while [LiveController.syncing]** — during a drop,
///    and after it until live state is re-read (FR-097).
class EmergencyStrip extends StatefulWidget {
  final LiveController live;

  /// How long an armed action stays armed before reverting on its own.
  /// Injectable so the timing is deterministic under test (COMPONENT-SPECS §1.2
  /// specifies a ~3s inline confirm window).
  final Duration confirmWindow;

  const EmergencyStrip({
    super.key,
    required this.live,
    this.confirmWindow = const Duration(seconds: 3),
  });

  @override
  State<EmergencyStrip> createState() => _EmergencyStripState();
}

class _EmergencyStripState extends State<EmergencyStrip> {
  _Arm? _armed;
  Timer? _disarm;

  @override
  void dispose() {
    _disarm?.cancel();
    super.dispose();
  }

  void _arm(_Armed which, Map<String, dynamic> cmd) {
    _disarm?.cancel();
    setState(() => _armed = _Arm(which, cmd));
    _disarm = Timer(widget.confirmWindow, () {
      if (mounted) setState(() => _armed = null);
    });
  }

  void _fire(Map<String, dynamic> cmd) {
    _disarm?.cancel();
    setState(() => _armed = null);
    widget.live.act(cmd);
  }

  /// One tap arms, the next fires **the command that was armed**. [intent] is
  /// evaluated at tap time — it is what this gesture means to the operator
  /// looking at the button right now. [immediate] skips the arming step for
  /// non-destructive directions (un-blackout).
  VoidCallback? _guarded(_Armed which, Map<String, dynamic> Function() intent,
      {bool immediate = false}) {
    if (widget.live.syncing) return null; // disabled: state is unknown
    return () {
      SettingsScope.maybeOf(context)?.haptic();
      final armed = _armed;
      // An existing arm wins over [immediate]. If the host moved while this
      // control sat armed, the intent the operator actually expressed is still
      // the one to honour — never the one the new state happens to offer.
      if (armed != null && armed.which == which) {
        _fire(armed.cmd);
      } else if (immediate) {
        _fire(intent());
      } else {
        _arm(which, intent());
      }
    };
  }

  @override
  Widget build(BuildContext context) {
    final live = widget.live;
    final blackout = live.blackout;
    // Each emergency action is role-gated: blackout → Blackout cap,
    // Clear All → ClearLive cap. The call site (controller_view) omits the whole
    // strip when a role holds neither, so this never renders empty.
    final canBlackout = live.can(Capability.blackout);
    final canClear = live.can(Capability.clearLive);
    final armedBlackout = _armed?.which == _Armed.blackout;
    final armedClear = _armed?.which == _Armed.clear;
    final disabled = live.syncing;

    return Container(
      decoration: const BoxDecoration(
        color: DesignTokens.bgPanel,
        border: Border(
          top: BorderSide(color: DesignTokens.border),
          bottom: BorderSide(color: DesignTokens.border),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Row(
        children: [
          if (canBlackout)
            Expanded(
              child: _EmgButton(
                // An armed control announces what the NEXT tap will do, which
                // outranks what the poll last said the host is. Letting
                // `blackout` win here put the word "UN-BLACKOUT" under a thumb
                // that was about to confirm a blackout.
                label: armedBlackout
                    ? '■ CONFIRM BLACKOUT'
                    : blackout
                        ? '■ UN-BLACKOUT'
                        : '■ BLACKOUT',
                semanticLabel: armedBlackout
                    ? 'Confirm blackout'
                    : blackout
                        ? 'Un-blackout'
                        : 'Blackout',
                fill: armedBlackout
                    ? DesignTokens.liveInk
                    : blackout
                        ? DesignTokens.liveFill
                        : DesignTokens.bgBase,
                border: (blackout || armedBlackout)
                    ? DesignTokens.liveInk
                    : DesignTokens.border,
                textColor: (blackout || armedBlackout)
                    ? Colors.white
                    : DesignTokens.textPrimary,
                disabled: disabled,
                // Un-blackout restores the audience screen — never gate recovery.
                // The direction is absolute and decided from what the operator
                // is looking at as they tap, not rebuilt under their gesture.
                onTap: _guarded(_Armed.blackout, () => cmdBlackout(!blackout),
                    immediate: blackout),
              ),
            ),
          if (canBlackout && canClear) const SizedBox(width: 8),
          if (canClear)
            Expanded(
              child: _EmgButton(
                label: armedClear ? '✕ CONFIRM CLEAR' : '✕ CLEAR ALL',
                semanticLabel:
                    armedClear ? 'Confirm clear all' : 'Clear all',
                fill: armedClear ? DesignTokens.liveInk : DesignTokens.bgBase,
                border: DesignTokens.liveInk,
                textColor:
                    armedClear ? Colors.white : DesignTokens.liveInk,
                disabled: disabled,
                onTap: _guarded(_Armed.clear, cmdClear),
              ),
            ),
        ],
      ),
    );
  }
}

class _EmgButton extends StatelessWidget {
  final String label;
  final String semanticLabel;
  final Color fill;
  final Color border;
  final Color textColor;

  /// Null = not tappable. Kept separate from [disabled] so a null callback can
  /// never render as an enabled-looking control.
  final VoidCallback? onTap;

  /// Greyed with the reason announced, rather than hidden: the control is not
  /// forbidden (that is role gating, which hides), just momentarily
  /// untrustworthy (COMPONENT-SPECS §12 `disabled-while-offline`).
  final bool disabled;

  const _EmgButton({
    required this.label,
    required this.semanticLabel,
    required this.fill,
    required this.border,
    required this.textColor,
    required this.onTap,
    this.disabled = false,
  });

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        enabled: !disabled,
        // Announce the plain word, not the "■"/"✕" glyph baked into the label.
        label: disabled ? '$semanticLabel, unavailable while reconnecting'
            : semanticLabel,
        excludeSemantics: true,
        child: Opacity(
          opacity: disabled ? 0.4 : 1,
          child: Material(
            color: fill,
            borderRadius: BorderRadius.circular(8),
            child: InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: onTap,
              child: Container(
                height: 46,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  border: Border.all(color: border),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(label,
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.3,
                        color: textColor)),
              ),
            ),
          ),
        ),
      );
}

/// Format a whole-seconds duration as `M:SS`.
String fmtClock(int secs) => '${secs ~/ 60}:${(secs % 60).toString().padLeft(2, '0')}';
