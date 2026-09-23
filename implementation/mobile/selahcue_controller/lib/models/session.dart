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
import 'rbac.dart';

/// Mirrors the Rust client's budgets: transport 10s; pairing additionally waits
/// through the host's 30s confirmation window.
const Duration connectTimeout = Duration(seconds: 10);
// Must exceed the server's operator-approval park window (120s) so the device does not hang up
// before the operator has decided (86ajxer8n).
const Duration pairTimeout = Duration(seconds: 150);
const Duration commandTimeout = Duration(seconds: 10);

class SessionException implements Exception {
  final String message;
  const SessionException(this.message);
  @override
  String toString() => message;
}

/// The host **rejected our stored credentials** (auth) — the device was unpaired
/// or revoked by an admin, so retrying is pointless. A subtype of
/// [SessionException] so existing catches still handle it, while callers that
/// want to STOP reconnecting (and prompt a re-pair) can catch it specifically.
class SessionRevoked extends SessionException {
  const SessionRevoked(super.message);
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
  /// The role the host granted this device (parsed; drives UI capability gating).
  MobileRole get grantedRole;
  Future<ServerMessage> command(Map<String, dynamic> cmd);
  Future<OperatorStateView> operatorState();
  Future<void> close();
}

class SelahSession implements ControllerSession {
  final WebSocket _ws;
  final StreamQueue _incoming;

  /// The role the host granted this device (raw wire string).
  final String role;

  /// The parsed role that drives client-side capability gating.
  @override
  MobileRole get grantedRole => MobileRole.parse(role);

  /// Serializes command round-trips (the protocol is lockstep per connection).
  ///
  /// Not depth-limited by this field itself: nothing stops overlapping
  /// [command] calls from chaining onto this indefinitely, so the bound has
  /// to come from the callers. It does: the app has exactly three independent
  /// single-flight domains that guard against queuing a turn —
  ///
  ///  - `LiveController.refresh()`, guarded by `_refreshing` (the 1s poll
  ///    never queues a second turn).
  ///  - `LiveController.act()`, `.selectAndGoLive()` and
  ///    `.stageScriptureAndGoLive()`, all sharing ONE `_acting` claim. This
  ///    used to be narrower and wrong in two stages, both found by review of
  ///    this same investigation: first `act()` alone had no guard at all
  ///    (17tnw2ay2kk closed that — a double-tap or a burst of impatient taps
  ///    against a slow/dead host used to each queue their own turn and wait
  ///    up to `commandTimeout` for the ones ahead of it). Then the compound
  ///    gestures were found to release `_acting` after their FIRST internal
  ///    command, leaving the read between their two commands (and their
  ///    second command itself) unguarded — a second tap in that window could
  ///    land its own command on the wire BETWEEN a gesture's stage and its
  ///    go-live, proven live during review. `_acting` now spans a gesture's
  ///    full duration, not just its first command — see
  ///    `live_controller_reentrancy_test.dart`.
  ///  - The scripture chapter fetch, guarded caller-side by a `_loading` flag
  ///    in `ScriptureTab` (the one screen that calls `fetchChapter` directly).
  ///
  /// Those three domains are each single-flight *within* themselves, not
  /// mutually exclusive *across* each other — `act()` does not check
  /// `_refreshing` and `refresh()` does not check `_acting`, so a poll tick
  /// and an in-flight command (and, separately, a chapter fetch) can
  /// genuinely overlap. So the real bound on `_turn`'s chain depth is the
  /// small, fixed number of domains the app has (three today), not the size
  /// of any unbounded input like tap rate or keystrokes — a materially
  /// different, and much smaller, worst case than this file originally
  /// recorded. If a new call site reaches `command()` without joining one of
  /// these three domains (or adding a fourth), that changes — investigated
  /// alongside `StreamQueue._buffer` below.
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

