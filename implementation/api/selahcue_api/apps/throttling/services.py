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
from enum import Enum

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


class BudgetOutcome(str, Enum):
    """Why a budget check came out the way it did.

    `should_allow` collapses this to a bool and cannot distinguish "the store said yes" from
    "the store is down and we failed open" — which is fine for a read surface and NOT fine for
    a caller that sends email, because those two answers call for different behaviour.
    """

    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    STORE_UNAVAILABLE = "STORE_UNAVAILABLE"


def evaluate_budget(store, key: str, limit: int, window_seconds: int) -> BudgetOutcome:
    """Spend one unit of `key`'s budget and report what happened.

    **Still fails open** — `STORE_UNAVAILABLE` is a permit, not a refusal. Refusing all
    device traffic because the limiter is unavailable would cause the outage it is meant to
    prevent. The difference is that the caller can now SEE that it was a fail-open, and a
    caller with an expensive side effect (sending mail) can bound that side effect instead of
    treating the outage as a clean allow.
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
        return BudgetOutcome.STORE_UNAVAILABLE
    return BudgetOutcome.ALLOWED if count <= limit else BudgetOutcome.DENIED


def should_allow(store, key: str, limit: int, window_seconds: int) -> bool:
    """True while the caller is within `limit` requests per `window_seconds`.

    **Fails open.** If the store errors (Redis down), allow the request and log. Unchanged
    behaviour for the `/v1` device surface this was written for; callers that need to tell a
    fail-open apart from a real allow use `evaluate_budget` directly.
    """
    return evaluate_budget(store, key, limit, window_seconds) is not BudgetOutcome.DENIED


# IPv6 bucket size for throttle-identity purposes (86akcn8ww). A single attacker on a
# standard residential IPv6 allocation controls a whole /64 — roughly 2^64 addresses — so
# returning the full address as the cache key gives them roughly 2^64 distinct throttle
# identities, defeating every per-IP budget in the API (device-auth, resend-verification,
# both password-reset paths). Truncating to the /64 network prefix collapses that entire
# allocation onto one bucket, which is the same boundary a standard residential ISP hands out
# as a single customer's address space (RFC 6177's recommended minimum allocation). /56 was
# the other option the ticket named; /64 is chosen because it is the narrower, more
# conservative bucket — it groups only what a single customer plausibly controls, rather than
# the 256 /64s (a /56) that can span multiple distinct households or a small business's whole
# site. Hashing the address was explicitly rejected: a hash preserves cardinality 1:1 and
# fixes nothing, whereas truncation is what actually collapses the attacker's cheap address
# space onto a fixed number of buckets.
#
# COLLATERAL, stated rather than discovered later: /64 bucketing means every device behind one
# residential allocation shares a single budget. For an ordinary household that is correct —
# it is one "customer" for throttling purposes. For a large IPv6-native NAT (e.g. a campus or
# carrier-grade NAT that hands out addresses within a single /64 to many unrelated real users)
# it is a shared-bucket denial risk of the same shape as this module's existing
# SELAHCUE_TRUSTED_PROXY_COUNT misconfiguration behaviour: many legitimate callers can exhaust
# one shared budget because of how the network above them is structured, not because of
# anything they did. That trade is accepted here because the alternative — no bucketing at
# all — makes the per-IP budget meaningless against any IPv6-reachable attacker.
#
# IPv4 is completely unaffected: a /32 IS the whole address, so "truncate to /32" is a no-op
# and the existing full-address behaviour is preserved exactly.
_IPV6_THROTTLE_BUCKET_PREFIX_BITS = 64


def _bucket_for_throttling(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Collapse `address` onto its throttle-identity bucket.

    IPv4 passes through unchanged (its /32 network address is the address itself). IPv6 is
    truncated to its /64 network prefix — see `_IPV6_THROTTLE_BUCKET_PREFIX_BITS` above for
    why 64 and not the full address or a hash.
    """
    if address.version == 4:
        return str(address)
    network = ipaddress.ip_network(f"{address}/{_IPV6_THROTTLE_BUCKET_PREFIX_BITS}", strict=False)
    return str(network.network_address)



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

    The returned value is a throttle-identity BUCKET, not necessarily the literal address:
    IPv4 is returned unchanged, IPv6 is truncated to its /64 network prefix (see
    `_bucket_for_throttling`). Every caller of this function gets that bucketing for free,
    which is the point of fixing it here rather than in each of the /v1, resend-verification
    and password-reset callers separately.
    """
    hops = int(getattr(settings, "SELAHCUE_TRUSTED_PROXY_COUNT", 0))
    if hops > 0:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            try:
                # str() of the parsed value normalises IPv6 spelling, so `2001:DB8::1` and
                # `2001:db8:0:0:0:0:0:1` cannot buy two separate budgets — and bucketing
                # collapses the low 64 bits too, so they cannot buy separate budgets that way
                # either.
                return _bucket_for_throttling(ipaddress.ip_address(parts[-hops]))
            except ValueError:
                pass
    remote_addr = request.META.get("REMOTE_ADDR", "")
    if not remote_addr:
        return "unknown"
    try:
        return _bucket_for_throttling(ipaddress.ip_address(remote_addr))
    except ValueError:
        # REMOTE_ADDR is set by the WSGI/ASGI server from the socket peer, never by the
        # caller, so this should be unreachable in practice. Falling back to the raw value
        # (rather than "unknown") preserves the pre-existing behaviour for whatever wrote it
        # if it is ever something unparseable, e.g. in an unusual test harness.
        return remote_addr
