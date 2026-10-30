/// 17tnw2b0vtm: parked frames are liveness, not a fresh pairing budget.
/// Exercise the shared production handshake using PR132's in-memory transport.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/session.dart';

const _budget = Duration(milliseconds: 300);
const _outerBound = Duration(seconds: 3);
const _grant = '{"pair":"granted","device_id":"dev-test",'
    '"token":"opaque-token","role":"viewer"}';
const _parked = '{"pair":"parked"}';

class _Harness {
  _Harness({this.deadline = _budget}) {
    host = StreamController<dynamic>(sync: true);
    incoming = StreamQueue(host.stream);
  }

  final Duration deadline;
  late final StreamController<dynamic> host;
  late final StreamQueue incoming;
  final sent = <Map<String, dynamic>>[];
  int closeCalls = 0;

  Future<(SelahSession, Credentials)> pair() => SelahSession.pairForTest(
        send: (frame) => sent.add(jsonDecode(frame) as Map<String, dynamic>),
        close: () {
          closeCalls++;
          return host.close();
        },
        incoming: incoming,
        code: 'CODE-1',
        deviceName: 'Test phone',
        deadline: deadline,
      );

  void frame(String value) => host.add(value);

  Future<void> dispose() async {
    await incoming.close();
    await host.close();
  }
}

Matcher _timeout() => throwsA(isA<SessionException>().having(
    (error) => error.message, 'message', 'timed out waiting for the host'));

void main() {
  test('parked frames forever cannot renew the overall pairing budget', () async {
    final h = _Harness();
    final noise = Timer.periodic(const Duration(milliseconds: 20),
        (_) => h.frame(_parked));
    addTearDown(() async {
      noise.cancel();
      await h.dispose();
    });
    final elapsed = Stopwatch()..start();
    await expectLater(h.pair().timeout(_outerBound), _timeout());
    expect(elapsed.elapsed, lessThan(const Duration(seconds: 2)));
    expect(h.closeCalls, 1);
    expect(h.sent.single['hello'], 'pair');
  });

  test('parked late then silent cannot obtain a fresh full wait', () async {
    final h = _Harness(deadline: const Duration(seconds: 1));
    final noise = Timer(const Duration(milliseconds: 850), () => h.frame(_parked));
    addTearDown(() async {
      noise.cancel();
      await h.dispose();
    });
    final elapsed = Stopwatch()..start();
    await expectLater(h.pair().timeout(_outerBound), _timeout());
    expect(elapsed.elapsed, lessThan(const Duration(milliseconds: 1500)),
        reason: 'a renewed per-frame budget would finish near1.85 seconds');
    expect(h.closeCalls, 1);
  });

  test('an expired budget cannot accept a grant already in the input buffer',
      () async {
    final h = _Harness(deadline: Duration.zero);
    addTearDown(h.dispose);
    h.frame(_grant);
    await expectLater(h.pair().timeout(_outerBound), _timeout());
    expect(h.closeCalls, 1);
  });

  test('control: honest host parks for120of150 scaled seconds then grants',
      () async {
    // The production150s/host120s relationship is scaled by100 for this real
    // Stopwatch test. No test-only virtual clock or wire parser is substituted.
    expect(pairTimeout, const Duration(seconds: 150),
        reason: 'keep the production30s margin over the host120s park window');
    final h = _Harness(deadline: const Duration(milliseconds: 1500));
    final parked = Timer.periodic(const Duration(milliseconds: 100),
        (_) => h.frame(_parked));
    final granted = Timer(const Duration(milliseconds: 1200), () {
      parked.cancel();
      h.frame(_grant);
    });
    addTearDown(() async {
      parked.cancel();
      granted.cancel();
      await h.dispose();
    });
    final (session, creds) = await h.pair().timeout(_outerBound);
    expect((creds.deviceId, creds.token), ('dev-test', 'opaque-token'));
    expect(session.role, 'viewer');
    expect(h.closeCalls, 0, reason: 'successful session remains caller-owned');
    expect(h.sent.single['hello'], 'pair');
    expect(h.sent.single['code'], 'CODE-1');
    await session.close();
    expect(h.closeCalls, 1);
  });

  test('control: an immediate grant stays usable until caller close', () async {
    final h = _Harness();
    addTearDown(h.dispose);
    h.frame(_grant);
    final (session, creds) = await h.pair().timeout(_outerBound);
    expect((creds.deviceId, creds.token), ('dev-test', 'opaque-token'));
    expect(h.closeCalls, 0);
    await session.close();
    expect(h.closeCalls, 1);
  });

  test('control: explicit operator cancellation retains rejection and closes',
      () async {
    final h = _Harness();
    addTearDown(h.dispose);
    h.frame(_parked);
    h.frame('{"pair":"rejected","reason":"operator_cancelled"}');
    await expectLater(h.pair().timeout(_outerBound), throwsA(
        isA<SessionException>().having((error) => error.message, 'message',
            'pairing rejected: operator_cancelled')));
    expect(h.closeCalls, 1);
  });

  test('control: malformed terminal after parked fails and closes', () async {
    final h = _Harness();
    addTearDown(h.dispose);
    h.frame(_parked);
    h.frame('{"pair":"granted","token":5}');
    await expectLater(h.pair().timeout(_outerBound), throwsA(
        isA<SessionException>().having((error) => error.message, 'message',
            'malformed frame from the host')));
    expect(h.closeCalls, 1);
  });

  test('control: host disconnect while parked terminates and closes once',
      () async {
    final h = _Harness();
    addTearDown(h.dispose);
    final pairing = h.pair();
    final checked = expectLater(pairing.timeout(_outerBound), throwsA(
        isA<SessionException>().having((error) => error.message, 'message',
            'connection closed')));
    h.frame(_parked);
    await h.host.close();
    await checked;
    expect(h.closeCalls, 1);
  });

  test('control: a silent host still times out and closes exactly once', () async {
    final h = _Harness();
    addTearDown(h.dispose);
    await expectLater(h.pair().timeout(_outerBound), _timeout());
    expect(h.closeCalls, 1);
  });
}
