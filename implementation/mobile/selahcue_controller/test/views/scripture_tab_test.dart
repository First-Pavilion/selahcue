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
  final MobileRole grantedRole;
  _Fake(this.view, {this.chapterFetchFails = false,
    this.grantedRole = MobileRole.producer});

  bool dead = false;
  Completer<void>? stateGate;
  final sent = <Map<String, dynamic>>[];

  /// When true, `get_chapter` degrades (old-host / bad-reference path) so the
  /// fallback Stage/Live buttons render instead of the verse list.
  final bool chapterFetchFails;

  /// When set, a non-`get_chapter` command parks before replying — a command
  /// reached the host but its acknowledgement hasn't landed yet.
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('offline');
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
    sent.add(Map<String, dynamic>.from(cmd));
    final g = commandGate;
    if (g != null) await g.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('offline');
    final gate = stateGate;
    if (gate != null) await gate.future;
    return view;
  }

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

const _chapterView = OperatorStateView(
  planName: 'Sunday', items: [], liveIndex: null, stagedIndex: null,
  blackout: false, timer: null, stagedScripture: 'Romans 8:28',
);

Future<LiveController> _pumpReconnectTab(
    WidgetTester tester, _Fake old, _Fake replacement) async {
  final live = LiveController(session: old, stored: _stored, connect: ({
    required String host, required int port, required String pinHex,
    required Credentials creds,
  }) async => replacement);
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: ListenableBuilder(
    listenable: live, builder: (_, _) => ScriptureTab(live: live),
  ))));
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

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
  testWidgets('syncing dims verse rows and disables both gestures until refresh',
      (tester) async {
    final handle = tester.ensureSemantics();
    final old = _Fake(_chapterView);
    final replacement = _Fake(_chapterView)..stateGate = Completer<void>();
    final live = await _pumpReconnectTab(tester, old, replacement);
    try {
      expect(find.text('And we know…'), findsOneWidget);
      expect(live.syncing, isFalse);
      old.dead = true;
      await live.refresh();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isTrue);
      expect(live.reconnecting, isFalse,
          reason: 'socket returned, but fresh truth has not arrived');
      final rowFinder = find.byType(SelahListRow).first;
      final row = tester.widget<SelahListRow>(rowFinder);
      expect(row.onTap, isNull);
      expect(row.onDoubleTap, isNull);
      final opacity = find.ancestor(of: rowFinder, matching: find.byType(Opacity));
      expect(opacity, findsOneWidget, reason: 'callbacks alone do not dim a row');
      expect(tester.widget<Opacity>(opacity).opacity, 0.4);
      await tester.tap(find.text('And we know…'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 400));
      expect(replacement.sent, isEmpty, reason: 'no audience action while syncing');

      replacement.stateGate!.complete();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isFalse);
      expect(tester.widget<SelahListRow>(rowFinder).onTap, isNotNull);
      expect(tester.widget<Opacity>(opacity).opacity, 1);
      await tester.tap(find.text('And we know…'));
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pump();
      expect(replacement.sent.where((c) => c['cmd'] == 'stage_scripture'),
          hasLength(1), reason: 'ready-state tap reaches the replacement host');
    } finally {
      if (!replacement.stateGate!.isCompleted) replacement.stateGate!.complete();
      await tester.pump();
      await tester.pumpWidget(const SizedBox());
      live.dispose();
      handle.dispose();
    }
  });

  testWidgets('syncing caption dims and explains why Scripture gestures pause',
      (tester) async {
    final old = _Fake(_chapterView);
    final replacement = _Fake(_chapterView)..stateGate = Completer<void>();
    final live = await _pumpReconnectTab(tester, old, replacement);
    try {
      old.dead = true;
      await live.refresh();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isTrue);
      final caption = find.textContaining('Syncing live state…');
      expect(caption, findsOneWidget);
      expect(find.text('Tap a verse to stage · double-tap to send live'), findsNothing);
      final opacity = find.ancestor(of: caption, matching: find.byType(Opacity));
      expect(opacity, findsOneWidget);
      expect(tester.widget<Opacity>(opacity).opacity, 0.4);
      replacement.stateGate!.complete();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isFalse);
      expect(caption, findsNothing);
      expect(find.text('Tap a verse to stage · double-tap to send live'), findsOneWidget);
    } finally {
      if (!replacement.stateGate!.isCompleted) replacement.stateGate!.complete();
      await tester.pump();
      await tester.pumpWidget(const SizedBox());
      live.dispose();
    }
  });

  testWidgets('syncing disables fallback actions and recovers after fresh state',
      (tester) async {
    final handle = tester.ensureSemantics();
    final old = _Fake(_emptyView, chapterFetchFails: true);
    final replacement = _Fake(_emptyView, chapterFetchFails: true)
      ..stateGate = Completer<void>();
    final live = await _pumpReconnectTab(tester, old, replacement);
    try {
      await tester.enterText(find.byType(TextField), 'Romans 8:28');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 60));
      expect(find.bySemanticsLabel('Stage'), findsOneWidget);
      old.dead = true;
      await live.refresh();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isTrue);
      expect(find.bySemanticsLabel('Stage, unavailable while reconnecting'), findsOneWidget);
      expect(find.bySemanticsLabel('Live, unavailable while reconnecting'), findsOneWidget);
      await tester.tap(find.text('Stage'), warnIfMissed: false);
      await tester.tap(find.text('Live'), warnIfMissed: false);
      await tester.pump();
      expect(replacement.sent, isEmpty);
      replacement.stateGate!.complete();
      await tester.pump(const Duration(milliseconds: 60));
      expect(live.syncing, isFalse);
      expect(find.bySemanticsLabel('Stage'), findsOneWidget);
      await tester.tap(find.text('Stage'));
      await tester.pump(const Duration(milliseconds: 60));
      expect(replacement.sent.where((c) => c['cmd'] == 'stage_scripture'), hasLength(1));
    } finally {
      if (!replacement.stateGate!.isCompleted) replacement.stateGate!.complete();
      await tester.pump();
      await tester.pumpWidget(const SizedBox());
      live.dispose();
      handle.dispose();
    }
  });

  testWidgets('Viewer Scripture remains read only during this UI change',
      (tester) async {
    final viewer = _Fake(_emptyView, grantedRole: MobileRole.viewer);
    final live = LiveController(session: viewer, stored: _stored);
    try {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
      await tester.pump();
      expect(find.text('Scripture control is not part of your role.'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      expect(find.byType(SelahListRow), findsNothing);
      expect(viewer.sent, isEmpty);
    } finally {
      await tester.pumpWidget(const SizedBox());
      live.dispose();
    }
  });

}
