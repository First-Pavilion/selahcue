# Goal Contract — TASK-17tnw2b2ka8

## Identity

- Goal ID: TASK-17tnw2b2ka8
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Account and navbar share one sign-out operation
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2ka8
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Account and navbar send one logout request, share pending and failure feedback, and both land on `/signin`.

## Baseline

Verified at main 55d5ff3a1b8d18e4702613cd1861a8d226197d37: Account uses useSignOut while Navbar duplicates its own request, flags and `/` navigation. Two composable consumers also have independent state.

## Inputs and evidence sources

- Full task and comments saved in wave2-20261029/frontend-qualification/17tnw2b2ka8-live.json.
- Owner comment 1400430000060105 approves `/signin` for both controls.
- Existing signOutFlow, useSignOut, Navbar, AccountView, accountSignOut tests and auth_pages_headless.py.

## Scope

### In scope

- Router-scoped shared pending/error state with caller-scoped disposal.
- Both real controls use the shared flow, canonical destination and announced feedback.
- Runtime composition, lifecycle and scripted network regression coverage.

### Non-goals

- Ticket 17tnw2b2ka9 refresh/sign-out race and changes to sessionStore refresh semantics.
- API contract, authentication policy, new visual design or unrelated features.

### Constraints

- One ticket, isolated worktree, one branch and PR. Root owns ClickUp updates, publication, hosted CI, independent reviews and merge.
- No local project runtime while host is paging. Prepare tests-only RED for hosted execution before production edits.
- Preserve server-confirmed sign-out semantics and per-caller navigation disposal.

### Assumptions and unknowns

- UNKNOWN: hosted regressions and independent review outcome; root verifies before merge.
- Screen-reader announcements use existing SrOnly and live-region conventions; no new design decision required.

## Dependencies and approvals

- Root authorized ticket implementation and `/signin` decision; root records start in ClickUp.
- Hosted clean npm install and execution owned by root because local resource admission failed.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Two consumers share one revoke and hold pending through navigation; separate routers remain isolated | `node --test tests/sharedSignOut.test.ts` | All behavioral assertions pass after observed assertion RED on unchanged production | Hosted test log linked by root | PENDING |
| C-002 | yes | Account and navbar use canonical shared flow, `/signin`, accessible pending and failure feedback | `npm run test:states` and component tests | Scripted logout, recovery, route and announcement assertions pass | Hosted states/component log | PENDING |
| C-003 | yes | Lifecycle failure remains visible to surviving chrome and disposed callers do not redirect | Focused sign-out node and browser tests | Late failure, navigation rejection, retry and disposal cases pass | Hosted focused log | PENDING |
| C-004 | yes | Marketing checks and existing state regressions pass | `make marketing-check` and `npm run test:states` | Exit zero with no new failures | Hosted check logs | PENDING |
| C-005 | yes | Independent reviewers approve frozen implementation | Cody, Quinn, Vera and Shadow review current commit | No unresolved blocking findings | Root consolidated review | PENDING |

## Verification plan

- Focused verification: fresh hosted npm ci then `node --test tests/sharedSignOut.test.ts`, existing accountSignOut tests and scripted sign-out scenarios.
- Broader regression verification: make marketing-check and marketing test:states.
- Independent verifier: Cody, Quinn, Vera, Shadow coordinated by root.
- Required environment: clean hosted Node matching lockfile; browser state runner with required browser availability. Local runtime prohibited during host paging.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: two component scopes sharing one real router currently each send a revoke request; an assertion on shared pending and request count exposes the duplicate flow.
- Change or investigation: create tests-only regression against unchanged production before implementing shared state.
- Verifier executed: hosted CI run 40940516583, diagnostic f6f15157, source bd25796d81a09ee76ea348ca23d257e3602edad6; `node --test tests/sharedSignOut.test.ts`.
- Result: Observed assertion RED, expected one revoke and actual two; distinct-router positive control PASS (one pass, one fail). No product code was changed before this evidence.
- New evidence: wave2-20261029/frontend-red.log; https://github.com/First-Pavilion/selahcue/actions/runs/40940516583.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: sharing operation refs per real router, while retaining per-caller disposal, prevents cross-control duplicate revocation without redirecting a departed Account caller.
- Change or investigation: both components adopt the same composable and `/signin`; surviving chrome reports late failures; pending always settles; late rejected navigation is disposal-gated. Account, navbar header and mobile modal have one active announcement owner. Replace source-label parity pins with runtime composition and scripted simultaneous real-control presses. Add node coverage of the default revoke through the real session store/account seam, router isolation, retry/remount and navigation rejection.
- Verifier executed: Python stdlib AST of the changed headless script, Goal Contract structural validator and baseline-to-candidate `git diff --check`; no local project runtime under resource restriction.
- Result: Static gates PASS. Hosted GREEN, type/lint/build, real browser gates and independent review remain unexecuted on this candidate.
- New evidence: source/test diff and root handoff for this frozen revision. The exact browser check count is deliberately not guessed: retain the old strict guard until the first hosted run reports the measured new count, then update it and rerun before acceptance.
- Decision: handoff

