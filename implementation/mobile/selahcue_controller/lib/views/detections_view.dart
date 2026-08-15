/// The detection-approval queue (FR-095) as its own full-screen route.
///
/// The human-in-the-loop gate: auto-detected scripture the operator must approve
/// before it can go live (it never auto-displays, FR-115). Approve stages the
/// verse in Preview (`ApproveDetection`); Reject drops it (`DismissDetection`).
///
/// These cards used to be stacked inline at the top of the Scripture tab, where
/// they were an UNBOUNDED, non-flexing sibling of the verse list: past ~5
/// detections they ate the whole viewport and the tab threw a RenderFlex
/// overflow, taking the translation picker and the reference field with it
/// (86ak188mz). Here the list SCROLLS, so no number of detections can overflow,
/// and the tab keeps only a fixed-height banner pointing at this route.
///
/// Because this is a PUSHED route it covers `ControllerView.body`, so it must
/// carry its own copies of the two things that live there and matter on any
/// screen an operator can sit on for a whole sermon: the emergency strip
/// (always-on Blackout/Clear is a testable invariant, UX-CANONICAL §3) and the
/// connection banner (otherwise Approve silently does nothing during a
/// reconnect, with no explanation on screen). Both reuse the shared widgets
/// rather than forking them. See `docs/design/DETECTIONS-VIEW-spec.md` §7.3/§7.6.
library;

import 'package:flutter/material.dart';

import '../controllers/live_controller.dart';
import '../models/design_tokens.dart';
import '../models/protocol.dart';
import '../models/rbac.dart';
import '../models/settings.dart';
import 'widgets/mobile_widgets.dart';
import 'widgets/responsive.dart';

/// At and above this text scale the Approve/Reject pair stacks instead of
/// sitting side by side. A hard threshold rather than a `LayoutBuilder` guess so
/// the boundary is exactly testable: 1.29 → side by side, 1.30 → stacked.
const double kStackActionsAtTextScale = 1.3;

class DetectionsView extends StatefulWidget {
  final LiveController live;
  const DetectionsView({super.key, required this.live});

  /// Push the approval queue over the current tab. A plain [MaterialPageRoute]
  /// on purpose — `main.dart` already installs a zero-duration transition
  /// builder for reduced motion, which a hand-rolled `PageRouteBuilder` would
  /// bypass.
  static Future<void> open(BuildContext context, LiveController live) =>
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          settings: const RouteSettings(name: 'detections'),
          builder: (_) => DetectionsView(live: live),
        ),
      );

  @override
  State<DetectionsView> createState() => _DetectionsViewState();
}

class _DetectionsViewState extends State<DetectionsView> {
  /// One-shot: a stream of notifications must not be able to pop twice.
  bool _popped = false;

  @override
  void initState() {
    super.initState();
    widget.live.addListener(_gate);
    // Belt-and-braces: if the route is somehow entered without the capability,
    // leave on the next frame rather than waiting for a notification.
    WidgetsBinding.instance.addPostFrameCallback((_) => _gate());
  }

  @override
  void dispose() {
    widget.live.removeListener(_gate);
    super.dispose();
  }

  /// May this device still act on detections at all? Mirrors the gate the
  /// Scripture tab applies: Approve/Reject both require SearchScripture, and a
  /// revoked device may do nothing.
  bool get _allowed =>
      !widget.live.revoked && widget.live.can(Capability.searchScripture);

