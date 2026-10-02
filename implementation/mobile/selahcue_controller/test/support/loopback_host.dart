/// A scripted fake SelahCue host for tests: a REAL pinned-TLS WebSocket server on
/// loopback, so `SelahSession.connect` / `SelahSession.pair` run their production
/// path (TLS handshake, certificate pin, the hello, the reply parse) against a
/// peer whose replies the test chooses frame by frame.
///
/// Why not a hand-built frame source: the interesting failures live in how the
/// client reads the host's reply, and a fake that skips the transport can only
/// assert what the test author believed about it.
///
/// The certificate below is a THROWAWAY, test-only, self-signed key pair
/// (`CN=selahcue-test-loopback`, generated with
/// `openssl req -x509 -newkey rsa:2048 -nodes -days 36500`). It protects
/// nothing: the server binds loopback only, lives for the length of one test,
/// and no real host, device or pairing invite has ever used it. It is NOT a
/// credential and must never be reused outside tests.
///
/// SECRET SCANNERS: the embedded PEM block below is that test-only throwaway.
/// If a secret scanner (gitleaks, GitHub secret scanning, ...) is ever added to
/// this repo, allowlist this file (`test/support/loopback_host.dart`) rather than
/// removing the key: it is deliberate and worthless.
library;

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

const String _testCertPem = '''
-----BEGIN CERTIFICATE-----
MIICwDCCAagCCQDEYTx18lQGEDANBgkqhkiG9w0BAQsFADAhMR8wHQYDVQQDDBZz
ZWxhaGN1ZS10ZXN0LWxvb3BiYWNrMCAXDTI2MTAwMjA1MjQ0M1oYDzIxMjYwOTA4
MDUyNDQzWjAhMR8wHQYDVQQDDBZzZWxhaGN1ZS10ZXN0LWxvb3BiYWNrMIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp3l3ZEDw19nh+oLMKPBhSG/DUVEt
GyhU/nPTsV/0w9AIljt15HN6/a8WE1KSN1tXGmY5ODccQYbsIVbTiZd5elwHlxFp
+Y/8Y/IZgz/k8LE6MpjEBEE/X/Z4AihdTE3RSl44KaL2cBnLvkZQG5JRo8wjnJK/
btJd10SpHA6/DiKP1ELDwTFWVplMb4hJ6yoQBZ5r/6rg9WiUAlgpcw2CPw+K/QTQ
su2rnS8cayY9EpNURYBnNmL+3qQ7u54TOlvznppJFfi1xW30RK39twVpvWJf1vQa
ezl4hKfqyQvS7Zy7KXbyvd3G8KWnTxmsgmOMr+smPU0xfDJxrCf4m3ScaQIDAQAB
MA0GCSqGSIb3DQEBCwUAA4IBAQATWYFFM5xYKSKTIbk5YuDWaWuxQJ3Syd4SRE71
D8vgbx26GkZkT0HXSVjtjpZwYIC/JwHfRuI8IMGl4YiDtDlvmrykIBTeknj+mcGL
Jn4P3vPEPgGnjgIB5hgbfa6opmp7qSVH2LuqktZmzJgCUneyF/RWWQ7FAbVrT2jI
CIQsX8JeICrPxggO0w2Vyw5PDlzroHPDYVh9zvY/LQrIMoQ3NBBeo0Zw/MQzGXUr
EeXkEIQmzK6hQBS+ndV13DWu3m/YkBtgOlUQM03G4FP4Gie6+bYUfTmzOjGWlafM
ACQ91H6gLln80RVgvv1WSTzXt0KMaLXIhnq8AJFNZL1tL1xw
-----END CERTIFICATE-----
''';

