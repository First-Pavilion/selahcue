# Goal Contract — 17tnw2b0vtm

## Identity

- Goal ID: TASK-17tnw2b0vtm
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Bound the entire parked pairing handshake from its hello
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0vtm
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Pairing receives one overall monotonic 150-second budget from its hello, independent of parked frames, closes on expiry, and still accepts an honest host's grant within its 120-second park window.

## Baseline

Fresh actual main bd6f6a531dc3393959c49fa44a70d6c688e4b9c1 contains approved queue disposal, credential bounds and late WebSocket cleanup. SelahSession.pair still loops past PairParked with a new nextJson(pairTimeout) each time. pairTimeout is150 seconds; the host park window is120 seconds. The existing PR132 forTest seam exposes the shared in-memory transport for commands, but no pairing entry yet.

## Inputs and evidence sources

- Complete wrapped task/comments at wave2-20261029/mobile-qualification/17tnw2b0vtm.json: comments empty, no blocking dependency, linked predecessor17tnw2ay5jk implemented by PR132.
- Current pair/connect/StreamQueue, forTest/_over transport seam, pairing controller and real pinned-TLS handshake tests.
- Existing monotonic command deadline tests and declared fake_async package; Stopwatch timing is real and cannot be advanced by fake_async.
- Root selected this final mobile unit and owns task UI, allfour independent reviews, merge and exactQA readback.

## Scope

### In scope

- Overall monotonic pairing budget from hello, remaining-time reads and expired-budget guard.
- Minimal shared private handshake extraction and visibleForTesting entry using PR132's existing send/close/StreamQueue/_over transport abstractions. Before RED, preserve existing per-frame behavior; productionpair signature, timeout and wire remain unchanged.
- Parked drip, near-deadline parked/silence, expired buffered grant, timely grant, rejection, malformed, host cancellation and resource cleanup regressions/controls.

### Non-goals

- New user cancellation API, retries, role/pairing policy, active buffer/frame caps or wire changes.
- Changes to TLS pinning, credentials/reason bounds, connection10s cleanup or queue lifecycle algorithms.
- UI/storage/platform/build/native acceptance or statistical performance measurements.

### Constraints

- Hosted actual behavioral RED and passing controls before minimal deadline correction; analyzer/setup failures do not qualify.
- Preserve default150s and public pair API; short in-memory test budgets scale the120/150 honest-host relationship without a150s local/runtime test.
- No local Flutter/pub/Node/build/runtime/simulator/container/benchmark while host resource restriction applies.
- New isolated branch only; not alone, preserve other authors' changes. Ordinary push/draft PR/body-file/immediateattachment/hostedCI allowed; no forcepush/protected edits/merge/ClickUpUI/status/review publication/subagents/new ticket.

### Assumptions and unknowns

- Honest120s grant acceptance is exercised at the same80percent of a short budget, supplemented by the production150s constant assertion and existing realTLS parked/granted tests; no native120s wall-time claim.
- Host stream completion models cancellation/disconnect; no user-facing cancellation policy is invented.
- Hosted setup/behaviorRED/GREEN and allfour reviews remain unverified until actual receipts.

## Dependencies and approvals

- PR132 in-memory transport/monotonic command prerequisite and current queue/lateconnect fixes are merged in actual main.
- Root owns ClickUp start, reviews, merge andQA. Mika owns this isolated source and authorized draft/hosted pipeline. No owner policy decision needed.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Parked frames cannot prolong pairing beyond one budget | In-memory repeated parked drip and late parked/silence tests on shared production handshake | Typed SessionException near total deadline, exactlyone transport close, no session returned | Hosted pairing deadline tests | PENDING |
| C-002 | yes | Expired pairing cannot accept an already buffered grant | Zero-budget in-memory grant fixture | Typed timeout, exactlyone close, no issued session | Hosted expired-budget guard test | PENDING |
| C-003 | yes | Honest parked host grants within its allowed window | In-memory80percent grant control, production150s constant guard, existing real pinnedTLS parked/granted tests | Credentials/role preserved, session stays live until callerclose, one hello | Hosted positive controls/fullsuite | PENDING |
| C-004 | yes | Rejection/malformed/cancellation/silent failures preserve cleanup and meaning | In-memory terminal/error controls and current realTLS/session suites | Original typed messages; close once, no successful session after failure | Hosted controls/fullsuite | PENDING |
| C-005 | yes | Regression detects the original overall-bound defect | Frozen behavior-preserving seam and tests, no deadline correction | Parked/clamped/expired tests fail behaviorally while controls pass | Actual exact-source hostedRED log | PENDING |
| C-006 | yes | Full corrected mobile checks pass | Fresh exact-source hosted flutter analyze and full flutter test | Both exit0; all new controls and regressions pass | GREEN run/rawlog/head/tree | PENDING |
| C-007 | yes | Independent review and authorized delivery complete | Root Cody/Quinn/Vera/Shadow reviews, merge and exactlinkedQA receipts | Four current-source Pass verdicts, verified merge and persistedQA readback | Root delivery evidence | PENDING |

## Verification plan

- Focused selector: flutter test test/models/session_pairing_deadline_test.dart from implementation/mobile/selahcue_controller.
- Existing hosted workflow runs analysis/fullFluttertest; preserve actual raw logs/source/tree and distinguish setup failure, behavioralRED and correctedGREEN.
- Existing realTLS tests cover production call path and wire/cleanup; in-memory regression invokes the same private handshake and PR132 transport abstractions.
- Short real Stopwatches exercise deadline semantics, using wide outer bounds to prevent a broken implementation hanging CI; no localruntime or benchmark.
- Root invokes allfour independent reviewers; no self-approval or merge.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: per-frame pairTimeout renews on every parked frame; a shared unchanged handshake seam will expose the defect with bounded real-time parked drips and positive controls.
- Change or investigation: full task/current main inspected, new isolated managed worktree/branch, prepare behavior-preserving shared handshake extraction and meaningful tests.
- Verifier executed: structural Goal validation before source work; hostedRED pending publication.
- Result: pending tests-only/seam publication and actual hosted behavior.
- New evidence: existing publicpair and in-memoryforTest do not yet share a pairing entry; narrow helper extraction is necessary for the ticket's explicit in-memory regression criterion.
- Decision: obtain actual hosted behavioralRED before adding the monotonic overall budget.

## Risks and rollback

- Risks: renewing the budget, starting before transport establishment instead ofhello, accepting a buffered expiredgrant, prematurely cancelling honest park, leaking failedhandshake socket or changing terminal reason semantics.
- Rollback or recovery: revert only this ticket; no wire/storage/schema/dependency/platform change.

## Pause and escalation conditions

- Repair setup/test-only errors before acceptingRED. No deadline correction before actual behaviorRED with controls.
- Yield long hosted waits with immutable source/run/checkpoint. Allfourreviews/mergeQA remain root-owned.
- Return remaining predicate for explicit root replan if eight iterations are exhausted; no silent extension. No additional mobile ticket after this unit.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0vtm-overall-pairing-deadline.md
- Validator result: structural validation passed exit0; behavioral RED pending hosted run
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-007
- ClickUp final evidence comment: root owns publication
