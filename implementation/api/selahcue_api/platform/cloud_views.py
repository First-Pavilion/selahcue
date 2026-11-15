"""Header-authenticated native cloud commands with explicit wire serialization."""
from dataclasses import replace
import re
from uuid import UUID

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from selahcue_api.apps.devices.services import authenticate_device_token
from selahcue_api.apps.providers.adapters.grants_child import strict_object
from selahcue_api.apps.providers.contracts import SessionFailureCode, SessionRejected, SessionResult
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.providers.sessions import _defaults, _issue_stt_session, validate_session_request
from selahcue_api.apps.providers.stt_audit import wire_time
from selahcue_api.apps.providers.stt_policy import STT_MINT_POLICY, get_stt_policy_versions
from selahcue_api.apps.throttling.cloud import evaluate_cloud_budget
from selahcue_api.apps.throttling.services import BudgetOutcome
from selahcue_api.apps.usage.contracts import SessionRequest
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.services import remaining
from selahcue_api.apps.usage.weeks import utc_instant
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

from .cloud_contracts import CloudPolicies, QuotaEnvelope
from .responses import command_error_response
from .views import _bearer_from_header, _no_store

_MAX_BODY = 8192
_SESSION_KEYS = {"idempotency_key", "action", "socket", "consent_version", "policy_version"}


def _canonical_uuid(raw):
    if type(raw) is not str or len(raw) != 36:
        raise ValueError("Invalid UUID")
    ident = UUID(raw)
    if str(ident) != raw:
        raise ValueError("Invalid UUID")
    return ident


def _session_request(request):
    raw_length = request.META.get("CONTENT_LENGTH")
    if (
        request.content_type != "application/json" or "HTTP_TRANSFER_ENCODING" in request.META
        or "TRANSFER_ENCODING" in request.META
        or type(raw_length) is not str or re.fullmatch(r"[0-9]+", raw_length) is None
    ):
        raise ValueError("Unsupported request framing")
    digits = raw_length.lstrip("0")
    if len(digits) > 4 or int(digits or "0") > _MAX_BODY:
        raise ValueError("Request body too large")
    size = int(digits or "0")
    raw = bytearray()
    while len(raw) < size:
        chunk = request.read(min(size - len(raw), 4096))
        if not chunk or len(chunk) > size - len(raw):
            raise ValueError("Invalid framed body length")
        raw.extend(chunk)
    obj = strict_object(raw)
    action = obj.get("action")
    valid_keys = _SESSION_KEYS | {"previous_reservation_id"} if action == "renew" else _SESSION_KEYS
    if obj.keys() != valid_keys:
        raise ValueError("Invalid request fields")
    if any(type(value) is not str or re.search(r"[\ud800-\udfff]", value) for value in obj.values()):
        raise ValueError("Invalid request field")
    command = SessionRequest(
        _canonical_uuid(obj["idempotency_key"]), action,
        _canonical_uuid(obj["previous_reservation_id"]) if action == "renew" else None,
        obj["socket"], False, obj["consent_version"], obj["policy_version"],
    )
    validate_session_request(command)
    return command


def _error(operation, code, *, retry=None, method=None):
    response = command_error_response(
        code=ErrorCode(code.value), surface="desktop", operation=operation, allowed_method=method,
    )
    if retry is not None:
        response["Retry-After"] = str(retry)
    return _no_store(response)


def _authenticate(request):
    return authenticate_device_token(_bearer_from_header(request) or "")


def render_session_reply(result: SessionResult) -> JsonResponse:
    decision = result.decision
    if (
        type(decision.reservation_id) is not UUID or decision.state != "ISSUED"
        or not decision.authorized_from < decision.authorized_until or result.issued_at > result.server_time
    ):
        raise ValueError("Invalid STT authorization")
    payload = {
        "reservation_id": str(decision.reservation_id), "meter": "stt",
        "issued_at": wire_time(result.issued_at), "server_time": wire_time(result.server_time),
        "authorized_from": wire_time(decision.authorized_from), "authorized_until": wire_time(decision.authorized_until),
        "policy_version": result.policy_version,
    }
    grant = result.grant
    if grant is not None:
        if (
            grant.provider_kind != "deepgram" or grant.endpoint != STT_MINT_POLICY.endpoint
            or not 0 < len(grant.secret.value) <= 12288
            or not decision.authorized_from <= result.server_time < decision.authorized_until
            or grant.expires_at <= result.server_time
        ):
            raise ValueError("Invalid STT grant")
        credential = grant.secret.value.decode("ascii")
        if any(not 33 <= ord(character) <= 126 for character in credential):
            raise ValueError("Invalid STT credential")
        payload["provider"] = {
            "kind": grant.provider_kind, "endpoint": grant.endpoint,
            "credential": credential, "credential_expires_at": wire_time(grant.expires_at),
        }
    return _no_store(JsonResponse(payload))


@csrf_exempt
def stt_session(request):
    if request.method != "POST":
        return _error("stt_session", ErrorCode.VALIDATION_FAILED, method="POST")
    try:
        command = _session_request(request)
    except (ValueError, TypeError, OSError, RecursionError, SessionRejected):
        return _error("stt_session", ErrorCode.VALIDATION_FAILED)
    try:
        token = _authenticate(request)
        _, reply = _issue_stt_session(token, command, _defaults(timezone.now))
        return reply
    except SafeAPIError as error:
        return _error("stt_session", error.code)
    except SessionRejected as error:
        return _error("stt_session", error.code, retry=error.retry_after_seconds)
    except Exception:
        return _error("stt_session", ErrorCode.INTERNAL)


def _quota_envelope(token, at):
    org = token.device.customer
    stt, notes = remaining(org, at)
    mapping_id = ProviderCredential.objects.filter(
        org=org, provider="deepgram", state="ACTIVE",
    ).values_list("pk", flat=True).first()
    status = "not_initialized" if mapping_id is None else read_stt_readiness(
        org_id=org.pk, mapping_id=mapping_id, at=at,
    ).status
    return QuotaEnvelope(replace(stt, status=status), notes, CloudPolicies(get_stt_policy_versions(), None))


def _quota_snapshot(snapshot):
    return {
        "meter": snapshot.meter, "limit": snapshot.limit, "settled": snapshot.settled, "held": snapshot.held,
        "carried_debt": snapshot.carried_debt, "remaining": snapshot.remaining, "as_of": wire_time(snapshot.as_of),
        "resets_at": wire_time(snapshot.resets_at), "status": snapshot.status,
    }


@csrf_exempt
def cloud_quota(request):
    if request.method != "GET":
        return _error("quota", ErrorCode.VALIDATION_FAILED, method="GET")
    try:
        token = _authenticate(request)
        budget = evaluate_cloud_budget(org_id=token.device.customer_id, device_id=token.device_id, kind="quota")
        if budget.outcome is not BudgetOutcome.ALLOWED:
            return _error("quota", SessionFailureCode.RATE_LIMITED, retry=budget.retry_after_seconds)
        envelope = _quota_envelope(token, utc_instant(timezone.now()))
        stt_policy = envelope.policies.stt
        return _no_store(JsonResponse({
            "stt": _quota_snapshot(envelope.stt), "notes": _quota_snapshot(envelope.notes),
            "policies": {"stt": None if stt_policy is None else {
                "policy_version": stt_policy.policy_version, "consent_version": stt_policy.consent_version,
            }, "notes": None},
        }))
    except SafeAPIError as error:
        return _error("quota", error.code)
    except Exception:
        return _error("quota", ErrorCode.INTERNAL)
