"""Small, exact public projection; never serializes internal catalogue model fields.

The singleton cache has both a TTL and an effective-time deadline. Every read still
checks the database revision, and a cold read verifies that its projection did not
cross a catalogue write. Failed reads never serve stale data. Price history remains
in the database; only the latest current row for each configured pair is materialized.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import threading
import time

from django.db.models import F, Min, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from selahcue_api.apps.catalogue.currency_reference import currency_minor_units
from selahcue_api.apps.catalogue.models import CatalogueRevision, Plan, PlanGrant, PlanPrice, PriceInterval
from selahcue_api.graphql.context import has_control_characters
from selahcue_api.apps.catalogue.services import coerce_grant_value

MAX_PUBLIC_PLANS = 64
MAX_OFFERS_PER_PLAN = 128
MAX_PAYLOAD_BYTES = 1024 * 1024
CACHE_TTL_SECONDS = 30.0
PUBLIC_DIMENSIONS = {
    "cloud_transcript_minutes_per_week": "INTEGER",
    "sermon_notes_per_week": "INTEGER",
    "watermark": "BOOLEAN",
}


class CatalogueUnavailable(Exception):
    """Projection cannot truthfully describe the configured catalogue."""


def _revision():
    revision = CatalogueRevision.objects.filter(pk=CatalogueRevision.SINGLETON_PK).values_list("revision", flat=True).first()
    if revision is None:
        raise CatalogueUnavailable
    return revision


def _grant_value(grant):
    dimension = grant.dimension
    if not dimension.is_active or dimension.value_type != PUBLIC_DIMENSIONS[dimension.key]:
        raise CatalogueUnavailable
    value = coerce_grant_value(dimension.value_type, grant.raw_value)
    if dimension.value_type == "BOOLEAN" and type(value) is bool:
        return value
    if dimension.value_type == "INTEGER" and type(value) is int and value <= 9007199254740991:
        return value
    # Public weekly counts require an explicit finite, JSON-safe nonnegative integer.
    # Missing/unlimited/malformed entries must not become fabricated zero allowances.
    raise CatalogueUnavailable



def _text(value, max_length):
    if not value or len(value) > max_length or has_control_characters(value):
        raise CatalogueUnavailable
    return value


def _build(now):
    plans = list(Plan.objects.order_by("sort_order", "code")[:MAX_PUBLIC_PLANS + 1])
    if not plans or len(plans) > MAX_PUBLIC_PLANS:
        raise CatalogueUnavailable
    plan_ids = [plan.pk for plan in plans]
    grants = list(PlanGrant.objects.filter(plan_id__in=plan_ids, dimension__key__in=PUBLIC_DIMENSIONS)
        .select_related("dimension").order_by("plan_id", "dimension__key")[:MAX_PUBLIC_PLANS * 3 + 1])
    values = {pk: {} for pk in plan_ids}
    for grant in grants:
        values[grant.plan_id][grant.dimension.key] = _grant_value(grant)
    if any(set(value) != set(PUBLIC_DIMENSIONS) for value in values.values()):
        raise CatalogueUnavailable
    # Partition in SQL before LIMIT: arbitrarily long old history cannot crowd out
    # another pair's current offer. The existing composite index covers each partition.
    prices = list(PlanPrice.objects.filter(plan_id__in=plan_ids, effective_from__lte=now)
        .annotate(_position=Window(RowNumber(), partition_by=[F("plan_id"), F("currency"), F("interval")],
            order_by=F("effective_from").desc())).filter(_position=1)
        .order_by("plan_id", "currency", "interval")[:MAX_PUBLIC_PLANS * MAX_OFFERS_PER_PLAN + 1])
    if len(prices) > MAX_PUBLIC_PLANS * MAX_OFFERS_PER_PLAN:
        raise CatalogueUnavailable
    offers = {pk: [] for pk in plan_ids}
    for price in prices:
        exponent = currency_minor_units(price.currency)
        if (exponent is None or price.interval not in PriceInterval.values or
                (price.amount_minor is not None and not 0 <= price.amount_minor <= 9223372036854775807)):
            raise CatalogueUnavailable
        offers[price.plan_id].append({"currency": price.currency, "interval": price.interval,
            "price_state": "unpriced" if price.amount_minor is None else "priced",
            "amount_minor": None if price.amount_minor is None else str(price.amount_minor),
            "minor_unit_exponent": exponent})
        if len(offers[price.plan_id]) > MAX_OFFERS_PER_PLAN:
            raise CatalogueUnavailable
    next_effective = PlanPrice.objects.filter(plan_id__in=plan_ids, effective_from__gt=now).aggregate(next=Min("effective_from"))["next"]
    payload = {"plans": [{"key": _text(plan.code, 64), "name": _text(plan.display_name, 128),
        "price_state": "priced" if any(o["price_state"] == "priced" for o in offers[plan.pk]) else "unpriced",
        "offers": offers[plan.pk], **values[plan.pk]} for plan in plans]}
    wire = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(wire) > MAX_PAYLOAD_BYTES:
        raise CatalogueUnavailable
    return wire, next_effective


@dataclass(frozen=True)
class _Entry:
    revision: int
    wire: bytes
    stored_at: float
    observed_at: datetime
    next_effective: datetime | None


class PublicCatalogueCache:
    """Exactly one immutable projection, at most1MiB; request parameters never key it."""
    def __init__(self):
        self._entry = None
        self._lock = threading.Lock()

    def clear(self):
        with self._lock:
            self._entry = None

    def read(self):
        revision = _revision()  # Never return cached commercial data through a DB outage.
        with self._lock:
            now = timezone.now()
            tick = time.monotonic()
            entry = self._entry
            if (entry is not None and entry.revision == revision and
                    0 <= tick - entry.stored_at < CACHE_TTL_SECONDS and now >= entry.observed_at and
                    (entry.next_effective is None or now < entry.next_effective)):
                return entry.wire
            wire, next_effective = _build(now)
            if _revision() != revision:
                raise CatalogueUnavailable
            self._entry = _Entry(revision, wire, tick, now, next_effective)
            return wire


PUBLIC_CACHE = PublicCatalogueCache()
