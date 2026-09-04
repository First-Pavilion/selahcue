# Goal Contract — TASK-security-review-pr17-web-auth-rereview

## Identity

- Goal ID: TASK-security-review-pr17-web-auth-rereview
- Parent goal ID: NONE
- Title: PR #17 (feat/86ak11r67-web-auth-wiring) is security re-reviewed at head 9fef5db with prior findings re-verified, findings posted on the PR, and a verdict reported to the requester
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak11r67
- Created: 2026-08-30
- Updated: 2026-08-30 (completed)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

At head 9fef5db (base origin/main 90b28f7): the five original security findings (LOW-1..LOW-5, closed by 4e0bca3) are independently re-verified as still closed; the update-merge integrity claims are verified by SHA; the full auth-wiring diff is re-reviewed for what the 112-commit update may have disturbed; the two cross-review judgement questions (settled-state probe coverage union, strip/trim divergence in signupPolicy.ts) receive explicit verdicts; findings are posted as PR review comments and a security verdict issued.

## Baseline

PR #17 is an open Draft against main wiring the marketing SPA's sign-in / create-account / forgot-password to /graphql/account. I reviewed the branch four days ago (5 LOW findings, closed by 4e0bca3); code review found 1 HIGH / 2 MEDIUM in the guard set (closed by 1f21f41); QA found the DOM-attribute channel (closed by 0b8dbf5, 212f99a). The branch was then brought up to date by merge (9fef5db). Second-opinion step waived by the owner for this session. My concurrent PR #16 review found a Python strip / JS trim divergence on U+001C-U+001F and U+0085 and a stale passwordPolicy.ts rationale; this PR ships a new client-side signupPolicy.ts.

## Inputs and evidence sources

- Repository at /Users/m.oluwole/Documents/code/scph (read-only against the reviewed branch; own worktree in the session scratchpad for gates and mutation probes)
- `git show 9fef5db:<path>` / `git show 90b28f7:<path>` / merge-base 607a7b5 — never the shared working tree
- PR #17 description, commits 7df4746 / 4e0bca3 / 0b8dbf5 / 212f99a / 1f21f41 / 891d044 / 9fef5db
- implementation/marketing: lib/auth/sessionStore.ts, session.ts, signupPolicy.ts, redirect.ts, countries.ts; lib/api/account.ts, graphql.ts; views SignInView/SignUpView/ForgotPasswordView; router/index.ts; scripts/auth_pages_headless.py; six test files
- implementation/api at origin/main: selahcue_api/graphql/account_schema.py (the server side of the contract), apps/accounts/services.py validators
- npm gates run in an isolated worktree, exit codes captured directly, never piped

## Scope

### In scope

- Update-merge integrity: marketing tree identity across the merge, no marketing changes on origin/main since merge base, account_schema.py byte-identity, context.py scope (admin-only or not)
- Re-verification that LOW-1..LOW-5 remain closed at 9fef5db, including independent mutation probes of at least the attrs/timing/staleness controls
- Session handling in sessionStore.ts: token lifetime, storage, refresh, logout, CSRF bootstrap (CSRF_BOOTSTRAP_TIMEOUT_MS, AbortController lifecycle)
- signupPolicy.ts client-side policy vs server-side validation: the strip/trim divergence and any stale rationale, as a finding on THIS PR if present
- Coverage union of the settled-state headless probe and authViews.test.ts inspection ban: whether a pre-submit leak escapes both
- Anything in the diff the update could have disturbed indirectly (contract drift, dependency drift)

### Non-goals

