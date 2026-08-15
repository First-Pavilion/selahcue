/// The "syncing" gate (86ajxx4x8 / FR-097, COMPONENT-SPECS §12): while the link
/// is down — and after it is back but before we have re-read the host — the
/// controller cannot prove what is on the audience screen, so controls must stay
/// disabled. "On reconnect, live state re-syncs BEFORE controls re-enable."
library;

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

OperatorStateView _view() => const OperatorStateView(
      planName: 'Sunday',
      items: [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
    );

class _Session implements ControllerSession {
  _Session({this.dead = false});

  bool dead;

  /// When set, the state fetch parks until the test completes it — lets a test
  /// observe the window between "socket is back" and "we have re-read the host"
  /// without depending on how promptly the controller schedules that re-read.
  Completer<void>? gate;

  @override
  final MobileRole grantedRole = MobileRole.producer;

  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    if (dead) throw const SessionException('down');
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async {
    if (dead) throw const SessionException('down');
    final g = gate;
    if (g != null) await g.future;
    return _view();
  }

  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  test('syncing is true until the first snapshot lands', () async {
    final live = LiveController(session: _Session(), stored: _stored);
    addTearDown(live.dispose);
    // Before the constructor's refresh completes we know nothing about the host.
    expect(live.syncing, isTrue);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(live.syncing, isFalse, reason: 'a snapshot has now landed');
  });

  test('syncing stays true after a reconnect until state is re-read', () async {
    final dead = _Session(dead: true);
    // The replacement connects fine but holds its first state fetch open, so we
    // can observe the window between "socket back" and "host re-read".
    final gate = Completer<void>();
    final replacement = _Session()..gate = gate;
    var connected = false;

    Future<ControllerSession> connect({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async {
      connected = true;
      return replacement;
    }

    final live =
        LiveController(session: dead, stored: _stored, connect: connect);
    addTearDown(live.dispose);

    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(connected, isTrue, reason: 'baseline: the reconnect landed');
    expect(live.reconnecting, isFalse, reason: 'baseline: socket is back');
    // The socket is back, but nothing has re-read the host yet — the snapshot we
    // hold still describes the pre-disconnect world.
    expect(live.syncing, isTrue,
        reason: 'a live connection is not the same as a current view');

    // Let the re-sync land; only now may controls come back.
    gate.complete();
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(live.syncing, isFalse);
  });

  test('a command is refused while the link is down', () async {
    final dead = _Session(dead: true);
    Future<ControllerSession> neverConnects({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    }) async =>
        throw const SessionException('still down');

    final live =
        LiveController(session: dead, stored: _stored, connect: neverConnects);
    addTearDown(live.dispose);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(live.reconnecting, isTrue, reason: 'baseline: still retrying');

    expect(await live.act(cmdGoLive()), CommandOutcome.failed,
        reason: 'no ghost actions: a tap during a drop is refused outright, '
            'not queued and replayed later');
  });
}
