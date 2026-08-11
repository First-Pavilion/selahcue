# Goal Contract — GOAL-be-traditional-auth

## Identity

- Goal ID: GOAL-be-traditional-auth
- Parent goal ID: 86ajy5v6k (EPIC — Licensing / Customer identity)
- Title: Traditional email/password customer authentication on the Platform API (CustomerUser + opaque server-side session + email verification + password reset + account-based device activation), superseding Logto/OIDC per DEC-007
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: TBD — link to the customer-identity epic on next ClickUp sync
- Created: 2026-08-11
- Updated: 2026-08-11
- Maximum iterations: 14
- Independent verification required: yes

## Objective

Ship SelahCue-owned traditional email/password authentication on the Django + Strawberry Platform API — a `CustomerUser` login principal, an opaque hashed session token (device-token pattern, not JWT), email verification, password reset, and account-based device activation — with no user-enumeration, session-invalidation-on-password-change, and full reuse of the repo's existing hashed-credential/idempotency/audit conventions.

## Baseline

Verified from the codebase (workflow `wf_7b321daa-ba0`, 6 agents): the API has NO user/credential/login model (only `AuditEvent`, `CustomerOrg`, `AppLicenseKey`, `Device`, `DeviceToken`). `graphql/account_schema.py` is a single read-only `account_viewer` query. `require_customer_org()` and `ActorKind.CUSTOMER` exist in `graphql/context.py` but are unreachable (no way to mint a CUSTOMER actor; identity is header-trusted under `SELAHCUE_TRUST_ACTOR_HEADERS`). `DeviceToken` is the shipped opaque-bearer precedent (`make_password` hash + unique `HMAC-SHA256(SECRET_KEY)` fingerprint + `compare_digest`). No JWT/JWKS anywhere. DEC-007 recorded; ADR-0022 superseded; ADR-0023 written.

## Inputs and evidence sources

- DEC-007 (`docs/decisions/DECISION-LOG.md`) and ADR-0023 (`docs/architecture/adr/ADR-0023-customer-auth-email-password.md`)
- Design recon + spec: workflow `wf_7b321daa-ba0` output (`scratchpad/auth_design.json`)
- Existing patterns: `apps/accounts/services.py` (idempotency), `apps/devices/services.py` (token fingerprint/`activate_device`), `graphql/{context,errors,redaction,views}.py`, `apps/*/migrations/`
- Desktop sign-in design: `docs/design/ACCOUNT-SETUP-HANDOFF.md`
- Test patterns: `implementation/api/tests/test_device_activation_slice.py`, `test_admin_license_key_slice.py`, `test_foundation_contract.py`

## Scope

### In scope

- `CustomerUser`, `CustomerSession`, `CredentialToken` models + forward-only migrations
- Account GraphQL mutations: register, verifyEmail, login, refreshSession, logout, requestPasswordReset, confirmPasswordReset
- Customer session authentication in `graphql/context.py`; retire header-trust for customers in prod
- Email verification + password reset via an injectable `EmailSender` seam (no-op/console default)
- Account-based device activation delegating into the unchanged `activate_device`; `require_customer_role(ADMIN)`
- Bounded rate-limiting/lockout; credential redaction; audit on every mutation; security-reviewer pass

### Non-goals

- 2FA (deferred; forward-compatible seam only)
- A concrete email/SMTP provider (seam now; provider wired later)
- Self-serve org creation UNLESS the product answer selects it (see Dependencies)
- Any change to the enrollment-key `POST /v1/activations` path or the render/output path

### Constraints

- No user-enumeration oracle anywhere; timing-equalized login (dummy hash on unknown email)
- Passwords: `make_password`/`check_password` only (PBKDF2), never `compare_digest`; high-entropy tokens: `compare_digest`
- Never-blank (NFR-024): identity stays off the render path; logout/expiry never revokes device tokens
- Bounded memory (no unbounded throttle/session growth); bounded-memory test required
- Forward-only migrations; secrets only in OS keychain/redacted; every new env key documented in `deployments.md` in the change that reads it

### Assumptions and unknowns

- RESOLVED (2026-08-11): one email → one org via FK (global-unique email) — confirmed for v1.
- RESOLVED (2026-08-11): **self-serve signup** — `registerCustomerUser` creates a NEW `CustomerOrg` (TRIAL, `created_by_actor_id='self_signup'`) + first user = ADMIN, atomically. (Was previously assumed invite-only; owner chose self-serve.)
- RESOLVED (2026-08-11): `SESSION_TTL` = **30 days**; email-verify token TTL **24h**, reset token TTL **1h** (defaulted, revisable); email delivery = injectable no-op/console seam; `seat_limit` enforcement dormant.

