"""Time-boxed public-beta plan grant for self-service churches (17tnw2bhkd2).

The beta plan code and its exclusive end come only from settings. Either being empty is the
off switch, so no plan code is hard-coded here. The grant sits on top of the normal Free
licence; it never touches licence issuance or renewal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.conf import settings

from selahcue_api.apps.catalogue.models import OrgPlanGrant, Plan

logger = logging.getLogger(__name__)

BETA_ACTOR = "system:beta"
BETA_REASON = "Public beta: all features until the beta end date"


def beta_window() -> tuple[Plan, datetime] | None:
    """Return (plan, exclusive end) when beta is configured and valid, else None. Never raises."""
    code = str(getattr(settings, "SELAHCUE_BETA_PLAN_CODE", "") or "").strip()
    raw_end = str(getattr(settings, "SELAHCUE_BETA_ENDS_AT", "") or "").strip()
    if not code or not raw_end:
        return None
    try:
        ends_at = datetime.fromisoformat(raw_end)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=UTC)
        plan = Plan.objects.filter(code=code).first()
    except Exception:
        logger.warning("Beta licensing is misconfigured and has been skipped.")
        return None
    if plan is None:
        logger.warning("Beta licensing is misconfigured and has been skipped.")
        return None
    return plan, ends_at


def ensure_beta_grant(org, *, at: datetime) -> OrgPlanGrant | None:
    """Create the org's single beta grant [at, ends_at); idempotent for the configured plan."""
    window = beta_window()
    if window is None:
        return None
    plan, ends_at = window
    existing = OrgPlanGrant.objects.filter(org=org, plan=plan).order_by("pk").first()
    if existing is not None:
        return existing
    if not at < ends_at:
        return None
    return OrgPlanGrant.objects.create(
        org=org, plan=plan, starts_at=at, ends_at=ends_at,
        granted_by_actor_id=BETA_ACTOR, reason=BETA_REASON,
    )
