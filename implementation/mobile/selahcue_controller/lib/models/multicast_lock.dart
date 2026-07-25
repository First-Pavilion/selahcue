/// Holds a Wi-Fi multicast lock while mDNS discovery runs (story 86ajp0b0t).
///
/// Android drops inbound multicast packets unless an app holds a
/// `WifiManager.MulticastLock`, so pure-Dart `multicast_dns` browses find
/// nothing without it. This is the Dart side of the `selahcue/multicast`
/// platform channel; only Android needs it, so every other platform is a no-op.
library;

import 'dart:io' show Platform;

import 'package:flutter/services.dart';

/// Acquire/release the multicast lock around a discovery browse. Injectable so
/// the controller's lock lifecycle can be unit-tested without a platform host.
abstract interface class MulticastLock {
  Future<void> acquire();
  Future<void> release();
}

/// The production lock: calls the Android host over a `MethodChannel`.
/// **Best-effort** — a failure (no channel on an older build, a platform error)
/// just means discovery may find nothing; it must never break discovery, so
/// every failure is swallowed. A no-op on non-Android platforms.
class PlatformMulticastLock implements MulticastLock {
  static const MethodChannel _channel = MethodChannel('selahcue/multicast');

  const PlatformMulticastLock();

  @override
  Future<void> acquire() => _invoke('acquire');

  @override
  Future<void> release() => _invoke('release');

  Future<void> _invoke(String method) async {
    // Only Android filters multicast; elsewhere the lock is unnecessary.
    if (!Platform.isAndroid) return;
    try {
      await _channel.invokeMethod<void>(method);
    } on PlatformException {
      // best-effort: a lock hiccup must not break discovery
    } on MissingPluginException {
      // an older host build without the channel — degrade silently
    }
  }
}
