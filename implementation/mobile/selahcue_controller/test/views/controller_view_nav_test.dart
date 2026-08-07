/// The bottom bar is role-scoped (Figma 363-124): a role sees only the tabs it
/// may use. Viewer loses Scripture; Producer keeps all four.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
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

Future<void> _pump(WidgetTester tester, MobileRole role) async {
  await tester.pumpWidget(MaterialApp(
      home: ControllerView(session: _Fake(role), stored: _stored)));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

int _destinationCount(WidgetTester tester) =>
    tester.widgetList(find.byType(NavigationDestination)).length;

void main() {
  testWidgets('Producer bar has all four tabs incl. Scripture', (tester) async {
    await _pump(tester, MobileRole.producer);
    expect(_destinationCount(tester), 4);
    expect(find.widgetWithText(NavigationDestination, 'Scripture'),
        findsOneWidget);
    await tester.pumpWidget(const SizedBox()); // dispose → cancel the 1s poll
  });

  testWidgets('Viewer bar drops Scripture (3 tabs)', (tester) async {
    await _pump(tester, MobileRole.viewer);
    expect(_destinationCount(tester), 3);
    expect(find.widgetWithText(NavigationDestination, 'Scripture'), findsNothing);
    expect(find.widgetWithText(NavigationDestination, 'Live'), findsOneWidget);
    expect(find.widgetWithText(NavigationDestination, 'Timer'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Assistant keeps all four tabs', (tester) async {
    await _pump(tester, MobileRole.assistant);
    expect(_destinationCount(tester), 4);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('selecting a tab on the Viewer bar switches without overflow',
      (tester) async {
    await _pump(tester, MobileRole.viewer);
    // Tap the last destination (Timer, index 2 of 3) — must not throw / overflow.
    await tester.tap(find.widgetWithText(NavigationDestination, 'Timer'));
    await tester.pump();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}
