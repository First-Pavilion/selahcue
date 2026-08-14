"""View glue for the throttle. Kept apart from services.py so the logic stays free of
HTTP and Django-cache concerns."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.core.cache import cache

from selahcue_api.apps.throttling.services import CacheStore, client_ip, should_allow
from selahcue_api.graphql.errors import ErrorCode
from selahcue_api.platform.responses import command_error_response


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
