/// Timer tab — a big readout with its state chip, presets, an HH:MM:SS custom
/// time, and live ±1:00 / Pause / Stop. Design 2.0 (Figma `343:169`, `356:139`).
///
/// Two controls the frame draws are **not here, and not drawn dead**: `Reset`
/// and `Send "TIME UP" to stage`. Neither is a client-side omission —
/// `selahcue-lan/src/protocol.rs` carries `StartTimer` / `StopTimer` /
/// `AdjustTimer` / `PauseTimer` / `ResumeTimer` and nothing else, and
/// `TimerSnapshot` has no original-duration field, so this device could not even
/// compute what Reset would restore. `time_up` is host-computed state, not a
/// command a phone can push. Both need new protocol variants plus a
/// cross-language fixture update — an owner decision, not a mobile one. Until
/// then the tab says so in words (see `_DeferredControlsNote`), because a button
/// that sends nothing during a service is the worst of the three options.
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
          const SizedBox(height: SelahSpace.lg),
          const _DeferredControlsNote(),
        ],
      ],
    );
  }
}

/// The two frame controls that have no wire command, said in words.
///
/// This is the honest middle between the two dishonest options: drawing them
/// (an operator taps `Reset` mid-service and nothing happens, with no way to
/// tell that from a dropped link) and omitting them silently (the next person to
/// build from the frame reintroduces them, and the operator who knows the
/// desktop has them wonders why the phone does not). It is deliberately NOT
/// tappable — there is nothing behind it to reach.
class _DeferredControlsNote extends StatelessWidget {
  const _DeferredControlsNote();

  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
    padding: const EdgeInsets.symmetric(
      horizontal: SelahSpace.md,
      vertical: SelahSpace.sm,
    ),
    decoration: BoxDecoration(
      color: DesignTokens.d2Inset,
      borderRadius: BorderRadius.circular(SelahRadius.row),
      border: Border.all(color: DesignTokens.d2Border),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(
          Icons.info_outline,
          size: 16,
          color: DesignTokens.d2TextSecondary,
        ),
        const SizedBox(width: SelahSpace.xs),
        Expanded(
          child: Text(
            // A11Y-FIX (spec §6.2 item 3): `d2TextSecondary`, never the frame's
            // `d2TextMuted`, which is 3.96:1 on this well.
            'Reset and the stage “TIME UP” cue aren’t here yet — the desktop '
            'has no command for either, so this app would have nothing to '
            'send. They arrive with the host.',
            style: SelahType.caption.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
      ],
    ),
  );
}
