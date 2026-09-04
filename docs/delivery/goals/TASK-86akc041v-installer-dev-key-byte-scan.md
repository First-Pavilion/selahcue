# Goal Contract — TASK-86akc041v

## Identity

- Goal ID: TASK-86akc041v
- Parent goal ID: EPIC-86ajp08py
- Title: The Windows installer build fails when a developer-key signature is present in a shipped artefact, and the scan proves it read a real artefact
- Role: devops-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc041v
- Created: 2026-09-04
- Updated: 2026-09-04 (review round 1 applied)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`.github/workflows/windows-installer.yml` scans the built operator binary and the bundled
installer for a declared set of developer-key signature strings, fails the build if any is
present, and fails — never passes — when it cannot prove it read a real artefact.

## Baseline

Verified at `origin/main` = `3f3072edc158310182d18910e3a7dccabfb66a08` (PR #18 merged):

- `dev-keys = []` at `selahcue-operator/Cargo.toml:40`, off by default.
- `selahcue dev-keys:` appears 3x in `dev_env.rs` (lines 365, 371, 386), behind `#[cfg(any(feature = "dev-keys", test))]`.
- `REPO_ROOT_ENV_FILE` (`dev_env.rs:134`) is `concat!(env!("CARGO_MANIFEST_DIR"), "/../../../../.env")`, gated on `#[cfg(feature = "dev-keys")]`.
- `windows-installer.yml` builds `--release` throughout; the only artefact-producing steps are
  the output window (line 119) and `cargo tauri build --features stt` (line 135).
- The workflow's lines 24-33 comment states the entitlement-key scan is deliberately NOT wired here.
- `.github/scripts/check_workflows.py` enforces two invariants over every workflow: checkout
  token scopes, and the ordinal setup/gate rule (no implicit-`success()` step after any
  `!cancelled()` step). `windows-installer.yml` uses no `!cancelled()` today.
- Precedent family: `scripts/dev_key_not_in_release.sh` + `scripts/dev_key_scan.py`; the
  `--self-test` then run pattern is established by `check_workflows.py` and `ci_alarm.py`.

### Baseline addendum — state at review round 1

Head `c18841d` + this round's fixes. **4** declared targets (operator binary, sidecar, NDI
runtime, NSIS bundle), **6** signatures x **2** encodings = 12 needles, **33** self-test cases.
The scanner's arithmetic was independently verified exhaustively in review (2,000 randomised
files across five chunk sizes, plus every needle position at nine more): zero mismatches. The
defects found in this round were all in the TESTS, not the scanner.

## Inputs and evidence sources

- ClickUp task 86akc041v (acceptance criteria and verification expectations)
- `scripts/dev_key_not_in_release.sh` header (the effect-level argument)
- `scripts/dev_key_scan.py` (positive-control-first structure, artefact-selection trap)
- `.github/scripts/check_workflows.py` (workflow invariants my edit must satisfy)
- `implementation/desktop/crates/selahcue-operator/src/dev_env.rs` @ 3f3072e (the real signatures)

## Scope

### In scope

- `scripts/installer_secret_scan.py` — new; the declared signature set, the scanner, its self-test.
- `.github/workflows/windows-installer.yml` — two steps invoking it, before artefact upload.

### Non-goals

- Any change to `dev_env.rs` or the `dev-keys` feature.
- The `Makefile` (contended; the optional local target was struck from scope).
- `ci.yml` (contended by two in-flight PRs).
- The entitlement-key scan in this workflow — structure for two, implement one.
- macOS or Linux artefacts.

### Constraints

- Own worktree, own branch cut from `origin/main` pinned by SHA; Draft PR against `main`.
- Every build step keeps `--release`.
- No file under `implementation/`.
- Runtime not materially extended.

### Assumptions and unknowns

