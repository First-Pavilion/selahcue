# Goal Contract — GOAL-devops-ci-toolchain-drift

## Identity

- Goal ID: GOAL-devops-ci-toolchain-drift
- Parent goal ID: BUILD-selahcue
- Title: `main`'s pipeline is green again, and the local gate and CI provably compile with the same pinned Rust toolchain
- Role: devops-engineer
- Status: GATE_REVIEW (all four reviewers pass; awaiting merge)
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5rc9c
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

CI on `main` passes again, and the toolchain that broke it can no longer diverge silently: `make ci` and `.github/workflows/ci.yml` gate on one pinned Rust version, a shared script asserts it in both, a scheduled canary surfaces the next release before it bites, and a failed `main` run raises a visible alarm.

## Baseline

Verified 2026-08-25 against `origin/main` at `607a7b5`.

- The last green CI run on `main` was `31978969262` (2026-08-16). Every run since has failed: `32637352346`, `32637406933` (08-23), `32712283681`, `32723339463` (08-24), `32821185981` (08-25). Nine days without a green; red began 08-23, the first push after Rust 1.98.0 shipped on 08-18.
- Failure 1 (all five runs): `clippy::chunks_exact_to_as_chunks`, new in Rust 1.98.0, met the `-D warnings` gate. `rust` failed on ubuntu, macOS and Windows. Exit 101 (Unix) / 1 (Windows).
- Failure 2 (two runs only, already fixed): `error[E0063]: missing field 'overrun_secs'` at `selahcue-present/tests/test_present.rs:369`, from `7369f61` adding the field without updating that test; fixed by `f73e9b9`. It surfaced only in `launch-smoke` (via `make nfr`) because the `rust` job fail-fasts at clippy before `cargo test`.
- Root cause: no `rust-toolchain.toml` existed anywhere. CI used `dtolnay/rust-toolchain@stable` (newest stable at run time); local was rustc 1.97.1. CI installed rustc 1.98.0 (88d9e12ae 2026-08-18).
- The CI log named 5 lint sites; that was only the prefix clippy reached before aborting on the library. The true count is 16 across four crates.
- No notification exists on a failed `main` run, and branch protection is unavailable for this private repo on the current plan.

## Inputs and evidence sources

- `gh run view --log-failed` for the five failed runs and the last green one
- `.github/workflows/ci.yml`, `Makefile`, `CLAUDE.md`
- `git log -S chunks_exact`, `git show 7369f61`, `git show f73e9b9`
- rustup toolchains 1.97.1 and 1.98.0 installed locally to reproduce CI exactly

## Scope

### In scope

- Convert all 16 constant-size `chunks_exact(N)` sites to `as_chunks::<N>()`, the fix the lint itself suggests, with no `#[allow]`.
- Add `rust-toolchain.toml` pinning an exact version, plus `scripts/check_toolchain.sh` called by both `make ci` and every Rust CI job.
- Add `.github/workflows/rust-canary.yml` — scheduled, non-blocking, floating stable, files an issue.
- Add `ci-red` issue alerting on a failed `main` run, self-clearing when `main` recovers.
- Correct `CLAUDE.md`'s "local mirror" claim.

### Non-goals

- Widening `make ci` to cover the `api (django)` and `marketing (vue spa)` jobs, the WebKit smoke, launch-smoke/`make nfr`, `cargo audit`/`cargo deny`, or the Android APK check — tracked separately as 86ak5rjh7.
- Changing rasterizer behaviour in any way.
- Opening the pull request (owner requires the four-reviewer gate first).

### Constraints

- `selahcue-engine/src/raster.rs` sits behind the ADR-0015 GPU parity oracle (SSIM ≥ 0.99) and a bounded prefix cache; its output must not change.
- Work in an isolated worktree with a dedicated `CARGO_TARGET_DIR`; never touch the shared checkout's build cache.

### Assumptions and unknowns

- ASSUMED: pinning to 1.98.0 (current stable) rather than 1.97.1 is preferred, since CI already installs it and the new lint is a genuine improvement. Validation owner: reviewers.
- UNKNOWN: whether the owner wants the `ci-red` alarm routed somewhere beyond a GitHub issue (email/Slack). Validation owner: repository owner.

## Dependencies and approvals

