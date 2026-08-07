/// Plan tab (revamp 86ajpx7bd): the read-only service plan. Tapping an item
/// STAGES it in Preview (Producers cannot Go Live from here — that is the Live
/// tab, preserving the preview→live safety).
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../widgets/mobile_widgets.dart';

class PlanTab extends StatelessWidget {
  final LiveController live;
  const PlanTab({super.key, required this.live});

  @override
  Widget build(BuildContext context) {
    final view = live.view;
    if (view == null) {
      return const Center(child: CircularProgressIndicator());
    }
    // Plan is role-gated: staging needs Navigate; one-gesture go-live needs
    // GoLive. A role with neither (Viewer) gets a read-only list.
    final canStage = live.can(Capability.navigate);
    final canGoLive = live.can(Capability.goLive);
    final hint = !canStage
        ? 'Read-only — your role can view the plan but not stage it.'
        : canGoLive
            ? 'Tap to stage in Preview · double-tap to send it live'
            : 'Tap to stage in Preview';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 14, 16, 8),
          child: Text('SERVICE PLAN',
              style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.7,
                  color: DesignTokens.textMuted)),
        ),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            itemCount: view.items.length,
            separatorBuilder: (context, index) => const SizedBox(height: 6),
            itemBuilder: (context, i) {
              final it = view.items[i];
              final border = it.isLive
                  ? DesignTokens.liveInk
                  : it.isStaged
                      ? DesignTokens.previewInk
                      : DesignTokens.border;
              return Material(
                color: DesignTokens.bgBase,
                borderRadius: BorderRadius.circular(8),
                child: InkWell(
                  borderRadius: BorderRadius.circular(8),
                  onTap: canStage ? () => live.act(cmdSelectItem(it.id)) : null,
                  onDoubleTap:
                      canGoLive ? () => live.selectAndGoLive(it.id) : null,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      border: Border.all(color: border),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(it.title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                      color: DesignTokens.textPrimary)),
                              const SizedBox(height: 2),
                              Text(it.kind.toUpperCase() + it.slideBadge,
                                  style: const TextStyle(
                                      fontSize: 10,
                                      letterSpacing: 0.5,
                                      color: DesignTokens.textMuted)),
                            ],
                          ),
                        ),
                        if (it.isLive)
                          const StatusBadge(
                              text: 'LIVE', color: DesignTokens.liveFill)
                        else if (it.isStaged)
                          const StatusBadge(
                              text: 'PREVIEW', color: DesignTokens.previewFill),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: Text(hint,
              style:
                  const TextStyle(fontSize: 11, color: DesignTokens.textMuted)),
        ),
      ],
    );
  }
}