  /// Leave the route the moment approval stops being permitted — an admin
  /// revoked the device, or a reconnect re-roled it below SearchScripture.
  ///
  /// Deliberately NOT triggered by the queue draining to empty: yanking
  /// navigation out from under a thumb that is already descending on the next
  /// Approve lands the tap on whatever the Scripture tab has at those
  /// coordinates — plausibly a verse row, whose double-tap sends a verse live.
  /// An empty screen the operator leaves themselves is the safer failure.
  ///
  /// Never fires on `syncing`/`reconnecting` either: a dropped link is
  /// temporary, so we disable rather than navigate.
  void _gate() {
    if (_popped || !mounted || _allowed) return;
    // If a dialog or the licence page is above us, popping would dismiss THAT.
    // Popping the wrong route is worse than popping late — retry on the next
    // notification (the 1s poll) or the next frame.
    if (ModalRoute.of(context)?.isCurrent != true) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _gate());
      return;
    }
    final nav = Navigator.of(context);
    if (!nav.canPop()) return;
    _popped = true;
    nav.pop();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: widget.live,
        builder: (context, _) {
          final live = widget.live;
          final detections = live.view?.detections ?? const <DetectionView>[];
          // Controls stay disabled until we can prove what is on the audience
          // screen right now (FR-097) — a silent no-op is worse than a greyed
          // button, so the banner above says why.
          final gated = live.syncing;
          return Scaffold(
            backgroundColor: DesignTokens.bgBase,
            appBar: AppBar(
              backgroundColor: DesignTokens.bgPanel,
              elevation: 0,
              titleSpacing: 16,
              iconTheme: const IconThemeData(color: DesignTokens.textMuted),
              title: Semantics(
                namesRoute: true,
                child: Row(
                  children: [
                    const Flexible(
                      child: Text(
                        'Needs your approval',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: DesignTokens.textPrimary,
                        ),
                      ),
                    ),
                    // Outside the Flexible on purpose: at a large text scale the
                    // WORDS truncate and the number survives, never the reverse.
                    if (detections.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      StatusBadge(
                        text: '${detections.length}',
                        color: DesignTokens.warnFill,
                      ),
                    ],
                  ],
                ),
              ),
            ),
            body: SafeArea(
              top: false,
              child: ResponsiveBody(
                child: Column(
                  children: [
                    ConnectionBanner(live: live),
                    Expanded(
                      child: detections.isEmpty
                          ? const _AllCaughtUp()
                          : ListView.builder(
                              padding:
                                  const EdgeInsets.fromLTRB(14, 12, 14, 20),
                              // +1 for the footnote, which rides as the last
                              // list child so it costs no vertical space once
                              // scrolled past.
                              itemCount: detections.length + 1,
                              itemBuilder: (context, i) => i == detections.length
                                  ? const _Footnote()
                                  : _DetectionCard(
                                      detection: detections[i],
                                      live: live,
                                      gated: gated,
                                    ),
                            ),
                    ),
                    // Always-on emergency chrome. Without this, the approvals
                    // screen would be the ONLY place in the app where an
                    // operator cannot black out the audience — on a screen they
                    // may sit on for an entire sermon. Same role gate
                    // ControllerView applies, so a role holding neither
                    // capability gets no empty strip.
                    if (live.can(Capability.blackout) ||
                        live.can(Capability.clearLive))
                      EmergencyStrip(live: live),
                  ],
                ),
              ),
            ),
          );
        },
      );
}

/// FR-115 is a promise to the operator as much as to the audience: someone who
/// reads "Approve" as "display" will approve and then wait for something that
/// never happens.
class _Footnote extends StatelessWidget {
  const _Footnote();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.fromLTRB(4, 8, 4, 4),
        child: Text(
          'Approving stages the verse in Preview. It does not go on air.',
          style: TextStyle(fontSize: 11, color: DesignTokens.textMuted),
        ),
      );
}

/// The queue drained while the operator was standing here. They stay on the
/// route and leave under their own steam — hence a large, obvious exit rather
/// than only the small back chevron.
class _AllCaughtUp extends StatelessWidget {
  const _AllCaughtUp();

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        // Scrollable so the icon, both lines and the button still reach at a
        // 3.0 text scale on a short landscape viewport.
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: DesignTokens.previewFill.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(28),
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.check_circle_outline,
                  color: DesignTokens.previewInk, size: 28),
            ),
            const SizedBox(height: 18),
            // Focusable header: without it a screen-reader user hears nothing
            // at all when the queue empties under them.
            Semantics(
              header: true,
              child: const Text('All caught up',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: DesignTokens.textPrimary)),
            ),
            const SizedBox(height: 10),
            const Text('No verses are waiting for approval.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: DesignTokens.textMuted)),
            const SizedBox(height: 20),
            OutlinedButton(
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(0, 48),
                side: const BorderSide(color: DesignTokens.border),
                foregroundColor: DesignTokens.textPrimary,
              ),
              onPressed: () => Navigator.of(context).maybePop(),
              child: const Text('Back to Scripture'),
            ),
          ],
        ),
      );
}

/// One pending detection: reference (+ translation) and confidence, the heard
/// text (two lines, ellipsised), and the Approve / Reject pair.
class _DetectionCard extends StatelessWidget {
  final DetectionView detection;
  final LiveController live;

  /// Live state is unknown (reconnecting, or not yet re-read) — actions are
  /// disabled and say so.
  final bool gated;

