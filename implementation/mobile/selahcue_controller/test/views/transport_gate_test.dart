/// Transport + plan controls are disabled while the controller cannot prove
/// what is on the audience screen (86ajxx4x8 / FR-097, COMPONENT-SPECS §12:
/// "On disconnect, controls disable immediately… on reconnect, live state
/// re-syncs before controls re-enable and queued stale taps are discarded").
///
/// Role gating stays hide-not-disable; this gate is disable-not-hide, because
/// the control still exists — it is momentarily untrustworthy, not forbidden.
///
/// The gate was first written per-screen, and per-screen it was only ever three
/// of five surfaces: Scripture and Timer never got it, so a verse tap staged on
/// the host and a ±1:00 tap moved a timer the device could not see. It now lives
/// in [LiveController.act], which is the only place every screen must pass
/// through. The per-tab tests below exist so the NEXT screen to forget it fails
/// here instead of shipping.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/widgets/primitives.dart';
import 'package:selahcue_controller/views/tabs/live_tab.dart';
import 'package:selahcue_controller/views/tabs/plan_tab.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';
import 'package:selahcue_controller/views/tabs/timer_tab.dart';

class _Fake implements ControllerSession {
  _Fake({List<String>? sent, this.timer, this.stagedScripture})
      : sent = sent ?? <String>[];

  /// Shared across the dropped session and its replacement, so a test can assert
  /// that a tap reached NEITHER.
  final List<String> sent;

  /// Seeded into the operator view so the Timer tab's adjust/stop controls are
  /// enabled on their own terms — otherwise they are already inert for want of a
  /// timer and the gate under test proves nothing.
  final TimerSnapshot? timer;

  /// Seeded so the Scripture tab preloads a chapter at mount and has real verse
  /// rows to tap after the drop.
  final String? stagedScripture;

  bool dead = false;

  /// When set, the state fetch parks — the socket is back but the re-sync has
  /// not landed, which is precisely the window controls must stay disabled for.
  Completer<void>? gate;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    final name = cmd['cmd'] as String;
    sent.add(name);
    // `get_chapter` is a READ. It does not go through act() and is deliberately
    // still allowed while syncing — browsing scripture changes nothing on the
    // audience screen, and taking the browser away during a blip would be a
    // regression, not a safety win.
    if (name == 'get_chapter') {
      return const ChapterResult(
        bookName: 'John',
        chapter: 3,
        translation: 'KJV',
        verses: [VerseView(16, 'For God so loved the world')],
      );
    }
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('down');
    final g = gate;
    if (g != null) await g.future;
    return OperatorStateView(
      planName: 'Sunday',
      items: const [
        PlanItemView(
            id: 1,
            kind: 'song',
            title: 'Amazing Grace',
            isLive: false,
            isStaged: false),
      ],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: timer,
      stagedScripture: stagedScripture,
      detections: const [
        DetectionView(
            id: 7, reference: 'John 3:16', text: 'heard', translation: 'KJV'),
      ],
    );
  }

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

const _runningTimer = TimerSnapshot(
    remainingSecs: 300,
    elapsedSecs: 0,
    timeUp: false,
    warn: false,
    running: true);

/// Brings the controller up healthy (so a view exists), then drops the link and
/// reconnects onto a session whose first state fetch is still in flight. That is
/// the exact state the story is about: socket back, truth not yet re-read.
Future<(LiveController, List<String>)> _droppedMidService(
  WidgetTester tester,
  Widget Function(LiveController) child, {
  _Fake Function(List<String> sent)? session,
}) async {
  final sent = <String>[];
  _Fake make() => session?.call(sent) ?? _Fake(sent: sent);
  final original = make();
  final replacement = make()..gate = Completer<void>();

  final live = LiveController(
    session: original,
    stored: _stored,
    connect: ({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        replacement,
  );
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListenableBuilder(
        listenable: live,
        builder: (_, _) => child(live),
      ),
    ),
  ));
  await tester.pump(const Duration(milliseconds: 60));
  expect(live.syncing, isFalse, reason: 'baseline: healthy link, view loaded');

  original.dead = true;
  await live.refresh();
  await tester.pump(const Duration(milliseconds: 60));
  expect(live.reconnecting, isFalse, reason: 'baseline: the socket came back');
  expect(live.syncing, isTrue,
      reason: 'baseline: but the host has not been re-read yet');

  sent.clear();
  return (live, sent);
}