- Four-reviewer gate (Cody, Vera, Sana, Quinn) before any PR — owner requirement, pending.
- No production or destructive action is involved.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The lint no longer fires anywhere in the desktop workspace on the toolchain CI uses | `cargo clippy --workspace --all-targets -- -D warnings` on 1.98.0 | exit 0 | `scratchpad/gate_clippy_all.log` | PASS |
| C-002 | yes | The three feature-gated clippy runs also pass on 1.98.0 | the `-p selahcue-lan/app/scripture` clippy runs | exit 0 each | `scratchpad/gate_clippy_all.log` | PASS |
| C-003 | yes | No `#[allow]` was added to suppress the lint | `grep -rn 'chunks_exact_to_as_chunks' implementation/` | no match outside comments | grep output | PASS |
| C-004 | yes | The rasterizer's output is bit-identical: pixels, `average_luminance`, `average_redness`, `tile_stats`, `ssim` | golden probe over 6 scenes, f64 bit patterns, before vs after | zero diff | `golden_BEFORE.txt` vs `golden_AFTER.txt` | PASS |
| C-005 | yes | That probe actually detects a change (it is not vacuous) | deliberately mutate `average_luminance` + `channel_ssim`, re-run | probe output differs; restored output matches baseline | `golden_MUT.txt`, `mutdiff.txt` | PASS |
| C-006 | yes | The whole desktop suite plus the Flutter gate passes | `make ci` | exit 0 | `scratchpad/make_ci2.log` | PASS |
| C-007 | yes | The GPU↔CPU parity oracle passes at SSIM ≥ 0.99 | `cargo test -p selahcue-gpu` | `wgpu_matches_cpu_rasterizer_to_ssim_0_99` passes, not skipped | `scratchpad/gpu_parity.log` | PASS |
| C-008 | yes | The pin actually changes which compiler runs, with no flags | `rustc --version` in the worktree vs the unpinned checkout | 1.98.0 vs 1.97.1 | recorded terminal output | PASS |
| C-009 | yes | The guard refuses a mismatched, floating, or missing pin | run `check_toolchain.sh` under each condition | exit 1 with a specific message each time | recorded terminal output | PASS |
| C-010 | yes | `make ci` and CI invoke the same guard before any gate | read `Makefile` `ci:` and all three Rust jobs in `ci.yml` | `sh scripts/check_toolchain.sh` present in all four | `make -n ci`, `grep` over `ci.yml` | PASS |
| C-011 | yes | Both workflow files are valid and the canary genuinely floats | `yaml.safe_load` both; confirm `RUSTUP_TOOLCHAIN: stable` in the canary | parse clean; canary overrides the pin | recorded output | PASS |
| C-012 | yes | `CLAUDE.md` no longer claims `make ci` mirrors CI | read the Conventions section | claim replaced by an explicit covered/not-covered statement | `CLAUDE.md` diff | PASS |
| C-013 | yes | The alarm cannot close itself on a run that merely SKIPPED the failing job | `ci_alarm.py --self-test`, incl. the api-only-push case | exit 0; skipped never clears | `.github/scripts/ci_alarm.py` | PASS |
| C-014 | yes | That self-test detects the bug it exists to prevent | reintroduce "skipped counts as recovery", re-run | self-test exits 1 naming the case | recorded terminal output | PASS |
| C-015 | yes | Both workflows pass a real workflow linter, not review by eye | `actionlint 1.7.12` over both files | exit 0 | recorded terminal output | PASS |
| C-016 | yes | A failing gate no longer suppresses the gates after it in CI | parse `ci.yml`; check every GATE step (Format onward) in `rust` and `operator` | all carry `if: ${{ !cancelled() }}`; setup steps deliberately do not | `.github/workflows/ci.yml` | PASS |
| C-017 | yes | `--no-fail-fast` measurably surfaces a failure it would otherwise hide | inject a failing test in two independent crates, run with and without | 1 binary reported FAILED without, 2 with | recorded terminal output | PASS |
| C-018 | yes | Every job holding a `permissions` block that checks out code also has `contents` access | `check_workflows.py` over all workflows | exit 0 | `.github/scripts/check_workflows.py` | PASS |
| C-019 | yes | That check detects the shipped defect, and actionlint does not | restore `issues: write`-only on `ci-alarm`; run both | check exits 1 naming the job; actionlint exits 0 | recorded terminal output | PASS |
| C-020 | yes | Every job that can fail on `main` is inside the alarm's `needs` | compare `jobs:` keys with `ci-alarm.needs` | only `ci-alarm` itself absent | `.github/workflows/ci.yml` | PASS |
| C-021 | yes | Placeholder staging cannot truncate an existing file | run the `stage()` helper over a non-empty file | contents preserved; missing file created at 0 bytes | recorded terminal output | PASS |
| C-022 | no | The alarm's GitHub WRITE path works end to end | one `workflow_dispatch` of `ci` on `main` after merge | an issue is created and then closed | ClickUp 86ak5rc9c | PENDING |
| C-039 | yes | The alarm job executes at all — condition, permissions, checkout, self-test | `workflow_dispatch` of `ci` on the branch (run 32900486643) | job conclusion `success`; checkout and self-test steps pass | GitHub run 32900486643 job 97978166110 | PASS |
| C-040 | yes | `always()` keeps the alarm running when its dependencies fail | same run, with `api` and `rust` already failed | alarm still executes rather than being skipped | same job log | PASS |
| C-041 | yes | The reconcile produces the right verdict from real `needs` data | read the job's output | `newly failed: ['api', 'rust']`, marker `api,rust` | same job log | PASS |
| C-042 | yes | DRY_RUN withholds EVERY write, including `gh label create` | after the run, list issues and labels on the repo | zero issues, zero `ci-red` label | `gh issue list` / `gh api .../labels` — both empty | PASS |
| C-024 | yes | A job absent from a run's results does not count as recovered | `ci_alarm.py --self-test`, plus mutating to `results.get(job, "success")` | self-test exits 0 clean, exits 1 mutated | `.github/scripts/ci_alarm.py` | PASS |
| C-025 | yes | An issue whose marker was edited away cannot be closed by a run that skips the broken jobs | self-test's stripped-marker case, plus mutating `parse_marker` to return `set()` | stays outstanding; mutation caught | recorded terminal output | PASS |
| C-026 | yes | A fully green run still closes a marker-less issue (the fallback self-heals) | self-test `conservative_outstanding` + `reconcile` over an all-success run | outstanding empties | `.github/scripts/ci_alarm.py` | PASS |
| C-027 | yes | The pin parser accepts either TOML quote style and still rejects a floating one | `--print-channel` against `"1.98.0"`, `'1.98.0'`, `'stable'` | 0, 0, 1 | recorded terminal output | PASS |
| C-028 | yes | No claim in `CLAUDE.md` is falsified by this branch | re-read every claim this branch touches | `--no-fail-fast` and operator-coverage sentences corrected | `CLAUDE.md` | PASS |
| C-030 | yes | No corrupt marker shape can produce a false all-clear | 9 shapes (absent, mangled, 2 empty spellings, commas-only, whitespace, prepended-empty, intact, pruned) through `outstanding_from` + `reconcile` | 0 shapes close while `rust` is red | recorded terminal output | PASS |
| C-031 | yes | The self-test actually guards the trust decision (is not vacuous) | revert `if not recorded` to `if recorded is None`; re-run self-test | exits 1 | recorded terminal output | PASS |
| C-032 | yes | No `success()` step follows a `!cancelled()` step in any job | `check_workflows.py` ordinal check | exit 0 | `.github/scripts/check_workflows.py` | PASS |
| C-033 | yes | That ordering check detects the stranded staging step, and actionlint does not | strand staging back between Format and Check; run both | checker exits 1 naming the step; actionlint exits 0 | recorded terminal output | PASS |
| C-034 | yes | Every mutating `gh` call is withheld under DRY_RUN | run the alarm with `DRY_RUN=true` against a stub `gh` that logs real invocations | 0 real writes executed | recorded terminal output | PASS |
| C-036 | yes | A step with a NON-STATUS `if:` after a gate is also flagged as stranded | add `if: runner.os == 'Linux'` between two gates; run the checker | checker exits 1 naming the step; actionlint exits 0 | recorded terminal output | PASS |
| C-037 | yes | That rule is guarded (reverting it to "no `if:` only" is caught) | mutate `STATUS_FN.search(cond)` back to `not cond`, and disable the rule | self-test exits 1 in both cases | recorded terminal output | PASS |
| C-038 | yes | CI can actually run on a pull request | open PR #2 and observe the pipeline | `changes` succeeds and the matrix runs, rather than failing on a refused API call | GitHub PR #2 checks | PASS |
| C-035 | yes | The four reviewers have reviewed and blocking findings are cleared | Cody, Vera, Sana, Quinn (+ Codex counterparts) | no unresolved blocking findings | ClickUp 86ak5rc9c comments | PASS |

