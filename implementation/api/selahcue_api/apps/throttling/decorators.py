"""View glue for the throttle. Kept apart from services.py so the logic stays free of
HTTP and Django-cache concerns."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.core.cache import cache

from selahcue_api.apps.throttling.guards import report_native_denial
from selahcue_api.apps.throttling.services import (
    BudgetOutcome, CacheStore, client_ip, evaluate_budget, ip_bucket_identity,
)
from selahcue_api.graphql.errors import ErrorCode
from selahcue_api.platform.responses import command_error_response


def throttle(
    scope: str, setting_name: str, default: tuple[int, int], *,
    fail_closed_on_store_unavailable: bool = False,
):
    """Limit `scope` per client IP using the configured `(limit, window_seconds)` budget.

    Device routes retain fail-open availability. Native bootstrap login opts into refusing
    an unavailable budget before password work; this changes no store outcome or healthy limit.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            limit, window = getattr(settings, setting_name, default)
            key = f"throttle:{scope}:{ip_bucket_identity(client_ip(request))}"
            store = CacheStore(cache)
            outcome = evaluate_budget(store, key, limit, window)
            unavailable = outcome is BudgetOutcome.STORE_UNAVAILABLE
            if outcome is BudgetOutcome.DENIED or (unavailable and fail_closed_on_store_unavailable):
                report_native_denial(scope)
                response = command_error_response(
                    code=ErrorCode.RATE_LIMITED, surface="desktop", operation=scope
                )
                response["Cache-Control"] = "no-store"
                # A failed store has no reliable expiry metadata. Do not pay another
                # failed socket operation; a full-window hint is deliberately conservative.
                retry_after = max(1, int(window)) if unavailable else store.retry_after(key, window)
                response["Retry-After"] = str(retry_after)
                return response
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
