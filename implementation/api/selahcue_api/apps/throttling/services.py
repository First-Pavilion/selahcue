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
        try:
            return self._cache.incr(key)
        except ValueError:
            # The window expired between add() and incr(). Treat it as the first request
            # of a fresh window rather than an error — failing open here would hand a
            # caller a free request every time a window rolls over.
            self._cache.add(key, 1, timeout=window_seconds)
            return 1


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