## Verification plan

- Focused verification: reproduce the exact CI failure on 1.98.0, fix, re-run the same command, confirm exit 0.
- Broader regression verification: full `make ci`; explicit `selahcue-gpu` parity run; golden-output probe with a mutation control.
- Independent verifier: Cody, Vera, Sana, Quinn per the review pipeline.
- Required environment: macOS worktree with a dedicated `CARGO_TARGET_DIR`; rustup 1.97.1 and 1.98.0 both installed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: the failure is toolchain drift, not a code regression; installing 1.98.0 locally will reproduce it exactly.
- Change or investigation: installed rustc 1.98.0; ran the engine clippy gate.
- Verifier executed: `cargo +1.98.0 clippy -p selahcue-engine --all-targets -- -D warnings`
- Result: exit 101, the same five sites CI named. Reproduced.
- New evidence: CI's log shows `stable ... updated - rustc 1.98.0 (88d9e12ae 2026-08-18) (from rustc 1.97.1 ...)`.
- Decision: iterate

### Iteration 2

- Target criterion: C-004, C-005
- Hypothesis: `chunks_exact(N)` and `as_chunks::<N>().0` yield identical element sequences, so the rewrite cannot change output.
- Change or investigation: proved equivalence on both toolchains; captured a golden baseline; applied the five library fixes; re-ran; then mutated two of the touched functions to prove the probe is not vacuous.
- Verifier executed: golden probe before / after / mutated / restored
- Result: after == before bit-for-bit; mutated != before; restored == before.
- New evidence: `as_chunks` is stable on 1.97.1 as well, so the fix does not raise the effective MSRV.
- Decision: iterate

