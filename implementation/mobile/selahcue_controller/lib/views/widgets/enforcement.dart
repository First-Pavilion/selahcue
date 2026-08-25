/// The three RBAC enforcement surfaces (MOBILE-2.0-SPEC §4.10–§4.13, Figma
/// `357:218`, `358:128`, `358:149`).
///
/// | State | Surface | Blocking? | Dismissal |
/// |---|---|---|---|
/// | Permission blocked | bottom sheet | yes — but never over the emergency strip | Got it / scrim |
/// | Role changed — live | inline banner | no | auto 20 s or tap |
/// | Action rejected | inline toast | no | auto on resync |
///
/// All three are driven by real [LiveController] state — a `forbidden` wire
/// denial, a role diff across a reconnect, a command lost mid-flight. None of
/// them has a demo hook, because an enforcement surface that can be triggered by
/// anything other than enforcement is a surface nobody trusts.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import '../../controllers/live_controller.dart';
import '../../models/design_tokens.dart';
import '../../models/rbac.dart';
import '../../models/selah_theme.dart';
import 'primitives.dart';

// ---------------------------------------------------------------------------
// §4.10 — Permission blocked
// ---------------------------------------------------------------------------

/// Hosts the permission-blocked sheet over the tab CONTENT only.
///
/// Deliberately not `showModalBottomSheet`: a route-level modal sheet covers the
/// whole screen, and §4.13 is explicit that the emergency chords stay reachable
/// behind this one — blackout and clear are the two controls that must never sit
/// behind a modal (UX-CANONICAL §1.2 invariant 2). Scoping the scrim and the
/// sheet to the region between the connection banner and the emergency strip is
/// what makes "modal over the tab, not over the app" buildable.
///
/// Wrap the Expanded body of a screen that carries the emergency strip:
/// `Expanded(child: PermissionBlockedHost(live: live, child: pages))`.
class PermissionBlockedHost extends StatelessWidget {
  final LiveController live;
  final Widget child;

  const PermissionBlockedHost({
    super.key,
    required this.live,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final blocked = live.blocked;
    if (blocked == null) return child;
    return Stack(
      fit: StackFit.expand,
      children: [
        child,
        // *measured*: `d2Base` reads `#08090E` behind the sheet — black at 28 %.
        // The scrim also absorbs every tap, which is how the control the
        // operator touched renders inert while the sheet is up without the tab
        // having to know which control it was.
        Positioned.fill(
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: live.dismissBlocked,
            child: ColoredBox(color: Colors.black.withValues(alpha: 0.28)),
          ),
        ),
        // Last in paint order, so it blocks the semantics of the dimmed content
        // beneath it — and only of that. The emergency strip lives OUTSIDE this
        // stack and keeps both its hit area and its screen-reader node.
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: BlockSemantics(
            child: PermissionBlockedSheet(
              denial: blocked,
              onDismiss: live.dismissBlocked,
            ),
          ),
        ),
      ],
    );
  }
}

/// "That's not in your role" — the sheet itself (spec §4.10).
///
/// Exists for the two cases where hiding the control was not possible: a
/// server-side denial arriving after an optimistic tap, and a capability this
/// client's mirror wrongly believed it had. Everything else a role lacks is
/// simply not drawn.
class PermissionBlockedSheet extends StatelessWidget {
  final PermissionDenial denial;
  final VoidCallback onDismiss;

