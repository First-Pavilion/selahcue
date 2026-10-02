import json
import logging
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from selahcue_api.apps.accounts.services import (
    MAX_PASSWORD_LENGTH,
    LoginData,
    actor_from_session_token,
    login as _login_service,
)
from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    ActivateDeviceWithSessionData,
    activate_device as _activate_device_service,
    activate_device_with_session as _activate_device_with_session_service,
    refresh_license as _refresh_license_service,
)
from selahcue_api.apps.entitlements.services import (
    build_entitlement_manifest as _entitlement_manifest_service,
)
from selahcue_api.apps.entitlements.signing import SigningKeyUnavailable
from selahcue_api.apps.throttling.decorators import throttle
from selahcue_api.graphql.errors import ErrorCode, SAFE_MESSAGES, SafeAPIError
from selahcue_api.graphql.redaction import assert_no_restricted_payload_fields

# Lives in `responses.py` so the throttle decorator can build a 429 without importing this
# module back (that cycle is real: this module imports `throttle` at module scope). Re-exported
# here because `command_error_response` has always been part of this module's surface.
from selahcue_api.platform.responses import command_error_response

logger = logging.getLogger(__name__)


def not_implemented_payload(*, surface: str, operation: str) -> dict:
    payload = {
        "error": {
            "code": ErrorCode.NOT_IMPLEMENTED.value,
            "message": SAFE_MESSAGES[ErrorCode.NOT_IMPLEMENTED],
        },
        "surface": surface,
        "operation": operation,
    }
    assert_no_restricted_payload_fields(payload)
    return payload


def not_implemented_response(*, surface: str, operation: str) -> JsonResponse:
    return JsonResponse(not_implemented_payload(surface=surface, operation=operation), status=501)


@csrf_exempt
@require_POST
# Below the method decorators on purpose: a 405 must not consume throttle budget.
@throttle("activation", "SELAHCUE_THROTTLE_ACTIVATION", (10, 60))
def activate_device(request):
    """POST /v1/activations — register an account-bound device instance for a presented
    enrollment key and return a show-once device token (DEC-004). Authenticated by the
    presented key (`app_key_then_device_token`); the device is its own actor."""
    try:
        raw = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return command_error_response(
            code=ErrorCode.VALIDATION_FAILED, surface="desktop", operation="activation"
        )
    if not isinstance(raw, dict):
        return command_error_response(
            code=ErrorCode.VALIDATION_FAILED, surface="desktop", operation="activation"
        )

    data = ActivateDeviceData(
        idempotency_key=str(raw.get("idempotency_key") or ""),
        presented_key=str(raw.get("license_key") or ""),
        device_fingerprint=str(raw.get("device_fingerprint") or ""),
        platform=str(raw.get("platform") or ""),
        app_version=str(raw.get("app_version") or ""),
        display_name=str(raw.get("display_name") or ""),
    )
    try:
        result = _activate_device_service(data)
    except SafeAPIError as error:
        return command_error_response(
            code=error.code, surface="desktop", operation="activation"
        )

    return JsonResponse(_activation_payload(result, operation="activation"), status=200)


def _activation_payload(result, *, operation: str) -> dict:
    """The success body shared by both activation routes, so the desktop parses one shape
    whichever credential it activated with."""
    token = result.device_token
    # Success payload: the full token is the ONE legitimate place a device token leaves the
    # system (show-once), so this payload is deliberately NOT run through the redaction assertion.
    return {
        "created": result.created,
        # True when an existing device was issued a REPLACEMENT token (its own was expired or
        # revoked). The client should overwrite whatever it had cached: the old one is now
        # REVOKED, not merely stale.
        "reminted": result.reminted,
        # None only when the device already holds a usable token (show-once replay).
        "activation_token": result.full_token,
        "device": {
            "device_public_id": result.device.device_public_id,
            "status": result.device.status,
            "platform": result.device.platform,
        },
        "token": {
            "masked": token.masked_token if token else None,
            "prefix": token.token_prefix if token else None,
            "suffix": token.token_suffix if token else None,
            "fingerprint": token.token_fingerprint if token else None,
            "expires_at": token.expires_at.isoformat() if token else None,
        },
        "license": {
            "status": result.license_key.status,
            "expires_at": result.license_key.expires_at.isoformat(),
        },
        "surface": "desktop",
        "operation": operation,
    }


# --- Native-client account sign-in (86ak5t1gw, ADR-0029) -------------------------------------
#
# The two views below are `csrf_exempt` and that is SOUND only because of three properties, each
# pinned by `tests/test_native_account_surface.py`. Break one and the exemption stops being safe:
#
#   1. They read the account session from the `Authorization` header ONLY. The browser surface
#      (`graphql/context.py::_read_account_session_token`) also falls back to the
#      `selahcue_account_session` cookie, and that cookie is exactly the ambient credential CSRF
#      protection exists for. Nothing here may call that function or read `request.COOKIES`.
#   2. They never set a cookie, so a forged cross-site sign-in leaves nothing in the victim's
#      browser (login-CSRF) and the response is unreadable cross-origin anyway.
#   3. They require `Content-Type: application/json`, which a cross-site HTML form cannot send
#      without a CORS preflight (and this API emits no CORS headers). That check sits ABOVE the
#      throttle (`_json_content_type_only`), so a forged simple POST neither reaches the
#      credential check nor spends the victim network's per-IP budget.
#
# `/graphql/account` is deliberately NOT exempted and is unchanged: it authenticates from that
# cookie, so for it the CSRF check is load-bearing.

