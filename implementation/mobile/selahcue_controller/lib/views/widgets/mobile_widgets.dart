/// Session-aware shared widgets: the connection notice, the Preview/Live
/// monitor cards, and the persistent emergency strip. These know about
/// [LiveController]; the colour/typography/shape vocabulary they are built from
/// lives in `primitives.dart` (re-exported here so every existing
/// `import 'widgets/mobile_widgets.dart'` keeps reaching the same names).
///
/// Design 2.0: `docs/design/MOBILE-2.0-SPEC.md` §3.9 (monitor), §4.2 (shell).
/// Colour comes from `DesignTokens.d2*` through [SelahTheme] and the [SelahTone]
/// table — never picked per widget.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import 'enforcement.dart';
import 'primitives.dart';

export 'enforcement.dart';
export 'primitives.dart';

/// The connection notice: the action-rejected toast (§4.12), "your taps won't be
/// sent" (warning, while the link is down or live state is still being re-read),
/// or a dismissible command error (live/red). Renders nothing when the link is
/// healthy and there is no error.
///
/// One slot, three tenants, in that priority order. Spec §4.12 puts the rejected
/// toast here rather than beside the reconnecting bar because the two are the
/// same event seen twice — a rejection is *always* followed by a reconnect — and
/// the toast carries its own reconnecting row, so nothing is lost by it winning.
///
/// Shared rather than inlined because a pushed full-screen route COVERS
/// `ControllerView.body` and therefore covers its copy of this banner. Any
/// screen the operator can sit on must carry its own, and the two must say the
/// same thing — so there is exactly one implementation (DETECTIONS-VIEW-spec
/// §7.3 "identical copy and behaviour").
///
/// A11Y-FIX (spec §4.2): both states used to be white on a solid fill — white on
/// `d2Warn` is 2.04:1 and on `d2Live` 3.27:1. The soft-tint form measures 7.56
/// and 5.31.
class ConnectionBanner extends StatelessWidget {
  final LiveController live;
  const ConnectionBanner({super.key, required this.live});

  @override
  Widget build(BuildContext context) {
    // A command the operator actually sent was lost with the link. That is
    // strictly more information than "reconnecting", and it is about something
    // they did — so it outranks the ambient status.
    if (live.rejected) {
      return ActionRejectedToast(host: live.stored.host);
    }
    // Two distinct truths, both of which mean "your taps won't be sent": the
    // link is down, or it is back but this device has not yet re-read the host.
    // The second is the one that used to leave controls live against a stale
    // view (FR-097).
    if (live.syncing) {
      return _Bar(
        tone: SelahTone.warn,
        child: Text(
          live.reconnecting
              ? 'Reconnecting to the host… your taps won’t be sent'
              : 'Syncing live state…',
          textAlign: TextAlign.center,
          style: SelahType.caption.copyWith(
            fontWeight: FontWeight.w600,
            color: SelahToneStyle.of(SelahTone.warn).ink,
          ),
        ),
      );
    }
    // A command any control on screen sent is still on the wire. Every gated
    // control already greys out (`disabledReason`), but that reason only ever
    // reaches the `Semantics` label — a sighted operator watching the screen
    // rather than listening to it sees nothing else change, on EVERY screen
    // this banner sits above, including the one where that matters most: the
    // emergency strip. Without this branch the banner fell through to
    // [SizedBox.shrink] while busy, which is exactly what let an armed-but-
    // inert BLACKOUT confirm go unexplained (17tnw2ay2pq review, Sana).
    if (live.busy) {
      return _Bar(
        tone: SelahTone.warn,
        child: Text(
          'Sending… your taps aren’t being sent yet',
          textAlign: TextAlign.center,
          style: SelahType.caption.copyWith(
            fontWeight: FontWeight.w600,
            color: SelahToneStyle.of(SelahTone.warn).ink,
          ),
        ),
      );
    }
    // A role refusal that raised the sheet is already being explained there, in
    // full, with a way out. Repeating it as a red strip would make the operator
    // dismiss one refusal twice and read it once — so the richer surface owns
    // it. (`dismissBlocked` clears the notice as well, so closing the sheet does
    // not hand the banner back.)
    final error = live.blocked != null ? null : live.error;
    if (error == null) return const SizedBox.shrink();
    final tone = SelahToneStyle.of(SelahTone.live);
    return _Bar(
      tone: SelahTone.live,
      onTap: live.dismissError,
      child: Row(
        children: [
          Expanded(
            child: Text(
              error,
              style: SelahType.caption.copyWith(color: tone.ink),
            ),
          ),
          Text(
            'Dismiss',
            style: SelahType.caption.copyWith(
              fontWeight: FontWeight.w700,
              color: tone.ink,
            ),
          ),
        ],
      ),
    );
  }
}

