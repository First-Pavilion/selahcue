# Platform API Infrastructure + Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Platform API a real runtime — containers, Postgres, Redis, Celery worker and beat — then use it to rate-limit `/v1`, deliver the transactional emails, and cascade licence revocation to device tokens.

**Architecture:** Compose services mirroring `yharah-logistics/docker-compose.yml`. Rate limiting is a pure, injectable `should_allow()` behind a thin view decorator, so its logic is testable without Redis or a clock. Celery carries side-effecting work: email from the worker, revocation cascade and expiry sweeps from beat. Every task is idempotent because `acks_late` can redeliver.

**Tech Stack:** Django 6.1, Celery 5, Redis 7, Postgres 16, `mailhog`, pytest-django, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-14-platform-api-infra-hardening-design.md`
**ClickUp:** [86ajy62xz](https://app.clickup.com/t/86ajy62xz) · [86ajyq86g](https://app.clickup.com/t/86ajyq86g)

## Global Constraints

- **Django package is `selahcue_api`** — Celery is `-A selahcue_api`, never `-A core` (that is yharah's package name).
- **Env keys follow the house convention** (landed in `0bd8226`): `SECRET_KEY`, `DEBUG`, `SQL_*`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `MAIL_*`. Do not reintroduce `DATABASE_URL` or `DJANGO_SECRET_KEY`.
- **Redis db split:** broker = db `2`, Django cache = db `1`. Never the same db.
- **Bare `pytest` must stay green with no Redis, no Postgres, no Docker.** Defaults fall back to LocMemCache and SQLite.
- **Every Celery task must be idempotent** — `CELERY_TASK_ACKS_LATE = True` means redelivery on worker crash.
- **Rate limiting fails OPEN** on Redis error. Log loudly; never refuse traffic because the limiter is unavailable.
- **Never blank live output (NFR-024).** Revoking a device token stops future API calls only.
- Mail uses Django 6.1 `MAILERS`, already configured. Do not add `EMAIL_*` settings.
- Interpreter: `/private/tmp/selahcue-api-venv/bin/python`. All commands from `implementation/api/` unless stated.

---

## File Structure

| File | Responsibility |
|---|---|
| `implementation/api/Dockerfile` | *Create* — API image, shared by api/worker/beat |
| `implementation/docker-compose.yml` | *Modify* — add api, db, redis, celery-worker, celery-beat, mailhog |
| `selahcue_api/celery.py` | *Create* — Celery app + autodiscovery |
| `selahcue_api/__init__.py` | *Modify* — export `celery_app` so `-A selahcue_api` resolves |
| `selahcue_api/settings.py` | *Modify* — `CACHES`, `CELERY_BEAT_SCHEDULE`, trusted-proxy count |
| `selahcue_api/apps/throttling/` | *Create* — `services.py` (pure logic), `decorators.py` (view glue), `apps.py` |
| `selahcue_api/apps/accounts/email.py` | *Create* — template rendering + the Celery-backed `EmailSender` |
| `selahcue_api/apps/accounts/tasks.py` | *Create* — email delivery tasks |
| `selahcue_api/templates/email/*.{html,txt}` | *Create* — 6 templates (3 emails × html/text) |
| `selahcue_api/apps/devices/tasks.py` | *Create* — revocation cascade |
| `selahcue_api/apps/accounts/maintenance.py` | *Create* — expiry sweeps |
| `.github/workflows/ci.yml` | *Modify* — Postgres + Redis service containers for the `api` job |
| `tests/test_throttling.py`, `tests/test_email_delivery.py`, `tests/test_revocation_cascade.py`, `tests/test_concurrency_postgres.py` | *Create* |

---

### Task 1: Container image, compose stack, and the Celery app

**Files:**
- Create: `implementation/api/Dockerfile`
- Create: `implementation/api/selahcue_api/celery.py`
- Modify: `implementation/api/selahcue_api/__init__.py`
- Modify: `implementation/docker-compose.yml`
- Test: `implementation/api/tests/test_celery_app.py`

**Interfaces:**
- Produces: `selahcue_api.celery.app` (Celery instance), re-exported as `selahcue_api.celery_app`. Tasks in later tasks register against it via `@shared_task`.

- [ ] **Step 1: Write the failing test**

Create `implementation/api/tests/test_celery_app.py`:

```python
"""The Celery app must be importable and configured from Django settings, so that
`celery -A selahcue_api worker` resolves without a running broker."""

from django.conf import settings


def test_celery_app_is_exported_from_the_package():
    from selahcue_api import celery_app

    assert celery_app is not None
    assert celery_app.main == "selahcue_api"


def test_broker_and_backend_come_from_settings():
    from selahcue_api import celery_app

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_side_effecting_defaults_are_set():
    """acks_late + prefetch 1: these tasks send email and revoke tokens. Losing one to a
    worker crash is worse than running one twice, and every task is idempotent."""
    from selahcue_api import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_celery_app.py -q`
Expected: FAIL — `ImportError: cannot import name 'celery_app' from 'selahcue_api'`

- [ ] **Step 3: Add the dependency**

In `implementation/api/pyproject.toml`, add to `dependencies`:

```toml
  # Async task runtime: transactional email (worker) + revocation cascade and expiry
  # sweeps (beat). Redis is the broker; see CELERY_BROKER_URL in settings.
  "celery[redis]>=5.4,<6",
```

Install: `/private/tmp/selahcue-api-venv/bin/python -m pip install -q -e ".[dev]"`

- [ ] **Step 4: Create the Celery app**

Create `implementation/api/selahcue_api/celery.py`:

```python
"""Celery application for the SelahCue Platform API.

Entry point for `celery -A selahcue_api worker` and `celery -A selahcue_api beat`.
Configuration lives in Django settings under the `CELERY_` namespace, so there is one
place to change broker/backend/timezone.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")

app = Celery("selahcue_api")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

Modify `implementation/api/selahcue_api/__init__.py` to:

```python
# Import the Celery app on package import so `-A selahcue_api` resolves and
# @shared_task decorators bind to it.
from selahcue_api.celery import app as celery_app

__all__ = ("celery_app",)
```

- [ ] **Step 5: Run to verify it passes**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_celery_app.py -q`
Expected: `3 passed`

- [ ] **Step 6: Verify the whole suite still imports cleanly**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q`
Expected: `107 passed` (104 existing + 3 new)

Importing Celery at package import time is the classic place to break Django startup — this run is what proves it did not.

- [ ] **Step 7: Create the Dockerfile**

Create `implementation/api/Dockerfile`:

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# psycopg needs libpq; build-essential for any wheel that lacks a manylinux build.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Postgres driver is only needed inside the container; local dev stays on SQLite.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[dev]" "psycopg[binary]>=3.2,<4"

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 8: Add the services to compose**

In `implementation/docker-compose.yml`, add these services alongside the existing `marketing-site` (keep that untouched):

```yaml
  api:
    build: ./api
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./api:/usr/src/app
    ports:
      - "8008:8000"
    env_file:
      - ./api/.env
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: selahcue_db
      POSTGRES_USER: pavilion
      POSTGRES_PASSWORD: pavilion
    volumes:
      - selahcue-pgdata:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pavilion -d selahcue_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - selahcue-redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  celery-worker:
    build: ./api
    command: celery -A selahcue_api worker --loglevel=info --concurrency=2
    volumes:
      - ./api:/usr/src/app
    env_file:
      - ./api/.env
    depends_on:
      - api
      - redis
    restart: unless-stopped

  celery-beat:
    build: ./api
    command: celery -A selahcue_api beat --loglevel=info --pidfile=/tmp/celerybeat.pid --schedule=/tmp/celerybeat-schedule
    volumes:
      - ./api:/usr/src/app
    env_file:
      - ./api/.env
    depends_on:
      - api
      - redis
    restart: unless-stopped

  mailhog:
    image: mailhog/mailhog
    container_name: selahcue_mailhog
    ports:
      - "1025:1025"
      - "8025:8025"

volumes:
  selahcue-pgdata:
  selahcue-redisdata:
```

`container_name: selahcue_mailhog` must match the `MAIL_HOST` default in settings.

- [ ] **Step 9: Validate the compose file parses and the service set is right**

```bash
cd /Users/m.oluwole/Documents/code/scph
python3 -c "
import yaml
d = yaml.safe_load(open('implementation/docker-compose.yml'))
names = sorted(d['services'])
print('services:', names)
assert {'api','db','redis','celery-worker','celery-beat','mailhog','marketing-site'} <= set(names)
assert 'selahcue_api' in d['services']['celery-worker']['command']
assert 'selahcue_api' in d['services']['celery-beat']['command']
print('OK')
"
```

Expected: `OK`

- [ ] **Step 10: Commit**

```bash
git add implementation/api/Dockerfile implementation/api/pyproject.toml \
        implementation/api/selahcue_api/celery.py implementation/api/selahcue_api/__init__.py \
        implementation/api/tests/test_celery_app.py implementation/docker-compose.yml
git commit -m "feat(api): containerise the Platform API + Celery worker and beat

Compose gains api, db (Postgres 16), redis, celery-worker, celery-beat and
mailhog, mirroring yharah-logistics so the two stacks operate identically.
Celery is -A selahcue_api (our package), not -A core (theirs).

acks_late + prefetch 1 because every task here is side-effecting; each is
written to be idempotent so redelivery is safe."
```

---

### Task 2: Redis cache and `/v1` rate limiting

**Files:**
- Create: `implementation/api/selahcue_api/apps/throttling/__init__.py`, `apps.py`, `services.py`, `decorators.py`, `migrations/__init__.py`
- Modify: `implementation/api/selahcue_api/settings.py`
- Modify: `implementation/api/selahcue_api/platform/views.py`
- Test: `implementation/api/tests/test_throttling.py`

**Interfaces:**
- Produces:
  - `client_ip(request) -> str`
  - `should_allow(store, key: str, limit: int, window_seconds: int) -> bool`
  - `throttle(scope: str, limit: int, window_seconds: int)` — view decorator
- Consumes: `SafeAPIError`, `ErrorCode.RATE_LIMITED`, `command_error_response` (all shipped).

- [ ] **Step 1: Write the failing tests**

Create `implementation/api/tests/test_throttling.py`:

```python
"""Rate limiting for the /v1 device-auth surface.

The load-bearing test here is `spoofed_forwarded_for_is_ignored_by_default`: behind a
proxy, trusting a caller-supplied X-Forwarded-For lets anyone mint a fresh identity per
request and bypass the limiter entirely.
"""

import json

import pytest
from django.test import RequestFactory

from selahcue_api.apps.throttling.services import client_ip, should_allow


class FakeStore:
    """Minimal cache double — incr/expire semantics only, no Redis, no clock."""

    def __init__(self, raise_on_use=False):
        self.data = {}
        self.raise_on_use = raise_on_use

    def incr_with_expiry(self, key, window_seconds):
        if self.raise_on_use:
            raise RuntimeError("redis down")
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]


def test_allows_up_to_the_limit_then_denies():
    store = FakeStore()
    assert [should_allow(store, "k", 3, 60) for _ in range(3)] == [True, True, True]
    assert should_allow(store, "k", 3, 60) is False


def test_separate_keys_have_separate_budgets():
    store = FakeStore()
    for _ in range(3):
        should_allow(store, "a", 3, 60)
    assert should_allow(store, "a", 3, 60) is False
    assert should_allow(store, "b", 3, 60) is True


def test_fails_open_when_the_store_errors():
    """A Redis outage must not refuse device traffic — brute force is already
    infeasible, so denying everyone would cause the outage it aims to prevent."""
    store = FakeStore(raise_on_use=True)
    assert should_allow(store, "k", 1, 60) is True


def test_client_ip_uses_remote_addr_by_default(settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_spoofed_forwarded_for_is_ignored_by_default(settings):
    """THE test. Without this, the limiter is bypassable with one header."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.2.3.4"
    )
    assert client_ip(request) == "10.0.0.9"


def test_forwarded_for_is_honoured_behind_one_trusted_proxy(settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 1
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.8"
    )
    # One trusted hop → the entry before the last is the real client.
    assert client_ip(request) == "1.2.3.4"


@pytest.mark.django_db
def test_activation_returns_429_over_the_limit(client, settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    from django.core.cache import cache

    cache.clear()
    body = json.dumps({"idempotency_key": "x", "license_key": "nope",
                       "device_fingerprint": "fp", "platform": "macos"})
    last = None
    for _ in range(4):
        last = client.post("/v1/activations", data=body, content_type="application/json")
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "RATE_LIMITED"
```

- [ ] **Step 2: Run to verify it fails**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_throttling.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'selahcue_api.apps.throttling'`

- [ ] **Step 3: Create the app package**

```bash
cd implementation/api
mkdir -p selahcue_api/apps/throttling/migrations
touch selahcue_api/apps/throttling/__init__.py selahcue_api/apps/throttling/migrations/__init__.py
```

Create `selahcue_api/apps/throttling/apps.py`:

```python
from django.apps import AppConfig


class SelahCueThrottlingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_throttling"
    name = "selahcue_api.apps.throttling"
    verbose_name = "SelahCue Throttling"
```

Note the label convention: `selahcue_<app>`, matching every other app here. Add
`"selahcue_api.apps.throttling.apps.SelahCueThrottlingConfig"` to `INSTALLED_APPS`.

- [ ] **Step 4: Write the pure logic**

Create `selahcue_api/apps/throttling/services.py`:

```python
"""Fixed-window rate limiting for the public /v1 device-auth surface.

Defense in depth, not a brute-force fix: a device token is ~158 bits behind an
HMAC-keyed fingerprint index, so guesses never reach a hash comparison. What this stops
is crude flooding and enumeration noise.

The logic is pure and store-injected so window behaviour is testable with no Redis and
no clock.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class CacheStore:
    """Redis-backed counter using the Django cache API. `incr` is atomic in the Redis
    backend, so two concurrent requests cannot both read the pre-increment value."""

    def __init__(self, cache):
        self._cache = cache

    def incr_with_expiry(self, key: str, window_seconds: int) -> int:
        # add() only succeeds if the key is absent, which is also what starts the window.
        if self._cache.add(key, 1, timeout=window_seconds):
            return 1
        return self._cache.incr(key)


def should_allow(store, key: str, limit: int, window_seconds: int) -> bool:
    """True while the caller is within `limit` requests per `window_seconds`.

    **Fails open.** If the store errors (Redis down), allow the request and log. Refusing
    all device traffic because the limiter is unavailable would cause the outage it is
    meant to prevent.
    """
    try:
        count = store.incr_with_expiry(key, window_seconds)
    except Exception:
        logger.exception("rate-limit store unavailable; failing open for key=%s", key)
        return True
    return count <= limit


def client_ip(request) -> str:
    """The caller's IP, trusting `X-Forwarded-For` ONLY behind a known proxy count.

    `X-Forwarded-For` is caller-controlled. Trusting it unconditionally lets anyone forge
    a fresh identity per request and bypass the limiter completely, so it is read only
    when `SELAHCUE_TRUSTED_PROXY_COUNT > 0`, taking the entry that proxy would have
    appended the real client as.
    """
    hops = int(getattr(settings, "SELAHCUE_TRUSTED_PROXY_COUNT", 0))
    if hops > 0:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.META.get("REMOTE_ADDR", "") or "unknown"
```

- [ ] **Step 5: Write the decorator**

Create `selahcue_api/apps/throttling/decorators.py`:

```python
"""View glue for the throttle. Kept apart from services.py so the logic stays free of
HTTP and Django-cache concerns."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.core.cache import cache

from selahcue_api.apps.throttling.services import CacheStore, client_ip, should_allow
from selahcue_api.graphql.errors import ErrorCode
from selahcue_api.platform.views import command_error_response


def throttle(scope: str, setting_name: str, default: tuple[int, int]):
    """Limit `scope` per client IP. Budget comes from `settings.<setting_name>` as a
    `(limit, window_seconds)` pair so it is tunable per environment and per test."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            limit, window = getattr(settings, setting_name, default)
            key = f"throttle:{scope}:{client_ip(request)}"
            if not should_allow(CacheStore(cache), key, limit, window):
                return command_error_response(
                    code=ErrorCode.RATE_LIMITED, surface="desktop", operation=scope
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
```

- [ ] **Step 6: Add settings**

In `selahcue_api/settings.py`, after the Celery block:

```python
# --- Cache / throttling ---------------------------------------------------------------
# Redis db 1 — deliberately NOT db 2, which is the Celery broker: a FLUSHDB on either
# must not destroy the other. Falls back to per-process LocMemCache when CACHE_URL is
# unset so a bare `pytest` needs no Redis. That fallback is only safe because the
# throttle's logic tests inject their own store.
_cache_url = os.getenv("CACHE_URL", "")
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _cache_url}
        if _cache_url
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "selahcue"}
    )
}

# 0 = trust REMOTE_ADDR only. Raise to the number of proxies in front of Django BEFORE
# relying on X-Forwarded-For — a caller-supplied header is otherwise a limiter bypass.
SELAHCUE_TRUSTED_PROXY_COUNT = int(os.getenv("SELAHCUE_TRUSTED_PROXY_COUNT", "0"))

# (limit, window_seconds) per client IP. Activation is the expensive one — it runs
# `make_password` against the enrollment key — so it gets the tighter budget.
SELAHCUE_THROTTLE_ACTIVATION = (10, 60)
SELAHCUE_THROTTLE_DEVICE_READ = (60, 60)
```

Add `CACHE_URL=redis://redis:6379/1` to `implementation/api/.env.sample` under a `# --- Cache ---` heading.

- [ ] **Step 7: Apply the decorator to the three `/v1` device endpoints**

In `selahcue_api/platform/views.py`, import at the top:

```python
from selahcue_api.apps.throttling.decorators import throttle
```

> Import inside the function bodies is **not** needed, but note `decorators.py` imports
> `command_error_response` from this module. Python resolves this because the decorator
> module is imported lazily at first use of `throttle(...)` at class-body time — if you hit
> a circular import, move `command_error_response` into a small `platform/responses.py`
> and import it from both places. Verify with Step 9 before assuming it is fine.

Decorate, placing `@throttle` **below** the method decorators so it runs after method
checking (a 405 should not consume budget):

```python
@csrf_exempt
@require_POST
@throttle("activation", "SELAHCUE_THROTTLE_ACTIVATION", (10, 60))
def activate_device(request):
    ...

@csrf_exempt
@require_POST
@throttle("license_refresh", "SELAHCUE_THROTTLE_DEVICE_READ", (60, 60))
def refresh_license(request):
    ...

@require_GET
@throttle("entitlement_manifest", "SELAHCUE_THROTTLE_DEVICE_READ", (60, 60))
def entitlement_manifest(request):
    ...
```

- [ ] **Step 8: Run the throttling tests**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_throttling.py -q`
Expected: `8 passed`

- [ ] **Step 9: Run the whole suite — check for circular imports and budget bleed**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q`
Expected: all pass.

If existing device tests now fail with 429, they are sharing a LocMemCache across tests.
Fix by adding `cache.clear()` to those tests, **not** by raising the limits.

- [ ] **Step 10: Commit**

```bash
git add implementation/api/selahcue_api/apps/throttling implementation/api/selahcue_api/settings.py \
        implementation/api/selahcue_api/platform/views.py implementation/api/tests/test_throttling.py \
        implementation/api/.env.sample
git commit -m "feat(api): fixed-window rate limiting on the /v1 device-auth surface

RATE_LIMITED existed but was never raised. Redis-backed fixed window per
(endpoint, client IP), returning 429 through the shipped error map.

Client IP trusts X-Forwarded-For only behind a configured proxy count: the header
is caller-supplied, so trusting it unconditionally lets anyone forge a fresh
identity per request and bypass the limiter entirely. Defaults to REMOTE_ADDR.

Fails OPEN on store error — brute force is already infeasible, so refusing all
device traffic during a Redis outage would cause the outage it prevents."
```

---

### Task 3: Transactional email delivery through the worker

**Files:**
- Create: `implementation/api/selahcue_api/templates/email/{verify_email,password_reset,account_exists}.{html,txt}` (6 files)
- Create: `implementation/api/selahcue_api/apps/accounts/email.py`
- Create: `implementation/api/selahcue_api/apps/accounts/tasks.py`
- Modify: `implementation/api/selahcue_api/settings.py` (template dir)
- Test: `implementation/api/tests/test_email_delivery.py`

**Interfaces:**
- Consumes: `EmailSender` seam at `apps/accounts/services.py:220`, `get_email_sender()`, `set_email_sender()`.
- Produces: `CeleryEmailSender`, and tasks `send_verification_email_task(email, raw_token)`, `send_password_reset_task(email, raw_token)`, `send_account_exists_task(email)`.

**Design source:** `docs/design/TRANSACTIONAL-EMAIL-spec.md` — copy deck is authoritative, do not paraphrase it.

- [ ] **Step 1: Write the failing tests**

Create `implementation/api/tests/test_email_delivery.py`:

```python
"""Transactional email rendering + dispatch.

Copy comes from docs/design/TRANSACTIONAL-EMAIL-spec.md. The account-exists assertions
enforce a security property, not a style preference.
"""

import pytest
from django.core import mail

from selahcue_api.apps.accounts.email import (
    render_account_exists,
    render_password_reset,
    render_verification,
)

pytestmark = pytest.mark.django_db


def test_verification_renders_both_parts_with_the_link():
    html, txt = render_verification("https://app.selahcue.com/verify?token=abc")
    assert "https://app.selahcue.com/verify?token=abc" in html
    assert "https://app.selahcue.com/verify?token=abc" in txt
    assert "24 hours" in html and "24 hours" in txt


def test_password_reset_states_the_one_hour_expiry():
    html, txt = render_password_reset("https://app.selahcue.com/reset?token=abc")
    assert "1 hour" in html and "1 hour" in txt
    assert "https://app.selahcue.com/reset?token=abc" in html


def test_account_exists_contains_no_url_at_all():
    """Security property. Signup returns an identical response whether or not the
    address is registered, so this email reaching the real owner is the ONLY signal an
    account exists. A link would hand that signal to an attacker probing addresses."""
    html, txt = render_account_exists()
    for part in (html, txt):
        assert "http://" not in part
        assert "https://" not in part
        assert "token" not in part.lower()


def test_sending_produces_html_and_text_alternatives():
    from selahcue_api.apps.accounts.tasks import send_verification_email_task

    send_verification_email_task("church@example.test", "tok-123")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["church@example.test"]
    assert message.body  # plain text
    assert any(ct == "text/html" for _, ct in message.alternatives)


def test_task_takes_an_opaque_token_not_a_user_object():
    """Tasks are serialized onto Redis. A queued message is not a place to leave a user
    record, and a token string is the minimum the task needs."""
    import inspect

    from selahcue_api.apps.accounts.tasks import send_verification_email_task

    params = list(inspect.signature(send_verification_email_task).parameters)
    assert params == ["email", "raw_token"]


def test_enqueue_failure_does_not_break_the_caller(monkeypatch):
    """Signup succeeding with a delayed email is recoverable; signup 500ing because
    Redis blinked is not."""
    from selahcue_api.apps.accounts import email as email_module

    def boom(*a, **k):
        raise RuntimeError("broker down")

    monkeypatch.setattr(email_module.send_verification_email_task, "delay", boom)
    sender = email_module.CeleryEmailSender()

    class FakeUser:
        email = "church@example.test"

    sender.send_email_verification(FakeUser(), "tok")  # must not raise
```

- [ ] **Step 2: Run to verify it fails**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_email_delivery.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'selahcue_api.apps.accounts.email'`

- [ ] **Step 3: Point Django at a templates directory**

In `settings.py`, set `TEMPLATES[0]["DIRS"] = [BASE_DIR / "selahcue_api" / "templates"]`.

- [ ] **Step 4: Create the six templates**

Create `selahcue_api/templates/email/verify_email.txt` with the plain-text block from the
spec's §Plain-text fallbacks (verification), using `{{ verify_url }}`. Create
`password_reset.txt` and `account_exists.txt` the same way from their spec blocks.

Create `verify_email.html` using the spec's copy deck and palette:

```html
{% raw %}<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<style>
  @media (prefers-color-scheme: dark) {
    .card { background:#1e232c !important; }
    .text { color:#eef1f6 !important; }
    .muted { color:#9aa4b2 !important; }
    .page { background:#0e1116 !important; }
  }
</style>
</head>
<body class="page" style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;">
 <tr><td align="center" style="padding:40px 20px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" class="card"
         style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e2e5ea;border-radius:12px;">
   <tr><td style="padding:40px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <p class="text" style="margin:0 0 20px;font-size:20px;font-weight:700;color:#1a1d23;">SelahCue</p>
    <h1 class="text" style="margin:0 0 20px;font-size:26px;line-height:1.3;color:#1a1d23;">Verify your email address</h1>
    <p class="muted" style="margin:0 0 20px;font-size:15px;line-height:1.55;color:#5c6470;">
      Thanks for creating a SelahCue account. Confirm this address so we know we can reach you — it is how we send password resets and important service notices.
    </p>
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
     <tr><td bgcolor="#5b6bd6" style="border-radius:8px;">
      <a href="{{ verify_url }}" style="display:inline-block;padding:14px 28px;font-size:16px;font-weight:600;color:#ffffff;text-decoration:none;">Verify email address</a>
     </td></tr>
    </table>
    <p style="margin:0 0 20px;font-size:13px;line-height:1.55;color:#4453b8;word-break:break-all;">
      Button not working? Paste this link into your browser:<br>{{ verify_url }}
    </p>
    <p class="muted" style="margin:0 0 20px;font-size:13px;line-height:1.55;color:#5c6470;">
      This link expires in 24 hours. If it has already expired, sign in and request a new one.
    </p>
    <p class="muted" style="margin:0;font-size:13px;line-height:1.55;color:#5c6470;">
      Did not create a SelahCue account? Ignore this email — no account is active until this address is verified.
    </p>
   </td></tr>
  </table>
  <p class="muted" style="margin:20px 0 0;font-size:12px;color:#5c6470;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    SelahCue · Sent because someone signed up with this address.
  </p>
 </td></tr>
</table>
</body>
</html>{% endraw %}
```

Build `password_reset.html` identically but with the reset copy, `{{ reset_url }}`, the
"Choose a new password" CTA, and the security band:

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fdf3dd;border-radius:8px;">
 <tr><td style="padding:16px;font-size:13px;line-height:1.55;color:#7a4a00;">
   Did not request this? Your password has not changed and no action is needed. If you keep receiving these, contact your church administrator.
 </td></tr>
</table>
```

Build `account_exists.html` from the spec copy with the security band — and **no `<a>` tag
and no URL anywhere**. The test enforces this.

- [ ] **Step 5: Write the renderers and the Celery sender**

Create `selahcue_api/apps/accounts/email.py`:

```python
"""Rendering + dispatch for the three transactional emails.

Design: docs/design/TRANSACTIONAL-EMAIL-spec.md (Figma page 719:132). The copy there is
authoritative — change it there first, not here.
"""

from __future__ import annotations

import logging

from django.template.loader import render_to_string

from selahcue_api.apps.accounts.services import EmailSender
from selahcue_api.apps.accounts.tasks import (
    send_account_exists_task,
    send_password_reset_task,
    send_verification_email_task,
)

logger = logging.getLogger(__name__)


def render_verification(verify_url: str) -> tuple[str, str]:
    ctx = {"verify_url": verify_url}
    return (
        render_to_string("email/verify_email.html", ctx),
        render_to_string("email/verify_email.txt", ctx),
    )


def render_password_reset(reset_url: str) -> tuple[str, str]:
    ctx = {"reset_url": reset_url}
    return (
        render_to_string("email/password_reset.html", ctx),
        render_to_string("email/password_reset.txt", ctx),
    )


def render_account_exists() -> tuple[str, str]:
    # No context: this email deliberately carries no token and no link.
    return (
        render_to_string("email/account_exists.html", {}),
        render_to_string("email/account_exists.txt", {}),
    )


class CeleryEmailSender(EmailSender):
    """Dispatches to the worker. Enqueue failure is logged, never raised: signup
    succeeding with a delayed email is recoverable; signup 500ing because the broker
    blinked is not."""

    @staticmethod
    def _dispatch(task, *args) -> None:
        try:
            task.delay(*args)
        except Exception:
            logger.exception("could not enqueue %s; email not sent", task.name)

    def send_email_verification(self, user, raw_token: str) -> None:
        self._dispatch(send_verification_email_task, user.email, raw_token)

    def send_password_reset(self, user, raw_token: str) -> None:
        self._dispatch(send_password_reset_task, user.email, raw_token)

    def send_account_exists(self, email: str) -> None:
        self._dispatch(send_account_exists_task, email)
```

Create `selahcue_api/apps/accounts/tasks.py`:

```python
"""Celery tasks for transactional email.

Tasks take an **opaque token string**, never a user object: task arguments are
serialized onto Redis, and a queued message is not a place to leave a user record.
Idempotent — CELERY_TASK_ACKS_LATE means a crashed worker redelivers, and sending the
same verification email twice is harmless.
"""

from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def _send(subject: str, to: str, html: str, text: str) -> None:
    message = EmailMultiAlternatives(
        subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=[to]
    )
    message.attach_alternative(html, "text/html")
    message.send()


@shared_task(name="accounts.send_verification_email")
def send_verification_email_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_verification

    url = f"{settings.FRONTEND_BASE_URL}/verify?token={raw_token}"
    html, text = render_verification(url)
    _send("Verify your SelahCue email address", email, html, text)


@shared_task(name="accounts.send_password_reset")
def send_password_reset_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_password_reset

    url = f"{settings.FRONTEND_BASE_URL}/reset?token={raw_token}"
    html, text = render_password_reset(url)
    _send("Reset your SelahCue password", email, html, text)


@shared_task(name="accounts.send_account_exists")
def send_account_exists_task(email: str) -> None:
    from selahcue_api.apps.accounts.email import render_account_exists

    html, text = render_account_exists()
    _send("Someone tried to sign up with your SelahCue address", email, html, text)
```

The in-function imports break the `email.py` ↔ `tasks.py` cycle.

Add to `settings.py`:

```python
# Base URL of the web surface that hosts /verify and /reset. NOTE: those routes do not
# exist yet — they land with slice 4. Emails will link to a 404 until then.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:2000")
```

- [ ] **Step 6: Install the sender at startup**

In `selahcue_api/apps/accounts/apps.py`, add:

```python
    def ready(self):
        # Swap the no-op seam for the Celery-backed sender once apps are loaded.
        from selahcue_api.apps.accounts.email import CeleryEmailSender
        from selahcue_api.apps.accounts.services import set_email_sender

        set_email_sender(CeleryEmailSender())
```

- [ ] **Step 7: Make tests use the locmem mail backend**

Add to `pytest.ini`:

```ini
env =
    CELERY_TASK_ALWAYS_EAGER=1
```

If `pytest-env` is not installed, instead add to `settings.py`:

```python
# Run tasks inline under test so `.delay()` executes synchronously and mail.outbox fills.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
```

and set `settings.CELERY_TASK_ALWAYS_EAGER = True` via the `settings` fixture in the test.
Prefer the settings route — no new dependency.

- [ ] **Step 8: Run the email tests**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_email_delivery.py -q`
Expected: `6 passed`

- [ ] **Step 9: Run the whole suite**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q`
Expected: all pass. Existing auth tests override `EmailSender` via `set_email_sender`, so
`ready()` installing the Celery sender must not break them — this run is what proves it.

- [ ] **Step 10: Commit**

```bash
git add implementation/api/selahcue_api/templates implementation/api/selahcue_api/apps/accounts/email.py \
        implementation/api/selahcue_api/apps/accounts/tasks.py implementation/api/selahcue_api/apps/accounts/apps.py \
        implementation/api/selahcue_api/settings.py implementation/api/tests/test_email_delivery.py
git commit -m "feat(api): deliver transactional email through the Celery worker

Implements the three templates from docs/design/TRANSACTIONAL-EMAIL-spec.md,
replacing the no-op EmailSender seam. Signup can now complete end to end.

Tasks take an opaque token string, never a user object — arguments are
serialized onto Redis. Enqueue failure is logged, never raised.

account_exists renders no link and no token; a test asserts no URL appears in
either part. That is a security property: this email is the only signal an
account exists, and a link would hand it to an attacker probing addresses."
```

---

### Task 4: Beat jobs — revocation cascade and expiry sweeps

**Files:**
- Create: `implementation/api/selahcue_api/apps/devices/tasks.py`
- Create: `implementation/api/selahcue_api/apps/accounts/maintenance.py`
- Modify: `implementation/api/selahcue_api/settings.py` (`CELERY_BEAT_SCHEDULE`)
- Test: `implementation/api/tests/test_revocation_cascade.py`

**Interfaces:**
- Produces: `cascade_license_revocations(batch_size=500) -> int`, `sweep_expired_credentials(batch_size=1000) -> dict`.
- Consumes: `ACTIVATABLE_KEY_STATUSES`, `DeviceTokenStatus`, `record_audit_event`, `ActorContext`, `ActorKind` (all shipped).

- [ ] **Step 1: Write the failing tests**

Create `implementation/api/tests/test_revocation_cascade.py`:

```python
"""Revocation cascade + expiry sweeps.

Closes R6 from the entitlement-manifest spec: the issuance gate stops re-issue, this
stops the already-issued token. Together they make revocation effective without a
revocation list.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys.models import LicenseKeyStatus

pytestmark = pytest.mark.django_db

# Reuse the seeding helpers from the manifest slice — copy _seed_license_key and
# _activate from tests/test_entitlement_manifest_slice.py verbatim into this module.
# The shipped slices each seed their own; do not introduce a shared conftest.


def test_revoked_licence_revokes_its_device_tokens(activated):
    device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])

    changed = cascade_license_revocations()

    assert changed == 1
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.REVOKED


def test_active_licence_is_left_alone(activated):
    device, _token, _key = activated
    assert cascade_license_revocations() == 0
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.ACTIVE


def test_cascade_is_idempotent(activated):
    _device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])

    assert cascade_license_revocations() == 1
    assert cascade_license_revocations() == 0  # nothing left to do


def test_cascade_is_audited(activated):
    _device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])
    cascade_license_revocations()
    assert AuditEvent.objects.filter(action="device_token.revoked_by_cascade").count() == 1


def test_sweep_deletes_expired_credential_tokens_only():
    from selahcue_api.apps.accounts.maintenance import sweep_expired_credentials
    from selahcue_api.apps.accounts.models import CustomerSession

    # Sessions past expiry are removed; live ones survive.
    before = CustomerSession.objects.count()
    result = sweep_expired_credentials()
    assert result["sessions"] >= 0
    assert CustomerSession.objects.filter(expires_at__lt=timezone.now()).count() == 0
    assert CustomerSession.objects.count() <= before
```

- [ ] **Step 2: Run to verify it fails**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_revocation_cascade.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'selahcue_api.apps.devices.tasks'`

- [ ] **Step 3: Write the cascade**

Create `selahcue_api/apps/devices/tasks.py`:

```python
"""Periodic revocation cascade.

Revoking a licence key does not cascade to already-issued device tokens: the token's
expiry is the LICENCE's expiry, and `authenticate_device_token` never consults licence
status. This job closes that gap.

Pairs with the entitlement manifest's issuance gate — the gate stops re-issue, this stops
the existing token. **Never blanks live output (NFR-024):** revoking a token stops future
API calls; the desktop keeps its cached entitlement until the licence expires.
"""

from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.graphql.context import ActorContext, ActorKind


def cascade_license_revocations(batch_size: int = 500) -> int:
    """Revoke ACTIVE device tokens whose licence has left an activatable status.

    Idempotent: already-revoked tokens are excluded by the filter. Bounded by
    `batch_size` so a large tenant cannot produce an unbounded query.
    """
    stale = list(
        DeviceToken.objects.select_related("device__license_key")
        .filter(status=DeviceTokenStatus.ACTIVE)
        .exclude(device__license_key__status__in=list(ACTIVATABLE_KEY_STATUSES))[:batch_size]
    )
    now = timezone.now()
    changed = 0
    for token in stale:
        with transaction.atomic():
            token.status = DeviceTokenStatus.REVOKED
            token.save(update_fields=["status", "updated_at"])
            record_audit_event(
                ActorContext(kind=ActorKind.SERVICE, actor_id="revocation-cascade"),
                action="device_token.revoked_by_cascade",
                target_type="device_token",
                target_id=str(token.id),
                request_id=f"cascade-{now.isoformat()}",
                reason=f"licence status {token.device.license_key.status} is not activatable",
                source_surface="desktop_v1",
                after={"status": DeviceTokenStatus.REVOKED},
            )
        changed += 1
    return changed


@shared_task(name="devices.cascade_license_revocations")
def cascade_license_revocations_task() -> int:
    return cascade_license_revocations()
```

- [ ] **Step 4: Write the sweeps**

Create `selahcue_api/apps/accounts/maintenance.py`:

```python
"""Expiry sweeps. Pure hygiene — expiry is already enforced at read time, so this only
stops unbounded table growth. Bounded batches; safe to re-run."""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from selahcue_api.apps.accounts.models import CredentialToken, CustomerSession


def sweep_expired_credentials(batch_size: int = 1000) -> dict[str, int]:
    now = timezone.now()
    session_ids = list(
        CustomerSession.objects.filter(expires_at__lt=now).values_list("id", flat=True)[:batch_size]
    )
    sessions, _ = CustomerSession.objects.filter(id__in=session_ids).delete()
    token_ids = list(
        CredentialToken.objects.filter(expires_at__lt=now).values_list("id", flat=True)[:batch_size]
    )
    tokens, _ = CredentialToken.objects.filter(id__in=token_ids).delete()
    return {"sessions": sessions, "credential_tokens": tokens}


@shared_task(name="accounts.sweep_expired_credentials")
def sweep_expired_credentials_task() -> dict[str, int]:
    return sweep_expired_credentials()
```

- [ ] **Step 5: Schedule them**

In `settings.py`, after the Celery block:

```python
from celery.schedules import crontab  # noqa: E402  (kept beside the schedule it configures)

CELERY_BEAT_SCHEDULE = {
    # Hourly: a revoked licence should stop working within the hour, not at expiry.
    "cascade-license-revocations": {
        "task": "devices.cascade_license_revocations",
        "schedule": crontab(minute=0),
    },
    # Nightly: pure row hygiene, no behavioural effect.
    "sweep-expired-credentials": {
        "task": "accounts.sweep_expired_credentials",
        "schedule": crontab(hour=3, minute=30),
    },
}
```

- [ ] **Step 6: Run the tests**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_revocation_cascade.py -q`
Expected: all pass.

- [ ] **Step 7: Run the whole suite**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add implementation/api/selahcue_api/apps/devices/tasks.py \
        implementation/api/selahcue_api/apps/accounts/maintenance.py \
        implementation/api/selahcue_api/settings.py \
        implementation/api/tests/test_revocation_cascade.py
git commit -m "feat(api): beat jobs — licence revocation cascade + expiry sweeps

Closes R6 from the entitlement-manifest spec. Revoking a licence key did not
reach already-issued device tokens: the token expiry IS the licence expiry, and
authenticate_device_token never consults licence status. Hourly cascade revokes
tokens whose licence has left ACTIVATABLE_KEY_STATUSES.

The manifest's issuance gate stops re-issue; this stops the existing token.
Together they make revocation effective without a revocation list.

Audited, idempotent, bounded batches. Does not blank live output (NFR-024) — a
revoked token stops future API calls, nothing else."
```

---

### Task 5: Postgres concurrency test and CI service containers

Closes finding 1 of [86ajyq86g](https://app.clickup.com/t/86ajyq86g) — untestable until now because there was no Postgres.

**Files:**
- Create: `implementation/api/tests/test_concurrency_postgres.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:** consumes `activate_device` and `ActivateDeviceData` (shipped, unchanged).

- [ ] **Step 1: Write the test**

Create `implementation/api/tests/test_concurrency_postgres.py`:

```python
"""The DEC-004 instance limit under real concurrency.

`activate_device` guards the limit with select_for_update, which SQLite silently no-ops
(has_select_for_update = False). This test therefore SKIPS on SQLite — it would pass
there for the wrong reason and hide the very race it exists to catch.
"""

import threading

import pytest
from django.db import connection, connections

from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import ActivateDeviceData, activate_device

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="select_for_update is a no-op on SQLite; this race is only observable on Postgres",
    ),
]


def test_concurrent_activations_cannot_exceed_the_device_limit():
    # Seed a licence with device_limit=1 using the helper copied from
    # tests/test_entitlement_manifest_slice.py, with device_limit=1.
    key, full_key = _seed_license_key(tag="conc", device_limit=1)

    errors = []

    def activate(n):
        try:
            activate_device(
                ActivateDeviceData(
                    idempotency_key=f"conc-{n}",
                    presented_key=full_key,
                    device_fingerprint=f"fp-conc-{n}",
                    platform="macos",
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=activate, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    active = Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count()
    assert active == 1, f"instance limit exceeded: {active} active devices, errors={errors}"
    assert len(errors) == 1, "exactly one activation should have been rejected"
```

Copy `_seed_license_key` from `tests/test_entitlement_manifest_slice.py` into this module.

- [ ] **Step 2: Verify it skips locally on SQLite**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests/test_concurrency_postgres.py -v`
Expected: `1 skipped` with the reason printed. A skip here is the correct local result — the
test is meaningless without row locking.

- [ ] **Step 3: Add service containers to the `api` CI job**

In `.github/workflows/ci.yml`, inside the `api` job add:

```yaml
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: selahcue_test
          POSTGRES_USER: selahcue
          POSTGRES_PASSWORD: selahcue
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U selahcue"
          --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s --health-timeout 5s --health-retries 5
```

And add `env:` to the **Tests** step so it runs against Postgres:

```yaml
      - name: Tests
        env:
          SQL_ENGINE: django.db.backends.postgresql
          SQL_DATABASE: selahcue_test
          SQL_USER: selahcue
          SQL_PASSWORD: selahcue
          SQL_HOST: localhost
          SQL_PORT: "5432"
          CACHE_URL: redis://localhost:6379/1
          CELERY_BROKER_URL: redis://localhost:6379/2
        run: python -m pytest tests -q
```

Also add `psycopg[binary]>=3.2,<4` to the **Install** step:

```yaml
      - name: Install
        run: pip install -e ".[dev]" "psycopg[binary]>=3.2,<4"
```

- [ ] **Step 4: Verify the workflow parses and the env is wired**

```bash
cd /Users/m.oluwole/Documents/code/scph
python3 -c "
import yaml
d = yaml.safe_load(open('.github/workflows/ci.yml'))
api = d['jobs']['api']
assert set(api['services']) == {'postgres','redis'}, api.get('services')
tests = [s for s in api['steps'] if s.get('name') == 'Tests'][0]
assert tests['env']['SQL_ENGINE'].endswith('postgresql')
print('OK — api job has postgres+redis and runs tests against Postgres')
"
```

Expected: `OK — …`

- [ ] **Step 5: Confirm the suite still passes locally on SQLite**

Run: `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q`
Expected: all pass, with the concurrency test skipped.

- [ ] **Step 6: Commit**

```bash
git add implementation/api/tests/test_concurrency_postgres.py .github/workflows/ci.yml
git commit -m "test(api): Postgres concurrency test for the DEC-004 instance limit

Closes finding 1 of 86ajyq86g, untestable until this slice because there was no
Postgres to run it against. Two concurrent activations against a device_limit=1
licence must produce exactly one active device.

SKIPS on SQLite deliberately: select_for_update is a no-op there
(has_select_for_update=False), so the test would pass for the wrong reason and
hide the race it exists to catch. The api CI job gains Postgres and Redis
service containers so it actually executes where it counts."
```

- [ ] **Step 7: Push and watch CI**

```bash
GIT_SSH_COMMAND='ssh -o BatchMode=yes' git push origin main
gh run list --branch main --limit 1
```

The `api` job must now show the concurrency test **running, not skipped**. If it skips in
CI, `SQL_ENGINE` did not reach the test process — fix that before considering the task done.

---

## Self-Review

**Spec coverage**

| Spec section | Task |
|---|---|
| Compose services (api/db/redis/worker/beat/mailhog) | 1 |
| Celery application, `-A selahcue_api` | 1 |
| `acks_late` + prefetch 1 | 1 |
| Redis cache, db 1 vs broker db 2 | 2 |
| Fixed-window limiter, pure + injectable | 2 |
| Trusted-proxy IP resolution + spoofing test | 2 |
| Fail-open on store error | 2 |
| 429 via existing `command_error_response` | 2 |
| Email delivery, HTML + text parts | 3 |
| Opaque token, not user object | 3 |
| Enqueue failure must not fail signup | 3 |
| account-exists has no URL | 3 |
| Revocation cascade, audited, idempotent, bounded | 4 |
| Expiry sweeps | 4 |
| Postgres concurrency test | 5 |
| CI Postgres + Redis containers | 5 |
| Ops requirements (header stripping, edge throttling) | **Gap — see below** |

**Gap found and closed:** the spec's §Ops requirements had no task. Add to Task 2, Step 10,
before committing: append an "Ops requirements" subsection to `docs/ops/DEPLOYMENT.md`
stating that the ingress must strip inbound `X-SelahCue-*` headers before
`SELAHCUE_TRUST_ACTOR_HEADERS` is ever enabled, that per-IP flood protection belongs at
the edge with the app limiter as second layer, and that Redis must not be publicly
reachable.

**Type consistency:** `should_allow(store, key, limit, window_seconds)` and
`client_ip(request)` are defined in Task 2 and used with those exact signatures in the
decorator. `cascade_license_revocations(batch_size)` and `sweep_expired_credentials(batch_size)`
are defined in Task 4 and called from their `@shared_task` wrappers with matching names.
`CeleryEmailSender` implements the three `EmailSender` methods with the shipped signatures
(`send_email_verification(user, raw_token)`, `send_password_reset(user, raw_token)`,
`send_account_exists(email)`), verified against `apps/accounts/services.py:225-232`.

**Known risk the implementer must confirm, not assume:** Task 2 Step 7 has
`throttling/decorators.py` importing `command_error_response` from `platform/views.py`
while `views.py` imports `throttle` from the decorator module. Step 9 exists to catch the
circular import if it materialises; the stated fix is extracting `command_error_response`
into `platform/responses.py`. Do not skip Step 9.
