# Goal Contract - 86ak1090r-license-revoke-extend

## Identity

- Goal ID: 86ak1090r-license-revoke-extend
- Parent goal ID: NONE
- Title: Staff can revoke and extend a licence key through two audited, permission-gated mutations that write only through the licence state machine; the writer announces a lost denial; audit payload redaction is depth-bounded
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak1090r
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`adminRevokeLicenseKey` (ADMIN-GQL-005, FR-505) and `adminExtendLicenseKey` (ADMIN-GQL-006, FR-509) exist on the admin GraphQL schema. Each is gated by the existing `REVOKE_LICENSE_KEY` / `EXTEND_LICENSE_KEY` permission BEFORE any state is read or written, refuses an unauthorised actor with `PERMISSION_DENIED` and an audit row, and changes a licence status only through `apply_license_status_transition`. Revoke makes the previously unreachable revocation cascade fire. Extend moves `expires_at` forward and returns an EXPIRING or EXPIRED licence to ACTIVATED so a device can re-mint. The writer refuses (fails closed) to run inside a caller's open transaction unless the caller opts in by name, and the two audit-payload redaction functions are depth-bounded so a pathological `extra_before` / `extra_after` is refused at the boundary instead of raising `RecursionError` inside the writer's lock.

## Baseline

Verified on origin/main 93bf8063 (2026-10-26):

- `apps/license_keys/state_machine.py` holds `LEGAL_TRANSITIONS`, `apply_license_status_transition` (no authorisation by design; `recognise_retry` opt-in) and the DENIED-row-after-the-atomic-block contract. Suspend and reinstate (86ak5mn0c) already ship as `suspend_license_key` / `reinstate_license_key` in `apps/license_keys/services.py` with `_lifecycle_mutation`, `_require_autocommit`, a shared per-staff lifecycle budget (`SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE`) and `_get_license_key_or_not_found`.
- `StaffPermission.REVOKE_LICENSE_KEY` and `EXTEND_LICENSE_KEY` exist and have no caller.
- Device activation (`devices/services.py::_activate_device_for_key`) calls the writer inside its own `atomic()` on purpose and passes `extra_after={"device_public_id": ...}`. The writer-discipline scan therefore pins ONE direct-write site (staff issuance).
- G1 (device-token re-mint, 86ak108w0) is merged: `tests/test_device_token_remint.py` exists and re-mint is reached through re-activation of a known device.
- `graphql/redaction.py::redact_public_payload` and `assert_no_restricted_payload_fields` recurse with no depth bound.
- `ACTIVATABLE_KEY_STATUSES` is {ISSUED, ACTIVATED, EXPIRING}; EXPIRED is not activatable; REVOKED is outside it, which is what the hourly cascade keys on.
- No production code writes EXPIRING, EXPIRED, CONVERTED or ARCHIVED (their tickets: 86ak109dv, 86ak5mn2k, 86ak5mn2m). The table-derived sweep counts them as written because the edge exists.
- API suite baseline on this commit: see iteration 0.

## Inputs and evidence sources

