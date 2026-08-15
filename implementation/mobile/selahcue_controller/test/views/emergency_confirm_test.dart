/// Accidental-tap protection on the emergency strip (86ajxx4x8).
///
/// COMPONENT-SPECS §12: "destructive/audience actions (Blackout) get a brief
/// press-and-hold or confirm on mobile (touch is slip-prone) even where the
/// desktop equivalent is one-tap." §1.2 keeps emergency actions out of modal
/// dialogs, so this is an INLINE arm-then-confirm on the button itself.
///
/// Un-blackout is the recovery direction — restoring the audience screen must
/// never sit behind a confirmation.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

class _Fake implements ControllerSession {
  _Fake({this.blackout = false});

  final bool blackout;
  bool dead = false;
  final List<String> sent = [];

  /// When set, the state fetch parks — socket back, truth not yet re-read.
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
    return OperatorStateView(
      planName: 'S',
      items: const [],
      liveIndex: null,
      stagedIndex: null,
      blackout: blackout,
      timer: null,
    );
  }

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

Future<LiveController> _pumpStrip(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
  await tester.pump(const Duration(milliseconds: 60));
  return live;
}

void main() {
  testWidgets('one tap on Blackout does not black out the audience',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpStrip(tester, fake);

    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();

    expect(fake.sent, isNot(contains('blackout')),
        reason: 'a single slip must not reach the audience output');
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget,
        reason: 'the button arms in place — no modal over live control');

    handle.dispose();
    live.dispose();
  });

  testWidgets('a second tap confirms and sends the blackout', (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpStrip(tester, fake);

    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    await tester.tap(find.bySemanticsLabel('Confirm blackout'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(fake.sent, contains('blackout'));
    handle.dispose();
    live.dispose();
  });

  testWidgets('the armed state reverts on its own so it cannot fire later',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = LiveController(session: fake, stored: _stored);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: EmergencyStrip(
                live: live, confirmWindow: const Duration(seconds: 3)))));
    await tester.pump(const Duration(milliseconds: 60));

    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget);

    await tester.pump(const Duration(seconds: 4));
    expect(find.bySemanticsLabel('Confirm blackout'), findsNothing,
        reason: 'an armed control left untouched must disarm, not lie in wait');
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget);
    expect(fake.sent, isNot(contains('blackout')));

    handle.dispose();
    live.dispose();
  });

  testWidgets('UN-blackout is one tap — recovery is never gated',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake(blackout: true);
    final live = await _pumpStrip(tester, fake);

    await tester.tap(find.bySemanticsLabel('Un-blackout'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(fake.sent, contains('blackout'),
        reason: 'restoring the audience screen must not need a confirmation');
    handle.dispose();
    live.dispose();
  });

  testWidgets('Clear All also needs a confirming tap', (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpStrip(tester, fake);

    await tester.tap(find.bySemanticsLabel('Clear all'));
    await tester.pump();
    expect(fake.sent, isNot(contains('clear')));

    await tester.tap(find.bySemanticsLabel('Confirm clear all'));
    await tester.pump(const Duration(milliseconds: 60));
    expect(fake.sent, contains('clear'));

    handle.dispose();
    live.dispose();
  });

  testWidgets('emergency controls are disabled while the link is syncing',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    // The reconnect lands, but its first state fetch is still in flight — the
    // socket is back and the truth is not yet re-read.
    final replacement = _Fake()..gate = Completer<void>();
    final live = LiveController(
      session: fake,
      stored: _stored,
      connect: ({
        required String host,
        required int port,
        required String pinHex,
        required Credentials creds,
      }) async =>
          replacement,
    );
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ListenableBuilder(
          listenable: live,
          builder: (_, _) => EmergencyStrip(live: live),
        ),
      ),
    ));
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.syncing, isFalse, reason: 'baseline: healthy link');

    fake.dead = true;
    await live.refresh();
    await tester.pump(const Duration(milliseconds: 60));

    expect(live.syncing, isTrue, reason: 'baseline');
    // The control is present but greyed and announced as unavailable.
    expect(find.bySemanticsLabel('Blackout, unavailable while reconnecting'),
        findsOneWidget);

    await tester.tap(find.text('■ BLACKOUT'));
    await tester.pump();

    expect(find.text('■ CONFIRM BLACKOUT'), findsNothing,
        reason: 'a disabled control must not even arm');
    expect(fake.sent, isEmpty);

    handle.dispose();
    live.dispose();
  });
}
