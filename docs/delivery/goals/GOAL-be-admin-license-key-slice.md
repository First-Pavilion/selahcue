# Goal Contract - GOAL-be-admin-license-key-slice

## Identity

- Goal ID: GOAL-be-admin-license-key-slice
- Parent goal ID: GOAL-be-admin-api-foundation
- Title: Admin customer and license-key issuance API slice is ready for review
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Implement the first durable Admin API slice under `implementation/api`: staff-authorized customer organisation creation/search and finite app license-key generation with show-once secret return, hash-only persistence, idempotency, reason capture, safe GraphQL payloads, and append-only audit evidence, while stopping before desktop activation, billing automation, Bible entitlements, downloads, production IdP, signing, or legal/provider decisions.

## Baseline

Verified current state before substantive backend work:

- ClickUp Build Control task `86ajnx548` is readable and currently `in progress`; `_clickup_create_task_comment` has repeatedly returned `INVALID_ARGUMENT` for Admin handoffs.
- `implementation/api` contains a Django 5.2 + Strawberry API foundation with separate `/graphql/admin` and `/graphql/account` endpoints, safe GraphQL errors, staff/customer actor primitives, route contracts, domain app configs, safe non-browser stubs, and 13 passing foundation tests.
- `GOAL-sec-admin-api-foundation.md` is in `GATE_REVIEW` with six mandatory criteria passing.
- No Django models, migrations, durable customer data, durable app license-key data, audit table, customer search, or Admin license-key mutation exists yet.
- User direction places all Django API code under `implementation/api`; Admin frontend code, when created, must live under `implementation/admin`.
- Product, UX, architecture, ADR, and security artifacts define Slice A, app license-key requirements `ADM-FR-020` through `ADM-FR-029`, customer requirements `ADM-FR-010` through `ADM-FR-014`, audit requirements `ADM-FR-070` through `ADM-FR-071`, and the requirement that full keys are shown once and never stored recoverably.
- Staff IdP, customer identity, billing provider, signing envelope, device-token model, first licensed translations, offline grace/deletion policy, retention policy, provider reporting, and production deployment remain unresolved owner decisions.

## Inputs and evidence sources

