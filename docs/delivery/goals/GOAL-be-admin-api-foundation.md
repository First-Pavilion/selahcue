# Goal Contract - GOAL-be-admin-api-foundation

## Identity

- Goal ID: GOAL-be-admin-api-foundation
- Parent goal ID: GOAL-sec-admin-licensing
- Title: Admin licensing Platform API foundation exists under implementation/api
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Create the first Django + Strawberry Platform API foundation under `implementation/api`, with separate staff and customer GraphQL surfaces, documented domain app boundaries for account, billing, license-key, entitlement, catalogue, download, and audit work, security-first request primitives, and focused tests that prove the foundation rejects missing permissions and cross-tenant account access before later feature slices add real licensing, billing, entitlement, and download behaviour.

## Baseline

Verified current state before substantive backend work:

- ClickUp Build Control task `86ajnx548` is readable and currently `in progress`.
- User direction on 2026-08-08 says Vue 3 Admin code belongs under `implementation/admin` and Django API code belongs under `implementation/api`.
- `implementation/api` does not exist yet.
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` recommends the backend foundation sequence after security review: Django project, modular contexts, Strawberry schema split, staff IdP integration, RBAC middleware, audit ledger, database migrations, and outbox.
- `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` requires separate staff/customer schema namespaces, resolver/service authorization, tenant-scoped repository APIs, CSRF/CORS/CSP/security defaults, GraphQL production guardrails, idempotency, redaction, and no licensed Bible text in GraphQL/download diagnostics.
- Local macOS Python 3.9, bundled Python 3.12, and the initial environment did not include Django, Strawberry, or pytest.
- A throwaway verifier virtualenv exists at `/private/tmp/selahcue-api-venv`; dependency installation succeeded after approved network access with Django 5.2.17, strawberry-graphql 0.323.2, strawberry-graphql-django 0.86.8, pytest 8.4.2, and pytest-django 4.13.0.
- No repository `AGENTS.md` was found; `CLAUDE.md` and `implementation/README.md` define the repo layout and current platform conventions.

## Inputs and evidence sources

- User request: `$backend-engineer` work on account, billing, license-key, entitlement, and download architecture based on prior handoffs.
- User refinement: Admin should be Vue 3; Django-Strawberry GraphQL API should serve both Admin and normal users.
- User refinement: Admin code belongs under `implementation/admin`; Django API code belongs under `implementation/api`.
- ClickUp Build Control task `86ajnx548` and recent comments.
- `CLAUDE.md`
- `implementation/README.md`
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md`
- `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- Current Django and Strawberry docs checked on 2026-08-08 for Django 5.2 LTS compatibility, Strawberry Django installation, GraphQLView options, and production GraphiQL/introspection posture.

## Scope

### In scope

- New backend source root under `implementation/api`.
- Django 5.2 LTS project scaffold with Strawberry GraphQL dependencies declared.
- Separate staff Admin and customer Account GraphQL schemas and URL endpoints.
- Security defaults for browser GraphQL surfaces: CSRF middleware retained, secure cookie and header settings declared, GraphiQL disabled outside debug, GET GraphQL queries disabled, multipart uploads disabled.
- Pure backend primitives for actor context, staff permission checks, customer tenant checks, idempotency key validation, reason validation, stable error codes, route contracts, and request redaction boundaries.
- Placeholder domain Django apps for customer account, billing, license keys, Bible catalogue, entitlements, downloads, and audit/outbox, ready for later vertical slices.
- Narrow desktop and billing/provider URL contract stubs that return safe `NOT_IMPLEMENTED` JSON without licensed content, full keys, or provider secrets.
- Focused tests under `implementation/api/tests` proving the foundation contract, permission denial, cross-tenant denial, idempotency/reason validation, safe redaction, and GraphQL smoke behaviour.
- Local README and goal evidence updates.

### Non-goals

- Vue 3 Admin frontend implementation under `implementation/admin`.
- Real staff IdP/MFA integration, customer login, billing provider integration, provider adapters, KMS/object-store integration, signed policy cryptography, app-key generation, device activation, real database schema/migrations, licensed Bible package bytes, download lease issuance, reporting exports, production deployment, or secrets.
- Legal/Product approval of first licensed translations, retention, provider reporting, offline grace, export/copy limits, or customer-facing terms.
- Moving or modifying desktop/mobile implementation code.
- Creating duplicate Markdown tickets in place of ClickUp tasks.

### Constraints

- All generated backend code must live under `implementation/api`.
- Keep docs in the established `docs/...` tree.
- Use tests first for behaviour-bearing production code.
- Preserve Django CSRF middleware for browser GraphQL and do not use frontend route guards as security controls.
- Do not include full license keys, provider secrets, signing keys, or licensed Bible text in code fixtures, logs, GraphQL payloads, diagnostics, or tests.
- If ClickUp comment creation still fails, record the pending start/final update text in this contract rather than claiming ClickUp was updated.

### Assumptions and unknowns

- ASSUMED: The first backend implementation slice can be a non-production foundation with explicit stubs because Product/Legal/Security/DevOps decisions still block real activation, download, billing, and key-custody behaviour. Owner: Product/Architecture/Security.
- ASSUMED: Django 5.2 LTS is the correct baseline because current Django docs identify it as the LTS release supporting Python 3.10 through 3.14. Owner: Backend/DevOps.
- ASSUMED: Strawberry Django is declared now for future Django ORM integration, while the initial schema uses plain Strawberry types to keep authorization tests explicit. Owner: Backend.
- UNKNOWN: Staff IdP, customer identity model, hosting/database/object store, KMS/secrets provider, exact signing suite, retention policy, billing provider, first licensed translations, provider terms, and legal reporting payloads. Owner: Product/Security/Legal/Finance/DevOps.

## Dependencies and approvals

- Product/Admin brief, UX handoff, architecture handoff, and security review exist. Status: satisfied for this foundation slice.
- Network approval for dependency verification was required and granted for the throwaway virtualenv install. Status: satisfied for local verification only; no vendored dependencies are added to the repo.
- Staff IdP, customer identity, billing provider, KMS/object store, signing suite, first translations, and retention decisions remain future blockers for real production behaviour. Status: not blocking this foundation scaffold.
- Independent code/security review remains required before this foundation can be treated as release-ready. Status: read-only code review completed for this foundation; release security review remains future work.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Backend Goal Contract and baseline are valid before implementation | `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md` and `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md` | Both validators exit 0 before production code changes | Both validators passed before implementation; ClickUp start comment returned `INVALID_ARGUMENT`, so pending text is recorded in this contract | PASS |
| C-002 | yes | Django/Strawberry API scaffold is confined to `implementation/api` and declares current backend dependencies | `find implementation/api -maxdepth 4 -type f` and `python -m compileall implementation/api` | Project files exist only under `implementation/api`; Python files compile successfully | `implementation/api` file list contains only source/test/config files; compileall exited 0 | PASS |
| C-003 | yes | Staff and account GraphQL surfaces are separated and configured with security-first defaults | `/private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check` and focused pytest tests | Django check exits 0; tests prove `/graphql/admin` and `/graphql/account` are separate, GET queries disabled, multipart disabled, production GraphiQL disabled, CSRF retained for browser GraphQL, and introspection disabled outside debug | Django check exited 0; pytest `12 passed`; `implementation/api/selahcue_api/urls.py` registers separate endpoints | PASS |
| C-004 | yes | Authorization primitives deny missing staff permissions and cross-tenant account access with stable safe error codes | `/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q` | Tests pass for `UNAUTHENTICATED`, `PERMISSION_DENIED`, `NOT_FOUND`, idempotency key validation, reason validation, safe GraphQL error formatting, test/dev-only actor headers, and redaction boundaries | Pytest `12 passed`; tests cover `selahcue_api.graphql.context`, `errors`, `views`, and `redaction` | PASS |
| C-005 | yes | Account, billing, license-key, catalogue, entitlement, download, audit, and outbox boundaries are represented as Django app contracts without real production side effects | Django app registry test and README review | Tests confirm expected app labels are installed; README states the boundaries and blocked future decisions | Pytest app-registry test passed; `implementation/api/README.md` documents foundation-only status and open decisions | PASS |
| C-006 | yes | Desktop and billing/provider URL stubs expose stable command paths without returning licensed content or secret-bearing payloads | Focused pytest tests against Django test client | Stub endpoints return safe `501` JSON with stable codes and no `license_key`, `secret`, `bible_text`, or `content` fields, and are not blocked by browser CSRF because they will use token/signature auth later | Pytest stub-response and CSRF-enforcement tests passed; `implementation/api/selahcue_api/platform/views.py` returns safe `NOT_IMPLEMENTED` payloads | PASS |
| C-007 | yes | Goal ledger, validators, and final scoped status are updated honestly | Shared/repo goal validators and `git status --short docs/delivery/goals/GOAL-be-admin-api-foundation.md implementation/api` | Validators exit 0; status shows only the new backend foundation and this goal contract for this slice | Shared and repo validators exited 0; scoped status shows `?? docs/delivery/goals/GOAL-be-admin-api-foundation.md` and `?? implementation/api/`; ClickUp final comment returned `INVALID_ARGUMENT` and pending text is recorded below | PASS |
| C-008 | yes | Independent code review findings are evaluated and Important findings are addressed before gate handoff | Read-only code reviewer result plus red-green regression tests and final verifier run | No Critical findings remain; Important review findings for CSRF split, trusted actor headers, safe GraphQL errors, introspection, and camelCase redaction are fixed or explicitly deferred with rationale | Code review returned `With fixes`; review-regression red run failed 5 tests; final pytest `12 passed`; minor SECRET_KEY hardening remains follow-up | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Red test verification: add focused tests under `implementation/api/tests`, run them before production modules exist, and record the expected failure.
- Focused verification: run `/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q`.
- Django verification: run `/private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`.
- Syntax/package verification: run `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`.
- Goal verification: run both shared and repo Goal Contract validators before and after implementation.
- Independent verifier: read-only code review for this foundation plus security-reviewer follow-up before production readiness; this backend slice ends at `GATE_REVIEW`.
- Required environment: local repository plus throwaway `/private/tmp/selahcue-api-venv` verifier environment.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: A bounded backend foundation goal can be validated before any implementation work, using existing Admin PRD, UX, architecture, and security handoff evidence.
- Change or investigation: Created this Goal Contract from the shared template after reading backend-engineer, goal, TDD, workflow, ClickUp, quality gate, artefact, and test-writing instructions.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md`; attempted `_clickup_create_task_comment` on task `86ajnx548`.
- Result: C-001 PASS. Shared validator exited 0; repo validator exited 0. ClickUp create-comment returned `{"error_code":"INVALID_ARGUMENT"}`.
- New evidence: This Goal Contract validates structurally before production code work. Pending ClickUp start text: `Backend foundation started: GOAL-be-admin-api-foundation, engine=goal, max iterations=6. Scope: create the Django 5.2 + Strawberry Platform API foundation under implementation/api only, with separate /graphql/admin and /graphql/account schemas, placeholder domain app boundaries for account, billing, license-key, Bible catalogue, entitlement, download, audit/outbox, secure request primitives, safe desktop/billing URL stubs, and focused tests. Non-goals: no real IdP, billing provider, app-key generation, device activation, signed policy, entitlement grant, licensed Bible content, download leases, provider integration, secrets, or production deployment. Verifiers: goal validators, pytest, Django manage.py check, compileall, scoped git status.`
- Decision: iterate

