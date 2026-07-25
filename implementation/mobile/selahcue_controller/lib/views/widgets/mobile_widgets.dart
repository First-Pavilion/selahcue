/// Shared mobile Producer widgets (revamp 86ajpx7bd): the design-system pieces
/// every tab reuses — status/output cards, badges, the persistent emergency
/// strip. Colours come from [DesignTokens] (bound to the same tokens the
/// desktop console and the Figma design use). Widgets only.
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';

/// A LIVE / PREVIEW badge — colour + text label (never colour alone, WCAG 1.4.1).
class StatusBadge extends StatelessWidget {
  final String text;
  final Color color;
  const StatusBadge({super.key, required this.text, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration:
            BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
        child: Text(text,
            style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.6,
                color: Colors.white)),
      );
}

/// A labeled output card (PREVIEW · STAGED / ● LIVE · ON AIR) with its black
/// surface. `blackout` drapes the live card with an explicit text overlay.
class OutputCard extends StatelessWidget {
  final String header;
  final Color headerColor;
  final Color borderColor;
  final String? title;
  final String? caption;
  final String idle;
  final bool blackout;

  const OutputCard({
    super.key,
    required this.header,
    required this.headerColor,
    required this.borderColor,
    required this.title,
    required this.caption,
    required this.idle,
    this.blackout = false,
  });

  @override
  Widget build(BuildContext context) {
    final hasContent = title != null;
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: borderColor),
        borderRadius: BorderRadius.circular(12),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: headerColor,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Text(header,
                style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.7,
                    color: Colors.white)),
          ),
          Container(
            color: DesignTokens.outputBlack,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 22),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (blackout)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          border: Border.all(color: DesignTokens.liveInk),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('BLACKOUT — OUTPUT DARK',
                            style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.8,
                                color: Colors.white)),
                      ),
                    ),
                  Opacity(
                    opacity: blackout ? 0.3 : 1,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(hasContent ? title! : idle,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                                fontSize: hasContent ? 18 : 15,
                                fontWeight: hasContent
                                    ? FontWeight.w600
                                    : FontWeight.w500,
                                color: hasContent
                                    ? DesignTokens.textPrimary
                                    : DesignTokens.textMuted)),
                        if (caption != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(caption!,
                                style: const TextStyle(
                                    fontSize: 11,
                                    color: DesignTokens.textMuted)),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The always-on emergency strip (UX-CANONICAL §3): Blackout + Clear All,
/// present above the tab bar on every screen. Never scrolls away.
class EmergencyStrip extends StatelessWidget {
  final LiveController live;
  const EmergencyStrip({super.key, required this.live});

  @override
  Widget build(BuildContext context) {
    final blackout = live.blackout;
    return Container(
      decoration: const BoxDecoration(
        color: DesignTokens.bgPanel,
        border: Border(
          top: BorderSide(color: DesignTokens.border),
          bottom: BorderSide(color: DesignTokens.border),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Row(
        children: [
          Expanded(
            child: _EmgButton(
              label: blackout ? '■ UN-BLACKOUT' : '■ BLACKOUT',
              semanticLabel: blackout ? 'Un-blackout' : 'Blackout',
              fill: blackout ? DesignTokens.liveFill : DesignTokens.bgBase,
              border:
                  blackout ? DesignTokens.liveInk : DesignTokens.border,
              textColor:
                  blackout ? Colors.white : DesignTokens.textPrimary,
              onTap: () => live.act(cmdBlackout(!blackout)),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _EmgButton(
              label: '✕ CLEAR ALL',
              semanticLabel: 'Clear all',
              fill: DesignTokens.bgBase,
              border: DesignTokens.liveInk,
              textColor: DesignTokens.liveInk,
              onTap: () => live.act(cmdClear()),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmgButton extends StatelessWidget {
  final String label;
  final String semanticLabel;
  final Color fill;
  final Color border;
  final Color textColor;
  final VoidCallback onTap;
  const _EmgButton({
    required this.label,
    required this.semanticLabel,
    required this.fill,
    required this.border,
    required this.textColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        // Announce the plain word, not the "■"/"✕" glyph baked into the label.
        label: semanticLabel,
        excludeSemantics: true,
        child: Material(
          color: fill,
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: onTap,
            child: Container(
              height: 46,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border.all(color: border),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(label,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.3,
                      color: textColor)),
            ),
          ),
        ),
      );
}

/// Format a whole-seconds duration as `M:SS`.
String fmtClock(int secs) => '${secs ~/ 60}:${(secs % 60).toString().padLeft(2, '0')}';
