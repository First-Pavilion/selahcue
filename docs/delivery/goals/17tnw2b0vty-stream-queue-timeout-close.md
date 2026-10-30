# Goal Contract — 17tnw2b0vty

## Identity

- Goal ID: TASK-17tnw2b0vty
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Preserve timeout-boundary frames and dispose closed session queues
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0vty
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A frame already handed to a queue waiter at its timeout boundary is returned exactly once. Closing the owning session stops inbound retention, clears buffered frames, cancels its subscription and releases pending reads consistently.

## Baseline

Freshly fetched main 7f2e35734fcb56fa0616221a6796bccf82c630c8 (tree e2d344e2) leaves nextJson throwing after timeout even when the waiter has already been removed for delivery. StreamQueue does not retain its subscription or expose explicit disposal, and SelahSession.close only closes the transport. Existing malformed-frame, handshake, deadline and controller tests exercise the current session behavior.

Full saved task/comments at wave2-20261029/mobile-qualification/17tnw2b0vty.json were read. Successful comments response is empty; no declared blocker exists. Task measurements are reporter evidence, not locally reproduced timings or memory claims.

## Inputs and evidence sources

- Existing task 17tnw2b0vty, complete criteria and successful comments read.
- lib/models/session.dart StreamQueue and SelahSession.close ownership.
- Existing real queue/session tests and SelahSession.forTest transport seam.
- Existing hosted Flutter workflow runs pub get, analysis and full tests.
- Root's explicit scoped branch-publication/draft PR/hosted RED-GREEN authority; root retains reviews, merge and ClickUp.

## Scope

### In scope

- Resolve already-delivered waiter data at the timeout boundary without dropping or duplicating it.
- Explicit queue/session close lifecycle: stop subscription, clear retained frames, finish pending reads, await cancellation.
- Deterministic synchronous-stream/scheduler regression and public queue/session lifecycle controls.

### Non-goals

- General active-session buffer/frame caps (separate ticket 86ajxwcnc), late WebSocket connect cleanup, overall pairing deadline, wire changes or retry policy.
- New UI, platform configuration, signing, native builds or physical-device acceptance claims.

### Constraints

- No local project runtime, Flutter/pub/Node/build/simulator/container or statistical measurement while resource admission is unavailable.
- Observe actual hosted behavioral RED on unchanged production before implementing; compilation/setup failure is not RED.
- Use the real queue/session implementation; controlled external scheduling must not substitute a fake queue algorithm.
- No force push, protected branch edits, merge, ClickUp mutation, review publishing or additional agents.
- Preserve others' changes; only this isolated ticket branch and assigned queue/session lifecycle files/tests/goal.

### Assumptions and unknowns

- A controlled Timer zone can deliver synchronous data and fire its read timeout before delivery microtasks run, making the reported boundary deterministic without thousands of trials.
- Buffer disposal is checked through existing nextJson behavior: pre-close buffered and post-close frames cannot be read after session close. Subscription cancellation is observed at the controlled stream boundary.
- These tests establish queue ownership and logical disposal, not native socket-close latency, RSS measurements or throughput.
- Actual hosted test-only RED is established; corrected GREEN and independent reviews remain pending.

## Dependencies and approvals

- Existing typed SessionException, production session seam and hosted CI are available on current main.
- No declared task dependency or owner decision blocks this slice.
- Mika may push this branch, create/attach a draft PR and run/read hosted test-only and candidate CI. Root owns independent review routing, merge and exact QA handoff.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A waiter-delivered frame survives its timeout boundary | Real synchronous stream and controlled timer callbacks in the same turn | Delivered JSON returned exactly once; no false timeout | Hosted boundary regression and positive controls | PENDING |
| C-002 | yes | Session close releases retained and future inbound data | Buffer frames, close real in-memory SelahSession, then emit more frames and read queue | Subscription cancelled; no readable pre/post-close frame; closed SessionException | Hosted lifecycle regression receipts | PENDING |
| C-003 | yes | Close releases pending readers and awaits cancellation consistently | Multiple pending reads plus controlled asynchronous stream cancellation | Readers fail closed promptly; close remains pending until cancellation completes; repeat close safe | Hosted lifecycle regression receipts | PENDING |
| C-004 | yes | Existing queue/session behavior remains intact | Normal delivery, genuine timeout/late frame, FIFO/natural completion controls and full suite | Controls pass; existing parser, handshake, deadline and controller tests pass | Hosted analysis/full Flutter tests | PENDING |
| C-005 | yes | Regressions detect the baseline gaps before implementation | Frozen test-only commit, draft PR and actual hosted execution | Behavioral boundary/lifecycle failures with positive controls passing | PR 274 run 41032689523 on 87e19f3f: analysis passed, 446 tests passed and 5 behavioral failures; saved mobile-stream-queue-red.log | PASS |
| C-006 | yes | Corrected candidate passes broader hosted gates | Fresh hosted flutter analyze and full flutter test | Analysis exits 0; full applicable suite passes on exact candidate | Exact-source hosted GREEN log/run | PENDING |
| C-007 | yes | Required independent review and delivery close | Cody, Quinn, Vera, Shadow and root merge/QA receipts | Four current-source passes, actual merge verified, exact linked QA status persisted/reread | Root review/delivery evidence | PENDING |

