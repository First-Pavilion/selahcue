# Goal Contract — TASK-code-review-pr13-plan-links

## Identity

- Goal ID: TASK-code-review-pr13-plan-links
- Parent goal ID: NONE
- Title: PR #13 head dcbe201 is code-reviewed, the prior blocking finding B3 is judged closed or re-stated with evidence, and the verdict is posted on the PR
- Role: code-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hw0
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The two commits added since the previous code review (713125d, dcbe201) are reviewed against the findings they claim to close, each claim is confirmed or refuted by mutating the control rather than reading it, and a verdict with any remaining blocking findings is posted as a PR comment.

## Baseline

PR #13 was reviewed at 49cd4e8 and returned CHANGES REQUESTED with B3 blocking: a `section` divider could still hold an owner, a duration and a link while every summary metric excluded it, so one frame could report `missing: 0` beside a row whose own link said `"missing"`. H1 (blank label erases the last known good deck name), M3 (cited spec in no commit), M4 (frame-12 card has no automated cover) and L6/L7 were also open. The branch has since been rebased onto origin/main @ 3ae0d87; the `implementation/desktop` tree hash is identical at 49cd4e8 and its rebased twin 922907d, so the prior review carries over unchanged.

## Inputs and evidence sources

- Own detached worktree at /Users/m.oluwole/Documents/code/scph-wt-cody-b3 (head dcbe201), own CARGO_TARGET_DIR
- `git diff 922907d dcbe201` and `git diff 3ae0d87 dcbe201`
- Prior review comment 5460603922 on PR #13
- selahcue-core/src/plan.rs, selahcue-app/src/controller.rs, selahcue-lan/src/protocol.rs, selahcue-operator/dist/app.js, scripts/operator_headless.py
- selahcue-data/src/plan_repo.rs (the one rehydration path)
- implementation/mobile/selahcue_controller/lib (checked for owner/duration senders)

## Scope

### In scope

- The B3 remediation: the divider guard, its propagation to the LAN reply, the rehydration sweep, and the wire docs it corrects
- Whether refusing rather than storing-and-ignoring rejects a legitimate edit or destroys data on a migration path
- H1, L6 and M4 as claimed closed in 713125d/dcbe201
- Mutation verification of every control named as evidence
- The Rust and headless gates at dcbe201

### Non-goals

- Deep security review (Sana) and performance profiling (Vera)
- Re-reviewing scope already cleared at 49cd4e8 (B1, B2, M1, M2, L1-L4)
- The Django api and marketing projects, untouched by this PR

### Constraints

- Do not enter, check out in, or run anything inside /Users/m.oluwole/Documents/code/scph-wt-plan-links
- Never pipe a gate command into tail/head; capture output and read the exit code
- Never modify the code under review outside a mutation that is restored immediately

### Assumptions and unknowns

- ASSUMED: `cargo check` on the selahcue-operator crate fails in a fresh worktree only because the Tauri sidecar binary is absent — validated by observing that no operator Rust source is in the diff
- UNKNOWN: cross-OS and WebKit behaviour, which only CI can exercise — owner is CI on the PR

## Dependencies and approvals

