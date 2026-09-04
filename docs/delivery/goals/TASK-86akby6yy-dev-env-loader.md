# Goal Contract — TASK-86akby6yy

## Identity

- Goal ID: TASK-86akby6yy
- Parent goal ID: NONE
- Title: The operator reads developer AI provider keys from the repo-root `.env` in developer builds only, and a default build cannot read a key file at all.
- Role: backend-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby6yy
- Created: 2026-09-04
- Updated: 2026-09-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A developer who puts `DEEPGRAM_API_KEY` and `OPENAI_API_KEY` in the repo-root `.env` and builds
the operator with `--features dev-keys` finds both readable as ordinary process environment
variables. A build without that feature does not read `.env` at all, and a key file sitting on the
machine has no effect on it.

## Baseline

Verified against `origin/main` at `cb006fc6ce12df1f03341203c3894da2c6c57429`, 2026-09-04:

- The repo-root `.env` exists and is 0 bytes. `.gitignore` line 9 ignores `.env`, line 10 ignores
  `.env.*` — which also ignores `.env.sample`, confirmed with
  `git check-ignore -v .env.sample` → `.gitignore:10:.env.*`.
- Nothing in the repository reads `.env`. `grep` over `implementation/`, `scripts/`, `.github/`
  and `docs/` finds no `DEEPGRAM`, no `OPENAI`, and no `dotenv` in any manifest.
- The only environment reads in the operator are `SELAHCUE_STT_MODEL` /
  `SELAHCUE_STT_MODEL_SHA256` (`src/listening.rs:318`, `src/main.rs:1010`) and
  `SELAHCUE_CLOUD_URL` (`src/main.rs:2723`, behind `#[cfg(feature = "cloud-live")]`). The last of
  these is the house pattern this work follows.
- The operator crate is excluded from the desktop workspace and is its own workspace root with its
  own `Cargo.lock`. `make ci` reaches it through `cargo check`/`cargo clippy --all-targets`/
  `cargo test` on its manifest, all with **default features**.
- `scripts/dev_key_not_in_release.sh` documents that a **runtime configuration loader** is the one
  route its byte scan cannot close, and that "no config loader in this crate" is a review-enforced
  rule for `selahcue-licensing`. That is a constraint on this work, not a precedent for it.
- Toolchain is pinned at 1.98.0 (`rust-toolchain.toml`); `rustc --version` confirms 1.98.0.

## Inputs and evidence sources

- ClickUp 86akby6yy, including Diego's amendment comment of 2026-09-04 (frozen FE↔BE contract).
- ClickUp 86akby4yz (Deepgram lane) and 86akby7d8 (OpenAI notes lane) — the two consumers.
- Repository `CLAUDE.md`, in particular "Bounded-memory tests" and the `make ci` masking notes.
- `scripts/dev_key_not_in_release.sh`, `scripts/dev_key_scan.py`.
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (`cloud_base_url`, `fn main`).

## Scope

### In scope

- A new `dev_env` module in the operator carrying all the logic.
- An off-by-default Cargo feature `dev-keys` that alone compiles the file read.
- Two variables, `DEEPGRAM_API_KEY` and `OPENAI_API_KEY`, exposed as ordinary process
  environment variables.
- A startup report that names missing variables and can never carry a value.
- `.env.sample` with names and no values, plus the one `.gitignore` negation that lets it be
  committed.
- One `Makefile` line so the feature-enabled tests are gated locally.

### Non-goals

- Any use of either key — 86akby4yz and 86akby7d8 own that.
- Any change to `cloud_base_url()`, the `cloud-live` feature, `providers_view`, the nine
  `providers_*` commands, the four error codes, `dist/`, or `settings.js`.
- Any change to `selahcue-core/src/providers.rs`. `build_note_request` stays the single egress
  choke point and consent still gates egress.
- Server-side or production secret handling. This never runs in a shipped build.
- A `.github/workflows/ci.yml` change to run the feature-enabled suite in CI. Noted as a residual
  gap under 86ak5rjh7 rather than silently expanded into here.

### Constraints

- Never work on a protected branch; own worktree, own branch, Draft MR against `main`.
- The shared checkout holds other sessions' uncommitted WIP: nothing outside the worktree is
  committed, staged, stashed or reverted.