## Verification plan

- Focused selector: flutter test test/models/stream_queue_lifecycle_test.dart from implementation/mobile/selahcue_controller.
- Test-only draft PR runs hosted pub get, flutter analyze and full flutter test. Inspect actual negative assertions and positive controls before production edits.
- Corrected candidate runs fresh hosted analysis/full tests; preserve all skipped/unexecuted native and path-gated jobs explicitly.
- Root independently coordinates Cody, Quinn, Vera and Shadow; Mika does not self-approve or merge.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: a waiter removed for delivery can lose to timeout propagation, while missing queue disposal leaves dead-session frames/subscription alive.
- Change or investigation: inspect task/current main and write deterministic scheduler plus public session-close regressions before production changes.
- Verifier executed: structural Goal validation/full baseline diff check; published tests-only draft PR 274 and inspected full hosted Flutter log from run 41032689523, job 123986046411, on commit 87e19f3fddfcabc26879d6d7e6b017c5b397e318.
- Result: actual behavioral RED. Analysis passed, 446 tests passed and 5 failed: the boundary read timed out despite delivery, close had zero cancels, buffered frame 1 remained readable, pending-reader results stayed empty, and asynchronous cancellation was never started. Normal delivery/cancelled timeout, genuine timeout/late frame and natural FIFO completion controls passed.
- New evidence: raw log saved at wave2-20261029/mobile-stream-queue-red.log and inspected before any production edit. Existing public session seam exercises ownership without a new production test-only API.
- Decision: iterate with timeout-result rescue and explicit queue/session disposal; retain all observed tests unchanged.

### Iteration 2

- Target criterion: C-001 through C-004, C-006 and C-007
- Hypothesis: a timeout should throw only if its waiter is still queued; otherwise consuming the original delivered result prevents loss. Queue disposal must synchronously stop retention before waiting on transport cleanup.
- Change or investigation: retain/cancel the subscription, discard explicit-close buffers and finish pending waiters as closed, ignore terminal-stream callbacks, and make queue cancellation idempotent. Session close starts queue disposal before the transport handshake and awaits both cleanup futures even if either fails. Timeout handling consumes the original waiter result when delivery/terminal completion already removed it.
- Verifier executed: source inspection, full baseline diff check, structural Goal validation and unchanged-test diff. No local project runtime ran under resource restrictions.
- Result: corrected candidate prepared for fresh hosted analysis/full Flutter tests; no corrected-source pass is claimed yet.
- New evidence: production edits are confined to session.dart queue/session ownership and timeout handling, with active-session caps, connection establishment and pairing deadlines unchanged.
- Decision: publish corrected candidate and inspect fresh hosted full-suite results; yield the exact CI checkpoint during long waits, then hand immutable source to root for independent reviews.

## Risks and rollback

- Risks: timeout rescue must not swallow a genuine timeout or duplicate a frame; disposal must not abandon pending futures, retain late data or leak transport when cancellation fails.
- Rollback or recovery: revert this ticket only; no schema, storage, wire or platform migration.

## Pause and escalation conditions

- Actual behavioral RED was observed before production edits; corrected-source hosted gates and independent reviews remain required.
- Yield a checkpoint with PR/head/run ID during long CI waits; root can supply completion evidence and resume work.
- Hand back an immutable clean corrected candidate after hosted gates; root owns independent review, merge and QA. Do not start another ticket.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0vty-stream-queue-timeout-close.md
- Validator result: structural validation passed (exit 0); corrected-source behavior awaits fresh hosted execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-004, C-006 and C-007; C-005 passed on frozen test-only source
- ClickUp final evidence comment: root owns publication
