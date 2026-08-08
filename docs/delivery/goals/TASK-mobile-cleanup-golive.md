# Goal Contract — TASK-mobile-cleanup-golive

## Identity

- Goal ID: TASK-mobile-cleanup-golive
- Parent goal ID: NONE
- Title: Mobile design cleanup + go-live prep — responsive/tablet, logo, splash, privacy/terms, release-prep
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxxu0r
- Design ref: docs/design/MOBILE-DESIGN-CLEANUP-handoff.md (/ui-ux-designer handoff)
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Implement the design cleanup: the controller renders correctly on tablets (constrained/centred,
adaptive), uses the SelahCue logo (splash/headers/app icons), a redesigned splash, and ships
well-defined privacy/terms drafts + release-prep — store-ready except the publish itself.

## Baseline

- **Verified**: ~zero responsive code (1 MediaQuery use; no LayoutBuilder/max-width) → stretches on
  tablets. Splash = in-Dart `Launcher` with an "S" box. App icons = stock Flutter. No privacy/terms
  docs (only an in-app privacy dialog). Logo now at `assets/selahcue-logo.png` (committed f204fd0).

## Inputs and evidence sources

- Design handoff `docs/design/MOBILE-DESIGN-CLEANUP-handoff.md`; `lib/models/design_tokens.dart`.
- Current app under `implementation/mobile/selahcue_controller/`.

## Scope

### In scope

- `ResponsiveBody` (560 dp cap + adaptive padding) applied to screen bodies + emergency strip;
  Live tab Preview/Live side-by-side ≥600 dp.
- Splash redesign (Dart `Launcher` with logo + wordmark) + `flutter_native_splash` config.
- Logo in pairing header + About header (replace the "S" box); `flutter_launcher_icons` config +
  generated icons.
- Privacy policy + terms drafts (`docs/legal/`) + in-app Privacy/Terms screens (legal-review flagged).
- Release-prep: version, iOS `PrivacyInfo.xcprivacy`, store-listing metadata draft, release checklist.

### Non-goals

- The actual store publish (signing certs + Apple/Google accounts — owned elsewhere → follow-up).
- Legal sign-off on the policy/terms (drafts only, flagged). Net-new Figma frames (optional).

### Constraints

- No backend/wire change. `make mobile-test` green. Bounded memory. AA + ≥48 dp targets. Commit with
  explicit pathspecs (WIP-heavy repo).

### Assumptions and unknowns

- **ASSUMED**: `flutter_launcher_icons` / `flutter_native_splash` resolve on this toolchain — validate
  when added.

## Dependencies and approvals

- Design approved (this session). Owner chose drafts + release-prep; publish is a follow-up.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `ResponsiveBody` caps content at 560 dp on a wide surface; applied to screens | `flutter test test/views/responsive_test.dart` | PASS | test output | PASS |
| C-002 | yes | Live tab shows Preview+Live side-by-side ≥600 dp; stacked <600 | `flutter test test/views/live_tab_test.dart` | PASS | test output | PASS |
| C-003 | yes | Splash renders the logo + "SelahCue"/"CONTROLLER" (not the "S" box) | `flutter test test/views/splash_test.dart` | PASS | test output | PASS |
| C-004 | yes | Logo used in pairing + About headers (image present, "S" box gone) | `flutter test test/views/logo_usage_test.dart` | PASS | test output | PASS |
| C-005 | yes | App icons generated from the logo (flutter_launcher_icons config + non-stock icons) | review: config present + `ic_launcher` regenerated | config in pubspec; icons regenerated | files | PASS |
| C-006 | yes | Privacy + terms drafts (docs/legal) + in-app screens reachable from Config | `flutter test test/views/config_sheet_test.dart` + files exist | PASS + docs present | test + docs | PASS |
| C-007 | yes | Release-prep: iOS PrivacyInfo + store metadata draft + release checklist present | review | files exist | docs/release | PASS |
| C-008 | yes | Full gate green | `make mobile-test`; `wireVersion = 2` | analyze clean, tests PASS | CI output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-criterion `flutter test <file>` + file presence.
- Broader: `make mobile-test`; a tablet-simulator render check (representative-device).
- Independent verifier: /qa-engineer (tablet simulator: portrait/landscape, splash, icons) +
  /code-reviewer; legal review of privacy/terms.
- Required environment: Flutter ^3.12; a tablet simulator; icon/splash generators.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008 (design cleanup + go-live prep).
- Hypothesis: a 560dp ResponsiveBody + LayoutBuilder side-by-side + the brand logo + generators +
  grounded privacy/terms drafts make the app tablet-correct, branded, and store-ready (minus publish).
- Change or investigation: /ui-ux-designer handoff spec; ResponsiveBody applied app-wide; Live
  side-by-side; SplashView + logo in About/pairing; app icons + native splash generated; privacy +
  terms drafts + in-app screens; iOS PrivacyInfo + store-listing + release checklist; publish
  follow-up filed.
- Verifier executed: per-criterion flutter tests; `make mobile-test`; `wireVersion` grep; explicit
  per-commit scope checks (no owner WIP swept).
- Result: 95/95 tests PASS; analyze clean; wireVersion=2; all story commits mobile+docs only.
- New evidence: commits f204fd0…b340b07; publish follow-up 86ajxz3nj.
- Decision: gate-review — all automated criteria PASS; independent QA (real tablet + phone) +
  legal sign-off on privacy/terms + the store publish (86ajxz3nj) are owned elsewhere.

## Risks and rollback

- Risks: icon/splash generators write many binary files → commit deliberately; generator dep
  resolution. Concurrent WIP → explicit-pathspec commits, re-read before editing.
- Rollback: additive mobile-only; revert commits.

## Pause and escalation conditions

- Actual store publish / signing / legal sign-off → owned elsewhere; file follow-up, do not attempt.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-mobile-cleanup-golive.md
- Validator result: PASS (8/8) at authoring; re-run after status edits.
- Independent verification result: PENDING — /qa-engineer (tablet + phone device check) +
  /code-reviewer; legal review of docs/legal/*; store publish 86ajxz3nj.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: none FAIL; all 8 PASS. Owned-elsewhere: legal sign-off +
  store publish (tracked 86ajxz3nj).
- ClickUp final evidence comment: posted on 86ajxxu0r; story moved to QA.