- `make ci` must be serialised against other agents (Flutter iOS ephemeral-dir collision).
- No `CARGO_TARGET_DIR` shared between the worktree and the main checkout.
- A test that names a control must fail when that control is removed, verified by mutation with
  siblings running.

### Assumptions and unknowns

- ASSUMED: `DEEPGRAM_API_KEY` and `OPENAI_API_KEY` are the names both lanes will read. Basis: the
  ticket says third-party credentials take the third party's own name, and these are Deepgram's
  and OpenAI's documented variable names. Validation owner: the two lane tickets; stated
  explicitly in the MR and the ClickUp handoff so either lane can object before building on it.
- VERIFIED: the repo-root `.env` is empty today, so every criterion below is met against
  absent/placeholder values rather than real keys.

## Dependencies and approvals

- 86akby4yz (Deepgram) and 86akby7d8 (OpenAI notes) both depend on this task — ClickUp dependency
  records confirm `depends_on: 86akby6yy` for both. Neither may start its own env plumbing.
- No approval needed beyond the four-reviewer gate.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | With `dev-keys` on and both keys in a `.env`, both values are readable via `std::env::var` | `cargo test --manifest-path .../selahcue-operator/Cargo.toml --features dev-keys` | exits 0; both-keys test passes | `make ci` line 3463; `dev_env::tests::enabled::a_dev_keys_build_makes_both_variables_readable ... ok` | PASS |
| C-002 | yes | With `dev-keys` off, a `.env` holding a key is not read and the variable is not set | `cargo test --manifest-path .../selahcue-operator/Cargo.toml` | exits 0; disabled test passes | `make ci` line 3379; `a_build_without_dev_keys_does_not_read_a_key_file ... ok` | PASS |
| C-003 | yes | C-002's test bites: un-gating the loader turns it red | mutation M1 — delete the `cfg(not(feature))` no-op, un-gate the real `load_from`, whole suite | test FAILS; restored tree passes | mutation battery M1 = KILLED by the named test; tree restored byte-identical | PASS |
| C-004 | yes | The feature is off by default and no `.env` read is compiled into a default build | build both binaries, capture each before the next build, scan for four strings | all four present in the dev-keys build (positive control), all four absent from the default build | repo-root `.env` path, `selahcue dev-keys:`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY` — present/absent as expected; sha256 differ | PASS |
| C-005 | yes | A missing key produces a startup line naming that exact variable | `the_startup_lines_name_the_missing_variable_and_carry_no_value`; mutation M6 | line names the exact variable; M6 turns it red | test ok in `make ci`; M6 = KILLED | PASS |
| C-006 | yes | No key value reaches a startup line or any `Debug` rendering | `the_startup_lines...` + `the_plan_debug_rendering_carries_names_but_no_values` | probe value absent from both; variable name present | both ok in `make ci` | PASS |
| C-007 | yes | C-006 bites: replacing the redacting `Debug` with a derive turns it red | mutation M2 — `#[derive(Debug)]` on `Plan`, whole suite | test FAILS; restored tree passes | M2 = KILLED by the named test | PASS |
| C-008 | yes | Only the two allowlisted names are ever taken from the file | `only_the_allowlisted_names_are_taken_from_the_file` | only `DEEPGRAM_API_KEY` planned, bound to its own line's value; parser proven to have understood the rejected lines | test ok in `make ci`; assertion strengthened mid-work to pin the name-to-value binding after M3b exposed a names-only hole | PASS |
| C-009 | yes | C-008 bites: removing the allowlist filter turns it red | mutations M3a (widen the allowlist) and M3b (unbind name from line), whole suite | test FAILS in both; restored tree passes | M3a = KILLED, M3b = KILLED | PASS |
| C-010 | yes | A blank or whitespace-only value leaves the variable unset, never set to empty | `a_blank_or_whitespace_value_leaves_the_variable_unset`; mutation M4 | not planned, reported missing; M4 turns it red | test ok in `make ci`; M4 = KILLED | PASS |
| C-011 | yes | An already-exported variable is not clobbered by `.env` | `an_already_exported_variable_is_not_clobbered_by_the_file`; mutation M5 | nothing planned for that name; M5 turns it red | test ok in `make ci`; M5 = KILLED | PASS |
| C-012 | yes | `.env` stays gitignored and unstaged; `.env.sample` is committed and holds no value | `git add --dry-run` on `.env`, `.env.local`, `.env.sample`; `git status`; `cat .env.sample` | `.env` and `.env.local` refused as ignored; `.env.sample` addable; sample holds two bare `NAME=` lines | `.env` absent from `git status`; main checkout's `.env` still 0 bytes, mtime unchanged; no 20+ char token in the sample | PASS |
| C-013 | yes | The module's own docs state this is temporary and name the replacements | review of `dev_env.rs` header | names server-minted Deepgram tokens (`POST /v1/stt/session`) and the proxied notes service | module doc lines 3-17 | PASS |
| C-014 | yes | The frozen FE↔BE contract is untouched and `dist/` is diff-clean | `git diff --cached --name-only origin/main` filtered for `dist/`, `settings.js`, the 9 commands, 11 fields, 4 error codes | no matches | diff is 912 insertions / 0 deletions across 7 files; `selahcue-core` and `selahcue-cloud` untouched | PASS |
| C-015 | yes | `make ci` passes end to end on the branch | `make ci` | final line ALL GREEN, exit 0 | `MAKE_CI_EXIT=0`; `== local Rust/Flutter gate: ALL GREEN ==`; ran to completion through the Flutter tail (223 mobile tests) | PASS |
| C-016 | yes | Branch is cut from `origin/main`, not behind it, and the MR is a Draft against `main` | `git merge-base --is-ancestor origin/main HEAD`; `gh pr view` | ancestor check passes; PR is Draft, base `main` | branch `feat/86akby6yy-dev-env-loader` cut from `cb006fc` | PASS |
| C-017 | yes | The allowlist holds at the **write boundary**, not only in `plan` | Probe A — widen the write loop in `load_from` to export every assignment, keeping "exported wins" and the blank-value rule; whole suite, siblings, no `--exact` | suite RED via a test asserting on the process environment | `no_unallowlisted_name_reaches_the_process_environment` red: "AWS_SECRET_ACCESS_KEY was exported into the process environment from a .env file…". Pre-fix reproduction was green 81/81, confirming the finding | PASS |
| C-018 | yes | A NUL-bearing value is treated as missing, so `set_var` cannot panic and print the credential | Probe C — remove the NUL guard; whole suite, siblings | suite RED; the removed guard's absence is observable | `a_nul_bearing_value_is_not_treated_as_a_key` and `a_nul_bearing_value_does_not_panic_and_is_not_exported` both red. Panic text observed under mutation embeds the whole value: ``failed to set environment variable `"DEEPGRAM_API_KEY"` to `"dev-env-loader-probe-4a91c7\0tail"`: file name contained an unexpected NUL byte`` — F2 confirmed empirically | PASS |
| C-019 | yes | Widening `LOADABLE` is caught at both layers | Probe B — add an entitlement-style name plus its compile-time pin; whole suite, siblings | suite RED, including the new write-boundary test | ten tests red, among them `no_unallowlisted_name_reaches_the_process_environment`: "the allowlist changed. NEVER_EXPORTED below is hard-coded and cannot see a newly admitted name…" | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the `dev_env` unit tests, in both feature states, plus the four mutation
  runs (C-003, C-007, C-009, and the blank-value/clobber guards spot-checked the same way). Every
  mutation run executes the whole module's tests, never `--exact`, because a control that passes
  in isolation and misses with siblings running is a known trap in this repo.
