/// Scripture search/stage is role-gated: SearchScripture (Producer/Assistant)
/// sees the field; Viewer gets a read-only notice.
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
  testWidgets('Assistant sees the search field', (tester) async {
    final live =
        LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.byType(TextField), findsOneWidget);
    live.dispose();
  });

  testWidgets('Viewer sees a read-only notice, no search field', (tester) async {
    final live =
        LiveController(session: _Fake(MobileRole.viewer), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.byType(TextField), findsNothing);
    expect(find.textContaining('not part of your role'), findsOneWidget);
    live.dispose();
  });
}
