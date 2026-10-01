/// `SelahSession.command()` must give up on a command a bounded time after THAT
/// command was sent (17tnw2ay5jk).
///
/// It used to restart its `commandTimeout` clock for every frame it read, so a
/// host that kept the socket busy with frames that never answered the in-flight
/// command — stale correlated acks are the shape `command()` discards and keeps
/// reading past — held the command open for ever. `LiveController.act()` awaits
/// that future while `busy` is true, and every control including the emergency
/// strip's BLACKOUT is gated on `busy`, so one stuck command left the whole phone
/// dead with no banner.
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/session.dart';

const Duration _deadline = Duration(milliseconds: 300);

/// An in-memory transport: [host] plays the operator host's side of the socket.
class _Harness {
  _Harness() {
    session = SelahSession.forTest(
      send: sent.add,
      incoming: StreamQueue(host.stream),
      role: 'producer',
      commandDeadline: _deadline,
    );
  }

  final host = StreamController<dynamic>();
  final sent = <String>[];
  late final SelahSession session;

  void ack(int requestId) => host.add('{"event":"ack","request_id":$requestId}');

  Future<void> dispose() => host.close();
}

void main() {
  test('a host that only sends stale acks cannot hold a command open past the deadline',
      () async {
    final h = _Harness();
    // Stale = correlated to a request id EARLIER than the in-flight one (the
    // first command is id 1), which `command()` discards and reads past. Faster
    // than the deadline, so a per-frame timeout never fires.
    final noise = Timer.periodic(const Duration(milliseconds: 20), (_) => h.ack(0));
    addTearDown(() {
      noise.cancel();
      return h.dispose();
    });

    final started = Stopwatch()..start();
    // The outer `.timeout` turns the old unbounded hang into a failure instead of
    // a hung test run.
    await expectLater(
      h.session.command(cmdBlackout(true)).timeout(const Duration(seconds: 5)),
      throwsA(isA<SessionException>()),
    );
    expect(started.elapsed, lessThan(const Duration(seconds: 2)),
        reason: 'must give up near the per-command deadline, not wait on liveness');
  });

  test('a host that goes silent still times out', () async {
    final h = _Harness();
    addTearDown(h.dispose);
    await expectLater(
      h.session.command(cmdBlackout(true)).timeout(const Duration(seconds: 5)),
      throwsA(isA<SessionException>()),
    );
  });

  test('a stale ack followed by the real reply still completes', () async {
    final h = _Harness();
    addTearDown(h.dispose);
    final reply = h.session.command(cmdBlackout(true));
    h.ack(0); // stale: discarded
    h.ack(1); // this command's own ack
    expect(await reply, isA<Ack>());
  });

  test('the deadline is per command: a fast command after a slow one gets a full budget',
      () async {
    final h = _Harness();
    addTearDown(h.dispose);
    final first = h.session.command(cmdBlackout(true));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    h.ack(1);
    await first;
    // Well past 300ms since the FIRST command was sent, but this one has only
    // just started.
    await Future<void>.delayed(const Duration(milliseconds: 150));
    final second = h.session.command(cmdBlackout(false));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    h.ack(2);
    expect(await second, isA<Ack>());
  });
}
