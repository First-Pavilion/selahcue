/// The app-bar role badge shows the REAL granted role — not the old hardcoded
/// "Producer".
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';

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

void main() {
  testWidgets('badge shows the granted role (Assistant, not hardcoded Producer)',
      (tester) async {
    final live =
        LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(appBar: AppBar(actions: [RoleBadge(live: live)])),
    ));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.text('ASSISTANT'), findsOneWidget);
    expect(find.text('PRODUCER'), findsNothing);
    live.dispose();
  });

  testWidgets('badge reflects a Viewer grant', (tester) async {
    final live =
        LiveController(session: _Fake(MobileRole.viewer), stored: _stored);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(appBar: AppBar(actions: [RoleBadge(live: live)])),
    ));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.text('VIEWER'), findsOneWidget);
    live.dispose();
  });
}
