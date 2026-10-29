# Goal Contract — 17tnw2b1wqb-activation-content-type

## Identity

- Goal ID: TASK-17tnw2b1wqb-activation-content-type
- Parent goal ID: SelahCue-batch20
- Title: Simple non-JSON native requests cannot spend the shared-egress activation/read budget
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wqb
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Refuse non-JSON enrollment activation before throttle/database work, while preserving valid JSON requests and bearer-only refresh compatibility.

## Baseline

Fresh main034fa597 includes device-input validation. Enrollment activation and license refresh still throttle before checking Content-Type; account activation/session login already use a JSON guard. Refresh accepts either a bearer header or a JSON body token, whereas manifest is GET.

## Inputs and evidence sources

- Coordinator live ClickUp payload in api-queued-payloads.md, task section17tnw2b1wqb: description, three acceptance criteria, related prerequisite86ak5t1gw QA, no blocker or substantive comments.
- Existing native content-type guard, refresh bearer/body handling, shipped HTTP fixtures and API tests.

## Scope

### In scope

- Reuse the existing JSON guard above enrollment activation throttle and protect refresh's JSON body-token fallback while retaining bearer-only requests.
- Meaningful budget-order, no-database and existing-client regressions.

### Non-goals

- Authentication, budget sizes/outage policy, response-header policy, GET routes or other queued tickets.

### Constraints

- Own branch/worktree; no push/PR/merge or self-approval; coordinator owns final hosted CI/four reviews/QA.
- No competing full make-ci or duplicate broad local API run; changed-tests PostgreSQL verification required.

### Assumptions and unknowns

- INFERRED: allowing the existing bearer-header refresh path is compatible with the content-type threat model because Authorization requires a cross-origin preflight; the token still authenticates in the existing service.
- UNKNOWN: tracker status/start comment pending Mac unlock, coordinator owns access and updates.

## Dependencies and approvals

- Related native route prerequisite86ak5t1gw is QA; no blocking dependency listed.
- User authorized this20-ticket implementation/review/remediation/merge/QA batch.

## Completion predicate

All mandatory criteria must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Two simple non-JSON activation requests leave a1/60s budget usable by valid JSON activation | new content-type HTTP regressions on SQLite/PostgreSQL |400,400,200; zero queries/writes on refusals | 11 focused PostgreSQL tests pass;125 covering SQLite tests pass,1 existing expected failure | PASS |
| C-002 | yes | Guard ordering is load-bearing | production-linked decorator-order mutant | moving guard below throttle fails budget regression | Both production guards relocated below throttle:6 failures,5 deselected; restored source passes | PASS |
| C-003 | yes | Refresh JSON fallback protected, bearer-only and valid JSON clients unchanged | new tests plus covering native/refresh/activation suites | all applicable tests pass; no GET changes | 11 PostgreSQL tests pass, including header-only positive controls and invalid-header precedence;125 covering SQLite passes | PASS |
| C-004 | yes | Django checks/migrations and final hosted API gate pass | checks and coordinator final CI | no system/schema issues and full API green | local logs and CI | PENDING |
| C-005 | yes | Four independent reviews pass and merge/QA state verified | coordinator Cody/Quinn/Vera/Shadow and GitHub/ClickUp read-back | final head approved, merged, exact QA persisted | coordinator report | BLOCKED |

## Verification plan

- Focused verification: real HTTP/budget/database checks, test-first baseline, decorator-order mutant.
- Broader regression verification: native/activation/refresh/entitlement tests; hosted full API gate by coordinator.
- Independent verifier: Cody, Quinn, Vera, Shadow.
- Required environment: Python3.14, SQLite and dedicated PostgreSQL16.2; no production services.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: reuse the existing guard before throttle; allow only the already-supported bearer-header refresh alternative to bypass JSON-body requirement.
- Change or investigation: write failing budget/no-query/client-compatibility regressions before production edits.
- Verifier executed: pending.
- Result: pending.
- New evidence: pending.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: placing the existing JSON guard above throttle closes both simple-request budget drains while allowing the existing non-ambient bearer refresh alternative.
- Change or investigation: moved the helper before enrollment view, reused it above activation throttle and above refresh throttle with a bearer-header option. The original account activation and session-login guards retain their strict default. No authentication, budgets or GET routes changed.
- Verifier executed: focused baseline, corrected focused tests on PostgreSQL16.2, covering native/activation/refresh/manifest suites on SQLite, actual source decorator-order mutation with restoration in finally, system/migration/diff checks.
- Result: baseline6 failures4 positive passes; corrected focused11 pass4.78s; covering125 pass1 existing expected failure66.64s. Mutant6 failures5 deselected3.07s, exit1 as required. Django system and committed-migration checks pass.
- New evidence: the guard's rejected requests execute zero database queries and leave a real one-request budget available; next valid JSON call succeeds and another valid call is429. The unchanged expected failure is the separate17tnw2b1wqc429-header ticket. Coordinator approved the conditional bearer-header refresh interpretation before implementation finalization.
- Decision: handoff.

## Risks and rollback

- Risks: guard ordering can consume budgets; strict JSON on bearer-only refresh could break existing clients.
- Rollback or recovery: revert this isolated ticket commit; no data/schema/config migration.

## Pause and escalation conditions

- Escalate any legitimate client compatibility conflict; never weaken credential authority to make a transport test pass.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wqb-activation-content-type.md
- Validator result: structural pass; completion blocked by final hosted CI and independent review/delivery.
- Independent verification result: pending coordinator.
- Terminal state: BLOCKED pending coordinator-owned review, final hosted CI and delivery.
- Remaining failed or blocked criteria: external review/CI/delivery.
- ClickUp final evidence comment: pending coordinator.
