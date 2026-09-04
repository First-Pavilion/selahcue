# Goal Contract — TASK-security-review-pr19-retest-sweep

## Identity

- Goal ID: TASK-security-review-pr19-retest-sweep
- Parent goal ID: TASK-security-review-pr19-openai-notes
- Title: PR #19 head 8492c90 is re-tested: the F-1 sweep is verified to kill both surviving echo arms, its positive control is checked for bite, the read_capped no-echo and boundary tests are mutation-verified, the split constants' ordering is confirmed in effect, and the verdict posted
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

At head 8492c90e6acbfce439b797a7b7d31866f800061a: my E1/E1b mutations are re-run and both go RED
via the landed sweep; the sweep's non-empty-message positive control is tested for whether it can
fail at all, and the fixture-drift vacuity route is assessed; the read_capped refusal no-echo and
at-cap boundary are mutation-verified through the new ungated tests; the socket-before-parse
ordering is confirmed in effect and at compile time; containment is re-confirmed for the delta;
findings posted on PR #19.

## Baseline

Round 1 complete at ea5ba05 (review 5112035744): verdict clear with conditions, F-1 the one
finding. 8492c90 lands the sweep as specified plus Cody's six residuals: read_capped extraction
with ungated tests, constant split with compile-time ordering pin, SENTINEL_MODEL. My two
follow-ups are ticketed outside this diff. CI state to be confirmed at head.

## Inputs and evidence sources

- git show 8492c90:<path>; diff ea5ba05..8492c90
- Isolated scratchpad worktree at 8492c90, own CARGO_TARGET_DIR, restored clean and removed
- gh CLI for CI evidence

## Scope

### In scope

- E1/E1b re-run; sweep positive-control bite probe (empty-message mutation); fixture-marker
  premise assessment
- read_capped: refusal-echo mutation; read-exactly-cap mutation; test file confirmed ungated
- Constant split ordering in effect (read_bounded then parse_draft) and at compile time
- Delta containment: ci.yml/main.rs changes carry no new egress or feature route

### Non-goals

- Re-reviewing settled round-1 territory; the ticketed follow-ups; modifying code; merging

### Constraints

- Exit codes captured directly; probes only in the isolated worktree; SHA-pinned reads

### Assumptions and unknowns

- ClickUp MCP absent; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Baseline green (openai + default feature states) with sweep and transport tests present | cargo test both states | exit 0; test names in output | openai state exit 0 (31 tests incl. the sweep); default state exit 0 with the transport tests present — a_refusal_leaks_nothing_from_the_body runs UNGATED in the default build as claimed | PASS |
| C-002 | yes | E1 and E1b both RED via the sweep | re-applied mutations | two REDs naming the sweep | E1 (default-arm echo) RED at exactly no_status_arm_anywhere_in_the_mapping_echoes_the_response_body; E1b (5xx echo) RED at the same test. Both formerly-surviving arms now die. F-1 closed | PASS |
| C-003 | yes | The sweep's positive control is assessed for bite: can any mutation make it fail; the fixture-drift route named if unpinned | empty-message mutation + analysis | explicit verdict with evidence | verdict: the non-empty-message positive control CANNOT fail — NoteError's Display always prefixes text, and the EMPTY mutation (other arm returns Malformed(String::new())) passed the whole suite exit 0. The genuine vacuity route is fixture drift, demonstrated live: stripping the key fragment and provider URL from ERR_401_INVALID_KEY left all 31 tests green while every absence assertion exercised nothing. Finding F-2 (Low) with a fixture-premise remediation that dies under exactly that mutation | PASS |
| C-004 | yes | read_capped refusal-echo mutation RED at the named test; read-exactly-cap mutation RED; file ungated | mutations + read | two REDs; no cfg gate on the file | refusal-echo mutation RED at exactly a_refusal_leaks_nothing_from_the_body (default build); read-exactly-cap mutation RED at one_byte_over_the_cap_is_refused (+ the refusal test); test_transport.rs carries no crate-level cfg gate and its tests appear in the default run | PASS |
| C-005 | yes | Socket cap precedes parse cap in effect; compile-time pin present | code read | confirmed | in effect: read_bounded caps the socket read at MAX_TRANSPORT_RESPONSE_BYTES (4 MB) before parse_draft refuses above MAX_PARSED_RESPONSE_BYTES (512 KB) pre-serde; compile-time ordering pin present in test_transport.rs (openai-gated, where the parse cap is visible) | PASS |
| C-006 | yes | Delta containment: no new egress/feature route in ci.yml or main.rs changes | diff read | confirmed or named | ci.yml delta splits the combined clippy+test step into two (masking-prevention); main.rs delta introduces Direct/Hosted newtypes making the notes_status argument swap unrepresentable; no new egress or feature route; CI completed success at head | PASS |
| C-007 | yes | Verdict posted on PR #19 and reported | gh api | comment visible; report stated | re-test comment posted on PR #19, verified via gh api; verdict reported to coordinator | PASS |

## Verification plan

- Focused: mutations with siblings, never --exact; both feature states where relevant
- Independent verifier: coordinator and remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006
- Change or investigation: worktree at 8492c90, cached target dir; baselines both feature states; six mutations (E1, E1b, EMPTY, REFUSAL_ECHO, EXACT_CAP, DRIFT), each restored clean; delta reads of ci.yml/main.rs/transport/openai; CI polled to completion
- Verifier executed: exit codes captured directly
- Result: F-1 verified closed; landed transport controls bite; F-2 (Low) found and demonstrated both ways (control cannot fail; drift undetected)
- New evidence: scratchpad r3_p19_*.log
- Decision: iterate

### Iteration 2

- Target criterion: C-007
- Change or investigation: posted the re-test comment; reported to the coordinator
- Result: PASS
- Decision: complete

## Risks and rollback

- Probes isolated; worktree removed; review is additive commentary

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr19-retest-sweep.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator and remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (re-test deliverable)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
