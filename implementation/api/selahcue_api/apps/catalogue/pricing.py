"""Internal accountable append-only price versions; no staff/public endpoint.

Callers select an explicit future timestamp, or None for an immediate server-timed price. A repeated timestamp
conflicts rather than creating another version; no update/delete service exists.
"""
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Window
from django.db.models.functions import Lead
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.models import Plan, PlanPrice
from selahcue_api.apps.catalogue.write_lock import lock_catalogue_revision
from selahcue_api.graphql.context import (ActorContext, StaffPermission, require_staff_permission,
    require_reason, validate_idempotency_key, has_control_characters)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


@dataclass(frozen=True)
class AppendPlanPriceData:
    plan_code: str
    currency: str
    interval: str
    amount_minor: int | None
    effective_from: datetime | None
    reason: str
    idempotency_key: str


def current_plan_price(plan: Plan, currency: str, interval: str, *, at: datetime | None = None):
    """No row is unpriced; a row with amount0 remains distinctly priced zero."""
    return (PlanPrice.objects.filter(plan=plan, currency=currency, interval=interval,
            effective_from__lte=at or timezone.now()).order_by("-effective_from").first())


def plan_price_history(plan: Plan, currency: str, interval: str, *, limit: int = 100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    return (PlanPrice.objects.filter(plan=plan, currency=currency, interval=interval)
            .annotate(_effective_until=Window(Lead("effective_from"), order_by=F("effective_from").asc()))
            .order_by("effective_from")[:limit])


def append_plan_price(actor: ActorContext | None, data: AppendPlanPriceData) -> PlanPrice:
    staff = require_staff_permission(actor, StaffPermission.MANAGE_PLAN_PRICING)
    if not isinstance(data.reason, str):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    reason = require_reason(data.reason)
    request_id = validate_idempotency_key(data.idempotency_key)
    if (not isinstance(data.plan_code, str) or not data.plan_code.strip() or has_control_characters(data.plan_code)):
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    now = timezone.now()
    effective_from = now if data.effective_from is None else data.effective_from
    if (not isinstance(effective_from, datetime) or timezone.is_naive(effective_from)
            or effective_from < now):
        error = SafeAPIError(ErrorCode.VALIDATION_FAILED)
        error.extensions['field'] = 'effectiveFrom'
        raise error
    # Validate typed scalar fields BEFORE any lookup using them. PostgreSQL refuses NUL
    # text at the driver boundary; SQLite would otherwise defer that case until save.
    price = PlanPrice(currency=data.currency, interval=data.interval, amount_minor=data.amount_minor,
                      effective_from=effective_from, changed_by_actor_id=staff.actor_id, reason=reason)
    try:
        price.full_clean(exclude=["plan"], validate_unique=False, validate_constraints=False)
    except ValidationError as error:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from error
    with transaction.atomic():
        lock_catalogue_revision()
        plan = Plan.objects.select_for_update().filter(code=data.plan_code).first()
        if plan is None:
            raise SafeAPIError(ErrorCode.NOT_FOUND)
        price.plan = plan
        identity = dict(plan=plan, currency=price.currency, interval=price.interval, effective_from=price.effective_from)
        if PlanPrice.objects.filter(**identity).exists():
            raise SafeAPIError(ErrorCode.CONFLICT)
        previous = current_plan_price(plan, data.currency, data.interval, at=effective_from)
        try:
            with transaction.atomic():
                price.save()
        except ValidationError as error:
            raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from error
        except IntegrityError as error:
            # The unique constraint remains the final arbiter even on engines without row locks.
            if PlanPrice.objects.filter(**identity).exists():
                raise SafeAPIError(ErrorCode.CONFLICT) from error
            raise
        record_audit_event(staff, action="catalogue.plan_price_added", target_type="catalogue_plan_price",
            target_id=str(price.pk), request_id=request_id, reason=reason, source_surface="catalogue_internal",
            before={"price_id": str(previous.pk), "amount_minor": previous.amount_minor} if previous else {},
            after={"plan_id": str(plan.pk), "currency": price.currency, "interval": price.interval,
                   "amount_minor": price.amount_minor, "effective_from": price.effective_from.isoformat()})
        return price
