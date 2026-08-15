"""Transport-agnostic budget guard.

`decorators.throttle` wraps a Django VIEW: it reads the request, and it returns a `/v1`
JSON error response. A GraphQL mutation is neither — it is a resolver reached through one
shared view (`/graphql/account`), so a view decorator could only ever budget the whole
surface, not the one expensive field on it. Three options were on the table:

1. Decorate `AccountGraphQLView`. Rejected: one bucket for every account mutation means a
   burst of logins can exhaust the resend budget and vice versa, and the limit could not be
   keyed on the resend's own identity (the target address), which is the key that actually
   matters for mailbox flooding.
2. A Strawberry extension / field permission. Rejected as premature: it needs a resolver-name
   registry to decide which fields carry which budget, for exactly one field today.
3. THIS — call the same pure `should_allow` the /v1 throttle uses, from the service, and
   raise `SafeAPIError(RATE_LIMITED)` like any other policy failure. The limiter logic,
   store semantics and fail-open behaviour are shared with `/v1`; only the transport glue
   differs, which is precisely the part that had to differ.

Fails OPEN through `should_allow` (a Redis outage must not take the surface down), and
keeps the raise separate from the counting so callers can spend several budgets in order.
"""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

from selahcue_api.apps.throttling.services import BudgetOutcome, CacheStore, evaluate_budget
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


def spend_budget(
    scope: str, identity: str, setting_name: str, default: tuple[int, int]
) -> BudgetOutcome:
    """Spend one unit of `identity`'s `scope` budget and report the outcome.

    `identity` must never be raw PII: cache keys land in Redis and in slow-log output, so
    callers pass an HMAC fingerprint of an address rather than the address itself.

    Returning the outcome rather than a bool is what lets a caller distinguish a real allow
    from a fail-open. That matters wherever the guarded action is expensive or externally
    visible — sending email, say — because "the limiter is down" is not the same permission
    as "you are within your budget".
    """
    limit, window = getattr(settings, setting_name, default)
    return evaluate_budget(CacheStore(cache), f"throttle:{scope}:{identity}", limit, window)


def within_budget(scope: str, identity: str, setting_name: str, default: tuple[int, int]) -> bool:
    """`spend_budget` collapsed to a bool, fail-open. Unchanged semantics for /v1."""
    return spend_budget(scope, identity, setting_name, default) is not BudgetOutcome.DENIED


def enforce_budget(scope: str, identity: str, setting_name: str, default: tuple[int, int]) -> None:
    """`within_budget`, raising RATE_LIMITED instead of returning False."""
    if not within_budget(scope, identity, setting_name, default):
        raise SafeAPIError(ErrorCode.RATE_LIMITED)


def enforce_budget_reporting_outage(
    scope: str, identity: str, setting_name: str, default: tuple[int, int]
) -> bool:
    """`enforce_budget`, additionally reporting whether the limiter was actually consulted.

    Returns True when the budget could not be checked because the store is unavailable, so a
    caller with an expensive side effect can degrade that side effect while still returning
    its normal response.
    """
    outcome = spend_budget(scope, identity, setting_name, default)
    if outcome is BudgetOutcome.DENIED:
        raise SafeAPIError(ErrorCode.RATE_LIMITED)
    return outcome is BudgetOutcome.STORE_UNAVAILABLE
