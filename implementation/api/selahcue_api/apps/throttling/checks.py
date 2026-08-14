"""Deployment checks for the rate limiter.

The limiter's identity is the client IP, and behind the documented Coolify/Cloudflare edge
`REMOTE_ADDR` is the *proxy* for every request. `SELAHCUE_TRUSTED_PROXY_COUNT` defaults to 0,
which is the safe default for a directly-exposed service and the WRONG one behind an edge:
every customer worldwide would then share a single 10/min activation bucket, and one busy
church would rate-limit everybody.

That is a deployment decision, not a code defect, so this is a Warning and never an Error —
CI sets `CACHE_URL` with `DEBUG` unset, and an Error would fail `manage.py check` there.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Warning as CheckWarning, register

SHARED_BUCKET_WARNING = "selahcue_throttling.W001"


def _uses_a_shared_cache() -> bool:
    """True when the cache is the Redis backend, i.e. `CACHE_URL` was supplied.

    Read off the effective `CACHES` config rather than the environment variable, so this
    reflects what the process will actually use.
    """
    backend = (settings.CACHES.get("default") or {}).get("BACKEND", "")
    return backend.endswith("redis.RedisCache")


@register()
def trusted_proxy_count_is_set_behind_a_proxy(app_configs, **kwargs):
    if settings.DEBUG or not _uses_a_shared_cache():
        return []
    if int(getattr(settings, "SELAHCUE_TRUSTED_PROXY_COUNT", 0)) > 0:
        return []
    return [
        CheckWarning(
            "SELAHCUE_TRUSTED_PROXY_COUNT is 0, so the rate limiter identifies every caller "
            "by REMOTE_ADDR.",
            hint=(
                "Behind a reverse proxy or CDN, REMOTE_ADDR is the proxy for every request, "
                "so ALL clients share ONE rate-limit bucket and a single busy site can 429 "
                "the entire customer base. Set SELAHCUE_TRUSTED_PROXY_COUNT to the number of "
                "proxies that append to X-Forwarded-For in front of this service (1 for a "
                "single reverse proxy, 2 for CDN -> load balancer). Do NOT set it higher than "
                "the real depth: the extra entries are caller-supplied and forgeable."
            ),
            id=SHARED_BUCKET_WARNING,
        )
    ]
