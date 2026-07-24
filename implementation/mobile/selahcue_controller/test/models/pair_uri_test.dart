/// Pairing-invite URI tests — mirrors the Rust `pairing_invite_uri_round_trips_
/// and_rejects_garbage` cases so both parsers accept/reject identically.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/pair_uri.dart';

void main() {
  test('round-trips a well-formed invite', () {
    final invite = PairingInvite(
      host: '192.168.1.20',
      port: 53621,
      pinHex: 'ab' * 32,
      code: 'CODE2345',
    );
    final uri = invite.toUri()!;
    expect(uri, startsWith('selahcue://pair?'));
    final back = PairingInvite.parse(uri)!;
    expect(back.host, invite.host);
    expect(back.port, invite.port);
    expect(back.pinHex, invite.pinHex);
    expect(back.code, invite.code);
  });

  test('rejects malformed inputs without throwing', () {
    const bad = [
      '',
      'selahcue://pair?',
      'selahcue://pair?host=&port=1&pin=ab&code=C',
      'selahcue://pair?host=h&port=notaport&pin=ab&code=C',
      'selahcue://pair?host=h&port=1&pin=ab', // missing code
      'http://evil/pair?host=h&port=1&pin=ab&code=C',
      'selahcue://pair?host=h&port=1&pin=ab&code=has space',
      'selahcue://pair?host=h&port=0&pin=ab&code=C', // port out of range
      'selahcue://pair?host=h&port=70000&pin=ab&code=C',
    ];
    for (final uri in bad) {
      expect(PairingInvite.parse(uri), isNull, reason: 'should reject: $uri');
    }
  });

  test('unknown query params are ignored (forward compatibility)', () {
    final invite = PairingInvite.parse(
        'selahcue://pair?host=h&port=1&pin=ab&code=C&future=x');
    expect(invite, isNotNull);
    expect(invite!.code, 'C');
  });

  test('refuses to encode URI-breaking values', () {
    final evil =
        PairingInvite(host: 'a&b', port: 1, pinHex: 'ab', code: 'C');
    expect(evil.toUri(), isNull);
  });
}
