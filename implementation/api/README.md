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
- **License refresh** `POST /v1/license:refresh` — device-token authed; reports status and rotates a still-live token after a valid licence extension (FR-509)
- **Signed offline entitlement** `GET /v1/entitlements/manifest` — see below

## Live-token renewal and response-loss recovery (FR-509)

`POST /v1/license:refresh` keeps the existing response fields. When a still-live device
credential expires before its currently valid licence, the response additionally contains
`activation_token`, using activation's existing show-once field name. `token.expires_at`
then names the replacement's expiry. The old token is REVOKED in the same transaction
as replacement issuance and its audit. Persist the new credential securely before the
next API call; do not log the response. Responses use `Cache-Control: no-store`.
Ordinary status reads return no `activation_token`. Expired/revoked tokens and revoked
devices return 401 and cannot renew themselves; blocked licences report their status
without minting credentials. Licence, device and token are rechecked under row locks.

If a response is lost before persistence, repeating the old device credential returns
401. An ADMIN must authenticate through the existing account session and explicitly
replace the known installation's token:

```http
POST /v1/activations:with-session
Authorization: Bearer <admin account session>
Content-Type: application/json

{"idempotency_key":"new-recovery-intent-001","device_fingerprint":"same-install-id","platform":"macos","replace_token":true}
```

Use the existing `device_fingerprint`, a fresh idempotency key and JSON boolean `true`.
Only a known ACTIVE device of the session's own org is eligible; licence validity and
plan allowance are checked under the licence lock. The response uses activation's normal
`activation_token`/`reminted` fields. Persist it through the same secret-store path as
activation. Replaying the recovery intent returns no raw credential and does not rotate
again. If that response is also lost, use a fresh explicit recovery intent. Defaults remain
show-once/idempotent; the enrollment-key route does not expose this option. The account
GraphQL twin accepts `replaceToken: true` with the same ADMIN gates. Neither path can
recover a revoked device or a blocked licence.

No shipped refresh client exists in the current desktop/mobile/marketing source: the
native licensing client implements sign-in, activation and manifest retrieval. The API
HTTP tests cover adopting the rotated token and the actual ADMIN recovery route; adding
a scheduled native refresh caller or recovery UI remains separate product work.

The cascade processes 500-token working sets until drained or its 240-second delivery
budget ends, then requests a continuation. The minute beat tick recovers remaining ACTIVE
rows after worker/broker interruption; their database status is the durable queue. Each
token/status audit transaction rechecks licence and token under locks. NFR-503's 65-minute
deadline still requires healthy worker/database capacity; this does not claim unlimited
fleet throughput or availability during a prolonged outage.

## Still stubbed (`501`)

`POST /v1/downloads:prepare`, `POST /v1/downloads/<lease_id>:complete`, `POST /v1/usage-events:batch`, and `/webhooks/billing/<provider>`.

The API does not yet issue download leases, serve licensed Bible text, sync billing providers, or store provider secrets. Header-derived actors remain a local/test bridge for **staff** only — customer identity now goes through real session auth, and `SELAHCUE_TRUST_ACTOR_HEADERS` must be false in production.

## `GET /v1/entitlements/manifest`

The signed offline entitlement (DEC-004). Device-token auth via `Authorization: Bearer <device_token>`. Returns an Ed25519 envelope:

```json
{ "envelope_version": 1, "alg": "Ed25519", "key_id": "a1b2c3d4",
  "payload": "<base64url>", "signature": "<base64url>" }
```

**Verify the signature over the `payload` string exactly as received, then decode it.** Do not re-serialize the decoded JSON and verify against that — the signature covers the transmitted bytes, which is what lets a Rust verifier agree without matching Python's JSON formatting. Check `alg` against an allow-list of exactly `Ed25519`; dispatching on a caller-supplied algorithm field is how confusion attacks work.

Issued **only** when the licence status is in `ACTIVATABLE_KEY_STATUSES` and the validity window is open — deliberately stricter than `license:refresh`, which reports status honestly even for a blocked licence, and rotates credentials only while commercial validity holds. This endpoint mints a credential cacheable to the licence expiry, and with no revocation list issuance is the only enforcement point.

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
