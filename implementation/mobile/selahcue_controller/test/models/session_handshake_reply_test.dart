/// 17tnw2b1f1v — an unrecognised or wrong-typed auth/pair reply is a MALFORMED
/// reply, not a verdict.
///
/// `SelahSession.connect` used to read a valid JSON object with a missing or
/// unknown `auth` key (`{}`) as `AuthRejected('malformed reply')` and throw it
/// as `SessionRevoked`, which makes `LiveController._reconnect` wipe the stored
/// credentials and show "Access removed". A wrong-typed field
/// (`{"auth":"granted","role":5}`) was worse in a different way: a raw
/// `TypeError` out of a cast, which on the PAIRING path surfaced as the untrue
/// "Paired, but could not save credentials on this device".
///
/// The contract these tests pin:
///   - ONLY an explicit `"auth":"rejected"` is a revocation (`SessionRevoked`).
///   - Any other reply the client cannot read is a `SessionException` saying
///     `malformed frame from the host` — transient, so retried, credentials kept.
///   - On the pair path the same malformed reply is that same `SessionException`
///     (the real cause), never a rejection by the operator and never "could not
///     save credentials".
///
/// Every test runs the production `connect`/`pair` over a real pinned-TLS
/// loopback socket (test/support/loopback_host.dart), so the reply goes through
/// the same transport, `StreamQueue` and parse the app uses.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/pair_uri.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';

import '../support/loopback_host.dart';

const _creds = Credentials(deviceId: 'dev-1', token: 'tok-1');

/// What a malformed reply must surface as: a plain [SessionException] (so it is
/// retried and shown honestly), explicitly NOT the revocation subtype, carrying
/// the same words `StreamQueue` uses for any frame it cannot read.
Matcher _malformed() => isA<SessionException>()
    .having((e) => e, 'is not a revocation', isNot(isA<SessionRevoked>()))
    .having((e) => e.message, 'message', 'malformed frame from the host');

Future<SelahSession> _connect(LoopbackHost host) => SelahSession.connect(
      host: '127.0.0.1',
      port: host.port,
      pinHex: host.pinHex,
      creds: _creds,
    );

Future<(SelahSession, Credentials)> _pair(LoopbackHost host) =>
    SelahSession.pair(
      PairingInvite(
        host: '127.0.0.1',
        port: host.port,
        pinHex: host.pinHex,
        code: 'CODE-1',
      ),
      'Test phone',
    );

/// Replies to the auth hello that are NOT a verdict. The first four are the
/// shapes the ticket names; the rest are neighbours of the same class.
const _malformedAuthReplies = <String, String>{
  'an empty object': '{}',
  'an object with no auth key': '{"foo":"bar"}',
  'a numeric auth tag': '{"auth":123}',
  'granted with a numeric role': '{"auth":"granted","role":5}',
  'a null auth tag': '{"auth":null}',
  'an unknown auth tag (an interim frame from a newer host)':
      '{"auth":"parked"}',
  'a wrongly cased tag': '{"auth":"Granted","role":"producer"}',
  'granted with a null role': '{"auth":"granted","role":null}',
  'granted with no role': '{"auth":"granted"}',
  'rejected with a non-string reason': '{"auth":"rejected","reason":5}',
};

/// Replies to the pair hello that are NOT a verdict.
const _malformedPairReplies = <String, String>{
  'an empty object': '{}',
  'a numeric pair tag': '{"pair":123}',
  'an unknown pair tag': '{"pair":"maybe"}',
  'an auth reply on the pair path': '{"auth":"granted","role":"producer"}',
  // The tag is exact: a wrongly cased verdict is not a verdict.
  'a wrongly cased granted tag':
      '{"pair":"GRANTED","device_id":"d","token":"t","role":"producer"}',
  'a wrongly cased rejected tag': '{"pair":"Rejected","reason":"forbidden"}',
  'a wrongly cased parked tag': '{"pair":"PARKED"}',
  'granted with a numeric device_id':
      '{"pair":"granted","device_id":5,"token":"t","role":"producer"}',
  'granted with a numeric token':
      '{"pair":"granted","device_id":"d","token":5,"role":"producer"}',
  'granted with a numeric role':
      '{"pair":"granted","device_id":"d","token":"t","role":5}',
  'granted with no fields': '{"pair":"granted"}',
  'granted with no token': '{"pair":"granted","device_id":"d","role":"producer"}',
  'granted with an empty device_id':
      '{"pair":"granted","device_id":"","token":"t","role":"producer"}',
  'granted with an empty token':
      '{"pair":"granted","device_id":"d","token":"","role":"producer"}',
  'rejected with a non-string reason': '{"pair":"rejected","reason":5}',
};

