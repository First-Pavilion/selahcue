import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';

const _view = OperatorStateView(
  planName: 'Sunday',
  items: [],
  liveIndex: null,
  stagedIndex: null,
  blackout: false,
  timer: null,
  translations: ['KJV', 'WEB'],
);
const _stored = StoredSession(
  host: 'test-host',
  port: 1,
  pinHex: 'ab',
  deviceId: 'd',
  token: 't',
);

/// RPC boundary fake: chapters are read-only; audience commands are recorded.
/// First-verse narrowing belongs to the real Rust controller tests rather than
/// a duplicate implementation in this fake.
class _Session implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Session({this.grantedRole = MobileRole.producer});
  final sent = <Map<String, dynamic>>[];
  Completer<ServerMessage>? chapterGate;
  bool failChapter = false;
  bool offline = false;
  Completer<void>? stateGate;
  Completer<void>? commandGate;

  @override
  Future<ServerMessage> command(Map<String, dynamic> command) async {
    if (offline) throw const SessionException('offline');
    sent.add(Map.of(command));
    if (command['cmd'] == 'get_chapter') {
      if (chapterGate != null) return chapterGate!.future;
      if (failChapter) return const Denied(1, 'not found');
      final next = command['reference'] == 'Psalms 120';
      return ChapterResult(
        bookName: 'Psalms',
        chapter: next ? 120 : 119,
        translation: command['translation'] as String? ?? 'KJV',
        verses: [for (var i = 1; i <= 12; i++) VerseView(i, 'Verse text $i')],
        prevRef: next ? 'Psalms 119' : 'Psalms 118',
        nextRef: next ? 'Psalms 121' : 'Psalms 120',
      );
    }
    if (commandGate != null) await commandGate!.future;
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (offline) throw const SessionException('offline');
    if (stateGate != null) await stateGate!.future;
    return _view;
  }

  @override
  Future<void> close() async {}
}

// Own the polling controller for exactly the mounted test app lifetime.
class _ControllerOwner extends StatefulWidget {
  final LiveController live;
  const _ControllerOwner({required this.live});
  @override
  State<_ControllerOwner> createState() => _ControllerOwnerState();
}

class _ControllerOwnerState extends State<_ControllerOwner> {
  @override
  void dispose() {
    widget.live.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    home: Scaffold(
      body: ListenableBuilder(
        listenable: widget.live,
        builder: (_, _) => ScriptureTab(live: widget.live),
      ),
    ),
  );
}

Future<LiveController> _mount(
  WidgetTester tester,
  _Session session, {
  _Session? replacement,
}) async {
  final live = LiveController(
    session: session,
    stored: _stored,
    connect: replacement == null
        ? null
        : ({
            required String host,
            required int port,
            required String pinHex,
            required Credentials creds,
          }) async => replacement,
  );
  await tester.pumpWidget(_ControllerOwner(live: live));
  await tester.pump();
  return live;
}

Future<void> _browse(WidgetTester tester, String reference) async {
  await tester.enterText(find.byType(TextField), reference);
  await tester.testTextInput.receiveAction(TextInputAction.search);
  await tester.pump();
}

String _field(WidgetTester tester) =>
    tester.widget<TextField>(find.byType(TextField)).controller!.text;