## Dependencies and approvals

- PRODUCT DECISION (blocks AUTH-2+): signup model (self-serve org creation vs invite-only/staff-provisioned org linkage) — owner. Until resolved, C-002..C-007 are BLOCKED.
- PRODUCT DECISION (default-able): `SESSION_TTL`, token TTLs, email uniqueness scope, seat enforcement — owner; sensible defaults proposed in DEC-007.
- Independent security-reviewer pass on auth/activation endpoints — required before VERIFIED_COMPLETE.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-000 | yes | DEC-007 recorded, ADR-0022 superseded, ADR-0023 written | review of docs/decisions/DECISION-LOG.md + docs/architecture/adr/ADR-0022,0023 | DEC-007 present; ADR-0022 Status=Superseded; ADR-0023 Accepted | docs/decisions/DECISION-LOG.md; docs/architecture/adr/ADR-0023-customer-auth-email-password.md | PASS |
| C-001 | yes | AUTH-1: CustomerUser model + forward-only migration + credential redaction; no behaviour change to existing tests | `python manage.py makemigrations --check` + `migrate` + `pytest` | makemigrations clean; migrate applies; all existing tests pass; email globally unique + email_fingerprint unique-indexed; redaction rejects a 'password' key | implementation/api/selahcue_api/apps/accounts/models.py + migrations/0002_customeruser.py; redaction.py; 37/37 existing tests pass (2026-08-11) | PASS |
| C-002 | yes | AUTH-2: register_customer_user service + registerCustomerUser mutation; password hashed; uniform accepted:true (no enumeration); idempotent replay | `pytest tests/test_customer_auth_slice.py -k signup` | plaintext never stored/returned; new email → INVITED/unverified; existing email → same accepted:true, no dup; racing dup → one row; audit-rollback leaves zero rows | implementation/api/tests/test_customer_auth_slice.py | PASS |
| C-003 | yes | AUTH-3: CredentialToken(EMAIL_VERIFY) + EmailSender seam + verifyEmail; single-use, no-oracle | `pytest tests/test_customer_auth_slice.py -k verify` | raw token leaves once, never stored plaintext; valid token → email_verified_at+ACTIVE; expired/consumed/unknown all VALIDATION_FAILED; EmailSender injectable | implementation/api/tests/test_customer_auth_slice.py | PASS |
| C-004 | yes | AUTH-4: CustomerSession + login/logout/refreshSession + customer session auth in context.py | `pytest tests/test_customer_auth_slice.py -k session` | unknown-email==wrong-password (UNAUTHENTICATED, identical); login mints ACTIVE session and account_viewer resolves WITHOUT header-trust; logout revokes and leaves DeviceToken untouched; refresh rotates | implementation/api/tests/test_customer_auth_slice.py; graphql/context.py | PASS |
| C-005 | yes | AUTH-5: password reset (request+confirm) with session invalidation on password change | `pytest tests/test_customer_auth_slice.py -k reset` | request accepted:true for existing+non-existing (no oracle); confirm changes password; all prior sessions rejected after reset; token single-use; secrets never in audit | implementation/api/tests/test_customer_auth_slice.py | PASS |
| C-006 | yes | AUTH-6: account-based device activation (session-authed) + require_customer_role(ADMIN); enrollment path unchanged | `pytest tests/test_customer_auth_slice.py -k activation` + existing device tests | signed-in ADMIN activates without enrollment key, identical DeviceToken shape; device_limit enforced under lock; MEMBER denied PERMISSION_DENIED; enrollment-key tests unchanged | implementation/api/tests/test_customer_auth_slice.py; test_device_activation_slice.py | PASS |
| C-007 | yes | AUTH-7: lockout + deployments.md config + security-reviewer sign-off + desktop handoff (Postgres-lock test + per-IP throttle = infra-blocked follow-ups) | `pytest` + adversarial security-review workflow + review of deployments.md/handoff | DONE: per-user lockout blocks with UNAUTHENTICATED (no enumeration leak); deployments.md documents every new key + SELAHCUE_TRUST_ACTOR_HEADERS=false in prod; security review (12 agents) → 5 findings, all fixed + re-tested (63/63 pass); desktop handoff written. BLOCKED (infra): Postgres select_for_update concurrency test needs an API CI job + local Postgres (neither exists yet); per-IP throttle deferred to edge/shared-store | implementation/api/tests/test_customer_auth_slice.py (63 pass); deployments.md §1c; docs/design/ACCOUNT-AUTH-API-HANDOFF.md; security-review wf_64841bd7-a86 | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `pytest` in `implementation/api` per-slice (`test_customer_auth_slice.py` filters), `python manage.py makemigrations --check`.
- Broader regression verification: full `implementation/api` pytest suite (existing device/license/foundation slices must stay green); the desktop `make ci` is unaffected (API is outside its gates) but CI's API job must pass.
- Independent verifier: security-reviewer (auth/activation endpoints) + code-reviewer before VERIFIED_COMPLETE; the implementation role may not self-approve the security criterion.
- Required environment: Python API venv (`implementation/api`); a Postgres-backed run for the `select_for_update` serialization test (SQLite for the rest).

