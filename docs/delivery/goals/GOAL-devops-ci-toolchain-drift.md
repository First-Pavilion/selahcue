# Goal Contract — GOAL-devops-ci-toolchain-drift

## Identity

- Goal ID: GOAL-devops-ci-toolchain-drift
- Parent goal ID: BUILD-selahcue
- Title: `main`'s pipeline is green again, and the local gate and CI provably compile with the same pinned Rust toolchain
- Role: devops-engineer
- Status: GATE_REVIEW
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
| C-013 | yes | The four reviewers have reviewed and blocking findings are cleared | Cody, Vera, Sana, Quinn (+ Codex counterparts) | no unresolved blocking findings | ClickUp 86ak5rc9c comments | PENDING |

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
- Independent verification result: PENDING — four-reviewer gate not yet run
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-013 (independent review) PENDING
- ClickUp final evidence comment: posted on 86ak5rc9c
