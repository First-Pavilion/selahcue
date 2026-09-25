# ADR-0022: Customer identity via a self-hosted open-source IdP (Logto) over OIDC

> **⚠️ SUPERSEDED 2026-08-11 by [DEC-007](../../decisions/DECISION-LOG.md) (traditional email/password, SelahCue-owned) and ADR-0023.** The OIDC/Logto direction is abandoned. The technology-independent parts — account is the identity spine, primary account sign-in + secondary enrollment key, account-based device activation, offline entitlement = full license window, never-blank — are carried forward.


- Status: Superseded by DEC-007 (2026-08-11)
- Date: 2026-08-10
- Confidence: Medium-High
- Owner: Software Architect
- Related: **DEC-006**, DEC-005, DEC-004 (`docs/decisions/DECISION-LOG.md`); ADR-0021 (Admin Licensing Platform), ADR-0008 (LAN/secret-store + redaction posture), ADR-0011 (observability/redaction); `docs/design/ACCOUNT-SETUP-HANDOFF.md`; PRD NFR-015/CON-2 (offline-first), NFR-024 (never-blank), NFR-017 (OS-secret-store-only), FR-132 (cloud opt-in), FR-134 (account token store), FR-137 (admin-gated account changes), FR-176/FR-177 (privacy/DPA)
- ClickUp: epic 86ajy5v6k (Platform API / Licensing & Entitlements); design story 86ajy600r (Account setup, Desktop Design 2.0)
- Supersedes-in-part: ADR-0021's deferred "customer identity model" and "identity integrated with a managed IdP" open items — resolved here to a **self-hosted OSS IdP over OIDC** per DEC-006

## Context

**DEC-006** decided customer sign-in / identity uses a **self-hostable open-source IdP (Logto leading)** integrated over **OIDC**, self-hosted rather than a paid managed provider or bespoke auth — and explicitly deferred the *implementation approach* to this ADR. It sits on top of **DEC-005** (real customer sign-in is in scope now; offline entitlement = full license window, no separate grace) and **DEC-004** (licensing = account-identity spine + account-bound device *instances* + activation-cached offline entitlement; the org **enrollment key is the secondary/offline-friendly** activation path and must keep working).

The system this must integrate with already exists and constrains the design (all **Verified** from source):

