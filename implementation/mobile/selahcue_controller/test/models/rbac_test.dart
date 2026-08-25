/// Pins the client RBAC mirror to the desktop's `Role::permissions()` table
/// (`implementation/desktop/crates/selahcue-lan/src/rbac.rs:62-91`). If the
/// backend role→capability policy changes, this test is the single place the
/// mirror is updated. The server stays authoritative — this mirror only gates
/// what the UI offers.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';
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

  _commandMirror();

  test('label is the real backend role name', () {
    expect(MobileRole.producer.label, 'Producer');
    expect(MobileRole.assistant.label, 'Assistant');
    expect(MobileRole.viewer.label, 'Viewer');
    expect(MobileRole.unknown.label, 'Unknown');
  });
}

/// The command→permission mirror the enforcement sheet reads (§4.10). It is a
/// transcription of Rust `required_permission()`, so it is checked against the
/// same rules that file's comments call out — particularly the two places the
/// desktop deliberately does NOT escalate.
void _commandMirror() {
  test('command→capability mirrors required_permission()', () {
    Capability? capOf(Map<String, dynamic> cmd) =>
        commandActionFor(cmd)?.capability;

    expect(capOf(cmdGoLive()), Capability.goLive);
    expect(capOf(cmdNext()), Capability.navigate);
    expect(capOf(cmdPrevious()), Capability.navigate);
    expect(capOf(cmdSelectItem(1)), Capability.navigate);
    expect(capOf(cmdSelectSlide(1, 0)), Capability.navigate);
    expect(capOf(cmdClear()), Capability.clearLive);
    expect(capOf(cmdBlackout(true)), Capability.blackout);
    for (final cmd in [
      cmdStartTimer(60),
      cmdStopTimer(),
      cmdAdjustTimer(60),
      cmdPauseTimer(),
      cmdResumeTimer(),
    ]) {
      expect(capOf(cmd), Capability.timer, reason: '${cmd['cmd']}');
    }
    expect(capOf(cmdStageScripture('John 3:16')), Capability.searchScripture);
    expect(capOf(cmdGetChapter('John 3')), Capability.searchScripture);
    expect(capOf(cmdGetOperatorState()), Capability.monitor);
    expect(capOf(cmdSetTheme('x')), Capability.configureOutputs);
  });

  test('approving a detection is SearchScripture, never GoLive', () {
    // rbac.rs:126 — approving stages a candidate in Preview; it does not put
    // anything on the audience screen. Mirroring it as goLive would tell an
    // Assistant they need a Producer role for something they can already do.
    expect(commandActionFor(cmdApproveDetection(7))?.capability,
        Capability.searchScripture);
    expect(commandActionFor(cmdDismissDetection(7))?.capability,
        Capability.searchScripture);
    expect(MobileRole.assistant.can(Capability.searchScripture), isTrue);
  });

  test('an unrecognised command is null, not a guess', () {
    // A newer host may know commands this build does not. The sheet has copy for
    // exactly this case; inventing a capability would name the wrong role.
    expect(commandActionFor({'cmd': 'reset_timer'}), isNull);
    expect(commandActionFor(const {}), isNull);
  });

  test('rolesWith lists holders most-capable first and never `unknown`', () {
    expect(rolesWith(Capability.goLive),
        [MobileRole.operator, MobileRole.producer]);
    expect(rolesWith(Capability.searchScripture),
        [MobileRole.operator, MobileRole.producer, MobileRole.assistant]);
    expect(rolesWith(Capability.monitor), [
      MobileRole.operator,
      MobileRole.producer,
      MobileRole.assistant,
      MobileRole.viewer,
    ]);
    for (final capability in Capability.values) {
      expect(rolesWith(capability), isNot(contains(MobileRole.unknown)),
          reason: '`unknown` is a fail-closed parse, not an assignable role');
    }
  });

  test('minimalRoleFor answers with the LEAST role that would have been enough',
      () {
    // The body line says "needs the <role> role" — singular. That is only
    // honest because the roles form a superset ladder, which this pins.
    expect(minimalRoleFor(Capability.goLive), MobileRole.producer);
    expect(minimalRoleFor(Capability.searchScripture), MobileRole.assistant);
    expect(minimalRoleFor(Capability.monitor), MobileRole.viewer);
    expect(minimalRoleFor(Capability.manageDevices), MobileRole.operator);
  });

  test('the role ladder really is a superset chain', () {
    // minimalRoleFor is only well-defined while this holds. If a future backend
    // role gains a capability its superior lacks, this fails BEFORE the sheet
    // starts naming a role that would not have helped.
    const ladder = [
      MobileRole.viewer,
      MobileRole.assistant,
      MobileRole.producer,
      MobileRole.operator,
    ];
    for (var i = 0; i < ladder.length - 1; i++) {
      expect(ladder[i + 1].capabilities.containsAll(ladder[i].capabilities),
          isTrue,
          reason: '${ladder[i + 1].label} must hold everything '
              '${ladder[i].label} does');
    }
  });

  test('every capability has a human label for the removed-controls receipt',
      () {
    for (final capability in Capability.values) {
      expect(capability.label, isNotEmpty);
      expect(capability.label, isNot(contains('_')),
          reason: 'the receipt shows the operator\'s words, not the wire\'s');
    }
  });
}
