/// The controller's connection to the operator host: a TLS-**pinned** WebSocket
/// speaking the SelahCue control protocol (mirror of the Rust `ControlClient`).
///
/// Trust model: the server's self-signed certificate is accepted **only** if its
/// SHA-256 matches the pin from the pairing invite — no CA roots at all — while the
/// TLS handshake still proves possession of the private key.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

import 'pair_uri.dart';
import 'protocol.dart';

/// Mirrors the Rust client's budgets: transport 10s; pairing additionally waits
/// through the host's 30s confirmation window.
const Duration connectTimeout = Duration(seconds: 10);
const Duration pairTimeout = Duration(seconds: 45);
const Duration commandTimeout = Duration(seconds: 10);

class SessionException implements Exception {
  final String message;
  const SessionException(this.message);
  @override
  String toString() => message;
}

/// Credentials issued at pairing time (store securely; reused on reconnect).
class Credentials {
  final String deviceId;
  final String token;
  const Credentials({required this.deviceId, required this.token});
}

/// The slice of a live connection the [LiveController] drives. Extracted as an
/// interface so the controller can be unit-tested against a fake without a real
/// pinned-TLS socket; [SelahSession] is the production implementation.
abstract interface class ControllerSession {
  Future<ServerMessage> command(Map<String, dynamic> cmd);
  Future<OperatorStateView> operatorState();
  Future<void> close();
}

class SelahSession implements ControllerSession {
  final WebSocket _ws;
  final StreamQueue _incoming;

  /// The role the host granted this device.
  final String role;

  /// Serializes command round-trips (the protocol is lockstep per connection).
  Future<void> _turn = Future.value();

  SelahSession._(this._ws, this._incoming, this.role);

  /// Open the pinned TLS WebSocket (no authentication yet).
  static Future<WebSocket> _establish(String host, int port, String pinHex) async {
    final wanted = pinHex.toLowerCase();
    final client = HttpClient(context: SecurityContext(withTrustedRoots: false));
    client.badCertificateCallback = (X509Certificate cert, String h, int p) {
      // Pin-only trust: accept iff the presented certificate hashes to the pin.
      return sha256.convert(cert.der).toString() == wanted;
    };
    try {
      return await WebSocket.connect('wss://$host:$port/', customClient: client)
          .timeout(connectTimeout);
    } on TimeoutException {
      throw const SessionException('connection timed out');
    } on Exception catch (e) {
      throw SessionException('could not connect: $e');
    }
  }

  /// Redeem a pairing invite. Waits through the operator's confirmation window; on
  /// success the connection is already authenticated and credentials are returned.
  static Future<(SelahSession, Credentials)> pair(
      PairingInvite invite, String deviceName) async {
    final ws = await _establish(invite.host, invite.port, invite.pinHex);
    try {
      final incoming = StreamQueue(ws);
      ws.add(jsonEncode(helloPair(invite.code, deviceName)));
      final reply = await incoming.nextJson(pairTimeout);
      switch (PairResult.fromJson(reply)) {
        case PairGranted(:final deviceId, :final token, :final role):
          return (
            SelahSession._(ws, incoming, role),
            Credentials(deviceId: deviceId, token: token),
          );
        case PairRejected(:final reason):
          throw SessionException('pairing rejected: $reason');
      }
    } catch (e) {
      // Never leak the socket on a failed handshake (timeout/reject/malformed).
      await ws.close();
      rethrow;
    }
  }

  /// Reconnect with previously issued credentials.
  static Future<SelahSession> connect({
    required String host,
    required int port,
    required String pinHex,
    required Credentials creds,
  }) async {
    final ws = await _establish(host, port, pinHex);
    try {
      final incoming = StreamQueue(ws);
      ws.add(jsonEncode(helloAuth(creds.deviceId, creds.token)));
      final reply = await incoming.nextJson(connectTimeout);
      switch (AuthResult.fromJson(reply)) {
        case AuthGranted(:final role):
          return SelahSession._(ws, incoming, role);
        case AuthRejected(:final reason):
          throw SessionException('authentication rejected: $reason');
      }
    } catch (e) {
      // Never leak the socket on a failed handshake (timeout/reject/malformed).
      await ws.close();
      rethrow;
    }
  }

  int _nextId = 1;

  /// Send one command and await its reply (lockstep; callers may overlap freely).
  ///
  /// Invariant callers must keep: a [SessionException] from a command (e.g. a
  /// timeout) means this session should be TORN DOWN and reconnected — a timed-out
  /// command's uncorrelated reply (state frames carry no request_id) could otherwise
  /// be attributed to the next command on the same socket.
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) {
    final completer = Completer<ServerMessage>();
    _turn = _turn.then((_) async {
      try {
        final id = _nextId++;
        _ws.add(jsonEncode(request(id, cmd)));
        // Read until this command's reply: correlated frames (ack/denied carry
        // request_id) from an EARLIER, timed-out command are discarded rather than
        // mis-attributed. Uncorrelated frames (state/operator_state/...) are the
        // reply under the lockstep discipline.
        while (true) {
          final reply = await _incoming.nextJson(commandTimeout);
          final rid = reply['request_id'];
          if (rid is int && rid < id) continue; // stale reply to a timed-out call
          completer.complete(ServerMessage.fromJson(reply));
          break;
        }
      } catch (e) {
        if (!completer.isCompleted) {
          completer.completeError(
              e is SessionException ? e : SessionException('$e'));
        }
      }
    });
    return completer.future;
  }

  /// Fetch the host-authoritative operator view.
  @override
  Future<OperatorStateView> operatorState() async {
    final reply = await command(cmdGetOperatorState());
    if (reply is OperatorState) return reply.view;
    throw SessionException('unexpected reply to get_operator_state');
  }

  @override
  Future<void> close() async {
    await _ws.close();
  }
}

/// Buffers inbound WebSocket frames for ordered consumption. Correlation is the
/// caller's job: `command()` discards stale correlated replies; otherwise the
/// protocol is lockstep (one outstanding request per connection).
class StreamQueue {
  final List<dynamic> _buffer = [];
  final List<Completer<dynamic>> _waiters = [];
  bool _done = false;

  StreamQueue(WebSocket ws) {
    ws.listen((frame) {
      if (_waiters.isNotEmpty) {
        _waiters.removeAt(0).complete(frame);
      } else {
        _buffer.add(frame);
      }
    }, onDone: () {
      _done = true;
      for (final w in _waiters) {
        if (!w.isCompleted) {
          w.completeError(const SessionException('connection closed'));
        }
      }
      _waiters.clear();
    }, onError: (Object e) {
      _done = true;
      for (final w in _waiters) {
        if (!w.isCompleted) w.completeError(SessionException('$e'));
      }
      _waiters.clear();
    });
  }

  /// The next frame, parsed as a JSON object.
  Future<Map<String, dynamic>> nextJson(Duration timeout) async {
    dynamic frame;
    if (_buffer.isNotEmpty) {
      frame = _buffer.removeAt(0);
    } else {
      if (_done) throw const SessionException('connection closed');
      final waiter = Completer<dynamic>();
      _waiters.add(waiter);
      try {
        frame = await waiter.future.timeout(timeout);
      } on TimeoutException {
        _waiters.remove(waiter);
        throw const SessionException('timed out waiting for the host');
      }
    }
    final decoded = jsonDecode(frame as String);
    if (decoded is! Map<String, dynamic>) {
      throw const SessionException('malformed frame from the host');
    }
    return decoded;
  }
}
