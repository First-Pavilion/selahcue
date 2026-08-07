# v2 Mobile Remote — Role-Aware Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Flutter controller consume its server-granted role and render only role-permitted controls across the v2 screens (Connect / Live / Scriptures / Timer), on the current 4-role backend.

**Architecture:** A pure Dart RBAC mirror (`lib/models/rbac.dart`) transcribes `selahcue-lan/src/rbac.rs`. The granted role travels with the session (`ControllerSession.grantedRole`) so it refreshes on reconnect; `LiveController.can(Capability)` is the single gate the views call. Enforcement stays 100% server-side — the mirror only decides what the UI *offers*. Controls a role lacks are **hidden** (owner decision D1).

**Tech Stack:** Flutter (Dart `^3.12.0`), plain `ChangeNotifier` (no state-mgmt package), `flutter_test` with hand-written fakes. No new dependencies.

## Global Constraints

- **No new dependencies.** Reuse existing packages only.
- **Server stays authoritative.** The Dart RBAC mirror is UX-only; every command is still `authorize()`-checked on the desktop, and `Denied` frames still surface via the existing banner.
- **Mirror `rbac.rs` verbatim.** `MobileRole.capabilities` must equal `Role::permissions()` (`implementation/desktop/crates/selahcue-lan/src/rbac.rs:62-91`). `rbac_test.dart` pins it.
- **Wire `v` stays 2.** No new command, no shape change. `pause_timer`/`resume_timer` already exist server-side (`protocol.rs:64,67`); this only adds Dart builders + fixtures.
- **Hide, don't disable** controls a role lacks (D1). Whole-screen-empty → read-only.
- **Omitted this pass (D2):** Send "TIME UP" to stage, Reset, 7-role labels — tracked in two follow-up tickets. Do **not** add them.
- **Accessibility:** keep `Semantics(button:…, label:…)` on every control (WCAG 1.4.1 — never colour alone), matching existing widgets.
- **Bounded memory:** no new unbounded queues/caches. (No new buffering is introduced here.)
- **Gate:** `make mobile-test` (flutter analyze + test) green. No `selahcue-lan` or wire-`VERSION` change.

---

### Task 1: RBAC mirror model

**Files:**
- Create: `implementation/mobile/selahcue_controller/lib/models/rbac.dart`
- Test: `implementation/mobile/selahcue_controller/test/models/rbac_test.dart`

**Interfaces:**
- Produces: `enum Capability { goLive, navigate, clearLive, blackout, timer, searchScripture, transcribe, monitor, editPlan, manageDevices, configureOutputs }`; `enum MobileRole { operator, producer, assistant, viewer, unknown }` with `static MobileRole parse(String?)`, `Set<Capability> get capabilities`, `bool can(Capability)`, `String get label`.

- [ ] **Step 1: Write the failing test**

```dart
// test/models/rbac_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/rbac.dart';

void main() {
  test('parse maps the wire strings and fails closed', () {
    expect(MobileRole.parse('operator'), MobileRole.operator);
    expect(MobileRole.parse('producer'), MobileRole.producer);
    expect(MobileRole.parse('assistant'), MobileRole.assistant);
    expect(MobileRole.parse('viewer'), MobileRole.viewer);
    expect(MobileRole.parse(''), MobileRole.unknown);
    expect(MobileRole.parse(null), MobileRole.unknown);
    expect(MobileRole.parse('root'), MobileRole.unknown);
  });

  test('capability sets mirror rbac.rs Role::permissions() verbatim', () {
    expect(MobileRole.producer.capabilities, {
      Capability.goLive, Capability.navigate, Capability.clearLive,
      Capability.blackout, Capability.timer, Capability.searchScripture,
      Capability.transcribe, Capability.monitor,
    });
    expect(MobileRole.assistant.capabilities,
        {Capability.searchScripture, Capability.navigate, Capability.monitor});
    expect(MobileRole.viewer.capabilities, {Capability.monitor});
    expect(MobileRole.unknown.capabilities, isEmpty);
    expect(MobileRole.operator.capabilities.length, Capability.values.length);
  });

  test('can() gates the live-output actions', () {
    expect(MobileRole.producer.can(Capability.goLive), isTrue);
    expect(MobileRole.assistant.can(Capability.goLive), isFalse);
    expect(MobileRole.assistant.can(Capability.navigate), isTrue);
    expect(MobileRole.assistant.can(Capability.searchScripture), isTrue);
    expect(MobileRole.assistant.can(Capability.timer), isFalse);
    expect(MobileRole.viewer.can(Capability.navigate), isFalse);
    expect(MobileRole.viewer.can(Capability.monitor), isTrue);
  });

  test('label is the real backend role name', () {
    expect(MobileRole.producer.label, 'Producer');
    expect(MobileRole.assistant.label, 'Assistant');
    expect(MobileRole.viewer.label, 'Viewer');
    expect(MobileRole.unknown.label, 'Unknown');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd implementation/mobile/selahcue_controller && flutter test test/models/rbac_test.dart`
