/// 17tnw2b1wt4: real pinned-TLS pairing must reject malformed issued secrets
/// before the production persistence path. Only the platform keystore is faked.
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/pairing_controller.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/stored_session.dart';

import '../support/fake_keystore.dart';
import '../support/loopback_host.dart';

String _invite(LoopbackHost host) =>
    'selahcue://pair?host=127.0.0.1&port=${host.port}&pin=${host.pinHex}&code=CODE-1';

Map<String, dynamic> _grant(String field, String value) => {
      'pair': 'granted',
      'device_id': 'dev-0123456789abcdef',
      'token': '0123456789abcdef' * 4,
      'role': 'viewer',
      field: value,
    };

void main() {
  for (final field in ['device_id', 'token']) {
    final invalid = <String, String>{
      '1025 characters': 'a' * 1025,
      '2 MiB': 'a' * (2 * 1024 * 1024),
      'NUL': 'ab\u0000cd',
      'spaces only': '   ',
      'tabs only': '\t\t',
      'non-ASCII': 'abé',
    };
    for (final entry in invalid.entries) {
      test('$field with ${entry.key} shows malformed host and saves nothing',
          () async {
        final host = await LoopbackHost.start(
            replies: [jsonEncode(_grant(field, entry.value))]);
        final keystore = FakeKeystore()..install();
        final controller = PairingController();
        addTearDown(controller.dispose);

        final outcome = await controller.pair(_invite(host), 'Test phone');
        addTearDown(() async => outcome?.session.close());

        expect(outcome, isNull);
        expect(controller.error, 'malformed frame from the host');
        expect(controller.busy, isFalse);
        expect(keystore.writes, 0);
        expect(keystore.deletes, 0);
        expect(await StoredSession.load(), isNull);
        expect(await host.waitClientClosed(1), isTrue,
            reason: 'the malformed grant must release its pinned-TLS socket');
      });
    }
  }

  test('real host dev-hex and 64-character hex credentials still pair', () async {
    const deviceId = 'dev-0123456789abcdef';
    final token = '0123456789abcdef' * 4;
    final host = await LoopbackHost.start(replies: [
      '{"pair":"parked"}',
      jsonEncode(_grant('token', token)),
    ]);
    final keystore = FakeKeystore()..install();
    final controller = PairingController();
    addTearDown(controller.dispose);
    final outcome = await controller.pair(_invite(host), 'Test phone');
    addTearDown(() async => outcome?.session.close());

    expect(outcome, isNotNull);
    expect(controller.error, isNull);
    expect(controller.busy, isFalse);
    expect(keystore.writes, 1);
    expect(keystore.deletes, 0);
    final saved = await StoredSession.load();
    expect(saved?.deviceId, deviceId);
    expect(saved?.token, token);
    expect(outcome!.session.grantedRole, MobileRole.viewer);
  });

  test('1024-character opaque credentials and an unknown role remain valid',
      () async {
    final deviceId = ' ${'d' * 1022}~';
    final token = '!${'t' * 1022} ';
    final host = await LoopbackHost.start(replies: [
      jsonEncode({
        'pair': 'granted',
        'device_id': deviceId,
        'token': token,
        'role': 'future_role',
      }),
    ]);
    final keystore = FakeKeystore()..install();
    final controller = PairingController();
    addTearDown(controller.dispose);
    final outcome = await controller.pair(_invite(host), 'Test phone');
    addTearDown(() async => outcome?.session.close());

    expect(outcome, isNotNull);
    expect(controller.error, isNull);
    expect(keystore.writes, 1);
    final saved = await StoredSession.load();
    expect(saved?.deviceId, deviceId, reason: 'never trim an opaque credential');
    expect(saved?.token, token);
    final role = outcome!.session.grantedRole;
    expect(role, MobileRole.unknown);
    expect(role.capabilities, isEmpty);
  });

  test('an invalid grant preserves an existing stored profile', () async {
    final host = await LoopbackHost.start(
        replies: [jsonEncode(_grant('token', 'ab\u0000cd'))]);
    final keystore = FakeKeystore()..install();
    const prior = StoredSession(
        host: 'previous', port: 1, pinHex: 'ab', deviceId: 'dev-old', token: 'old');
    await StoredSession.save(prior);
    final controller = PairingController();
    addTearDown(controller.dispose);
    final outcome = await controller.pair(_invite(host), 'Test phone');
    addTearDown(() async => outcome?.session.close());

    expect(outcome, isNull);
    expect(controller.error, 'malformed frame from the host');
    expect(keystore.writes, 1, reason: 'only the test preloaded the profile');
    expect(keystore.deletes, 0);
    expect((await StoredSession.load())?.toJson(), prior.toJson());
  });

  test('a 1 MiB rejection reason is bounded in the pairing error', () async {
    final reason = 'prefix:${'r' * (1024 * 1024)}:hidden-tail';
    final host = await LoopbackHost.start(replies: [
      jsonEncode({'pair': 'rejected', 'reason': reason}),
    ]);
    final keystore = FakeKeystore()..install();
    final controller = PairingController();
    addTearDown(controller.dispose);

    expect(await controller.pair(_invite(host), 'Test phone'), isNull);
    final error = controller.error!;
    expect(error, startsWith('pairing rejected: prefix:'));
    expect(error.length, lessThanOrEqualTo('pairing rejected: '.length + 1024));
    expect(error, isNot(contains(':hidden-tail')));
    expect(controller.busy, isFalse);
    expect(keystore.writes, 0);
    expect(keystore.deletes, 0);
    expect(await StoredSession.load(), isNull);
    expect(await host.waitClientClosed(1), isTrue);
  });
}
