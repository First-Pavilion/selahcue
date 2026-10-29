# Goal Contract — 86ak7kka2

## Identity

- Goal ID: TASK-86ak7kka2
- Parent goal ID: NONE
- Title: Pad allowed password-reset requests above measured branch work
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/86ak7kka2
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Allowed reset requests return byte-identical responses with branch timing inside a measured noise band under the documented deployment conditions, using the real production email sender and committed broker path.

## Baseline

Verified main b8fbb7c34a093cf98a612f76f4abe65a6cb84d2f includes PR260's bounded broker/result policy. Reset request already spends global/IP/address budgets and degraded-send ceiling, then performs existence-dependent commit/email work without a floor. Resend has a floor and rate-limited overrun report. The historical tiny branch-gap estimate excluded the synchronous broker round trip and is not a current measurement. Root verified the throttling parent is merged/QA and corrected only its stale dummy-hash paragraph with readback.

## Inputs and evidence sources

- Full task and both owner comments reread and saved in batch20-recovery/86ak7kka2-live.json; dated historical latency is not a current broker measurement.
- 86ak7kka2-parent-readback.json confirms narrow Markdown correction and unchanged QA status of86ak65mj5.
- Current accounts services, real CeleryEmailSender/shared task, resend floor/reporting and existing paired comparison tests.

## Scope

### In scope

- Padding allowed request_password_reset work outside owned transactions, an operational floor measured with real broker I/O, shared overrun reporting, existing-module tests and deployment evidence.

### Non-goals

- DEC013 reversal, login, confirm-reset, budgets, denied-path work, degraded ceilings, new logging pipeline, worker/result policy or native clients.

### Constraints

- No padding denied traffic and no extra work before existing refusal guards. Preserve generic responses and historical financial/domain data. No production broker/account/email side effects.
- Use a fresh Python3.14 environment from this tree's pyproject and owned synthetic PostgreSQL/Redis namespaces. No shared FLUSHDB, worker or actual email delivery.
- Local statistical measurements and heavy suites are prohibited while host paging rises. Root owns isolated hosted PostgreSQL/Redis baseline/candidate runs and retains their raw samples.

### Assumptions and unknowns

- The necessary default floor and measured noise band are UNKNOWN until the authorized quiet-window baseline. Network and overrun limits must remain explicit; there is no universal constant-time claim.

## Dependencies and approvals

- Root-approved ticket and four-review/fix/CI/merge/QA delivery. PR260 is actually merged and all reviews/CI passed.
- Root owns ClickUp comments/status, PR publication/push/merge, all four independent reviews and exact main CI. New circuit/native work is unpublished and must not be copied.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Allowed reset work pads after commit; denied traffic unchanged; existing overrun report reused | deterministic mechanism/no-extra-work tests in test_customer_auth_slice.py plus refusal controls | positive pad and shared bounded reporting; refusal does no extra work | /Users/m.oluwole/.codex/visualizations/2026/10/29/01a18528-5063-7712-beaa-3c2952075e3a/batch20-recovery/86ak7kka2-report.md | PENDING |
| C-002 | yes | Real sender/broker committed HTTP paired samples meet measured floor/noise bounds with identical response bytes | baseline/candidate paired test with raw timing/config receipt | actual shared task publishes private messages before HTTP returns; paired interval inside declared noise band | /Users/m.oluwole/.codex/visualizations/2026/10/29/01a18528-5063-7712-beaa-3c2952075e3a/batch20-recovery/reset-floor/measurements | PENDING |
| C-003 | yes | Removing only reset pad makes uniformity test fail with siblings running | bounded mutation driver and exact source restoration | RED with only pad removed; restored tests PASS; positive benign pad control executes | /Users/m.oluwole/.codex/visualizations/2026/10/29/01a18528-5063-7712-beaa-3c2952075e3a/batch20-recovery/reset-floor/mutation.log | PENDING |
| C-004 | yes | Focused/broad regression and docs/static checks pass on fresh merged main | fresh environment API tests, deployment docs guard, Django checks, main ancestry | actual results disclosed separately from earlier snapshots/skips; no attributable regression | /Users/m.oluwole/.codex/visualizations/2026/10/29/01a18528-5063-7712-beaa-3c2952075e3a/batch20-recovery/86ak7kka2-report.md | PENDING |
| C-005 | yes | All four reviews, exact hosted CI and api(django) green on main, with mutation evidence attached | root Cody/Quinn/Vera/Shadow re-review, hosted CI and ClickUp receipt | all required gates pass, exact merge/main and evidence linkage verified | root delivery evidence | PENDING |

## Verification plan

- Focused verification: new deterministic/production-path tests in test_customer_auth_slice.py, existing reset refusal/degraded tests and resend/reporting siblings.
- Broader regression verification: full API under owned PostgreSQL/Redis, deployment environment guard and Django/schema checks. Preserve every failed/incomplete run separately.
- Independent verifier: Cody, Quinn, Vera and Shadow through root; production-shaped timing measured only in the root-released window.
- Required environment: fresh Python3.14 venv from pyproject, synthetic private database and dedicated real Redis broker/unique queues; no worker.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: existing request reset leaves a deterministic pad-wiring gap; committed real sender measurements will determine a sufficient floor and noise band.
- Change or investigation: trace resend's padding/report and reset's guards; create fresh environment; write deterministic RED tests and prepare measurement harness without taking timing samples before window release.
- Verifier executed: structural validator before execution; deterministic tests and later measurement receipts recorded in handoff.
- Result: pending
- New evidence: source trace confirms current unpadded reset and synchronous on_commit broker publish; parent correction/merged broker prerequisite verified by root. Fresh Python 3.14.5 venv installed from pyproject. Deterministic tests: 3 expected failures (allowed reset has no outside-transaction sleep), 2 refusal controls passed, 116 deselected in 1.27s; no local statistical samples taken. New harness measures 4 warmup pairs, 32 AB/BA pairs and 32 interleaved same-path null pairs with actual Redis tasks and separate-connection committed-token checks.
- Decision: iterate

## Risks and rollback

- Risks: each allowed call occupies a request thread until the floor. A floor cannot hide work that overruns it or guarantee arbitrary network timing; reuse rate-limited reporting. Invalid/fault behavior and measured conditions must be explicit.
- Rollback or recovery: revert this ticket only; no schema migration, queue replay or token-policy change.

## Pause and escalation conditions

- Root-controlled quiet-window release required before statistical measurement. Escalate only real owner/access changes or new policy decisions; routine technical choices remain within this scope.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak7kka2-reset-request-floor.md
- Validator result: pending
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-005
- ClickUp final evidence comment: root owns publication
