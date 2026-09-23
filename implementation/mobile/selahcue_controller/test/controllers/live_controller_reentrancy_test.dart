/// A burst of taps against a slow/dead host must never queue N commands, each
/// waiting up to `commandTimeout` behind the ones ahead of it on
/// `SelahSession._turn` — that makes the app look hung for tens of seconds
/// with no feedback, even though every queued command eventually resolves or
/// is superseded. `refresh()` already guards this shape with `_refreshing`;
/// `act()` had no equivalent, so a double-tap (misfire, or an impatient tap
/// against a slow link) queued a second command behind the first instead of
/// being rejected immediately (17tnw2ay2kk).
///
/// That fix closed the gap for a BARE `act()` call, but review of it found the
/// same gap still open one level up: `selectAndGoLive` and
/// `stageScriptureAndGoLive` each send two commands with a state read
/// (`_confirmedView`) between them, and used to release the guard as soon as
/// their FIRST command settled — leaving the window around the read, and
/// their own second command, unguarded. A tap landing there queued its own
/// turn and could reach the host BETWEEN the gesture's two commands. This
/// file's later tests cover that compound-gesture case.
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

  /// When true, the next `command()` throws instead of returning — a socket
  /// blip mid-command.
  bool throwOnCommand = false;

  /// Set by the test to hold `operatorState()` (the [_confirmedView] read
  /// inside a compound gesture) open, so it can observe/act while a gesture
  /// is between its two commands rather than only while its first command is
  /// still on the wire.
  Completer<void>? operatorStateGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    commandCount++;
    sent.add(cmd['cmd'] as String);
    if (throwOnCommand) {
      throwOnCommand = false;
      throw const SessionException('socket blip');
    }
    final g = gate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    final g = operatorStateGate;
    if (g != null) await g.future;
    return view;
  }

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

const _planItemId = 7;

