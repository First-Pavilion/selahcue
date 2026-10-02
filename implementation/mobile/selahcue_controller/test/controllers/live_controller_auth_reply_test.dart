/// 17tnw2b1f1v — what a host's auth reply does to the stored pairing.
///
/// A reply the client cannot read used to wipe the device's credentials:
/// `{}` became `AuthRejected('malformed reply')`, `SelahSession.connect` threw it
/// as `SessionRevoked`, and `LiveController._reconnect` cleared the stored
/// profile and raised "Access removed" — forcing a fresh pairing code and an
/// operator approval for a device nobody revoked. Only an explicit
/// `"auth":"rejected"` may do that.
///
/// These tests drive the REAL production chain end to end: the controller's
/// default `SelahSession.connect`, over pinned TLS, against a loopback host that
/// answers with the frame under test, with the stored profile held in a mocked
/// platform keystore so "credentials kept" and "credentials cleared" are read
/// back through `StoredSession.load()`, not inferred from a flag.
library;

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

import '../support/fake_keystore.dart';
import '../support/loopback_host.dart';

/// A session whose every call fails, forcing the controller into `_reconnect`.
class _DeadSession implements ControllerSession {
  @override
  MobileRole get grantedRole => MobileRole.producer;
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async =>
      throw const SessionException('dead');
  @override
  Future<OperatorStateView> operatorState() async =>
      throw const SessionException('dead');
  @override
  Future<void> close() async {}
}

/// Poll until [done] holds. The reconnect backoff is a real 2 s delay, so a fixed
/// sleep would be either flaky or slow.
Future<void> _until(bool Function() done,
    {Duration timeout = const Duration(seconds: 10)}) async {
  final deadline = DateTime.now().add(timeout);
  while (!done()) {
    if (DateTime.now().isAfter(deadline)) {
      fail('condition not reached within $timeout');
    }
    await Future<void>.delayed(const Duration(milliseconds: 20));
  }
}

/// A paired device whose stored profile points at [host], with the controller
/// already running over a dead session so its first reconnect dials [host].
Future<LiveController> _pairedDeviceAgainst(
    LoopbackHost host, FakeKeystore keystore) async {
  keystore.install();
  final stored = StoredSession(
    host: '127.0.0.1',
    port: host.port,
    pinHex: host.pinHex,
    deviceId: 'dev-1',
    token: 'tok-1',
  );
  await StoredSession.save(stored);
  // Default `connect`: the production `SelahSession.connect`.
  final live = LiveController(session: _DeadSession(), stored: stored);
  addTearDown(live.dispose);
  return live;
}

/// Replies the host must NOT treat as a verdict — the four shapes the ticket
/// names. (The full set of malformed shapes is pinned one level down, in
/// test/models/session_handshake_reply_test.dart.)
const _malformedReplies = <String, String>{
  '{}': '{}',
  '{"foo":"bar"}': '{"foo":"bar"}',
  '{"auth":123}': '{"auth":123}',
  '{"auth":"granted","role":5}': '{"auth":"granted","role":5}',
};

void main() {
  for (final entry in _malformedReplies.entries) {
    test('a host answering the auth hello with ${entry.key} keeps the '
        'credentials and the loop retries', () async {
      // `debugReportUnexpectedConnectFailure` is how the reconnect loop owns up
      // to a failure NOBODY MODELLED (it writes the runtime type). A malformed
      // reply is a modelled failure, so it must not take that route — which is
      // also what tells `{"auth":"granted","role":5}` apart from its old self: a
      // raw TypeError was retried by the loop's catch-all too, but only as an
      // "unexpected" one.
      final reports = <String>[];
      final realDebugPrint = debugPrint;
      debugPrint = (String? message, {int? wrapWidth}) =>
          reports.add(message ?? '');
      addTearDown(() => debugPrint = realDebugPrint);

      final host = await LoopbackHost.start(replies: [entry.value]);
      final keystore = FakeKeystore();
      final live = await _pairedDeviceAgainst(host, keystore);

      // Attempt 1 fails as malformed; the loop backs off 2 s and dials again.
      await _until(() => host.hellos.length >= 2);
      expect(reports.where((m) => m.contains('unexpected')), isEmpty,
          reason: 'a malformed reply is a modelled failure, not an unexpected one');

      expect(live.revoked, isFalse, reason: 'a malformed reply is not a verdict');
      expect(live.reconnecting, isTrue, reason: 'still trying');
      expect(keystore.deletes, 0, reason: 'the stored profile is never cleared');
      final kept = await StoredSession.load();
      expect(kept, isNotNull, reason: 'the stored credentials are kept');
      expect(kept!.deviceId, 'dev-1');
      expect(kept.token, 'tok-1');
    });
  }

  // `unauthenticated` is what the Rust host sends for an unknown/revoked device;
  // `bad_request` is its protocol-version-mismatch rejection. Both are EXPLICIT
  // rejections and both must keep working exactly as before.
  for (final reason in ['unauthenticated', 'bad_request']) {
    test('an explicit "rejected" ($reason) revokes: credentials cleared, '
        'exactly one attempt', () async {
      final host = await LoopbackHost.start(
          replies: ['{"auth":"rejected","reason":"$reason"}']);
      final keystore = FakeKeystore();
      final live = await _pairedDeviceAgainst(host, keystore);

      await _until(() => live.revoked);
      expect(live.reconnecting, isFalse);
      expect(await StoredSession.load(), isNull,
          reason: 'the dead credentials are dropped');

      // Give a (wrongly) surviving loop time to dial again: 2 s backoff + slack.
      await Future<void>.delayed(const Duration(milliseconds: 2500));
      expect(host.hellos, hasLength(1),
          reason: 'revoked is terminal: exactly one attempt');
    });
  }

  test('control: a well-formed granted reconnects and nothing is cleared',
      () async {
    // Proves the harness really reaches a success through the same chain, so
    // the "kept" results above are not an artefact of a connect that can never
    // succeed.
    final host = await LoopbackHost.start(
        replies: ['{"auth":"granted","role":"producer"}']);
    final keystore = FakeKeystore();
    final live = await _pairedDeviceAgainst(host, keystore);

    await _until(() => host.hellos.isNotEmpty && !live.reconnecting);
    expect(live.revoked, isFalse);
    expect(keystore.deletes, 0);
    expect((await StoredSession.load())?.deviceId, 'dev-1');
  });
}
