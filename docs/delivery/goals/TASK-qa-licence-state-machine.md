# Goal Contract — TASK-qa-86ak5mn00

## Identity

- Goal ID: TASK-qa-86ak5mn00
- Parent goal ID: NONE
- Title: Independent QA verdict on the licence lifecycle state machine — acceptance criteria verified and the test battery proven to bite
- Role: qa-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5mn00
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every acceptance criterion on 86ak5mn00 is independently confirmed PASS or FAIL against
commit `7e13719`, and every control the battery claims to guard is shown by mutation to
fail RED when that control is removed.

## Baseline

- Worktree `/Users/m.oluwole/Documents/code/scph-wt-86ak5mn00`, branch
  `feat/86ak5mn00-licence-state-machine`, commit `7e13719`, cut from `main` @ `607a7b5`.
- QA venv rebuilt from `pyproject.toml` on Python 3.14.5 (the documented
  `/private/tmp/selahcue-api-venv` no longer exists).
- SQLite full suite: 287 passed, 1 failed, 3 skipped, 2 errors. The failure is the known
  load-sensitive `test_resend_verification` timing probe; the 2 errors are the
  `_reset_degraded_send_window` breakage `main` already carries (`2c89159`). Neither is
  this branch's.
- Postgres 16.15 (Docker, `quinn-pg16-86ak5mn00`, port 55433):
  `tests/test_license_state_machine.py` + `tests/test_concurrency_postgres.py` = 103 passed.

## Inputs and evidence sources

- ClickUp 86ak5mn00 (acceptance criteria, D3/DEC-010 note)
- `docs/product/prds/SelahCue-Platform-PRD.md` §13 (FR-501, FR-504, FR-505, FR-508, FR-510, NFR-506)
- `implementation/api/selahcue_api/apps/license_keys/state_machine.py`
- `implementation/api/selahcue_api/apps/license_keys/models.py` + `migrations/0002_applicensekey_prior_status.py`
- `implementation/api/tests/test_license_state_machine.py`, `tests/test_concurrency_postgres.py`

## Scope

### In scope

- Acceptance verification of each of the nine ticket criteria.
- Independent re-run of Kenji's mutations M1-M8, against the artefact the test database is
  actually built from.
- Invented mutations targeting controls Kenji's set did not cover.
- Severity call on the declared refusal-audit durability limitation.

### Non-goals

- Correctness review (Cody), security review (Sana), performance review (Vera).
- Implementing fixes. QA reports; the implementation owner remediates.
- Opening a PR — explicitly excluded by the task brief.

### Constraints

- Do not commit, stage or revert any work in this or the shared checkout.
- Restore every mutated file before moving on; verify restoration with `git diff --quiet`.
- Never pipe a gate through `tail`/`head`.
- Postgres is the authoritative backend for the check constraint and `select_for_update`.

### Assumptions and unknowns

- ASSUMED: CI runs the same Python 3.14 + SQLite default the local suite does; validated
  against `pyproject.toml` and `settings.py` defaults.

## Dependencies and approvals

- Dependent lifecycle tickets 86ak1090r / 86ak109dv / 86ak5mn0c / 86ak5mn2k / 86ak5mn2m —
  not yet landed; they determine how reachable the refusal-audit durability gap is.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All 23 legal edges are driven and succeed | pytest on Postgres | 23 parametrised cases pass | pg-focused.txt | PASS |
| C-002 | yes | All 41 illegal edges refused, coded, status unchanged, attempt recorded | pytest on Postgres | 41 parametrised cases pass | pg-focused.txt | PASS |
| C-003 | yes | Reinstatement returns the stored prior status for ACTIVATED and EXPIRING | M2 mutation | EXPIRING case RED | mutation log | PASS |
| C-004 | yes | The sweep cannot pass vacuously, incl. visiting no files | M3 + invented mutations | sweep RED when a status loses its writer | mutation log | PASS |
| C-005 | yes | Transition count == audit-row count across the battery | M6 mutation | RED | mutation log | PASS |
| C-006 | yes | Audit rows carry actor, before, after, reason, request id | test read + mutation | RED when a field is dropped | mutation log | FAIL |
| C-007 | yes | Idempotent replay writes no second audit row | M5 mutation | RED | mutation log | PASS |
| C-008 | yes | The audit store has no update/delete surface | scan + positive control | scan finds a planted mutation | mutation log | FAIL |
| C-009 | yes | The check constraint bites, verified against the MIGRATION not just models.py | M7 mutation on migration | RED | mutation log | PASS |
| C-010 | yes | Every mutation in Kenji's set was run against the artefact under test | audit of each mutation site | no mutation is schema-blind | this contract | PASS |
| C-011 | yes | At least one mutation Kenji did not run is attempted | invented mutation battery | result recorded either way | mutation log | PASS |
| C-012 | yes | The refusal-audit durability gap is reproduced and severity assigned | purpose-built test | refusal row demonstrably vanishes | mutation log | PASS |

## Verification plan

