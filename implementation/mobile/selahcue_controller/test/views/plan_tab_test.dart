/// The Plan tab is role-gated: staging needs Navigate. Viewer is read-only.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/plan_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final List<Map<String, dynamic>> sent = [];
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
        planName: 'Sunday',
        items: [
          PlanItemView(
              id: 1, kind: 'song', title: 'Opening', isLive: false, isStaged: false),
        ],
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

Future<LiveController> _pump(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester
      .pumpWidget(MaterialApp(home: Scaffold(body: PlanTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Producer taps an item to stage it', (tester) async {
    final fake = _Fake(MobileRole.producer);
    final live = await _pump(tester, fake);
    await tester.tap(find.text('Opening'));
    // The row has both onTap + onDoubleTap, so single-tap disambiguation waits
    // for the double-tap timer before onTap fires — pump past it.
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'select_item'), isTrue);
    live.dispose();
  });

  testWidgets('Viewer plan is read-only — a tap stages nothing', (tester) async {
    final fake = _Fake(MobileRole.viewer);
    final live = await _pump(tester, fake);
    await tester.tap(find.text('Opening'));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'select_item'), isFalse);
    expect(find.textContaining('Read-only'), findsOneWidget);
    live.dispose();
  });
}
