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
    ExtendLicenseKeyData,
    GenerateLicenseKeyData,
    ReinstateLicenseKeyData,
    RevokeLicenseKeyData,
    SuspendLicenseKeyData,
    extend_license_key,
    generate_license_key,
    reinstate_license_key,
    revoke_license_key,
    suspend_license_key,
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
    territory: str
    reason: str


@strawberry.input
class AdminSuspendLicenseKeyInput:
    # The retry key, one per USER INTENT: send a fresh key for each deliberate action and
    # re-send the same key only to retry that action. A retry of a request that already took
    # effect applies nothing and reports the licence's CURRENT state with `changed=false` and
    # `replayed=true` (so after another staff action it reports that action's result, not the
    # one this request produced). Send ONE mutation per HTTP request: the lifecycle
    # throttle counts calls, and a batch of aliased mutations that exhausts it fails as a
    # whole.
    idempotency_key: str
    license_key_id: strawberry.ID
    # Mandatory (FR-504); recorded on the audit row beside the acting staff member.
    reason: str


@strawberry.input
class AdminReinstateLicenseKeyInput:
    # Same retry-key rules as `AdminSuspendLicenseKeyInput`.
    idempotency_key: str
    license_key_id: strawberry.ID
    reason: str


@strawberry.input
class AdminRevokeLicenseKeyInput:
    # Same retry-key rules as `AdminSuspendLicenseKeyInput`. Revocation is PERMANENT (FR-505):
    # nothing moves a licence out of REVOKED except archiving, so the reason is the record of
    # why, and it is mandatory.
    idempotency_key: str
    license_key_id: strawberry.ID
    reason: str


@strawberry.input
class AdminExtendLicenseKeyInput:
    # Same retry-key rules as `AdminSuspendLicenseKeyInput`.
    idempotency_key: str
    license_key_id: strawberry.ID
    # The new expiry. Must carry a UTC offset (a value without one is refused, not guessed),
    # be later than the current expiry and in the future, and be within five years of now.
    new_expires_at: datetime
    reason: str


@strawberry.type
class AdminLicenseKeySummary:
    """A licence WITHOUT its customer. The lifecycle mutations return this, not
    `AdminLicenseKey`, on purpose: `AdminLicenseKey.customer` carries no permission check of
    its own (it relies on the query that reached it having checked VIEW_CUSTOMERS), so
    handing it to an actor who holds only the suspend or reinstate permission would let them
    read customer contact details they cannot otherwise query."""

    id: strawberry.ID
    key_type: str
    status: str
    # The status a SUSPENDED licence returns to on reinstatement; empty for every other
    # status. Surfaced so the console can say where a reinstatement will land (FR-526).
    prior_status: str
    key_prefix: str
    key_suffix: str
    masked_key: str
    feature_scope: str
    starts_at: str
    expires_at: str
    # How many device instances this licence admits: the ONE device limit. Activation enforces
    # it, the signed manifest publishes it as `instances_limit` and the refresh endpoint reports
    # it as `instances.limit`. It is copied from the plan at issuance (86ak5mn0m); the org has no
    # limit of its own, so this is the only number the console can show for "how many devices".
    device_limit: int


@strawberry.type
class AdminLicenseKey(AdminLicenseKeySummary):
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


@strawberry.type
class AdminSuspendLicenseKeyPayload:
    license_key: AdminLicenseKeySummary
    # False when this call changed nothing: the licence was already suspended, OR this was a
    # retry of a request that already took effect (then `replayed` is also true).
    changed: bool
    # True only for the retry case, so a console can tell "already suspended" from "your
    # earlier request went through".
    replayed: bool


@strawberry.type
class AdminReinstateLicenseKeyPayload:
    license_key: AdminLicenseKeySummary
    changed: bool
    replayed: bool


@strawberry.type
class AdminRevokeLicenseKeyPayload:
    license_key: AdminLicenseKeySummary
    # False when this call changed nothing: the licence was already revoked, OR this was a
    # retry of a request that already took effect (then `replayed` is also true).
    changed: bool
    replayed: bool


@strawberry.type
class AdminExtendLicenseKeyPayload:
    license_key: AdminLicenseKeySummary
    # False only for a retry of a request that already took effect (`replayed` is then true):
    # an extension that would change nothing is rejected, not reported as a no-op.
    changed: bool
    replayed: bool


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
        _model=customer,
    )


