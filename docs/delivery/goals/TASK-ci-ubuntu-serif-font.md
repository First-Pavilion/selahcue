# Goal Contract — TASK-ci-ubuntu-serif-font

## Identity

- Goal ID: TASK-ci-ubuntu-serif-font
- Parent goal ID: NONE
- Title: `rust (ubuntu-latest)` runs `themes_differing_only_in_typography_never_share_a_measurement` and passes, with its positive control intact and its environmental premise stated
- Role: devops-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak643rc (Defect 1 only)
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The Linux CI runner can distinguish two typographies, so the test does real work rather than
failing its own positive control — and the requirement is declared in CI rather than inherited
from whatever the runner image happens to ship.

## Baseline

Verified on run `32896017248`, job `rust (ubuntu-latest)` (`97958849795`):

```
test themes_differing_only_in_typography_never_share_a_measurement ... FAILED
panicked at crates/selahcue-present/tests/test_measure.rs:477:5:
the serif family shapes identically to the default on this host, so the serif frame
comparisons below cannot tell a font-blind key from a correct one
test result: FAILED. 7 passed; 1 failed
```

`rust (macos-latest)` and `rust (windows-latest)` pass on the same commit. The test arrived in
`53f0032` (2026-08-23), the day the clippy failure started, so it has never executed on ubuntu CI.

## Inputs and evidence sources

- GitHub Actions job logs for run `32896017248` (rust + operator, ubuntu-latest)
- `implementation/desktop/crates/selahcue-engine/src/raster.rs` — `build_system_fs`, `attrs_for`
- `implementation/desktop/crates/selahcue-engine/tests/test_raster.rs` — the crate's own
  documented fallback behaviour (`a_missing_font_falls_back_readably_and_deterministically`)
- `fontdb-0.16.2/src/lib.rs` — `load_system_fonts` directory list per OS
- Local container reproduction on `ubuntu:24.04` (arm64) with the runner's exact font package

## Scope

### In scope

- Defect 1 of 86ak643rc: the ubuntu font failure
- `.github/workflows/ci.yml` — declaring the font requirement for the `rust` job
- `implementation/desktop/crates/selahcue-present/tests/test_measure.rs` — making the premise
  legible and actually checked

### Non-goals

- Defects 2 and 3 of 86ak643rc (`api (django)`) — owned by another agent on the same ticket
- Merging PR #2 / the clippy fix
- Opening a pull request (the owner requires review by Cody, Sana, Vera and Quinn first)

### Constraints

- Do not weaken the assertion. The environment is wrong, not the test.
- Pinned and reproducible; not "whatever apt serves today".
- Own worktree, own branch, own `CARGO_TARGET_DIR`; never `cargo clean` the primary checkout.

### Assumptions and unknowns

- ASSUMED: `windows-latest` carries Times New Roman in `C:\Windows\Fonts`. It passes today and
  the new premise check is strictly stronger, so a regression there fails closed with a named
  diagnostic rather than passing vacuously. Validated by the CI matrix when a run happens.
- UNKNOWN: whether Windows falls back to a system face (macOS behaviour) or to the bundled face
  (Linux behaviour) for an unknown family. Either way the chosen candidate is genuinely
  installed there, so the outcome is the same.

## Dependencies and approvals

- PR #2 (86ak5rc9c) must merge before any run reaches `cargo test` at all — until it does, this
  branch is evaluated against a `main` that still fails at clippy. Owner: the PR's reviewer.
- No production, destructive or credential-bearing action is involved.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The diagnosis is established empirically, not inferred | Container reproduction on `ubuntu:24.04` measuring the real engine code | Unknown family and requested family shape identically to the bundled default | `linux-probe.log` phase 1/2 | PASS |
| C-002 | yes | The test passes on macOS with the fix | `cargo test -p selahcue-present --test test_measure` | 8 passed; 0 failed | local run, exit 0 | PASS |
| C-003 | yes | The test passes on Linux once the CI font step has run | Same command in `ubuntu:24.04` after `fonts-liberation=1:2.1.5-3` | 8 passed; 0 failed | phase B, exit 0 | PASS |
| C-004 | yes | The test still FAILS CLOSED on a host with no usable serif, naming the faces it looked for | Same command in `ubuntu:24.04` with no fonts installed | 1 failed, message names all four candidates and the fix | phase A, exit 101 | PASS |
| C-005 | yes | The premise is checked, not assumed: a nonsense family name cannot satisfy it | `installed_serif`'s `resolved` condition vs `NO_SUCH_FAMILY` | A nonsense name is rejected on every OS | `test_measure.rs` `installed_serif` | PASS |
| C-010 | yes | The font/weight contract stays guarded on a host with NO fonts, so the pinned package restores a layer rather than holding the contract up | `cargo test -p selahcue-present --test test_measure` on a bare `ubuntu:24.04`, unmutated and with a font-blind `measure::Key` | Unmutated 7 passed/1 failed; mutated 6 passed/2 failed — `every_shaping_attribute_is_part_of_the_cache_key` passes then goes RED | `guarded2.log` | PASS |
| C-006 | yes | The font requirement is DECLARED in CI and its arrival ASSERTED, on any runner image | Run the step verbatim on `ubuntu:24.04` and `ubuntu:26.04` | Install succeeds and the `test -f` passes on both, despite different package versions and different .ttf bytes | `lin-2404.log` / `lin-2604.log` | PASS |
| C-011 | yes | Each half of the selection predicate is exercised, not merely present | Mutation battery: drop `resolved`, then drop `distinct`, siblings running | Both go RED | battery C and D, exit 101 each | PASS |
| C-007 | yes | Formatting and lint gates stay green | `cargo fmt --check`, `cargo clippy --workspace --all-targets -- -D warnings` | exit 0 | `rustci.log` EXIT=0 for all 6 fmt/clippy gates | PASS |
| C-008 | yes | No other CI runner or backend carries the same latent gap, or it is reported | Read GPU parity + Windows/macOS test paths | GPU parity renders `Layer::Fill` only — no text, no font dependency | `selahcue-gpu/tests/test_parity.rs` | PASS |
| C-009 | yes | Every Rust/operator gate of `make ci` passes | 16 gates run individually with exit codes captured | TOTAL_FAILING_GATES=0 | `rustci.log` + `opci.log` | PASS |

