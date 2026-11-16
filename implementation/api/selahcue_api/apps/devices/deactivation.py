"""Terminal customer device revocation, serialized with activation and final grant issue."""
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from selahcue_api.apps.accounts.account_overview import (
    can_deactivate, customer_identity, validate_device_public_id,
)
from selahcue_api.apps.accounts.models import CustomerUser, CustomerUserStatus
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import Device, DeviceStatus, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.services import lock_customer_for_key_changes
from selahcue_api.graphql.context import ActorContext, ActorKind, validate_idempotency_key
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

DEACTIVATION_SERVICE = ActorContext(ActorKind.SERVICE, 'customer-device-deactivation')


@dataclass(frozen=True)
class DeactivationResult:
    already_inactive: bool


def deactivate_own_device(
    actor: ActorContext | None, device_public_id: str, request_id: str,
) -> DeactivationResult:
    public_id = validate_device_public_id(device_public_id)
    if not isinstance(request_id, str):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    request_id = validate_idempotency_key(request_id)
    user_id, org_id = customer_identity(actor)
    try:
        with transaction.atomic():
            org = lock_customer_for_key_changes(org_id)
            user = CustomerUser.objects.select_for_update().filter(
                pk=user_id, customer=org, status=CustomerUserStatus.ACTIVE,
            ).first()
            if user is None:
                raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
            if not can_deactivate(user):
                raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
            # Never reveal target presence before the locked persisted authority check.
            license_id = Device.objects.filter(customer=org, device_public_id=public_id).values_list(
                'license_key_id', flat=True,
            ).first()
            license_key = AppLicenseKey.objects.select_for_update().filter(pk=license_id, customer=org).first()
            if license_key is None:
                raise SafeAPIError(ErrorCode.NOT_FOUND)
            device = Device.objects.select_for_update().filter(
                customer=org, license_key=license_key, device_public_id=public_id,
            ).first()
            if device is None:
                raise SafeAPIError(ErrorCode.NOT_FOUND)
            tokens = list(DeviceToken.objects.select_for_update().filter(device=device).exclude(
                status=DeviceTokenStatus.REVOKED,
            ).order_by('pk').values_list('pk', flat=True))
            now = timezone.now()  # Final clock, after all authority and target locks.
            if device.status == DeviceStatus.REVOKED:
                return DeactivationResult(already_inactive=True)
            Device.objects.filter(pk=device.pk).update(status=DeviceStatus.REVOKED, updated_at=now)
            DeviceToken.objects.filter(pk__in=tokens).update(status=DeviceTokenStatus.REVOKED, updated_at=now)
            record_audit_event(
                DEACTIVATION_SERVICE, action='device.deactivated', target_type='device',
                target_id=public_id, request_id=request_id, source_surface='account_graphql',
                reason='Verified account administrator deactivated a device.',
                before={'status': device.status},
                after={'status': DeviceStatus.REVOKED, 'requested_by': str(user.pk)},
            )
            return DeactivationResult(already_inactive=False)
    except SafeAPIError:
        raise
    except Exception:
        # Translation happens only after atomic has rolled back every status and audit write.
        raise SafeAPIError(ErrorCode.INTERNAL) from None
