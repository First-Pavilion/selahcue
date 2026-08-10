# Goal Contract - GOAL-arch-customer-identity-oidc

## Identity

- Goal ID: GOAL-arch-customer-identity-oidc
- Parent goal ID: GOAL-arch-admin-licensing
- Title: Customer-identity architecture (self-hosted OSS IdP over OIDC) is review-ready and decomposed into ClickUp work
- Role: software-architect
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy5v6k
- Created: 2026-08-10
- Updated: 2026-08-10
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Produce a review-ready ADR that resolves DEC-006 into an implementable architecture for SelahCue customer identity via a self-hosted open-source IdP (Logto) integrated over OIDC — covering IdP choice, desktop native OIDC flows + token storage, Platform API as OIDC relying party / resource server, account↔CustomerOrg mapping + roles, account-based device activation alongside the enrollment-key path, session/revocation model, offline-first / never-blank alignment, self-hosting/data-residency, and security posture — and decompose the resulting workstream into sequenced ClickUp tasks under epic 86ajy5v6k with a clear unblock path for the account-setup frontend (86ajy600r). Architecture + planning only; no product/runtime code.

## Baseline

Verified current state before substantive work:

- **DEC-006** (`docs/decisions/DECISION-LOG.md`, 2026-08-10) decides customer identity uses a self-hostable OSS IdP (Logto leading) via OIDC; the *implementation approach* is explicitly deferred to an ADR. DEC-005 puts real sign-in in scope now with offline entitlement = full license window; DEC-004 keeps the enrollment key as the secondary/offline activation path.
- Platform API (`implementation/api`, Django 5.2 + Strawberry) ships: `/graphql/admin`, `/graphql/account`, and desktop `/v1/activations` (enrollment-key-authed) + `/v1/license:refresh` (device-token-authed). `graphql/context.py` already defines `ActorKind.CUSTOMER` and `require_customer_org`, but customer/account auth is only the `SELAHCUE_TRUST_ACTOR_HEADERS` dev header bridge — a placeholder for real identity.
- Data model: `CustomerOrg` (accounts), `AppLicenseKey` (enrollment/bootstrap token; `device_limit` = plan instance limit), `Device` + `DeviceToken` (show-once token = `make_password` hash + HMAC `token_fingerprint`; `expires_at` == license window). `authenticate_device_token` gives an oracle-free device-token auth reusable by every `device_token`-gated `/v1` endpoint.
- Desktop = Tauri operator (`implementation/desktop/crates/selahcue-operator`) + `selahcue-cloud` crate: `Token` (redacts in Debug/Display, `expose()` once), `SecretStore` trait, `KeyringSecretStore` (OS keychain under `cloud-live`), `ACCOUNT_TOKEN_NAME = "account_token"`, `set_account_token`/`clear_account_token` Tauri commands. This is the OS-keychain pattern to reuse for OIDC tokens (FR-134/NFR-017).
- Account-setup design is complete (Figma `651:124`, `docs/design/ACCOUNT-SETUP-HANDOFF.md`, story 86ajy600r); its A1 sign-in path is explicitly gated on the (now-resolved) IdP decision.
- Existing ADR spine: ADR-0008 (LAN security patterns: OS-secret-store-only, redaction, no secrets in logs), ADR-0021 (Admin Licensing Platform; "identity/staff RBAC integrated with a managed IdP" + "customer identity model" left open). Max existing ADR = ADR-0021, so the new ADR is ADR-0022.
- ClickUp epic 86ajy5v6k (Platform API / Licensing & Entitlements) is `planning/todo` with subtasks 86ajy5v7h (activation, QA), 86ajy5yze (license refresh, QA), 86ajy62xz (/v1 rate-limiting, todo). ClickUp read/create tools are available.

## Inputs and evidence sources

- User/delegating-agent task on 2026-08-10: ADR for customer identity via self-hosted Logto over OIDC + ClickUp decomposition under epic 86ajy5v6k linking story 86ajy600r. Architecture + planning, NOT implementation.
- `docs/decisions/DECISION-LOG.md` (DEC-006/005/004)
- `implementation/api/**` (context.py, account_schema.py, route_contracts.py, errors.py, apps/{accounts,devices,license_keys}/models.py, apps/devices/services.py, platform/views.py + urls.py, settings.py, README.md)
- `implementation/desktop/crates/selahcue-operator/src/main.rs` + `selahcue-cloud/src/secret.rs`
- `docs/design/ACCOUNT-SETUP-HANDOFF.md`; `docs/architecture/adr/ADR-0008-*`, `ADR-0021-*`
- ClickUp tasks 86ajy5v6k, 86ajy600r, 86ajy5v7h, 86ajy5yze, 86ajy62xz

## Scope

### In scope

