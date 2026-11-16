"""Fixed Deepgram request-list profile with typed metadata projection."""
from datetime import UTC, datetime
import re

from selahcue_api.apps.providers.contracts import ProviderScope
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.observation_contracts import (
    DGCompletion, DeepgramRequestObservation, UsageFailureCode as Code, UsagePage,
    UsagePageReceipt, UsageProfile,
)

from .usage_child import dg_page
from .usage_transport import (
    array_value, counter, exact_duration, invalid, object_value, optional_id, read_metadata,
)

_PROFILE = UsageProfile.DG_LISTEN_V1
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def _timestamp(value):
    if type(value) is not str or not _TIMESTAMP.fullmatch(value):
        invalid()
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError, OverflowError):
        invalid()


def _record(item, scope, interval):
    item = object_value(item)
    request_id = optional_id(item.get("request_id"))
    if request_id is None:
        invalid()
    created = _timestamp(item.get("created"))
    if not interval.start <= created <= interval.end:
        invalid()
    if created == interval.end:
        return None
    project = optional_id(item.get("project_uuid"))
    key = optional_id(item.get("api_key_id"))
    if project is not None and project != scope.parent_scope_id:
        invalid(Code.IDENTITY_CONFLICT)
    response = {} if item.get("response") is None else object_value(item["response"])
    details = {} if response.get("details") is None else object_value(response["details"])
    completed = None if response.get("completed") is None else _timestamp(response["completed"])
    if completed is not None and completed < created:
        invalid()
    code = response.get("code")
    if code is not None:
        code = counter(code, allow_decimal=True, maximum=599)
        if code < 100:
            invalid()
    duration = None if details.get("duration") is None else exact_duration(details["duration"])
    return DeepgramRequestObservation(
        request_id, project, key, created,
        DGCompletion.COMPLETE if completed is not None else DGCompletion.COMPLETION_UNKNOWN,
        completed, duration, code,
    )


def _parse_page(data, scope, interval, cursor):
    try:
        requested = dg_page(cursor)
    except ValueError:
        invalid(Code.INVALID_CURSOR)
    if (
        counter(data.get("page"), allow_decimal=True) != requested
        or counter(data.get("limit"), allow_decimal=True) != 100
    ):
        invalid()
    entries = array_value(data.get("requests"))
    if len(entries) > 100:
        invalid()
    following = None
    if len(entries) == 100:
        if requested == 2**63 - 1:
            invalid(Code.INVALID_CURSOR)
        following = str(requested + 1)
    records = []
    for item in entries:
        record = _record(item, scope, interval)
        if record is not None:
            records.append(record)
    return UsagePage(
        tuple(records), following, UsagePageReceipt(scope, interval, _PROFILE, cursor, following is None),
    )


def read_usage_page(scope: ProviderScope, interval: UTCInterval, cursor: str | None) -> UsagePage:
    if scope.provider != "deepgram":
        invalid(Code.SCOPE_MISSING)
    return _parse_page(read_metadata(scope, interval, cursor, _PROFILE), scope, interval, cursor)
