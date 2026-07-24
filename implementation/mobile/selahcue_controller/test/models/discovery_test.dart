import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/discovery.dart';

void main() {
  test('TXT entries parse into a map, garbage skipped', () {
    expect(
      parseTxt(['pin=abc123', 'name=Sanctuary Mac', 'noequals', '=empty']),
      {'pin': 'abc123', 'name': 'Sanctuary Mac'},
    );
  });

  test('a discovered host composes the exact QR-equivalent invite URI', () {
    const h = DiscoveredHost(
        name: 'Sanctuary', host: '10.0.0.5', port: 4433, pinHex: 'aa11');
    expect(
      h.inviteUri(' abcd2345 '),
      'selahcue://pair?host=10.0.0.5&port=4433&pin=aa11&code=ABCD2345',
    );
  });

  test('pin fingerprint matches the Rust format (SAS comparison)', () {
    expect(pinFingerprint('ab12cd34ef56aa99bbccddee'), 'AB12-CD34-EF56');
    expect(pinFingerprint('abcd'), 'ABCD');
    expect(pinFingerprint(''), '');
    const h = DiscoveredHost(
        name: 'x', host: 'h', port: 1, pinHex: 'ab12cd34ef56aa99');
    expect(h.fingerprint, 'AB12-CD34-EF56');
  });
}
