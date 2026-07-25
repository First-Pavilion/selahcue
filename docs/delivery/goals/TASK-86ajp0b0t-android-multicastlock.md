# Goal Contract — TASK-86ajp0b0t-android-multicastlock

## Identity

- Goal ID: TASK-86ajp0b0t-android-multicastlock
- Parent goal ID: STAGE7-foundation
- Title: Android holds a WifiManager.MulticastLock while mDNS discovery runs, so pure-Dart multicast_dns actually receives multicast on Android
- Role: mobile-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajp0b0t
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Complete the mDNS-discovery story's recorded Android remainder: acquire a `WifiManager.MulticastLock` for the duration of a discovery browse (Android drops multicast otherwise), so Nearby-hosts discovery works on Android.

## Baseline

Verified from the repository as of 2026-07-25:
- The Flutter controller discovers hosts with pure-Dart `multicast_dns` (`DiscoveryController.refresh()` → `MDnsClient`). On Android, the OS filters multicast unless an app holds a `WifiManager.MulticastLock`.
- The `CHANGE_WIFI_MULTICAST_STATE` permission is already in `AndroidManifest.xml` (batch 7aj); the **runtime lock acquisition is missing**.
- `MainActivity.kt` is a bare `FlutterActivity` (no platform channel).
- The flutter CI job runs `flutter analyze` + `flutter test` (no Android build yet).

## Inputs and evidence sources

- ClickUp story 86ajp0b0t (acceptance + the 7aj-recorded remainder).
- `lib/controllers/discovery_controller.dart`, `android/app/src/main/kotlin/.../MainActivity.kt`, `android/app/src/main/AndroidManifest.xml`, `.github/workflows/ci.yml`.

## Scope

### In scope

- A Dart `MulticastLock` abstraction + a `PlatformMulticastLock` (MethodChannel `selahcue/multicast`, Android-only, best-effort).
- `DiscoveryController.refresh()` acquires the lock before the browse and ALWAYS releases it (finally); the mDNS browse extracted behind an injectable seam for hermetic testing.
- A Kotlin `MethodChannel` handler in `MainActivity` acquiring/releasing a `WifiManager.MulticastLock` (reference-safe; released on destroy).
- A unit test proving acquire-before-browse and always-release.

### Non-goals

- iOS / other platforms (no-op — only Android filters multicast).
- The runtime "discovery actually finds a host on a real Android device" behaviour — that is on-device QA (owner-run), not automatable in CI.

### Constraints

- Best-effort: a lock failure must not break discovery (the QR/manual paths are unaffected) or throw out of `refresh()`.
- No leaked lock: released in `finally` and on Activity destroy.

### Assumptions and unknowns

- ASSUMED: the GitHub ubuntu flutter runner can `flutter build apk --debug` (Android SDK preinstalled) to compile the Kotlin. VALIDATION OWNER: the CI run. If Android setup is problematic → the Kotlin is structurally reviewed + on-device QA documented (the acceptance's honest fallback).

## Dependencies and approvals

- None blocking. On-device QA is the owner's.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A MulticastLock abstraction + Android-only best-effort PlatformMulticastLock exists; refresh() acquires before the browse and always releases (finally); best-effort (never throws out of refresh in production) | `flutter analyze` | no issues | multicast_lock.dart; discovery_controller.dart | PASS |
| C-002 | yes | A unit test (fake lock + injected browse) proves acquire→browse→release ordering and release-even-on-browse-error | `flutter test` | the discovery lock tests pass | discovery_controller_test.dart (3 tests; 39 total) | PASS |
| C-003 | yes | The Android host registers the `selahcue/multicast` channel and acquires/releases a WifiManager.MulticastLock (reference-safe; released on destroy) | `flutter build apk --debug` in CI compiling the Kotlin, OR reviewed + on-device QA documented | APK builds (Kotlin compiles), or documented limitation + QA steps | MainActivity.kt; CI/QA doc | PENDING |
| C-004 | yes | flutter analyze + test green in CI | CI run of the flutter job | green | CI run URL | PENDING |
| C-005 | yes | Independent review; confirmed findings fixed | Workflow adversarial review | confirmed findings fixed | CODE-REVIEW-batch7ao.md | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `flutter analyze` + `flutter test` locally.
- Broader regression verification: full flutter suite stays green (the change is additive + injectable).
- Independent verifier: Workflow adversarial review (lock lifecycle, no-leak, best-effort, Kotlin correctness).
- Required environment: local Flutter + GitHub CI (flutter job; Android build where the runner permits) + an Android device for owner QA.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: a MulticastLock abstraction wired into refresh() (acquire→browse→release, browse behind an injectable seam) is testable with a fake lock and analyzes clean.
- Change or investigation: add multicast_lock.dart; refactor discovery_controller.dart; add discovery_controller_test.dart; verify locally.
- Verifier executed: `flutter analyze` (clean) + `flutter test` (39, +3 discovery lock tests).
- Result: **C-001 PASS**, **C-002 PASS** — refresh() holds the lock across the browse and always releases (even on browse error); a concurrent refresh does not double-acquire.
- New evidence: injectable browse seam makes the lock lifecycle hermetically testable.
- Decision: iterate (C-003 Kotlin host + C-004 CI)

### Iteration 2

- Target criterion: C-003, C-004
- Hypothesis: a Kotlin `selahcue/multicast` MethodChannel acquiring/releasing a non-ref-counted WifiManager.MulticastLock (released on destroy) compiles via `flutter build apk --debug` in CI.
- Change or investigation: wrote MainActivity.kt; added the APK build to the flutter CI job (JDK 17). Pushing.
- Verifier executed: (pending CI run)
- Result: (pending)
- New evidence: (pending)
- Decision: iterate

## Risks and rollback

- Risks: the Android APK build may need SDK/license setup in CI. Rollback: the feature is additive + Android-only + best-effort; drop the CI apk step and document + on-device QA if the runner can't build.
- Rollback or recovery: git-versioned.

## Pause and escalation conditions

- If the runtime multicast behaviour cannot be confirmed without a device (it can't), that portion is owner on-device QA, explicitly out of automatable scope — document, do not block.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajp0b0t-android-multicastlock.md`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: IN_PROGRESS → GATE_REVIEW
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
