/// The granted role must travel session → controller so views can gate on it.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

class _RoleFake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _RoleFake(this.grantedRole);
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
  test('LiveController exposes the session role and gates capabilities', () {
    final producer =
        LiveController(session: _RoleFake(MobileRole.producer), stored: _stored);
    expect(producer.role, MobileRole.producer);
    expect(producer.can(Capability.goLive), isTrue);
    producer.dispose();

    final assistant =
        LiveController(session: _RoleFake(MobileRole.assistant), stored: _stored);
    expect(assistant.can(Capability.goLive), isFalse);
    expect(assistant.can(Capability.searchScripture), isTrue);
    assistant.dispose();

    final viewer =
        LiveController(session: _RoleFake(MobileRole.viewer), stored: _stored);
    expect(viewer.can(Capability.navigate), isFalse);
    expect(viewer.can(Capability.monitor), isTrue);
    viewer.dispose();
  });
}