- One ADR (`docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md`) covering all seven required topics.
- A short comparative evaluation of Logto vs Zitadel / Keycloak / Authentik / Ory (Hydra+Kratos) with a recommendation.
- Desktop native OIDC design (Auth Code + PKCE, loopback/custom-scheme redirect, system-browser, token/refresh handling, OS-keychain storage) reusing existing patterns.
- Platform API relying-party / resource-server design: token validation (JWKS vs introspection), `sub`→CustomerOrg+user mapping, multi-user-per-org roles, account-based device activation alongside `/v1/activations`.
- Session/token/logout/revocation model and its interaction with device token + offline license window.
- Self-hosting/devops topology, secrets, backup, upgrades, data residency (flagged for /devops-engineer).
- Offline-first / never-blank alignment and migration/coexistence + security posture.
- Sequenced ClickUp tasks under epic 86ajy5v6k with dependencies and a frontend unblock path; link to story 86ajy600r.

### Non-goals

- Any product/runtime code, migrations, Logto deployment, IdP tenant/app configuration, or secrets provisioning.
- Final owner sign-off on offline-grace duration, policy-envelope crypto suite, plan tiers/pricing (OD-04), staff IdP/MFA — these remain owner decisions.
- Security approval (this ADR can request a security review; it cannot approve its own posture).
- Changing the shipped enrollment-key activation contract.

### Constraints

- Honour DEC-006 (Logto default unless evidence says otherwise), DEC-005, DEC-004.
- Offline-first (NFR-015/CON-2) + never-blank (NFR-024) are hard: auth is one-time online; identity/auth failures must never block or gate live presentation.
- Reuse existing patterns: OS-keychain secret store + redacting `Token`, oracle-free auth, SafeAPIError taxonomy, no secrets in logs (ADR-0008/NFR-017).
- OIDC is a standard interface so the specific IdP stays swappable (DEC-006 reversibility).
- Label material facts Verified / Inferred / Assumed / Unknown.

### Assumptions and unknowns

- ASSUMED: Logto's first-class Organizations + org roles map cleanly onto CustomerOrg multi-tenant + per-org roles. Owner: Architecture/Backend (confirm in the [devops]/[backend] tasks).
- ASSUMED: JWKS-validated JWT access tokens are the default RP validation model, with introspection reserved for high-value/immediate-revocation operations. Owner: Backend/Security.
- UNKNOWN: whether account-based activation keeps hanging a `Device` off the org's `AppLicenseKey` (instance-limit carrier) or introduces an account-level entitlement; carried as an ADR decision + flagged in the activation task. Owner: Architecture/Product.
- UNKNOWN: production hosting stack, KMS/secret manager, and data-residency region for the self-hosted Logto + its Postgres. Owner: DevOps.
- UNKNOWN: offline-grace duration and signed policy-envelope crypto (pre-existing open items, unchanged by this ADR).

## Dependencies and approvals