/// A full-width tinted notice bar: `*-soft` fill with a `*-border` hairline
/// along the bottom, carrying `*-ink` text.
class _Bar extends StatelessWidget {
  final SelahTone tone;
  final Widget child;
  final VoidCallback? onTap;
  const _Bar({required this.tone, required this.child, this.onTap});

  @override
  Widget build(BuildContext context) {
    final s = SelahToneStyle.of(tone);
    final body = Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: SelahSpace.md,
        vertical: SelahSpace.xs,
      ),
      decoration: BoxDecoration(
        color: s.fill,
        border: Border(bottom: BorderSide(color: s.border)),
      ),
      child: child,
    );
    if (onTap == null) return body;
    return Material(
      color: Colors.transparent,
      child: InkWell(onTap: onTap, child: body),
    );
  }
}

/// A Preview or Live monitor card (spec §3.9).
///
/// The status chip sits ABOVE the card, and the card body is the violet on-air
/// wash standing in for rendered slide content, framed by a 2px status border.
/// A scripture reference is rendered in GOLD, which on this surface means
/// scripture and nothing else (handoff §2).
///
/// Departure from §3.9, forced by the wire model: the spec puts the reference in
/// a gold overline and the verse text in the body. `OperatorStateView` carries
/// only ONE content string per slot (`liveScripture` / the plan item's title) —
/// there is no verse text over the wire — so the reference is promoted into the
/// body and the *context* line ("scripture · main output") becomes the overline.
/// The gold still marks exactly the reference, which is what §2.4 is protecting.
///
/// `blackout` replaces the wash with real black and says so in words — an
/// operator glancing at a dark card must be able to tell "nothing is staged"
/// from "the audience screen is off".
class OutputCard extends StatelessWidget {
  /// The chip above the card, e.g. `PREVIEW` / `LIVE`.
  final String header;

  /// live → on air; preview → staged.
  final SelahTone tone;

  final String? title;

  /// The context line, rendered as the in-card overline.
  final String? caption;

  /// Shown in place of [title] when there is no content.
  final String idle;

  /// [title] is a scripture reference, so it takes the gold treatment.
  final bool scripture;

  final bool blackout;

  const OutputCard({
    super.key,
    required this.header,
    required this.tone,
    required this.title,
    required this.caption,
    required this.idle,
    this.scripture = false,
    this.blackout = false,
  });

