/// Pairing view (V in MVC): pick a nearby host, scan the operator's QR, or paste
/// the invite URI, and name this device. All logic lives in [PairingController];
/// this is widgets only.
///
/// Design 2.0: MOBILE-2.0-SPEC §4.1, Figma `342:133`.
library;

import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../controllers/discovery_controller.dart';
import '../controllers/pairing_controller.dart';
import '../models/design_tokens.dart';
import '../models/discovery.dart';
import '../models/selah_theme.dart';
import '../models/stored_session.dart';
import 'controller_view.dart';
import 'widgets/mobile_widgets.dart';
import 'widgets/responsive.dart';

class PairingView extends StatefulWidget {
  const PairingView({super.key});

  @override
  State<PairingView> createState() => _PairingViewState();
}

class _PairingViewState extends State<PairingView> {
  final _discovery = DiscoveryController();
  final _controller = PairingController();
  final _uriField = TextEditingController();
  final _nameField = TextEditingController();

  /// The host this device already holds credentials for, if any — the only
  /// truthful source for the frame's PAIRED chip.
  ///
  /// This screen is reachable in two ways: with no stored session (first run, or
  /// after an explicit unpair, which clears them) and WITH one (the launcher
  /// tried to reconnect and the host was off or had moved). Only the second can
  /// light the chip, and in that case it is genuinely useful — it points at the
  /// host you are already paired to among several on the network.
  StoredSession? _paired;

  @override
  void initState() {
    super.initState();
    _nameField.text = _defaultDeviceName();
    // Nearby hosts is the promoted primary path — start a discovery pass on
    // entry so the foregrounded list fills itself instead of stranding a
    // first-run user on an empty "None found…" until they find the refresh icon.
    _discovery.refresh();
    _loadPaired();
  }

  Future<void> _loadPaired() async {
    StoredSession? stored;
    try {
      stored = await StoredSession.load();
    } on Object {
      // The keystore is unavailable (or there is no platform channel, as under
      // a widget test). The chip is an affordance, not a security control —
      // losing it must never keep the operator off the pairing screen.
      stored = null;
    }
    if (mounted && stored != null) setState(() => _paired = stored);
  }

  bool _isPaired(DiscoveredHost h) =>
      _paired != null && _paired!.host == h.host && _paired!.port == h.port;

  static String _defaultDeviceName() {
    try {
      return '${Platform.localHostname} (${Platform.operatingSystem})';
    } on Object {
      return 'SelahCue controller';
    }
  }

  @override
  void dispose() {
    _discovery.dispose();
    _controller.dispose();
    _uriField.dispose();
    _nameField.dispose();
    super.dispose();
  }

  Future<void> _scan() async {
    final uri = await Navigator.of(
      context,
    ).push<String>(MaterialPageRoute(builder: (_) => const ScanView()));
    if (uri != null) {
      _uriField.text = uri;
      await _pair();
    }
  }