Expected: FAIL — `Target of URI doesn't exist: 'package:selahcue_controller/models/rbac.dart'`.

- [ ] **Step 3: Write minimal implementation**

```dart
// lib/models/rbac.dart
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/models/rbac_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/models/rbac.dart test/models/rbac_test.dart
git commit -m "feat(mobile): client RBAC mirror of the 4-role backend (rbac.rs)"
```

---

### Task 2: Surface the granted role through the session and controller

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/models/session.dart` (interface `ControllerSession` ~line 43; `SelahSession` ~line 49)
- Modify: `implementation/mobile/selahcue_controller/lib/controllers/live_controller.dart` (add getters ~line 43)
- Modify: `implementation/mobile/selahcue_controller/test/controllers/live_controller_test.dart` (`FakeSession` ~line 9)
- Modify: `implementation/mobile/selahcue_controller/test/views/scripture_tab_test.dart` (`_Fake` ~line 12)
- Test: `implementation/mobile/selahcue_controller/test/controllers/live_controller_rbac_test.dart` (new)

**Interfaces:**
- Consumes: `MobileRole`, `Capability` (Task 1).
- Produces: `ControllerSession.grantedRole` → `MobileRole`; `LiveController.role` → `MobileRole`; `LiveController.can(Capability)` → `bool`.

- [ ] **Step 1: Write the failing test**

```dart
// test/controllers/live_controller_rbac_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';

