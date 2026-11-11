# Goal Contract — REMEDIATION-17tnw2b2jvy-20261105

## Identity

- Goal ID: REMEDIATION-17tnw2b2jvy-20261105
- Parent goal ID: NONE
- Title: Bound public catalogue outage latency and verify real admin mutation
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jvy
- Created: 2026-11-05
- Updated: 2026-11-05
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Bound public catalogue outage latency and verify real admin mutation, with measurable runtime evidence and independent review.

## Baseline

Remote main7f6dbcbb; public PR366439ca56. Prior API iterations1–8 remain historical, not reset. This explicit user-requested remediation has a new finite budget4. Catalogue internal writers exist; admin mutations do not. Nginx public route has default DNS/connect/read timeouts exceeding the30second client deadline. Real staff login remains undecided and is not implemented here.

## Inputs and evidence sources

- Live ClickUp task and dependencies, ADR0027, existing catalogue pricing/services and proxy tests.
- Retained iteration8 runtime evidence in /private/tmp/17tnw2b2jvy-iteration8-evidence.

## Scope

### In scope

- Task-specific backend service, GraphQL, tests, required exact public proxy controls, docs and runtime evidence.

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
| C-001 | yes | Missing and stopped API yield bounded honest JSON503 through shipping proxies | actual Docker nginx and Vite HTTP rehearsal | Original30second timeout no longer reached; JSON503/no-store | docs/delivery/evidence/17tnw2b2jvy-remediation.md | PENDING |
| C-002 | yes | Actual GraphQL admin mutation changes next public HTTP response | actual dev-auth-fixture HTTP mutation rehearsal | Changed price and weekly limit appear without deploy; production gate stays closed | docs/delivery/evidence/17tnw2b2jvy-remediation.md | PENDING |
| C-003 | yes | Existing public contract, full API gate and four reviews pass | focused tests, API check, hosted CI and four independent reviewers | All required gates pass | docs/delivery/evidence/17tnw2b2jvy-remediation.md | PENDING |

## Verification plan

- Focused verification: meaningful negative before fix and matching positive; permissions, values, cache/response controls.
- Broader regression verification: full API checks and actual hosted service CI.
- Independent verifier: Cody, Shadow, Quinn and Vera via parent.
- Required environment: pinned uv0.13.4, Python3.14, owned locked environment; actual Docker nginx/PostgreSQL/Redis where applicable.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: existing service writers can serve audited mutations while a finite exact-route timeout bounds upstream outage.
- Change or investigation: live requirements and code tracing; no production change yet.
- Verifier executed: contract validator before code.
- Result: exact-route timeout negative was red, then focused proxy tests passed; original local Docker runtime could not start.
- New evidence: staff login explicitly remains a production release gate, not a merge prohibition.
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

- Target criterion: C-001 and C-002.
- Hypothesis: actual exact-route timeout controls yield truthful fallback before existing client deadlines; real admin GraphQL writes invalidate the public response without deploy.
- Change or investigation: added finite shipping nginx/Vite controls, actual TCP/CSRF admin-to-public test, current Vite old/fixed proof and mandatory Linux nginx CI proof.
- Verifier executed: focused integrated95pass/4PGskip; actual Vite old10.0169second timeout vs currentJSON503in5.3016seconds; workflow checker7/21; runtime source compile.
- Result: actual HTTP mutation propagation and Vite proof pass; actual nginx Linux CI and PostgreSQL/four-reviewer gates pending.
- New evidence: original Docker runtime setup timed out; diagnostic Python3.9/HTTPError bugs corrected with all failures retained in evidence. Original client deadlines and strict response guards unchanged.
- Decision: handoff.
