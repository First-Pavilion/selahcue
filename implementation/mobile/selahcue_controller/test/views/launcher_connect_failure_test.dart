/// 17tnw2b0vtj — at launch, ANY connect failure must fall through to the Connect
/// screen. The splash used to catch only `SessionException`, so a host that
/// answered the auth handshake with garbage (`FormatException` for non-JSON,
/// `TypeError` for a binary frame) left the splash spinning for ever: the error
/// escaped `_start()` as an unhandled async error and nothing ever navigated.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/main.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/pairing_view.dart';

import '../support/capture_debug_print.dart';

const _stored = StoredSession(
    host: 'host.local', port: 4000, pinHex: 'ab', deviceId: 'd', token: 't');

/// The error `frame as String` throws when the host answers with a binary frame,
/// produced by a real failing cast rather than a hand-made look-alike.
Object _binaryFrameTypeError() {
  try {
    final Object frame = <int>[0, 1, 2];
    return frame as String;
  } on TypeError catch (e) {
    return e;
  }
}

Future<ControllerSession> Function({
  required String host,
  required int port,
  required String pinHex,
  required Credentials creds,
}) _failingWith(Object error) => ({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        throw error;

void _quietWidgetTest(
    String name, Future<void> Function(WidgetTester) body) {
  testWidgets(name, (tester) =>
      captureDebugPrintAsync(<String>[], () => body(tester)));
}

void main() {
  setUp(() {
    // The Launcher reads the stored profile from secure storage first. Serve a
    // stored session so it takes the "reconnect" branch (not the first-run one).
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'read') return jsonEncode(_stored.toJson());
      return null;
    });
  });

  /// Launch the real [Launcher] with a connect that fails as [error], let the
  /// brand moment elapse, and report whether we landed on the Connect screen.
  Future<void> launchFailingWith(WidgetTester tester, Object error) async {
    await tester.pumpWidget(
        MaterialApp(home: Launcher(connect: _failingWith(error))));
    await tester.pump(); // stored profile loads, connect fails
    expect(find.byType(SplashView), findsOneWidget,
        reason: 'baseline: the splash is up while the launch connect runs');

    await tester.pump(const Duration(seconds: 1)); // brand delay (900 ms) ends
    await tester.pump(const Duration(seconds: 1)); // route transition
  }

  /// Unmount, then let the Connect screen's own timers (mDNS browse) expire —
  /// the binding checks for pending timers before tearDown runs.
  Future<void> teardown(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 10));
  }

  group('stored-profile read at launch (17tnw2b0wg3)', () {
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

    for (final missingProfile in [false, true]) {
      _quietWidgetTest(
          missingProfile
              ? 'a missing profile reaches Connect without a reconnect attempt'
              : 'a platform keystore read failure reaches Connect without an '
                  'unhandled error', (tester) async {
        var connects = 0;
        var writes = 0;
        var deletes = 0;
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'write') writes++;
          if (call.method == 'delete') deletes++;
          if (call.method == 'read' && !missingProfile) {
            throw PlatformException(
                code: 'keystore_unavailable', message: 'test read failure');
          }
          return null;
        });
        try {
          await tester.pumpWidget(MaterialApp(
            home: Launcher(connect: ({
              required String host,
              required int port,
              required String pinHex,
              required Credentials creds,
            }) async {
              connects++;
              throw const SessionException('unexpected reconnect attempt');
            }),
          ));
          await tester.pump();
          expect(find.byType(SplashView), findsOneWidget,
              reason: 'the existing brand delay remains in place');

          await tester.pump(const Duration(seconds: 1));
          await tester.pump(const Duration(seconds: 1));

          expect(tester.takeException(), isNull,
              reason: 'an unavailable profile must not escape Launcher._start');
          expect(find.byType(PairingView), findsOneWidget);
          expect(find.byType(SplashView), findsNothing);
          expect(connects, 0,
              reason: 'no readable profile means there are no credentials to use');
          expect(writes, 0);
          expect(deletes, 0,
              reason: 'a failed read must not erase the stored profile');
        } finally {
          await teardown(tester);
        }
      });
    }

    _quietWidgetTest('a valid profile is passed unchanged to reconnect',
        (tester) async {
      var connects = 0;
      Map<String, Object>? observed;
      try {
        await tester.pumpWidget(MaterialApp(
          home: Launcher(connect: ({
            required String host,
            required int port,
            required String pinHex,
            required Credentials creds,
          }) async {
            connects++;
            observed = {
              'host': host,
              'port': port,
              'pin': pinHex,
              'device_id': creds.deviceId,
              'token': creds.token,
            };
            // A controlled connect failure avoids opening a real session. The
            // established connect-failure route has its own sibling checks.
            throw const SessionException('controlled reconnect failure');
          }),
        ));
        await tester.pump();
        expect(connects, 1);
        expect(observed, _stored.toJson());
        expect(find.text('Reconnecting to ${_stored.host}…'), findsOneWidget);

        await tester.pump(const Duration(seconds: 1));
        await tester.pump(const Duration(seconds: 1));
        expect(tester.takeException(), isNull);
        expect(find.byType(PairingView), findsOneWidget);
      } finally {
        await teardown(tester);
      }
    });
  });

  _quietWidgetTest('a FormatException from the launch connect shows Connect, '
      'not a stuck splash', (tester) async {
    await launchFailingWith(tester, const FormatException('not json'));

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  _quietWidgetTest('a TypeError from the launch connect shows Connect, '
      'not a stuck splash', (tester) async {
    await launchFailingWith(tester, _binaryFrameTypeError());

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  _quietWidgetTest('a SessionException (including a revoked device) still shows '
      'Connect', (tester) async {
    // No regression: the case the old catch DID handle must keep working.
    await launchFailingWith(
        tester, const SessionRevoked('authentication rejected: revoked'));

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  _quietWidgetTest('a throwing diagnostic printer still reaches Connect',
      (tester) async {
    final original = debugPrint;
    try {
      try {
        debugPrint = (String? message, {int? wrapWidth}) {
          if (message?.startsWith('connect failed with an unexpected') == true) {
            throw StateError('printer unavailable');
          }
          original(message, wrapWidth: wrapWidth);
        };
        await launchFailingWith(tester, const FormatException('HOST-PAYLOAD'));
      } finally {
        debugPrint = original;
      }
      expect(tester.takeException(), isNull);
      expect(find.byType(PairingView), findsOneWidget);
      expect(find.byType(SplashView), findsNothing);
    } finally {
      await teardown(tester);
    }
  });

  group('recording what the catch-all swallowed', () {
    _quietWidgetTest('an unexpected launch failure is recorded by TYPE and stack '
        'only, never with host-sent text', (tester) async {
      // Falling through to Connect is right, but it must not make a parsing bug
      // invisible. A FormatException's toString() embeds the offending source —
      // text the peer chose — so only the runtime type and a stack are written.
      final printed = <String>[];
      await captureDebugPrintAsync(printed, () async {
        await launchFailingWith(
            tester, const FormatException('HOST-SENT-PAYLOAD'));
        expect(find.byType(PairingView), findsOneWidget);
        await teardown(tester);
      });

      final log = printed.join('\n');
      expect(log, contains('unexpected FormatException'));
      expect(log, isNot(contains('HOST-SENT-PAYLOAD')));
    });

    _quietWidgetTest('an expected failure (revoked) records nothing', (tester) async {
      final printed = <String>[];
      await captureDebugPrintAsync(printed, () async {
        await launchFailingWith(
            tester, const SessionRevoked('authentication rejected: revoked'));
        expect(find.byType(PairingView), findsOneWidget);
        await teardown(tester);
      });

      expect(printed.where((m) => m.contains('unexpected')), isEmpty);
    });
  });
}
