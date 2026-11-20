"""Resolve the ranked plan shared by org metering and signed entitlements."""

from datetime import datetime

from django.db.models import OuterRef, Q, Subquery

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.base_plan import _base_plan_for_license
from selahcue_api.apps.catalogue.contracts import EffectivePlan
from selahcue_api.apps.catalogue.models import (
    CatalogueRevision, GrantDimension, GrantValueType, OrgPlanGrant, Plan, PlanGrant,
)
from selahcue_api.apps.license_keys.selection import find_eligible_org_license

_STT_MINUTES = "cloud_transcript_minutes_per_week"
_NOTES = "sermon_notes_per_week"
_MAX_LEDGER_UNITS = 2**63 - 1


def _select_org_plan(org_id: int, at: datetime) -> tuple[Plan | None, str, datetime | None]:
    """(plan, source, ends_at). `ends_at` is the winning grant's end, and None unless a staff
    grant won: an early `ended_at` counts, since that is when the grant actually stops."""
    key = find_eligible_org_license(org_id, at)
    base = _base_plan_for_license(key) if key else Plan.objects.filter(is_fallback=True).first()
    grant = (
        OrgPlanGrant.objects.select_related("plan")
        .filter(org_id=org_id, starts_at__lte=at, ends_at__gt=at)
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gt=at))
        .order_by("-plan__rank", "-starts_at", "-pk")
        .first()
    )
    if grant is not None and (base is None or grant.plan.rank > base.rank):
        ends_at = grant.ends_at
        if grant.ended_at is not None and grant.ended_at < ends_at:
            ends_at = grant.ended_at
        return grant.plan, "staff_grant", ends_at
    return base, "license" if key and base and not base.is_fallback else "fallback", None


def _quota_units(value: str | None, multiplier: int) -> int | None:
    try:
        units = int(value) * multiplier
    except (ValueError, TypeError):
        return None
    return units if 0 <= units <= _MAX_LEDGER_UNITS else None


def effective_plan(org: CustomerOrg, at: datetime) -> EffectivePlan:
    """Read live plan/limits without caching a grant selection or any org data."""
    if at.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    plan, source, ends_at = _select_org_plan(org.pk, at)
    if plan is None:
        raise LookupError("No effective catalogue plan is configured")
    revision = CatalogueRevision.objects.filter(pk=CatalogueRevision.SINGLETON_PK).values_list(
        "revision", flat=True,
    ).first()
    plan_values = PlanGrant.objects.filter(plan=plan, dimension_id=OuterRef("pk")).values("raw_value")
    dimensions = GrantDimension.objects.filter(
        key__in=(_STT_MINUTES, _NOTES), is_active=True, value_type=GrantValueType.INTEGER,
    ).annotate(plan_value=Subquery(plan_values[:1]))
    quotas = {}
    for dimension in dimensions:
        multiplier = 60 if dimension.key == _STT_MINUTES else 1
        limit = _quota_units(dimension.plan_value, multiplier)
        if limit is None:
            limit = _quota_units(dimension.default_raw_value, multiplier)
        quotas[dimension.key] = limit or 0
    return EffectivePlan(
        plan.pk, plan.rank, revision or 0, quotas.get(_STT_MINUTES, 0),
        quotas.get(_NOTES, 0), source, ends_at,
    )
