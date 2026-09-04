# Goal Contract — TASK-security-review-pr16-reset-order

## Identity

- Goal ID: TASK-security-review-pr16-reset-order
- Parent goal ID: NONE
- Title: PR #16 (fix/86ak5p9aq-reset-token-before-password) is security-reviewed with findings posted on the PR and a verdict reported to the requester
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5p9aq
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every attacker-relevant property of PR #16's diff (head 692c7ab, base origin/main 90b28f7) is assessed with code-level evidence — the token-enumeration oracle closure on all paths including timing, the signup-path collapsed code, the marketing-client residuals, and the 112-commit rebase against DEC-013 — findings are posted as PR review comments, and a security verdict is issued.

## Baseline

PR #16 is an open Draft against main reordering `confirm_password_reset` so the reset token is fully validated (empty check, fingerprint lookup, `compare_digest`, purpose/consumed/expired) before `_validate_password` runs, and introducing a distinct `PASSWORD_INVALID` error code visible only to live-token holders. Prior order was an enumeration oracle (FR-551). No security review has been posted yet. Second-opinion step waived by the owner for this session.

## Inputs and evidence sources

- Repository at /Users/m.oluwole/Documents/code/scph (read-only against the reviewed branch; scratch work in the session scratchpad)
- `git diff 90b28f7..692c7ab` and `git show 692c7ab:<path>` / `git show 90b28f7:<path>` — never the shared working tree
- PR #16 description and files (gh)
- implementation/api: apps/accounts/services.py, graphql/errors.py, graphql (mutation layer), tests/test_customer_auth_slice.py
- implementation/marketing at origin/main: src/lib/auth/passwordPolicy.ts, src/lib/api/graphql.ts, src/views (ResetView)
- Django test suite run in an isolated worktree if environment permits; exit codes captured directly, never piped

## Scope

### In scope

- Indistinguishability of all dead-token error returns under attacker-varied token x password (error code, message, extensions, and timing)
- The live-token-only reachability of PASSWORD_INVALID and whether it leaks anything new
- Signup path's bare `_validate_password` call and signup's own enumeration surface
- Marketing client residuals: stale passwordPolicy.ts rationale and SERVER_ERROR_CODES missing PASSWORD_INVALID — security-relevant or copy-only
- Rebase soundness: no inherited assumption from the pre-DEC-013 credential-token mint

### Non-goals

- Modifying the code under review
- Codex/second-opinion step (waived by owner)
- Merging, approving, or marking the PR ready
- Re-reviewing pre-existing surfaces except where adjacent to the diff

### Constraints

- No `make ci` (verifies nothing about implementation/api; concurrent-session false reds)
- Never pipe a gate whose exit code will be read
- Verify against origin/main by SHA (90b28f7), not local branch state or the shared working tree
- Negative searches require a positive control

### Assumptions and unknowns

- ASSUMED: gh CLI is authenticated for First-Pavilion/selahcue (verified via pr view)
- UNKNOWN: whether a local Python/Postgres environment can reproduce the api job; resolve by attempting in scratchpad, else rely on code-level evidence and say so
- UNKNOWN: ClickUp MCP connectivity in this session; if absent, return a structured pending update

## Dependencies and approvals

