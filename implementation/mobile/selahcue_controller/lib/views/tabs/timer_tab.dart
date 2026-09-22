/// Timer tab — a big readout with its state chip, presets, an HH:MM:SS custom
/// time, and live ±1:00 / Pause / Reset / Stop / Send "TIME UP" to stage.
/// Design 2.0 (Figma `343:169`, `356:139`).
///
/// `Reset` and `Send "TIME UP" to stage` (MOB-009) ship WITHOUT any new
/// `Command` variant — each composes commands the wire already carries, the
/// same composition the desktop operator console's own `Reset` button already
/// uses (`selahcue-operator/dist/app.js`'s `timer-reset` handler, shipped in
/// the Design 2.0 operator console rewrite, predates this mobile wiring). One
/// real difference from that button, not "exact" parity (PR #78 review —
/// Cody): the desktop handler does a synchronous `invoke("view")` refetch at
/// CLICK TIME before computing its total; this Reset reads `totalSecs` from
/// the same ~1s-polled `TimerSnapshot` every other control on this tab already
/// reads from, not a fresh fetch. A narrow, self-correcting staleness window
/// (the next poll reconciles the readout to whatever the host actually did),
/// consistent with how Stop/Pause/±1:00 already read state on this tab — not
/// singled out for a live-refetch pattern nothing else here uses.
///
/// * `Reset` restarts the countdown at its CURRENT TARGET length via the
///   existing [cmdStartTimer] — the same command the presets and custom-time
///   Start use. The length comes from `TimerSnapshot.totalSecs` (Rust
///   `total_secs`, `protocol.rs`), which the host has reported since that same
///   rewrite; this Dart model just never parsed it until now. Falls back to
///   `remaining + elapsed` for a pre-total_secs host, matching the desktop
///   button's own fallback — `total_secs` is correct in overrun where that sum
///   no longer equals the target, elapsed keeps growing past TIME UP.
///   "Current target", not the length it was first started at (PR #78 review
///   — Sana): `totalSecs` is the same field ±1:00 already mutates, so Reset
///   after any adjustment restores to wherever the operator has since moved
///   the target — pre-existing ±1:00 behaviour, not new here.
/// * `Send "TIME UP" to stage` reduces the countdown's remaining time to zero
///   via the existing [cmdAdjustTimer]: `AdjustTimer`'s own contract
///   ("Clamps at zero (landing in TIME UP)", `protocol.rs`) is exactly the
///   forced-overrun this control needs — a negative delta equal to
///   `remainingSecs` lands `elapsed == total` immediately. `time_up` itself
///   stays host-COMPUTED (`Timer::is_time_up`); this never invents a
///   client-asserted `time_up` field on the wire, it only changes the total the
///   host already derives that state from. Guarded against a double-tap
///   compounding two `-remainingSecs` deltas from the same stale snapshot
///   (`_forcingTimeUp`, PR #78 review — Sana).
///
/// Both stay behind the same `Capability.timer` gate as every other control on
/// this tab (`AdjustTimer`/`StartTimer` already require RBAC `Permission::
/// Timer` — `rbac.rs` — so no server-side RBAC change was needed either).
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import '../widgets/custom_time_well.dart';
import '../widgets/mobile_widgets.dart';

class TimerTab extends StatefulWidget {
  final LiveController live;
  const TimerTab({super.key, required this.live});

  @override
  State<TimerTab> createState() => _TimerTabState();
}

class _TimerTabState extends State<TimerTab> {
  final _custom = CustomTimeController();

  @override
  void dispose() {
    _custom.dispose();
    super.dispose();
  }

  /// True while a start is on the wire. The well keeps its digits until the
  /// host has answered, so without this the Start button (and the keyboard's
  /// done key, which lands here too) could fire the same duration twice.
  bool _starting = false;

  /// Start the typed duration, and clear the well **only once the host has
  /// accepted it**.
  ///
  /// Clearing on dispatch threw the operator's input away on every outcome that
  /// is not "applied" — a `forbidden` from a role that no longer holds the
  /// Timer capability, a link that died mid-command, a reconnect that landed
  /// under it. All three are the moments a service is already going wrong, and
  /// all three used to be answered by an empty field and no timer, with nothing
  /// on screen tying the two together. `act()` returns [CommandOutcome]
  /// precisely so a caller can tell an acknowledged command from a lost one
  /// (86ajxwcft); this is a caller that has to.
  Future<void> _startCustom() async {
    if (_starting) return;
    final seconds = _custom.totalSeconds;
    if (seconds < 1) return;
    _starting = true;
    final CommandOutcome outcome;
    try {
      outcome = await widget.live.act(cmdStartTimer(seconds));
    } finally {
      _starting = false;
    }
    if (!mounted || outcome != CommandOutcome.applied) return;
    // Only now: the duration is running on the host, so the digits have done
    // their job and the next start should be a deliberate re-entry. The
    // keyboard goes with them — on a refusal it stays up, over a field that
    // still holds what was typed, which is the state a retry needs.
    _custom.clear();
    FocusScope.of(context).unfocus();
  }

