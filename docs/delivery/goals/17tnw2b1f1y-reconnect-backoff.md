# Goal Contract — 17tnw2b1f1y

## Identity

- Goal ID: TASK-17tnw2b1f1y
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Bound reconnect attempts with capped jittered backoff and immediate teardown cancellation
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f1y
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Consecutive failed reconnect attempts wait increasing capped jittered intervals, success resets the sequence, and dispose/unpair synchronously remove pending backoff timers. Unexpected failures remain observable by type/stack without host text; attempts remain serialized and retired results cannot revive a stopped controller.

## Baseline

Actual main e5a1611b728901811b6427f7cff2ded0ccfa4dcd. LiveController._reconnect still uses uncancellable fixed Future.delayed(2s). Existing per-outage type/stack-only reporting already satisfies the original observability behavior and must remain unchanged. Epoch fencing and late socket cleanup are merged; auth/revocation/command deadlines remain authoritative. Fresh dispatch payload has planning/todo, zero comments/dependencies, linked predecessor17tnw2b0vtj captured in qualification. Root explicitly sequences this independent unit while WT5 fixture runtime is pending; no shared source/tests.

## Inputs and evidence sources

- wave3-20261030/AGENT-RUNBOOK.md and mobile-qualification/qualifications.md.
- Full17tnw2b1f1y-dispatch-live.json/task history and17tnw2b0vtj-prerequisite.json.
- Current LiveController, SessionException/reporting helper and existing backoff/malformed/retired-read/revoked tests.

## Scope

### In scope

- Controller reconnect delay state, bounded jitter calculation and cancellation lifecycle; focused fake-clock tests and minimal injected random seam.
- Existing observable type-only diagnostics controls, successful reset, no overlap, in-flight completion/failure after teardown.

### Non-goals

- Protocol, credentials, revocation, pairing/connect/command deadlines, queue policy, polling cadence or product workflow changes.
- UHZ seven-item diagnostics expansion, real radio/battery/native/device/Windows/macOS acceptance or benchmarks.

### Constraints

- Isolated managed codex worktree/branch, own controller/focused tests/Goal only. Not alone; never stage/revert others.
- No local project runtime/build/test/install/import/pub/simulator/container/benchmark. Tiny Git/source/stdlib/static checks only; runtime hosted.
- Actual hosted behavioral RED with existing positive controls before production behavior edits. Deterministic random seam may be added only with minimal fix after RED.
- Retry delay windows chosen to preserve existing minimum2s while adding bounded jitter:2–2.5s,4–5s,8–10s,16–20s, then24–30s repeatedly. Upper ceiling doubles from2.5s to maximum30s; actual delay80–100percent of ceiling. Per-outage local ceiling naturally resets after success. Clock injection uses existing fake_async timer-zone pattern; deterministic random injection verifies endpoints and repeated capped jitter. This is a bounded technical choice within explicit task scope, not a protocol timeout change.
- Ordinary push/draft/body-file/immediate attachment and separate workflow-only bounded hosted diagnostics allowed. No forcepush/protected edits/merge/status/ClickUpUI/review publishing/subagents/next ticket.

### Assumptions and unknowns

- No immediate abort of an already in-flight socket connect is introduced; existing bounded connection deadline and late-session close remain. Teardown must not create a new delay after that attempt fails.
- Hosted RED/candidate/normal/mutation results pending. Native hardware behavior unexecuted and not required for this timer/controller scope.

## Dependencies and approvals

- Root freezes selected20 and owns task start/status, allfour independent reviews, merge andQA.
- WT5 product source remains frozen/independent. UHZ starts only after F1Y merge/root dispatch.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Consecutive failures use growing capped jittered backoff and successful reconnect resets it | Hosted fake-clock actual attempt timestamps and deterministic random sequence | Declared windows across uncapped/capped delays; endpoint/midpoint draws change delays; second outage restarts first window | Focused raw test receipt/source hashes | PENDING |
| C-002 | yes | Teardown cancels waiting immediately and does not create later attempts or delay timers | Fake-clock pending timers at dispose/unpair; delayed connect success/failure controls | Zero pending delay/poll timers immediately; no post-teardown retries; late acquired session closes | Focused hosted tests/raw | PENDING |
| C-003 | yes | Retry remains serialized and error reporting safe/observable | Slow connect overlap, typed unexpected failures and expected SessionException/revoked controls | Max one connect; bounded type/stack reports without planted payload; revoked terminal; current-epoch synchronization preserved | Focused/full hosted Flutter outputs | PENDING |
| C-004 | yes | Regression tests detect the actual defect and meaningful candidate control mutations | Unchanged-production hosted RED plus selected interval/cap/reset/cancel mutant cases with restored controls | Expected behavior failures before fix; targeted new assertions fail for actual mutants; restored focused source passes | Immutable RED/mutant/restoration runs and objects | PENDING |
| C-005 | yes | Normal full affected Flutter gate and clean scope pass | Hosted normal flutter analyze/fulltest plus baseline diffcheck/source/target proof | Analysis and all tests pass; final diff only scoped controller/tests/Goal; no diagnostic workflow | Current normalCI/head/tree/raw manifest | PENDING |
| C-006 | yes | Independent review and authorized delivery close | Root Cody/Quinn/Vera/Shadow final reports/merge and exactQA readback | Four current-source Pass; actual merge/tree andQA verified | Root receipts | PENDING |

## Verification plan

- Initial tests use unchanged production, actual fake-clock attempt timestamps and pendingTimers. Growth/cancellation must fail behaviorally while timely recovery/serialization/reporting controls remain meaningful.
- Minimal fix adds deterministic random injection and a single owned cancellable Timer/Completer; clock is supplied by existing fake_async zone, no production clock policy.
- Focused fake-clock suite plus existing backoff/malformed/revoked/retired-read/command deadline regressions; normal hosted full Flutter analyze/test mandatory.
- Separate workflow-only exact-first-parent mutation runner anchors candidate objects, runs meaningful interval/cap/reset/cancel mutations with surviving controls and restores identical source; no product diagnostic file survives.
- Root runs allfour current-source reviews; no completion claim until every mandatory predicate passes.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-004
- Hypothesis: actual fake-clock interval and synchronous pending-timer observations reproduce fixed-delay and teardown leakage without any production edit.
- Change or investigation: full task/linked prerequisite/current source read; own managed worktree created at actual main; define concrete bounded windows, deterministic verification and scope before code.
- Verifier executed: structural Goal validation before tests; source-only inspection, no local runtime.
- Result: preparation only; hosted RED and runtime controls pending.
- New evidence: type/stack-only diagnostics are already shipped and are preserved, not reimplemented.
- Decision: add meaningful tests-only regressions and publish hosted baseline RED; only after actual behavioral qualification implement minimal delay/cancellation change.

## Risks and rollback

- Risks: resetting too soon defeats backoff; cap overflow, timer leak, post-dispose scheduling, stale session adoption, or payload-bearing diagnostics.
- Rollback or recovery: revert this unit's controller/tests/Goal only; protocol and auth unchanged.

## Pause and escalation conditions

- Compiler/setup failures are not behavioral RED; repair tests/setup without product behavior changes.
- Yield long hosted waits with clean immutable source/run/checkpoint. No silent iteration extension after8 or next unit without root.
- Valid failures remain recorded; no diagnostics-only success substitutes for normal acceptance.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1f1y-reconnect-backoff.md
- Validator result: structural validation PASS before and after tests-only preparation; actual hosted RED pending
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-006
- ClickUp final evidence comment: root owns publication