### Iteration 3

- Target criterion: C-001 across the whole workspace
- Hypothesis: the five sites CI named are only the prefix clippy reached before aborting on the library.
- Change or investigation: ran the full `--workspace --all-targets` gate on 1.98.0.
- Verifier executed: `cargo +1.98.0 clippy --workspace --all-targets -- -D warnings`
- Result: an eleven-site tail in test targets and `selahcue-import` that the original run never reached. All fixed; gate now exits 0.
- New evidence: clippy fail-fast masked 11 of 16 sites, the same way it masked the E0063 in `selahcue-present`.
- Decision: iterate

### Iteration 4

- Target criterion: C-008 … C-012
- Hypothesis: a repo-root `rust-toolchain.toml` plus one shared assertion script makes local/CI agreement checkable rather than asserted.
- Change or investigation: added the pin, `scripts/check_toolchain.sh`, wired it into `make ci` and all three Rust CI jobs, added the canary and the `ci-red` alarm, corrected `CLAUDE.md`.
- Verifier executed: guard self-test plus three negative controls; `rustc --version` per directory; YAML parse of both workflows; `make -n ci`.
- Result: pin flips the compiler with no flags; guard exits 1 on mismatch, on a floating channel, and on a missing file.
- New evidence: `make ci` cannot run in a fresh worktree at all — CI stages Tauri sidecar placeholders in a dedicated step and `make ci` does not. Added to 86ak5rjh7.
- Decision: gate-review

### Iteration 5 — code review (Cody) rework