  @override
  Widget build(BuildContext context) {
    final s = SelahToneStyle.of(tone);
    final hasContent = title != null;
    final live = tone == SelahTone.live;
    return Semantics(
      container: true,
      label: hasContent
          ? '${live ? 'Live' : 'Preview'}: $title'
          : (live ? 'Live output idle' : 'Preview empty'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: StatusBadge(text: header, tone: tone, dot: true),
          ),
          const SizedBox(height: 6),
          SelahCard(
            // 2px of the full status ink: the frame is the card's whole job, and
            // a soft hairline reads as decoration next to a content border.
            borderColor: s.ink,
            borderWidth: 2,
            radius: SelahRadius.row,
            // Idle carries no wash — a violet field with nothing on it reads as
            // content that failed to load rather than an empty slot (spec §3.9).
            color: blackout
                ? DesignTokens.outputBlack
                : DesignTokens.d2Surface,
            gradient: (blackout || !hasContent)
                ? null
                : SelahGradient.onAirWash,
            padding: const EdgeInsets.all(SelahSpace.md),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (blackout)
                  Padding(
                    padding: const EdgeInsets.only(bottom: SelahSpace.sm),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: SelahSpace.xs,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        border: Border.all(color: DesignTokens.d2Live),
                        borderRadius: BorderRadius.circular(
                          SelahRadius.badge,
                        ),
                      ),
                      child: Text(
                        'BLACKOUT — OUTPUT DARK',
                        style: SelahType.overline.copyWith(
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                Opacity(
                  opacity: blackout ? 0.3 : 1,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (hasContent && caption != null) ...[
                        Text(
                          caption!.toUpperCase(),
                          style: SelahType.overline.copyWith(
                            color: DesignTokens.d2TextSecondary,
                          ),
                        ),
                        const SizedBox(height: 6),
                      ],
                      Text(
                        hasContent ? title! : idle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: hasContent
                            ? SelahType.slide.copyWith(
                                fontSize: 15,
                                color: scripture
                                    ? DesignTokens.d2Gold
                                    : DesignTokens.d2Text,
                              )
                            : SelahType.rowTitle.copyWith(
                                fontWeight: FontWeight.w500,
                                color: DesignTokens.d2TextSecondary,
                              ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The compact UP NEXT row (spec §4.3, Figma `342:205`): a wash thumbnail, the
/// overline, and what is queued. A scripture reference is gold here too.
///
/// Rendered only when nothing is staged — when something IS staged the Preview
/// monitor above already shows it, and two cards naming the same item would
/// read as two different queued things.
class UpNextCard extends StatelessWidget {
  final String title;
  final bool scripture;

  const UpNextCard({super.key, required this.title, this.scripture = false});

  @override
  Widget build(BuildContext context) => SelahCard(
    radius: SelahRadius.row,
    child: Row(
      children: [
        Container(
          width: 64,
          height: 38,
          decoration: BoxDecoration(
            gradient: SelahGradient.onAirWash,
            borderRadius: BorderRadius.circular(SelahRadius.badge),
            border: Border.all(color: DesignTokens.d2Border),
          ),
        ),
        const SizedBox(width: SelahSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'UP NEXT',
                style: SelahType.overline.copyWith(
                  color: DesignTokens.d2TextSecondary,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: SelahType.rowTitle.copyWith(
                  color: scripture
                      ? DesignTokens.d2Gold
                      : DesignTokens.d2Text,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
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

/// The always-on emergency strip (UX-CANONICAL §3, spec §4.2): Blackout + Clear
/// All, present above the tab bar on every screen. Never scrolls away.
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
///
/// Colour follows spec §4.2/Q3: **Blackout owns the red family**, because it is
/// the control with an *engaged* state and therefore needs a soft→solid
/// escalation ladder. Clear All keeps red ink and border on a neutral fill, so
/// two red blocks never compete for the same glance.
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

  // NOTE (17tnw2ay2pq review, Sana — blocking finding 1): an armed control
  // here is silently discarded if `LiveController.busy` becomes true (from
  // ANY control, not just this strip) during the confirm window — the
  // `_disarm` Timer above keeps running regardless, so the confirming tap
  // lands on an inert button and the arm expires with no indication to the
  // operator. This is being fixed in a concurrent session
  // ("Fix emergency strip arm window eaten by busy") to avoid two sessions
  // editing this exact arm/disarm mechanism at once — see that fix for the
  // pause/resume-around-busy remediation. Do not re-fix here without
  // checking that session's outcome first.

  /// One tap arms, the next fires **the command that was armed**. [intent] is
  /// evaluated at tap time — it is what this gesture means to the operator
  /// looking at the button right now. [immediate] skips the arming step for
  /// non-destructive directions (un-blackout).
  VoidCallback? _guarded(
    _Armed which,
    Map<String, dynamic> Function() intent, {
    bool immediate = false,
  }) {
    // Disabled while state is unknown (syncing) or while a command this
    // strip (or any other control) sent is still on the wire (busy) — a tap
    // that lands here must not look live while it would only be dropped.
    if (widget.live.syncing || widget.live.busy) return null;
    return () {
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
    // Reconnecting is the more urgent/informative reason when both are true:
    // it means the link is down or unproven, open-ended until a reconnect.
    // busy is at least bounded, but not "well under" a single commandTimeout
    // — act() awaits the command's own round trip AND the refresh() that
    // follows it, so it can span roughly two commandTimeout windows (and
    // session.dart's read loop has no single hard cap beyond that; Sana,
    // 17tnw2ay2pq review).
    final disabledReason =
        live.syncing ? 'unavailable while reconnecting' : 'sending…';

    return Container(
      decoration: const BoxDecoration(
        color: DesignTokens.d2Surface,
        border: Border(
          top: BorderSide(color: DesignTokens.d2Border),
          bottom: BorderSide(color: DesignTokens.d2Border),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(
        SelahSpace.md,
        SelahSpace.xs,
        SelahSpace.md,
        SelahSpace.xs,
      ),
      child: Row(
        children: [
          if (canBlackout)
            Expanded(
              child: SelahButton(
                // An armed control announces what the NEXT tap will do, which
                // outranks what the poll last said the host is. Letting
                // `blackout` win here put the word "UN-BLACKOUT" under a thumb
                // that was about to confirm a blackout.
                glyph: '■',
                label: armedBlackout
                    ? 'CONFIRM BLACKOUT'
                    : blackout
                    ? 'UN-BLACKOUT'
                    : 'BLACKOUT',
                semanticLabel: armedBlackout
                    ? 'Confirm blackout'
                    : blackout
                    ? 'Un-blackout'
                    : 'Blackout',
                disabledReason: disabledReason,
                // The `aria-pressed` equivalent: the engaged state is announced,
                // not only drawn (spec §6.3).
                toggled: blackout,
                haptic: true,
                // Idle carries the soft red; armed or already-dark escalates to
                // the solid alarm fill, because both mean the audience screen is
                // (about to be) off.
                variant: (blackout || armedBlackout)
                    ? SelahButtonVariant.alarm
                    : SelahButtonVariant.danger,
                textStyle: _emgLabel,
                // Un-blackout restores the audience screen — never gate recovery.
                // The direction is absolute and decided from what the operator
                // is looking at as they tap, not rebuilt under their gesture.
                onPressed: _guarded(
                  _Armed.blackout,
                  () => cmdBlackout(!blackout),
                  immediate: blackout,
                ),
              ),
            ),
          if (canBlackout && canClear) const SizedBox(width: SelahSpace.sm),
          if (canClear)
            Expanded(
              child: SelahButton(
                glyph: '✕',
                label: armedClear ? 'CONFIRM CLEAR' : 'CLEAR ALL',
                semanticLabel: armedClear ? 'Confirm clear all' : 'Clear all',
                disabledReason: disabledReason,
                haptic: true,
                variant: armedClear
                    ? SelahButtonVariant.alarm
                    : SelahButtonVariant.dangerQuiet,
                textStyle: _emgLabel,
                onPressed: _guarded(_Armed.clear, cmdClear),
              ),
            ),
        ],
      ),
    );
  }

  static const TextStyle _emgLabel = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w800,
    letterSpacing: 0.4,
  );
}

/// Format a whole-seconds duration as `M:SS`.
String fmtClock(int secs) =>
    '${secs ~/ 60}:${(secs % 60).toString().padLeft(2, '0')}';

/// The timer readout spoken as a duration. `12:45` is read by assistive tech as
/// a time of day, which is precisely wrong for a countdown (spec §6.4).
String spokenClock(int secs) {
  final m = secs ~/ 60, s = secs % 60;
  return '$m ${m == 1 ? "minute" : "minutes"} $s '
      '${s == 1 ? "second" : "seconds"} remaining';
}
