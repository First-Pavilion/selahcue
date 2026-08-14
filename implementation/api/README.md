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
- **License refresh** `POST /v1/license:refresh` — device-token authed, pure read
- **Signed offline entitlement** `GET /v1/entitlements/manifest` — see below

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

Mirrors the `api` job in `.github/workflows/ci.yml`. From this directory:

```bash
/private/tmp/selahcue-api-venv/bin/python manage.py check
/private/tmp/selahcue-api-venv/bin/python manage.py makemigrations --check --noinput
/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q
```

Migrations are **hand-committed**; the `makemigrations --check` gate catches a model shipped without one. Every app needs a `migrations/` package for that gate to see it — Django silently excludes apps without one from autodetection.