class _RoleFake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _RoleFake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
      planName: 'S', items: [], liveIndex: null, stagedIndex: null,
      blackout: false, timer: null);
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  test('LiveController exposes the session role and gates capabilities', () {
    final producer = LiveController(session: _RoleFake(MobileRole.producer), stored: _stored);
    expect(producer.role, MobileRole.producer);
    expect(producer.can(Capability.goLive), isTrue);
    producer.dispose();

    final assistant = LiveController(session: _RoleFake(MobileRole.assistant), stored: _stored);
    expect(assistant.can(Capability.goLive), isFalse);
    expect(assistant.can(Capability.searchScripture), isTrue);
    assistant.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/controllers/live_controller_rbac_test.dart`
Expected: FAIL — `_RoleFake` isn't a valid `ControllerSession` (missing `grantedRole`) / `role` undefined on `LiveController`.

- [ ] **Step 3: Write minimal implementation**

In `lib/models/session.dart`, add the import and the interface member:

```dart
import 'pair_uri.dart';
import 'protocol.dart';
import 'rbac.dart';
```

```dart
abstract interface class ControllerSession {
  /// The role the host granted this device (parsed; drives UI capability gating).
  MobileRole get grantedRole;
  Future<ServerMessage> command(Map<String, dynamic> cmd);
  Future<OperatorStateView> operatorState();
  Future<void> close();
}
```

In `SelahSession` (keeps the raw `role` string; adds the parsed getter):

```dart
  @override
  MobileRole get grantedRole => MobileRole.parse(role);
```

In `lib/controllers/live_controller.dart`, add the import and getters (near the `blackout` getter, ~line 44):

```dart
import '../models/rbac.dart';
```

```dart
  /// The role the host granted this device. Reads through the CURRENT session,
  /// so a reconnect that re-roles the device is reflected once it lands.
  MobileRole get role => _session.grantedRole;

  /// Whether the granted role may perform [capability] (UX gate; the server is
  /// still authoritative and denies anything this mirror gets wrong).
  bool can(Capability capability) => role.can(capability);
```

Update `test/controllers/live_controller_test.dart` `FakeSession` — add the import and member (default producer so existing tests are unchanged in behaviour):

```dart
import 'package:selahcue_controller/models/rbac.dart';
```

```dart
class FakeSession implements ControllerSession {
  OperatorStateView view;
  ServerMessage Function(Map<String, dynamic> cmd) onCommand;
  MobileRole grantedRole;
  int commandCount = 0;
  int closeCount = 0;

  FakeSession(this.view, this.onCommand, {this.grantedRole = MobileRole.producer});
  // ... existing command/operatorState/close unchanged
}
```

Update `test/views/scripture_tab_test.dart` `_Fake` — add the import and getter:

```dart
import 'package:selahcue_controller/models/rbac.dart';
```

```dart
class _Fake implements ControllerSession {
  final OperatorStateView view;
  final MobileRole grantedRole;
  _Fake(this.view, {this.grantedRole = MobileRole.producer});
  // ... existing command/operatorState/close unchanged
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `flutter test test/controllers/live_controller_rbac_test.dart test/controllers/live_controller_test.dart test/views/scripture_tab_test.dart`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add lib/models/session.dart lib/controllers/live_controller.dart test/controllers/live_controller_test.dart test/controllers/live_controller_rbac_test.dart test/views/scripture_tab_test.dart
git commit -m "feat(mobile): carry granted role through session -> controller.can()"
```

---

### Task 3: `pause_timer` / `resume_timer` command builders + contract fixtures

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/models/protocol.dart` (near `cmdStopTimer` ~line 50)
- Test: `implementation/mobile/selahcue_controller/test/models/protocol_test.dart` (in the `command shapes are internally tagged` test ~line 47)

**Interfaces:**
- Produces: `Map<String, dynamic> cmdPauseTimer()` → `{'cmd':'pause_timer'}`; `Map<String, dynamic> cmdResumeTimer()` → `{'cmd':'resume_timer'}`.

- [ ] **Step 1: Write the failing test** (add these two lines inside the existing `command shapes are internally tagged` test, after the `cmdStopTimer` line)

```dart
    expect(jsonEncode(cmdPauseTimer()), '{"cmd":"pause_timer"}');
    expect(jsonEncode(cmdResumeTimer()), '{"cmd":"resume_timer"}');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/models/protocol_test.dart`
Expected: FAIL — `cmdPauseTimer`/`cmdResumeTimer` not defined.

- [ ] **Step 3: Write minimal implementation** (in `lib/models/protocol.dart`, after `cmdStopTimer`)

```dart
/// Pause / resume a running countdown. Additive unit variants that already
/// exist server-side (`protocol.rs:64,67`, Timer permission) — no VERSION bump.
Map<String, dynamic> cmdPauseTimer() => {'cmd': 'pause_timer'};
Map<String, dynamic> cmdResumeTimer() => {'cmd': 'resume_timer'};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/models/protocol_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/models/protocol.dart test/models/protocol_test.dart
git commit -m "feat(mobile): pause/resume timer command builders (v2 protocol, no VERSION bump)"
```

---

### Task 4: Role badge in the app bar + real role in the About sheet

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/controller_view.dart` (app bar `actions` ~line 127; `_AboutSheet` subtitle ~line 274 and `_row('Role', …)` ~line 305)
- Test: `implementation/mobile/selahcue_controller/test/views/controller_view_role_test.dart` (new)

**Interfaces:**
- Consumes: `LiveController.role` (Task 2), `MobileRole.label` (Task 1), `StatusBadge` (existing).

- [ ] **Step 1: Write the failing test**

```dart
// test/views/controller_view_role_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/controller_view.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
      planName: 'Sunday', items: [], liveIndex: null, stagedIndex: null,
      blackout: false, timer: null);
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  testWidgets('app bar shows the granted role label (Assistant, not hardcoded Producer)',
      (tester) async {
    // ControllerView needs a real SelahSession type param; drive the badge via a
    // LiveController-backed helper widget instead of the full view if construction
    // requires SelahSession. Here we assert the label the badge renders.
    final live = LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(appBar: AppBar(actions: [RoleBadge(live: live)])),
    ));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.text('Assistant'), findsOneWidget);
    expect(find.text('Producer'), findsNothing);
    live.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/views/controller_view_role_test.dart`
Expected: FAIL — `RoleBadge` undefined.

- [ ] **Step 3: Write minimal implementation**

Add a small public `RoleBadge` widget to `lib/views/controller_view.dart` (so it is testable in isolation) and use it in the app bar; replace the two hardcoded `'Producer'` strings in `_AboutSheet` with the live role.

```dart
/// The granted-role chip shown in the app bar (the real backend role — the
/// 7-role design vocabulary is a tracked follow-up). Colour-coded but always
/// carries the text label (WCAG 1.4.1).
class RoleBadge extends StatelessWidget {
  final LiveController live;
  const RoleBadge({super.key, required this.live});

  static Color colorFor(MobileRole r) {
    switch (r) {
      case MobileRole.operator:
        return DesignTokens.accentBrand;
      case MobileRole.producer:
        return DesignTokens.previewInk;
      case MobileRole.assistant:
        return DesignTokens.warnInk;
      case MobileRole.viewer:
      case MobileRole.unknown:
        return DesignTokens.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: live,
        builder: (context, _) => Padding(
          padding: const EdgeInsets.only(right: 6),
          child: Center(
            child: StatusBadge(
                text: live.role.label.toUpperCase(),
                color: colorFor(live.role)),
          ),
        ),
      );
}
```

Add `import '../models/rbac.dart';` to `controller_view.dart`. In the app bar `actions` list, insert `RoleBadge(live: _live)` before the wall-clock padding. In `_AboutSheet`, change the subtitle `Text('Controller · Producer', …)` to build from `live.role.label` (make that `Text` non-`const` and use `'Controller · ${live.role.label}'`), and change `_row('Role', 'Producer')` to `_row('Role', live.role.label)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/controller_view_role_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/views/controller_view.dart test/views/controller_view_role_test.dart
git commit -m "feat(mobile): app-bar role badge + real role in About sheet (drop hardcoded Producer)"
```

---

### Task 5: Live tab — role-gated transport

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/tabs/live_tab.dart` (the transport `Row` ~line 58-95)
- Test: `implementation/mobile/selahcue_controller/test/views/live_tab_test.dart` (new)

**Interfaces:**
- Consumes: `LiveController.can(Capability)` (Task 2).

Gating: `GO LIVE` requires `Capability.goLive`; `◀ Prev` / `Next ▶` require `Capability.navigate`. If a role has neither, no transport row renders (read-only cards only).

- [ ] **Step 1: Write the failing test**

```dart
// test/views/live_tab_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/live_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
      planName: 'Sunday', items: [], liveIndex: null, stagedIndex: null,
      blackout: false, timer: null);
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

Future<LiveController> _pump(WidgetTester tester, MobileRole role) async {
  final live = LiveController(session: _Fake(role), stored: _stored);
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: LiveTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Producer sees GO LIVE + transport', (tester) async {
    final live = await _pump(tester, MobileRole.producer);
    expect(find.text('GO LIVE'), findsOneWidget);
    expect(find.bySemanticsLabel('Next item'), findsOneWidget);
    live.dispose();
  });

  testWidgets('Assistant sees Prev/Next but not GO LIVE', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.assistant);
    expect(find.text('GO LIVE'), findsNothing);
    expect(find.bySemanticsLabel('Next item'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Viewer sees no transport controls', (tester) async {
    final handle = tester.ensureSemantics();
    final live = await _pump(tester, MobileRole.viewer);
    expect(find.text('GO LIVE'), findsNothing);
    expect(find.bySemanticsLabel('Next item'), findsNothing);
    expect(find.bySemanticsLabel('Previous item'), findsNothing);
    handle.dispose();
    live.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/views/live_tab_test.dart`
Expected: FAIL — Assistant/Viewer still show GO LIVE / transport (currently ungated).

- [ ] **Step 3: Write minimal implementation**

Replace the transport `Row` (currently `children:[ _TransportBtn(◀), GO LIVE Expanded, _TransportBtn(▶) ]`, `live_tab.dart:58-95`) and its trailing `SizedBox` with a gated block. Compute the pieces conditionally and only insert a transport row when at least one control renders:

```dart
        // Transport is role-gated: navigate → Prev/Next; goLive → GO LIVE.
        // A role with neither (Viewer) gets read-only cards, no transport row.
        if (live.can(Capability.navigate) || live.can(Capability.goLive)) ...[
          Row(
            children: [
              if (live.can(Capability.navigate)) ...[
                _TransportBtn(
                    glyph: '◀',
                    label: 'Previous item',
                    onTap: () => live.act(cmdPrevious())),
                const SizedBox(width: 8),
              ],
              if (live.can(Capability.goLive))
                Expanded(
                  child: Semantics(
                    button: true,
                    label: 'Go live',
                    child: Material(
                      color: DesignTokens.previewFill,
                      borderRadius: BorderRadius.circular(10),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(10),
                        onTap: () => live.act(cmdGoLive()),
                        child: Container(
                          height: 54,
                          alignment: Alignment.center,
                          child: const Text('GO LIVE',
                              style: TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 0.4,
                                  color: Colors.white)),
                        ),
                      ),
                    ),
                  ),
                )
              else
                const Spacer(),
              if (live.can(Capability.navigate)) ...[
                const SizedBox(width: 8),
                _TransportBtn(
                    glyph: '▶',
                    label: 'Next item',
                    onTap: () => live.act(cmdNext())),
              ],
            ],
          ),
          const SizedBox(height: 10),
        ],
```

Add `import '../../models/rbac.dart';` to `live_tab.dart`. (The `else const Spacer()` keeps the Prev/Next buttons hugging the edges when GO LIVE is hidden, matching a balanced two-button row.)

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/live_tab_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/views/tabs/live_tab.dart test/views/live_tab_test.dart
git commit -m "feat(mobile): role-gate the Live transport (GO LIVE/nav hidden per role)"
```

---

### Task 6: EmergencyStrip — role-gated Blackout / Clear

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/widgets/mobile_widgets.dart` (`EmergencyStrip.build` ~line 145)
- Modify: `implementation/mobile/selahcue_controller/lib/views/controller_view.dart` (the `EmergencyStrip(live: _live)` call ~line 191)
- Test: `implementation/mobile/selahcue_controller/test/views/emergency_strip_test.dart` (new)

**Interfaces:**
- Consumes: `LiveController.can(Capability)`.

Gating: Blackout button requires `Capability.blackout`; Clear button requires `Capability.clearLive`. If a role has neither, `controller_view` omits the strip entirely.

- [ ] **Step 1: Write the failing test**

```dart
// test/views/emergency_strip_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/widgets/mobile_widgets.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
      planName: 'S', items: [], liveIndex: null, stagedIndex: null,
      blackout: false, timer: null);
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  testWidgets('Producer sees Blackout + Clear', (tester) async {
    final handle = tester.ensureSemantics();
    final live = LiveController(session: _Fake(MobileRole.producer), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsOneWidget);
    expect(find.bySemanticsLabel('Clear all'), findsOneWidget);
    handle.dispose();
    live.dispose();
  });

  testWidgets('Assistant sees neither emergency control', (tester) async {
    final handle = tester.ensureSemantics();
    final live = LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: EmergencyStrip(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.bySemanticsLabel('Blackout'), findsNothing);
    expect(find.bySemanticsLabel('Clear all'), findsNothing);
    handle.dispose();
    live.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/views/emergency_strip_test.dart`
Expected: FAIL — Assistant still shows Blackout/Clear.

- [ ] **Step 3: Write minimal implementation**

In `EmergencyStrip.build` (`mobile_widgets.dart`), gate each button by capability and drop the fixed `SizedBox(width:8)` when only one renders. Add `import '../../models/rbac.dart';`:

```dart
  @override
  Widget build(BuildContext context) {
    final blackout = live.blackout;
    final canBlackout = live.can(Capability.blackout);
    final canClear = live.can(Capability.clearLive);
    return Container(
      decoration: const BoxDecoration(
        color: DesignTokens.bgPanel,
        border: Border(
          top: BorderSide(color: DesignTokens.border),
          bottom: BorderSide(color: DesignTokens.border),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      child: Row(
        children: [
          if (canBlackout)
            Expanded(
              child: _EmgButton(
                label: blackout ? '■ UN-BLACKOUT' : '■ BLACKOUT',
                semanticLabel: blackout ? 'Un-blackout' : 'Blackout',
                fill: blackout ? DesignTokens.liveFill : DesignTokens.bgBase,
                border: blackout ? DesignTokens.liveInk : DesignTokens.border,
                textColor: blackout ? Colors.white : DesignTokens.textPrimary,
                onTap: () => live.act(cmdBlackout(!blackout)),
              ),
            ),
          if (canBlackout && canClear) const SizedBox(width: 8),
          if (canClear)
            Expanded(
              child: _EmgButton(
                label: '✕ CLEAR ALL',
                semanticLabel: 'Clear all',
                fill: DesignTokens.bgBase,
                border: DesignTokens.liveInk,
                textColor: DesignTokens.liveInk,
                onTap: () => live.act(cmdClear()),
              ),
            ),
        ],
      ),
    );
  }
```

In `controller_view.dart`, gate the call site so no empty strip renders for a role with neither capability (replace `EmergencyStrip(live: _live),` at ~line 191):

```dart
              if (_live.can(Capability.blackout) || _live.can(Capability.clearLive))
                EmergencyStrip(live: _live),
```

(The `import '../models/rbac.dart';` added in Task 4 already covers `Capability` here.)

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/emergency_strip_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/views/widgets/mobile_widgets.dart lib/views/controller_view.dart test/views/emergency_strip_test.dart
git commit -m "feat(mobile): role-gate the emergency strip (Blackout/Clear hidden per role)"
```

---

### Task 7: Scripture tab — role-gated search/stage

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/tabs/scripture_tab.dart` (`build` ~line 150)
- Test: `implementation/mobile/selahcue_controller/test/views/scripture_tab_role_test.dart` (new)

**Interfaces:**
- Consumes: `LiveController.can(Capability.searchScripture)`.

Gating: the whole search + verse-list surface requires `Capability.searchScripture` (Producer/Assistant). A role without it (Viewer) sees a read-only empty state and no search field.

- [ ] **Step 1: Write the failing test**

```dart
// test/views/scripture_tab_role_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/scripture_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  _Fake(this.grantedRole);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async => const Ack(1);
  @override
  Future<OperatorStateView> operatorState() async => const OperatorStateView(
      planName: 'S', items: [], liveIndex: null, stagedIndex: null,
      blackout: false, timer: null);
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

void main() {
  testWidgets('Assistant sees the search field', (tester) async {
    final live = LiveController(session: _Fake(MobileRole.assistant), stored: _stored);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.byType(TextField), findsOneWidget);
    live.dispose();
  });

  testWidgets('Viewer sees a read-only notice, no search field', (tester) async {
    final live = LiveController(session: _Fake(MobileRole.viewer), stored: _stored);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ScriptureTab(live: live))));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.byType(TextField), findsNothing);
    expect(find.textContaining('not part of your role'), findsOneWidget);
    live.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/views/scripture_tab_role_test.dart`
Expected: FAIL — Viewer still shows the search field.

- [ ] **Step 3: Write minimal implementation**

At the top of `_ScriptureTabState.build` (`scripture_tab.dart:150`), short-circuit for a role without scripture capability. Add `import '../../models/rbac.dart';`:

```dart
  @override
  Widget build(BuildContext context) {
    if (!widget.live.can(Capability.searchScripture)) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
              'Scripture control is not part of your role.',
              textAlign: TextAlign.center,
              style: TextStyle(color: DesignTokens.textMuted)),
        ),
      );
    }
    final view = widget.live.view;
    // ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/scripture_tab_role_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/views/tabs/scripture_tab.dart test/views/scripture_tab_role_test.dart
git commit -m "feat(mobile): role-gate Scripture (read-only notice without searchScripture)"
```

---

### Task 8: Timer tab — role-gated controls + Pause/Resume

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/tabs/timer_tab.dart` (`build` ~line 39; controls ~line 86-137)
- Test: `implementation/mobile/selahcue_controller/test/views/timer_tab_test.dart` (new)

**Interfaces:**
- Consumes: `LiveController.can(Capability.timer)`, `cmdPauseTimer`/`cmdResumeTimer` (Task 3), `TimerSnapshot.running`.

Gating: the readout is always shown (Monitor). All controls (presets, custom start, ±1:00, Pause/Resume, Stop) require `Capability.timer`. Pause/Resume is a single toggle keyed on `TimerSnapshot.running`. **Do not** add Reset or "Send TIME UP" (D2).

- [ ] **Step 1: Write the failing test**

```dart
// test/views/timer_tab_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/controllers/live_controller.dart';
import 'package:selahcue_controller/models/protocol.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/session.dart';
import 'package:selahcue_controller/models/stored_session.dart';
import 'package:selahcue_controller/views/tabs/timer_tab.dart';

class _Fake implements ControllerSession {
  @override
  final MobileRole grantedRole;
  final OperatorStateView view;
  final List<Map<String, dynamic>> sent = [];
  _Fake(this.grantedRole, this.view);
  @override
  Future<ServerMessage> command(Map<String, dynamic> cmd) async {
    sent.add(cmd);
    return const Ack(1);
  }
  @override
  Future<OperatorStateView> operatorState() async => view;
  @override
  Future<void> close() async {}
}

const _stored =
    StoredSession(host: 'h', port: 1, pinHex: 'ab', deviceId: 'd', token: 't');

OperatorStateView _viewWith(TimerSnapshot? t) => OperatorStateView(
    planName: 'S', items: const [], liveIndex: null, stagedIndex: null,
    blackout: false, timer: t);

Future<LiveController> _pump(WidgetTester tester, _Fake fake) async {
  final live = LiveController(session: fake, stored: _stored);
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: TimerTab(live: live))));
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
  return live;
}

