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

/// What a single command round-trip actually achieved.
///
/// Only [applied] proves the host acknowledged the command **on a connection
/// that is still current**. Every other outcome means "unknown" — and for an
/// audience-facing follow-up, unknown must read as *no*, never as *probably*.
/// This distinction is the whole point: `act()` used to return `void`, so a
/// command swallowed by a socket blip was indistinguishable from one the host
/// actually ran (86ajxwcft).
///
/// [applied] deliberately does NOT promise that [LiveController.view] has caught
/// up with the command's effect. A caller that needs to reason about resulting
/// host state must re-read it — see `_confirmedView`.
enum CommandOutcome { applied, denied, failed }

class LiveController extends ChangeNotifier {
  ControllerSession _session;
  final StoredSession stored;

  /// How to open a fresh authenticated session on reconnect. Injected so the
  /// reconnect path is unit-testable without a real socket; defaults to the
  /// production `SelahSession.connect`. Typed to the [ControllerSession]
  /// interface (not the concrete `SelahSession`) so a test can substitute a
  /// fake *replacement* session and exercise what happens AFTER a reconnect
  /// lands — the window in which the stale-go-live race lives.
  final Future<ControllerSession> Function({
    required String host,
    required int port,
    required String pinHex,
    required Credentials creds,
  }) _connect;

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
  bool _revoked = false;
  Timer? _poll;

  /// Monotonic **connection epoch**, bumped every time [_session] is replaced.
  ///
  /// This is the spine of the stale-go-live fix. While we are away the desktop
  /// stays authoritative and may stage something else entirely, so an intent the
  /// operator formed against the pre-disconnect world cannot be carried across a
  /// reconnect. Comparing the epoch a command was sent under against the current
  /// one turns "did the world move under me?" into a cheap, local, exact check —
  /// no wire change, no host cooperation, no revision field required.
  int _epoch = 0;

  /// The epoch the currently held [_view] was fetched under. Starts behind
  /// [_epoch] because we have not read the host yet.
  int _viewEpoch = -1;

