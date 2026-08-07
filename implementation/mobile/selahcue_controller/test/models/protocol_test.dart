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

  test('hello pair appends an optional platform last', () {
    // The optional platform is added last and omitted when empty, so it stays byte-compatible
    // with the Rust `PairRequest` (skip-when-empty) and the pinned no-platform fixture above.
    expect(
      jsonEncode(helloPair('ABCD2345', 'Phone', platform: 'ios')),
      '{"hello":"pair","v":2,"code":"ABCD2345","device_name":"Phone","platform":"ios"}',
    );
    expect(
      jsonEncode(helloPair('ABCD2345', 'Phone', platform: '')),
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
    // S8-3b — mirrors the Rust `set_theme` fixture exactly.
    expect(jsonEncode(cmdSetTheme('high-contrast')),
        '{"cmd":"set_theme","name":"high-contrast"}');
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

  test('adjust_timer command matches the Rust wire shape', () {
    expect(cmdAdjustTimer(60), {'cmd': 'adjust_timer', 'delta_secs': 60});
    expect(cmdAdjustTimer(-60), {'cmd': 'adjust_timer', 'delta_secs': -60});
  });

  test('stage_scripture command matches the Rust wire shape', () {
    expect(cmdStageScripture('Romans 8:28'),
        {'cmd': 'stage_scripture', 'reference': 'Romans 8:28'});
    // Translation is skip-if-none (byte-identical to the old shape when absent).
    expect(cmdStageScripture('Romans 8:28', translation: 'WEB'), {
      'cmd': 'stage_scripture',
      'reference': 'Romans 8:28',
      'translation': 'WEB',
    });
  });

  test('get_chapter command matches the Rust wire shape', () {
    expect(jsonEncode(cmdGetChapter('Romans 8')),
        '{"cmd":"get_chapter","reference":"Romans 8"}');
    expect(jsonEncode(cmdGetChapter('Romans 8', translation: 'WEB')),
        '{"cmd":"get_chapter","reference":"Romans 8","translation":"WEB"}');
  });

  test('chapter reply parses (Rust fixture)', () {
    const fixture =
        '{"event":"chapter","book_name":"Romans","chapter":8,"translation":"KJV",'
        '"verses":[{"number":28,"text":"And we know…"}],'
        '"prev_ref":"Romans 7","next_ref":"Romans 9"}';
    final m =
        ServerMessage.fromJson(jsonDecode(fixture) as Map<String, dynamic>);
    expect(m, isA<ChapterResult>());
    final ch = m as ChapterResult;
    expect(ch.bookName, 'Romans');
    expect(ch.chapter, 8);
    expect(ch.translation, 'KJV');
    expect(ch.heading, 'Romans 8 (KJV)');
    expect(ch.verses, hasLength(1));
    expect(ch.verses.first.number, 28);
    expect(ch.verses.first.reference('Romans', 8), 'Romans 8:28');
    expect(ch.prevRef, 'Romans 7');
    expect(ch.nextRef, 'Romans 9');
  });

  test('chapter reply at a canon edge omits the missing neighbour', () {
    const fixture =
        '{"event":"chapter","book_name":"Genesis","chapter":1,"translation":"KJV",'
        '"verses":[{"number":1,"text":"In the beginning…"}],"next_ref":"Genesis 2"}';
    final ch = ServerMessage.fromJson(jsonDecode(fixture) as Map<String, dynamic>)
        as ChapterResult;
    expect(ch.prevRef, isNull);
    expect(ch.nextRef, 'Genesis 2');
  });

  test('operator_state parses the advertised translation list', () {
    final v = OperatorStateView.fromJson({
      'plan_name': 'Sunday',
      'items': const [],
      'blackout': false,
      'translations': const ['KJV', 'WEB', 'ASV'],
    });
    expect(v.translations, ['KJV', 'WEB', 'ASV']);
    // Absent = empty (the host doesn't advertise them).
    final v2 = OperatorStateView.fromJson({'plan_name': 'X', 'items': const []});
    expect(v2.translations, isEmpty);
  });

  test('operator_state parses the active theme + offered themes (S8-3b)', () {
    // The EXACT string the Rust serializer pins in test_protocol.rs (the themed
    // operator_state fixture) — change both together.
    final v = OperatorStateView.fromJson(jsonDecode(
      '{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,'
      '"blackout":false,"timer":null,"theme":"lower-third",'
      '"themes":["classic","high-contrast","lower-third"]}',
    ) as Map<String, dynamic>);
    expect(v.theme, 'lower-third');
    expect(v.themes, ['classic', 'high-contrast', 'lower-third']);
    // An older host omits both — they parse to empty (the picker then hides).
    final v2 = OperatorStateView.fromJson({'plan_name': 'X', 'items': const []});
    expect(v2.theme, '');
    expect(v2.themes, isEmpty);
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


  test('PlanItemView parses old JSON without slide fields (S8-1)', () {
    // A pre-8a host omits slide fields; serde(default) parity on the Dart side.
    final it = PlanItemView.fromJson({
      'id': 9,
      'kind': 'song',
      'title': 'Old',
      'is_live': false,
      'is_staged': false,
    });
    expect(it.slideCount, isNull);
    expect(it.slideIndex, isNull);
    expect(it.slideBadge, '');
  });

  test('PlanItemView reads slide_count/slide_index and formats a badge (S8-1)',
      () {
    final it = PlanItemView.fromJson({
      'id': 2,
      'kind': 'song',
      'title': 'Way Maker',
      'is_live': true,
      'is_staged': false,
      'slide_count': 6,
      'slide_index': 2,
    });
    expect(it.slideCount, 6);
    expect(it.slideIndex, 2);
    expect(it.slideBadge, ' · 3/6'); // 1-based display
    // Count-only (not the live/staged item) shows "· N slides".
    final counted = PlanItemView.fromJson({
      'id': 3,
      'kind': 'song',
      'title': 'Hymn',
      'is_live': false,
      'is_staged': false,
      'slide_count': 4,
    });
    expect(counted.slideBadge, ' · 4 slides');
  });

}
