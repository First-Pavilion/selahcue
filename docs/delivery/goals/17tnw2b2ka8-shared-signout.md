# Goal Contract — TASK-17tnw2b2ka8

## Identity

- Goal ID: TASK-17tnw2b2ka8
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Account and navbar share one sign-out operation
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2ka8
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Account and navbar send one logout request, share pending and failure feedback, and both land on `/signin`.

## Baseline

Verified at main 55d5ff3a1b8d18e4702613cd1861a8d226197d37: Account uses useSignOut while Navbar duplicates its own request, flags and `/` navigation. Two composable consumers also have independent state.

## Inputs and evidence sources

- Full task and comments saved in wave2-20261029/frontend-qualification/17tnw2b2ka8-live.json.
- Owner comment 1400430000060105 approves `/signin` for both controls.
- Existing signOutFlow, useSignOut, Navbar, AccountView, accountSignOut tests and auth_pages_headless.py.

## Scope

### In scope

- Router-scoped shared pending/error state with caller-scoped disposal.
- Both real controls use the shared flow, canonical destination and announced feedback.
- Runtime composition, lifecycle and scripted network regression coverage.

### Non-goals

- Ticket 17tnw2b2ka9 refresh/sign-out race and changes to sessionStore refresh semantics.
- API contract, authentication policy, new visual design or unrelated features.

### Constraints

- One ticket, isolated worktree, one branch and PR. Root owns ClickUp updates, publication, hosted CI, independent reviews and merge.
- No local project runtime while host is paging. Prepare tests-only RED for hosted execution before production edits.
- Preserve server-confirmed sign-out semantics and per-caller navigation disposal.

### Assumptions and unknowns

- UNKNOWN: hosted regressions and independent review outcome; root verifies before merge.
- Screen-reader announcements use existing SrOnly and live-region conventions; no new design decision required.

## Dependencies and approvals

- Root authorized ticket implementation and `/signin` decision; root records start in ClickUp.
- Hosted clean npm install and execution owned by root because local resource admission failed.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Two consumers share one revoke and hold pending through navigation; separate routers remain isolated | `node --test tests/sharedSignOut.test.ts` | All behavioral assertions pass after observed assertion RED on unchanged production | Hosted test log linked by root | PENDING |
| C-002 | yes | Account and navbar use canonical shared flow, `/signin`, accessible pending and failure feedback | `npm run test:states` and component tests | Scripted logout, recovery, route and announcement assertions pass | Hosted states/component log | PENDING |
| C-003 | yes | Lifecycle failure remains visible to surviving chrome and disposed callers do not redirect | Focused sign-out node and browser tests | Late failure, navigation rejection, retry and disposal cases pass | Hosted focused log | PENDING |
| C-004 | yes | Marketing checks and existing state regressions pass | `make marketing-check` and `npm run test:states` | Exit zero with no new failures | Hosted check logs | PENDING |
| C-005 | yes | Independent reviewers approve frozen implementation | Cody, Quinn, Vera and Shadow review current commit | No unresolved blocking findings | Root consolidated review | PENDING |

## Verification plan

- Focused verification: fresh hosted npm ci then `node --test tests/sharedSignOut.test.ts`, existing accountSignOut tests and scripted sign-out scenarios.
- Broader regression verification: make marketing-check and marketing test:states.
- Independent verifier: Cody, Quinn, Vera, Shadow coordinated by root.
- Required environment: clean hosted Node matching lockfile; browser state runner with required browser availability. Local runtime prohibited during host paging.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: two component scopes sharing one real router currently each send a revoke request; an assertion on shared pending and request count exposes the duplicate flow.
- Change or investigation: create tests-only regression against unchanged production before implementing shared state.
- Verifier executed: structural Goal Contract validation; project runtime deferred to hosted root execution.
- Result: Pending actual hosted assertion RED; no product code changed.
- New evidence: tests/sharedSignOut.test.ts; root handoff records exact test commit and commands.
- Decision: handoff

## Risks and rollback

- Risks: a global pending flag can stick after unmount; duplicate live regions can announce twice; sharing across SSR routers can leak state. Tests must cover each relevant boundary.
- Rollback or recovery: revert this ticket's single PR; retain server-confirmed revocation semantics throughout.

## Pause and escalation conditions

- Pause production edits until hosted assertion RED is observed. Root owns resource admission, CI and review gates.
- Escalate newly required product/authentication policy decisions; do not include ka9 race remediation.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2ka8-shared-signout.md
- Validator result: PASS structural validation on 2026-10-29; project runtime remains unexecuted locally.
- Independent verification result: Pending root review pipeline.
- Terminal state: ACTIVE; tests-only handoff awaiting hosted RED.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns publication after implementation, CI and review.
