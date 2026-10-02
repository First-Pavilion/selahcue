/// 17tnw2b1f1v — what the pairing screen says when the host's pair reply is
/// malformed.
///
/// A wrong-typed field in a granted pair reply (`{"pair":"granted","device_id":5}`)
/// used to escape `SelahSession.pair` as a raw `TypeError`. `PairingController`
/// maps every non-`SessionException` to "Paired, but could not save credentials
/// on this device", which is untrue: nothing was granted and nothing was saved.
/// The screen must show the real cause (a malformed reply from the host), keep
/// the "could not save credentials" wording for the one case it is true, and a
/// malformed reply must never be recorded as a pairing.
///
/// Runs the real `SelahSession.pair` over pinned TLS against a loopback host
/// (test/support/loopback_host.dart), with the keystore faked so "nothing was
/// saved" is read back through `StoredSession.load()`.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/pairing_controller.dart';
import 'package:selahcue_controller/models/stored_session.dart';

import '../support/fake_keystore.dart';
import '../support/loopback_host.dart';

String _inviteFor(LoopbackHost host) =>
    'selahcue://pair?host=127.0.0.1&port=${host.port}&pin=${host.pinHex}&code=CODE-1';

/// Granted replies with a wrong-typed or missing field, one per field.
const _malformedGranted = <String, String>{
  'a numeric device_id':
      '{"pair":"granted","device_id":5,"token":"t","role":"producer"}',
  'a numeric token':
      '{"pair":"granted","device_id":"d","token":5,"role":"producer"}',
  'a numeric role': '{"pair":"granted","device_id":"d","token":"t","role":5}',
  'no fields at all': '{"pair":"granted"}',
};

void main() {
  for (final entry in _malformedGranted.entries) {
    test('a granted pair reply with ${entry.key} shows a malformed-reply '
        'message, not "could not save credentials"', () async {
      final host = await LoopbackHost.start(replies: [entry.value]);
      final keystore = FakeKeystore()..install();
      final controller = PairingController();

      final outcome = await controller.pair(_inviteFor(host), 'Test phone');

      expect(outcome, isNull);
      expect(controller.error, 'malformed frame from the host');
      expect(controller.error, isNot(contains('could not save credentials')));
      expect(controller.busy, isFalse);
      expect(keystore.writes, 0, reason: 'a malformed reply is never saved');
      expect(await StoredSession.load(), isNull);
    });
  }

  test('a malformed reply after "parked" shows the same malformed-reply message',
      () async {
    final host = await LoopbackHost.start(replies: [
      '{"pair":"parked"}',
      '{"pair":"granted","device_id":5,"token":"t","role":"producer"}',
    ]);
    FakeKeystore().install();
    final controller = PairingController();

    expect(await controller.pair(_inviteFor(host), 'Test phone'), isNull);
    expect(controller.error, 'malformed frame from the host');
  });

  test('an empty object is a malformed reply, not an operator rejection',
      () async {
    // Used to read "pairing rejected: malformed reply", which blames the
    // operator for a frame no operator sent.
    final host = await LoopbackHost.start(replies: ['{}']);
    FakeKeystore().install();
    final controller = PairingController();

    expect(await controller.pair(_inviteFor(host), 'Test phone'), isNull);
    expect(controller.error, 'malformed frame from the host');
  });

  test('control: a well-formed granted reply pairs and the credentials are saved',
      () async {
    final host = await LoopbackHost.start(replies: [
      '{"pair":"parked"}',
      '{"pair":"granted","device_id":"dev-9","token":"t9","role":"viewer"}',
    ]);
    final keystore = FakeKeystore()..install();
    final controller = PairingController();

    final outcome = await controller.pair(_inviteFor(host), 'Test phone');
    addTearDown(() async => outcome?.session.close());

    expect(outcome, isNotNull);
    expect(controller.error, isNull);
    expect(keystore.writes, 1);
    final saved = await StoredSession.load();
    expect(saved?.deviceId, 'dev-9');
    expect(saved?.token, 't9');
  });

  test('control: "could not save credentials" is still shown when the keystore '
      'write really fails', () async {
    // The one case that wording is true: pairing succeeded, saving did not.
    final host = await LoopbackHost.start(replies: [
      '{"pair":"granted","device_id":"dev-9","token":"t9","role":"viewer"}',
    ]);
    FakeKeystore()
      ..failWrites = true
      ..install();
    final controller = PairingController();

    expect(await controller.pair(_inviteFor(host), 'Test phone'), isNull);
    expect(controller.error,
        'Paired, but could not save credentials on this device.');
  });

  test('control: an explicit "rejected" still reads as the operator\'s answer',
      () async {
    final host = await LoopbackHost.start(
        replies: ['{"pair":"rejected","reason":"forbidden"}']);
    FakeKeystore().install();
    final controller = PairingController();

    expect(await controller.pair(_inviteFor(host), 'Test phone'), isNull);
    expect(controller.error, 'pairing rejected: forbidden');
  });
}
