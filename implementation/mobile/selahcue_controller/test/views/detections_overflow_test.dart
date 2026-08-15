/// The detection-approval queue must never be able to break the Scripture tab.
///
/// Regression for the overflow bug (86ak188mz): the approval cards used to be an
/// UNBOUNDED, non-flexing sibling of the verse list inside the tab's `Column`.
/// Past ~5 detections they consumed the whole viewport, the `Expanded` verse
/// list was handed negative space, and the tab threw `RenderFlex overflowed` —
/// taking the translation picker and the reference field down with it, mid
/// service. The cards now live on their own scrolling route behind a
/// fixed-height banner, so the tab's children are all bounded again.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/design_tokens.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';
import 'package:selahcue_controller/views/detections_view.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

/// A session whose role and operator view can be changed mid-test, so the host
/// pushing/draining detections (and an admin revoking the device) can be
/// exercised against a route that is already open.
class _Fake implements ControllerSession {
  MobileRole role;
  OperatorStateView state;

  /// When true every call fails, driving the controller into `_reconnect`.
  bool dead = false;

  final List<Map<String, dynamic>> sent = [];

  _Fake({required this.role, required this.state});

  @override
  MobileRole get grantedRole => role;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('dead');
    sent.add(cmd);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('dead');
    return state;
  }

  @override
  Future<void> close() async {}
}

const _stored = StoredSession(
    host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

/// A view carrying [n] pending detections. The text is deliberately long — the
/// two-line ellipsised body is part of what made each card ~100px tall.
OperatorStateView _viewWith(int n) => OperatorStateView(
      planName: 'Sunday',
      items: const [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
      detections: [
        for (var i = 0; i < n; i++)
          DetectionView(
            id: i + 1,
            reference: 'Romans 8:${i + 1}',
            text: 'And we know that all things work together for good to them '
                'that love God, to them who are the called according to his '
                'purpose.',
            confidence: 90 + (i % 10),
          ),
      ],
    );

/// A phone-sized surface (iPhone-13-class, 390x844 logical) — the geometry the
/// bug actually shows up on.
void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1170, 2532);
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

/// Let the constructor's `refresh()` land and the tab settle.
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

/// Advance past a 1s poll so a mutated fake view reaches the widgets.
Future<void> _poll(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 1));
  await tester.pump(const Duration(milliseconds: 60));
  await tester.pump(const Duration(milliseconds: 60));
}

Future<LiveController> _pumpTab(WidgetTester tester, _Fake fake,
    {Future<ControllerSession> Function({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    })? connect}) async {
  final live =
      LiveController(session: fake, stored: _stored, connect: connect);
  await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
  await _settle(tester);
  return live;
}

