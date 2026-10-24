# Goal Contract — 86ak5v7av-activation-state-machine

## Identity

- Goal ID: 86ak5v7av-activation-state-machine
- Parent goal ID: NONE
- Title: First activation moves a licence ISSUED to ACTIVATED through the licence state machine and is audited as a licence transition
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5v7av
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

When a device first activates against an ISSUED enrollment key, the licence moves to ACTIVATED via `state_machine.apply_license_status_transition`, in the same transaction and under the same row lock that activation already holds, and a licence-level audit row (`target_type="app_license_key"`) records actor, before, after, reason and request id. Behaviour for the caller is otherwise unchanged.

## Baseline

Verified on origin/main f176db35: `apps/devices/services.py` `_activate_device_for_key` assigned `license_key.status = LicenseKeyStatus.ACTIVATED` and saved with `update_fields`, so the edge was never checked against `LEGAL_TRANSITIONS`, and the only audit row was `device.activated` with `target_type="device"`. `tests/test_license_state_machine.py` pinned this one site as a known direct write (`_KNOWN_DIRECT_WRITES`). The licence audit trail therefore had no row for the first activation (NFR-506, FR-527).

## Inputs and evidence sources

- ClickUp 86ak5v7av (description, acceptance criteria); no comments on the ticket.
- `implementation/api/selahcue_api/apps/license_keys/state_machine.py` (writer, calling contract, refusal-durability trade-off).
- `implementation/api/selahcue_api/apps/devices/services.py` (activation core shared by the enrollment-key and account-session paths).
- `implementation/api/tests/test_license_state_machine.py`, `tests/test_concurrency_postgres.py`, `tests/test_device_activation_slice.py`.
- `.github/workflows/ci.yml` job `api (django)` (exact gate steps).

## Scope

### In scope

- Route the ISSUED to ACTIVATED flip in `_activate_device_for_key` through `apply_license_status_transition`, for both entry points (enrollment key and account session).
- Actor is the same actor the existing `device.activated` row uses (the device, or the signed-in customer on the account path); request id is the activation idempotency key; source surface is the activation's; reason is a fixed automated-activation string.
- Keep the `device.activated` row unchanged.
- Remove the activation entry from `_KNOWN_DIRECT_WRITES`; update the state machine docstring that described the bypass.
- Tests: new `tests/test_activation_licence_transition.py`; a Postgres race test in `tests/test_concurrency_postgres.py`.

### Non-goals

- Changing activation's instance-limit, re-mint, idempotency or token logic.
- Changing the state machine's refusal-audit durability decision (recorded in its docstring; not reopened here).
- Any other licence mutation (revoke, extend, expire, suspend, convert), or `settings.py`.

### Constraints

- Keep `select_for_update` ordering in `_activate_device_for_key` intact; no new lock acquired before it.
- The transition runs inside the existing `transaction.atomic()`, so status, device, token and both audit rows commit or roll back together.
- Keep the diff tight: later tickets touch licence admin mutations in the same app.

### Assumptions and unknowns

