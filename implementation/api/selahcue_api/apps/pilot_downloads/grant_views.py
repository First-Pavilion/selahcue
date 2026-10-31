"""Dedicated n8n server grant callback; neither cookies nor devices authorize it."""

import hmac
import json

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from selahcue_api.apps.pilot_downloads.grant_manifest import unique_object
from selahcue_api.apps.pilot_downloads.grants import grant_download, load_grant_policy
from selahcue_api.apps.pilot_downloads.policy import PilotRegistrationError
from selahcue_api.apps.throttling.decorators import throttle


MAX_BODY_BYTES = 8192


@throttle("pilot-download-grant", "SELAHCUE_THROTTLE_PILOT_DOWNLOAD_GRANT", (30, 60), fail_closed_on_store_unavailable=True)
def _authenticated_operation(request, policy):
    if request.content_type != "application/json":
        raise PilotRegistrationError("json_required", 415)
    try:
        body = request.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise PilotRegistrationError("request_too_large", 413)
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object)
    except RequestDataTooBig:
        raise PilotRegistrationError("request_too_large", 413) from None
    except PilotRegistrationError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise PilotRegistrationError("download_request_invalid", 400) from None
    return JsonResponse(grant_download(payload, policy=policy))


@csrf_exempt
def grant(request):
    try:
        if request.method != "POST":
            raise PilotRegistrationError("post_required", 405)
        policy = load_grant_policy()
        supplied = request.headers.get("Authorization", "")
        try:
            authorized = len(supplied) <= 512 and hmac.compare_digest(supplied.encode("utf-8"), ("Bearer " + policy.n8n_token).encode("utf-8"))
        except UnicodeError:
            authorized = False
        if not authorized:
            raise PilotRegistrationError("server_auth_required", 403)
        response = _authenticated_operation(request, policy)
        if response.status_code in (429, 503):
            retry_after = response.get("Retry-After", "60")
            code = "download_rate_limited" if response.status_code == 429 else "downloads_temporarily_unavailable"
            response = JsonResponse({"error": {"code": code}}, status=response.status_code)
            response["Retry-After"] = retry_after
    except PilotRegistrationError as error:
        response = JsonResponse({"error": {"code": error.code}}, status=error.status)
    except DatabaseError:
        response = JsonResponse({"error": {"code": "downloads_temporarily_unavailable"}}, status=503)
    if response.status_code == 405:
        response["Allow"] = "POST"
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
