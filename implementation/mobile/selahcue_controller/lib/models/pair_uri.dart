/// The `selahcue://pair?...` pairing-invite URI (Dart mirror of the Rust
/// `PairingInvite` — same fields, same URL-safe validation, no percent-encoding).
library;

class PairingInvite {
  final String host;
  final int port;

  /// Lowercase hex SHA-256 pin of the operator's certificate.
  final String pinHex;

  /// The single-use pairing code.
  final String code;

  const PairingInvite({
    required this.host,
    required this.port,
    required this.pinHex,
    required this.code,
  });

  static final RegExp _valueOk = RegExp(r'^[A-Za-z0-9.\-:_]+$');

  /// Parse a `selahcue://pair?...` URI; `null` for anything malformed.
  static PairingInvite? parse(String uri) {
    const prefix = 'selahcue://pair?';
    if (!uri.startsWith(prefix)) return null;
    final query = uri.substring(prefix.length);
    String? host, pin, code;
    int? port;
    for (final pair in query.split('&')) {
      final eq = pair.indexOf('=');
      if (eq < 0) return null;
      final k = pair.substring(0, eq);
      final v = pair.substring(eq + 1);
      if (!_valueOk.hasMatch(v)) return null;
      switch (k) {
        case 'host':
          host = v;
        case 'port':
          port = int.tryParse(v);
          if (port == null || port < 1 || port > 65535) return null;
        case 'pin':
          pin = v;
        case 'code':
          code = v;
        default:
        // Ignore unknown params (forward compatibility).
      }
    }
    if (host == null || port == null || pin == null || code == null) return null;
    return PairingInvite(host: host, port: port, pinHex: pin, code: code);
  }

  String? toUri() {
    if (!_valueOk.hasMatch(host) || !_valueOk.hasMatch(pinHex) || !_valueOk.hasMatch(code)) {
      return null;
    }
    return 'selahcue://pair?host=$host&port=$port&pin=$pinHex&code=$code';
  }
}
