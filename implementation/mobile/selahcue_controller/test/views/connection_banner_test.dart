/// `ConnectionBanner`'s `busy` branch (17tnw2ay2pq review, Sana). Before this,
/// the banner branched on `rejected`, `syncing`, then `error` and fell through
/// to [SizedBox.shrink] while `busy` — the ONE place a sighted operator (as
/// opposed to a screen-reader user, who gets `disabledReason` in the
/// semantics label) learns that a command any control on screen sent is still
/// on the wire. `detections_view.dart`'s "the banner above says why" comment
/// was only true once this branch existed.
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
  @override
  final MobileRole grantedRole = MobileRole.producer;

  /// When set, `command()` parks before replying — a command reached the
  /// host but its acknowledgement hasn't landed yet.
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    final g = commandGate;
    if (g != null) await g.future;
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

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

Future<LiveController> _pumpBanner(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListenableBuilder(
        listenable: live,
        builder: (_, _) => ConnectionBanner(live: live),
      ),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets(
      'shows a visible reason while a command is in flight, not just while '
      'reconnecting', (tester) async {
    final fake = _Fake();
    final live = await _pumpBanner(tester, fake);
    expect(live.syncing, isFalse, reason: 'baseline: healthy link');
    expect(find.textContaining('Sending…'), findsNothing,
        reason: 'nothing in flight yet — the banner has nothing to say');

    fake.commandGate = Completer<void>();
    unawaited(live.act(cmdNext()));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'the command is now in flight');
    expect(find.textContaining('Sending…'), findsOneWidget,
        reason: 'a sighted operator must be told something is happening — '
            'disabledReason only ever reaches the semantics label '
            '(17tnw2ay2pq review, Sana)');

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    expect(find.textContaining('Sending…'), findsNothing,
        reason: 'the banner clears itself once busy does');

    live.dispose();
  });
}