## Iteration ledger

### Iteration 1

- Target criterion: C-000, C-001
- Hypothesis: DEC-007/ADR supersession + a fork-independent `CustomerUser` model/migration can land safely before the signup-model product fork is resolved.
- Change or investigation: Recorded DEC-007, superseded ADR-0022, wrote ADR-0023 (C-000). Building AUTH-1 (CustomerUser model + 0002 migration + redaction fields) next (C-001).
- Verifier executed: (C-000) doc review — PASS. (C-001) `makemigrations --check` (clean), `migrate` (applies), `pytest tests` (37/37 pass), ORM introspection of constraints/redaction — PASS.
- Result: C-000 PASS; C-001 PASS.
- New evidence: DECISION-LOG.md DEC-007; ADR-0023; apps/accounts/models.py (CustomerUser) + migrations/0002_customeruser.py; graphql/redaction.py.
- Decision: gate-review — AUTH-1 (fork-independent foundation) landed; PAUSE C-002+ for the product signup-model decision (invite-only vs self-serve org provisioning) + SESSION_TTL before building the service/mutation layer.

### Iteration 2

- Target criterion: C-002 … C-007 (product fork resolved: self-serve signup + 30-day sessions).
- Hypothesis: the full service/mutation layer can land on the AUTH-1 schema reusing the repo's hashed-credential/idempotency/audit conventions, verified per-slice + by an independent security review.
- Change or investigation: Built AUTH-2..6 (signup/verify/login/session/reset/account-activation) + AUTH-7 config/docs. Extracted `_activate_device_for_key` so the account path reuses the enrollment machinery unchanged. Ran an adversarial security-review workflow (5 lenses × find→verify).
- Verifier executed: `pytest tests` → **63/63 pass**; `manage.py check` clean; `makemigrations --check` clean; compileall OK. Security review (wf_64841bd7-a86, 12 agents) → 5 CONFIRMED findings.
- New evidence: apps/accounts/{models,services}.py; graphql/{context,account_schema}.py; apps/devices/services.py; settings.py; tests/test_customer_auth_slice.py; deployments.md; ADR-0023; docs/design/ACCOUNT-AUTH-API-HANDOFF.md.
- Findings fixed (all 5): (1) login lockout leaked RATE_LIMITED — collapsed to UNAUTHENTICATED + timing-equalized; (2) password-reset timing oracle — dummy PBKDF2 on the missing-email branch; (3) slug-collision mis-caught as replay — bounded slug retry; (4) orphan-org on user-race — org+user under one savepoint; (5) shared idempotency namespace — namespaced per email fingerprint. Re-tested green.
- Decision: **GATE_REVIEW** — implementable scope complete + independently security-reviewed; awaits the user's commit approval. Residual (documented, infra-blocked): Postgres concurrency test (no API CI job / no local Postgres) + per-IP throttle (edge/shared-store follow-up).

## Risks and rollback

- Risk: building AUTH-2+ on the wrong signup model → rework. Mitigation: BLOCK C-002+ until the owner answers; AUTH-1 model is fork-independent.
- Risk: `select_for_update` no-ops on SQLite → false-green concurrency. Mitigation: Postgres-backed lock test (C-007).
- Rollback: all migrations are additive/forward-only; the model + mutations are new surfaces — reverting is dropping the new tables/schema, with no change to existing device/license/enrollment paths.