  Future<void> _pairDiscovered(DiscoveredHost h) async {
    // SECURITY: a nearby host is discovered from the NETWORK, so its pin is
    // untrusted (a rogue can advertise its own). Before the single-use code is
    // disclosed, the operator MUST confirm the discovered fingerprint matches
    // the one the host prints (press P) — otherwise the code could be phished.
    // The flow is unchanged by the re-skin; only its surface colours moved.
    final code = await showDialog<String>(
      context: context,
      builder: (context) {
        final field = TextEditingController();
        var confirmed = false;
        return StatefulBuilder(
          builder: (context, setInner) => AlertDialog(
            backgroundColor: DesignTokens.d2Surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(SelahRadius.card),
            ),
            title: Text(
              'Pair with ${h.name}',
              style: SelahType.h2.copyWith(color: DesignTokens.d2Text),
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${h.host}:${h.port}',
                  style: SelahType.caption.copyWith(
                    color: DesignTokens.d2TextSecondary,
                  ),
                ),
                const SizedBox(height: SelahSpace.md),
                Text(
                  'Host fingerprint',
                  style: SelahType.caption.copyWith(
                    color: DesignTokens.d2TextSecondary,
                  ),
                ),
                const SizedBox(height: 6),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: SelahSpace.md,
                    vertical: SelahSpace.sm,
                  ),
                  decoration: BoxDecoration(
                    color: DesignTokens.d2Inset,
                    borderRadius: BorderRadius.circular(SelahRadius.badge),
                    border: Border.all(color: DesignTokens.d2Border),
                  ),
                  child: SelectableText(
                    h.fingerprint,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: DesignTokens.d2Text,
                    ),
                  ),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: confirmed,
                  onChanged: (v) => setInner(() => confirmed = v ?? false),
                  title: Text(
                    'This matches the fingerprint the host shows',
                    style: SelahType.bodySmall.copyWith(
                      color: DesignTokens.d2Text,
                    ),
                  ),
                ),
                TextField(
                  controller: field,
                  enabled: confirmed,
                  textCapitalization: TextCapitalization.characters,
                  style: SelahType.body.copyWith(color: DesignTokens.d2Text),
                  decoration: const InputDecoration(
                    labelText: 'Pairing code (on the host: press P)',
                  ),
                  onSubmitted: (v) =>
                      confirmed ? Navigator.of(context).pop(v) : null,
                ),
              ],
            ),
            actions: [
              SelahButton(
                label: 'Cancel',
                variant: SelahButtonVariant.ghost,
                onPressed: () => Navigator.of(context).pop(),
              ),
              SelahButton(
                label: 'Pair',
                variant: SelahButtonVariant.primary,
                onPressed: confirmed
                    ? () => Navigator.of(context).pop(field.text)
                    : null,
              ),
            ],
          ),
        );
      },
    );
    if (code == null || code.trim().isEmpty) return;
    _uriField.text = h.inviteUri(code);
    await _pair();
  }

  Widget _waiting() {
    final name = _nameField.text.trim().isEmpty
        ? _defaultDeviceName()
        : _nameField.text.trim();
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 30,
              height: 30,
              child: CircularProgressIndicator(strokeWidth: 3),
            ),
            const SizedBox(height: SelahSpace.section),
            Text(
              'Waiting for the host to allow this device',
              textAlign: TextAlign.center,
              style: SelahType.h2.copyWith(
                fontWeight: FontWeight.w600,
                color: DesignTokens.d2Text,
              ),
            ),
            const SizedBox(height: SelahSpace.sm),
            Text(
              'You appear as "$name" — the operator approves you (with a role) '
              'from the Remote Control console.',
              textAlign: TextAlign.center,
              style: SelahType.bodySmall.copyWith(
                color: DesignTokens.d2TextSecondary,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'This request expires in about 2 minutes.',
              textAlign: TextAlign.center,
              style: SelahType.caption.copyWith(
                color: DesignTokens.d2TextSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pair() async {
    final name = _nameField.text.trim().isEmpty
        ? _defaultDeviceName()
        : _nameField.text.trim();
    final outcome = await _controller.pair(_uriField.text, name);
    if (outcome == null || !mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) =>
            ControllerView(session: outcome.session, stored: outcome.stored),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DesignTokens.d2Base,
      body: SafeArea(
        child: ResponsiveBody(
          child: ListenableBuilder(
            listenable: _controller,
            builder: (context, _) {
              if (_controller.busy) return _waiting();
              return ListView(
                padding: const EdgeInsets.all(SelahSpace.gutter),
                children: [
                  // Brand header (spec §4.1): the violet mark on the dark
                  // surface, no background tile.
                  Row(
                    children: [
                      Image.asset(
                        'assets/selahcue-logo.png',
                        width: 32,
                        height: 32,
                        semanticLabel: '',
                      ),
                      const SizedBox(width: SelahSpace.sm),
                      Text(
                        'SelahCue',
                        style: SelahType.appBar.copyWith(
                          color: DesignTokens.d2Text,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: SelahSpace.lg),
                  Text(
                    'Connect to a host',
                    style: SelahType.h2.copyWith(color: DesignTokens.d2Text),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'On the SelahCue host, press P to start pairing. Pick it '
                    'below, scan its QR, or paste the invite.',
                    style: SelahType.bodySmall.copyWith(
                      color: DesignTokens.d2TextSecondary,
                    ),
                  ),
                  const SizedBox(height: SelahSpace.gutter),

                  // Nearby hosts (primary path)
                  ListenableBuilder(
                    listenable: _discovery,
                    builder: (context, _) => Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SectionLabel(
                          'DISCOVERED ON YOUR NETWORK',
                          trailing: _discovery.searching
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : IconButton(
                                  tooltip: 'Search the network',
                                  constraints: const BoxConstraints(
                                    minWidth: kSelahMinTouchTarget,
                                    minHeight: kSelahMinTouchTarget,
                                  ),
                                  onPressed: _discovery.refresh,
                                  icon: const Icon(
                                    Icons.refresh,
                                    color: DesignTokens.d2TextSecondary,
                                  ),
                                ),
                        ),
                        if (_discovery.hosts.isEmpty && !_discovery.searching)
                          Padding(
                            padding: const EdgeInsets.only(
                              bottom: SelahSpace.xs,
                            ),
                            child: Text(
                              'None found — make sure this phone is on the '
                              'same Wi-Fi as the host, then tap refresh.',
                              style: SelahType.caption.copyWith(
                                color: DesignTokens.d2TextSecondary,
                              ),
                            ),
                          ),
                        for (final h in _discovery.hosts)
                          Padding(
                            padding: const EdgeInsets.only(
                              top: SelahSpace.sm,
                            ),
                            child: _HostRow(
                              host: h,
                              paired: _isPaired(h),
                              onConnect: () => _pairDiscovered(h),
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: SelahSpace.xl),

                  // Scan QR (primary)
                  SelahButton(
                    label: 'Scan the pairing QR',
                    icon: Icons.qr_code_scanner,
                    variant: SelahButtonVariant.primary,
                    height: 54,
                    textStyle: SelahType.cta.copyWith(fontSize: 15),
                    onPressed: _scan,
                  ),
                  const SizedBox(height: SelahSpace.xl),

                  // Device name
                  SelahInput(
                    controller: _nameField,
                    label: 'This device shows to the operator as',
                  ),
                  const SizedBox(height: SelahSpace.xs),

                  // Paste invite (tucked behind a disclosure)
                  Theme(
                    data: Theme.of(
                      context,
                    ).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: Text(
                        'Enter an invite manually',
                        style: SelahType.bodySmall.copyWith(
                          color: DesignTokens.d2TextSecondary,
                        ),
                      ),
                      children: [
                        SelahInput(
                          controller: _uriField,
                          label: 'selahcue://pair?...',
                        ),
                        const SizedBox(height: SelahSpace.sm),
                        SelahButton(
                          label: 'Pair with this invite',
                          onPressed: _pair,
                        ),
                      ],
                    ),
                  ),
                  if (_controller.error != null) ...[
                    const SizedBox(height: SelahSpace.md),
                    Text(
                      _controller.error!,
                      style: SelahType.bodySmall.copyWith(
                        fontWeight: FontWeight.w500,
                        color: DesignTokens.d2Live,
                      ),
                    ),
                  ],
                  const SizedBox(height: SelahSpace.gutter),
                  const _QrHintCard(),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

/// One discovered host (spec §4.1). A host this device already holds credentials
/// for takes the selected row treatment and a PAIRED chip instead of a Connect
/// button — the chip is a statement of fact, so it is only ever drawn from a
/// real stored session.
class _HostRow extends StatelessWidget {
  final DiscoveredHost host;
  final bool paired;
  final VoidCallback onConnect;

  const _HostRow({
    required this.host,
    required this.paired,
    required this.onConnect,
  });

  @override
  Widget build(BuildContext context) => SelahListRow(
    state: paired ? SelahRowState.selected : SelahRowState.normal,
    onTap: onConnect,
    semanticLabel: paired
        ? 'Pair again with ${host.name}, ${host.host}, already paired'
        : 'Pair with ${host.name}, ${host.host}',
    child: Row(
      children: [
        const Icon(
          Icons.desktop_windows_outlined,
          size: 20,
          color: DesignTokens.d2TextSecondary,
        ),
        const SizedBox(width: SelahSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                host.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: SelahType.rowTitle.copyWith(
                  fontWeight: FontWeight.w700,
                  color: DesignTokens.d2Text,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '${host.host}:${host.port}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: SelahType.caption.copyWith(
                  color: DesignTokens.d2TextSecondary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: SelahSpace.xs),
        if (paired)
          const StatusBadge(text: 'PAIRED', tone: SelahTone.preview, dot: true)
        else
          SizedBox(
            width: 85,
            child: SelahButton(
              label: 'Connect',
              variant: SelahButtonVariant.primary,
              onPressed: onConnect,
            ),
          ),
      ],
    ),
  );
}

/// The QR hint card (spec §4.1). It is a real control — tapping it opens the
/// scanner — rather than a decorative panel, because a card that looks tappable
/// and is not is the same dead end as a fake affordance.
class _QrHintCard extends StatelessWidget {
  const _QrHintCard();

  @override
  Widget build(BuildContext context) => SelahCard(
    padding: const EdgeInsets.symmetric(
      horizontal: SelahSpace.gutter,
      vertical: SelahSpace.section,
    ),
    child: Column(
      children: [
        const Icon(
          Icons.qr_code_2,
          size: 84,
          color: DesignTokens.d2TextSecondary,
        ),
        const SizedBox(height: SelahSpace.md),
        Text(
          'Scan the QR on the desktop to pair a new booth',
          textAlign: TextAlign.center,
          style: SelahType.bodySmall.copyWith(
            color: DesignTokens.d2TextSecondary,
          ),
        ),
      ],
    ),
  );
}

/// Full-screen camera scan; pops with the first `selahcue://pair?...` payload seen.
class ScanView extends StatefulWidget {
  const ScanView({super.key});

  @override
  State<ScanView> createState() => _ScanViewState();
}

class _ScanViewState extends State<ScanView> {
  bool _handled = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DesignTokens.d2Base,
      appBar: AppBar(title: const Text('Scan the pairing QR')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_handled) return;
          for (final barcode in capture.barcodes) {
            final value = barcode.rawValue;
            if (value != null && value.startsWith('selahcue://pair?')) {
              _handled = true;
              Navigator.of(context).pop(value);
              return;
            }
          }
        },
      ),
    );
  }
}
