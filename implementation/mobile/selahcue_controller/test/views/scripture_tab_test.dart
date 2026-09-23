import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';
import 'package:selahcue_controller/views/widgets/primitives.dart';

/// Fake session whose operator view reports the SAME reference as both staged
/// and live — the post-go-live state the host actually sends — and which serves
/// Romans 8 for get_chapter.
class _Fake implements ControllerSession {
  final OperatorStateView view;
  @override
  final MobileRole grantedRole = MobileRole.producer;
  _Fake(this.view, {this.chapterFetchFails = false});

  /// When true, `get_chapter` degrades (old-host / bad-reference path) so the
  /// fallback Stage/Live buttons render instead of the verse list.
  final bool chapterFetchFails;

  /// When set, a non-`get_chapter` command parks before replying — a command
  /// reached the host but its acknowledgement hasn't landed yet.
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (cmd['cmd'] == 'get_chapter') {
      if (chapterFetchFails) return const Denied(1, 'no such command');
      return const ChapterResult(
        bookName: 'Romans',
        chapter: 8,
        translation: 'KJV',
        verses: [
          VerseView(27, 'And he that searcheth…'),
          VerseView(28, 'And we know…'),
        ],
        prevRef: 'Romans 7',
        nextRef: 'Romans 9',
      );
    }
    final g = commandGate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

const _emptyView = OperatorStateView(
  planName: 'Sunday',
  items: [],
  liveIndex: null,
  stagedIndex: null,
  blackout: false,
  timer: null,
);

void main() {
  testWidgets(
      'a verse that is both staged and live announces "live", not "staged"',
      (tester) async {
    const view = OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
      // After go-live the host reports the same ref in BOTH fields.
      stagedScripture: 'Romans 8:28',
      liveScripture: 'Romans 8:28',
    );
    final handle = tester.ensureSemantics();

    final live = LiveController(session: _Fake(view), stored: _stored);

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ScriptureTab(live: live))),
    );
    // Let refresh() populate the view, the initial-load listener fire, and the
    // chapter fetch resolve.
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }

    // The verse actually rendered (sanity before asserting its semantics).
    expect(find.text('And we know…'), findsOneWidget);
    // The verse that is both staged and live must announce "live", never
    // "staged" (the label mirrors the border/fill colour ordering).
    expect(find.bySemanticsLabel(RegExp('Verse 28, live')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Verse 28, staged')), findsNothing);

    handle.dispose();
    live.dispose(); // cancel the 1s poll before the test ends
  });

  testWidgets('a verse row is disabled while a command is in flight',
      (tester) async {
    final fake = _Fake(_emptyView);
    final live = LiveController(session: fake, stored: _stored);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ListenableBuilder(
          listenable: live,
          builder: (_, _) => ScriptureTab(live: live),
        ),
      ),
    ));
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    // No staged/live scripture on this view, so nothing auto-loads — search
    // for a chapter explicitly.
    await tester.enterText(find.byType(TextField), 'Romans 8');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    expect(find.text('And we know…'), findsOneWidget, reason: 'baseline');
    expect(live.busy, isFalse, reason: 'baseline');

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('And we know…'));
    // The row has both onTap + onDoubleTap, so single-tap disambiguation
    // waits for the double-tap timer before onTap actually fires.
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'stage_scripture is now in flight');
    final row = tester.widget<SelahListRow>(find.byType(SelahListRow).first);
    expect(row.onTap, isNull,
        reason: 'a row must not accept a new stage while a command is '
            'still on the wire (17tnw2ay2pq, follow-up to 17tnw2ay2kk)');
    expect(row.onDoubleTap, isNull);
    expect(find.textContaining('Sending'), findsOneWidget);

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);
    final rowAfter =
        tester.widget<SelahListRow>(find.byType(SelahListRow).first);
    expect(rowAfter.onTap, isNotNull,
        reason: 'and re-enables once busy clears');

    live.dispose();
  });

  testWidgets(
      'the fallback Stage/Live buttons are disabled while a command is in flight',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake(_emptyView, chapterFetchFails: true);
    final live = LiveController(session: fake, stored: _stored);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ListenableBuilder(
          listenable: live,
          builder: (_, _) => ScriptureTab(live: live),
        ),
      ),
    ));
    for (var i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    await tester.enterText(find.byType(TextField), 'Romans 8:28');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 60));
    }
    expect(find.text('Stage'), findsOneWidget,
        reason: 'baseline: the old-host fallback is showing');

    fake.commandGate = Completer<void>();
    await tester.tap(find.text('Stage'));
    await tester.pump();

    expect(live.busy, isTrue, reason: 'stage_scripture is now in flight');
    expect(find.bySemanticsLabel('Stage, sending…'), findsOneWidget,
        reason: 'these buttons had NO gating at all before 17tnw2ay2pq — '
            'not even on syncing');
    expect(find.bySemanticsLabel('Live, sending…'), findsOneWidget);

    fake.commandGate!.complete();
    await tester.pump(const Duration(milliseconds: 60));
    expect(live.busy, isFalse);

    handle.dispose();
    live.dispose();
  });
}