- Product owner: confirm the account-level-entitlement-vs-license-key activation-carrier decision and plan tiers; review before broad implementation.
- Security Reviewer: must review PKCE/redirect/token-storage/JWKS/introspection/revocation/threat-model delta before implementation (own task created).
- DevOps Engineer: must own the self-hosted Logto topology, secrets, backup/restore, upgrades, and data residency before production.
- Backend/Desktop/Frontend Engineers: validate feasibility of RP integration, native PKCE client, and wired sign-in against their surfaces.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ADR exists at the next number, follows the repo ADR format, and is grounded in DEC-006/005/004 + current code | Doc review + `rg` for headings | ADR-0022 present with Status/Date/Confidence/Owner/Related, Context, Decision, Options, Consequences, Traceability, Follow-Up; cites DEC-006/005/004 | `docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md` | PASS |
| C-002 | yes | IdP choice is a reasoned comparison of Logto vs Zitadel/Keycloak/Authentik/Ory against the required criteria with a recommendation | ADR §Options review | Comparison table + recommendation (Logto) with rationale and swap-out (OIDC reversibility) | ADR-0022 "IdP evaluation" section | PASS |
| C-003 | yes | Desktop native OIDC flow specified: Auth Code + PKCE, redirect strategy, token/refresh handling, OS-keychain storage reusing the existing pattern; enrollment-key coexistence | ADR review + cross-check to selahcue-cloud pattern | Loopback/system-browser PKCE, rotating refresh, keychain (`KeyringSecretStore`/`Token`) storage, enrollment key as offline/secondary path | ADR-0022 "Desktop OIDC client" section | PASS |
| C-004 | yes | Platform API RP/resource-server design: token validation model, sub→CustomerOrg+user mapping, multi-user-per-org roles, account-based activation alongside `/v1/activations` | ADR review | JWKS-primary (+introspection) validation; AccountUser/OrgMembership mapping to CustomerOrg via Logto org; roles→FR-137; account-token activation converging on Device+DeviceToken | ADR-0022 "Relying party" + "Account-based activation" sections | PASS |
| C-005 | yes | Session/revocation model + offline/never-blank + self-host/devops + migration/security posture are explicit | ADR review | Session/refresh/logout/revocation vs device-token+license-window; offline degradation; Logto topology/secrets/backup/residency (flagged devops); PKCE/redirect/token-leak/no-logs posture; coexistence/migration | ADR-0022 "Session & revocation", "Offline-first", "Self-hosting", "Security posture", "Migration" sections | PASS |
| C-006 | yes | Workstream decomposed into sequenced ClickUp tasks under epic 86ajy5v6k with dependencies and a frontend unblock path; story 86ajy600r linked | ClickUp read-back of created tasks | [devops] Logto, [backend] RP+mapping, [backend] account activation, [desktop] PKCE client, [frontend] wired sign-in, [security] review — created under 86ajy5v6k with waiting_on dependencies; 86ajy600r linked | ClickUp task IDs listed in ADR "ClickUp decomposition" + final evaluation | PASS |
| C-007 | yes | No product/runtime code, migrations, or duplicate Markdown tickets were created | `git status` review | Only docs (ADR + this contract) changed; work items live in ClickUp, not Markdown | `git status --short` scoped to docs | PASS |
| C-008 | yes | Goal contract validates before and after execution; ClickUp start/final evidence posted | `validate_goal_contract.py` + ClickUp comment | Validator exits 0; epic comment records goal ID, engine, ADR path, created task IDs, terminal state | Validator output + ClickUp comment on 86ajy5v6k | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-customer-identity-oidc.md`; `rg` for ADR sections/decision IDs; ClickUp read-back of the created tasks + their dependencies.
- Broader regression verification: `git status --short` confirms no code/migrations changed and no duplicate Markdown tickets; existing epic subtasks untouched.
- Independent verifier: Product gate + Security Reviewer (dedicated ClickUp task) before implementation; this architecture pass ends at `GATE_REVIEW`.
- Required environment: local repository, ClickUp read/create tools, shell validators.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-008
- Hypothesis: DEC-006/005/004, the shipped Platform API + desktop cloud/keychain patterns, and the account-setup design are sufficient to author a review-ready OIDC/Logto ADR and decompose the workstream without writing code.
- Change or investigation: Read the decision log, Platform API (context/schemas/models/services/views/settings/README), desktop operator + selahcue-cloud secret store, account-setup handoff, ADR-0008/0021, and the ClickUp epic + related stories. Authored ADR-0022 and created the sequenced ClickUp tasks under epic 86ajy5v6k with dependencies and story 86ajy600r links.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-customer-identity-oidc.md`; `rg -n '^## |^### |Logto|PKCE|JWKS|introspection|CustomerOrg|OrgMembership|never-blank|DEC-006' docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md`; ClickUp `get_task`/read-back of created task IDs + dependencies; `git status --short`.
- Result: C-001..C-008 PASS. See ADR + ClickUp task IDs in the final evaluation.
- New evidence: `docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md`; ClickUp tasks created under 86ajy5v6k; ClickUp evidence comment on 86ajy5v6k.
- Decision: gate-review

## Risks and rollback

- Risk: the ADR could imply a bespoke-auth or embedded-webview shortcut. Mitigation: system-browser PKCE + delegate all credential handling to Logto; explicit anti-patterns section.
- Risk: identity coupling could erode offline-first / never-blank. Mitigation: auth is one-time online; device token + cached entitlement (= license window) are the offline authority; identity failures never touch the render/output path.
- Risk: multi-tenant leakage (one org seeing another's data). Mitigation: token-derived `ActorContext` with org-scoped resolvers (reuse `require_customer_org`), org claim → CustomerOrg, mandatory security review.
- Risk: IdP lock-in. Mitigation: integrate via standard OIDC only; keep the RP validation IdP-agnostic (DEC-006 reversibility).
- Rollback or recovery: docs-only + ClickUp planning; revertible without runtime impact. The shipped enrollment-key path is untouched and remains a valid fallback.

## Pause and escalation conditions

- Pause before any Logto deployment, IdP config, secret provisioning, code, or migration (owned by devops/backend/desktop after the gate).
- Escalate the account-level-entitlement-vs-license-key activation-carrier decision to Product/Architecture.
- Escalate PKCE/redirect/token-storage/revocation specifics to Security Reviewer before implementation.
- If ClickUp write access fails, record pending task/comment text in the ADR and stop at gate review rather than claiming ClickUp was updated.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-customer-identity-oidc.md`
- Validator result: PASS (structural).
- Independent verification result: Pending product gate + security review; this pass does not approve implementation.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None.
- ClickUp final evidence comment: recorded on epic 86ajy5v6k (goal ID, engine, ADR path, created task IDs + sequencing, terminal state).
