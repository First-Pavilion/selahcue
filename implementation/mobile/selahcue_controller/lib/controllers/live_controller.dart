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

/// The wire `DenyReason` that means "your role may not do this" — the closed set
/// lives in Rust (`selahcue-lan/src/protocol.rs:952`: `forbidden` /
/// `unauthenticated` / `bad_request`) and is pinned cross-language by the
/// protocol fixtures.
///
/// This single string is why the enforcement sheet needs no heuristics. A
/// malformed reference comes back `bad_request`, and telling an operator
/// "that's not in your role" for a typo would be a lie; only `forbidden` is a
/// role problem, whatever this client's capability mirror happens to believe.
const String denyReasonForbidden = 'forbidden';

/// A command the desktop refused **because of this device's role**.
///
/// Carries the parsed action rather than the raw wire string so the UI can say
/// what was refused and who could have done it (MOBILE-2.0-SPEC §4.10). [action]
/// is null when this build does not recognise the command — a real state, not an
/// error: the sheet then drops the roles card instead of inventing one.
@immutable
class PermissionDenial {
  /// The wire `DenyReason` (always [denyReasonForbidden] for a raised sheet).
  final String reason;

  /// What was attempted, or null when this mirror cannot name it.
  final CommandAction? action;

  /// The role held at the moment of the refusal.
  final MobileRole role;

  const PermissionDenial({
    required this.reason,
    required this.action,
    required this.role,
  });

  /// The roles that could have run this command, most-capable first. Empty when
  /// the command is unrecognised.
  List<MobileRole> get qualifyingRoles =>
      action == null ? const [] : rolesWith(action!.capability);

  /// The least-capable role that would have been enough — the honest single
  /// answer for `needs the <role> role`.
  MobileRole? get requiredRole =>
      action == null ? null : minimalRoleFor(action!.capability);
}

/// A role reassignment this device observed (MOBILE-2.0-SPEC §4.11).
///
/// A re-role is only ever visible as a DIFFERENCE between the role we were
/// acting under and the one the host is granting now — there is no "you were
/// demoted" frame on the wire. Diffing the capability sets is what turns "your
/// role changed" into the list of controls that just disappeared.
///
/// Where that difference shows up is the part that is easy to get wrong: the
/// desktop's `SetSessionRole` mutates the session registry and
/// `selahcue-lan/src/server.rs` re-derives the live authority from it **per
/// request**, so a re-role takes effect on the connection that is already open
/// (86ajxer8n). It is not a reconnect-only event.
@immutable
class RoleChange {
  final MobileRole from;
  final MobileRole to;
  const RoleChange({required this.from, required this.to});

  /// Capabilities the operator had a moment ago and no longer has.
  Set<Capability> get removed =>
      from.capabilities.difference(to.capabilities);

  /// Capabilities the change granted (an upgrade rather than a downgrade).
  Set<Capability> get gained => to.capabilities.difference(from.capabilities);

