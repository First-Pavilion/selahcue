from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.text import slugify

from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.graphql.context import (
    ActorContext,
    StaffPermission,
    require_staff_permission,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


@dataclass(frozen=True)
class CreateCustomerData:
    idempotency_key: str
    name: str
    primary_contact_email: str
    country: str
    timezone: str
    status: str = CustomerStatus.PROSPECT
    plan: str = "TRIAL"
    seat_limit: int = 1
    device_limit: int = 1
    billing_contact_email: str = ""
    internal_notes: str = ""


@dataclass(frozen=True)
class CreateCustomerResult:
    customer: CustomerOrg
    created: bool


def _validation_error() -> SafeAPIError:
    return SafeAPIError(ErrorCode.VALIDATION_FAILED)


def _clean_customer(customer: CustomerOrg) -> None:
    try:
        customer.full_clean()
    except ValidationError as error:
        raise _validation_error() from error


def _unique_slug(name: str) -> str:
    base = slugify(name)[:180] or "customer"
    candidate = base
    counter = 2
    while CustomerOrg.objects.filter(slug=candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{base[: 220 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def create_customer(actor: ActorContext | None, data: CreateCustomerData) -> CreateCustomerResult:
    staff = require_staff_permission(actor, StaffPermission.MANAGE_CUSTOMERS)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    if data.seat_limit < 1 or data.device_limit < 1:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    with transaction.atomic():
        existing = CustomerOrg.objects.filter(
            created_by_actor_id=staff.actor_id,
            idempotency_key=idempotency_key,
        ).first()
        if existing is not None:
            return CreateCustomerResult(customer=existing, created=False)

        try:
            status = CustomerStatus(data.status)
        except ValueError as error:
            raise _validation_error() from error

        customer = CustomerOrg(
            name=" ".join(data.name.strip().split()),
            slug=_unique_slug(data.name),
            status=status,
            primary_contact_email=data.primary_contact_email.strip().lower(),
            billing_contact_email=data.billing_contact_email.strip().lower(),
            country=data.country.strip().upper(),
            timezone=data.timezone.strip() or "UTC",
            plan=data.plan.strip().upper() or "TRIAL",
            seat_limit=data.seat_limit,
            device_limit=data.device_limit,
            internal_notes=data.internal_notes.strip(),
            created_by_actor_id=staff.actor_id,
            idempotency_key=idempotency_key,
        )
        _clean_customer(customer)
        # Concurrency-safe idempotency: two racing requests with the same
        # (actor, idempotency_key) both pass the check above; the unique constraint rejects the
        # loser's INSERT. Catch it in a savepoint and return the winner's row as an idempotent
        # replay instead of surfacing a spurious VALIDATION_FAILED. (Mirrors `activate_device`.)
        try:
            with transaction.atomic():
                customer.save()
        except IntegrityError:
            existing = CustomerOrg.objects.filter(
                created_by_actor_id=staff.actor_id,
                idempotency_key=idempotency_key,
            ).first()
            if existing is not None:
                return CreateCustomerResult(customer=existing, created=False)
            raise _validation_error()
        record_audit_event(
            staff,
            action="customer.created",
            target_type="customer_org",
            target_id=str(customer.id),
            request_id=idempotency_key,
            after={
                "name": customer.name,
                "status": customer.status,
                "primary_contact_email": customer.primary_contact_email,
                "country": customer.country,
                "timezone": customer.timezone,
                "plan": customer.plan,
                "seat_limit": customer.seat_limit,
                "device_limit": customer.device_limit,
            },
        )
        return CreateCustomerResult(customer=customer, created=True)


def search_customers(
    actor: ActorContext | None,
    *,
    search: str | None = None,
    first: int = 50,
) -> list[CustomerOrg]:
    require_staff_permission(actor, StaffPermission.VIEW_CUSTOMERS)
    page_size = max(1, min(first, 200))
    queryset = CustomerOrg.objects.order_by("name", "id")
    cleaned = (search or "").strip()
    if cleaned:
        queryset = queryset.filter(
            Q(name__icontains=cleaned)
            | Q(slug__icontains=cleaned)
            | Q(primary_contact_email__icontains=cleaned)
        )
    return list(queryset[:page_size])


def _customer_search_queryset(search: str | None):
    queryset = CustomerOrg.objects.all()
    cleaned = (search or "").strip()
    if cleaned:
        queryset = queryset.filter(
            Q(name__icontains=cleaned)
            | Q(slug__icontains=cleaned)
            | Q(primary_contact_email__icontains=cleaned)
        )
    return queryset


def count_customers(actor: ActorContext | None, *, search: str | None = None) -> int:
    """True match count for a customer search, independent of the page limit — so a paginating
    client sees the real total (not the page size)."""
    require_staff_permission(actor, StaffPermission.VIEW_CUSTOMERS)
    return _customer_search_queryset(search).count()
