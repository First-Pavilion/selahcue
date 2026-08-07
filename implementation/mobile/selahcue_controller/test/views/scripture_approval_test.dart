/// The Scripture tab shows the detection-approval card (FR-095) and Approve /
/// Reject send the right commands.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final OperatorStateView view;
  final List<Map<String, dynamic>> sent = [];
  _Fake(this.grantedRole, this.view);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

OperatorStateView _viewWithDetections() => const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
      detections: [
        DetectionView(
            id: 7, reference: 'Romans 8:28', text: 'And we know…', confidence: 94),
      ],
    );

Future<LiveController> _pump(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester
      .pumpWidget(MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Assistant (Scripture Op) sees the approval card', (tester) async {
    final live =
        await _pump(tester, _Fake(MobileRole.assistant, _viewWithDetections()));
    expect(find.text('NEEDS YOUR APPROVAL'), findsOneWidget);
    expect(find.text('Romans 8:28'), findsOneWidget);
    expect(find.text('94% MATCH'), findsOneWidget);
    expect(find.text('Approve'), findsOneWidget);
    expect(find.text('Reject'), findsOneWidget);
    live.dispose();
  });

  testWidgets('Approve sends approve_detection; Reject sends dismiss_detection',
      (tester) async {
    final fake = _Fake(MobileRole.producer, _viewWithDetections());
    final live = await _pump(tester, fake);

    await tester.tap(find.text('Approve'));
    await tester.pump();
    expect(
        fake.sent.any((c) =>
            c['cmd'] == 'approve_detection' && c['detection_id'] == 7),
        isTrue);

    await tester.tap(find.text('Reject'));
    await tester.pump();
    expect(
        fake.sent.any((c) =>
            c['cmd'] == 'dismiss_detection' && c['detection_id'] == 7),
        isTrue);
    live.dispose();
  });

  testWidgets('Viewer (no scripture) does not see the approval card',
      (tester) async {
    final live =
        await _pump(tester, _Fake(MobileRole.viewer, _viewWithDetections()));
    expect(find.text('NEEDS YOUR APPROVAL'), findsNothing);
    expect(find.textContaining('not part of your role'), findsOneWidget);
    live.dispose();
  });
}
