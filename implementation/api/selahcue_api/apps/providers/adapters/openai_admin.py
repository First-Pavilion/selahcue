"""Organization-bound OpenAI projects and combined service account/key operations."""
from datetime import UTC, datetime
from urllib.parse import quote

from ..configuration import valid_id
from ..contracts import AdminOperation as Op, ProviderPartialIdentity, ProvisioningErrorCode as Error
from . import transport
from .contracts import CleanupConfirmed, Created, InventoryPage, InventoryRecord, MutationUnknown, NotCreated, ReadFailed
from .deepgram_admin import _decode, _id, _not_sent_or_unknown, _secret

PROJECTS = "/v1/organization/projects"


def _matches(request, credential):
    return request.scope == credential.scope and request.scope.provider == "openai"


def _part(value):
    return quote(value, safe="")


def _timestamp(value):
    if type(value) is int and value >= 0:
        try:
            return datetime.fromtimestamp(value, UTC)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _operation(request):
    op = request.operation
    if op == Op.OA_CREATE_PROJECT and (request.project_id, request.service_account_id, request.api_key_id) == (None, None, None):
        return transport._Operation("POST", PROJECTS, body={"name": request.marker})
    if not valid_id(request.project_id):
        return None
    path = f"{PROJECTS}/{_part(request.project_id)}"
    if op == Op.OA_CREATE_SERVICE_ACCOUNT_KEY and request.service_account_id is None and request.api_key_id is None:
        return transport._Operation("POST", f"{path}/service_accounts", body={"name": request.marker})
    if op == Op.OA_REVOKE_KEY and valid_id(request.api_key_id) and valid_id(request.service_account_id):
        return transport._Operation("DELETE", f"{path}/api_keys/{_part(request.api_key_id)}")
    if op == Op.OA_DELETE_SERVICE_ACCOUNT and valid_id(request.service_account_id):
        return transport._Operation("DELETE", f"{path}/service_accounts/{_part(request.service_account_id)}")
    if op == Op.OA_ARCHIVE_PROJECT:
        return transport._Operation("POST", f"{path}/archive")
    return None


def mutate(request, credential):
    operation = _operation(request) if _matches(request, credential) else None
    if operation is None:
        return NotCreated(Error.INVALID_CONTEXT)
    response = transport._send(operation, credential)
    identity = ProviderPartialIdentity(request.scope, request.project_id, request.service_account_id, request.api_key_id)
    failed = _not_sent_or_unknown(response, identity)
    if failed:
        return failed
    body = _decode(response)
    op = request.operation
    if op == Op.OA_CREATE_PROJECT:
        identity = ProviderPartialIdentity(request.scope, _id(body.get("id")), None, None)
        if identity.project_id and body.get("object") == "organization.project":
            return Created(identity, None, None, response.request_id, _timestamp(body.get("created_at")))
    elif op == Op.OA_CREATE_SERVICE_ACCOUNT_KEY:
        key = body.get("api_key")
        key = key if type(key) is dict else {}
        account = _id(body.get("id"))
        identity = ProviderPartialIdentity(request.scope, request.project_id, account, _id(key.get("id")) if account else None)
        secret = _secret(key.get("value"))
        if account and identity.api_key_id and secret and "expires_at" in key and body.get("object") == "organization.project.service_account":
            expiry = key["expires_at"]
            expires_at = _timestamp(expiry)
            if expiry is None or expires_at is not None:
                return Created(identity, secret if expires_at is None else None, expires_at,
                               response.request_id, _timestamp(body.get("created_at")))
    elif _cleanup_confirmed(request, body):
        return CleanupConfirmed(identity, response.request_id)
    return MutationUnknown(Error.RESPONSE_INVALID, identity)


def _cleanup_confirmed(request, body):
    op = request.operation
    if op == Op.OA_REVOKE_KEY:
        return body.get("id") == request.api_key_id and body.get("deleted") is True
    if op == Op.OA_DELETE_SERVICE_ACCOUNT:
        return (body.get("object") == "organization.project.service_account.deleted"
                and body.get("id") == request.service_account_id and body.get("deleted") is True)
    return (op == Op.OA_ARCHIVE_PROJECT and body.get("object") == "organization.project"
            and body.get("id") == request.project_id and body.get("status") == "archived"
            and _timestamp(body.get("archived_at")) is not None)


def list_page(request, credential):
    if not _matches(request, credential) or (request.cursor is not None and not valid_id(request.cursor)):
        return ReadFailed(Error.INVALID_CONTEXT)
    query = {"limit": 100}
    if request.cursor is not None:
        query["after"] = request.cursor
    if request.collection == "OA_PROJECTS" and request.project_id is None:
        path = PROJECTS
        query["include_archived"] = "true"
    elif request.collection in ("OA_KEYS", "OA_SERVICE_ACCOUNTS") and valid_id(request.project_id):
        path = f"{PROJECTS}/{_part(request.project_id)}"
        if request.collection == "OA_KEYS":
            path += "/api_keys"
            query["owner_project_access"] = "any"
        else:
            path += "/service_accounts"
    else:
        return ReadFailed(Error.INVALID_CONTEXT)
    response = transport._send(transport._Operation("GET", path, query), credential)
    if not isinstance(response, transport._Response) or response.status != 200:
        return ReadFailed(Error.INVENTORY_UNAVAILABLE)
    body = _decode(response)
    more = body.get("has_more")
    rows = body.get("data")
    if type(rows) is not list or len(rows) > 100 or type(more) is not bool:
        return ReadFailed(Error.RESPONSE_INVALID)
    next_cursor = body.get("last_id") if more else None
    if more and (not valid_id(next_cursor) or next_cursor == request.cursor or not rows):
        return ReadFailed(Error.RESPONSE_INVALID)
    records = []
    for row in rows:
        if type(row) is not dict or not valid_id(row.get("id")):
            return ReadFailed(Error.RESPONSE_INVALID)
        owner = row.get("owner")
        account = owner.get("service_account") if type(owner) is dict and owner.get("type") == "service_account" else None
        status = row.get("status")
        marker = _id(row.get("name")) if request.collection != "OA_KEYS" else None
        records.append(InventoryRecord(
            row["id"], marker, _timestamp(row.get("created_at")),
            status if status in ("active", "archived", "expired") else "unknown",
            _id(account.get("id")) if type(account) is dict else None,
        ))
    if more and records[-1].external_id != next_cursor:
        return ReadFailed(Error.RESPONSE_INVALID)
    return InventoryPage(tuple(records), next_cursor, not more)
