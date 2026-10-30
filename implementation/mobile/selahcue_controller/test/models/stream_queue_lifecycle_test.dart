/// 17tnw2b0vty: keep real StreamQueue/future behavior while controlling only
/// external stream delivery and timer ordering. No elapsed-time probability test.
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/session.dart';

const _wait = Duration(seconds: 10);

/// A single due timer callback, invoked explicitly before yielding to delivery
/// microtasks. Future.timeout still installs/cancels its real callback itself.
class _DueTimer implements Timer {
  _DueTimer(this._callback);

  final void Function() _callback;
  bool _active = true;
  int _tick = 0;

  void fire() {
    if (!_active) return;
    _active = false;
    _tick = 1;
    _callback();
  }

  @override
  bool get isActive => _active;

  @override
  int get tick => _tick;

  @override
  void cancel() => _active = false;
}

class _DueTimers {
  final timers = <_DueTimer>[];

  T run<T>(T Function() body) => runZoned(body,
      zoneSpecification: ZoneSpecification(
        createTimer: (self, parent, zone, duration, callback) {
          expect(duration, _wait, reason: 'only the selected due timers belong here');
          final timer = _DueTimer(zone.bindCallbackGuarded(callback));
          timers.add(timer);
          return timer;
        },
      ));
}

SelahSession _session(StreamQueue queue) => SelahSession.forTest(
      send: (_) {},
      incoming: queue,
      role: 'producer',
    );

Matcher _closedRead() => throwsA(isA<SessionException>()
    .having((error) => error.message, 'message', 'connection closed'));

void main() {
  test('control: normal synchronous delivery cancels the read timeout', () async {
    final frames = StreamController<dynamic>(sync: true);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final clock = _DueTimers();
    final read = clock.run(() {
      final pending = queue.nextJson(_wait);
      frames.add('{"n":1}');
      return pending;
    });

    expect(await read, {'n': 1});
    expect(clock.timers, hasLength(1));
    expect(clock.timers.single.isActive, isFalse);
  });

  test('a frame handed to a waiter survives the same-turn timeout callback',
      () async {
    final frames = StreamController<dynamic>(sync: true);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final clock = _DueTimers();
    final read = clock.run(() {
      final pending = queue.nextJson(_wait);
      Timer(_wait, () => frames.add('{"n":7}'));
      expect(clock.timers, hasLength(2));
      // Both timers are due. Deliver synchronously, then fire read timeout in
      // the SAME stack, before the waiter's completion microtask can propagate.
      clock.timers[1].fire();
      clock.timers[0].fire();
      return pending;
    });

    expect(await read, {'n': 7});
    // The rescued frame belongs to the first read; it must not be duplicated
    // into the queue for the next one.
    frames.add('{"n":8}');
    expect(await queue.nextJson(_wait), {'n': 8});
  });

  test('control: a genuine timeout leaves a later frame for the next reader',
      () async {
    final frames = StreamController<dynamic>(sync: true);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final clock = _DueTimers();
    final read = clock.run(() => queue.nextJson(_wait));
    final failure = expectLater(
        read,
        throwsA(isA<SessionException>().having((error) => error.message,
            'message', 'timed out waiting for the host')));
    clock.timers.single.fire();
    await failure;

    frames.add('{"n":9}');
    expect(await queue.nextJson(_wait), {'n': 9});
  });

  test('control: natural stream completion drains existing FIFO frames',
      () async {
    final frames = StreamController<dynamic>(sync: true);
    final queue = StreamQueue(frames.stream);
    frames.add('{"n":1}');
    frames.add('{"n":2}');
    await frames.close();

    expect(await queue.nextJson(_wait), {'n': 1});
    expect(await queue.nextJson(_wait), {'n': 2});
    await expectLater(queue.nextJson(_wait), _closedRead());
  });

  test('session close cancels inbound delivery and rejects late frames',
      () async {
    var cancels = 0;
    final frames = StreamController<dynamic>(
        sync: true, onCancel: () => cancels++);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final session = _session(queue);

    await session.close();
    expect(cancels, 1);
    expect(frames.hasListener, isFalse);
    frames.add('{"late":true}');
    await expectLater(queue.nextJson(_wait), _closedRead());
    await session.close();
    expect(cancels, 1, reason: 'repeated close must remain safe');
  });

  test('session close discards frames already buffered before teardown',
      () async {
    final frames = StreamController<dynamic>(sync: true);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final session = _session(queue);
    frames.add('{"buffered":1}');
    frames.add('{"buffered":2}');

    await session.close();
    await expectLater(queue.nextJson(_wait), _closedRead());
  });

  test('session close promptly finishes every pending reader as closed',
      () async {
    final frames = StreamController<dynamic>(sync: true);
    addTearDown(frames.close);
    final queue = StreamQueue(frames.stream);
    final session = _session(queue);
    final outcomes = <Object>[];
    for (var i = 0; i < 3; i++) {
      unawaited(queue.nextJson(_wait).then<void>(outcomes.add,
          onError: (Object error) => outcomes.add(error)));
    }

    await session.close();
    await pumpEventQueue();
    expect(outcomes, hasLength(3), reason: 'close must not await read deadlines');
    for (final outcome in outcomes) {
      expect(
          outcome,
          isA<SessionException>()
              .having((error) => error.message, 'message', 'connection closed'));
    }
  });

  test('session close awaits asynchronous subscription cancellation', () async {
    var cancels = 0;
    final cancelGate = Completer<void>();
    final frames = StreamController<dynamic>(sync: true, onCancel: () {
      cancels++;
      return cancelGate.future;
    });
    addTearDown(() {
      if (!cancelGate.isCompleted) cancelGate.complete();
      return frames.close();
    });
    final queue = StreamQueue(frames.stream);
    final session = _session(queue);
    var finished = false;
    final closing = session.close().then((_) => finished = true);
    await pumpEventQueue();

    expect(cancels, 1);
    expect(finished, isFalse);
    cancelGate.complete();
    await closing;
    expect(finished, isTrue);
    await session.close();
    expect(cancels, 1);
  });
}