  /// Redeem a pairing invite. The device parks until the operator approves it (assigning a role)
  /// from the Remote Control console; on approval the connection is already authenticated and the
  /// issued credentials are returned.
  static Future<(SelahSession, Credentials)> pair(
      PairingInvite invite, String deviceName) async {
    final ws = await _establish(invite.host, invite.port, invite.pinHex);
    try {
      final incoming = StreamQueue(ws);
      ws.add(jsonEncode(
          helloPair(invite.code, deviceName, platform: Platform.operatingSystem)));
      // The host may send an interim `parked` frame while it awaits the operator's decision
      // (86ajxhv0q) — keep waiting for the terminal Granted/Rejected.
      pairing:
      while (true) {
        final reply = await incoming.nextJson(pairTimeout);
        switch (PairResult.fromJson(reply)) {
          case PairParked():
            continue pairing;
          case PairGranted(:final deviceId, :final token, :final role):
            return (
              SelahSession._(ws, incoming, role),
              Credentials(deviceId: deviceId, token: token),
            );
          case PairRejected(:final reason):
            throw SessionException('pairing rejected: $reason');
        }
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
          // Credentials no longer valid (revoked/unpaired) — distinct from a
          // transient network failure so the controller stops reconnecting.
          throw SessionRevoked('authentication rejected: $reason');
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
///
/// `_buffer` has no cap. **This is safe against today's host IMPLEMENTATION,
/// not against the untrusted LAN peer the architecture actually posits** — the
/// distinction matters and the rest of this comment is precise about it.
///
/// Post-pairing (`request_loop`, `server.rs`), the host answers exactly one
/// frame per frame it receives and never pushes unsolicited — confirmed by
/// reading `request_loop` itself (a single `send_json` per loop iteration, no
/// concurrent writer task; `ws` is a `&mut` held exclusively by the loop, so a
/// second writer isn't just absent, it can't compile) and corroborated by
/// `implementation/desktop/CODE-REVIEW-batch7e-transport.md`, which already
/// notes unsolicited server pushes as *future* work, not present behaviour.
/// `ServerMessage::State`'s "unsolicited or in reply to `GetState`" doc
/// comment (`selahcue-lan/src/protocol.rs`) describes the wire format's
/// range, not what this server does today. (Scoped to *post-pairing*
/// deliberately: the PAIRING handshake genuinely sends two frames for one —
/// `Parked` then a terminal `Granted`/`Rejected` — but that is bounded by a
/// different, already-reasoned-about mechanism: a single-shot park capped by
/// `PAIRING_PARK_TIMEOUT`, not a repeating one-request-many-replies pattern,
/// and `pair()` above loops until the terminal frame rather than treating the
/// first reply as final.)
///
/// What actually prevents pile-up from a late reply is NOT primarily the
/// per-frame `request_id` discard in `command()` — only `Ack`/`Denied` carry
/// one; `OperatorState`/`ErrorMessage`/`ChapterResult` don't, so a late reply
/// to a timed-out `operatorState()`/`fetchChapter()` call is accepted as the
/// NEXT command's reply, not discarded. What actually bounds it is the
/// teardown invariant `command()`'s own doc comment states: a
/// [SessionException] (e.g. a timeout) means the WHOLE session — this
/// `StreamQueue` included — gets torn down and reconnected, not retried on
/// the same socket. That is what stops a bursty-timeout pattern from
/// accumulating stale entries here.
///
/// So: **the no-cap design is safe only as long as (a) the current host
/// implementation's one-reply-per-request behaviour holds, AND (b) every
/// caller keeps the teardown invariant.** Two things reopen this, not one —
/// add a cap + drop-oldest policy if EITHER becomes false:
///  - the host starts pushing unsolicited state (e.g. to replace 1s polling), or
///  - a peer holding the pinned TLS key — the pin authenticates WHO, not WHAT
///    it sends, and this repo's own architecture treats the LAN control plane
///    as untrusted — sends frames faster than this client's own request rate
///    calls for. `StreamQueue.listen` below never pauses its subscription and
///    imposes no per-frame size cap or rate limit of its own, so today that
///    growth path is bounded only by the honesty of whoever holds the key,
///    not by anything in this file.
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
