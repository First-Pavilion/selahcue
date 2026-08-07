/// Scripture tab (revamp 86ajpx7bd; verse-list refine): the desktop chapter
/// browser on the phone. Type/pick a reference → the host sends the whole
/// chapter over the wire (`get_chapter`) → the numbered verse list renders, and
/// a single tap stages a verse in Preview while a double-tap sends it live —
/// mirroring the desktop console. Against an older host that predates the
/// chapter command it degrades to reference-only staging.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/bible_books.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';

class ScriptureTab extends StatefulWidget {
  final LiveController live;
  const ScriptureTab({super.key, required this.live});

  @override
  State<ScriptureTab> createState() => _ScriptureTabState();
}

class _ScriptureTabState extends State<ScriptureTab> {
  final _ctrl = TextEditingController();
  List<String> _suggestions = const [];
  String _translation = 'KJV';
  ChapterResult? _chapter;
  bool _loading = false;
  bool _fetchFailed = false; // last fetch returned no chapter (old host / bad ref)
  bool _triedInitial = false;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onChanged);
    // The operator view isn't available at mount (it arrives on the first poll
    // reply, and the tab is kept alive in an IndexedStack), so listen until it
    // is, then preload the staged/live chapter once so the tab opens with
    // context instead of a blank field.
    widget.live.addListener(_maybeInitialLoad);
    _maybeInitialLoad();
  }

  void _maybeInitialLoad() {
    if (_triedInitial || !mounted) return;
    final view = widget.live.view;
    if (view == null) return;
    _triedInitial = true;
    widget.live.removeListener(_maybeInitialLoad);
    if (view.translations.isNotEmpty &&
        !view.translations.contains(_translation)) {
      _translation = view.translations.first;
    }
    final ref = view.stagedScripture ?? view.liveScripture;
    if (ref != null) _load(ref);
  }

  void _onChanged() {
    final next = suggestBooks(_ctrl.text);
    final changed = next.length != _suggestions.length ||
        (next.isNotEmpty && next.first != _suggestions.first);
    if (changed) setState(() => _suggestions = next);
  }

  void _pickBook(String book) {
    _ctrl.text = '$book ';
    _ctrl.selection = TextSelection.collapsed(offset: _ctrl.text.length);
    setState(() => _suggestions = const []);
  }

  Future<void> _load(String reference, {String? asTranslation}) async {
    final ref = reference.trim();
    if (_loading || ref.isEmpty) return;
    setState(() => _loading = true);
    final result = await widget.live
        .fetchChapter(ref, translation: asTranslation ?? _translation);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _suggestions = const [];
      if (result != null) {
        _chapter = result;
        _translation = result.translation; // host is authoritative on the code
        _fetchFailed = false;
      } else {
        _fetchFailed = true;
      }
    });
    if (result != null) {
      // Sync the field to the chapter actually shown, so ‹ › paging and the
      // field never disagree.
      _setField('${result.bookName} ${result.chapter}');
    } else if (_chapter != null) {
      // A failed lookup while a chapter is displayed keeps that chapter on
      // screen — report the miss and re-sync the field rather than failing
      // silently (and leaving the picker/field pointing at the wrong place).
      _setField('${_chapter!.bookName} ${_chapter!.chapter}');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Couldn’t load “$ref”.'),
        duration: const Duration(seconds: 2),
      ));
    }
  }

  void _setField(String text) {
    _ctrl.text = text;
    _ctrl.selection = TextSelection.collapsed(offset: text.length);
  }

  void _onSubmit() {
    final ref = _ctrl.text.trim();
    if (ref.isEmpty) return;
    FocusScope.of(context).unfocus();
    _load(ref);
  }

  void _setTranslation(String code) {
    if (code == _translation) return;
    final ch = _chapter;
    if (ch != null) {
      // Commit the new code only if the reload succeeds (via result.translation
      // in _load); on failure _translation is untouched, so the picker reverts
      // in step with the chapter still on screen.
      _load('${ch.bookName} ${ch.chapter}', asTranslation: code);
    } else {
      setState(() => _translation = code);
    }
  }

  // A verse reference in the browsed chapter, e.g. "Romans 8:28".
  String _verseRef(VerseView v) =>
      v.reference(_chapter!.bookName, _chapter!.chapter);

  void _stageVerse(VerseView v) =>
      widget.live.act(cmdStageScripture(_verseRef(v), translation: _translation));

  void _liveVerse(VerseView v) => widget.live
      .stageScriptureAndGoLive(_verseRef(v), translation: _translation);

  @override
  void dispose() {
    widget.live.removeListener(_maybeInitialLoad);
    _ctrl.removeListener(_onChanged);
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Scripture search/stage requires the SearchScripture capability (Producer/
    // Assistant). A role without it (Viewer) gets a read-only notice, no field.
    if (!widget.live.can(Capability.searchScripture)) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('Scripture control is not part of your role.',
              textAlign: TextAlign.center,
              style: TextStyle(color: DesignTokens.textMuted)),
        ),
      );
    }
    final view = widget.live.view;
    final options =
        (view?.translations.isNotEmpty ?? false) ? view!.translations : ['KJV'];
    final current = options.contains(_translation) ? _translation : options.first;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Controls: translation picker + reference/search field.
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
          child: Row(
            children: [
              _TranslationPicker(
                  current: current, options: options, onPick: _setTranslation),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  textInputAction: TextInputAction.search,
                  style: const TextStyle(color: DesignTokens.textPrimary),
                  decoration: InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: DesignTokens.bgBase,
                    hintText: 'Reference — e.g. gen 1 1',
                    hintStyle: const TextStyle(color: DesignTokens.textMuted),
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.search,
                          size: 20, color: DesignTokens.textMuted),
                      tooltip: 'Browse chapter',
                      onPressed: _onSubmit,
                    ),
                  ),
                  onSubmitted: (_) => _onSubmit(),
                ),
              ),
            ],
          ),
        ),
        if (_suggestions.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
            child: Wrap(
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
          ),
        if (_loading)
          const LinearProgressIndicator(
              minHeight: 2, color: DesignTokens.accentBrand),
        if (_chapter != null) _chapterNav(_chapter!),
        Expanded(child: _body(view)),
        const Padding(
          padding: EdgeInsets.fromLTRB(14, 6, 14, 12),
          child: Text('Tap a verse to stage · double-tap to send live',
              style: TextStyle(fontSize: 11, color: DesignTokens.textMuted)),
        ),
      ],
    );
  }

  Widget _chapterNav(ChapterResult ch) => Padding(
        padding: const EdgeInsets.fromLTRB(14, 4, 14, 6),
        child: Row(
          children: [
            _NavBtn(
                glyph: '‹',
                label: 'Previous chapter',
                onTap: ch.prevRef == null ? null : () => _load(ch.prevRef!)),
            Expanded(
              child: Text(ch.heading,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: DesignTokens.textPrimary)),
            ),
            _NavBtn(
                glyph: '›',
                label: 'Next chapter',
                onTap: ch.nextRef == null ? null : () => _load(ch.nextRef!)),
          ],
        ),
      );

  Widget _body(OperatorStateView? view) {
    final ch = _chapter;
    if (ch != null) {
      return ListView.builder(
        padding: const EdgeInsets.fromLTRB(14, 2, 14, 2),
        itemCount: ch.verses.length,
        itemBuilder: (context, i) {
          final v = ch.verses[i];
          final ref = _verseRef(v);
          final staged = view?.stagedScripture == ref;
          final live = view?.liveScripture == ref;
          return _VerseRow(
            verse: v,
            staged: staged,
            live: live,
            onTap: () => _stageVerse(v),
            onDoubleTap: () => _liveVerse(v),
          );
        },
      );
    }
    if (_fetchFailed) return _fallback();
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text('Type a reference above to browse its chapter.',
            textAlign: TextAlign.center,
            style: TextStyle(color: DesignTokens.textMuted)),
      ),
    );
  }

  /// Old-host / bad-reference fallback: stage the typed reference directly.
  Widget _fallback() => Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                  'Couldn’t load that chapter here. You can still stage the '
                  'reference directly.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: DesignTokens.textMuted, fontSize: 13)),
              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  OutlinedButton(
                    onPressed: () {
                      final ref = _ctrl.text.trim();
                      if (ref.isEmpty) return;
                      widget.live.act(
                          cmdStageScripture(ref, translation: _translation));
                    },
                    child: const Text('Stage'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    style: FilledButton.styleFrom(
                        backgroundColor: DesignTokens.previewFill),
                    onPressed: () {
                      final ref = _ctrl.text.trim();
                      if (ref.isEmpty) return;
                      widget.live.stageScriptureAndGoLive(ref,
                          translation: _translation);
                    },
                    child: const Text('Live'),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
}

class _TranslationPicker extends StatelessWidget {
  final String current;
  final List<String> options;
  final ValueChanged<String> onPick;
  const _TranslationPicker(
      {required this.current, required this.options, required this.onPick});

  @override
  Widget build(BuildContext context) => PopupMenuButton<String>(
        tooltip: 'Translation',
        color: DesignTokens.bgPanel,
        initialValue: current,
        onSelected: onPick,
        itemBuilder: (context) => [
          for (final code in options)
            PopupMenuItem<String>(
              value: code,
              child: Text(code,
                  style: const TextStyle(color: DesignTokens.textPrimary)),
            ),
        ],
        child: Container(
          height: 40,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: DesignTokens.bgBase,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: DesignTokens.border),
          ),
          child: Row(
            children: [
              Text(current,
                  style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: DesignTokens.textPrimary)),
              const Icon(Icons.arrow_drop_down,
                  size: 18, color: DesignTokens.textMuted),
            ],
          ),
        ),
      );
}

