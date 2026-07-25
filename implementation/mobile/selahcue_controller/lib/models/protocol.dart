/// The SelahCue LAN control wire protocol (Dart mirror of
/// `implementation/desktop/crates/selahcue-lan/src/protocol.rs`).
///
/// The JSON shapes are pinned by the Rust side's
/// `wire_fixtures_are_stable_for_cross_language_clients` test and mirrored in
/// `test/models/protocol_test.dart` — change both together (with a VERSION bump).
library;

/// Wire protocol version (v2: tagged `hello` first frame).
const int wireVersion = 2;

/// First frame: authenticate with stored credentials.
Map<String, dynamic> helloAuth(String deviceId, String token) => {
      'hello': 'auth',
      'v': wireVersion,
      'device_id': deviceId,
      'token': token,
    };

/// First frame: redeem a pairing code (the operator must confirm on the host).
Map<String, dynamic> helloPair(String code, String deviceName) => {
      'hello': 'pair',
      'v': wireVersion,
      'code': code,
      'device_name': deviceName,
    };

/// A command request frame. Commands are internally tagged: `{'cmd': 'go_live'}`,
/// `{'cmd': 'select_item', 'item_id': 3}`, ...
Map<String, dynamic> request(int requestId, Map<String, dynamic> command) => {
      'v': wireVersion,
      'request_id': requestId,
      'command': command,
    };

Map<String, dynamic> cmdNext() => {'cmd': 'next'};
Map<String, dynamic> cmdPrevious() => {'cmd': 'previous'};
Map<String, dynamic> cmdGoLive() => {'cmd': 'go_live'};
Map<String, dynamic> cmdClear() => {'cmd': 'clear'};
Map<String, dynamic> cmdBlackout(bool on) => {'cmd': 'blackout', 'on': on};
Map<String, dynamic> cmdSelectItem(int itemId) =>
    {'cmd': 'select_item', 'item_id': itemId};
Map<String, dynamic> cmdStartTimer(int seconds) =>
    {'cmd': 'start_timer', 'seconds': seconds};
Map<String, dynamic> cmdStopTimer() => {'cmd': 'stop_timer'};
Map<String, dynamic> cmdAdjustTimer(int deltaSecs) =>
    {'cmd': 'adjust_timer', 'delta_secs': deltaSecs};
Map<String, dynamic> cmdStageScripture(String reference, {String? translation}) =>
    {'cmd': 'stage_scripture', 'reference': reference, 'translation': ?translation};
Map<String, dynamic> cmdGetOperatorState() => {'cmd': 'get_operator_state'};

/// Fetch a whole chapter's verses (read-only) so the mobile verse list mirrors
/// the desktop browser. `translation` omitted = the host's KJV default. An older
/// host that predates this command replies with `error`/unknown — the caller
/// degrades gracefully to reference-only staging.
Map<String, dynamic> cmdGetChapter(String reference, {String? translation}) => {
      'cmd': 'get_chapter',
      'reference': reference,
      'translation': ?translation,
    };

/// One plan item as the operator/host reports it.
class PlanItemView {
  final int id;
  final String kind;
  final String title;
  final bool isLive;
  final bool isStaged;

  /// Slide count for multi-slide items (songs, S8-1); null = single slide.
  final int? slideCount;

  /// Current within-item slide (0-based), present for the live/staged item.
  final int? slideIndex;

  const PlanItemView({
    required this.id,
    required this.kind,
    required this.title,
    required this.isLive,
    required this.isStaged,
    this.slideCount,
    this.slideIndex,
  });

  static PlanItemView fromJson(Map<String, dynamic> j) => PlanItemView(
        id: j['id'] as int,
        kind: j['kind'] as String? ?? '',
        title: j['title'] as String? ?? '',
        isLive: j['is_live'] as bool? ?? false,
        isStaged: j['is_staged'] as bool? ?? false,
        slideCount: j['slide_count'] as int?,
        slideIndex: j['slide_index'] as int?,
      );

  /// A human "Song · 2/6"-style suffix for multi-slide items (empty otherwise).
  String get slideBadge {
    final c = slideCount;
    if (c == null) return '';
    final pos = slideIndex;
    return pos != null ? ' · ${pos + 1}/$c' : ' · $c slides';
  }
}

/// The host's active-timer snapshot.
class TimerSnapshot {
  final int? remainingSecs;
  final int elapsedSecs;
  final bool timeUp;
  final bool warn;
  final bool running;

  const TimerSnapshot({
    required this.remainingSecs,
    required this.elapsedSecs,
    required this.timeUp,
    required this.warn,
    required this.running,
  });

  static TimerSnapshot fromJson(Map<String, dynamic> j) => TimerSnapshot(
        remainingSecs: j['remaining_secs'] as int?,
        elapsedSecs: j['elapsed_secs'] as int? ?? 0,
        timeUp: j['time_up'] as bool? ?? false,
        warn: j['warn'] as bool? ?? false,
        running: j['running'] as bool? ?? false,
      );
}

/// The host-authoritative operator view (reply to `get_operator_state`).
class OperatorStateView {
  final String planName;
  final List<PlanItemView> items;
  final int? liveIndex;
  final int? stagedIndex;
  final bool blackout;
  final TimerSnapshot? timer;

  /// Scripture reference staged in Preview (when no plan item is staged).
  final String? stagedScripture;

  /// Scripture reference on the Live output, if any.
  final String? liveScripture;

  /// A removed-but-still-on-screen plan item's title on Live (a free slide).
  final String? liveFreeText;

  /// Translation codes THIS host can stage/browse (the picker must only offer
  /// these). Empty when the host doesn't advertise them (fall back to KJV).
  final List<String> translations;