- ASSUMED: `api.deepgram.com` and `api.openai.com` must NOT appear in the shipped operator,
  because the shipping path is a server-minted grant token and a proxied notes service
  (stated in `selahcue-operator/Cargo.toml`'s `dev-keys` comment). If a provider endpoint
  ever becomes legitimate in the shipped artefact, that is a recorded decision, not a
  string to quietly delete. Validation owner: /security-reviewer (Sana).
- UNKNOWN: the workflow is `workflow_dispatch`-only, so this control cannot be observed
  green on a real Windows runner from a PR alone. Mitigated by the self-test, which runs
  the same scanning code against synthetic artefacts on any platform.

## Dependencies and approvals

- 86akby6yy (PR #18) — MERGED at 3f3072e. Unblocked.
- Gates 86akby4yz and 86akby7d8 merge; blocks neither from starting.
- /security-reviewer (Sana) to confirm finding F5 is satisfied.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The workflow scans the built operator artefact and fails when any set member is present | `installer_secret_scan.py --self-test` case `injected_signature_is_caught` | non-zero exit naming path + string | self-test `injected_signature_is_caught` (12 pairs); real-artefact demo exit 1 naming path+string+offset | PASS |
| C-002 | yes | The scan FAILS when the artefact is missing, the glob matches nothing, or the file cannot be read — each tested | self-test cases `missing_target`, `glob_matches_nothing`, `unreadable_file` | non-zero exit for each | `missing_target`, `glob_matches_nothing`, `unreadable_file`, `target_is_a_directory` — verbatim messages in ClickUp evidence comment. NOTE: `unreadable_file` self-skips where mode 000 is not enforced (Windows), and says so loudly; `target_is_a_directory` covers the same fail-closed branch on every platform | PASS |
| C-003 | yes | The positive control proves detection for EVERY string in the set, not just one | self-test case `positive_control_covers_every_signature` | every signature x encoding asserted | `positive_control_covers_every_signature` — ADDED this round; it did not exist when this row was written. Mutation `probes[:1]` now dies by name | PASS |
| C-004 | yes | If the positive control does not fire, the build fails | self-test case `dead_matcher_fails_closed` | non-zero exit | `dead_matcher_fails_closed`; mutation M2 killed | PASS |
| C-005 | yes | Evidence in the workflow log shows a real file of non-trivial size was examined | run scanner over a real artefact | per-artefact path + byte size printed | per-artefact path, byte count and sha256 printed; 21,685,872 bytes / sha256 3c70a8b2… on the real-binary demo | PASS |
| C-006 | yes | Strings are a declared set in ONE place; adding a provider is a data change | read `SIGNATURES` table | single tuple; scanning logic references no literal | AST walk: zero signature literals in any scanning function | PASS |
| C-007 | yes | Set includes all six required strings | self-test case `required_signatures_are_declared` | all six present | `required_signatures_are_declared` + module-level count floor; shrinking BOTH lists now fires the assert | PASS |
| C-008 | yes | The scan never modifies what it reads (non-truncation) | self-test case `scan_never_mutates_the_artefact` | size + sha256 unchanged after full run incl. positive control | `scan_never_mutates_the_artefact`: 2,048,050 bytes unchanged; mutation writing in place truncates to 701 bytes and the case fails | PASS |
| C-009 | yes | Mutation-verified: nonexistent path, empty string list, zero-byte file each go RED | self-test cases + manual mutation run | non-zero exit for each | 17 mutations across two batteries, every one killed by a NAMED case | PASS |
| C-010 | yes | The script explains why this is effect-level and what it does NOT close | read script header | states the compressed-installer and runtime-loader limits | header states the literal-free runtime loader and the `SetCompressor /SOLID` compression limits | PASS |
| C-011 | yes | Lines 24-33 comment stays accurate; every build step keeps `--release` | `git diff` review | comment consistent, no `--release` removed | lines 24-33 intact and extended; both build steps keep release | PASS |
| C-012 | yes | `check_workflows.py` and `actionlint` pass on the edited workflow | both tools over `.github/workflows/` | exit 0 | actionlint 1.7.12 exit 0; check_workflows.py exit 0 | PASS |
| C-013 | yes | No `Makefile` change, no file under `implementation/` | `git diff --name-only origin/main...HEAD` | only the script, the workflow, this contract | 3 files; ci.yml and Makefile untouched; 0 under implementation/ | PASS |
| C-014 | yes | Independent review: Cody, Vera, Sana, Quinn; Sana confirms F5 | review pipeline | no unremediated blocking findings | Sana PASS (F5 confirmed); Vera PASS (measured); Cody 2 High/5 Med/8 Low — both High fixed; Quinn GATE_REVIEW — F1-F4 fixed; Cody/Quinn re-review of the fixes outstanding | PENDING |
| C-015 | yes | Every collection the suite iterates is pinned, so it cannot be silently shortened | self-test `every_required_target_is_declared`, `every_encoding_is_declared`, `every_target_has_a_size_floor`, `the_pins_themselves_have_not_shrunk`, `self_test_case_floor`, `every_glob_match_is_scanned` | each mutation dies by its named case | second mutation battery: 10/10 previously-surviving mutations killed | PASS |
| C-016 | yes | The gate runs for real on a windows-latest runner, not merely parses | dispatched `windows-installer.yml` run | both gate steps execute and report | run 33874171169 (3-target head); re-dispatch pending on final head | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/installer_secret_scan.py --self-test`; deliberate
  mutations of the scanner confirmed RED and then restored.
- Broader regression verification: `python3 .github/scripts/check_workflows.py` over all
  workflows; `actionlint` over `.github/workflows/`. No Rust or Flutter change, so `make ci`
  is not the relevant gate and is NOT run (another engineer's cargo test is active in this
  checkout; concurrent runs produce false REDs).
- Independent verifier: /security-reviewer (Sana) against finding F5.
- Required environment: macOS local for the self-test; GitHub `windows-latest` for the live gate.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 .. C-010
- Hypothesis: A chunked byte scanner over a declared signature set, with a positive control
  built from a COPY of each real artefact, satisfies the detection and read-proof criteria.
- Change or investigation: write `scripts/installer_secret_scan.py` and its self-test.
- Verifier executed: pending
- Result: pending
- New evidence: pending
- Decision: iterate

## Risks and rollback

- Risks: the workflow is dispatch-only, so the gate cannot be proven on a real Windows
  artefact from a PR; an NSIS installer compresses its payload, so a scan of `*-setup.exe`
  alone would be a weak control — the operator binary is the primary target.
- Rollback or recovery: revert the two files; the control adds no build artefacts and no
  state, so removal is complete and immediate.

## Pause and escalation conditions

- If the control appears to require a `ci.yml` or `Makefile` edit — stop and report (both contended).
- If a required signature turns out to be legitimately present in a default-feature build —
  stop; that is a security decision owned by Sana, not a set edit.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path>`
- Validator result: OK (structural)
- Independent verification result: pending
- Terminal state: GATE_REVIEW — C-014 partial (Cody/Quinn re-review pending), C-016 pending the re-dispatched Windows run
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