### Iteration 2

- Target criterion: C-002 through C-006
- Hypothesis: A minimal Django + Strawberry foundation can satisfy the architecture/security handoff by separating Admin and Account GraphQL surfaces, adding explicit actor/permission primitives, registering bounded domain app contracts, and keeping real licensing/download/billing behaviour as safe stubs.
- Change or investigation: Added failing pytest contract tests first. Initial red run produced `ModuleNotFoundError: No module named 'selahcue_api'` for the first four contract tests and skipped the Django tests because no settings module existed. Added `implementation/api` with Django project files, package metadata, GraphQL schemas, request context/authorization/error/redaction helpers, route contracts, domain app configs, desktop/billing stubs, README, and pytest config.
- Verifier executed: `/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`; `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`; `find implementation/api -maxdepth 4 -type f`; scoped status and cache checks.
- Result: C-002 through C-006 PASS. Final focused pytest run: `7 passed in 0.11s`. Django system check: `System check identified no issues (0 silenced).` Compileall exited 0. Generated Python and pytest caches were removed after verification.
- New evidence: `implementation/api/README.md`, `implementation/api/pyproject.toml`, `implementation/api/manage.py`, `implementation/api/selahcue_api/`, and `implementation/api/tests/test_foundation_contract.py`.
- Decision: gate-review

