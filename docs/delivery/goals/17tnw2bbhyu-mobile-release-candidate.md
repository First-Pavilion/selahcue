# Goal Contract — 17tnw2bbhyu-mobile-release-candidate

## Identity

- Goal ID: 17tnw2bbhyu-mobile-release-candidate
- Parent goal ID: NONE
- Title: Include the Controller privacy manifest in the iOS application resource graph
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhyu
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

First bounded increment of the broader mobile release-candidate ticket: Runner includes its existing privacy manifest in Copy Bundle Resources. This increment does not establish store readiness.

## Baseline

Verified on main 93bf472: Runner/PrivacyInfo.xcprivacy exists but has no PBXFileReference, PBXBuildFile or Runner resources membership. Android release still uses debug signing and launcher label selahcue_controller. Those separate gaps remain pending.

## Inputs and evidence sources

- Owner-authorized ticket 17tnw2bbhyu supplied by root; completed cleanup 86ajxxu0r stays complete.
- ios/Runner.xcodeproj/project.pbxproj and ios/Runner/PrivacyInfo.xcprivacy
- docs/release/mobile/RELEASE-CHECKLIST.md; publishing ticket 86ajxz3nj

## Scope

### In scope

- Link the existing manifest into Runner resources; add a semantic native-project verifier; update release evidence.

### Non-goals

- No changes to privacy declarations, SDK policy, signing assets, app identifiers, store accounts or publication.
- No claim of compiled archive, signed build or physical-device verification.

### Constraints

- Isolated branch codex/17tnw2bbhyu-mobile-release-candidate; no merge or deployment.
- Root owns ClickUp browser updates; other agents own frontend/backend/CI.

### Assumptions and unknowns

- Unknown final plugin API privacy report and signed archive behavior; release owner verifies on final build.

## Dependencies and approvals

- User approved starting implementation; root posts ClickUp status/evidence.
- Independent reviews and real release/device evidence remain pending for the wider ticket.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Runner resource graph includes existing manifest | python3 implementation/mobile/selahcue_controller/scripts/check_ios_privacy_manifest.py | exits 0 with actual Runner file path | iteration ledger | PASS |
| C-002 | yes | Removing resource membership is rejected | temporary project mutation through checker | exits nonzero even if file reference remains | iteration ledger | PASS |
| C-003 | yes | Native project and manifest parse successfully | plutil -lint on both files | exits 0 | iteration ledger | PASS |
| C-004 | yes | Independent review verifies increment | Cody/Shadow/Quinn/Vera review current revision | no unresolved blocking findings | root handoff | PENDING |

## Verification plan

- Focused verification: semantic graph checker before/after fix and resource-membership mutation.
- Broader regression verification: native plist syntax and git diff --check; archive/device checks remain outside this increment and unverified.
- Independent verifier: root coordinates specialists after first increment.
- Required environment: macOS plutil and Python 3; no Flutter build or credentials needed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: adding explicit file/build references and Runner resource membership makes existing manifest part of native app resources.
- Change or investigation: baseline read establishes missing graph membership.
- Verifier executed: semantic graph checker before/after fix; temporary project with only Runner resource membership removed; plutil -lint on project and manifest; git diff --check.
- Result: baseline checker failed with missing Copy Bundle Resources membership; fixed graph passed; removing only resource membership failed again despite retained file/build references; plutil and diff check exited 0.
- New evidence: existing file alone does not enroll it in Runner resources.
- Decision: gate-review

## Risks and rollback

- Risks: graph inclusion does not prove a compiled archive or correctness of required-reason declarations.
- Rollback or recovery: revert this ticket commit; no migrations or external state changes.

## Pause and escalation conditions

- Stop for declaration-policy decisions, credential requirements, or unrelated release blockers; record separately.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbhyu-mobile-release-candidate.md
- Validator result: structural validator passed; completion validator deliberately withheld because independent review remains pending.
- Independent verification result: pending
- Terminal state: GATE_REVIEW for this first increment only; broader mobile ticket remains In Progress.
- Remaining failed or blocked criteria: C-004 pending. Broader ticket still needs Android signing/label cleanup, release builds, current store-requirement checks, final archive privacy report, physical-device matrix and independent QA. No Flutter suite, archive or device run is claimed by this native-config increment.
- ClickUp final evidence comment: root-owned browser handoff pending
