/// Scripture tab — the desktop chapter browser on the phone, Design 2.0
/// (Figma `343:128`). Type/pick a reference → the host sends the whole chapter
/// over the wire (`get_chapter`) → the numbered verse list renders, and a single
/// tap stages a verse in Preview while a double-tap sends it live — mirroring
/// the desktop console. Against an older host that predates the chapter command
/// it degrades to reference-only staging.
///
/// Gold is the scripture signal here and nowhere else (handoff §2): the chapter
/// heading, the translation pill and every verse number are `d2Gold`. Gold never
/// means status — staged/live are still green/red, and both carry a glyph.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/bible_books.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import '../detections_view.dart';
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
    final changed =
        next.length != _suggestions.length ||
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
    final result = await widget.live.fetchChapter(
      ref,
      translation: asTranslation ?? _translation,
    );
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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Couldn’t load “$ref”.'),
          duration: const Duration(seconds: 2),
        ),
      );
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

  void _stageVerse(VerseView v) => widget.live.act(
    cmdStageScripture(_verseRef(v), translation: _translation),
  );

  void _liveVerse(VerseView v) => widget.live.stageScriptureAndGoLive(
    _verseRef(v),
    translation: _translation,
  );

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
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(SelahSpace.section),
          child: Text(
            'Scripture control is not part of your role.',
            textAlign: TextAlign.center,
            style: SelahType.body.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
      );
    }
    final view = widget.live.view;
    final options = (view?.translations.isNotEmpty ?? false)
        ? view!.translations
        : ['KJV'];
    final current = options.contains(_translation)
        ? _translation
        : options.first;
    // A stage/go-live command is still on the wire — a tap must not accept a
    // second one while it is unresolved (17tnw2ay2pq, follow-up to the
    // act()-level guard in 17tnw2ay2kk). This tab does not gate on `syncing`
    // (act() already backstops that, see live_controller.dart's own note),
    // but `busy` still clears well short of needing a reconnect (bounded by
    // the in-flight command's own round trip and the refresh() that follows
    // it — up to roughly two `commandTimeout` windows at worst, not "well
    // under" one; see session.dart), so it is worth surfacing here rather
    // than leaving every tap silently dropped.
    final busy = widget.live.busy;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // The human-in-the-loop gate (FR-095): auto-detected scripture the
        // operator must approve before it can go live (never auto-displays,
        // FR-115). Only a FIXED-HEIGHT banner lives here — the cards themselves
        // are on a scrolling route. Every child of this Column must stay
        // bounded; the old inline card stack grew with the detection count
        // until it starved the Expanded verse list and overflowed the tab
        // (86ak188mz).
        if (view != null && view.detections.isNotEmpty)
          _DetectionBanner(
            count: view.detections.length,
            onTap: () => DetectionsView.open(context, widget.live),
          ),
        // Controls: reference/search field + translation pill.
        Padding(
          padding: const EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            SelahSpace.md,
            SelahSpace.gutter,
            SelahSpace.xs,
          ),
          child: Row(
            children: [
              Expanded(
                child: SelahInput(
                  controller: _ctrl,
                  textInputAction: TextInputAction.search,
                  hint: 'Reference — e.g. gen 1 1',
                  prefix: const Icon(
                    Icons.search,
                    size: 20,
                    color: DesignTokens.d2TextSecondary,
                  ),
                  suffix: IconButton(
                    icon: const Icon(
                      Icons.arrow_forward,
                      size: 20,
                      color: DesignTokens.d2TextSecondary,
                    ),
                    tooltip: 'Browse chapter',
                    onPressed: _onSubmit,
                  ),
                  onSubmitted: (_) => _onSubmit(),
                ),
              ),
              const SizedBox(width: SelahSpace.sm),
              _TranslationPicker(
                current: current,
                options: options,
                onPick: _setTranslation,
              ),
            ],
          ),
        ),
        if (_suggestions.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              SelahSpace.gutter,
              0,
              SelahSpace.gutter,
              SelahSpace.xs,
            ),
            child: Wrap(
              spacing: SelahSpace.xs,
              runSpacing: SelahSpace.xs,
              children: [
                for (final b in _suggestions)
                  ActionChip(
                    label: Text(b),
                    backgroundColor: DesignTokens.d2Surface,
                    side: const BorderSide(color: DesignTokens.d2Border),
                    labelStyle: SelahType.bodySmall.copyWith(
                      color: DesignTokens.d2Text,
                    ),
                    onPressed: () => _pickBook(b),
                  ),
              ],
            ),
          ),
        if (_loading)
          const LinearProgressIndicator(
            minHeight: 2,
            color: DesignTokens.d2Primary,
          ),
        if (_chapter != null) _chapterNav(_chapter!),
        Expanded(child: _body(view, busy)),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            SelahSpace.xs,
            SelahSpace.gutter,
            SelahSpace.md,
          ),
          child: Text(
            busy
                ? 'Sending… controls are disabled until the command finishes.'
                : 'Tap a verse to stage · double-tap to send live',
            style: SelahType.caption.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
      ],
    );
  }

  /// The chapter heading in gold (the frame's `ISAIAH 61 · KJV` overline), with
  /// the ‹ › chapter pager either side.
  Widget _chapterNav(ChapterResult ch) => Padding(
    padding: const EdgeInsets.fromLTRB(
      SelahSpace.gutter,
      4,
      SelahSpace.gutter,
      SelahSpace.xs,
    ),
    child: Row(
      children: [
        _NavBtn(
          icon: Icons.chevron_left,
          label: 'Previous chapter',
          onTap: ch.prevRef == null ? null : () => _load(ch.prevRef!),
        ),
        Expanded(
          child: Text(
            '${ch.heading.toUpperCase()} · $_translation',
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            // Spec §4.5 measures this overline in `d2TextSecondary`, not
            // gold: the gold budget on this screen is spent on the verse
            // NUMBERS and the translation pill, which is where a reader looks
            // to place a verse. A gold heading as well turns the signal into a
            // decoration.
            style: SelahType.overline.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
        _NavBtn(
          icon: Icons.chevron_right,
          label: 'Next chapter',
          onTap: ch.nextRef == null ? null : () => _load(ch.nextRef!),
        ),
      ],
    ),
  );

  Widget _body(OperatorStateView? view, bool busy) {
    final ch = _chapter;
    if (ch != null) {
      return ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          SelahSpace.gutter,
          2,
          SelahSpace.gutter,
          2,
        ),
        itemCount: ch.verses.length,
        separatorBuilder: (context, i) => const SizedBox(height: SelahSpace.sm),
        itemBuilder: (context, i) {
          final v = ch.verses[i];
          final ref = _verseRef(v);
          final staged = view?.stagedScripture == ref;
          final live = view?.liveScripture == ref;
          return _VerseRow(
            verse: v,
            staged: staged,
            live: live,
            onTap: busy ? null : () => _stageVerse(v),
            onDoubleTap: busy ? null : () => _liveVerse(v),
          );
        },
      );
    }
    if (_fetchFailed) return _fallback(busy);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(SelahSpace.section),
        child: Text(
          'Type a reference above to browse its chapter.',
          textAlign: TextAlign.center,
          style: SelahType.body.copyWith(color: DesignTokens.d2TextSecondary),
        ),
      ),
    );
  }

  /// Old-host / bad-reference fallback: stage the typed reference directly.
  Widget _fallback(bool busy) => Center(
    child: Padding(
      padding: const EdgeInsets.all(SelahSpace.gutter),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Couldn’t load that chapter here. You can still stage the '
            'reference directly.',
            textAlign: TextAlign.center,
            style: SelahType.bodySmall.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
          const SizedBox(height: SelahSpace.lg),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SelahButton(
                label: 'Stage',
                disabledReason: 'sending…',
                onPressed: busy
                    ? null
                    : () {
                        final ref = _ctrl.text.trim();
                        if (ref.isEmpty) return;
                        widget.live.act(
                          cmdStageScripture(ref, translation: _translation),
                        );
                      },
              ),
              const SizedBox(width: SelahSpace.sm),
              SelahButton(
                label: 'Live',
                variant: SelahButtonVariant.success,
                disabledReason: 'sending…',
                onPressed: busy
                    ? null
                    : () {
                        final ref = _ctrl.text.trim();
                        if (ref.isEmpty) return;
                        widget.live.stageScriptureAndGoLive(
                          ref,
                          translation: _translation,
                        );
                      },
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

/// The entry point to the detection-approval queue (FR-095).
///
/// "Fixed height" here means fixed **with respect to the detection count** —
/// this is the bounded replacement for the inline card stack that grew with N
/// until it starved the verse list and overflowed the tab (86ak188mz). It is
/// deliberately NOT a fixed `SizedBox`: a hard pixel height would clip the
/// label the moment the operator raises their system font size, trading an
/// overflow bug for a legibility bug on the same screen. So: a 48dp MINIMUM
/// around intrinsic content, which grows with the text scale and stays constant
/// in N at every scale.
///
/// Never disabled, including while syncing — reading the queue is always safe;
/// it is Approve/Reject that are gated. Blocking navigation during a reconnect
/// would strand the operator with a count they cannot inspect.
class _DetectionBanner extends StatelessWidget {
  final int count;
  final VoidCallback onTap;
  const _DetectionBanner({required this.count, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final label = count == 1
        ? '1 verse needs approval'
        : '$count verses need approval';
    final tone = SelahToneStyle.of(SelahTone.warn);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        SelahSpace.gutter,
        SelahSpace.md,
        SelahSpace.gutter,
        0,
      ),
      child: Semantics(
        button: true,
        label: label,
        hint: 'Opens the approval list',
        excludeSemantics: true,
        child: Material(
          color: tone.fill,
          borderRadius: BorderRadius.circular(SelahRadius.row),
          child: InkWell(
            borderRadius: BorderRadius.circular(SelahRadius.row),
            onTap: onTap,
            child: Container(
              constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
              padding: const EdgeInsets.symmetric(
                horizontal: SelahSpace.md,
                vertical: SelahSpace.sm,
              ),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(SelahRadius.row),
                border: Border.all(color: tone.border),
              ),
              child: Row(
            children: [
                  // Real icons, not the ⚠ / › glyphs: U+26A0 has an emoji
                  // presentation on iOS that ignores the ink colour, and glyph
                  // metrics differ across Android OEM fonts.
                  Icon(
                    Icons.warning_amber_rounded,
                    size: 18,
                    color: tone.ink,
                  ),
                  const SizedBox(width: SelahSpace.xs),
                  Expanded(
                    child: Text(
                      label,
                      maxLines: 1,
                      softWrap: false,
                      overflow: TextOverflow.ellipsis,
                      style: SelahType.bodySmall.copyWith(
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.2,
                        color: tone.ink,
                      ),
                    ),
                  ),
                  Icon(Icons.chevron_right, size: 20, color: tone.ink),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The translation pill (`KJV ▾`) — gold, because the translation is part of the
/// scripture reference.
class _TranslationPicker extends StatelessWidget {
  final String current;
  final List<String> options;
  final ValueChanged<String> onPick;
  const _TranslationPicker({
    required this.current,
    required this.options,
    required this.onPick,
  });

  @override
  Widget build(BuildContext context) => PopupMenuButton<String>(
    tooltip: 'Translation',
    initialValue: current,
    onSelected: onPick,
    itemBuilder: (context) => [
      for (final code in options)
        PopupMenuItem<String>(value: code, child: Text(code)),
    ],
    child: Container(
      height: kSelahMinTouchTarget,
      padding: const EdgeInsets.symmetric(horizontal: SelahSpace.md),
      decoration: BoxDecoration(
        color: DesignTokens.d2Surface,
        borderRadius: BorderRadius.circular(SelahRadius.control),
        border: Border.all(color: DesignTokens.d2Border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            current,
            style: SelahType.label.copyWith(
              fontSize: 13,
              color: DesignTokens.d2Gold,
            ),
          ),
          const Icon(
            Icons.arrow_drop_down,
            size: 18,
            color: DesignTokens.d2Gold,
          ),
        ],
      ),
    ),
  );
}

class _NavBtn extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  const _NavBtn({required this.icon, required this.label, this.onTap});

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      excludeSemantics: true,
      child: Opacity(
        opacity: enabled ? 1 : 0.4,
        child: Material(
          color: DesignTokens.d2Elevated,
          borderRadius: BorderRadius.circular(SelahRadius.badge),
          child: InkWell(
            borderRadius: BorderRadius.circular(SelahRadius.badge),
            onTap: onTap,
            child: Container(
              width: kSelahMinTouchTarget,
              height: 36,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border.all(color: DesignTokens.d2Border),
                borderRadius: BorderRadius.circular(SelahRadius.badge),
              ),
              child: Icon(icon, size: 20, color: DesignTokens.d2Text),
            ),
          ),
        ),
      ),
    );
  }
}

/// One verse row: gold number, verse text, and a trailing glyph that says what a
/// tap will do (→ stage) or what already happened (✓ staged / ● live).
///
/// The staged/live tint is never the only cue — the trailing glyph and the
/// semantic label carry the same fact (WCAG 1.4.1).
class _VerseRow extends StatelessWidget {
  final VerseView verse;
  final bool staged;
  final bool live;
  final VoidCallback? onTap;
  final VoidCallback? onDoubleTap;
  const _VerseRow({
    required this.verse,
    required this.staged,
    required this.live,
    required this.onTap,
    required this.onDoubleTap,
  });

  @override
  Widget build(BuildContext context) {
    // Live wins the colour when a verse is both staged AND live — after go-live
    // the host reports staged==live for the same reference, and the operator
    // needs the red "on the audience" cue (matches plan_tab's ordering).
    final state = live
        ? SelahRowState.live
        : staged
        ? SelahRowState.staged
        : SelahRowState.normal;
    return SelahListRow(
      state: state,
      onTap: onTap,
      onDoubleTap: onDoubleTap,
      padding: const EdgeInsets.symmetric(
        horizontal: SelahSpace.md,
        vertical: SelahSpace.md,
      ),
      semanticLabel:
          'Verse ${verse.number}'
          '${live
              ? ", live"
              : staged
              ? ", staged"
              : ""}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ≥26 wide: the frame draws 16 and a two-digit verse number wraps
          // onto a second line there (spec §4.5, measured on `355:239`).
          SizedBox(
            width: 26,
            child: Text(
              '${verse.number}',
              style: SelahType.bodySmall.copyWith(
                fontWeight: FontWeight.w700,
                color: DesignTokens.d2Gold,
              ),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              verse.text,
              style: SelahType.body.copyWith(color: DesignTokens.d2Text),
            ),
          ),
          const SizedBox(width: SelahSpace.xs),
          _StageAffordance(live: live, staged: staged),
        ],
      ),
    );
  }
}

/// The trailing stage affordance on a verse row (spec §4.5): `→` on an
/// `elevated` well by default, a solid `d2Preview` pill with a `d2PreviewSoft`
/// check once staged, and the live dot once it is on the audience screen.
///
/// It is not an independent tap target — the whole row is tappable — so it is
/// excluded from semantics; the row's own label already says ", staged" /
/// ", live".
class _StageAffordance extends StatelessWidget {
  final bool live;
  final bool staged;
  const _StageAffordance({required this.live, required this.staged});

  @override
  Widget build(BuildContext context) {
    final (IconData glyph, Color fill, Color ink) = live
        ? (Icons.circle, DesignTokens.d2LiveSoft, DesignTokens.d2Live)
        : staged
        ? (
            Icons.check,
            DesignTokens.d2Preview,
            DesignTokens.d2PreviewSoft,
          )
        : (
            Icons.arrow_forward,
            DesignTokens.d2Elevated,
            DesignTokens.d2TextSecondary,
          );
    return ExcludeSemantics(
      child: Container(
        width: 28,
        height: 28,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: fill,
          borderRadius: BorderRadius.circular(SelahRadius.badge),
        ),
        child: Icon(glyph, size: live ? 10 : 16, color: ink),
      ),
    );
  }
}