- User `continue` after security-review gate.
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md`
- `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`
- `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md`
- `docs/delivery/goals/GOAL-be-admin-api-foundation.md`
- `docs/delivery/goals/GOAL-sec-admin-api-foundation.md`
- `implementation/api`
- ClickUp Build Control task `86ajnx548` and recent comments.

## Scope

### In scope

- Django models and migrations for the minimum durable data needed by this slice: customer organisations, app license keys, and audit events.
- Backend services/repositories for customer creation/search and app license-key generation.
- Staff Admin GraphQL query/mutation fields for creating/searching customers and generating a license key.
- Staff permission enforcement using the existing actor context primitives.
- Idempotency keys on mutating Admin GraphQL operations in this slice.
- Reason capture for license-key generation.
- Finite start/end date validation and UTC persistence.
- Show-once generated full key in the successful generation response; subsequent reads/replays show masked metadata only.
- Hash/fingerprint/prefix/suffix persistence for app keys; no recoverable plaintext key storage.
- Audit events for customer creation and license-key generation, with full key excluded.
- TDD tests covering happy path, validation, authorization, idempotency, audit, and no-plaintext persistence.
- API README update documenting the slice boundary and remaining non-goals.

### Non-goals

- Vue 3 Admin frontend implementation.
- Real staff IdP/MFA/session integration or customer identity integration.
- Desktop activation, device tokens, signed policy envelopes, policy refresh, entitlement manifests, licensed downloads, or usage-event ingestion.
- Billing provider integration, subscription automation, invoice/refund/cancel flows, or webhooks beyond existing stubs.
- Bible translation catalogue implementation, Bible entitlement grant/revoke, provider adapters, object/package store, licensed Bible text handling, reporting exports, legal approval, or retention jobs.
- Production deployment settings, KMS/secrets provider selection, lockfile/SBOM/CI work, or operational runbooks.
- Risk acceptance on behalf of Product, Legal, Security, Finance, DevOps, or the user.
- Editing unrelated desktop/mobile/marketing files or reverting unrelated dirty worktree changes.

### Constraints

- Use test-first implementation for behaviour changes.
- Keep code under `implementation/api`.
- Reuse existing Django/Strawberry foundation patterns.
- Do not store, log, return through list/detail reads, or write to audit the full app license key after the generation response.
- Treat header-derived actors as test/dev-only; do not claim production authentication is implemented.
- Sensitive mutation persistence and audit write must share a transaction so audit failure does not silently leave a generated key committed.
- Generated bytecode/test caches must be removed before handoff.
- If ClickUp comment creation fails, record exact pending update text in this Goal Contract.

### Assumptions and unknowns

- ASSUMED: This slice may use the existing test/dev header actor context while production staff IdP remains an owner decision. Owner: Security/Product.
- ASSUMED: A human-friendly generated key format with a non-secret product/type prefix and high-entropy random body is acceptable for local implementation, pending later cryptographic/security review. Owner: Security/Architecture.
- ASSUMED: SQLite migrations are acceptable for local verification; PostgreSQL hosting remains a DevOps decision. Owner: DevOps/Architecture.
- UNKNOWN: Default production trial duration, billing-backed plan names, support extension limits, retention periods, and final app-key cryptographic suite.

## Dependencies and approvals

- API foundation and security review must pass. Status: satisfied by `GOAL-be-admin-api-foundation.md` and `GOAL-sec-admin-api-foundation.md`.
- Product/UX/architecture/security artifacts must define the target behaviour. Status: satisfied for this narrow slice, with production decisions deferred.
- ClickUp write path is desirable but unreliable. Status: read works; comment writes likely fail with `INVALID_ARGUMENT`.
- Later independent code review/security/QA remains required before any release claim. Status: future gate.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Backend goal contract and baseline validate before implementation | `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md` and `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md` | Both validators exit 0 before substantive implementation | Validator output and ClickUp start-comment attempt | PASS |
| C-002 | yes | Customer organisation persistence and Admin GraphQL create/search work with authorization and idempotency | Red/green pytest coverage using `/graphql/admin` | Staff with `manage_customers` can create a customer once by idempotency key and staff with `view_customers` can search it; unauthorized staff receive safe error codes | `implementation/api/tests/test_admin_license_key_slice.py`, `accounts/models.py`, `accounts/services.py`, and `graphql/admin_schema.py` | PASS |
| C-003 | yes | App license-key generation stores no recoverable full key and returns full key only on first successful generation | Red/green pytest coverage plus focused source/DB assertions | Staff with `generate_license_key` can generate a finite key with reason; response includes `fullKey` once, DB stores hash/fingerprint/prefix/suffix only, list metadata is masked, duplicate idempotency does not reveal `fullKey` or create duplicates | `test_staff_can_create_customer_and_generate_show_once_license_key`; `test_license_key_generation_is_idempotent_and_never_replays_full_key`; `license_keys/models.py`; `license_keys/services.py` | PASS |
| C-004 | yes | License-key validation, permission, and audit safety controls are implemented | Red/green pytest coverage | Invalid date windows, missing reason, non-positive limits, missing permission, missing target customer, and audit-write failure all return or raise safe outcomes without committing unsafe key state | `test_license_key_generation_rejects_unsafe_requests_without_committing`; `test_license_key_generation_rolls_back_when_audit_write_fails` | PASS |
| C-005 | yes | Migrations and Django checks are coherent for the new models | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py makemigrations --check --dry-run`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check` | No pending model migrations; Django system check reports no issues | `No changes detected`; `System check identified no issues (0 silenced).` | PASS |
| C-006 | yes | Full API regression and syntax/cache hygiene pass after implementation | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`; `find implementation/api \( -name __pycache__ -o -name .pytest_cache \) -print`; goal validators | Tests pass, compileall exits 0, generated caches are removed, both validators pass | `18 passed`; compileall exit 0; cache scan no output; final validators pass | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused TDD verification: run targeted tests in `implementation/api/tests/test_admin_license_key_slice.py` after writing each failing behaviour test.
- Regression verification: run all `implementation/api/tests`.
- Django verification: run `manage.py makemigrations --check --dry-run` and `manage.py check`.
- Syntax verification: run `compileall implementation/api`, then remove generated `__pycache__` directories.
- Sensitive-data verification: inspect DB/source/test assertions for no full key persistence and run focused `rg` scans for forbidden sample strings after implementation.
- Goal verification: run shared and repo Goal Contract validators before implementation and before handoff.
- Independent verifier: backend implementation can reach `GATE_REVIEW`; independent code/security/QA review remains required before release or `VERIFIED_COMPLETE`.
- Required environment: local repository plus `/private/tmp/selahcue-api-venv`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: The Admin API foundation and handoff artifacts are sufficient to start a bounded backend implementation goal for the first customer/license-key slice.
- Change or investigation: Created this Goal Contract after reading backend-engineer, goal, TDD, brainstorming, workflow, ClickUp, quality-gate, artifact, handoff, PRD, UX, architecture, ADR, security review, and current API foundation evidence.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md`; attempted `_clickup_create_task_comment` on task `86ajnx548`.
- Result: C-001 PASS. Shared validator exited 0; repo validator exited 0. ClickUp create-comment returned `{"error_code":"INVALID_ARGUMENT"}`.
- New evidence: This Goal Contract validates structurally before implementation. Pending ClickUp start text: `Backend implementation started: GOAL-be-admin-license-key-slice, engine=goal, max iterations=6. Scope: first durable Admin API slice under implementation/api only: customer organisation create/search, app license-key generation, hash/fingerprint/prefix/suffix persistence, show-once full key response, idempotency, reason capture, staff permission checks, and append-only audit evidence. Non-goals: Vue Admin frontend, real staff IdP/customer identity, desktop activation, device tokens, signed policies, billing automation, Bible catalogue/entitlements/downloads, provider integrations, production deployment, KMS, legal, or retention decisions. Verification: TDD pytest, makemigrations --check --dry-run, Django check, compileall, cache cleanup, and goal validators.`
- Decision: iterate

### Iteration 2

- Target criterion: C-002 and C-003
- Hypothesis: A narrow customer/key GraphQL contract can prove the first durable Admin slice by requiring create/search customer, show-once full key generation, masked list metadata, hash/fingerprint persistence, and audit evidence from the outside in.
- Change or investigation: Added `test_staff_can_create_customer_and_generate_show_once_license_key` before production code. Verified RED with `Unknown type 'AdminCreateCustomerInput'`. Implemented `CustomerOrg`, `AppLicenseKey`, and `AuditEvent` models, generated initial migrations, added accounts/license-key/audit services, and exposed `adminCreateCustomer`, `adminCustomers`, and `adminGenerateLicenseKey` in the Admin GraphQL schema.
- Verifier executed: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests/test_admin_license_key_slice.py::test_staff_can_create_customer_and_generate_show_once_license_key -q -p no:cacheprovider`.
- Result: C-002 PASS for create/search happy path; C-003 PASS for show-once full-key happy path. RED failed before implementation; GREEN passed after implementation with `1 passed`.
- New evidence: `implementation/api/tests/test_admin_license_key_slice.py`; `implementation/api/selahcue_api/apps/accounts/models.py`; `implementation/api/selahcue_api/apps/accounts/services.py`; `implementation/api/selahcue_api/apps/license_keys/models.py`; `implementation/api/selahcue_api/apps/license_keys/services.py`; `implementation/api/selahcue_api/apps/audit/models.py`; `implementation/api/selahcue_api/apps/audit/services.py`; generated migrations; `implementation/api/selahcue_api/graphql/admin_schema.py`.
- Decision: iterate

