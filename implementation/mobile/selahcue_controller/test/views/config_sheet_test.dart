/// The Config/About sheet (Figma 363-124) shows CONNECTION + PREFERENCES +
/// ABOUT; toggling Keep-awake drives the injected wakelock; version comes from
/// package_info (mocked). No real platform channels are touched.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/settings.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
        planName: 'Sunday',
        items: [],
        liveIndex: null,
        stagedIndex: null,
        blackout: false,
        timer: null,
      );
  @override
  Future<void> close() async {}
}

class _MemStore implements SettingsStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String v) async => value = v;
}

class _FakeWakelock implements WakelockControl {
  final List<bool> calls = [];
  @override
  Future<void> toggle(bool enabled) async => calls.add(enabled);
}

// A realistic 64-hex pin so pinFingerprint formats without a range error.
const _pin =
    '2244abcd2244abcd2244abcd2244abcd2244abcd2244abcd2244abcd2244abcd';
const _stored =
    StoredSession(host: '192.168.1.60', port: 52255, pinHex: _pin, deviceId: 'd', token: 't');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    PackageInfo.setMockInitialValues(
      appName: 'SelahCue',
      packageName: 'com.example.selahcue',
      version: '1.0.0',
      buildNumber: '128',
      buildSignature: '',
    );
  });

  testWidgets('renders CONNECTION/PREFERENCES/ABOUT, version, and toggles keep-awake',
      (tester) async {
    final wl = _FakeWakelock();
    final settings = SettingsController(store: _MemStore(), wakelock: wl);
    await settings.load(); // applies wakelock(false)
    final live =
        LiveController(session: _Fake(MobileRole.producer), stored: _stored);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ConfigSheet(
          stored: _stored,
          live: live,
          settings: settings,
          onDisconnect: () {},
        ),
      ),
    ));
    await tester.pump(); // resolve the PackageInfo future
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('CONNECTION'), findsOneWidget);
    expect(find.text('PREFERENCES'), findsOneWidget);
    expect(find.text('ABOUT'), findsOneWidget);
    expect(find.text('Keep screen awake'), findsOneWidget);
    expect(find.text('Haptic feedback'), findsOneWidget);
    expect(find.text('Reduce motion'), findsOneWidget);
    expect(find.textContaining('1.0.0 (128)'), findsOneWidget);
    expect(find.text('Open-source licenses'), findsOneWidget);
    expect(find.text('Privacy policy'), findsOneWidget); // FR-176
    expect(find.text('Producer'), findsOneWidget); // real granted role

    // Toggle Keep screen awake (first Switch) → wakelock enabled.
    final before = wl.calls.length;
    await tester.tap(find.byType(Switch).first);
    await tester.pump();
    expect(wl.calls.length, greaterThan(before));
    expect(wl.calls.last, isTrue);
    expect(settings.keepAwake, isTrue);

    live.dispose();
  });
}