- docs/design/PLAN-SECTIONS-DURATIONS-spec.md — owned by ticket 86ak7kgmk, still in no commit; merge-order dependency, owner is delivery
- Merge order #13 before #12 (both edit dist/app.js) — owner is delivery

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The whole changed scope since 49cd4e8 was read, not sampled | `git diff 922907d dcbe201` reviewed file by file | 6 files, 427 insertions accounted for | review notes | PASS |
| C-002 | yes | Removing the divider guard from each of the three setters turns a named test RED | mutate plan.rs, `cargo test -p selahcue-core --test test_plan` and `-p selahcue-app --features server --test test_controller` | exit 101 each time, restored to green | mutations 1-3 | PASS |
| C-003 | yes | Removing the controller's Deny propagation turns a named test RED | mutate controller.rs to `let _ =`, run test_controller | exit 101 | mutation 5 | PASS |
| C-004 | yes | Removing the from_parts rehydration sweep turns a named test RED | mutate plan.rs, run test_plan | exit 101 | mutation 4 | PASS |
| C-005 | yes | No shipped client can now be refused a legitimate edit | grep dist/app.js and mobile lib for the three senders; check for a kind-change command | zero owner/duration senders; link UI gated on kind; no kind-change command exists | app.js:7148, protocol.rs command list | PASS |
| C-006 | yes | The rehydration sweep's data-loss exposure is quantified | read plan_repo::load/save and the client senders | sweep is destructive on next save; only a hostile LAN peer under a pre-guard build could have created such a row | plan_repo.rs:206 | PASS |
| C-007 | yes | H1's blank-label guard is mutation-verified | revert the guard, run test_plan | exit 101 | mutation 6 | PASS |
| C-008 | yes | L6's sanitisation is mutation-verified on both halves | revert the core setter half, then the controller half | core half RED; controller half GREEN — gap found | mutations 7-8 | PASS |
| C-009 | yes | M4's new headless checks are load-bearing on both sides | drop `label` from each deck-link send site, run scripts/operator_headless.py | write side stays green at 834/0 — gap found | mutations 9-10 | PASS |
| C-010 | yes | The gates pass at dcbe201 in an isolated worktree with exit codes read directly | toolchain, fmt, clippy, per-crate tests, import_guards, headless | all exit 0; headless 834 checks 0 FAIL | scratchpad gate logs | PASS |
| C-011 | yes | M3's status is re-checked rather than accepted | `git log --all -- docs/design/PLAN-SECTIONS-DURATIONS-spec.md`, `git grep FR-202 -- docs` | in no commit on any branch; FR-201/FR-202 defined nowhere in committed docs | verified | PASS |
| C-012 | yes | Findings are severity-ranked, evidenced, and posted on the PR with a stated verdict | PR comment on #13 | comment posted, verdict stated, reviewed and unreviewed scope named | PR #13 comment | PASS |
| C-013 | no | The consolidated report is published as a link-shareable Artifact | artifact tool | published URL on the PR | not possible — no artifact tool in this session | BLOCKED |

## Verification plan

- Focused verification: mutate each control named as evidence for B3, H1, L6 and M4, confirm RED, restore, confirm green again
- Broader regression verification: fmt, clippy --workspace --all-targets --features server -D warnings, per-crate tests for core / app(server) / lan(server) / data / present, import_guards.sh, scripts/operator_headless.py
- Independent verifier: the author re-runs the two surviving mutations (mutation 8 and mutations 9-10) and sees them fail once the gaps are closed
- Required environment: own detached worktree, own CARGO_TARGET_DIR, pinned toolchain 1.98.0

## Iteration ledger

### Iteration 1

- Target criterion: C-002 through C-004 — is B3 actually closed
- Hypothesis: the guard, its propagation and the sweep are each load-bearing, and each is caught by a named test
- Change or investigation: five separate mutations of the code under review, each restored immediately
- Verifier executed: per-crate cargo test with --no-fail-fast, exit codes captured directly
- Result: all five mutations RED; tree restored byte-identical (git status clean)
- New evidence: the cross-field assertion block inside the new controller test compares 0 against 0 at the point it runs, so it is not the part of that test doing the work
- Decision: iterate

### Iteration 2

- Target criterion: C-005, C-006, C-008, C-009 — does the fix create a new problem, and are H1/L6/M4 fully covered
- Hypothesis: refusing is safe because no shipped client can send the refused commands, and the two remediation commits may have partial test cover
- Change or investigation: grepped both clients for the senders, read the rehydration and save paths, mutated the controller sanitiser and both deck-label send sites
- Verifier executed: cargo test, scripts/operator_headless.py, a temporary probe test (deleted) for parse-vs-sanitise interaction
- Result: no legitimate edit is rejected; two controls survive mutation — the controller-side sanitiser and the deck-label write sites
- New evidence: `"Romans 8:2\u{200B}8"` fails parse_one raw and parses clean, so the controller sanitiser changes accept/deny and nothing tests it
- Decision: complete

## Risks and rollback

- Risk: a mutation left in place would corrupt the shared checkout. Mitigated by working only in an isolated worktree and by confirming `git status` clean and `git diff` empty after every restore.
- Risk: a shared target directory produces a spurious red. Mitigated by a dedicated CARGO_TARGET_DIR inside the review worktree.
- Rollback: the review changes no repository file under review; the worktree is removed when the round closes.
