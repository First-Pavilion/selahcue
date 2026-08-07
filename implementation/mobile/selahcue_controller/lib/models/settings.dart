/// App preferences (Figma 363-124 · Config → PREFERENCES): keep-screen-awake,
/// haptic feedback, reduce motion. Persisted locally and exposed to the widget
/// tree via [SettingsScope] so the app builder (reduce-motion), the Config sheet
/// (toggles), and key action buttons (haptics) can read them without threading
/// through constructors.
///
/// Platform side-effects (wakelock) and storage are injected so widget/unit
/// tests never touch a real platform channel.
library;

// The injected-dependency constructor deliberately maps public named params to
// private fields (impossible to express as initializing formals, which can't be
// named + private), so prefer_initializing_formals is a false positive here.
// ignore_for_file: prefer_initializing_formals

import 'dart:convert';

import 'package:flutter/services.dart' show HapticFeedback;
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

/// Persists the settings blob. Abstracted so tests inject an in-memory store.
abstract interface class SettingsStore {
  Future<String?> read();
  Future<void> write(String value);
}

/// Production store: one key in the OS secure storage (already a dependency).
class SecureSettingsStore implements SettingsStore {
  static const _key = 'selahcue.settings.v1';
  final FlutterSecureStorage _storage;
  const SecureSettingsStore([this._storage = const FlutterSecureStorage()]);

  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);
}

/// Drives the screen-wake lock. Injected so tests never hit the platform channel.
abstract interface class WakelockControl {
  Future<void> toggle(bool enabled);
}

class PlatformWakelock implements WakelockControl {
  const PlatformWakelock();
  @override
  Future<void> toggle(bool enabled) => WakelockPlus.toggle(enable: enabled);
}

class SettingsController extends ChangeNotifier {
  final SettingsStore _store;
  final WakelockControl _wakelock;
  final Future<void> Function() _hapticSink;

  bool _keepAwake;
  bool _haptics;
  bool _reduceMotion;

  SettingsController({
    SettingsStore store = const SecureSettingsStore(),
    WakelockControl wakelock = const PlatformWakelock(),
    Future<void> Function()? hapticSink,
    bool keepAwake = false,
    bool haptics = true,
    bool reduceMotion = false,
  })  : _store = store,
        _wakelock = wakelock,
        _hapticSink = hapticSink ?? HapticFeedback.selectionClick,
        _keepAwake = keepAwake,
        _haptics = haptics,
        _reduceMotion = reduceMotion;

  bool get keepAwake => _keepAwake;
  bool get haptics => _haptics;
  bool get reduceMotion => _reduceMotion;

  /// Load persisted prefs and apply keep-awake. Best-effort — a storage/plugin
  /// failure falls back to defaults and never throws out of app startup.
  Future<void> load() async {
    try {
      final raw = await _store.read();
      if (raw != null) {
        final j = jsonDecode(raw) as Map<String, dynamic>;
        _keepAwake = j['keep_awake'] as bool? ?? _keepAwake;
        _haptics = j['haptics'] as bool? ?? _haptics;
        _reduceMotion = j['reduce_motion'] as bool? ?? _reduceMotion;
      }
    } catch (_) {
      // Corrupt/absent — keep defaults.
    }
    await _applyWakelock();
    notifyListeners();
  }

  Future<void> setKeepAwake(bool value) async {
    _keepAwake = value;
    await _applyWakelock();
    await _persist();
    notifyListeners();
  }

  Future<void> setHaptics(bool value) async {
    _haptics = value;
    await _persist();
    notifyListeners();
  }

  Future<void> setReduceMotion(bool value) async {
    _reduceMotion = value;
    await _persist();
    notifyListeners();
  }

  /// Fire a light haptic tick if haptics are enabled — call from key actions
  /// (GO LIVE, emergency). A no-op when the pref is off.
  void haptic() {
    if (_haptics) _hapticSink();
  }

  Future<void> _applyWakelock() async {
    try {
      await _wakelock.toggle(_keepAwake);
    } catch (_) {
      // Wakelock is best-effort; a platform failure must not break settings.
    }
  }

  Future<void> _persist() async {
    try {
      await _store.write(jsonEncode({
        'keep_awake': _keepAwake,
        'haptics': _haptics,
        'reduce_motion': _reduceMotion,
      }));
    } catch (_) {
      // Best-effort persistence.
    }
  }
}

/// Exposes the [SettingsController] to the subtree; place ABOVE MaterialApp so
/// the app builder and any descendant can read it and rebuild on change.
class SettingsScope extends InheritedNotifier<SettingsController> {
  const SettingsScope({
    super.key,
    required SettingsController settings,
    required super.child,
  }) : super(notifier: settings);

  static SettingsController of(BuildContext context) {
    final scope =
        context.dependOnInheritedWidgetOfExactType<SettingsScope>();
    assert(scope?.notifier != null, 'No SettingsScope found in the tree');
    return scope!.notifier!;
  }

  /// Null-safe lookup — returns null when no scope is present (e.g. a widget
  /// test that pumps a sub-tree in isolation), so callers can no-op gracefully.
  static SettingsController? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<SettingsScope>()?.notifier;
}
