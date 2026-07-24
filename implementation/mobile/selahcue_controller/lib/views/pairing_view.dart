/// Pairing view (V in MVC): scan the operator's QR (or paste the invite URI) and
/// name this device. All logic lives in [PairingController]; this is widgets only.
library;

import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../controllers/discovery_controller.dart';
import '../controllers/pairing_controller.dart';
import '../models/discovery.dart';
import 'controller_view.dart';

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
    final uri = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const ScanView()),
    );
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
                Text('${h.host}:${h.port}',
                    style: const TextStyle(fontSize: 12)),
                const SizedBox(height: 12),
                const Text('Host fingerprint',
                    style: TextStyle(fontSize: 12)),
                SelectableText(
                  h.fingerprint,
                  style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 20,
                      fontWeight: FontWeight.bold),
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

  Future<void> _pair() async {
    final name = _nameField.text.trim().isEmpty
        ? _defaultDeviceName()
        : _nameField.text.trim();
    final outcome = await _controller.pair(_uriField.text, name);
    if (outcome == null || !mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) =>
            ControllerView(session: outcome.session, stored: outcome.stored)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pair with SelahCue')),
      body: ListenableBuilder(
        listenable: _controller,
        builder: (context, _) {
          final busy = _controller.busy;
          return Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'On the SelahCue host, press P to show a pairing QR, then scan '
                  'it — or paste the invite below.',
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: busy ? null : _scan,
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan the pairing QR'),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _uriField,
                  enabled: !busy,
                  decoration: const InputDecoration(
                    labelText: 'or paste the invite (selahcue://pair?...)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _nameField,
                  enabled: !busy,
                  decoration: const InputDecoration(
                    labelText: 'This device shows to the operator as',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 20),
                ListenableBuilder(
                  listenable: _discovery,
                  builder: (context, _) => Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text('Nearby hosts',
                                style: TextStyle(fontWeight: FontWeight.w600)),
                          ),
                          _discovery.searching
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : IconButton(
                                  tooltip: 'Search the network',
                                  onPressed: busy ? null : _discovery.refresh,
                                  icon: const Icon(Icons.refresh),
                                ),
                        ],
                      ),
                      if (_discovery.hosts.isEmpty && !_discovery.searching)
                        const Text('None found yet — tap refresh.',
                            style: TextStyle(fontSize: 12)),
                      for (final h in _discovery.hosts)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.cast),
                          title: Text(h.name),
                          subtitle: Text('${h.host}:${h.port}'),
                          onTap: busy ? null : () => _pairDiscovered(h),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton.tonal(
                  onPressed: busy ? null : _pair,
                  child: busy
                      ? const Padding(
                          padding: EdgeInsets.all(4),
                          child: Text('Waiting for the host to allow…'),
                        )
                      : const Text('Pair'),
                ),
                if (_controller.error != null) ...[
                  const SizedBox(height: 16),
                  Text(_controller.error!,
                      style:
                          TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
              ],
            ),
          );
        },
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
