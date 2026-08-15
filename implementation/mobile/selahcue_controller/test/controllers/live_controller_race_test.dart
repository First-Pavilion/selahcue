/// The reconnect race (86ajxwcft): a socket blip during the stage half of the
/// stage-then-go-live double-tap must NEVER let the go-live half fire.
///
/// The double-tap's whole safety story is its guard: "only send it live if it
/// actually landed in Preview". That guard is only meaningful when it is
/// evaluated against a snapshot the controller can prove was taken **after** the
/// stage command, **on the connection that carried it**. While the controller is
/// away the desktop stays authoritative and may stage something else entirely —
/// so a guard evaluated against a pre-disconnect snapshot can promote the wrong
/// item to the congregation's screen.
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

const _itemA = 10;
const _itemB = 20;

/// Two-item plan; `staged` picks which one the host reports in Preview.
OperatorStateView _view({required int? staged}) => OperatorStateView(
      planName: 'Sunday',
      items: const [
        PlanItemView(
            id: _itemA,
            kind: 'song',
            title: 'Amazing Grace',
            isLive: false,
            isStaged: false),
        PlanItemView(
            id: _itemB,
            kind: 'song',
            title: 'Doxology',
            isLive: false,
            isStaged: false),
      ],
      liveIndex: null,
      stagedIndex: staged,
      blackout: false,
      timer: null,
    );

/// Records every command it is asked to send, so a test can assert on what
/// actually reached the host rather than on controller internals.
class _RecordingSession implements ControllerSession {
  _RecordingSession(this.view, {this.failOnce});

  OperatorStateView view;

  /// A `cmd` value that should throw once (a socket blip), then behave.
  final String? failOnce;
  bool _failed = false;

  final List<String> sent = [];
  int closeCount = 0;

  /// When set, `operatorState()` parks on this until the test completes it —
  /// used to hold a poll in flight and reproduce the refresh-coalescing path.
  Completer<void>? gate;

  /// When true, the state fetch dies even though `command()` still succeeds —
  /// the "command landed but we could not confirm its effect" path.
  bool failStateFetch = false;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    final name = cmd['cmd'] as String;
    if (failOnce != null && name == failOnce && !_failed) {
      _failed = true;
      throw const SessionException('socket blip');
    }
    sent.add(name);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (failStateFetch) throw const SessionException('socket blip');
    final g = gate;
    if (g != null) await g.future;
    return view;
  }

  @override
  Future<void> close() async => closeCount++;
}

const _stored = StoredSession(
  host: '10.0.0.2',
  port: 8443,
  pinHex: 'ab',
  deviceId: 'dev-1',
  token: 'tok-1',
);

