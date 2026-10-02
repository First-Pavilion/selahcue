/// 17tnw2b0vtj — the ROOT of the wedge: a malformed frame from the host must
/// surface as a [SessionException], never as a raw `FormatException` (non-JSON
/// text frame, from `jsonDecode`) or `TypeError` (binary frame, from
/// `frame as String`).
///
/// Every consumer of `StreamQueue.nextJson` — `connect`, `pair`, `command` —
/// treats [SessionException] as "this link is bad, tear it down". A raw
/// `FormatException`/`TypeError` bypassed all of those handlers. Pairing is the
/// visible second victim: its controller maps any non-SessionException to
/// "Paired, but could not save credentials on this device", which is simply
/// untrue for a host that sent garbage mid-handshake.
///
/// Uses a REAL loopback WebSocket pair rather than a hand-built frame source:
/// the claim that a binary frame arrives as a `List<int>` (and so trips the
/// `as String` cast) is a property of `dart:io`, and a fake could only assert
/// what the test author believed about it.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/session.dart';

/// A connected client [StreamQueue] plus the server's end of the socket, so the
/// test can push whatever frame it likes at the client.
Future<(StreamQueue, WebSocket)> _pair() async {
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  addTearDown(() => server.close(force: true));
  final serverSide = Completer<WebSocket>();
  server.listen((req) async {
    serverSide.complete(await WebSocketTransformer.upgrade(req));
  });

  final client = await WebSocket.connect('ws://127.0.0.1:${server.port}/');
  addTearDown(() => client.close());
  final host = await serverSide.future;
  addTearDown(() => host.close());
  return (StreamQueue(client), host);
}

const _wait = Duration(seconds: 5);

void main() {
  test('control: a well-formed JSON object frame is returned parsed', () async {
    // Proves the loopback transport itself works, so the failures below are
    // about the frame and not about the harness.
    final (queue, host) = await _pair();
    host.add('{"auth":"granted","role":"producer"}');
    expect(await queue.nextJson(_wait), {'auth': 'granted', 'role': 'producer'});
  });

  test('a non-JSON text frame is a SessionException, not a FormatException',
      () async {
    final (queue, host) = await _pair();
    host.add('this is not json');
    await expectLater(
      queue.nextJson(_wait),
      throwsA(isA<SessionException>()
          .having((e) => e.message, 'message', contains('malformed'))),
    );
  });

  test('a binary frame is a SessionException, not a TypeError', () async {
    final (queue, host) = await _pair();
    host.add(<int>[0x00, 0xff, 0x10]); // a binary WebSocket frame
    await expectLater(
      queue.nextJson(_wait),
      throwsA(isA<SessionException>()
          .having((e) => e.message, 'message', contains('malformed'))),
    );
  });

  test('a JSON value that is not an object is still a SessionException',
      () async {
    // Characterisation of the pre-existing guard, kept next to its new siblings
    // so the three ways a frame can be malformed are specified in one place.
    final (queue, host) = await _pair();
    host.add('[1,2,3]');
    await expectLater(
      queue.nextJson(_wait),
      throwsA(isA<SessionException>()),
    );
  });
}