### Iteration 3

- Target criterion: C-003, C-004, C-006, and C-008
- Hypothesis: The independent review findings are valid for this foundation and can be addressed with narrow security-contract tests plus small implementation changes without adding real production licensing/download/billing behaviour.
- Change or investigation: Received read-only code review with no Critical findings and Important findings for command-stub CSRF behaviour, spoofable header actors, uncoded framework GraphQL errors, unwired introspection setting, and snake_case-only redaction. Added failing tests first. Review-regression red run failed 5 tests: uncoded GraphQL validation errors, introspection still enabled, CSRF blocking `/v1` stubs, camelCase redaction not enforced, and header actors trusted by default.
- Verifier executed: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`; `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`; safety scan for banned fixture strings; cache cleanup.
- Result: Important findings addressed. Final pytest: `12 passed in 0.13s`. Django system check: `System check identified no issues (0 silenced).` Compileall exited 0. Safety scan found none of `SC_SECRET`, `provider-secret`, `restricted Bible content`, `package bytes`, or malformed `SEL AHCUE`.
- New evidence: `implementation/api/tests/test_foundation_contract.py` now covers CSRF split, safe framework error coding, disabled introspection, test/dev-only actor headers, and camelCase redaction. `implementation/api/selahcue_api/graphql/views.py`, `context.py`, `errors.py`, `redaction.py`, `admin_schema.py`, `account_schema.py`, `settings.py`, and `platform/views.py` implement the fixes.
- Decision: gate-review

## Risks and rollback

- Risks: The scaffold could be mistaken for production-ready licensing, billing, or download behaviour. Mitigation: explicit stubs, README warnings, and `GATE_REVIEW` terminal state pending review.
- Risks: Real staff/customer authentication decisions remain open. Mitigation: enforce local actor-context checks now and leave IdP/customer identity integration as a named future dependency.
- Risks: GraphQL security controls such as depth/complexity/rate limiting need concrete middleware/extensions later. Mitigation: declare production-safe defaults now and keep abuse controls in the security backlog.
- Risks: `SECRET_KEY` still has a development fallback for local checks. Mitigation: keep as a documented minor review follow-up and let DevOps/Security define the environment policy before production deployment.
- Risks: Dependency verification relies on a throwaway virtualenv outside the repo. Mitigation: dependencies are declared in `pyproject.toml`; verification commands name the environment used.
- Rollback or recovery: Remove the new `implementation/api` root and this goal contract before any production integration depends on them.

## Pause and escalation conditions

- Pause before implementing real app-key generation, signed policies, device tokens, entitlement grants, billing webhooks, provider downloads, licensed Bible content, KMS/object-store integration, or production deployment.
- Escalate identity, billing, cryptography, provider, legal/licensing, retention, and reporting decisions to the named owners.
- Escalate if dependency installation or Django/Strawberry verification cannot run in the approved throwaway environment.
- If ClickUp write access still fails, preserve exact pending update text here and continue only with repository evidence.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md` and `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-admin-api-foundation.md`
- Validator result: PASS via shared validator and repo `scripts/validate_goal_contract.py`.
- Independent verification result: Read-only code review completed with no Critical findings and Important findings fixed through Iteration 3. Minor `SECRET_KEY` hardening remains a follow-up; this backend goal does not claim production release readiness.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None for this foundation goal; production IdP, billing, signing, provider, legal, retention, and deployment decisions remain future blockers outside this slice.
- ClickUp final evidence comment: `_clickup_create_task_comment` returned `{"error_code":"INVALID_ARGUMENT"}` before and after the review fixes. Pending final text to post when ClickUp comments work: `Backend foundation ready for gate review: GOAL-be-admin-api-foundation reached GATE_REVIEW. Created Django 5.2 + Strawberry Platform API foundation under implementation/api only: separate /graphql/admin and /graphql/account schemas, secure defaults (CSRF middleware retained for browser GraphQL, non-browser /v1 and billing stubs CSRF-exempt for later token/signature auth, GET GraphQL disabled, multipart uploads disabled, GraphiQL disabled outside debug, introspection disabled outside debug), test/dev-only actor-header trust, actor/permission/tenant/idempotency/reason/redaction primitives, safe GraphQL error formatting, placeholder Django app boundaries for accounts, billing, license keys, Bible catalogue, entitlements, downloads, audit/outbox, and safe 501 desktop/billing command stubs. Tests and checks: initial red pytest failed with missing selahcue_api; review-regression red failed 5 tests; final pytest 12 passed; Django manage.py check no issues; compileall exited 0; both shared and repo goal validators pass. Independent read-only review found no Critical issues; Important findings were fixed; minor SECRET_KEY hardening remains a follow-up before production environment work. Non-goals remain: no real IdP, billing provider, key generation, device activation, signed policies, entitlement grants, licensed Bible content, download leases, provider integration, secrets, production deployment, or legal/retention decisions. Next recommended role: security-reviewer or backend-engineer for the next vertical API slice after owner gate.`
