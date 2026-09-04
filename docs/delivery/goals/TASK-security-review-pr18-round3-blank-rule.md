# Goal Contract — TASK-security-review-pr18-round3-blank-rule

## Identity

- Goal ID: TASK-security-review-pr18-round3-blank-rule
- Parent goal ID: TASK-security-review-pr18-dev-env-loader
- Title: PR #18 round-3 head c1d36fd is re-tested: the four-rule write-boundary harness result is independently confirmed, the F9 comment is checked for fidelity to the declined-re-check reasoning, containment is re-confirmed, and the verdict posted
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby6yy
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 5
- Independent verification required: yes

## Objective

At head c1d36fdbfd07e2c528b7e1468303daa5bcbb6132: the engineer's post-fix claim — all four
plan-rules bite at the write boundary, each by a distinct named test, with an all-rules-kept
re-derived control staying green — is confirmed by my own mutations; the new blank test is
verified to read the process environment after the real load_from; the F9 comment carries the
declined-runtime-re-check reasoning accurately; containment from round 1 still holds; findings
posted on PR #18.

## Baseline

Rounds 1-2 complete (review 5111431802; re-test comment 5539046722). Cody's F8 demonstrated the
blank-value rule as the one plan-rule not biting at the boundary (81/81 green with an empty
string exported). c1d36fd adds a_blank_value_is_never_exported_as_an_empty_string, corrects the
false F9 comment, hoists ENV_LOCK (F11), and writes the deletion map (F10). CI green at head.
The pre-fix baseline (blank GREEN, other three RED) is corroborated by two independent
measurements (Cody's demonstration, the engineer's reproduction) and is not re-run.

## Inputs and evidence sources

- git show c1d36fd:<path>; diff 70b116b..c1d36fd (dev_env.rs + engineer goal doc only)
- Isolated scratchpad worktree at c1d36fd, own CARGO_TARGET_DIR, restored clean and removed
- gh CLI for CI evidence

## Scope

### In scope

- Five mutation runs at c1d36fd replicating the harness against the REAL load_from: an
  all-rules-kept re-derived write loop (control, expect GREEN), then the same loop dropping one
  rule per run (allowlist, exported-wins, blank, NUL — each expect RED by its named test)
- Verification the blank test asserts std::env::var_os after load_from, not a Plan
- F9 comment fidelity; F10 deletion-map completeness spot-check; F11 lock-hoist sanity
- Containment: diff scope + binary signature re-scan at c1d36fd

### Non-goals

- Re-running the pre-fix baseline; re-reviewing settled rounds; modifying code; merging

### Constraints

- Exit codes captured directly; probes only in the isolated worktree; SHA-pinned reads

### Assumptions and unknowns

- ClickUp MCP absent again; routed via coordinator

## Dependencies and approvals

- gh CLI — available

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Baseline green in both feature states at c1d36fd | cargo test both states | exit 0 both; new test present and ok | 77 default / 82 dev-keys, both exit 0; a_blank_value_is_never_exported_as_an_empty_string present and ok | PASS |
| C-002 | yes | The all-rules-kept re-derived control is GREEN, so per-rule REDs are attributable | control mutation run | exit 0 | re-derived write loop keeping all four rules: exit 0, whole dev-keys suite green — the re-derivation is faithful, so per-rule REDs are attributable | PASS |
| C-003 | yes | Each dropped rule turns the suite RED by its distinct named test | four mutation runs | four REDs, names recorded | drop-allowlist RED at no_unallowlisted_name_reaches_the_process_environment; drop-exported-wins RED at an_exported_variable_survives_the_file; drop-blank RED at a_blank_value_is_never_exported_as_an_empty_string; drop-NUL RED at a_nul_bearing_value_does_not_panic_and_is_not_exported — each exactly one distinct failing test, exit 101, restored clean between runs | PASS |
| C-004 | yes | The blank test reads the process environment after the real load_from, with a same-fixture positive control | code read of the test | confirmed | confirmed by read: asserts std::env::var_os(blank).is_none() after the real load_from, positive control from the same fixture asserted first, plus environment-and-report agreement; never reads a Plan | PASS |
| C-005 | yes | F9 comment fidelity, F10 completeness, F11 sanity, containment re-scan | code read + grep + binary scan | verdicts recorded; 0/4 and 4/4 signatures | F9: the corrected comment states load_from applies the selection verbatim and re-checks nothing, names the false prior claim, and carries the declined-re-check reasoning accurately (inverted failure mode: filter absorbs a future widening silently where a test fails loudly). F10: grep at head finds no loader-owned site outside the eight listed (extra hits are the API project's own .env.sample convention and docs). F11: lock hoist is harmless hygiene; Rust-side env access was already serialised by std's internal lock, so this tightens ordering only. Containment: delta touches dev_env.rs + goal doc only; binary scan 0/4 default, 4/4 dev-keys (paired control); CI green at head (run completed success) | PASS |
| C-006 | yes | Verdict posted on PR #18 and reported | gh api | comment visible; report stated | re-test comment posted on PR #18, verified via gh api; verdict reported to coordinator | PASS |

## Verification plan

- Focused: the five mutation runs with siblings, never --exact; binary scans with paired control
- Independent verifier: coordinator and remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Change or investigation: worktree at c1d36fd, cached target dir; baselines; five-variant harness replication against the real load_from (control + four single-rule drops); F9/F10/F11 reads; deletion-map grep with API-scoped hits ruled out; binary re-scan
- Verifier executed: exit codes captured directly; worktree restored clean between runs and removed
- Result: all PASS; the engineer's post-fix claim reproduces exactly
- New evidence: scratchpad r3_default.log, r3_devkeys.log, r3_control.log, r3_drop_allow.log, r3_drop_wins.log, r3_drop_blank.log, r3_drop_nul.log, r3_bin_* scans
- Decision: iterate

### Iteration 2

- Target criterion: C-006
- Change or investigation: posted the re-test comment on PR #18; reported to the coordinator
- Result: PASS
- Decision: complete

## Risks and rollback

- Probes isolated; worktree removed; review is additive commentary

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr18-round3-blank-rule.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator and remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (re-test deliverable)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
