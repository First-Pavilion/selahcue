import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    activate_device as _activate_device_service,
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

    token = result.device_token
    # Success payload: the full token is the ONE legitimate place a device token leaves the
    # system (show-once), so this payload is deliberately NOT run through the redaction assertion.
    payload = {
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
        "operation": "activation",
    }
    return JsonResponse(payload, status=200)


def _device_bearer_token(request) -> str:
    """The device token from `Authorization: Bearer <token>`, falling back to a JSON body
    `{"device_token": ...}`. Returns "" when absent (→ UNAUTHENTICATED downstream)."""
    auth = request.headers.get("Authorization", "")
    # RFC 7235: the auth-scheme is case-insensitive.
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
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
