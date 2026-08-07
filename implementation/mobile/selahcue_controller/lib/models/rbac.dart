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
