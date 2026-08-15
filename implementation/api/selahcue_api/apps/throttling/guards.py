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

from selahcue_api.apps.throttling.services import CacheStore, should_allow
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


def within_budget(scope: str, identity: str, setting_name: str, default: tuple[int, int]) -> bool:
    """True while `identity` is inside the `settings.<setting_name>` budget for `scope`.

    `identity` must never be raw PII: cache keys land in Redis and in slow-log output, so
    callers pass an HMAC fingerprint of an address rather than the address itself.
    """
    limit, window = getattr(settings, setting_name, default)
    return should_allow(CacheStore(cache), f"throttle:{scope}:{identity}", limit, window)


def enforce_budget(scope: str, identity: str, setting_name: str, default: tuple[int, int]) -> None:
    """`within_budget`, raising RATE_LIMITED instead of returning False."""
    if not within_budget(scope, identity, setting_name, default):
        raise SafeAPIError(ErrorCode.RATE_LIMITED)
