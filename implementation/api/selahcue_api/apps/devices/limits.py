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

from django.db import DatabaseError, transaction

from selahcue_api.apps.catalogue.org_plans import _select_org_plan
from selahcue_api.apps.catalogue.services import plan_device_instances_for_issuance
from selahcue_api.apps.license_keys.models import AppLicenseKey

logger = logging.getLogger(__name__)


def _grant_device_instances(license_key: AppLicenseKey, at: datetime) -> int | None:
    """The winning plan GRANT's `device_instances` at `at`, or None when no grant wins or its
    plan gives no usable seat number. Raises `DatabaseError`/`LookupError` on a failed read;
    the savepoint keeps that failure from poisoning the caller's transaction."""
    if at.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    with transaction.atomic():
        plan, source, _ends_at = _select_org_plan(license_key.customer_id, at)
        if plan is None or source != "staff_grant":
            return None
        return plan_device_instances_for_issuance(plan)


def _log_read_failure(license_key: AppLicenseKey, outcome: str) -> None:
    logger.exception(
        "effective device limit: plan read failed for licence %s; %s",
        getattr(license_key, "id", "<unknown>"), outcome,
    )


def effective_device_limit(license_key: AppLicenseKey, at: datetime) -> int:
    """max(the licence's `device_limit`, the winning plan GRANT's `device_instances`) at `at`.

    Only a plan that won through an `OrgPlanGrant` (`source == "staff_grant"`) can raise the
    number. The grant is the ORG's, so it raises the limit for every key that org holds. The
    licence's own base plan (assignment, scope alias, fallback) is where `device_limit` was
    COPIED FROM at issuance, and a staff edit of `device_limit` after that is deliberate
    (`test_key_device_limit_is_the_only_limit.py`), so reading the base plan's value here
    would silently override it.

    A grant plan that gives no usable seat number (none declared, `unlimited`, switched off)
    adds nothing. A failed catalogue read (`DatabaseError`, or `LookupError` from an unseeded
    catalogue) also adds nothing: it is logged and the licence's own number stands. That fails
    toward the smaller, always-paid-for number, which is right where a credential or a seat is
    being GRANTED (activation, re-mint). Device authentication must not deny a live service
    over a catalogue fault (NFR-024), so it uses `effective_device_limit_or_none` instead.
    """
    try:
        grant_value = _grant_device_instances(license_key, at)
    except (DatabaseError, LookupError):
        _log_read_failure(license_key, "using its device_limit")
        return license_key.device_limit
    if grant_value is None:
        return license_key.device_limit
    return max(license_key.device_limit, grant_value)


def effective_device_limit_or_none(license_key: AppLicenseKey, at: datetime) -> int | None:
    """`effective_device_limit`, except a failed plan read returns None ("unknown") instead
    of falling back. For the device-auth check only, which then fails OPEN (NFR-024)."""
    try:
        grant_value = _grant_device_instances(license_key, at)
    except (DatabaseError, LookupError):
        _log_read_failure(license_key, "allowing the authenticated device")
        return None
    if grant_value is None:
        return license_key.device_limit
    return max(license_key.device_limit, grant_value)
