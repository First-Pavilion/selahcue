# Goal Contract — 86ak5mn0c-suspend-reinstate

## Identity

- Goal ID: 86ak5mn0c-suspend-reinstate
- Parent goal ID: NONE
- Title: Staff can suspend a licence with a mandatory reason and reinstate it to exactly its prior status, soft (running devices keep working), audited, throttled and idempotent
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5mn0c
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`adminSuspendLicenseKey` and `adminReinstateLicenseKey` exist on the admin GraphQL surface, gated by their own staff permissions, writing through `apply_license_status_transition` outside any wrapping transaction, so a suspended licence refuses new activations and manifest issuance while every already-issued device token keeps working, and reinstatement returns the licence to the status recorded at suspension time.

## Baseline

Verified on origin/main 12359b95 (and re-verified after merging origin/main 09c69736):

- The state machine (`apps/license_keys/state_machine.py`) owns the transition table, the `prior_status` bookkeeping and the audit contract; nothing called it for SUSPENDED.
- `StaffPermission` had no suspend or reinstate member.
- `cascade_license_revocations` excluded only `ACTIVATABLE_KEY_STATUSES`, so SUSPENDED would have killed device tokens exactly like REVOKED.
- `authenticate_device_token` checks the token and never the licence, so nothing but a route's own check stopped a suspended licence's device from using a commercial route.
- No cloud-feature endpoint exists in `implementation/api`; three `device_token` routes (`downloads:prepare`, `downloads/<lease_id>:complete`, `usage-events:batch`) are declared and answer 501.

## Inputs and evidence sources

- ClickUp 86ak5mn0c (description, three comments), 86ak1090r (sibling), 86ak1099u (cascade correctness), 86ak10g8q (D3).
- `docs/product/prds/SelahCue-Platform-PRD.md` FR-504, FR-510, FR-522, FR-531, FR-539, FLOW-506, section 13, section 19.
- `state_machine.py` module docstring, "Calling contract" sections.
- Review round 1 of PR #218 (Cody, Shadow, Vera, Quinn): all findings applied.

## Scope

### In scope

