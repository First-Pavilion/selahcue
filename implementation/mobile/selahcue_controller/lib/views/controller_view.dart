/// Controller view (V in MVC): the host-authoritative plan with LIVE/PREVIEW
/// badges and the control buttons. All logic lives in [LiveController]; this is
/// widgets only.
library;

import 'package:flutter/material.dart';

import '../controllers/live_controller.dart';
import '../models/design_tokens.dart';
import '../models/protocol.dart';
import '../models/session.dart';
import '../models/stored_session.dart';
import 'pairing_view.dart';

class ControllerView extends StatefulWidget {
  final SelahSession session;
  final StoredSession stored;

  const ControllerView({super.key, required this.session, required this.stored});

  @override
  State<ControllerView> createState() => _ControllerViewState();
}

class _ControllerViewState extends State<ControllerView> {
  late final LiveController _live;

  @override
  void initState() {
    super.initState();
    _live = LiveController(session: widget.session, stored: widget.stored);
  }

  @override
  void dispose() {
    _live.dispose();
    super.dispose();
  }

  Future<void> _unpair() async {
    await _live.unpair();
    if (!mounted) return;
    Navigator.of(context)
        .pushReplacement(MaterialPageRoute(builder: (_) => const PairingView()));
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _live,
      builder: (context, _) {
        final view = _live.view;
        final blackout = _live.blackout;
        return Scaffold(
          appBar: AppBar(
            title: Text(view?.planName ?? 'SelahCue'),
            actions: [
              if (view?.timer != null)
                Padding(
                  padding: const EdgeInsets.only(right: 12),
                  child: Center(child: _TimerBadge(timer: view!.timer!)),
                ),
              IconButton(
                tooltip: 'Un-pair this device',
                onPressed: _unpair,
                icon: const Icon(Icons.link_off),
              ),
            ],
          ),
          body: Column(
            children: [
              if (_live.error != null)
                MaterialBanner(
                  content: Text(_live.error!),
                  actions: [
                    TextButton(
                      onPressed: _live.dismissError,
                      child: const Text('Dismiss'),
                    ),
                  ],
                ),
              Expanded(
                child: view == null
                    ? const Center(child: CircularProgressIndicator())
                    : ListView.builder(
                        itemCount: view.items.length,
                        itemBuilder: (context, i) {
                          final item = view.items[i];
                          return ListTile(
                            onTap: () => _live.act(cmdSelectItem(item.id)),
                            leading: _KindChip(kind: item.kind),
                            title: Text(item.title),
                            trailing: item.isLive
                                ? const _Badge(
                                    text: 'LIVE',
                                    color: DesignTokens.liveFill)
                                : item.isStaged
                                    ? const _Badge(
                                        text: 'PREVIEW',
                                        color: DesignTokens.previewFill)
                                    : null,
                          );
                        },
                      ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _live.act(cmdPrevious()),
                              child: const Text('◀ Prev'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _live.act(cmdNext()),
                              child: const Text('Next ▶'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        height: 52,
                        child: FilledButton(
                          style: FilledButton.styleFrom(
                              backgroundColor: DesignTokens.previewFill),
                          onPressed: () => _live.act(cmdGoLive()),
                          child: const Text('GO LIVE',
                              style: TextStyle(
                                  fontSize: 18, fontWeight: FontWeight.w700)),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              style: blackout
                                  ? OutlinedButton.styleFrom(
                                      backgroundColor: DesignTokens.liveFill)
                                  : null,
                              onPressed: () => _live.act(cmdBlackout(!blackout)),
                              child: Text(blackout ? 'Un-blackout' : 'Blackout'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _live.act(cmdClear()),
                              child: const Text('Clear'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _live.act(cmdStartTimer(300)),
                              child: const Text('⏱ 5:00'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _live.act(cmdStopTimer()),
                              child: const Text('Stop timer'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _KindChip extends StatelessWidget {
  final String kind;
  const _KindChip({required this.kind});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: DesignTokens.border),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(kind.toUpperCase(),
          style: const TextStyle(fontSize: 10, color: DesignTokens.textMuted)),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;
  const _Badge({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(text,
          style: const TextStyle(
              fontSize: 10, fontWeight: FontWeight.w800, color: Colors.white)),
    );
  }
}

class _TimerBadge extends StatelessWidget {
  final TimerSnapshot timer;
  const _TimerBadge({required this.timer});

  @override
  Widget build(BuildContext context) {
    final String label;
    final Color color;
    if (timer.timeUp) {
      label = 'TIME UP';
      color = DesignTokens.liveInk;
    } else {
      final secs = timer.remainingSecs ?? timer.elapsedSecs;
      label = '${secs ~/ 60}:${(secs % 60).toString().padLeft(2, '0')}';
      color = timer.warn ? DesignTokens.warnInk : DesignTokens.previewInk;
    }
    return Text(label,
        style: TextStyle(fontWeight: FontWeight.w700, color: color));
  }
}
