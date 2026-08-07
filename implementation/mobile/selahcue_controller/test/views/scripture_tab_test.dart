import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';

/// Fake session whose operator view reports the SAME reference as both staged
/// and live — the post-go-live state the host actually sends — and which serves
/// Romans 8 for get_chapter.
class _Fake implements ControllerSession {
  final OperatorStateView view;
  @override
  final MobileRole grantedRole = MobileRole.producer;
  _Fake(this.view);

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (cmd['cmd'] == 'get_chapter') {
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
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

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
}