- Target criterion: C-013 … C-017
- Hypothesis: the alarm's close condition treats a SKIPPED job as evidence of health, so a path-filtered push could clear it while `main` was still broken.
- Change or investigation: confirmed the defect. Replaced the two `if:`-driven alert jobs with one `ci-alarm` job whose logic lives in `.github/scripts/ci_alarm.py` and tracks the outstanding job set; a job clears only by reporting `success`. Added `actionlint` to CI and ran it locally over both workflows. Added `if: ${{ !cancelled() }}` after Clippy and `--no-fail-fast` to the test commands. Extended the canary to the `selahcue-operator` root. Hardened the guard (`cd "$root"`, captured `rustc --version` instead of piping it, single `--print-channel` parser now used by `ci.yml`).
- Verifier executed: `ci_alarm.py --self-test` plus a mutation of it; `actionlint` over both workflows plus a probe workflow; injected two-crate failures to measure `--keep-going` and `--no-fail-fast`.
- Result: self-test passes and goes RED when the bug is reintroduced; actionlint clean; `--no-fail-fast` surfaced a second failing binary (1 → 2).
- New evidence — three review claims did not survive checking, and are recorded rather than quietly accepted:
  1. `needs.launch-smoke.result` is **valid** GitHub Actions syntax, not runtime-fatal. actionlint models the context as `{launch-smoke: {outputs: {}; result: string}}` and accepts dot notation, while correctly rejecting a genuinely undefined job. The bracket form is defensive style, not a bug fix.
  2. actionlint would **not** have caught it — verified by reintroducing the expression and re-running actionlint (exit 0). actionlint earns its place on other grounds.
  3. `--keep-going` is a **no-op for this workspace**: every crate holding a hidden lint site depends on `selahcue-engine`, so nothing could compile past its failure, and for independent siblings cargo already reported both without the flag. Not adopted; the honest fix for that masking is the step-level one.
- Also found: `selahcue-stt` is linted by no gate at all and already fails its own `unwrap_used` policy (3 errors). Deliberately excluded from the canary so it cannot manufacture a permanent false alarm; raised on 86ak5rjh7.
- Decision: gate-review

### Iteration 6 — security review (Sana) rework

- Target criterion: C-018 … C-021
- Hypothesis: `ci-alarm` declared `permissions: issues: write` only. Declaring any scope sets the rest to `none`, so `contents: none` on a private repo means `actions/checkout` cannot clone and the job dies at step 1 — a permanently dead alarm shipped next to documentation calling it the only alarm.
- Change or investigation: confirmed the asymmetry directly (the canary had `contents: read` + `issues: write`; `ci-alarm` did not; repo confirmed `private: true`). Added `contents: read`. Added `lint-workflows` to the alarm's `needs` — it could fail on `main` and never enter the outstanding set. Added `persist-credentials: false` to both checkouts. Made both workflows' placeholder staging create-only. Added a workflow checker (now `check_workflows.py`) so this class cannot recur, since actionlint does not model it.
- Verifier executed: the workflow checker plus a mutation restoring the exact shipped defect; `actionlint` on the same mutated file; a `stage()` helper trial over a non-empty file.
- Result: the check exits 1 and names `ci-alarm`; **actionlint exits 0 on the same file**, confirming nothing else in the pipeline would have caught it. `stage()` preserves a 16-byte file that `: >` destroys.
- New evidence: the finding sat exactly where the contract was thin — C-013 verified the reconcile *logic*, never the GitHub write path. C-022 now names that gap explicitly and stays PENDING until a post-merge dispatch proves it, and `CLAUDE.md` describes the alarm as **unproven, not live** until then.
- Decision: gate-review

### Iteration 7 — QA review (Quinn) rework

- Target criterion: C-024 … C-028
- Hypothesis: the skipped-jobs fix closed one route to a false all-clear, but the outstanding set lives in a human-editable issue body with no integrity check, so the same lie is reachable by stripping the marker and then pushing something that skips the broken jobs.
- Change or investigation: made `parse_marker` distinguish **absent** (`None`) from **present-but-empty** (`set()`). An open issue with no readable marker is no longer trusted: the alarm seeds the outstanding set with every job not observed succeeding in this run, so corrupting the marker can only make the alarm stricter, never looser, and a genuinely all-green run still clears it. Added the self-test axis for a job absent from `results`. Split the operator's single `run:` into Check/Clippy/Test steps and extended `!cancelled()` to every gate step from Format onward, so C-016's property is actually achieved rather than narrowly worded. Taught the pin parser both TOML quote styles. Made the alarm dispatch-rehearsable off `main` under `DRY_RUN` (reads happen, writes are printed and withheld). Corrected two `CLAUDE.md` claims.
- Verifier executed: four targeted mutants of `ci_alarm.py`, each asserted to land and then checked against the self-test; a parsed audit of every gate step's `if:`; `--print-channel` against both quote styles and a floating value; `actionlint` and the permissions check after each edit.
- Result: **4/4 mutants caught**, including Quinn's survivor (`results.get(job, "success")`) and her second door (marker stripped). Gate-step audit reports no gate step without `!cancelled()`. Quote styles 0/0/1 as expected.
- New evidence: the `!cancelled()` claim had been *literally true and materially false* — the operator's Clippy was the middle line of one `run:` under `bash -e`, so an operator clippy failure still hid the operator's own tests. Fixed rather than reworded. Separately, `CLAUDE.md`'s "no `--no-fail-fast` anywhere" became false in this very branch (8 occurrences in the Makefile, 8 in `ci.yml`), and its "CI only compile-checks" the operator was already inaccurate — both corrected.
- Residual, stated rather than hidden: the alarm's state remains a label plus a body marker, both collaborator-editable. The fallback makes corruption fail *safe* rather than impossible; reconstructing state from run history would remove the editable surface entirely and is the stronger fix if this ever proves noisy. C-022 (post-merge proof of the write path) stays PENDING.
- Decision: gate-review