void main() {
  testWidgets(
    'typed range survives chapter browsing and Stage sends the range',
    (tester) async {
      final session = _Session();
      await _mount(tester, session);
      await _browse(tester, 'Psalms 119:2-10');
      expect(find.text('Verse text 2'), findsOneWidget);
      expect(_field(tester), 'Psalms 119:2-10');
      expect(
        session.sent.where((c) => c['cmd'] == 'stage_scripture'),
        isEmpty,
        reason: 'browsing must never stage or change Live implicitly',
      );
      await tester.tap(find.text('Stage'));
      await tester.pump();
      expect(session.sent.last, {
        'cmd': 'stage_scripture',
        'reference': 'Psalms 119:2-10',
        'translation': 'KJV',
      });
    },
  );

  for (final reference in ['Psalms 119', 'Psalms 119:2']) {
    testWidgets('$reference preserves its identity and stages explicitly', (
      tester,
    ) async {
      final session = _Session();
      await _mount(tester, session);
      await _browse(tester, reference);
      expect(_field(tester), reference);
      await tester.tap(find.text('Stage'));
      await tester.pump();
      expect(session.sent.last['reference'], reference);
    });
  }

  testWidgets('translation reload retains range; chapter paging replaces it', (
    tester,
  ) async {
    final session = _Session();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    await tester.tap(find.text('KJV').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('WEB').last);
    await tester.pumpAndSettle();
    expect(_field(tester), 'Psalms 119:2-10');
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last['translation'], 'WEB');
    expect(session.sent.last['reference'], 'Psalms 119:2-10');
    await tester.tap(find.bySemanticsLabel('Next chapter'));
    await tester.pump();
    expect(_field(tester), 'Psalms 120');
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last['reference'], 'Psalms 120');
  });

  testWidgets('failed lookup keeps previous range and its staged identity', (
    tester,
  ) async {
    final session = _Session();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    session.failChapter = true;
    await _browse(tester, 'unknown reference');
    expect(find.text('Couldn’t load “unknown reference”.'), findsOneWidget);
    expect(_field(tester), 'Psalms 119:2-10');
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last['reference'], 'Psalms 119:2-10');
  });

  testWidgets('chapter response cannot overwrite a newer unsubmitted edit', (
    tester,
  ) async {
    final session = _Session()..chapterGate = Completer<ServerMessage>();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    await tester.enterText(find.byType(TextField), 'Romans 8:28');
    session.chapterGate!.complete(
      const ChapterResult(
        bookName: 'Psalms',
        chapter: 119,
        translation: 'KJV',
        verses: [VerseView(2, 'Verse text 2')],
      ),
    );
    await tester.pump();
    expect(_field(tester), 'Romans 8:28');
    expect(
      find.text('Stage'),
      findsNothing,
      reason: 'an unsubmitted edit must not stage the prior loaded passage',
    );
  });
  testWidgets('newest submitted lookup wins when replies arrive out of order', (
    tester,
  ) async {
    final first = Completer<ServerMessage>();
    final second = Completer<ServerMessage>();
    final session = _Session()..chapterGate = first;
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    session.chapterGate = second;
    await _browse(tester, 'Psalms 120');
    second.complete(
      const ChapterResult(
        bookName: 'Psalms',
        chapter: 120,
        translation: 'KJV',
        verses: [VerseView(1, 'New chapter')],
      ),
    );
    await tester.pump();
    first.complete(
      const ChapterResult(
        bookName: 'Psalms',
        chapter: 119,
        translation: 'KJV',
        verses: [VerseView(2, 'Obsolete chapter')],
      ),
    );
    await tester.pump();
    expect(_field(tester), 'Psalms 120');
    expect(find.text('New chapter'), findsOneWidget);
    expect(find.text('Obsolete chapter'), findsNothing);
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last['reference'], 'Psalms 120');
  });

  testWidgets('initial old-host fallback stages the untouched typed range', (
    tester,
  ) async {
    final session = _Session()..failChapter = true;
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    expect(_field(tester), 'Psalms 119:2-10');
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last['reference'], 'Psalms 119:2-10');
  });

  testWidgets(
    'Assistant can stage the range and busy disables repeat staging',
    (tester) async {
      final semantics = tester.ensureSemantics();
      try {
        final session = _Session(grantedRole: MobileRole.assistant);
        await _mount(tester, session);
        await _browse(tester, 'Psalms 119:2-10');
        session.commandGate = Completer<void>();
        await tester.tap(find.text('Stage'));
        await tester.pump();
        expect(find.bySemanticsLabel('Stage, sending…'), findsOneWidget);
        await tester.tap(find.text('Stage'));
        await tester.pump();
        expect(
          session.sent.where((c) => c['cmd'] == 'stage_scripture'),
          hasLength(1),
        );
        expect(session.sent.where((c) => c['cmd'] == 'go_live'), isEmpty);
        session.commandGate!.complete();
        await tester.pump();
        expect(find.bySemanticsLabel('Stage'), findsOneWidget);
      } finally {
        semantics.dispose();
      }
    },
  );

  testWidgets('verse-row selection still stages one verse after a range load', (
    tester,
  ) async {
    final session = _Session();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    await tester.tap(find.text('Verse text 3'));
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
    expect(session.sent.last['reference'], 'Psalms 119:3');
    expect(_field(tester), 'Psalms 119:2-10');
  });

  testWidgets('disposing the tab while loading ignores the late reply', (
    tester,
  ) async {
    final session = _Session()..chapterGate = Completer<ServerMessage>();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    await tester.pumpWidget(const SizedBox());
    session.chapterGate!.complete(
      const ChapterResult(
        bookName: 'Psalms',
        chapter: 119,
        translation: 'KJV',
        verses: [],
      ),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(session.sent.where((c) => c['cmd'] == 'stage_scripture'), isEmpty);
  });
  testWidgets(
    'loaded range Stage pauses while syncing and resumes after refresh',
    (tester) async {
      final semantics = tester.ensureSemantics();
      final session = _Session();
      final replacement = _Session()..stateGate = Completer<void>();
      final live = await _mount(tester, session, replacement: replacement);
      try {
        await _browse(tester, 'Psalms 119:2-10');
        session.offline = true;
        await live.refresh();
        await tester.pump(const Duration(milliseconds: 60));
        expect(live.syncing, isTrue);
        expect(
          find.bySemanticsLabel('Stage, unavailable while reconnecting'),
          findsOneWidget,
        );
        await tester.tap(find.text('Stage'));
        await tester.pump();
        expect(replacement.sent, isEmpty);
        replacement.stateGate!.complete();
        await tester.pump(const Duration(milliseconds: 60));
        expect(live.syncing, isFalse);
        await tester.tap(find.text('Stage'));
        await tester.pump();
        expect(replacement.sent.single['reference'], 'Psalms 119:2-10');
      } finally {
        if (!replacement.stateGate!.isCompleted) {
          replacement.stateGate!.complete();
        }
        semantics.dispose();
      }
    },
  );
  testWidgets(
    'selection-only change does not discard a delayed chapter reply',
    (tester) async {
      final session = _Session()..chapterGate = Completer<ServerMessage>();
      await _mount(tester, session);
      await _browse(tester, 'Psalms 119:2-10');
      await tester.tap(find.byType(TextField));
      await tester.pump();
      tester.testTextInput.updateEditingValue(
        const TextEditingValue(
          text: 'Psalms 119:2-10',
          selection: TextSelection.collapsed(offset: 3),
        ),
      );
      await tester.pump();
      expect(_field(tester), 'Psalms 119:2-10');
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.selection,
        const TextSelection.collapsed(offset: 3),
      );
      session.chapterGate!.complete(
        const ChapterResult(
          bookName: 'Psalms',
          chapter: 119,
          translation: 'KJV',
          verses: [VerseView(2, 'Delayed verse')],
        ),
      );
      await tester.pump();
      expect(find.text('Delayed verse'), findsOneWidget);
      await tester.tap(find.text('Stage'));
      await tester.pump();
      expect(session.sent.last, {
        'cmd': 'stage_scripture',
        'reference': 'Psalms 119:2-10',
        'translation': 'KJV',
      });
    },
  );

  testWidgets('selection-only change does not discard a translation reload', (
    tester,
  ) async {
    final session = _Session();
    await _mount(tester, session);
    await _browse(tester, 'Psalms 119:2-10');
    session.chapterGate = Completer<ServerMessage>();
    await tester.tap(find.text('KJV').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('WEB').last);
    await tester.pump();
    await tester.tap(find.byType(TextField));
    await tester.pump();
    tester.testTextInput.updateEditingValue(
      const TextEditingValue(
        text: 'Psalms 119:2-10',
        selection: TextSelection(baseOffset: 0, extentOffset: 6),
      ),
    );
    await tester.pump();
    expect(_field(tester), 'Psalms 119:2-10');
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.selection,
      const TextSelection(baseOffset: 0, extentOffset: 6),
    );
    session.chapterGate!.complete(
      const ChapterResult(
        bookName: 'Psalms',
        chapter: 119,
        translation: 'WEB',
        verses: [VerseView(2, 'Reloaded verse')],
      ),
    );
    await tester.pump();
    expect(find.text('Reloaded verse'), findsOneWidget);
    await tester.tap(find.text('Stage'));
    await tester.pump();
    expect(session.sent.last, {
      'cmd': 'stage_scripture',
      'reference': 'Psalms 119:2-10',
      'translation': 'WEB',
    });
  });
}
