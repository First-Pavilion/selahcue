# Goal Contract — TASK-17tnw2b2g24

## Identity
- Goal ID: TASK-17tnw2b2g24
- Parent goal ID: NONE
- Title: Loading-only footer height reservation
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2g24
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
During an actual cold lazy-route pending state, reserve the viewport below the navbar so the footer is offscreen; release reservation when content resolves and preserve short-page flow.

## Baseline
Fresh main e45ac0efc5e897c84427634601ff8e787b436d79. App.vue has a Suspense fallback but no reserved height; Vue Router import readiness must be observed in real Chromium. Integrated root main d9fcd524634ab9328231b6d984bd16be11d2ea78 (PR345 auth baseline2765 retained).

## Inputs and evidence sources
Active ticket, Uma comment1400430000277444, App.vue, existing router, responsive browser server and current main.

## Scope
Only App.vue, focused loading/CLS browser checks, goal and evidence. No page/footer design, shared tokens, API/provider calls, route loading changes, prices/copy, deployment or packaging. Analytics and permissions have no new behavior; preserve bare-route chrome policy.

## Dependencies and approvals
User authorized selected public ticket PR delivery. Uma approved loading-only reservation. Root owns independent reviews, merge and QA. Auth PR345 integration expected before final checks; other agents own separate lanes.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual delayed lazy route shows readable announced fallback with footer below viewport | loading_footer_headless.py | fallback observed, contrast at least4.5, footer top at least viewport height | docs/delivery/evidence/17tnw2b2g24/green.json | PASS |
| C-002 | yes | Pricing and Terms cold-load CLS median below0.1 at375/1440,3 runs each | loading_footer_headless.py | each four-cell median below0.1 | docs/delivery/evidence/17tnw2b2g24/green.json | PASS |
| C-003 | yes | Resolved404/short Changelog match baseline footer flow; reservation removed | loading_footer_headless.py baseline comparison | main/foot geometry unchanged within1px and no loading element | docs/delivery/evidence/17tnw2b2g24/green.json | PASS |
| C-004 | yes | No horizontal scroll375/768/1440, bare auth chrome preserved, eagerHome CLS below0.1, readiness rejection releases loading and Home navigation recovers | loading_footer_headless.py | overflow zero, bare nav/footer absent | docs/delivery/evidence/17tnw2b2g24/green.json | PASS |
| C-005 | yes | Restoring missing reservation fails target browser checks | isolated mutant build plus browser check | nonzero exit and footer/reservation assertion fails | docs/delivery/evidence/17tnw2b2g24/negative.json | PASS |
| C-006 | yes | Required marketing/state/responsive commands pass completely | make marketing-check; npm run test:states; npm run test:responsive | all exit0 with no skipped required engine | external completed PR/ClickUp receipt | PENDING |
| C-007 | yes | Four independent reviews pass exact source | root coordinated Cody Shadow Quinn Vera review | all four pass | external PR review receipt | PENDING |

## Verification plan
Production bundle served locally; Chromium Playwright with isolated fresh contexts, explicitly held route chunks and PerformanceObserver layout-shift session-window metric. Three samples per Pricing/Terms width. Existing responsive server reused. External fonts/API blocked or deterministically stubbed. Baseline short-page geometry retained, no real account/provider calls.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 through C-004
- Hypothesis: observe actual lazy chunk pending state before applying fallback-only reservation.
- Change or investigation: write browser harness before product source edits and measure unchanged shell.
- Verifier executed: loading_footer_headless.py on untouched App bundle
- Result: exit1,120 target failures; actual fallback absent, footer visible. Terms medians0.5188889 at375 and0.398021 at1440; Pricing medians0.0484296/0.0253805 already below threshold but loading footer still violates decision.
- New evidence: router imports resolved outside Suspense; short-page baseline captured before edits.
- Decision: iterate

## Risks and rollback
Initial router readiness may not render Suspense fallback; verify real pending DOM. Bare routes must keep chrome absent. Reservation must not survive resolution. Revert this ticket commit to roll back.

## Pause and escalation conditions
Stop for changed design intent or route-loading/API contract changes; report measured failing source. Maximum4 iterations; root owns review gate.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b2g24.md
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: review and complete command receipts pending
- ClickUp final evidence comment: pending

### Iteration 2
- Target criterion: C-001 through C-004
- Hypothesis: App-only initial router readiness plus fallback min-height fixes actual pending state; resolve/reject both release it.
- Change: observe router.isReady, preserve target bare metadata before currentRoute resolves, add loading-only viewport-minus-navbar height and explanatory comment.
- Verifier: complete focused browser harness including failure recovery and eagerHome; pending.
- Decision: iterate.

### Iteration 3 — measured refinement approved by root
- Fallback reservation alone fixed Terms but Pricing375 was short and its footer moved900px to517px on resolution, producing medianCLS0.18109753. Root approved pending-only visibility:hidden while retaining footer layout/reservation, restored on readiness success/failure.
- Corrected the verifier's mistaken computed min-height expectation0px: unchanged baseline is auto. Compare actual baseline geometry/minimum, not an invented value. Earlier diagnostic includes that test-assumption failure and is not a passing command.
- Added short Pricing baseline comparison and pending/resolved footer visibility checks; final complete browser measurement pending.
- Decision: iterate to complete browser measurement and negative proofs.

### Iteration 4 — final validation and frozen handoff
- Approved App source restored after all4 targeted mutant builds; each fails its intended assertion, including missing rejection release and recovery.
- Complete focused browser run after pending-visibility refinement passes all27 cases; medians0 at375 and0.00003057 at1440 for Pricing/Terms.
- make marketing-check passes1246 unit tests, lint, type and production build.
- First required responsive invocation correctly failed1 of2363 checks: broad main-child wait sampled new shell Loading... text at Reset375 before route rendering. Root approved replacing only that wait with a resolved-route child predicate; all assertions/counts retained. Failed invocation kept separately.
- Final source now frozen; required responsive/state commands rerun sequentially and kept alive until completion. A final strengthened focused measurement runs against an immutable fresh bundle.
- Independent four-role review remains with root; no completion claim before all command receipts and review.

Final focused receipt: all27 cases pass on fresh immutable production bundle, Chromium148.0.7778.96. Pricing/Terms medians0 at375 and0.00003057 at1440; all3 samples retained per cell. Contrast8.7374:1; short geometry and failure recovery pass. All4 negative cases rejected. Final responsive command passes2363 checks across41 routes ×5 widths after the approved readiness-wait fix; no assertion/count removed. Exact2765-state CLI remains active at publication. Final external receipt supersedes publication-time pending labels, without a source-only update. C-006 remains pending until command completion; C-007 awaits root's four independent reviews.
