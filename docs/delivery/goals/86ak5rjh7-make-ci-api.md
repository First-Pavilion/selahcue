# Goal Contract — 86ak5rjh7-make-ci-api

## Identity

- Goal ID: 86ak5rjh7-make-ci-api
- Parent goal ID: NONE
- Title: `make ci` verifies the Django API (API half of 86ak5rjh7): a failing API test or a model without a committed migration fails it, it never installs, and what it cannot run locally is stated
- Role: devops-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5rjh7
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Running `make ci` (or `make api-check` alone) in a checkout exits non-zero when an `implementation/api` test
fails or a Django model changed without a committed migration, in a fresh worktree after one deliberate
`make api-install`. Neither target ever installs anything; `api-check` refuses, naming `make api-install`,
when the venv is missing, not ours, a symlink, built with another interpreter or from another checkout, or
older than `pyproject.toml`'s content. What the local run cannot cover (the Postgres- and Redis-only tests)
is named in the target's help text, the Makefile and `CLAUDE.md`.

This covers the API half of ticket 86ak5rjh7 only. The ticket stays open for the criteria listed under
Non-goals (17tnw2b9aaw, 17tnw2b9aax).

## Baseline

**Verified** on `origin/main` at `f176db35`:

- `make ci` ran nothing for `implementation/api`. The Makefile header and `CLAUDE.md` both said so.
- CI's `api (django)` job (`.github/workflows/ci.yml`, job `api`) runs `manage.py check`,
  `makemigrations --check --noinput` and `pytest tests -q` against Postgres 16 and Redis 7.
- The marketing half of the ticket is already done: `make marketing-check` exists and `make ci` calls it.
- `implementation/api/README.md` told readers to use `/private/tmp/selahcue-api-venv`, a path that exists on no
  other machine. The main checkout's `implementation/api/venv` is an editable install of the MAIN checkout.
- `implementation/api/pyproject.toml` had no `[build-system]` table, so pip built the editable install with
  whatever setuptools was newest on PyPI. The API has no lockfile (ClickUp 17tnw2az0kw).
- `selahcue-stt` is referenced by no CI job and no `make ci` line (grep of `ci.yml` and the Makefile: only comments).
- `make ci` aborts at its first failing recipe line.
- System `python3` is 3.9.6; the API needs Python >=3.12 and CI pins 3.14. `/opt/homebrew/bin/python3.14` exists.

## Inputs and evidence sources

- ClickUp 86ak5rjh7 (description, acceptance criteria, all comments), 86akc2kmh (fresh-worktree clause, complete)
- Root `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml` (job `api`, path filters), `implementation/api/Dockerfile`, `.github/dependabot.yml`
- `implementation/api/pyproject.toml`, `pytest.ini`, `.gitignore`, `.dockerignore`, `selahcue_api/settings.py`
- `scripts/check_launch_reachability.py`, `scripts/check_dependency_audit_coverage.py` (guards that read the Makefile)
- Round 1 reviews of PR #216 (Cody, Shadow) and the owner's decision below
- Owner requirement 2b (happy paths and edge cases, each test able to fail)

## Scope

### In scope

- `make api-install` (the one step that installs) and `make api-check` (system checks, migrations committed, pytest, on SQLite, never installs, refuses an untrustworthy venv); `scripts/api_venv.py` holds the logic.
- `make ci` calls `api-check`.
- An exact `setuptools` pin in `implementation/api/pyproject.toml`'s `[build-system]` (owner-conditioned interim).
- The Makefile header, the targets' help text, `CLAUDE.md` and `implementation/api/README.md` state what is and is not covered, and what the install does and does not guarantee.
- `scripts/check_api_gate.py`: self-test of the targets' logic, a comparison with `ci.yml`'s `api` job, and a mutation proof.
- Linked follow-up tickets for the acceptance criteria not in this PR.

### Non-goals

