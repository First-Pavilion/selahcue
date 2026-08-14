# Signed offline entitlement manifest (`GET /v1/entitlements/manifest`) + API CI job — design

- **Date:** 2026-08-13
- **Status:** Approved design (pending spec review) → next step: implementation plan
- **Slice:** 1 of 4 in the account + licensing continuation (see §Sequence)
- **Implements:** DEC-004 (activation-cached offline entitlement), DEC-005 (offline entitlement = full licence window)
- **Epic:** [86ajy5v6k](https://app.clickup.com/t/86ajy5v6k)

## Goal

Replace the `501` stub at `GET /v1/entitlements/manifest` with the **signed, time-boxed,
device-bound entitlement** that DEC-004 is built around — the artefact a desktop install caches at
activation and then verifies locally, so it runs fully offline without trusting the machine it sits
on.

Ship an **API CI job** alongside it, because this slice introduces cryptographic code that must
never regress silently, and the Platform API currently has no automated verification at all.

## Sequence (this slice in context)

The owner asked for all four remaining account/licensing slices. They are dependency-ordered, each
with its own spec → plan → implementation cycle:

1. **Entitlement manifest** ← *this spec*. Everything downstream reads from it.
2. **Hardening** — rate-limiting on `/v1` device auth (86ajy62xz) + the idempotency-concurrency and
   backend-independent instance-limit follow-up (86ajyq86g).
3. **Usage events + downloads** — the remaining `/v1` stubs.
4. **Desktop sign-in UI** — consumes the whole loop: sign in → activate → cache + verify entitlement.

Building 4 before 1 would mean building it twice, which is why the UI is last despite being the most
visible.

## Decisions (settled)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Signing suite | **Ed25519 asymmetric.** Desktop embeds only the public key |
| 2 | Signed bytes | **The base64url payload string as received** — not a re-serialization |
| 3 | Persistence | **None.** Manifest derived per request; issuance audited |
| 4 | Entitlement expiry | **= licence expiry** (DEC-005; no separate grace timer) |
| 5 | Device binding | `device_public_id` + `device_fingerprint` in the payload |
| 6 | Missing signing key | **Fail loudly.** Never serve unsigned, never fall back to a dev key |
| 7 | CI | **New `api` job in `ci.yml`**, added in this slice rather than deferred |
| 8 | Issuance gate | **Allow-list** on `ACTIVATABLE_KEY_STATUSES`, not a deny-list — see §Issuance gate |
| 9 | `license_status` | The raw `LicenseKeyStatus` value **verbatim**, as the shipped endpoints already emit |

## Why sign the encoded bytes

The signature covers the **base64url payload string exactly as transmitted**, and the client
verifies that string before decoding it.

The alternative — signing a canonical JSON serialization — requires Python and Rust to agree, byte
for byte, on key ordering, separator whitespace, unicode escaping, and float and timestamp
formatting. Every one of those is a place where a signature silently fails to verify, or worse,
where two different documents produce the same signed bytes. Signing the transmitted encoding
removes the entire class of problem: there is exactly one byte string, and both sides see it.

The cost is that the payload is not human-readable in transit. That is acceptable — it is a machine
artefact, and `license:refresh` already serves the same data in plain JSON for humans and for
debugging.

## Envelope

```json
{
  "envelope_version": 1,
  "alg": "Ed25519",
  "key_id": "a1b2c3d4",
  "payload": "<base64url(JSON)>",
  "signature": "<base64url(Ed25519 signature over the payload string bytes)>"
}
```

`envelope_version` is present so a future format change is a version bump rather than a guess.
`alg` is explicit and **must be checked by the verifier** — a client that reads `alg` and dispatches
without an allow-list is how algorithm-confusion attacks work. The client accepts `Ed25519` and
nothing else.

### Payload

| Field | Source | Purpose |
|-------|--------|---------|
| `entitlement_version` | constant | Payload schema version |
| `device_public_id` | `Device` | Binding + client self-check |
| `device_fingerprint` | `Device` | Binding — stops a cached manifest being copied to another install |
| `customer_org_id` | `Device.customer` | Tenant attribution |
| `license_status` | `AppLicenseKey` | The `LicenseKeyStatus` value **verbatim** — ISSUED / ACTIVATED / EXPIRING / EXPIRED / SUSPENDED / REVOKED / CONVERTED / ARCHIVED. Same pass-through the shipped `/v1/activations` and `/v1/license:refresh` already do. There is **no** `ACTIVE` member; only ISSUED, ACTIVATED and EXPIRING can reach a signed manifest (§Issuance gate) |
| `license_valid_now` | derived | Computed exactly as `refresh_license` does — status in `ACTIVATABLE_KEY_STATUSES` **and** inside the window. Saves the client re-deriving policy from raw status |
| `license_starts_at`, `license_expires_at` | `AppLicenseKey` | The validity window |
| `feature_scope` | `AppLicenseKey` | Existing `CharField`; unchanged by this slice |
| `territory` | `AppLicenseKey` | Existing `CharField` |
| `instances_used`, `instances_limit` | derived / `device_limit` | Plan usage at issue time |
| `issued_at` | now | Freshness |
| `not_before` | `license_starts_at` | Explicit lower bound |
| `expires_at` | `license_expires_at` | DEC-005 — **equals** the licence window |

## Architecture

Three layers, each ignorant of the ones around it — mirroring how the `license_keys` and `devices`
slices are already built:

- **`apps/entitlements/signing.py`** — bytes in, envelope out. Loads the key, derives `key_id`,
  signs. Knows nothing about licensing, devices, or HTTP. The key is injectable so tests never
  depend on process environment.
- **`apps/entitlements/services.py`** — frozen-dataclass `Data`/`Result`. Calls the **shipped
  `apps/devices/services.authenticate_device_token` unchanged** (the same helper `refresh_license`
  uses — device-token auth is not re-implemented here), applies the §Issuance gate, assembles the
  payload, runs `assert_no_restricted_payload_fields` on the payload **mapping**, then calls
  `signing` and records the audit event. Knows nothing about HTTP.
- **`platform/views.py`** — auth extraction, error mapping, `JsonResponse`. Knows nothing about
  crypto.

No new models. The manifest is a projection of `Device` + `AppLicenseKey`; storing it would add a
staleness problem and buy nothing until a revocation list exists.

## Key management

- Private key from **`SELAHCUE_ENTITLEMENT_SIGNING_KEY`** — base64 of a 32-byte Ed25519 seed.
- **`key_id` = first 8 hex characters of SHA-256 over the public key bytes.** Derived, not
  configured, so it cannot drift out of sync with the key it names and no registry is needed.
- **Rotation:** the client trusts a *set* of public keys and selects by `key_id`. Ship the new public
  key in a desktop release, wait for adoption, then switch the server. Old manifests keep verifying
  throughout. The server signs with one key at a time — no dual-signing.
- **No default.** `DJANGO_SECRET_KEY` ships an insecure dev default; a signing key must not. Absent
  or malformed key → the endpoint fails loudly and logs it. Serving an unsigned manifest, or one
  signed by a well-known dev key, would silently void the entire offline model.

## Issuance gate

A manifest is signed **only** when all three hold:

1. `license_key.status in ACTIVATABLE_KEY_STATUSES` — the shipped frozenset `{ISSUED, ACTIVATED,
   EXPIRING}` at `apps/devices/services.py:38-40`. An **allow-list**, so a status added to the enum
   later denies by default instead of silently qualifying.
2. `license_key.starts_at <= now < license_key.expires_at`.
3. Device authentication succeeds (which already requires `device.status == ACTIVE`).

**Why this diverges from `/v1/license:refresh`, deliberately.** The sibling endpoint reports
honestly rather than denying — an administratively SUSPENDED key with an open window still returns
`200` with its true status, so the client can react. That is right for refresh, which *reads*.
It is wrong here, because this endpoint **mints a signed, device-bound credential cacheable until
the licence expiry**, and with no revocation list (out of scope) **issuance is the only enforcement
point that exists**. Revoking a licence key does not cascade to `DeviceToken` rows, and
`authenticate_device_token` never consults licence status — so without this gate, a device under a
REVOKED licence would authenticate fine and be handed a freshly signed multi-year entitlement.
The signed artefact must never be laxer than the unsigned one. Do not "harmonise" these two
endpoints back together.

## Error handling

| Condition | Code | Note |
|-----------|------|------|
| No / malformed / unknown / expired / revoked device token, **or non-ACTIVE device** | `UNAUTHENTICATED` | Delegated wholesale to the shipped `authenticate_device_token`, which maps all of these — including device status — to one code with no oracle. `DeviceStatus` has only ACTIVE and REVOKED; there is no suspended state |
| Licence status outside `ACTIVATABLE_KEY_STATUSES`, or outside its validity window | `POLICY_DENIED` | The only denial this endpoint owns itself |
| Signing key absent or malformed | `500` + loud log | **Not** `NOT_IMPLEMENTED` — that would read as "by design" |

Never-blank (NFR-024) is a **client-side** guarantee and is unaffected here: a failed manifest fetch
means the desktop keeps its previously cached entitlement and carries on. The server's job is to be
honest, not to be lenient.

## Testing

Deterministic fixed seed so signatures are byte-reproducible across runs.

**The test that proves the design:** flip one byte of the payload, assert verification fails. Without
it, every other test would still pass against a no-op signer.

Also covered:
- Signature verifies against the public key; `key_id` matches the derived value.
- **Wrong-key rejection** — a signature from a different key fails.
- Device binding: the manifest names the requesting device and no other.
- `expires_at` equals the licence `expires_at` exactly (DEC-005 — guards against a grace timer being
  reintroduced by accident).
- **Licence status parametrised over every `LicenseKeyStatus` member**, driven off
  `LicenseKeyStatus.choices` so that adding a ninth status fails the suite rather than defaulting
  open. ISSUED / ACTIVATED / EXPIRING → signed envelope; the other five → `POLICY_DENIED`. The
  REVOKED case is built the reachable way — activate normally, then flip the key to REVOKED leaving
  `expires_at` in the future so the device token stays live (the shape already used in
  `tests/test_license_refresh_slice.py`).
- Window edges: not-yet-started (`now < starts_at`) and past-expiry both deny.
- `license_status` passes through **verbatim** — pins against a normalisation mapping being
  introduced later.
- All device-token failure modes return `UNAUTHENTICATED` and are indistinguishable, including a
  REVOKED device.
- Missing signing key fails loudly and does not emit an envelope.
- **Redaction, at the layer where it can actually see anything:**
  `assert_no_restricted_payload_fields` runs on the payload **mapping inside the service, before
  base64url encoding**. Run against the envelope it would be theatre — it matches key names over
  Mappings and Sequences, and the payload is by then an opaque string it walks straight past.
  A second assertion on the envelope guards only the envelope's own fields.
- Audit event recorded on issuance, with redaction intact.

## CI job

Today `implementation/api` matches **no** path filter in `ci.yml` — not `desktop`, not `mobile`. An
API-only push triggers the workflow, runs `detect changed areas`, and then runs nothing. The
filter's own comment states a code area must "never be silently unverified", so this is a gap
against its stated intent, not merely an absent feature.

Add:

- An `api` filter matching `implementation/api/**` and `.github/workflows/ci.yml`.
- An `api` job on `ubuntu-latest`, `needs: changes`, gated on that filter, pinned to **Python 3.12**:
  - `pip install -e ".[dev]"`
  - `manage.py check`
  - `manage.py makemigrations --check --noinput` — see the migration-blindness fix below
  - `pytest tests -q`

### The migration gate is blind by default — fix it first

`makemigrations --check` with no app labels **skips every app that has no `migrations/` package**;
Django treats those as `real_apps` and excludes them from autodetection. Four apps are in that
state today — `billing`, `catalogue`, `downloads`, and **`entitlements`, the very app this slice
creates**. So the gate would have been silently useless exactly where it was needed, which is worse
than not having it: a green check that proves nothing.

Commit an empty `migrations/__init__.py` under each of those four apps as part of this slice.

Two flag corrections while we're here: `--dry-run` has been implied by `--check` since Django 4.2,
so it is noise; and `--noinput` is load-bearing, because without it a **field rename** selects the
interactive questioner, which calls `input()` and dies on a TTY-less runner with an `EOFError`
traceback instead of a readable "migration missing" failure.

### No aggregate gate exists — say so rather than gesture at one

This repo has **no branch protection and no aggregator job**; `ci.yml`'s jobs are `changes`, `rust`,
`launch-smoke`, `operator`, `flutter`, `audit`, `supply-chain`. So there is no required-check set to
add `api` to, and a path-filtered job that is skipped reports neutral, not failed. Introducing an
aggregator is tracked separately under 86ajq0569 and is **not** in this slice — noted here so the
gap is recorded rather than assumed closed.

### Interpreter version

**Resolved differently at implementation time (owner decision, 2026-08-14).** The spec proposed
pinning CI to 3.12 to match Django 5.2's supported range. The owner chose instead to **keep Python
3.14 and upgrade Django to the latest stable**, which is the better resolution: Django 6.1 supports
3.12–3.14, so 3.14 becomes officially supported rather than merely tolerated, and local and CI run
the same interpreter with no downgrade.

Shipped as `bd5c469`: Django `>=6.1,<6.2`, `strawberry-graphql-django >=0.87,<0.88` (0.87 declares
`django>=5.2` with no upper bound), `requires-python >=3.12`. Verified: 63/63 pre-existing tests
pass under Django 6.1 with no deprecation breakage.

**Deliberately still on SQLite.** A Postgres service container is the right home for the
`select_for_update` concurrency test, but that test is slice 2's work; adding the container now
would be infrastructure with nothing using it.

**`make ci` is not extended.** It is the desktop/mobile gate and already takes minutes; the API's
verification stays the documented three commands in `implementation/api/README.md`. Revisit if the
two ever need to be run together.

## Risks

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Signature verification is only exercised in Python until slice 4 writes the Rust verifier — a cross-language mismatch would surface late | Sign the transmitted encoding (§Why), which is what makes the two sides agree by construction. Slice 4 adds a fixture pinned across both, mirroring how the LAN wire protocol is already cross-language contract-tested |
| R2 | `cryptography` is a new dependency with a binary wheel | Standard, widely deployed, actively maintained. Pinned in `pyproject.toml`; the CI job proves it installs cleanly |
| R3 | Client clock skew could reject a valid manifest | Tolerance is a slice-4 client concern; documented there. The server always stamps `issued_at` from its own clock |
| R4 | A leaked private key mints unlimited entitlements | Key lives only in the deployment environment, never in git. Rotation path is defined above; `DEPLOYMENT.md` gets the runbook |
| R5 | `feature_scope` is a flat `CharField`, so entitlements cannot express per-feature grants | Accepted for this slice. Structured plans are a `catalogue` concern and would expand scope well past a manifest |
| R6 | Revoking a licence key does not cascade to `DeviceToken`, so an already-issued manifest survives revocation until licence expiry | Inherent to DEC-005 + no revocation list. The §Issuance gate closes the re-issue path, which is the only lever this slice has. A revocation list remains the honest fix and stays out of scope — recorded so it is a known limit, not a surprise |

## Implementation outcome (2026-08-14) — VERIFIED

Shipped in five commits on `main`: `bd5c469` (Django 6.1), `ac68c11` (CI job + migration gate),
`cc364ae` (signing), `6cf9939` (service), `abaeb6b` (endpoint).

**Final state: 104/104 tests pass** (63 pre-existing + 41 new), `manage.py check` clean,
`makemigrations --check` clean, `compileall` clean.

Two things the implementation established that the spec had only asserted:

- **The migration-gate fix was verified empirically, not assumed.** With a probe model present in
  `entitlements`, the unscoped gate now exits 1 (`Create model GateProbe`) where before it reported
  "No changes detected". The probe was then removed. Note the app's Django label is
  `selahcue_entitlements`, not `entitlements` — a first attempt to target it by directory name
  returned "No installed app with label", which is a trap for anyone scoping the gate per-app.
- **The licence-status test genuinely expands to all eight members**, confirmed by name in verbose
  output: REVOKED, CONVERTED and ARCHIVED each carry their own `POLICY_DENIED` assertion. That is
  the hole the review found, now closed by an executing test rather than by prose.

One defect surfaced during implementation, in the *tests* rather than the design: activation flips
the licence key `ISSUED → ACTIVATED`, so the in-memory `AppLicenseKey` returned at creation is stale
by the time a manifest is issued. Fixed with `refresh_from_db()` in the fixture — the assertion was
right and the fixture was wrong, so the assertion stood.

## Review

This spec was put through adversarial multi-lens review (crypto, codebase-conventions, CI, internal
consistency): **52 findings raised, 42 refuted, 10 confirmed and fixed above.** The substantive ones
were a deny-list issuance gate that would have signed multi-year entitlements for REVOKED licences,
a `license_status` enum that did not exist in the model, a `POLICY_DENIED` branch for a device state
that does not exist, and a migration gate blind to the very app this slice creates. Each was
verified against the source before being accepted.

## Documentation

- `DEPLOYMENT.md` — `SELAHCUE_ENTITLEMENT_SIGNING_KEY`: how to generate it, how to store it, and the
  rotation runbook.
- `implementation/api/README.md` — the endpoint and its verification commands.
- ClickUp: correct the epic (see below).

## ClickUp correction (housekeeping, independent of this slice)

The epic still carries the superseded Logto/OIDC design. To be done regardless:

- Close as superseded: `86ajy7aa3` (self-host Logto — currently sitting in **code review** for work
  that must not happen), `86ajy7add` (OIDC relying party), `86ajy7ak8` (desktop PKCE client),
  `86ajy7aqw` (OIDC security review). Reference DEC-007 / ADR-0023.
- `86ajy7ag8` (account-based activation) → shipped as `activateDeviceWithSession` in `d1843ea`;
  move out of `planning/todo`.
- `86ajy7anx` (account-setup UI) → re-point from OIDC onto DEC-007 email/password; this is slice 4.
- New task for this slice under the epic.

## Out of scope

- Desktop-side verification, caching, and clock tolerance (slice 4).
- Revocation lists and a public-key publication endpoint.
- `catalogue` plan/tier modelling; `feature_scope` stays as-is.
- Postgres in CI (slice 2).
- Any change to the shipped `/v1/activations` or `/v1/license:refresh` behaviour.
