/// Role changed — live. MOBILE-2.0-SPEC §4.11, Figma `358:128`.
///
/// The hard requirement here is FR-090: the controls go **immediately**, and the
/// banner is a receipt for that, never the mechanism. So the tests assert the
/// disappearance first and the explanation second — in that order, because a
/// build that showed the banner while leaving a stale GO LIVE under the
/// operator's thumb would be worse than one that showed nothing.
library;

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

class _Fake implements ControllerSession {
  _Fake(this.grantedRole);

  /// Mutable on purpose: the desktop's `SetSessionRole` mutates the session
  /// registry and `server.rs` re-derives authority per request, so a re-role
  /// lands on the connection that is ALREADY OPEN. A fake with a final grant
  /// can only ever model the reconnect path, which is how an in-place re-role
  /// stayed invisible behind a green suite.
  @override
  MobileRole grantedRole;
  bool dead = false;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('down');
    return const OperatorStateView(
      planName: 'Sunday',
      items: [],
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

/// A controller whose next reconnect lands on a session granting [to].
(LiveController, _Fake) _pair(MobileRole from, MobileRole to) {
  final original = _Fake(from);
  final replacement = _Fake(to);
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
  return (live, original);
}

/// Drop the link and let the host hand back the re-roled session — ONE of the
/// two ways a re-role reaches this device (the other, and the commoner one, is
/// in place on the open socket; see the last two groups). Plain-`test` flavour
/// (real async).
Future<LiveController> _reRole(MobileRole from, MobileRole to) async {
  final (live, original) = _pair(from, to);
  await pumpEventQueue();
  original.dead = true;
  await live.refresh();
  await pumpEventQueue();
  return live;
}

/// Same, inside a widget test: the tree is built FIRST (the operator is looking
/// at the app when their role changes), and the fake clock is advanced with the
/// tester — `pumpEventQueue` never fires a `Timer.run` under it, which is how
/// the reconnect finishes its re-read.
Future<LiveController> _reRoleInTree(
  WidgetTester tester,
  MobileRole from,
  MobileRole to, {
  Duration autoDismiss = const Duration(seconds: 20),
}) async {
  final (live, original) = _pair(from, to);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ListenableBuilder(
          listenable: live,
          builder: (context, _) {
            final change = live.roleChange;
            // "gone" stands in for the rest of the app: before the re-role and
            // after the banner retires, this slot holds no banner at all.
            if (change == null) return const Text('gone');
            return RoleChangedBanner(
              live: live,
              change: change,
              autoDismiss: autoDismiss,
            );
          },
        ),
      ),
    ),
  );
  await _settle(tester);
  original.dead = true;
  await live.refresh();
  await _settle(tester);
  return live;
}

