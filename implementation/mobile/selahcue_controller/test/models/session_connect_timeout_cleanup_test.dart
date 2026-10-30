/// 17tnw2b1f1w: an expired connect still owns pending HTTP and late WebSockets.
/// Real pinned TLS/HTTP/socket paths, with only external upgrade/deadline/
/// completion scheduling controlled. Counts precede all fixture cleanup.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/pair_uri.dart';
import 'package:selahcue_controller/models/session.dart';

import '../support/connection_trace.dart';
import '../support/loopback_host.dart';

const _bound = Duration(seconds: 5);
const _creds = Credentials(deviceId: 'dev-test', token: 'test-token');
const _authGrant = '{"auth":"granted","role":"producer"}';
const _pairGrant = '{"pair":"granted","device_id":"dev-0123456789abcdef",'
    '"token":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",'
    '"role":"viewer"}';

Future<SelahSession> _connect(LoopbackHost host) => SelahSession.connect(
    host: '127.0.0.1', port: host.port, pinHex: host.pinHex, creds: _creds);

Future<(SelahSession, Credentials)> _pair(LoopbackHost host) => SelahSession.pair(
    PairingInvite(
        host: '127.0.0.1', port: host.port, pinHex: host.pinHex, code: 'CODE-1'),
    'Test phone');

Matcher _timedOut() => throwsA(isA<SessionException>()
    .having((error) => error.message, 'message', 'connection timed out'));

