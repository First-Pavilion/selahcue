# Goal Contract — TASK-security-review-pr19-timeouts

## Identity

- Goal ID: TASK-security-review-pr19-timeouts
- Parent goal ID: TASK-security-review-pr19-openai-notes
- Title: PR #19 head 9845bba is re-tested: the deadline is verified to cover the hand-rolled bounded body read, the new constants are checked for echo-free error paths, the landed F-2 controls are mutation-verified, the description incident is cleared, and the verdict posted
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

At head 9845bba55a5028ba3be190f6e4fbdcf96f73152d: the client deadline is empirically shown to
cover read_capped's manual Read::take/read_to_end path (a loopback stall server, not reasoning
from docs); the deadline and connect-timeout error paths are shown to echo no response content
(marker probe); the landed fixture premise and replacement control are mutation-verified to
redden; the restored PR description is re-read and my prior conclusions checked for any
description-derived dependency; findings posted on PR #19.

## Baseline

Round 2 complete at 8492c90 (comment 5539646876): F-1 verified closed; F-2 (Low) named. Head
adds f1c648c (F-2 premise verbatim + a replacement control) and 9845bba (connect_timeout 10s
new, request timeout 30s->60s, both http-gated consts; the engineer measured unreachable 10.0s,
accept-silence 60.0s, headers-then-stall 60.0s). Incident: the PR description was temporarily
another lane's body; my round-1 copy predates or missed the corruption and findings were
diff-derived, to be confirmed.

## Inputs and evidence sources

- git show 9845bba:<path>; diff 8492c90..9845bba; my saved round-1 description copy
- Isolated scratchpad worktree at 9845bba (sana_-prefixed files), own CARGO_TARGET_DIR
- gh CLI for CI evidence

## Scope

### In scope

- Loopback stall probe through the real read_capped with a short-deadline client of the same
  builder shape; marker in the stalled body asserted absent from the error
- Constants read at head (10/60, http-gated); no new error branch in our code confirmed by diff
- Mutation A: strip fixture markers -> expect RED at the landed premise
- Mutation B: gut the other arm to Malformed(String::new()) -> expect RED at the new 418 control
- Description-incident clearance: diff my saved copy against the restored body; name any
  conclusion that depended on the description rather than the diff
- Delta containment

### Non-goals

- Re-reviewing settled territory; judging the 30s->60s product trade (coordinator-owned, noted);
  modifying code; merging

### Constraints

- Exit codes captured directly; probes only in the isolated worktree; scratch files prefixed
  sana_; SHA-pinned reads

### Assumptions and unknowns

- UNKNOWN: whether reqwest compiles offline from cache for the http-feature probe; fall back to
  the engineer's measurements plus code reasoning, stated as such, if not
- ClickUp MCP absent; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The deadline covers the manual body read: a loopback peer sending headers+partial body then stalling produces an error at the client deadline, not a hang | temp http-gated probe test through read_capped | error within deadline+margin; elapsed recorded | loopback stall probe (headers + partial body + 20s hold) through the real read_capped with a same-shape short-deadline client (connect 1s / total 3s): error fired inside the asserted 2-10s window around the 3s deadline, not at the stall — the client deadline covers the manual Read::take/read_to_end path. Mechanism verified empirically; shipped constants (10/60) pinned in the probe and read at head. Consistent with the engineer's 60.0s measurements | PASS |
| C-002 | yes | Neither timeout error path echoes response content | marker in the stalled partial body; error string checked | marker absent from rendered error | the stalled partial body verifiably carried the marker (positive control: the server wrote it before stalling) and the rendered deadline error contained neither the marker nor sk-proj-; the connect-timeout path has no body to echo by construction and creates no new error branch in our code (both flow through the pre-existing map_err sites) | PASS |
| C-003 | yes | The landed F-2 premise and the replacement control both redden under the mutations they claim to catch | mutations A and B | two REDs at the named assertions | mutation A (strip fixture markers, the drift that survived round 2): RED at the sweep with the premise's own message. Mutation B (gut the other arm to Malformed(String::new()), the mutation the removed control could not catch): RED at the sweep via the new contains-418 control. Both landed controls redden | PASS |
| C-004 | yes | Constants and gating confirmed at head; no new error branch in our code | code read + diff | confirmed | CONNECT_TIMEOUT_SECS=10 and REQUEST_TIMEOUT_SECS=60 at head, both cfg(feature=http), pub consts with measurement-backed docs; delta touches transport.rs + test_openai.rs only; no default-build change, no new feature or egress route; CI completed success at head | PASS |
| C-005 | yes | The description incident is cleared: prior conclusions checked for description-dependency | diff saved copy vs restored body; review of round-1 evidence trail | explicit statement naming any affected conclusion or none | cleared: my saved round-1 description copy is the correct OpenAI-lane body (predates/missed the collision); the 133 differing lines vs the restored body are legitimate subsequent edits. Independently of that, every finding in my three rounds was diff- or mutation-derived; the only description-sourced items I cited were the live-API benchmark claims, labelled as the engineer's evidence and not load-bearing for any security conclusion. No conclusion requires revision | PASS |
| C-006 | yes | Verdict posted on PR #19 and reported | gh api | comment visible; report stated | comment posted on PR #19, verified via gh api; verdict reported to coordinator | PASS |

## Verification plan

- Focused: the loopback probe and two mutations, exit codes captured directly
- Independent verifier: coordinator and remaining reviewers
- Environment: pinned toolchain, gh CLI, loopback networking

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Change or investigation: worktree at 9845bba (sana_-prefixed); temp http-gated loopback probe (removed after); mutations A and B, restored clean; description diff; CI polled to completion
- Verifier executed: exit codes captured directly (PROBE_EXIT=0, MUTA_EXIT=101, MUTB_EXIT=101)
- Result: all PASS; deadline coverage and no-echo verified empirically on the real path
- New evidence: scratchpad sana_r4_probe.log, sana_r4_mutA.log, sana_r4_mutB.log, sana_body_diff.txt
- Decision: iterate

### Iteration 2

- Target criterion: C-006
- Change or investigation: posted the comment; reported to the coordinator
- Result: PASS
- Decision: complete

## Risks and rollback

- Probes isolated; worktree removed; review is additive commentary
- The probe uses its own short-deadline client of the same builder shape, so no 60s waits

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr19-timeouts.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator and remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (re-test deliverable)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