- Modifying the code under review
- Codex/second-opinion step (waived by owner)
- Merging, approving, or marking the PR ready
- Re-reviewing the api-side auth resolvers beyond contract-shape verification (PR #16's territory)

### Constraints

- No `make ci` (verifies nothing about implementation/marketing; concurrent-session false reds)
- Never pipe a gate whose exit code will be read
- Verify against origin/main by SHA (90b28f7) and head by SHA (9fef5db), not local branch state or the shared working tree
- Negative searches require a positive control
- Mutation probes only in my own scratchpad worktree, restored clean

### Assumptions and unknowns

- ASSUMED: gh CLI is authenticated for First-Pavilion/selahcue (verified via pr view)
- UNKNOWN: whether Node 22 is available locally for the gates; resolve by attempting in scratchpad, else rely on code-level evidence and say so
- UNKNOWN: ClickUp MCP connectivity in this session; if absent, return a structured pending update

## Dependencies and approvals

- gh CLI authenticated — available
- ClickUp MCP — not present in this session's toolset; pending update will be returned

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The update-merge integrity claims verify by SHA: origin/main touched no marketing file since merge base; the merge left the marketing tree byte-identical; account_schema.py byte-identical; context.py change scoped off the customer auth path | git diff/rev-parse/shasum against 607a7b5, 90b28f7, 1f21f41, 9fef5db | All four claims hold or the discrepancy is named | marketing tree object f22a7ed9 identical at 1f21f41 and 9fef5db; diff 607a7b5..origin/main empty under marketing with 131-file positive control; account_schema.py sha256 25247ff1...f03b6 at both ends; context.py +38 = require_reason guard, admin writers only. Nit: 112 commits, not 99 | PASS |
| C-002 | yes | LOW-1..LOW-5 are re-verified closed at 9fef5db by code read, and the load-bearing controls (attrs facet, timing ban, staleness inputs) are independently mutation-probed in an isolated worktree | git show 9fef5db reads + mutation probes with exit codes | Each finding closed; each probed control goes RED under its mutation and restores clean | All five closed by read (contract table in review). Mutation A (bound placeholder, SignInView): npm test EXIT=1 naming the ban, probe 1384 checks 1 FAIL (attrs only). Mutation B (setTimeout in sessionStore.ts): npm test EXIT=1 naming the file. Mutation C (touch package.json): probe refuses, EXIT=2. All restored, worktree clean | PASS |
| C-003 | yes | sessionStore.ts session handling is assessed: storage location, token lifetime handling, refresh, logout, CSRF bootstrap lifecycle | Code read at 9fef5db with server-side cross-check at 90b28f7 | Explicit verdict per property, findings filed where weak | Verdict: sound, no findings. Credential never in JS; hint allowlisted on write AND read (pinned by session.test.ts); expiry fail-dead; rotation-rare refresh with survivable loss; logout refuses to lie; CSRF bootstrap single-flight, own 5s AbortController, bounded from both sides by test; safeNextPath whitelist consumed only by router.replace | PASS |
| C-004 | yes | The settled-state probe + inspection-ban union is assessed: does a pre-submit dynamic leak escape both controls | Code read of auth_pages_headless.py sampling loop and authViews.test.ts ban scope; construct the candidate gap concretely | Explicit verdict: covered or a named gap with severity | Verdict: GAP, Medium (F2). Nine lexical bypass shapes verified against the ban's own regexes with positive controls; end-to-end mutation (/^nobody/.test computed :placeholder in ForgotPasswordView) passed npm test 110/110 EXIT=0 AND probe 1384 checks 0 FAIL EXIT=0 while rendering address-keyed registration copy pre-submit. Remediation: record pre-submit attrs/page in each enumeration pair | PASS |
| C-005 | yes | The strip/trim divergence and stale-rationale questions are answered for THIS diff, signupPolicy.ts in particular | Empirical node/python probe + code read of signupPolicy.ts and server validators at 90b28f7 | Explicit verdict: finding on this PR or demonstrated non-applicable | Verdict: FINDING on this PR, Low (F1): U+001C-U+001F/U+0085 diverge in collapseWhitespace and the wired-in password policy; U+FEFF diverges in reverse; signupPolicy.test.ts pins the false equivalence with intersection-only fixtures. Empirical probes with positive controls. Stale ordering rationale: pre-existing at origin/main (account.ts:83 untouched by this diff), PR #16 territory, filed informational F3. NUL/full_clean gap filed informational F4 (api-side, Django CharField has MaxLengthValidator only, verified) | PASS |
| C-006 | no | The marketing gates run in an isolated worktree at 9fef5db with exit codes captured directly | npm ci / npm run build / npm test / npm run test:states | EXIT=0 x4 or a justified NOT-RUN | NPM_CI_EXIT=0, BUILD_EXIT=0, TEST_EXIT=0 (110/110), STATES_EXIT=0 (49 scenarios, 1384 checks, 0 FAIL) — scratchpad npm_ci.log, gate_build.log, gate_test.log, gate_states.log. PR figures reproduce exactly | PASS |
| C-007 | yes | Findings are posted as PR review comments with a security verdict | gh pr review / gh api | Review visible on PR #17 | https://github.com/First-Pavilion/selahcue/pull/17#pullrequestreview-5059458282 (state COMMENTED, verified via gh api) | PASS |
| C-008 | yes | Verdict and finding count by severity reported to the requester | Final response text | Stated | Final assistant message: verdict Pass, 0 blocker/high, 1 medium, 1 low, 2 informational | PASS |

## Verification plan

- Focused verification: SHA-pinned code reads; scratchpad worktree at 9fef5db for gates and mutation probes; empirical node/python probes for the character-class divergence
- Broader regression verification: the PR's own mutation table cross-checked against the tests as committed
- Independent verifier: requester and the other three reviewers on the same PR
- Required environment: gh CLI; Node for the gates; python3 for divergence probes

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-006
- Hypothesis: the engineer's update-integrity claims hold and the gates reproduce
- Change or investigation: SHA-pinned verification (tree hashes, filtered diffs with positive controls, schema sha256); isolated worktree at 9fef5db; npm ci/build/test/test:states with exit codes captured directly
- Verifier executed: git rev-parse/diff/shasum; four gates
- Result: C-001 PASS (all claims hold; commit count corrected 99 -> 112, immaterial), C-006 PASS (0/0/0/0, figures reproduce)
- New evidence: scratchpad npm_ci.log, gate_build.log, gate_test.log, gate_states.log
- Decision: iterate

### Iteration 2

- Target criterion: C-002, C-003, C-004, C-005
- Hypothesis: prior findings remain closed; the union of probe and ban leaks pre-submit; the strip/trim divergence reaches signupPolicy.ts
- Change or investigation: full SHA-pinned read of the 20-file diff and server-side validators; node/python divergence probes with positive controls; Django validator check via venv-api; mutation battery A (attrs+ban), B (timing), C (staleness), D (union-gap regex-shaped pre-submit placeholder)
- Verifier executed: MUTA npm test EXIT=1 + probe 1 FAIL (attrs); MUTB npm test EXIT=1 naming sessionStore.ts; MUTC probe EXIT=2; MUTD npm test EXIT=0 AND probe 0 FAIL EXIT=0 (gap demonstrated); all restored clean
- Result: C-002/C-003/C-005 PASS; C-004 PASS with finding F2 (Medium); findings F1 (Low), F3/F4 (informational)
- New evidence: scratchpad mutA_test.log, mutA_probe.log, mutB_test.log, mutC_probe.log, mutD_test.log, mutD_build.log, mutD_probe.log
- Decision: iterate

### Iteration 3

- Target criterion: C-007, C-008
- Hypothesis: posting the consolidated review with four findings and the verdict completes the deliverable
- Change or investigation: posted review 5059458282 (verdict Pass, 0 blocking; 1 medium, 1 low, 2 informational; remediation outcomes stated per finding)
- Verifier executed: gh api repos/First-Pavilion/selahcue/pulls/17/reviews (state COMMENTED, id returned)
- Result: C-007 PASS; C-008 PASS via final report to requester
- New evidence: https://github.com/First-Pavilion/selahcue/pull/17#pullrequestreview-5059458282
- Decision: complete

## Risks and rollback

- Risk: review comments name exploit preconditions on a private repo PR — acceptable audience (team-only)
- Risk: mutation probes in a worktree sharing the npm cache — mitigated by isolated node_modules per worktree
- Rollback: none required; review is additive commentary; worktree removed at the end
