/// Pins the client RBAC mirror to the desktop's `Role::permissions()` table
/// (`implementation/desktop/crates/selahcue-lan/src/rbac.rs:62-91`). If the
/// backend role→capability policy changes, this test is the single place the
/// mirror is updated. The server stays authoritative — this mirror only gates
/// what the UI offers.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/rbac.dart';

void main() {
  test('parse maps the wire strings and fails closed', () {
    expect(MobileRole.parse('operator'), MobileRole.operator);
    expect(MobileRole.parse('producer'), MobileRole.producer);
    expect(MobileRole.parse('assistant'), MobileRole.assistant);
    expect(MobileRole.parse('viewer'), MobileRole.viewer);
    expect(MobileRole.parse(''), MobileRole.unknown);
    expect(MobileRole.parse(null), MobileRole.unknown);
    expect(MobileRole.parse('root'), MobileRole.unknown);
  });

  test('capability sets mirror rbac.rs Role::permissions() verbatim', () {
    expect(MobileRole.producer.capabilities, {
      Capability.goLive,
      Capability.navigate,
      Capability.clearLive,
      Capability.blackout,
      Capability.timer,
      Capability.searchScripture,
      Capability.transcribe,
      Capability.monitor,
    });
    expect(MobileRole.assistant.capabilities,
        {Capability.searchScripture, Capability.navigate, Capability.monitor});
    expect(MobileRole.viewer.capabilities, {Capability.monitor});
    expect(MobileRole.unknown.capabilities, isEmpty);
    expect(MobileRole.operator.capabilities.length, Capability.values.length);
  });

  test('can() gates the live-output actions', () {
    expect(MobileRole.producer.can(Capability.goLive), isTrue);
    expect(MobileRole.assistant.can(Capability.goLive), isFalse);
    expect(MobileRole.viewer.can(Capability.goLive), isFalse);
    expect(MobileRole.assistant.can(Capability.navigate), isTrue);
    expect(MobileRole.assistant.can(Capability.searchScripture), isTrue);
    expect(MobileRole.assistant.can(Capability.blackout), isFalse);
    expect(MobileRole.assistant.can(Capability.timer), isFalse);
    expect(MobileRole.viewer.can(Capability.navigate), isFalse);
    expect(MobileRole.viewer.can(Capability.monitor), isTrue);
  });

  test('label is the real backend role name', () {
    expect(MobileRole.producer.label, 'Producer');
    expect(MobileRole.assistant.label, 'Assistant');
    expect(MobileRole.viewer.label, 'Viewer');
    expect(MobileRole.unknown.label, 'Unknown');
  });
}
