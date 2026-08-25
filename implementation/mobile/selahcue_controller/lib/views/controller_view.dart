/// Controller view (V in MVC) — the tabbed shell, Design 2.0 (Figma `363:124`).
/// A role-scoped bottom tab bar (Live · Plan · Scripture · Timer) with a
/// PERSISTENT emergency strip above it on every tab, a compact top bar (plan
/// name · LIVE chip · role · clock · ⓘ), and a non-blocking reconnecting banner.
/// All logic lives in [LiveController]; this is widgets only.
library;

import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../controllers/live_controller.dart';
import '../models/design_tokens.dart';
import '../models/discovery.dart' show pinFingerprint;
import '../models/rbac.dart';
import '../models/selah_theme.dart';
import '../models/session.dart';
import '../models/settings.dart';
import '../models/stored_session.dart';
import '../models/tab_scope.dart';
import 'pairing_view.dart';
import 'tabs/live_tab.dart';
import 'tabs/plan_tab.dart';
import 'tabs/scripture_tab.dart';
import 'tabs/timer_tab.dart';
import 'widgets/mobile_widgets.dart';
import 'widgets/responsive.dart';

class ControllerView extends StatefulWidget {
  // The interface (not the concrete SelahSession) so the shell is widget-testable
  // with a fake; production callers pass a SelahSession, which implements it.
  final ControllerSession session;
  final StoredSession stored;

  /// Optional reconnect factory, forwarded to [LiveController] (a test seam so
  /// the revoked/reconnect path can be exercised without a real socket).
  ///
  /// Typed to [ControllerSession], matching [LiveController]'s own seam. It used
  /// to name the concrete `SelahSession`, which let a test simulate a reconnect
  /// that FAILS but not one that SUCCEEDS with a different grant — the only way
  /// a re-role reaches this device (spec §4.11). Return types are covariant, so
  /// every existing caller still type-checks.
  final Future<ControllerSession> Function({
    required String host,
    required int port,
    required String pinHex,
    required Credentials creds,
  })?
  connect;

  const ControllerView({
    super.key,
    required this.session,
    required this.stored,
    this.connect,
  });

  @override
  State<ControllerView> createState() => _ControllerViewState();
}

