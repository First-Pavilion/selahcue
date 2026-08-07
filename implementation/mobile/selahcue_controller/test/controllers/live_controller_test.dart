import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

/// In-memory stand-in for the pinned-TLS session, so the controller's error
/// lifecycle can be exercised without a real socket.
class FakeSession implements ControllerSession {
  OperatorStateView view;
  ServerMessage Function(Map<String, dynamic> cmd) onCommand;
  @override
  final MobileRole grantedRole = MobileRole.producer;
  int commandCount = 0;
  int closeCount = 0;

  FakeSession(this.view, this.onCommand);

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    commandCount++;
    return onCommand(cmd);
  }

  @override
  Future<OperatorStateView> operatorState() async => view;

  @override
  Future<void> close() async => closeCount++;
}

OperatorStateView _emptyView() => const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );

const _stored = StoredSession(
  host: '10.0.0.2',
  port: 8443,
  pinHex: 'ab',
  deviceId: 'dev-1',
  token: 'tok-1',
);

void main() {
  test('a command denial stays on screen across a poll refresh', () async {
    // The host denies every command.
    final session = FakeSession(
        _emptyView(), (_) => const Denied(1, 'producers cannot clear'));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);

    await live.act({'type': 'clear'});
    expect(live.error, contains('producers cannot clear'),
        reason: 'denial should be surfaced immediately');

    // Simulate the 1s poll firing again (a plain successful state fetch).
    await live.refresh();
    expect(live.error, contains('producers cannot clear'),
        reason: 'a successful refresh must NOT wipe a pending denial');
  });

  test('a later successful command clears the stale denial', () async {
    var deny = true;
    final session = FakeSession(_emptyView(),
        (_) => deny ? const Denied(1, 'nope') : const Ack(2));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);

    await live.act({'type': 'clear'});
    expect(live.error, isNotNull);

    deny = false;
    await live.act({'type': 'go_live'});
    expect(live.error, isNull,
        reason: 'a command that goes through supersedes the old denial');
  });

  test('dismissError clears a pending denial', () async {
    final session =
        FakeSession(_emptyView(), (_) => const Denied(1, 'nope'));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);

    await live.act({'type': 'clear'});
    expect(live.error, isNotNull);
    live.dismissError();
    expect(live.error, isNull);
  });

  test('fetchChapter returns the host chapter', () async {
    const chapter = ChapterResult(
      bookName: 'Romans',
      chapter: 8,
      translation: 'KJV',
      verses: [VerseView(28, 'And we know…')],
      prevRef: 'Romans 7',
      nextRef: 'Romans 9',
    );
    final session = FakeSession(_emptyView(), (_) => chapter);
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);

    final got = await live.fetchChapter('Romans 8');
    expect(got, isNotNull);
    expect(got!.bookName, 'Romans');
    expect(got.verses.single.reference('Romans', 8), 'Romans 8:28');
  });

  test('fetchChapter degrades to null against an old host (error/denied)', () async {
    // An older host that doesn't know get_chapter replies with an error event.
    final old = FakeSession(_emptyView(), (_) => const ErrorMessage('unknown'));
    final liveOld = LiveController(session: old, stored: _stored);
    addTearDown(liveOld.dispose);
    expect(await liveOld.fetchChapter('Romans 8'), isNull);

    final denied = FakeSession(_emptyView(), (_) => const Denied(1, 'forbidden'));
    final liveDenied = LiveController(session: denied, stored: _stored);
    addTearDown(liveDenied.dispose);
    expect(await liveDenied.fetchChapter('Romans 8'), isNull);
    // A read-only fetch must not raise the denial banner.
    expect(liveDenied.error, isNull);
  });
}
