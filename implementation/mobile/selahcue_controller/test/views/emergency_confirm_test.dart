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

  /// Mutable: the DESKTOP operator is authoritative and can black out at any
  /// moment, including in the gap between this device's arm tap and its
  /// confirm tap.
  bool blackout;
  bool dead = false;
  final List<String> sent = [];

  /// Full command maps, for the assertions that care about an absolute
  /// command's ARGUMENT rather than just its name — `blackout` on vs off is the
  /// difference between darkening the audience screen and restoring it.
  final List<Map<String, dynamic>> sentCmds = [];

  /// When set, the state fetch parks — socket back, truth not yet re-read.
  Completer<void>? gate;

  /// When set, `command()` parks before replying — a command reached the
  /// host but its acknowledgement hasn't landed yet.
  Completer<void>? commandGate;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    sent.add(cmd['cmd'] as String);
    sentCmds.add(cmd);
    final g = commandGate;
    if (g != null) await g.future;
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

/// Same, but rebuilt on every controller notification — i.e. on every 1s poll,
/// the way `ControllerView` really hosts the strip. That rebuild is load-bearing
/// for anything about state changing mid-gesture: a strip that never rebuilds
/// keeps the closures it was built with and cannot show the bug.
Future<LiveController> _pumpPolledStrip(
    WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListenableBuilder(
        listenable: live,
        builder: (_, _) => EmergencyStrip(live: live),
      ),
    ),
  ));
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

  testWidgets(
      'a blackout armed before the desktop blacked out still means BLACKOUT',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpPolledStrip(tester, fake);

    // The operator arms: their intent is "make the audience screen go dark".
    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget);

    // The DESKTOP operator blacks out in the gap between the two taps, and the
    // 1s poll rebuilds the strip with that new truth.
    fake.blackout = true;
    await live.refresh();
    await tester.pump(const Duration(milliseconds: 60));

    // The armed control keeps announcing what the confirming tap will DO. If it
    // relabels itself from the polled state, the operator's confirm gesture ends
    // up sitting under a button reading "UN-BLACKOUT".
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget,
        reason: 'an arm is the operator’s intent; a poll must not relabel it');
    expect(find.text('■ CONFIRM BLACKOUT'), findsOneWidget);

    await tester.tap(find.bySemanticsLabel('Confirm blackout'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(
        fake.sentCmds.where((c) => c['cmd'] == 'blackout').toList(),
        [
          {'cmd': 'blackout', 'on': true}
        ],
        reason: 'the confirming tap must send the command that was ARMED. '
            'Binding an absolute command at BUILD time let a rebuild between '
            'the two taps turn a confirmed blackout into an un-blackout — the '
            'exact opposite of the armed intent.');

    handle.dispose();
    live.dispose();
  });

  testWidgets('un-blackout stays one tap after the desktop blacks out',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpPolledStrip(tester, fake);

    // Nothing armed here — the desktop blacks out and this device simply
    // catches up. Recovery must still be the one-tap direction.
    fake.blackout = true;
    await live.refresh();
    await tester.pump(const Duration(milliseconds: 60));

    await tester.tap(find.bySemanticsLabel('Un-blackout'));
    await tester.pump(const Duration(milliseconds: 60));

    expect(
        fake.sentCmds.where((c) => c['cmd'] == 'blackout').toList(),
        [
          {'cmd': 'blackout', 'on': false}
        ],
        reason: 'restoring the audience screen is never gated');

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

  testWidgets('emergency controls are disabled while a command is in flight',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpPolledStrip(tester, fake);
    expect(live.busy, isFalse, reason: 'baseline');

    // Arm and confirm — the confirming tap sends `blackout`, held in flight
    // by the gate so the test can observe the strip while it is outstanding.
    fake.commandGate = Completer<void>();
    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    await tester.tap(find.bySemanticsLabel('Confirm blackout'));
    await tester.pump();

    expect(live.busy, isTrue,
        reason: 'the confirming tap sent blackout, still in flight');
    // _fire() disarms immediately, so the label reverts to BLACKOUT (the
    // host has not acknowledged yet) — but it must render disabled, not live.
    expect(find.bySemanticsLabel('Blackout, sending…'), findsOneWidget,
        reason: 'a control must not look tappable while its own command is '
            'still on the wire (17tnw2ay2pq, follow-up to 86ajxx4x8)');

    // A tap while busy must be a genuine no-op, not a second arm/fire.
    final sentBefore = fake.sent.length;
    await tester.tap(find.text('■ BLACKOUT'));
    await tester.pump();
    expect(fake.sent.length, sentBefore,
        reason: 'a disabled control must not even arm');

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse,
        reason: 'busy must clear once the command settles');
    // The fake host never actually applied the blackout (only recorded that
    // it was sent), so the label is still BLACKOUT — what matters here is
    // that it is enabled again, i.e. carries no disabled-reason suffix.
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget,
        reason: 'the control re-enables once busy clears');

    handle.dispose();
    live.dispose();
  });

  testWidgets(
      'an armed BLACKOUT survives an UNRELATED command overlapping the '
      'confirm window, instead of silently expiring (17tnw2ay2pq review, '
      'Sana)', (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    final live = await _pumpPolledStrip(tester, fake);

    // Arm BLACKOUT — no command sent yet.
    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget);

    // A command from a DIFFERENT control — anywhere else in the app — starts
    // and parks in flight. Before the fix, the 3s disarm timer kept running
    // regardless, so the confirm window could lapse while it was inert.
    fake.commandGate = Completer<void>();
    unawaited(live.act(cmdNext()));
    await tester.pump();
    expect(live.busy, isTrue, reason: 'an unrelated command is now in flight');

    // The confirming tap lands while busy — `_guarded` makes it a genuine
    // no-op (the arm must survive this, not fire and not vanish). The
    // control is disabled by `busy`, same as any other control, so its
    // semantics label carries the disabled-reason suffix.
    await tester.tap(find.bySemanticsLabel('Confirm blackout, sending…'),
        warnIfMissed: false);
    await tester.pump();
    expect(fake.sent, isNot(contains('blackout')),
        reason: 'the tap could not land while busy — nothing was sent');

    // Let the ORIGINAL 3-second confirm window fully elapse while busy is
    // still true. With the old behaviour the arm silently reverted here.
    await tester.pump(const Duration(seconds: 4));
    expect(find.bySemanticsLabel('Confirm blackout, sending…'), findsOneWidget,
        reason: 'the arm must survive the window elapsing while paused for '
            'busy — the operator confirmed nothing because they COULD not, '
            'not because they chose not to');

    // The unrelated command finally settles — busy clears, and the paused
    // window resumes with whatever time was left.
    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget,
        reason: 'still armed once busy clears — the arm was never lost');

    // A genuine confirm tap, now that the control is live again, fires it.
    await tester.tap(find.bySemanticsLabel('Confirm blackout'));
    await tester.pump(const Duration(milliseconds: 60));
    expect(fake.sent, contains('blackout'),
        reason: 'the operator can still complete the confirm they started');

    handle.dispose();
    live.dispose();
  });

  testWidgets(
      'a pause-then-resume grants only the time that was left, not a fresh '
      'window, and the arm still expires once that runs out', (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake();
    // Default `EmergencyStrip.confirmWindow` is 3s.
    final live = await _pumpPolledStrip(tester, fake);

    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();

    // Spend 2 of the 3 seconds BEFORE busy ever starts — only ~1s of budget
    // is left by the time the pause below begins.
    await tester.pump(const Duration(milliseconds: 2000));
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget,
        reason: 'still armed with ~1s of its window left');

    // Busy now holds for far longer than the ~1s that remains — a genuine
    // pause must not let this erode the budget at all, no matter how long
    // it lasts, or the operator would never get a fair shot at confirming a
    // control that happened to arm just before something else got busy.
    fake.commandGate = Completer<void>();
    unawaited(live.act(cmdNext()));
    await tester.pump();
    await tester.pump(const Duration(seconds: 5));
    expect(find.bySemanticsLabel('Confirm blackout, sending…'), findsOneWidget,
        reason: 'still paused — busy has not cleared yet');

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    // Resumed: still armed, with roughly the ~1s that was left — NOT a
    // fresh 3s window (a resume that reset the budget would let a stream of
    // unrelated busy edges keep this armed forever, which would hollow out
    // the accidental-tap protection, 86ajxx4x8).
    expect(find.bySemanticsLabel('Confirm blackout'), findsOneWidget,
        reason: 'resumed with only the leftover budget, not reset to 3s');

    // That leftover budget still runs out on its own.
    await tester.pump(const Duration(milliseconds: 1200));
    expect(find.bySemanticsLabel('Confirm blackout'), findsNothing,
        reason: 'the leftover ~1s must still expire once it is spent');
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget);
    expect(fake.sent, isNot(contains('blackout')));

    handle.dispose();
    live.dispose();
  });
}
