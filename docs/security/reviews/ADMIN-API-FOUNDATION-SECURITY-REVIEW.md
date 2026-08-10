# SelahCue - Admin API Foundation Security Review

Version: 0.1 gate review  
Date: 2026-08-08  
Reviewer: Security Reviewer  
Status: Gate review - foundation reviewed, not release sign-off  
Goal Contract: `docs/delivery/goals/GOAL-sec-admin-api-foundation.md`  
Reviewed Code: `implementation/api`  
ClickUp Build Control: `https://app.clickup.com/t/86ajnx548`

> This review covers the first Django + Strawberry API foundation only. It does not approve production deployment, staff identity, customer identity, billing, key generation, device activation, signed policies, Bible entitlements, licensed downloads, provider integrations, KMS/secrets, retention, or legal licensing terms.

## 1. Verdict

**Foundation security verdict: Pass with Required Controls.**

The `implementation/api` foundation is acceptable to keep as a non-production scaffold and to proceed to the next gated API slice. The review found one foundation-scoped HTTP error-formatting gap, fixed during this pass, and no unresolved Critical/Blocker issue in the current stubbed behaviour.

**Release security verdict: Not Assessed.**

Production release remains blocked until the required controls in section 8 are implemented and independently reviewed. The current API has no real staff IdP, customer identity, persistence, app-key cryptography, device-token auth, billing/provider signature verification, signed policies, entitlement grants, licensed Bible downloads, audit fail-closed path, rate limiting, query-depth/complexity controls, deployment hardening, retention policy, or legal approval.

## 2. Evidence Labels

- **Verified:** directly observed in repository files, command output, ClickUp read result, or current official documentation.
- **Inferred:** supported by verified evidence but not directly observed as runtime behaviour.
- **Assumed:** accepted only for this foundation review and owned by a named future decision-maker.
- **Unknown:** unresolved and decision-relevant.

## 3. Reviewed Evidence

| Evidence | Label | Notes |
|---|---|---|
| `implementation/api` exists and contains Django settings, URLs, Strawberry schemas, GraphQL helpers, platform stubs, domain app configs, tests, README, and dependency declarations. | Verified | Scoped source review and file listing. |
| Staff and customer GraphQL are separate endpoints at `/graphql/admin` and `/graphql/account`. | Verified | `implementation/api/selahcue_api/urls.py`. |
| Browser GraphQL keeps Django CSRF middleware active and tests CSRF enforcement. | Verified | `MIDDLEWARE` includes `CsrfViewMiddleware`; pytest CSRF-enforcement test passes. |
| Non-browser `/v1` desktop and billing webhook stubs are CSRF-exempt but return safe `501 NOT_IMPLEMENTED` payloads only. | Verified | `implementation/api/selahcue_api/platform/views.py`; pytest CSRF-enforcement and safe-payload tests pass. |
| Actor headers are ignored unless `SELAHCUE_TRUST_ACTOR_HEADERS` is explicitly enabled. | Verified | `implementation/api/selahcue_api/graphql/context.py`; pytest test passes. |
| GraphiQL, GET GraphQL queries, multipart uploads, and introspection are disabled outside debug by configuration/schema wiring. | Verified | `settings.py`, `urls.py`, `admin_schema.py`, `account_schema.py`; pytest tests pass for GET rejection and introspection denial. |
| Safe GraphQL result errors and HTTP request errors return stable `extensions.code` values after this review. | Verified | `graphql/errors.py`, `graphql/views.py`; pytest `test_graphql_http_request_errors_use_safe_json_envelope` passes. |
| The code/test scan does not include full app-key samples, provider-secret samples, licensed Bible text samples, or package-byte samples. | Verified | Focused `rg` scan found no banned fixture strings; README has human prose saying the implementation does not serve licensed Bible text. |
| `SECRET_KEY` falls back to a known development value even when `DJANGO_DEBUG` defaults false. | Verified | `implementation/api/selahcue_api/settings.py`. |
| CORS origin settings are declared, but no CORS middleware/package is installed in this foundation. | Verified | `settings.py` and `pyproject.toml`. |
| Staff IdP, customer identity, hosting, KMS, billing provider, licensed translations, provider reporting, and retention remain unresolved. | Unknown | Listed in API README, architecture, and threat model as owner decisions. |

