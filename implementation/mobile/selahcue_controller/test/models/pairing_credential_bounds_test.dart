/// 17tnw2b1wt4: issued opaque credentials are bounded printable text, not
/// arbitrary host payloads. Rejection reasons remain verdicts but are bounded
/// display text. Expected limits are independent of production constants.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';

Map<String, dynamic> _grant(String field, String value) => {
      'pair': 'granted',
      'device_id': 'dev-0123456789abcdef',
      'token': '0123456789abcdef' * 4,
      'role': 'producer',
      field: value,
    };

String _reason(String tag, String text) {
  final frame = <String, dynamic>{tag: 'rejected', 'reason': text};
  if (tag == 'pair') {
    final result = PairResult.fromJson(frame);
    expect(result, isA<PairRejected>());
    return (result as PairRejected).reason;
  }
  final result = AuthResult.fromJson(frame);
  expect(result, isA<AuthRejected>());
  return (result as AuthRejected).reason;
}

void main() {
  for (final field in ['device_id', 'token']) {
    group('issued $field', () {
      final invalid = <String, String>{
        '1025 characters': 'a' * 1025,
        '2 MiB': 'a' * (2 * 1024 * 1024),
        'NUL': 'ab\u0000cd',
        'tab': 'ab\tcd',
        'newline': 'ab\ncd',
        'DEL': 'ab\u007fcd',
        'spaces only': '   ',
        'tabs only': '\t\t',
        'non-ASCII': 'abé',
        'invisible Unicode': 'ab\u200bcd',
        'unpaired surrogate': 'ab\ud800cd',
      };
      for (final entry in invalid.entries) {
        test('${entry.key} is malformed rather than granted', () {
          expect(PairResult.fromJson(_grant(field, entry.value)),
              isA<PairMalformed>());
        });
      }

      for (final length in [1, 1024]) {
        test('$length printable characters remain unchanged', () {
          final value = 'x' * length;
          final result = PairResult.fromJson(_grant(field, value));
          expect(result, isA<PairGranted>());
          final grant = result as PairGranted;
          expect(field == 'device_id' ? grant.deviceId : grant.token, value);
        });
      }

      test('all printable ASCII is accepted without trimming or a hex grammar',
          () {
        final value = String.fromCharCodes(
            List<int>.generate(95, (index) => 0x20 + index));
        final result = PairResult.fromJson(_grant(field, value));
        expect(result, isA<PairGranted>());
        final grant = result as PairGranted;
        expect(field == 'device_id' ? grant.deviceId : grant.token, value);
      });
    });
  }

  for (final tag in ['pair', 'auth']) {
    group('$tag rejection display', () {
      test('a 1 MiB reason is truncated without changing the verdict', () {
        final value = 'prefix:${'r' * (1024 * 1024)}:hidden-tail';
        final reason = _reason(tag, value);
        expect(reason.length, lessThanOrEqualTo(1024));
        expect(reason, startsWith('prefix:'));
        expect(reason, isNot(contains(':hidden-tail')));
      });

      test('a reason at 1024 code units is unchanged', () {
        final value = 'r' * 1024;
        expect(_reason(tag, value), value);
      });

      test('a reason above 1024 code units is truncated', () {
        expect(_reason(tag, 'r' * 1025).length, lessThanOrEqualTo(1024));
      });

      test('short Unicode display text remains unchanged', () {
        const value = 'Not now — réessayer 😀';
        expect(_reason(tag, value), value);
      });

      test('truncation does not leave half a surrogate pair', () {
        final reason = _reason(tag, '${'x' * 1023}😀tail');
        expect(reason.length, lessThanOrEqualTo(1024));
        expect(reason, startsWith('x' * 1023));
        expect(reason.runes.any((rune) => rune >= 0xd800 && rune <= 0xdfff),
            isFalse);
      });
    });
  }
}
