/// 17tnw2b0vtj — a malformed auth reply must not wedge `_reconnect()`.
///
/// `SelahSession.connect` used to let a non-JSON reply escape as a
/// `FormatException` and a binary reply as a `TypeError`. `_reconnect()` only
/// caught `SessionException`, so either one escaped the loop with `_reconnecting`
/// still true: one attempt, ever, and a banner that read "Connection lost —
/// reconnecting…" for good.
///
/// These tests inject the failure at the connect seam, which is where the
/// controller meets it. The controller must not depend on every connect
/// implementation keeping its exception hygiene: inside the loop, anything that
/// is not `SessionRevoked` is a transient failure — back off and try again.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

OperatorStateView _view() => const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );

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

/// The healthy replacement a successful reconnect hands back.
class _LiveSession implements ControllerSession {
  int commands = 0;
  bool closed = false;

  @override
  MobileRole get grantedRole => MobileRole.producer;
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    commands++;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => _view();
  @override
  Future<void> close() async => closed = true;
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

/// Poll until [done] holds. The reconnect backoff is a real 2s delay, so a fixed
/// sleep would either be flaky or slow; this waits exactly as long as it must.
Future<void> _until(bool Function() done,
    {Duration timeout = const Duration(seconds: 8)}) async {
  final deadline = DateTime.now().add(timeout);
  while (!done()) {
    if (DateTime.now().isAfter(deadline)) {
      fail('condition not reached within $timeout');
    }
    await Future<void>.delayed(const Duration(milliseconds: 20));
  }
}

/// Run the scenario shared by both malformed-reply flavours: the first connect
/// attempt blows up with [firstFailure], the second succeeds.
Future<void> _recoversAfter(Object firstFailure) async {
  final replacement = _LiveSession();
  var attempts = 0;

  Future<ControllerSession> connect({
    required String host,
    required int port,
    required String pinHex,
    required Credentials creds,
  }) async {
    attempts++;
    if (attempts == 1) throw firstFailure;
    return replacement;
  }

  final live =
      LiveController(session: _DeadSession(), stored: _stored, connect: connect);
  addTearDown(live.dispose);

  // The constructor's refresh() fails → _reconnect() → attempt 1 throws.
  await _until(() => attempts >= 1);
  expect(live.reconnecting, isTrue,
      reason: 'baseline: the banner is up while we are retrying');

  // The loop must come back for a second attempt and clear the banner.
  await _until(() => !live.reconnecting);
  expect(attempts, greaterThanOrEqualTo(2),
      reason: 'a malformed reply is transient: back off, then retry');
  expect(live.reconnecting, isFalse);
  expect(live.revoked, isFalse, reason: 'this is not a revocation');
  expect(live.error, isNull,
      reason: 'the "Connection lost" banner must clear once we are back');

  // …and controls work again: the re-sync lands, then a command goes through.
  await _until(() => !live.syncing);
  expect(await live.act(cmdGoLive()), CommandOutcome.applied);
  expect(replacement.commands, 1,
      reason: 'the command must reach the NEW session');
}

void main() {
  test('a FormatException from connect is retried and the loop recovers',
      () async {
    await _recoversAfter(const FormatException('Unexpected character'));
  });

  test('a TypeError from connect is retried and the loop recovers', () async {
    // What `frame as String` throws when the host answers with a binary frame.
    // Built by a real failing cast so the test throws exactly what production
    // would, not a hand-made look-alike.
    Object binaryFrameError() {
      try {
        final Object frame = <int>[0, 1, 2];
        return (frame as String);
      } on TypeError catch (e) {
        return e;
      }
    }

    await _recoversAfter(binaryFrameError());
  });

  test('the loop keeps retrying across several consecutive malformed replies',
      () async {
    // One retry is not the same as "never gives up": a host that stays broken
    // for a while must keep being retried, with no attempt wedging the loop.
    var attempts = 0;
    final replacement = _LiveSession();
    Future<ControllerSession> connect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async {
      attempts++;
      if (attempts == 1) throw const FormatException('garbage');
      if (attempts == 2) throw StateError('some other bug');
      return replacement;
    }

    final live = LiveController(
        session: _DeadSession(), stored: _stored, connect: connect);
    addTearDown(live.dispose);

    // `reconnecting` is only true once the constructor's refresh() has failed, so
    // wait for the first attempt before waiting for the banner to clear.
    await _until(() => attempts >= 1);
    await _until(() => !live.reconnecting, timeout: const Duration(seconds: 12));
    expect(attempts, 3);
    expect(live.revoked, isFalse);
  });

  test('SessionRevoked still stops the loop and raises the Access-removed state',
      () async {
    // No regression: widening the catch must not swallow the one failure that
    // retrying can never fix. (`revoked` is what the view renders as "Access
    // removed" — see test/views/access_removed_test.dart.)
    var attempts = 0;
    Future<ControllerSession> connect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async {
      attempts++;
      throw const SessionRevoked('authentication rejected: revoked');
    }

    final live = LiveController(
        session: _DeadSession(), stored: _stored, connect: connect);
    addTearDown(live.dispose);

    await _until(() => live.revoked);
    expect(live.reconnecting, isFalse);

    // Give a (wrongly) surviving loop time to attempt again: 2s backoff + slack.
    await Future<void>.delayed(const Duration(milliseconds: 2500));
    expect(attempts, 1, reason: 'revoked is terminal: exactly one attempt');
  });
}
