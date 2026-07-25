import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/discovery_controller.dart';
import 'package:selahcue_controller/models/discovery.dart';
import 'package:selahcue_controller/models/multicast_lock.dart';

/// Records lock calls and interleaves with the browse to assert ordering.
class _FakeLock implements MulticastLock {
  final List<String> events;
  _FakeLock(this.events);
  int acquired = 0;
  int released = 0;

  @override
  Future<void> acquire() async {
    acquired++;
    events.add('acquire');
  }

  @override
  Future<void> release() async {
    released++;
    events.add('release');
  }
}

void main() {
  test('refresh holds the multicast lock across the browse (acquire→browse→release)',
      () async {
    final events = <String>[];
    final lock = _FakeLock(events);
    final c = DiscoveryController(
      lock: lock,
      browse: (found) async {
        events.add('browse');
        // The lock must already be held when the browse runs.
        expect(lock.acquired, 1);
        expect(lock.released, 0);
        found['10.0.0.2:8443'] = const DiscoveredHost(
          name: 'Host', host: '10.0.0.2', port: 8443, pinHex: 'ab',
        );
      },
    );
    addTearDown(c.dispose);

    await c.refresh();

    expect(events, ['acquire', 'browse', 'release']);
    expect(lock.acquired, 1);
    expect(lock.released, 1);
    expect(c.hosts.single.host, '10.0.0.2');
    expect(c.searching, isFalse);
  });

  test('the lock is released even when the browse throws', () async {
    final events = <String>[];
    final lock = _FakeLock(events);
    final c = DiscoveryController(
      lock: lock,
      browse: (_) async => throw StateError('mdns blew up'),
    );
    addTearDown(c.dispose);

    await expectLater(c.refresh(), throwsA(isA<StateError>()));
    // finally still ran: the lock is never leaked on a browse failure.
    expect(lock.acquired, 1);
    expect(lock.released, 1);
    expect(events, ['acquire', 'release']);
  });

  test('a concurrent refresh does not double-acquire the lock', () async {
    final events = <String>[];
    final lock = _FakeLock(events);
    late DiscoveryController c;
    c = DiscoveryController(
      lock: lock,
      browse: (_) async {
        // While the first browse is in flight, a second refresh must no-op.
        await c.refresh();
        expect(lock.acquired, 1, reason: 'second refresh must not re-acquire');
      },
    );
    addTearDown(c.dispose);

    await c.refresh();
    expect(lock.acquired, 1);
    expect(lock.released, 1);
  });
}