- Focused verification: `tests/test_license_state_machine.py` + `tests/test_concurrency_postgres.py` on Postgres 16.
- Broader regression verification: full `pytest` on SQLite, compared against the pristine-`main` baseline.
- Independent verifier: Verity (Codex QA second opinion).
- Required environment: Python 3.14.5 venv; Postgres 16.15 in Docker; SQLite default.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002 (baseline acceptance)
- Hypothesis: the shipped battery passes on both backends at the reported counts.
- Change or investigation: rebuilt the venv, ran both backends.
- Verifier executed: `pytest -q` (SQLite full), `pg.sh -q` (focused, Postgres).
- Result: SQLite 287P/1F/3S/2E (failure + errors pre-existing); Postgres focused 103 passed.
- New evidence: baseline-sqlite.txt, pg-focused.txt
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-005, C-007, C-009, C-010 (re-run Kenji's M1-M8)
- Hypothesis: each declared mutation bites at the reported count.
- Verifier executed: mutation harness, each run with siblings, on Postgres 16.
- Result: M1 35F · M2 6F (report said 8; the EXPIRING criterion still goes RED) · M3 1F ·
  M4 24F · M5 4F · M6 42F · M7a GREEN (survives, as Kenji documented) · M7b 2F · M8 1F.
- Decision: iterate

### Iteration 3

- Target criterion: C-011 (mutations Kenji did not run)
- Hypothesis: some named control has no test that fails when it is removed.
- Result: THREE survivors, each with a captured diff proving the edit landed —
  INV-1 (refusal row's reason + request_id blanked) 103 passed;
  INV-7 (`_sync` made a no-op) 103 passed;
  INV-2 (bypass writer named `lk`) and INV-3 (audit delete via a queryset variable) both
  evade the AST scans. INV-4a/INV-4b (terminality drift) and INV-6 (scan root misdirected)
  are correctly caught.
- Decision: iterate

### Iteration 4

- Target criterion: harness integrity (raised by the coordinator mid-run)
- Hypothesis: a shared scratchpad could let a peer agent clobber the harness and fabricate
  a GREEN, which is the direction that matters.
- Change or investigation: confirmed the scratchpad IS shared (peer files `mutate.py`,
  `mutate_rw.py`, `mutate2.py` present). Rebuilt the harness under a private directory and
  made it PROVE each mutation landed (unique sentinel present in the target file + git
  showing a change to that exact file) before any run is scored, with a distinct
  `MUTATION_DID_NOT_LAND` state that is never folded into a pass or a miss.
- Verifier executed: null-mutation self-test (must not score) and M1 positive control.
- Result: NULL -> `STATE=MUTATION_DID_NOT_LAND`, rc=93, unscored. M1 -> RED, 35 failed,
  identical to the first run. All three survivors re-run under the hardened harness and
  re-confirmed GREEN with their diffs captured. Venv integrity checked (3.14.5 / Django
  6.1 / pytest 8.4.2).
- Decision: iterate

### Iteration 5

- Target criterion: C-012 (refusal-audit durability) and the AC3 round trips
- Hypothesis: the declared limitation is reachable from the codebase's own house pattern.
- Change or investigation: all 17 production service writers use `transaction.atomic()`.
  Built a probe suite driving suspend/reinstate from every legal source, a double cycle,
  and the wrapped-caller case with a positive control.
- Result: 8 passed, 1 failed. Round trips correct from all five suspendable sources; the
  double cycle carries no stale prior status; the unwrapped refusal is durable (1 DENIED
  row); the wrapped refusal leaves **0 DENIED rows** — the gap is real and reachable.
  Separately, `makemigrations --check` is EXIT=0 pristine and EXIT=1 with M7a applied, so
  CI does catch the models.py/migration divergence that pytest misses.
- Decision: iterate

## Risks and rollback

- Risks: a mutation left un-restored would corrupt the branch under review.
- Rollback or recovery: `git -C <worktree> checkout --` the mutated path after every
  mutation, and assert `git status --porcelain` is clean before the next one.

## Pause and escalation conditions

- A finding that changes what the requirement means → escalate to Product Manager, not QA.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-qa-licence-state-machine.md`
- Validator result: OK (structural)
- Independent verification result: PARTIAL. The contract pairs QA with the Verity Codex
  agent; no `codex` CLI and no Verity agent definition exist in this environment, so that
  step could not run and is declared unmet. An independent read-only reviewer was
  substituted; its claims were verified by mutation rather than relayed, and one of them
  (the reinstatement-action collision) proved WRONG — it is caught, incidentally, by
  `.get()` raising MultipleObjectsReturned. Treat this as one reviewer's work, not two.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-006 (refusal rows' FR-508 fields unasserted) and
  C-008 (append-only positive control is inert and the scan is evadable). Both are
  small remediations owned by the implementation role. The refusal-audit durability gap
  (C-012 PASS = successfully reproduced) is a High-severity design decision that must be
  settled and pinned by a test before the dependent tickets build on this spine.
- ClickUp final evidence comment: https://app.clickup.com/t/86ak5mn00 (comment 90130310878080)
- Follow-up raised: https://app.clickup.com/t/86ak5v7av — first activation bypasses the
  state machine and writes no licence-level audit row (FR-508/NFR-506)
