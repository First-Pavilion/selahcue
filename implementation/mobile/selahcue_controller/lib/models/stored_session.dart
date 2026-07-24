/// The persisted connection profile (Model): where the host is, its certificate
/// pin, and this device's issued credentials — kept in the platform keystore.
library;

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage();
const _kSession = 'selahcue.session.v1';

class StoredSession {
  final String host;
  final int port;
  final String pinHex;
  final String deviceId;
  final String token;

  const StoredSession({
    required this.host,
    required this.port,
    required this.pinHex,
    required this.deviceId,
    required this.token,
  });

  Map<String, dynamic> toJson() => {
        'host': host,
        'port': port,
        'pin': pinHex,
        'device_id': deviceId,
        'token': token,
      };

  static StoredSession? fromJson(Map<String, dynamic> j) {
    final host = j['host'] as String?;
    final port = j['port'] as int?;
    final pin = j['pin'] as String?;
    final id = j['device_id'] as String?;
    final token = j['token'] as String?;
    if (host == null || port == null || pin == null || id == null || token == null) {
      return null;
    }
    return StoredSession(
        host: host, port: port, pinHex: pin, deviceId: id, token: token);
  }

  static Future<void> save(StoredSession s) =>
      _storage.write(key: _kSession, value: jsonEncode(s.toJson()));

  static Future<StoredSession?> load() async {
    final raw = await _storage.read(key: _kSession);
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw);
      return decoded is Map<String, dynamic> ? fromJson(decoded) : null;
    } on FormatException {
      return null;
    }
  }

  static Future<void> clear() => _storage.delete(key: _kSession);
}
