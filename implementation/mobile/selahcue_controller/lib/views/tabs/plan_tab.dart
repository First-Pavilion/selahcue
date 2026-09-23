/// Plan tab — the read-only service plan, Design 2.0 (MOBILE-2.0-SPEC §4.4).
///
/// ⚠ The four mobile frames do not draw this tab; the spec derives it from the
/// ListRow primitive (§3.5) and the desktop console's plan column, so everything
/// here follows §4.4 rather than a measured frame.
///
/// Tapping an item STAGES it in Preview (Producers cannot Go Live from here —
/// that is the Live tab, preserving the preview→live safety).
library;

import 'package:flutter/material.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/protocol.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
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
    // Staging into an unknown host state is exactly the tap that later goes live
    // on a stale premise, so the list goes inert while we re-sync (FR-097).
    final syncing = live.syncing;
    // A command any row's tap/double-tap sent is still on the wire — a row
    // must not accept a second stage while the first is unresolved, the same
    // reason [syncing] already goes inert (FR-097).
    final busy = live.busy;
    final canStage = live.can(Capability.navigate) && !syncing && !busy;
    final canGoLive = live.can(Capability.goLive) && !syncing && !busy;
    final hint = syncing
        ? 'Syncing live state… controls are disabled until this device is back '
              'in step with the desktop.'
        : busy
        ? 'Sending… controls are disabled until the command finishes.'
        : !live.can(Capability.navigate)
        ? 'Read-only — your role can view the plan but not stage it.'
        : live.can(Capability.goLive)
        ? 'Tap to stage in Preview · double-tap to send it live'
        : 'Tap to stage in Preview';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionLabel(
          'SERVICE PLAN',
          padding: EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            SelahSpace.xl,
            SelahSpace.gutter,
            SelahSpace.sm,
          ),
        ),
        Expanded(
          child: view.items.isEmpty
              ? const _EmptyPlan()
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(
                    horizontal: SelahSpace.gutter,
                  ),
                  itemCount: view.items.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: 6),
                  itemBuilder: (context, i) {
                    final it = view.items[i];
                    // Live wins the tint when an item is both live AND staged —
                    // after go-live the host reports the same index for both,
                    // and the operator needs the "on the audience" cue.
                    final state = it.isLive
                        ? SelahRowState.live
                        : it.isStaged
                        ? SelahRowState.staged
                        : SelahRowState.normal;
                    return SelahListRow(
                      state: state,
                      onTap: canStage
                          ? () => live.act(cmdSelectItem(it.id))
                          : null,
                      onDoubleTap: canGoLive
                          ? () => live.selectAndGoLive(it.id)
                          : null,
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  it.title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: SelahType.rowTitle.copyWith(
                                    color: DesignTokens.d2Text,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Row(
                                  children: [
                                    KindBadge(kind: it.kind),
                                    if (it.slideBadge.isNotEmpty) ...[
                                      const SizedBox(width: 6),
                                      Text(
                                        it.slideBadge.trim(),
                                        style: SelahType.caption.copyWith(
                                          color:
                                              DesignTokens.d2TextSecondary,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ],
                            ),
                          ),
                          // The tint is never the only signal — the chip says
                          // the same word (spec §6.3).
                          if (it.isLive)
                            const StatusBadge(
                              text: 'LIVE',
                              tone: SelahTone.live,
                              dot: true,
                            )
                          else if (it.isStaged)
                            const StatusBadge(
                              text: 'PREVIEW',
                              tone: SelahTone.preview,
                              dot: true,
                            ),
                        ],
                      ),
                    );
                  },
                ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            SelahSpace.sm,
            SelahSpace.gutter,
            SelahSpace.md,
          ),
          child: Text(
            hint,
            style: SelahType.caption.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
      ],
    );
  }
}

/// The host has a plan with no items (spec §4.4 — specified there, drawn
/// nowhere). Says who can fix it: plan editing is a desktop responsibility, so
/// an empty list on the phone is not something the operator can act on here.
class _EmptyPlan extends StatelessWidget {
  const _EmptyPlan();

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(SelahSpace.section),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: DesignTokens.d2Elevated,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: DesignTokens.d2Border),
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.list_alt,
              size: 26,
              color: DesignTokens.d2TextSecondary,
            ),
          ),
          const SizedBox(height: SelahSpace.xl),
          Semantics(
            header: true,
            child: Text(
              'No items in this plan',
              textAlign: TextAlign.center,
              style: SelahType.h2.copyWith(color: DesignTokens.d2Text),
            ),
          ),
          const SizedBox(height: SelahSpace.sm),
          Text(
            'The operator adds items on the desktop.',
            textAlign: TextAlign.center,
            style: SelahType.bodySmall.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ],
      ),
    ),
  );
}
