# Goal Contract — TASK-mobile-nav-config

## Identity

- Goal ID: TASK-mobile-nav-config
- Parent goal ID: NONE
- Title: v2 mobile Navigation & Config — role-scoped bottom tabs + Config/About session sheet
- Role: mobile-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxv48u
- Design ref: Figma 363-124 (Mobile — Navigation & Config)
- Spec: docs/superpowers/specs/2026-08-07-mobile-nav-config-design.md
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The bottom tab bar shows only the tabs a granted role may use (◐ = view-only, hidden otherwise),
and the top-bar ⓘ opens a Config/About session sheet (CONNECTION + PREFERENCES + ABOUT), on the
current 4-role backend.

## Baseline

- **Verified**: bottom bar is a fixed 4-tab NavigationBar (Live/Plan/Scripture/Timer) with a fixed
  index (`controller_view.dart`). Tab CONTENTS are role-gated (v2 RBAC story 86ajxuf5j) but the tab
  SET is not. `plan_tab.dart` stages on tap (`SelectItem`/Navigate) + go-lives on double-tap
  (`selectAndGoLive`/GoLive) with NO role gating. The ⓘ opens `_AboutSheet` = CONNECTION + Disconnect
  only (no PREFERENCES/ABOUT). `main.dart` already suppresses page transitions under
  `MediaQuery.disableAnimations`.
- **Verified**: pubspec has no wakelock/package_info dep; `LiveController.can(Capability)` + `role`
  exist (86ajxuf5j).

## Inputs and evidence sources

- Figma 363-124; the RBAC mirror `lib/models/rbac.dart`.
- `implementation/mobile/selahcue_controller/` current app + tests.
- Spec `docs/superpowers/specs/2026-08-07-mobile-nav-config-design.md`.

## Scope

### In scope

- `lib/models/tab_scope.dart` (`visibleTabsFor`) + `lib/models/settings.dart` (`SettingsController` +
  `SettingsScope`, injected wakelock).
- Role-scoped NavigationBar + IndexedStack (index clamp, ◐ marker) in `controller_view.dart`.
- `plan_tab` role gating; Config/About sheet with CONNECTION + PREFERENCES + ABOUT; haptics on
  GO LIVE + emergency; reduce-motion OR into `main.dart`.
- Deps `wakelock_plus`, `package_info_plus`.

### Non-goals

- The "More" tab + Production/Admin tools → follow-up 86ajxufbg.
- Backend/wire change; 7-role model; haptics on every command.

### Constraints

- 4-role model (Producer/Assistant/Viewer + unknown fail-closed). Plugin channels isolated behind
  injection so tests never hit a real channel. Bounded memory. `make mobile-test` green.

### Assumptions and unknowns

- **ASSUMED**: `wakelock_plus`/`package_info_plus` resolve on Flutter 3.44/Dart ^3.12 via
  `flutter pub add`. Validate at Task C1.

## Dependencies and approvals

- Scope decisions (omit More; full Config + new deps) approved by owner this session.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `visibleTabsFor` matches the §2 table for all roles | `flutter test test/models/tab_scope_test.dart` | PASS | test output | PENDING |
| C-002 | yes | Bottom bar renders only role tabs (Viewer no Scripture; Producer all 4); index clamps | `flutter test test/views/controller_view_nav_test.dart` | PASS | test output | PENDING |
| C-003 | yes | `plan_tab` read-only for Viewer; stage/go-live gated | `flutter test test/views/plan_tab_test.dart` | PASS | test output | PENDING |
| C-004 | yes | Settings persist + wakelock injected called on keep-awake toggle | `flutter test test/models/settings_test.dart` | PASS | test output | PENDING |
| C-005 | yes | Config sheet renders CONNECTION+PREFERENCES+ABOUT; keep-awake drives injected wakelock; version via package_info | `flutter test test/views/config_sheet_test.dart` | PASS | test output | PENDING |
| C-006 | yes | Full gate green; "More" absent; no backend/wire change | `make mobile-test` + `git diff --name-only` scoped to mobile+docs | analyze clean, tests PASS, no `selahcue-lan`; `wireVersion = 2` | CI output | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the per-task `flutter test <file>` above.
- Broader regression: `make mobile-test` (flutter analyze + full test suite).
- Independent verifier: /qa-engineer (device: role-scoped tabs per grant; keep-awake during a
  service; version/licenses) + /code-reviewer on the diff.
- Required environment: Flutter SDK ^3.12; a desktop host for the device check.

## Iteration ledger

### Iteration 1

- Target criterion:
- Hypothesis:
- Change or investigation:
- Verifier executed:
- Result:
- New evidence:
- Decision: iterate | handoff | blocked | gate-review | complete

## Risks and rollback

- Risks: plugin channels in tests (mitigated by injection / setMockInitialValues); tab-index churn
  (clamp + test).
- Rollback: additive mobile-only changes; revert the mobile commits. Deps are additive to pubspec.

## Pause and escalation conditions

- If `wakelock_plus`/`package_info_plus` fail to resolve on this toolchain → pause and confirm dep
  versions with the owner. Owner: executor → owner.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-mobile-nav-config.md
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
