# Goal Contract — 86ak5rjh7-make-ci-api

## Identity

- Goal ID: 86ak5rjh7-make-ci-api
- Parent goal ID: NONE
- Title: `make ci` verifies the Django API: a failing API test or a model without a committed migration fails it, and what it cannot run locally is stated
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
fails or a Django model changed without a committed migration, in any checkout including a fresh worktree,
without ever testing another checkout's code. What the local run cannot cover (the Postgres- and Redis-only
tests) is named in the target's help text, the Makefile and `CLAUDE.md`.

## Baseline

**Verified** on `origin/main` at `f176db35`:

- `make ci` ran nothing for `implementation/api`. The Makefile header and `CLAUDE.md` both said so.
- CI's `api (django)` job (`.github/workflows/ci.yml`, job `api`) runs `manage.py check`,
  `makemigrations --check --noinput` and `pytest tests -q` against Postgres 16 and Redis 7.
- The marketing half of the ticket is already done: `make marketing-check` exists and `make ci` calls it.
- `implementation/api/README.md` told readers to use `/private/tmp/selahcue-api-venv`, a path that exists on no
  other machine. The main checkout's `implementation/api/venv` is an editable install of the MAIN checkout.
- `selahcue-stt` is referenced by no CI job and no `make ci` line (grep of `ci.yml` and the Makefile: only comments).
- `make ci` aborts at its first failing recipe line.
- System `python3` is 3.9.6; the API needs Python >=3.12 and CI pins 3.14. `/opt/homebrew/bin/python3.14` exists.

## Inputs and evidence sources

- ClickUp 86ak5rjh7 (description, acceptance criteria, all comments), 86akc2kmh (fresh-worktree clause, complete)
- Root `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml` (job `api`, path filters)
- `implementation/api/pyproject.toml`, `pytest.ini`, `.gitignore`, `.dockerignore`, `selahcue_api/settings.py`
- `scripts/check_launch_reachability.py`, `scripts/check_dependency_audit_coverage.py` (guards that read the Makefile)
- Owner requirement 2b (happy paths and edge cases, each test able to fail), received mid-task

## Scope

### In scope

- A `make api-check` target: system checks, migrations committed, pytest, on SQLite, in a per-checkout virtualenv
  built on first use and rebuilt when `pyproject.toml` changes; hard errors instead of skips.
- `make ci` calls it.
- The Makefile header, the target's help text, `CLAUDE.md` and `implementation/api/README.md` state what is and is not covered.
- Linked follow-up tickets for the acceptance criteria not in this PR.
- `scripts/check_api_gate.py`: self-test of the target's logic against a fake API, and a mutation proof.

### Non-goals