- ASSUMED, validated by test: `ActorKind.DEVICE` is correct for the enrollment-key path (it is the actor the existing row carries); the account-session path keeps its CUSTOMER actor.
- ASSUMED, validated on Postgres: re-locking the same row inside one transaction (the machine's `select_for_update` in a nested atomic block) neither deadlocks nor blocks.
- The machine's DENIED row on a refusal rolls back with the wrapping activation transaction. This can only happen if the table loses the ISSUED to ACTIVATED edge, and the activation then fails closed. Accepted per the decision already recorded in the state machine docstring (no new owner decision needed).

## Dependencies and approvals

- 86ak5mn00 (state machine) is merged on origin/main. The refusal-durability decision it recorded is the input to the nesting choice above.
- No owner approval required.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | After first activation an `app_license_key` audit row exists with actor, before ISSUED, after ACTIVATED, reason (>= 8 chars) and request id = idempotency key | `pytest tests/test_activation_licence_transition.py::test_first_activation_writes_a_licence_level_transition_row` | exits 0; fails against the pre-fix code and against a direct-assignment mutant | red run and mutant run logs | PASS |
| C-002 | yes | The existing `device.activated` row is still written and unchanged | `pytest tests/test_activation_licence_transition.py::test_the_device_level_row_is_still_written_and_unchanged` | exits 0 | green run log | PASS |
| C-003 | yes | A retry or second device writes no second ISSUED to ACTIVATED row; activating against ACTIVATED or EXPIRING writes none | `pytest tests/test_activation_licence_transition.py -k "retry or non_issued"` | exits 0 | green run log | PASS |
| C-004 | yes | Activation consults `LEGAL_TRANSITIONS`: with the edge removed, activation is refused and nothing is written | `pytest tests/test_activation_licence_transition.py::test_activation_consults_the_transition_table` | exits 0; fails against the pre-fix code | red run log | PASS |
| C-005 | yes | The licence transition is atomic with device and token creation | `pytest tests/test_activation_licence_transition.py::test_the_licence_transition_rolls_back_with_the_activation` | exits 0 | green run log | PASS |
| C-006 | yes | Account-session path audits the customer as actor | `pytest tests/test_activation_licence_transition.py::test_the_account_session_path_audits_the_customer_as_actor` | exits 0 | green run log | PASS |
| C-007 | yes | The activation site is no longer a known direct write, and the scan still passes and still catches bypass shapes | `pytest tests/test_license_state_machine.py` | exits 0; the writer-discipline test goes red under the direct-assignment mutant | full run and mutant logs | PASS |
| C-008 | yes | On real Postgres the nested lock does not deadlock, the instance limit and re-mint races still hold, and concurrent first activations write exactly one licence transition | `pytest tests/test_concurrency_postgres.py` with `SQL_ENGINE=django.db.backends.postgresql` | exits 0, none skipped | Postgres run log | PASS |
| C-009 | yes | Django checks and migrations are clean, and the full suite is green on SQLite and on Postgres 16 | `manage.py check`; `makemigrations --check --noinput`; `pytest tests` on both engines | all exit 0 | gate logs | PASS |
| C-010 | yes | Diff contains no stray non-ASCII characters | grep -nP for non-ASCII over the added lines of `git diff origin/main -U0` | only visible, intentional characters (em dash, rightwards arrow, matching the surrounding comments) | command output | PASS |
| C-011 | yes | Independent review (Cody, Shadow, Vera, Quinn) clears | orchestrator-dispatched reviews | all verdicts recorded | review report | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new test module, `test_license_state_machine.py`, `test_concurrency_postgres.py`, `test_device_activation_slice.py`.
- Broader regression verification: full `pytest tests` on SQLite and on a throwaway Postgres 16 container.
- Independent verifier: the four-reviewer gate dispatched by the orchestrator.
- Required environment: venv built from this worktree's `implementation/api` (`pip install -e ".[dev]"` plus `psycopg[binary]`); Docker Postgres 16 (matches the CI service). Redis-only tests skip locally and run in CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-008
- Hypothesis: replacing the inline assignment with one call to the audited writer, placed where the assignment was, satisfies the ticket without disturbing lock order.
- Change or investigation: wrote failing tests first (5 of 8 red for the right reasons: no licence row, table not consulted, audit failure did not roll back); then changed `_activate_device_for_key`; narrowed `_KNOWN_DIRECT_WRITES`; updated the state machine docstring; added a Postgres race test.
- Verifier executed: focused tests, mutation runs (direct assignment, dropped source surface, dropped device link), full suites.
- Result: all green; each mutant turns at least one test red.
- New evidence: see Final evaluation.
- Decision: gate-review

## Risks and rollback

- Risks: the state machine validates `source_surface` and `request_id` lengths; both are already bounded by the same audit columns the `device.activated` row writes, so no new refusal path for valid requests. The audit table gains one row per licence on first activation.
- Rollback or recovery: revert the single commit; no migration, no data change, no setting.

## Pause and escalation conditions

- A deadlock or lock-wait seen on Postgres: stop and escalate to the architect.
- Any need to change the state machine's durability decision: stop; owner decision.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5v7av-activation-state-machine.md`
- Validator result: OK (structural), exit 0.
- Independent verification result: pending the orchestrator's four-reviewer gate.
- Terminal state: implementation VERIFIED_COMPLETE; contract stays open on C-011.
- Remaining failed or blocked criteria: C-011 (independent review).
- ClickUp final evidence comment: posted on the ticket when the PR opens.
