"""Server-to-server n8n callbacks; never use these from the marketing browser."""

import hmac
import json

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from selahcue_api.apps.pilot_downloads.policy import PilotRegistrationError, load_policy
from selahcue_api.apps.pilot_downloads.registration import RegistrationValidationError
from selahcue_api.apps.pilot_downloads.services import confirm_registration, reserve_registration
from selahcue_api.apps.throttling.decorators import throttle


MAX_BODY_BYTES = 32768


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


@throttle("pilot-registration", "SELAHCUE_THROTTLE_PILOT_REGISTRATION", (60, 60), fail_closed_on_store_unavailable=True)
def _authenticated_operation(request, operation, policy):
    if request.content_type != "application/json":
        raise PilotRegistrationError("json_required", 415)
    try:
        body = request.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise PilotRegistrationError("request_too_large", 413)
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except RequestDataTooBig:
        raise PilotRegistrationError("request_too_large", 413) from None
    except PilotRegistrationError:
        raise
    except (ValueError, UnicodeError):
        raise PilotRegistrationError("registration_invalid", 400) from None
    return JsonResponse(operation(payload, policy=policy))


def _dispatch(request, operation):
    try:
        if request.method != "POST":
            raise PilotRegistrationError("post_required", 405)
        policy = load_policy()
        supplied = request.headers.get("Authorization", "")
        expected = "Bearer " + policy.n8n_token
        if len(supplied) > 512 or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            raise PilotRegistrationError("server_auth_required", 403)
        response = _authenticated_operation(request, operation, policy)
        if response.status_code == 429:
            # The shared limiter's legacy envelope labels desktop operations.
            # Keep these server callbacks on their own small error contract.
            retry_after = response.get("Retry-After", "60")
            response = JsonResponse({"error": {"code": "registration_rate_limited"}}, status=429)
            response["Retry-After"] = retry_after
    except PilotRegistrationError as error:
        response = JsonResponse({"error": {"code": error.code}}, status=error.status)
    except RegistrationValidationError as error:
        response = JsonResponse({"error": {"code": "registration_invalid", "fields": error.fields}}, status=400)
    except DatabaseError:
        # Integrity/availability failures are retryable; no DB/PII error text escapes.
        response = JsonResponse({"error": {"code": "registration_temporarily_unavailable"}}, status=503)
    if response.status_code == 405:
        response["Allow"] = "POST"
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# CSRF exemption is limited to these server callbacks: no cookie/session/header-
# actor authentication or permissive CORS, and a dedicated secret is mandatory.
@csrf_exempt
def reserve(request):
    return _dispatch(request, reserve_registration)


@csrf_exempt
def confirm(request):
    return _dispatch(request, confirm_registration)
