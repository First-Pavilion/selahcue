# Goal Contract — TASK-security-review-pr19-drip-fix

## Identity

- Goal ID: TASK-security-review-pr19-drip-fix
- Parent goal ID: TASK-security-review-pr19-openai-notes
- Title: PR #19 head 41e52d09 is re-reviewed after my round-4 conclusion was falsified: the drip fix is verified with complement-of-the-probe discipline, the new deadline error branch is checked for echo pinning, the round-4 verdict is restated, and findings posted
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

At head 41e52d098fe69ae7e84a1f5ef781a682cb68d450: the drip hole Vera demonstrated is confirmed
closed by the loop-owned deadline; the hang-not-pass property of the drip test is confirmed under
mutation; the usize::MAX overflow fix is spot-checked; the NEW deadline error branch is probed for
whether an echo added to it would survive the suite (the complement of round-2's per-arm lesson,
applied to the branch this fix introduces); the wire-cost entity control is understood; my
round-4 "no open security conditions" statement is explicitly retracted and restated against this
head; findings posted on PR #19.

## Baseline

Round 4 concluded the client deadline covered the manual read. FALSIFIED by Vera: reqwest's
blocking Read applies the timeout per read-wait, so a dripping peer resets it indefinitely
(172s past a 60s deadline measured; pre-PR text() cut at 30.0s). My probe and the engineer's
both tested the silent-stall region only — the fix and its verification shared the assumption
that a stalling peer stops sending. 41e52d09: read_capped takes Option<Instant> deadline checked
before every read and after every chunk; saturating_add fixes the +1 overflow at usize::MAX;
deterministic offline drip tests; an entity control on bytes pulled off the wire.

## Inputs and evidence sources

- git show 41e52d09:<path>; diff 9845bba..41e52d09
- Isolated scratchpad worktree at 41e52d09 (sana_-prefixed), own CARGO_TARGET_DIR
- gh CLI for CI evidence

## Scope

### In scope

- Baselines both feature states; the four landed transport controls read and understood
- Mutation H1: remove both deadline checks -> the drip test must hang, not pass (bounded by a
  kill-after-N harness; a hang is the RED)
- Mutation H2: saturating_add reverted to +1 -> expect RED (debug panic) in the drip test
- Mutation H3 (the complement lesson applied): add a body-content echo to the NEW timeout error
  branch -> record whether any test fails; if none, validate a marker-dripping pinning test that
  kills H3 and file the finding
- read_bounded's two-phase worst case (head 60s + body 60s) assessed and stated
- main.rs delta read for security relevance; CI at head
- Explicit retraction and restatement of the round-4 verdict

### Non-goals

- Re-litigating settled rounds beyond the falsified claim; modifying code; merging

### Constraints

- Exit codes captured directly; probes isolated; sana_-prefixed scratch files; SHA-pinned reads
- Mutations that can hang run under a kill-after-N wrapper, never bare

### Assumptions and unknowns

- ClickUp MCP absent; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Baselines green in both feature states; drip and wire-cost tests present and passing | cargo test both states | exit 0; names in output | default and openai states both exit 0; a_peer_that_drips_bytes_forever_is_cut_off_at_the_deadline, the_cap_bounds_what_is_read_off_the_wire_not_merely_what_is_returned and the_cap_still_bites_while_a_deadline_is_live all present and ok in the DEFAULT build | PASS |
| C-002 | yes | Removing the deadline checks makes the drip test hang rather than pass | mutation H1 under kill-after-N | no completion within N; killed; restored green | H1 (both deadline checks removed): cargo test on test_transport still running at 90s under the kill harness — RED-by-hang exactly as claimed; killed, no strays, restored green. Nuance noted: a hang is a red only where a runner enforces a timeout; CI job timeouts do | PASS |
| C-003 | yes | The +1 overflow fix bites: reverting saturating_add reddens the drip test | mutation H2 | RED (panic) at the named test | H2 (saturating_add reverted to +1): RED, panic 'attempt to add with overflow' at transport.rs:146 in exactly the drip test — the overflow claim reproduces | PASS |
| C-004 | yes | The new timeout error branch is probed for echo pinning; gap filed with a validated test if unpinned | mutation H3 (+ pinning-test validation if H3 survives) | explicit verdict with evidence | H3 (body-prefix echo added to both timeout branches): SURVIVED the full openai-state suite, exit 0, zero failures — the new deadline error branch is unpinned against echo, the third instance of the F-1 lesson, now on the branch this fix introduced. Validated remediation: a_timeout_refusal_leaks_nothing_from_the_body with a marker-dripping reader and a live-short deadline (so content accumulates before expiry — an expired deadline fires on an empty buffer and proves nothing); it kills H3 (RED showing the echoed marker) and passes on clean code. Finding F-3 (Low) | PASS |
| C-005 | yes | The two-phase worst case is stated; main.rs delta carries no new security surface; CI green at head | code read + gh | stated; confirmed | two-phase worst case stated plainly in read_bounded (~60s head + 60s body budget = up to ~120s, honest and bounded); main.rs delta is a testability split (direct_provider_from_key takes the value, no env mutation in tests) with no new security surface; CI completed success at head | PASS |
| C-006 | yes | Round-4 verdict explicitly retracted and restated at 41e52d09; comment posted and reported | gh api + final response | comment visible; restatement present | round-4 statement 'the R2 bound did not relocate the gap' explicitly retracted in the PR comment — my probe measured the silent-stall region and I generalised beyond it; the fix and both verifications shared the assumption that a stalling peer stops sending. Verdict restated at 41e52d09. Comment posted and verified via gh api | PASS |

## Verification plan

- Focused: the three mutations with siblings; the hang mutation under a bounded wrapper
- Independent verifier: coordinator, Vera's measurements, remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Change or investigation: worktree at 41e52d09; baselines; H1 under a 90s kill harness (hang confirmed); H2 (overflow panic confirmed); H3 (echo survived — gap) then the pinning test validated both directions (kills H3, passes clean); main.rs delta read; CI polled to completion
- Verifier executed: exit codes captured directly; hang bounded by an explicit kill, never bare
- Result: fix verified closed for the drip shape; F-3 (Low) found and remediation validated
- New evidence: scratchpad sana_r5_base_*.log, sana_r5_H1.log, sana_r5_H2.log, sana_r5_H3.log, sana_r5_H3pin.log, sana_r5_H3pin_clean.log
- Decision: iterate

### Iteration 2

- Target criterion: C-006
- Change or investigation: posted the comment with the explicit retraction and the restated verdict; reported to the coordinator
- Result: PASS
- Decision: complete

## Risks and rollback

- H1 can hang a cargo test process: run backgrounded with an explicit kill; never in the shared
  checkout; worktree removed at the end

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr19-drip-fix.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator, Vera's measurements, remaining reviewers
- Terminal state: VERIFIED_COMPLETE (re-review deliverable)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