/// A one-item plan; `staged` picks whether the host reports that item as
/// staged in Preview — the condition [LiveController.selectAndGoLive]'s
/// second (go-live) command is gated on.
OperatorStateView _planView({required bool staged}) => OperatorStateView(
      planName: 'Sunday',
      items: const [
        PlanItemView(
          id: _planItemId,
          kind: 'song',
          title: 'Amazing Grace',
          isLive: false,
          isStaged: false,
        ),
      ],
      liveIndex: null,
      stagedIndex: staged ? 0 : null,
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

    // The second tap — must not queue behind the first. Bounded by an
    // explicit timeout: without the guard this call would await the same
    // unreleased gate as the first, and a bare `await` would fail this test
    // by hanging until the suite's own timeout rather than with a clear
    // assertion.
    final secondOutcome =
        await live.act(cmdPrevious()).timeout(const Duration(seconds: 2));
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

  test(
      'a command lost to a socket blip clears _acting so a later command is not blocked',
      () async {
    final session = _GatingSession(_emptyView());
    final healthy = _GatingSession(_emptyView());
    Future<ControllerSession> reconnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        healthy;
    final live =
        LiveController(session: session, stored: _stored, connect: reconnect);
    addTearDown(live.dispose);
    await _synced(live);

    session.throwOnCommand = true;
    final outcome = await live.act(cmdGoLive());
    expect(outcome, CommandOutcome.failed);
    expect(live.busy, isFalse,
        reason: '_acting must be cleared by the finally block even when '
            'the command throws, not just on the success path');

    // Let the reconnect (triggered by the thrown SessionException) land.
    await pumpEventQueue();

    final second = await live.act(cmdPrevious());
    expect(second, CommandOutcome.applied,
        reason: 'a later command must not be permanently blocked by the '
            'earlier failure');
  });

  test(
      'a listener reacting synchronously to the in-flight notification cannot slip a second command past the guard',
      () async {
    final session = _GatingSession(_emptyView());
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    session.gate = Completer<void>();
    CommandOutcome? reentrantOutcome;
    // act() must publish `busy` (via `_notify()`) before it does anything
    // else that could re-enter act() — otherwise a listener reacting to that
    // very notification could slip a second command in before the guard is
    // actually up (this was a real race: `_syncRole()`'s own `_notify()`
    // used to fire before `_acting` was set).
    void listener() {
      if (live.busy && reentrantOutcome == null) {
        live.act(cmdPrevious()).then((o) => reentrantOutcome = o);
      }
    }

    live.addListener(listener);
    addTearDown(() => live.removeListener(listener));

    final first = live.act(cmdGoLive());
    await pumpEventQueue();

    expect(reentrantOutcome, CommandOutcome.failed,
        reason: 'the reentrant call must be rejected outright, not queued');
    expect(session.sent, ['go_live'],
        reason: 'the reentrant command must never have reached the host');

    session.gate!.complete();
    await first;
  });

  test(
      'a second act() cannot interleave its command between selectAndGoLive\'s '
      'stage and its own go-live', () async {
    // Reproduces the gap review found: `act()`'s own `_acting` guard closed
    // reentrancy for a BARE double-tap (17tnw2ay2kk), but `selectAndGoLive`
    // used to release `_acting` as soon as its first command (`select_item`)
    // settled — leaving the window around its `_confirmedView` read, and its
    // own second command (`go_live`), completely unguarded. A tap landing in
    // that window queued its own turn on `SelahSession._turn` and could reach
    // the host BETWEEN the gesture's two commands.
    final session = _GatingSession(_planView(staged: true));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    // Hold the confirming state-read open so the test can act while
    // selectAndGoLive is between its two commands.
    session.operatorStateGate = Completer<void>();

    final gesture = live.selectAndGoLive(_planItemId);
    await pumpEventQueue();
    expect(session.sent, ['select_item'],
        reason: 'baseline: the stage command reached the host and settled');
    expect(live.busy, isTrue,
        reason: 'the WHOLE gesture must read as busy, not just its first '
            'command — otherwise a screen gating controls on `busy` would '
            'wrongly re-enable them mid-gesture');

    // The interloper — must not queue behind the gesture's own commands.
    // Bounded by an explicit timeout: without the fix this call would await
    // the same unreleased gate the gesture's next command is waiting behind.
    final interloperOutcome =
        await live.act(cmdGoLive()).timeout(const Duration(seconds: 2));
    expect(interloperOutcome, CommandOutcome.failed,
        reason: 'a command must be rejected outright while a compound '
            'gesture holds `_acting`, not queued behind it');
    expect(session.sent, ['select_item'],
        reason: 'the interloper must never reach the host while the '
            'gesture is still between its own two commands');

    // Release the confirming read; the gesture completes on its own.
    session.operatorStateGate!.complete();
    await gesture;

    expect(session.sent, ['select_item', 'go_live'],
        reason: 'the gesture\'s two commands must land in order with '
            'nothing interleaved between them');
    expect(live.busy, isFalse);

    // Now that nothing is in flight, a fresh command goes through normally.
    final after = await live.act(cmdPrevious());
    expect(after, CommandOutcome.applied);
  });

  test(
      'a second selectAndGoLive cannot interleave with a stageScriptureAndGoLive '
      'already in flight', () async {
    final session = _GatingSession(_planView(staged: true));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    session.operatorStateGate = Completer<void>();
    final gesture = live.stageScriptureAndGoLive('Romans 8:28');
    await pumpEventQueue();
    expect(session.sent, ['stage_scripture']);
    expect(live.busy, isTrue);

    // A second compound gesture, not just a bare act() — the same guard must
    // reject it too. The guard check is synchronous (before any await), so
    // this resolves immediately; the timeout is a clean-failure backstop in
    // case a regression makes it queue instead.
    await live.selectAndGoLive(_planItemId).timeout(const Duration(seconds: 2));
    expect(session.sent, ['stage_scripture'],
        reason: 'the second gesture must never send its own command while '
            'the first is still in flight');

    session.operatorStateGate!.complete();
    await gesture;
    expect(session.sent, ['stage_scripture'],
        reason: 'stageScriptureAndGoLive\'s go-live half only fires when '
            'the confirmed view reports the SAME reference staged — this '
            'fake\'s fixed view has no stagedScripture set, so it correctly '
            'does not fire; the point of this test is the absence of an '
            'interleaved command, not this particular outcome');
  });

  test(
      'busy publishes its falling edge immediately, not only on the next poll tick',
      () async {
    final session = _GatingSession(_emptyView());
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await _synced(live);

    var sawFalseWhileNotified = false;
    void listener() {
      if (!live.busy) sawFalseWhileNotified = true;
    }

    live.addListener(listener);
    addTearDown(() => live.removeListener(listener));

    session.gate = Completer<void>();
    final pending = live.act(cmdGoLive());
    await pumpEventQueue();
    expect(live.busy, isTrue);

    session.gate!.complete();
    // If act() completing means its finally block has already run, this
    // await returns only after `_acting` is cleared. A missing `_notify()`
    // on that edge would leave `sawFalseWhileNotified` false here — nothing
    // would tell a listener until the next 1s poll tick.
    await pending;

    expect(sawFalseWhileNotified, isTrue,
        reason: 'a screen gating its controls on `busy` must see it clear '
            'as soon as the command settles, not up to a second later on '
            'the next poll tick');
  });
}
