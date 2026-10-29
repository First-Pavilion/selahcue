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
- **Native-client account sign-in** `POST /v1/sessions` (email + password → session token) and `POST /v1/activations:with-session` (`Authorization: Bearer <session token>` → device token). These are what the desktop calls (`selahcue-licensing`, ClickUp 17tnw2b1we2); it never calls `/graphql/account`, which authenticates from a session cookie, so it keeps CSRF enforced and a cookie-less native client cannot use it. The two routes are `csrf_exempt` because they read the session from the `Authorization` header only and never set a cookie. Wire contract: `docs/design/ACCOUNT-AUTH-API-HANDOFF.md`; decision and safety argument: ADR-0029 (86ak5t1gw).
- **License refresh** `POST /v1/license:refresh` — device-token authed, pure read
- **Signed offline entitlement** `GET /v1/entitlements/manifest` — see below

## Still stubbed (`501`)

`POST /v1/downloads:prepare`, `POST /v1/downloads/<lease_id>:complete`, `POST /v1/usage-events:batch`, and `/webhooks/billing/<provider>`.

The API does not yet issue download leases, serve licensed Bible text, sync billing providers, or store provider secrets. Header-derived actors remain a local/test bridge for **staff** only — customer identity now goes through real session auth, and `SELAHCUE_TRUST_ACTOR_HEADERS` must be false in production.

## Activation input

Both native activation routes and account GraphQL activation validate device metadata before writing a device or token. Fields must be strings; control characters and invalid Unicode are refused. `platform` is one of `macos`, `windows`, or `linux`, matching the desktop licensing client. Fingerprints and display names are at most128 characters, app versions at most32; optional version/name fields may be omitted or empty. Native routes return JSON400 `VALIDATION_FAILED` for malformed, excessively nested or oversized JSON bodies, using Django's existing body-size limit. No field is converted from an array, object, boolean or number into text.

Enrollment activation requires `Content-Type: application/json` before any throttle budget or database work. A browser-simple non-JSON request receives400 `VALIDATION_FAILED` without spending the shared-egress budget. License refresh applies the same rule to its JSON body-token fallback. Its existing `Authorization: Bearer` form remains usable without a JSON body or Content-Type; the existing token authentication and header-over-body precedence still apply. GET manifest requests are unchanged (17tnw2b1wqb).

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
make api-install   # once per checkout, and after pyproject.toml changes: builds the venv, needs the network
make api-check     # django check + migrations committed + pytest, the same three commands as the CI `api` job
```

`make ci` runs `make api-check`; it never installs, so on a fresh worktree it stops with an instruction to run `make api-install`. `api-install` needs Python 3.14 on PATH (CI's version) or `API_PYTHON=/path/to/python` for any 3.12 or newer.

- The venv is `implementation/api/.venv-api-check`, a name only these targets use (your own `.venv` is never touched), gitignored and per checkout. `api-check` refuses it when it is a symlink, was built with another Python minor version (a patch update is fine) or from another checkout, or `pyproject.toml` changed since (content hash, so a `touch` is fine). If you built it with an interpreter other than the default `python3.14`, keep `API_PYTHON` exported for `make api-check` as well. An interrupted or failed `make api-install` can simply be run again.
- It runs on SQLite in memory, so the tests that need Postgres or Redis (`tests/test_concurrency_postgres.py`, one test in `tests/test_cache_socket_timeouts.py`) **skip locally**; only CI runs them.
- The install is not locked: direct dependencies and the build backend (`[build-system]`) are pinned exactly, transitive dependencies are not locked or hashed, so the venv holds whatever resolved when you ran `make api-install` while CI re-resolves each run (ClickUp 17tnw2az0kw).

By hand, from this directory, with a venv that has `pip install -e ".[dev]"` run in this checkout:

```bash
.venv-api-check/bin/python manage.py check
.venv-api-check/bin/python manage.py makemigrations --check --noinput
.venv-api-check/bin/python -m pytest tests -q
```

Migrations are **hand-committed**; the `makemigrations --check` gate catches a model shipped without one. Every app needs a `migrations/` package for that gate to see it — Django silently excludes apps without one from autodetection.