void main() {
  // On the revoke path the controller awaits `StoredSession.clear()` (secure
  // storage) BEFORE it notifies listeners. Under `testWidgets` the clock is
  // fake, so an unmocked platform channel never delivers its reply and that
  // await never resolves — the revoked state would never reach the widgets.
  // A real device has the plugin and resolves in milliseconds; stand one in so
  // the test exercises production behaviour rather than a missing-plugin stall.
  setUp(() {
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async => null);
  });

  testWidgets('20 pending detections do not overflow the Scripture tab, and the '
      'reference field stays present and hittable', (tester) async {
    _phone(tester);
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.producer, state: _viewWith(20)));

    expect(tester.takeException(), isNull,
        reason: 'the tab must lay out with 20 pending detections');

    // The controls the overflow used to take down with it.
    expect(find.byType(TextField), findsOneWidget);
    await tester.tap(find.byType(TextField));
    await tester.pump();
    expect(tester.takeException(), isNull,
        reason: 'the reference field must still be hittable');

    live.dispose();
  });

  testWidgets('the tab shows a single-line banner, not a stack of cards',
      (tester) async {
    _phone(tester);
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.producer, state: _viewWith(4)));

    expect(find.text('4 verses need approval'), findsOneWidget);
    // The cards themselves are NOT in the tab any more.
    expect(find.text('Approve'), findsNothing);
    expect(find.text('Reject'), findsNothing);

    live.dispose();
  });

  testWidgets('tapping the banner opens the approval route with the detections',
      (tester) async {
    _phone(tester);
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.producer, state: _viewWith(4)));

    await tester.tap(find.text('4 verses need approval'));
    await tester.pumpAndSettle();

    expect(find.byType(DetectionsView), findsOneWidget);
    expect(find.text('Needs your approval'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.widgetWithText(StatusBadge, '4'),
      ),
      findsOneWidget,
    );
    expect(find.text('Romans 8:1'), findsOneWidget);
    expect(find.text('Approve'), findsWidgets);

    live.dispose();
  });

  testWidgets('the approval route scrolls 20 detections without overflowing',
      (tester) async {
    _phone(tester);
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.producer, state: _viewWith(20)));

    await tester.tap(find.text('20 verses need approval'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    // The last detection is reachable by scrolling — nothing is clipped away.
    await tester.dragUntilVisible(
      find.text('Romans 8:20'),
      find.byType(ListView),
      const Offset(0, -300),
    );
    expect(find.text('Romans 8:20'), findsOneWidget);
    expect(tester.takeException(), isNull);

    live.dispose();
  });

  testWidgets('Approve and Reject on the route send the right commands',
      (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(2));
    final live = await _pumpTab(tester, fake);

    await tester.tap(find.text('2 verses need approval'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Approve').first);
    await tester.pump();
    expect(
        fake.sent.any((c) =>
            c['cmd'] == 'approve_detection' && c['detection_id'] == 1),
        isTrue);

    await tester.tap(find.text('Reject').last);
    await tester.pump();
    expect(
        fake.sent.any((c) =>
            c['cmd'] == 'dismiss_detection' && c['detection_id'] == 2),
        isTrue);

    live.dispose();
  });

  testWidgets('draining the last detection shows "All caught up" and keeps the '
      'route open', (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(2));
    final live = await _pumpTab(tester, fake);

    await tester.tap(find.text('2 verses need approval'));
    await tester.pumpAndSettle();
    expect(find.byType(DetectionsView), findsOneWidget);

    // The host clears the queue while the operator is standing on this route.
    fake.state = _viewWith(0);
    await _poll(tester);
    await tester.pumpAndSettle();

    expect(find.text('All caught up'), findsOneWidget);
    // Never yank navigation out from under an operator's thumb mid-service.
    expect(find.byType(DetectionsView), findsOneWidget);
    expect(tester.takeException(), isNull);

    live.dispose();
  });

  testWidgets('the route closes itself when the role loses scripture access',
      (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(3));
    final live = await _pumpTab(tester, fake);

    await tester.tap(find.text('3 verses need approval'));
    await tester.pumpAndSettle();
    expect(find.byType(DetectionsView), findsOneWidget);

    // A reconnect re-roles the device down to Viewer (no SearchScripture).
    fake.role = MobileRole.viewer;
    await _poll(tester);
    await tester.pumpAndSettle();

    expect(live.can(Capability.searchScripture), isFalse);
    expect(find.byType(DetectionsView), findsNothing);

    live.dispose();
  });

  testWidgets('the route closes itself when the device is revoked',
      (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(3));
    Future<ControllerSession> revokedConnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        throw const SessionRevoked('authentication rejected: revoked');

    final live = await _pumpTab(tester, fake, connect: revokedConnect);

    await tester.tap(find.text('3 verses need approval'));
    await tester.pumpAndSettle();
    expect(find.byType(DetectionsView), findsOneWidget);

    // An admin revokes the device: the next poll fails, the reconnect is
    // rejected outright, and the approval route must not linger on top.
    fake.dead = true;
    await _poll(tester);
    await tester.pumpAndSettle();

    expect(live.revoked, isTrue);
    expect(find.byType(DetectionsView), findsNothing);

    live.dispose();
  });

  testWidgets('the route carries its own EmergencyStrip — the always-on '
      'Blackout/Clear invariant survives being pushed over', (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(3));
    final live = await _pumpTab(tester, fake);

    await tester.tap(find.text('3 verses need approval'));
    await tester.pumpAndSettle();

    // Present…
    expect(find.byType(EmergencyStrip), findsOneWidget);
    expect(find.text('■ BLACKOUT'), findsOneWidget);

    // …and operable: arm, then confirm, and the command actually goes.
    await tester.tap(find.text('■ BLACKOUT'));
    await tester.pump();
    await tester.tap(find.text('■ CONFIRM BLACKOUT'));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'blackout'), isTrue,
        reason: 'an operator must be able to black out from this screen');

    live.dispose();
  });

  testWidgets('a role with neither emergency capability gets no empty strip',
      (tester) async {
    _phone(tester);
    // Assistant holds searchScripture (so the route is legal) but neither
    // blackout nor clearLive.
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.assistant, state: _viewWith(2)));

    await tester.tap(find.text('2 verses need approval'));
    await tester.pumpAndSettle();

    expect(find.byType(DetectionsView), findsOneWidget);
    expect(find.byType(EmergencyStrip), findsNothing);

    live.dispose();
  });

  testWidgets('while reconnecting the route explains itself and Approve/Reject '
      'are disabled', (tester) async {
    _phone(tester);
    final fake = _Fake(role: MobileRole.producer, state: _viewWith(2));
    Future<ControllerSession> hangingConnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        throw const SessionException('still down');

    final live = await _pumpTab(tester, fake, connect: hangingConnect);

    await tester.tap(find.text('2 verses need approval'));
    await tester.pumpAndSettle();
    final before = fake.sent.length;

    // The link drops while the operator is on the approvals screen.
    fake.dead = true;
    await _poll(tester);

    expect(live.reconnecting, isTrue);
    // The route covers ControllerView's banner, so it must carry its own.
    expect(find.textContaining('Reconnecting to the host'), findsOneWidget);

    // Tapping Approve must not silently do nothing — the button is disabled.
    final approve = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Approve').first);
    expect(approve.onPressed, isNull,
        reason: 'a silent no-op is worse than a greyed button');

    await tester.tap(find.text('Approve').first, warnIfMissed: false);
    await tester.pump();
    expect(fake.sent.length, before,
        reason: 'no command may be sent while live state is unknown');

    live.dispose();
    // The reconnect loop sleeps 2s between attempts; let that timer retire so
    // the binding does not report it as pending.
    await tester.pump(const Duration(seconds: 3));
  });

  testWidgets('the banner grows with the text scale instead of clipping, and '
      'stays the same height as the detection count climbs', (tester) async {
    _phone(tester);

    Future<double> bannerHeight(int detections, double scale) async {
      final live = LiveController(
          session: _Fake(role: MobileRole.producer, state: _viewWith(detections)),
          stored: _stored);
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
      await _settle(tester);
      expect(tester.takeException(), isNull);
      final h = tester
          .getSize(find.text('$detections verses need approval'))
          .height;
      final box = tester.getSize(find.ancestor(
          of: find.text('$detections verses need approval'),
          matching: find.byType(InkWell)));
      // Unmount BEFORE disposing: tearing down the notifier under a still-
      // mounted tab makes the next pumpWidget throw during unmount.
      await tester.pumpWidget(const SizedBox());
      live.dispose();
      // The label must fit inside its container — no clipped glyphs.
      expect(box.height, greaterThanOrEqualTo(h));
      return box.height;
    }

    final small = await bannerHeight(4, 1.0);
    final large = await bannerHeight(4, 2.0);
    final manyLarge = await bannerHeight(40, 2.0);

    expect(small, greaterThanOrEqualTo(48.0),
        reason: 'the banner is a 48dp touch target');
    expect(large, greaterThan(small),
        reason: 'a hard pixel height would clip the label at 2.0 instead');
    expect(manyLarge, large,
        reason: 'height must be constant in the detection count');
  });

  testWidgets('Approve/Reject clear 48dp and stack at a large text scale',
      (tester) async {
    _phone(tester);

    // Disposed inside the test body, not via addTearDown: teardown runs after
    // the binding's pending-timer check, so a live 1s poll would fail the test.
    LiveController? current;
    Future<void> pumpAt(double scale) async {
      // Reset the tree first: pumping another MaterialApp of the same shape
      // reuses the element tree, so the previously pushed (opaque) route would
      // still be on the Navigator, hiding the tab underneath it.
      await tester.pumpWidget(const SizedBox());
      current?.dispose();
      final live = LiveController(
          session: _Fake(role: MobileRole.producer, state: _viewWith(2)),
          stored: _stored);
      current = live;
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
      await _settle(tester);
      await tester.tap(find.text('2 verses need approval'));
      await tester.pumpAndSettle();
    }

    Rect approve() =>
        tester.getRect(find.widgetWithText(FilledButton, 'Approve').first);
    Rect reject() =>
        tester.getRect(find.widgetWithText(OutlinedButton, 'Reject').first);

    // 1.29 → side by side: the two share a row (their vertical extents overlap)
    // and Reject sits to the right of Approve.
    await pumpAt(1.29);
    expect(reject().top, lessThan(approve().bottom));
    expect(reject().left, greaterThan(approve().left));
    expect(approve().height, greaterThanOrEqualTo(48.0),
        reason: 'Approve must clear the 48dp touch target');
    expect(reject().height, greaterThanOrEqualTo(48.0),
        reason: 'Reject must clear the 48dp touch target');
    expect(tester.takeException(), isNull);

    // 1.30 → stacked: Reject drops entirely below Approve, both full width, so
    // neither label can be squeezed into an overflow.
    await pumpAt(1.30);
    expect(reject().top, greaterThanOrEqualTo(approve().bottom));
    expect(reject().left, approve().left);
    expect(approve().height, greaterThanOrEqualTo(48.0));
    expect(reject().height, greaterThanOrEqualTo(48.0));
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox());
    current?.dispose();
  });

  testWidgets('the app bar count survives a large text scale — the words '
      'truncate, not the number', (tester) async {
    _phone(tester);
    final live = LiveController(
        session: _Fake(role: MobileRole.producer, state: _viewWith(7)),
        stored: _stored);
    tester.platformDispatcher.textScaleFactorTestValue = 3.0;
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
    await _settle(tester);
    await tester.tap(find.text('7 verses need approval'));
    await tester.pumpAndSettle();

    // The count is a pill outside the ellipsised title, so it is still there.
    expect(
      find.descendant(
        of: find.byType(AppBar),
        matching: find.widgetWithText(StatusBadge, '7'),
      ),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    live.dispose();
  });

  testWidgets('the confidence badge does not use the green "staged" ink',
      (tester) async {
    _phone(tester);
    final live = await _pumpTab(
        tester, _Fake(role: MobileRole.producer, state: _viewWith(1)));
    await tester.tap(find.text('1 verse needs approval'));
    await tester.pumpAndSettle();

    final style = tester.widget<Text>(find.text('90% MATCH')).style!;
    // Green means "preview / staged" everywhere else in the app; this card's
    // whole point is that the verse is NOT staged yet.
    expect(style.color, isNot(DesignTokens.previewInk));
    expect(style.color, DesignTokens.textMuted);
    live.dispose();
  });

  testWidgets('the Scripture tab icon carries the pending count', (tester) async {
    _phone(tester);
    await tester.pumpWidget(MaterialApp(
      home: ControllerView(
        session: _Fake(role: MobileRole.producer, state: _viewWith(4)),
        stored: _stored,
      ),
    ));
    await _settle(tester);

    final badge = find.descendant(
      of: find.byType(NavigationBar),
      matching: find.widgetWithText(Badge, '4'),
    );
    expect(badge, findsAtLeastNWidgets(1),
        reason: 'pending approvals must be visible from every tab');
    expect(tester.widget<Badge>(badge.first).backgroundColor,
        DesignTokens.warnFill);

    await tester.pumpWidget(const SizedBox()); // dispose → cancel the 1s poll
  });

  testWidgets('no pending detections means no count badge', (tester) async {
    _phone(tester);
    await tester.pumpWidget(MaterialApp(
      home: ControllerView(
        session: _Fake(role: MobileRole.producer, state: _viewWith(0)),
        stored: _stored,
      ),
    ));
    await _settle(tester);

    expect(
      find.descendant(
        of: find.byType(NavigationBar),
        matching: find.widgetWithText(Badge, '0'),
      ),
      findsNothing,
    );

    await tester.pumpWidget(const SizedBox());
  });
}
