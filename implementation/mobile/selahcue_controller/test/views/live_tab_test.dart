/// Live transport is role-gated (hide-not-disable): navigate → Prev/Next;
/// goLive → GO LIVE. Viewer sees read-only cards only.
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

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);

  /// When set, `command()` parks before replying — a command reached the
  /// host but its acknowledgement hasn't landed yet.
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    final g = commandGate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
        planName: 'Sunday',
        items: [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
      );
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

Future<LiveController> _pump(WidgetTester tester, MobileRole role) async {
  final live = LiveController(session: _Fake(role), stored: _stored);
  await tester
      .pumpWidget(MaterialApp(home: Scaffold(body: LiveTab(live: live))));
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
        builder: (_, _) => LiveTab(live: live),
      ),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Producer sees GO LIVE + transport', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.producer);
    expect(find.text('GO LIVE'), findsOneWidget);
    expect(find.bySemanticsLabel('Next item'), findsOneWidget);
    expect(find.bySemanticsLabel('Previous item'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Assistant sees Prev/Next but not GO LIVE', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.assistant);
    expect(find.text('GO LIVE'), findsNothing);
    expect(find.bySemanticsLabel('Next item'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Preview + Live are side-by-side on a wide (tablet) surface',
      (tester) async {
    tester.view.physicalSize = const Size(900, 700);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final live = await _pump(tester, MobileRole.producer);
    final previewTop = tester.getTopLeft(find.text('PREVIEW'));
    final liveTop = tester.getTopLeft(find.text('LIVE'));
    // Same row → aligned tops; Live is to the RIGHT of Preview.
    expect(liveTop.dy, previewTop.dy);
    expect(liveTop.dx, greaterThan(previewTop.dx));
    live.dispose();
  });

  testWidgets('Preview + Live stack on a narrow (phone) surface', (tester) async {
    tester.view.physicalSize = const Size(360, 720);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final live = await _pump(tester, MobileRole.producer);
    final previewTop = tester.getTopLeft(find.text('PREVIEW'));
    final liveTop = tester.getTopLeft(find.text('LIVE'));
    expect(liveTop.dy, greaterThan(previewTop.dy)); // Live below Preview
    live.dispose();
  });

  testWidgets('Viewer sees no transport controls', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.viewer);
    expect(find.text('GO LIVE'), findsNothing);
    expect(find.bySemanticsLabel('Next item'), findsNothing);
    expect(find.bySemanticsLabel('Previous item'), findsNothing);
    handle.dispose();
    live.dispose();
  });

  testWidgets('transport is disabled while a command is in flight',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake(MobileRole.producer);
    final live = await _pumpPolled(tester, fake);
    expect(live.busy, isFalse, reason: 'baseline');

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('GO LIVE'));
    await tester.pump();

    expect(live.busy, isTrue);
    expect(find.bySemanticsLabel('Go live, sending…'), findsOneWidget,
        reason: 'a control must not look tappable while its own command is '
            'still on the wire (17tnw2ay2pq, follow-up to 17tnw2ay2kk)');
    expect(find.bySemanticsLabel('Next item, sending…'), findsOneWidget,
        reason: 'every control gated the same way must disable together, '
            'not just the one that was tapped');
    expect(find.bySemanticsLabel('Previous item, sending…'), findsOneWidget);

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    expect(find.bySemanticsLabel('Go live'), findsOneWidget,
        reason: 'and re-enables once busy clears');

    handle.dispose();
    live.dispose();
  });
}