const String _testKeyPem = '''
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCneXdkQPDX2eH6
gswo8GFIb8NRUS0bKFT+c9OxX/TD0AiWO3Xkc3r9rxYTUpI3W1caZjk4NxxBhuwh
VtOJl3l6XAeXEWn5j/xj8hmDP+TwsToymMQEQT9f9ngCKF1MTdFKXjgpovZwGcu+
RlAbklGjzCOckr9u0l3XRKkcDr8OIo/UQsPBMVZWmUxviEnrKhAFnmv/quD1aJQC
WClzDYI/D4r9BNCy7audLxxrJj0Sk1RFgGc2Yv7epDu7nhM6W/OemkkV+LXFbfRE
rf23BWm9Yl/W9Bp7OXiEp+rJC9LtnLspdvK93cbwpadPGayCY4yv6yY9TTF8MnGs
J/ibdJxpAgMBAAECggEAbOD0NNJfggVd/A5zCp6UsJIwijpbN8+1yiOlWijHKVKj
coA/ugE10Z21nWROOP0CGOCijKCPly5Pb7FSH57B1EHmkVk564ynipbH7WNpxO2D
p4dX0GhW+l1zUfvKBCSHT3EH1FHlI6Yxpodx5yruNq4t7Moe+L59UcmKo/oWTeou
rFOnVro8OlnyyFfu+N7j8L7vmIVFeoYgldNjtCTWiIMdR1rW0Xo0zwSOJBpPSL4C
M08ZOjNMLIi1Mx+iETx9wyXOJYntLhMa7Rxzc9O7rjWBWZDg11U7a6dvifCs2j21
LLd1GYsUjv3aHZfgU6QHlLrgjOkpYFJ8up6/CfZGcQKBgQDbHDoBWbUN9sy5qLnu
6iRYnA2zhzghMRTupZuA+DfTDuzua0ytEArdBD8b5JpMnnGj4cwls08/xNF+a7hi
7IoK9c9WaNYDC0ppZfWVp3I+FYsGiMLL2gFzDyGUAZetQfVPEWtM4QrmJKM4fJSV
n2OcNmDDTqK3qgE/IV2HYS17nQKBgQDDq7WCTF25aCG3tV8T9jne2oxNZ27o478+
Zw2zyNCDViumRRyIVc9ePStDEI6TG1ZxcYuyKvLg1szYy6jHxgnpxF4wJvesddh6
v4dIzzlJrIhb6aP/xKl2IRuJ2Si/u4NHeeaKhjxOk3S5Xayt4wQBdkNjtWngt9J2
b7tq1iJIPQKBgEca/ef6SLtjYETP8KcL7QekfP3J3/lFiFl5/OD5rIQdz93/jD6N
ejkHa8ONiFVdBdv9JtcFPa6gHKw+IPRZduLfqo2MMAeE3n0dzXjngjeLnjZco3qs
INRKEMeLTMG5Kfai3INydKsDMMTgCQgVVaoYK4a2OjAIR6dJGKUacDwxAoGBALRP
PuvbQ2LfOnL3h631cE6URkXt0p55gHoYrN/HZZ4hggeuGCTqLjVBWORsFXYp8vaH
E5wTR805I3uD8Pxm2iu48LKetg0Oa3ZxmFDX5IqnmuBX5PCEYUSiLaZRnuNQACGV
i4SLPneKGj3WvJFgaQiP2nm/atnRivfo7mP8/4phAoGADnsgzlOr2TU+EguZ2yUb
S0vj5VyOnjDzjuUCvXzP9qfqSCqNb7zLSozVHgn71rGyOEYIsGKM5fAm8ghvw/ys
FRNj7ZIr7BxsE6BGHc+SaML2Jzjf4w7VRTC/90lfyY3sxYB3AhLgxO5pJcniPnh9
g/58/QeJVzTnODmAW1ckU1c=
-----END PRIVATE KEY-----
''';

/// The SHA-256 of the test certificate's DER, lowercase hex — the pin a client
/// must present to trust this host (what a pairing invite carries as `pin`).
String _testPinHex() {
  final body = _testCertPem
      .split('\n')
      .where((l) => l.isNotEmpty && !l.startsWith('-----'))
      .join();
  return sha256.convert(base64Decode(body)).toString();
}

/// A loopback pinned-TLS WebSocket host that answers each connection's first
/// frame (the client's hello) with a scripted list of reply frames.
class LoopbackHost {
  final HttpServer _server;
  final List<WebSocket> _sockets = [];

  /// Every hello received, in arrival order — one entry per connection attempt.
  /// The length is how many times a client dialled in and spoke.
  final List<Map<String, dynamic>> hellos = [];

  int _clientClosed = 0;

  /// How many connections the CLIENT has closed (this host never closes one
  /// itself before the test ends, so a socket that ends is the client's doing).
  int get clientClosedCount => _clientClosed;

  /// Wait until [count] connections have been closed from the client's side.
  /// `false` on timeout, which is how a leaked socket shows up.
  Future<bool> waitClientClosed(int count,
      {Duration timeout = const Duration(seconds: 5)}) async {
    final deadline = DateTime.now().add(timeout);
    while (_clientClosed < count) {
      if (DateTime.now().isAfter(deadline)) return false;
      await Future<void>.delayed(const Duration(milliseconds: 20));
    }
    return true;
  }

  LoopbackHost._(this._server);

  int get port => _server.port;

  /// The pin a client must hold to trust this host.
  String get pinHex => _testPinHex();

  /// Start a host that answers every connection's hello with [replies], in
  /// order, as text frames. [replies] are sent as-is, so a test can send
  /// well-formed JSON, wrong-typed JSON, or not JSON at all.
  ///
  /// The server and every socket are closed when the test ends.
  static Future<LoopbackHost> start({required List<String> replies}) async {
    // Once a test has initialised the Flutter test binding (anything that mocks
    // a platform channel does), `HttpClient` is replaced by a stub that answers
    // every request with a 400, so the production `WebSocket.connect` could
    // never reach this host. It exists to be dialled for real: lift the stub
    // for the length of the test.
    // Initialise the binding first (idempotent) so that it cannot install its
    // stub AFTER we have lifted it, whichever order a test sets things up in.
    TestWidgetsFlutterBinding.ensureInitialized();
    final previousOverrides = HttpOverrides.current;
    HttpOverrides.global = null;
    addTearDown(() => HttpOverrides.global = previousOverrides);

    final context = SecurityContext(withTrustedRoots: false)
      ..useCertificateChainBytes(utf8.encode(_testCertPem))
      ..usePrivateKeyBytes(utf8.encode(_testKeyPem));
    final server = await HttpServer.bindSecure(
        InternetAddress.loopbackIPv4, 0, context);
    final host = LoopbackHost._(server);
    addTearDown(host._close);

    server.listen((req) async {
      final ws = await WebSocketTransformer.upgrade(req);
      host._sockets.add(ws);
      var answered = false;
      ws.listen((frame) {
        if (answered) return;
        answered = true;
        host.hellos.add(jsonDecode(frame as String) as Map<String, dynamic>);
        for (final reply in replies) {
          ws.add(reply);
        }
      }, onDone: () => host._clientClosed++,
          onError: (Object _) {},
          cancelOnError: true);
    }, onError: (Object _) {});
    return host;
  }

  Future<void> _close() async {
    for (final ws in _sockets) {
      await ws.close();
    }
    await _server.close(force: true);
  }
}
