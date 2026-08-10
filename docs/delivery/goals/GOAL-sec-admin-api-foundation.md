# Goal Contract - GOAL-sec-admin-api-foundation

## Identity

- Goal ID: GOAL-sec-admin-api-foundation
- Parent goal ID: GOAL-be-admin-api-foundation
- Title: Admin API foundation security review is ready for gate review
- Role: security-reviewer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Independently review the new Django + Strawberry Admin API foundation under `implementation/api` for security and privacy posture, verify that the backend-foundation controls align with the Admin architecture and threat model, record actionable findings with severity and evidence, and stop at a gate-review verdict without approving production release.

## Baseline

Verified current state before substantive security work:

- ClickUp Build Control task `86ajnx548` is readable and currently `in progress`.
- ClickUp create-comment has repeatedly returned `INVALID_ARGUMENT` for Admin PM, UX, architecture, security, and backend handoff comments; this goal will attempt comments and preserve pending update text if writes remain unavailable.
- `GOAL-be-admin-api-foundation.md` is in `GATE_REVIEW` with 8 mandatory criteria passing after an independent read-only code review and review-fix iteration.
- `implementation/api` contains a new Django 5.2 + Strawberry foundation with separate `/graphql/admin` and `/graphql/account`, actor/permission/tenant/idempotency/reason/redaction primitives, domain app placeholders, and safe `501` desktop/billing stubs.
- Final backend verifier evidence before this security review: pytest `12 passed`, Django check `0 silenced`, compileall exit `0`, shared and repo goal validators pass, and generated Python/pytest caches are absent.
- No real staff IdP, customer identity, billing provider, app-key generation, device activation, signing, entitlement grant, provider download, licensed Bible content, KMS/object store, secrets, production deployment, retention policy, or legal approval exists in this slice.
- Current official documentation reviewed on 2026-08-08 confirms Django CSRF middleware behaviour and Strawberry Django GraphQLView options for GraphiQL, GET queries, multipart uploads, and production introspection posture.

## Inputs and evidence sources

- User `continue` after backend foundation gate-review handoff.
- `docs/delivery/goals/GOAL-be-admin-api-foundation.md`
- `implementation/api/`
- `implementation/api/tests/test_foundation_contract.py`
- `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md`
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- ClickUp Build Control task `86ajnx548` and recent comments.
- Official Django CSRF/security docs and Strawberry Django/deployment docs checked on 2026-08-08.

## Scope

### In scope

- Security review document under `docs/security/reviews/`.
- Code/config/test review of `implementation/api` only.
- Browser GraphQL security: CSRF posture, GraphiQL, introspection, GET query behaviour, multipart upload posture, safe error formatting, actor-context trust, RBAC primitive, tenant primitive, redaction, and settings.
- Non-browser command stubs: desktop `/v1` and billing webhook safe output, CSRF exemption rationale, and future token/signature-auth blockers.
- Dependency/config review of declared Django, Strawberry, and pytest dependencies, Python version floor, secret-key handling, CORS assumptions, cookie/header defaults, and non-production environment assumptions.
- Privacy/content-boundary review for app license keys, provider secrets, device tokens, licensed Bible text, diagnostics, logs, and tests.
- Findings table with severity, evidence, impact, remediation, and verification route.

### Non-goals

- Implementing new production features, real IdP/customer auth, billing, provider adapters, activation, license-key generation, device tokens, signed policies, entitlement grants, download leases, licensed Bible package handling, KMS/object store, deployment, or legal/retention decisions.
- Destructive testing, secret handling, production access, exploit execution, or penetration testing.
- Editing unrelated desktop/mobile/marketing files or resolving unrelated dirty worktree changes.
- Risk acceptance on behalf of Product, Legal, Finance, Security, DevOps, or the user.
- Creating duplicate Markdown tickets in place of ClickUp tasks.

### Constraints

- Label material facts as Verified, Inferred, Assumed, or Unknown.
- Do not overstate unimplemented stubs as production security controls.
- Do not expose exploit detail beyond what is needed for remediation.
- If ClickUp comment creation fails, record the exact pending update text in repository evidence.
- If release-blocking issues are found that require code changes within the foundation scope, either fix them with evidence or return `BLOCKED`/`GATE_REVIEW` with explicit owner and verifier.

### Assumptions and unknowns

