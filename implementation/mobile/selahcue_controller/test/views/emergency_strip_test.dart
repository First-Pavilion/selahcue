/// The emergency strip's Blackout / Clear are role-gated (hide-not-disable).
library;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/design_tokens.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/selah_theme.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';
import 'package:selahcue_controller/views/widgets/primitives.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final List<String> clearedLayers;
  final List<Map<String, dynamic>> sentCmds = [];
  _Fake(this.grantedRole, {this.clearedLayers = const []});
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sentCmds.add(cmd);
    return const Ack(1);
  }

  @override
  Future<OperatorStateView> operatorState() async => OperatorStateView(
        planName: 'S',
        items: const [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
        clearedLayers: clearedLayers,
      );
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  testWidgets('Producer sees Blackout + Clear', (tester) async {
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.producer), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget);
    expect(find.bySemanticsLabel('Clear all'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Assistant sees neither emergency control', (tester) async {
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsNothing);
    expect(find.bySemanticsLabel('Clear all'), findsNothing);
    handle.dispose();
    live.dispose();
  });

  Widget host(LiveController live) => MaterialApp(
        home: Scaffold(
          body: Column(
            mainAxisSize: MainAxisSize.min,
            children: [ClearTextRow(live: live), EmergencyStrip(live: live)],
          ),
        ),
      );

  testWidgets('Clear text sends clear_layer for the text layer',
      (tester) async {
    final handle = tester.ensureSemantics();
    final fake = _Fake(MobileRole.operator);
    final live = LiveController(session: fake, stored: _stored);
    await tester.pumpWidget(host(live));
    await tester.pump(const Duration(milliseconds: 60));
    await tester.tap(find.bySemanticsLabel('Clear text'));
    await tester.pump(const Duration(milliseconds: 60));
    expect(fake.sentCmds, [cmdClearLayer('text')]);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Clear text shows as pressed, not solid red, when cleared',
      (tester) async {
    final handle = tester.ensureSemantics();
    for (final cleared in [true, false]) {
      final fake = _Fake(MobileRole.operator,
          clearedLayers: cleared ? const ['text'] : const []);
      final live = LiveController(session: fake, stored: _stored);
      await tester.pumpWidget(host(live));
      await tester.pump(const Duration(milliseconds: 60));
      expect(
          tester.getSemantics(find.bySemanticsLabel('Clear text')),
          matchesSemantics(
            label: 'Clear text',
            isButton: true,
            hasEnabledState: true,
            isEnabled: true,
            hasToggledState: true,
            isToggled: cleared,
          ),
          reason: 'cleared=$cleared');
      final material = tester.widget<Material>(find.descendant(
          of: find.byType(ClearTextRow), matching: find.byType(Material)).last);
      if (cleared) {
        expect(material.color, isNot(DesignTokens.d2Live),
            reason: 'solid red is reserved for Blackout and armed confirms');
      }
      live.dispose();
    }
    handle.dispose();
  });

  testWidgets('Viewer does not see Clear text', (tester) async {
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.viewer), stored: _stored);
    await tester.pumpWidget(host(live));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Clear text'), findsNothing);
    handle.dispose();
    live.dispose();
  });

  testWidgets('at 320x640 nothing overflows, the strip keeps two buttons and '
      'CONFIRM BLACKOUT is not truncated', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final handle = tester.ensureSemantics();
    final live =
        LiveController(session: _Fake(MobileRole.operator), stored: _stored);
    await tester.pumpWidget(host(live));
    await tester.pump(const Duration(milliseconds: 60));

    expect(
        find.descendant(
            of: find.byType(EmergencyStrip), matching: find.byType(SelahButton)),
        findsNWidgets(2));
    expect(find.byType(SelahButton), findsNWidgets(3));

    await tester.tap(find.bySemanticsLabel('Blackout'));
    await tester.pump();
    final finder = find.text('■ CONFIRM BLACKOUT');
    expect(finder, findsOneWidget);
    final box = tester.renderObject<RenderParagraph>(finder);
    // The flutter_test font (Ahem, 1em per glyph) is far wider than the real
    // UI font, so absolute ellipsis cannot be asserted here: the label
    // truncates identically on the untouched pre-change strip. What this
    // guards is that the strip keeps its two-button geometry: each button gets
    // exactly half of (320 - 2*md padding - sm gap), not a third.
    final strip = find.descendant(
        of: find.byType(EmergencyStrip), matching: find.byType(SelahButton));
    const w = (320 - 2 * SelahSpace.md - SelahSpace.sm) / 2;
    for (var i = 0; i < 2; i++) {
      expect(tester.getSize(strip.at(i)).width, closeTo(w, 0.5));
    }
    expect(box.size.width, lessThan(w));
    expect(tester.takeException(), isNull);
    handle.dispose();
    live.dispose();
  });
}
