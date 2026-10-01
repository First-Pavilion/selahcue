/// 17tnw2b0vtj — at launch, ANY connect failure must fall through to the Connect
/// screen. The splash used to catch only `SessionException`, so a host that
/// answered the auth handshake with garbage (`FormatException` for non-JSON,
/// `TypeError` for a binary frame) left the splash spinning for ever: the error
/// escaped `_start()` as an unhandled async error and nothing ever navigated.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart' show DebugPrintCallback;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/main.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/pairing_view.dart';

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

  testWidgets('a FormatException from the launch connect shows Connect, '
      'not a stuck splash', (tester) async {
    await launchFailingWith(tester, const FormatException('not json'));

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  testWidgets('a TypeError from the launch connect shows Connect, '
      'not a stuck splash', (tester) async {
    await launchFailingWith(tester, _binaryFrameTypeError());

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  testWidgets('a SessionException (including a revoked device) still shows '
      'Connect', (tester) async {
    // No regression: the case the old catch DID handle must keep working.
    await launchFailingWith(
        tester, const SessionRevoked('authentication rejected: revoked'));

    expect(find.byType(PairingView), findsOneWidget);
    expect(find.byType(SplashView), findsNothing);
    await teardown(tester);
  });

  group('recording what the catch-all swallowed', () {
    /// Run [body] with `debugPrint` captured into [sink]. Restored BEFORE the
    /// test body returns, not in tearDown: flutter_test's invariant check runs
    /// ahead of tearDown and fails a test that leaves a foundation debug
    /// variable changed.
    Future<void> capturing(
        List<String> sink, Future<void> Function() body) async {
      final DebugPrintCallback original = debugPrint;
      debugPrint = (String? message, {int? wrapWidth}) {
        if (message != null) sink.add(message);
      };
      try {
        await body();
      } finally {
        debugPrint = original;
      }
    }

    testWidgets('an unexpected launch failure is recorded by TYPE and stack '
        'only, never with host-sent text', (tester) async {
      // Falling through to Connect is right, but it must not make a parsing bug
      // invisible. A FormatException's toString() embeds the offending source —
      // text the peer chose — so only the runtime type and a stack are written.
      final printed = <String>[];
      await capturing(printed, () async {
        await launchFailingWith(
            tester, const FormatException('HOST-SENT-PAYLOAD'));
        expect(find.byType(PairingView), findsOneWidget);
        await teardown(tester);
      });

      final log = printed.join('\n');
      expect(log, contains('unexpected FormatException'));
      expect(log, isNot(contains('HOST-SENT-PAYLOAD')));
    });

    testWidgets('an expected failure (revoked) records nothing', (tester) async {
      final printed = <String>[];
      await capturing(printed, () async {
        await launchFailingWith(
            tester, const SessionRevoked('authentication rejected: revoked'));
        expect(find.byType(PairingView), findsOneWidget);
        await teardown(tester);
      });

      expect(printed.where((m) => m.contains('unexpected')), isEmpty);
    });
  });
}
