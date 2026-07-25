/// Timer tab (revamp 86ajpx7bd): a big readout, presets, manual minutes entry,
/// and live +1:00/−1:00/Stop (the adjust buttons act on a running timer).
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
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
    final running = t != null;
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
        Row(
          children: [
            Expanded(
                child: _TBtn('⏱ 5:00',
                    () => widget.live.act(cmdStartTimer(300)))),
            const SizedBox(width: 8),
            Expanded(
                child: _TBtn('⏱ 10:00',
                    () => widget.live.act(cmdStartTimer(600)))),
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
            OutlinedButton(onPressed: _startCustom, child: const Text('Start')),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
                child: _TBtn('−1:00',
                    running ? () => widget.live.act(cmdAdjustTimer(-60)) : null)),
            const SizedBox(width: 8),
            Expanded(
                child: _TBtn('+1:00',
                    running ? () => widget.live.act(cmdAdjustTimer(60)) : null)),
            const SizedBox(width: 8),
            Expanded(
                child: _TBtn('Stop',
                    running ? () => widget.live.act(cmdStopTimer()) : null)),
          ],
        ),
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