- **Platform API** (`implementation/api`, Django 5.2 + Strawberry). Endpoints shipped: `/graphql/admin`, `/graphql/account`, desktop `/v1/activations` (enrollment-key-authed) and `/v1/license:refresh` (device-token-authed); `/v1/entitlements/manifest`, `/v1/downloads:*`, `/v1/usage-events:batch` are 501 stubs.
- **Actor model** (`graphql/context.py`): `ActorKind` already enumerates `STAFF | CUSTOMER | DEVICE | SERVICE`; `require_customer_org(actor, org_id)` enforces `kind == CUSTOMER` and an exact `org_id` match (mismatch → `NOT_FOUND`, no oracle). But the *only* way an `ActorContext` is produced today is the `SELAHCUE_TRUST_ACTOR_HEADERS` **dev header bridge** (`X-SelahCue-Actor-Kind/-Id/-Org-Id`), which `README.md` calls "a local/test development bridge until real staff IdP and customer identity are implemented." `route_contracts.py` declares `/graphql/account` auth as `customer_session_with_csrf` — a placeholder, not implemented.
- **Data model**: `CustomerOrg` (name, slug, status, `primary_contact_email`, country, timezone, plan, `seat_limit`, `device_limit`). `AppLicenseKey` (the enrollment/bootstrap token; hash + HMAC `secret_fingerprint`; `device_limit` = plan **instance** limit; validity window `starts_at <= now < expires_at`). `Device` (`device_public_id`, `device_fingerprint`, `platform`, PROTECT FK to both `AppLicenseKey` and `CustomerOrg`) + `DeviceToken` (show-once; `token_hash` — **originally** **`make_password`****, superseded by 86ak69u8u** (the same DEC-013 ruling applied to this column: the token is `secrets`-generated high-entropy material, so PBKDF2 bought nothing over a never-read-back column while leaving a salt-bearing, offline-testable value in any DB leak) — is now a keyed `HMAC-SHA256(SECRET_KEY)` under a distinct label; unique `token_fingerprint` = HMAC-SHA256 under `SECRET_KEY` unchanged; `expires_at == license_key.expires_at`, i.e. token lifetime **==** license window per DEC-005).
- **`activate_device` / `authenticate_device_token` / `refresh_license`** (`apps/devices/services.py`): activation is authenticated **by the presented key** and the device is its own actor (`ActorKind.DEVICE`); `authenticate_device_token` is an oracle-free (any failure → `UNAUTHENTICATED`) reusable auth for every `device_token`-gated `/v1` call. Instance-limit is enforced under a `select_for_update` row lock; idempotent on `(key, idempotency_key)` and natural `(key, device_fingerprint)`.
- **Desktop** = the Tauri operator (`implementation/desktop/crates/selahcue-operator`). The **account-token secret pattern already exists** in `selahcue-cloud`: a redacting `Token` (`Debug`/`Display` print `***redacted***`; secret reachable only via `expose()`), a `SecretStore` trait, `KeyringSecretStore` (OS Keychain/Credential Manager/Secret Service under the `cloud-live` feature) vs `InMemorySecretStore`, credential name `ACCOUNT_TOKEN_NAME = "account_token"`, and `set_account_token`/`clear_account_token` Tauri commands (FR-134/NFR-017). This is the storage seam OIDC tokens must reuse.
- **Account-setup design** is complete and QA-passed (Figma `651:124`, `docs/design/ACCOUNT-SETUP-HANDOFF.md`, story 86ajy600r). A0 leads with **"Sign in to your SelahCue account"** (primary) with the enrollment key as an **OPTIONAL** co-equal path; A1 is the sign-in screen, drawn but explicitly gated on "customer IdP is a tracked owner decision." That decision is now made — this ADR unblocks A1.

The forces:

- **Offline-first + never-blank are hard invariants** (NFR-015/CON-2/NFR-024). Auth may be online **once** (activation); after that, live presentation, slides, local scripture, media, blackout/clear and timers must work with no network and no valid session. Identity/auth must be *out of the live-output path entirely*.
- **Multi-tenant by construction.** A church = a `CustomerOrg` with potentially several people (operator, admin, volunteers). Identity must model users-in-an-org and per-org roles, and must never let one org read another's data.
- **The enrollment-key path already shipped** and is the offline/bulk/reseller bootstrap (DEC-004). Account sign-in is *additive*; it must not break or replace `/v1/activations`.
- **We must not own auth crypto or an auth UI.** DEC-006's whole point is to avoid both bespoke auth and per-user managed-IdP cost. The IdP owns password storage, password reset, MFA, and the sign-in UI.
- **Reuse, don't reinvent.** The desktop keychain+redaction pattern, the `SafeAPIError` taxonomy, the oracle-free auth style, and the OS-secret-store/no-secrets-in-logs posture (ADR-0008) are established and must be extended, not forked.

## IdP evaluation

DEC-006 names Logto as the leading candidate "or a comparable OSS self-hostable IdP." All five are OSS and self-hostable and all speak OIDC; the differentiators for *SelahCue customer (CIAM) identity* are multi-tenant/organization modelling, how much sign-in/UI/MFA we get for free, and self-host operational weight.