class _ControllerViewState extends State<ControllerView> {
  late final LiveController _live;
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    _live = LiveController(
      session: widget.session,
      stored: widget.stored,
      connect: widget.connect,
    );
  }

  /// Leave the revoked device on the pairing screen (credentials were already
  /// cleared when the revoke was detected).
  void _repair() {
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => const PairingView()));
  }

  @override
  void dispose() {
    _live.dispose();
    super.dispose();
  }

  Future<void> _unpair() async {
    await _live.unpair();
    if (!mounted) return;
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => const PairingView()));
  }

  /// Open the About & connection sheet — the home for connection details and
  /// Disconnect, reached from the top bar instead of a competing nav drawer.
  void _showAbout() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: DesignTokens.d2Base,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(SelahRadius.card),
        ),
      ),
      isScrollControlled: true,
      builder: (sheetContext) => ConfigSheet(
        stored: widget.stored,
        live: _live,
        settings: SettingsScope.of(context),
        onDisconnect: () {
          Navigator.of(sheetContext).pop(); // close the sheet first
          _unpair();
        },
      ),
    );
  }

  Widget _pageFor(ControllerTab tab) {
    switch (tab) {
      case ControllerTab.live:
        return LiveTab(live: _live);
      case ControllerTab.plan:
        return PlanTab(live: _live);
      case ControllerTab.scripture:
        return ScriptureTab(live: _live);
      case ControllerTab.timer:
        return TimerTab(live: _live);
    }
  }

  static String _tabTitle(ControllerTab tab) {
    switch (tab) {
      case ControllerTab.live:
        return 'Live';
      case ControllerTab.plan:
        return 'Plan';
      case ControllerTab.scripture:
        return 'Scripture';
      case ControllerTab.timer:
        return 'Timer';
    }
  }

  /// Build a bottom-bar destination; a view-only tab gets a muted dot + a
  /// "view only" tooltip (the ◐ marker from the design), and the Scripture tab
  /// additionally carries the count of detections waiting for approval so they
  /// are noticeable from Live/Plan/Timer — they used to be visible only once
  /// you were already standing on the Scripture tab.
  ///
  /// [pending] is the number of detections awaiting approval (0 = no badge).
  NavigationDestination _destinationFor(TabSpec spec, int pending) {
    final (IconData icon, IconData selected) = switch (spec.tab) {
      ControllerTab.live => (Icons.play_arrow_outlined, Icons.play_arrow),
      ControllerTab.plan => (Icons.list_alt_outlined, Icons.list_alt),
      ControllerTab.scripture => (Icons.menu_book_outlined, Icons.menu_book),
      ControllerTab.timer => (Icons.timer_outlined, Icons.timer),
    };
    final label = _tabTitle(spec.tab);
    final count = spec.tab == ControllerTab.scripture ? pending : 0;
    Widget wrap(IconData i) {
      Widget marked = Icon(i);
      if (spec.viewOnly) {
        marked = Badge(
          backgroundColor: DesignTokens.d2TextSecondary,
          smallSize: 7,
          // The count is actionable and time-critical, so it keeps the
          // conventional top-end corner and the ambient view-only dot yields to
          // top-start — a view-only tab must still show BOTH markers, not one
          // stacked under the other. AlignmentDirectional so RTL mirrors it.
          alignment: count > 0 ? AlignmentDirectional.topStart : null,
          offset: count > 0 ? const Offset(-2, -2) : null,
          child: marked,
        );
      }
      if (count > 0) {
        marked = Badge(
          backgroundColor: DesignTokens.d2Warn,
          // Dark-on-amber: white on `warn` is ~2:1 and fails AA, the same trap
          // the GO LIVE label avoids.
          textColor: DesignTokens.d2Base,
          // Capped: an uncapped count blows the badge out past the nav icon and
          // starts shoving the bar's labels around.
          label: Text(count > 99 ? '99+' : '$count'),
          child: marked,
        );
      }
      return marked;
    }

    // `NavigationDestination` has no badge-semantics slot — assistive tech
    // reads the label and surfaces the tooltip as the hint, so the count has to
    // live in the tooltip to be announced at all. The label itself stays short
    // so the bar does not wrap at a large text scale.
    return NavigationDestination(
      icon: wrap(icon),
      selectedIcon: wrap(selected),
      label: label,
      tooltip: [
        label,
        if (spec.viewOnly) 'view only',
        if (count > 0) '$count need approval',
      ].join(' — '),
    );
  }

  /// Local wall-clock as `H:MM`, e.g. `10:42` (24-hour, no leading zero on hour).
  static String _wallClock() {
    final now = DateTime.now();
    return '${now.hour}:${now.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _live,
      builder: (context, _) {
        // An admin revoked/unpaired this device — show the terminal re-pair
        // screen (RBAC enforcement, Figma 357) instead of the console.
        if (_live.revoked) {
          return AccessRemovedScreen(onRepair: _repair);
        }
        final view = _live.view;
        final onAir =
            view?.liveIndex != null ||
            view?.liveScripture != null ||
            view?.liveFreeText != null;
        // The bottom bar is role-scoped (Figma 363-124): only the tabs this role
        // may use are shown. Clamp the selected index so a role change (reconnect)
        // can never leave it pointing at a now-hidden tab.
        final specs = visibleTabsFor(_live.role);
        final tab = _tab.clamp(0, specs.length - 1);
        // Detections waiting for approval — badged onto the Scripture tab so
        // they are visible from every tab, not just once you are already there.
        final pendingApprovals = view?.detections.length ?? 0;
        final pages = [for (final s in specs) _pageFor(s.tab)];
        final currentTitle = _tabTitle(specs[tab].tab);
        // Hoisted so the null check promotes for the widget below.
        final roleChange = _live.roleChange;
        return Scaffold(
          backgroundColor: DesignTokens.d2Base,
          appBar: AppBar(
            backgroundColor: DesignTokens.d2Base,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
            scrolledUnderElevation: 0,
            titleSpacing: SelahSpace.gutter,
            title: Row(
              children: [
                Flexible(
                  // planName defaults to '' (not null) once connected, and an
                  // unnamed plan is a legitimate host state — fall back to the
                  // tab title on empty too, so the bar is never blank.
                  child: Text(
                    (view?.planName.isNotEmpty ?? false)
                        ? view!.planName
                        : currentTitle,
                    overflow: TextOverflow.ellipsis,
                    style: SelahType.appBar.copyWith(
                      color: DesignTokens.d2Text,
                    ),
                  ),
                ),
                if (onAir) ...[
                  const SizedBox(width: SelahSpace.xs),
                  const StatusBadge(
                    text: 'LIVE',
                    tone: SelahTone.live,
                    dot: true,
                  ),
                ],
              ],
            ),
            actions: [
              // The granted-role chip (the real backend role) — surfaces RBAC
              // and replaces the old hardcoded "Producer".
              RoleBadge(live: _live),
              // A wall clock for service-timing awareness (matches the design);
              // it refreshes on each 1s poll rebuild.
              Padding(
                padding: const EdgeInsets.only(right: 4),
                child: Center(
                  child: Text(
                    _wallClock(),
                    style: SelahType.bodySmall.copyWith(
                      fontWeight: FontWeight.w600,
                      color: DesignTokens.d2TextSecondary,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
              ),
              // About & connection lives on the top bar, not a nav drawer —
              // a drawer competing with the bottom tabs is a second nav surface.
              IconButton(
                icon: const Icon(
                  Icons.info_outline,
                  color: DesignTokens.d2TextSecondary,
                ),
                constraints: const BoxConstraints(
                  minWidth: kSelahMinTouchTarget,
                  minHeight: kSelahMinTouchTarget,
                ),
                tooltip: 'Session, settings and about',
                onPressed: _showAbout,
              ),
            ],
          ),
          body: Column(
            children: [
              ConnectionBanner(live: _live),
              // Under the connection banner, above the body — spec §4.11. The
              // role has ALREADY changed everywhere else on this screen by the
              // time this renders (the tab row above was rebuilt from the new
              // grant, and every `can()` gate with it); this is the receipt for
              // that, not the mechanism.
              if (roleChange != null)
                ResponsiveBody(
                  child: RoleChangedBanner(live: _live, change: roleChange),
                ),
              // Constrain + centre the control column so it doesn't stretch
              // edge-to-edge on a tablet / in landscape (design handoff §1).
              Expanded(
                // The permission sheet is scoped to the CONTENT region, so its
                // scrim never reaches the emergency strip below (spec §4.13).
                child: PermissionBlockedHost(
                  live: _live,
                  child: ResponsiveBody(
                    child: IndexedStack(index: tab, children: pages),
                  ),
                ),
              ),
              // Persistent emergency chrome — on every tab, above the nav.
              // Hidden entirely for a role that can neither blackout nor clear.
              if (_live.can(Capability.blackout) ||
                  _live.can(Capability.clearLive))
                ResponsiveBody(child: EmergencyStrip(live: _live)),
            ],
          ),
          bottomNavigationBar: DecoratedBox(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: DesignTokens.d2Border)),
            ),
            child: NavigationBar(
              backgroundColor: DesignTokens.d2Surface,
              surfaceTintColor: Colors.transparent,
              // Selection is carried by the violet ink + the label, matching
              // the frame; the M3 pill would be a second, louder signal for
              // the same fact (spec Q9).
              indicatorColor: Colors.transparent,
              overlayColor: const WidgetStatePropertyAll(Colors.transparent),
              elevation: 0,
              selectedIndex: tab,
              onDestinationSelected: (i) => setState(() => _tab = i),
              destinations: [
                for (final s in specs) _destinationFor(s, pendingApprovals),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// The Config / About session sheet (Figma `366:128`), opened from the top-bar
/// ⓘ: the identity header, CONNECTION (status/host/role/fingerprint +
/// disconnect), PREFERENCES (keep awake / haptics / reduce motion), and ABOUT
/// (version / policies / licenses / help). Presented as a modal sheet from the
/// top bar so it never becomes a second navigation surface alongside the tabs.
class ConfigSheet extends StatelessWidget {
  final StoredSession stored;
  final LiveController live;
  final SettingsController settings;
  final VoidCallback onDisconnect;

  const ConfigSheet({
    super.key,
    required this.stored,
    required this.live,
    required this.settings,
    required this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: ResponsiveBody(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            SelahSpace.gutter,
            4,
            SelahSpace.gutter,
            SelahSpace.gutter,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Image.asset(
                    'assets/selahcue-logo.png',
                    width: 44,
                    height: 44,
                    semanticLabel: '',
                  ),
                  const SizedBox(width: SelahSpace.md),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'SelahCue',
                        style: SelahType.appBar.copyWith(
                          color: DesignTokens.d2Text,
                        ),
                      ),
                      Text(
                        'Controller · ${live.role.label}',
                        style: SelahType.caption.copyWith(
                          color: DesignTokens.d2TextSecondary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const Divider(
                color: DesignTokens.d2Border,
                height: SelahSpace.section + 4,
              ),
              const SectionLabel(
                'CONNECTION',
                padding: EdgeInsets.only(bottom: SelahSpace.sm),
              ),
              SelahCard(
                padding: const EdgeInsets.symmetric(
                  horizontal: SelahSpace.lg,
                  vertical: SelahSpace.xs,
                ),
                child: Column(
                  children: [
                    // Status tracks the live connection while the sheet is open.
                    ListenableBuilder(
                      listenable: live,
                      builder: (context, _) => _row(
                        'Status',
                        live.reconnecting ? 'Reconnecting…' : 'Connected',
                        valueColor: live.reconnecting
                            ? DesignTokens.d2Warn
                            : DesignTokens.d2Preview,
                      ),
                    ),
                    _row('Host', '${stored.host}:${stored.port}'),
                    _row('Role', live.role.label),
                    _row('Fingerprint', pinFingerprint(stored.pinHex)),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(
                  top: SelahSpace.sm,
                  bottom: SelahSpace.md,
                ),
                child: Text(
                  'Your role is assigned & managed on the desktop.',
                  style: SelahType.caption.copyWith(
                    color: DesignTokens.d2TextSecondary,
                  ),
                ),
              ),
              SelahButton(
                label: 'Disconnect this device',
                icon: Icons.link_off,
                variant: SelahButtonVariant.dangerOutline,
                onPressed: onDisconnect,
              ),
              const Divider(
                color: DesignTokens.d2Border,
                height: SelahSpace.section + 4,
              ),
              const SectionLabel(
                'PREFERENCES',
                padding: EdgeInsets.only(bottom: SelahSpace.sm),
              ),
              // Rebuilds with the controller so the switches reflect the persisted
              // state and each toggle applies immediately (keep-awake → wakelock).
              ListenableBuilder(
                listenable: settings,
                builder: (context, _) => SelahCard(
                  padding: const EdgeInsets.symmetric(
                    vertical: SelahSpace.xs,
                  ),
                  child: Column(
                    children: [
                      SelahToggle(
                        label: 'Keep screen awake',
                        value: settings.keepAwake,
                        onChanged: settings.setKeepAwake,
                      ),
                      const Divider(color: DesignTokens.d2Border),
                      SelahToggle(
                        label: 'Haptic feedback',
                        value: settings.haptics,
                        onChanged: settings.setHaptics,
                      ),
                      const Divider(color: DesignTokens.d2Border),
                      SelahToggle(
                        label: 'Reduce motion',
                        value: settings.reduceMotion,
                        onChanged: settings.setReduceMotion,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: SelahSpace.section),
              const SectionLabel(
                'ABOUT',
                padding: EdgeInsets.only(bottom: SelahSpace.sm),
              ),
              SelahCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    FutureBuilder<PackageInfo>(
                      future: PackageInfo.fromPlatform(),
                      builder: (context, snap) => Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: SelahSpace.lg,
                          vertical: SelahSpace.xs,
                        ),
                        child: _row(
                          'Version',
                          snap.hasData
                              ? '${snap.data!.version} (${snap.data!.buildNumber})'
                              : '…',
                        ),
                      ),
                    ),
                    const Divider(color: DesignTokens.d2Border),
                    _linkRow('Privacy policy', () => _showPrivacy(context)),
                    const Divider(color: DesignTokens.d2Border),
                    _linkRow('Terms of use', () => _showTerms(context)),
                    const Divider(color: DesignTokens.d2Border),
                    _linkRow(
                      'Open-source licenses',
                      () => showLicensePage(
                        context: context,
                        applicationName: 'SelahCue Controller',
                      ),
                    ),
                    const Divider(color: DesignTokens.d2Border),
                    _linkRow('Help & support', () => _showHelp(context)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _linkRow(String label, VoidCallback onTap) => InkWell(
    onTap: onTap,
    child: Container(
      constraints: const BoxConstraints(minHeight: kSelahMinTouchTarget),
      padding: const EdgeInsets.symmetric(horizontal: SelahSpace.lg),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: SelahType.body.copyWith(color: DesignTokens.d2Text),
            ),
          ),
          const Icon(
            Icons.chevron_right,
            size: 18,
            color: DesignTokens.d2TextSecondary,
          ),
        ],
      ),
    ),
  );

  void _showPrivacy(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: DesignTokens.d2Surface,
        title: const Text('Privacy'),
        content: const SingleChildScrollView(
          child: Text(
            'SelahCue runs offline-first on your local network. This controller '
            'talks only to the paired desktop over an encrypted (pinned-TLS) LAN '
            'link and sends no data to any third party. Sermon audio, '
            'transcripts, and notes stay on the desktop under your operator’s '
            'control; retention and any optional cloud features are configured '
            'and disclosed there. Your organisation can provide the full policy.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showTerms(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: DesignTokens.d2Surface,
        title: const Text('Terms of use'),
        content: const SingleChildScrollView(
          child: Text(
            'SelahCue Controller is a companion remote for a SelahCue desktop you '
            'are authorised to operate. The desktop stays authoritative and '
            'enforces your role; use the app only on a network and system you are '
            'permitted to use. The app is provided “as is”, without warranty; you '
            'are responsible for content licensing (songs/scripture) and for '
            'appropriate rehearsal and fallbacks during live production. An '
            'administrator can revoke your device at any time. Your organisation '
            'can provide the full Terms of Use.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showHelp(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: DesignTokens.d2Surface,
        title: const Text('Help & support'),
        content: const Text(
          'Pairing, roles, and outputs are managed on the SelahCue desktop. '
          'Ask your operator or administrator for help with access.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value, {Color? valueColor}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: SelahSpace.xs),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 104,
          child: Text(
            label,
            style: SelahType.bodySmall.copyWith(
              color: DesignTokens.d2TextSecondary,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: SelahType.bodySmall.copyWith(
              fontWeight: FontWeight.w600,
              color: valueColor ?? DesignTokens.d2Text,
            ),
          ),
        ),
      ],
    ),
  );
}

/// Terminal screen shown when an admin revoked/unpaired this device (RBAC
/// enforcement, Figma 357). The live service is unaffected; the user re-pairs.
class AccessRemovedScreen extends StatelessWidget {
  final VoidCallback onRepair;
  const AccessRemovedScreen({super.key, required this.onRepair});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DesignTokens.d2Base,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            children: [
              const Spacer(),
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: DesignTokens.d2LiveSoft,
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: DesignTokens.d2LiveBorder),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.link_off,
                  color: DesignTokens.d2Live,
                  size: 28,
                ),
              ),
              const SizedBox(height: SelahSpace.gutter),
              Semantics(
                header: true,
                child: Text(
                  'Access removed',
                  textAlign: TextAlign.center,
                  style: SelahType.h1.copyWith(color: DesignTokens.d2Text),
                ),
              ),
              const SizedBox(height: SelahSpace.sm),
              Text(
                'An administrator unpaired this device. Your role and keys are '
                'no longer valid.',
                textAlign: TextAlign.center,
                style: SelahType.body.copyWith(
                  color: DesignTokens.d2TextSecondary,
                ),
              ),
              const SizedBox(height: SelahSpace.xl + 2),
              SelahCard(
                color: DesignTokens.d2PreviewSoft,
                borderColor: DesignTokens.d2PreviewBorder,
                padding: const EdgeInsets.symmetric(
                  horizontal: SelahSpace.lg,
                  vertical: SelahSpace.md,
                ),
                radius: SelahRadius.control,
                child: Row(
                  children: [
                    const Icon(
                      Icons.check_circle_outline,
                      color: DesignTokens.d2Preview,
                      size: 18,
                    ),
                    const SizedBox(width: SelahSpace.xs),
                    Expanded(
                      child: Text(
                        'The live service is unaffected — the desktop keeps '
                        'running.',
                        style: SelahType.bodySmall.copyWith(
                          color: DesignTokens.d2Preview,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              SelahButton(
                label: 'Scan QR to pair again',
                icon: Icons.qr_code_scanner,
                variant: SelahButtonVariant.primary,
                height: 54,
                onPressed: onRepair,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The granted-role chip shown in the app bar (the real backend role — the
/// 7-role design vocabulary is a tracked follow-up, ClickUp 86ajxuf81 /
/// 86ajxufbg). Tone-coded but always carrying the text label (WCAG 1.4.1).
/// Rebuilds with the controller so a role change on reconnect is reflected.
class RoleBadge extends StatelessWidget {
  final LiveController live;
  const RoleBadge({super.key, required this.live});

  /// The role→tone table now lives beside the tone vocabulary in
  /// `primitives.dart`, because the permission sheet's `ROLES THAT CAN …` chips
  /// have to agree with this badge — two tables would eventually disagree and
  /// paint the same role two colours on two screens. Kept as an alias so the
  /// symbol call sites already reach for still resolves.
  static SelahTone toneFor(MobileRole r) => roleTone(r);

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: live,
    builder: (context, _) => Padding(
      padding: const EdgeInsets.only(right: 6),
      child: Center(
        child: StatusBadge(
          text: live.role.label.toUpperCase(),
          tone: toneFor(live.role),
          dot: true,
          large: true,
          // "PRODUCER" is read letter-by-letter by some VoiceOver voices.
          semanticLabel: 'Role: ${live.role.label}',
        ),
      ),
    ),
  );
}