Future<void> _until(bool Function() condition) async {
  final deadline = Stopwatch()..start();
  while (!condition()) {
    if (deadline.elapsed >= _bound) fail('owned socket condition did not settle');
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
}

void main() {
  test('control: a timely authenticated session remains open until caller close',
      () async {
    final host = await LoopbackHost.start(replies: [_authGrant]);
    final trace = ConnectionTrace();
    final session = await trace.run(() => _connect(host));
    final observed = await trace.socketAcquired.future;

    expect(trace.deadlineActive, isFalse);
    expect(observed.readyState, WebSocket.open);
    expect(observed.closeCalls, 0);
    expect(session.role, 'producer');
    expect(host.hellos, hasLength(1));
    expect(host.upgradeErrors, isEmpty);
    await session.close();
    // Session.close cancels its input subscription. Dart's WebSocket.readyState
    // can then retain its last value even after the peer observes transport
    // closure, so use the peer's completion as the timely-session oracle.
    expect(await host.waitClientClosed(1), isTrue);
    expect(observed.closeCalls, 1);
    expect(host.openSocketCount, 0);
  });

  test('control: timely pairing retains its issued credentials and live session',
      () async {
    final host = await LoopbackHost.start(replies: [_pairGrant]);
    final trace = ConnectionTrace();
    final (session, creds) = await trace.run(() => _pair(host));
    final observed = await trace.socketAcquired.future;

    expect(creds.deviceId, 'dev-0123456789abcdef');
    expect(creds.token.length, 64);
    expect(session.role, 'viewer');
    expect(observed.readyState, WebSocket.open);
    expect(observed.closeCalls, 0);
    expect(host.upgradeErrors, isEmpty);
    await session.close();
    expect(await host.waitClientClosed(1), isTrue);
    expect(observed.closeCalls, 1);
    expect(host.openSocketCount, 0);
  });

  test('control: held acquired-socket delivery before deadline still succeeds',
      () async {
    final host = await LoopbackHost.start(replies: [_authGrant]);
    final trace = ConnectionTrace(holdSocketCompletion: true);
    final connecting = trace.run(() => _connect(host));
    final observed = await trace.socketAcquired.future.timeout(_bound);
    expect(trace.deadlineActive, isTrue);
    trace.releaseSocketCompletion();
    final session = await connecting.timeout(_bound);

    expect(session.role, 'producer');
    expect(trace.deadlineActive, isFalse);
    expect(observed.closeCalls, 0);
    await session.close();
    expect(await host.waitClientClosed(1), isTrue);
    expect(observed.closeCalls, 1);
    expect(host.openSocketCount, 0);
  });

  for (final pairing in [false, true]) {
    test('an acquired late ${pairing ? 'pair' : 'auth'} socket closes exactly once',
        () async {
      final host = await LoopbackHost.start(
          replies: [pairing ? _pairGrant : _authGrant]);
      final trace = ConnectionTrace(holdSocketCompletion: true);
      final Future<Object> connecting =
          trace.run(() => pairing ? _pair(host) : _connect(host));
      final failed = expectLater(connecting, _timedOut());
      final observed = await trace.socketAcquired.future.timeout(_bound);
      expect(observed.readyState, WebSocket.open,
          reason: 'a real socket is acquired before completion is released');
      trace.expire();
      await failed;
      trace.releaseSocketCompletion();
      await trace.awaitProductionCloses();

      expect(observed.closeCalls, 1);
      await _until(() => observed.readyState == WebSocket.closed &&
          host.openSocketCount == 0);
      expect(observed.readyState, WebSocket.closed);
      expect(trace.openSocketCount, 0);
      expect(host.hellos, isEmpty, reason: 'an expired attempt cannot own a session');
    });
  }

  test('an upgrade after the real ten-second deadline leaves zero owned sockets',
      () async {
    final requested = Completer<void>();
    final release = Completer<void>();
    final host = await LoopbackHost.start(replies: [_authGrant], beforeUpgrade: () {
      requested.complete();
      return release.future;
    });
    addTearDown(() {
      if (!release.isCompleted) release.complete();
    });
    final trace = ConnectionTrace(manualDeadline: false);
    final connecting = trace.run(() => _connect(host));
    final failure = expectLater(connecting, _timedOut());
    await requested.future.timeout(_bound);
    // No shortened deadline here: this one pins the actual ten-second default.
    await failure;
    release.complete();
    await trace.connectionSettled.future.timeout(_bound);
    await _until(() => host.upgradeAttemptsCompleted == 1);
    await trace.awaitProductionCloses();

    await _until(() => trace.openSocketCount == 0 &&
        host.openSocketCount == 0 && host.httpConnectionCount == 0);
    expect(trace.openSocketCount, 0);
    expect(host.hellos, isEmpty);
  });

  test('100 consecutive late upgrades retain zero owned sockets', () async {
    var requested = Completer<void>();
    var release = Completer<void>();
    final host = await LoopbackHost.start(replies: [_authGrant], beforeUpgrade: () {
      final seen = requested;
      final gate = release;
      seen.complete();
      return gate.future;
    });
    addTearDown(() {
      if (!release.isCompleted) release.complete();
    });
    final traces = <ConnectionTrace>[];
    final clientCounts = <int>[];
    final serverCounts = <int>[];
    expect(host.openSocketCount, 0);
    expect(host.httpConnectionCount, 0);

    for (var i = 0; i < 100; i++) {
      final trace = ConnectionTrace();
      traces.add(trace);
      final connecting = trace.run(() => _connect(host));
      final failure = expectLater(connecting, _timedOut());
      await requested.future.timeout(_bound);
      trace.expire();
      await failure;
      release.complete();
      await trace.connectionSettled.future.timeout(_bound);
      await _until(() => host.upgradeAttemptsCompleted == i + 1);
      await trace.awaitProductionCloses();
      if (trace.sockets.values.any((socket) => socket.closeCalls > 0)) {
        await _until(() => trace.openSocketCount == 0 && host.openSocketCount == 0);
      }
      clientCounts.add(traces.fold(0, (sum, item) => sum + item.openSocketCount));
      serverCounts.add(host.openSocketCount);
      requested = Completer<void>();
      release = Completer<void>();
    }

    // Counts are observed BEFORE any fixture teardown can mask a leak. On the
    // broken baseline all 100 cycles finish, retaining up to 100 real sockets.
    expect(clientCounts, everyElement(0));
    final terminalBound = Stopwatch()..start();
    while (!host.allSocketTransportsDone && terminalBound.elapsed < _bound) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    expect(serverCounts, everyElement(0), reason:
        'SDK ${Platform.version}; peer transports done: '
        '${host.allSocketTransportsDone}; ${host.socketDiagnostics}');
    await _until(() => host.httpConnectionCount == 0);
    expect(host.httpConnectionCount, 0);
    expect(host.hellos, isEmpty);
  }, timeout: const Timeout(Duration(minutes: 2)));

  test('control: a late upgrade error preserves timeout without uncaught failure',
      () async {
    final requested = Completer<void>();
    final release = Completer<void>();
    final host = await LoopbackHost.start(
        replies: [], rejectUpgrade: true, beforeUpgrade: () {
      requested.complete();
      return release.future;
    });
    addTearDown(() {
      if (!release.isCompleted) release.complete();
    });
    final trace = ConnectionTrace();
    final connecting = trace.run(() => _connect(host));
    final failure = expectLater(connecting, _timedOut());
    await requested.future.timeout(_bound);
    trace.expire();
    await failure;
    release.complete();
    await trace.connectionSettled.future.timeout(_bound);
    await _until(() => host.upgradeAttemptsCompleted == 1);
    expect(trace.openSocketCount, 0);
    expect(host.openSocketCount, 0);
    expect(host.hellos, isEmpty);
  });

  test('control: a timely wrong-pin error remains a connection exception',
      () async {
    final host = await LoopbackHost.start(replies: [_authGrant]);
    final trace = ConnectionTrace();
    await expectLater(
        trace.run(() => SelahSession.connect(
            host: '127.0.0.1', port: host.port, pinHex: '00' * 32, creds: _creds)),
        throwsA(isA<SessionException>().having(
            (error) => error.message, 'message', startsWith('could not connect:'))));
    expect(trace.deadlineActive, isFalse);
    expect(trace.openSocketCount, 0);
    expect(host.hellos, isEmpty);
  });
}
