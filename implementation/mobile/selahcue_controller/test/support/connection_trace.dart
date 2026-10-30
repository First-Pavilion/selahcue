/// Test-only observation/scheduling around the REAL WebSocket.connect future.
/// HTTP/TLS, socket I/O, handshake parsing and session code remain production.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/session.dart';

class _Deadline implements Timer {
  _Deadline(this.callback);
  final void Function() callback;
  bool _active = true;
  bool expired = false;

  void fire() {
    if (!_active) throw StateError('deadline was already cancelled');
    _active = false;
    expired = true;
    callback();
  }

  @override
  void cancel() => _active = false;
  @override
  bool get isActive => _active;
  @override
  int get tick => expired ? 1 : 0;
}

/// Fully forwards an acquired real socket; only explicit close calls are counted.
class ObservedWebSocket extends Stream<dynamic> implements WebSocket {
  ObservedWebSocket(this.socket);
  final WebSocket socket;
  int closeCalls = 0;
  Future<void>? closeDone;

  @override
  StreamSubscription<dynamic> listen(void Function(dynamic)? onData,
          {Function? onError, void Function()? onDone, bool? cancelOnError}) =>
      socket.listen(onData,
          onError: onError, onDone: onDone, cancelOnError: cancelOnError);
  @override
  void add(dynamic data) => socket.add(data);
  @override
  void addError(Object error, [StackTrace? stackTrace]) =>
      socket.addError(error, stackTrace);
  @override
  Future<void> addStream(Stream<dynamic> stream) async {
    await socket.addStream(stream);
  }
  @override
  void addUtf8Text(List<int> bytes) => socket.addUtf8Text(bytes);
  @override
  Future<void> close([int? code, String? reason]) {
    closeCalls++;
    return closeDone = socket.close(code, reason).then<void>((_) {});
  }
  @override
  Future<dynamic> get done => socket.done;
  @override
  int get readyState => socket.readyState;
  @override
  String get extensions => socket.extensions;
  @override
  String? get protocol => socket.protocol;
  @override
  int? get closeCode => socket.closeCode;
  @override
  String? get closeReason => socket.closeReason;
  @override
  Duration? get pingInterval => socket.pingInterval;
  @override
  set pingInterval(Duration? interval) => socket.pingInterval = interval;
}

class ConnectionTrace {
  ConnectionTrace({this.manualDeadline = true, this.holdSocketCompletion = false}) {
    addTearDown(() async {
      releaseSocketCompletion();
      for (final observed in sockets.values) {
        // Fixture cleanup is deliberately below the observer, after assertions;
        // it must not manufacture a successful production close count.
        await observed.socket.close().timeout(const Duration(seconds: 5));
      }
    });
  }

  final bool manualDeadline;
  final bool holdSocketCompletion;
  final sockets = Map<WebSocket, ObservedWebSocket>.identity();
  final socketAcquired = Completer<ObservedWebSocket>();
  final connectionSettled = Completer<void>();
  _Deadline? _deadline;
  void Function()? _heldCompletion;
  bool _heldOnce = false;

  bool get deadlineActive => _deadline?.isActive ?? false;
  int get openSocketCount =>
      sockets.values.where((value) => value.readyState != WebSocket.closed).length;

  void expire() {
    final deadline = _deadline;
    if (deadline == null) throw StateError('connect timeout was not installed');
    deadline.fire();
  }

  void releaseSocketCompletion() {
    final callback = _heldCompletion;
    _heldCompletion = null;
    callback?.call();
  }

  Future<T> run<T>(Future<T> Function() body) => runZoned(body,
      zoneSpecification: ZoneSpecification(
        createTimer: (self, parent, zone, duration, callback) {
          // Only the first public establishment timeout is controlled. HTTP,
          // TLS and subsequent auth/pair timers retain their real scheduling.
          if (manualDeadline && _deadline == null && duration == connectTimeout) {
            return _deadline = _Deadline(zone.bindCallbackGuarded(callback));
          }
          return parent.createTimer(zone, duration, callback);
        },
        runUnary: <R, T>(self, parent, zone, callback, value) {
          if (value is WebSocket && value is! ObservedWebSocket) {
            final observed =
                sockets.putIfAbsent(value, () => ObservedWebSocket(value));
            if (!socketAcquired.isCompleted) socketAcquired.complete(observed);
            if (!connectionSettled.isCompleted) connectionSettled.complete();
            if (holdSocketCompletion && !_heldOnce) {
              // SDK Future.timeout registers a void completion callback on its
              // source future. Defer that delivery after a real socket has been
              // detached/acquired, rather than faking a WebSocket or connect.
              _heldOnce = true;
              _heldCompletion = () => parent.runUnary(zone, callback, observed as T);
              return null as R;
            }
            return parent.runUnary(zone, callback, observed as T);
          }
          return parent.runUnary(zone, callback, value);
        },
        runBinary: <R, T1, T2>(self, parent, zone, callback, first, second) {
          // Timeout is not an IOException. An eventual real transport failure
          // marks the abandoned connect settled without intercepting its error.
          if (first is IOException && !connectionSettled.isCompleted) {
            connectionSettled.complete();
          }
          return parent.runBinary(zone, callback, first, second);
        },
      ));

  Future<void> awaitProductionCloses() async {
    await pumpEventQueue();
    for (final observed in sockets.values) {
      final closeDone = observed.closeDone;
      if (closeDone != null) {
        await closeDone.timeout(const Duration(seconds: 5));
      }
    }
    await pumpEventQueue();
  }
}
