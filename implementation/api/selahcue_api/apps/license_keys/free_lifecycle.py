"""Issue and renew the explicitly managed self-service Free licence."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg, CustomerRole, CustomerStatus
from selahcue_api.apps.accounts.services import (
    is_self_service_org,
    promote_trial_for_self_service_activation,
    require_verified_activation_admin,
)
from selahcue_api.apps.audit.models import AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
from selahcue_api.apps.devices.models import Device, DeviceStatus, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.license_keys.models import (
    AppLicenseKey, FreeLicenseLifecycle, LicenseKeyStatus, LicenseKeyType,
)
from selahcue_api.apps.license_keys.selection import (
    ACTIVATABLE_KEY_STATUSES, find_eligible_org_license,
)
from selahcue_api.apps.license_keys.services import (
    GenerateLicenseKeyData,
    _issue_license_key,
    _prepare_license_credential,
    lock_customer_for_key_changes,
    require_no_overlapping_license_key,
)
from selahcue_api.apps.license_keys.state_machine import apply_license_status_transition
from selahcue_api.graphql.context import ActorContext, ActorKind, require_customer_role
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

POLICY_VERSION = 1
VALIDITY = timedelta(days=365)
RENEWAL_WINDOW = timedelta(days=30)
FREE_SERVICE = ActorContext(kind=ActorKind.SERVICE, actor_id="free-license-lifecycle")
RENEWAL_REASON = "Automatic renewal of the managed Free licence."
RENEWAL_ACTION = "license_key.free_renewed"


@dataclass(frozen=True)
class RenewalResult:
    changed: bool
    license_expires_at: datetime
    token_expires_at: datetime


class FreeRenewalDenied(SafeAPIError):
    """Carry only safe audit data through the owning transaction's rollback."""

    def __init__(self, license_key: AppLicenseKey, request_id: str, cause: SafeAPIError):
        super().__init__(cause.code)
        self.license_id = str(license_key.pk)
        self.request_id = request_id

    def audit(self) -> None:
        record_audit_event(
            FREE_SERVICE, action=RENEWAL_ACTION, target_type="app_license_key",
            target_id=self.license_id, request_id=self.request_id,
            result=AuditResult.DENIED, source_surface="free_lifecycle",
            reason=RENEWAL_REASON, after={"code": self.code.value},
        )


def _locked_marker(customer: CustomerOrg, license_key: AppLicenseKey) -> FreeLicenseLifecycle | None:
    return FreeLicenseLifecycle.objects.select_for_update().filter(
        customer=customer, license_key=license_key,
    ).first()


def _lock_fallback_assignment(license_key: AppLicenseKey) -> bool:
    # Keep an assignment column selected: exists() discards model columns and
    # PostgreSQL then loses OF self, also locking the shared joined Plan row.
    return LicensePlanAssignment.objects.select_for_update(of=("self",)).filter(
        license_key=license_key, plan__is_fallback=True,
    ).values_list("pk", flat=True).first() is not None


def _may_renew(
    marker: FreeLicenseLifecycle, license_key: AppLicenseKey, now: datetime,
    *, fallback_assigned: bool,
) -> bool:
    return (
        marker.renewal_enabled
        and marker.policy_version == POLICY_VERSION
        and license_key.starts_at <= now
        and (
            license_key.status in ACTIVATABLE_KEY_STATUSES
            or (license_key.status == LicenseKeyStatus.EXPIRED and license_key.expires_at <= now)
        )
        and fallback_assigned
    )


def _renew_locked(
    customer: CustomerOrg,
    license_key: AppLicenseKey,
    marker: FreeLicenseLifecycle,
    now: datetime,
    request_id: str,
    *,
    fallback_assigned: bool,
) -> bool:
    if (
        customer.status != CustomerStatus.ACTIVE
        or license_key.expires_at - now > RENEWAL_WINDOW
        or not _may_renew(marker, license_key, now, fallback_assigned=fallback_assigned)
    ):
        return False

    new_expiry = now + VALIDITY
    try:
        require_no_overlapping_license_key(
            customer, starts_at=license_key.starts_at, expires_at=new_expiry,
            exclude_key_id=license_key.pk, requested_by=FREE_SERVICE.actor_id,
        )
        before = {"expires_at": license_key.expires_at.isoformat()}
        after = {"expires_at": new_expiry.isoformat(), "policy_version": POLICY_VERSION}
        license_key.expires_at = new_expiry
        license_key.save(update_fields=["expires_at", "updated_at"])
        if license_key.status in {LicenseKeyStatus.EXPIRING, LicenseKeyStatus.EXPIRED}:
            apply_license_status_transition(
                license_key, to_status=LicenseKeyStatus.ACTIVATED, actor=FREE_SERVICE,
                reason=RENEWAL_REASON, request_id=request_id, action=RENEWAL_ACTION,
                source_surface="free_lifecycle", extra_before=before, extra_after=after,
                allow_wrapping_transaction=True,
            )
        else:
            record_audit_event(
                FREE_SERVICE, action=RENEWAL_ACTION, target_type="app_license_key",
                target_id=str(license_key.pk), request_id=request_id, reason=RENEWAL_REASON,
                source_surface="free_lifecycle", before=before, after=after,
            )
    except SafeAPIError as error:
        raise FreeRenewalDenied(license_key, request_id, error) from error
    return True


