# Goal Contract — 17tnw2b1uhz

## Identity

- Goal ID: TASK-17tnw2b1uhz
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Verify bounded payload-safe reconnect diagnostics and quiet test output
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1uhz
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Resolve or explicitly decline each of the seven existing diagnostics test/documentation items, prove per-outage deduplication and eight-frame truncation with meaningful mutants, and pass normal full Flutter analysis/tests without stray diagnostic stack dumps.

## Baseline

Preparation-only checkout from actual main5d041a102d0fb01e53719e99a55107b4efb69650 after F1Y merge. Existing controller has safe per-outage reportedTypes, capped jitter and cancellable retry, while debugReportUnexpectedConnectFailure prints runtime type plus maxFrames8 without printer-failure containment or release intent documentation. Existing diagnostics test lacks explicit SessionException-label exclusion; its1000attempt interval includes100ms transport time. Older malformed/launcher tests do not consistently capture print output. Qualification task has zero comments/dependencies and linked merged17tnw2b0vtj. Fresh full UI dispatch17tnw2b1uhz-dispatch-ui.txt confirms unchanged seven items/AC. Root authorized implementation; status/start comment pending Mac unlock, no false tracker receipt.

## Inputs and evidence sources

- Complete mobile-qualification/17tnw2b1uhz.json, linked17tnw2b0vtj-prerequisite.json, qualifications.md and AGENT-RUNBOOK.md.
- Current controller, session diagnostic helper, launcher and reconnect/launcher tests at actual main.
- Canonical runtime, role routing, mobile-engineer/goal operating contracts and bounded Goal validator.

## Scope

### In scope

- Existing reconnect diagnostic tests/documentation, small shared test-only capture utility, optional minimal helper containment with explicit tests if retained after fresh dispatch.
- Per-outage report reset, real eight-frame stack bound, safe expected-error exclusion, correct failure-to-next-start measurement and quiet sibling tests.

### Non-goals

- Reconnect backoff/cancellation behavior already merged in F1Y; protocol/credential/auth/revocation/command-deadline/epoch changes.
- New logging payload/telemetry policy, device/radio/battery/OS acceptance, native benchmarks, or unrelated UI work.

### Constraints

- Fresh full UI dispatch read before edits; code authorized while root catches up pending tracker start on unlock. No local runtime or tracker mutation.
- Own managed codex worktree and only scoped mobile diagnostic helper/docs/tests/Goal after dispatch. Not alone; preserve all others' changes.
- No local project runtime/build/test/import/install/pub/simulator/container/benchmark. Tiny source/Git/stdlib/static checks only; all runtime hosted.
- Coverage-only test/doc additions may correctly start GREEN; do not manufacture productionRED. If implementing optional printer-failure containment, prove actual hosted throwing-printer RED before helper behavior edits.
- Per-outage dedupe and frame-cap mutants must actually fail new named assertions with sibling positive controls; runner exact-first-parent/source/dependency identity and unchanged restoration required.
- Once dispatched, ordinary own push/draft/body-file/immediate attachment/separate workflow-only bounded diagnostics permitted. No forcepush/protected edits/merge/ClickUp/status/review publishing/subagents/next unit.

### Assumptions and unknowns

- Preserve existing intentional type/stack-only release reporting, document it instead of introducing kDebugMode gating. No host message or exception toString may reach the report.
- Optional printer containment is planned with explicit throwing-printer recovery controls, subject to unchanged fresh dispatch scope. If consciously declined, record one-line reason in PR before acceptance.
- No current runtime result for this unit; no native/device acceptance claim. F1Y QA receipt is pending and does not satisfy its completed export yet.

## Dependencies and approvals

- Root authorizes implementation after verified F1Y merge/QA and fresh complete UI dispatch; root owns pending start/status catch-up.
- Root owns allfour independent reviews, ClickUp start/status, merge and exactQA. No connector retry while ClickUp quota is capped.

## Seven-item disposition plan