- `StaffPermission.SUSPEND_LICENSE_KEY` and `REINSTATE_LICENSE_KEY`.
- Service functions `suspend_license_key` / `reinstate_license_key` and the two GraphQL mutations; `prior_status` on the admin read type; payloads return a licence view WITHOUT the customer and a `replayed` flag.
- Gate with `require_staff_permission` before the writer; per-staff-actor throttle (FR-539); fail-closed guard when called inside a transaction; actor ids longer than the audit column refused at the boundary.
- Retry recognition INSIDE the writer under the row lock: an additive optional `recognise_retry` parameter on `apply_license_status_transition` (opt-in; device activation does not use it).
- One named enforcement point for commercial device calls (`devices.services.require_commercial_service`) and a `license_gate` declaration on every route whose auth context is `device_token` in `graphql/route_contracts.py`, swept by a test and tied to the URLconf by a second test.
- Narrowing of the revocation cascade so a licence suspended from an ACTIVATABLE status keeps its device tokens (needed to honour this ticket's token-survival criteria; accepted by the orchestrator to stay in this PR).
- Tests, including Postgres races; the mutation script and its logs are committed under `docs/delivery/goals/86ak5mn0c-evidence/`.

### Non-goals

- The rest of the cascade rework (row locking, key-driven scan): 86ak1099u.
- Revoke / extend mutations and the writer-level in-transaction tripwire: 86ak1090r.
- Dunning-triggered suspension (FR-535), the staff authenticator (17tnw2az0n5), customer notification, the Vue console.
- Any cloud/AI endpoint (none exists in this API; see criterion C-014).
- Auditing permission denials, reinstatement past the licence window, zero-width characters in the shared reason validator: follow-ups filed by the orchestrator.

### Constraints

- Never assign `.status` outside the state machine (writer-discipline scan).
- Call the writer outside any wrapping transaction so a DENIED row is durable.
- No secrets in audit rows, errors or logs.

### Assumptions and unknowns

- ASSUMED: staff authority is platform-wide, so "wrong tenant" reduces to "no licence reference leaks to a non-staff actor"; owner: Priya.
- ASSUMED: 30 requests / 60 s per staff actor is comfortable; tunable in settings.
- KNOWN LIMIT: a request that was itself a no-op (the licence was already suspended) wrote no audit row, so a later retry of it cannot be recognised and applies if the licence has since moved. Deliberately not fixed: an audit row for a no-op is not wanted. Pinned by `test_a_retry_of_a_request_that_was_itself_a_no_op_is_not_recognised`.
- KNOWN LIMIT: the staff authenticator is still the `X-SelahCue-*` header bridge (17tnw2az0n5).
- KNOWN, PRE-EXISTING, OUT OF SCOPE: what a suspend-only actor can read through the summary view is the masked key, prefix, suffix, feature scope, dates and prior status, and on an already-suspended licence that read writes no audit row. `AdminLicenseKey.customer` is still not permission-gated for generate-only actors (that path writes a licence and an audit row). Neither is changed here.
- KNOWN LIMIT: the retry lookup has no composite index; the planner may use the `(action, created_at)` index and filter, moving to the `request_id` index as the action grows (checked at 200k rows by Vera). Revisit if the audit table gets very large (noted on 86ak1099u by the orchestrator).

## Dependencies and approvals

- 86ak5mn00 state machine: merged. D3: closed 2026-08-25. The cascade overlap with 86ak1099u is accepted by the orchestrator.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. Test names below are in `implementation/api/tests/test_license_suspend_reinstate.py` unless a path says otherwise.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Suspend succeeds from ISSUED/ACTIVATED/EXPIRING/EXPIRED/CONVERTED, records prior status and writes one SUCCESS audit row | `pytest tests/test_license_suspend_reinstate.py -k suspend_succeeds` | exit 0 | `test_suspend_succeeds_from_every_suspendable_status_and_records_where_it_came_from` | PASS |
| C-002 | yes | Suspend of REVOKED/ARCHIVED is refused CONFLICT and leaves a durable DENIED row, in service and over HTTP | `pytest ... -k "terminal_licence or durable"` | exit 0 | `test_suspend_of_a_terminal_licence_is_refused_and_the_denial_survives`, `test_graphql_a_refused_suspend_over_http_leaves_its_denied_row` | PASS |
| C-003 | yes | Reinstate returns the exact prior status for every suspendable source, proven separately for ACTIVATED and EXPIRING | `pytest ... -k reinstate_returns` | exit 0 | `test_reinstate_returns_the_exact_prior_status` | PASS |
| C-004 | yes | Unauthorised actors (none, customer, device, service, staff without the specific permission, staff with revoke only) get UNAUTHENTICATED / PERMISSION_DENIED, with no transition, no audit row and no existence oracle | `pytest ... -k "refused_to_anyone or oracle or separate_authorities"` | exit 0 | the three tests named | PASS |
| C-005 | yes | A retry takes effect once, including after another staff member's action between the copies, decided under the row lock | `pytest ... -k "retry or duplicate or stale"`, and on Postgres `tests/test_concurrency_postgres.py -k "retried or between"` | exit 0 | `test_a_duplicate_reinstate_after_another_staff_member_suspended_again_changes_nothing`, `test_a_duplicate_request_with_another_staff_action_between_the_copies_is_not_reapplied` | PASS |
| C-006 | yes | Reason and key validation; uniform NOT_FOUND (same code and message) for any reference that names nothing | `pytest ... -k "reason or idempotency or names_nothing or spellings"` | exit 0 | the matching tests | PASS |
| C-007 | yes | Called inside a transaction the mutations fail closed before any change | `pytest ... -k inside_a_transaction` | exit 0 | `test_a_call_inside_a_transaction_fails_closed_before_changing_anything` | PASS |
| C-008 | yes | Throttled per staff actor under the shared lifecycle budget, gate first, with the shipped default (30 per 60 s) | `pytest ... -k "rate_limited or budget or throttle"` | exit 0 | the matching tests | PASS |
| C-009 | yes | Suspension leaves device tokens valid through a cascade run; REVOKED kills; manifest and activation refused while suspended; recovery without re-activation or slot use; cached entitlement unchanged | `pytest ... -k "device or token or cascade or manifest or activation or recovery or cached"` | exit 0 | section 5 of the module | PASS |
| C-010 | yes | Audit rows pair suspend/reinstate and carry no secret | `pytest ... -k "cycle or secret"` | exit 0 | the matching tests | PASS |
| C-011 | yes | Races on Postgres: suspend vs first activation (both orders), vs revoke (both orders), vs itself, vs reinstate, and a duplicate with another action between | `SQL_ENGINE=django.db.backends.postgresql ... pytest tests/test_concurrency_postgres.py` | exit 0 | 18 passed | PASS |
| C-012 | yes | Mutation checks turn the guarding tests red; no unexplained survivor; a stale "equivalent" declaration also fails | `python docs/delivery/goals/86ak5mn0c-evidence/mutate.py --python "$VENV_PYTHON" --allow-skip` for the SQLite mutants, then `python docs/delivery/goals/86ak5mn0c-evidence/mutate.py --python "$VENV_PYTHON" --postgres` (SQL_* pointing at a disposable Postgres) | both exit 0: 46 mutants KILLED (43 SQLite + 4 Postgres, minus the one equivalent) and one declared equivalent survivor | `docs/delivery/goals/86ak5mn0c-evidence/mutation-sqlite-a.txt`, `mutation-sqlite-b.txt`, `mutation-postgres.txt`, each stamped with the code head it ran against (c4f57d01). The equivalent survivor is M11 (the retry lookup counting non-SUCCESS rows: refusal rows carry a different action name, so the filter is redundant). The retry-lookup-before-the-lock mutant (P03) and the lookup-disabled mutant (P02) were run three times in total (twice on 845e4695, once on c4f57d01) and the between-the-copies race test was red every time | PASS |
| C-013 | yes | `manage.py check`, `makemigrations --check --dry-run`, the full SQLite suite and the Postgres concurrency file plus the new module exit 0 | commands in the PR body | all exit 0 at the code head | PASS AT CODE HEAD c4f57d01 (production source identical to the final head; the later commits change docs and evidence only): check 0, makemigrations 0, full SQLite 1127 passed / 19 skipped / 1 xfailed exit 0, Postgres concurrency 18 passed exit 0, new module on Postgres 178 passed exit 0. Earlier heads, for honesty: at 845e4695 the full SQLite run was also green (1117 passed); at the merged head 87de5da4 one wall-clock test in `test_cache_socket_timeouts.py` failed at machine load 45-57 and the file passed on rerun (a load flake, not a green run); the round-2 reviewers saw `test_resend_verification` (a millisecond assertion) fail once under load. No flake fired at c4f57d01 | PASS |
| C-014 | yes | Ticket criterion 8, "cloud features are refused while suspended and resume on reinstatement": ONE named enforcement point (`require_commercial_service`, over the shared predicate `license_allows_commercial_service`) used by activation and the manifest; every route whose auth context is exactly `device_token` declares `license_gate` in `graphql/route_contracts.py`; and three tests guard that: a sweep that fails on an undeclared route, a walk of the URL resolver that fails when a `v1/` route has no contract entry (or the reverse), and a behavioural check that calls each declared route with a suspended licence's token. Limits, stated plainly: no cloud endpoint exists in this API yet; the three 501 routes are declared but the sweep can only check that they refuse once they answer; a route registered outside `v1/` is not seen; the account-session bearer on `activations:with-session` is gated through activation (and answers NOT_FOUND, not POLICY_DENIED, on a suspended licence: pinned by a test, behaviour unchanged) | `pytest ... -k "declares or declaration or enforcement_point or sweep or urlconf or session_activation"` | exit 0 | section 6 and 7 of the module | PASS |
| C-015 | yes | New activations RESUME after reinstatement (device_limit 2, and first activation of an ISSUED licence) | `pytest ... -k "admitted_after_reinstatement or first_activated"` | exit 0 | section 7 of the module | PASS |
| C-016 | yes | The cascade spares a suspended licence's tokens only when it was suspended from an activatable status; EXPIRED and CONVERTED still die | `pytest ... -k cascade` and `tests/test_revocation_cascade.py` | exit 0 | section 8 of the module and the parametrised test in `tests/test_revocation_cascade.py` | PASS |
| C-017 | yes | Neither lifecycle payload widens what a lifecycle permission can read: a suspend-only or reinstate-only actor cannot ask for the customer (direct selection or inline fragment) | `pytest ... -k "customer_details"` | exit 0 | `test_a_suspend_only_actor_cannot_read_customer_details_through_the_payload`, `test_neither_lifecycle_payload_can_be_asked_for_customer_details` | PASS |
| C-018 | yes | Actor ids longer than the audit column are refused before any write; at the limit a refusal keeps its DENIED row (Postgres included) | `pytest ... -k "actor_id or header_bridge"` on SQLite and Postgres | exit 0 | section 9 of the module | PASS |
| C-019 | yes | The `replayed` flag is exact on both mutations over HTTP: true only for a request that already took effect (suspend and reinstate), false for a plain no-op, and a replay refreshes the caller's in-memory licence | `pytest ... -k "replay or no_op"` | exit 0 | `test_graphql_retry_reports_changed_false`, `test_graphql_reinstate_retry_is_flagged_as_a_replay`, `test_graphql_a_plain_no_op_is_not_flagged_as_a_replay`, `test_a_replay_refreshes_the_callers_licence_instance` | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: new test module (SQLite and Postgres) and the Postgres race tests.
- Broader regression verification: full API suite on SQLite; concurrency file on Postgres 16.
- Independent verifier: Cody, Shadow, Vera, Quinn (dispatched by the orchestrator); rounds 1 and 2 complete, round 3 (verification of this update) pending.
- Required environment: own venv, throwaway postgres:16-alpine.

## Iteration ledger

### Iteration 1

- Target criterion: all
- Hypothesis: a thin service layer over the writer plus the gate, budget and retry identity is sufficient.
- Change or investigation: first implementation (head 1abc328b).
- Verifier executed: gates and mutation run recorded in the PR body.
- Result: four reviewers: 0 blockers, 0 high; conditions C1-C5, security fixes S1-S3, test gaps T1-T7, docs D1-D6.
- New evidence: review round 1 report.
- Decision: iterate

### Iteration 2

- Target criterion: C-005, C-012, C-013, C-014 to C-018 and every review finding
- Hypothesis: moving the retry lookup under the row lock, adding one enforcement point with a swept declaration, scoping the cascade exemption by prior status and trimming the payload closes every finding without widening scope.
- Change or investigation: see PR #218 (origin/main 09c69736 merged first).
- Verifier executed: gates and mutation run by head SHA in the PR body.
- Result: gates green at 845e4695 and, after the merge, one load-flake failure recorded in C-013; every non-equivalent mutant killed.
- New evidence: the mutation logs under `docs/delivery/goals/86ak5mn0c-evidence/`.
- Decision: iterate (round 2 conditions)

### Iteration 3

- Target criterion: C-012, C-013, C-014, C-017, C-019 and every round 2 finding
- Hypothesis: tying the sweep to the URLconf, pinning the reinstate twin of each regression, and sharing one predicate closes the round 2 conditions without a behaviour change.
- Change or investigation: see PR #218 (origin/main merged again at c4f57d01; it brought a Django 6.1.2 pin).
- Verifier executed: gates and the extended mutation run at c4f57d01, recorded in the PR body and the evidence directory.
- Result: all gates exit 0 at c4f57d01; 46 mutants killed, one declared equivalent survivor.
- New evidence: `docs/delivery/goals/86ak5mn0c-evidence/mutation-*.txt` stamped c4f57d01.
- Decision: gate-review

## Risks and rollback

- Risks: the cascade narrowing overlaps 86ak1099u (accepted); `apply_license_status_transition` gained an optional parameter and 86ak1090r edits the same file; the throttle fails open when the cache store is down.
- Rollback or recovery: revert the PR; no migration is involved.

## Pause and escalation conditions

- Owner decision needed if the writer-level in-transaction tripwire (86ak1090r AC 8) is wanted on this ticket instead.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5mn0c-suspend-reinstate.md`
- Validator result: OK (structural)
- Independent verification result: round 1 all PASS WITH CONDITIONS; round 2 Cody and Shadow APPROVE WITH CONDITIONS, Vera and Quinn APPROVE; those conditions are applied in this update and await re-verification
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none known
- ClickUp final evidence comment: posted by the orchestrator