def _authorize_managed_activation(customer: CustomerOrg, actor: ActorContext) -> None:
    if customer.status != CustomerStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)
    require_verified_activation_admin(actor, customer)


def renew_free_license_for_activation(
    customer: CustomerOrg,
    license_key: AppLicenseKey,
    actor: ActorContext,
    now: datetime,
    request_id: str,
    *,
    completed_without_token: bool = False,
) -> bool:
    """Handle an exact target under the caller's org, licence and device locks.

    The read-only completed receipt can identify an otherwise renewable expired
    licence so the client can submit a separate recovery operation.
    """
    marker = _locked_marker(customer, license_key)
    if marker is None:
        return False
    _authorize_managed_activation(customer, actor)
    fallback_assigned = _lock_fallback_assignment(license_key)
    if completed_without_token:
        return _may_renew(marker, license_key, now, fallback_assigned=fallback_assigned)
    return _renew_locked(
        customer, license_key, marker, now, request_id, fallback_assigned=fallback_assigned,
    )


def _issue_initial_free(customer: CustomerOrg, now: datetime, request_id: str) -> AppLicenseKey:
    plan = Plan.objects.filter(is_fallback=True).first()
    if plan is None:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)

    reason = "First verified administrator activation for self-service Free."
    promote_trial_for_self_service_activation(
        customer, actor=FREE_SERVICE, request_id=request_id, reason=reason,
    )

    key_type = LicenseKeyType.CUSTOM
    data = GenerateLicenseKeyData(
        idempotency_key=request_id, customer_id=str(customer.pk), key_type=key_type,
        feature_scope=plan.code, plan_code=plan.code, starts_at=now, expires_at=now + VALIDITY,
        timezone=customer.timezone, seat_limit=customer.seat_limit, territory=customer.country,
        reason=reason,
    )
    # The service never returns the enrollment key. Namespace the persisted
    # issuance idempotency key by org because different orgs can share a nonce.
    result = _issue_license_key(
        customer, FREE_SERVICE, data, key_type=key_type, plan_code=data.plan_code,
        starts_at=data.starts_at, expires_at=data.expires_at,
        idempotency_key=f"initial-free:{customer.pk}", reason=reason,
        credential=_prepare_license_credential(key_type), source_surface="free_lifecycle",
    )
    FreeLicenseLifecycle.objects.create(
        customer=customer, license_key=result.license_key, policy_version=POLICY_VERSION,
    )
    return result.license_key


def ensure_free_license_under_org_lock(
    customer: CustomerOrg,
    actor: ActorContext,
    now: datetime,
    request_id: str,
    *,
    defer_renewal: bool = False,
) -> AppLicenseKey:
    """Select the activation licence, with an optional exact-device check before renewal."""
    selected = find_eligible_org_license(customer.pk, now)
    if selected is None:
        managed_id = FreeLicenseLifecycle.objects.filter(customer=customer).values_list(
            "license_key_id", flat=True,
        ).first()
        if managed_id is None:
            if not is_self_service_org(customer):
                raise SafeAPIError(ErrorCode.NOT_FOUND)
            if (
                customer.status not in {CustomerStatus.ACTIVE, CustomerStatus.TRIAL}
                or AppLicenseKey.objects.filter(customer=customer).exists()
            ):
                raise SafeAPIError(ErrorCode.POLICY_DENIED)
            require_verified_activation_admin(actor, customer)
            return _issue_initial_free(customer, now, request_id)
        license_id = managed_id
    else:
        license_id = selected.pk

    license_key = AppLicenseKey.objects.select_for_update().get(pk=license_id, customer=customer)
    marker = _locked_marker(customer, license_key)
    if marker is not None:
        _authorize_managed_activation(customer, actor)
        if defer_renewal:
            return license_key
        _renew_locked(
            customer, license_key, marker, now, request_id,
            fallback_assigned=_lock_fallback_assignment(license_key),
        )
    if (
        license_key.status not in ACTIVATABLE_KEY_STATUSES
        or not license_key.starts_at <= now < license_key.expires_at
    ):
        raise SafeAPIError(ErrorCode.POLICY_DENIED if marker is not None else ErrorCode.NOT_FOUND)
    return license_key