  /// True when controls were taken away — the case §4.11 draws.
  bool get isDowngrade => removed.isNotEmpty;
}

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
  // The three enforcement states (MOBILE-2.0-SPEC §4.10–§4.12). Each is a single
  // nullable/boolean slot that is REPLACED, never appended to — an enforcement
  // event is news, not a log, and a queue of them would be exactly the unbounded
  // growth the project forbids.
  PermissionDenial? _blocked;
  RoleChange? _roleChange;
  bool _rejected = false;
  bool _reconnecting = false;
  bool _refreshing = false;
  bool _acting = false;
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

  /// The role this device is currently acting under — the last grant actually
  /// OBSERVED from the session, and the single value both the capability gate
  /// ([role]) and the receipt ([roleChange]) are read from.
  ///
  /// Reading the gate straight off `_session.grantedRole` is what made an
  /// in-place re-role silent: the gating would move the instant the host changed
  /// its mind, with nothing left to compare against and therefore no receipt.
  /// Holding the observed grant here means the two can never disagree — every
  /// change to this field goes through [_syncRole], which raises the receipt in
  /// the same step.
  late MobileRole _knownRole;

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
    _knownRole = _session.grantedRole;
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

  /// The role the host granted this device — the last grant [_syncRole]
  /// observed. Reads through [_knownRole] rather than the live session so that
  /// gating and the [roleChange] receipt are the same observation: a control
  /// can never vanish without the receipt that explains it, and the receipt can
  /// never appear while a stale control is still under the operator's thumb.
  MobileRole get role => _knownRole;

  /// Whether the granted role may perform [capability] (UX gate only; the server
  /// is still authoritative and denies anything this mirror gets wrong).
  bool can(Capability capability) => role.can(capability);

  /// The pending role refusal, if the host said `forbidden` and nothing has
  /// dismissed it yet (MOBILE-2.0-SPEC §4.10).
  PermissionDenial? get blocked => _blocked;

  /// The role reassignment this device last observed, until dismissed
  /// (MOBILE-2.0-SPEC §4.11). Null when the role did not change.
  RoleChange? get roleChange => _roleChange;

  /// A command reached the wire and was lost with the connection — not queued,
  /// not retried (FR-097, MOBILE-2.0-SPEC §4.12).
  ///
  /// Deliberately NOT set by the pre-flight [syncing] refusal: a control that
  /// was already inert did not have an action "rejected", it simply never fired,
  /// and the connection banner already explains that state.
  bool get rejected => _rejected;

  /// True while a command — or a whole compound gesture ([selectAndGoLive],
  /// [stageScriptureAndGoLive]) — is still in flight.
  ///
  /// [act], [selectAndGoLive] and [stageScriptureAndGoLive] all share this ONE
  /// flag and refuse to start while it is already true (see each one's guard),
  /// rather than queueing behind whatever is in flight on `SelahSession._turn`
  /// — a burst of taps against a slow/dead host would otherwise each wait up
  /// to `commandTimeout` for the ones ahead of it, so the app looks hung for
  /// tens of seconds with no feedback even though every queued command
  /// eventually resolves. The compound gestures hold this claim for their
  /// FULL duration (every internal command plus the read between them), not
  /// just their first command — a narrower claim left the gap between their
  /// two commands unguarded, and a second tap landing there could interleave
  /// its own command with the gesture's own two on the wire. Exposed so a
  /// screen can also disable its controls while any of this is outstanding,
  /// mirroring how it already disables them for [syncing].
  bool get busy => _acting;

  void dismissError() {
    _denial = null;
    _statusError = null;
    _notify();
  }

  /// Close the permission sheet. Clears the denial NOTICE too, otherwise
  /// dismissing the sheet would hand the same refusal straight back as a red
  /// banner — the operator would have to dismiss one refusal twice.
  void dismissBlocked() {
    _blocked = null;
    _denial = null;
    _notify();
  }

  /// Dismiss the role-changed receipt. The role itself is unaffected — the
  /// receipt is a record of what already happened, never a control.
  void dismissRoleChange() {
    _roleChange = null;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  /// Observe the grant the session is carrying **now** and turn any difference
  /// from the role this device has been acting under into a [RoleChange].
  ///
  /// This is the one place [_knownRole] moves, and it is called from every path
  /// that touches the session — the 1s poll, the post-command re-read, each
  /// outgoing command, and the reconnect — rather than from the reconnect
  /// alone. A reconnect-only diff models a desktop that only re-roles on the
  /// next handshake, and that is not the desktop we have: `SetSessionRole`
  /// mutates the registry and `server.rs` re-derives authority per request, so
  /// the change lands on the OPEN socket (86ajxer8n). Diffing only across a
  /// reconnect meant an in-place downgrade silently took the controls with it —
  /// no FR-090 banner, no "PREVIOUS CONTROLS" receipt, and a permission sheet
  /// that would have named the role the operator no longer held.
  ///
  /// Bounded like the rest of the enforcement state: one slot, replaced. Two
  /// re-roles in a row leave the latest, never a queue.
  ///
  /// Returns true when the role moved; the caller decides when to notify, so a
  /// change can be published in the same frame as the state that caused it.
  bool _syncRole() {
    final granted = _session.grantedRole;
    if (granted == _knownRole) return false;
    _roleChange = RoleChange(from: _knownRole, to: granted);
    _knownRole = granted;
    return true;
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
      // The poll is the app's heartbeat, so it is also where an in-place
      // re-role is noticed: within one tick of the desktop changing this
      // device's grant, the gate moves and the receipt appears together.
      _syncRole();
      // Connection is healthy — clear only the transient status. A pending
      // denial is left untouched so it survives the poll (see field docs).
      _statusError = null;
      // The link is healthy AND live state has been re-read: exactly the
      // condition §4.12 gives for the action-rejected toast to retire itself.
      // A role refusal is NOT cleared here — that one is about the operator's
      // permissions, not the link, and re-reading state does not answer it.
      _rejected = false;
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
  /// Bounded: one extra round-trip per operator gesture at most. This has no
  /// single-flight guard of its own — it relies entirely on its caller having
  /// already claimed `_acting` for the gesture's full duration ([selectAndGoLive],
  /// [stageScriptureAndGoLive]). That was not always true: `_acting` used to be
  /// released as soon as the gesture's FIRST command settled, leaving this read
  /// unguarded for the rest of the gesture — a second tap in that window queued
  /// its own turn on `SelahSession._turn`, and could land it on the wire between
  /// this gesture's two commands. Never call this without `_acting` already true.
  Future<OperatorStateView?> _confirmedView(int epoch) async {
    if (_disposed || _revoked || _reconnecting || _epoch != epoch) return null;
    try {
      final view = await _session.operatorState();
      // The connection must STILL be the one that carried the command; a swap
      // while this was in flight invalidates the answer.
      if (_disposed || _epoch != epoch) return null;
      _view = view;
      _viewEpoch = epoch;
      _syncRole();
      _statusError = null;
      _rejected = false;
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
    if (_disposed || _revoked) return;
    // Claims `_acting` for the WHOLE gesture (both commands AND the
    // [_confirmedView] read between them), not just one command at a time —
    // see [act] and [_sendCommand]. A plain [act] call in between would see
    // this claim and reject itself, exactly like a double-tap on [act] does.
    if (_acting) return;
    if (syncing) return;
    _acting = true;
    _notify();
    try {
      final epoch = _epoch;
      if (await _sendCommand(cmdSelectItem(itemId)) !=
          CommandOutcome.applied) {
        return;
      }
      final v = await _confirmedView(epoch);
      if (v == null) return;
      final idx = v.items.indexWhere((it) => it.id == itemId);
      if (idx >= 0 && v.stagedIndex == idx) {
        await _sendCommand(cmdGoLive());
      }
    } finally {
      _acting = false;
      _notify();
    }
  }

  /// Stage a scripture reference and, only if it landed in Preview, send it
  /// live in one action. `translation` stages the verse in the browsed text.
  /// Same two-part proof, and the same single `_acting` claim spanning the
  /// whole gesture, as [selectAndGoLive].
  Future<void> stageScriptureAndGoLive(String reference,
      {String? translation}) async {
    if (_disposed || _revoked) return;
    if (_acting) return;
    if (syncing) return;
    _acting = true;
    _notify();
    try {
      final epoch = _epoch;
      final outcome = await _sendCommand(
          cmdStageScripture(reference, translation: translation));
      if (outcome != CommandOutcome.applied) return;
      final v = await _confirmedView(epoch);
      if (v == null) return;
      if (v.stagedScripture == reference) {
        await _sendCommand(cmdGoLive());
      }
    } finally {
      _acting = false;
      _notify();
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
    // Refuse a second command while one is still in flight, the same shape
    // [refresh] already guards with `_refreshing`. Without this, a double-tap
    // (a misfire, or an impatient tap against a slow link) queues a second
    // command behind the first on `SelahSession._turn` instead of being
    // rejected: each queued command then waits up to `commandTimeout` for the
    // ones ahead of it, so a burst of N taps can take up to N x
    // commandTimeout to drain before the operator gets any feedback. Not set
    // via [_rejected] — like the [syncing] pre-flight refusal below, this
    // command never reached the wire, so it was never "rejected" as
    // MOBILE-2.0-SPEC §4.12 uses that word.
    //
    // [selectAndGoLive] and [stageScriptureAndGoLive] claim this SAME flag for
    // their WHOLE compound gesture, not just each inner command, and call
    // [_sendCommand] directly instead of this method once they hold it — see
    // there for why. Without that, the gap between a compound gesture's own
    // two commands was exactly as unguarded as a bare double-tap used to be:
    // 17tnw2ay2kk closed it here; a follow-up closed it for the compound
    // gestures too, after review proved an interleaved command could land ON
    // THE WIRE between a gesture's stage and its go-live.
    if (_acting) return CommandOutcome.failed;
    if (syncing) return CommandOutcome.failed;
    // Claimed and published before anything else runs — in particular before
    // [_syncRole]'s own [_notify] below, which calls listeners synchronously.
    // A listener that reacts to that notification by calling [act] again must
    // see `_acting` already true, or the guard above would not have seen it
    // yet either and a second command would slip in through the same
    // re-entrant call this guard exists to stop.
    _acting = true;
    _notify();
    try {
      return await _sendCommand(cmd);
    } finally {
      // Published on this edge too, not just the rising one: without this a
      // screen gating its controls on [busy] would see it clear only on the
      // next 1s poll tick, leaving a control that looks dead for up to a
      // second after the command it was waiting on already finished — the
      // same symptom this guard exists to fix, reintroduced on the other
      // edge.
      _acting = false;
      _notify();
    }
  }

  /// The body of [act] — everything EXCEPT claiming/releasing `_acting`.
  ///
  /// [act] itself is the thin single-command wrapper: guard, claim, call this,
  /// release. [selectAndGoLive] and [stageScriptureAndGoLive] call this
  /// directly, for BOTH of their internal commands, having already claimed
  /// `_acting` once for the whole gesture — calling [act] a second time there
  /// would just see its own claim and reject itself.
  ///
  /// Never call this without `_acting` already true. It has no guard of its
  /// own by design: guarding is the caller's job, because the caller is the
  /// one who knows how many commands its gesture needs under one claim.
  ///
  /// [syncing] IS still checked in here, every call — unlike the single-flight
  /// guard, it can flip true partway through a multi-command gesture (e.g. a
  /// reconnect triggered by [_confirmedView]'s own `SessionException`), and
  /// the second command must see that live, not a snapshot from before the
  /// gesture started.
  Future<CommandOutcome> _sendCommand(Map<String, dynamic> cmd) async {
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
    try {
      // The gate this command is about to be judged against. Cheap, local,
      // and taken before the send so a re-role that landed between two taps
      // is news the operator gets now rather than one poll later.
      if (_syncRole()) _notify();
      // The connection this intent is being formed against.
      final epoch = _epoch;
      final reply = await _session.command(cmd);
      // The host answered; re-observe the grant before interpreting the answer,
      // so a `forbidden` raised below names the role the operator holds NOW
      // rather than the one they held when they reached for the control.
      final reRoled = _syncRole();
      if (reply is Denied) {
        _denial = 'Not allowed (${reply.reason}).';
        // Only a ROLE refusal raises the enforcement sheet. `bad_request` (an
        // unknown reference, a stale detection id) and `unauthenticated` are not
        // things a different role would fix, and "That's not in your role" would
        // simply be untrue for them — they keep the notice banner.
        if (reply.reason == denyReasonForbidden) {
          _blocked = PermissionDenial(
            reason: reply.reason,
            action: commandActionFor(cmd),
            role: role,
          );
        }
        _notify();
        await refresh();
        return CommandOutcome.denied;
      }
      if (_denial != null) {
        // A command went through — the earlier denial notice is now stale.
        _denial = null;
        _notify();
      } else if (reRoled) {
        _notify();
      }
      await refresh();
      // Acknowledged — but only "applied" if we are still on the connection that
      // carried it. A swap in between means the host we proved something about
      // is no longer the host we are talking to.
      if (_epoch == epoch) return CommandOutcome.applied;
      // The pairing moved under a command that was already on the wire. Nothing
      // is replayed; the operator is told the action was dropped (§4.12).
      _rejected = true;
      _notify();
      return CommandOutcome.failed;
    } on SessionException {
      // Same story, one step earlier: the command left this device and the link
      // died before it could be acknowledged. "Rejected" is the honest word —
      // it did not run, and it will not be retried.
      _rejected = true;
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
        // A reconnect can ALSO carry a new grant (the handshake re-issues it),
        // so diff here too — before anything else reads the new session. Same
        // helper, same one slot: the controls vanish immediately (FR-090) and
        // the receipt is the only trace of WHY, since otherwise a chip in the
        // app bar would quietly change word and nothing else would say so.
        _syncRole();
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
