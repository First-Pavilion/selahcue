"""Project-bound Deepgram keys endpoint and redacted result parsing."""
from datetime import UTC, datetime
from urllib.parse import quote

from ..configuration import valid_id
from ..contracts import AdminOperation as Op, ProviderPartialIdentity, ProvisioningErrorCode as Error, SecretBytes
from . import transport
from .contracts import CleanupConfirmed, Created, InventoryPage, InventoryRecord, MutationUnknown, NotCreated, ReadFailed


def _matches(request, credential):
    return request.scope == credential.scope and request.scope.provider == "deepgram"


def _collection(scope):
    return f"/v1/projects/{quote(scope.parent_scope_id, safe='')}/keys"


def _decode(response):
    try:
        data = transport.loads(response.body)
        return data if type(data) is dict else {}
    except (UnicodeError, ValueError, RecursionError):
        return {}


def _id(value):
    return value if valid_id(value) else None


def _timestamp(value):
    try:
        if type(value) is str:
            parsed = datetime.fromisoformat(value)
            if parsed.utcoffset() is not None:
                return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        pass
    return None


def _secret(value):
    if type(value) is str and 0 < len(value) <= 4096 and all("!" <= item <= "~" for item in value):
        return SecretBytes(value.encode("ascii"))
    return None


def _not_sent_or_unknown(response, identity):
    if isinstance(response, transport._Failure):
        if response.phase == "before_http":
            return NotCreated(Error.TRANSPORT_NOT_SENT)
        return MutationUnknown(Error.OUTCOME_UNKNOWN, identity)
    if not 200 <= response.status < 300:
        return MutationUnknown(Error.OUTCOME_UNKNOWN, identity)
    return None


def mutate(request, credential):
    project = request.scope.parent_scope_id
    identity = ProviderPartialIdentity(request.scope, project, None, request.api_key_id)
    if (
        not _matches(request, credential) or request.project_id != project or request.service_account_id is not None
        or request.operation not in (Op.DG_CREATE_KEY, Op.DG_REVOKE_KEY)
    ):
        return NotCreated(Error.INVALID_CONTEXT)
    path = _collection(request.scope)
    if request.operation == Op.DG_REVOKE_KEY:
        if not valid_id(request.api_key_id):
            return NotCreated(Error.INVALID_CONTEXT)
        response = transport._send(transport._Operation("DELETE", f"{path}/{quote(request.api_key_id, safe='')}"), credential)
        failed = _not_sent_or_unknown(response, identity)
        return failed or (CleanupConfirmed(identity, response.request_id) if response.status == 200
                          else MutationUnknown(Error.RESPONSE_INVALID, identity))
    if request.api_key_id is not None:
        return NotCreated(Error.INVALID_CONTEXT)
    response = transport._send(transport._Operation(
        "POST", path, body={"comment": request.marker, "scopes": ["member"]},
    ), credential)
    failed = _not_sent_or_unknown(response, identity)
    if failed:
        return failed
    body = _decode(response)
    identity = ProviderPartialIdentity(request.scope, project, None, _id(body.get("api_key_id")))
    secret = _secret(body.get("key"))
    if not identity.api_key_id or not secret or "expiration_date" not in body:
        return MutationUnknown(Error.RESPONSE_INVALID, identity)
    expiry = body["expiration_date"]
    expires_at = _timestamp(expiry)
    if expiry is not None and expires_at is None:
        return MutationUnknown(Error.RESPONSE_INVALID, identity)
    return Created(identity, secret if expires_at is None else None, expires_at,
                   response.request_id, _timestamp(body.get("created")))


def list_page(request, credential):
    if (not _matches(request, credential) or request.collection != "DG_KEYS"
            or request.project_id not in (None, request.scope.parent_scope_id) or request.cursor is not None):
        return ReadFailed(Error.INVALID_CONTEXT)
    response = transport._send(transport._Operation("GET", _collection(request.scope)), credential)
    if not isinstance(response, transport._Response) or response.status != 200:
        return ReadFailed(Error.INVENTORY_UNAVAILABLE)
    rows = _decode(response).get("api_keys")
    if type(rows) is not list:
        return ReadFailed(Error.RESPONSE_INVALID)
    items = []
    for row in rows:
        item = row.get("api_key") if type(row) is dict else None
        if type(item) is not dict or not valid_id(item.get("api_key_id")):
            return ReadFailed(Error.RESPONSE_INVALID)
        items.append(InventoryRecord(
            item["api_key_id"], _id(item.get("comment")), _timestamp(item.get("created")),
            "expired" if item.get("is_expired") is True else "unknown", None,
        ))
    return InventoryPage(tuple(items), None, True)
