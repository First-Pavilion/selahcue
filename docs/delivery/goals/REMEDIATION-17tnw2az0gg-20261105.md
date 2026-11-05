# Goal Contract — REMEDIATION-17tnw2az0gg-20261105

## Identity

- Goal ID: REMEDIATION-17tnw2az0gg-20261105
- Parent goal ID: NONE
- Title: Audited optimistic admin catalogue mutations
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az0gg
- Created: 2026-11-05
- Updated: 2026-11-05
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Audited optimistic admin catalogue mutations, with measurable runtime evidence and independent review.

## Baseline

Remote main7f6dbcbb; public PR366439ca56. Prior API iterations1–8 remain historical, not reset. This explicit user-requested remediation has a new finite budget4. Catalogue internal writers exist; admin mutations do not. Real staff login remains undecided and is not implemented here.

## Inputs and evidence sources

- Live ClickUp task and dependencies, ADR0027, existing catalogue pricing/services and proxy tests.
- Retained iteration8 runtime evidence in /private/tmp/17tnw2b2jvy-iteration8-evidence.

## Scope

### In scope

- Task-specific backend service, GraphQL, tests, docs and runtime evidence.

### Non-goals

- Staff IdP or MFA decisions, production enablement, deployment, payment changes, frontend card implementation.

### Constraints

- Owned branch/worktree; preserve other authors and dirty primary lockfile. One ticket per PR. No fake authentication evidence; distinguish controlled dev HTTP identity fixture from real production sign-in.

### Assumptions and unknowns

- UNKNOWN historical exact outage cause until reproduced. Production staff authentication is absent; owner decisions remain on17tnw2az0n5.

## Dependencies and approvals

- User explicitly requests fix, re-review and merge after all required gates. Parent coordinates four reviews, publication and merge.
- Admin mutation may be built and merged before staff login per17tnw2az0n5; it cannot be enabled in production.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Authorized admin GraphQL reads and writes current prices and grants | focused admin catalogue tests | All happy paths and permission negatives pass | docs/delivery/evidence/17tnw2az0gg-remediation.md | PENDING |
| C-002 | yes | Replay once, reject stale revision and invalid data without writes | focused admin catalogue tests | One audit/receipt on replay; concurrent stale edits refused | docs/delivery/evidence/17tnw2az0gg-remediation.md | PENDING |
| C-003 | yes | Production catalogue mutation remains disabled until real staff authentication | settings subprocess and HTTP tests | Production refuses enablement; forged headers cannot mutate | docs/delivery/evidence/17tnw2az0gg-remediation.md | PENDING |
| C-004 | yes | Regression and all four independent reviews pass | API checks, hosted CI and Cody/Shadow/Quinn/Vera | All required gates pass | docs/delivery/evidence/17tnw2az0gg-remediation.md | PENDING |

## Verification plan

- Focused verification: meaningful negative before fix and matching positive; permissions, values, cache/response controls.
- Broader regression verification: full API checks and actual hosted service CI.
- Independent verifier: Cody, Shadow, Quinn and Vera via parent.
- Required environment: pinned uv0.13.4, Python3.14, owned locked environment; actual Docker nginx/PostgreSQL/Redis where applicable.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: existing service writers can serve audited admin catalogue mutations while preserving their validation.
- Change or investigation: live requirements and code tracing; no production change yet.
- Verifier executed: contract validator before code.
- Result: focused20 passed/2 explicit PostgreSQL skips before final accountability assertion; final focused and full checks recorded in handoff.
- New evidence: staff login explicitly remains a production release gate, not a merge prohibition. Actual query/grant HTTP, signed manifest propagation, history/replay, invalid values and production gate tests pass locally.
- Decision: iterate.

## Risks and rollback

- Risks: accidental staff exposure, duplicate audit, lost updates, proxy timing regressions.
- Rollback or recovery: revert task PR; never remove retained price/audit history or production data.

## Pause and escalation conditions

- Stop for unresolved owner authentication decisions if production enablement requested; do not implement guessed login. Three failed materially different attempts without new evidence stop. Parent owns review/merge.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py this-file
- Validator result: pending.
- Independent verification result: pending.
- Terminal state: pending.
- Remaining failed or blocked criteria: pending.
- ClickUp final evidence comment: pending.

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: durable request receipts plus a revision CAS close duplicate and stale writes; current-only price SQL avoids historical read growth.
- Change or investigation: implemented field errors, immediate price append, HTTP and signed manifest checks; two actual PostgreSQL concurrency tests await hosted execution.
- Verifier executed: focused tests, migration generation; full API verification started with actual local socket permissions after sandbox refusal.
- Result: local focused passes; required PostgreSQL/hosted and independent reviews pending.
- New evidence: real dev-fixture GraphQL operation changes next signed manifest, not a mocked service response.
- Decision: handoff.

### Iteration 3

- Target criterion: C-001 through C-004.
- Hypothesis: meaningful non-control names prevent catalogue poisoning, and all managed writers acquiring revision before data eliminate the verified lock-order inversion.
- Change or investigation: fixed both reviewer findings; added HTTP rollback negatives and actual PostgreSQL lock-boundary tests; documented the new environment flag and API contract.
- Verifier executed: expanded focused443pass/6explicitPG/service skips; prior full check2388pass/56skip/57subtests plus one now-focused-corrected environment-doc failure; current full and hosted verification required.
- Result: local focused passes; actual PostgreSQL and four-reviewer final gates remain pending.
- New evidence: four name negatives failed before the fix; actual PostgreSQL lock inspection is encoded, not falsely credited from SQLite.
- Decision: handoff.
