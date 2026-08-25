/// Action rejected — MOBILE-2.0-SPEC §4.12, Figma `358:149`.
///
/// The behavioural promise (FR-097) is the load-bearing part: a command lost
/// with the link is **dropped, not queued**. "Rejected" is the honest word, and
/// the surface exists so the operator does not sit waiting for something that
/// will never happen — nor find it happening two minutes later, out of context.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/settings.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/live_tab.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

class _Fake implements ControllerSession {
  _Fake(this.sent);

  final List<String> sent;
  bool dead = false;

  /// Parks the state fetch so a test can stand inside the window where the
  /// socket is back but the host has not been re-read — which is exactly when
  /// the toast is on screen.
  Completer<void>? gate;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    sent.add(cmd['cmd'] as String);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('down');
    final g = gate;
    if (g != null) await g.future;
    return const OperatorStateView(
      planName: 'Sunday',
      items: [
        PlanItemView(
          id: 1,
          kind: 'song',
          title: 'Amazing Grace',
          isLive: false,
          isStaged: false,
        ),
      ],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );
  }

  @override
  Future<void> close() async {}
}

const _stored = StoredSession(
  host: 'booth-mac',
  port: 1,
  pinHex: 'ab',
  deviceId: 'd',
  token: 't',
);

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

/// A healthy controller whose reconnect lands on a session holding its first
/// state fetch open.
({LiveController live, _Fake original, _Fake replacement, List<String> sent})
_rig() {
  final sent = <String>[];
  final original = _Fake(sent);
  final replacement = _Fake(sent)..gate = Completer<void>();
  final live = LiveController(
    session: original,
    stored: _stored,
    connect:
        ({
          required String host,
          required int port,
          required String pinHex,
          required Credentials creds,
        }) async => replacement,
  );
  return (
    live: live,
    original: original,
    replacement: replacement,
    sent: sent,
  );
}

