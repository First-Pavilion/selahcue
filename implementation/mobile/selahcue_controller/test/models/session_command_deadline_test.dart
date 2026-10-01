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
  _Harness({Duration deadline = _deadline}) {
    session = SelahSession.forTest(
      send: sent.add,
      incoming: StreamQueue(host.stream),
      role: 'producer',
      commandDeadline: deadline,
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

  test('a stale frame late in the budget, then silence, does not extend the deadline',
      () async {
    // Pins that each read is clamped to the time REMAINING, not handed a fresh
    // full budget: a stale frame at 85% of the deadline followed by silence
    // would otherwise run to roughly 1.85x (QA review, PR #132). Real time: the
    // deadline uses a Stopwatch that fake time does not advance.
    final h = _Harness(deadline: const Duration(seconds: 1));
    addTearDown(h.dispose);
    Timer(const Duration(milliseconds: 850), () => h.ack(0));
    final started = Stopwatch()..start();
    await expectLater(
      h.session.command(cmdBlackout(true)).timeout(const Duration(seconds: 5)),
      throwsA(isA<SessionException>()),
    );
    expect(started.elapsed, lessThan(const Duration(milliseconds: 1500)),
        reason: 'unclamped reads would end near 1.85s');
  });

  test('an expired deadline fails the command even when its reply is already buffered',
      () async {
    // Pins the `remaining <= zero` guard: nextJson returns a buffered frame
    // without consulting its timeout, so only that guard stops an expired
    // command from reading on. Expired means failed.
    final h = _Harness(deadline: Duration.zero);
    addTearDown(h.dispose);
    h.ack(1);
    await Future<void>.delayed(Duration.zero); // let the frame reach the buffer
    await expectLater(
      h.session.command(cmdBlackout(true)).timeout(const Duration(seconds: 5)),
      throwsA(isA<SessionException>()),
    );
  });

  test('the clock starts when a command\'s turn starts, not when it was queued',
      () async {
    // Real time on purpose: the deadline uses a Stopwatch, which fake time does
    // not advance. 1s budget with 400ms+ of slack on each side keeps this stable
    // on a loaded runner.
    final h = _Harness(deadline: const Duration(seconds: 1));
    addTearDown(h.dispose);
    final first = h.session.command(cmdBlackout(true));
    final second = h.session.command(cmdBlackout(false)); // queued behind `first`
    await Future<void>.delayed(const Duration(milliseconds: 600));
    h.ack(1);
    await first;
    // `second` has now been waiting 600ms+ since the call, and its own turn
    // starts only now. Answering 600ms into that turn lands 1.2s after the
    // call: inside its own 1s budget, but past it if the clock ran from queueing.
    await Future<void>.delayed(const Duration(milliseconds: 600));
    h.ack(2);
    expect(await second, isA<Ack>());
  });
}
