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

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final OperatorStateView view;
  final List<Map<String, dynamic>> sent = [];
  _Fake(this.grantedRole, this.view);

  /// When set, `command()` parks on this until the test completes it — lets a
  /// test dispatch a SECOND tap while the first command is genuinely still
  /// in flight, rather than after it has already round-tripped (this fake's
  /// default `Ack` resolves on the next microtask, too fast to reproduce a
  /// real double-tap race without a gate).
  Completer<void>? gate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    final g = gate;
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
    fake.gate = Completer<void>();
    final live = await _pump(tester, fake);
    final button = find.textContaining('TIME UP" to stage');
    // `tester.tap` returns once the pointer-event dispatch is done, not once
    // the (now-gated) async command resolves — so this does not hang.
    await tester.tap(button);
    await tester.tap(button);
    fake.gate!.complete();
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
}
