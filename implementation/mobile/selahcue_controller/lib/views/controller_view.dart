/// Controller view (V in MVC) — the tabbed Producer shell (revamp 86ajpx7bd).
/// A bottom tab bar (Live · Plan · Scripture · Timer) with a PERSISTENT
/// emergency strip above it on every tab, a compact top bar (plan name · LIVE
/// pill · unpair), and a non-blocking reconnecting banner. All logic lives in
/// [LiveController]; this is widgets only.
library;

import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../controllers/live_controller.dart';
import '../models/design_tokens.dart';
import '../models/discovery.dart' show pinFingerprint;
import '../models/rbac.dart';
import '../models/session.dart';
import '../models/settings.dart';
import '../models/tab_scope.dart';
import 'widgets/responsive.dart';
import '../models/stored_session.dart';
import 'pairing_view.dart';
import 'tabs/live_tab.dart';
import 'tabs/plan_tab.dart';
import 'tabs/scripture_tab.dart';
import 'tabs/timer_tab.dart';
import 'widgets/mobile_widgets.dart';

class ControllerView extends StatefulWidget {
  // The interface (not the concrete SelahSession) so the shell is widget-testable
  // with a fake; production callers pass a SelahSession, which implements it.
  final ControllerSession session;
  final StoredSession stored;

  /// Optional reconnect factory, forwarded to [LiveController] (a test seam so
  /// the revoked/reconnect path can be exercised without a real socket).
  final Future<SelahSession> Function({
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
      backgroundColor: DesignTokens.bgPanel,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
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
  /// "view only" tooltip (the ◐ marker from the design).
  NavigationDestination _destinationFor(TabSpec spec) {
    final (IconData icon, IconData selected) = switch (spec.tab) {
      ControllerTab.live => (Icons.play_arrow_outlined, Icons.play_arrow),
      ControllerTab.plan => (Icons.list_alt_outlined, Icons.list_alt),
      ControllerTab.scripture => (Icons.menu_book_outlined, Icons.menu_book),
      ControllerTab.timer => (Icons.timer_outlined, Icons.timer),
    };
    final label = _tabTitle(spec.tab);
    Widget wrap(IconData i) => spec.viewOnly
        ? Badge(
            backgroundColor: DesignTokens.textMuted,
            smallSize: 7,
            child: Icon(i),
          )
        : Icon(i);
    return NavigationDestination(
      icon: wrap(icon),
      selectedIcon: wrap(selected),
      label: label,
      tooltip: spec.viewOnly ? '$label — view only' : label,
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
        final pages = [for (final s in specs) _pageFor(s.tab)];
        final currentTitle = _tabTitle(specs[tab].tab);
        return Scaffold(
          backgroundColor: DesignTokens.bgBase,
          appBar: AppBar(
            backgroundColor: DesignTokens.bgPanel,
            elevation: 0,
            titleSpacing: 16,
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
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: DesignTokens.textPrimary,
                    ),
                  ),
                ),
                if (onAir) ...[
                  const SizedBox(width: 8),
                  const StatusBadge(
                    text: '● LIVE',
                    color: DesignTokens.liveFill,
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
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: DesignTokens.textMuted,
                    ),
                  ),
                ),
              ),
              // About & connection lives on the top bar, not a nav drawer —
              // a drawer competing with the bottom tabs is a second nav surface.
              IconButton(
                icon: const Icon(
                  Icons.info_outline,
                  color: DesignTokens.textMuted,
                ),
                tooltip: 'About & connection',
                onPressed: _showAbout,
              ),
            ],
          ),
          body: Column(
            children: [
              // Two distinct truths, both of which mean "your taps won't be
              // sent": the link is down, or it is back but this device has not
              // yet re-read the host. The second is the one that used to leave
              // controls live against a stale view (FR-097).
              if (_live.syncing)
                Container(
                  width: double.infinity,
                  color: DesignTokens.warnFill,
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text(
                    _live.reconnecting
                        ? 'Reconnecting to the host… your taps won’t be sent'
                        : 'Syncing live state…',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                )
              else if (_live.error != null)
                Material(
                  color: DesignTokens.liveFill,
                  child: InkWell(
                    onTap: _live.dismissError,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              _live.error!,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.white,
                              ),
                            ),
                          ),
                          const Text(
                            'Dismiss',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              // Constrain + centre the control column so it doesn't stretch
              // edge-to-edge on a tablet / in landscape (design handoff §1).
              Expanded(
                child: ResponsiveBody(
                  child: IndexedStack(index: tab, children: pages),
                ),
              ),
              // Persistent emergency chrome — on every tab, above the nav.
              // Hidden entirely for a role that can neither blackout nor clear.
              if (_live.can(Capability.blackout) ||
                  _live.can(Capability.clearLive))
                ResponsiveBody(child: EmergencyStrip(live: _live)),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            backgroundColor: DesignTokens.bgPanel,
            indicatorColor: DesignTokens.accentBrand.withValues(alpha: 0.22),
            selectedIndex: tab,
            onDestinationSelected: (i) => setState(() => _tab = i),
            destinations: [for (final s in specs) _destinationFor(s)],
          ),
        );
      },
    );
  }
}