void main() {
  testWidgets('GO LIVE does nothing while the link is syncing', (tester) async {
    final (live, sent) =
        await _droppedMidService(tester, (l) => LiveTab(live: l));

    await tester.tap(find.text('GO LIVE'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(sent, isEmpty,
        reason: 'a tap into an unsynced link must not be sent — and must not be '
            'queued for replay when the re-sync lands');
    live.dispose();
  });

  testWidgets('the transport row is visibly disabled while syncing',
      (tester) async {
    final handle = tester.ensureSemantics();
    final (live, _) =
        await _droppedMidService(tester, (l) => LiveTab(live: l));

    // Present but not forbidden — greyed and announced, never hidden.
    expect(find.text('GO LIVE'), findsOneWidget);
    expect(find.bySemanticsLabel('Go live, unavailable while reconnecting'),
        findsOneWidget);
    expect(find.bySemanticsLabel('Next item, unavailable while reconnecting'),
        findsOneWidget);

    handle.dispose();
    live.dispose();
  });

  testWidgets('plan items are not stageable while syncing', (tester) async {
    final (live, sent) =
        await _droppedMidService(tester, (l) => PlanTab(live: l));

    await tester.tap(find.text('Amazing Grace'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(sent, isEmpty,
        reason: 'staging into an unknown host state is exactly the tap that '
            'later goes live on a stale premise');
    expect(find.textContaining('Syncing live state'), findsOneWidget,
        reason: 'the operator is told why the list went inert');
    live.dispose();
  });

  // --- the gate as a property of the controller, not of the screens ----------

  testWidgets('every command is refused while syncing, whoever sends it',
      (tester) async {
    final (live, sent) =
        await _droppedMidService(tester, (l) => const SizedBox.shrink());

    // The three commands a screen used to be able to slip through, plus one
    // whose ARGUMENT is read from the stale view: `approve_detection` carries a
    // detection id taken from a snapshot that predates the drop.
    final outcomes = <String, CommandOutcome>{
      'stage_scripture': await live.act(cmdStageScripture('John 3:16')),
      'adjust_timer': await live.act(cmdAdjustTimer(60)),
      'start_timer': await live.act(cmdStartTimer(300)),
      'approve_detection': await live.act(cmdApproveDetection(7)),
    };

    for (final entry in outcomes.entries) {
      expect(entry.value, isNot(CommandOutcome.applied),
          reason: '${entry.key} must not report applied against a view the '
              'device cannot prove is current');
    }
    expect(sent, isEmpty,
        reason: 'and none of them may reach the host at all');
    live.dispose();
  });

  // --- Timer tab -------------------------------------------------------------

  testWidgets('timer controls do nothing while syncing', (tester) async {
    final (live, sent) = await _droppedMidService(
      tester,
      (l) => TimerTab(live: l),
      session: (sent) => _Fake(sent: sent, timer: _runningTimer),
    );

    await tester.tap(find.text('+ 1:00'));
    await tester.tap(find.text('− 1:00'));
    await tester.tap(find.widgetWithText(SelahButton, '5:00'));
    await tester.tap(find.widgetWithText(SelahButton, 'Stop'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(sent, isEmpty,
        reason: 'a timer nudge against a countdown this device cannot see is '
            'the same stale-premise tap as staging one');
    live.dispose();
  });

  testWidgets('timer controls are visibly disabled while syncing',
      (tester) async {
    final (live, _) = await _droppedMidService(
      tester,
      (l) => TimerTab(live: l),
      session: (sent) => _Fake(sent: sent, timer: _runningTimer),
    );

    // Disabled, not hidden — the control is untrustworthy, not forbidden.
    for (final label in ['+ 1:00', '− 1:00', '5:00', 'Stop', 'Pause']) {
      expect(find.widgetWithText(SelahButton, label), findsOneWidget,
          reason: '$label stays on screen');
      final button =
          tester.widget<SelahButton>(find.widgetWithText(SelahButton, label));
      expect(button.onPressed, isNull, reason: '$label must not be tappable');
    }
    live.dispose();
  });

  // --- Scripture tab ---------------------------------------------------------

  testWidgets('scripture verses are not stageable while syncing',
      (tester) async {
    final (live, sent) = await _droppedMidService(
      tester,
      (l) => ScriptureTab(live: l),
      session: (sent) => _Fake(sent: sent, stagedScripture: 'John 3:16'),
    );

    expect(find.textContaining('For God so loved'), findsOneWidget,
        reason: 'the chapter loaded before the drop and stays browsable');

    await tester.tap(find.textContaining('For God so loved'));
    // Past kDoubleTapTimeout: a verse row carries onDoubleTap, so its onTap only
    // resolves once the arena gives up waiting for a second tap. Pumping less
    // than that passes against an ungated tab for the wrong reason.
    await tester.pump(const Duration(milliseconds: 500));

    expect(sent, isEmpty,
        reason: 'staging a verse into an unknown host state is exactly the tap '
            'that later goes live on a stale premise (plan_tab.dart:26-27)');
    live.dispose();
  });

  testWidgets('a verse double-tap does not go live while syncing',
      (tester) async {
    final (live, sent) = await _droppedMidService(
      tester,
      (l) => ScriptureTab(live: l),
      session: (sent) => _Fake(sent: sent, stagedScripture: 'John 3:16'),
    );

    final verse = find.textContaining('For God so loved');
    await tester.tap(verse);
    await tester.tap(verse);
    await tester.pump(const Duration(milliseconds: 500));

    expect(sent, isEmpty,
        reason: 'the compound gesture must stop at its first half, which is '
            'exactly what act() refusing gives it');
    live.dispose();
  });
}
