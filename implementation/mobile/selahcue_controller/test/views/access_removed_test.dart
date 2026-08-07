/// A revoked device shows the Access-removed screen (not an infinite reconnect),
/// with a re-pair action.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';

class _DeadSession implements ControllerSession {
  @override
  MobileRole get grantedRole => MobileRole.producer;
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async =>
      throw const SessionException('dead');
  @override
  Future<OperatorStateView> operatorState() async =>
      throw const SessionException('dead');
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

Future<SelahSession> _revokedConnect({
  required String host,
  required int port,
  required String pinHex,
  required Credentials creds,
}) async =>
    throw const SessionRevoked('authentication rejected: revoked');

void main() {
  testWidgets('AccessRemovedScreen renders the message + re-pair button',
      (tester) async {
    var repaired = 0;
    await tester.pumpWidget(MaterialApp(
      home: AccessRemovedScreen(onRepair: () => repaired++),
    ));
    expect(find.text('Access removed'), findsOneWidget);
    expect(find.textContaining('live service is unaffected'), findsOneWidget);
    await tester.tap(find.text('Scan QR to pair again'));
    await tester.pump();
    expect(repaired, 1);
  });

  testWidgets('a revoked device shows Access removed instead of reconnecting',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: ControllerView(
        session: _DeadSession(),
        stored: _stored,
        connect: _revokedConnect,
      ),
    ));
    // Constructor refresh() fails → _reconnect() → revoked → rebuild.
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 20));
    }
    expect(find.text('Access removed'), findsOneWidget);
    expect(find.textContaining('Reconnecting'), findsNothing);
    await tester.pumpWidget(const SizedBox()); // dispose
  });
}