void main() {
  group('the controller', () {
    test('a command lost mid-flight is rejected — never queued (FR-097)',
        () async {
      final rig = _rig();
      addTearDown(rig.live.dispose);
      await pumpEventQueue();
      expect(rig.live.syncing, isFalse, reason: 'baseline: healthy');
      rig.sent.clear();

      // The link dies with the command already on the wire.
      rig.original.dead = true;
      expect(await rig.live.act(cmdGoLive()), CommandOutcome.failed);

      expect(rig.live.rejected, isTrue);
      // Not on the old session, and — the whole point — not replayed onto the
      // new one when it comes up either.
      rig.replacement.gate!.complete();
      await pumpEventQueue();
      expect(rig.sent, isEmpty,
          reason: 'a command replayed after a reconnect fires into a service '
              'that has moved on');
    });

    test('it retires when the link is healthy AND state has been re-read',
        () async {
      final rig = _rig();
      addTearDown(rig.live.dispose);
      await pumpEventQueue();

      rig.original.dead = true;
      await rig.live.act(cmdGoLive());
      expect(rig.live.rejected, isTrue);

      // Socket back — but the snapshot still describes the pre-drop world, so
      // the toast stays: §4.12 says "healthy AND re-read", not "healthy".
      expect(rig.live.reconnecting, isFalse);
      expect(rig.live.syncing, isTrue);
      expect(rig.live.rejected, isTrue);

      rig.replacement.gate!.complete();
      await pumpEventQueue();
      expect(rig.live.syncing, isFalse);
      expect(rig.live.rejected, isFalse);
    });

    test('a control that was ALREADY inert does not claim a rejection',
        () async {
      // The pre-flight `syncing` refusal is a different event: nothing was sent,
      // so nothing was rejected, and the connection banner already explains it.
      // Conflating the two would put "Action rejected" on screen for a button
      // the operator could not have pressed.
      final rig = _rig();
      addTearDown(rig.live.dispose);

      expect(rig.live.syncing, isTrue, reason: 'baseline: never read the host');
      expect(await rig.live.act(cmdGoLive()), CommandOutcome.failed);
      expect(rig.live.rejected, isFalse);
    });

    test('a poll that fails on its own is not a rejection either', () async {
      final rig = _rig();
      addTearDown(rig.live.dispose);
      await pumpEventQueue();

      // The 1s poll losing the link is ambient, not something the operator did.
      rig.original.dead = true;
      await rig.live.refresh();
      await pumpEventQueue();

      expect(rig.live.rejected, isFalse);
      expect(rig.live.syncing, isTrue);
    });
  });

  group('the toast', () {
    Future<LiveController> pumpRejection(
      WidgetTester tester, {
      bool reduceMotion = false,
      Widget Function(LiveController)? below,
    }) async {
      final rig = _rig();
      final settings = SettingsController(
        store: const _NullStore(),
        wakelock: const _NullWakelock(),
        hapticSink: () async {},
        reduceMotion: reduceMotion,
      );
      await tester.pumpWidget(
        SettingsScope(
          settings: settings,
          child: MaterialApp(
            home: Scaffold(
              body: ListenableBuilder(
                listenable: rig.live,
                builder: (context, _) => Column(
                  children: [
                    ConnectionBanner(live: rig.live),
                    if (below != null) Expanded(child: below(rig.live)),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await _settle(tester);
      rig.original.dead = true;
      await rig.live.act(cmdGoLive());
      await _settle(tester);
      return rig.live;
    }

    testWidgets('takes the connection-banner slot and explains the drop', (
      tester,
    ) async {
      final live = await pumpRejection(tester);

      expect(find.byType(ActionRejectedToast), findsOneWidget);
      expect(find.text('Action rejected'), findsOneWidget);
      expect(find.text('Your pairing changed — reconnecting…'), findsOneWidget);
      expect(
        find.textContaining('never queued to fire later out of context'),
        findsOneWidget,
        reason: '"rejected" invites the assumption that it will be retried',
      );
      // The two never coexist — the toast carries its own reconnecting row, so
      // the ambient bar would only repeat it.
      expect(find.textContaining('Reconnecting to the host'), findsNothing);
      expect(find.text('Reconnecting to booth-mac…'), findsOneWidget);

      live.dispose();
    });

    testWidgets('the control that was rejected renders disabled at 40%', (
      tester,
    ) async {
      final live = await pumpRejection(tester, below: (l) => LiveTab(live: l));

      // Disabled, not hidden, and announced with its reason — the same
      // treatment every control gets while the device cannot prove host state.
      final goLive = tester.widget<SelahButton>(
        find.widgetWithText(SelahButton, 'GO LIVE'),
      );
      expect(goLive.onPressed, isNull);
      final opacity = tester.widget<Opacity>(
        find
            .descendant(
              of: find.widgetWithText(SelahButton, 'GO LIVE'),
              matching: find.byType(Opacity),
            )
            .first,
      );
      expect(opacity.opacity, 0.4);

      live.dispose();
    });

    testWidgets('spins while reconnecting', (tester) async {
      final live = await pumpRejection(tester);
      expect(
        find.descendant(
          of: find.byType(ActionRejectedToast),
          matching: find.byType(CircularProgressIndicator),
        ),
        findsOneWidget,
      );
      live.dispose();
    });

    testWidgets('reduced motion turns the spinner into a static ring', (
      tester,
    ) async {
      final live = await pumpRejection(tester, reduceMotion: true);

      expect(
        find.descendant(
          of: find.byType(ActionRejectedToast),
          matching: find.byType(CircularProgressIndicator),
        ),
        findsNothing,
        reason: 'spec §6.7 — the in-app preference, not only the OS setting',
      );
      // Still a ring: it is what makes the row read as "in progress".
      expect(find.text('Reconnecting to booth-mac…'), findsOneWidget);

      live.dispose();
    });

    testWidgets('the OS reduced-motion setting counts too', (tester) async {
      final rig = _rig();
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(disableAnimations: true),
            child: Scaffold(
              body: ListenableBuilder(
                listenable: rig.live,
                builder: (context, _) => ConnectionBanner(live: rig.live),
              ),
            ),
          ),
        ),
      );
      await _settle(tester);
      rig.original.dead = true;
      await rig.live.act(cmdGoLive());
      await _settle(tester);

      expect(find.byType(ActionRejectedToast), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);

      rig.live.dispose();
    });

    testWidgets('it clears itself once the re-sync lands', (tester) async {
      final rig = _rig();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListenableBuilder(
              listenable: rig.live,
              builder: (context, _) => ConnectionBanner(live: rig.live),
            ),
          ),
        ),
      );
      await _settle(tester);
      rig.original.dead = true;
      await rig.live.act(cmdGoLive());
      await _settle(tester);
      expect(find.byType(ActionRejectedToast), findsOneWidget);

      rig.replacement.gate!.complete();
      await _settle(tester);

      // No dismiss control by design (§4.13: "auto on resync") — a banner about
      // a link the operator cannot fix should not ask them to acknowledge it.
      expect(find.byType(ActionRejectedToast), findsNothing);
      expect(find.byType(ConnectionBanner), findsOneWidget);

      rig.live.dispose();
    });
  });
}

class _NullStore implements SettingsStore {
  const _NullStore();
  @override
  Future<String?> read() async => null;
  @override
  Future<void> write(String value) async {}
}

class _NullWakelock implements WakelockControl {
  const _NullWakelock();
  @override
  Future<void> toggle(bool enabled) async {}
}
