/// Retired-session reads must not publish state or tear down a replacement
/// (17tnw2b0vtk). Keep the real SelahSession turn chain: a poll queued behind a
/// command must really wait its turn, including after that command fails.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

OperatorStateView _view(String name) => OperatorStateView(
      planName: name,
      items: const [
        PlanItemView(
            id: 7, kind: 'song', title: 'Song', isLive: false, isStaged: true),
      ],
      liveIndex: null,
      stagedIndex: 0,
      blackout: false,
      timer: null,
    );

/// Only the external host and close completion are controlled. Serialization,
/// request IDs, frame parsing and the controller are production implementations.
class _OldSession implements ControllerSession {
  final incoming = StreamController<dynamic>();
  final closeStarted = Completer<void>();
  final closeGate = Completer<void>();
  final commands = <String>[];
  int stateReads = 0;
  int lastActionId = 0;
  late final SelahSession transport = SelahSession.forTest(
    send: _send,
    incoming: StreamQueue(incoming.stream),
    role: 'producer',
  );

  void _send(String frame) {
    final request = jsonDecode(frame) as Map<String, dynamic>;
    final command = request['command'] as Map<String, dynamic>;
    final name = command['cmd'] as String;
    if (name == 'get_operator_state') {
      stateReads++;
      if (stateReads == 1) reply('initial');
    } else {
      commands.add(name);
      lastActionId = request['request_id'] as int;
    }
  }

  void reply(String name) => incoming.add(jsonEncode({
        'event': 'operator_state',
        'view': {
          'plan_name': name,
          'items': [
            {
              'id': 7,
              'kind': 'song',
              'title': 'Song',
              'is_live': false,
              'is_staged': true,
            },
          ],
          'live_index': null,
          'staged_index': 0,
          'blackout': false,
          'timer': null,
        },
      }));

  void acknowledgeAction() => incoming
      .add(jsonEncode({'event': 'ack', 'request_id': lastActionId}));

  // A malformed frame fails this round trip with SessionException but keeps
  // the transport open, just as a command timeout permits late host frames.
  // A stream error would mark StreamQueue done and could not model that window.
  void failRead() => incoming.add('not-json');

  @override
  MobileRole get grantedRole => transport.grantedRole;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) =>
      transport.command(cmd);

  @override
  Future<OperatorStateView> operatorState() => transport.operatorState();

  @override
  Future<void> close() {
    if (!closeStarted.isCompleted) closeStarted.complete();
    return closeGate.future;
  }
}

/// A newly authenticated host whose first snapshot is independently releasable.
class _Replacement implements ControllerSession {
  final readGate = Completer<void>();
  final commands = <String>[];
  int stateReads = 0;
  int closeCount = 0;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    commands.add(cmd['cmd'] as String);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    stateReads++;
    await readGate.future;
    return _view('replacement');
  }

  @override
  Future<void> close() async => closeCount++;
}

class _Fixture {
  final old = _OldSession();
  final replacement = _Replacement();
  late final LiveController live;
  int connects = 0;