## 4. Controls Verified In This Foundation

| Control | Evidence | Status |
|---|---|---|
| Separate Admin and Account GraphQL schemas | `admin_schema.py`, `account_schema.py`, `urls.py` | Pass for foundation |
| Resolver-level authorization primitive | `require_staff_permission`, `require_customer_org` tests | Pass for foundation |
| Tenant hiding primitive returns `NOT_FOUND` for other orgs | `test_customer_scope_hides_other_tenants` | Pass for foundation |
| Stable safe GraphQL error code for resolver, validation, and HTTP request errors | `test_graphql_errors_are_safely_coded_without_internal_messages`, `test_graphql_http_request_errors_use_safe_json_envelope` | Pass after review fix |
| Browser GraphQL CSRF retained | `Client(enforce_csrf_checks=True)` test returns `403` for missing CSRF | Pass |
| Non-browser stubs are not cookie-authenticated browser surfaces | CSRF-exempt stubs return only safe `501` payloads | Pass for stubs only |
| GraphiQL and introspection disabled outside debug | Settings and `DisableIntrospection`; tests pass | Pass |
| GET queries disabled | `allow_queries_via_get=False`; tests pass | Pass |
| Multipart uploads disabled | `multipart_uploads_enabled=False`; route-contract tests pass | Pass |
| Redaction catches snake_case and camelCase restricted keys | `redaction.py`; tests pass | Pass for current helper |
| No licensed Bible content served through GraphQL or stubs | Source and payload tests | Pass for current stubs |

## 5. Fixed During Review

| ID | Severity | Finding | Evidence | Fix | Verification |
|---|---|---|---|---|---|
| SEC-API-FIX-001 | Medium | Malformed JSON and empty GraphQL bodies returned plain-text Strawberry HTTP errors instead of SelahCue's stable JSON error envelope. | Direct Django client probe returned `400 text/plain` before the fix. | `SafeGraphQLView.dispatch` now catches `cross_web.exceptions.HTTPException` and returns a safe JSON error payload; `safe_error_payload` centralizes the envelope. | Red test failed first; final focused test passed; full pytest now `13 passed`. |

## 6. Findings And Required Controls

