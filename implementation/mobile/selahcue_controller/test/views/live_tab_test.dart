/// Live transport is role-gated (hide-not-disable): navigate → Prev/Next;
/// goLive → GO LIVE. Viewer sees read-only cards only.
library;

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
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
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

  testWidgets('Viewer sees no transport controls', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.viewer);
    expect(find.text('GO LIVE'), findsNothing);
    expect(find.bySemanticsLabel('Next item'), findsNothing);
    expect(find.bySemanticsLabel('Previous item'), findsNothing);
    handle.dispose();
    live.dispose();
  });
}
