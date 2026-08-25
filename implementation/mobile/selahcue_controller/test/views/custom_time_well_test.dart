/// The HH:MM:SS custom-time well (MOBILE-2.0-SPEC §4.6, Figma `367:126`).
///
/// The point of the change is that the shipped minutes-only field could not
/// express an hour, so the first thing asserted is that an hour survives the
/// round trip to `start_timer` — the rest guards the entry rules that make that
/// safe on a touch screen mid-service.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/models/selah_theme.dart';
import 'package:selahcue_controller/views/tabs/timer_tab.dart';
import 'package:selahcue_controller/views/widgets/custom_time_well.dart';
import 'package:selahcue_controller/views/widgets/primitives.dart';

class _Fake implements ControllerSession {
  _Fake({this.denyCmd, this.deadCmd});

  /// The one command this host refuses on role grounds, if any.
  final String? denyCmd;

  /// The one command that takes the link down with it, if any.
  final String? deadCmd;

  @override
  final MobileRole grantedRole = MobileRole.producer;
  final List<Map<String, dynamic>> sent = [];

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    if (cmd['cmd'] == deadCmd) throw const SessionException('down');
    if (cmd['cmd'] == denyCmd) return const Denied(1, 'forbidden');
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
    planName: 'S',
    items: [],
    liveIndex: null,
    stagedIndex: null,
    blackout: false,
    timer: null,
  );

  @override
  Future<void> close() async {}
}

const _stored = StoredSession(
  host: 'h',
  port: 1,
  pinHex: 'ab',
  deviceId: 'd',
  token: 't',
);

