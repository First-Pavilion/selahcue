/// Client-side mirror of the desktop's role-based access control
/// (`implementation/desktop/crates/selahcue-lan/src/rbac.rs`).
///
/// Enforcement is 100% server-side: the desktop calls `authorize(role, cmd)`
/// before acting and fail-closes. This mirror is a UX affordance ONLY — it
/// decides which controls the app OFFERS for the granted role, never what is
/// permitted. If it drifts, the server still denies (surfaced as a `Denied`
/// banner). The role→capability table is transcribed verbatim from
/// `Role::permissions()` (rbac.rs:62-91); `rbac_test.dart` pins it.
///
/// Remote paired devices can never be granted `operator` (the desktop clamps
/// remote roles below Operator), so `producer`/`assistant`/`viewer` are the
/// achievable phone roles; `operator` is mirrored for completeness.
library;

/// A capability a role may hold — mirror of Rust `Permission` (rbac.rs:29-58).
enum Capability {
  goLive,
  navigate,
  clearLive,
  blackout,
  timer,
  searchScripture,
  transcribe,
  monitor,
  editPlan,
  manageDevices,
  configureOutputs,
}

/// The role the host granted this device — mirror of Rust `Role` (rbac.rs:13-26),
/// plus `unknown` for an unrecognised/empty wire string (deny-all, fail-closed).
enum MobileRole {
  operator,
  producer,
  assistant,
  viewer,
  unknown;

  /// Parse the snake_case wire string (`PairGranted.role`/`AuthGranted.role`).
  /// Anything unrecognised (older/newer host, empty) → [unknown] = no capabilities.
  static MobileRole parse(String? wire) {
    switch (wire) {
      case 'operator':
        return MobileRole.operator;
      case 'producer':
        return MobileRole.producer;
      case 'assistant':
        return MobileRole.assistant;
      case 'viewer':
        return MobileRole.viewer;
      default:
        return MobileRole.unknown;
    }
  }

  /// The capabilities this role holds — verbatim from `Role::permissions()`
  /// (rbac.rs:62-91). Higher roles are supersets of lower ones.
  Set<Capability> get capabilities {
    switch (this) {
      case MobileRole.operator:
        return const {
          Capability.goLive,
          Capability.navigate,
          Capability.clearLive,
          Capability.blackout,
          Capability.timer,
          Capability.searchScripture,
          Capability.transcribe,
          Capability.monitor,
          Capability.manageDevices,
          Capability.editPlan,
          Capability.configureOutputs,
        };
      case MobileRole.producer:
        return const {
          Capability.goLive,
          Capability.navigate,
          Capability.clearLive,
          Capability.blackout,
          Capability.timer,
          Capability.searchScripture,
          Capability.transcribe,
          Capability.monitor,
        };
      case MobileRole.assistant:
        return const {
          Capability.searchScripture,
          Capability.navigate,
          Capability.monitor,
        };
      case MobileRole.viewer:
        return const {Capability.monitor};
      case MobileRole.unknown:
        return const {};
    }
  }

  /// Whether this role holds [capability] (mirror of `Role::can`).
  bool can(Capability capability) => capabilities.contains(capability);

  /// Short human label for the role badge / About sheet — the REAL granted
  /// backend role, not the 7-role design vocabulary (a tracked follow-up).
  String get label {
    switch (this) {
      case MobileRole.operator:
        return 'Operator';
      case MobileRole.producer:
        return 'Producer';
      case MobileRole.assistant:
        return 'Assistant';
      case MobileRole.viewer:
        return 'Viewer';
      case MobileRole.unknown:
        return 'Unknown';
    }
  }
}

/// A human name for a capability, used by the "PREVIOUS CONTROLS" receipt when
/// a role change takes controls away (MOBILE-2.0-SPEC §4.11). These are the
/// operator's words for the control, not the wire's — "Go live", not `go_live`.
extension CapabilityLabel on Capability {
  String get label {
    switch (this) {
      case Capability.goLive:
        return 'Go live';
      case Capability.navigate:
        return 'Next / Previous';
      case Capability.clearLive:
        return 'Clear live';
      case Capability.blackout:
        return 'Blackout';
      case Capability.timer:
        return 'Service timer';
      case Capability.searchScripture:
        return 'Scripture search & staging';
      case Capability.transcribe:
        // NOT "Transcript". `Transcribe` is a WRITE grant: it gates exactly one
        // command, `IngestTranscript` — the STT ingestion channel
        // (`selahcue-lan/src/rbac.rs:127`) — and no client on a phone sends it.
        // READING the transcript rides inside `GetOperatorState`, which needs
        // only `Monitor`. Labelled "Transcript", the role-changed receipt told
        // a demoted Viewer their transcript had been removed while the row two
        // below correctly promised they could still watch it. Naming the grant
        // for what it actually is settles that in favour of the truth.
        return 'Live transcription feed';
      case Capability.monitor:
        return 'Watch previews';
      case Capability.editPlan:
        return 'Edit the plan';
      case Capability.manageDevices:
        return 'Manage devices';
      case Capability.configureOutputs:
        return 'Configure outputs';
    }
  }
}