  const OperatorStateView({
    required this.planName,
    required this.items,
    required this.liveIndex,
    required this.stagedIndex,
    required this.blackout,
    required this.timer,
    this.stagedScripture,
    this.liveScripture,
    this.liveFreeText,
    this.translations = const [],
  });

  static OperatorStateView fromJson(Map<String, dynamic> j) => OperatorStateView(
        planName: j['plan_name'] as String? ?? '',
        items: ((j['items'] as List?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(PlanItemView.fromJson)
            .toList(),
        liveIndex: j['live_index'] as int?,
        stagedIndex: j['staged_index'] as int?,
        blackout: j['blackout'] as bool? ?? false,
        timer: j['timer'] == null
            ? null
            : TimerSnapshot.fromJson(j['timer'] as Map<String, dynamic>),
        stagedScripture: j['staged_scripture'] as String?,
        liveScripture: j['live_scripture'] as String?,
        liveFreeText: j['live_free_text'] as String?,
        translations: ((j['translations'] as List?) ?? const [])
            .whereType<String>()
            .toList(),
      );
}

/// A parsed operator → controller message (`{'event': ...}` tagged).
sealed class ServerMessage {
  const ServerMessage();

  /// Parse a server frame; returns [UnknownMessage] for unrecognized events
  /// (never throws on well-formed JSON of an unknown shape).
  static ServerMessage fromJson(Map<String, dynamic> j) {
    switch (j['event']) {
      case 'ack':
        return Ack(j['request_id'] as int? ?? 0);
      case 'denied':
        return Denied(j['request_id'] as int? ?? 0, j['reason'] as String? ?? '');
      case 'operator_state':
        return OperatorState(
            OperatorStateView.fromJson(j['view'] as Map<String, dynamic>? ?? {}));
      case 'chapter':
        return ChapterResult.fromJson(j);
      case 'error':
        return ErrorMessage(j['message'] as String? ?? '');
      default:
        return UnknownMessage(j);
    }
  }
}

class Ack extends ServerMessage {
  final int requestId;
  const Ack(this.requestId);
}

class Denied extends ServerMessage {
  final int requestId;
  final String reason;
  const Denied(this.requestId, this.reason);
}

class OperatorState extends ServerMessage {
  final OperatorStateView view;
  const OperatorState(this.view);
}

class ErrorMessage extends ServerMessage {
  final String message;
  const ErrorMessage(this.message);
}

class UnknownMessage extends ServerMessage {
  final Map<String, dynamic> raw;
  const UnknownMessage(this.raw);
}

/// One verse of a fetched chapter (mirror of Rust `VerseView`).
class VerseView {
  final int number;
  final String text;
  const VerseView(this.number, this.text);

  static VerseView fromJson(Map<String, dynamic> j) =>
      VerseView(j['number'] as int? ?? 0, j['text'] as String? ?? '');

  /// The stageable reference for this verse within [bookName]/[chapter]
  /// (e.g. `"Romans 8:28"` — parses on the host).
  String reference(String bookName, int chapter) => '$bookName $chapter:$number';
}

/// Reply to `get_chapter`: a whole chapter's numbered verses plus the
/// neighbouring-chapter references for ‹ › paging (null at the canon ends).
class ChapterResult extends ServerMessage {
  final String bookName;
  final int chapter;
  final String translation;
  final List<VerseView> verses;
  final String? prevRef;
  final String? nextRef;

  const ChapterResult({
    required this.bookName,
    required this.chapter,
    required this.translation,
    required this.verses,
    this.prevRef,
    this.nextRef,
  });

  static ChapterResult fromJson(Map<String, dynamic> j) => ChapterResult(
        bookName: j['book_name'] as String? ?? '',
        chapter: j['chapter'] as int? ?? 0,
        translation: j['translation'] as String? ?? '',
        verses: ((j['verses'] as List?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(VerseView.fromJson)
            .toList(),
        prevRef: j['prev_ref'] as String?,
        nextRef: j['next_ref'] as String?,
      );

  /// The header the browser shows, e.g. `"Romans 8 (KJV)"`.
  String get heading => '$bookName $chapter ($translation)';
}

/// The reply to a `pair` hello (`{'pair': 'granted'|'rejected'}` tagged).
sealed class PairResult {
  const PairResult();

  static PairResult fromJson(Map<String, dynamic> j) {
    switch (j['pair']) {
      case 'granted':
        return PairGranted(
          deviceId: j['device_id'] as String? ?? '',
          token: j['token'] as String? ?? '',
          role: j['role'] as String? ?? '',
        );
      case 'rejected':
        return PairRejected(j['reason'] as String? ?? '');
      default:
        return const PairRejected('malformed reply');
    }
  }
}

class PairGranted extends PairResult {
  final String deviceId;
  final String token;
  final String role;
  const PairGranted({required this.deviceId, required this.token, required this.role});
}

class PairRejected extends PairResult {
  final String reason;
  const PairRejected(this.reason);
}

/// The reply to an `auth` hello (`{'auth': 'granted'|'rejected'}` tagged).
sealed class AuthResult {
  const AuthResult();

  static AuthResult fromJson(Map<String, dynamic> j) {
    switch (j['auth']) {
      case 'granted':
        return AuthGranted(j['role'] as String? ?? '');
      case 'rejected':
        return AuthRejected(j['reason'] as String? ?? '');
      default:
        return const AuthRejected('malformed reply');
    }
  }
}

class AuthGranted extends AuthResult {
  final String role;
  const AuthGranted(this.role);
}

class AuthRejected extends AuthResult {
  final String reason;
  const AuthRejected(this.reason);
}
