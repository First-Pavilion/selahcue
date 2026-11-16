# Goal Contract — TASK-17tnw2b1wvf

## Identity

- Goal ID: TASK-17tnw2b1wvf
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Bound accepted three-budget Redis requests to three round trips with atomic fixed windows
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wvf
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A real accepted three-budget request uses at most three budget Redis round trips, preserves all existing limiting behavior, starts each window on first hit and never leaves its counter without expiry through recreation, concurrency or a lost reply.

## Baseline

Fresh actual main9d9da7a0f68d43923dcd79e11c6f7970d7dd692f includes reviewed/QA X1P purpose-derived IP privacy. Current CacheStore Redis path uses cache.add then cache.incr and conditional TTL repair. Full task and fresh root UI capture show unchanged whole criteria, planning/todo, no new feedback. Linked predecessor86ak65mj5 is complete. The historical title says nine commands; actual current command count remains to be measured rather than assumed.

## Inputs and evidence sources

- api-qualification/17tnw2b1wvf.json, fresh api-qualification/17tnw2b1wvf-dispatch-ui.txt, source-backed qualifications.md and completed X1P evidence.
- Current throttling services/CacheStore, unchanged generic/local counter fixtures, password-reset accepted path, socket/circuit/response/HMAC tests, normal API workflow and deployment command-count docs.
- Repository CLAUDE.md, backend/goal contracts, parent WAVE3-SELAHCUE-20 and AGENT-RUNBOOK.md.

## Scope

### In scope

- Redis-specific atomic counter/window path in CacheStore, preserving existing generic/local-cache behavior and public API.
- Real Redis7 wire/counting-wrapper measurement of accepted three-budget requests, cold and existing counters; explicitly separate connection initialization/control commands from budget packets.
- Fixed-window, actual expiry/recreation, persistent-key repair, concurrent exact counts and after-write/lost-reply failure controls with meaningful mutation/restoration.
- Focused new Redis tests, child goal and precise DEPLOYMENT.md command-count reconciliation if required.

### Non-goals

- No owner-held WQU reordering/global cardinality policy, new limit/window, HMAC scheme, IP grouping, caller admission, outage/circuit/native distinction or dependency/provisioning change.
- No broad application redesign, deployment, performance waiver, timer inflation, modification/weakening of existing limiting assertions, or next DNU unit.

### Constraints

- Owned isolated codex/17tnw2b1wvf-redis-budget-roundtrips branch; not alone, preserve others' changes.
- Real hosted Redis behavioral RED before implementation; actual command counts, not timing benchmarks or mocks, establish the acceptance ceiling.
- No local project runtime/imports/tests/install/build/container/benchmark under paging. Only source/Git/stdlib/static/goal checks locally.
- Existing throttle tests remain unchanged; preserve generic fallback when injected cache doubles/proxies exercise its existing API semantics.
- Root owns four reviews/publication/merge/ClickUp/QA; author ordinary push/draftPR/body-file/immediate attachment and exact-parent workflow-only hosted diagnostics authorized.

### Assumptions and unknowns

- UNKNOWN current measured baseline and precise Redis wire vocabulary until hosted capture. Do not force the historical nine or treat setup errors as RED.
- Tests must observe real transport writes/backend state and positively prove recorder/injection execution; no vacuous counters or failure controls.

## Dependencies and approvals

- User-authorized frozen wave and root dispatch cover this unchanged existing task. X1P is merged/QA with reviewed HMAC identities; retain them verbatim.
- Later DNU remains queued until root assignment. No unresolved declared owner gate in this unit.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Real current Redis baseline and fixed-window gaps established with positive controls | Hosted real request/wire counting wrapper and expiry/failure tests against unchanged production | Actual cold/hot budget and initialization counts recorded; meaningful behavioral RED, no setup/oracle failure | red-ci metadata/raw and red-classification.json:actual3failed73passed3.79s | PASS |
| C-002 | yes | Accepted three-budget requests use at most three Redis budget round trips | Hosted real wire packet/counting wrapper on accepted reset path with same keys/counts and cold/hot counters | One to three actual budget request/reply packets; setup/control commands reported separately; three real budget spends proven | Focused GREEN and full CI raw logs | PENDING |
| C-003 | yes | Atomic fixed windows retain counts/expiry through boundary and failure cases | Real Redis first-hit/repeat/expired/persistent/concurrent/lost-reply tests and meaningful mutant/restoration | Window not extended on repeat, missing key starts at1, no persistent key, exact concurrent counts, unavailable outcome preserved | Hosted atomicity/sensitivity/restoration receipts | PENDING |
| C-004 | yes | Existing limiting/privacy/local-cache/caller semantics preserved | Existing test files byte-identical, full normal throttle/reset/cache/socket/circuit/privacy/response regressions, source comparison and docs review | Existing assertions pass unchanged; resolver/order/budget/admission/HMAC and generic fallback unchanged; accurate command docs | Git component proof, hosted full API raw and reviews | PENDING |
| C-005 | yes | Full final normal API integration gates pass | Exact-source hosted normal API20m check/migrations/full pytest with PG16/Redis7 | Applicable gates pass; existing intentional study skip explicit; no timeout/assertion waiver | Normal CI metadata/raw receipts | PENDING |
| C-006 | yes | Four current independent reviews, actual merged tree and exact qa readback pass | Cody/Quinn/Vera/Shadow root receipts, prefix/merge proof, exact linked ticket QA readback | No unresolved finding; approved result merged and correct ticket qa | Root consolidated/review/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: real Redis7 first/hot accepted path transport counts, actual backend TTL/count state, bounded concurrency and positively triggered lost-reply injection; raw mutation and restoration.
- Broader regression verification: full normal API20m CI, including all existing limiting/cache/circuit/socket/privacy/response tests unchanged.
- Independent verifier: root-coordinated Cody, Quinn, Vera and Shadow; author does not independently approve own work.
- Required environment: hosted Linux current Python/API services only for runtime; local stdlib source/Git/static/goal tools.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: the current add/incr Redis path exceeds the required ceiling on existing counters and cannot atomically preserve expiry after a recreation with a lost reply.
- Change or investigation: complete task/fresh UI/source reads and new managed isolated worktree at actual9d9da7a0; mapped existing generic cache fixture expectations to retain unchanged.
- Verifier executed: Git base/branch identity, source inspection and structural child validation before code.
- Result: scope/baseline established; actual Redis measurement and tests-first runtime evidence pending; no production fix.
- New evidence: full qualification/fresh dispatch packets, prior X1P completion and this contract.
- Decision: iterate