def ensure_free_license(actor: ActorContext, now: datetime, request_id: str) -> AppLicenseKey:
    """Issue once or return the org's existing eligible licence."""
    checked = require_customer_role(actor, CustomerRole.ADMIN)
    try:
        with transaction.atomic():
            customer = lock_customer_for_key_changes(checked.org_id)
            return ensure_free_license_under_org_lock(customer, checked, now, request_id)
    except FreeRenewalDenied as error:
        error.audit()
        raise


def has_pending_staff_extension(license_key: AppLicenseKey, token: DeviceToken) -> bool:
    if token.staff_extension_generation > license_key.staff_extension_generation:
        raise SafeAPIError(ErrorCode.INTERNAL)
    return token.staff_extension_generation < license_key.staff_extension_generation


def is_managed_free_license(customer_id: int, license_key: AppLicenseKey) -> bool:
    return FreeLicenseLifecycle.objects.filter(customer_id=customer_id, license_key=license_key).exists()


def lock_device_refresh_rows(token: DeviceToken) -> tuple[AppLicenseKey, Device, DeviceToken]:
    """Re-read the authenticated rows in licence → device → token order inside the owner transaction."""
    device = token.device
    license_key = AppLicenseKey.objects.select_for_update().filter(
        pk=device.license_key_id, customer_id=device.customer_id,
    ).first()
    if license_key is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    device = Device.objects.select_for_update().filter(
        pk=device.pk, customer_id=device.customer_id, license_key=license_key,
        status=DeviceStatus.ACTIVE,
    ).first()
    if device is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    locked_token = DeviceToken.objects.select_for_update().filter(
        pk=token.pk, device=device, status=DeviceTokenStatus.ACTIVE,
        token_fingerprint=token.token_fingerprint,
    ).first()
    if locked_token is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    return license_key, device, locked_token


def renew_free_license_for_device_under_locks(
    customer: CustomerOrg,
    license_key: AppLicenseKey,
    device: Device,
    locked_token: DeviceToken,
    *,
    now: datetime | None,
    request_id: str,
    allow_token_catchup: bool = True,
) -> RenewalResult:
    """Renew managed dates after org, licence, device and token locking.

    A denial propagates to the transaction owner, which rolls back before auditing it.
    """
    marker = _locked_marker(customer, license_key)
    fallback_assigned = marker is not None and _lock_fallback_assignment(license_key)
    # Eligibility rows can wait behind staff writes. Sample liveness after both locks.
    now = now if now is not None else timezone.now()
    if locked_token.expires_at <= now:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)

    renewed = marker is not None and _renew_locked(
        customer, license_key, marker, now, request_id, fallback_assigned=fallback_assigned,
    )
    extend_token = allow_token_catchup and (renewed or (
        marker is not None
        and customer.status == CustomerStatus.ACTIVE
        and locked_token.expires_at - now <= RENEWAL_WINDOW
        and locked_token.expires_at < license_key.expires_at
        and _may_renew(marker, license_key, now, fallback_assigned=fallback_assigned)
    ))
    if extend_token:
        old_expiry = locked_token.expires_at
        locked_token.expires_at = license_key.expires_at
        locked_token.save(update_fields=["expires_at", "updated_at"])
        if not renewed:
            record_audit_event(
                FREE_SERVICE, action="device_token.free_validity_extended",
                target_type="device_token", target_id=str(locked_token.pk),
                request_id=request_id, source_surface="free_lifecycle",
                before={"expires_at": old_expiry.isoformat()},
                after={"expires_at": locked_token.expires_at.isoformat()},
            )

    license_key.customer = customer
    device.license_key = license_key
    return RenewalResult(renewed or extend_token, license_key.expires_at, locked_token.expires_at)


def renew_free_license_for_device(
    token: DeviceToken, now: datetime | None, request_id: str,
) -> RenewalResult:
    """Recheck a previously authenticated token before extending managed Free dates."""
    device = token.device
    license_key = device.license_key
    if not is_managed_free_license(device.customer_id, license_key):
        return RenewalResult(False, license_key.expires_at, token.expires_at)

    try:
        with transaction.atomic():
            customer = lock_customer_for_key_changes(device.customer_id)
            license_key, device, locked_token = lock_device_refresh_rows(token)
            result = renew_free_license_for_device_under_locks(
                customer, license_key, device, locked_token, now=now, request_id=request_id,
                allow_token_catchup=not has_pending_staff_extension(license_key, locked_token),
            )
            # Preserve the caller's authenticated instance after the locked renewal.
            token.device = device
            token.expires_at = locked_token.expires_at
            return result
    except FreeRenewalDenied as error:
        error.audit()
        raise
