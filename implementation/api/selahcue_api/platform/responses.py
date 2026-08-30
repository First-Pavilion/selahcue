"""Coded JSON error responses for the /v1 command surface.

Extracted out of `views.py` so the throttling decorator can build a 429 without importing
the view module: `views.py` imports `throttle`, and `decorators.py` needs
`command_error_response`, which would otherwise be a hard import cycle
(`views` → `decorators` → `views`, the second import landing on a half-initialised
module). This layer holds no view logic — only the code→status map and the payload shape.
"""

from __future__ import annotations

from django.http import JsonResponse

from selahcue_api.graphql.errors import ErrorCode, SAFE_MESSAGES
from selahcue_api.graphql.redaction import assert_no_restricted_payload_fields


# SafeAPIError renders itself only inside GraphQL; a plain /v1 Django view must translate its
# code to an HTTP status. No prior HTTP precedent — this map is the slice's documented choice.
_STATUS_BY_CODE = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.POLICY_DENIED: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.NOT_IMPLEMENTED: 501,
    # Not reachable from /v1 today — only `confirm_password_reset` raises it, on the GraphQL
    # account surface. It is here because the map must stay TOTAL over ErrorCode: `.get(code, 400)`
    # below silently absorbs a missing member, so the next code added would inherit a default
    # nobody chose. 400 happens to be right for this one; it will not always be.
    ErrorCode.PASSWORD_INVALID: 400,
    ErrorCode.INTERNAL: 500,
}


def command_error_response(*, code: ErrorCode, surface: str, operation: str) -> JsonResponse:
    """A safe, coded JSON error for a /v1 command, in the same shape as the not-implemented
    stub. Error payloads never carry secrets, so the redaction assertion is run over them."""
    payload = {
        "error": {"code": code.value, "message": SAFE_MESSAGES[code]},
        "surface": surface,
        "operation": operation,
    }
    assert_no_restricted_payload_fields(payload)
    return JsonResponse(payload, status=_STATUS_BY_CODE.get(code, 400))
