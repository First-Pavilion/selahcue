# SelahCue Platform API

This root contains the Django + Strawberry backend for SelahCue Admin licensing, customer accounts, and the desktop `/v1` command API.

**Stack:** Django 6.1 · Strawberry GraphQL · Python ≥3.12 (developed and CI-tested on 3.14).

## Implemented

- Staff Admin GraphQL endpoint: `/graphql/admin`
- Customer Account GraphQL endpoint: `/graphql/account`
- Durable customer-organisation creation/search (staff Admin)
- Durable app license-key issuance: finite validity window, reason capture, idempotency key, masked metadata, show-once full key, hash/fingerprint persistence, audit event
- **Customer authentication** (DEC-007 / ADR-0023): signup, email verification, login/logout, session refresh, password reset — opaque server-side hashed sessions, not JWT
- **Device activation** `POST /v1/activations` — enrollment-key authed, instance-limit enforced, show-once device token
- **Account-based activation** `activateDeviceWithSession` (GraphQL, ADMIN-only per DEC-005)
- **Native-client account sign-in** `POST /v1/sessions` (email + password → session token) and `POST /v1/activations:with-session` (`Authorization: Bearer <session token>` → device token). These are what the desktop calls (`selahcue-licensing`, ClickUp 17tnw2b1we2); it never calls `/graphql/account`, which authenticates from a session cookie, so it keeps CSRF enforced and a cookie-less native client cannot use it. These routes and the single-session cleanup route below are `csrf_exempt` because they read the session from the `Authorization` header only and never set a cookie. Wire contract: `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`; decision and safety argument: ADR-0029 (86ak5t1gw).
- **License refresh** `POST /v1/license:refresh` — device-token authed, pure read
- **Signed offline entitlement** `GET /v1/entitlements/manifest` — see below

## Still stubbed (`501`)

`POST /v1/downloads:prepare`, `POST /v1/downloads/<lease_id>:complete`, `POST /v1/usage-events:batch`, and `/webhooks/billing/<provider>`.

The API does not yet issue download leases, serve licensed Bible text, sync billing providers, or store provider secrets. Header-derived actors remain a local/test bridge; customer identity goes through real session auth. Startup refuses enabled `DEBUG` or `SELAHCUE_TRUST_ACTOR_HEADERS` whenever `ENVIRONMENT` is not exactly `dev`, including staging and explicit ingress opt-in. The bridge rejects `anonymous`; internally generated failed-confirm audit actors remain valid. Production staff identity integration remains separate.

## Activation input

Both native activation routes and account GraphQL activation validate device metadata before writing a device or token. Fields must be strings; control characters and invalid Unicode are refused. `platform` is one of `macos`, `windows`, or `linux`, matching the desktop licensing client. Fingerprints and display names are at most128 characters, app versions at most32; optional version/name fields may be omitted or empty. Native routes return JSON400 `VALIDATION_FAILED` for malformed, excessively nested or oversized JSON bodies, using Django's existing body-size limit. No field is converted from an array, object, boolean or number into text.

Enrollment activation requires `Content-Type: application/json` before any throttle budget or database work. A browser-simple non-JSON request receives400 `VALIDATION_FAILED` without spending the shared-egress budget. License refresh applies the same rule to its JSON body-token fallback. Its existing `Authorization: Bearer` form remains usable without a JSON body or Content-Type; the existing token authentication and header-over-body precedence still apply. GET manifest requests are unchanged (17tnw2b1wqb).

Shared `/v1` throttle denials return the existing 429 `RATE_LIMITED` JSON envelope with `Cache-Control: no-store` and `Retry-After` as remaining fixed-window seconds, rounded up to at least one. Expiry is read from the existing counter only after denial (Redis primary PTTL; local-memory expiry under its lock). Redis denials pay one additional command under the existing socket timeout; allowed and fail-open requests do not. If expiry metadata cannot be read or a custom backend has no supported expiry reader, the denial remains 429 with a bounded full-window retry hint. Keys, configured budgets and response bodies are unchanged. These headers do not extend to Django method guards or other framework errors (17tnw2b1wqc).

## Native authentication visibility

The application logger `selahcue_api.apps.throttling.guards` warns when a shared native
throttle actually refuses requests, at most once per 60 seconds per scope per worker process.
The fixed scopes are `activation`, `session_login`, `activation_with_session`, `license_refresh`
`entitlement_manifest`, and `session_revoke`; they reuse the existing scope-only denial suppression. A separate
aggregate `scope=session_login refused sign-ins` warning reports login-service refusals, including
wrong credentials, lockouts, account-policy refusals and service validation errors, at most once
per 60 seconds per worker. It does not distinguish these outcomes, count attempts or identify
callers. A login throttle denial and a service refusal are independent signals. Requests rejected
by the native transport/body checks before calling the login service, and successful sign-ins,
do not emit the service-failure warning.