| Existing item | Planned disposition and verifier |
|---|---|
|1 Expected-error assertion|Add explicit no SessionException printed line, retain planted payload/expected-error controls.|
|2 Per-outage and8frame properties|Exercise two actual outage/recovery cycles; deep supplied stack proves exact first8frame behavior; both required mutants fail named assertions.|
|3 Interval measurement|Subtract observed100ms connect duration or record actual failure timestamp so minimum wait2s cannot pass with1.9s; preserve F1Y growing/capped semantics.|
|4 Release intent|Document current intentionally enabled safe type/stack reporting in release; no new gating/policy.|
|5 Throwing debugPrint override|Plan minimal helper try/onObject containment only after actual hosted failing override control, preserving retry/launcher recovery; or explicitly decline with reason if fresh scope requires.|
|6 Throttling comment|Correct the claim that every debugPrint schedules aTimer; describe buffered throttling without relying on private Flutter thresholds.|
|7 Quiet sibling tests|Reuse shared capture helper in malformed-reply and launcher tests, restoring debugPrint before test invariants; full raw test log has no stray label/stack dumps.|

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All seven items have an explicit disposition | Full task-to-diff/PR matrix and source inspection | Seven done or consciously declined with one-line reason; no invented policy | Seven-item PR matrix/current patch | PENDING |
| C-002 | yes | Diagnostics stay payload-safe, expected errors absent and reset per outage | Hosted controlled errors and two real reconnect outages with recovery | Same unexpected type reports once per outage, reports again next outage; no SessionException label/payload | Focused raw test receipt | PENDING |
| C-003 | yes | Frame cap and backoff assertion measure claimed bounds | Deep stack and actual failure-to-next-start fake-clock observations | Only first8frames printed;2s minimum measured after transport completion | Focused hosted test output/source oracle | PENDING |
| C-004 | yes | Required diagnostic controls detect actual policy mutations | Separate hosted per-outage-set-to-controller-field and remove8frame-cap mutations, controls/restoration | Both new named assertions fail behaviorally; positive siblings and restored exact source pass | Mutant run/raw/source/dependency hashes | PENDING |
| C-005 | yes | Optional printer behavior is explicitly decided and verified if changed | PR disposition and actual hosted throwing-printer control before/after any helper behavior edit | Deliberate decline documented, or retry/launcher survive throwing printer without payload | Scoped disposition/RED/GREEN evidence | PENDING |
| C-006 | yes | Normal affected Flutter gates pass without stray stack dumps | Exact final-source normal flutter analyze/fulltest plus raw log inspection | Analysis/test success; no uncaptured unexpected-connect label/stack dumps; diagnostic globals restored | Normal job/head/tree/raw/hash receipt | PENDING |
| C-007 | yes | Clean immutable scope and independent delivery pass | Full current-main diffcheck/prefix proof, all4 final reports, merge and exactQA receipt | Only scoped files, no diagnostic workflow; Cody/Quinn/Vera/Shadow Pass and merge/QA verified | Root current-source receipts | PENDING |

## Verification plan

- After fresh dispatch, tests-first for optional behavior change and genuine coverage-first GREEN for properties already implemented. Keep these evidence types distinct.
- Shared test-only sync/async print capture restores global before Flutter invariant checks. Deep deterministic StackTrace input proves8frame cap; two-outage test uses current injected jitter/fake clock, actual state resynchronization and captured report labels.
- Hosted focused baseline, meaningful required mutants with siblings, exact restoration, then normal full Flutter analyze/test and raw quiet-output check; no local runtime.
- Root owns allfour fresh independent assessments/mergeQA. No completion while any mandatory criterion pending.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-007
- Hypothesis: a scoped seven-item matrix and source-qualified verifier design prepares the unit without premature implementation.
- Change or investigation: read complete qualification task/comments/dependencies/linked prerequisite and runbook; create own managed worktree/branch from actual5d041a10, inspect current helper/controller/tests, write bounded child Goal only.
- Verifier executed: structural Goal validation and tracked source/test diff check; hosted/runtime not executed.
- Result: preparation only; all runtime/review/delivery criteria pending. Await root fresh UI dispatch before implementation.
- New evidence: F1Y source already supplies capped/cancellable backoff; UHZ retains that behavior and tightens diagnostics assertions/docs only.
- Decision: yield preparation checkpoint; no source/test edits, publication, tracker writes or further unit.

### Iteration 2

- Target criterion: C-001 through C-006
- Hypothesis: real two-outage and supplied deep-stack observations close the existing coverage holes; an injected throwing diagnostic printer reproduces the optional survivability defect before helper changes.
- Change or investigation: read fresh full UI dispatch (unchanged7items/AC/list/task/link), root authorizes implementation while pending start/status catch-up remains explicit. Prepare shared sync/async print capture restoring before test invariants, quiet old malformed/launcher tests, explicit SessionException exclusion, actual failure-to-next-start timestamps, two real outages and deep20frame input. Add helper/reconnect/launcher throwing-printer controls before any production source edit. Preserve release/type-stack/F1Y/auth behavior.
- Verifier executed: structural Goal validation before edits, source/staticdiff checks; hosted full Flutter baseline and optional-printer behavioral RED pending.
- Result: tests/docs preparation; no production helper fix or runtime pass yet. Coverage-only existing properties may correctly pass the baseline.
- Decision: freeze tests-only candidate, obtain actual hosted printer failure and positive coverage/sibling outcomes; then minimal helper containment/docs, bounded mutants and full normal gates. No local runtime.

## Risks and rollback

- Risks: capture helper leaks a global override, test reads duplicate policy, default stack filter hides missing cap, or optional containment changes logging policy instead of preserving recovery.
- Rollback or recovery: revert only this unit's scoped diagnostics/test/docs changes; preserve F1Y transport/timing semantics and root delivery history.

## Pause and escalation conditions

- Follow captured fresh UI dispatch; escalate actual new owner decisions, do not assume unseen comments.
- Compiler/setup failures are not behavioral RED or killed mutants; preserve all failed attempts and actual unexecuted boundaries.
- Yield long hosted waits with immutable source/run; no silent extension beyond8 or next ticket without root assignment.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1uhz-reconnect-diagnostics.md
- Validator result: preparation structural validation PASS; no source/test implementation
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-007; hosted baseline/optional printer RED pending
- ClickUp final evidence comment: root owns publication