class _NavBtn extends StatelessWidget {
  final String glyph;
  final String label;
  final VoidCallback? onTap;
  const _NavBtn({required this.glyph, required this.label, this.onTap});

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      excludeSemantics: true,
      child: Material(
        color: DesignTokens.bgPanel,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: onTap,
          child: Container(
            width: 40,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              border: Border.all(color: DesignTokens.border),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(glyph,
                style: TextStyle(
                    fontSize: 20,
                    color: enabled
                        ? DesignTokens.textPrimary
                        : DesignTokens.textMuted)),
          ),
        ),
      ),
    );
  }
}

class _VerseRow extends StatelessWidget {
  final VerseView verse;
  final bool staged;
  final bool live;
  final VoidCallback onTap;
  final VoidCallback onDoubleTap;
  const _VerseRow({
    required this.verse,
    required this.staged,
    required this.live,
    required this.onTap,
    required this.onDoubleTap,
  });

  @override
  Widget build(BuildContext context) {
    // The staged verse gets the green preview box; a live verse the red one —
    // canonical colour + the surrounding number/label carry the meaning too.
    // Live wins the colour when a verse is both staged AND live — after go-live
    // the host reports staged==live for the same reference, and the operator
    // needs the red "on the audience" cue (matches plan_tab's ordering).
    final Color? border = live
        ? DesignTokens.liveInk
        : staged
            ? DesignTokens.previewInk
            : null;
    final Color? fill = live
        ? DesignTokens.liveFill.withValues(alpha: 0.12)
        : staged
            ? DesignTokens.previewFill.withValues(alpha: 0.12)
            : null;
    return Semantics(
      button: true,
      label: 'Verse ${verse.number}'
          '${live ? ", live" : staged ? ", staged" : ""}',
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Material(
          color: fill ?? Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: onTap,
            onDoubleTap: onDoubleTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              decoration: BoxDecoration(
                border: border == null ? null : Border.all(color: border),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 26,
                    child: Text('${verse.number}',
                        style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: DesignTokens.warnInk)),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(verse.text,
                        style: const TextStyle(
                            fontSize: 14,
                            height: 1.35,
                            color: DesignTokens.textPrimary)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
