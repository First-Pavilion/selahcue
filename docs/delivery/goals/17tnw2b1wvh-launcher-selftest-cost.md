# Goal Contract — 17tnw2b1wvh-launcher-selftest-cost

## Identity

- Goal ID: TASK-17tnw2b1wvh
- Parent goal ID: NONE
- Title: Reduce fake-hang fast-path cost while preserving strict launcher checks
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wvh
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The launcher self-test's ready fast path costs about two seconds less, while delayed startup retries, real hangs, cleanup and failure verdicts remain strict; scheduling and browser-wall-time decisions are documented with honest evidence scope.

## Baseline

Verified main8f7d610ef81efc4c7359e9b3cb6d9d44fb99c56e. The hung fake uses3s then20s startup attempts; the browser wall cap is90s and launcher self-test runs on every operator gate invocation. The new16 environment CLI checks fromPR253 are part of the baseline, so older4.1s/full-gate percentages are not current measurements.

## Inputs and evidence sources

- Coordinator full live task in additional-live-payloads.md: planning/todoLow, no blocker/comments, related17tnw2b1f32QA.
- scripts/headless_chrome.py and scripts/operator_headless.py; existing strict real-PID/helper/temp/signal/result checks.
- Historical ticket evidence: PR15320paired runs; old79.8s browser phase/load117 and59KB measurement. These are not fresh observations.

## Scope

### In scope

- Fake-hang schedule1s,3s,20s; paired startup/fallback measurement, explicit every-run scheduling and90s/150s wall-cap decision; parent-description narrow correction payload for root.

### Non-goals

- Weakened assertions, sweep/litter redesign, other launcher migration, native/API/dependencies or unsupported platform claims.

### Constraints

- Keep3s middle and20s fallback; no rescue of a hung browser from partial results. Preserve real process/temp cleanup.
- Shared repository: own this branch only. Root owns publication/reviews/CI/merge/QA and parent ClickUp description edit/read-back. No UI or shared Rust/Flutter/fullmakeci work.
- Defer heavy measurements during explicit Mika quiet-CPU windows; declare ambient workload and scope.

### Assumptions and unknowns

- Scoped repeated measurement executes the exact tracked hang-loop AST, real _Case/launcher and verdict/cleanup checks, not the entire16-case CLI group. A full gate runs after the change. Natural startup readiness and terminal flake counts are distinct.

## Dependencies and approvals

- User approved this existing task and four independent reviews/remediation, merge and QA. Parent-description correction is explicit taskAC; root owns the external edit/status.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Ready hang fast path saves about2s with bounded1/3/20 startup retries and repeated-run evidence | Scoped20paired AB/BA real-launcher samples | Median paired saving at least1.5s; all samples/readiness/fallback/flakes recorded | /private/tmp/selahcue-batch20-20261029/17tnw2b1wvh-samples.json | PASS |
| C-002 | yes | Delayed startup uses3s/20s fallbacks; a complete result plus genuine hang remains failing with no surviving process/temp files | Scoped controlled readiness cases, injected wrong timeout verdict and full launcher self-test | Forced fallback controls pass; incorrect timeout verdict isRED | Probe logs/report | PASS |
| C-003 | yes | Every-run versusCI-only and90s versus150s decisions record current scope and historical/fresh headroom separately | Committed decision document plus one full timed gate | Decisions explicit; exact current/historical calculations, no old measurements presented as current | docs/ops/HEADLESS-GATE.md and full-gate timing | PASS |
| C-004 | yes | Full operator gate, launcher siblings and syntax/diff/goal checks pass | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py plus syntax/diff/validator |2347browser checks0FAIL, complete self-test exit0 | /private/tmp/selahcue-batch20-20261029/17tnw2b1wvh-browser-green.log | PASS |
| C-005 | yes | Parent17tnw2b1f32 description replaces~1MB claim with Vera's historical~59KB measurement and persisted read-back | Root narrow description edit/read-back, no status change | Exact edited phrase saved; other contents/status preserved | Root tracker evidence | BLOCKED |
| C-006 | yes | Cody/Quinn/Vera/Shadow and final applicableCI pass on final revision | Coordinator independent reviews/CI | All pass | Coordinator evidence | BLOCKED |
| C-007 | yes | PR merged and linked taskQA persisted | Root GitHub/ClickUp read-back | Verified merged and saved QA | Coordinator evidence | BLOCKED |

## Verification plan

- Focused verification: baseline self-pair RED,20interleaved baseline/candidate pairs, forced readiness delay/fallback and strict partial-result hang failure; retain all samples/load/fallback counts.
- Broader regression verification: complete actual Chrome operator gate including16environment cases; Python syntax/diff/structural checks and hostedCI.
- Independent verifier: Cody, Quinn, Vera, Shadow through root.
- Required environment: current macOS/POSIX/Python/Chrome; quiet-CPU coordination with Mika, no claim of historical stress-load reproduction.

