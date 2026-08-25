/// Permission blocked — MOBILE-2.0-SPEC §4.10 / §4.13, Figma `357:218`.
///
/// This sheet is the app's answer to a control that could not be hidden: a
/// server-side denial arriving after an optimistic tap. Two properties matter
/// more than the pixels — it must not cover the emergency chords (§4.13), and it
/// must not offer "Request access", which has no wire command behind it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

/// A host that refuses one named command with a given wire reason and acks the
/// rest — the exact asymmetry the sheet exists for.
class _Fake implements ControllerSession {
  _Fake({
    required this.grantedRole,
    this.denyCmd,
    this.reason = denyReasonForbidden,
  });

  @override
  final MobileRole grantedRole;
  final String? denyCmd;
  final String reason;
  final List<String> sent = [];

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    final name = cmd['cmd'] as String?;
    sent.add(name ?? '?');
    if (name == denyCmd) return Denied(1, reason);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
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

/// The shell's shape in miniature: the connection banner, a content region
/// carrying the sheet, and the emergency strip OUTSIDE it. If the sheet ever
/// reaches past the content region, this harness is where it shows.
Widget _shellShape(LiveController live) => MaterialApp(
  home: Scaffold(
    // Same ListenableBuilder the real shell wraps its body in — without it the
    // harness would never see the controller's state change and every assertion
    // below would fail for a reason that has nothing to do with the sheet.
    body: ListenableBuilder(
      listenable: live,
      builder: (context, _) => Column(
        children: [
          ConnectionBanner(live: live),
          Expanded(
            child: PermissionBlockedHost(
              live: live,
              child: const Center(child: Text('the tab content')),
            ),
          ),
          EmergencyStrip(live: live),
        ],
      ),
    ),
  ),
);

/// Bring a controller up healthy, send [cmd], and render whatever came back.
Future<(LiveController, _Fake)> _pumpDenial(
  WidgetTester tester, {
  required MobileRole role,
  required Map<String, dynamic> cmd,
  String reason = denyReasonForbidden,
}) async {
  final fake = _Fake(
    grantedRole: role,
    denyCmd: cmd['cmd'] as String?,
    reason: reason,
  );
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(_shellShape(live));
  await _settle(tester);
  await live.act(cmd);
  await _settle(tester);
  return (live, fake);
}

void main() {
  group('the controller classifies denials', () {
    test('only `forbidden` raises the sheet', () async {
      final live = LiveController(
        session: _Fake(grantedRole: MobileRole.producer, denyCmd: 'go_live'),
        stored: _stored,
      );
      addTearDown(live.dispose);
      await pumpEventQueue();

      expect(await live.act(cmdGoLive()), CommandOutcome.denied);
      expect(live.blocked, isNotNull);
      expect(live.blocked!.action?.capability, Capability.goLive);
      expect(live.blocked!.role, MobileRole.producer,
          reason: 'the sheet reports the role held AT the refusal');
    });

    test('`bad_request` does NOT — it is a typo, not a role problem', () async {
      final live = LiveController(
        session: _Fake(
          grantedRole: MobileRole.producer,
          denyCmd: 'stage_scripture',
          reason: 'bad_request',
        ),
        stored: _stored,
      );
      addTearDown(live.dispose);
      await pumpEventQueue();

      expect(
        await live.act(cmdStageScripture('Hezekiah 4:12')),
        CommandOutcome.denied,
      );
      expect(live.blocked, isNull,
          reason: '"That\'s not in your role" would simply be false here');
      expect(live.error, contains('bad_request'),
          reason: 'but the operator still has to be told something failed');
    });

    test('dismissing the sheet does not hand the denial back as a banner',
        () async {
      final live = LiveController(
        session: _Fake(grantedRole: MobileRole.viewer, denyCmd: 'go_live'),
        stored: _stored,
      );
      addTearDown(live.dispose);
      await pumpEventQueue();

      await live.act(cmdGoLive());
      expect(live.blocked, isNotNull);
      live.dismissBlocked();

      expect(live.blocked, isNull);
      expect(live.error, isNull, reason: 'one refusal, one dismissal — not two');
    });
  });

  group('the sheet', () {
    testWidgets('names the action, the role that would do it, and the current '
        'role', (tester) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdApproveDetection(7),
      );

      expect(find.byType(PermissionBlockedSheet), findsOneWidget);
      expect(find.text("That's not in your role"), findsOneWidget);
      // The spec's own template, filled from the real backend roles rather than
      // the deferred 7-role design vocabulary (86ajxuf81 / 86ajxufbg).
      expect(
        find.text(
          'Approving scripture needs the Assistant role. '
          "You're signed in as a Viewer.",
        ),
        findsOneWidget,
      );
      live.dispose();
    });

    testWidgets('lists every role that could have run the command', (
      tester,
    ) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdApproveDetection(7),
      );

      expect(find.text('ROLES THAT CAN APPROVE SCRIPTURE'), findsOneWidget);
      expect(find.text('OPERATOR'), findsOneWidget);
      expect(find.text('PRODUCER'), findsOneWidget);
      expect(find.text('ASSISTANT'), findsOneWidget);
      expect(find.text('VIEWER'), findsNothing,
          reason: 'the role that was just refused is not a way out of it');
      live.dispose();
    });

    testWidgets('drops the roles card when it cannot name them', (
      tester,
    ) async {
      // A command a newer host knows and this build does not.
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: {'cmd': 'reset_timer'},
      );

      expect(find.byType(PermissionBlockedSheet), findsOneWidget);
      expect(find.textContaining('ROLES THAT CAN'), findsNothing);
      expect(
        find.text(
          "This control isn't part of your role. Ask your operator on the "
          'desktop.',
        ),
        findsOneWidget,
        reason: 'say less rather than name a role that might not help',
      );
      live.dispose();
    });

    testWidgets('offers Got it and NOT Request access', (tester) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdGoLive(),
      );

      expect(find.widgetWithText(SelahButton, 'Got it'), findsOneWidget);
      // There is no request-access command in the wire protocol. Spec §4.10 says
      // hide it entirely rather than ship a button that closes a sheet and
      // claims something was sent.
      expect(find.textContaining('Request access'), findsNothing);

      await tester.tap(find.widgetWithText(SelahButton, 'Got it'));
      await _settle(tester);
      expect(find.byType(PermissionBlockedSheet), findsNothing);
      expect(live.blocked, isNull);
      live.dispose();
    });

    testWidgets('a scrim tap dismisses it', (tester) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdGoLive(),
      );

      // Top-left of the content region — over the scrim, well clear of the
      // sheet, which is anchored to the bottom.
      await tester.tapAt(const Offset(20, 20));
      await _settle(tester);
      expect(find.byType(PermissionBlockedSheet), findsNothing);
      live.dispose();
    });

    testWidgets('the emergency strip stays reachable behind it (§4.13)', (
      tester,
    ) async {
      final (live, fake) = await _pumpDenial(
        tester,
        role: MobileRole.producer,
        cmd: cmdGoLive(),
      );
      expect(find.byType(PermissionBlockedSheet), findsOneWidget);

      fake.sent.clear();
      // Present, enabled, and it actually fires. An emergency control sitting
      // behind a modal is the single thing UX-CANONICAL §1.2 forbids outright,
      // and asserting the button merely EXISTS would not have caught a scrim
      // stretched one Column level too high.
      final blackout = tester.widget<SelahButton>(
        find.widgetWithText(SelahButton, '■ BLACKOUT'),
      );
      expect(blackout.onPressed, isNotNull);

      await tester.tap(find.widgetWithText(SelahButton, '■ BLACKOUT'));
      await tester.pump();
      await tester.tap(find.widgetWithText(SelahButton, '■ CONFIRM BLACKOUT'));
      await _settle(tester);

      expect(fake.sent, contains('blackout'),
          reason: 'the confirming tap must reach the host through the sheet');
      live.dispose();
    });

    testWidgets('the content behind is dimmed and cannot be tapped through', (
      tester,
    ) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdGoLive(),
      );

      // *measured*: black at 28 % over the tab content.
      final scrim = tester.widget<ColoredBox>(
        find
            .descendant(
              of: find.byType(PermissionBlockedHost),
              matching: find.byType(ColoredBox),
            )
            .first,
      );
      expect(scrim.color.a, closeTo(0.28, 0.005));
      expect(find.text('the tab content'), findsOneWidget,
          reason: 'the operator must still see what they touched');
      live.dispose();
    });

    testWidgets('the banner does not repeat what the sheet already says', (
      tester,
    ) async {
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdGoLive(),
      );

      expect(find.byType(PermissionBlockedSheet), findsOneWidget);
      // One refusal, one surface. A red strip carrying the raw wire reason on
      // top of a sheet explaining it in words is two dismissals for one fact.
      expect(find.textContaining('Not allowed'), findsNothing);

      // And closing the sheet must not hand it back as a banner.
      await tester.tap(find.widgetWithText(SelahButton, 'Got it'));
      await _settle(tester);
      expect(find.textContaining('Not allowed'), findsNothing);

      live.dispose();
    });

    testWidgets('is announced as a route', (tester) async {
      final handle = tester.ensureSemantics();
      final (live, _) = await _pumpDenial(
        tester,
        role: MobileRole.viewer,
        cmd: cmdGoLive(),
      );

      expect(
        find.bySemanticsLabel(RegExp("That's not in your role")),
        findsWidgets,
      );
      handle.dispose();
      live.dispose();
    });
  });

  group('in the shell', () {
    testWidgets('a forbidden denial from a tab raises the sheet over the tab, '
        'not over the whole app', (tester) async {
      final fake = _Fake(
        grantedRole: MobileRole.producer,
        denyCmd: 'select_item',
      );
      await tester.pumpWidget(
        MaterialApp(home: ControllerView(session: fake, stored: _stored)),
      );
      await _settle(tester);

      await tester.tap(find.widgetWithText(NavigationDestination, 'Plan'));
      await _settle(tester);
      // A plan row carries onDoubleTap, so its onTap only resolves once the
      // gesture arena stops waiting for a second tap.
      await tester.tap(find.text('Amazing Grace'));
      await tester.pump(const Duration(milliseconds: 500));
      await _settle(tester);

      expect(find.byType(PermissionBlockedSheet), findsOneWidget);
      // The chrome the sheet must NOT have covered.
      expect(find.byType(EmergencyStrip), findsOneWidget);
      expect(find.byType(NavigationBar), findsOneWidget);

      await tester.pumpWidget(const SizedBox());
    });
  });
}
