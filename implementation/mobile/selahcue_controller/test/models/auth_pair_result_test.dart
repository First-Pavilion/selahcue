/// 17tnw2b1f1v — the pure parse of the auth/pair replies: which frames are a
/// VERDICT and which are MALFORMED.
///
/// The end-to-end consequences (credentials kept or cleared, the pairing
/// screen's message) are pinned in session_handshake_reply_test.dart and the two
/// controller tests; this file pins the parse itself, shape by shape, so a
/// regression names the exact frame that broke. Nothing here may throw: a
/// wrong-typed field used to escape as a raw `TypeError` from a cast.
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';

Map<String, dynamic> _json(String s) => jsonDecode(s) as Map<String, dynamic>;

AuthResult _auth(String s) => AuthResult.fromJson(_json(s));
PairResult _pair(String s) => PairResult.fromJson(_json(s));

void main() {
  group('AuthResult.fromJson', () {
    test('only an explicit granted/rejected is a verdict', () {
      final granted = _auth('{"auth":"granted","role":"producer"}');
      expect(granted, isA<AuthGranted>());
      expect((granted as AuthGranted).role, 'producer');

      final rejected = _auth('{"auth":"rejected","reason":"unauthenticated"}');
      expect(rejected, isA<AuthRejected>());
      expect((rejected as AuthRejected).reason, 'unauthenticated');
    });

    test('a version-mismatch rejection (bad_request) is still an explicit reject',
        () {
      // The reason the Rust host sends from `authenticate` for `v != VERSION`.
      final r = _auth('{"auth":"rejected","reason":"bad_request"}');
      expect(r, isA<AuthRejected>());
      expect((r as AuthRejected).reason, 'bad_request');
    });

    test('a rejection with no reason is still a rejection (the reason is display '
        'text)', () {
      final r = _auth('{"auth":"rejected"}');
      expect(r, isA<AuthRejected>());
      expect((r as AuthRejected).reason, '');
    });

    test('an unknown role string is still granted (MobileRole fails it closed)',
        () {
      expect(_auth('{"auth":"granted","role":"archangel"}'), isA<AuthGranted>());
      expect(_auth('{"auth":"granted","role":""}'), isA<AuthGranted>());
    });

    const malformed = <String>[
      '{}',
      '{"foo":"bar"}',
      '{"auth":123}',
      '{"auth":null}',
      '{"auth":true}',
      '{"auth":["granted"]}',
      '{"auth":"parked"}',
      '{"auth":"Rejected","reason":"x"}',
      '{"auth":"granted"}',
      '{"auth":"granted","role":5}',
      '{"auth":"granted","role":null}',
      '{"auth":"granted","role":["producer"]}',
      '{"auth":"rejected","reason":5}',
      '{"auth":"rejected","reason":null}',
      '{"auth":"rejected","reason":{"code":"unauthenticated"}}',
    ];
    for (final frame in malformed) {
      test('$frame is AuthMalformed — never a rejection, never a throw', () {
        expect(_auth(frame), isA<AuthMalformed>());
      });
    }
  });

  group('PairResult.fromJson', () {
    test('granted, parked and rejected are verdicts', () {
      final g = _pair(
          '{"pair":"granted","device_id":"dev-9","token":"t9","role":"producer"}');
      expect(g, isA<PairGranted>());
      expect((g as PairGranted).deviceId, 'dev-9');
      expect(g.token, 't9');
      expect(g.role, 'producer');

      expect(_pair('{"pair":"parked"}'), isA<PairParked>());

      final r = _pair('{"pair":"rejected","reason":"forbidden"}');
      expect(r, isA<PairRejected>());
      expect((r as PairRejected).reason, 'forbidden');
    });

    test('a rejection with no reason is still a rejection', () {
      final r = _pair('{"pair":"rejected"}');
      expect(r, isA<PairRejected>());
      expect((r as PairRejected).reason, '');
    });

    test('an unknown role string is still granted', () {
      expect(
          _pair('{"pair":"granted","device_id":"d","token":"t","role":"archangel"}'),
          isA<PairGranted>());
    });

    const malformed = <String>[
      '{}',
      '{"foo":"bar"}',
      '{"pair":123}',
      '{"pair":null}',
      '{"pair":"maybe"}',
      '{"pair":"granted"}',
      '{"pair":"granted","device_id":5,"token":"t","role":"producer"}',
      '{"pair":"granted","device_id":"d","token":5,"role":"producer"}',
      '{"pair":"granted","device_id":"d","token":"t","role":5}',
      '{"pair":"granted","device_id":null,"token":"t","role":"producer"}',
      '{"pair":"granted","device_id":"d","role":"producer"}',
      '{"pair":"granted","device_id":"d","token":"t"}',
      '{"pair":"granted","device_id":"","token":"t","role":"producer"}',
      '{"pair":"granted","device_id":"d","token":"","role":"producer"}',
      '{"pair":"rejected","reason":5}',
      '{"pair":"rejected","reason":null}',
    ];
    for (final frame in malformed) {
      test('$frame is PairMalformed — never a rejection, never a throw', () {
        expect(_pair(frame), isA<PairMalformed>());
      });
    }
  });
}
