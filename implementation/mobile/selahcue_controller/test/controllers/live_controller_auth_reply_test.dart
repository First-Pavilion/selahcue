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

import 'dart:async';

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

/// How much faster the controller's own SHORT timers run in this file.
///
/// The reconnect loop backs off for a real 2 s between attempts, and this file
/// has to watch several attempts (and prove there is NOT another one), which at
/// full speed cost ~13 s of wall time per run. The controller is therefore built
/// inside a zone that divides every timer of 5 s or less by this factor — the 2 s
/// backoff becomes 100 ms — while keeping the REAL socket, TLS and parse stack
/// underneath. Timers above 5 s (the 10 s connect budget) are left alone so they
/// cannot fire spuriously.
const _timeScale = 20;

/// The reconnect backoff as the controller experiences it inside [_runFast].
const _scaledBackoff = Duration(milliseconds: 2000 ~/ _timeScale);

/// Run [body] with every timer of 5 s or less shortened by [_timeScale].
T _runFast<T>(T Function() body) => runZoned(body,
    zoneSpecification: ZoneSpecification(
      createTimer: (self, parent, zone, duration, f) => parent.createTimer(
          zone,
          duration > Duration.zero && duration <= const Duration(seconds: 5)
              ? duration ~/ _timeScale
              : duration,
          f),
    ));

/// Poll until [done] holds (real time; the caller's bound, not a fixed sleep).
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
  final live = _runFast(
      () => LiveController(session: _DeadSession(), stored: stored));
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

      // Attempt 1 fails as malformed; the loop backs off and dials again.
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
  //
  // DECISION PENDING (ClickUp 17tnw2b1wav): pinning `bad_request` as a
  // REVOCATION is today's behaviour, not a verdict that it is right. A host
  // version bump would tell every paired phone it was revoked and wipe its
  // pairing. Whoever settles that ticket should change this expectation (and
  // its session-level twin in test/models/session_handshake_reply_test.dart) ON
  // PURPOSE. It holds for any reason string: an unknown future reason (a
  // `rate_limited`, say) sent as an explicit rejection would wipe the
  // credentials in exactly the same way.
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

      // Give a (wrongly) surviving loop time to dial again: eight backoffs'
      // worth, so a loop that kept going would have dialled several more times.
      await Future<void>.delayed(_scaledBackoff * 8);
      expect(host.hellos, hasLength(1),
          reason: 'revoked is terminal: exactly one attempt');
    });
  }

  test('control: the fast-timer zone really shortens the 2 s backoff', () async {
    // The "exactly one attempt" windows above are only meaningful if they are
    // longer than the backoff the controller really waits. If the zone silently
    // stopped applying, the loop would back off a full 2 s, a window of eight
    // scaled backoffs (0.8 s) would end BEFORE a surviving loop dialled again,
    // and those tests would pass vacuously. Pin the premise.
    final watch = Stopwatch()..start();
    await _runFast(() => Future<void>.delayed(const Duration(seconds: 2)));
    expect(watch.elapsed, lessThan(const Duration(seconds: 1)),
        reason: 'a 2 s delay inside the zone must run at the scaled speed');
  });

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
