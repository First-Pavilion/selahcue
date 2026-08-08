/// Pairing view (V in MVC): scan the operator's QR (or paste the invite URI) and
/// name this device. All logic lives in [PairingController]; this is widgets only.
library;

import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../models/design_tokens.dart';
import '../controllers/discovery_controller.dart';
import '../controllers/pairing_controller.dart';
import '../models/discovery.dart';
import 'controller_view.dart';
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

  @override
  void initState() {
    super.initState();
    _nameField.text = _defaultDeviceName();
    // Nearby hosts is the promoted primary path — start a discovery pass on
    // entry so the foregrounded list fills itself instead of stranding a
    // first-run user on an empty "None found…" until they find the refresh icon.
    _discovery.refresh();
  }

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
    final code = await showDialog<String>(
      context: context,
      builder: (context) {
        final field = TextEditingController();
        var confirmed = false;
        return StatefulBuilder(
          builder: (context, setInner) => AlertDialog(
            title: Text('Pair with ${h.name}'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${h.host}:${h.port}',
                  style: const TextStyle(fontSize: 12),
                ),
                const SizedBox(height: 12),
                const Text('Host fingerprint', style: TextStyle(fontSize: 12)),
                SelectableText(
                  h.fingerprint,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: confirmed,
                  onChanged: (v) => setInner(() => confirmed = v ?? false),
                  title: const Text(
                    'This matches the fingerprint the host shows',
                    style: TextStyle(fontSize: 13),
                  ),
                ),
                TextField(
                  controller: field,
                  enabled: confirmed,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                    labelText: 'Pairing code (on the host: press P)',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (v) =>
                      confirmed ? Navigator.of(context).pop(v) : null,
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: confirmed
                    ? () => Navigator.of(context).pop(field.text)
                    : null,
                child: const Text('Pair'),
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
            const SizedBox(height: 24),
            const Text(
              'Waiting for the host to allow this device',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: DesignTokens.textPrimary,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'You appear as "$name" — the operator approves you (with a role) '
              'from the Remote Control console.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 13,
                color: DesignTokens.textMuted,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'This request expires in about 2 minutes.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: DesignTokens.textMuted),
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
      appBar: AppBar(title: const Text('Pair with SelahCue')),
      body: ResponsiveBody(
        child: ListenableBuilder(
          listenable: _controller,
          builder: (context, _) {
            final busy = _controller.busy;
            if (busy) return _waiting();
            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Brand header (design handoff §3): logo mark + wordmark.
                Row(
                  children: [
                    Image.asset(
                      'assets/selahcue-logo.png',
                      width: 32,
                      height: 32,
                      semanticLabel: '',
                    ),
                    const SizedBox(width: 10),
                    const Text(
                      'SelahCue',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: DesignTokens.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                const Text(
                  'Connect to a host',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: DesignTokens.textPrimary,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'On the SelahCue host, press P to start pairing. Pick it '
                  'below, scan its QR, or paste the invite.',
                  style: TextStyle(fontSize: 13, color: DesignTokens.textMuted),
                ),
                const SizedBox(height: 20),

                // Nearby hosts (primary path)
                ListenableBuilder(
                  listenable: _discovery,
                  builder: (context, _) => Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'DISCOVERED ON YOUR NETWORK',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.7,
                                color: DesignTokens.textMuted,
                              ),
                            ),
                          ),
                          _discovery.searching
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : IconButton(
                                  tooltip: 'Search the network',
                                  onPressed: _discovery.refresh,
                                  icon: const Icon(
                                    Icons.refresh,
                                    color: DesignTokens.textMuted,
                                  ),
                                ),
                        ],
                      ),
                      if (_discovery.hosts.isEmpty && !_discovery.searching)
                        const Padding(
                          padding: EdgeInsets.only(bottom: 4),
                          child: Text(
                            'None found — make sure this phone is on the same '
                            'Wi-Fi as the host, then tap refresh.',
                            style: TextStyle(
                              fontSize: 12,
                              color: DesignTokens.textMuted,
                            ),
                          ),
                        ),
                      for (final h in _discovery.hosts)
                        Card(
                          color: DesignTokens.bgPanel,
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            leading: const Icon(
                              Icons.cast,
                              color: DesignTokens.accentBrand,
                            ),
                            title: Text(
                              h.name,
                              style: const TextStyle(
                                color: DesignTokens.textPrimary,
                              ),
                            ),
                            subtitle: Text(
                              '${h.host}:${h.port}',
                              style: const TextStyle(
                                color: DesignTokens.textMuted,
                              ),
                            ),
                            trailing: const Icon(
                              Icons.chevron_right,
                              color: DesignTokens.textMuted,
                            ),
                            onTap: () => _pairDiscovered(h),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Scan QR (primary)
                FilledButton.icon(
                  onPressed: _scan,
                  style: FilledButton.styleFrom(
                    backgroundColor: DesignTokens.accentBrand,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan the pairing QR'),
                ),
                const SizedBox(height: 16),

                // Device name
                TextField(
                  controller: _nameField,
                  style: const TextStyle(color: DesignTokens.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'This device shows to the operator as',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),

                // Paste invite (tucked behind a disclosure)
                Theme(
                  data: Theme.of(
                    context,
                  ).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: const Text(
                      'Enter an invite manually',
                      style: TextStyle(
                        fontSize: 13,
                        color: DesignTokens.textMuted,
                      ),
                    ),
                    children: [
                      TextField(
                        controller: _uriField,
                        style: const TextStyle(color: DesignTokens.textPrimary),
                        decoration: const InputDecoration(
                          labelText: 'selahcue://pair?...',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      FilledButton.tonal(
                        onPressed: _pair,
                        child: const Text('Pair with this invite'),
                      ),
                    ],
                  ),
                ),
                if (_controller.error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _controller.error!,
                    style: const TextStyle(color: DesignTokens.liveInk),
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
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
