/// A revoked device (host sends AuthRejected on reconnect) must STOP retrying
/// and surface the revoked state — not loop "Reconnecting…" forever.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

/// A session whose poll always fails, forcing the controller into `_reconnect`.
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

void main() {
  test('AuthRejected on reconnect → revoked=true, stops reconnecting', () async {
    // The injected connect always reports the creds are revoked.
    Future<SelahSession> revokedConnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        throw const SessionRevoked('authentication rejected: revoked');

    final live = LiveController(
      session: _DeadSession(),
      stored: _stored,
      connect: revokedConnect,
    );
    // Let the constructor's refresh() fail → _reconnect() → revokedConnect().
    await Future<void>.delayed(const Duration(milliseconds: 30));

    expect(live.revoked, isTrue);
    expect(live.reconnecting, isFalse);
    live.dispose();
  });

  test('a transient failure keeps reconnecting (not revoked)', () async {
    var attempts = 0;
    Future<SelahSession> flakyConnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async {
      attempts++;
      throw const SessionException('network down');
    }

    final live = LiveController(
      session: _DeadSession(),
      stored: _stored,
      connect: flakyConnect,
    );
    await Future<void>.delayed(const Duration(milliseconds: 30));

    expect(live.revoked, isFalse);
    expect(live.reconnecting, isTrue); // still trying
    expect(attempts, greaterThanOrEqualTo(1));
    live.dispose();
  });

  test('SessionRevoked is a SessionException (existing catches still work)', () {
    expect(const SessionRevoked('x'), isA<SessionException>());
  });
}
