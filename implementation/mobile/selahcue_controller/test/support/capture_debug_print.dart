/// Scoped diagnostic capture for sync fake-clock and async widget tests.
/// Restore before the body returns, ahead of Flutter's global-invariant checks.
/// The production printer buffers/throttles large output and can schedule a
/// deferred flush; a small individual report need not create a Timer.
library;

import 'package:flutter/foundation.dart' show debugPrint;

T captureDebugPrint<T>(List<String> sink, T Function() body) {
  final original = debugPrint;
  debugPrint = (String? message, {int? wrapWidth}) {
    if (message != null) sink.add(message);
  };
  try {
    return body();
  } finally {
    debugPrint = original;
  }
}

Future<void> captureDebugPrintAsync(
    List<String> sink, Future<void> Function() body) async {
  final original = debugPrint;
  debugPrint = (String? message, {int? wrapWidth}) {
    if (message != null) sink.add(message);
  };
  try {
    await body();
  } finally {
    debugPrint = original;
  }
}