## Verification plan

- Focused verification: the single test, on macOS and in a Linux container in both font states.
- Broader regression verification: every Rust and operator gate of `make ci`, each run separately with its exit code captured (never piped). The Flutter leg was deliberately NOT run locally: another agent was mid-Flutter/SwiftPM work and concurrent `flutter test` in this shared checkout is a documented false-red (CLAUDE.md). This change touches no mobile file, and the `ci.yml` edit puts this branch in the **mobile** path filter, so `flutter controller` runs on the PR — the leg is covered there rather than left as a gap. `rust (windows-latest)` likewise settles the Windows premise on the PR run. Both should be READ on that run, not assumed from the trigger.
- Independent verifier: Cody, Vera, Sana and Quinn per the review pipeline; then a CI run once
  a PR is opened by the owner.
- Required environment: macOS host; `ubuntu:24.04` container standing in for `ubuntu-latest`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: the runner has no distinct serif face, per the ticket.
- Change or investigation: read the real job log; read the operator job's apt output for what
  the base image already carries; reproduced in a container.
- Verifier executed: `gh run view --job ... --log`; container probe of the real engine code.
- Result: hypothesis REFUTED in two places, and the refutation changed the fix.
- New evidence: (a) the runner already has `fonts-liberation 1:2.1.5-3`, so it does have a
  distinct serif; the test simply hard-codes `Times New Roman`, which is absent, and Linux's
  fallback for an absent family is the bundled Noto Sans itself. (b) The positive control never
  checked installation at all: on macOS a nonsense family name satisfies it, because macOS falls
  back to a system UI face that differs from the bundled font. Installing a serif alone leaves
  the test red — verified in phase 2 of the container probe, where `Times New Roman` is still
  `widths_move=false` with Liberation Serif present.
- Decision: iterate — the fix needs both a declared font AND a premise that is actually checked.

### Iteration 2

- Target criterion: C-002 … C-009
- Hypothesis: choosing the serif from an explicit candidate list, gated on "it resolved" and
  "it differs from the bundled default", passes everywhere a usable face exists and fails
  closed with a named diagnostic where none does.
- Change or investigation: `installed_serif` + `SERIF_CANDIDATES` + `NO_SUCH_FAMILY` in the
  test; a pinned `fonts-liberation` step with a file assertion in ci.yml.
- Verifier executed: see the completion predicate.
- Result: recorded per row above.
- Decision: handoff to review.

### Iteration 3

- Target criterion: the coordinator's challenge to re-derive "this test has never run on ubuntu CI" from the run records rather than from the claim.
- Hypothesis: the claim might be wrong; the test may have passed on ubuntu and later regressed, which would point at a different fix.
- Change or investigation: enumerated every `ci.yml` run since 2026-08-20 and pulled the
  step-level conclusions of each `rust (ubuntu-latest)` job.
- Verifier executed: `gh api repos/:owner/:repo/actions/runs/<id>/jobs`, plus
  `git merge-base --is-ancestor 53f0032 <head_sha>`.
- Result: claim CONFIRMED, and the reason is stronger than stated. The test landed in 53f0032
  (2026-08-23 11:42:20 UTC). That commit never received a run of its own — it was pushed in a
  batch whose tip was f75c2576. In all five subsequent `main` runs (32637352346, 32637406933,
  32712283681, 32723339463, 32821185981) the `rust (ubuntu-latest)` job ran, `Clippy (default
  features)` failed, and `Test (workspace ...)` was **skipped**. The test's first and only
  execution on ubuntu is run 32896017248, where it failed. It has never passed there, so this
  is a first-run fix and not a regression.
- New evidence: separately corroborated the coordinator's correction about the "last green
  main" — run 31978969262 (2026-08-16) had `flutter controller`, `marketing (vue spa)` and
  `api (django)` all SKIPPED. `rust (ubuntu-latest)` did genuinely pass in it, but the test did
  not exist yet.