void main() {
  test(
      'a stage lost to a socket blip must NOT go live against the pre-disconnect view',
      () async {
    // What the phone last saw: item A staged. (The operator is re-tapping the
    // item that is already in Preview — an ordinary double-tap.)
    final blipped =
        _RecordingSession(_view(staged: 0), failOnce: 'select_item');

    // The host's ACTUAL state by the time we are back: the desktop operator
    // staged item B while the phone was away. The desktop is authoritative and
    // unaffected during a mobile reconnect, so this is the normal case.
    final healthy = _RecordingSession(_view(staged: 1));

    Future<ControllerSession> reconnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        healthy;

    final live = LiveController(
        session: blipped, stored: _stored, connect: reconnect);
    addTearDown(live.dispose);
    // Let the constructor's first refresh settle so `_view` holds "A staged".
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(live.view?.stagedIndex, 0, reason: 'baseline: phone sees A staged');

    // The gesture: stage A and, only if it landed, send it live.
    await live.selectAndGoLive(_itemA);

    expect(blipped.sent, isNot(contains('select_item')),
        reason: 'the stage was lost to the blip — it never reached the host');
    expect(healthy.sent, isNot(contains('go_live')),
        reason: 'CRITICAL: the stage is unproven, so go_live must not be sent — '
            'the host has item B staged and would promote the wrong item to '
            'the congregation');
  });

  test('a stage lost to a socket blip is not reported as applied', () async {
    final blipped =
        _RecordingSession(_view(staged: 0), failOnce: 'select_item');
    final healthy = _RecordingSession(_view(staged: 0));
    Future<ControllerSession> reconnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        healthy;

    final live = LiveController(
        session: blipped, stored: _stored, connect: reconnect);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 10));

    final outcome = await live.act(cmdSelectItem(_itemA));
    expect(outcome, isNot(CommandOutcome.applied),
        reason: 'a command that never reached the host cannot be "applied"');
  });

  test('a stage whose CONFIRMING refresh is lost must NOT go live', () async {
    // The stage command LANDS, but the trailing state fetch dies with the
    // socket. The host may well have staged A — we simply cannot prove it, and
    // "unknown" must not read as "confirmed" to the go-live half. By the time we
    // are back the desktop has staged B.
    final session = _RecordingSession(_view(staged: 0));
    final healthy = _RecordingSession(_view(staged: 1));
    Future<ControllerSession> reconnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        healthy;

    final live = LiveController(
        session: session, stored: _stored, connect: reconnect);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 10));

    // From here the state fetch fails; the command itself still succeeds.
    session.failStateFetch = true;
    await live.selectAndGoLive(_itemA);

    expect(session.sent, contains('select_item'),
        reason: 'baseline: the stage itself did reach the host');
    expect(healthy.sent, isNot(contains('go_live')),
        reason: 'the effect of the stage was never confirmed on a live '
            'connection, so it cannot authorise a go-live');
  });

  test(
      'the go-live guard must not reuse a snapshot that predates the stage '
      '(refresh coalesced with an in-flight poll)', () async {
    // No socket blip at all. `refresh()` early-returns while another refresh is
    // in flight, so act()'s trailing refresh can silently be a no-op and leave
    // `_view` describing the world BEFORE the command.
    final session = _RecordingSession(_view(staged: 0));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(live.view?.stagedIndex, 0);

    // Park a poll's state fetch in flight, and move the host underneath us.
    final gate = Completer<void>();
    session.gate = gate;
    unawaited(live.refresh());
    await Future<void>.delayed(Duration.zero);
    session.view = _view(staged: 1); // host truth: item B is staged now

    final gesture = live.selectAndGoLive(_itemA);
    await Future<void>.delayed(const Duration(milliseconds: 10));
    gate.complete();
    await gesture;

    expect(session.sent.where((c) => c == 'go_live'), isEmpty,
        reason: 'the guard was evaluated against a snapshot taken before the '
            'stage — it cannot authorise a go-live');
  });

  test('the happy path still stages and goes live in one gesture', () async {
    // Regression guard: failing closed must not break the legitimate double-tap.
    final session = _RecordingSession(_view(staged: 0));
    final live = LiveController(session: session, stored: _stored);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 10));

    await live.selectAndGoLive(_itemA);
    expect(session.sent, containsAllInOrder(['select_item', 'go_live']));
  });

  test('a scripture stage lost to a socket blip must NOT go live', () async {
    final blipped = _RecordingSession(
      OperatorStateView(
        planName: 'Sunday',
        items: const [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
        stagedScripture: 'John 3:16',
      ),
      failOnce: 'stage_scripture',
    );
    final healthy = _RecordingSession(
      OperatorStateView(
        planName: 'Sunday',
        items: const [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
        stagedScripture: 'Romans 8:28', // the desktop moved on
      ),
    );
    Future<ControllerSession> reconnect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        healthy;

    final live = LiveController(
        session: blipped, stored: _stored, connect: reconnect);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 10));

    await live.stageScriptureAndGoLive('John 3:16');
    expect(healthy.sent, isNot(contains('go_live')),
        reason: 'the stale view still said John 3:16 was staged; the host has '
            'Romans 8:28');
  });
}