- gh CLI authenticated — available
- ClickUp MCP — to be probed; pending update returned if unavailable

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every error return reachable by varying token and password independently is enumerated and dead-token cases are indistinguishable in code, message, and extensions | Code trace of confirm_password_reset at 692c7ab + errors.py + the GraphQL error surface | No response-content channel distinguishes unknown/consumed/expired/wrong-purpose, with or without a weak password | services.py:1185-1233 (5 raise sites: 4 collapsed, 1 PASSWORD_INVALID behind live token); views.py process_result rewrites all errors via safe_graphql_error (message+code only, no locations/path); non-null schema fields reject pre-resolver, uncoded, collapsing identically | PASS |
| C-002 | yes | The timing channel is assessed: work skipped/performed per path, and an explicit exploitability verdict | Code trace of per-path work (DB lookup, compare_digest, _validate_password cost) | Explicit verdict: exploitable or theoretical, with reasoning | Dead paths never read the password (no new channel); residual dead-but-real vs never-existed = row-hit+join+lock vs miss, micro-scale, PRE-EXISTING, theoretical at 2^256 token space. New non-destructive liveness probe via weak password reported as Low accepted-by-design | PASS |
| C-003 | yes | The signup path's collapsed VALIDATION_FAILED is confirmed correct and signup's email-enumeration surface is assessed | Code read of signup flow at 692c7ab | Explicit verdict recorded | services.py:634 bare call correct: password checked before the email-existence branch, identically on both branches; uniform accepted:true unchanged; make_password runs pre-branch so no timing skew; fail-safe default keeps future callers collapsed | PASS |
| C-004 | yes | The marketing-client residuals are tested: does any security property depend on client pre-validation, and is the missing allowlist entry security-relevant | Code read of passwordPolicy.ts, graphql.ts, ResetView at origin/main; server-side trace of what a non-client attacker gets | Explicit verdict: security-relevant or copy-only | Copy-only: server enforces the identical rule authoritatively. BUT "unreachable from our client" is false: U+001C x12 passes JS validators (trim keeps it, 12 code points) and fails Python strip -> PASSWORD_INVALID -> UNKNOWN -> R7 misattributed copy. Verified empirically (python3/node). Reported Low, follow-up ticket recommended | PASS |
| C-005 | yes | The rebase inherited no assumption from the pre-DEC-013 mint | Diff of services.py merge-base vs 90b28f7 vs 692c7ab; trace of what confirm_password_reset consumes from the mint | Explicit verdict with evidence | base->head diff contains exactly the intended change; confirm path resolves by token_fingerprint + compare_digest at BOTH SHAs and never reads token_hash or calls check_password (only check_password sites are login's, lines 988-997); DEC-013 does not interact | PASS |
| C-006 | no | The api test suite runs locally with exit codes captured directly | pytest in isolated checkout of 692c7ab, exit code captured | EXIT=0 or a justified NOT-RUN with code-level fallback | scratchpad worktree at 692c7ab, uv venv py3.14: test_customer_auth_slice.py 35 passed, PYTEST_EXIT=0 (pytest_auth_slice.log); mutation F reproduced 1 failed/34 passed (pytest_mutF.log); mutation A reproduced 2 failed/33 passed (pytest_mutA.log); worktree restored clean | PASS |
| C-007 | yes | Findings are posted as PR review comments with a security verdict | gh pr review / gh api | Review visible on PR #16 | https://github.com/First-Pavilion/selahcue/pull/16#pullrequestreview-5059404760 (state COMMENTED, verified via gh api) | PASS |
| C-008 | yes | Verdict and finding count by severity reported to the requester | Final response text | Stated | Final assistant message: verdict Pass, 0 blocker/high/medium, 2 low, 2 informational | PASS |

## Verification plan

- Focused verification: SHA-pinned code reads; scratch empirical probes where behaviour is disputable; optional local pytest run of the auth slice
- Broader regression verification: the PR's own mutation table cross-checked against the tests as committed
- Independent verifier: requester and the other three reviewers on the same PR
- Required environment: gh CLI; optional Python 3.14 + Postgres via scratchpad

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006
- Hypothesis: the reorder closes the response-content oracle; timing remains as a channel but pre-existing and likely theoretical; residuals are copy-only
- Change or investigation: full SHA-pinned read of the diff and surrounding flows (confirm/verify/signup/request/mint, errors.py, views.py, account_schema.py, throttling guards); marketing client read at 90b28f7; empirical python3/node probe of the strip/trim divergence; isolated worktree at 692c7ab with uv venv py3.14
- Verifier executed: pytest tests/test_customer_auth_slice.py (EXIT=0, 35 passed); mutation F applied/run/restored (EXIT=1, exactly test_a_dead_but_real_token_with_a_weak_password_stays_collapsed failed); mutation A applied/run/restored (EXIT=1, the two dead-token tests failed)
- Result: C-001..C-006 PASS; findings: 2 Low (sanctioned non-destructive liveness probe needs explicit risk acceptance; client-reachability premise false via U+001C but copy-only), 2 Informational (pre-existing micro-timing residue; stale in-file catch-map counts)
- New evidence: scratchpad pytest_auth_slice.log, pytest_mutF.log, pytest_mutA.log; services_head.py/services_base.py extracts
- Decision: iterate (post review -> C-007, C-008)

### Iteration 2

- Target criterion: C-007, C-008
- Hypothesis: posting the consolidated review with the four findings and the verdict completes the deliverable
- Change or investigation: posted review 5059404760 (verdict Pass, 0 blocking, 2 low + 2 informational, with the accepted-risk callout on the non-destructive liveness probe routed to the risk owner)
- Verifier executed: gh api repos/First-Pavilion/selahcue/pulls/16/reviews (state COMMENTED, id returned)
- Result: C-007 PASS; C-008 PASS via final report to requester
- New evidence: https://github.com/First-Pavilion/selahcue/pull/16#pullrequestreview-5059404760
- Decision: complete

## Risks and rollback

- Risk: review comments name exploit preconditions on a private repo PR — acceptable audience (team-only)
- Rollback: none required; review is additive commentary
