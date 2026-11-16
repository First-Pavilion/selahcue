"""Fixed, hourly OpenAI usage grouping without content or customer charges."""
from dataclasses import fields
from datetime import UTC, datetime, timedelta
import unicodedata

from selahcue_api.apps.providers.contracts import ProviderScope
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.observation_contracts import (
    OpenAIBucketDimensions, OpenAIBucketMetrics, OpenAIUsageBucketObservation,
    UsageFailureCode as Code, UsagePage, UsagePageReceipt, UsageProfile,
)

from .usage_child import valid_cursor
from .usage_transport import array_value, counter, invalid, object_value, optional_id, read_metadata

_PROFILE = UsageProfile.OA_COMPLETIONS_1H_V1


def _hour(value):
    if type(value) is not int or value % 3600:
        invalid()
    try:
        return datetime.fromtimestamp(value, UTC)
    except (ValueError, OverflowError, OSError):
        invalid()


def _result(item, start, end):
    item = object_value(item)
    if item.get("object") != "organization.usage.completions.result":
        invalid()
    model = item.get("model")
    if model is not None and (
        type(model) is not str or not 1 <= len(model) <= 256
        or any(unicodedata.category(c) in ("Cc", "Cs") for c in model)
    ):
        invalid()
    batch = item.get("batch")
    if batch is not None and type(batch) is not bool:
        invalid()
    values = {}
    for field in fields(OpenAIBucketMetrics):
        value = item.get(field.name)
        values[field.name] = None if value is None else counter(value)
    for cached, total in (
        ("input_cached_tokens", "input_tokens"),
        ("input_cached_audio_tokens", "input_audio_tokens"),
    ):
        if values[cached] is not None and values[total] is not None and values[cached] > values[total]:
            invalid()
    return OpenAIUsageBucketObservation(
        start, end,
        OpenAIBucketDimensions(optional_id(item.get("project_id")), optional_id(item.get("api_key_id")), model, batch),
        OpenAIBucketMetrics(**values),
    )


def _parse_page(data, scope, interval, cursor):
    more, following = data.get("has_more"), data.get("next_page")
    if data.get("object") != "page" or type(more) is not bool or "next_page" not in data:
        invalid()
    if (
        (more and (not valid_cursor(following) or following == cursor))
        or (not more and following is not None)
    ):
        invalid(Code.INVALID_CURSOR)
    buckets = array_value(data.get("data"))
    if len(buckets) > 24:
        invalid()
    records, starts = [], set()
    for bucket in buckets:
        bucket = object_value(bucket)
        start, end = _hour(bucket.get("start_time")), _hour(bucket.get("end_time"))
        if (
            bucket.get("object") != "bucket" or end - start != timedelta(hours=1)
            or start in starts or not interval.start <= start < end <= interval.end
        ):
            invalid()
        starts.add(start)
        for item in array_value(bucket.get("results")):
            if len(records) == 1000:
                invalid()
            records.append(_result(item, start, end))
    return UsagePage(
        tuple(records), following, UsagePageReceipt(scope, interval, _PROFILE, cursor, not more, tuple(sorted(starts))),
    )


def read_usage_page(scope: ProviderScope, interval: UTCInterval, cursor: str | None) -> UsagePage:
    if scope.provider != "openai":
        invalid(Code.SCOPE_MISSING)
    return _parse_page(read_metadata(scope, interval, cursor, _PROFILE), scope, interval, cursor)