These warnings contain no IP, email, customer ID, password, token, fingerprint or exception. Native
reporting adds at most six fixed denial timestamps and one aggregate failure timestamp, protected
by the shared reporting lock, with no per-identity maps or database writes. State resets on worker
restart; fleets can emit one warning per scope/event per worker each minute. This application
warning bound does not change Django's existing request-status logs or broker/cache-outage logs.
Browser GraphQL login, authentication decisions, budgets and response envelopes,
remaining-window retry headers and native cookie/content-type guards keep their existing behavior
(17tnw2b1wqa).

## Native bootstrap login during limiter outages

`POST /v1/sessions` returns the existing429 `RATE_LIMITED` JSON response when the limiter store
is unavailable, before calling the login service or hashing a password (17tnw2b1wq9). This
intentionally prevents new native sign-ins during a cache outage: bootstrap availability is
traded for bounded password work. Twentyfive such attempts perform zero password hashes.
Healthy behavior remains ten attempts per 60 seconds per IP, with the existing account lockout.
Browser GraphQL login does not gain this native policy. Enrollment/session-based activation,
license refresh and entitlement reads retain their existing fail-open limiter policy; already
activated devices can refresh with their existing device tokens during the same cache outage.

Outage refusal retains `Cache-Control: no-store`, sets no cookie and uses a conservative
full-window `Retry-After` hint (60 seconds at the default); it does not query failed-store expiry
metadata. A real budget denial still reports the actual remaining-window hint. Admission resumes
as soon as the store recovers; the hint is not a separate local lock or per-identity fallback.
Each request may still pay the existing bounded store timeout; no circuit breaker is introduced.
The shared outage warning reports unavailable budget evaluation, without keys, IPs, credentials
or exception text, once per 60 seconds per process under a reporting lock. Admission is decided by
the caller; the separate scope-only native denial warning retains its existing suppression.

## `GET /v1/entitlements/manifest`

The signed offline entitlement (DEC-004). Device-token auth via `Authorization: Bearer <device_token>`. Returns an Ed25519 envelope:

```json
{ "envelope_version": 1, "alg": "Ed25519", "key_id": "a1b2c3d4",
  "payload": "<base64url>", "signature": "<base64url>" }
```

**Verify the signature over the `payload` string exactly as received, then decode it.** Do not re-serialize the decoded JSON and verify against that — the signature covers the transmitted bytes, which is what lets a Rust verifier agree without matching Python's JSON formatting. Check `alg` against an allow-list of exactly `Ed25519`; dispatching on a caller-supplied algorithm field is how confusion attacks work.

Issued **only** when the licence status is in `ACTIVATABLE_KEY_STATUSES` and the validity window is open — deliberately stricter than `license:refresh`, which reports honestly because it mints nothing. This endpoint mints a credential cacheable to the licence expiry, and with no revocation list issuance is the only enforcement point.

Requires `SELAHCUE_ENTITLEMENT_SIGNING_KEY` (see `docs/ops/DEPLOYMENT.md` §6a). Without it the endpoint returns `500` rather than serving an unsigned manifest.

## Open owner decisions

- Staff IdP, MFA, session TTL, and emergency access
- Hosting, database, object store, and KMS/secrets provider
- First licensed translations, territories, deletion SLA, export/copy caps, provider reporting payloads
- Retention/deletion periods by data class
- Plan tiers and price points (OD-04)

*Resolved:* customer identity (DEC-007); policy-envelope cryptographic suite and rotation (Ed25519 with a derived `key_id`); offline grace (DEC-005 — entitlement expiry equals the licence window, no separate timer).

## Local verification

From the repository root:

```bash
make api-install   # once per checkout, and after lock/profile/build-input changes: builds the venv, needs the network
make api-check     # django check + migrations committed + pytest, the same three commands as the CI `api` job
```

