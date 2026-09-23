/// Timer controls are role-gated (Timer capability); the readout stays for all.
/// Pause↔Resume toggles on `TimerSnapshot.running`. Reset and Send "TIME UP" to
/// stage (MOB-009) compose the EXISTING `start_timer`/`adjust_timer` commands —
/// see `timer_tab.dart`'s doc comment.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/timer_tab.dart';
import 'package:selahcue_controller/views/widgets/custom_time_well.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final OperatorStateView view;
  final List<Map<String, dynamic>> sent = [];
  _Fake(this.grantedRole, this.view);

  /// When set, `command()` parks before replying — a command reached the
  /// host but its acknowledgement hasn't landed yet, letting a test dispatch
  /// a SECOND tap while the first is genuinely still in flight rather than
  /// after it has already round-tripped (this fake's default immediate `Ack`
  /// resolves on the next microtask, too fast to reproduce a real double-tap
  /// race without a gate).
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    final g = commandGate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

OperatorStateView _viewWith(TimerSnapshot? t) => OperatorStateView(
      planName: 'S',
      items: const [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: t,
    );

Future<LiveController> _pump(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester
      .pumpWidget(MaterialApp(home: Scaffold(body: TimerTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

/// Same, but rebuilt on every controller notification — i.e. on every 1s
/// poll and every `busy` edge, the way `ControllerView` really hosts the tab.
Future<LiveController> _pumpPolled(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListenableBuilder(
        listenable: live,
        builder: (_, _) => TimerTab(live: live),
      ),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Producer with a running timer sees Pause; taps it',
      (tester) async {
    const running = TimerSnapshot(
        remainingSecs: 120,
        elapsedSecs: 60,
        timeUp: false,
        warn: false,
        running: true);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pump(tester, fake);
    expect(find.text('Pause'), findsOneWidget);
    await tester.tap(find.text('Pause'));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'pause_timer'), isTrue);
    live.dispose();
  });

  testWidgets('Producer with a paused timer sees Resume', (tester) async {
    const paused = TimerSnapshot(
        remainingSecs: 120,
        elapsedSecs: 60,
        timeUp: false,
        warn: false,
        running: false);
    final live = await _pump(tester, _Fake(MobileRole.producer, _viewWith(paused)));
    expect(find.text('Resume'), findsOneWidget);
    live.dispose();
  });

  testWidgets('Viewer sees the readout but no timer controls', (tester) async {
    final live = await _pump(tester, _Fake(MobileRole.viewer, _viewWith(null)));
    expect(find.text('Start'), findsNothing);
    expect(find.text('Stop'), findsNothing);
    expect(find.text('SERVICE TIMER'), findsOneWidget); // readout kept
    live.dispose();
  });

  testWidgets(
      'Producer taps Reset — restarts from totalSecs via start_timer (MOB-009)',
      (tester) async {
    // remaining(45) + elapsed(255) = 300, same as totalSecs here on purpose —
    // the assertion below still pins totalSecs as the SOURCE, not the sum.
    const running = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pump(tester, fake);
    expect(find.text('Reset'), findsOneWidget);
    await tester.tap(find.text('Reset'));
    await tester.pump();
    final sent = fake.sent.singleWhere((c) => c['cmd'] == 'start_timer');
    expect(sent['seconds'], 300);
    live.dispose();
  });

  testWidgets(
      'Reset still works from a TIME UP snapshot — the core restart-after-overrun case (QA review gap)',
      (tester) async {
    // `canAdjust` (which gates Reset) does not depend on `t.timeUp` — Reset
    // must keep working once the countdown has overrun, since "restart the
    // service timer after it ran out" is the scenario this control exists for.
    const overrun = TimerSnapshot(
        remainingSecs: 0,
        elapsedSecs: 320,
        timeUp: true,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(overrun));
    final live = await _pump(tester, fake);
    final resetButton = find.text('Reset');
    expect(resetButton, findsOneWidget);
    await tester.tap(resetButton);
    await tester.pump();
    final sent = fake.sent.singleWhere((c) => c['cmd'] == 'start_timer');
    expect(sent['seconds'], 300);
    live.dispose();
  });

  testWidgets(
      'Reset falls back to remaining+elapsed when a host predates totalSecs (MOB-009)',
      (tester) async {
    const noTotal = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true); // totalSecs omitted
    final fake = _Fake(MobileRole.producer, _viewWith(noTotal));
    final live = await _pump(tester, fake);
    await tester.tap(find.text('Reset'));
    await tester.pump();
    final sent = fake.sent.singleWhere((c) => c['cmd'] == 'start_timer');
    expect(sent['seconds'], 300); // 45 + 255
    live.dispose();
  });

  testWidgets(
      'Producer taps Send "TIME UP" to stage — zeroes remaining via adjust_timer (MOB-009)',
      (tester) async {
    const running = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pump(tester, fake);
    final button = find.textContaining('TIME UP" to stage');
    expect(button, findsOneWidget);
    await tester.tap(button);
    await tester.pump();
    final sent = fake.sent.singleWhere((c) => c['cmd'] == 'adjust_timer');
    expect(sent['delta_secs'], -45);
    live.dispose();
  });

  testWidgets(
      'Send "TIME UP" to stage is disabled once already at time up (MOB-009)',
      (tester) async {
    const timeUp = TimerSnapshot(
        remainingSecs: 0,
        elapsedSecs: 320,
        timeUp: true,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(timeUp));
    final live = await _pump(tester, fake);
    await tester.tap(find.textContaining('TIME UP" to stage'));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'adjust_timer'), isFalse);
    live.dispose();
  });

  testWidgets(
      'Double-tapping Send "TIME UP" to stage sends adjust_timer only once (PR #78 review fix)',
      (tester) async {
    // Both taps read the SAME stale `remainingSecs` (45) before the first
    // command's Ack can update the synced view. Without the in-flight guard,
    // the second tap would compound a second `-45` onto an already-reduced
    // total, driving `totalSecs` toward 0 and leaving Reset nothing to
    // restart to (Sana, PR #78 review).
    const running = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    // Gate the first command in flight, so the second tap genuinely lands
    // before it resolves — the fake's default immediate `Ack` round-trips too
    // fast (within one microtask) to reproduce a real double-tap race.
    fake.commandGate = Completer<void>();
    final live = await _pump(tester, fake);
    final button = find.textContaining('TIME UP" to stage');
    // `tester.tap` returns once the pointer-event dispatch is done, not once
    // the (now-gated) async command resolves — so this does not hang.
    await tester.tap(button);
    await tester.tap(button);
    fake.commandGate!.complete();
    await tester.pump();
    final adjustCmds =
        fake.sent.where((c) => c['cmd'] == 'adjust_timer').toList();
    expect(adjustCmds, hasLength(1),
        reason: 'the second tap must be swallowed by the in-flight guard');
    expect(adjustCmds.single['delta_secs'], -45);
    live.dispose();
  });

  testWidgets(
      'Reset and Send "TIME UP" to stage stay hidden for a Viewer (no Timer capability)',
      (tester) async {
    final live = await _pump(tester, _Fake(MobileRole.viewer, _viewWith(null)));
    expect(find.text('Reset'), findsNothing);
    expect(find.textContaining('TIME UP" to stage'), findsNothing);
    live.dispose();
  });

  testWidgets(
      'Send "TIME UP" to stage announces its caption to assistive tech (PR #78 review, Cody)',
      (tester) async {
    // `_SendTimeUpButton` sets `excludeSemantics: true` so its own Semantics
    // node replaces BOTH child Texts' announcements — the caption "stage
    // display only — never audience" must be folded into that one label, or a
    // screen-reader user never hears it even though sighted users see it.
    final handle = tester.ensureSemantics();
    const running = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true,
        totalSecs: 300);
    final live =
        await _pump(tester, _Fake(MobileRole.producer, _viewWith(running)));
    expect(find.bySemanticsLabel(RegExp('stage display only')), findsOneWidget,
        reason: 'the caption must reach the accessibility tree, not just the '
            'visible Text');
    live.dispose();
    handle.dispose();
  });

  testWidgets(
      'Stop/Pause/Adjust announce "no timer running" when that is the actual '
      'reason, not "sending…" or "unavailable while reconnecting"',
      (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, _Fake(MobileRole.producer, _viewWith(null)));
    // Neither syncing nor busy — the only reason these are disabled is that
    // no timer exists yet (17tnw2ay2pq review: Cody + Sana).
    expect(live.syncing, isFalse);
    expect(live.busy, isFalse);

    expect(find.bySemanticsLabel('Resume, no timer running'), findsOneWidget);
    expect(find.bySemanticsLabel('Stop, no timer running'), findsOneWidget);
    expect(find.bySemanticsLabel('Subtract one minute, no timer running'),
        findsOneWidget);
    expect(
        find.bySemanticsLabel('Add one minute, no timer running'), findsOneWidget);

    handle.dispose();
    live.dispose();
  });

  testWidgets(
      'the preset and Pause controls are disabled while a command is in flight',
      (tester) async {
    final handle = tester.ensureSemantics();
    const running = TimerSnapshot(
        remainingSecs: 120,
        elapsedSecs: 60,
        timeUp: false,
        warn: false,
        running: true);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pumpPolled(tester, fake);
    expect(live.busy, isFalse, reason: 'baseline');

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('Pause'));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'pause_timer is now in flight');
    expect(find.bySemanticsLabel('Pause, sending…'), findsOneWidget,
        reason: '17tnw2ay2pq, follow-up to 17tnw2ay2kk');
    expect(
        find.bySemanticsLabel('Start a five minute timer, sending…'),
        findsOneWidget,
        reason: 'every control gated the same way must disable together');

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    expect(find.bySemanticsLabel('Pause'), findsOneWidget);

    handle.dispose();
    live.dispose();
  });

  testWidgets(
      'the custom-time well and Start are disabled while a command is in '
      'flight, and cannot fire the same duration twice',
      (tester) async {
    final fake = _Fake(MobileRole.producer, _viewWith(null));
    final live = await _pumpPolled(tester, fake);

    await tester.enterText(find.byType(TextField).last, '5');
    await tester.pump();

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('Start'));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'start_timer is now in flight');
    expect(fake.sent.where((c) => c['cmd'] == 'start_timer').length, 1);
    final well = tester.widget<CustomTimeWell>(find.byType(CustomTimeWell));
    expect(well.enabled, isFalse,
        reason: 'the well must grey out while a command is in flight, not '
            'just while syncing');

    // A second tap while busy — with the controller-level guard as the only
    // remaining protection (the old local `_starting` flag was removed as
    // redundant once `act()` itself guards re-entrancy) — must not queue or
    // duplicate the start.
    await tester.tap(find.text('Start'));
    await tester.pump();
    expect(fake.sent.where((c) => c['cmd'] == 'start_timer').length, 1,
        reason: 'a second start must never reach the host while the first '
            'is still in flight');

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);

    live.dispose();
  });

  testWidgets(
      'a burst of taps on Start with no frame between them still sends '
      'exactly one start_timer', (tester) async {
    // The tightest version of the race the removed local `_starting` guard
    // used to protect against: the widget tree has not yet rebuilt to
    // reflect `busy`, so if anything here still relied on a RENDERED
    // disabled state (rather than act()'s own synchronous guard) to prevent
    // a duplicate dispatch, this would catch it. 17tnw2ay2pq review (Vera,
    // Quinn) each independently verified this by hand; this makes it a
    // permanent regression test.
    final fake = _Fake(MobileRole.producer, _viewWith(null));
    final live = await _pumpPolled(tester, fake);

    await tester.enterText(find.byType(TextField).last, '5');
    await tester.pump();

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('Start'));
    await tester.tap(find.text('Start'));
    await tester.tap(find.text('Start'));
    await tester.pump();

    expect(fake.sent.where((c) => c['cmd'] == 'start_timer').length, 1);

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    live.dispose();
  });

  testWidgets(
      'Reset and Send "TIME UP" to stage are also disabled while a command '
      'is in flight (17tnw2ay2pq, rebased onto MOB-009)', (tester) async {
    final handle = tester.ensureSemantics();
    const running = TimerSnapshot(
        remainingSecs: 45,
        elapsedSecs: 255,
        timeUp: false,
        warn: false,
        running: true,
        totalSecs: 300);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pumpPolled(tester, fake);
    expect(live.busy, isFalse, reason: 'baseline');

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('Pause'));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'pause_timer is now in flight');
    expect(find.bySemanticsLabel('Reset to the current target duration, sending…'),
        findsOneWidget,
        reason: 'Reset must disable together with every other control gated '
            'the same way, not just the one that was tapped');
    expect(
        find.bySemanticsLabel(
            'Send "TIME UP" to stage. stage display only — never audience. sending…'),
        findsOneWidget);

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    expect(find.text('Reset'), findsOneWidget);

    handle.dispose();
    live.dispose();
  });
}