| ID | Severity | Status | Finding | Evidence | Impact | Required remediation | Verification |
|---|---|---|---|---|---|---|---|
| SEC-API-F01 | High for production | Open release blocker | A known development `SECRET_KEY` fallback is used when `DJANGO_SECRET_KEY` is absent, even though `DJANGO_DEBUG` defaults false. | `implementation/api/selahcue_api/settings.py` | If accidentally deployed as-is, signed cookies/session-related security assumptions could be weakened. | Before staging/production, fail closed when `DJANGO_SECRET_KEY` is absent outside explicit local/test mode, and document environment setup. | Production settings test: no `DJANGO_SECRET_KEY` fails startup; configured secret passes `manage.py check`. |
| SEC-API-F02 | High for production | Open release blocker | Header-derived actors are a test/dev convenience, not authentication. | `SELAHCUE_TRUST_ACTOR_HEADERS` gate in `context.py`; default false when `DEBUG=false`. | If enabled in production, callers could spoof staff/customer identity and permissions. | Replace with staff IdP/session claims and customer identity context; assert the header trust setting is false in production. | Integration tests with real auth context; production settings check rejects `SELAHCUE_TRUST_ACTOR_HEADERS=true`. |
| SEC-API-F03 | High for production | Open release blocker | `/v1` desktop APIs and billing webhook are CSRF-exempt and currently unauthenticated stubs. | `platform/views.py` returns only `501 NOT_IMPLEMENTED`. | Safe for current stubs, unsafe for any future side effect. | Before implementing behaviour, add device-token/app-key auth, billing/provider signature verification, replay windows, idempotency, rate limits, and audit. | Tests prove unauthenticated requests cannot activate, refresh, download, complete downloads, submit usage, or process webhooks. |
| SEC-API-F04 | High for production | Open release blocker | GraphQL denial-of-service controls are not implemented beyond disabling GET/multipart/introspection. | No depth, complexity, alias, batching, timeout, or rate-limit middleware exists. | Deep or aliased queries could exhaust API/database once real fields land. | Add depth/complexity/alias/page-size/operation-count limits, per-actor/IP rate limits, timeouts, and DataLoader patterns before real list/detail fields. | Abuse tests for deep, aliased, batched, and oversized pagination requests. |
| SEC-API-F05 | High for production | Open release blocker | Audit fail-closed and durable outbox are placeholder app boundaries only. | Domain app configs exist; no models/services/migrations. | Sensitive mutations could be added later without durable accountability. | Before key generation, revocation, entitlement, billing, impersonation, export, or provider-secret actions, implement transactional audit and idempotent outbox. | Tests prove sensitive mutation fails if audit write fails and duplicate requests do not duplicate effects. |
| SEC-API-F06 | Medium | Open future control | `CORS_ALLOWED_ORIGINS` is declared but not enforced because no CORS middleware/package is installed. | `settings.py`, `pyproject.toml`. | Current default is effectively closed to browser cross-origin calls, but the setting name could mislead future implementers. | When Admin/account origins are chosen, add explicit CORS middleware or remove the placeholder until implemented; pair with CSP. | Browser/API tests prove only approved origins receive credentialed CORS headers. |
| SEC-API-F07 | Medium | Open release blocker | Dependency reproducibility and supply-chain scanning are not established for the new Python API root. | `pyproject.toml` declares ranges; no lockfile or SBOM. | Unpinned transitive dependency changes can alter runtime behaviour or introduce vulnerabilities. | Add a chosen resolver/lock workflow, dependency scanning, SBOM, and vulnerability alerting before CI/deployment. | CI proves lockfile sync, vulnerability scan, and SBOM generation pass. |
| SEC-API-F08 | Medium | Open future control | Safe error formatting now covers current GraphQL execution and HTTP request errors, but logging policy is not configured. | Strawberry still logs validation errors during tests. | Future errors could leak internal details to logs if payloads include sensitive context. | Add structured redacted logging policy before sensitive operations; keep framework exception details out of production response bodies and sensitive logs. | Log-capture tests prove keys, tokens, provider secrets, and licensed text are redacted. |

## 7. Privacy And Licensed-Content Assessment

| Area | Assessment |
|---|---|
| Full app keys | No real key generation exists. Redaction helpers reject `license_key` and `fullKey` fields unless redacted. Future key generation still needs CSPRNG, hash-only persistence, show-once flow, abuse throttling, and audit. |
| Provider secrets and signing keys | No provider or signing integration exists. Redaction helpers reject provider/signing secret field names. Future settings must use managed secret custody, not staff-visible plaintext. |
| Device tokens | No device token issuance exists. Redaction helper includes `device_token`; future desktop endpoints must store/verify tokens safely and rate-limit abuse. |
| Licensed Bible text | No licensed content is served. Stub payload tests assert no `bible_text` or `content` fields. Future downloads still require lease scoping, checksums/signatures, encrypted local store, export/print limits, reporting, and legal-approved grace/deletion policy. |
| Customer/account data | No persistent customer data exists. Tenant primitive hides other orgs with `NOT_FOUND`; real database repositories must make tenant scope mandatory. |
| Diagnostics/logs | No diagnostics/export implementation exists. Safe response formatting is present; redacted structured logging remains required before sensitive flows. |
| Retention/deletion | Not implemented and not decided. Legal/Security must define data-class retention before audit, activation, download, usage, billing, support, and export data ship. |

## 8. Required Before Production-Oriented Slices

These are not blockers for keeping the foundation scaffold, but they are blockers before real customer/admin behaviour can ship:

