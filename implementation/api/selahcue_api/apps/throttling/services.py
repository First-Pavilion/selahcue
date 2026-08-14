"""Fixed-window rate limiting for the public /v1 device-auth surface.

Defense in depth, not a brute-force fix: a device token is ~158 bits behind an
HMAC-keyed fingerprint index, so guesses never reach a hash comparison. What this stops
is crude flooding and enumeration noise.

The logic is pure and store-injected so window behaviour is testable with no Redis and
no clock.
"""

from __future__ import annotations

import ipaddress
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# One report per outage, not one per request. A five-minute Redis outage at 100 rps would
# otherwise emit ~30,000 log records — unbounded logging, which the repo forbids. State is a
# single module-level float, so this stays bounded in memory too. A benign race between
# threads costs at most one extra line.
_STORE_ERROR_LOG_INTERVAL_SECONDS = 60.0
_last_store_error_log = float("-inf")


class CacheStore:
    """Redis-backed counter using the Django cache API.

    `cache.incr()` is NOT atomic in Django's Redis backend — `django/core/cache/backends/
    redis.py` implements it as `EXISTS` then `INCR`, two separate round trips. If the key's
    TTL lapses **between** those two calls, Redis `INCR` recreates the key at 1 **with no
    expiry**: `add()` can then never reclaim it (the key exists) and nothing else sets a TTL,
    so the counter climbs forever and that caller is rate-limited permanently, with no
    self-heal short of a manual `DEL`.

    The invariant this class holds is therefore: **no path leaves the counter key
    persistent.** Any increment that returns 1 either created the window or was a silent
    recreation by `INCR`; both are followed by `touch()`, which is Redis `EXPIRE`. LocMemCache
    evaluates expiry under a lock and never reproduces the race, which is exactly why the
    original shape passed its tests.
    """

    def __init__(self, cache):
        self._cache = cache

    def incr_with_expiry(self, key: str, window_seconds: int) -> int:
        # add() is SET NX EX — atomic, and its success is what starts a window.
        if self._cache.add(key, 1, timeout=window_seconds):
            return 1
        try:
            count = self._cache.incr(key)
        except ValueError:
            # The window expired before incr()'s existence check — the harmless half of the
            # race. Treat it as the first request of a fresh window rather than an error:
            # failing open here would hand a caller a free request on every rollover.
            self._cache.add(key, 1, timeout=window_seconds)
            # add() may have lost to a concurrent starter; touch() guarantees a TTL either way.
            self._cache.touch(key, window_seconds)
            return 1
        if count == 1:
            # We only ever store 1 and increment, so a count of 1 out of incr() cannot be a
            # normal increment — it means the TTL lapsed between EXISTS and INCR and Redis
            # recreated the key PERSISTENTLY. touch() is the EXPIRE that add() can no longer
            # apply. (Residual: a process death between INCR and touch() would still leave the
            # key persistent. Closing that needs a Lua script or a raw pipeline, i.e. a
            # Redis-only code path that the no-Redis test suite could not exercise.)
            self._cache.touch(key, window_seconds)
        return count


def should_allow(store, key: str, limit: int, window_seconds: int) -> bool:
    """True while the caller is within `limit` requests per `window_seconds`.

    **Fails open.** If the store errors (Redis down), allow the request and log. Refusing
    all device traffic because the limiter is unavailable would cause the outage it is
    meant to prevent.
    """
    global _last_store_error_log
    try:
        count = store.incr_with_expiry(key, window_seconds)
    except Exception as error:
        now = time.monotonic()
        if now - _last_store_error_log >= _STORE_ERROR_LOG_INTERVAL_SECONDS:
            _last_store_error_log = now
            # warning, not exception: a traceback per failing request is the unbounded-log
            # problem. The store is either up or down; one line per minute says so.
            logger.warning(
                "rate-limit store unavailable (%s) for key=%s; failing open. "
                "Further reports suppressed for %.0fs.",
                type(error).__name__,
                key,
                _STORE_ERROR_LOG_INTERVAL_SECONDS,
            )
        return True
    return count <= limit


def client_ip(request) -> str:
    """The caller's IP, trusting `X-Forwarded-For` ONLY behind a known proxy count.

    `X-Forwarded-For` is caller-controlled. Trusting it unconditionally lets anyone forge
    a fresh identity per request and bypass the limiter completely, so it is read only
    when `SELAHCUE_TRUSTED_PROXY_COUNT > 0`, taking the entry that proxy would have
    appended the real client as.

    The derived entry is then **parsed as an IP address** before it is returned. The caller
    controls everything to the left of the trusted hops, so if the hop count is set higher
    than the real proxy depth the selected entry is attacker-chosen text — and it goes
    straight into a cache key. Django only warns (`CacheKeyWarning`) about an over-long or
    illegal key, so a 300-character forgery would mint a fresh limiter budget per request AND
    create unbounded distinct Redis keys. Refusing to parse caps key cardinality at real
    addresses and downgrades a hop-count misconfiguration to "everyone shares one bucket".

    Note: an entry carrying a port (`1.2.3.4:5678`) does not parse and falls back. That is not
    the `X-Forwarded-For` format (ports belong to RFC 7239 `Forwarded`), and falling back is
    the safe direction.
    """
    hops = int(getattr(settings, "SELAHCUE_TRUSTED_PROXY_COUNT", 0))
    if hops > 0:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            try:
                # str() of the parsed value normalises IPv6 spelling, so `2001:DB8::1` and
                # `2001:db8:0:0:0:0:0:1` cannot buy two separate budgets.
                return str(ipaddress.ip_address(parts[-hops]))
            except ValueError:
                pass
    return request.META.get("REMOTE_ADDR", "") or "unknown"