  _Fixture() {
    live = LiveController(
      session: old,
      stored: _stored,
      connect: ({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async {
        connects++;
        return replacement;
      },
    );
    addTearDown(() async {
      live.dispose();
      if (!old.closeGate.isCompleted) old.closeGate.complete();
      if (!replacement.readGate.isCompleted) replacement.readGate.complete();
      await old.incoming.close();
      await pumpEventQueue();
    });
  }

  Future<void> sync() async {
    await pumpEventQueue();
    expect(live.syncing, isFalse, reason: 'initial snapshot must be real');
    expect(live.view?.planName, 'initial');
  }

  Future<(Future<CommandOutcome>, Future<void>)> failedActionAndPoll() async {
    final action = live.act(cmdBlackout(true));
    await pumpEventQueue();
    expect(old.commands, ['blackout']);
    final poll = live.refresh();
    await pumpEventQueue();
    expect(old.stateReads, 1,
        reason: 'poll is queued behind the real in-flight command');
    old.failRead();
    await pumpEventQueue();
    expect(old.closeStarted.isCompleted, isTrue);
    expect(old.stateReads, 2,
        reason: 'queued old poll starts after the failed command turn');
    expect(live.rejected, isTrue);
    return (action, poll);
  }

  Future<(Future<void>, Future<void>)> confirmedReadAndFailedPoll() async {
    final gesture = live.selectAndGoLive(7);
    await pumpEventQueue();
    expect(old.commands, ['select_item']);
    // The poll is queued behind stage. Its in-flight claim coalesces the
    // command's trailing refresh, so _confirmedView queues its own later read.
    final poll = live.refresh();
    old.acknowledgeAction();
    await pumpEventQueue();
    expect(old.stateReads, 2);
    old.failRead();
    await pumpEventQueue();
    expect(old.closeStarted.isCompleted, isTrue);
    expect(old.stateReads, 3,
        reason: 'the public gesture has a confirming read on the old turn chain');
    return (gesture, poll);
  }
}

void main() {
  test('a same-session refresh still publishes its new snapshot', () async {
    final f = _Fixture();
    await f.sync();
    final poll = f.live.refresh();
    await pumpEventQueue();
    f.old.reply('same-session');
    await poll;
    expect(f.live.view?.planName, 'same-session');
    expect(f.live.syncing, isFalse);
    expect(f.live.error, isNull);
    expect(f.connects, 0);
  });

  test('an old poll reply during close cannot erase action rejection or status',
      () async {
    final f = _Fixture();
    await f.sync();
    final (_, poll) = await f.failedActionAndPoll();
    f.old.reply('forged-old');
    await poll;
    expect(f.live.view?.planName, 'initial');
    expect(f.live.rejected, isTrue);
    expect(f.live.error, contains('reconnecting'));
    expect(f.live.syncing, isTrue);
    expect(f.connects, 0, reason: 'old close is deliberately still pending');
  });

  test('an old poll failure after replacement cannot reconnect again', () async {
    final f = _Fixture();
    await f.sync();
    final (action, poll) = await f.failedActionAndPoll();
    f.old.closeGate.complete();
    expect(await action, CommandOutcome.failed);
    await pumpEventQueue();
    expect(f.connects, 1, reason: 'the replacement is installed');
    f.old.failRead();
    await poll;
    await pumpEventQueue();
    expect(f.connects, 1);
    expect(f.replacement.closeCount, 0,
        reason: 'a retired read cannot tear down the healthy replacement');
    expect(f.replacement.commands, isEmpty, reason: 'BLACKOUT is never replayed');
  });

  test('replacement resync finishes without waiting for the retired poll',
      () async {
    final f = _Fixture();
    await f.sync();
    final (action, poll) = await f.failedActionAndPoll();
    f.old.closeGate.complete();
    expect(await action, CommandOutcome.failed);
    await pumpEventQueue();
    expect(f.replacement.stateReads, 1,
        reason: 'old pending refresh must not coalesce replacement recovery');
    expect(f.live.syncing, isTrue, reason: 'replacement has not replied yet');
    f.replacement.readGate.complete();
    await pumpEventQueue();
    expect(f.live.view?.planName, 'replacement');
    expect(f.live.syncing, isFalse);
    expect(f.live.busy, isFalse);
    expect(f.live.rejected, isFalse);
    expect(f.live.error, isNull);
    // Only now release the old read: recovery above cannot depend on it.
    f.old.reply('forged-late');
    await poll;
    expect(f.live.view?.planName, 'replacement');
    expect(f.connects, 1);
  });

  test('a retired confirming reply during close cannot replace the snapshot',
      () async {
    final f = _Fixture();
    await f.sync();
    final (gesture, _) = await f.confirmedReadAndFailedPoll();
    f.old.reply('forged-confirmation');
    await gesture;
    expect(f.live.view?.planName, 'initial');
    expect(f.live.error, contains('reconnecting'));
    expect(f.live.syncing, isTrue);
    expect(f.old.commands, ['select_item'], reason: 'no unproven go-live');
    expect(f.replacement.commands, isEmpty);
  });

  test('a retired confirming failure cannot reconnect the replacement', () async {
    final f = _Fixture();
    await f.sync();
    final (gesture, poll) = await f.confirmedReadAndFailedPoll();
    f.old.closeGate.complete();
    await poll;
    await pumpEventQueue();
    expect(f.connects, 1);
    f.old.failRead();
    await gesture;
    await pumpEventQueue();
    expect(f.connects, 1);
    expect(f.replacement.closeCount, 0);
    expect(f.old.commands, ['select_item']);
    expect(f.replacement.commands, isEmpty, reason: 'no cross-session go-live');
  });
}
