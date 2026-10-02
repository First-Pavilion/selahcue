/// An in-memory stand-in for the platform keystore behind `StoredSession`
/// (`flutter_secure_storage`), so a test can read back whether the stored
/// profile was written, kept, or cleared — through the real `StoredSession`
/// model — instead of inferring it from a controller flag.
library;

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeKeystore {
  final Map<String, String> _values = {};

  /// How many times the profile was deleted (`StoredSession.clear()`).
  int deletes = 0;

  /// How many times a profile was written (`StoredSession.save()`).
  int writes = 0;

  /// Make every write fail like a keystore fault (a `PlatformException`), to
  /// exercise the "saving the credentials failed" path.
  bool failWrites = false;

  /// Route the plugin's method channel to this instance for the current test.
  void install() {
    // Plain `test()`s (as opposed to `testWidgets`) have no binding yet.
    TestWidgetsFlutterBinding.ensureInitialized();
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      final args = (call.arguments as Map?) ?? const {};
      final key = args['key'] as String?;
      switch (call.method) {
        case 'write':
          if (failWrites) {
            throw PlatformException(code: 'keystore', message: 'unavailable');
          }
          writes++;
          _values[key!] = args['value'] as String;
          return null;
        case 'read':
          return _values[key];
        case 'delete':
          deletes++;
          _values.remove(key);
          return null;
        default:
          return null;
      }
    });
    addTearDown(() => TestDefaultBinaryMessengerBinding
        .instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null));
  }
}
