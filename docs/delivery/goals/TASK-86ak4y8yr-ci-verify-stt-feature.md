# Goal Contract — TASK-86ak4y8yr

## Identity

- Goal ID: TASK-86ak4y8yr
- Parent goal ID: NONE
- Title: CI verifies the operator build users actually install (`--features stt`) on every push and PR
- Role: devops-engineer
- Status: GATE_REVIEW (all criteria PASS; the four reviewers found no blockers; PR #137 stays Draft until the coordinator merges)
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak4y8yr
- Created: 2026-10-01
- Updated: 2026-10-01
- Maximum iterations: 6
- Independent verification required: yes (the four-reviewer gate is brokered by the parent; hosted CI on the PR is the proof for the YAML)

## Objective

A change that breaks the operator shell compiled with `--features stt` and nothing else (the exact
configuration `.github/workflows/windows-installer.yml` ships) turns a push/PR CI run red, and the
local `make ci` gate turns red for the same change.

## Baseline

Verified against `origin/main` (b73d389) before any change:

- The ticket's named defect (`manual checked division`, `listening.rs:115`) is ALREADY gone: the
  expression is now `done.saturating_mul(100).checked_div(total)` (introduced by 27f4c68, 2026-09-04,
  with the `cloud-stt` wiring). Re-measured below in C-001, not assumed.
- The ticket's headline ("verified by nothing") is PARTLY STALE: `ci.yml`'s `operator-native` job
  and `make ci` already run `clippy`/`test --features stt,cloud-stt` (added by c83b6fb / 27f4c68
  after the ticket was filed). Because `cloud-stt` implies `stt`, `listening.rs` IS now compiled
  and linted on every push.
- The core of the ticket still holds for the SHIPPED configuration. `stt` WITHOUT `cloud-stt` is a
  different compilation: `listening.rs` carries a `#[cfg(not(feature = "cloud-stt"))]` arm
  (the `TranscriptionRoute::Cloud` fallback in `start_listening`) that is compiled ONLY when `stt`
  is on and `cloud-stt` is off, and `windows-installer.yml` builds exactly `--features stt`
  (`cloud-stt` is `RELEASE: UNSAFE` and is stripped from release builds by the Makefile). No gate
  on any push compiles that arm.

## Inputs and evidence sources

- ClickUp 86ak4y8yr (description; no comments at start), linked 86akcmzyq.
- `.github/workflows/ci.yml` (`operator`, `operator-native` jobs), `.github/workflows/windows-installer.yml`.
- `Makefile` `ci:` target; `scripts/check_launch_reachability.py` (only relevant if Cargo features change; they do not).
- `implementation/desktop/crates/selahcue-operator/{Cargo.toml,src/listening.rs}`.

## Scope

### In scope

- A CI step that clippies the operator with `--features stt` (no `cloud-stt`, no `dev-keys`, no
  `openai-notes`) with `-D warnings --all-targets`, on push/PR, in the existing `operator-native` job.
- The same line in the local `make ci` target.
- Any lint/compile failure that line finds at HEAD (fixed, not suppressed).

### Non-goals

- A macOS/Linux installer workflow (the ticket's "Also noted" item; separate concern).
- Building the Windows installer on every push (`cargo tauri build` is far too heavy; the compile/lint
  of the feature set is the part that rots silently).
- Running the `stt`-only TEST suite on every OS unless C-001's measurement shows its results differ
  from `stt,cloud-stt` (decided in the iteration ledger, with the measurement).
- Changing any Cargo feature (so the `LAUNCH_REACHABILITY`/`RELEASE` tagging rules are untouched).

### Constraints

- PR #134 (`feat/17tnw2b0q9j-web-marketing-gates-download`) also edits the root `Makefile` `ci:` target
  and `.github/workflows/ci.yml`: keep both hunks small, separate and unreformatted.
- `make stage-operator-binaries` stays create-only; the full `make ci` is NOT run here (Flutter collides
  with other sessions) — targeted commands only. No `CARGO_TARGET_DIR`.
- Hosted CI cannot be run from here; the PR's own run is the evidence for the YAML.

### Assumptions and unknowns

- ASSUMED: `stt` on macOS (Metal) and Linux (ALSA) lints the same platform-independent code as on
  Windows; the shipped OS is Windows, so Windows stays in the matrix (see C-003). Validated: the
  hosted run passed the step on all three OSes (run 36819129002).
- MEASURED (was unknown at the start): the marginal wall-clock cost of the new step, on run
  36819129002, is 5s on ubuntu (a full cache miss, so a cold job), 10s on windows and 16s on macOS.

## Dependencies and approvals

- None for the change itself. Review gate (Cody, Vera, Shadow, Quinn) is brokered by the parent.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The existing rot is fixed: the operator is `-D warnings` clean and compiles with `--features stt` at the branch head | `cargo clippy --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features stt --all-targets -- -D warnings` (clippy type-checks every cfg arm, so it subsumes `cargo check`) plus `cargo fmt --check` | exit 0, no warnings; log shows `whisper-rs-sys` compiled | Verified on macOS arm64: cold run at origin/main exit 0 in 9m51s with `whisper-rs-sys v0.13.1` and `whisper-rs v0.14.4` compiled; clean-tree re-run exit 0; `cargo fmt --check` exit 0; `cargo test --features stt` 198 passed. No rot found, so no product-code change. | PASS |
| C-002 | yes | CI runs that same clippy command on every push/PR that touches desktop code | `grep` the step in `ci.yml`; `actionlint` and `.github/scripts/check_workflows.py` exit 0; the PR's hosted run shows the step executing | step present in a job gated on `needs.changes.outputs.desktop == 'true'`; both linters exit 0; hosted run shows the step | Local: step is in `operator-native` (gated on `desktop`); `actionlint` 1.7.12 exit 0; `check_workflows.py` and its self-test exit 0. Hosted run https://github.com/First-Pavilion/selahcue/actions/runs/36819129002 (head a82191f, `pull_request`): every job success; the new step ran and passed on all three OSes, and the Windows log shows the exact command and `Finished dev profile`. Step times: ubuntu 5s (a full cache miss), windows 10s, macOS 16s; Cody and Vera read the same logs and agree. | PASS |
| C-003 | yes | The runner/OS choice and its cost are justified from evidence, not guessed | review of the PR body and the YAML comment | choice, rejected alternatives and measured/unknown costs are stated; unknowns labelled | The YAML comment above the step and the PR body: added to `operator-native` on all 3 OSes (reuses the job's already-built whisper.cpp and OpenSSL); rejected a new job and Linux-only; 7s measured locally; hosted cost measured on run 36819129002 (ubuntu 5s on a full cache miss, windows 10s, macOS 16s) with a stated fallback if a later run nears a timeout. | PASS |
| C-004 | yes | The local `make ci` path has the same coverage | `make -n ci` lists the `--features stt` clippy line; the line itself exits 0 | line present and green | `make -n ci` line 126 expands to the identical cargo command, which exits 0 (see C-001). Full `make ci` deliberately NOT run (Flutter collides with other sessions). | PASS |
| C-005 | yes | The guard is non-vacuous | Mutation: add a clippy violation visible ONLY to `stt`-alone (inside the `#[cfg(not(feature = "cloud-stt"))]` arm), and separately re-introduce the ticket's literal `manual_checked_division`; run the new command | new command exits non-zero naming the lint, while the EXISTING `--features stt,cloud-stt` command stays green for the first mutation (proving the new step covers a hole the old one did not); both mutations reverted, `git diff` clean | Mutation 1 (violation inside the `not(cloud-stt)` arm of `listening.rs`): new command exit 101 `manual checked division` at the injected line; existing `--features stt,cloud-stt` command exit 0 on the SAME tree. Mutation 2 (the ticket's literal `if total > 0 { done.saturating_mul(100) / total }` at `emit_phase`): new command exit 101 `manual checked division` at `listening.rs:254`. Both reverted; diff of `implementation/` empty. | PASS |
| C-006 | yes | The diff in the two contended files is minimal and localized | `git diff origin/main --stat -- Makefile .github/workflows/ci.yml`; read the hunks | small separate hunks, no reformatting, none inside PR #134's hunk ranges | `ci.yml` +28 in one hunk at the end of `operator-native` (PR #134 touches about lines 148 and 1133); `Makefile` +9/-2 in two hunks (a stale comment at line 60 and the new line near 761; PR #134 touches 277, 615, 661, 707). | PASS |
| C-007 | yes | Honest reporting: what is Verified vs Inferred vs not covered is stated, including that the ticket's premise was partly stale | review of PR body + ClickUp comments | stale parts named; hosted-only claims labelled | Baseline section above and the PR body name the stale rot claim and the stale "verified by nothing" claim; the hosted cost and run were labelled Unknown or pending until run 36819129002 measured them, and the PR body now states the measured numbers. | PASS |
| C-008 | yes | The branch is mergeable and its own CI is read | `git rev-list --count HEAD..origin/main` is 0; PR is Draft; `gh run list/view` for this branch read and reported (or a stated reason it did not run) | 0; Draft; real result reported | origin/main was merged into the branch in the review-fix push and `git rev-list --count HEAD..origin/main` re-measured as 0 afterwards; PR #137 is Draft; the run on the previous head (36819129002) was read green. The run on the merge head is read after the push and recorded on the PR and the ClickUp task. | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001/C-004/C-005 commands above, run in this worktree with `/opt/homebrew/bin` on PATH.
- Broader regression verification: `python3 scripts/check_launch_reachability.py --self-test && python3 scripts/check_launch_reachability.py`,
  `python3 scripts/check_dependency_audit_coverage.py`, `python3 .github/scripts/check_workflows.py`, `actionlint`.
- Independent verifier: hosted CI on the PR (YAML), plus the parent-brokered four-reviewer gate.
- Required environment: macOS arm64 local worktree (cmake available); hosted GitHub Actions for ubuntu/macOS/windows.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 (baseline).
- Hypothesis: the ticket's lint is already fixed, but `stt`-alone has never been compiled by a gate, so it may hold other rot.
- Change or investigation: run the new command at `origin/main` before changing anything.
- Verifier executed: the C-001 clippy command at origin/main code (cold build, macOS arm64).
- Result: exit 0 in 9m51s, no warnings; `whisper-rs-sys` and `whisper-rs` compiled. Hypothesis half-refuted: no rot found in `stt`-alone today; the named lint was fixed on 2026-09-04.
- New evidence: the shipped build is clean now, but no push-time gate would have noticed had it not been.
- Decision: iterate (add the guard, then prove it bites)

### Iteration 2

- Target criterion: C-002, C-004, C-005.
- Hypothesis: a step linting `--features stt` in `operator-native` plus the same `make ci` line closes the gap, and it bites on a violation only `stt`-alone can see.
- Change or investigation: added the step to `ci.yml` and the line to the `ci:` target; ran two mutations (see C-005); measured `cargo test --features stt` (198 tests, all also in the `stt,cloud-stt` run of 206) to decide that no `Test (stt)` step is needed.
- Verifier executed: the C-005 mutation probes; `actionlint`, `check_workflows.py`, `check_launch_reachability.py`, `check_dependency_audit_coverage.py`.
- Result: both mutations fail the new command with exit 101; the existing `stt,cloud-stt` command stays green on mutation 1; all linters exit 0.
- New evidence: marginal cost of the new clippy after the other feature set's deps are built is 7s locally.
- Decision: handoff (push, open Draft PR, read the hosted run)

### Iteration 3

- Target criterion: C-002, C-008 and the stale wording found in review (Cody F1/F2, Vera, Quinn).
- Hypothesis: the hosted run finished green and the four reviews found no blockers, so only evidence and comment accuracy are left.
- Change or investigation: recorded the hosted run and measured step times in C-002/C-003/C-007; corrected the header status and the assumptions line; rewrote three `ci.yml` comments (measured cost, the six re-checked packages, the "never separately gated" sentence); merged `origin/main` (30 commits behind by then, no conflicts) and re-verified the behind count.
- Verifier executed: both goal-contract validators with the completion flag; `actionlint` 1.7.12; `check_workflows.py` and its self-test; `make -n ci`; `check_launch_reachability.py`; the stt-alone clippy command on the merged tree.
- Result: see Final evaluation.
- New evidence: the ubuntu job was a full cache miss and the new step still took 5s, so the reuse claim holds cold.
- Decision: complete (pending the hosted run on the merge head and the coordinator's merge)

## Risks and rollback

- Risks: (1) added wall-clock on the slowest job (`operator-native`, windows) — mitigated by reusing the
  already-built `whisper-rs-sys`/OpenSSL artefacts in the same job; measured at 5-16s per OS on run 36819129002.
  (2) rebase conflict with PR #134 in `ci.yml`/`Makefile` — mitigated by minimal separate hunks.
- Rollback: revert the single commit (pure additive CI/Makefile lines; no product code unless C-001 finds rot).

## Pause and escalation conditions

- Stop if the hosted run shows the new step pushing a matrix arm past its `timeout-minutes` (owner decides: raise timeout, drop an OS).
- Stop if fixing a rot finding needs a product decision (e.g. behaviour change in `listening.rs`).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ak4y8yr-ci-verify-stt-feature.md --completion`
- Validator result: both validators (`~/.claude/skills/goal/scripts/validate_goal_contract.py --completion` and `scripts/validate_goal_contract.py --require-complete`) exit 0 with every mandatory criterion PASS.
- Independent verification result: hosted run 36819129002 green on the previous head; Cody Approve-with-non-blocking, Shadow Pass, Vera Pass, Quinn Pass, no blockers. The run on the merge head is read after the push.
- Terminal state: GATE_REVIEW (every criterion PASS; the reviewers have signed off; the coordinator merges)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ak4y8yr after the review-fix push
