# Goal Contract — TASK-86akc041v

## Identity

- Goal ID: TASK-86akc041v
- Parent goal ID: EPIC-86ajp08py
- Title: The Windows installer build fails when a developer-key signature is present in a shipped artefact, and the scan proves it read a real artefact
- Role: devops-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc041v
- Created: 2026-09-04
- Updated: 2026-09-04
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
| C-001 | yes | The workflow scans the built operator artefact and fails when any set member is present | `installer_secret_scan.py --self-test` case `injected_signature_is_caught` | non-zero exit naming path + string | self-test output | PENDING |
| C-002 | yes | The scan FAILS when the artefact is missing, the glob matches nothing, or the file cannot be read — each tested | self-test cases `missing_target`, `glob_matches_nothing`, `unreadable_file` | non-zero exit for each | self-test output | PENDING |
| C-003 | yes | The positive control proves detection for EVERY string in the set, not just one | self-test case `positive_control_covers_every_signature` | every signature x encoding asserted | self-test output | PENDING |
| C-004 | yes | If the positive control does not fire, the build fails | self-test case `dead_matcher_fails_closed` | non-zero exit | self-test output | PENDING |
| C-005 | yes | Evidence in the workflow log shows a real file of non-trivial size was examined | run scanner over a real artefact | per-artefact path + byte size printed | scanner stdout | PENDING |
| C-006 | yes | Strings are a declared set in ONE place; adding a provider is a data change | read `SIGNATURES` table | single tuple; scanning logic references no literal | script source | PENDING |
| C-007 | yes | Set includes all six required strings | self-test case `required_signatures_are_declared` | all six present | self-test output | PENDING |
| C-008 | yes | The scan never modifies what it reads (non-truncation) | self-test case `scan_never_mutates_the_artefact` | size + sha256 unchanged after full run incl. positive control | self-test output | PENDING |
| C-009 | yes | Mutation-verified: nonexistent path, empty string list, zero-byte file each go RED | self-test cases + manual mutation run | non-zero exit for each | ClickUp evidence comment | PENDING |
| C-010 | yes | The script explains why this is effect-level and what it does NOT close | read script header | states the compressed-installer and runtime-loader limits | script source | PENDING |
| C-011 | yes | Lines 24-33 comment stays accurate; every build step keeps `--release` | `git diff` review | comment consistent, no `--release` removed | PR diff | PENDING |
| C-012 | yes | `check_workflows.py` and `actionlint` pass on the edited workflow | both tools over `.github/workflows/` | exit 0 | command output | PENDING |
| C-013 | yes | No `Makefile` change, no file under `implementation/` | `git diff --name-only origin/main...HEAD` | only the script, the workflow, this contract | command output | PENDING |
| C-014 | yes | Independent review: Cody, Vera, Sana, Quinn; Sana confirms F5 | review pipeline | no unremediated blocking findings | review artifact URL | PENDING |

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

- Validator command: pending
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
