"""The one device-instance limit every enforcement and reporting site reads (17tnw2bhkd2).

A licence's `device_limit` is copied from its plan at issuance and never moves afterwards. A
time-boxed plan grant (the public beta) raises a church's plan without touching the licence,
so the number activation enforces is the larger of the two: the licence's own seats, or the
seats the winning grant's plan gives at this instant. When the grant ends the plan value
drops back and the licence's own number applies again.

Activation (new-device refusal), the re-mint allowance, `/v1/license:refresh` and the signed
manifest's `instances_limit` all call this, so the four can never disagree about one quantity.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db import transaction

from selahcue_api.apps.catalogue.org_plans import _select_org_plan
from selahcue_api.apps.catalogue.services import plan_device_instances_for_issuance
from selahcue_api.apps.license_keys.models import AppLicenseKey

logger = logging.getLogger(__name__)


def effective_device_limit(license_key: AppLicenseKey, at: datetime) -> int:
    """max(the licence's `device_limit`, the winning plan GRANT's `device_instances`) at `at`.

    Only a plan that won through an `OrgPlanGrant` (`source == "staff_grant"`) can raise the
    number. The licence's own base plan (assignment, scope alias, fallback) is where
    `device_limit` was COPIED FROM at issuance, and a staff edit of `device_limit` after that
    is deliberate (`test_key_device_limit_is_the_only_limit.py`), so reading the base plan's
    value here would silently override it.

    A grant plan that gives no usable seat number (none declared, `unlimited`, switched off)
    adds nothing. A failed catalogue read also adds nothing: it is logged and the licence's
    own number stands, inside a savepoint so the caller's transaction (activation holds the
    licence row lock) stays usable. That fails toward the smaller, always-paid-for number.
    """
    if at.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    try:
        with transaction.atomic():
            plan, source, _ends_at = _select_org_plan(license_key.customer_id, at)
            plan_value = (
                plan_device_instances_for_issuance(plan)
                if plan is not None and source == "staff_grant" else None
            )
    except Exception:
        logger.exception(
            "effective device limit: plan read failed for licence %s; using its device_limit",
            getattr(license_key, "id", "<unknown>"),
        )
        return license_key.device_limit
    if plan_value is None:
        return license_key.device_limit
    return max(license_key.device_limit, plan_value)