  const PermissionBlockedSheet({
    super.key,
    required this.denial,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final action = denial.action;
    final required = denial.requiredRole;
    final roles = denial.qualifyingRoles;
    // Spec §4.10 "States": an older host, or a command this build does not know,
    // leaves nothing honest to put in the roles card — so it is dropped rather
    // than filled with a guess, and the body stops naming a role it cannot name.
    final canName = action != null && required != null && roles.isNotEmpty;
    final body = canName
        ? '${action.phrase} needs the ${required.label} role. '
              "You're signed in as a ${denial.role.label}."
        : "This control isn't part of your role. Ask your operator on the "
              'desktop.';

    return Semantics(
      scopesRoute: true,
      namesRoute: true,
      explicitChildNodes: true,
      label: "That's not in your role",
      child: Material(
        color: DesignTokens.d2Surface,
        borderRadius: const BorderRadius.vertical(
          top: Radius.circular(SelahRadius.card + 2),
        ),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
              SelahSpace.gutter,
              SelahSpace.md,
              SelahSpace.gutter,
              SelahSpace.gutter,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Drag handle — decoration, and it says so, otherwise assistive
                // tech announces an unlabelled node before the heading.
                const ExcludeSemantics(
                  child: Center(
                    child: SizedBox(
                      width: 44,
                      height: 5,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: DesignTokens.d2BorderStrong,
                          borderRadius: BorderRadius.all(Radius.circular(3)),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 31 - SelahSpace.md),
                Center(
                  child: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      // Gold-on-gold, per spec §6.2 item 4 — the frame
                      // transposes this fill with `d2LiveSoft`, which would say
                      // "error" where the app means "not yours".
                      color: DesignTokens.d2GoldSoft,
                      shape: BoxShape.circle,
                      border: Border.all(color: DesignTokens.d2WarnBorder),
                    ),
                    child: const Icon(
                      Icons.lock_outline,
                      size: 22,
                      color: DesignTokens.d2Gold,
                    ),
                  ),
                ),
                const SizedBox(height: SelahSpace.lg),
                Semantics(
                  header: true,
                  child: Text(
                    "That's not in your role",
                    textAlign: TextAlign.center,
                    style: SelahType.h2.copyWith(
                      fontSize: 19,
                      color: DesignTokens.d2Text,
                    ),
                  ),
                ),
                const SizedBox(height: SelahSpace.lg),
                Text(
                  body,
                  textAlign: TextAlign.center,
                  style: SelahType.body.copyWith(
                    height: 1.4,
                    color: DesignTokens.d2TextSecondary,
                  ),
                ),
                if (canName) ...[
                  const SizedBox(height: SelahSpace.lg),
                  _RolesCard(verb: action.verb, roles: roles),
                ],
                const SizedBox(height: SelahSpace.lg),
                // "Request access" is NOT here. The frame draws it beside Got
                // it, but there is no request-access command in the wire
                // protocol, so it could only ever be a button that closes a
                // sheet and tells the operator something happened that did not.
                // Spec §4.10 says to hide it entirely rather than show it dead,
                // and with one action left, that action takes the full width.
                SelahButton(
                  label: 'Got it',
                  onPressed: onDismiss,
                  semanticLabel: 'Got it, close',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// `ROLES THAT CAN <VERB>` + a chip per qualifying role (spec §4.10).
///
/// Chips, not prose, because the answer to "who can do this?" is a set the
/// operator has to carry to whoever assigns roles on the desktop. They take the
/// same tone as the app-bar role chip via [roleTone], so a role is one colour
/// everywhere in the app.
class _RolesCard extends StatelessWidget {
  final String verb;
  final List<MobileRole> roles;

  const _RolesCard({required this.verb, required this.roles});

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(SelahSpace.lg),
    decoration: BoxDecoration(
      color: DesignTokens.d2Inset,
      borderRadius: BorderRadius.circular(SelahRadius.row),
      border: Border.all(color: DesignTokens.d2Border),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'ROLES THAT CAN $verb',
          style: SelahType.overline.copyWith(
            fontSize: 10,
            color: DesignTokens.d2TextSecondary,
          ),
        ),
        const SizedBox(height: SelahSpace.sm),
        Wrap(
          spacing: SelahSpace.xs,
          runSpacing: SelahSpace.xs,
          children: [
            for (final role in roles)
              StatusBadge(
                text: role.label.toUpperCase(),
                tone: roleTone(role),
                semanticLabel: role.label,
              ),
          ],
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// §4.11 — Role changed, live
// ---------------------------------------------------------------------------

/// The role-changed banner and its `PREVIOUS CONTROLS` receipt (spec §4.11).
///
/// Inline and non-blocking on purpose: UX-CANONICAL §3 forbids a blocking modal
/// over live-control chrome, and a role change is news rather than a decision.
///
/// The rows beneath are a **receipt, not a control**. The controls themselves
/// are already gone — `LiveController.role` reads through the current session,
/// so every `can()` gate re-evaluates the instant the fresh grant lands (FR-090).
/// These rows exist so the disappearance has an explanation attached to it.
class RoleChangedBanner extends StatefulWidget {
  final LiveController live;

  /// The change to render. Passed in rather than read off [live] so this widget
  /// mounts when a change appears and re-mounts its announcement and timer when
  /// a DIFFERENT change replaces it — a controller read in `build` could do
  /// neither without announcing on every 1 s poll.
  final RoleChange change;

  /// How long the banner stays before retiring itself (*default* 20 s).
  /// Injected so the timing is deterministic under test — the same seam
  /// `EmergencyStrip.confirmWindow` uses.
  final Duration autoDismiss;

  const RoleChangedBanner({
    super.key,
    required this.live,
    required this.change,
    this.autoDismiss = const Duration(seconds: 20),
  });

  @override
  State<RoleChangedBanner> createState() => _RoleChangedBannerState();
}

class _RoleChangedBannerState extends State<RoleChangedBanner> {
  Timer? _dismiss;

  @override
  void initState() {
    super.initState();
    _onChange();
  }

  @override
  void didUpdateWidget(RoleChangedBanner old) {
    super.didUpdateWidget(old);
    // A second reassignment before the first receipt was read replaces it; the
    // window restarts so the new one gets its full read time.
    if (old.change.to != widget.change.to ||
        old.change.from != widget.change.from) {
      _onChange();
    }
  }

  void _onChange() {
    _dismiss?.cancel();
    _dismiss = Timer(widget.autoDismiss, () {
      if (mounted) widget.live.dismissRoleChange();
    });
    // Deferred to after the frame because the announcement needs `View.of` and
    // `Directionality.of`, and an inherited-widget lookup is illegal inside
    // initState. A post-frame callback (not a Timer) also means nothing here can
    // outlive the widget in a way the pending-timer check would catch.
    final change = widget.change;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      // Assertive, not polite: the controls under the operator's thumb just
      // changed, and a polite announcement waits for a gap that a live service
      // may not give (spec §6.4).
      //
      // The spec names `SemanticsService.announce`, which Flutter deprecated
      // after 3.35 for being incompatible with multiple windows.
      // `sendAnnouncement` is the same call with the view made explicit — same
      // channel, same event, same assertiveness.
      SemanticsService.sendAnnouncement(
        View.of(context),
        _announcement(change),
        Directionality.of(context),
        assertiveness: Assertiveness.assertive,
      );
    });
  }

  static String _announcement(RoleChange change) {
    final removed = change.removed.map((c) => c.label).join(', ');
    return 'Your role changed to ${change.to.label}.'
        '${removed.isEmpty ? '' : ' $removed removed.'}';
  }

  @override
  void dispose() {
    // Non-negotiable: a 20 s timer surviving this widget is both a leak and a
    // test-suite failure (the binding's pending-timer check).
    _dismiss?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final change = widget.change;
    final removed = change.removed.toList();
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        SelahSpace.md,
        SelahSpace.xs,
        SelahSpace.md,
        0,
      ),
      child: ConstrainedBox(
        // The receipt is bounded so a downgrade that strips seven capabilities
        // cannot push the tab content off a phone. Beyond this the receipt
        // scrolls inside itself; the screen behind stays usable, which is the
        // whole point of an inline banner over a modal.
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.42,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              _banner(change),
              if (removed.isNotEmpty) ...[
                const SizedBox(height: SelahSpace.md),
                const SectionLabel('PREVIOUS CONTROLS'),
                const SizedBox(height: SelahSpace.xs),
                for (final capability in removed) ...[
                  _RemovedRow(capability: capability),
                  const SizedBox(height: 6),
                ],
              ],
              // Only claimed when it is true. `Capability.monitor` is exactly
              // the right test: the transcript is not a capability the reader
              // needs, it rides inside the operator state that `monitor` gates
              // (`selahcue-lan/src/rbac.rs`: `GetOperatorState => Monitor`).
              // A role that cannot even monitor (an unrecognised grant, which
              // fails closed to no capabilities) gets no reassurance, because
              // there would be nothing left to watch and the sentence would be
              // a lie.
              if (change.to.can(Capability.monitor)) ...[
                const SizedBox(height: 6),
                _reassurance(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _banner(RoleChange change) {
    final tone = SelahToneStyle.of(SelahTone.warn);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(SelahRadius.row),
        onTap: widget.live.dismissRoleChange,
        child: Container(
          constraints: const BoxConstraints(minHeight: 68),
          padding: const EdgeInsets.all(13),
          decoration: BoxDecoration(
            color: tone.fill,
            borderRadius: BorderRadius.circular(SelahRadius.row),
            border: Border.all(color: tone.border),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.vpn_key_outlined,
                size: 14,
                color: DesignTokens.d2Warn,
              ),
              const SizedBox(width: SelahSpace.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      // The REAL granted role, not the 7-role design vocabulary
                      // (deferred: 86ajxuf81 / 86ajxufbg).
                      'Your role changed → ${change.to.label}',
                      style: SelahType.rowTitle.copyWith(
                        fontWeight: FontWeight.w700,
                        color: DesignTokens.d2Text,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      change.isDowngrade
                          ? 'An admin updated your access · live controls were '
                                'removed just now.'
                          : 'An admin updated your access · you have more '
                                'controls than a moment ago.',
                      style: SelahType.caption.copyWith(
                        height: 1.4,
                        color: DesignTokens.d2Warn,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: SelahSpace.xs),
              Text(
                'Dismiss',
                style: SelahType.caption.copyWith(
                  fontWeight: FontWeight.w700,
                  color: DesignTokens.d2Warn,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// What the operator can still do (spec §4.11, verbatim).
  ///
  /// This row used to appear to contradict the receipt above it: a
  /// Producer→Viewer demotion removes [Capability.transcribe], which the
  /// receipt printed as "Transcript — removed" two rows above a promise that
  /// the transcript was still watchable. The row is the half that is TRUE.
  /// `Transcribe` is a WRITE grant — it gates `IngestTranscript`, the STT
  /// ingestion channel, and nothing else (`selahcue-lan/src/rbac.rs:127`),
  /// a command this client never sends. Reading the transcript rides in
  /// `GetOperatorState`, which needs only `Monitor`. So the fix belongs on the
  /// label (see `CapabilityLabel` in `rbac.dart`), not here: weakening this
  /// sentence would have taken away a reassurance the Viewer is genuinely owed.
  static Widget _reassurance() => Container(
    constraints: const BoxConstraints(minHeight: 40),
    padding: const EdgeInsets.symmetric(
      horizontal: SelahSpace.md,
      vertical: SelahSpace.xs,
    ),
    decoration: BoxDecoration(
      color: DesignTokens.d2Elevated,
      borderRadius: BorderRadius.circular(SelahRadius.row),
      border: Border.all(color: DesignTokens.d2Border),
    ),
    child: Row(
      children: [
        const Icon(
          Icons.visibility_outlined,
          size: 16,
          color: DesignTokens.d2TextSecondary,
        ),
        const SizedBox(width: SelahSpace.xs),
        Expanded(
          child: Text(
            'You can still watch previews & the transcript.',
            style: SelahType.bodySmall.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
      ],
    ),
  );
}

/// One line of the receipt: a control that was there a moment ago.
///
/// Drawn at 50 % (*measured*) and carrying no gesture at all — half-opacity on
/// something tappable would read as "disabled, try later", and this is neither.
class _RemovedRow extends StatelessWidget {
  final Capability capability;
  const _RemovedRow({required this.capability});

  // The row is dimmed to 0.5 (spec §4.11, *measured*) — but an ancestor `Opacity`
  // composites EVERY descendant down, including text, and a token-on-token contrast
  // check cannot see it: `d2TextSecondary` on `d2Surface` measures 8.12:1 and passes,
  // while the same pair inside this 0.5 wrapper composites to **2.97:1** and fails
  // AA-normal. So the ink here is chosen for what it becomes AFTER compositing, not
  // for what it measures on its own: `d2Text` at 0.5 lands at 4.96:1 and clears AA,
  // where `d2TextSecondary` cannot. The label/marker hierarchy is carried by size and
  // weight (`body` vs `caption`) instead of colour — the same trade §4.6 makes for the
  // TIME UP sub-line.
  @override
  Widget build(BuildContext context) => Opacity(
    opacity: 0.5,
    child: Container(
      constraints: const BoxConstraints(minHeight: 42),
      padding: const EdgeInsets.symmetric(
        horizontal: SelahSpace.md,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: DesignTokens.d2Surface,
        borderRadius: BorderRadius.circular(SelahRadius.row),
        border: Border.all(color: DesignTokens.d2Border),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              capability.label,
              style: SelahType.body.copyWith(color: DesignTokens.d2Text),
            ),
          ),
          const SizedBox(width: SelahSpace.xs),
          const Icon(
            Icons.lock_outline,
            size: 13,
            // d2TextSecondary composites to 2.97:1 here, under the 3:1 non-text
            // minimum as well as AA-normal.
            color: DesignTokens.d2Text,
          ),
          const SizedBox(width: 4),
          Text(
            'removed',
            style: SelahType.caption.copyWith(color: DesignTokens.d2Text),
          ),
        ],
      ),
    ),
  );
}

// ---------------------------------------------------------------------------
// §4.12 — Action rejected
// ---------------------------------------------------------------------------

/// "Action rejected" (spec §4.12) — a command that reached the wire and was lost
/// with the connection.
///
/// Rendered in the connection banner's slot, which is not a compromise: a
/// rejection is always followed by a reconnect, so the two would compete for the
/// same strip every time. The toast carries its own reconnecting row, so taking
/// the slot costs the operator nothing.
///
/// **Nothing is queued and nothing is retried** (FR-097). The copy says so
/// explicitly, because "rejected" invites the assumption that the app will try
/// again — and a command replayed later fires into a service that has moved on.
class ActionRejectedToast extends StatelessWidget {
  /// The host the device is reconnecting to, for the status row.
  final String host;

  const ActionRejectedToast({super.key, required this.host});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      SelahSpace.md,
      SelahSpace.xs,
      SelahSpace.md,
      SelahSpace.xs,
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          constraints: const BoxConstraints(minHeight: 57),
          padding: const EdgeInsets.all(13),
          decoration: BoxDecoration(
            color: DesignTokens.d2Elevated,
            borderRadius: BorderRadius.circular(SelahRadius.row),
            border: Border.all(color: DesignTokens.d2LiveBorder),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                size: 15,
                color: DesignTokens.d2Live,
              ),
              const SizedBox(width: SelahSpace.xs),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Action rejected',
                      style: SelahType.body.copyWith(
                        fontWeight: FontWeight.w700,
                        color: DesignTokens.d2Text,
                      ),
                    ),
                    Text(
                      'Your pairing changed — reconnecting…',
                      style: SelahType.caption.copyWith(
                        color: DesignTokens.d2TextSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: SelahSpace.xs),
        Text(
          'The desktop validates every command at execution time. A command it '
          "can't validate is dropped — never queued to fire later out of "
          'context.',
          textAlign: TextAlign.center,
          style: SelahType.caption.copyWith(
            height: 1.4,
            color: DesignTokens.d2TextSecondary,
          ),
        ),
        const SizedBox(height: SelahSpace.xs),
        _ReconnectingRow(host: host),
      ],
    ),
  );
}

/// The info-toned status strip under the toast.
class _ReconnectingRow extends StatelessWidget {
  final String host;
  const _ReconnectingRow({required this.host});

  @override
  Widget build(BuildContext context) {
    final tone = SelahToneStyle.of(SelahTone.info);
    return Container(
      constraints: const BoxConstraints(minHeight: 35),
      padding: const EdgeInsets.symmetric(
        horizontal: SelahSpace.md,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: tone.fill,
        borderRadius: BorderRadius.circular(SelahRadius.row),
        border: Border.all(color: tone.border),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const _ReconnectSpinner(),
          const SizedBox(width: SelahSpace.xs),
          Flexible(
            child: Text(
              'Reconnecting to $host…',
              style: SelahType.bodySmall.copyWith(color: tone.ink),
            ),
          ),
        ],
      ),
    );
  }
}

/// 13 px indeterminate spinner — or a **static ring** when the operator asked
/// for reduced motion (spec §4.12, §6.7).
///
/// A static ring rather than nothing at all: the ring is what makes the row read
/// as "in progress", and the sentence beside it is doing the real work either
/// way.
class _ReconnectSpinner extends StatelessWidget {
  const _ReconnectSpinner();

  @override
  Widget build(BuildContext context) {
    if (selahReduceMotion(context)) {
      return Container(
        width: 13,
        height: 13,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: DesignTokens.d2Info, width: 2),
        ),
      );
    }
    return const SizedBox(
      width: 13,
      height: 13,
      child: CircularProgressIndicator(
        strokeWidth: 2,
        color: DesignTokens.d2Info,
      ),
    );
  }
}
