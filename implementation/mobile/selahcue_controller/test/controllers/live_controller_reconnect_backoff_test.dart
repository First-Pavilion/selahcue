/// 17tnw2b0vtj — the reconnect loop's BOUNDS, on a virtual clock.
///
/// Widening the catch in `_reconnect()` means a permanently-broken host is now
/// retried for as long as the app is open. That is only acceptable if the retry
/// is cheap and bounded where it matters: one attempt at a time, a real backoff
/// between attempts (not a hot loop), and no state that grows with the number of
/// failures. The recovery tests next door cannot see any of that — they pass
/// just as well with a 100 ms backoff — so it is pinned here with a fake clock,
/// where a thousand failures cost no real time.
library;

import 'dart:math' as math;

import 'package:fake_async/fake_async.dart';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

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

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

/// The error `frame as String` throws for a binary frame, from a real failing
/// cast rather than a hand-made look-alike.
Object _binaryFrameTypeError() {
  try {
    final Object frame = <int>[0, 1, 2];
    return frame as String;
  } on TypeError catch (e) {
    return e;
  }
}

/// Run [body] with `debugPrint` captured into [sink], restoring it afterwards.
///
/// Needed in BOTH tests below: the production `debugPrint` is throttled and
/// schedules a Timer, which on the virtual clock would show up as a pending
/// timer that has nothing to do with the loop under test.
T _capturingDebugPrint<T>(List<String> sink, T Function() body) {
  final original = debugPrint;
  debugPrint = (String? message, {int? wrapWidth}) {
    if (message != null) sink.add(message);
  };
  try {
    return body();
  } finally {
    debugPrint = original;
  }
}

void main() {
  test('1000 consecutive failures: a real backoff between attempts, one at a '
      'time, nothing grows, and dispose leaves no timers behind', () {
    // Every unexpected failure type is recorded once per outage; captured here
    // so that is not mistaken for the loop's own state.
    final recorded = <String>[];
    _capturingDebugPrint(recorded, () => fakeAsync((async) {
      var attempts = 0;
      var inFlight = 0;
      var maxInFlight = 0;
      final starts = <Duration>[]; // when each attempt began, on the fake clock

      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        attempts++;
        inFlight++;
        maxInFlight = math.max(maxInFlight, inFlight);
        starts.add(async.elapsed);
        try {
          // A slow failing connect, so an attempt is genuinely in flight for a
          // while and a second, overlapping loop would show up in maxInFlight.
          await Future<void>.delayed(const Duration(milliseconds: 100));
          // Rotate the failure kinds the loop must absorb.
          switch (attempts % 4) {
            case 0:
              throw const FormatException('not json');
            case 1:
              throw const SessionException('network down');
            case 2:
              throw _binaryFrameTypeError();
            default:
              throw StateError('some other failure');
          }
        } finally {
          inFlight--;
        }
      }

      final live = LiveController(
          session: _DeadSession(), stored: _stored, connect: connect);
      var notifications = 0;
      live.addListener(() => notifications++);

      // The constructor's refresh() fails, _reconnect() starts, attempt 1 runs.
      async.flushMicrotasks();
      async.elapse(const Duration(milliseconds: 500));
      expect(attempts, 1, reason: 'baseline: the loop is up and has tried once');
      final baselineTimers = async.pendingTimers.length;
      final baselineNotifications = notifications;
      var maxTimers = baselineTimers;

      while (attempts < 1000) {
        async.elapse(const Duration(seconds: 1));
        maxTimers = math.max(maxTimers, async.pendingTimers.length);
      }

      // A real backoff: no two attempts closer than the 2 s the loop declares.
      // (A 100 ms backoff, or none, would fail here — and only here.)
      for (var i = 1; i < starts.length; i++) {
        expect(starts[i] - starts[i - 1], greaterThanOrEqualTo(
            const Duration(seconds: 2)),
            reason: 'attempt ${i + 1} began too soon after attempt $i');
      }
      expect(maxInFlight, 1, reason: 'attempts never overlap');
      // Nothing grows with the number of failures.
      expect(maxTimers, baselineTimers, reason: 'no timer accumulation');
      expect(notifications, baselineNotifications,
          reason: 'failed attempts must not spam listeners');
      expect(live.reconnecting, isTrue, reason: 'still retrying, not wedged');

      // Dispose mid-loop: the loop must wind down and leave nothing scheduled.
      live.dispose();
      async.elapse(const Duration(seconds: 5));
      final attemptsAtDispose = attempts;
      async.elapse(const Duration(seconds: 30));
      expect(attempts, attemptsAtDispose, reason: 'no attempts after dispose');
      expect(async.pendingTimers, isEmpty, reason: 'no leaked timers');
    }));
    // Bounded recording: 1000 failures of 3 unexpected types are 3 records
    // (2 lines each: label + stack), not 750.
    expect(recorded.length, lessThanOrEqualTo(6),
        reason: 'recording must not grow with the number of failures');
  });

  test('an unexpected connect failure is recorded by TYPE and stack only, once '
      'per type, and never with host-sent text', () {
    // The loop treats anything but SessionRevoked as transient, which would make
    // an unmodelled failure (a parsing bug, a platform error) invisible. So it
    // is recorded — but a FormatException's toString() embeds the offending
    // source, i.e. text the peer chose, so only the runtime TYPE and a stack
    // (which carries no payload) may be written.
    final printed = <String>[];
    _capturingDebugPrint(printed, () => fakeAsync((async) {
      final failures = <Object>[
        const FormatException('HOST-SENT-PAYLOAD-1'),
        const FormatException('HOST-SENT-PAYLOAD-2'), // same type: not repeated
        const SessionException('network down'), // expected: not recorded
        StateError('HOST-SENT-PAYLOAD-3'), // new type: recorded
      ];
      var attempts = 0;
      final replacement = _HealthySession();
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        if (attempts < failures.length) throw failures[attempts++];
        attempts++;
        return replacement;
      }

      final live = LiveController(
          session: _DeadSession(), stored: _stored, connect: connect);
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 30));
      expect(live.reconnecting, isFalse, reason: 'baseline: it recovered');
      expect(attempts, failures.length + 1);
      live.dispose();
      async.elapse(const Duration(seconds: 5));
    }));

    final log = printed.join('\n');
    expect(log, isNot(contains('HOST-SENT-PAYLOAD')),
        reason: 'never the message/toString() of a host-influenced error');
    expect(log, isNot(contains('network down')),
        reason: 'an expected SessionException is not an unexpected failure');
    expect(
        printed.where((m) => m.contains('unexpected FormatException')), hasLength(1),
        reason: 'recorded once per type, not once per attempt');
    expect(printed.where((m) => m.contains('unexpected StateError')),
        hasLength(1));
    expect(log, contains('live_controller_reconnect_backoff_test.dart'),
        reason: 'a stack is recorded, so the failure can be located');
  });
}

/// A healthy replacement session for the recovery step of a reconnect.
class _HealthySession implements ControllerSession {
  @override
  MobileRole get grantedRole => MobileRole.producer;
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
        planName: 'Sunday',
        items: [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
      );
  @override
  Future<void> close() async {}
}
