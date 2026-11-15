"""Versioned native activation receipts with one-time credential delivery."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerRole
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import (
    ActivateDeviceResult,
    _activate_device_for_key,
    _activation_metadata,
    _activation_text,
    _assert_device_activatable,
    _existing_device_result,
    _resolve_license_key,
    require_commercial_service,
)
from selahcue_api.apps.license_keys.free_lifecycle import (
    FreeRenewalDenied,
    _authorize_managed_activation,
    _locked_marker,
    ensure_free_license_under_org_lock,
    renew_free_license_for_activation,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.services import lock_customer_for_key_changes
from selahcue_api.graphql.context import ActorContext, require_customer_role
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


@dataclass(frozen=True)
class BoundActivationData:
    operation_version: int
    mode: str
    idempotency_key: str
    expected_device_public_id: str | None
    device_fingerprint: str
    platform: str
    app_version: str
    display_name: str


@dataclass(frozen=True)
class BoundEnrollmentData(BoundActivationData):
    presented_key: str = field(repr=False)


@dataclass(frozen=True)
class BoundActivationResult:
    activation: ActivateDeviceResult
    idempotency_key: str
    operation_state: str


class CompletedActivationReceipt(SafeAPIError):
    """Authenticated proof of a completed operation whose token is unusable."""

    def __init__(self, receipt: DeviceActivationOperation, device: Device):
        super().__init__(ErrorCode.ACTIVATION_OPERATION_COMPLETED)
        self.identity = {
            "idempotency_key": receipt.operation_key,
            "device_public_id": device.device_public_id,
            "platform": device.platform,
        }


def _conflict():
    return SafeAPIError(ErrorCode.ACTIVATION_OPERATION_CONFLICT)


def _normalized(data: BoundActivationData) -> BoundActivationData:
    expected = data.expected_device_public_id
    if (
        type(data.operation_version) is not int
        or data.operation_version != 1
        or not isinstance(data.idempotency_key, str)
        or re.fullmatch(r"[a-f0-9]{32}", data.idempotency_key) is None
        or not (
            (data.mode == "initial" and expected is None)
            or (data.mode == "recover" and isinstance(expected, str)
                and re.fullmatch(r"dev_[a-f0-9]{32}", expected) is not None)
        )
    ):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    nonce, fingerprint, platform, version, name = _activation_metadata(data)
    return BoundActivationData(1, data.mode, nonce, expected, fingerprint, platform, version, name)


def activate_bound_with_key(data: BoundEnrollmentData) -> BoundActivationResult:
    request = _normalized(data)
    presented = _activation_text(data.presented_key, limit=128, required=True)
    license_key = _resolve_license_key(presented)
    return _complete(request, license_key.customer_id, "enrollment", enrollment=license_key)


def activate_bound_with_session(actor: ActorContext | None, data: BoundActivationData) -> BoundActivationResult:
    checked = require_customer_role(actor, CustomerRole.ADMIN)
    return _complete(_normalized(data), int(checked.org_id), "account_session", actor=checked)


def _complete(data, org_id, auth_path, *, enrollment=None, actor=None):
    digest = hashlib.sha256(json.dumps(
        {"organization": org_id, "auth_path": auth_path, **asdict(data)},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()
    try:
        try:
            return _transaction(data, org_id, auth_path, digest, enrollment=enrollment, actor=actor)
        except IntegrityError:
            # Different organizations take different row locks. If they race on a global
            # nonce, the failed insert rolls back every mutation from the losing transaction.
            if not DeviceActivationOperation.objects.filter(operation_key=data.idempotency_key).exists():
                raise
            return _transaction(data, org_id, auth_path, digest, enrollment=enrollment, actor=actor)
    except FreeRenewalDenied as error:
        error.audit()
        raise


def _verify_receipt(receipt, org_id, auth_path, digest, enrollment):
    if (
        receipt.organization_id != org_id
        or receipt.auth_path != auth_path
        or receipt.request_digest != digest
        or (enrollment is not None and receipt.license_key_id != enrollment.pk)
    ):
        raise _conflict()


@transaction.atomic
def _transaction(data, org_id, auth_path, digest, *, enrollment, actor):
    # Serializes simultaneous operations in the same org before resolving the
    # currently preferred licence. Different orgs arbitrate through the unique nonce.
    customer = lock_customer_for_key_changes(org_id)
    now = timezone.now()
    receipt = DeviceActivationOperation.objects.filter(operation_key=data.idempotency_key).first()
    if receipt is not None:
        _verify_receipt(receipt, org_id, auth_path, digest, enrollment)
        license_id = receipt.license_key_id
    elif enrollment is not None:
        license_id = enrollment.pk
    elif data.expected_device_public_id is not None:
        license_id = Device.objects.filter(
            customer_id=org_id, device_public_id=data.expected_device_public_id
        ).values_list("license_key_id", flat=True).first()
        if license_id is None:
            raise _conflict()
    else:
        license_id = ensure_free_license_under_org_lock(
            customer, actor, now, data.idempotency_key, defer_renewal=True,
        ).pk

    license_key = (
        AppLicenseKey.objects.select_for_update().filter(pk=license_id, customer_id=org_id).first()
    )
    if license_key is None:
        raise _conflict()
    if enrollment is not None and (
        license_key.secret_fingerprint != enrollment.secret_fingerprint
        or license_key.secret_hash != enrollment.secret_hash
    ):
        # Preserve the current authenticated proof after acquiring the licence row.
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    if enrollment is not None:
        require_commercial_service(license_key)

    devices = Device.objects.select_for_update().filter(license_key=license_key, customer_id=org_id)
    if receipt is not None:
        device = devices.filter(pk=receipt.device_id).first()
        _verify_device(data, device)
        _assert_device_activatable(device)
        # Only the original result may be observed. The PK snapshot is never used
        # as lookup authority. A concurrent SET_NULL/deletion can make this miss.
        token = DeviceToken.objects.select_for_update().filter(
            pk=receipt.result_token_id, device=device, status=DeviceTokenStatus.ACTIVE,
        ).first()
        if token is None or token.expires_at <= timezone.now():
            if actor is not None:
                may_recover = renew_free_license_for_activation(
                    customer, license_key, actor, timezone.now(), data.idempotency_key,
                    completed_without_token=True,
                )
                if not may_recover:
                    require_commercial_service(license_key)
            raise CompletedActivationReceipt(receipt, device)
        if actor is not None:
            if _locked_marker(customer, license_key) is not None:
                _authorize_managed_activation(customer, actor)
            require_commercial_service(license_key)
        activation = ActivateDeviceResult(device, token, license_key, None, False)
        return BoundActivationResult(activation, data.idempotency_key, "replay")

    if data.expected_device_public_id is not None:
        device = devices.filter(device_public_id=data.expected_device_public_id).first()
        _verify_device(data, device)
        _assert_device_activatable(device)
        if actor is not None:
            renew_free_license_for_activation(
                customer, license_key, actor, timezone.now(), data.idempotency_key,
            )
            require_commercial_service(license_key)
        activation = _existing_device_result(
            device, license_key, idempotency_key=data.idempotency_key,
            audit_actor=actor, source_surface="desktop_v1", lock_result_token=True,
        )
    else:
        # Legacy creation keys are scoped to a licence. If a stored creation key
        # collides with this nonce, verify the identity before invoking the core.
        existing = devices.filter(idempotency_key=data.idempotency_key).first()
        if existing is not None:
            _verify_device(data, existing)
        else:
            existing = devices.filter(device_fingerprint=data.device_fingerprint).first()
            if existing is not None:
                _verify_device(data, existing)
        if existing is not None:
            _assert_device_activatable(existing)
        if actor is not None:
            renew_free_license_for_activation(
                customer, license_key, actor, timezone.now(), data.idempotency_key,
            )
        activation = _activate_device_for_key(
            license_key, idempotency_key=data.idempotency_key,
            device_fingerprint=data.device_fingerprint, platform=data.platform,
            app_version=data.app_version, display_name=data.display_name,
            activated_by_actor_id=actor.actor_id if actor else None,
            audit_actor=actor, source_surface="desktop_v1", lock_result_token=True,
        )

    outcome = DeviceActivationOperation.Outcome
    DeviceActivationOperation.objects.create(
        operation_key=data.idempotency_key, organization_id=org_id, license_key=license_key,
        device=activation.device, result_token=activation.device_token,
        issued_token_pk=activation.device_token.pk, auth_path=auth_path, mode=data.mode,
        expected_device_public_id=data.expected_device_public_id, request_digest=digest,
        outcome=outcome.CREATED if activation.created else (
            outcome.REMINTED if activation.reminted else outcome.EXISTING
        ),
        completed_at=timezone.now(),
    )
    return BoundActivationResult(activation, data.idempotency_key, "completed")


def _verify_device(data, device):
    if (
        device is None
        or device.device_fingerprint != data.device_fingerprint
        or device.platform != data.platform
        or (data.expected_device_public_id is not None
            and device.device_public_id != data.expected_device_public_id)
    ):
        raise _conflict()
