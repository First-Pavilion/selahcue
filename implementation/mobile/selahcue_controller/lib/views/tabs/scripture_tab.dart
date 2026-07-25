/// Scripture tab (revamp 86ajpx7bd): stage a reference or shorthand ("gen 1 1")
/// — the wire resolves it into verse text on the outputs — and see what is
/// staged/live. The full chapter verse-list browser is the desktop console's
/// (it uses a local bundle); mobile reaching that parity needs a scripture
/// verse-list wire path, tracked on the story.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/bible_books.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../widgets/mobile_widgets.dart';

class ScriptureTab extends StatefulWidget {
  final LiveController live;
  const ScriptureTab({super.key, required this.live});

  @override
  State<ScriptureTab> createState() => _ScriptureTabState();
}

class _ScriptureTabState extends State<ScriptureTab> {
  final _ctrl = TextEditingController();
  List<String> _suggestions = const [];

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onChanged);
  }

  void _onChanged() {
    final next = suggestBooks(_ctrl.text);
    final changed = next.length != _suggestions.length ||
        (next.isNotEmpty && next.first != _suggestions.first);
    if (changed) setState(() => _suggestions = next);
  }

  void _pickBook(String book) {
    // Replace the typed book portion with the full name + a trailing space,
    // keeping the cursor at the end so the user continues with chapter:verse.
    _ctrl.text = '$book ';
    _ctrl.selection = TextSelection.collapsed(offset: _ctrl.text.length);
    setState(() => _suggestions = const []);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onChanged);
    _ctrl.dispose();
    super.dispose();
  }

  void _stage() {
    final ref = _ctrl.text.trim();
    if (ref.isEmpty) return;
    widget.live.act(cmdStageScripture(ref));
    _ctrl.clear();
    FocusScope.of(context).unfocus();
  }

  void _live() {
    final ref = _ctrl.text.trim();
    if (ref.isEmpty) return;
    widget.live.stageScriptureAndGoLive(ref);
    _ctrl.clear();
    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
    final view = widget.live.view;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('SCRIPTURE',
            style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.7,
                color: DesignTokens.textMuted)),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _ctrl,
                style: const TextStyle(color: DesignTokens.textPrimary),
                decoration: const InputDecoration(
                  isDense: true,
                  filled: true,
                  fillColor: DesignTokens.bgBase,
                  hintText: 'Reference or keywords — e.g. gen 1 1',
                  hintStyle: TextStyle(color: DesignTokens.textMuted),
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _stage(),
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton(
              onPressed: _stage,
              child: const Text('Stage'),
            ),
            const SizedBox(width: 6),
            FilledButton(
              onPressed: _live,
              style: FilledButton.styleFrom(
                  backgroundColor: DesignTokens.previewFill),
              child: const Text('Live'),
            ),
          ],
        ),
        if (_suggestions.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final b in _suggestions)
                ActionChip(
                  label: Text(b),
                  backgroundColor: DesignTokens.bgPanel,
                  side: const BorderSide(color: DesignTokens.border),
                  labelStyle: const TextStyle(
                      fontSize: 13, color: DesignTokens.textPrimary),
                  onPressed: () => _pickBook(b),
                ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        const Text(
            'Stage → Preview · Live → straight to the audience. '
            '"gen 1 1", "Romans 8:28", and "gen 1 1-3" all work.',
            style: TextStyle(fontSize: 11, color: DesignTokens.textMuted)),
        const SizedBox(height: 20),
        if (view?.stagedScripture != null)
          _StatusRow(
              badge: 'PREVIEW',
              color: DesignTokens.previewFill,
              text: view!.stagedScripture!),
        if (view?.liveScripture != null) ...[
          const SizedBox(height: 8),
          _StatusRow(
              badge: 'LIVE',
              color: DesignTokens.liveFill,
              text: view!.liveScripture!),
        ],
      ],
    );
  }
}

class _StatusRow extends StatelessWidget {
  final String badge;
  final Color color;
  final String text;
  const _StatusRow(
      {required this.badge, required this.color, required this.text});

  @override
  Widget build(BuildContext context) => Row(
        children: [
          StatusBadge(text: badge, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: DesignTokens.textPrimary)),
          ),
        ],
      );
}