Future<LiveController> _pumpTab(
  WidgetTester tester,
  _Fake fake, {
  Future<ControllerSession> Function({
    required String host,
    required int port,
    required String pinHex,
    required Credentials creds,
  })? connect,
}) async {
  final live =
      LiveController(session: fake, stored: _stored, connect: connect);
  await tester.pumpWidget(
    MaterialApp(home: Scaffold(body: TimerTab(live: live))),
  );
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

/// The three pairs are laid out left to right, so position IS the identity —
/// no test-only keys needed in the widget.
const _pairIndex = {'HOURS': 0, 'MIN': 1, 'SEC': 2};

Finder _pairs(Type of) =>
    find.descendant(of: find.byType(CustomTimeWell), matching: find.byType(of));

/// Type [digits] into the pair sitting under [unit], ONE KEY AT A TIME.
///
/// `enterText` replaces the whole value in a single edit, which is a paste, not
/// typing — and the two go through the clamp formatter differently ("60" pasted
/// is rejected whole; "6" then "60" leaves "6"). A keypad produces the second,
/// so the tests drive the second.
Future<void> _enter(WidgetTester tester, String unit, String digits) async {
  final field = _pairs(TextField).at(_pairIndex[unit]!);
  for (var i = 1; i <= digits.length; i++) {
    await tester.enterText(field, digits.substring(0, i));
  }
  await tester.pump();
}

void main() {
  testWidgets('the well shows three labelled pairs with colon separators', (
    tester,
  ) async {
    final live = await _pumpTab(tester, _Fake());

    expect(find.text('HOURS'), findsOneWidget);
    expect(find.text('MIN'), findsOneWidget);
    expect(find.text('SEC'), findsOneWidget);
    expect(find.text(':'), findsNWidgets(2));
    expect(find.byType(CustomTimeWell), findsOneWidget);

    live.dispose();
  });

  testWidgets('an hour survives the round trip — the whole point of the change',
      (tester) async {
    final fake = _Fake();
    final live = await _pumpTab(tester, fake);

    await _enter(tester, 'HOURS', '1');
    await _enter(tester, 'MIN', '05');
    await _enter(tester, 'SEC', '30');
    await tester.tap(find.widgetWithText(SelahButton, 'Start'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(
      fake.sent.where((c) => c['cmd'] == 'start_timer').single,
      {'cmd': 'start_timer', 'seconds': 3930},
      reason: '1:05:30 is 3930s — the minutes-only field could not say this',
    );
    live.dispose();
  });

  testWidgets('Start is inert until something is typed, and clears after',
      (tester) async {
    final fake = _Fake();
    final live = await _pumpTab(tester, fake);

    SelahButton start() =>
        tester.widget(find.widgetWithText(SelahButton, 'Start'));

    expect(start().onPressed, isNull,
        reason: 'an empty well would start a 0-second timer');
    expect(start().disabledReason, 'set a time first');

    await _enter(tester, 'MIN', '20');
    expect(start().onPressed, isNotNull);

    await tester.tap(find.widgetWithText(SelahButton, 'Start'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(fake.sent.single['seconds'], 1200);
    // Cleared, so the next start is a deliberate re-entry rather than an
    // accidental repeat of the last one.
    expect(start().onPressed, isNull);
    live.dispose();
  });

  // The well is the only control in the app that holds operator INPUT rather
  // than mirroring host state, so it is the only one where a lost command costs
  // something that cannot be re-derived. `act()` reports what actually happened
  // (86ajxwcft); these two assert the well listens to the answer.
  testWidgets('a refused start keeps the digits — nothing typed is thrown away',
      (tester) async {
    final fake = _Fake(denyCmd: 'start_timer');
    final live = await _pumpTab(tester, fake);

    SelahButton start() =>
        tester.widget(find.widgetWithText(SelahButton, 'Start'));

    await _enter(tester, 'MIN', '20');
    await tester.tap(find.widgetWithText(SelahButton, 'Start'));
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }

    expect(fake.sent.where((c) => c['cmd'] == 'start_timer').length, 1,
        reason: 'the command was sent and refused');
    expect(find.text('20'), findsOneWidget,
        reason: 'a denied start must not swallow what the operator typed');
    expect(start().onPressed, isNotNull,
        reason: 'the value is still there, so Start is still live for a retry');
    live.dispose();
  });

  testWidgets('a start lost with the link keeps the digits too', (tester) async {
    final fake = _Fake(deadCmd: 'start_timer');
    final replacement = _Fake();
    final live = await _pumpTab(
      tester,
      fake,
      connect:
          ({
            required String host,
            required int port,
            required String pinHex,
            required Credentials creds,
          }) async => replacement,
    );

    await _enter(tester, 'MIN', '20');
    await tester.tap(find.widgetWithText(SelahButton, 'Start'));
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }

    // The command left the device and was never acknowledged — "rejected", not
    // "probably ran". The typed duration is the operator's, and it stays.
    expect(find.text('20'), findsOneWidget);
    live.dispose();
  });

  testWidgets('minutes and seconds refuse 60+; hours refuse 24+', (
    tester,
  ) async {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CustomTimeWell(controller: controller)),
      ),
    );

    await _enter(tester, 'MIN', '60');
    await _enter(tester, 'SEC', '99');
    await _enter(tester, 'HOURS', '24');

    // The formatter DECLINES the edit rather than rewriting it, so what stays
    // is what was legally typed — never a silently substituted value.
    expect(controller.minutes.text, '6');
    expect(controller.seconds.text, '9');
    expect(controller.hours.text, '2');
    expect(controller.totalSeconds, 2 * 3600 + 6 * 60 + 9);
  });

  testWidgets('non-digits never reach the value', (tester) async {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CustomTimeWell(controller: controller)),
      ),
    );

    await _enter(tester, 'MIN', 'a-5');
    expect(controller.minutes.text, '5');
    expect(controller.totalSeconds, 300);
  });

  testWidgets('each pair is at least a 48dp tap target', (tester) async {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CustomTimeWell(controller: controller)),
      ),
    );

    // Spec §6.6: the frame's digits are narrower than a thumb. The 48-wide box
    // around each field is the fix, not decoration.
    for (final entry in _pairIndex.entries) {
      final box = tester.getSize(_pairs(GestureDetector).at(entry.value));
      expect(box.width, greaterThanOrEqualTo(kSelahMinTouchTarget),
          reason: '${entry.key} pair must be thumb-sized');
    }
  });

  testWidgets('tapping the unit caption focuses its field', (tester) async {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CustomTimeWell(controller: controller)),
      ),
    );

    // The caption is visually part of the control; a tap landing on it must not
    // fall through to the well and do nothing.
    await tester.tap(find.text('SEC'));
    await tester.pump();

    final focused = tester.widgetList<TextField>(find.byType(TextField)).where(
          (f) => f.focusNode?.hasFocus ?? false,
        );
    expect(focused.length, 1);
    expect(focused.single.controller, same(controller.seconds));
  });

  testWidgets('the well greys out and stops accepting taps while syncing', (
    tester,
  ) async {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CustomTimeWell(controller: controller, enabled: false),
        ),
      ),
    );

    final opacity = tester.widget<Opacity>(_pairs(Opacity).first);
    expect(opacity.opacity, 0.4, reason: 'the app-wide disabled treatment');

    for (final field in tester.widgetList<TextField>(find.byType(TextField))) {
      expect(field.enabled, isFalse);
    }
  });

  testWidgets('the well grows rather than clipping at a 3.0 text scale', (
    tester,
  ) async {
    // Spec §6.7. A fixed 67-tall box would clip the digits outright; the
    // measured height is a minimum.
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);

    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(3)),
          child: Scaffold(
            body: Center(child: CustomTimeWell(controller: controller)),
          ),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(
      tester.getSize(find.byType(CustomTimeWell)).height,
      greaterThan(67),
      reason: 'the measured 67 is a floor, not a ceiling',
    );
  });

  testWidgets('the well is a labelled form for assistive tech', (tester) async {
    final handle = tester.ensureSemantics();
    final controller = CustomTimeController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CustomTimeWell(controller: controller)),
      ),
    );

    // "HOURS"/"MIN"/"SEC" are decoration; the spoken names are whole words —
    // some VoiceOver voices read "MIN" as an abbreviation of nothing.
    for (final spoken in ['Hours', 'Minutes', 'Seconds']) {
      expect(find.bySemanticsLabel(RegExp(spoken)), findsOneWidget,
          reason: '$spoken must name its field');
    }
    handle.dispose();
  });

  test('the controller adds its three fields into one duration', () {
    final controller = CustomTimeController();
    addTearDown(controller.dispose);

    expect(controller.isEmpty, isTrue);
    expect(controller.totalSeconds, 0);

    controller.hours.text = '2';
    controller.minutes.text = '3';
    controller.seconds.text = '4';
    expect(controller.totalSeconds, 2 * 3600 + 3 * 60 + 4);
    expect(controller.isEmpty, isFalse);

    controller.clear();
    expect(controller.totalSeconds, 0);
  });

  test('the controller notifies on every keystroke, and stops on dispose', () {
    final controller = CustomTimeController();
    var notifications = 0;
    controller.addListener(() => notifications++);

    controller.minutes.text = '5';
    expect(notifications, 1, reason: 'Start enables on the first digit');

    // Disposing must detach from the text controllers BEFORE disposing them —
    // a field that outlived the detach would notify a dead ChangeNotifier.
    expect(controller.dispose, returnsNormally);
  });

  testWidgets('the deferred timer controls are explained, not drawn', (
    tester,
  ) async {
    final live = await _pumpTab(tester, _Fake());

    // `Reset` and the stage TIME UP cue have no wire command. The tab says so
    // in prose, and the prose is not a control: no button, no gesture.
    expect(find.textContaining('no command for either'), findsOneWidget);
    final note = find.ancestor(
      of: find.textContaining('no command for either'),
      matching: find.byWidgetPredicate(
        (w) => w is InkWell || w is GestureDetector || w is SelahButton,
      ),
    );
    expect(note, findsNothing,
        reason: 'an explanation must not be tappable — there is nothing behind '
            'it to reach');

    live.dispose();
  });
}