/// The About & connection sheet: what this device is paired to, its role, the
/// certificate fingerprint (for trust verification), live connection status,
/// and Disconnect (un-pair). Presented as a modal sheet from the top bar so it
/// never becomes a second navigation surface alongside the bottom tabs.
/// The Config / About session sheet (Figma 363-124), opened from the top-bar ⓘ:
/// CONNECTION (status/host/role/fingerprint + disconnect), PREFERENCES (keep
/// awake / haptics / reduce motion), and ABOUT (version / licenses / help).
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
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
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
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SelahCue',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: DesignTokens.textPrimary,
                        ),
                      ),
                      Text(
                        'Controller · ${live.role.label}',
                        style: const TextStyle(
                          fontSize: 12,
                          letterSpacing: 1.5,
                          color: DesignTokens.textMuted,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const Divider(color: DesignTokens.border, height: 28),
              const Padding(
                padding: EdgeInsets.only(bottom: 4),
                child: Text(
                  'CONNECTION',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.7,
                    color: DesignTokens.textMuted,
                  ),
                ),
              ),
              // Status tracks the live connection while the sheet is open.
              ListenableBuilder(
                listenable: live,
                builder: (context, _) => _row(
                  'Status',
                  live.reconnecting ? 'Reconnecting…' : 'Connected',
                  valueColor: live.reconnecting
                      ? DesignTokens.warnInk
                      : DesignTokens.previewInk,
                ),
              ),
              _row('Host', '${stored.host}:${stored.port}'),
              _row('Role', live.role.label),
              _row('Fingerprint', pinFingerprint(stored.pinHex)),
              const Padding(
                padding: EdgeInsets.only(top: 6, bottom: 12),
                child: Text(
                  'Your role is assigned & managed on the desktop.',
                  style: TextStyle(fontSize: 12, color: DesignTokens.textMuted),
                ),
              ),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: DesignTokens.liveInk,
                  side: const BorderSide(color: DesignTokens.liveInk),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                icon: const Icon(Icons.link_off),
                label: const Text('Disconnect this device'),
                onPressed: onDisconnect,
              ),
              const Divider(color: DesignTokens.border, height: 28),
              _sectionLabel('PREFERENCES'),
              // Rebuilds with the controller so the switches reflect the persisted
              // state and each toggle applies immediately (keep-awake → wakelock).
              ListenableBuilder(
                listenable: settings,
                builder: (context, _) => Column(
                  children: [
                    _toggle(
                      'Keep screen awake',
                      settings.keepAwake,
                      settings.setKeepAwake,
                    ),
                    _toggle(
                      'Haptic feedback',
                      settings.haptics,
                      settings.setHaptics,
                    ),
                    _toggle(
                      'Reduce motion',
                      settings.reduceMotion,
                      settings.setReduceMotion,
                    ),
                  ],
                ),
              ),
              const Divider(color: DesignTokens.border, height: 28),
              _sectionLabel('ABOUT'),
              FutureBuilder<PackageInfo>(
                future: PackageInfo.fromPlatform(),
                builder: (context, snap) => _row(
                  'Version',
                  snap.hasData
                      ? '${snap.data!.version} (${snap.data!.buildNumber})'
                      : '…',
                ),
              ),
              _linkRow('Privacy policy', () => _showPrivacy(context)),
              _linkRow('Terms of use', () => _showTerms(context)),
              _linkRow(
                'Open-source licenses',
                () => showLicensePage(
                  context: context,
                  applicationName: 'SelahCue Controller',
                ),
              ),
              _linkRow('Help & support', () => _showHelp(context)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionLabel(String text) => Padding(
    padding: const EdgeInsets.only(bottom: 4),
    child: Text(
      text,
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w800,
        letterSpacing: 0.7,
        color: DesignTokens.textMuted,
      ),
    ),
  );

  Widget _toggle(
    String label,
    bool value,
    Future<void> Function(bool) onChanged,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 14,
              color: DesignTokens.textPrimary,
            ),
          ),
        ),
        Switch(value: value, onChanged: (v) => onChanged(v)),
      ],
    ),
  );

  Widget _linkRow(String label, VoidCallback onTap) => InkWell(
    onTap: onTap,
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: DesignTokens.textPrimary,
              ),
            ),
          ),
          const Icon(
            Icons.chevron_right,
            size: 18,
            color: DesignTokens.textMuted,
          ),
        ],
      ),
    ),
  );

  void _showPrivacy(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: DesignTokens.bgPanel,
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
        backgroundColor: DesignTokens.bgPanel,
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
        backgroundColor: DesignTokens.bgPanel,
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
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 104,
          child: Text(
            label,
            style: const TextStyle(fontSize: 13, color: DesignTokens.textMuted),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: valueColor ?? DesignTokens.textPrimary,
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
      backgroundColor: DesignTokens.bgBase,
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
                  color: DesignTokens.liveFill.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(28),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.link_off,
                  color: DesignTokens.liveInk,
                  size: 28,
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Access removed',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: DesignTokens.textPrimary,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'An administrator unpaired this device. Your role and keys are '
                'no longer valid.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: DesignTokens.textMuted),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  color: DesignTokens.previewFill.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: DesignTokens.previewInk),
                ),
                child: const Row(
                  children: [
                    Icon(
                      Icons.check_circle_outline,
                      color: DesignTokens.previewInk,
                      size: 18,
                    ),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'The live service is unaffected — the desktop keeps '
                        'running.',
                        style: TextStyle(
                          fontSize: 13,
                          color: DesignTokens.previewInk,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: DesignTokens.accentBrand,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan QR to pair again'),
                  onPressed: onRepair,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The granted-role chip shown in the app bar (the real backend role — the
/// 7-role design vocabulary is a tracked follow-up). Colour-coded but always
/// carries the text label (WCAG 1.4.1). Rebuilds with the controller so a role
/// change on reconnect is reflected.
class RoleBadge extends StatelessWidget {
  final LiveController live;
  const RoleBadge({super.key, required this.live});

  static Color colorFor(MobileRole r) {
    switch (r) {
      case MobileRole.operator:
        return DesignTokens.accentBrand;
      case MobileRole.producer:
        return DesignTokens.previewInk;
      case MobileRole.assistant:
        return DesignTokens.warnInk;
      case MobileRole.viewer:
      case MobileRole.unknown:
        return DesignTokens.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: live,
    builder: (context, _) => Padding(
      padding: const EdgeInsets.only(right: 6),
      child: Center(
        child: StatusBadge(
          text: live.role.label.toUpperCase(),
          color: colorFor(live.role),
        ),
      ),
    ),
  );
}
