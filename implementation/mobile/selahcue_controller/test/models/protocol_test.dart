/// Wire-contract tests: these JSON literals are pinned by the Rust side's
/// `wire_fixtures_are_stable_for_cross_language_clients` test
/// (implementation/desktop/crates/selahcue-lan/tests/test_protocol.rs).
/// Change both together (with a VERSION bump).
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/protocol.dart';

void main() {
  test('hello auth matches the Rust wire fixture', () {
    expect(
      jsonEncode(helloAuth('dev-1', 'tok')),
      '{"hello":"auth","v":2,"device_id":"dev-1","token":"tok"}',
    );
  });

  test('hello pair matches the Rust wire fixture', () {
    expect(
      jsonEncode(helloPair('ABCD2345', 'Phone')),
      '{"hello":"pair","v":2,"code":"ABCD2345","device_name":"Phone"}',
    );
  });

  test('request select_item matches the Rust wire fixture', () {
    expect(
      jsonEncode(request(7, cmdSelectItem(3))),
      '{"v":2,"request_id":7,"command":{"cmd":"select_item","item_id":3}}',
    );
  });

  test('command shapes are internally tagged', () {
    expect(jsonEncode(cmdNext()), '{"cmd":"next"}');
    expect(jsonEncode(cmdPrevious()), '{"cmd":"previous"}');
    expect(jsonEncode(cmdGoLive()), '{"cmd":"go_live"}');
    expect(jsonEncode(cmdClear()), '{"cmd":"clear"}');
    expect(jsonEncode(cmdBlackout(true)), '{"cmd":"blackout","on":true}');
    expect(jsonEncode(cmdStartTimer(300)), '{"cmd":"start_timer","seconds":300}');
    expect(jsonEncode(cmdStopTimer()), '{"cmd":"stop_timer"}');
    expect(jsonEncode(cmdGetOperatorState()), '{"cmd":"get_operator_state"}');
  });

  test('pair granted parses (Rust fixture)', () {
    final r = PairResult.fromJson(jsonDecode(
            '{"pair":"granted","device_id":"dev-9","token":"t9","role":"producer"}')
        as Map<String, dynamic>);
    expect(r, isA<PairGranted>());
    final g = r as PairGranted;
    expect(g.deviceId, 'dev-9');
    expect(g.token, 't9');
    expect(g.role, 'producer');
  });

  test('denied parses (Rust fixture)', () {
    final m = ServerMessage.fromJson(
        jsonDecode('{"event":"denied","request_id":7,"reason":"forbidden"}')
            as Map<String, dynamic>);
    expect(m, isA<Denied>());
    expect((m as Denied).reason, 'forbidden');
  });

  test('operator_state parses with timer (Rust fixture)', () {
    const fixture =
        '{"event":"operator_state","view":{"plan_name":"Sunday","items":'
        '[{"id":1,"kind":"song","title":"Opening","is_live":true,"is_staged":false}],'
        '"live_index":0,"staged_index":null,"blackout":false,'
        '"timer":{"remaining_secs":90,"elapsed_secs":30,"time_up":false,"warn":false,"running":true}}}';
    final m =
        ServerMessage.fromJson(jsonDecode(fixture) as Map<String, dynamic>);
    expect(m, isA<OperatorState>());
    final v = (m as OperatorState).view;
    expect(v.planName, 'Sunday');
    expect(v.items, hasLength(1));
    expect(v.items.first.isLive, isTrue);
    expect(v.liveIndex, 0);
    expect(v.stagedIndex, isNull);
    expect(v.timer!.remainingSecs, 90);
    expect(v.timer!.running, isTrue);
  });

  test('unknown events degrade gracefully', () {
    final m = ServerMessage.fromJson(
        jsonDecode('{"event":"something_new","x":1}') as Map<String, dynamic>);
    expect(m, isA<UnknownMessage>());
  });

  test('stage_scripture command matches the Rust wire shape', () {
    expect(cmdStageScripture('Romans 8:28'),
        {'cmd': 'stage_scripture', 'reference': 'Romans 8:28'});
  });

  test('operator_state tolerates the desktop-only outputs fields', () {
    // Mobile ignores outputs/displays (desktop console surface) — parsing a
    // frame that carries them must not throw or disturb the known fields.
    final v = OperatorStateView.fromJson({
      'plan_name': 'Sunday',
      'items': [],
      'live_index': null,
      'staged_index': null,
      'blackout': false,
      'timer': null,
      'outputs': [
        {'role': 'main', 'display': 'Projector', 'width': 1920, 'height': 1080, 'assigned': true}
      ],
      'displays': [
        {'key': 'Projector|1920x1080', 'name': 'Projector', 'width': 1920, 'height': 1080}
      ],
    });
    expect(v.planName, 'Sunday');
    expect(v.blackout, isFalse);
  });

  test('operator_state parses scripture fields (and their absence)', () {
    // The EXACT string the Rust serializer pins in
    // selahcue-lan/tests/test_protocol.rs (wire_fixtures...) — change together.
    const fixture =
        '{"event":"operator_state","view":{"plan_name":"Sunday","items":[],'
        '"live_index":null,"staged_index":null,"blackout":false,"timer":null,'
        '"staged_scripture":"Romans 8:28","live_scripture":"John 3:16",'
        '"live_free_text":"Removed Song"}}';
    final frame = jsonDecode(fixture) as Map<String, dynamic>;
    final withScripture =
        OperatorStateView.fromJson(frame['view'] as Map<String, dynamic>);
    expect(withScripture.stagedScripture, 'Romans 8:28');
    expect(withScripture.liveScripture, 'John 3:16');
    expect(withScripture.liveFreeText, 'Removed Song');
    // Absent fields (the wire omits them when None) parse as null.
    final without = OperatorStateView.fromJson({
      'plan_name': 'Sunday',
      'items': [],
      'live_index': 0,
      'staged_index': null,
      'blackout': false,
      'timer': null,
    });
    expect(without.stagedScripture, isNull);
    expect(without.liveScripture, isNull);
  });

}
