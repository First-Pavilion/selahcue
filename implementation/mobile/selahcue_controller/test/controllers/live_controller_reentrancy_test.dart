/// A burst of taps against a slow/dead host must never queue N commands, each
/// waiting up to `commandTimeout` behind the ones ahead of it on
/// `SelahSession._turn` — that makes the app look hung for tens of seconds
/// with no feedback, even though every queued command eventually resolves or
/// is superseded. `refresh()` already guards this shape with `_refreshing`;
/// `act()` had no equivalent, so a double-tap (misfire, or an impatient tap
/// against a slow link) queued a second command behind the first instead of
/// being rejected immediately.
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

/// Holds `command()` open until the test releases [gate], so a test can
/// observe controller state while a command is genuinely in flight.
class _GatingSession implements ControllerSession {
  _GatingSession(this.view);

  final OperatorStateView view;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  int commandCount = 0;
  final List<String> sent = [];

  /// Set by the test before sending a command it wants to hold in flight.
  Completer<void>? gate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    commandCount++;
    sent.add(cmd['cmd'] as String);
    final g = gate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;

  @override
  Future<void> close() async {}
}

OperatorStateView _emptyView() => const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );

const _stored = StoredSession(
  host: '10.0.0.2',
  port: 8443,
  pinHex: 'ab',
  deviceId: 'dev-1',
  token: 'tok-1',
);

Future<void> _synced(LiveController live) async {
  await pumpEventQueue();
  expect(live.syncing, isFalse,
      reason: 'precondition: the first operator-state fetch has landed');
}

void main() {
  test(
      'a second act() call while one is in flight is rejected immediately, not queued',
      () async {
    final session = _GatingSession(_emptyView());
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    // Hold the next command in flight so the test can tap again while it is
    // still outstanding.
    session.gate = Completer<void>();

    final first = live.act(cmdGoLive());
    await pumpEventQueue();
    expect(session.commandCount, 1,
        reason: 'baseline: the first command reached the host');

    // The second tap — must not queue behind the first.
    final secondOutcome = await live.act(cmdPrevious());
    expect(secondOutcome, CommandOutcome.failed,
        reason: 'a command already in flight must reject a new one outright');
    expect(session.commandCount, 1,
        reason: 'the second command must never reach the host while the '
            'first is still in flight — that would be a queued command, '
            'not a rejected one');
    expect(session.sent, ['go_live'],
        reason: 'previous must never have been sent');

    // Release the first command; it should still complete normally.
    session.gate!.complete();
    final firstOutcome = await first;
    expect(firstOutcome, CommandOutcome.applied);

    // Now that nothing is in flight, a third call must go through normally.
    final thirdOutcome = await live.act(cmdPrevious());
    expect(thirdOutcome, CommandOutcome.applied);
    expect(session.commandCount, 2);
  });

  test('LiveController.busy reflects whether a command is currently in flight',
      () async {
    final session = _GatingSession(_emptyView());
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    expect(live.busy, isFalse);

    session.gate = Completer<void>();
    final pending = live.act(cmdGoLive());
    await pumpEventQueue();
    expect(live.busy, isTrue);

    session.gate!.complete();
    await pending;
    expect(live.busy, isFalse);
  });
}