`make ci` runs `make api-check`; it never installs, so on a fresh worktree it stops with an instruction to run `make api-install`. `api-install` needs Python 3.14 on PATH (CI's version) or `API_PYTHON=/path/to/python` for any 3.12 or newer.

- The venv is `implementation/api/.venv-api-check`, a name only these targets use (your own `.venv` is never touched), gitignored and per checkout. `api-check` refuses it when it is a symlink, was built with another Python minor version (a patch update is fine) or from another checkout, or project/lock/tool/installer inputs changed since (content hash, so a `touch` is fine). If you built it with an interpreter other than the default `python3.14`, keep `API_PYTHON` exported for `make api-check` as well. An interrupted or failed `make api-install` can simply be run again.
- Local database-backed tests run on SQLite in memory. Controls that require a live Postgres or Redis service (`tests/test_concurrency_postgres.py`, the deployed PostgreSQL connection control in `tests/test_deployment_guards.py`, and one test in `tests/test_cache_socket_timeouts.py`) **skip locally**; CI runs them. Deployed-mode startup checks remain mandatory locally: the dev extra now installs exact `psycopg[binary]==3.3.6`, the driver already exercised by successful CI40945205792 and consumed from the same lock by CI/Docker, so these checks can load a legitimate PostgreSQL configuration without a running database. This driver stays outside core runtime dependencies.
- After this dependency change, rerun `make api-install` before `make api-check`; the venv content stamp rejects the previous install.
- `uv.lock` includes runtime, dev/PostgreSQL-driver, transitive and explicit `build` dependencies. Every local/CI/Docker install uses `--locked`: manifest drift fails instead of silently resolving. First sync is wheel-only (`--no-build --no-install-project`); final editable installation is offline and non-isolated with the locked setuptools backend. Unsupported platforms without a compatible wheel fail deliberately; there is no automatic source-build exception. Python >=3.12 is retained; CI/Docker use3.14.
- Verification never runs uv, installs, resolves or rewrites the stamp. A lock-only change requires a deliberate reinstall; touching files without changing their content does not.

### Pinned uv bootstrap and dependency updates

Use **uv0.13.4** (`.uv-version` and `[tool.uv].required-version`); it was released2026-10-20, outside the14-day cooldown on2026-11-04. Install deliberately using the [official versioned installer](https://docs.astral.sh/uv/getting-started/installation/#installing-a-specific-version), or download the exact platform archive from the [official release](https://github.com/astral-sh/uv/releases/tag/0.13.4), compare SHA256 with its published digest, then place its binary on PATH. This migration verified the macOS arm64 archive SHA256 `e0b1d4743ce64c55d9f0f4a444afa6b81125680070ee04e853fcd0f6c1ebf8f1`. CI pins the official setup-uv action commit and version; Docker pins the official multi-platform image digest. Upgrading uv is a separate reviewed pin update across these consumers.

From `implementation/api`, use `uv lock --check --offline` to check committed lock freshness without installation. `--locked` validates that the manifest and lock agree and fails if resolution would change the lock; `--frozen` uses the existing lock without checking that agreement. All installation consumers here use `--locked`; substituting `--frozen` would weaken the stale-lock gate. Ordinary resolutions enforce `[tool.uv].exclude-newer = "14 days"`, mirrored by Dependabot's uv cooldown. A direct update edits its exact pin (and both build-system/build-group pins for setuptools), then runs `uv lock --upgrade-package PACKAGE`. A transitive-only update runs that same command without changing direct pins. Review the complete diff; do not use an unrestricted `--upgrade` for a targeted update. Run `make api-install`, all API checks and the four reviews before merging. Roll back by reverting the manifest and lock together, then deliberately reinstall. Never hand-edit hashes or bypass `--locked`, wheel-only dependency sync, or offline project build.

Native [Dependabot uv support](https://docs.astral.sh/uv/guides/integration/dependency-bots/#dependabot) consumes this directory's manifest and lock, including exact transitive versions. GitHub's [static graph support matrix](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems) currently does not list uv.lock. The main-push/API-changes-only `api-dependency-graph` job therefore exports every registry package, version, edge and scope using `scripts/api_dependency_snapshot.py`, submits the snapshot through GitHub's dependency submission API, and retains the exact payload as an artifact. Only that job has `contents: write`; PR checks remain read-only. After merge, wait for its actual successful submission for the merged SHA, then read `gh api repos/First-Pavilion/selahcue/dependency-graph/sbom`. Compare its PyPI name/version set to all37 registry entries in uv.lock (including platform-conditional packages and setuptools84.1.0), record submission receipt/commit/run provenance and concrete versions on the ticket. Do not move to QA on an artifact or HTTP acceptance alone if graph indexing is still pending.

By hand, after `make api-install`, run:

```bash
.venv-api-check/bin/python manage.py check
.venv-api-check/bin/python manage.py makemigrations --check --noinput
.venv-api-check/bin/python -m pytest tests -q
```

`tests/test_nginx_forwarded_proto.py` requires the full repository checkout: it reads
`implementation/marketing/nginx.conf` as the deployment fixture. The compose `api` container
mounts only `./api`, so running the suite there without the sibling marketing directory fails
with `FileNotFoundError`. Run the host checkout commands above, or mount the full checkout
with that relative layout preserved. The guard is required and is not skipped when its fixture
is missing.

Migrations are **hand-committed**; the `makemigrations --check` gate catches a model shipped without one. Every app needs a `migrations/` package for that gate to see it — Django silently excludes apps without one from autodetection.

### Native single-session cleanup (17tnw2b1wf2)

`POST /v1/sessions:revoke` requires an account bearer, `Content-Type: application/json` and `{}`; it never reads/sets cookies, accepts a body token or exposes an all-sessions option. It reuses account logout/auth/audit with `desktop_v1` provenance; an inactive token is401. The independent fixed `SELAHCUE_THROTTLE_SESSION_REVOKE` budget is10/minute/IP (a code setting, not an environment option). Simple content types and non-POST methods do not spend it;429 includes `Retry-After`/`no-store`. Device tokens, other account sessions and live output are unchanged. Native cleanup failure does not invalidate successful device activation; the client/handoff document exposes explicit retry and local secret-store outcomes. DEC-007 TTL and ADR-0029 Proposed status remain unchanged.
