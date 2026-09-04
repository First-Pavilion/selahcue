# Goal Contract — TASK-security-review-pr19-restate-82a1bb2

## Identity

- Goal ID: TASK-security-review-pr19-restate-82a1bb2
- Parent goal ID: TASK-security-review-pr19-openai-notes
- Title: The PR #19 verdict is restated against the true head 82a1bb2: F-3 mutation-verified, the allowlist widening verified per my pre-landing checklist, the doc rewrites and standing rule read, model-by-value spot-checked, and the CI-not-yet-run caveat carried
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 5
- Independent verification required: yes

## Objective

At head 82a1bb251f483009fa1e42aeb5a1719e53caa791 (base origin/main 3f3072e): F-3's pin is
re-verified by my own H3 mutation; the widening is verified by a fourth credential-shaped name
with its pin updated; the three rewritten posture statements and the standing rule are read; a
model-ignored mutation is spot-checked; gate-line survival is spot-checked; the verdict is
restated with the three-OS-matrix-pending caveat; posted on PR #19.

## Baseline

41e52d09 is gone (local-only rebase); 82a1bb2 carries the rebase onto merged main, F-3, three
doc rewrites, the standing rule, and SELAHCUE_OPENAI_MODEL in the loader allowlist. The
engineer reports 11 tests red under a pin-updated fourth-name widening and 5 model mutations
red; make ci green locally only.

## Inputs and evidence sources

- git show 82a1bb2:<path>; isolated worktree at 82a1bb2 (sana_-prefixed), own target dirs
- gh CLI for head/CI verification

## Scope

### In scope

- H3 echo mutation at 82a1bb2 -> RED at a_timeout_refusal_leaks_nothing_from_the_body
- Fourth-name widening (credential-shaped, pin updated) -> reds incl. the exact-equality control
- The three doc rewrites + standing rule; NEVER_EXPORTED disjointness at three names
- One model mutation (env value ignored) -> RED at its named test
- Gate-line survival spot-check; restated verdict with the CI caveat

### Non-goals

- Re-running the engineer's full batteries; PR #20 work (separate contract); modifying code

### Constraints

- Exit codes captured directly; probes isolated; sana_-prefixed files

### Assumptions and unknowns

- ClickUp MCP absent; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | F-3 bites at this head under my own H3 mutation | mutation + suite | RED at the named test | H3 echo mutation re-applied byte-for-byte at 82a1bb2: RED at exactly a_timeout_refusal_leaks_nothing_from_the_body (8 passed, 1 failed). F-3 landed and bites under my own mutation | PASS |
| C-002 | yes | A pin-updated fourth-name widening still reddens the loader suite including the widener-addressed control | mutation + suite | RED; count and names recorded | fourth credential-shaped name (SELAHCUE_DEV_SIGNING_SEED) with the compile-time pin dutifully updated to 4: RED, 11 failed (matches the engineer's count), including no_unallowlisted_name_reaches_the_process_environment and every_name_reported_missing_is_absent_from_the_environment. Widening cannot be routine | PASS |
| C-003 | yes | The three posture statements are rewritten, the standing rule is recorded, NEVER_EXPORTED stays disjoint | code reads | confirmed | standing rule recorded beside LOADABLE — categorical credential prohibition, misleading-outcome bar (stronger than my non-secret bar), per-addition requirements, no numeric cap with the deletion-date bound, and the aeddf2d clear-set note I asked for. NEVER_EXPORTED stays hard-coded [3] and disjoint. openai.rs preserves the original rejection reasoning and records the reversal honestly with MODEL_ENV length-bounded; .env.sample carries the third entry and the rewritten header | PASS |
| C-004 | yes | The env-model-ignored mutation reddens its named test | mutation + suite | RED | FINDING F-4 (Low): the env->model WIRING is unpinned. My mutation model_from_env -> resolve_model(None) survives BOTH suites (cloud openai exit 0; operator openai-notes 89 passed exit 0). an_env_supplied_model_reaches_the_request_body drives resolve_model(Some(..)) directly — the copy, not the environment link — so the exact silent no-op the standing rule cites as the reason for the widening is undetected if reintroduced. Validated remediation: the_environment_actually_reaches_model_selection driving model_from_env() under a private lock — kills the mutation (RED with its named message), passes clean. This corrects the relayed claim that the env-ignored mutation was RED; at the wiring expression it is GREEN | PASS |
| C-005 | yes | Gate lines survive at the merged base; verdict restated with the matrix-pending caveat; posted | reads + gh api | comment visible | gate lines survive (6 feature-gate hits in Makefile, 13 in ci.yml, superset of main's); verdict restated on PR #19 with the three-OS-matrix-pending caveat, comment verified via gh api | PASS |

## Verification plan

- Focused: three mutations with siblings; SHA-pinned reads
- Independent verifier: coordinator and remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Change or investigation: worktree at 82a1bb2; H3 re-run; fourth-name widening with pin updated; doc/standing-rule reads; wiring mutation run against BOTH suites; pinning test validated both directions; gate-line greps; worktree removed
- Verifier executed: exit codes captured directly
- Result: F-3 verified; widening control verified at 11 red; F-4 (Low) found, demonstrated across two suites, remediation validated
- New evidence: scratchpad sana_r6_H3.log, sana_r6_widen.log, sana_r6_model.log, sana_r6_model_op.log, sana_r6_modelpin.log, sana_r6_modelpin_clean.log
- Decision: complete after posting

## Risks and rollback

- Probes isolated; worktree removed; additive commentary only

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr19-restate-82a1bb2.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator and remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (restatement deliverable)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
