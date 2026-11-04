# Goal Contract — TASK-17tnw2b0x3m-csp-wait

## Identity
- Goal ID: TASK-17tnw2b0x3m-csp-wait
- Parent goal ID: TASK-17tnw2b0x3m
- Title: CSP-safe authentication wait in shipping-image verification
- Role: frontend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0x3m
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
The production security browser gate waits for authentication completion under the existing strict CSP without evaluating a string predicate or weakening its checks.

## Baseline
Verified main6b096771d3d65c1dacf105523a4ee48edc2d4f93. Actual CI41823034596/job126550763358 reaches Chromium68 routes, then fails security_headers_headless.py85 with unsafe-eval EvalError from wait_for_function. Original PR352 is merged and its ticket QA. This is a new follow-up goal; the original ledger remains unchanged.

## Inputs and evidence sources
- Owning temporary follow-up record: https://github.com/First-Pavilion/selahcue/issues/364 (native ClickUp backfill pending); original merged implementation PR352.
- Root-provided actual CI log /private/tmp/wave2-350-final-marketing-ci.log and explicit approved follow-up scope.
- Existing shipping harness, nginx policy and API proxy-guard tests.
- Installed pinned Playwright1.60.0 source and actual Chromium/WebKit behavior.

## Scope
### In scope
- CSP-safe DOM authentication wait and meaningful real-browser regression with positive and pending-form negative behavior.
- Full existing68-route both-engine production probe and unchanged API nginx trust guards.
### Non-goals
- App/CSP changes, browser pins, timeout relaxation, nginx or Vite integration work, footer361, live accounts, secrets, provider/deployment/installer actions.
### Constraints
- Preserve all route/font/auth/mobile/header/error/injected-script assertions and strict script-src self without unsafe-eval/bypassCSP.
- New owned managed branch/worktree; never change frozen prior branches or primary mobile lock.
### Assumptions and unknowns
- VERIFIED: controlled real strict-CSP fixture independently reproduces old unsafe-eval error in both installed engines; the captured hosted shipping trace remains separate origin evidence.

## Dependencies and approvals
- User authorized fix/review loop; root explicitly assigned this necessary CI unblock.
- Tracker write is pending: connector dailyquota1000/1000 and browser inputs unavailable. Root explicitly authorizes code before verified InProgress for this external write blocker and will backfill native bug/status; no saved InProgress claim.
- Root owns all four independent reviews, actual CI, merge/main verification and QA.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Existing failure reproduced and auth wait uses CSP-safe DOM observation | real strict-CSP browser positive/negative regression | settled passes; busy/missing state fails; old expression refusal recorded | docs/delivery/evidence/17tnw2b0x3m-csp-wait/results.md | PASS |
| C-002 | yes | Complete shipping probe and API proxy guards preserved | actual Docker/CSP Chromium/WebKit and locked API file |68routes each/all existing checks and28APIcases pass | docs/delivery/evidence/17tnw2b0x3m-csp-wait/results.md | PASS |
| C-003 | yes | Current-source controls and clean immutable PR ready | focused tests, workflow/visual controls and freshness | actual completed commands pass, source/target recorded | docs/delivery/evidence/17tnw2b0x3m-csp-wait/results.md | PASS |
| C-004 | yes | Independent reviews/CI/integration/tracker backfill recorded | root Cody Shadow Quinn Vera/currentCI/merge/QA/readback | actual gates pass and tracker write confirmed | root handoff | PENDING |

## Verification plan
- Focused verification: real CSP fixture old-expression RED, locator wait GREEN, busy/missing negative.
- Broader regression verification: complete actual production browser probe, existing API proxy controls and affected CI checks.
- Independent verifier: root coordinates all four reviewers.
- Required environment: pinned Playwright1.60.0, actual Chromium/WebKit, official existing Docker image build and uv API environment.

## Iteration ledger
### Iteration 1
- Target criterion: C-001.
- Hypothesis: locator attribute assertion avoids main-world string evaluation while preserving exact aria-busy=false completion.
- Change or investigation: read actual hosted traceback and pinned Playwright waiter implementation; establish real-browser RED before harness edit.
- Verifier executed: pinned source traces all three old waits to globalThis.eval; real controlled Chromium/WebKit auth-wait RED; real locator fixture3 positive/4 negative cases per engine GREEN. Shipping-image production probe and API/control checks run separately.
- Result: three same-hazard waits replaced with exact DOM/real-event observations and original30s defaults. Controlled14 positive/negative cases pass; actual APIproxyfile28cases pass. Full production Chromium68routes passes, WebKit pending. Sharedvisual content/control checks pass but11.383s exceeded unchanged10s bound; do not claim that command passed.
- New evidence: actual hosted failure trace and unchanged strict production CSP.
- Decision: iterate.

### Iteration 2
- Target criterion: C-002/C-003 and final handoff.
- Hypothesis: run the existing visual budget gate separately from this task's browser workload without changing its source or10s limit.
- Change or investigation: completed shipping Chromium68+WebKit68/API28; preserved every assertion/policy/default30s timeout. Then ran the unchanged visual gate serially; retained both observations rather than hiding the first failure.
- Verifier executed: full shipping probe exit0/240.205s, real controlled14 positive/negative cases exit0, three real CLI missing-wait mutants exit1, API28 exit0, workflow118/normal20job/minute controls exit0, visual serial exit0/9.257s.
- Result: C-001/C-002/C-003 local PASS. C-004 root reviews/currentCI/integration and native tracker backfill PENDING.
- New evidence: docs/delivery/evidence/17tnw2b0x3m-csp-wait/results.md and raw compact JSON/text receipts.
- Decision: gate-review; all local processes and container finished before final freeze.

## Risks and rollback
- Risks: fixture could mask a pending form or weaken security checks; require negative behavior and full production assertions.
- Rollback or recovery: revert isolated harness follow-up; no app/data policy change.

## Pause and escalation conditions
- Stop for actual public-egress rejection or new owner-level scope decision; do not bypass gates or reset old ledger.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b0x3m-csp-wait.md
- Validator result: structural validation passes; completion remains pending C-004 external review/CI/integration/tracker evidence.
- Independent verification result: pending root reviews.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-004 pending root four reviews/currentCI/merge/main/QA and native tracker backfill; no write or completion claimed.
- ClickUp final evidence comment: pending root backfill; no write claimed.