  LiveController({
    required this._session,
    required this.stored,
    Future<ControllerSession> Function({
      required String host,
      required int port,
      required String pinHex,
      required Credentials creds,
    })? connect,
  }) : _connect = connect ?? SelahSession.connect {
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

  /// True while we cannot prove what is on the audience screen *right now* —
  /// either the link is down, or it is back but the snapshot we hold still
  /// describes the pre-disconnect world.
  ///
  /// Controls stay disabled until this clears: "on reconnect, live state
  /// re-syncs BEFORE controls re-enable" (FR-097, COMPONENT-SPECS §12). Note
  /// that a live socket is not the same as a current view, which is why this is
  /// deliberately broader than [reconnecting].
  bool get syncing => _reconnecting || _viewEpoch != _epoch;

  bool get blackout => _view?.blackout ?? false;

  /// The device's credentials were revoked/unpaired by an admin — the app shows
  /// the "Access removed" screen and offers to re-pair. Terminal for this session.
  bool get revoked => _revoked;

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
    if (_reconnecting || _disposed || _refreshing || _revoked) return;
    _refreshing = true;
    try {
      final epoch = _epoch;
      final view = await _session.operatorState();
      // Only stamp if the connection did not change under us mid-fetch.
      if (_epoch != epoch) return;
      _view = view;
      _viewEpoch = epoch;
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

  /// Re-read host state with a snapshot we can prove was requested **after** the
  /// caller's command and carried by the **same** connection.
  ///
  /// Deliberately does not reuse [refresh], for two reasons that are exactly the
  /// bug: refresh coalesces with the 1s poll (`_refreshing`), and a coalesced
  /// result can predate the command; and refresh silently reconnects, whereas a
  /// go-live guard must treat "unknown" as *no*, not as *retry*.
  ///
  /// Bounded: one extra round-trip per operator gesture at most, and the session
  /// serialises command turns internally — no queue, no backlog, no growth.
  Future<OperatorStateView?> _confirmedView(int epoch) async {
    if (_disposed || _revoked || _reconnecting || _epoch != epoch) return null;
    try {
      final view = await _session.operatorState();
      // The connection must STILL be the one that carried the command; a swap
      // while this was in flight invalidates the answer.
      if (_disposed || _epoch != epoch) return null;
      _view = view;
      _viewEpoch = epoch;
      _statusError = null;
      _notify();
      return view;
    } on SessionException {
      await _reconnect();
      return null;
    }
  }

  /// Stage a plan item and — only if it actually landed in Preview — send it
  /// live in one gesture (mobile double-tap; mirrors the desktop's verified
  /// double-click so a denied stage never commits the wrong thing).
  ///
  /// The go-live half fires only when BOTH halves of the proof hold: the stage
  /// was acknowledged on this connection, and a snapshot fetched *afterwards on
  /// that same connection* still shows this item in Preview. Anything less and
  /// we stop — a missed go-live costs one more tap, a wrong one reaches the
  /// congregation (86ajxwcft).
  Future<void> selectAndGoLive(int itemId) async {
    final epoch = _epoch;
    if (await act(cmdSelectItem(itemId)) != CommandOutcome.applied) return;
    final v = await _confirmedView(epoch);
    if (v == null) return;
    final idx = v.items.indexWhere((it) => it.id == itemId);
    if (idx >= 0 && v.stagedIndex == idx) {
      await act(cmdGoLive());
    }
  }

  /// Stage a scripture reference and, only if it landed in Preview, send it
  /// live in one action. `translation` stages the verse in the browsed text.
  /// Same two-part proof as [selectAndGoLive].
  Future<void> stageScriptureAndGoLive(String reference,
      {String? translation}) async {
    final epoch = _epoch;
    final outcome =
        await act(cmdStageScripture(reference, translation: translation));
    if (outcome != CommandOutcome.applied) return;
    final v = await _confirmedView(epoch);
    if (v == null) return;
    if (v.stagedScripture == reference) {
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
  ///
  /// Returns what actually happened rather than `void`. The old signature made a
  /// command lost to a socket blip look exactly like one the host ran, which is
  /// what let a compound gesture go live on a stale premise (86ajxwcft).
  Future<CommandOutcome> act(Map<String, dynamic> cmd) async {
    if (_disposed || _revoked) return CommandOutcome.failed;
    // Refuse outright until we can prove what is on the audience screen — see
    // [syncing]: either the link is down, or it is back but the snapshot we hold
    // still describes the pre-disconnect world. Both mean the same thing for an
    // outgoing command, because both mean the operator formed the intent against
    // a host state this device cannot vouch for. Some commands even read their
    // *argument* out of that stale view (a detection id, a blackout direction).
    //
    // This is the whole gate, and it lives here rather than on each screen
    // because per-screen it was only ever three of the five command surfaces:
    // Live, Plan and the emergency strip checked `syncing`, Scripture and Timer
    // never did, and the suite stayed green because no test covered them. "No
    // ghost actions" (FR-097, COMPONENT-SPECS §12) has to be a property of the
    // controller, not of whichever screen remembered to disable a button.
    //
    // Nothing that must keep working DURING a re-sync passes through here:
    // refresh() and _confirmedView() read host state directly (they are the
    // re-sync), fetchChapter() is a read-only query so the scripture browser
    // stays usable, and unpair() — the recovery affordance — closes the session
    // without sending a command. Screens still disable their controls so a dead
    // button never looks live; this is the backstop that makes that cosmetic.
    if (syncing) return CommandOutcome.failed;
    // The connection this intent is being formed against.
    final epoch = _epoch;
    try {
      final reply = await _session.command(cmd);
      if (reply is Denied) {
        _denial = 'Not allowed (${reply.reason}).';
        _notify();
        await refresh();
        return CommandOutcome.denied;
      }
      if (_denial != null) {
        // A command went through — the earlier denial notice is now stale.
        _denial = null;
        _notify();
      }
      await refresh();
      // Acknowledged — but only "applied" if we are still on the connection that
      // carried it. A swap in between means the host we proved something about
      // is no longer the host we are talking to.
      return _epoch == epoch ? CommandOutcome.applied : CommandOutcome.failed;
    } on SessionException {
      await _reconnect();
      return CommandOutcome.failed;
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
        final fresh = await _connect(
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
        // A new connection: every snapshot taken and every intent formed against
        // the old one is now stale by definition.
        _epoch++;
        _reconnecting = false;
        _statusError = null;
        _notify();
        // Re-read host state promptly. Controls stay disabled until this lands
        // (see [syncing]), so without it the operator would face up to a full
        // poll interval of dead controls after every blip. Scheduled rather than
        // awaited because we are usually already inside refresh()'s own frame,
        // where the in-flight guard would swallow a direct call.
        Timer.run(refresh);
        return;
      } on SessionRevoked {
        // An admin unpaired/revoked this device — retrying can never succeed.
        // Stop, drop the dead credentials, and surface the revoked state so the
        // UI shows "Access removed → pair again". The desktop is unaffected.
        _revoked = true;
        _reconnecting = false;
        _poll?.cancel();
        try {
          await StoredSession.clear();
        } on Object {
          // best-effort — the revoked state is what matters
        }
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
