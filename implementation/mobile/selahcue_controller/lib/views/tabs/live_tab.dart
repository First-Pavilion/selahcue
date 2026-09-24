/// Live tab — the primary control surface, Design 2.0 (MOBILE-2.0-SPEC §4.3;
/// Figma `342:189`, `363:149`).
///
/// Order is the shipped one, which the spec explicitly keeps: PREVIEW monitor →
/// transport → LIVE monitor. That puts GO LIVE under the thumb, between the two
/// things it moves content from and to. The role-home frames draw the monitors
/// side by side even on a phone; the spec resolves in favour of the stacked
/// order (§4.3).
///
/// The core invariant is visual here as well as behavioural: staging never
/// changes Live; only GO LIVE does.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import '../widgets/mobile_widgets.dart';
import '../widgets/responsive.dart';

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
    String? nameAt(int? i) =>
        (i != null && i >= 0 && i < items.length) ? items[i].title : null;
    String? kindAt(int? i) =>
        (i != null && i >= 0 && i < items.length) ? items[i].kind : null;

    // Preview: a staged plan item, or a staged scripture reference.
    final previewIsScripture = view.stagedScripture != null;
    final previewTitle = nameAt(view.stagedIndex) ?? view.stagedScripture;
    final previewCap = previewIsScripture
        ? 'scripture · staged'
        : (kindAt(view.stagedIndex) != null
              ? '${kindAt(view.stagedIndex)!.toLowerCase()} · staged'
              : null);

    // Live: a live plan item, a live scripture, or a removed free slide.
    final liveIsScripture = view.liveScripture != null;
    final liveTitle =
        nameAt(view.liveIndex) ?? view.liveScripture ?? view.liveFreeText;
    final liveCap = liveIsScripture
        ? 'scripture · main output'
        : (kindAt(view.liveIndex) != null
              ? '${kindAt(view.liveIndex)!.toLowerCase()} · main output'
              : null);

    final previewCard = OutputCard(
      header: 'PREVIEW',
      tone: SelahTone.preview,
      title: previewTitle,
      caption: previewCap,
      idle: 'Nothing staged',
      scripture: previewIsScripture,
    );
    final liveCard = OutputCard(
      header: 'LIVE',
      tone: SelahTone.live,
      title: liveTitle,
      caption: liveCap,
      idle: 'Output idle',
      scripture: liveIsScripture,
      blackout: view.blackout,
    );

    // Transport is role-gated: navigate → Prev/Next; goLive → GO LIVE.
    // A role with neither (Viewer) gets read-only cards, no transport row.
    // While the controller cannot prove what is on the audience screen, the
    // transport is disabled rather than hidden — the control is not forbidden,
    // it is momentarily untrustworthy (FR-097, COMPONENT-SPECS §12). Role gating
    // below still HIDES, which is a different thing.
    final syncing = live.syncing;
    // Disabled while state is unknown (syncing) or while a command any of
    // these controls sent is still on the wire (busy) — a control must not
    // look tappable while a tap on it would only be dropped.
    final disabled = syncing || live.busy;
    final disabledReason =
        syncing ? 'unavailable while reconnecting' : 'sending…';
    final canNavigate = live.can(Capability.navigate);
    final canGoLive = live.can(Capability.goLive);
    final Widget? transport = (canNavigate || canGoLive)
        ? Row(
            children: [
              if (canNavigate) ...[
                SizedBox(
                  width: 64,
                  child: SelahButton(
                    label: '',
                    icon: Icons.chevron_left,
                    semanticLabel: 'Previous item',
                    disabledReason: disabledReason,
                    height: 54,
                    onPressed: disabled ? null : () => live.act(cmdPrevious()),
                  ),
                ),
                const SizedBox(width: SelahSpace.xs),
              ],
              if (canGoLive)
                Expanded(
                  child: SelahButton(
                    label: 'GO LIVE',
                    semanticLabel: 'Go live',
                    disabledReason: disabledReason,
                    variant: SelahButtonVariant.success,
                    height: 54,
                    // An audience-affecting commit — one of the three places
                    // haptics fire (spec §6.7).
                    haptic: true,
                    textStyle: SelahType.cta,
                    onPressed: disabled ? null : () => live.act(cmdGoLive()),
                  ),
                )
              else
                const Spacer(),
              if (canNavigate) ...[
                const SizedBox(width: SelahSpace.xs),
                SizedBox(
                  width: 64,
                  child: SelahButton(
                    label: '',
                    icon: Icons.chevron_right,
                    semanticLabel: 'Next item',
                    disabledReason: disabledReason,
                    height: 54,
                    onPressed: disabled ? null : () => live.act(cmdNext()),
                  ),
                ),
              ],
            ],
          )
        : null;

    // UP NEXT only when nothing is staged: when something IS staged the Preview
    // monitor above already names it, and two cards naming the same item read as
    // two different queued things.
    final nextIndex = _nextIndex(view);
    final showNext = previewTitle == null && nextIndex != null;

    final hasTranscript =
        view.transcript.isNotEmpty ||
        (view.partialTranscript?.isNotEmpty ?? false);

    // On a wide surface (tablet/landscape) the monitors sit side by side; on a
    // phone they stack with the transport between them (spec §4.3).
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= kSideBySideBreakpoint;
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            SelahSpace.lg,
            SelahSpace.gutter,
            SelahSpace.gutter,
          ),
          children: [
            if (wide) ...[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: previewCard),
                  const SizedBox(width: SelahSpace.md),
                  Expanded(child: liveCard),
                ],
              ),
              const SizedBox(height: SelahSpace.lg),
              ?transport,
            ] else ...[
              previewCard,
              const SizedBox(height: SelahSpace.lg),
              if (transport != null) ...[
                transport,
                const SizedBox(height: SelahSpace.lg),
              ],
              liveCard,
            ],
            if (showNext) ...[
              const SizedBox(height: SelahSpace.lg),
              UpNextCard(
                title: view.items[nextIndex].title,
                scripture:
                    view.items[nextIndex].kind.toLowerCase() == 'scripture',
              ),
            ],
            // Live transcript (read-only) — every role can watch it (Monitor).
            if (hasTranscript) _transcriptSection(view),
          ],
        );
      },
    );
  }

  /// The read-only live-transcript panel: the last few finalised segments plus
  /// the in-progress (italic) partial line.
  Widget _transcriptSection(OperatorStateView v) {
    final recent = v.transcript.length > 6
        ? v.transcript.sublist(v.transcript.length - 6)
        : v.transcript;
    return Padding(
      padding: const EdgeInsets.only(top: SelahSpace.lg),
      child: SelahCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SectionLabel('LIVE TRANSCRIPT'),
            const SizedBox(height: SelahSpace.xs),
            for (final s in recent)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  s.text,
                  style: SelahType.bodySmall.copyWith(
                    height: 1.35,
                    color: DesignTokens.d2Text,
                  ),
                ),
              ),
            if (v.partialTranscript?.isNotEmpty ?? false)
              Text(
                v.partialTranscript!,
                style: SelahType.bodySmall.copyWith(
                  height: 1.35,
                  fontStyle: FontStyle.italic,
                  color: DesignTokens.d2TextSecondary,
                ),
              ),
          ],
        ),
      ),
    );
  }

  int? _nextIndex(OperatorStateView v) {
    final cur = v.liveIndex;
    if (cur == null) return v.items.isNotEmpty ? 0 : null;
    final n = cur + 1;
    return (n < v.items.length) ? n : null;
  }
}
