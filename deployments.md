# SelahCue — Deployment & Configuration Keys

All hosts, secrets, and environment-specific configuration are supplied via **environment variables** — never hard-coded, never committed. This file documents **the keys** (names, purpose, whether secret, defaults). It contains **no secret values**; provide those per environment (a local `.env` that is git-ignored, your orchestrator's secret store, or the CI/host env).

**Status legend:** `WIRED` = read by the current code today · `PLANNED` = designed, not yet implemented · `DROPPED` = superseded/abandoned, kept for history · `SECRET` = never log, never commit, treat as a credential.

Grounding: [DEC-004](docs/decisions/DECISION-LOG.md) (licensing/offline entitlement), [DEC-005](docs/decisions/DECISION-LOG.md) (offline = license window), **[DEC-007](docs/decisions/DECISION-LOG.md) (traditional email/password auth, SelahCue-owned — SUPERSEDES the Logto/OIDC direction of DEC-006/ADR-0022)** / [ADR-0023](docs/architecture/adr/ADR-0023-customer-auth-email-password.md). Related ops doc: [docs/ops/WINDOWS-INSTALLER.md](docs/ops/WINDOWS-INSTALLER.md). **All `SELAHCUE_OIDC_*` / `LOGTO_*` keys below are `DROPPED` (never wired) per DEC-007.**

---

## 1. Platform API — Django (`implementation/api`)

### 1a. Core (WIRED — read in `selahcue_api/settings.py`)

> **The names below are exactly what the API reads, and `implementation/api/tests/test_deployment_env_docs.py` fails when this table and `settings.py` disagree** (a documented name nothing reads, a variable the API reads that has no row here, or a stale name in any default column or sentence of §1a–1e). It runs under `make api-check` and the weekly scheduled CI run, and in CI on any commit that changes these docs together with a file the workflow does not ignore; a docs-only commit does not start CI at all, because the workflow ignores `docs/**` and `**.md`, so run `make api-check` yourself when you edit this file. The API does **not** read `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` or `DATABASE_URL`; setting them does nothing. The only operator-set names with a Django prefix are `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `ENVIRONMENT` | **prod: yes** | no | `dev` | `dev`, `staging` or `prod`. **When genuinely unset, an absent/empty `SECRET_KEY` plus any non-local `DJANGO_ALLOWED_HOSTS` entry refuses startup.** Local-only defaults still select dev, and explicit `dev` remains supported. The local host set is exactly `localhost`, `127.0.0.1`, `::1` (also `[::1]`) and `testserver`; wildcard/suffix entries are non-local. A configured raw key is outside this narrow guard. Any value other than exact `dev` makes the API refuse to start when `SECRET_KEY` is empty or public. It also refuses enabled `DEBUG` or `SELAHCUE_TRUST_ACTOR_HEADERS` outside exact `dev`, selects the mail defaults (`dev` points at mailhog, anything else expects real SMTP), and is the switch for the TLS-proxy warning (`selahcue_accounts.W002`) and the eager-Celery refusal. |
| `SECRET_KEY` | **prod: yes** | **SECRET** | empty ⇒ `selahcue-dev-only-insecure-key` in `dev` only | Django secret key. **Also the HMAC pepper** for license-key + device-token + account-session fingerprints (`apps/*/services.py::_fingerprint`) — rotating it invalidates existing key/token fingerprints, so treat as long-lived + backed up. The dev key, and the `replace-me-with-a-fresh-key` placeholder that earlier copies of `implementation/api/.env.sample` carried, are public (they are in this repository's history). When `ENVIRONMENT` is not `dev` the API **refuses to start**, with an error naming `SECRET_KEY`, if it is empty, is the dev key or is that placeholder (letter case, whitespace, matched ASCII quotes and invisible format characters such as a BOM, zero-width space or joiner, or soft hyphen are ignored when comparing). A short or weak key is not refused. |
| `DEBUG` | no | no | `false` | Debug mode (`1`/`true`/`yes`/`on` are true, ignoring case and surrounding whitespace; anything else, including unset, is false). **Startup refuses a true value whenever `ENVIRONMENT` is not exactly `dev`, including staging.** In dev it also gates the GraphQL IDE/introspection, zeroes HSTS and supplies the default for `SELAHCUE_TRUST_ACTOR_HEADERS`. |
| `DJANGO_ALLOWED_HOSTS` | **prod: yes** | no | `localhost 127.0.0.1 testserver` | Allowed Host headers, **space**-separated (commas are tolerated). Any non-local entry together with genuinely unset `ENVIRONMENT` and an absent/empty raw `SECRET_KEY` refuses settings import. See the `ENVIRONMENT` row for the exact local set. |
| `SELAHCUE_CORS_ALLOWED_ORIGINS` | as needed | no | `` (empty) | Comma-separated CORS origins. **Read but not enforced**: no CORS middleware is installed (the SPA is served same-origin), and `selahcue_accounts.W001` warns if it is set. |
| `SESSION_COOKIE_SECURE` | no | no | `true` when not DEBUG | Force secure session cookie. |
| `CSRF_COOKIE_SECURE` | no | no | `true` when not DEBUG | Force secure CSRF cookie. |
| `SECURE_HSTS_SECONDS` | no | no | `31536000` (prod) / `0` (debug) | HSTS max-age. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | no | `true` when not DEBUG | HSTS includeSubDomains. |
| `SECURE_HSTS_PRELOAD` | no | no | `true` when not DEBUG | HSTS preload. |
| `SELAHCUE_TRUST_FORWARDED_PROTO` | **prod behind a TLS proxy: yes** | no | `false` | Trust `X-Forwarded-Proto: https` (sets Django `SECURE_PROXY_SSL_HEADER`); on = `1`/`true`/`yes`/`on`, anything else off. Without it a browser `Origin: https://...` is refused by CSRF and HSTS is never sent. **Opt-in**: only where every route to Django goes through a proxy that overwrites the header, else a client can forge `https`. See `docs/ops/DEPLOYMENT.md` §6c. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | only if `Origin` differs from the forwarded `Host` | no | `` (empty) | Space- or comma-separated exact `https://host[:port]` origins (no `*`, no path); a bad entry refuses to boot. See `docs/ops/DEPLOYMENT.md` §6c. |
| `SELAHCUE_TRUST_ACTOR_HEADERS` | no | no | = `DEBUG` in dev; `false` elsewhere | **Dev/test bridge only** — trusts `X-SelahCue-Actor-*` headers as the caller identity, except `anonymous` (reserved for internal failed-confirm audit rows). **Startup refuses a true value whenever `ENVIRONMENT` is not exactly `dev`, including staging and explicit ingress opt-in.** False/unset is required outside dev. DEC-007/ADR-0023 replace this for customers with the opaque **account session token** (`Authorization: Bearer` / the `selahcue_account_session` cookie); staff IdP is still pending. |
| `SELAHCUE_TRUSTED_PROXY_COUNT` | **prod behind a proxy: yes** | no | `0` | Number of **your own** proxies in front of Django, for the rate limiter's client-IP lookup (`X-Forwarded-For`). Too high is a limiter bypass, too low shares one bucket. See `docs/ops/DEPLOYMENT.md` §6b. |
| `SELAHCUE_ENTITLEMENT_SIGNING_KEY` | **prod: yes** | **SECRET** | — (none, on purpose) | Ed25519 seed (32 bytes, base64) signing offline entitlement manifests (DEC-004). No default and no dev fallback: unset, `GET /v1/entitlements/manifest` fails rather than serving an unsigned manifest. See `docs/ops/DEPLOYMENT.md` §6a. |
| `SENTRY_DSN` | no | **SECRET** | `` (empty) | Read into settings; nothing consumes it yet. Set in staging/prod only. |
| `FRONTEND_BASE_URL` | prod: yes | no | `http://localhost:2000` | Base URL of the web surface that hosts `/verify` and `/reset`; the transactional emails link to it. |

### 1b. Database (WIRED — `settings.py::_database_config`)

> The API does **not** read a `DATABASE_URL` DSN. `settings.py` reads the discrete `SQL_*` variables (the First Pavilion house convention). With `SQL_ENGINE` unset it falls back to bundled SQLite only in exact `dev`. Every other `ENVIRONMENT` refuses a missing/blank or SQLite engine and a missing/blank or exact public-default database password at settings import. In production configure Postgres: the DEC-004 device instance-limit guard uses `select_for_update`, which SQLite silently no-ops, so the limit is only enforced on a row-locking backend.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `SQL_ENGINE` | **prod: yes** | no | `django.db.backends.sqlite3` in dev only | Django database backend. Outside exact `dev`, settings import refuses an unset/blank engine or one ending in `sqlite3`, naming `SQL_ENGINE` and `ENVIRONMENT`. Configure `django.db.backends.postgresql` for deployment. |
| `SQL_DATABASE` | **prod: yes** | no | SQLite file path / `selahcue` (Postgres) | Database name (the file path for SQLite). |
| `SQL_USER` | **prod: yes** | no | `postgres` | Postgres user. |
| `SQL_PASSWORD` | **prod: yes** | **SECRET** | `postgres` in dev only | Outside exact `dev`, settings import refuses an unset/blank password or exact `postgres`, naming `SQL_PASSWORD` and `ENVIRONMENT` without logging the value. Whitespace-only is blank; configured values are preserved verbatim, with no strength or case-normalization policy. Dev retains the default for non-SQLite configurations. |
| `SQL_HOST` | **prod: yes** | no | `localhost` | Postgres host. |
| `SQL_PORT` | no | no | `5432` | Postgres port. |
| `DB_CONN_MAX_AGE` | no | no | `60` | Persistent-connection lifetime (seconds) for non-SQLite engines. |

### 1c. Customer account auth (WIRED — DEC-007 / ADR-0023, `apps/accounts/services.py` + `settings.py`)

Traditional email/password auth. All keys are optional (the code falls back to the documented defaults via `getattr`); set them per environment to tune. The **HMAC pepper for session/credential-token fingerprints is `SECRET_KEY`** (§1a) — rotating it invalidates all live account sessions + email-verify/reset tokens (users re-login / re-request), so treat as long-lived.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `ACCOUNT_SESSION_TTL_SECONDS` | no | no | `2592000` (30 days) | Absolute account-session lifetime (DEC-007). `refreshSession` rotates + extends. Independent of — never shortens — the offline device-entitlement window. |
| `ACCOUNT_EMAIL_VERIFY_TTL_SECONDS` | no | no | `86400` (24h) | Email-verification token lifetime. |
| `ACCOUNT_PASSWORD_RESET_TTL_SECONDS` | no | no | `3600` (1h) | Password-reset token lifetime. |
| `ACCOUNT_LOGIN_LOCKOUT_THRESHOLD` | no | no | `5` | Failed logins before a per-user soft lockout. A locked account is refused with the **same `UNAUTHENTICATED`** as any failed login (never a distinct code — that would be an account-existence oracle). Durable (DB-backed on `CustomerUser`), bounded by user count — no in-memory growth. |
| `ACCOUNT_LOGIN_LOCKOUT_SECONDS` | no | no | `900` (15 min) | Lockout duration once the threshold trips. |
| `ACCOUNT_MIN_PASSWORD_LENGTH` | no | no | `10` | Minimum password length at signup / reset. |
| `ACCOUNT_RESEND_MIN_SECONDS` | no | no | `0.4` | Constant-time floor for the resend-verification mutation; keep it above the slowest branch. `0` disables padding and is for tests only. |
| `ACCOUNT_RESET_REQUEST_MIN_SECONDS` | no | no | `0.1` | Floor for allowed password-reset requests, after the real commit and synchronous broker publish. Reference healthy PostgreSQL/Redis study: slowest branch 29.121ms, leaving >70ms at this default. Measure your deployment and raise this above its slowest branch when the shared rate-limited overrun warning fires. Refused budgets never pad; allowed degraded responses still do, so cache outages retain the request-thread cost even when the fallback send ceiling is spent. `0` is for tests only. |

> **Native-client sign-in has its own app-level per-IP budget** (86ak5t1gw, ADR-0029): `POST /v1/sessions` is limited by `SELAHCUE_THROTTLE_SESSION_LOGIN` and `POST /v1/activations:with-session` by `SELAHCUE_THROTTLE_ACTIVATION` (its own bucket, same budget as the enrollment-key route). Both budgets are `(10, 60)` = 10 requests per minute per client IP. **They are fixed values in `selahcue_api/settings.py`, like every other `SELAHCUE_THROTTLE_*` budget, not environment variables** — change them by editing that file; do not look for an env key. Like every `/v1` limiter they **fail open** if the limiter store is unreachable, which leaves only the per-account lockout (above) as the brake on password guessing. Both depend on `SELAHCUE_TRUSTED_PROXY_COUNT` being set to the real proxy depth behind a reverse proxy, otherwise every caller shares the proxy's address. **An edge rule keyed on `/graphql/account` does not cover these paths — extend any such rule to `/v1/sessions` and `/v1/activations:with-session`.**

> **Per-IP / distributed throttling** on the browser surface is an **edge/proxy responsibility** (reverse proxy or WAF rate-limit on `/graphql/account`) — the app enforces the durable per-user lockout above; a shared-store (Redis/DB) per-IP throttle is a tracked hardening follow-up, deliberately not an in-process cache (would not hold across worker processes and would add an unbounded structure).

> **Email delivery** goes out over SMTP using the `MAIL_*` and `DEFAULT_*` keys in §1e (mailhog in `dev`). The provider choice (DEC-007) is still open; whichever it is, it is configured through those keys.

### 1d. Customer identity via OIDC/Logto (DROPPED — superseded by DEC-007)

The `SELAHCUE_OIDC_*` and `LOGTO_MGMT_*` relying-party keys (Logto-issued access-token validation, JWKS/introspection, M2M management) are **abandoned** per DEC-007 — never wired. Retained here only so old deploy configs referencing them are understood as no-ops. See §1c for the replacement.

### 1e. Background work, cache and mail (WIRED — `settings.py`)

Redis db **1** is the cache/throttle store and db **2** is the Celery broker; keep them separate. Operational detail: `docs/ops/DEPLOYMENT.md` §6b.

| Key | Required | Secret | Default | Purpose |
|---|---|---|---|---|
| `CELERY_BROKER_URL` | **prod: yes** | **SECRET** (may carry a password) | `redis://redis:6379/2` | Celery broker (Redis db 2). |
| `CELERY_BROKER_SOCKET_CONNECT_TIMEOUT` | no | no | `0.5` (seconds) | Redis broker connection timeout. Allowed `0.05` to `10`; invalid values refuse startup. |
| `CELERY_BROKER_SOCKET_TIMEOUT` | no | no | `0.5` (seconds) | Redis broker per-command timeout. Allowed `0.05` to `10`; email publishing does not reconnect or retry on the request thread. See DEPLOYMENT §6b. |
| `CELERY_RESULT_BACKEND` | **prod: yes** | **SECRET** (may carry a password) | `redis://redis:6379/2` | Celery result backend. |
| `CELERY_TASK_ALWAYS_EAGER` | no | no | `false` | Run tasks inline in the web process. Test/debug lever: **the API refuses to start with it on when `ENVIRONMENT` is `prod`.** |
| `CELERY_TASK_EAGER_PROPAGATES` | no | no | = `CELERY_TASK_ALWAYS_EAGER` | Re-raise task exceptions in the caller while eager. |
| `CACHE_URL` | **prod: yes** | **SECRET** (may carry a password) | `` (empty ⇒ per-process LocMemCache) | Redis cache for the throttle counters, db **1** (never the broker's db 2). Unset is unusable across web workers. |
| `CACHE_SOCKET_CONNECT_TIMEOUT` | no | no | `0.5` (seconds) | How long the cache waits to open a connection to Redis. Allowed `0.05` to `10`; anything else refuses to boot. |
| `CACHE_SOCKET_TIMEOUT` | no | no | `0.5` (seconds) | How long the cache waits for Redis to answer one command. Allowed `0.05` to `10`; anything else refuses to boot. |
| `CACHE_CIRCUIT_FAILURE_THRESHOLD` | no | no | `3` | Consecutive cache budget failures before this worker bypasses Redis. Integer `1` to `100`; blank uses default. See ops §6b. |
| `CACHE_CIRCUIT_COOLDOWN` | no | no | `5` (seconds) | Bypass duration before exactly one recovery probe. Finite `0.1` to `60`; blank uses default. See ops §6b. |
| `MAIL_HOST` | **prod: yes** | no | `selahcue_mailhog` in `dev`, empty otherwise | SMTP host. |
| `MAIL_PORT` | no | no | `1025` in `dev`, `587` otherwise | SMTP port (TLS is on outside `dev`). |
| `MAIL_USERNAME` | prod: yes | no | `` (empty) | SMTP username. |
| `MAIL_PASSWORD` | prod: yes | **SECRET** | `` (empty) | SMTP password. |
| `DEFAULT_FROM_EMAIL` | prod: yes | no | `noreply@selahcue.com` | Sender address; use your verified sending domain. |
| `DEFAULT_EMAIL` | no | no | `info@firstpavitech.com` | Read into `settings.DEFAULT_EMAIL`; nothing in the API uses it today. |

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
| `SELAHCUE_CLOUD_URL` | for cloud-live | no | HTTPS base URL of the SelahCue-hosted cloud service (Providers & Privacy / AI notes; operator `--features cloud-live`). Absent/empty ⇒ cloud is not configured. Invalid or non-HTTPS ⇒ hosted cloud is disabled with a fixed diagnostic that never prints the configured URL. |
| `SELAHCUE_PASSPHRASE` | no | **SECRET** | Passphrase deriving the at-rest DB encryption key (Argon2id) when no OS keychain path is used (`selahcue-desktop/src/keys.rs`). |
| `SELAHCUE_STT_MODEL` | no | no | **Development builds only.** Path to a local Whisper model file to load instead of the pinned download; needs `SELAHCUE_STT_MODEL_SHA256`. A release build (`--release`, `make launch RELEASE=1`, the installer) ignores it, prints one line on stderr and uses the pinned, hash-checked model (17tnw2b0prh). Never set it on a production machine. |
| `SELAHCUE_STT_MODEL_SHA256` | with `SELAHCUE_STT_MODEL` | no | **Development builds only.** SHA-256 the `SELAHCUE_STT_MODEL` file must match. It proves the file is the one you meant, not that SelahCue ships it, which is why release builds ignore the pair. |
| `SELAHCUE_STT_CACHE` | no | no | Override the on-device STT model cache directory. Never point it at shared or network storage: the model file there is hashed once and then reopened by path to load, so anyone who can write to that directory can change the model that is loaded. |
| `SELAHCUE_SMOKE` | no | no | Test/smoke-run flag. |

> Runtime secrets the desktop *stores* (not env): the SelahCue account/session token and provider tokens live in the **OS keychain** (`KeyringSecretStore`), never in env or files.

The hosted cloud boundary requires HTTPS even for a loopback address. A refused value prints
`SELAHCUE_CLOUD_URL must be an HTTPS URL; hosted cloud is disabled`, without its userinfo or
query. Existing presentation/offline operation continues. `LicensingClient::new` is fallible:
callers must handle its fixed configuration error before attempting sign-in or activation.
The normal `ReqwestTransport::new` validates HTTPS before every GET/POST and also configures
reqwest with `https_only(true)`; it still follows no redirects, uses OS certificate roots and
ring, and keeps the existing connect/request deadlines.

Plain HTTP is available **only through the explicitly named test constructors**
`LicensingClient::new_for_loopback_tests` and `ReqwestTransport::new_for_loopback_tests`.
They admit HTTP only for parsed loopback IPv4/IPv6 addresses or literal `localhost`, never
arbitrary hosts or loopback-looking domain suffixes. They are for local test fixtures, are not
selected by an environment switch, and are never used by normal operator/cloud wiring. TLS,
redirect, proxy and wire tests retain their existing assertions; loopback HTTP fixtures opt in
explicitly. This is unrelated to the abandoned OIDC callback below.

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
- **Rotate with care:** `SECRET_KEY` doubles as the fingerprint HMAC pepper — rotating it invalidates issued license-key/device-token fingerprints (plan a migration if ever rotated).
- **Prod must-set:** `ENVIRONMENT` (`staging` or `prod`; **genuinely unset with an empty key and any non-local allowed host refuses settings import**; local-only defaults and explicit `dev` remain available, while a configured raw key is outside this narrow guard), `SECRET_KEY` (a fresh random value: when `ENVIRONMENT` is not `dev` the API refuses to start if it is empty, the dev key or the old `.env.sample` placeholder), `DEBUG` unset or `0`, `DJANGO_ALLOWED_HOSTS`, `SQL_ENGINE=django.db.backends.postgresql` with `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD` and `SQL_HOST`, `CACHE_URL` (without it the rate-limit counters live in each web worker's own memory and reset on every restart, so the per-IP and per-address limits barely limit anything), `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `MAIL_HOST`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `DEFAULT_FROM_EMAIL`, `FRONTEND_BASE_URL`, `SELAHCUE_ENTITLEMENT_SIGNING_KEY`, and `SELAHCUE_TRUST_ACTOR_HEADERS` unset/false. Behind a TLS-terminating proxy also `SELAHCUE_TRUST_FORWARDED_PROTO` and `SELAHCUE_TRUSTED_PROXY_COUNT`, set exactly as their rows describe (the proxy must overwrite `X-Forwarded-Proto` and be the only route to Django; the count must be exact, because a count that is too high lets a client bypass the rate limiter). Every row above marked `prod: yes` belongs on this list; a test fails if one is missing.
- **Desktop is a public OIDC client** — it holds no client secret; PKCE + redirect validation carry the security (see the ADR-0022 security review, task 86ajy7aqw).
- Add new keys here in the same turn you add the `os.getenv`/`env::var` read, so this stays the single source of truth. For the API this is checked: `implementation/api/tests/test_deployment_env_docs.py` fails when a documented name is not read, when the API reads a name with no row here, and when a name in §1a–1e or `docs/ops/DEPLOYMENT.md` §6 is stale. Run it with `make api-check`; CI runs it on the weekly schedule and on commits that also change a file CI does not ignore, but a docs-only commit does not start CI.
