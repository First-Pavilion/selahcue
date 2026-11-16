# Goal Contract — 17tnw2bbjvc-native-splash

## Identity

- Goal ID: 17tnw2bbjvc-native-splash
- Parent goal ID: NONE
- Title: Align native splash backgrounds with the approved brand theme
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbjvc
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 2
- Independent verification required: yes

## Objective

Committed native Android/iOS launch backgrounds use configured #0B0D12 while preserving approved logo/layout.

## Baseline

Current main c6fa1b4b has #0E1116 background bitmaps and white iOS storyboard root. No visible device flash has been observed.

## Inputs and evidence sources

- Current browser ticket readback saved by Diego and pubspec locked splash config.

## Scope

- In scope: native splash resources and stale generator comment; focused verification evidence.
- Non-goals: launcher icons, IDs, version, signing, permissions, dependencies, store submission.
- Constraints: existing logo/layout, no SDK downloads, no whole-app builds or shared caches.
- Unknown: physical launch behavior and store readiness remain M01/86ajxz3nj.

## Dependencies and approvals

- User-approved atomic ticket via root; root owns browser statuses and reviewer dispatch.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Native backgrounds match configured theme | decoded PNG/XML inspection and native resource checks | #0B0D12 in launch variants | docs/release/mobile/17tnw2bbjvc-splash-evidence.md | PASS |
| C-002 | yes | Logo/layout and unrelated config remain unchanged | decoded pixel comparison and git diff inspection | only scoped color resources/comment change | docs/release/mobile/17tnw2bbjvc-splash-evidence.md | PASS |
| C-003 | yes | Independent reviews pass | root coordinated Cody/Shadow/Quinn/Vera | no blocking findings at final head | PR review | PENDING |

## Verification plan

- Focused: PNG pixel/alpha checks, XML parsing, Android aapt2 resource compile, iOS ibtool if installed SDK permits.
- Broader: no Dart/runtime changes; no new mirroring tests for reversible resource color change per ticket; full mobile suite/build intentionally not repeated.
- Independent: all four reviewers through root.
- Environment: installed local tools only. Device evidence explicitly out of source correction scope.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: rerunning existing locked generator and retaining only color changes aligns native resources without altering approved artwork/layout.
- Change or investigation: ran locked generator; aligned iOS root fallback color; inspected complete scoped diff.
- Verifier executed: aapt2 resource compile, ibtool storyboard compile, decoded PNG RGB/alpha, XML/layout comparison, 57 unchanged PNG comparisons and git diff --check.
- Result: focused resource checks pass; no device or whole-app claims.
- New evidence: docs/release/mobile/17tnw2bbjvc-splash-evidence.md
- Decision: gate-review

## Risks and rollback

- Risks: source/static preview does not establish launch timing or physical device appearance.
- Rollback: revert this ticket commit.

## Pause and escalation conditions

- Unexpected identity/permission/dependency changes or missing tools: stop and report.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbjvc-native-splash.md
- Validator result: structural validator passes; completion intentionally withheld for independent reviews.
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining criteria: C-003 four independent reviews pending; actual hardware/store release gates remain outside this source correction.
- ClickUp final evidence comment: root-owned
