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

    test('unknown extra keys on a verdict frame are ignored (the wire evolves '
        'additively)', () {
      // A newer host may add a field to a verdict without a version bump. The
      // parse must read the keys it knows and ignore the rest, never demand an
      // exact key set.
      final granted = _auth(
          '{"auth":"granted","role":"producer","note":{"a":[1,2]},"extra":null}');
      expect(granted, isA<AuthGranted>());
      expect((granted as AuthGranted).role, 'producer');

      final rejected = _auth(
          '{"auth":"rejected","reason":"unauthenticated","extra":{"a":1}}');
      expect(rejected, isA<AuthRejected>());
      expect((rejected as AuthRejected).reason, 'unauthenticated');

      // ...also when the rejection carries no reason of its own.
      expect(_auth('{"auth":"rejected","extra":1}'), isA<AuthRejected>());
    });

    test('an UNKNOWN future reason string and an EMPTY reason are still '
        'rejections (any string is display text)', () {
      final future = _auth('{"auth":"rejected","reason":"expired_v2"}');
      expect(future, isA<AuthRejected>());
      expect((future as AuthRejected).reason, 'expired_v2');

      final empty = _auth('{"auth":"rejected","reason":""}');
      expect(empty, isA<AuthRejected>());
      expect((empty as AuthRejected).reason, '');
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

    test('unknown extra keys on a verdict frame are ignored (the wire evolves '
        'additively)', () {
      final granted = _pair('{"pair":"granted","device_id":"d9","token":"t9",'
          '"role":"viewer","extra":[1,{"y":2}]}');
      expect(granted, isA<PairGranted>());
      expect((granted as PairGranted).deviceId, 'd9');
      expect(granted.token, 't9');
      expect(granted.role, 'viewer');

      final rejected =
          _pair('{"pair":"rejected","reason":"forbidden","extra":{"a":1}}');
      expect(rejected, isA<PairRejected>());
      expect((rejected as PairRejected).reason, 'forbidden');

      expect(_pair('{"pair":"parked","note":{"a":1}}'), isA<PairParked>());
    });

    test('an unknown future reason string and an empty reason are still '
        'rejections', () {
      final future = _pair('{"pair":"rejected","reason":"newthing"}');
      expect(future, isA<PairRejected>());
      expect((future as PairRejected).reason, 'newthing');

      final empty = _pair('{"pair":"rejected","reason":""}');
      expect(empty, isA<PairRejected>());
      expect((empty as PairRejected).reason, '');
    });

    const malformed = <String>[
      '{}',
      '{"foo":"bar"}',
      '{"pair":123}',
      '{"pair":null}',
      '{"pair":"maybe"}',
      // The tag is exact: a wrongly cased verdict is not a verdict.
      '{"pair":"GRANTED","device_id":"d","token":"t","role":"producer"}',
      '{"pair":"Rejected","reason":"forbidden"}',
      '{"pair":"PARKED"}',
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
