/// Live controller (C in MVC): owns the connection lifecycle and the
/// host-authoritative operator state the controller view renders — the 1s poll,
/// command dispatch, graceful reconnection (FR-093), and un-pairing. No widgets.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/protocol.dart';
import '../models/rbac.dart';
import '../models/session.dart';
import '../models/stored_session.dart';

class LiveController extends ChangeNotifier {
  ControllerSession _session;
  final StoredSession stored;

  OperatorStateView? _view;
  // Two independent notices with different lifetimes: a transient connection
  // status (set/cleared by reconnect+refresh) and a *sticky* command denial that
  // must survive the 1s poll so the operator can actually read it. A blind
  // `_error = null` on every successful refresh used to wipe the denial before
  // it could be seen — hence the split.
  String? _statusError;
  String? _denial;
  bool _reconnecting = false;
  bool _refreshing = false;
  bool _disposed = false;
  Timer? _poll;

  LiveController({required this._session, required this.stored}) {
    _poll = Timer.periodic(const Duration(seconds: 1), (_) => refresh());
    refresh();
  }

  OperatorStateView? get view => _view;

  /// The single message the banner surfaces. While reconnecting the connection
  /// status wins (nothing works until we are back); otherwise a pending denial
  /// takes priority over any stale status because it is the actionable one.
  String? get error =>
      _reconnecting ? (_statusError ?? _denial) : (_denial ?? _statusError);
  bool get reconnecting => _reconnecting;
  bool get blackout => _view?.blackout ?? false;

  /// The role the host granted this device. Reads through the CURRENT session,
  /// so a reconnect that re-roles the device is reflected once it lands.
  MobileRole get role => _session.grantedRole;

  /// Whether the granted role may perform [capability] (UX gate only; the server
  /// is still authoritative and denies anything this mirror gets wrong).
  bool can(Capability capability) => role.can(capability);

  void dismissError() {
    _denial = null;
    _statusError = null;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  /// Pull the host-authoritative operator view. Skipped while a previous poll is
  /// still in flight, so a slow link can never build an unbounded command backlog.
  Future<void> refresh() async {
    if (_reconnecting || _disposed || _refreshing) return;
    _refreshing = true;
    try {
      final view = await _session.operatorState();
      _view = view;
      // Connection is healthy — clear only the transient status. A pending
      // denial is left untouched so it survives the poll (see field docs).
      _statusError = null;
      _notify();
    } on SessionException {
      await _reconnect();
    } finally {
      _refreshing = false;
    }
  }

  /// Stage a plan item and — only if it actually landed in Preview — send it
  /// live in one gesture (mobile double-tap; mirrors the desktop's verified
  /// double-click so a denied stage never commits the wrong thing).
  Future<void> selectAndGoLive(int itemId) async {
    await act(cmdSelectItem(itemId));
    final v = _view;
    if (v == null) return;
    final idx = v.items.indexWhere((it) => it.id == itemId);
    if (idx >= 0 && v.stagedIndex == idx) {
      await act(cmdGoLive());
    }
  }

  /// Stage a scripture reference and, only if it landed in Preview, send it
  /// live in one action. `translation` stages the verse in the browsed text.
  Future<void> stageScriptureAndGoLive(String reference,
      {String? translation}) async {
    await act(cmdStageScripture(reference, translation: translation));
    if (_view?.stagedScripture == reference) {
      await act(cmdGoLive());
    }
  }

  /// Fetch a whole chapter's verses for the verse-list browser. Returns null on
  /// any non-chapter outcome — an older host that doesn't know `get_chapter`
  /// replies with `error`/unknown, a bad reference is denied — so the caller can
  /// fall back to reference-only staging. A read-only query: it does NOT touch
  /// the denial banner or refresh state.
  Future<ChapterResult?> fetchChapter(String reference,
      {String? translation}) async {
    // Retry once across a reconnect so a transient socket blip on the first
    // fetch isn't mistaken for an old host that lacks the command (which would
    // wrongly show the reference-only fallback on a perfectly capable host).
    for (var attempt = 0; attempt < 2 && !_disposed; attempt++) {
      try {
        final reply = await _session
            .command(cmdGetChapter(reference, translation: translation));
        return reply is ChapterResult ? reply : null;
      } on SessionException {
        await _reconnect();
      }
    }
    return null;
  }

  /// Send one command, surface a denial as a message, then re-render fresh state.
  Future<void> act(Map<String, dynamic> cmd) async {
    if (_disposed) return;
    try {
      final reply = await _session.command(cmd);
      if (reply is Denied) {
        _denial = 'Not allowed (${reply.reason}).';
        _notify();
      } else if (_denial != null) {
        // A command went through — the earlier denial notice is now stale.
        _denial = null;
        _notify();
      }
      await refresh();
    } on SessionException {
      await _reconnect();
    }
  }

  /// Graceful reconnection: retry with stored credentials until disposed; the
  /// desktop is authoritative and unaffected while we are away.
  Future<void> _reconnect() async {
    if (_reconnecting || _disposed) return;
    _reconnecting = true;
    _statusError = 'Connection lost — reconnecting…';
    _notify();
    // Release the broken session's socket before replacing it (no-leak rule) —
    // best-effort: the transport may already be gone.
    try {
      await _session.close();
    } on Object {
      // already closed / unreachable
    }
    while (!_disposed) {
      try {
        final fresh = await SelahSession.connect(
          host: stored.host,
          port: stored.port,
          pinHex: stored.pinHex,
          creds: Credentials(deviceId: stored.deviceId, token: stored.token),
        );
        if (_disposed) {
          await fresh.close();
          return;
        }
        _session = fresh;
        _reconnecting = false;
        _statusError = null;
        _notify();
        return;
      } on SessionException {
        await Future<void>.delayed(const Duration(seconds: 2));
      }
    }
  }

  /// Forget this device's credentials and close the connection.
  Future<void> unpair() async {
    // Stop polling and mark stopped BEFORE closing the socket, so no in-flight or next 1s refresh
    // tick can hit the closed session, fall into _reconnect(), and silently re-open with the stored
    // credentials the link the user just disconnected. (The same _disposed guard act()/refresh()/
    // _reconnect() already honour.)
    _disposed = true;
    _poll?.cancel();
    await StoredSession.clear();
    await _session.close();
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    _session.close();
    super.dispose();
  }
}