- ClickUp 86ak1090r: description, the amended section, AC 1-11, and the four comments (PRD traceability FR-505/FR-509, the state-machine routing note, the activation heads-up from PR #214, the suspend/reinstate rebase note from PR #218).
- `docs/product/prds/SelahCue-Platform-PRD.md` section 13 (transition list, FR-505, FR-508, FR-509, NFR-503, NFR-506), section 15 and 19.
- `apps/license_keys/state_machine.py`, `services.py`, `graphql/context.py`, `graphql/redaction.py`, `apps/audit/services.py`, `apps/devices/services.py`, `apps/devices/tasks.py`.
- `tests/test_license_suspend_reinstate.py` (the pattern this slice follows), `tests/test_device_token_remint.py`, `tests/test_revocation_cascade.py`, `tests/test_license_state_machine.py`.
- `.github/workflows/ci.yml` job `api (django)`.

## Scope

### In scope

- `revoke_license_key` and `extend_license_key` in `apps/license_keys/services.py`, and `adminRevokeLicenseKey` / `adminExtendLicenseKey` in `graphql/admin_schema.py`.
- A refusal audit row for an authenticated but unauthorised caller (AC 2), bounded by a per-actor and a global budget so it cannot be used to flood the audit table.
- The in-atomic-block tripwire on the writer (AC 8): a keyword-only opt-in, fail closed when absent, opted in by device activation and by extend with the reason written down.
- The depth bound on the two redaction functions and a boundary check in the writer (AC 9).
- The status-coverage record (AC 7): which statuses a production entry point writes and which are deliberately unwritten, with the owning ticket, pinned by a test.
- Two additive settings entries for the refusal-audit budgets (`settings.py`).

### Non-goals

- Scheduled EXPIRING / EXPIRED transitions (86ak109dv), suspend and reinstate (shipped), CONVERTED (86ak5mn2k), ARCHIVED (86ak5mn2m), billing-driven suspension (G10).
- Synchronously revoking device tokens on revoke: the hourly cascade stays the mechanism (NFR-503, 65 minutes).
- Any database migration. None is created.
- Any change to `LEGAL_TRANSITIONS`.
- The confirmPasswordReset lane (86ak5r2pt): `account_schema.py`, `accounts/services.py`, `test_customer_auth_slice.py` are not touched.

### Constraints

- Strict TDD: failing test first, then the code. Each guard named in the ticket is mutation-verified (remove, RED with siblings running and not `--exact`, restore byte-identical with `cmp`).
- Neither mutation assigns `.status`; the writer-discipline scan keeps exactly its one known site.
- Python imports at module top level.
- Module-local seeding helpers; no new `conftest.py`.
- No Co-Authored-By trailer or attribution footer; push only the ticket branch; PR opened as Draft against main; no ready, no merge, no QA move.
- Scratch files only under the session scratchpad with the prefix `w2-86ak1090r-`.

### Assumptions and unknowns

- DECIDED, flagged for review: extend is accepted from ISSUED, ACTIVATED, EXPIRING and EXPIRED only. SUSPENDED (reinstate first), CONVERTED, REVOKED and ARCHIVED are refused with CONFLICT and a durable DENIED row. Owner or product may want extend-while-suspended; it needs no table change to add later.
- DECIDED, flagged: an extended ISSUED or ACTIVATED licence keeps its status (only `expires_at` moves); EXPIRING and EXPIRED go to ACTIVATED through the writer (edges already in the table). An EXPIRING licence that never had a device ends ACTIVATED with zero devices, which the table forces (there is no EXPIRING to ISSUED edge) and which stays activatable.
- DECIDED, flagged: new expiry must be timezone-aware (naive is refused, unlike issuance which coerces to UTC), strictly later than the current expiry, in the future, and no more than five years from now. The five-year ceiling is a technical sanity bound, not a product rule: issuance has no ceiling and there is no PRD text on a maximum term. Owner call if a different ceiling is wanted.
- DECIDED: reason is the shared `require_reason` (8 to 1000 characters, no control characters), mandatory for both, stored verbatim on the audit row.
- UNKNOWN: Postgres-only behaviour (row-lock ordering and the two-caller races). Only SQLite is available to `make api-check`; the Postgres race tests are written and skip-guarded the way `tests/test_concurrency_postgres.py` does it, and the report says exactly what ran.
- UNKNOWN: whether the owner accepts that AC 7's "6 of 8 have a writer" holds only in the table-derived sense (8 of 8) and not in the production-caller sense (4 of 8: ISSUED, ACTIVATED, SUSPENDED, REVOKED) until 86ak109dv lands.

## Dependencies and approvals

- 86ak5mn00 (state machine), 86ak5mn0c (suspend/reinstate), 86ak5v7av (activation through the writer), 86ak108w0 (G1 re-mint): all merged on origin/main.
- Parallel lane 86ak5r2pt in worktree w2-p1 (confirmPasswordReset). Disjoint files; the only shared file this ticket touches is `settings.py`, additively.
- No approvals needed; a DB migration would have required stopping to ask and none is needed.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A permitted staff actor revokes a licence from every status the table allows (ISSUED, ACTIVATED, EXPIRING, EXPIRED, SUSPENDED, CONVERTED); status is REVOKED, prior_status cleared, exactly one SUCCESS audit row with actor, target, before and after status, reason, request id and timestamp | `pytest tests/test_license_revoke_extend.py -q` | all parametrised sources pass | PENDING | PENDING |
| C-002 | yes | The previously dead cascade fires: after a revoke through the GraphQL mutation, `cascade_license_revocations` revokes the device token; before the revoke it leaves it alone | same file | token ACTIVE before, REVOKED after, one cascade audit row, none on a second run | PENDING | PENDING |
| C-003 | yes | Revoking an already REVOKED licence is a no-op (changed false, no second audit row, no second cascade); ARCHIVED to REVOKED is refused with CONFLICT and a durable DENIED row; a repeat with the same idempotency key is reported as a replay | same file | as stated | PENDING | PENDING |
| C-004 | yes | Authorisation gates both mutations BEFORE any read or write: a CUSTOMER, DEVICE, SERVICE, permission-less STAFF or wrong-permission STAFF actor gets `PERMISSION_DENIED`, no transition occurs, no licence is looked up (identical answer for existing and missing ids), an authenticated refusal writes one DENIED audit row, and an unauthenticated caller gets `UNAUTHENTICATED` | same file | as stated | PENDING | PENDING |
| C-005 | yes | The refusal audit is bounded: past the per-actor budget no further rows are written (the call is still refused), and a global cap bounds the total | same file | row count stops at the budget | PENDING | PENDING |
| C-006 | yes | Extend from ISSUED and ACTIVATED moves `expires_at` only (status unchanged); from EXPIRING and EXPIRED it writes ACTIVATED through the writer in the same transaction as the date; one SUCCESS audit row carries before and after status and expiry | same file | as stated | PENDING | PENDING |
| C-007 | yes | Extend refuses SUSPENDED, CONVERTED, REVOKED and ARCHIVED with CONFLICT, a durable DENIED row and no change; a REVOKED licence is never moved out of REVOKED by any mutation | same file | as stated | PENDING | PENDING |
| C-008 | yes | Extend input validation: naive datetime, not later than current expiry, in the past, beyond the ceiling, reason too short or with a control character, malformed idempotency key, unknown or malformed id all fail with the coded error and change nothing; overlap with another valid licence of the org is POLICY_DENIED; an archived customer is refused | same file | as stated | PENDING | PENDING |
| C-009 | yes | Extend is idempotent or safely rejected on repeat: same key replays (changed false, replayed true, original audit row), a new key with the same date is rejected, and a failed writer call rolls the date back with it | same file | as stated | PENDING | PENDING |
| C-010 | yes | Integration with G1: a device whose token died (EXPIRED licence, cascade revoked it) re-activates after the extension and receives a fresh token expiring at the new date; before the extension it is refused | same file | as stated | PENDING | PENDING |
| C-011 | yes | AC 8 tripwire: the writer refuses with INTERNAL, before changing anything, when called inside an open transaction without `allow_wrapping_transaction=True`; a first activation still succeeds with the opt-in; extend passes it for the documented reason; a test fires the tripwire and a positive control shows the same call succeeds in autocommit | `pytest tests/test_license_revoke_extend.py tests/test_license_state_machine.py tests/test_activation_licence_transition.py -q` | as stated; mutant (tripwire removed) RED with siblings running | PENDING | PENDING |
| C-012 | yes | AC 9 depth bound: a payload nested past the bound is refused with VALIDATION_FAILED by `redact_public_payload`, `assert_no_restricted_payload_fields` and the writer boundary, with no `RecursionError`, no status change and no audit row; a payload at the bound still passes; a self-referential payload is refused | same files | as stated; mutant (bound removed) RED | PENDING | PENDING |
| C-013 | yes | Neither mutation assigns `.status`: the writer-discipline scan still finds exactly its one known site and the mutations are shown (behaviourally) to reach the writer | `pytest tests/test_license_state_machine.py -q` and the new file | scan equals the known set | PENDING | PENDING |
| C-014 | yes | AC 7 recorded: the statuses a production entry point writes are ISSUED, ACTIVATED, SUSPENDED, REVOKED; EXPIRING, EXPIRED, CONVERTED, ARCHIVED are documented as deliberately unwritten with the owning ticket; the record is pinned by a test that fails if the two sets overlap or leave a status out | new file | as stated | PENDING | PENDING |
| C-015 | yes | Both mutations work end to end over the admin GraphQL schema and the HTTP view with a permitted and a refused actor, with error codes in the response | new file | as stated | PENDING | PENDING |
| C-016 | yes | Mutation verification: removing the AC 8 tripwire, the AC 11 gate (each mutation), the refusal-audit budget, the depth bound and the writer call each turns named tests RED with siblings running; each file restored byte-identical | mutation script, `cmp` | every mutant RED, every restore identical | PENDING | PENDING |
| C-017 | yes | No regression: the full API suite and the Django gates | `make api-check` | exit 0, all tests green | PENDING | PENDING |
| C-018 | yes | Branch is up to date with origin/main, pushed to its own branch, and a Draft PR exists against main | `git rev-list --count HEAD..origin/main`, `gh pr view` | 0; Draft | PENDING | PENDING |
| C-019 | yes | The goal contract validates, structurally now and with `--completion` before the claim | `validate_goal_contract.py` | exit 0 both times | PENDING | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `tests/test_license_revoke_extend.py` (new), `tests/test_license_state_machine.py`, `tests/test_activation_licence_transition.py`, `tests/test_license_suspend_reinstate.py`, `tests/test_revocation_cascade.py`, `tests/test_device_token_remint.py`, each run by file without `--exact`.
- Broader regression verification: `make api-check` (manage.py check, makemigrations --check, pytest on SQLite).
- Mutation verification: one textual change per mutant, run against the new file plus its siblings, RED required, restore and `cmp`.
- Independent verifier: the orchestrator dispatches the reviewers; this run does not.
- Required environment: the repo's `make api-install` venv (Python 3.14), SQLite. Postgres is not available; Postgres-only behaviour is not verified.

## Iteration ledger

### Iteration 0

- Target criterion: baseline
- Hypothesis: the API suite is green on origin/main 93bf8063
- Change or investigation: full suite on the untouched worktree
- Verifier executed: pytest tests (same environment as `make api-check`)
- Result: PENDING
- New evidence: PENDING
- Decision: iterate

## Risks and rollback

- Risks: the writer now fails closed inside a transaction, so any caller or test that wraps it must opt in by name; the only production wrapped caller (device activation) is updated and tested. Another open ticket (86ak109dv expiry job, 86ak5mn2k, 86ak5mn2m) will need to call outside a transaction or opt in with a stated reason. Extend holds the organisation row lock and then the licence row lock; no other path takes them in the opposite order (revoke, suspend and activation take only the licence lock). The five-year ceiling and the refusal of extend-while-suspended are policy choices open to the owner.
- Rollback or recovery: no migration, no data written outside audit rows and `expires_at` / `status` of the licence being acted on. Reverting the PR restores the previous behaviour; a revoke is permanent by product rule (FR-505) and cannot be undone by this code.

## Pause and escalation conditions

- A change to `LEGAL_TRANSITIONS`, a DB migration, or a conflict in `account_schema.py`, `accounts/services.py` or `test_customer_auth_slice.py`: stop and ask the orchestrator.
- Disk free below 13 GiB: stop.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak1090r-license-revoke-extend.md --completion`
- Validator result: PENDING
- Independent verification result: NOT YET RUN
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