## Iteration ledger

### Iteration 1

- Target criterion: C-001,C-002
- Hypothesis: an initial1s readiness attempt saves2s on a ready fake while3/20s retries preserve delayed-start coverage.
- Change or investigation: build source-linked scoped measurement and first observe the performance predicate fail against the unchanged schedule.
- Verifier executed: one baseline/candidate pair before the schedule edit, using the exact tracked hang-controller AST and actual fixture/launcher/verdict.
- Result: expected RED exit1; both schedules still3/20, baseline3.022381s/candidate3.010357s, saving0.012025s below the predeclared1.5s predicate. All process/temp/strict-verdict checks pass.
- New evidence: docs/delivery/goals/17tnw2b1wvh-evidence/red-samples.json and batch17tnw2b1wvh-red.log.
- Decision: iterate

### Iteration 2

- Target criterion: C-001,C-002
- Hypothesis: prepend a1s readiness attempt while retaining3s/20s and every assertion.
- Change or investigation: one schedule edit plus explanatory comments. Execute20interleaved AB/BA pairs before Mika's subsequent full nativeCI load; no quiet-host/stress claim. Launcher/fixture/PID primitives are AST-identical to baseline. All40 samples/load/attempts retained.
- Verifier executed: scoped20paired real launches and controlled readiness/incorrect-verdict checks.
- Result: GREEN exit0, median paired saving2.003454s; baseline median3.013465s/candidate1.010239s. Each version0natural retries/0terminal failures in20 samples at ambient1m load6.48–15.35. Synthetic1.5s delay uses1/3,4s delay uses1/3/20; all recorded processes dead/temp folders empty. Incorrect non-timeout flag on a real hung fake produces the expected strict-verdict RED.
- New evidence: docs/delivery/goals/17tnw2b1wvh-evidence/schedule-samples.json and schedule-controls.json; full batch logs.
- Decision: iterate

### Iteration 3

- Target criterion: C-003,C-004
- Hypothesis: retain mandatory every-run launcher checks and bounded90s Chrome wall cap, with explicit headroom/cost provenance rather than historical figures presented as fresh.
- Change or investigation: docs/ops/HEADLESS-GATE.md records decisions, worst nominal startup-budget tradeoff, scoped raw/reproduction artifacts and parent-edit payload. Replace stale~4s startup wording without changing runtime assertions.
- Verifier executed: one complete actual operator gate with read-only timing instrumentation; no verdict substitution or skipped checks.
- Result: GREEN exit0,2347browser checks/0FAIL and full launcher/environment contract. Current single self-test38.736s, Chrome13.763s,total55.021s;90s cap leaves76.237s/553.9% of that observed phase. Historical79.8s/10.2s/12.8% is separately labeled. No paired full-gate percentage or maximum-latency claim.
- New evidence: docs/delivery/goals/17tnw2b1wvh-evidence/gate-timing.json; batch17tnw2b1wvh-browser-green.log.
- Decision: iterate

### Iteration 4

- Target criterion: C-001..C-004
- Hypothesis: current target's reset-KDF API-only delta cannot alter the tested launcher/browser inputs.
- Change or investigation: fast-forwarded the isolated feature branch onto mainc0b8f84aa801ae97ac3faf7717cc313dcc4b312b while preserving this ticket's owned edits. Its4-file delta is API/tests/goal only. Verified both tested script SHA256 values unchanged from the measured full gate after integration. Saved all raw samples and portable runner; function-body AST equals the executed runner, with only workspace/output binding changed.
- Verifier executed: Python compilation, portable runner help, diff check, source hashes, target ancestry/behind0, structural Goal Contract validator.
- Result: all checks PASS. No unnecessary repeat of unchanged20pairs/full browser gate. Independent reviews/CI and root-owned parent-description/merge/QA remain required.
- New evidence: final handoff report and committed raw evidence; parent edit payload17tnw2b1wvh-parent-edit.md in batch directory.
- Decision: handoff

## Risks and rollback

- Risks: wall-clock scheduling variability and benchmark overlap; record all samples and defer during explicit quiet windows. Startup retry is inconclusive, distinct from a failing terminal verdict.
- Rollback or recovery: revert the isolated ticket commit(s).

## Pause and escalation conditions

- Pause heavy tests for Mika's explicit quiet-CPU window. Root handles owner/access/parent-description dependencies. Do not weaken predicates to manufacture a performance result.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wvh-launcher-selftest-cost.md
- Validator result: structural PASS; completion blocked only C-005,C-006,C-007
- Independent verification result: pending root
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006,C-007
- ClickUp final evidence comment: root owned
