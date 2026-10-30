/// F1Y: observe real controller attempt starts and owned timer lifetimes on the
/// fake clock. Transport is injected; retry scheduling is production code.
library;

import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

import '../support/fake_keystore.dart';

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

class _Session implements ControllerSession {
  _Session({this.dead = false});

  bool dead;
  int closes = 0;
  int reads = 0;

  @override
  MobileRole get grantedRole => MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);

  @override
  Future<OperatorStateView> operatorState() async {
    reads++;
    if (dead) throw const SessionException('offline');
    return const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );
  }

  @override
  Future<void> close() async {
    closes++;
  }
}

void main() {
  test('failed attempts grow into the capped retry window without overlap', () {
    fakeAsync((clock) {
      final starts = <Duration>[];
      var inFlight = 0;
      var peakInFlight = 0;
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        expect(host, _stored.host);
        expect(port, _stored.port);
        expect(pinHex, _stored.pinHex);
        expect(creds.deviceId, _stored.deviceId);
        expect(creds.token, _stored.token);
        starts.add(clock.elapsed);
        inFlight++;
        if (inFlight > peakInFlight) peakInFlight = inFlight;
        try {
          await Future<void>.delayed(const Duration(milliseconds: 100));
          throw const SessionException('offline');
        } finally {
          inFlight--;
        }
      }

      final live = LiveController(
        session: _Session(dead: true),
        stored: _stored,
        connect: connect,
      );
      try {
        clock.flushMicrotasks();
        // A finite virtual horizon also catches a wedged or over-cap loop.
        while (starts.length < 9 && clock.elapsed < const Duration(minutes: 5)) {
          clock.elapse(const Duration(milliseconds: 100));
        }
        expect(starts, hasLength(9), reason: 'all eight waits were exercised');
        const lower = [2000, 4000, 8000, 16000, 24000, 24000, 24000, 24000];
        const upper = [2500, 5000, 10000, 20000, 30000, 30000, 30000, 30000];
        for (var i = 0; i < lower.length; i++) {
          final wait = starts[i + 1] - starts[i] -
              const Duration(milliseconds: 100);
          expect(wait.inMicroseconds,
              inInclusiveRange(lower[i] * 1000, upper[i] * 1000),
              reason: 'wait ${i + 1} must grow, then remain capped');
        }
        expect(peakInFlight, 1, reason: 'polling never starts another loop');
        expect(live.reconnecting, isTrue);
      } finally {
        live.dispose();
        // Finish only the transport-owned 100ms operation, not a retry wait.
        clock.elapse(const Duration(seconds: 35));
      }
      expect(clock.pendingTimers, isEmpty);
    });
  });

  test('successful recovery resets the next outage to its first retry window',
      () {
    fakeAsync((clock) {
      final first = _Session();
      final second = _Session();
      final starts = <Duration>[];
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        starts.add(clock.elapsed);
        if (starts.length == 4) return first;
        if (starts.length == 6) return second;
        throw const SessionException('offline');
      }

      final live = LiveController(
        session: _Session(dead: true),
        stored: _stored,
        connect: connect,
      );
      try {
        clock.flushMicrotasks();
        clock.elapse(const Duration(seconds: 20));
        expect(starts, hasLength(4), reason: 'three failures then recovery');
        expect(live.syncing, isFalse);
        expect(first.reads, greaterThan(0), reason: 'fresh state really arrived');
        first.dead = true;
        unawaited(live.refresh());
        clock.flushMicrotasks();
        expect(starts, hasLength(5), reason: 'second outage starts immediately');
        clock.elapse(const Duration(seconds: 3));
        expect(starts, hasLength(6), reason: 'success reset the accumulated wait');
        expect((starts[5] - starts[4]).inMicroseconds,
            inInclusiveRange(2000000, 2500000));
        expect(live.syncing, isFalse);
        expect(second.reads, greaterThan(0));
        expect(first.closes, 1, reason: 'failed replacement was retired');
      } finally {
        live.dispose();
        clock.elapse(const Duration(seconds: 35));
      }
      expect(clock.pendingTimers, isEmpty);
    });
  });

  test('dispose synchronously cancels the pending retry timer', () {
    fakeAsync((clock) {
      var attempts = 0;
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        attempts++;
        throw const SessionException('offline');
      }

      final live = LiveController(
          session: _Session(dead: true), stored: _stored, connect: connect);
      clock.flushMicrotasks();
      expect(attempts, 1);
      expect(clock.nonPeriodicTimerCount, 1,
          reason: 'a real backoff is pending before teardown');
      live.dispose();
      expect(clock.pendingTimers, isEmpty,
          reason: 'cancel now, without advancing time to the deadline');
      clock.flushMicrotasks();
      clock.elapse(const Duration(minutes: 2));
      expect(attempts, 1);
      expect(clock.pendingTimers, isEmpty);
    });
  });

  test('unpair synchronously cancels the pending retry timer', () {
    final keystore = FakeKeystore()..install();
    fakeAsync((clock) {
      var attempts = 0;
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        attempts++;
        throw const SessionException('offline');
      }

      final live = LiveController(
          session: _Session(dead: true), stored: _stored, connect: connect);
      try {
        clock.flushMicrotasks();
        expect(attempts, 1);
        expect(clock.nonPeriodicTimerCount, 1);
        unawaited(live.unpair());
        expect(clock.pendingTimers, isEmpty,
            reason: 'clear wait before asynchronous credential deletion');
        clock.flushMicrotasks();
        clock.elapse(const Duration(minutes: 2));
        expect(attempts, 1);
        expect(keystore.deletes, 1);
      } finally {
        live.dispose();
        clock.elapse(const Duration(seconds: 35));
      }
      expect(clock.pendingTimers, isEmpty);
    });
  });

  test('a connect failure after dispose cannot schedule a new backoff', () {
    fakeAsync((clock) {
      final pending = Completer<ControllerSession>();
      var attempts = 0;
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) {
        attempts++;
        return pending.future;
      }

      final live = LiveController(
          session: _Session(dead: true), stored: _stored, connect: connect);
      clock.flushMicrotasks();
      expect(attempts, 1);
      live.dispose();
      expect(clock.pendingTimers, isEmpty);
      pending.completeError(const SessionException('late offline'));
      clock.flushMicrotasks();
      expect(clock.pendingTimers, isEmpty,
          reason: 'a stopped controller must not create a fresh retry timer');
      clock.elapse(const Duration(minutes: 2));
      expect(attempts, 1);
    });
  });

  test('a connect success after unpair is closed without adoption', () {
    FakeKeystore().install();
    fakeAsync((clock) {
      final pending = Completer<ControllerSession>();
      final late = _Session();
      var attempts = 0;
      Future<ControllerSession> connect({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) {
        attempts++;
        return pending.future;
      }

      final live = LiveController(
          session: _Session(dead: true), stored: _stored, connect: connect);
      clock.flushMicrotasks();
      expect(attempts, 1);
      unawaited(live.unpair());
      clock.flushMicrotasks();
      pending.complete(late);
      clock.flushMicrotasks();
      expect(late.closes, 1);
      expect(late.reads, 0, reason: 'retired connect result was never adopted');
      expect(clock.pendingTimers, isEmpty);
      clock.elapse(const Duration(minutes: 2));
      expect(attempts, 1);
      live.dispose();
    });
  });
}