void main() {
  testWidgets('Producer with a running timer sees Pause; taps it', (tester) async {
    const running = TimerSnapshot(
        remainingSecs: 120, elapsedSecs: 60, timeUp: false, warn: false, running: true);
    final fake = _Fake(MobileRole.producer, _viewWith(running));
    final live = await _pump(tester, fake);
    expect(find.text('Pause'), findsOneWidget);
    await tester.tap(find.text('Pause'));
    await tester.pump();
    expect(fake.sent.any((c) => c['cmd'] == 'pause_timer'), isTrue);
    live.dispose();
  });

  testWidgets('Producer with a paused timer sees Resume', (tester) async {
    const paused = TimerSnapshot(
        remainingSecs: 120, elapsedSecs: 60, timeUp: false, warn: false, running: false);
    final live = await _pump(tester, _Fake(MobileRole.producer, _viewWith(paused)));
    expect(find.text('Resume'), findsOneWidget);
    live.dispose();
  });

  testWidgets('Viewer sees the readout but no timer controls', (tester) async {
    final live = await _pump(tester, _Fake(MobileRole.viewer, _viewWith(null)));
    expect(find.text('Start'), findsNothing);
    expect(find.text('Stop'), findsNothing);
    expect(find.text('SERVICE TIMER'), findsOneWidget); // readout kept
    live.dispose();
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/views/timer_tab_test.dart`
Expected: FAIL — no Pause/Resume yet; Viewer still shows controls.

- [ ] **Step 3: Write minimal implementation**

Add `import '../../models/rbac.dart';` to `timer_tab.dart`. In `build`, keep the readout block unchanged; wrap the controls (from the presets `Row` through the ±1:00/Stop `Row`) in `if (widget.live.can(Capability.timer)) ...[ … ]`, and replace the final ±1:00/Stop `Row` with one that includes Pause/Resume. Concretely, the control section becomes:

```dart
        const SizedBox(height: 16),
        if (widget.live.can(Capability.timer)) ...[
          Row(
            children: [
              Expanded(child: _TBtn('⏱ 5:00', () => widget.live.act(cmdStartTimer(300)))),
              const SizedBox(width: 8),
              Expanded(child: _TBtn('⏱ 10:00', () => widget.live.act(cmdStartTimer(600)))),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _minutes,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: DesignTokens.textPrimary),
                  decoration: const InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: DesignTokens.bgBase,
                    hintText: 'Minutes…',
                    hintStyle: TextStyle(color: DesignTokens.textMuted),
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _startCustom(),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton(onPressed: _startCustom, child: const Text('Start')),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _TBtn('−1:00', hasTimer ? () => widget.live.act(cmdAdjustTimer(-60)) : null)),
              const SizedBox(width: 8),
              Expanded(child: _TBtn('+1:00', hasTimer ? () => widget.live.act(cmdAdjustTimer(60)) : null)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _TBtn(
                  (t?.running ?? false) ? 'Pause' : 'Resume',
                  hasTimer
                      ? () => widget.live.act(
                          (t!.running) ? cmdPauseTimer() : cmdResumeTimer())
                      : null,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(child: _TBtn('Stop', hasTimer ? () => widget.live.act(cmdStopTimer()) : null)),
            ],
          ),
        ],
```

Rename the existing local `final running = t != null;` to `final hasTimer = t != null;` (it means "a timer exists", not "actively counting" — the latter is `t.running`). Update the two prior uses accordingly. Leave the readout logic (`if (t == null) … else if (t.timeUp) … else …`) untouched — the "TIME UP" *readout* is the host's derived state, not a control, and stays.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/timer_tab_test.dart`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/views/tabs/timer_tab.dart test/views/timer_tab_test.dart
git commit -m "feat(mobile): role-gate Timer controls + Pause/Resume toggle"
```

---

### Task 9: Connect (pairing) — v2 visual alignment

**Files:**
- Modify: `implementation/mobile/selahcue_controller/lib/views/pairing_view.dart` (presentation only)
- Test: `implementation/mobile/selahcue_controller/test/views/pairing_view_test.dart` (new smoke test)

**Interfaces:** none new. **Security behaviour is unchanged** — the fingerprint-confirm gate, QR path, and parked-waiting state stay exactly as they are; this task only aligns spacing/typography/section headers/status chips to the v2 Connect layout (discovered-host cards with a status chip, a "Discovered on your network" section header, the QR entry, and the manual-paste affordance).

- [ ] **Step 1: Write the failing test**

```dart
// test/views/pairing_view_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/views/pairing_view.dart';

void main() {
  testWidgets('Connect screen shows the discovery header and a scan affordance',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: PairingView()));
    await tester.pump(const Duration(milliseconds: 60));
    expect(find.textContaining('network'), findsWidgets); // "Discovered on your network"
    expect(find.textContaining('Scan'), findsWidgets);    // QR pairing affordance
  });
}
```

Note: `PairingView` starts mDNS discovery on mount; the smoke test only pumps once and asserts static chrome. If discovery requires platform plugins that throw under the test binding, wrap the discovery start so it is a no-op when `discovery` finds nothing (it already tolerates an empty network) — do not stub platform channels here.

- [ ] **Step 2: Run test to verify it fails (or reveals the current copy)**

Run: `flutter test test/views/pairing_view_test.dart`
Expected: FAIL if the current copy differs from the v2 headers; use the failure to confirm the exact strings to align.

- [ ] **Step 3: Write minimal implementation**

Apply presentation-only edits to `pairing_view.dart` to match the v2 Connect layout: a "Discovered on your network" section header above the host list, each discovered host rendered as a card with a trailing status chip (`PAIRED` / `Connect`), and the QR/manual entry grouped below with the "Scan the QR on the desktop to pair a new booth" caption. **Do not** change `_pairDiscovered`, the fingerprint confirm dialog, `_waiting`, or any credential/keychain logic.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/views/pairing_view_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/views/pairing_view.dart test/views/pairing_view_test.dart
git commit -m "feat(mobile): align Connect (pairing) screen to the v2 layout (no behaviour change)"
```