  /// The highest seconds value this device will ever send for a countdown —
  /// the same 23:59:59 ceiling [CustomTimeWell] enforces on typed entry
  /// (`maxCustomHours`), applied here too as defence-in-depth: a host-reported
  /// `totalSecs` is host data, not user input, but Reset still must never
  /// forward an unbounded value to [cmdStartTimer]. Mirrors the desktop
  /// console's own `MAX_TIMER_SECS` clamp on its Reset button (`app.js`).
  static const int _maxTimerSecs = maxCustomHours * 3600 + 59 * 60 + 59;

  /// Restart the countdown at its CURRENT target length (MOB-009). Prefers the
  /// host's own `totalSecs` — correct even in overrun, where
  /// `remaining + elapsed` no longer equals that target (elapsed keeps growing
  /// past TIME UP). Falls back to `remaining + elapsed` for a host that
  /// predates the field, matching the desktop button's own fallback.
  ///
  /// "Current target", not "the length it was first started at" (PR #78
  /// review — Sana): `totalSecs` is the SAME field ±1:00 already mutates, so a
  /// Reset after any adjustment — including `_sendTimeUp` below — restores to
  /// wherever the operator has since moved the target, not the original
  /// 5:00/10:00/custom value. This is pre-existing ±1:00 behaviour, not new
  /// here; only the wording risked implying permanence that was never true.
  void _resetTimer(TimerSnapshot t) {
    final total = t.totalSecs ?? ((t.remainingSecs ?? 0) + t.elapsedSecs);
    if (total < 1) return;
    widget.live.act(cmdStartTimer(total.clamp(1, _maxTimerSecs)));
  }

  /// True while a Send-TIME-UP command is on the wire (PR #78 review — Sana).
  /// `_sendTimeUp` sizes its delta from the CURRENT `remainingSecs` in the
  /// synced view, so a second tap before the host's Ack updates that view
  /// would read the SAME stale `remainingSecs` and send a SECOND
  /// `-remainingSecs` — subtracting it again from a target `adjust_timer`
  /// already reduced to (about) zero, driving `totalSecs` negative-then-
  /// clamped-to-0. Once there, `_resetTimer` has nothing to restart to and
  /// silently no-ops. Mirrors `_starting` above (same class of bug Start had
  /// before that guard existed).
  bool _forcingTimeUp = false;