/// What a wire command needs, and how to say it to the operator.
///
/// [capability] is transcribed from Rust `required_permission(cmd)`
/// (`selahcue-lan/src/rbac.rs:100`) for the commands THIS client can send —
/// the desktop is still the authority, this only lets a refusal be explained in
/// words instead of a raw wire reason.
class CommandAction {
  /// The permission the desktop checks before running the command.
  final Capability capability;

  /// Sentence-leading gerund for the blocked-sheet body: "Approving scripture".
  final String phrase;

  /// Overline form for `ROLES THAT CAN <verb>`: "APPROVE SCRIPTURE".
  final String verb;

  const CommandAction(this.capability, this.phrase, this.verb);
}

const Map<String, CommandAction> _commandActions = {
  'go_live': CommandAction(Capability.goLive, 'Going live', 'GO LIVE'),
  'next': CommandAction(
      Capability.navigate, 'Moving to the next item', 'MOVE THROUGH THE PLAN'),
  'previous': CommandAction(Capability.navigate,
      'Moving to the previous item', 'MOVE THROUGH THE PLAN'),
  'select_item':
      CommandAction(Capability.navigate, 'Staging a plan item', 'STAGE AN ITEM'),
  'select_slide':
      CommandAction(Capability.navigate, 'Staging a slide', 'STAGE A SLIDE'),
  'clear': CommandAction(
      Capability.clearLive, 'Clearing the live output', 'CLEAR THE OUTPUT'),
  'blackout': CommandAction(
      Capability.blackout, 'Blacking out the output', 'BLACK OUT THE OUTPUT'),
  'start_timer':
      CommandAction(Capability.timer, 'Starting the timer', 'RUN THE TIMER'),
  'stop_timer':
      CommandAction(Capability.timer, 'Stopping the timer', 'RUN THE TIMER'),
  'adjust_timer':
      CommandAction(Capability.timer, 'Adjusting the timer', 'RUN THE TIMER'),
  'pause_timer':
      CommandAction(Capability.timer, 'Pausing the timer', 'RUN THE TIMER'),
  'resume_timer':
      CommandAction(Capability.timer, 'Resuming the timer', 'RUN THE TIMER'),
  'stage_scripture': CommandAction(
      Capability.searchScripture, 'Staging scripture', 'STAGE SCRIPTURE'),
  'get_chapter': CommandAction(
      Capability.searchScripture, 'Browsing scripture', 'BROWSE SCRIPTURE'),
  'approve_detection': CommandAction(
      Capability.searchScripture, 'Approving scripture', 'APPROVE SCRIPTURE'),
  'dismiss_detection': CommandAction(Capability.searchScripture,
      'Rejecting a detection', 'APPROVE SCRIPTURE'),
  'get_operator_state':
      CommandAction(Capability.monitor, 'Reading live state', 'WATCH PREVIEWS'),
  'set_theme': CommandAction(
      Capability.configureOutputs, 'Changing the theme', 'CONFIGURE OUTPUTS'),
};

/// What [cmd] needs, or null when this mirror does not recognise the command.
///
/// Null is a real answer, not a failure: a newer host may know commands this
/// build does not, and the enforcement sheet has a copy path for exactly that
/// case (spec §4.10 "if the app cannot name the qualifying roles"). Guessing
/// would be worse than saying less.
CommandAction? commandActionFor(Map<String, dynamic> cmd) =>
    _commandActions[cmd['cmd']];

/// The roles that hold [capability], most-capable first.
///
/// `unknown` is never listed — it is the fail-closed parse of a role string this
/// build does not recognise, not something an administrator can assign.
List<MobileRole> rolesWith(Capability capability) => [
      for (final r in MobileRole.values)
        if (r != MobileRole.unknown && r.can(capability)) r,
    ];

/// The LEAST-capable role that holds [capability], or null if none does.
///
/// Well-defined because the roles form a strict superset ladder
/// (`viewer ⊂ assistant ⊂ producer ⊂ operator`, mirrored from
/// `Role::permissions()`), so "the role you need" has one honest answer rather
/// than a list — which is what the blocked sheet's body line asks for.
MobileRole? minimalRoleFor(Capability capability) {
  final holders = rolesWith(capability);
  return holders.isEmpty ? null : holders.last;
}