NATIVE_AUDIT_SURFACE = "desktop_v1"
# RFC 5321's mailbox limit; also `EmailField`'s default `max_length`.
_MAX_EMAIL_LENGTH = 254


def _json_content_type_only(operation: str):
    """Refuse anything not declared `application/json` — property 3 above.

    A string comparison on a header: no database, no cache, no budget. It is applied OUTSIDE
    `@throttle` on purpose. A cross-site HTML form can send `text/plain` or
    `application/x-www-form-urlencoded` without a preflight; if the refusal came after the
    throttle, every such forged POST would spend the victim network's per-IP budget although it
    can never reach a credential check, and a hostile page could lock real sign-ins out."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.content_type != "application/json":
                return _no_store(
                    command_error_response(
                        code=ErrorCode.VALIDATION_FAILED, surface="desktop", operation=operation
                    )
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def _json_object(request) -> dict | None:
    """The body as a JSON object, or None if it is anything else.

    `RecursionError` is caught with the parse errors: ~1.3 MB of `[` fits under Django's 2.5 MB
    body cap and recurses the parser past the interpreter limit, which would otherwise surface
    as a 500 on an unauthenticated route."""
    try:
        raw = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return raw if isinstance(raw, dict) else None


def _is_bounded_text(value: object, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _no_store(response):
    """These responses carry (or sit next to) a show-once credential; no cache may keep one."""
    response["Cache-Control"] = "no-store"
    return response


def _bearer_from_header(request) -> str | None:
    """The token in `Authorization: Bearer <token>`, or None when the header is not a bearer
    credential at all. An empty token is `""`, which is not the same answer as None.

    The auth-scheme is case-insensitive (RFC 7235). This is deliberately NOT shared with the
    browser reader (`graphql/context.py::_read_account_session_token`), which is case-sensitive
    and also falls back to a cookie."""
    auth = request.headers.get("Authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return None


def _account_session_bearer(request) -> str:
    """The account session token from `Authorization: Bearer <token>`, or "" when absent.

    The ONLY source a native route reads a session from (property 1 above). Unlike
    `_device_bearer_token` there is no JSON-body fallback either: a credential in a body that a
    cross-site form can author is not a credential.
    """
    return _bearer_from_header(request) or ""


@csrf_exempt
@require_POST
# Both guards below `require_POST` on purpose: a 405 must not consume budget. The content-type
# check sits ABOVE the throttle for the reason in `_json_content_type_only`. The throttle is the
# app-level per-IP limit the browser login mutation does not carry; the durable per-account
# lockout lives in `login` itself and therefore applies here exactly as it does there.
@_json_content_type_only("session_login")
@throttle("session_login", "SELAHCUE_THROTTLE_SESSION_LOGIN", (10, 60))
def create_session(request):
    """POST /v1/sessions — exchange an account email + password for an account session token, for
    a native client that cannot take part in the browser CSRF ceremony (DEC-011 pt 3).

    Same `login` service as the GraphQL mutation, so the no-enumeration collapse (unknown email
    and wrong password are indistinguishable), the unverified-account rule and the per-account
    lockout are inherited, not re-implemented. Differs in transport only: bearer-out, no cookie."""
    raw = _json_object(request)
    email = raw.get("email") if raw is not None else None
    password = raw.get("password") if raw is not None else None
    if not (_is_bounded_text(email, _MAX_EMAIL_LENGTH) and _is_bounded_text(password, MAX_PASSWORD_LENGTH)):
        return _no_store(
            command_error_response(
                code=ErrorCode.VALIDATION_FAILED, surface="desktop", operation="session_login"
            )
        )
    try:
        result = _login_service(
            LoginData(email=email, password=password), source_surface=NATIVE_AUDIT_SURFACE
        )
    except SafeAPIError as error:
        return _no_store(
            command_error_response(code=error.code, surface="desktop", operation="session_login")
        )
    payload = {
        # The one place the session token leaves the system (show-once).
        "session_token": result.session_token,
        "expires_at": result.expires_at,
        "role": result.role,
        "org_id": result.org_id,
        "surface": "desktop",
        "operation": "session_login",
    }
    # Nothing here is a credential but the token, and `session_token` is not on the denylist;
    # this guards against a future field (a hash, a password echo) being added to the payload.
    assert_no_restricted_payload_fields(payload)
    return _no_store(JsonResponse(payload, status=200))


@csrf_exempt
@require_POST
@_json_content_type_only("activation_with_session")
@throttle("activation_with_session", "SELAHCUE_THROTTLE_ACTIVATION", (10, 60))
def activate_device_with_session(request):
    """POST /v1/activations:with-session — register a device for the signed-in administrator's
    organisation, authenticated by `Authorization: Bearer <account session token>` (DEC-005).

    Same service, same instance limit, same show-once device token as the GraphQL
    `activateDeviceWithSession`; the body is `POST /v1/activations` minus `license_key`, and the
    response is that route's shape. Its own throttle bucket (same budget): the enrollment-key
    path must not be able to starve the primary one."""
    raw = _json_object(request)
    if raw is None:
        return _no_store(
            command_error_response(
                code=ErrorCode.VALIDATION_FAILED,
                surface="desktop",
                operation="activation_with_session",
            )
        )
    actor = actor_from_session_token(_account_session_bearer(request))
    data = ActivateDeviceWithSessionData(
        idempotency_key=str(raw.get("idempotency_key") or ""),
        device_fingerprint=str(raw.get("device_fingerprint") or ""),
        platform=str(raw.get("platform") or ""),
        app_version=str(raw.get("app_version") or ""),
        display_name=str(raw.get("display_name") or ""),
    )
    try:
        result = _activate_device_with_session_service(
            actor, data, source_surface=NATIVE_AUDIT_SURFACE
        )
    except SafeAPIError as error:
        return _no_store(
            command_error_response(
                code=error.code, surface="desktop", operation="activation_with_session"
            )
        )
    return _no_store(
        JsonResponse(_activation_payload(result, operation="activation_with_session"), status=200)
    )


def _device_bearer_token(request) -> str:
    """The device token from `Authorization: Bearer <token>`, falling back to a JSON body
    `{"device_token": ...}`. Returns "" when absent (→ UNAUTHENTICATED downstream)."""
    header_token = _bearer_from_header(request)
    if header_token is not None:
        return header_token
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return ""
    if isinstance(body, dict):
        return str(body.get("device_token") or "")
    return ""


@csrf_exempt
@require_POST
@throttle("license_refresh", "SELAHCUE_THROTTLE_DEVICE_READ", (60, 60))
def refresh_license(request):
    """POST /v1/license:refresh — an authenticated device reads its current license/entitlement
    status to refresh its cached offline entitlement (DEC-004). Pure read; device-token auth."""
    try:
        result = _refresh_license_service(_device_bearer_token(request))
    except SafeAPIError as error:
        return command_error_response(
            code=error.code, surface="desktop", operation="license_refresh"
        )
    payload = {
        "device": {
            "device_public_id": result.device_public_id,
            "status": result.device_status,
        },
        "license": {
            "status": result.license_status,
            "starts_at": result.license_starts_at,
            "expires_at": result.license_expires_at,
            "valid_now": result.license_valid_now,
        },
        "instances": {"used": result.instances_used, "limit": result.instances_limit},
        "token": {"expires_at": result.token_expires_at},
        "entitlement": {
            "feature_scope": result.feature_scope,
            "territory": result.territory,
        },
        "surface": "desktop",
        "operation": "license_refresh",
    }
    # Refresh returns only status (no token material), so — unlike the activation payload — it is
    # safe to run the redaction guard as defense-in-depth against a future field addition.
    assert_no_restricted_payload_fields(payload)
    return JsonResponse(payload, status=200)


@require_GET
@throttle("entitlement_manifest", "SELAHCUE_THROTTLE_DEVICE_READ", (60, 60))
def entitlement_manifest(request):
    """GET /v1/entitlements/manifest — the signed, device-bound, time-boxed offline
    entitlement (DEC-004). Device-token auth; pure read.

    The response IS the envelope: its `payload` is an opaque base64url string the client
    must verify BEFORE decoding. Do not re-serialize the decoded JSON and verify against
    that — the signature covers the transmitted bytes."""
    try:
        result = _entitlement_manifest_service(_device_bearer_token(request))
    except SafeAPIError as error:
        return command_error_response(
            code=error.code, surface="desktop", operation="entitlement_manifest"
        )
    except SigningKeyUnavailable:
        # Misconfiguration, not a client error. Loud in the log, silent to the caller —
        # and never an unsigned manifest as a fallback.
        logger.exception(
            "entitlement signing key unavailable; refusing to issue a manifest"
        )
        return command_error_response(
            code=ErrorCode.INTERNAL, surface="desktop", operation="entitlement_manifest"
        )
    payload = {
        **result.envelope,
        "surface": "desktop",
        "operation": "entitlement_manifest",
    }
    # Defense in depth over the envelope's own fields only. The signed payload was already
    # checked as a mapping inside the service — the one layer that can actually see it.
    assert_no_restricted_payload_fields(payload)
    return JsonResponse(payload, status=200)


@csrf_exempt
@require_POST
def download_prepare_not_implemented(request):
    return not_implemented_response(surface="desktop", operation="download_prepare")


@csrf_exempt
@require_POST
def download_complete_not_implemented(request, lease_id: str):
    return not_implemented_response(surface="desktop", operation="download_complete")


@csrf_exempt
@require_POST
def usage_events_not_implemented(request):
    return not_implemented_response(surface="desktop", operation="usage_events")


@csrf_exempt
@require_POST
def billing_webhook_not_implemented(request, provider: str):
    return not_implemented_response(surface="billing_provider", operation="billing_webhook")