  /// Force the countdown into TIME UP right now (MOB-009), by reducing its
  /// remaining time to zero — `AdjustTimer`'s own documented contract already
  /// "clamps at zero (landing in TIME UP)" (`protocol.rs`), so a delta equal
  /// to `-remainingSecs` lands `elapsed == total` on the very next tick.
  /// `time_up` itself stays host-computed; this never asserts it directly.
  Future<void> _sendTimeUp(TimerSnapshot t) async {
    if (_forcingTimeUp) return;
    final remaining = t.remainingSecs ?? 0;
    if (remaining < 1) return;
    _forcingTimeUp = true;
    try {
      await widget.live.act(cmdAdjustTimer(-remaining));
    } finally {
      _forcingTimeUp = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.live.view?.timer;
    // "A timer exists" (drives the adjust/stop enablement) — distinct from
    // `t.running` = actively counting (drives the Pause↔Resume label).
    final hasTimer = t != null;
    // Every control goes inert until this device is back in step with the host
    // (FR-097). Nudging ±1:00 against a countdown we cannot see is the same
    // stale-premise tap as staging a slide against a stale plan. The READOUT
    // deliberately stays: it is the same snapshot the rest of the app is already
    // showing, and the global "Syncing live state…" banner says it is stale —
    // blanking it would tell the operator less, not more.
    final syncing = widget.live.syncing;
    final canAdjust = hasTimer && !syncing;
    final String readout;
    final Color readoutColor;
    final String chip;
    final SelahTone chipTone;
    final String state;
    if (t == null) {
      readout = '–:––';
      readoutColor = DesignTokens.d2TextSecondary;
      chip = 'NO TIMER';
      chipTone = SelahTone.neutral;
      state = 'no timer running';
    } else if (t.timeUp) {
      readout = 'TIME UP';
      readoutColor = DesignTokens.d2Live;
      chip = 'TIME UP';
      chipTone = SelahTone.live;
      state = 'overrun · shown on the stage output only';
    } else {
      final secs = t.remainingSecs ?? t.elapsedSecs;
      readout = fmtClock(secs);
      readoutColor = t.warn ? DesignTokens.d2Warn : DesignTokens.d2Preview;
      chip = t.warn
          ? 'WARNING'
          : t.running
          ? 'RUNNING'
          : 'PAUSED';
      // Spec §4.6: PAUSED is a warn chip, not a neutral one — a stopped clock
      // during a service is a thing to notice, not ambient state.
      chipTone = t.warn
          ? SelahTone.warn
          : t.running
          ? SelahTone.preview
          : SelahTone.warn;
      state = t.warn
          ? 'warning · shown on the stage output only'
          : 'shown on the stage output only';
    }

    return ListView(
      padding: const EdgeInsets.all(SelahSpace.gutter),
      children: [
        const SectionLabel(
          'SERVICE TIMER',
          padding: EdgeInsets.only(bottom: SelahSpace.xs),
        ),
        SelahCard(
          padding: const EdgeInsets.symmetric(
            horizontal: SelahSpace.gutter,
            vertical: SelahSpace.section,
          ),
          child: Column(
            children: [
              StatusBadge(text: chip, tone: chipTone, dot: true),
              const SizedBox(height: SelahSpace.md),
              Semantics(
                liveRegion: true,
                label: t == null
                    ? 'No timer running'
                    : t.timeUp
                    ? 'Time up'
                    : spokenClock(t.remainingSecs ?? t.elapsedSecs),
                excludeSemantics: true,
                // Shrink-to-fit rather than wrap, so a 3.0 text scale cannot
                // break the readout across two lines (spec §6.7).
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    readout,
                    style: SelahType.display.copyWith(color: readoutColor),
                  ),
                ),
              ),
              const SizedBox(height: SelahSpace.xs),
              Text(
                state,
                textAlign: TextAlign.center,
                style: SelahType.caption.copyWith(
                  color: DesignTokens.d2TextSecondary,
                ),
              ),
            ],
          ),
        ),
        // All timer controls require the Timer capability (Producer). The
        // readout above stays for every role (Monitor).
        if (widget.live.can(Capability.timer)) ...[
          const SizedBox(height: SelahSpace.gutter),
          Row(
            children: [
              Expanded(
                child: SelahButton(
                  label: '5:00',
                  icon: Icons.timer_outlined,
                  semanticLabel: 'Start a five minute timer',
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: syncing
                      ? null
                      : () => widget.live.act(cmdStartTimer(300)),
                ),
              ),
              const SizedBox(width: SelahSpace.sm),
              Expanded(
                child: SelahButton(
                  label: '10:00',
                  icon: Icons.timer_outlined,
                  semanticLabel: 'Start a ten minute timer',
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: syncing
                      ? null
                      : () => widget.live.act(cmdStartTimer(600)),
                ),
              ),
            ],
          ),
          const SizedBox(height: SelahSpace.xl),
          const SectionLabel(
            'SET A CUSTOM TIME',
            padding: EdgeInsets.only(bottom: SelahSpace.xs),
          ),
          // Rebuilt on each keystroke so Start reflects what is in the well —
          // scoped to this row so a digit does not rebuild the whole tab.
          ListenableBuilder(
            listenable: _custom,
            builder: (context, _) => Row(
              children: [
                Expanded(
                  child: CustomTimeWell(
                    controller: _custom,
                    enabled: !syncing,
                    onSubmitted: syncing ? null : _startCustom,
                  ),
                ),
                const SizedBox(width: SelahSpace.sm),
                SelahButton(
                  label: 'Start',
                  variant: SelahButtonVariant.primary,
                  // Two different reasons a start cannot happen, and the
                  // announcement says which: an empty well is the operator's
                  // turn, a re-sync is the link's.
                  disabledReason: syncing
                      ? 'unavailable while reconnecting'
                      : 'set a time first',
                  onPressed: (syncing || _custom.isEmpty) ? null : _startCustom,
                ),
              ],
            ),
          ),
          const SizedBox(height: SelahSpace.sm),
          Row(
            children: [
              Expanded(
                child: SelahButton(
                  label: '− 1:00',
                  semanticLabel: 'Subtract one minute',
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: canAdjust
                      ? () => widget.live.act(cmdAdjustTimer(-60))
                      : null,
                ),
              ),
              const SizedBox(width: SelahSpace.sm),
              Expanded(
                child: SelahButton(
                  label: '+ 1:00',
                  semanticLabel: 'Add one minute',
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: canAdjust
                      ? () => widget.live.act(cmdAdjustTimer(60))
                      : null,
                ),
              ),
            ],
          ),
          const SizedBox(height: SelahSpace.sm),
          // Pause | Reset | Stop — three-across per the frame (`356:151`), Reset
          // added between the two pre-existing buttons rather than appended, so
          // the row keeps the frame's exact order.
          Row(
            children: [
              Expanded(
                child: SelahButton(
                  label: (t?.running ?? false) ? 'Pause' : 'Resume',
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: (t == null || syncing)
                      ? null
                      : () => widget.live.act(
                          t.running ? cmdPauseTimer() : cmdResumeTimer(),
                        ),
                ),
              ),
              const SizedBox(width: SelahSpace.sm),
              Expanded(
                child: SelahButton(
                  label: 'Reset',
                  semanticLabel: 'Reset to the current target duration',
                  // Two different reasons Reset cannot fire, named like
                  // Send-TIME-UP's below (PR #78 review — Cody): syncing is
                  // the link's, no timer is the operator's.
                  disabledReason: syncing
                      ? 'unavailable while reconnecting'
                      : 'start a timer first',
                  onPressed: canAdjust ? () => _resetTimer(t) : null,
                ),
              ),
              const SizedBox(width: SelahSpace.sm),
              Expanded(
                child: SelahButton(
                  label: 'Stop',
                  variant: SelahButtonVariant.danger,
                  disabledReason: 'unavailable while reconnecting',
                  onPressed: canAdjust
                      ? () => widget.live.act(cmdStopTimer())
                      : null,
                ),
              ),
            ],
          ),
          const SizedBox(height: SelahSpace.sm),
          _SendTimeUpButton(
            // Nothing left to force once TIME UP is already showing — disabled
            // rather than a silent no-op tap (spec: uniform disabled-with-reason).
            // `canAdjust` already promotes `t` to non-null here (it is
            // `hasTimer && !syncing`, and `hasTimer` is `t != null`).
            onPressed: (canAdjust && !t.timeUp)
                ? () => _sendTimeUp(t)
                : null,
            disabledReason: syncing
                ? 'unavailable while reconnecting'
                : t == null
                ? 'start a timer first'
                : 'already at time up',
          ),
        ],
      ],
    );
  }
}