---

### Task 10: Full verification + follow-up tickets + handoff

**Files:** none (verification + ClickUp).

- [ ] **Step 1: Run the full mobile gate**

Run: `make mobile-test` (from repo root) — `flutter analyze` + `flutter test`.
Expected: analyze clean, all tests PASS.

- [ ] **Step 2: Confirm no backend / wire change leaked in**

Run: `git diff --name-only origin/main...HEAD` (or `git diff --stat` for the branch)
Expected: only files under `implementation/mobile/selahcue_controller/` and `docs/`. No `selahcue-lan`, no `protocol.rs`, `wireVersion`/`VERSION` unchanged (still `2`).

- [ ] **Step 3: Screenshot the four screens per role** (representative-device check)

Run the app against a desktop host (`make output` for the host, then run the controller) and capture Live/Scripture/Timer under Producer vs Assistant vs Viewer grants; save under the goal's evidence folder. (If no device is available, note it and rely on the widget tests as the role-gating evidence.)

- [ ] **Step 4: Create the two follow-up ClickUp tickets** (owner decision D2), under epic `86ajp086b`:
  - **Backend:** "7-role RBAC expansion + TIME UP + ResetTimer commands (matrix PERSONAS §2)". Owner /backend-engineer + /security-reviewer. Includes: expand `rbac.rs` to the 7 roles × 14 capabilities, add a TIME UP command + `ResetTimer`, wire role vocabulary + `VERSION` bump + cross-language fixtures, live role-change push (optional).
  - **Mobile:** "Consume 7 roles + wire TIME UP/Reset + 7-role badges (after backend lands)". Depends on the backend ticket.

