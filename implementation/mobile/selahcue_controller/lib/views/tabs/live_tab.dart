/// Live tab (revamp 86ajpx7bd): the primary control surface — PREVIEW/LIVE
/// cards, the ◀ GO LIVE ▶ transport, and the next-item hint.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../widgets/mobile_widgets.dart';

class LiveTab extends StatelessWidget {
  final LiveController live;
  const LiveTab({super.key, required this.live});

  @override
  Widget build(BuildContext context) {
    final view = live.view;
    if (view == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final items = view.items;
    String? nameAt(int? i) => (i != null && i >= 0 && i < items.length)
        ? items[i].title
        : null;
    String? kindAt(int? i) => (i != null && i >= 0 && i < items.length)
        ? items[i].kind
        : null;

    // Preview: a staged plan item, or a staged scripture reference.
    final previewTitle = nameAt(view.stagedIndex) ?? view.stagedScripture;
    final previewCap = view.stagedScripture != null
        ? 'scripture · staged'
        : (kindAt(view.stagedIndex) != null
            ? '${kindAt(view.stagedIndex)!.toLowerCase()} · staged'
            : null);
    // Live: a live plan item, a live scripture, or a removed free slide.
    final liveTitle =
        nameAt(view.liveIndex) ?? view.liveScripture ?? view.liveFreeText;
    final liveCap = view.liveScripture != null
        ? 'scripture · main output'
        : (kindAt(view.liveIndex) != null
            ? '${kindAt(view.liveIndex)!.toLowerCase()} · main output'
            : null);

    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        OutputCard(
          header: 'PREVIEW · STAGED',
          headerColor: DesignTokens.previewFill,
          borderColor: DesignTokens.previewInk,
          title: previewTitle,
          caption: previewCap,
          idle: 'Nothing staged',
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            _TransportBtn(
                glyph: '◀',
                label: 'Previous item',
                onTap: () => live.act(cmdPrevious())),
            const SizedBox(width: 8),
            Expanded(
              child: Semantics(
                button: true,
                label: 'Go live',
                child: Material(
                  color: DesignTokens.previewFill,
                  borderRadius: BorderRadius.circular(10),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => live.act(cmdGoLive()),
                    child: Container(
                      height: 54,
                      alignment: Alignment.center,
                      child: const Text('GO LIVE',
                          style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.4,
                              color: Colors.white)),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            _TransportBtn(
                glyph: '▶',
                label: 'Next item',
                onTap: () => live.act(cmdNext())),
          ],
        ),
        const SizedBox(height: 10),
        OutputCard(
          header: '● LIVE · ON AIR',
          headerColor: DesignTokens.liveFill,
          borderColor: DesignTokens.liveInk,
          title: liveTitle,
          caption: liveCap,
          idle: 'Output idle',
          blackout: view.blackout,
        ),
        const SizedBox(height: 8),
        if (nameAt(view.stagedIndex) == null &&
            view.stagedScripture == null &&
            _nextName(view) != null)
          Text('Next: ${_nextName(view)}',
              style:
                  const TextStyle(fontSize: 11, color: DesignTokens.textMuted)),
      ],
    );
  }

  String? _nextName(OperatorStateView v) {
    final cur = v.liveIndex;
    if (cur == null) return v.items.isNotEmpty ? v.items.first.title : null;
    final n = cur + 1;
    return (n < v.items.length) ? v.items[n].title : null;
  }
}

class _TransportBtn extends StatelessWidget {
  final String glyph;
  final String label;
  final VoidCallback onTap;
  const _TransportBtn(
      {required this.glyph, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: label,
        // The bare '◀'/'▶' glyph is decorative once the button is named — hide
        // it from assistive tech so it isn't announced as "left-pointing triangle".
        excludeSemantics: true,
        child: Material(
          color: DesignTokens.bgPanel,
          borderRadius: BorderRadius.circular(10),
          child: InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap: onTap,
            child: Container(
              width: 64,
              height: 54,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border.all(color: DesignTokens.border),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(glyph,
                  style: const TextStyle(
                      fontSize: 18, color: DesignTokens.textPrimary)),
            ),
          ),
        ),
      );
}