- Decision: handoff — the diagnosis and the fix are unchanged by the re-derivation.

### Iteration 5

- Target criterion: C-011 and a revised C-006, both raised by code review (Cody), not by a gate.
- Hypothesis (MEDIUM 1): the `resolved` condition this fix ADDS is itself an unexercised
  control — the repository's own bar ("assert the hostile case is refused AND the benign case
  still exercises the code") applied to the fix rather than to the thing it fixes.
- Change or investigation: added a control asserting an uninstalled family is refused, then
  mutation-checked it.
- Result: **the first fix was itself dead.** Dropping `resolved` from the loop left the file
  green, because the control RE-WROTE the predicate instead of SHARING it. Corrected by giving
  the predicate — including the conjunction — a single definition (`verdict`) consumed by both
  the control and the loop. Two further consequences: the control needs a SECOND impossible
  family (feeding it the sentinel the fallback was measured from reduces to `fallback !=
  fallback`, a tautology); and with `resolved` guarded, `distinct` was then in exactly the same
  unexercised position, so a second control using the bundled family name now covers it.
- Verifier executed: mutation battery, siblings running, never `--exact`.
- New evidence: A (font-blind, BOTH sites) 101; B (weight-blind) 101; C (`resolved` dropped)
  101; D (`distinct` dropped) 101; baseline and restore 0. C and D were both GREEN before this
  iteration.
- Hypothesis (MEDIUM 2): the exact apt version pin is dated and pins the wrong thing.
- Result: CONFIRMED and fixed. `ubuntu:24.04` carries `1:2.1.5-3`, `ubuntu:26.04` carries
  `1:2.1.5-3build1`, and the two ship DIFFERENT .ttf bytes (sha256 `705903ae…` vs `350f4ffd…`),
  so the version string never pinned the face the test measures. `ubuntu-26.04` is already a
  preview runner label and `-latest` migrates gradually, so the same commit could land on either
  image and the pinned half would die with "Version … not found" — a failure that blocks
  everyone, not just this branch. Dropped the version; kept the `test -f`, which asserts the
  actual contract. Verified by running the step verbatim on both images: install and file
  assertion pass on each, and the suite passes on each (8 passed, exit 0), while the font-less
  phase still fails closed with the named diagnostic (exit 101).
- Decision: handoff — re-review.

### Iteration 4

- Target criterion: C-010, raised from the mutation results rather than from a failing gate.
- Hypothesis: the mutation catch landing at test_measure.rs:608 — the portable key-level block —
  might mean the serif install restores a LAYER rather than holding the cache-key contract up.
  If so, both this contract and the ticket described the change's value incorrectly, and the
  difference is not academic: it changes how someone weighs keeping a version-pinned apt package.
- Change or investigation: rather than infer it from macOS runs (where fonts exist), ran the
  suite on a bare `ubuntu:24.04` with ZERO fonts installed, unmutated and with a font-blind
  `measure::Key`.
- Verifier executed: `cargo test -p selahcue-present --test test_measure` in-container, twice.
- Result: hypothesis CONFIRMED. Unmutated: 7 passed / 1 failed —
  `every_shaping_attribute_is_part_of_the_cache_key` PASSES with no fonts at all; only the
  typography test fails, by design, with its named diagnostic. Mutated font-blind: 6 passed /
  2 failed — that same sibling test goes RED. So the contract is guarded on a font-less host.
- New evidence: the pinned font package RESTORES the layout-level check (the one proving a
  font-blind key changes a composed frame, not merely a cache entry). It is not what makes the
  test valid. Corrected in the ci.yml comment, the `installed_serif` doc, this contract and the
  ClickUp ticket.
- Decision: handoff — the fix is unchanged; only the claim about what it buys was wrong.

## Risks and rollback

- Risks: `.github/workflows/ci.yml` is also edited by PR #2 in the same region; a textual
  conflict is expected at the `Linux system deps` → `Format` boundary. Resolution is additive —
  keep PR #2's `if: ${{ !cancelled() }}` gating and comment, and keep this new setup step. The
  new step is a SETUP step and deliberately keeps the default `success()` condition, which is
  the convention PR #2 establishes for setup steps.
- Rollback or recovery: both changes are self-contained and revert cleanly; reverting restores
  the previous (red) state without affecting any other job.

## Pause and escalation conditions

- If the pinned package version is unavailable on a future runner image, the install step fails
  loudly and the fix is a one-line version bump — no escalation needed.
- If Windows ever loses Times New Roman, the test fails with a named diagnostic; add a Windows
  candidate or a font step by the same pattern.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-ci-ubuntu-serif-font.md --completion`
- Validator result: OK
- Independent verification result: PENDING — Cody, Sana, Vera and Quinn have not yet reviewed; no CI run is possible on this branch until it targets `fix/ci-toolchain-drift` and a PR is opened, which the owner has reserved until after review
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none; C-008's Windows half is ASSUMED rather than verified (no Windows host available here) and will be settled by the CI matrix
- ClickUp final evidence comment: https://app.clickup.com/t/86ak643rc (comment 90130311173882)