### Iteration 3

- Target criterion: C-002, C-003, and C-004
- Hypothesis: Focused negative/idempotency tests will show whether the slice avoids duplicate customer/key rows, never replays the full key, rejects unsafe requests, and rolls back key persistence if audit cannot be written.
- Change or investigation: Added tests for customer idempotency and permission denial; key idempotency with no second full-key replay; invalid date window, short reason, missing permission, missing customer, and audit-write rollback. Added a zero seat/device limit validation case, watched it fail because the mutation accepted zero limits, then added positive-limit validation in customer and license-key services.
- Verifier executed: targeted unsafe-request test before/after limit validation; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests/test_admin_license_key_slice.py -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`.
- Result: C-002 PASS, C-003 PASS, C-004 PASS. Zero-limit test failed before the validation change and passed after. Slice tests reported `5 passed`; full API suite reported `18 passed`.
- New evidence: `test_customer_creation_requires_permission_and_is_idempotent`; `test_license_key_generation_is_idempotent_and_never_replays_full_key`; `test_license_key_generation_rejects_unsafe_requests_without_committing`; `test_license_key_generation_rolls_back_when_audit_write_fails`.
- Decision: iterate

### Iteration 4

- Target criterion: C-005 and C-006
- Hypothesis: The additive model/migration/schema changes should have no pending migration drift, no Django system-check issue, no syntax failure, no generated cache residue, and no sensitive sample key/content strings in the API tree.
- Change or investigation: Ran migration drift check, Django system check, full API pytest, compileall, diff whitespace check, cache scan/cleanup, and focused sensitive-string scan. Updated `implementation/api/README.md` with the implemented slice boundary and remaining non-goals.
- Verifier executed: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py makemigrations --check --dry-run`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`; `find implementation/api \( -name __pycache__ -o -name .pytest_cache \) -print`; focused `rg` scan.
- Result: C-005 PASS and C-006 PASS. `makemigrations --check --dry-run` reported `No changes detected`; Django check reported `System check identified no issues (0 silenced).`; pytest reported `18 passed`; compileall exited 0; cache scan returned no output after cleanup; sensitive-string scan found only README prose and existing redaction fixture names, not generated key/provider/content samples.
- New evidence: command output in this session and README update.
- Decision: gate-review

## Risks and rollback

- Risks: Implemented test/dev actor headers could be mistaken for production staff authentication. Mitigation: README and handoff explicitly label real IdP as out of scope.
- Risks: Early key hashing/fingerprint implementation could be treated as final cryptographic approval. Mitigation: record that final app-key crypto/signing remains a Security/Architecture decision.
- Risks: Audit/event model is minimal and may later need outbox/immutability hardening. Mitigation: keep schema additive and sensitive mutations transactional with audit.
- Risks: ClickUp write failures could hide handoff evidence. Mitigation: record pending comment text in this contract.
- Rollback or recovery: Remove the additive `implementation/api` model/service/schema/test changes and migrations for this slice; no production data exists.

## Pause and escalation conditions

- Pause before implementing real IdP, billing provider, app activation, device tokens, signed policies, entitlement grants, licensed downloads, provider secrets, KMS/object store, retention jobs, destructive actions, production deployment, or external network integration.
- Escalate app-key cryptographic suite, production secret custody, support extension limits, billing-backed plan names, retention periods, and legal/licensing terms to their owners.
- If durable implementation is blocked by unavailable dependencies or verifier environment failure, return `BLOCKED` with the smallest owner action.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-license-key-slice.md`.
- Validator result: Passed after implementation and final ledger update.
- Independent verification result: Backend implementation reached gate-review evidence; independent code review/security/QA remains required before release or `VERIFIED_COMPLETE`.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None for this backend slice. Production blockers remain for real staff IdP/customer identity, app-key crypto review, signing/device-token/activation, billing provider, Bible catalogue/entitlements/downloads, provider/legal/KMS/retention/deployment decisions.
- ClickUp final evidence comment: `_clickup_create_task_comment` returned `{"error_code":"INVALID_ARGUMENT"}`. Pending text: `Backend slice ready for gate review: GOAL-be-admin-license-key-slice reached GATE_REVIEW. Implemented the first durable Admin API slice under implementation/api: CustomerOrg, AppLicenseKey, and AuditEvent models/migrations; Admin GraphQL adminCreateCustomer, adminCustomers, and adminGenerateLicenseKey; service-layer staff permission checks, idempotency, finite date and positive limit validation, show-once full key response, masked metadata, hash/fingerprint persistence, and transactional audit evidence. Final checks: pytest implementation/api/tests 18 passed, makemigrations --check --dry-run no changes, Django check no issues, compileall exit 0, goal validators pass, generated cache scan clean. Release/production remains not approved: real staff IdP/customer identity, app-key crypto review, activation/device tokens/signed policies, billing provider, Bible catalogue/entitlements/downloads, provider/legal/KMS/retention/deployment decisions remain future gates. Recommended next role: code-reviewer, then security-reviewer if code review does not require rework.`
