/// The ticket's actual harm, end to end (17tnw2ay5jk): a host that keeps the
/// socket busy with frames that never answer the in-flight command must not leave
/// the phone dead. `act()` has to resolve as failed in bounded time, `busy` has
/// to clear, and the control has to work again once the session is re-established.
///
/// `test/models/session_command_deadline_test.dart` pins the deadline at the
/// `command()` level; this pins the consequence at the `LiveController` level
/// (every control, including the emergency strip's BLACKOUT, is gated on `busy`),
/// so a later change that awaits something unbounded before `_acting` is released
/// fails here even with every session-level test green.
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

const _opState = '{"event":"operator_state","view":{"plan_name":"Sunday",'
    '"items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null}}';

/// The operator host's side of one connection. Answers state reads normally;
/// answers a command with its ack, or — when [stalls] — with stale acks (request
/// id 0, always earlier than any real id) every 20ms and never the real one.
class _Host {
  _Host({this.stalls = false});

  final bool stalls;
  final out = StreamController<dynamic>();
  Timer? _noise;
  int _received = 0;
  int commandsApplied = 0;

  void onSend(String frame) {
    final id = ++_received;
    final isStateRead = frame.contains('get_operator_state');
    scheduleMicrotask(() {
      if (out.isClosed) return;
      if (isStateRead) {
        out.add(_opState);
        return;
      }
      commandsApplied++;
      if (stalls) {
        _noise = Timer.periodic(const Duration(milliseconds: 20),
            (_) => out.isClosed ? null : out.add('{"event":"ack","request_id":0}'));
      } else {
        out.add('{"event":"ack","request_id":$id}');
      }
    });
  }

  SelahSession session(Duration deadline) => SelahSession.forTest(
        send: onSend,
        incoming: StreamQueue(out.stream),
        role: 'producer',
        commandDeadline: deadline,
      );

  void stop() {
    _noise?.cancel();
    out.close();
  }
}

Future<void> _until(bool Function() cond, {Duration within = const Duration(seconds: 3)}) async {
  final end = Stopwatch()..start();
  while (!cond()) {
    if (end.elapsed > within) fail('condition not met within $within');
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
}

void main() {
  test('a stalled command resolves failed, clears busy, and BLACKOUT works after the reconnect',
      () async {
    const deadline = Duration(milliseconds: 300);
    final stalled = _Host(stalls: true);
    final healthy = _Host();
    var connects = 0;
    Future<ControllerSession> connect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async {
      connects++;
      return healthy.session(deadline);
    }

    final live = LiveController(
        session: stalled.session(deadline), stored: _stored, connect: connect);
    addTearDown(() {
      stalled.stop();
      healthy.stop();
      live.dispose();
    });
    await _until(() => !live.syncing);

    final started = Stopwatch()..start();
    final outcome = live.act(cmdBlackout(true));
    await _until(() => live.busy);
    expect(await outcome.timeout(const Duration(seconds: 5)), CommandOutcome.failed);
    expect(started.elapsed, lessThan(const Duration(seconds: 2)),
        reason: 'bounded by the per-command deadline, not by host liveness');
    expect(live.busy, isFalse, reason: 'no control may stay disabled by one stuck command');

    // The failure tears the session down and re-syncs on a fresh connection.
    await _until(() => connects == 1 && !live.syncing);
    expect(await live.act(cmdBlackout(true)).timeout(const Duration(seconds: 3)),
        CommandOutcome.applied);
    expect(healthy.commandsApplied, 1);
  });
}