- ASSUMED: This pass reviews the backend foundation for gate readiness, not production release readiness. Owner: Product/Architecture/Security.
- ASSUMED: Header-based actor context is intentionally test/dev-only until staff IdP and customer identity decisions land. Owner: Backend/Security.
- ASSUMED: `/v1` desktop and billing webhook stubs are CSRF-exempt because future auth is token/signature based, not cookie based. Owner: Backend/Security.
- UNKNOWN: Staff IdP, customer identity model, hosting/database/object store, KMS/secrets provider, exact signing suite, billing provider, first translations, retention periods, provider reporting payloads, and production CORS/CSP origins. Owner: Product/Security/Legal/Finance/DevOps.

## Dependencies and approvals

- Backend foundation must exist and pass its focused verifiers. Status: satisfied by `GOAL-be-admin-api-foundation`.
- Product/Admin PRD, UX handoff, architecture, ADR, and design-time threat model must exist. Status: satisfied for this review.
- Legal/Product/DevOps/Security decisions remain required before production behaviour or release sign-off. Status: future blockers, not blocking this foundation security review.
- ClickUp write path is desirable for evidence but currently unreliable. Status: read works; comment writes likely fail with `INVALID_ARGUMENT`.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Security-review Goal Contract and baseline validate before review work | `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md` and `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md` | Both validators exit 0 before substantive security review | Both validators passed before review; ClickUp start comment returned `INVALID_ARGUMENT`, so pending text is recorded in this contract | PASS |
| C-002 | yes | API foundation security controls are reviewed against the Admin threat model and current code | Source review plus focused searches and test execution | Review covers staff/account GraphQL separation, CSRF split, actor trust, RBAC/tenant checks, safe errors, redaction, introspection, stubs, and content boundaries | `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md` and pytest output | PASS |
| C-003 | yes | Dependency and configuration posture is assessed without claiming production readiness | Config/dependency review | Review covers Django/Strawberry dependency floor, SECRET_KEY fallback, CORS assumptions, secure cookies/headers, debug/introspection posture, and missing deployment controls | `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md` findings SEC-API-F01, F06, F07, and F08 | PASS |
| C-004 | yes | Privacy and licensed-content boundaries are assessed | Redaction/content-boundary review | Review confirms tests/source avoid full keys, provider secrets, device tokens, and licensed Bible text in public payloads, and records remaining future controls | Review section 7 plus focused `rg` evidence | PASS |
| C-005 | yes | Findings are severity-classified, actionable, and separately identify release blockers versus foundation blockers | Findings review | Every finding has severity, evidence, impact, remediation, and verification route; no unresolved Blocker/Critical issue is hidden | Review sections 5, 6, and 8 | PASS |
| C-006 | yes | Verifiers pass after the review and no unrelated generated artifacts remain | Test/check commands and scoped status | Pytest, Django check, compileall, goal validators, scoped status, and cache scan produce expected output | Command output and goal ledger | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused code review: inspect `implementation/api/selahcue_api/`, tests, `README.md`, `pyproject.toml`, and backend goal evidence.
- Behavioural verification: run `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`.
- Django verification: run `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`.
- Syntax verification: run `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`, then remove generated bytecode caches.
- Search verification: run focused `rg` checks for restricted fixture strings, unsafe placeholders, and security-control terms.
- Goal verification: run both shared and repo Goal Contract validators before and after review.
- Independent verifier: this security-reviewer pass is independent of the backend implementation agent; later production security review remains required.
- Required environment: local repository plus throwaway `/private/tmp/selahcue-api-venv` verifier environment already created for backend verification.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: The new API foundation has enough code/test evidence to support a bounded security review goal without touching production systems or secrets.
- Change or investigation: Created this Goal Contract after reading security-reviewer, goal, team workflow, ClickUp, quality gate, artefact instructions, repository guidance, active ClickUp Build Control, backend goal evidence, and current official Django/Strawberry documentation.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md`; attempted `_clickup_create_task_comment` on task `86ajnx548`.
- Result: C-001 PASS. Shared validator exited 0; repo validator exited 0. ClickUp create-comment returned `{"error_code":"INVALID_ARGUMENT"}`.
- New evidence: This Goal Contract validates structurally before review. Pending ClickUp start text: `Security review started: GOAL-sec-admin-api-foundation, engine=goal, max iterations=5. Scope: independent security/privacy review of implementation/api Django + Strawberry foundation only: staff/account GraphQL split, browser CSRF posture, non-browser /v1 and billing stubs, actor trust, RBAC/tenant primitives, safe errors, redaction, introspection/GraphiQL/GET/multipart defaults, dependency/config posture, and licensed-content boundaries. Non-goals: no production access, secrets, exploit testing, real IdP, billing, key generation, device activation, signed policy, entitlement grant, licensed downloads, provider integration, deployment, legal, or retention decisions. Evidence target: docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md.`
- Decision: iterate

### Iteration 2

- Target criterion: C-002 through C-005
- Hypothesis: The foundation controls satisfy gate-review readiness if current code behaviour matches the architecture/threat-model controls and any foundation-scoped response-safety gap is fixed with a regression test.
- Change or investigation: Reviewed `implementation/api` settings, URLs, GraphQL schemas/views/errors/context, platform stubs, tests, README, backend goal evidence, architecture, ADR, and threat model. Probed malformed/empty GraphQL request bodies and found plain-text Strawberry HTTP errors outside SelahCue's stable JSON envelope. Added a failing regression test, then changed `SafeGraphQLView.dispatch` and `safe_error_payload` so Strawberry HTTP request errors return safe JSON payloads with stable `extensions.code` values. Created `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md`.
- Verifier executed: direct Django client probe before fix; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests/test_foundation_contract.py::test_graphql_http_request_errors_use_safe_json_envelope -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; focused restricted-string `rg` scan against `implementation/api`.
- Result: C-002 PASS, C-003 PASS, C-004 PASS, C-005 PASS. The new regression test failed before the fix with `400 text/plain`, then passed after the fix. Full pytest reported `13 passed`.
- New evidence: `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md`; changed `implementation/api/selahcue_api/graphql/errors.py`; changed `implementation/api/selahcue_api/graphql/views.py`; changed `implementation/api/tests/test_foundation_contract.py`.
- Decision: iterate

### Iteration 3

- Target criterion: C-006
- Hypothesis: Fresh final verifiers will show the reviewed API foundation is internally consistent and has no generated cache artifacts left under `implementation/api`.
- Change or investigation: Ran the full API test suite, Django system check, compileall, shared and repo Goal Contract validators, scoped status/cache scans, and removed generated Python bytecode caches after syntax verification.
- Verifier executed: `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check`; `/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api`; `find implementation/api -name __pycache__ -o -name .pytest_cache -print`; goal validators.
- Result: C-006 PASS. Pytest reported `13 passed`; Django check reported `System check identified no issues (0 silenced).`; compileall exited `0`; cache scan returned no output after cleanup.
- New evidence: command output in this session and the security review verification section.
- Decision: gate-review

## Risks and rollback

- Risks: Foundation controls could be mistaken for production release sign-off. Mitigation: security review verdict must distinguish gate-readiness from release-readiness.
- Risks: Review may find issues requiring Product/Security/DevOps decisions. Mitigation: classify as owner-blocked future controls unless the issue belongs in the current scaffold.
- Risks: ClickUp write failures could hide handoff evidence. Mitigation: record pending update text in this contract and security review.
- Rollback or recovery: Docs-only security review can be revised without runtime impact; any code fix would remain scoped to `implementation/api`.

## Pause and escalation conditions

- Pause before destructive testing, production access, secret handling, exploit execution, dependency upgrades beyond the approved verifier env, or real provider/billing/download work.
- Escalate IdP/MFA, customer identity, key custody, signing suite, retention, billing, provider, legal/licensing, CORS/CSP origins, and deployment decisions to the named owners.
- If a release-blocking issue cannot be remediated in this foundation scope, return `GATE_REVIEW` or `BLOCKED` with the smallest owner action.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-api-foundation.md`.
- Validator result: Passed after review.
- Independent verification result: Security-reviewer reviewed the backend foundation independently of the backend implementation pass. This is a foundation gate review only; release security review remains required before production.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None for this foundation security review. Production-oriented release blockers are recorded in `docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md`.
- ClickUp final evidence comment: Pending because `_clickup_create_task_comment` continues to return `INVALID_ARGUMENT`. Pending text: `Security review ready for gate review: GOAL-sec-admin-api-foundation reached GATE_REVIEW. Reviewed implementation/api Django + Strawberry foundation and created docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md. Verdict: Pass with Required Controls for the foundation; release security verdict remains Not Assessed. Fixed one foundation-scoped Medium issue during review: malformed/empty GraphQL HTTP request errors now return the safe JSON error envelope. Final checks: pytest 13 passed, Django check no issues, compileall exit 0, goal validators pass. No Critical/Blocker issue remains for the current stubbed foundation. Production blockers remain for SECRET_KEY fail-closed settings, real staff/customer auth, /v1 token and webhook signature auth, GraphQL DoS controls, transactional audit/outbox, dependency locking/SBOM, deployment hardening, legal/licensing, provider, billing, KMS, and retention decisions.`
