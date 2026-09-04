# Goal Contract — TASK-security-review-pr16-remediation-confirm

## Identity

- Goal ID: TASK-security-review-pr16-remediation-confirm
- Parent goal ID: TASK-security-review-pr16-reset-order
- Title: PR #16 remediation at head 340601b is independently confirmed: the two corrected claims are verified true as written, and the reviewer's position on the follow-up-ticket precondition and the Finding 1 risk acceptance is stated precisely
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5p9aq (MCP unavailable this session — pending update to be returned)
- Created: 2026-08-30
- Updated: 2026-08-30
- Maximum iterations: 4
- Independent verification required: yes

## Objective

Confirm on PR #16 (head 340601b, base origin/main 90b28f7, 0 behind) that the round-2 rewording is true as written: (1) "the bounds are equal but the rules are not equivalent" and (2) "PASSWORD_INVALID is reachable from this client, and harmless because no security property rests on client pre-validation" — and deliver two precise position statements: whether the marketing follow-up precondition means ticket-exists or work-done before merge, and a one-paragraph risk-acceptance ask for Finding 1.

## Baseline

Round-1 review posted at 692c7ab (verdict Pass, 2 Low + 2 Informational). Head moved to 340601b: services.py comment-only changes in the reviewed region, responses.py adds PASSWORD_INVALID:400 to the /v1 status map, two test files extended. PR body rewritten with the two corrected claims. ClickUp MCP has no tools in any session today.

## Inputs and evidence sources

- git show 340601b:<path> and git show 90b28f7:<path> — never the shared working tree
- gh pr view 16 (body, state, headRefOid)
- Empirical node/python3 probes of the strip/trim divergence in the scratchpad
- Round-1 goal contract TASK-security-review-pr16-reset-order.md (COMPLETE)

## Scope

### In scope

- Truth of the two corrected claims as now written (PR body at 340601b)
- Interdiff 692c7ab..340601b for anything that alters the round-1 security verdict
- The responses.py PASSWORD_INVALID:400 row (new surface since round 1)
- The two position statements

### Non-goals

- Modifying the code under review
- Codex/second-opinion step (waived by owner)
- Resolving threads, marking ready, merging
- Re-running the full mutation table (engineer + two reviewers reproduced it; existence and shape checked, not re-executed)

### Constraints

- No make ci; verify against origin/main by SHA (90b28f7); capture exit codes directly, never piped
- Ports 6379, 55432/56379, 55442/56389, 55452/56399, 55472/56419 are in use by other sessions
- Negative searches require a positive control

### Assumptions and unknowns

- ASSUMED: gh CLI authenticated (verified via pr view)
- Verified: ClickUp MCP unavailable (no MCP tools in this session)

## Dependencies and approvals

- gh CLI — available
- ClickUp MCP — unavailable; structured pending update returned instead

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| R-001 | yes | Head/base/behind state matches the tasking (340601b, base 90b28f7, 0 behind, Draft) | gh pr view + git rev-list/merge-base | Exact match | gh pr view: head 340601b, Draft, base main; merge-base(340601b,90b28f7)=90b28f7; rev-list --count 340601b..90b28f7 = 0 | PASS |
| R-002 | yes | The interdiff 692c7ab..340601b introduces nothing that changes the round-1 verdict; the confirm-path code is semantically unchanged | git diff by SHA + code read of new surfaces (responses.py row, new tests) | Comment/test-only in the reviewed region; new row assessed | diff 692c7ab..340601b: services.py two comment-only hunks (raise site 1245 + order unchanged); responses.py PASSWORD_INVALID:400 inert today (single raise site, enumerated) and pinned total by test_foundation_contract.py:418; tests additive, round-1 mutation-F catcher still present (line 914) | PASS |
| R-003 | yes | Corrected claim 1 is true as written: bounds equal (10/200 both sides), rules not equivalent (strip/trim divergence), upper bound now tested | Code read at 340601b and 90b28f7 + empirical node/python3 probe + test existence | Claim wording matches evidence | Bounds: settings.py:309 default 10, services.py:232 MAX=200 vs passwordPolicy.ts 10/200 at 90b28f7. Probes: U+001C-001F,U+0085 py-strips/js-keeps (U+0020 positive control); U+FEFF js-trims/py-keeps (reverse direction, client-stricter). Upper-bound test exists at line 705 with at-limit positive control | PASS |
| R-004 | yes | Corrected claim 2 is true as written: PASSWORD_INVALID reachable from the client; no security property rests on client pre-validation; fallback copy truthful | Code trace at 340601b (raise sites, transaction, consume order) + client read at 90b28f7 | Claim wording matches evidence, incl. the word "identical" scrutinised | Reachable: passes all client gates; F2 has_control_characters call sites never cover accounts; server fails not-strip() behind live token pre-consume -> PASSWORD_INVALID, consumed_at None. Harmless: collapse+policy server-side only; PASSWORD_INVALID->UNKNOWN->serverError, banner truthful. One editorial residue: "identical rule" contradicts "not equivalent"; load-bearing word "authoritatively" is true | PASS |
| R-005 | yes | Position stated: ticket-exists vs work-done precondition, with the ClickUp-unavailable consequence surfaced | Final response text | Unambiguous statement | Final response: ticket-must-exist (not work-done); blocked on ClickUp tooling; owner-actionable pending update supplied | PASS |
| R-006 | yes | Finding 1 risk-acceptance ask stated in one owner-actionable paragraph | Final response text | Names what is accepted, by whom, and the alternative | Final response: one-paragraph acceptance ask naming the probe, the measured absence of throttling, the paper-trail gap, and the revert alternative | PASS |
| R-007 | yes | Confirmation recorded on the PR (comment; no thread resolution, no ready, no merge) and reported to the requester | gh + final response | Comment visible on PR #16 | https://github.com/First-Pavilion/selahcue/pull/16#issuecomment-5465728973 (no threads resolved, not marked ready, not merged) | PASS |

## Verification plan

- SHA-pinned code reads; two-line empirical probes for the divergence primitive; gh for PR state
- Independent verifier: the requester acting on the report
- Required environment: gh CLI, node, python3

## Iteration ledger

### Iteration 1

- Target criterion: R-001..R-004
- Hypothesis: the interdiff is comment/test-only in the reviewed region and both corrected claims are true as written
- Change or investigation: SHA-pinned reads (340601b, 90b28f7, interdiff 692c7ab..340601b), node/python3 divergence probes with positive controls, F2 guard call-site enumeration, client flow trace (passwordPolicy.ts, graphql.ts, ResetView.vue)
- Verifier executed: git diff/show by SHA; gh pr view; probes (transcript in session); grep enumerations with positive controls
- Result: R-001..R-004 PASS; one editorial residue noted ("identical rule"), not a finding; verdict unchanged
- New evidence: recorded in predicate rows
- Decision: iterate (post confirmation, deliver position statements)

## Risks and rollback

- Risk: none — read-only review plus one additive PR comment
- Rollback: not required

### Iteration 2

- Target criterion: R-005..R-007
- Hypothesis: posting the confirmation and delivering the two position statements completes the goal
- Change or investigation: posted issue comment 5465728973 on PR #16; position statements delivered in the final response
- Verifier executed: gh pr comment (URL returned); validator --completion
- Result: R-005..R-007 PASS
- New evidence: comment URL above
- Decision: complete
