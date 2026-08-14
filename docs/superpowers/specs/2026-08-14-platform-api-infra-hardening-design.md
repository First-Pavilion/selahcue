# Platform API infrastructure + hardening (Docker · Redis · Celery · rate limiting · jobs) — design

- **Date:** 2026-08-14
- **Status:** Approved design (pending spec review) → next step: implementation plan
- **Slice:** 2 of 4 in the account + licensing continuation
- **ClickUp:** [86ajy62xz](https://app.clickup.com/t/86ajy62xz) (rate limiting) · [86ajyq86g](https://app.clickup.com/t/86ajyq86g) (review follow-ups) · epic [86ajy5v6k](https://app.clickup.com/t/86ajy5v6k)

## Goal

Give the Platform API the runtime it has never had — containers, Postgres, Redis, a Celery worker
and a Celery beat scheduler — then use it for the three things that were blocked on its absence:
rate limiting the `/v1` device-auth surface, delivering the transactional emails, and cascading
licence revocation to device tokens.

## The tickets are stale — verified 2026-08-14

[86ajyq86g](https://app.clickup.com/t/86ajyq86g) lists six findings. **Five are already fixed**;
later batches did the work without updating the ticket. Verified against current source:

| # | Finding | Actual state |
|---|---|---|
| 1 | Instance-limit race is a no-op on SQLite | **Partly done.** Config is env-driven (now `SQL_*`). Residual: no concurrency *test*, because there was no Postgres to run one against |
| 2 | `create_customer` idempotency not concurrency-safe | **Fixed** — `IntegrityError` savepoint, `accounts/services.py:125` |
| 3 | `generate_license_key` same race | **Fixed** — `license_keys/services.py:160` |
| 4 | `adminCustomers.totalCount` returns page size | **Fixed** — real `count_customers()`, `admin_schema.py` |
| 5 | PBKDF2 on every device request | **Fixed** — `hmac.compare_digest` on the fingerprint, `devices/services.py:390` |
| 6 | Staff identity from client headers | **Partly** — flag defaults false outside dev. Edge-stripping is an ops requirement, documented here, not code |

So this slice closes finding 1's residual and finding 6's documentation, and implements the rate
limiting that genuinely does not exist (`RATE_LIMITED` is defined but never raised).

## Decisions (settled)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Throttle store | **Redis**, via Django's cache framework |
| 2 | Async runtime | **Celery worker + beat**, both containerised |
| 3 | Env convention | **First Pavilion house keys** — already landed in `0bd8226` |
| 4 | Scope | Infra **+** rate limiting **+** all three job types |
| 5 | Compose shape | Mirror `yharah-logistics/docker-compose.yml` |

## Architecture

Compose services, mirroring the sibling project so the two stacks are operationally identical:

| Service | Image / build | Purpose |
|---|---|---|
| `api` | `./implementation/api` | Django, `runserver` in dev |
| `db` | `postgres:16-alpine` | Postgres — **the only backend where the DEC-004 instance limit is actually enforced** |
| `redis` | `redis:7-alpine` | Celery broker (db 2) + Django cache (db 1) |
| `celery-worker` | same image as `api` | `celery -A selahcue_api worker` |
| `celery-beat` | same image as `api` | `celery -A selahcue_api beat` |
| `mailhog` | `mailhog/mailhog` | Catches dev email on :1025, UI on :8025 |

Note `-A selahcue_api`, not `-A core` — yharah's Django package is `core`; ours is `selahcue_api`.

The existing `implementation/docker-compose.yml` holds only the marketing site; these services are
added alongside it.

## Components

### 1. Celery application

`selahcue_api/celery.py` with the standard `app.autodiscover_tasks()`, exported from
`selahcue_api/__init__.py` so `-A selahcue_api` resolves. Config from the settings already added
in `0bd8226`: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TIMEZONE`,
`CELERY_TASK_ACKS_LATE = True`, `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`.

`acks_late` + prefetch 1 is deliberate: these tasks are side-effecting (sending email, revoking
tokens). Losing one to a worker crash is worse than running one twice, and every task below is
written to be idempotent.

### 2. Redis cache

`CACHES` pointing at `redis://redis:6379/1` — a **different db from the broker** so a
`FLUSHDB` on either cannot destroy the other. Django 6.1 ships `django.core.cache.backends.redis`,
so no new dependency.

**Test and bare-`pytest` behaviour:** default to LocMemCache when `CACHE_URL` is unset, so the
suite and the CI job keep running without Redis. This is safe *only* because the limiter's
correctness tests inject a cache explicitly rather than relying on the default.

### 3. Rate limiting

A small `apps/throttling/` app: a pure `should_allow(key, limit, window, now, store)` function plus
a thin decorator for the `/v1` views.

- **Fixed window per (endpoint, client IP)** — not a token bucket. At church-scale request volume
  the extra precision buys nothing, and a fixed window is trivially correct to reason about and
  test.
- Redis `INCR` + `EXPIRE` on first increment. Atomic, no read-modify-write race.
- Over limit → raise `SafeAPIError(ErrorCode.RATE_LIMITED)`, which the shipped
  `command_error_response` map already turns into **429**.
- Limits: activation is the expensive one (`make_password` on the enrollment key), so it gets a
  tighter budget than the read-only refresh/manifest endpoints. Exact numbers in the plan.

**Client IP must come from a trusted source.** Behind a proxy, `REMOTE_ADDR` is the proxy and
`X-Forwarded-For` is caller-controlled — trusting the raw header lets anyone forge a fresh identity
per request and bypass the limit entirely. The resolver reads `X-Forwarded-For` **only** when
`SELAHCUE_TRUSTED_PROXY_COUNT > 0`, taking the Nth-from-last entry. Default 0 = use `REMOTE_ADDR`.

**Honest limitation:** this is defense-in-depth, not a brute-force fix. A device token is ~158 bits
behind an HMAC-keyed fingerprint index, so guessing never reaches a hash comparison. What this stops
is crude flooding and enumeration noise. Real per-IP flood protection belongs at the edge; §Ops
records that.

### 4. Email delivery (worker)

Replace the no-op `EmailSender` with a Celery-dispatched implementation rendering the three
templates from `docs/design/TRANSACTIONAL-EMAIL-spec.md` (Figma page `719:132`).

- HTML + plain-text alternative parts — both are specified in the design.
- **The task receives an opaque token, never a user object**: tasks are serialized onto Redis, and
  a broker with a queued message is not a place to leave credentials any longer than necessary.
- `send_account_exists` carries **no token and no link** — the design constraint is load-bearing,
  not cosmetic. A test asserts the rendered output contains no URL.
- Dispatch is `.delay()` from the service, but **failure to enqueue must not fail signup**. Signup
  succeeding and email being delayed is recoverable; signup 500ing because Redis blinked is not.

### 5. Revocation cascade (beat)

The R6 limitation recorded in the manifest spec: revoking a licence key does not reach already
issued device tokens. A periodic task revokes `DeviceToken` rows whose licence has left
`ACTIVATABLE_KEY_STATUSES`.

This **closes the loop** the manifest's issuance gate could only half-close: the gate stops
re-issue, this stops the existing token. Together they make revocation effective without a
revocation list.

- Idempotent — revoking an already-revoked token is a no-op.
- Bounded batch size per run; no unbounded query.
- Audited: every cascade writes `record_audit_event`, because silently killing a church's device
  mid-service with no trail is unacceptable.
- **NFR-024 is not violated**: revoking a token stops future API calls. It does not blank live
  output, and the desktop keeps its cached entitlement until expiry.

### 6. Expiry sweeps (beat)

Delete expired `CustomerSession` and `CredentialToken` rows. Pure hygiene — expiry is already
enforced at read time, so this only stops unbounded table growth. Bounded batches.

## Error handling

| Condition | Behaviour |
|---|---|
| Redis down, rate limiting | **Fail open.** Availability beats defense-in-depth for a non-live hole; log loudly |
| Redis down, task dispatch | Signup/reset still succeed; the email is lost and logged. Explicitly not retried into a queue that is down |
| Task raises | `acks_late` returns it to the queue; idempotency makes redelivery safe |
| Beat task partially fails | Bounded batch, next run picks up the remainder |

Fail-open on the limiter is a real trade-off, stated rather than hidden: a Redis outage removes
throttling. Given brute force is already infeasible, refusing all device traffic would cause the
outage rather than prevent one.

## Testing

- `should_allow` is pure and injected — window boundaries, exact-limit, over-limit, and key
  isolation tested with no Redis and no clock dependency.
- IP resolution: spoofed `X-Forwarded-For` is **ignored** when the trusted-proxy count is 0. This is
  the test that matters; without it the limiter is bypassable by header.
- 429 shape asserted through the real view, including the `RATE_LIMITED` code.
- Email tasks: rendered HTML and text parts assert the spec's copy; account-exists asserts **no URL
  present**; token passed as opaque string.
- Cascade: revoked licence → token revoked, audited, idempotent on re-run.
- **Postgres concurrency test** (finding 1's residual): two concurrent activations against a real
  Postgres must not exceed `device_limit`. Runs only when `SQL_ENGINE` is Postgres, skipped
  otherwise, so bare `pytest` stays green — and the CI job gains a Postgres service container so it
  actually executes there.

## Ops requirements (documented, not code)

Finding 6, and the edge half of rate limiting:

- Strip inbound `X-SelahCue-*` headers at the ingress before any production use of
  `SELAHCUE_TRUST_ACTOR_HEADERS`.
- Per-IP flood protection at the edge (Coolify/Cloudflare) — the app limiter is the second layer.
- Redis must not be publicly reachable; it holds queued tasks and cache entries.

## Risks

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Rate limiter bypassable via forged `X-Forwarded-For` | Trusted-proxy count gate, defaulting to `REMOTE_ADDR`; explicit spoofing test |
| R2 | Fail-open means a Redis outage silently removes throttling | Accepted and documented; loud log; edge is the real protection |
| R3 | Cascade revokes a device mid-service | Only fires when the licence has genuinely left an activatable status; audited; never blanks live output (NFR-024) |
| R4 | Celery adds two processes that can fail silently | Flower is **out of scope**; instead beat/worker liveness is a documented ops check. Revisit if it bites |
| R5 | Postgres concurrency test is environment-dependent | Skipped unless `SQL_ENGINE` is Postgres; CI adds a service container so it is not skipped where it counts |
| R6 | Compose sprawl — six services for a desktop-first product | They are dev/deploy-time only. The desktop app remains fully offline-first and never talks to this stack to present |

## Out of scope

- Flower (task monitoring UI) — yharah has it; add later if worker opacity becomes a problem.
- Email provider credentials, sending domain, SPF/DKIM/DMARC — owner.
- The `{verify_url}` / `{reset_url}` web routes — no such route exists yet; the emails link to a
  destination that must be built alongside slice 4.
- Usage-events and downloads endpoints — slice 3.
- Kubernetes, autoscaling, multi-region.
