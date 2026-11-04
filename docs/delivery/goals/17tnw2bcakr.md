# Goal Contract — TASK-17tnw2bcakr

## Identity

- Goal ID: TASK-17tnw2bcakr
- Parent goal ID: NONE
- Title: Reconnect malformed-reply tests await fresh state deterministically
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bcakr
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Remove the reconnect test scheduling race while proving controls and the outage notice remain gated until fresh state arrives.

## Baseline

Main 13bb3c255dd83ef9917a344964ce55725ec91db2. PR356 job126354512243 failed the premature null-banner assertion: 514 passed, one failed. Production intentionally keeps the notice and command gate until snapshot completion. Root verified ticket In Progress and start comment before edits.

## Inputs and evidence sources

- /private/tmp/wave2-356-flutter-ci.log
- lib/controllers/live_controller.dart and existing sync/retired-read tests
- ClickUp task and root verified start receipt

## Scope

### In scope

- Controlled replacement snapshot in malformed-reconnect test; focused and full Flutter validation; evidence.

### Non-goals

- Production changes, SDK/dependency upgrades, installer/deployment operations.
- Device, permission, navigation, release, accessibility and battery changes: not applicable to test-only correction.

### Constraints

- Preserve both malformed flavours, retry/revocation/disposal checks and production byte-for-byte.
- No fixed sleeps, increased timeouts or removed assertions to mask failure.
- Never edit primary worktree's user-modified lockfile.

### Assumptions and unknowns

- Actual hosted stable runtime may differ from installed Flutter3.47.4/Dart3.13.3; root verifies hosted CI.

## Dependencies and approvals

- Root owns four independent reviews, hosted CI, merge and QA transition; user authorized delivery.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Controlled pending snapshot reproduces old premature expectation failure | Focused RED run | Expected null receives outage notice | evidence/17tnw2bcakr | PASS |
| C-002 | yes | Both malformed flavours keep notice and commands blocked until fresh state, then recover | Focused repeated GREEN runs | All focused tests pass | evidence/17tnw2bcakr | PASS |
| C-003 | yes | Production and lockfiles unchanged; format, analyzer and full tests pass | Git diff and Flutter checks | Clean format/analyze; all tests pass | evidence/17tnw2bcakr | PASS |
| C-004 | yes | Cody, Shadow, Quinn, Vera and actual hosted CI pass exact PR revision | Independent reviews and hosted CI | Four passes and CI success | Root handoff | PENDING |

## Verification plan

- Focused verification: deterministic RED; malformed suite repeated; sync/retired-read/stalled tests.
- Broader regression verification: format, flutter analyze, flutter test.
- Independent verifier: Cody, Shadow, Quinn, Vera and hosted Linux CI via root.
- Required environment: configured current Flutter toolchain; committed lockfile enforced.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003
- Hypothesis: reconnect completion precedes snapshot completion; existing assertion races the latter.
- Change or investigation: inspect production and sync fixture; gate replacement snapshot at session boundary.
- Verifier executed: deterministic RED; malformed7/7; combined31/31; three repeats2/2 each; full515/515; analyzer; formatter; diff check
- Result: C-001 through C-003 PASS; hosted and independent gates pending
- New evidence: production explicitly documents preserved outage notice until snapshot.
- Decision: gate-review

## Risks and rollback

- Risks: fixture cleanup must release pending snapshot even on test failure.
- Rollback or recovery: revert test/docs commit; no product runtime changes.

## Pause and escalation conditions

- New production defect or failed independent gate: report to root; no merge.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bcakr.md
- Validator result: structural PASS
- Independent verification result: pending root review
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-004 pending independent reviewers and hosted CI
- ClickUp final evidence comment: root owns posting