/// Full-width "Send TIME UP to stage" (frame `356:158`) — a solid `d2Live`
/// block with a bold title + a muted caption, which [SelahButton] has no shape
/// for (single line only), so this is its own small button rather than a
/// stretch of that widget.
///
/// Caption colour is NOT the frame's literal `#6b7383` (`d2TextMuted`): that is
/// ~1.5:1 on solid `d2Live` (`#ff4d4d`) — nowhere near AA even for large text.
/// `SelahGradient.onLiveInk` (the SAME ink `SelahButtonVariant.alarm` already
/// uses on this exact fill, documented there at 5.31:1) covers both lines —
/// the same A11Y-FIX class as this file's lock-note (`d2TextMuted` avoided at
/// :336 for the identical reason).
class _SendTimeUpButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String disabledReason;

  const _SendTimeUpButton({required this.onPressed, required this.disabledReason});

  bool get _disabled => onPressed == null;

  static const _ink = SelahGradient.onLiveInk;
  static const _title = 'Send "TIME UP" to stage';
  static const _caption = 'stage display only — never audience';

  // Every input is a compile-time constant, so this — and the two styles
  // below — are computed once per app run, not once per rebuild (PR #78
  // review — Vera, optional tidy-up: `SelahButton` does the same at
  // `primitives.dart:534` for its own radius).
  static const _radius = BorderRadius.all(Radius.circular(SelahRadius.row));
  static final _titleStyle =
      SelahType.label.copyWith(color: _ink, fontWeight: FontWeight.bold);
  static final _captionStyle = SelahType.caption.copyWith(color: _ink);

  @override
  Widget build(BuildContext context) {
    // `excludeSemantics: true` replaces the two child `Text`s' own announcements
    // with this single label — the caption MUST be folded in here too, or a
    // screen-reader user never hears "stage display only, never audience" at
    // all (PR #78 review — Cody, blocking).
    final label = _disabled
        ? '$_title. $_caption. $disabledReason'
        : '$_title. $_caption';
    return Semantics(
      button: true,
      enabled: !_disabled,
      label: label,
      excludeSemantics: true,
      child: Opacity(
        opacity: _disabled ? 0.4 : 1,
        child: Material(
          color: DesignTokens.d2Live,
          borderRadius: _radius,
          child: InkWell(
            borderRadius: _radius,
            onTap: onPressed,
            child: Container(
              constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
              width: double.infinity,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(
                horizontal: SelahSpace.md,
                vertical: SelahSpace.sm,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_title, style: _titleStyle),
                  const SizedBox(height: 2),
                  Text(_caption, style: _captionStyle),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