- Running Postgres or Redis locally (CI's job does; the ticket criteria accept naming the limit).
- Changing `.github/workflows/ci.yml` (the Linux-only policy and billed minutes; the criteria do not require it).
- `selahcue-stt` lint and tests, run-every-gate-and-report restructure of `make ci`, path-aware dispatch: follow-ups 17tnw2b9aaw and 17tnw2b9aax.
- A hash-locked requirements file and `--require-hashes`: ClickUp 17tnw2az0kw.
- A minimum-tests-ran floor in both gates, one case list instead of three in the script, moving the self-test into the workflow-lint job: filed by the orchestrator.
- The fresh-worktree sidecar clause: done by 86akc2kmh.

### Constraints

- Never write the virtualenv into a tracked path; it must install from the tree it runs in, under a name no developer's own venv uses.
- Never skip silently. `make ci` and `make api-check` never install. No new CI minutes.
- `make -n ci` stays a clean preview; `scripts/check_launch_reachability.py` stays green.

### Assumptions and unknowns

- ASSUMED: developers have Python 3.14 (CI's and the dev interpreter) or can set `API_PYTHON`. Validation owner: reviewers; the failure message names the fix.
- ASSUMED: a desktop-only change paying for the API gate until 17tnw2b9aax adds path-aware dispatch is acceptable.
- VERIFIED: the CI job's three commands are written in both the Makefile and `ci.yml`; the self-test compares them (with an explicit allow-list: `-rfEs`), so a change to one that is not made to the other fails `make ci`. `ci.yml` itself is not changed.
- VERIFIED: the `setuptools==84.0.0` pin builds the editable install on Python 3.14 (`make api-install` from scratch). The CI job's `pip install -e ".[dev]" "psycopg[binary]>=3.2,<4"` and the Dockerfile's `pip install -e ".[dev]" ...` read the same file; neither was run here (CI has not run this branch; no image was built).

## Dependencies and approvals

- Owner acceptance, recorded 2026-10-24, in the owner's words: "Accept the unlocked-install risk on #216 until 17tnw2az0kw lands. Apply the interim fixes (exact setuptools pin, honest wording) and record the acceptance on the ticket." Scope of the accepted risk: the install is unlocked and unhashed for transitive dependencies (and, before this change, the build backend); the venv holds whatever resolved on the day `make api-install` ran while CI re-resolves each run, so the two can differ; `pip install` runs with the developer's unscrubbed environment. It ends when the hash-locked requirements file of 17tnw2az0kw lands. The orchestrator records it on ClickUp.
- No production, secret or infrastructure change.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | In a fresh worktree `make api-check` refuses with `make api-install` named, installs nothing and runs nothing; after `make api-install` it passes | `make api-check`, `make api-install`, `make api-check` in the worktree | exit 2 then 0 then 0; pass, skip and xfail counts printed by pytest | PR description | PASS |
| C-002 | yes | A failing API test makes the gate exit non-zero and names the test | append a failing test to `tests/test_foundation_contract.py`, run `make api-check`, revert | non-zero exit; the test named in the `FAILED` summary line | PR description | PASS |
| C-003 | yes | A model field without a migration makes the gate exit non-zero before pytest | add a field to `CustomerOrg`, run `make api-check`, revert | non-zero exit at `makemigrations --check`, naming the missing migration | PR description | PASS |
| C-004 | yes | The gate refuses a venv from another checkout, a symlink, a changed `pyproject.toml`, a changed interpreter and an unfinished install, with an actionable message, and does not refuse a content-neutral `touch` | self-test cases for each, real `pyproject.toml` edit on the real API | each refusal exits non-zero naming `make api-install`; the touch passes | PR description | PASS |
| C-005 | yes | The targets never run on or clear what is not theirs: a developer's own `.venv` and any directory without the marker are untouched; overrides on the command line change nothing; two installs do not overlap | self-test cases | all pass | PR description | PASS |
| C-006 | yes | Missing, empty, old and hostile interpreter values fail loudly; an interpreter path with spaces works; a failed install or rebuild leaves no stamp and the next install retries | self-test cases | all pass | PR description | PASS |
| C-007 | yes | The test commands run under the venv's interpreter, in a scrubbed environment with an in-memory database; a developer's `db.sqlite3` cannot break them | self-test cases; the real API with an inconsistent `db.sqlite3` present | self-test pass; real run exit 0 | PR description | PASS |
| C-008 | yes | `make ci` includes `api-check`, never `api-install`, and `make -n ci` stays a clean preview | self-test case; `make -n ci` | exit 0 | PR description | PASS |
| C-009 | yes | The Makefile's three API commands match `ci.yml`'s `api` job, and `ci.yml` is unchanged | self-test case; `git diff origin/main --stat -- .github` | match; empty diff | PR description | PASS |
| C-010 | yes | The Postgres/Redis-only skips are named in the output, the help text, the Makefile and `CLAUDE.md`; the install's unlocked state is stated in the same places and in the README | self-test cases; read the diff | present | `git diff` | PASS |
| C-011 | yes | `implementation/api/pyproject.toml` has an exact `setuptools` pin that builds on Python 3.14 | `make api-install` from scratch; `grep` the pin | exit 0 | PR description | PASS |
| C-012 | yes | The self-test and the mutation proof pass, and every mutation is caught | `python3 scripts/check_api_gate.py --self-test`, then `--mutation-proof` | both exit 0; counts as printed | PR description | PASS |
| C-013 | yes | Guards that read the Makefile stay green | `check_launch_reachability.py` and `check_dependency_audit_coverage.py`, self-test and real | all exit 0 | PR description | PASS |
| C-014 | yes | A full `make ci` on the branch head exits 0 with the self-test and `api-check` inside it | `make ci`, one at a time, output to a file, exit code captured unpiped | exit 0; `ALL GREEN` | PR description | PASS |
| C-015 | yes | Ticket criteria not in this PR are tracked, not dropped | ClickUp | 17tnw2b9aaw and 17tnw2b9aax exist and are linked | ClickUp | PASS |
| C-016 | yes | No stray non-ASCII in the diff, no tracked virtualenv, branch not behind `origin/main` | scan the added lines of `git diff origin/main -U0`; `git status --short`; `git rev-list --count HEAD..origin/main` | only U+2014 in `CLAUDE.md` and this file's title; 0 | PR description | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-011 above, each with a deliberate-failure proof or a reproduced failure mode.
- Broader regression verification: C-012 to C-014.
- Independent verifier: the four reviewers (Cody, Shadow, Vera, Quinn), dispatched by the orchestrator.
- Required environment: macOS with Homebrew Python 3.14, network for `make api-install`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-006
- Hypothesis: a stamp-file make target building a per-checkout venv and a scrubbed-environment run of CI's three commands gives the local signal.
- Change or investigation: added `api-check` and an installing venv target; ran it fresh, then each failure mode.
- Verifier executed: the deliberate-failure proofs.
- Result: green on the clean tree; red on a broken test and on a missing migration; hard errors on no interpreter, old interpreter, no network.
- New evidence: the failing test appeared only as a traceback header with `-rs`; changed to `-rfEs`.
- Decision: iterate

### Iteration 2

- Target criterion: C-007 to C-016
- Hypothesis: wiring into `make ci`, documentation, follow-up tickets and a self-test with a mutation proof complete the in-scope criteria without touching CI.
- Change or investigation: wired into `make ci`; documentation; follow-up tickets; self-test and mutation proof, which found one weak case.
- Verifier executed: full `make ci`.
- Result: full `make ci` exit 0 at f84338f7.
- New evidence: none beyond the result.
- Decision: gate-review

### Iteration 3 (round 1 review remediation)

- Target criterion: all
- Hypothesis: following the marketing gate's precedent (the gate never installs) removes the surprise install, the stale-venv problem and most of the races at once.
- Change or investigation: Cody and Shadow found no blockers. Applied: `api-install` and a refusing `api-check`; `scripts/api_venv.py`; a venv name only this target uses with a marker, symlink refusal, lock, content-hash and interpreter stamp; `override` on every variable; in-memory database in the scrubbed environment; exact `setuptools` pin; honest wording about the unlocked install; the corrected reason for the wrong-tree assertion (a borrowed venv's packages came from another tree's `pyproject.toml`; it would not test that tree's code); a comparison with `ci.yml`; fixes to the self-test and mutation proof the reviewers listed.
- Verifier executed: see the PR description for exit codes and counts at the head SHA.
- Result: all rows above PASS at the PR head; counts and exit codes are in the PR description.
- New evidence: GNU Make 3.81 exports `export VAR` placed before `VAR ?= x` as an empty string; the default interpreter is defined first and a case plus a mutation pin it.
- Decision: gate-review

## Risks and rollback

- Risks: the install is unlocked (accepted, above); `make ci` needs a one-time `make api-install` on every fresh worktree; the three API commands are written in both the Makefile and `ci.yml` and are only compared, not shared; `make ci` is slower for every change until path-aware dispatch (17tnw2b9aax).
- Rollback or recovery: revert the commits; delete `implementation/api/.venv-api-check` (gitignored) if a venv is ever in doubt, then `make api-install`.

## Pause and escalation conditions

- A reviewer or the owner decides CI should call `make api-check` instead of listing the commands: that is a `ci.yml` change and needs a CI run to prove.
- The owner decides the API gate should be opt-in locally rather than part of `make ci`.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5rjh7-make-ci-api.md`
- Validator result: OK (structural) and OK (completion), see PR description
- Independent verification result: round 1 (Cody, Shadow) approve with conditions, applied above; Quinn and later rounds pending
- Terminal state: GATE_REVIEW (the implementation is done and verified by its author; this is not VERIFIED_COMPLETE until the reviews finish)
- Remaining failed or blocked criteria: none known; criteria of the parent ticket outside the API half are in 17tnw2b9aaw and 17tnw2b9aax
- ClickUp final evidence comment: posted by the orchestrator with the PR link
