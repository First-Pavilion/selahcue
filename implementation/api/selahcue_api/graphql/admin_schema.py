from datetime import datetime

import strawberry
from django.conf import settings
from strawberry.extensions import DisableIntrospection

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.accounts.services import (
    CreateCustomerData,
    count_customers,
    create_customer,
    search_customers,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.services import (
    GenerateLicenseKeyData,
    generate_license_key,
)
from selahcue_api.graphql.context import (
    StaffPermission,
    actor_from_info,
    require_staff_permission,
)


@strawberry.type
class AdminHealth:
    surface: str
    ready: bool


@strawberry.input
class AdminCreateCustomerInput:
    idempotency_key: str
    name: str
    primary_contact_email: str
    country: str
    timezone: str
    status: str = "PROSPECT"
    plan: str = "TRIAL"
    seat_limit: int = 1
    device_limit: int = 1
    billing_contact_email: str = ""
    internal_notes: str = ""


@strawberry.input
class AdminGenerateLicenseKeyInput:
    idempotency_key: str
    customer_id: strawberry.ID
    key_type: str
    feature_scope: str
    # Required by the schema, so the surface DOCUMENTS that a licence is issued on a plan
    # rather than leaving a staff caller to discover it from a refusal (DEC-014). The
    # service refuses an empty or unknown code as well, because it has callers that never
    # come through GraphQL — management commands, tests, and any future admin surface.
    plan_code: str
    starts_at: datetime
    expires_at: datetime
    timezone: str
    seat_limit: int
    device_limit: int
    territory: str
    reason: str


@strawberry.type
class AdminLicenseKey:
    id: strawberry.ID
    key_type: str
    status: str
    key_prefix: str
    key_suffix: str
    masked_key: str
    feature_scope: str
    starts_at: str
    expires_at: str

    @strawberry.field
    def customer(self) -> "AdminCustomer":
        return customer_to_type(self._model.customer)

    _model: strawberry.Private[AppLicenseKey]


@strawberry.type
class AdminLicenseKeyConnection:
    total_count: int
    nodes: list[AdminLicenseKey]


@strawberry.type
class AdminCustomer:
    id: strawberry.ID
    name: str
    status: str
    primary_contact_email: str
    country: str
    timezone: str
    plan: str
    seat_limit: int
    device_limit: int

    @strawberry.field
    def license_keys(self, info: strawberry.Info) -> AdminLicenseKeyConnection:
        require_staff_permission(actor_from_info(info), StaffPermission.VIEW_CUSTOMERS)
        keys = list(self._model.license_keys.order_by("-created_at", "-id")[:50])
        return AdminLicenseKeyConnection(
            total_count=self._model.license_keys.count(),
            nodes=[license_key_to_type(key) for key in keys],
        )

    _model: strawberry.Private[CustomerOrg]


@strawberry.type
class AdminCustomerConnection:
    total_count: int
    nodes: list[AdminCustomer]


@strawberry.type
class AdminCreateCustomerPayload:
    customer: AdminCustomer
    created: bool


@strawberry.type
class AdminGenerateLicenseKeyPayload:
    license_key: AdminLicenseKey
    full_key: str | None
    created: bool


def customer_to_type(customer: CustomerOrg) -> AdminCustomer:
    return AdminCustomer(
        id=strawberry.ID(str(customer.id)),
        name=customer.name,
        status=customer.status,
        primary_contact_email=customer.primary_contact_email,
        country=customer.country,
        timezone=customer.timezone,
        plan=customer.plan,
        seat_limit=customer.seat_limit,
        device_limit=customer.device_limit,
        _model=customer,
    )


def license_key_to_type(license_key: AppLicenseKey) -> AdminLicenseKey:
    return AdminLicenseKey(
        id=strawberry.ID(str(license_key.id)),
        key_type=license_key.key_type,
        status=license_key.status,
        key_prefix=license_key.key_prefix,
        key_suffix=license_key.key_suffix,
        masked_key=license_key.masked_key,
        feature_scope=license_key.feature_scope,
        starts_at=license_key.starts_at.isoformat(),
        expires_at=license_key.expires_at.isoformat(),
        _model=license_key,
    )


@strawberry.type
class AdminQuery:
    @strawberry.field
    def admin_health(self, info: strawberry.Info) -> AdminHealth:
        require_staff_permission(actor_from_info(info), StaffPermission.VIEW_PLATFORM_HEALTH)
        return AdminHealth(surface="admin", ready=True)

    @strawberry.field
    def admin_customers(
        self,
        info: strawberry.Info,
        search: str | None = None,
        first: int = 50,
    ) -> AdminCustomerConnection:
        actor = actor_from_info(info)
        customers = search_customers(actor, search=search, first=first)
        return AdminCustomerConnection(
            # True match count, independent of the page limit (was len(page) → hid matches
            # when totalCount was used for pagination).
            total_count=count_customers(actor, search=search),
            nodes=[customer_to_type(customer) for customer in customers],
        )


@strawberry.type
class AdminMutation:
    @strawberry.mutation
    def admin_create_customer(
        self,
        info: strawberry.Info,
        input: AdminCreateCustomerInput,
    ) -> AdminCreateCustomerPayload:
        result = create_customer(
            actor_from_info(info),
            CreateCustomerData(
                idempotency_key=input.idempotency_key,
                name=input.name,
                primary_contact_email=input.primary_contact_email,
                billing_contact_email=input.billing_contact_email,
                country=input.country,
                timezone=input.timezone,
                status=input.status,
                plan=input.plan,
                seat_limit=input.seat_limit,
                device_limit=input.device_limit,
                internal_notes=input.internal_notes,
            ),
        )
        return AdminCreateCustomerPayload(
            customer=customer_to_type(result.customer),
            created=result.created,
        )

    @strawberry.mutation
    def admin_generate_license_key(
        self,
        info: strawberry.Info,
        input: AdminGenerateLicenseKeyInput,
    ) -> AdminGenerateLicenseKeyPayload:
        result = generate_license_key(
            actor_from_info(info),
            GenerateLicenseKeyData(
                idempotency_key=input.idempotency_key,
                customer_id=str(input.customer_id),
                key_type=input.key_type,
                feature_scope=input.feature_scope,
                plan_code=input.plan_code,
                starts_at=input.starts_at,
                expires_at=input.expires_at,
                timezone=input.timezone,
                seat_limit=input.seat_limit,
                device_limit=input.device_limit,
                territory=input.territory,
                reason=input.reason,
            ),
        )
        return AdminGenerateLicenseKeyPayload(
            license_key=license_key_to_type(result.license_key),
            full_key=result.full_key,
            created=result.created,
        )


schema = strawberry.Schema(
    query=AdminQuery,
    mutation=AdminMutation,
    extensions=[] if settings.GRAPHQL_INTROSPECTION_ENABLED else [DisableIntrospection],
)
