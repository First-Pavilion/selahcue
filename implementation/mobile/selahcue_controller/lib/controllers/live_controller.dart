/// Live controller (C in MVC): owns the connection lifecycle and the
/// host-authoritative operator state the controller view renders — the 1s poll,
/// command dispatch, graceful reconnection (FR-093), and un-pairing. No widgets.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/protocol.dart';
import '../models/session.dart';
import '../models/stored_session.dart';

class LiveController extends ChangeNotifier {
  SelahSession _session;
  final StoredSession stored;

  OperatorStateView? _view;
  String? _error;
  bool _reconnecting = false;
  bool _refreshing = false;
  bool _disposed = false;
  Timer? _poll;

  LiveController({required this._session, required this.stored}) {
    _poll = Timer.periodic(const Duration(seconds: 1), (_) => refresh());
    refresh();
  }

  OperatorStateView? get view => _view;
  String? get error => _error;
  bool get reconnecting => _reconnecting;
  bool get blackout => _view?.blackout ?? false;

  void dismissError() {
    _error = null;
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
      _error = null;
      _notify();
    } on SessionException {
      await _reconnect();
    } finally {
      _refreshing = false;
    }
  }

  /// Send one command, surface a denial as a message, then re-render fresh state.
  Future<void> act(Map<String, dynamic> cmd) async {
    if (_disposed) return;
    try {
      final reply = await _session.command(cmd);
      if (reply is Denied) {
        _error = 'Not allowed (${reply.reason}).';
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
    _error = 'Connection lost — reconnecting…';
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
        _error = null;
        _notify();
        return;
      } on SessionException {
        await Future<void>.delayed(const Duration(seconds: 2));
      }
    }
  }

  /// Forget this device's credentials and close the connection.
  Future<void> unpair() async {
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
