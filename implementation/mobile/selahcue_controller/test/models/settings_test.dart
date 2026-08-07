/// Preferences persist round-trip; keep-awake drives the injected wakelock;
/// haptic() respects the pref. No real platform channels are touched.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/settings.dart';

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

void main() {
  test('load applies keep-awake and defaults sanely', () async {
    final wl = _FakeWakelock();
    final s = SettingsController(store: _MemStore(), wakelock: wl);
    await s.load();
    expect(s.keepAwake, isFalse);
    expect(s.haptics, isTrue);
    expect(s.reduceMotion, isFalse);
    expect(wl.calls, [false]); // applied on load
  });

  test('setters drive the wakelock and persist a round-trip', () async {
    final store = _MemStore();
    final wl = _FakeWakelock();
    final s = SettingsController(store: store, wakelock: wl);
    await s.load();

    await s.setKeepAwake(true);
    expect(wl.calls.last, isTrue);
    await s.setHaptics(false);
    await s.setReduceMotion(true);

    // A fresh controller over the SAME store reads the persisted values.
    final s2 = SettingsController(store: store, wakelock: _FakeWakelock());
    await s2.load();
    expect(s2.keepAwake, isTrue);
    expect(s2.haptics, isFalse);
    expect(s2.reduceMotion, isTrue);
  });

  test('haptic() fires the sink only when haptics are enabled', () async {
    var fired = 0;
    final on = SettingsController(
        store: _MemStore(),
        wakelock: _FakeWakelock(),
        hapticSink: () async => fired++,
        haptics: true);
    on.haptic();
    expect(fired, 1);

    final off = SettingsController(
        store: _MemStore(),
        wakelock: _FakeWakelock(),
        hapticSink: () async => fired++,
        haptics: false);
    off.haptic();
    expect(fired, 1); // unchanged — pref off
  });
}
