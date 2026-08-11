# SelahCue — Deployment & Configuration Keys

All hosts, secrets, and environment-specific configuration are supplied via **environment variables** — never hard-coded, never committed. This file documents **the keys** (names, purpose, whether secret, defaults). It contains **no secret values**; provide those per environment (a local `.env` that is git-ignored, your orchestrator's secret store, or the CI/host env).

**Status legend:** `WIRED` = read by the current code today · `PLANNED` = designed, not yet implemented · `DROPPED` = superseded/abandoned, kept for history · `SECRET` = never log, never commit, treat as a credential.

Grounding: [DEC-004](docs/decisions/DECISION-LOG.md) (licensing/offline entitlement), [DEC-005](docs/decisions/DECISION-LOG.md) (offline = license window), **[DEC-007](docs/decisions/DECISION-LOG.md) (traditional email/password auth, SelahCue-owned — SUPERSEDES the Logto/OIDC direction of DEC-006/ADR-0022)** / [ADR-0023](docs/architecture/adr/ADR-0023-customer-auth-email-password.md). Related ops doc: [docs/ops/WINDOWS-INSTALLER.md](docs/ops/WINDOWS-INSTALLER.md). **All `SELAHCUE_OIDC_*` / `LOGTO_*` keys below are `DROPPED` (never wired) per DEC-007.**

---

## 1. Platform API — Django (`implementation/api`)

### 1a. Core (WIRED — read in `selahcue_api/settings.py`)

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `DJANGO_SECRET_KEY` | **prod: yes** | **SECRET** | `selahcue-dev-only-insecure-key` | Django secret key. **Also the HMAC pepper** for license-key + device-token fingerprints (`apps/*/services.py::_fingerprint`) — rotating it invalidates existing key/token fingerprints, so treat as long-lived + backed up. The dev default is insecure; a real value is mandatory in prod. |
| `DJANGO_DEBUG` | no | no | `false` | Debug mode. Must be `false`/unset in prod (also gates GraphQL IDE/introspection). |
| `DJANGO_ALLOWED_HOSTS` | **prod: yes** | no | `localhost,127.0.0.1,testserver` | Comma-separated allowed Host headers. |
| `SELAHCUE_CORS_ALLOWED_ORIGINS` | as needed | no | `` (empty) | Comma-separated CORS origins (e.g. the account web surface). |
| `SESSION_COOKIE_SECURE` | no | no | `true` when not DEBUG | Force secure session cookie. |
| `CSRF_COOKIE_SECURE` | no | no | `true` when not DEBUG | Force secure CSRF cookie. |
| `SECURE_HSTS_SECONDS` | no | no | `31536000` (prod) / `0` (debug) | HSTS max-age. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | no | `true` when not DEBUG | HSTS includeSubDomains. |
| `SECURE_HSTS_PRELOAD` | no | no | `true` when not DEBUG | HSTS preload. |
| `SELAHCUE_TRUST_ACTOR_HEADERS` | no | no | = `DJANGO_DEBUG` | **Dev/test bridge only** — trusts `X-SelahCue-Actor-*` headers as the caller identity. **MUST be `false`/unset in prod.** DEC-007/ADR-0023 replace this for customers with the opaque **account session token** (`Authorization: Bearer` / the `selahcue_account_session` cookie); staff IdP is still pending. |

### 1b. Database (WIRED — `settings.py::_database_config`)

> `settings.py` now reads `DATABASE_URL`: when set it configures Postgres (so row-locking / `select_for_update` — the DEC-004 device instance-limit guard — actually holds); when unset it falls back to the bundled SQLite for dev/test.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | **prod: yes** | **SECRET** (contains DB password) | — (sqlite fallback) | Postgres DSN (`postgres://user:pass@host:port/name`) for the Platform API in prod. Unset ⇒ bundled SQLite. |
| `DB_CONN_MAX_AGE` | no | no | `60` | Persistent-connection lifetime (seconds) when `DATABASE_URL` is set. |

### 1c. Customer account auth (WIRED — DEC-007 / ADR-0023, `apps/accounts/services.py` + `settings.py`)

Traditional email/password auth. All keys are optional (the code falls back to the documented defaults via `getattr`); set them per environment to tune. The **HMAC pepper for session/credential-token fingerprints is `DJANGO_SECRET_KEY`** (§1a) — rotating it invalidates all live account sessions + email-verify/reset tokens (users re-login / re-request), so treat as long-lived.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `ACCOUNT_SESSION_TTL_SECONDS` | no | no | `2592000` (30 days) | Absolute account-session lifetime (DEC-007). `refreshSession` rotates + extends. Independent of — never shortens — the offline device-entitlement window. |
| `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS` | no | no | `86400` (24h) | Email-verification token lifetime. |
| `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` | no | no | `3600` (1h) | Password-reset token lifetime. |
| `ACCOUNT_LOGIN_LOCKOUT_THRESHOLD` | no | no | `5` | Failed logins before a per-user soft lockout. A locked account is refused with the **same `UNAUTHENTICATED`** as any failed login (never a distinct code — that would be an account-existence oracle). Durable (DB-backed on `CustomerUser`), bounded by user count — no in-memory growth. |
| `ACCOUNT_LOGIN_LOCKOUT_SECONDS` | no | no | `900` (15 min) | Lockout duration once the threshold trips. |
| `ACCOUNT_MIN_PASSWORD_LENGTH` | no | no | `10` | Minimum password length at signup / reset. |

> **Per-IP / distributed throttling** is an **edge/proxy responsibility** (reverse proxy or WAF rate-limit on `/graphql/account`) — the app enforces the durable per-user lockout above; a shared-store (Redis/DB) per-IP throttle is a tracked hardening follow-up, deliberately not an in-process cache (would not hold across worker processes and would add an unbounded structure).

> **Email delivery** ships as an injectable no-op seam (`EmailSender`) — no SMTP creds today. The concrete provider + its `EMAIL_*` keys are added **in the change that wires them** (DEC-007 defers the provider choice).

### 1d. Customer identity via OIDC/Logto (DROPPED — superseded by DEC-007)

The `SELAHCUE_OIDC_*` and `LOGTO_MGMT_*` relying-party keys (Logto-issued access-token validation, JWKS/introspection, M2M management) are **abandoned** per DEC-007 — never wired. Retained here only so old deploy configs referencing them are understood as no-ops. See §1c for the replacement.

---

## 2. Logto — self-hosted IdP service (DROPPED — superseded by DEC-007)

> **This entire section is abandoned per DEC-007** (traditional email/password auth, no self-hosted IdP). No Logto service is deployed and none of these env vars are used. Kept for history; the runbook `docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md` is likewise superseded.

The IdP is self-hosted (DEC-006). These are Logto's own env vars — see the Logto self-hosting docs for the complete set; the load-bearing ones:

| Key | Required | Secret | Purpose |
|---|---|---|---|
| `LOGTO_DB_URL` (Logto's `DB_URL`) | yes | **SECRET** | Postgres DSN for Logto's own database (separate from the Platform API DB). |
| `LOGTO_ENDPOINT` (`ENDPOINT`) | yes | no | Public base URL Logto serves from (must match the OIDC issuer host). |
| `LOGTO_ADMIN_ENDPOINT` (`ADMIN_ENDPOINT`) | yes | no | Admin console URL. |
| `LOGTO_PORT` / `LOGTO_ADMIN_PORT` | no | no | Listen ports (default 3001 / 3002). |
| `LOGTO_TRUST_PROXY_HEADER` (`TRUST_PROXY_HEADER`) | prod: yes | no | Set when behind a TLS-terminating reverse proxy. |
| `LOGTO_POSTGRES_PASSWORD` | **prod: yes** | **SECRET** | Password for Logto's dedicated Postgres user; the password component of `LOGTO_DB_URL`. |

> Logto's **OIDC signing keys + cookie keys are stored in its Postgres** (`logto_configs`), not as env vars — protect the DB and rotate via the Logto CLI (see runbook §7). No key material is set through the environment.

### 2a. Logto backup / hosting (PLANNED — DevOps, Coolify-managed backups)

Coolify-managed encrypted offsite backups of the Logto Postgres (identity + signing keys are a system of record). See [docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md](docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md) §5–§6.

| Key | Required | Secret | Purpose |
|---|---|---|---|
| `LOGTO_BACKUP_S3_BUCKET` | prod: yes | no | Offsite S3-compatible bucket for Logto Postgres backups (separate account/region). |
| `LOGTO_BACKUP_S3_REGION` | prod: yes | no | Region of the backup bucket. |
| `LOGTO_BACKUP_S3_ACCESS_KEY_ID` | prod: yes | **SECRET** | Access key id for the backup bucket (least-privilege writer). |
| `LOGTO_BACKUP_S3_SECRET_ACCESS_KEY` | prod: yes | **SECRET** | Secret access key for the backup bucket. |
| `LOGTO_BACKUP_ENCRYPTION_KEY` | no | **SECRET** | Passphrase/key to encrypt backup dumps when not relying solely on storage-side SSE. |

**DevOps owner decisions (task 86ajy7aa3):** hosting **region**, TLS/reverse-proxy, backups + upgrade path, and **identity-data retention/deletion** (FR-176/FR-177, cross-border transfer) — align with the privacy posture. Full runbook: [docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md](docs/ops/LOGTO-COOLIFY-DEPLOYMENT.md).

---

## 3. Desktop app (`implementation/desktop`)

### 3a. WIRED (read via `std::env::var` in the Rust workspace)

| Key | Required | Secret | Purpose |
|---|---|---|---|
| `SELAHCUE_CLOUD_URL` | for cloud-live | no | Base URL of the SelahCue cloud service (Providers & Privacy / AI notes; operator `--features cloud-live`). Empty ⇒ cloud shows honest "not configured". |
| `SELAHCUE_PASSPHRASE` | no | **SECRET** | Passphrase deriving the at-rest DB encryption key (Argon2id) when no OS keychain path is used (`selahcue-desktop/src/keys.rs`). |
| `SELAHCUE_STT_MODEL` | no | no | Override path to the on-device Whisper model file. |
| `SELAHCUE_STT_CACHE` | no | no | Override the on-device STT model cache directory. |
| `SELAHCUE_SMOKE` | no | no | Test/smoke-run flag. |

> Runtime secrets the desktop *stores* (not env): the SelahCue account/session token and provider tokens live in the **OS keychain** (`KeyringSecretStore`), never in env or files.

### 3b. OIDC native client (DROPPED — superseded by DEC-007)

> **Abandoned per DEC-007.** The desktop no longer uses OIDC/PKCE; it signs in against the account GraphQL surface and stores the returned opaque **account session token** in the OS keychain (`account_token`, via `KeyringSecretStore`). None of the `SELAHCUE_OIDC_*` keys below are used.

The desktop is a **PUBLIC OIDC client** → Authorization Code + **PKCE**, **no client secret**. Proposed keys (baked into the build/config, not user secrets):

| Key | Required | Secret | Purpose |
|---|---|---|---|
| `SELAHCUE_OIDC_ISSUER` | yes | no | Logto issuer URL (same host as the API's issuer). |
| `SELAHCUE_OIDC_CLIENT_ID` | yes | no (public client) | The desktop app's Logto application id. **No client secret** — PKCE only. |
| `SELAHCUE_OIDC_REDIRECT_URI` | yes | no | Loopback (`http://127.0.0.1:<port>/callback`) or custom-scheme (`selahcue://auth/callback`) redirect. |

---

## Handling rules

- **Never commit secrets.** Keep real values in a git-ignored `.env` (or the host/orchestrator secret store). This file lists keys only.
- **Rotate with care:** `DJANGO_SECRET_KEY` doubles as the fingerprint HMAC pepper — rotating it invalidates issued license-key/device-token fingerprints (plan a migration if ever rotated).
- **Prod must-set:** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, and `SELAHCUE_TRUST_ACTOR_HEADERS` unset/false.
- **Desktop is a public OIDC client** — it holds no client secret; PKCE + redirect validation carry the security (see the ADR-0022 security review, task 86ajy7aqw).
- Add new keys here in the same turn you add the `os.getenv`/`env::var` read, so this stays the single source of truth.
