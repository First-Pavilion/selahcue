"""Gated admin catalogue operations; real staff sign-in remains a release dependency."""
import hashlib
import json
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Prefetch, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.models import (
    CatalogueAdminMutation, CatalogueRevision, Plan, PlanGrant, PlanPrice,
)
from selahcue_api.apps.catalogue.pricing import AppendPlanPriceData, append_plan_price
from selahcue_api.apps.catalogue.services import SetPlanGrantData, current_revision, set_plan_grant
from selahcue_api.graphql.context import (
    StaffPermission, require_reason, require_staff_permission, validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


def _invalid(field):
    error = SafeAPIError(ErrorCode.VALIDATION_FAILED)
    error.extensions['field'] = field
    return error


def require_admin_catalogue_permission(actor):
    # The slice may merge before the authenticator, but may never be enabled in prod.
    if settings.ENVIRONMENT != 'dev' or not settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    return require_staff_permission(actor, StaffPermission.MANAGE_PLAN_PRICING)


def read_admin_catalogue(actor):
    require_admin_catalogue_permission(actor)
    latest_prices = (
        PlanPrice.objects.filter(effective_from__lte=timezone.now())
        .annotate(_position=Window(
            RowNumber(), partition_by=['plan_id', 'currency', 'interval'],
            order_by=F('effective_from').desc(),
        ))
        .filter(_position=1)
    )
    plans = Plan.objects.order_by('rank', 'code').prefetch_related(
        Prefetch('prices', queryset=latest_prices),
        Prefetch('grants', queryset=PlanGrant.objects.select_related('dimension').order_by('dimension__key')),
    )
    # Read the optimistic token BEFORE the data. A concurrent edit can conservatively
    # make it stale, but must never pair old values with a newer token that permits overwrite.
    revision = current_revision()
    result = []
    for plan in plans:
        result.append(dict(
            code=plan.code,
            name=plan.display_name,
            prices=[dict(
                currency=price.currency,
                interval=price.interval,
                amount_minor=None if price.amount_minor is None else str(price.amount_minor),
                effective_from=price.effective_from.isoformat(),
            ) for price in plan.prices.all()],
            grants=[dict(key=grant.dimension.key, raw_value=grant.raw_value) for grant in plan.grants.all()],
        ))
    return dict(revision=revision, plans=result)


def _receipt(staff, key):
    return CatalogueAdminMutation.objects.filter(actor_id=staff.actor_id, idempotency_key=key).first()


def _replay(receipt, fingerprint):
    if receipt.fingerprint != fingerprint:
        raise SafeAPIError(ErrorCode.CONFLICT)
    return {**receipt.result, 'replayed': True}


def _apply(actor, operation, data, writer):
    staff = require_admin_catalogue_permission(actor)
    try:
        key = validate_idempotency_key(data['idempotency_key'])
    except (SafeAPIError, AttributeError):
        raise _invalid('idempotencyKey') from None
    try:
        reason = require_reason(data['reason'])
    except (SafeAPIError, AttributeError):
        raise _invalid('reason') from None
    expected = data['expected_revision']
    if type(expected) is not int or expected < 0:
        raise _invalid('expectedRevision')
    canonical = {key: (value.isoformat() if isinstance(value, datetime) else value)
                 for key, value in data.items()}
    canonical['reason'] = reason
    fingerprint = hashlib.sha256(json.dumps(
        dict(operation=operation, data=canonical), sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    with transaction.atomic():
        previous = _receipt(staff, key)
        if previous:
            return _replay(previous, fingerprint)
        # CAS serializes admin writes and refuses same-revision lost updates. Unlike
        # select_for_update alone, the comparison also has meaning on SQLite.
        updated = CatalogueRevision.objects.filter(
            pk=CatalogueRevision.SINGLETON_PK, revision=expected,
        ).update(revision=F('revision') + 1)
        if not updated:
            # A simultaneous retry may have committed while the CAS waited for its lock.
            previous = _receipt(staff, key)
            if previous:
                return _replay(previous, fingerprint)
            error = SafeAPIError(ErrorCode.CONFLICT)
            error.extensions['catalogueChanged'] = True
            raise error
        previous = _receipt(staff, key)
        if previous:
            result = _replay(previous, fingerprint)
            transaction.set_rollback(True)
            return result
        result = writer(staff, reason)
        result['revision'] = current_revision()
        CatalogueAdminMutation.objects.create(
            actor_id=staff.actor_id, idempotency_key=key, fingerprint=fingerprint, result=result,
        )
        return {**result, 'replayed': False}


def set_admin_price(actor, **data):
    def writer(staff, reason):
        price = append_plan_price(staff, AppendPlanPriceData(
            plan_code=data['plan_code'], currency=data['currency'], interval=data['interval'],
            amount_minor=data['amount_minor'], effective_from=data['effective_from'],
            reason=reason, idempotency_key=data['idempotency_key'],
        ))
        return dict(price_id=str(price.pk), amount_minor=None if price.amount_minor is None else str(price.amount_minor))
    try:
        return _apply(actor, 'price', data, writer)
    except SafeAPIError as error:
        cause = error.__cause__
        if isinstance(cause, ValidationError) and hasattr(cause, 'message_dict'):
            fields = {'amount_minor': 'amountMinor', 'currency': 'currency',
                      'interval': 'interval', 'effective_from': 'effectiveFrom'}
            field = next((fields[key] for key in cause.message_dict if key in fields), None)
            if field:
                raise _invalid(field) from error
        raise


def set_admin_grant(actor, **data):
    def writer(staff, reason):
        # Reuse the single grant writer's validation, audit and cache invalidation.
        result = set_plan_grant(staff, SetPlanGrantData(
            plan_code=data['plan_code'], dimension_key=data['dimension_key'],
            raw_value=data['raw_value'], reason=reason, idempotency_key=data['idempotency_key'],
        ))
        return dict(grant_id=str(result.grant.pk), raw_value=result.grant.raw_value)
    try:
        return _apply(actor, 'grant', data, writer)
    except SafeAPIError as error:
        if error.code is ErrorCode.VALIDATION_FAILED and 'field' not in error.extensions:
            raise _invalid('rawValue') from error
        raise


def rename_admin_plan(actor, **data):
    def writer(staff, reason):
        plan = Plan.objects.select_for_update().filter(code=data['plan_code']).first()
        if plan is None:
            raise SafeAPIError(ErrorCode.NOT_FOUND)
        previous = plan.display_name
        plan.display_name = data['name']
        plan.changed_by_actor_id = staff.actor_id
        plan.reason = reason
        try:
            plan.full_clean()
        except ValidationError as error:
            raise _invalid('name') from error
        plan.save(update_fields=['display_name', 'changed_by_actor_id', 'reason', 'updated_at'])
        record_audit_event(
            staff, action='catalogue.plan_renamed', target_type='catalogue_plan',
            target_id=str(plan.pk), request_id=data['idempotency_key'], reason=reason,
            before={'display_name': previous},
            after={'plan_code': plan.code, 'display_name': plan.display_name},
        )
        return dict(name=plan.display_name)
    return _apply(actor, 'rename', data, writer)