  const _DetectionCard({
    required this.detection,
    required this.live,
    required this.gated,
  });

  void _act(BuildContext context, Map<String, dynamic> cmd) {
    SettingsScope.maybeOf(context)?.haptic();
    live.act(cmd);
  }

  @override
  Widget build(BuildContext context) {
    final d = detection;
    // Which text the operator is judging matters: the verse below is
    // ellipsised, so the translation belongs next to the reference.
    final reference =
        d.translation.isNotEmpty ? '${d.reference} · ${d.translation}' : d.reference;
    final stacked = MediaQuery.textScalerOf(context).scale(1) >=
        kStackActionsAtTextScale;

    final approve = _ActionButton(
      label: 'Approve',
      semanticLabel: 'Approve ${d.reference}',
      filled: true,
      gated: gated,
      onPressed: () => _act(context, cmdApproveDetection(d.id)),
    );
    final reject = _ActionButton(
      label: 'Reject',
      semanticLabel: 'Reject ${d.reference}',
      filled: false,
      gated: gated,
      onPressed: () => _act(context, cmdDismissDetection(d.id)),
    );

    return Semantics(
      // One swipe stop per detection, not five.
      container: true,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: DesignTokens.bgPanel,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: DesignTokens.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    reference.isEmpty ? 'Unknown reference' : reference,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      fontStyle:
                          reference.isEmpty ? FontStyle.italic : FontStyle.normal,
                      color: reference.isEmpty
                          ? DesignTokens.textMuted
                          : DesignTokens.textPrimary,
                    ),
                  ),
                ),
                if (d.confidence != null) ...[
                  const SizedBox(width: 8),
                  _ConfidencePill(confidence: d.confidence!),
                ],
              ],
            ),
            if (d.text.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(d.text,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 13,
                        height: 1.4,
                        color: DesignTokens.textMuted)),
              ),
            const SizedBox(height: 10),
            // Side by side normally; stacked once the text scale would squeeze
            // the labels, so neither button can overflow horizontally.
            if (stacked)
              Column(
                // Full width each, so a long label has room instead of being
                // squeezed toward an overflow.
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  approve,
                  const SizedBox(height: 10),
                  reject,
                ],
              )
            else
              Row(
                children: [
                  Expanded(child: approve),
                  const SizedBox(width: 8),
                  Expanded(child: reject),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// Confidence is a NEUTRAL quantity, so it is deliberately not green: green
/// means "preview / staged, not on air" everywhere else in the app (UX-CANONICAL
/// §4), and a green `94% MATCH` on a card whose whole point is that the verse is
/// NOT staged inverts that meaning.
class _ConfidencePill extends StatelessWidget {
  final int confidence;
  const _ConfidencePill({required this.confidence});

  @override
  Widget build(BuildContext context) => Semantics(
        // '94% MATCH' is read correctly by TalkBack, but some VoiceOver voices
        // spell the all-caps MATCH letter by letter.
        label: '$confidence percent match',
        excludeSemantics: true,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: DesignTokens.bgBase,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: DesignTokens.border),
          ),
          child: Text('$confidence% MATCH',
              style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                  color: DesignTokens.textMuted)),
        ),
      );
}

/// Approve / Reject. No arm-then-confirm step: unlike Blackout and Clear these
/// never touch the audience output — Approve only stages to Preview and Reject
/// only drops a suggestion — so a confirm would cost a tap per detection during
/// a service and buy no safety.
class _ActionButton extends StatelessWidget {
  final String label;
  final String semanticLabel;
  final bool filled;
  final bool gated;
  final VoidCallback onPressed;

  const _ActionButton({
    required this.label,
    required this.semanticLabel,
    required this.filled,
    required this.gated,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final child = Text(label);
    final button = filled
        ? FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: DesignTokens.previewFill,
              minimumSize: const Size(0, 48),
            ),
            onPressed: gated ? null : onPressed,
            child: child,
          )
        : OutlinedButton(
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(0, 48),
              side: const BorderSide(color: DesignTokens.border),
              foregroundColor: DesignTokens.textPrimary,
            ),
            onPressed: gated ? null : onPressed,
            child: child,
          );
    return Semantics(
      button: true,
      enabled: !gated,
      label: gated
          ? '$semanticLabel, unavailable while reconnecting'
          : semanticLabel,
      excludeSemantics: true,
      child: Opacity(opacity: gated ? 0.4 : 1, child: button),
    );
  }
}