void main() {
  group('connect (auth hello)', () {
    for (final entry in _malformedAuthReplies.entries) {
      test('${entry.key} is a malformed SessionException, not a revocation',
          () async {
        final host = await LoopbackHost.start(replies: [entry.value]);
        await expectLater(_connect(host), throwsA(_malformed()));
        expect(host.hellos, hasLength(1),
            reason: 'the host really received the auth hello');
        expect(await host.waitClientClosed(1), isTrue,
            reason: 'a failed handshake must not leak its socket');
      });
    }

    test('control: the host sees a close only when the client really closes',
        () async {
      // Proves `waitClientClosed` is not vacuously true: an open, healthy
      // session has closed nothing, and closing it is what the host observes.
      final host = await LoopbackHost.start(
          replies: ['{"auth":"granted","role":"producer"}']);
      final session = await _connect(host);
      expect(host.clientClosedCount, 0);
      await session.close();
      expect(await host.waitClientClosed(1), isTrue);
    });

    test('control: a well-formed granted still connects with its role',
        () async {
      // Proves the harness (TLS, pin, hello, reply) is live, so the failures
      // above are about the frame and not about the plumbing.
      final host = await LoopbackHost.start(
          replies: ['{"auth":"granted","role":"producer"}']);
      final session = await _connect(host);
      addTearDown(session.close);
      expect(session.grantedRole, MobileRole.producer);
      expect(host.hellos.single['hello'], 'auth');
    });

    test('an unknown role STRING is still granted, as the deny-all role',
        () async {
      // A newer host may invent a role. That is a well-typed reply, and the
      // fail-closed `MobileRole.unknown` already handles it: it must not be
      // reclassified as malformed by the stricter parse.
      final host = await LoopbackHost.start(
          replies: ['{"auth":"granted","role":"archangel"}']);
      final session = await _connect(host);
      addTearDown(session.close);
      expect(session.grantedRole, MobileRole.unknown);
    });

    // The reasons the Rust host really sends (selahcue-lan/src/server.rs
    // `authenticate`): `unauthenticated` for an unknown/revoked device and
    // `bad_request` for a protocol-version mismatch. `forbidden` is the third
    // member of the closed `DenyReason` set.
    //
    // DECISION PENDING (ClickUp 17tnw2b1wav): pinning `bad_request` as a
    // REVOCATION is today's behaviour, not a verdict that it is right. A host
    // version bump would tell every paired phone it was revoked. Whoever settles
    // that ticket should update this expectation (and its controller-level twin
    // in test/controllers/live_controller_auth_reply_test.dart) ON PURPOSE.
    // The same holds for any reason string: an unknown future reason (see the
    // `expired_v2` test below) also revokes, so a future `rate_limited` sent as
    // an explicit rejection would wipe the credentials in exactly the same way.
    for (final reason in ['unauthenticated', 'bad_request', 'forbidden']) {
      test('an explicit "rejected" ($reason) is still a revocation', () async {
        final host = await LoopbackHost.start(
            replies: ['{"auth":"rejected","reason":"$reason"}']);
        await expectLater(
          _connect(host),
          throwsA(isA<SessionRevoked>().having((e) => e.message, 'message',
              'authentication rejected: $reason')),
        );
      });
    }

    test('an explicit "rejected" with no reason is still a revocation',
        () async {
      // The reason is display text only. The tag alone is the verdict.
      final host = await LoopbackHost.start(replies: ['{"auth":"rejected"}']);
      await expectLater(_connect(host), throwsA(isA<SessionRevoked>()));
    });

    test('an explicit "rejected" with an UNKNOWN future reason string still '
        'revokes', () async {
      // The reason set is open-ended on the wire; the client must not need to
      // know every reason to honour an explicit rejection. (See the DECISION
      // PENDING note above: this is also why a future non-fatal reason would
      // need the client to learn it first.)
      final host = await LoopbackHost.start(
          replies: ['{"auth":"rejected","reason":"expired_v2"}']);
      await expectLater(
        _connect(host),
        throwsA(isA<SessionRevoked>().having((e) => e.message, 'message',
            'authentication rejected: expired_v2')),
      );
    });

    test('an explicit "rejected" with an EMPTY reason string still revokes',
        () async {
      // An empty string is a string: present and well-typed, so a verdict.
      final host = await LoopbackHost.start(
          replies: ['{"auth":"rejected","reason":""}']);
      await expectLater(
        _connect(host),
        throwsA(isA<SessionRevoked>().having((e) => e.message, 'message',
            'authentication rejected: ')),
      );
    });

    test('unknown extra keys on a verdict frame are ignored (the wire evolves '
        'additively)', () async {
      final granted = await LoopbackHost.start(replies: [
        '{"auth":"granted","role":"producer","note":{"a":[1,2]},"extra":null}'
      ]);
      final session = await _connect(granted);
      addTearDown(session.close);
      expect(session.grantedRole, MobileRole.producer);

      final rejected = await LoopbackHost.start(replies: [
        '{"auth":"rejected","reason":"unauthenticated","extra":{"a":1}}'
      ]);
      await expectLater(
        _connect(rejected),
        throwsA(isA<SessionRevoked>().having((e) => e.message, 'message',
            'authentication rejected: unauthenticated')),
      );
    });
  });

  group('pair (pair hello)', () {
    for (final entry in _malformedPairReplies.entries) {
      test('${entry.key} is a malformed SessionException', () async {
        final host = await LoopbackHost.start(replies: [entry.value]);
        await expectLater(_pair(host), throwsA(_malformed()));
        expect(host.hellos, hasLength(1));
        expect(await host.waitClientClosed(1), isTrue,
            reason: 'a failed pairing must not leak its socket');
      });
    }

    test('a malformed reply AFTER the interim "parked" frame is still malformed',
        () async {
      // The host parks the request, then the terminal frame is garbage: the
      // loop that waits through `parked` must not swallow it.
      final host = await LoopbackHost.start(replies: [
        '{"pair":"parked"}',
        '{"pair":"granted","device_id":5,"token":"t","role":"producer"}',
      ]);
      await expectLater(_pair(host), throwsA(_malformed()));
    });

    test('control: parked then granted still pairs and returns the credentials',
        () async {
      final host = await LoopbackHost.start(replies: [
        '{"pair":"parked"}',
        '{"pair":"granted","device_id":"dev-9","token":"t9","role":"viewer"}',
      ]);
      final (session, creds) = await _pair(host);
      addTearDown(session.close);
      expect(creds.deviceId, 'dev-9');
      expect(creds.token, 't9');
      expect(session.grantedRole, MobileRole.viewer);
      expect(host.hellos.single['hello'], 'pair');
    });

    test('control: an explicit "rejected" still reads as the operator\'s answer',
        () async {
      // Not malformed, and not rephrased: the operator said no, and the screen
      // must keep saying so.
      final host = await LoopbackHost.start(
          replies: ['{"pair":"rejected","reason":"forbidden"}']);
      await expectLater(
        _pair(host),
        throwsA(isA<SessionException>().having(
            (e) => e.message, 'message', 'pairing rejected: forbidden')),
      );
    });

    test('an explicit "rejected" with an unknown reason string keeps its '
        'meaning', () async {
      final host = await LoopbackHost.start(
          replies: ['{"pair":"rejected","reason":"newthing"}']);
      await expectLater(
        _pair(host),
        throwsA(isA<SessionException>().having(
            (e) => e.message, 'message', 'pairing rejected: newthing')),
      );
    });

    test('unknown extra keys on parked, granted and rejected frames are '
        'ignored', () async {
      final granted = await LoopbackHost.start(replies: [
        '{"pair":"parked","note":{"a":1}}',
        '{"pair":"granted","device_id":"d9","token":"t9","role":"viewer",'
            '"extra":[1,{"y":2}]}',
      ]);
      final (session, creds) = await _pair(granted);
      addTearDown(session.close);
      expect((creds.deviceId, creds.token), ('d9', 't9'));
      expect(session.grantedRole, MobileRole.viewer);

      final rejected = await LoopbackHost.start(
          replies: ['{"pair":"rejected","reason":"forbidden","extra":[1]}']);
      await expectLater(
        _pair(rejected),
        throwsA(isA<SessionException>().having(
            (e) => e.message, 'message', 'pairing rejected: forbidden')),
      );
    });
  });
}
