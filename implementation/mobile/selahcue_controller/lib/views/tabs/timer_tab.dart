/// Timer tab (revamp 86ajpx7bd): a big readout, presets, manual minutes entry,
/// and live +1:00/−1:00/Stop (the adjust buttons act on a running timer).
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../widgets/mobile_widgets.dart';

class TimerTab extends StatefulWidget {
  final LiveController live;
  const TimerTab({super.key, required this.live});

  @override
  State<TimerTab> createState() => _TimerTabState();
}

class _TimerTabState extends State<TimerTab> {
  final _minutes = TextEditingController();

  @override
  void dispose() {
    _minutes.dispose();
    super.dispose();
  }

  void _startCustom() {
    var mins = int.tryParse(_minutes.text.trim());
    if (mins == null || mins < 1) return;
    if (mins > 999) mins = 999;
    widget.live.act(cmdStartTimer(mins * 60));
    _minutes.clear();
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
    String state;
    if (t == null) {
      readout = '–:––';
      readoutColor = DesignTokens.textMuted;
      state = 'no timer running';
    } else if (t.timeUp) {
      readout = 'TIME UP';
      readoutColor = DesignTokens.liveInk;
      state = 'overrun · shown on the stage output only';
    } else {
      final secs = t.remainingSecs ?? t.elapsedSecs;
      readout = fmtClock(secs);
      readoutColor =
          t.warn ? DesignTokens.warnInk : DesignTokens.previewInk;
      state = t.warn
          ? 'warning · shown on the stage output only'
          : 'shown on the stage output only';
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('SERVICE TIMER',
            style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.7,
                color: DesignTokens.textMuted)),
        const SizedBox(height: 8),
        Center(
          child: Text(readout,
              style: TextStyle(
                  fontSize: 68,
                  fontWeight: FontWeight.w800,
                  color: readoutColor,
                  fontFeatures: const [FontFeature.tabularFigures()])),
        ),
        Center(
          child: Text(state,
              style:
                  const TextStyle(fontSize: 12, color: DesignTokens.textMuted)),
        ),
        const SizedBox(height: 16),
        // All timer controls require the Timer capability (Producer). The
        // readout above stays for every role (Monitor). TIME UP / Reset are
        // omitted this pass — tracked in the backend + mobile follow-ups.
        if (widget.live.can(Capability.timer)) ...[
          Row(
            children: [
              Expanded(
                  child: _TBtn('⏱ 5:00',
                      syncing ? null : () => widget.live.act(cmdStartTimer(300)))),
              const SizedBox(width: 8),
              Expanded(
                  child: _TBtn('⏱ 10:00',
                      syncing ? null : () => widget.live.act(cmdStartTimer(600)))),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _minutes,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: DesignTokens.textPrimary),
                  decoration: const InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: DesignTokens.bgBase,
                    hintText: 'Minutes…',
                    hintStyle: TextStyle(color: DesignTokens.textMuted),
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _startCustom(),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                  onPressed: syncing ? null : _startCustom,
                  child: const Text('Start')),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                  child: _TBtn('−1:00',
                      canAdjust ? () => widget.live.act(cmdAdjustTimer(-60)) : null)),
              const SizedBox(width: 8),
              Expanded(
                  child: _TBtn('+1:00',
                      canAdjust ? () => widget.live.act(cmdAdjustTimer(60)) : null)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _TBtn(
                  (t?.running ?? false) ? 'Pause' : 'Resume',
                  (t == null || syncing)
                      ? null
                      : () => widget.live.act(
                          t.running ? cmdPauseTimer() : cmdResumeTimer()),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                  child: _TBtn('Stop',
                      canAdjust ? () => widget.live.act(cmdStopTimer()) : null)),
            ],
          ),
        ],
      ],
    );
  }
}

class _TBtn extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  const _TBtn(this.label, this.onTap);

  @override
  Widget build(BuildContext context) => OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
        child: Text(label),
      );
}
