# Goal Contract — 86ak5mn0c-suspend-reinstate

## Identity

- Goal ID: 86ak5mn0c-suspend-reinstate
- Parent goal ID: NONE
- Title: Staff can suspend a licence with a mandatory reason and reinstate it to exactly its prior status, soft (devices keep working), audited, throttled and idempotent
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5mn0c
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`adminSuspendLicenseKey` and `adminReinstateLicenseKey` exist on the admin GraphQL surface, gated by their own staff permissions, writing through `apply_license_status_transition` outside any wrapping transaction, so a suspended licence refuses new activations and manifest issuance while every already-issued device token keeps working, and reinstatement returns the licence to the status recorded at suspension time.

## Baseline

Verified on origin/main 12359b95:

- The state machine (`apps/license_keys/state_machine.py`) owns the transition table, the `prior_status` bookkeeping and the audit contract; nothing calls it for SUSPENDED.
- `StaffPermission` has no suspend or reinstate member.
- `cascade_license_revocations` excludes only `ACTIVATABLE_KEY_STATUSES`, so SUSPENDED would kill device tokens exactly like REVOKED.
- `_assert_key_activatable`, `build_entitlement_manifest` and `refresh_license` already treat SUSPENDED as not activatable (verified, not rebuilt).
- No cloud-feature endpoint exists in `implementation/api`.

## Inputs and evidence sources

- ClickUp 86ak5mn0c (description, three comments), 86ak1090r (sibling), 86ak1099u (cascade correctness), 86ak10g8q (D3).
- `docs/product/prds/SelahCue-Platform-PRD.md` FR-504, FR-510, FR-522, FR-539, FLOW-506, section 13, section 19.
- `state_machine.py` module docstring, "Calling contract" sections.

## Scope

### In scope

- `StaffPermission.SUSPEND_LICENSE_KEY` and `REINSTATE_LICENSE_KEY`.
- Service functions `suspend_license_key` / `reinstate_license_key` and the two GraphQL mutations; `prior_status` on the admin read type.
- Gate with `require_staff_permission` before the writer; per-staff-actor throttle (FR-539); fail-closed guard when called inside a transaction; request-level retry recognition.
- One-line narrowing of the revocation cascade so SUSPENDED is spared (needed to honour this ticket's token-survival criteria).
- Tests, including Postgres races.

### Non-goals

- The rest of the cascade rework (row locking, key-driven scan): 86ak1099u.
- Revoke / extend mutations and the writer-level in-transaction tripwire: 86ak1090r.
- Dunning-triggered suspension (FR-535), staff authenticator replacement (17tnw2az0n5), customer notification.
- Any cloud/AI endpoint (none exists in this API).

### Constraints

- Never assign `.status` outside the state machine (writer-discipline scan).
- Call the writer outside any wrapping transaction so a DENIED row is durable.
- No secrets in audit rows, errors or logs.

### Assumptions and unknowns

- ASSUMED: staff authority is platform-wide, so "wrong tenant" reduces to "no licence reference leaks to a non-staff actor"; owner: Priya.
- ASSUMED: 30 requests / 60 s per staff actor is comfortable; tunable in settings.

## Dependencies and approvals

- 86ak5mn00 state machine: merged. D3: closed 2026-08-25.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Suspend succeeds from ISSUED/ACTIVATED/EXPIRING/EXPIRED/CONVERTED, records prior status and one SUCCESS audit row | `pytest tests/test_license_suspend_reinstate.py -k suspend_succeeds` | exit 0 | PR body | PENDING |
| C-002 | yes | Suspend of REVOKED/ARCHIVED is refused CONFLICT and leaves a durable DENIED row | `pytest ... -k terminal_licence` | exit 0 | PR body | PENDING |
| C-003 | yes | Reinstate returns the exact prior status for every suspendable source, proven separately for ACTIVATED and EXPIRING | `pytest ... -k reinstate_returns` | exit 0 | PR body | PENDING |
| C-004 | yes | Unauthorised actors (none, customer, device, service, staff without the specific permission, staff with revoke only) get UNAUTHENTICATED / PERMISSION_DENIED and no transition or audit row | `pytest ... -k "refused_to_anyone or oracle"` | exit 0 | PR body | PENDING |
| C-005 | yes | Retry with the same key takes effect once, including a stale retry after an intervening reinstate/suspend | `pytest ... -k "retry or stale"` | exit 0 | PR body | PENDING |
| C-006 | yes | Reason and key validation, uniform NOT_FOUND for any reference that names nothing | `pytest ... -k "reason or idempotency or names_nothing or spellings"` | exit 0 | PR body | PENDING |
| C-007 | yes | Called inside a transaction the mutations fail closed before any change | `pytest ... -k inside_a_transaction` | exit 0 | PR body | PENDING |
| C-008 | yes | Throttled per staff actor under the shared lifecycle budget, gate first | `pytest ... -k "rate_limited or budget or throttle"` | exit 0 | PR body | PENDING |
| C-009 | yes | Suspension leaves device tokens valid through a cascade run; REVOKED kills; activation and manifest refused while suspended; recovery without re-activation or slot use; cached entitlement unchanged | `pytest ... -k "device or token or cascade or manifest or activation or recovery or cached"` | exit 0 | PR body | PENDING |
| C-010 | yes | Audit rows pair suspend/reinstate and carry no secret | `pytest ... -k "cycle or secret"` | exit 0 | PR body | PENDING |
| C-011 | yes | Races on Postgres: suspend vs first activation (both orders), vs revoke (both orders), vs itself, vs reinstate | `SQL_ENGINE=... pytest tests/test_concurrency_postgres.py` | exit 0 | PR body | PENDING |
| C-012 | yes | Mutation checks turn the named tests red | `86ak5mn0c-mutate.py` | each mutant killed | PR body | PENDING |
| C-013 | yes | `manage.py check`, `makemigrations --check --dry-run`, full pytest on SQLite exit 0 | commands | exit 0 | PR body | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: new test module and Postgres race tests.
- Broader regression verification: full API suite on SQLite; concurrency file on Postgres 16.
- Independent verifier: Cody, Shadow, Vera, Quinn (dispatched by the orchestrator).
- Required environment: own venv, throwaway postgres:16-alpine.

## Iteration ledger

### Iteration 1

- Target criterion: all
- Hypothesis: thin service layer over the writer plus the gate, budget and retry identity is sufficient.
- Change or investigation: see PR.
- Verifier executed: see PR body evidence by head SHA.
- Result: recorded in the PR.
- New evidence: PR body.
- Decision: handoff to review

## Risks and rollback

- Risks: the cascade narrowing overlaps 86ak1099u (one line, flagged); in-flight duplicate reinstate writes one extra DENIED row before replaying.
- Rollback or recovery: revert the PR; no migration is involved.

## Pause and escalation conditions

- Owner decision needed if the writer-level in-transaction tripwire (86ak1090r AC 8) is wanted on this ticket instead.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5mn0c-suspend-reinstate.md`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: none known
- ClickUp final evidence comment: pending