### Iteration 8 — QA delta (Quinn) + security exactness (Sana)

- Target criterion: C-030 … C-034
- Hypothesis: the previous round shut the *delete* door on marker corruption and left the *empty* door open, and the self-test asserted the defective behaviour as correct.
- Change or investigation: verified Quinn's proof against the shipped code — `if not new_outstanding:` returns and closes at line 291, before the only production `render_marker` at 323, so **the alarm can never write an empty marker onto an open issue**; an empty one is therefore always corruption, not a legitimate state. That turns Sana's accepted residual into something rejectable at no cost. One-line fix at the call site (`if not recorded`), and the self-test's assertion — which I had written to bless the defect one iteration earlier — inverted. Extracted the decision into `outstanding_from()` so the self-test drives the real rule instead of a copy of it. Hoisted the operator's staging step above the gate boundary. Replaced the hand-audited gate partition with an ordinal check. Routed `gh label create` through `gh_write`. Renamed the CI step to what it actually checks, pinned `pyyaml`, recorded the checker's known gaps.
- Verifier executed: 9 corruption shapes; a 5-mutant battery on the alarm; A/B mutation of both workflow checks against their motivating defects with actionlint run on the same files; a stub-`gh` DRY_RUN run.
- Result: **0 of 9 shapes** produce a false all-clear (was 4). **5/5 alarm mutants caught.** Both workflow checks exit 1 on their real defect while actionlint exits 0 on the same file. DRY_RUN executed **0** real writes.
- New evidence — the sharpest finding of the whole review, and it was about my verification rather than my code: `gate steps WITHOUT !cancelled(): none` could not see the stranded staging step, because my audit exempted it **by name**. The partition was hand-maintained, so the parse validated a labelling I had chosen rather than an independent property. Replaced with a purely ordinal rule that needs no list. Separately, my first attempt at pinning C-030 was itself vacuous: the self-test re-implemented the call-site rule, so reverting the real fix left it green. Caught by mutating it.
- Decision: gate-review

### Iteration 9 — Quinn's residual, folded in rather than deferred

- Target criterion: C-036, C-037
- Hypothesis: the ordinal rule matched "has no `if:`", which is the SPELLING of the defect. GitHub implies `success() &&` in front of any `if:` that calls no status function, so `if: runner.os == 'Linux'` after a gate is stranded identically and was not flagged.
- Change or investigation: the rule now flags any post-gate step whose condition invokes no status function. Chose to fold it in rather than defer it: the whole branch has been about closing classes rather than instances, and deferring the class while shipping the spelling would have been the same mistake in miniature. No live instance existed (verified), so this is prevention.
- Verifier executed: stranded a real `if: runner.os == 'Linux'` step between two gates in `ci.yml`; two mutations of the rule (revert to `not cond`, and disable outright).
- Result: checker exits 1 naming the step while actionlint exits 0 on the same file; both mutations turn the self-test red. Self-test grew to 12 cases, including a status-function conditional and an explicit `always()` after a gate, both correctly accepted.
- New evidence: none contradicting; the three legitimate shapes Quinn built are all accepted, so the rule did not gain false positives.
- Decision: complete — all four reviewers pass.