1. Staff IdP/MFA/session model and production actor context.
2. Customer identity and tenant-scoped repository contract.
3. Production settings split with required secret key, allowed hosts, HTTPS, CSRF trusted origins, CSP, CORS, secure cookies, HSTS, logging, and debug-off checks.
4. GraphQL depth, complexity, alias, operation count, timeout, page-size, DataLoader, and rate-limit controls.
5. Transactional audit and idempotency for sensitive mutations.
6. Device-token/app-key auth for `/v1` APIs and provider signature/replay verification for webhooks.
7. App-key format, hashing, rate limit, and show-once flow approved by Security.
8. Signed policy envelope and KMS/HSM-equivalent key custody approved by Security/Architecture.
9. Licensed Bible content boundary tests before any package metadata, lease, URL, or content path ships.
10. Dependency lockfile, SBOM, vulnerability scanning, CI integration, and deployment runbook.

## 9. Verification Evidence

Commands run from `/Users/m.oluwole/Documents/code/scph`:

```bash
PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q -p no:cacheprovider
# 13 passed

PYTHONDONTWRITEBYTECODE=1 /private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check
# System check identified no issues (0 silenced).

/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api
# exit 0
```

Additional checks:

- Direct probe before fix: malformed GraphQL JSON returned `400 text/plain`.
- After fix: `test_graphql_http_request_errors_use_safe_json_envelope` passes.
- Focused restricted-string scan found no app-key samples, provider-secret samples, licensed Bible text samples, package-byte samples, or malformed CORS env var spelling in `implementation/api`.
- Generated Python bytecode caches were removed after `compileall`.

## 10. Gate Notes And Pending ClickUp Update

ClickUp task/comment reads work for `86ajnx548`. `_clickup_create_task_comment` still returns `INVALID_ARGUMENT`, so no ClickUp comment was posted by this pass.

Pending ClickUp start update:

`Security review started: GOAL-sec-admin-api-foundation, engine=goal, max iterations=5. Scope: independent security/privacy review of implementation/api Django + Strawberry foundation only: staff/account GraphQL split, browser CSRF posture, non-browser /v1 and billing stubs, actor trust, RBAC/tenant primitives, safe errors, redaction, introspection/GraphiQL/GET/multipart defaults, dependency/config posture, and licensed-content boundaries. Non-goals: no production access, secrets, exploit testing, real IdP, billing, key generation, device activation, signed policy, entitlement grant, licensed downloads, provider integration, deployment, legal, or retention decisions. Evidence target: docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md.`

Pending ClickUp final update:

`Security review ready for gate review: GOAL-sec-admin-api-foundation reached GATE_REVIEW. Reviewed implementation/api Django + Strawberry foundation and created docs/security/reviews/ADMIN-API-FOUNDATION-SECURITY-REVIEW.md. Verdict: Pass with Required Controls for the foundation; release security verdict remains Not Assessed. Fixed one foundation-scoped Medium issue during review: malformed/empty GraphQL HTTP request errors now return the safe JSON error envelope. Final checks: pytest 13 passed, Django check no issues, compileall exit 0, goal validators pass. No Critical/Blocker issue remains for the current stubbed foundation. Production blockers remain for SECRET_KEY fail-closed settings, real staff/customer auth, /v1 token and webhook signature auth, GraphQL DoS controls, transactional audit/outbox, dependency locking/SBOM, deployment hardening, legal/licensing, provider, billing, KMS, and retention decisions.`

## 11. Sources

Repository sources:

- `implementation/api`
- `implementation/api/tests/test_foundation_contract.py`
- `docs/delivery/goals/GOAL-be-admin-api-foundation.md`
- `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md`
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`

External sources checked 2026-08-08:

- Django CSRF reference: https://docs.djangoproject.com/en/4.2/ref/csrf/
- Django middleware/security headers reference: https://docs.djangoproject.com/en/4.2/ref/middleware/
- Strawberry Django integration options: https://beta.strawberry.rocks/docs/integrations/django
- Strawberry deployment guidance: https://beta.strawberry.rocks/docs/operations/deployment