def license_key_to_summary(license_key: AppLicenseKey) -> AdminLicenseKeySummary:
    return AdminLicenseKeySummary(
        id=strawberry.ID(str(license_key.id)),
        key_type=license_key.key_type,
        status=license_key.status,
        prior_status=license_key.prior_status,
        key_prefix=license_key.key_prefix,
        key_suffix=license_key.key_suffix,
        masked_key=license_key.masked_key,
        feature_scope=license_key.feature_scope,
        starts_at=license_key.starts_at.isoformat(),
        expires_at=license_key.expires_at.isoformat(),
        device_limit=license_key.device_limit,
    )


def license_key_to_type(license_key: AppLicenseKey) -> AdminLicenseKey:
    return AdminLicenseKey(
        id=strawberry.ID(str(license_key.id)),
        key_type=license_key.key_type,
        status=license_key.status,
        prior_status=license_key.prior_status,
        key_prefix=license_key.key_prefix,
        key_suffix=license_key.key_suffix,
        masked_key=license_key.masked_key,
        feature_scope=license_key.feature_scope,
        starts_at=license_key.starts_at.isoformat(),
        expires_at=license_key.expires_at.isoformat(),
        device_limit=license_key.device_limit,
        _model=license_key,
    )


def _is_replay(result) -> bool:
    """A no-change result that carries the original audit row is a retry of a request that
    already took effect; a plain "already in that state" no-op carries none."""
    return (not result.changed) and result.audit_event is not None


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
                territory=input.territory,
                reason=input.reason,
            ),
        )
        return AdminGenerateLicenseKeyPayload(
            license_key=license_key_to_type(result.license_key),
            full_key=result.full_key,
            created=result.created,
        )

    @strawberry.mutation
    def admin_suspend_license_key(
        self,
        info: strawberry.Info,
        input: AdminSuspendLicenseKeyInput,
    ) -> AdminSuspendLicenseKeyPayload:
        result = suspend_license_key(
            actor_from_info(info),
            SuspendLicenseKeyData(
                idempotency_key=input.idempotency_key,
                license_key_id=str(input.license_key_id),
                reason=input.reason,
            ),
        )
        return AdminSuspendLicenseKeyPayload(
            license_key=license_key_to_summary(result.license_key),
            changed=result.changed,
            replayed=_is_replay(result),
        )

    @strawberry.mutation
    def admin_reinstate_license_key(
        self,
        info: strawberry.Info,
        input: AdminReinstateLicenseKeyInput,
    ) -> AdminReinstateLicenseKeyPayload:
        result = reinstate_license_key(
            actor_from_info(info),
            ReinstateLicenseKeyData(
                idempotency_key=input.idempotency_key,
                license_key_id=str(input.license_key_id),
                reason=input.reason,
            ),
        )
        return AdminReinstateLicenseKeyPayload(
            license_key=license_key_to_summary(result.license_key),
            changed=result.changed,
            replayed=_is_replay(result),
        )

    @strawberry.mutation
    def admin_revoke_license_key(
        self,
        info: strawberry.Info,
        input: AdminRevokeLicenseKeyInput,
    ) -> AdminRevokeLicenseKeyPayload:
        result = revoke_license_key(
            actor_from_info(info),
            RevokeLicenseKeyData(
                idempotency_key=input.idempotency_key,
                license_key_id=str(input.license_key_id),
                reason=input.reason,
            ),
        )
        return AdminRevokeLicenseKeyPayload(
            license_key=license_key_to_summary(result.license_key),
            changed=result.changed,
            replayed=_is_replay(result),
        )

    @strawberry.mutation
    def admin_extend_license_key(
        self,
        info: strawberry.Info,
        input: AdminExtendLicenseKeyInput,
    ) -> AdminExtendLicenseKeyPayload:
        result = extend_license_key(
            actor_from_info(info),
            ExtendLicenseKeyData(
                idempotency_key=input.idempotency_key,
                license_key_id=str(input.license_key_id),
                new_expires_at=input.new_expires_at,
                reason=input.reason,
            ),
        )
        return AdminExtendLicenseKeyPayload(
            license_key=license_key_to_summary(result.license_key),
            changed=result.changed,
            replayed=_is_replay(result),
        )


schema = strawberry.Schema(
    query=AdminQuery,
    mutation=AdminMutation,
    extensions=[] if settings.GRAPHQL_INTROSPECTION_ENABLED else [DisableIntrospection],
)
