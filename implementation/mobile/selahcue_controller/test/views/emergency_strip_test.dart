/// The emergency strip's Blackout / Clear are role-gated (hide-not-disable).
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
        planName: 'S',
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

void main() {
  testWidgets('Producer sees Blackout + Clear', (tester) async {
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.producer), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget);
    expect(find.bySemanticsLabel('Clear all'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Assistant sees neither emergency control', (tester) async {
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsNothing);
    expect(find.bySemanticsLabel('Clear all'), findsNothing);
    handle.dispose();
    live.dispose();
  });
}
