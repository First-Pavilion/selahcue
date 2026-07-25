/// Controller view (V in MVC) — the tabbed Producer shell (revamp 86ajpx7bd).
/// A bottom tab bar (Live · Plan · Scripture · Timer) with a PERSISTENT
/// emergency strip above it on every tab, a compact top bar (plan name · LIVE
/// pill · unpair), and a non-blocking reconnecting banner. All logic lives in
/// [LiveController]; this is widgets only.
library;

import 'package:flutter/material.dart';

import '../controllers/live_controller.dart';
import '../models/design_tokens.dart';
import '../models/discovery.dart' show pinFingerprint;
import '../models/session.dart';
import '../models/stored_session.dart';
import 'pairing_view.dart';
import 'tabs/live_tab.dart';
import 'tabs/plan_tab.dart';
import 'tabs/scripture_tab.dart';
import 'tabs/timer_tab.dart';
import 'widgets/mobile_widgets.dart';

class ControllerView extends StatefulWidget {
  final SelahSession session;
  final StoredSession stored;

  const ControllerView({super.key, required this.session, required this.stored});

  @override
  State<ControllerView> createState() => _ControllerViewState();
}

class _ControllerViewState extends State<ControllerView> {
  late final LiveController _live;
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    _live = LiveController(session: widget.session, stored: widget.stored);
  }

  @override
  void dispose() {
    _live.dispose();
    super.dispose();
  }

  Future<void> _unpair() async {
    await _live.unpair();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const PairingView()));
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
      builder: (sheetContext) => _AboutSheet(
        stored: widget.stored,
        live: _live,
        onDisconnect: () {
          Navigator.of(sheetContext).pop(); // close the sheet first
          _unpair();
        },
      ),
    );
  }

  static const _titles = ['Live', 'Plan', 'Scripture', 'Timer'];

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
        final view = _live.view;
        final onAir = view?.liveIndex != null ||
            view?.liveScripture != null ||
            view?.liveFreeText != null;
        final tabs = [
          LiveTab(live: _live),
          PlanTab(live: _live),
          ScriptureTab(live: _live),
          TimerTab(live: _live),
        ];
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
                          : _titles[_tab],
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: DesignTokens.textPrimary)),
                ),
                if (onAir) ...[
                  const SizedBox(width: 8),
                  const StatusBadge(text: '● LIVE', color: DesignTokens.liveFill),
                ],
              ],
            ),
            actions: [
              // A wall clock for service-timing awareness (matches the design);
              // it refreshes on each 1s poll rebuild.
              Padding(
                padding: const EdgeInsets.only(right: 4),
                child: Center(
                  child: Text(_wallClock(),
                      style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: DesignTokens.textMuted)),
                ),
              ),
              // About & connection lives on the top bar, not a nav drawer —
              // a drawer competing with the bottom tabs is a second nav surface.
              IconButton(
                icon: const Icon(Icons.info_outline,
                    color: DesignTokens.textMuted),
                tooltip: 'About & connection',
                onPressed: _showAbout,
              ),
            ],
          ),
          body: Column(
            children: [
              if (_live.reconnecting)
                Container(
                  width: double.infinity,
                  color: DesignTokens.warnFill,
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: const Text('Reconnecting to the host…',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white)),
                )
              else if (_live.error != null)
                Material(
                  color: DesignTokens.liveFill,
                  child: InkWell(
                    onTap: _live.dismissError,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(_live.error!,
                                style: const TextStyle(
                                    fontSize: 12, color: Colors.white)),
                          ),
                          const Text('Dismiss',
                              style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white)),
                        ],
                      ),
                    ),
                  ),
                ),
              Expanded(child: IndexedStack(index: _tab, children: tabs)),
              // Persistent emergency chrome — on every tab, above the nav.
              EmergencyStrip(live: _live),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            backgroundColor: DesignTokens.bgPanel,
            indicatorColor: DesignTokens.accentBrand.withValues(alpha: 0.22),
            selectedIndex: _tab,
            onDestinationSelected: (i) => setState(() => _tab = i),
            destinations: const [
              NavigationDestination(
                  icon: Icon(Icons.play_arrow_outlined),
                  selectedIcon: Icon(Icons.play_arrow),
                  label: 'Live'),
              NavigationDestination(
                  icon: Icon(Icons.list_alt_outlined),
                  selectedIcon: Icon(Icons.list_alt),
                  label: 'Plan'),
              NavigationDestination(
                  icon: Icon(Icons.menu_book_outlined),
                  selectedIcon: Icon(Icons.menu_book),
                  label: 'Scripture'),
              NavigationDestination(
                  icon: Icon(Icons.timer_outlined),
                  selectedIcon: Icon(Icons.timer),
                  label: 'Timer'),
            ],
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
class _AboutSheet extends StatelessWidget {
  final StoredSession stored;
  final LiveController live;
  final VoidCallback onDisconnect;

  const _AboutSheet({
    required this.stored,
    required this.live,
    required this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: DesignTokens.accentBrand,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  alignment: Alignment.center,
                  child: const Text('S',
                      style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: Colors.white)),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text('SelahCue',
                        style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: DesignTokens.textPrimary)),
                    Text('Controller · Producer',
                        style: TextStyle(
                            fontSize: 12,
                            letterSpacing: 1.5,
                            color: DesignTokens.textMuted)),
                  ],
                ),
              ],
            ),
            const Divider(color: DesignTokens.border, height: 28),
            const Padding(
              padding: EdgeInsets.only(bottom: 4),
              child: Text('CONNECTION',
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.7,
                      color: DesignTokens.textMuted)),
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
            _row('Role', 'Producer'),
            _row('Fingerprint', pinFingerprint(stored.pinHex)),
            const SizedBox(height: 16),
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
          ],
        ),
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
              child: Text(label,
                  style: const TextStyle(
                      fontSize: 13, color: DesignTokens.textMuted)),
            ),
            Expanded(
              child: Text(value,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: valueColor ?? DesignTokens.textPrimary)),
            ),
          ],
        ),
      );
}