void main() {
  group('the controller diffs the grant across a reconnect', () {
    test('a downgrade is reported with exactly the capabilities lost', () async {
      final live = await _reRole(MobileRole.producer, MobileRole.viewer);
      addTearDown(live.dispose);

      final change = live.roleChange;
      expect(change, isNotNull);
      expect(change!.from, MobileRole.producer);
      expect(change.to, MobileRole.viewer);
      expect(change.isDowngrade, isTrue);
      expect(
        change.removed,
        MobileRole.producer.capabilities.difference(
          MobileRole.viewer.capabilities,
        ),
      );
      expect(change.removed, isNot(contains(Capability.monitor)),
          reason: 'a Viewer keeps monitoring — it was never taken away');
    });

    test('the controls are gone the instant the grant lands (FR-090)',
        () async {
      final live = await _reRole(MobileRole.producer, MobileRole.viewer);
      addTearDown(live.dispose);

      // Not "after the banner is dismissed", not "on the next poll".
      expect(live.role, MobileRole.viewer);
      expect(live.can(Capability.goLive), isFalse);
      expect(live.can(Capability.blackout), isFalse);
      expect(live.can(Capability.timer), isFalse);
      expect(live.can(Capability.monitor), isTrue);
    });

    test('an upgrade is reported too, with nothing in the removed set',
        () async {
      final live = await _reRole(MobileRole.viewer, MobileRole.producer);
      addTearDown(live.dispose);

      // Silently handing someone MORE authority mid-service is also news.
      expect(live.roleChange?.isDowngrade, isFalse);
      expect(live.roleChange!.removed, isEmpty);
      expect(live.roleChange!.gained, contains(Capability.goLive));
    });

    test('a reconnect that keeps the role reports nothing', () async {
      final live = await _reRole(MobileRole.producer, MobileRole.producer);
      addTearDown(live.dispose);

      expect(live.roleChange, isNull,
          reason: 'a plain reconnect is not an access change');
    });

    test('a second re-role replaces the first — the state never accumulates',
        () async {
      final live = await _reRole(MobileRole.producer, MobileRole.assistant);
      addTearDown(live.dispose);
      expect(live.roleChange!.to, MobileRole.assistant);

      // No queue, no history: one slot, replaced.
      live.dismissRoleChange();
      expect(live.roleChange, isNull);
    });
  });

  group('the banner', () {
    testWidgets('names the new role and lists the controls that just went', (
      tester,
    ) async {
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);

      expect(find.text('Your role changed → Viewer'), findsOneWidget);
      expect(
        find.text(
          'An admin updated your access · live controls were removed just now.',
        ),
        findsOneWidget,
      );
      expect(find.text('PREVIOUS CONTROLS'), findsOneWidget);
      expect(find.text('Go live'), findsOneWidget);
      expect(find.text('Blackout'), findsOneWidget);
      expect(find.text('Service timer'), findsOneWidget);
      expect(find.text('removed'), findsWidgets);
      // A Viewer still monitors, so the reassurance is true and shown — the
      // transcript included. `Capability.transcribe` is a WRITE grant
      // (`IngestTranscript` only, `selahcue-lan/src/rbac.rs:127`); READING the
      // transcript rides in `GetOperatorState`, which needs only `Monitor`.
      expect(
        find.text('You can still watch previews & the transcript.'),
        findsOneWidget,
      );
      // …which is why the removed row may not be called "Transcript". Labelled
      // that way, this receipt said the transcript was gone directly above a
      // promise that it was not.
      expect(find.text('Live transcription feed'), findsOneWidget);
      expect(find.text('Transcript'), findsNothing,
          reason: 'a Viewer keeps the transcript — only the FEED was removed');

      live.dispose();
    });

    testWidgets('the receipt rows are a record, not controls', (tester) async {
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);

      // 50 % (*measured*) AND no gesture. Half-opacity on something tappable
      // would read as "disabled, try again later", which is the opposite of
      // what happened.
      final row = find.ancestor(
        of: find.text('Go live'),
        matching: find.byType(Opacity),
      );
      expect(tester.widget<Opacity>(row.first).opacity, 0.5);
      expect(
        find.descendant(
          of: find.ancestor(
            of: find.text('Go live'),
            matching: find.byType(Container),
          ),
          matching: find.byType(InkWell),
        ),
        findsNothing,
      );

      live.dispose();
    });

    testWidgets('an upgrade says so instead of claiming a removal', (
      tester,
    ) async {
      final live = await _reRoleInTree(tester, MobileRole.viewer, MobileRole.producer);

      expect(find.text('Your role changed → Producer'), findsOneWidget);
      expect(find.textContaining('were removed just now'), findsNothing);
      expect(find.text('PREVIOUS CONTROLS'), findsNothing,
          reason: 'there is no receipt when nothing was taken');

      live.dispose();
    });

    testWidgets('an unrecognised grant gets no false reassurance', (
      tester,
    ) async {
      // `unknown` fails closed to no capabilities — there would be nothing left
      // to watch, so "you can still watch previews" would be a lie.
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.unknown);

      expect(find.text('PREVIOUS CONTROLS'), findsOneWidget);
      expect(
        find.text('You can still watch previews & the transcript.'),
        findsNothing,
      );


      live.dispose();
    });

    testWidgets('a tap dismisses it', (tester) async {
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);

      await tester.tap(find.text('Dismiss'));
      await _settle(tester);

      expect(find.text('gone'), findsOneWidget);
      expect(live.roleChange, isNull);

      live.dispose();
    });

    testWidgets('it retires itself on the injected window, leaving no timer', (
      tester,
    ) async {
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);
      expect(find.text('Your role changed → Viewer'), findsOneWidget);

      await tester.pump(const Duration(seconds: 19));
      expect(find.text('gone'), findsNothing, reason: 'still inside the window');

      await tester.pump(const Duration(seconds: 2));
      expect(find.text('gone'), findsOneWidget);
      expect(live.roleChange, isNull);

      // If the auto-dismiss timer outlived the widget, the binding's
      // pending-timer invariant fails this test on the way out. That is the
      // assertion — nothing further is needed.
      live.dispose();
    });

    testWidgets('a banner disposed early cancels its timer', (tester) async {
      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);

      // Torn down long before the 20 s window — the common case when the
      // operator navigates away, and the one that leaks if dispose forgets.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 25));

      live.dispose();
    });

    testWidgets('announces assertively for assistive tech', (tester) async {
      final announcements = <Map<Object?, Object?>>[];
      tester.binding.defaultBinaryMessenger.setMockDecodedMessageHandler<
        dynamic
      >(SystemChannels.accessibility, (message) async {
        if (message is Map) announcements.add(message);
        return null;
      });
      addTearDown(
        () => tester.binding.defaultBinaryMessenger
            .setMockDecodedMessageHandler<dynamic>(
              SystemChannels.accessibility,
              null,
            ),
      );

      final live = await _reRoleInTree(tester, MobileRole.producer, MobileRole.viewer);

      final announce = announcements.firstWhere(
        (m) => m['type'] == 'announce',
        orElse: () => const {},
      );
      expect(announce, isNotEmpty, reason: 'a silent role change is a trap');
      final data = announce['data']! as Map<Object?, Object?>;
      expect(data['message'], contains('Your role changed to Viewer'));
      expect(data['message'], contains('Go live'));
      expect(data['message'], contains('Live transcription feed'),
          reason: 'spoken aloud, "Transcript removed" would be the same lie');
      // Polite would wait for a gap a live service may never give.
      expect(data['assertiveness'], Assertiveness.assertive.index);

      live.dispose();
    });
  });

  group('a re-role that lands on the LIVE socket', () {
    /// Any reconnect here is a bug in the test's premise, not a path under
    /// test: the link never breaks, so `_connect` must never be reached.
    Future<ControllerSession> never({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async => throw StateError('reconnected — the socket never dropped');

    test('the running poll notices it, with no reconnect at all', () async {
      final session = _Fake(MobileRole.producer);
      final live =
          LiveController(session: session, stored: _stored, connect: never);
      addTearDown(live.dispose);
      await pumpEventQueue();
      expect(live.roleChange, isNull, reason: 'nothing has changed yet');

      // The admin demotes the device from the Remote Control console. No
      // handshake, no dropped link — the same socket, re-authorised.
      session.grantedRole = MobileRole.viewer;
      await live.refresh();
      await pumpEventQueue();

      final change = live.roleChange;
      expect(change, isNotNull,
          reason: 'an in-place re-role is exactly as much news as one carried '
              'by a reconnect');
      expect(change!.from, MobileRole.producer);
      expect(change.to, MobileRole.viewer);
      expect(change.isDowngrade, isTrue);
    });

    test('the gate moves with it (FR-090) — immediately, not on reconnect',
        () async {
      final session = _Fake(MobileRole.producer);
      final live =
          LiveController(session: session, stored: _stored, connect: never);
      addTearDown(live.dispose);
      await pumpEventQueue();
      expect(live.can(Capability.goLive), isTrue);

      session.grantedRole = MobileRole.viewer;
      await live.refresh();
      await pumpEventQueue();

      expect(live.role, MobileRole.viewer);
      expect(live.can(Capability.goLive), isFalse);
      expect(live.can(Capability.blackout), isFalse);
      expect(live.can(Capability.timer), isFalse);
      expect(live.can(Capability.monitor), isTrue);
    });

    test('a command dispatched after the re-role is judged against the NEW role',
        () async {
      final session = _Fake(MobileRole.producer);
      final live =
          LiveController(session: session, stored: _stored, connect: never);
      addTearDown(live.dispose);
      await pumpEventQueue();

      session.grantedRole = MobileRole.viewer;
      // No poll in between: act() takes its own reading, so the enforcement
      // sheet can never name a role the operator has already lost.
      await live.act(cmdGoLive());
      await pumpEventQueue();

      expect(live.role, MobileRole.viewer);
      expect(live.roleChange?.to, MobileRole.viewer);
    });
  });

  group('in the shell', () {
    testWidgets('an in-place re-role takes the controls and raises the '
        'receipt on the next poll', (tester) async {
      final session = _Fake(MobileRole.producer);
      await tester.pumpWidget(
        MaterialApp(
          home: ControllerView(
            session: session,
            stored: _stored,
            connect:
                ({
                  required String host,
                  required int port,
                  required String pinHex,
                  required Credentials creds,
                }) async =>
                    throw StateError('reconnected — the socket never dropped'),
          ),
        ),
      );
      await _settle(tester);
      expect(find.widgetWithText(NavigationDestination, 'Scripture'),
          findsOneWidget);
      expect(find.byType(EmergencyStrip), findsOneWidget);

      // The link stays up throughout: `dead` is never set.
      session.grantedRole = MobileRole.viewer;
      await tester.pump(const Duration(seconds: 1));
      await _settle(tester);

      expect(find.byType(RoleChangedBanner), findsOneWidget,
          reason: 'the operator is told WHY their controls went');
      expect(find.widgetWithText(NavigationDestination, 'Scripture'),
          findsNothing);
      expect(find.byType(EmergencyStrip), findsNothing,
          reason: 'a Viewer holds neither blackout nor clear');

      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('the removed tab and controls are gone while the receipt '
        'explains them', (tester) async {
      final original = _Fake(MobileRole.producer);
      final replacement = _Fake(MobileRole.viewer);
      await tester.pumpWidget(
        MaterialApp(
          home: ControllerView(
            session: original,
            stored: _stored,
            connect:
                ({
                  required String host,
                  required int port,
                  required String pinHex,
                  required Credentials creds,
                }) async => replacement,
          ),
        ),
      );
      await _settle(tester);
      expect(find.widgetWithText(NavigationDestination, 'Scripture'),
          findsOneWidget);

      original.dead = true;
      await _settle(tester);
      await tester.pump(const Duration(seconds: 1));
      await _settle(tester);

      expect(find.byType(RoleChangedBanner), findsOneWidget);
      // The tab row rebuilt from the new grant BEFORE the operator read a word
      // of the banner — that ordering is FR-090.
      expect(find.widgetWithText(NavigationDestination, 'Scripture'),
          findsNothing);
      expect(find.byType(EmergencyStrip), findsNothing,
          reason: 'a Viewer holds neither blackout nor clear');

      await tester.pumpWidget(const SizedBox());
    });
  });
}