### Iteration 10 — the PR exposed a defect that had been latent for months

- Target criterion: C-038
- Hypothesis: none — this was discovered by opening the PR, which produced a red pipeline in 20 seconds.
- Change or investigation: `detect changed areas` failed with `Resource not accessible by integration` and every downstream job was skipped. `dorny/paths-filter` uses git against the merge base on a push, but on a `pull_request` it calls the GitHub API (`listFiles`), which needs `pull-requests: read`; the repository default grants only contents and packages. Granted the `changes` job `contents: read` + `pull-requests: read`.
- Verifier executed: `gh run view` on the failing run; then `gh run list --event pull_request` over the repository's history.
- Result: fixed in `f491735`. Dropping `contents` from that same block makes `check_workflows.py` flag it, which is the pairing that guard exists to enforce.
- New evidence: **this was not introduced here.** The only other PR run in the repository's history, `30718327254` on 2026-08-01, died the same way in 17s with the identical error. It went unnoticed because work is pushed straight to `main`, where paths-filter takes the git path and never calls the API — nothing had ever exercised the PR path. It is the same shape as the failure this whole goal addresses: a gate failing for months somewhere nobody was looking, found only because someone finally looked.
- Decision: complete

### Iteration 11 — the alarm rehearsed on the branch, and what it does not prove

- Target criterion: C-039 … C-042, and partial evidence toward C-022
- Hypothesis: dispatching `ci` on the branch would exercise the alarm end to end without letting it touch the real `main` issue, since `DRY_RUN` is derived from `github.ref != 'refs/heads/main'`.
- Change or investigation: dispatched run `32900486643` on `fix/ci-toolchain-drift`. The `api` and `rust` jobs failed on that run, which made it a stronger test than a clean one.
- Verifier executed: inspected job `97978166110`; then listed issues and labels on the repository to confirm nothing was actually written.
- Result: job conclusion `success`. Checkout, self-test and reconcile all passed. Output: `newly failed: ['api', 'rust']`, marker `<!-- ci-red-outstanding: api,rust -->`, and `DRY-RUN, would run: gh issue create …`. Repository afterwards: **zero issues, zero labels**.
- New evidence: this closes Sana's HIGH in production, not just in review — `actions/checkout` succeeded under the job's own `permissions` block on a private repo, which is exactly what `contents: none` had made impossible. It also confirms her item 2: `gh label create` was the one write that used to bypass `gh_write`, and it created nothing.
- **What it does NOT prove, stated so C-022 is not quietly closed:** no write was executed. `checkout` exercises `contents: read`; `issues: write` is granted but untested. The failure mode "the job cannot run" is closed; the failure mode "the write is refused" is not. C-022 stays PENDING for the post-merge dispatch on `main`.
- Decision: complete

## Risks and rollback

- Risks: the pin is a deliberate lag — new compiler and clippy releases stop arriving automatically, so the canary must actually be watched. Landing the pin will move every developer and every in-flight worktree to 1.98.0 on their next `cargo` invocation, which may surface new lints in their unmerged work.
- Rollback or recovery: delete `rust-toolchain.toml` and revert the three `toolchain:` inputs; the pipeline returns to floating stable. The source changes are independent of the pin and need no revert — they are correct on both 1.97.1 and 1.98.0.

## Pause and escalation conditions

- Any rasterizer output change, however small — stop, do not proceed (owner/architect decision).
- A reviewer raises a blocking finding — route back before any PR.
- Whether the `ci-red` alarm should also page a human channel — owner decision.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-devops-ci-toolchain-drift.md`
- Validator result: see the run recorded on ClickUp 86ak5rc9c
- Independent verification result: PASS — Cody, Vera, Sana and Quinn have all cleared the branch; every blocking finding remediated and re-checked
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-022 only (post-merge proof of the alarm's GitHub WRITE path; its execution path is now proven by run 32900486643) — non-mandatory, and unprovable pre-merge by design, since DRY_RUN withholds writes precisely so a branch cannot touch the real issue. To be closed on the first `workflow_dispatch` after merge, which also resolves the org-level workflow-permissions unknown. Owner acceptance of the collaborator-editable marker/label residual is flagged on 86ak5rc9c and is the owner's to give.
- ClickUp final evidence comment: posted on 86ak5rc9c
