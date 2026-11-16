/// UHZ: real helper output, including a stack whose untruncated size is known.
library;

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/session.dart';

import '../support/capture_debug_print.dart';

void main() {
  test('unexpected failure stack contains only its first eight frames', () {
    final frames = List.generate(20, (i) =>
        '#$i diagnosticFrame$i (package:selahcue_controller/diagnostic_fixture.dart:${i + 1}:1)');
    final printed = <String>[];
    captureDebugPrint(printed, () {
      debugReportUnexpectedConnectFailure(
          const FormatException('HOST-PAYLOAD'),
          StackTrace.fromString(frames.join('\n')));
    });
    final lines = printed.expand((message) => message.split('\n')).toList();
    final frameLines = lines.where((line) => line.contains('diagnosticFrame'));
    expect(frameLines, hasLength(8),
        reason: 'the helper must bound a supplied twenty-frame stack');
    expect(frameLines.toList(), frames.take(8).toList());
    expect(lines.where((line) => line.contains('unexpected FormatException')),
        hasLength(1));
    expect(printed.join('\n'), isNot(contains('HOST-PAYLOAD')));
  });

  test('a throwing diagnostic printer does not escape the helper', () {
    final original = debugPrint;
    Object? escaped;
    try {
      debugPrint = (String? message, {int? wrapWidth}) {
        throw StateError('printer unavailable');
      };
      try {
        debugReportUnexpectedConnectFailure(
            const FormatException('HOST-PAYLOAD'), StackTrace.current);
      } on Object catch (error) {
        escaped = error;
      }
    } finally {
      debugPrint = original;
    }
    expect(escaped, isNull,
        reason: 'best-effort diagnostics cannot defeat connection recovery');
  });
}
