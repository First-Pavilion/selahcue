/// Nearby-host discovery (C in MVC): browses `_selahcue._tcp.local.` for a few
/// seconds on demand and exposes the found hosts. No widgets.
library;

import 'package:flutter/foundation.dart';
import 'package:multicast_dns/multicast_dns.dart';

import '../models/discovery.dart';

class DiscoveryController extends ChangeNotifier {
  static const _service = '_selahcue._tcp.local';

  List<DiscoveredHost> _hosts = const [];
  bool _searching = false;
  bool _disposed = false;

  List<DiscoveredHost> get hosts => _hosts;
  bool get searching => _searching;

  /// One bounded browse pass (~4s). Best-effort: an mDNS-hostile network just
  /// yields an empty list — the QR/manual paths are unaffected.
  Future<void> refresh() async {
    if (_searching) return;
    _searching = true;
    _notify();
    final found = <String, DiscoveredHost>{};
    final client = MDnsClient();
    try {
      await client.start();
      await for (final ptr in client
          .lookup<PtrResourceRecord>(
            ResourceRecordQuery.serverPointer(_service),
          )
          .timeout(const Duration(seconds: 4), onTimeout: (sink) => sink.close())) {
        String? host;
        int? port;
        final txt = <String>[];
        await for (final srv in client
            .lookup<SrvResourceRecord>(
              ResourceRecordQuery.service(ptr.domainName),
            )
            .timeout(const Duration(seconds: 2), onTimeout: (sink) => sink.close())) {
          port = srv.port;
          await for (final ip in client
              .lookup<IPAddressResourceRecord>(
                ResourceRecordQuery.addressIPv4(srv.target),
              )
              .timeout(const Duration(seconds: 2),
                  onTimeout: (sink) => sink.close())) {
            host = ip.address.address;
            break;
          }
          break;
        }
        await for (final t in client
            .lookup<TxtResourceRecord>(
              ResourceRecordQuery.text(ptr.domainName),
            )
            .timeout(const Duration(seconds: 2), onTimeout: (sink) => sink.close())) {
          txt.addAll(t.text.split('\n'));
          break;
        }
        final props = parseTxt(txt);
        final pin = props['pin'];
        if (host != null && port != null && pin != null) {
          final name = props['name'] ??
              ptr.domainName.replaceAll('.$_service', '');
          found['$host:$port'] = DiscoveredHost(
            name: name,
            host: host,
            port: port,
            pinHex: pin,
          );
        }
      }
    } catch (_) {
      // Discovery is best-effort by design.
    } finally {
      client.stop();
    }
    if (_disposed) return;
    _hosts = found.values.toList()..sort((a, b) => a.name.compareTo(b.name));
    _searching = false;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