- Running Postgres or Redis locally (CI's job does; ticket criteria accept naming the limit).
- Changing `.github/workflows/ci.yml` (the Linux-only policy and billed minutes; the criteria do not require it).
- `selahcue-stt` lint and tests, run-every-gate-and-report restructure of `make ci`, path-aware dispatch: follow-ups
  17tnw2b9aaw and 17tnw2b9aax.
- The fresh-worktree sidecar clause: done by 86akc2kmh.

### Constraints

- Never write the virtualenv into a tracked path; it must install from the tree it runs in.
- Never skip silently. No new CI minutes.
- `make -n ci` stays a clean preview; `scripts/check_launch_reachability.py` stays green.

### Assumptions and unknowns

- ASSUMED: developers have Python 3.14 (CI's and the dev interpreter) or can set `API_PYTHON`. Validation owner: reviewers; the failure message names the fix.
- ASSUMED: a desktop-only change paying about 100 seconds for the API gate is acceptable until 17tnw2b9aax adds path-aware dispatch.
- VERIFIED: the CI job's three commands are duplicated in the Makefile, not shared. Making CI call `make api-check` was
  considered and rejected here because it cannot be proved without a CI run and needs a way to install `psycopg` into the venv.

## Dependencies and approvals

- None. No production, secret or infrastructure change.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | In a fresh worktree, `make api-check` builds its own venv and passes | `make api-check` in the new worktree (no venv beforehand) | exit 0; 709 passed, 4 skipped, 1 xfailed | PR description, evidence section | PASS |
| C-002 | yes | A failing API test makes the gate exit non-zero and names the test | append `assert 1 + 1 == 3` test to `tests/test_foundation_contract.py`, run `make api-check`, revert | exit 2; `1 failed, 709 passed`; `test_deliberately_broken_for_gate_proof` named | PR description | PASS |
| C-003 | yes | A model field without a migration makes the gate exit non-zero | add a field to `CustomerOrg`, run `make api-check`, revert | exit 2 at `makemigrations --check`, naming `0004_customerorg_gate_proof_field.py`, before pytest | PR description | PASS |
| C-004 | yes | The gate cannot run on another checkout's code | `python -I` location assertion run against a venv installed from a different tree | an AssertionError naming the other tree that selahcue_api was imported from | PR description | PASS |
| C-005 | yes | The gate fails loudly, never skips, when it cannot run | run with no interpreter, a Python 3.9 interpreter, and an unreachable package index | each exits 2 with the fix named; no install stamp left behind after the network failure | PR description | PASS |
| C-006 | yes | A changed `pyproject.toml` rebuilds the venv; an interrupted install is retried | touch `pyproject.toml`, run after a failed install | next run rebuilds and passes (709 passed) | PR description | PASS |
| C-007 | yes | `make ci` includes `api-check`, and `make -n ci` stays a clean preview | `make -n ci` | exit 0; lists `api-check` after `marketing-check` | PR description | PASS |
| C-008 | yes | The Postgres/Redis-only skips are named in the help text, the Makefile and `CLAUDE.md`; `CLAUDE.md` and the Makefile header no longer say `make ci` ignores the API | `make help`, read the diff | text present in all places | `git diff` | PASS |
| C-009 | yes | Guards that read the Makefile stay green | `check_launch_reachability.py` (self-test and real), `check_dependency_audit_coverage.py` (self-test and real) | all exit 0 | PR description | PASS |
| C-010 | yes | CI workflow is unchanged and no macOS or extra job is added | `git diff origin/main --stat -- .github` | empty | `git diff` | PASS |
| C-011 | yes | Ticket criteria not in this PR are tracked, not dropped | ClickUp search, then follow-ups | 17tnw2b9aaw (selahcue-stt), 17tnw2b9aax (run every gate, path-aware dispatch) created and linked | ClickUp | PASS |
| C-012 | yes | A full `make ci` on the branch head exits 0 with `api-check` inside it | `make ci`, one at a time, output to a file, exit code captured unpiped | exit 0; `ALL GREEN` | PR description | PENDING |
| C-014 | yes | The target's logic is covered by tests that can fail: 18 cases (fresh worktree, reuse, rebuild on pyproject change, wrong-tree venv, failing test, missing migration, system check failure, missing pytest, no interpreter, old interpreter, failed install, scrubbed environment, venv path override, other working directory, wrong-directory `make -f`, `make -n ci` wiring, help text, skip statement) | `python3 scripts/check_api_gate.py --self-test`, then `--mutation-proof` | self-test exit 0, 18 cases; mutation proof exit 0, 16 of 16 mutations caught (one real gap found and fixed: the old-interpreter fake could not tell a missing version check from a failing one) | PR description | PASS |
| C-013 | yes | No stray non-ASCII in the diff, no tracked virtualenv | grep the added lines of `git diff origin/main -U0` for non-ASCII characters; `git status --short` | only U+2014 in `CLAUDE.md` (the file's own style); only 4 paths changed | PR description | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-006 above, each with a deliberate-failure proof or a reproduced failure mode.
- Broader regression verification: C-009, C-012.
- Independent verifier: the four reviewers (Cody, Shadow, Vera, Quinn), dispatched by the orchestrator.
- Required environment: macOS with Homebrew Python 3.14, network for the first venv build.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-006
- Hypothesis: a stamp-file make target building `implementation/api/.venv` and a scrubbed-environment run of CI's three commands gives the local signal.
- Change or investigation: added `api-check` and its venv target to the Makefile; ran it fresh (95 s build and install, 104 s tests), then each failure mode.
- Verifier executed: all proofs listed above.
- Result: gate green on the clean tree (709 passed, 4 skipped, 1 xfailed); red (exit 2) on a broken test and on a missing migration; hard errors on no interpreter, old interpreter, no network; the location assertion fires on a venv from another tree.
- New evidence: the failing test appeared only as a traceback header with `-rs`; changed to `-rfEs` so it also appears in the summary.
- Decision: iterate

### Iteration 2

- Target criterion: C-007 to C-013
- Hypothesis: wiring into `make ci`, updating the documentation and filing follow-ups completes the in-scope criteria without touching CI.
- Change or investigation: `ci` calls `api-check`; header, help, `CLAUDE.md`, README updated; two follow-up tickets created and linked.
- Verifier executed: `make -n ci`, guards, full `make ci`.
- Result: see C-012.
- New evidence: a `make ci` from another worktree was already running; this one waited for it.
- Decision: complete

## Risks and rollback

- Risks: `make ci` takes about 100 seconds longer for every change, including desktop-only ones (tracked in 17tnw2b9aax); first run needs the network and Python 3.14; the three API commands are written in both the Makefile and `ci.yml` and can drift.
- Rollback or recovery: revert the commit; delete `implementation/api/.venv` (gitignored) if a venv is ever in doubt, the next run rebuilds it.

## Pause and escalation conditions

- A reviewer or the owner decides CI should call `make api-check` instead of listing the commands: that is a `ci.yml` change and needs a CI run to prove.
- The owner decides the API gate should be opt-in locally rather than part of `make ci`.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5rjh7-make-ci-api.md`
- Validator result: see PR description
- Independent verification result: pending the four-reviewer gate
- Terminal state: pending C-012 and review
- Remaining failed or blocked criteria: none known
- ClickUp final evidence comment: posted with the PR link