### Iteration 3

- Target criterion: C-002 through C-004.
- Hypothesis: adopting the actual measured browser check total will let the strict guard accept the added scenarios without removing checks or changing bounds.
- Change or investigation: update only EXPECTED_MIN_CHECKS from 2575 to the measured 2608 and record the receipt. Inspect existing workflow ordering for the subsequent WebKit infrastructure failure; do not change workflow or tests.
- Verifier executed: read hosted CI run 40941630343 for source d46097bb803899bfefdd370097a1244bade6a891, saved wave2-20261029/frontend-green-attempt1.log, lines 188-190; inspect .github/workflows/ci.yml marketing step ordering; Python stdlib AST, Goal Contract structural validation and full baseline-to-HEAD diff check.
- Result: Browser behaviour passed 73 scenarios and 2608 checks with zero failures, but the command exited 4 because the old exact-count guard expected 2575. The later Playwright install step uses the default success condition and was skipped after that failure; WebKit explicitly uses `if: !cancelled()` and therefore ran without Playwright and exited 3. This is not evidence of a WebKit product regression. The complete hosted rerun remains mandatory.
- New evidence: https://github.com/First-Pavilion/selahcue/actions/runs/40941630343 and the saved full failed log. Static gates PASS; no local project runtime.
- Decision: handoff

### Iteration 4

- Target criterion: C-003 and Cody finding CODY-KA8-01.
- Hypothesis: router-lifetime reuse retains a settled failure after all consumers leave for bare `/signin`, so a new successful sign-in on the same router remounts Account with stale feedback.
- Change or investigation: verified App.vue bare-route unmount, SignInView's real sign-in then router replacement, and useSignOut's unbounded settled error lifetime. Add tests only: real signIn/account seam plus all-consumer disposal/remount reproducer; active-operation remount and surviving feedback control.
- Verifier executed: hosted diagnostic 40943085685 on source e302a7a574c7cba4299b235931d2c0fc4b96fc88; `node --test tests/sharedSignOut.test.ts`.
- Result: Actual assertion RED, expected empty feedback for the new session and actual prior SIGN_OUT_FAILED. Six tests passed and one failed; the all-consumers-leave-active/remount positive control passed. Production was unchanged at this checkpoint.
- New evidence: tests/sharedSignOut.test.ts, wave2-20261029/reviews/cody-ka8-r1.md and frontend-review-red.log; https://github.com/First-Pavilion/selahcue/actions/runs/40943085685.
- Decision: iterate

### Iteration 5

- Target criterion: C-003 and Cody finding CODY-KA8-01.
- Hypothesis: count active consumers per router, retaining an entry only while observed or pending, to expire a settled failure before a later sign-in without clearing a live operation.
- Change or investigation: useSignOut releases an unused settled entry at the final scope disposal and after an operation settles; keep entries with surviving/remounted consumers and all pending entries. An identity guard prevents an old disposed controller from removing a newer router entry. No sessionStore, authentication policy or ka9 changes.
- Verifier executed: Goal Contract structural validation, stdlib AST of the changed browser script and full baseline-to-HEAD diff check. No local project runtime.
- Result: Static checks PASS. Fresh hosted regression GREEN, complete marketing/browser CI and all four current-source reviews remain pending with root.
- New evidence: narrow useSignOut lifetime change and the observed RED plus positive control from iteration 4.
- Decision: handoff

## Risks and rollback

- Risks: a global pending flag can stick after unmount; duplicate live regions can announce twice; sharing across SSR routers can leak state. Tests must cover each relevant boundary.
- Rollback or recovery: revert this ticket's single PR; retain server-confirmed revocation semantics throughout.

## Pause and escalation conditions

- Pause production edits until hosted assertion RED is observed. Root owns resource admission, CI and review gates.
- Escalate newly required product/authentication policy decisions; do not include ka9 race remediation.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2ka8-shared-signout.md
- Validator result: PASS structural validation on 2026-10-29; project runtime remains unexecuted locally.
- Independent verification result: Pending root review pipeline.
- Terminal state: BLOCKED on root-owned hosted candidate verification and independent reviews; implementation prepared.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns publication after implementation, CI and review.