### Iteration 2

- Target criterion: C-001.
- Hypothesis: current configured Redis exceeds the hot-counter ceiling and can leave valid counters persistent under existing broken state or an after-write lost reply.
- Change or investigation: actual hosted41128913268 at tests-only035871a1/workflow-onlyec60d036; independently read raw, transport marker, all3failures and positive failure-injection assertions.
- Verifier executed: real Redis packed-write counting,3real ordered budget counts, fixed-window/expiry/concurrency/error controls and unchanged3limiting sibling modules.
- Result: actual3failed73passed3.79s, no setup/oracle errors. Cold3SET budget writes plus3separateCLIENT/CLIENT/SELECT initialization; hot9SET/EXISTS/INCRBY budget writes, zero setup. Persistent count8 and positively injected INCRBY lost-reply recreation count1 both retained PTTL=-1. Other73controls passed.
- New evidence: api-redis-budget-roundtrips/red-ci official raw/metadata/hashes; red-classification.json and exact-source component proof.
- Decision: iterate

### Iteration 3

- Target criterion: C-002 through C-005.
- Hypothesis: one bounded primary-key script creating with expiry and repairing persistence before increment meets the ceiling and failure/window invariants without altering generic callers.
- Change or investigation: Redis-positive-timeout branch uses Django's verified timeout/key adapter and one EVAL; new key SET includes expiry atomically, old deadline retained, persistent count repaired before increment. Generic API body, HMAC, resolver, caller order/limits/outage/circuit/native behavior unchanged. Ops command-count/ACL/timeout wording reconciled; historical latency is not claimed current.
- Verifier executed: official pinned Django6.1.2 Redis source read (get_backend_timeout/key/client contract), stdlib AST/unchanged-body/component checks, whitespace/goal validation. Hosted target GREEN, meaningful mutants/exact restoration and full normal API pending.
- Result: scoped candidate prepared; no runtime GREEN or review/merge claim yet.
- New evidence: django-6.1.2-redis-source.json/.py and forthcoming immutable candidate/mutation/full CI receipts.
- Decision: handoff

### Iteration 4

- Target criterion: C-004 and C-005; CODY-WVF-01.
- Hypothesis: truthful command vocabulary in the rewritten docs can satisfy the existing unchanged scanner contract without changing Redis code, tests or scanner allowlist/logic.
- Change or investigation: read full Cody review and independently classified actual diagnostic41134553072 candidate baseline1failed128passed6.34s. All7Redis controls passed/coldhot3EVAL; required docs dead-entry test failed, orchestrator correctly stopped before all mutants/restored suite. Docs now explicitly explain removal of the former EXISTS network check and format actual Lua EXPIRE/INCR ACL commands consistently. All55test files/scanner bodies/constants and Redis implementation unchanged.
- Verifier executed: exact raw failure/phase/transport marker classification, stdlib source/AST/component/diff/goal checks; fresh final normal and actual3mutants/restoration to follow.
- Result: required doc gate correction prepared; old failed run retained as incomplete mutation proof. CODY-WVF-01 closure and final gates pending actual fresh hosted results/review.
- New evidence: reviews/17tnw2b1wvf-cody.md; mutant-attempt1 official raw/metadata/hashes; mutant-attempt1-classification.json; forthcoming current-source r2 receipts.
- Decision: handoff

## Risks and rollback

- Risks: counting wrapper missing wire writes or including handshake, Redis serializer/versioned-key mismatch, TTL refresh or persistent recreation, partial write/reply failure, proxy-cache double regression or shared-file conflict.
- Rollback or recovery: one scoped PR, immutable actual counts/backend states, no existing test edits, bounded failure injection and exact-byte mutant restoration; revert only an evidenced affected merge if needed.

## Pause and escalation conditions

- Stop for new owner policy, unapproved/destructive/production actions or failed bounded-progress limit. Preserve every actual failure/skipped gate.
- Yield immutable source/hosted checkpoints promptly; no DNU or other selected task until root dispatch.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wvf-redis-budget-roundtrips.md
- Validator result: PASS structural validation before substantive tests
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-006 pending
- ClickUp final evidence comment: root-owned, pending