| Criterion | **Logto** (recommended) | Zitadel | Keycloak | Authentik | Ory (Hydra + Kratos) |
|---|---|---|---|---|---|
| OIDC completeness (Auth Code+PKCE, refresh, JWKS, discovery) | Complete; built on the mature `oidc-provider`; native-app PKCE + refresh rotation | Complete (+SAML) | Complete, reference-grade (+SAML) | Complete (+SAML/LDAP/proxy) | Hydra is a certified OAuth2/OIDC provider; **no user store/UI** (Kratos supplies those) |
| Multi-tenant / org modelling | **First-class Organizations** + org-scoped roles/permissions (maps 1:1 to CustomerOrg + per-org roles) | First-class Organizations + projects/grants | Realms (heavy per-tenant) or newer Organizations feature | "Brands"/tenants weaker for B2B org RBAC | Build-your-own (no org concept out of the box) |
| Sign-in UI + MFA + password reset (we don't build/harden) | Hosted sign-in experience, TOTP/WebAuthn/backup-codes, password reset, social connectors — batteries included | Hosted UI + MFA + passwordless | Hosted UI + MFA (very complete) | Hosted flows + MFA | **You build the login/reset/MFA UI** against Kratos APIs |
| Self-host footprint / ops burden | Low: single service + Postgres, docker-compose; modest memory | Medium: Go + Postgres/Cockroach, event-sourced | High: JVM/Quarkus, heavier memory + realm ops | Medium: Python/Django + Redis + worker | High: two services + your own UI to assemble/operate |
| Licensing | MPL-2.0 core (permissive enough for self-host; some features are cloud/enterprise) | Apache-2.0 | Apache-2.0 | MIT core (+ enterprise) | Apache-2.0 |
| Data residency (self-hosted → church identities stay ours) | Yes | Yes | Yes | Yes | Yes |
| Admin/management API | Full management API + console | Full API + console | Full admin API + console | Full API + console | APIs only, no unified console |
| Net fit for SelahCue CIAM | **Best fit**: purpose-built customer identity, orgs, and a complete hosted UX at low ops cost | Strong alternative (heavier ops, orgs excellent) | Strongest feature set but heaviest to run; best if SAML/enterprise SSO becomes a hard need | Better as an internal SSO/proxy than B2B CIAM | Most flexible, **most to build/operate** — contradicts "don't own auth UI" |

**Recommendation: Logto** (confirming DEC-006). It is purpose-built customer identity with **first-class Organizations + org roles** that map directly onto our `CustomerOrg` + multi-user-per-org + FR-137 admin-gating, it gives us a complete hosted sign-in / MFA / password-reset UX so we build and harden **no** auth UI, and it self-hosts at the lowest operational weight (one service + Postgres). **Keycloak** is the designated alternative if enterprise SAML/SSO becomes a hard requirement or JVM ops are already in-house; **Zitadel** is a close second on org modelling with heavier ops. **Ory** and **Authentik** are rejected for this use: Ory forces us to build the sign-in/MFA/reset UI (the opposite of DEC-006's intent), and Authentik's tenancy is a weaker fit for per-org B2B RBAC.

Because integration is via **standard OIDC**, the choice is reversible: swapping IdP later changes IdP deployment + the RP's issuer/JWKS/claim mapping, not the desktop PKCE client shape, the device-token/entitlement machinery, or the enrollment-key path (DEC-006 reversibility).

## Decision

Adopt **self-hosted Logto as the customer IdP, integrated over OIDC**, with the Platform API as an **OIDC relying party + resource server** and the Tauri desktop as an **OIDC native (public) client** using **Authorization Code + PKCE**. Account sign-in becomes the primary activation path; the enrollment key remains the secondary/offline path (DEC-004). Concretely:

### 1. Desktop OIDC client (Tauri native app)

- **Flow: Authorization Code + PKCE (S256), no client secret** (RFC 8252 native-app best practice). The desktop is a **public** client.
- **User-agent: the system browser, never an embedded WebView.** SelahCue's own WebView must never render the IdP login (no credential capture in-app; ADR-0002/0003 already forbid rendering non-console content there). This is a hard anti-pattern boundary.
- **Redirect: loopback (`http://127.0.0.1:<ephemeral-port>/callback`) as the primary**, with a registered **custom scheme (`selahcue://auth/callback`)** as the fallback for platforms where loopback capture is awkward. `state` (CSRF) and `nonce` (ID-token binding) are mandatory and verified; the redirect URI is validated by exact match.
- **Tokens:** the IdP returns an **ID token** (identity assertion — verify `iss`/`aud`/`nonce`/`exp`), a short-lived **access token** (bearer for `/graphql/account` + account-scoped `/v1`), and a **rotating refresh token**. Request `openid profile email offline_access` + a SelahCue API resource/audience scope.
- **Storage: reuse the existing OS-keychain seam.** Persist the **refresh token** (and optionally the ID token) via `KeyringSecretStore` under new credential names (e.g. `oidc_refresh_token`), wrapped in the redacting `Token` type; keep the **access token in memory**, refreshing on demand. This directly extends the `ACCOUNT_TOKEN_NAME`/`set_account_token` pattern (FR-134/NFR-017). Access/refresh tokens are never written to logs (redacted `Debug`/`Display`).
- **New Tauri commands:** `account_sign_in` (launch system-browser PKCE, capture callback, exchange code, store tokens), `account_sign_out` (clear keychain + RP-initiated logout at Logto's `end_session_endpoint`), and an `account_status` that reports signed-in/expiry **without** exposing token material — mirroring how `providers_view`/`account_token_set` surface only booleans today.
- **Enrollment-key coexistence:** the A2 enrollment-key screen and `POST /v1/activations` are **unchanged**. The A0 chooser offers both co-equal paths; whichever completes, the device ends up with a **device instance + cached entitlement**, so offline behaviour is identical afterwards. Sign-in is the one-time-online step, exactly like entering a key.

### 2. Platform API as OIDC relying party / resource server

- **Token validation — JWKS-primary, introspection-reserved.** Validate Logto JWT access tokens **locally against Logto's published JWKS** (`/.well-known/jwks.json`), checking signature (`kid` rotation-aware, cached), `iss`, `aud` (the SelahCue API resource), `exp`, and required scopes. This is low-latency and avoids a per-request IdP round-trip (better for the offline-tolerant, self-hosted posture). Use **token introspection** only for high-value/immediate-revocation-sensitive operations (e.g. destructive account or device-management mutations) where a few-minute JWT validity window is unacceptable. Configure short access-token TTLs so JWKS validation stays safe.
- **`sub` → CustomerOrg + user mapping.** Introduce two new records in `apps/accounts`:
  - `AccountUser` — `idp_subject` (Logto `sub`, unique), `email`, `display_name`, status, timestamps.
  - `OrgMembership` — FK `AccountUser` × FK `CustomerOrg`, plus `role` and `status`; unique on `(account_user, customer_org)`.
  - Map the **Logto Organization id** to a `CustomerOrg` via a stored `external_org_id` (add to `CustomerOrg`). The access token carries the active **org claim** (Logto organization token) + **org roles**; the RP resolves org claim → `CustomerOrg`, `sub` → `AccountUser`, and builds a **token-derived `ActorContext`** (`kind=CUSTOMER`, `actor_id=sub`, `org_id=CustomerOrg.id`, roles). This replaces the header bridge as the real producer of the `CUSTOMER` actor that `require_customer_org` already expects.
  - **JIT provisioning** on first sign-in under controlled rules (org must exist / be invited — no self-serve org creation from the desktop unless Product decides otherwise; flagged).
- **Multi-user-per-org + roles.** Logto org roles map to SelahCue account roles (at least **Admin** and **Member/Operator**). **FR-137** (admin-gated activate/deactivate/manage-devices) maps to the **Admin** org role; the A10 read-only variant is the Member view. Resolvers stay org-scoped via `require_customer_org` (tenant isolation).
- **Account-based device activation alongside `/v1/activations`.** Add an **account-authenticated activation path** (a new `/v1` command, e.g. `POST /v1/activations:account`, authenticated by the **account access token** rather than an enrollment key) that: resolves the caller's `CustomerOrg` from the token, selects the org's canonical `AppLicenseKey` (the instance-limit + validity carrier), then runs the **same** instance-limit check + `Device`/`DeviceToken` issuance as the enrollment-key path — converging on the identical `Device` + show-once `DeviceToken` + cached-entitlement outcome. The device remains its own `ActorKind.DEVICE` afterward; `/v1/license:refresh` is unchanged and continues to authenticate by device token. This keeps the offline model identical regardless of how the device was activated.
  - **Open decision (flagged):** whether account activation keeps hanging a `Device` off the org's `AppLicenseKey` (chosen for this slice — minimal change, `Device.license_key` is a required PROTECT FK) **or** introduces an account-level entitlement so the instance limit can move to `CustomerOrg.device_limit`. Deferred to Product/Architecture; the activation task carries it.

### 3. Session, token, logout & revocation model

- **Sessions live in the IdP.** SelahCue holds no password and no long-lived server session for customers; the desktop holds the rotating refresh token, the API trusts short-lived access tokens.
- **Logout** = clear desktop keychain tokens **and** RP-initiated logout at Logto (`end_session_endpoint`) to end the IdP session.
- **Revocation layers, deliberately independent (this is what protects never-blank):**
  1. Revoking the **account session / refresh token** (at the IdP, or via reuse-detection) stops **new** cloud calls and **new** account-based activations. It does **not** revoke the already-issued **device token** or the **cached offline entitlement**.
  2. The **device token + cached entitlement remain valid for the full license window** (DEC-005) regardless of account session state — so a revoked/expired sign-in never blanks or blocks a device already presenting.
  3. Freeing an instance slot / stopping a device is the **existing device-deactivation** flow (revoke the `DeviceToken`, `Device.status → REVOKED`), which is separate from account logout by design (design frames A8/A9).
- Access-token TTL short (order of minutes to ~1h); refresh-token rotation with **reuse detection**; refresh happens opportunistically when online, exactly like `/v1/license:refresh`.

### 4. Offline-first & never-blank alignment

- **With no network:** live presentation and all local features work unchanged; an already-activated device keeps its cached entitlement until the **license window** ends (DEC-005). Sign-in and account-based activation require a **one-time** online step — identical to entering an enrollment key.
- **Degradation:** if the browser/IdP is unreachable during sign-in, the desktop shows the designed A7 "Can't reach SelahCue — you're ready to present offline" state and offers **Continue offline** / the **enrollment-key** path. No identity/auth failure is ever on the render/output path (NFR-024).

### 5. Self-hosting / devops / data residency  *(flagged for /devops-engineer)*

- **Topology:** Logto container + its **Postgres** (identity data of churches), fronted by TLS, alongside the existing Platform API + its DB. The Platform API reaches Logto's OIDC discovery/JWKS/introspection/management endpoints over TLS on a private network where possible.
- **Secrets:** Logto signing keys, DB credentials, the API↔Logto management credential, and cookie/encryption keys via a KMS/secret manager (not env files in prod); rotate on a schedule. No secrets in logs (ADR-0011/ADR-0008 posture).
- **Backup/restore + upgrades:** back up the Logto Postgres (identity is now a system of record); tested restore; version-pinned Logto upgrades with a rollback plan and a staging tenant. Availability target for the IdP should reflect that it gates **new** sign-ins/activations only, never live presentation.
- **Data residency:** self-hosting keeps church identities in SelahCue-controlled infrastructure (the DEC-006 privacy rationale). The hosting region + retention/deletion of identity data are owner decisions (align with FR-176/FR-177 and ADR-0021's retention follow-up).

### 6. Migration / coexistence & security posture

- **Coexistence/migration:** the enrollment-key activation contract (`app_key_then_device_token`) is **untouched**; account identity is purely additive. The `SELAHCUE_TRUST_ACTOR_HEADERS` header bridge is **retired in production** (kept for tests/local) once the token-derived `ActorContext` lands — `require_customer_org`/`ActorKind.CUSTOMER` already exist, so this is a producer swap, not a rewrite. `/graphql/account`'s declared `customer_session_with_csrf` becomes **bearer-token** auth (note the shift away from a CSRF-cookie session for the API resource surface).
- **Security posture (extends ADR-0008 / threat model):** PKCE **S256** mandatory; `state` + `nonce` verified; **exact** redirect-URI validation; **system browser only** (no embedded-WebView credential capture); tokens **only** in the OS keychain via the redacting `Token` (NFR-017), never in logs; JWKS signature + `iss`/`aud`/`exp`/scope validation with `kid`-rotation handling; refresh-token **rotation + reuse detection**; TLS for all IdP traffic; **rate-limiting** on account auth/activation endpoints (align with the existing `/v1` rate-limiting task 86ajy62xz); oracle-free failures (reuse the `SafeAPIError`/`UNAUTHENTICATED` style). A dedicated **Security Reviewer** pass is required before implementation (task created); it owns the threat-model delta and this posture — this ADR does not self-approve security.

## Options considered

### Option A — Self-hosted Logto over OIDC (CHOSEN)

Pros: satisfies DEC-006 directly; purpose-built CIAM with first-class Organizations + roles mapping onto CustomerOrg/FR-137; complete hosted sign-in/MFA/reset UX (no bespoke auth UI to build or harden); low self-host footprint; standard OIDC keeps the IdP swappable; reuses the desktop keychain/redaction + oracle-free auth patterns; enrollment-key path and offline model preserved unchanged.
Cons: we now operate an IdP (deployment, Postgres, secrets, backup, upgrades, residency); MFA/reset UX quality is bounded by Logto; adds JWKS/claim-mapping + token-lifecycle code to the RP; MPL-2.0 core (some enterprise features gated).

### Option B — A different OSS IdP (Keycloak / Zitadel / Authentik / Ory)

Rejected as the default (kept as alternatives). Keycloak/Zitadel are viable but heavier to operate for a modest per-church CIAM need (Keycloak) or slightly less turnkey (Zitadel); Authentik's tenancy fits internal SSO better than B2B org RBAC; Ory forces us to build and operate the login/MFA/reset UI ourselves — contradicting DEC-006's "don't own bespoke auth." Because we integrate via OIDC, any of these can replace Logto later without touching the client or device machinery.

### Option C — Build customer accounts on Django's own auth

Rejected (and superseded by DEC-006). It puts password storage, reset, MFA, session security, and org RBAC on us — exactly the bespoke-auth burden DEC-006 chose to avoid — and duplicates what a self-hosted IdP already provides. Higher long-term security-maintenance cost with no offsetting benefit.

### Option D — A paid managed IdP (Auth0/Clerk/Cognito/…)

Rejected by DEC-006: per-user managed-IdP cost and moving church identities off SelahCue-controlled infrastructure conflict with the privacy-first, self-hosted, no-vendor-lock-in posture (and DEC-004's self-hosted model). Managed IdPs also still speak OIDC, so this ADR's client/RP design would port if that decision ever reversed.

### Option E — Embedded-WebView login / ROPC (password grant) in-app

Rejected outright as an anti-pattern. Capturing IdP credentials in SelahCue's own WebView (or via the OAuth Resource-Owner-Password-Credentials grant) defeats the point of delegating auth, breaks MFA/social/SSO, and creates a credential-theft surface. Auth Code + PKCE in the **system browser** is the required approach (RFC 8252).

## Consequences

Positive:
- One coherent, standards-based customer-identity spine that unblocks the account-setup A1 sign-in (story 86ajy600r) and gives the cloud AI/quota/billing surfaces a real authenticated principal.
- Multi-user-per-org + roles land cleanly on the existing `CustomerOrg` + `ActorKind.CUSTOMER`/`require_customer_org` seam; FR-137 admin-gating is a role check.
- Offline-first + never-blank are preserved by construction: identity is one-time-online and strictly separated from the device-token/entitlement authority and the live-output path.
- The enrollment-key path and the whole `/v1` device machinery are untouched — additive, low-risk.
- IdP is swappable (OIDC), avoiding lock-in.

Negative / accepted costs:
- New operational surface (self-hosted Logto + Postgres + secrets + backups + upgrades + residency) — a high-value target requiring devops ownership and a security review.
- The RP gains token-validation, JWKS-cache/rotation, claim-mapping, and refresh-lifecycle code that must be built and reviewed.
- Two activation paths (key + account) to keep behaviourally convergent and tested.
- A migration step to retire the header-actor bridge and move `/graphql/account` to bearer auth.

## Requirements traceability

| Ref | Requirement | How this ADR satisfies it |
|---|---|---|
| DEC-006 | Self-hosted OSS IdP (Logto) over OIDC | Logto recommended + confirmed; OIDC RP + PKCE native client; swappable via OIDC |
| DEC-005 | Real sign-in now; offline entitlement = full license window | Account sign-in is primary; device token/entitlement TTL == license window; revoking a session never shortens it |
| DEC-004 | Account spine + device instances + enrollment key = secondary/offline | Account-based activation converges with `/v1/activations`; enrollment-key path unchanged |
| NFR-015/CON-2 | Offline-first | Auth one-time online; all live/local features work offline afterward |
| NFR-024 | Never-blank | Identity/auth failures off the render/output path; independent revocation layers; A7 offline degradation |
| NFR-017/FR-134 | OS-secret-store-only account token | Reuse `KeyringSecretStore` + redacting `Token`; tokens never in logs |
| FR-132 | Cloud opt-in | Account is the authenticated principal for cloud features; Providers & Privacy ↔ Account link |
| FR-137 | Admin-gated account changes | Admin org role gates activate/deactivate/manage-devices; A10 read-only = Member |
| FR-176/FR-177 | Privacy/DPA | Self-hosted identity, residency + retention flagged to owners |
| ADR-0008/ADR-0011 | Secret-store/redaction/no-secrets-in-logs | Extended to OIDC tokens; oracle-free failures; PKCE/redirect posture added to the threat model |

## ClickUp decomposition

Workstream created under **epic 86ajy5v6k** (Platform API / Licensing & Entitlements); design story **86ajy600r** linked so the account-setup frontend has a clear unblock path. Sequencing (waiting_on dependencies):

1. **[DevOps]** Self-host Logto (topology, Postgres, secrets/KMS, backup/restore, upgrades, data residency; register the desktop native app + the API resource/audience; publish issuer/JWKS/discovery). → blocks 2 and 4.
2. **[Backend]** Platform API as OIDC RP/resource server: JWKS-primary validation (+introspection option), `AccountUser`/`OrgMembership` models + `CustomerOrg.external_org_id` + migration, Logto-org↔CustomerOrg mapping, token-derived `ActorContext` replacing the header bridge, org roles, `/graphql/account` → bearer. → waiting_on 1; blocks 3.
3. **[Backend]** Account-based device activation (`POST /v1/activations:account`, account-token-authed) converging on `Device` + show-once `DeviceToken`; carry the license-key-vs-account-entitlement carrier decision. → waiting_on 2; blocks 5.
4. **[Desktop]** OIDC Auth Code + PKCE native client in Tauri: system-browser + loopback/custom-scheme redirect, code exchange, refresh rotation, keychain token storage (reuse `KeyringSecretStore`/`Token`), `account_sign_in`/`account_sign_out`/`account_status` commands, RP-initiated logout. → waiting_on 1; blocks 5.
5. **[Frontend]** Account-setup UI wired to real sign-in (A0 chooser + A1 sign-in from ACCOUNT-SETUP-HANDOFF) driving the desktop OIDC commands; enrollment-key path already exists as secondary. → waiting_on 3 and 4; realises story 86ajy600r.
6. **[Security]** Security review of the OIDC integration (PKCE/redirect/state+nonce, token storage, JWKS/introspection, refresh rotation/reuse detection, revocation vs never-blank, no-secrets-in-logs, threat-model delta). → waiting_on 2, 3, 4.

Related existing task: **86ajy62xz** (/v1 rate-limiting) should cover the account auth/activation endpoints.

## Required follow-up

- **Product/Architecture:** decide account-activation instance-limit carrier (org `AppLicenseKey` vs account-level entitlement); JIT-provisioning/invite rules for first sign-in; plan tiers (OD-04).
- **Security Reviewer:** own the threat-model delta + posture sign-off before implementation (task 6).
- **DevOps:** own Logto hosting, secrets/KMS, backup/restore, upgrades, data-residency region + identity-data retention (task 1).
- **Backend/Desktop/Frontend:** feasibility-confirm RP validation, native PKCE client, and wired sign-in on their surfaces (tasks 2–5).
- Pre-existing open items unchanged: offline-grace duration and signed policy-envelope crypto (tracked on the epic), staff IdP/MFA (ADR-0021).
