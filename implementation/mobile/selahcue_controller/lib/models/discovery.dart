/// mDNS discovery model (M in MVC): a nearby SelahCue host advertised as
/// `_selahcue._tcp.local.` (story 86ajp0b0t). The TXT record carries the
/// certificate pin — public data (it is printed in every QR invite); pairing
/// still requires the single-use code + host approval.
library;

class DiscoveredHost {
  final String name;
  final String host;
  final int port;

  /// Lowercase hex SHA-256 certificate pin from the TXT record.
  final String pinHex;

  const DiscoveredHost({
    required this.name,
    required this.host,
    required this.port,
    required this.pinHex,
  });

  /// Compose the pairing URI once the operator's on-screen code is known —
  /// identical to the QR contents, so the normal pairing path takes over.
  String inviteUri(String code) =>
      'selahcue://pair?host=$host&port=$port&pin=$pinHex&code=${code.trim().toUpperCase()}';

  /// Short, human-comparable fingerprint of the discovered pin — the operator
  /// MUST confirm it matches the fingerprint the host shows before the pairing
  /// code is disclosed (a rogue mDNS host advertises its own pin, so its
  /// fingerprint will not match). Byte-identical to the Rust `pin_fingerprint`.
  String get fingerprint => pinFingerprint(pinHex);
}

/// The Rust `pin_fingerprint` mirror: first 12 hex chars, uppercased, grouped
/// in 4s (e.g. `AB12-CD34-EF56`). Pinned by discovery_test.dart.
String pinFingerprint(String pinHex) {
  final head =
      (pinHex.length > 12 ? pinHex.substring(0, 12) : pinHex).toUpperCase();
  final groups = <String>[];
  for (var i = 0; i < head.length; i += 4) {
    groups.add(head.substring(i, i + 4 > head.length ? head.length : i + 4));
  }
  return groups.join('-');
}

/// Parse mDNS TXT bytes (`key=value` entries) into a map. Pure — unit-tested.
Map<String, String> parseTxt(List<String> entries) {
  final out = <String, String>{};
  for (final entry in entries) {
    final i = entry.indexOf('=');
    if (i <= 0) continue;
    out[entry.substring(0, i)] = entry.substring(i + 1);
  }
  return out;
}
