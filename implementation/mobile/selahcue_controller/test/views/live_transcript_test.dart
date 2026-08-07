/// The Live tab renders the read-only transcript (finalised segments + partial)
/// when the host is transcribing; nothing when there is none.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/live_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final OperatorStateView view;
  _Fake(this.grantedRole, this.view);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => view;
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

OperatorStateView _view({
  List<TranscriptSegmentView> transcript = const [],
  String? partial,
}) =>
    OperatorStateView(
      planName: 'Sunday',
      items: const [],
      liveIndex: null,
      stagedIndex: null,
      blackout: false,
      timer: null,
      transcript: transcript,
      partialTranscript: partial,
    );

Future<LiveController> _pump(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester
      .pumpWidget(MaterialApp(home: Scaffold(body: LiveTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('renders finalised segments + partial line (any role)',
      (tester) async {
    final fake = _Fake(
      MobileRole.viewer,
      _view(
        transcript: const [
          TranscriptSegmentView(id: 1, text: 'and we know'),
          TranscriptSegmentView(id: 2, text: 'that all things work together'),
        ],
        partial: 'for good to them',
      ),
    );
    final live = await _pump(tester, fake);
    expect(find.text('LIVE TRANSCRIPT'), findsOneWidget);
    expect(find.text('that all things work together'), findsOneWidget);
    expect(find.text('for good to them'), findsOneWidget);
    live.dispose();
  });

  testWidgets('no transcript section when the host is not transcribing',
      (tester) async {
    final live = await _pump(tester, _Fake(MobileRole.producer, _view()));
    expect(find.text('LIVE TRANSCRIPT'), findsNothing);
    live.dispose();
  });
}
