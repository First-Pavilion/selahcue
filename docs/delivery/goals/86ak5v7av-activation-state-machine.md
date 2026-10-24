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
- Tests: new `tests/test_activation_licence_transition.py` (both entry points, every other licence status, validity window, device limit, replays, atomicity, secret-free audit row, tenant and role boundaries); Postgres races in `tests/test_concurrency_postgres.py`; one added assertion in `tests/test_device_activation_slice.py`.

### Non-goals

- Changing activation's instance-limit, re-mint, idempotency or token logic.
- Changing the state machine's refusal-audit durability decision. Its docstring now names device activation as the one deliberate wrapped caller and says why that is safe there; the decision itself is not reopened.
- Extending the writer-discipline scan's blind spots (aliased queryset or related-manager update, `update(**{...})`, `setattr`, import alias). The docstring now says so; a follow-up ticket owns it.
- Any other licence mutation (revoke, extend, expire, suspend, convert), or `settings.py`.

### Constraints

- Keep `select_for_update` ordering in `_activate_device_for_key` intact; no new lock acquired before it.
- The transition runs inside the existing `transaction.atomic()`, so status, device, token and both audit rows commit or roll back together.
- Keep the diff tight: later tickets touch licence admin mutations in the same app.

### Assumptions and unknowns

- ASSUMED, validated by test: `ActorKind.DEVICE` is correct for the enrollment-key path (it is the actor the existing row carries); the account-session path keeps its CUSTOMER actor.
- ASSUMED, validated on Postgres: re-locking the same row inside one transaction (the machine's `select_for_update` in a nested atomic block) is a same-transaction re-entry and cannot self-deadlock; the Postgres suite shows activations parked behind a held row lock all complete once it is released, and that exactly one transition is written.
- The machine's DENIED row on a refusal rolls back with the wrapping activation transaction. This can only happen if the table loses the ISSUED to ACTIVATED edge, and the activation then fails closed. Accepted per the decision already recorded in the state machine docstring (no new owner decision needed).

## Dependencies and approvals

- 86ak5mn00 (state machine) is merged on origin/main. The refusal-durability decision it recorded is the input to the nesting choice above.
- No owner approval required.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. Every Verifier is a command run from `implementation/api` with a venv built from this worktree; the Postgres runs set `SQL_ENGINE=django.db.backends.postgresql SQL_DATABASE=selahcue_test SQL_USER=selahcue SQL_PASSWORD=selahcue SQL_HOST=<host> SQL_PORT=<port>` against a Postgres 16 container. Results and exit codes by head SHA are in the PR #214 "Evidence" section.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | After first activation, on both entry points, one `app_license_key` audit row exists with actor, before ISSUED, after ACTIVATED, pinned reason text, request id = idempotency key and the right source surface | `pytest tests/test_activation_licence_transition.py -k "writes_a_licence_level_transition_row or account_session_path_audits"` | exits 0; red against the pre-fix code and against a direct-assignment mutant | PR #214 Evidence (failing-first and mutation lists) | PASS |
| C-002 | yes | The existing `device.activated` row is still written, with its payload keys pinned | `pytest tests/test_activation_licence_transition.py -k "device_level_row"` | exits 0 | PR #214 Evidence | PASS |
| C-003 | yes | A retry, a retry from a different install, a known install re-enrolling and a second device write no second ISSUED to ACTIVATED row, on both entry points; the same request id on a different licence is not a replay | `pytest tests/test_activation_licence_transition.py -k "retry or re_enrolling or second_device or different_licence or different_install"` | exits 0 | PR #214 Evidence | PASS |
| C-004 | yes | A licence in each non-ISSUED status (ACTIVATED, EXPIRING activate; EXPIRED, SUSPENDED, REVOKED, CONVERTED, ARCHIVED are refused) behaves as before and writes no transition and no extra audit row, on both entry points; an ISSUED licence outside its validity window or at its device limit is refused and stays ISSUED | `pytest tests/test_activation_licence_transition.py -k "any_other_status or validity_window or device_limit"` | exits 0 | PR #214 Evidence | PASS |
| C-005 | yes | Activation consults `LEGAL_TRANSITIONS`: with the edge removed, activation fails closed with CONFLICT, nothing is written (the machine's DENIED row included, asserted), and the same request succeeds once the table is whole | `pytest tests/test_activation_licence_transition.py -k consults_the_transition_table` | exits 0; red against the pre-fix code | PR #214 Evidence | PASS |
| C-006 | yes | The licence transition is atomic with device and token creation, whichever audit write fails and in the production (autocommit) shape | `pytest tests/test_activation_licence_transition.py -k "rolls_back or rolls_the_licence"` and `tests/test_device_activation_slice.py::test_activation_rolls_back_when_audit_write_fails` | exits 0 | PR #214 Evidence | PASS |
| C-007 | yes | The licence row holds no secret material on either entry point; non-admin and cross-tenant sessions cannot trigger the transition | `pytest tests/test_activation_licence_transition.py -k "secret_material or non_admin or another_tenants"` | exits 0 | PR #214 Evidence | PASS |
| C-008 | yes | The activation site is no longer a known direct write, and the scan still passes and still catches bypass shapes | `pytest tests/test_license_state_machine.py` | exits 0; the writer-discipline test goes red under the direct-assignment mutant | PR #214 Evidence | PASS |
| C-009 | yes | On real Postgres, with the overlap forced (both requests parked on the licence-row lock via pg_stat_activity before it is released): the instance limit holds on a one-seat ISSUED licence, first activations (same licence, in-flight retry, enrollment against account) complete and write exactly one licence transition, activations of different licences do not interfere, and the re-mint and revoke races still hold. Removing the outer lock turns the limit and in-flight tests red; removing both locks turns all forced-overlap tests red | `pytest tests/test_concurrency_postgres.py` against Postgres 16 | exits 0, none skipped; repeated runs stay green | PR #214 Evidence | PASS |
| C-010 | yes | Django checks and migrations are clean, and the full suite is green on SQLite and on Postgres 16 | `python manage.py check`; `python manage.py makemigrations --check --dry-run`; `pytest` on both engines | all exit 0 | PR #214 Evidence | PASS |
| C-011 | yes | Diff contains no stray non-ASCII characters | grep -nP for non-ASCII over the added lines of `git diff origin/main -U0` | only visible, intentional characters (em dash, rightwards arrow, matching the surrounding text) | PR #214 Evidence | PASS |
| C-012 | yes | Independent review (Cody, Shadow, Vera, Quinn) clears, including the re-check of round-1 findings | orchestrator-dispatched reviews | all verdicts recorded | review report | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new test module, `test_license_state_machine.py`, `test_concurrency_postgres.py`, `test_device_activation_slice.py`.
- Broader regression verification: full `pytest` on SQLite and on a throwaway Postgres 16 container.
- Mutation checks: each production line the change relies on is altered in turn (direct assignment, wrong actor, fixed request id, dropped surface, dropped device link, unconditional call, secret in the row, no atomic block, no limit check, no window check, any status activatable, no row lock, no idempotent replay, replay ignoring the licence, reworded reason, swallowed refusal, no admin check, resolver ignoring org, window or status) and the suites must go red; the list and results are in the PR body.
- Independent verifier: the four-reviewer gate dispatched by the orchestrator.
- Required environment: venv built from this worktree's `implementation/api` (`pip install -e ".[dev]"` plus `psycopg[binary]`); Docker Postgres 16 (matches the CI service). Redis-only tests skip locally and run in CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 to C-009
- Hypothesis: replacing the inline assignment with one call to the audited writer, placed where the assignment was, satisfies the ticket without disturbing lock order.
- Change or investigation: wrote failing tests first (5 of 8 red for the right reasons: no licence row, table not consulted, audit failure did not roll back); then changed `_activate_device_for_key`; narrowed `_KNOWN_DIRECT_WRITES`; updated the state machine docstring; added a Postgres race test.
- Verifier executed: focused tests, mutation runs (direct assignment, dropped source surface, dropped device link), full suites.
- Result: all green; each mutant turns at least one test red.
- Decision: gate-review

### Iteration 2

- Target criterion: C-003 to C-009, plus review round 1 (Cody, Quinn, Shadow: 0 blockers)
- Hypothesis: the round-1 conditions are documentation and coverage gaps, not behaviour gaps.
- Change or investigation: state machine docstring names the deliberate wrapped caller and softens the scan claim; the DENIED row loss is asserted; imports hoisted; every non-ISSUED status, the validity window and the device limit are covered on both entry points; reason text made path-neutral and pinned; extra concurrency cases. A mutation run found that removing the idempotency-key replay branch stayed green (the fingerprint branch shadowed it), which is why the "same request from a different install" case was added.
- Verifier executed: all of the above, mutation list re-run on the final tests.
- Result: see PR #214 body.
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
- Independent verification result: round 1 returned no blockers; the re-check after this push is pending.
- Terminal state: GATE_REVIEW (implementation complete; VERIFIED_COMPLETE needs all four reviews finished).
- Remaining failed or blocked criteria: C-012 (independent review).
- ClickUp final evidence comment: owned by the orchestrator.