- [ ] **Step 5: Post the handoff evidence comment** on the active story (files changed, tests run + results, screenshots, decisions D1/D2/D3, the two follow-ups linked) and move it to the next valid status (QA). Do not mark it Done — QA/independent review required.

---

## Self-Review

**Spec coverage:**
- §2 role space → Task 1 (mirror) + Task 2 (surface). ✅
- §3 D1 hide-not-disable → Tasks 5–8 hide controls. ✅
- §3 D2 omit+track → Task 8 omits TIME UP/Reset; Task 10 creates the two tickets. ✅
- §3 D3 real role badge → Task 4. ✅
- §5.1 Connect → Task 9. §5.2 Live → Task 5 (+ Task 6 emergency strip). §5.3 Scriptures → Task 7. §5.4 Timer → Task 8. ✅
- §6 pause/resume, no VERSION bump → Task 3. ✅
- §8 tests: rbac_test, protocol fixtures, per-tab widget tests → Tasks 1,3,5,6,7,8. ✅
- §11 acceptance criteria 1–6 → all mapped to tasks; #6 gate → Task 10. ✅

**Placeholder scan:** No TBD/TODO; every code step shows real code. Task 9 is presentation-only and says so explicitly (the one lower-fidelity-to-TDD task, bounded by "no behaviour change" + a smoke test).

**Type consistency:** `Capability`/`MobileRole` names, `LiveController.can(Capability)`, `grantedRole`, `cmdPauseTimer`/`cmdResumeTimer`, `RoleBadge`, `hasTimer`/`t.running` are used consistently across tasks. The `ControllerSession.grantedRole` member is added in Task 2 and every fake (existing + new) implements it.
