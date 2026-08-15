/// Transport + plan controls are disabled while the controller cannot prove
/// what is on the audience screen (86ajxx4x8 / FR-097, COMPONENT-SPECS §12:
/// "On disconnect, controls disable immediately… on reconnect, live state
/// re-syncs before controls re-enable and queued stale taps are discarded").
///
/// Role gating stays hide-not-disable; this gate is disable-not-hide, because
/// the control still exists — it is momentarily untrustworthy, not forbidden.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/live_tab.dart';
import 'package:selahcue_controller/views/tabs/plan_tab.dart';

class _Fake implements ControllerSession {
  _Fake({List<String>? sent}) : sent = sent ?? <String>[];

  /// Shared across the dropped session and its replacement, so a test can assert
  /// that a tap reached NEITHER.
  final List<String> sent;

  bool dead = false;

  /// When set, the state fetch parks — the socket is back but the re-sync has
  /// not landed, which is precisely the window controls must stay disabled for.
  Completer<void>? gate;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    sent.add(cmd['cmd'] as String);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('down');
    final g = gate;
    if (g != null) await g.future;
    return const OperatorStateView(
      planName: 'Sunday',
      items: [
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
      timer: null,
    );
  }

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

/// Brings the controller up healthy (so a view exists), then drops the link and
/// reconnects onto a session whose first state fetch is still in flight. That is
/// the exact state the story is about: socket back, truth not yet re-read.
Future<(LiveController, List<String>)> _droppedMidService(
  WidgetTester tester,
  Widget Function(LiveController) child,
) async {
  final sent = <String>[];
  final original = _Fake(sent: sent);
  final replacement = _Fake(sent: sent)..gate = Completer<void>();

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
}