- Broader regression verification: the full `make ci` target, run to completion rather than
  trusting an early green line, since the target aborts at the first failing recipe line.
- Independent verifier: the four-reviewer gate — Cody, Vera, Sana, Quinn. Sana's read matters most
  here: this is credential handling and it deliberately introduces the runtime config loader that
  `scripts/dev_key_not_in_release.sh` names as its open bypass route.
- Required environment: macOS, Rust 1.98.0 as pinned, Flutter for the `make ci` tail.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-014 (the implementation as one coherent increment).
- Hypothesis: a `cfg`-split `load_from`, an allowlist of exactly two names, and a report typed to
  hold `&'static str` only will satisfy the whole predicate without touching any contended surface.
- Change or investigation: new `src/dev_env.rs`; two hunks in `main.rs`; one feature in
  `Cargo.toml`; `.env.sample`; one `.gitignore` negation; one `Makefile` line.
- Verifier executed: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings` in both
  feature states, `cargo test` in both feature states, an 8-mutation battery, a two-binary string
  scan with a positive control, and the full `make ci`.
- Result: every mandatory criterion PASS. `make ci` exit 0, ALL GREEN, run to completion.
- New evidence: the allowlist control was initially weaker than it read — it asserted the set of
  planned NAMES only, so mutation M3b (stop matching the name when picking a line, which lets
  `AWS_SECRET_ACCESS_KEY`'s value be exported as `DEEPGRAM_API_KEY`) survived it. Every fixture
  value is now distinct and the assertion pins the name-to-value binding; M3b is killed.
- Decision: complete

### Iteration 2 — remediating Sana's review of PR #18

- Target criterion: C-017 and C-018 (added below for the two findings).
- Hypothesis: the allowlist was pinned only at the pure `plan` layer, so nothing asserted what
  actually crosses `std::env::set_var`; and `set_var` panics on a NUL-bearing value with the whole
  value in the message, which with live credentials in `.env` would print a real secret.
- Change or investigation: **reproduced the finding before fixing it.** My first reproduction was
  blunter than Sana's — it dropped "an exported variable wins" as well, so a different test caught
  it and the suite went red for the wrong reason. Isolating the allowlist alone, keeping
  "exported wins" and the blank-value rule exactly as they were, reproduced Sana's result
  precisely: **81/81 green, exit 0**, with every non-allowlisted assignment in the file exported.
  The finding is real and was confirmed independently rather than taken on trust.
- Then: added `no_unallowlisted_name_reaches_the_process_environment`, which asserts on
  `std::env::var_os` after the real `load_from` and never looks at a `Plan`; added a NUL guard in
  `plan` with tests at both the pure and process-environment layers; and pinned the allowlist
  premise both at compile time beside `LOADABLE` and inside the new test.
- Verifier executed: three probes, each run against the whole crate suite with siblings and never
  `--exact`, each restored and re-confirmed green afterwards.
- Result: all three killed. See C-017/C-018.
- New evidence: **two things I got wrong and corrected.**
  1. `NEVER_EXPORTED` is hard-coded, which is deliberate — deriving it from `LOADABLE` would make
     it shrink exactly when the allowlist widened. But that left the new test blind to a widening
     that admitted a name the fixture never mentions, so the premise is now pinned explicitly.
  2. The in-test pin was first written as `assert_eq!` between two fixed-size arrays, which is a
     **type error** under widening, not an assertion failure — so the message written for whoever
     widens the allowlist would never have printed. Comparing slices instead makes it a real red
     with the explanatory text. Probe B went from "RED, no test named" to killing ten tests,
     including the new one.
- Decision: complete

## Risks and rollback

- Risks:
  - The loader is exactly the shape `scripts/dev_key_not_in_release.sh` warns about. Mitigated by
    the two-name allowlist, by living in the operator binary rather than in any library crate, and
    by never being compiled at all without the feature — but it is the reviewers' call, not mine.
  - `std::env::set_var` is process-global. Safe here because it runs as the first statement of
    `main()` before any thread exists; the tests that touch process env are in mutually exclusive
    `cfg` blocks so they never run in the same binary.
  - Baking `CARGO_MANIFEST_DIR` into the binary leaks the build machine's source path — another
    reason a `dev-keys` build must never ship, stated in the module docs.
- Rollback or recovery: the whole change is additive and behind an off-by-default feature.
  Reverting the branch restores the tree exactly; nothing persists and no data migrates.

## Pause and escalation conditions

- If either lane objects to the variable names, stop and re-agree them before they build — owner
  is whichever lane objects.
- If a reviewer judges the loader an unacceptable widening of the licensing dev-key bypass, stop:
  that is a security verdict, owned by Sana, not by this role.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py
  docs/delivery/goals/TASK-86akby6yy-dev-env-loader.md --completion`
- Validator result: (recorded on the run below)
- Independent verification result: PENDING — the four-reviewer gate (Cody, Vera, Sana, Quinn) has
  not run. Sana's read is the one that matters: this deliberately, narrowly reintroduces the
  runtime-config-loader shape that `scripts/dev_key_not_in_release.sh` names as its open bypass
  route, and whether the narrowing is sufficient is a security verdict owned by that role.
- Terminal state: GATE_REVIEW — the implementation predicate is satisfied and the work is ready
  for review, but `VERIFIED_COMPLETE` requires the four-reviewer gate, which this role does not
  own and must not self-certify.
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: posted on 86akby6yy at handoff to QA.
