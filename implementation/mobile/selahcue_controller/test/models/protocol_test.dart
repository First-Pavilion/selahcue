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
}
