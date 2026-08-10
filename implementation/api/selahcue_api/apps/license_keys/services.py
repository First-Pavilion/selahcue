from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.graphql.context import (
    ActorContext,
    StaffPermission,
    require_reason,
    require_staff_permission,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
KEY_BODY_GROUPS = 8
KEY_GROUP_SIZE = 4


@dataclass(frozen=True)
class GenerateLicenseKeyData:
    idempotency_key: str
    customer_id: str
    key_type: str
    feature_scope: str
    starts_at: datetime
    expires_at: datetime
    timezone: str
    seat_limit: int
    device_limit: int
    territory: str
    reason: str


@dataclass(frozen=True)
class GenerateLicenseKeyResult:
    license_key: AppLicenseKey
    full_key: str | None
    created: bool


def _validation_error() -> SafeAPIError:
    return SafeAPIError(ErrorCode.VALIDATION_FAILED)


def _clean_license_key(license_key: AppLicenseKey) -> None:
    try:
        license_key.full_clean()
    except ValidationError as error:
        raise _validation_error() from error


def _coerce_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _generate_full_key(key_type: LicenseKeyType) -> str:
    groups = [
        "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_GROUP_SIZE))
        for _ in range(KEY_BODY_GROUPS)
    ]
    return f"SC-{key_type.value}-{'-'.join(groups)}"


def _fingerprint(full_key: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        full_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _mask(full_key: str) -> tuple[str, str, str]:
    prefix = full_key[:12]
    suffix = full_key[-4:]
    return prefix, suffix, f"{prefix}...{suffix}"


def generate_license_key(
    actor: ActorContext | None,
    data: GenerateLicenseKeyData,
) -> GenerateLicenseKeyResult:
    staff = require_staff_permission(actor, StaffPermission.GENERATE_LICENSE_KEY)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = require_reason(data.reason)

    try:
        key_type = LicenseKeyType(data.key_type)
    except ValueError as error:
        raise _validation_error() from error

    starts_at = _coerce_datetime(data.starts_at)
    expires_at = _coerce_datetime(data.expires_at)
    if expires_at <= starts_at:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    if data.seat_limit < 1 or data.device_limit < 1:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    with transaction.atomic():
        existing = (
            AppLicenseKey.objects.select_related("customer")
            .filter(generated_by_actor_id=staff.actor_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)

        try:
            customer = CustomerOrg.objects.get(id=data.customer_id)
        except (CustomerOrg.DoesNotExist, ValueError) as error:
            raise SafeAPIError(ErrorCode.NOT_FOUND) from error
        if customer.status == CustomerStatus.ARCHIVED:
            raise SafeAPIError(ErrorCode.POLICY_DENIED)

        full_key = _generate_full_key(key_type)
        prefix, suffix, masked_key = _mask(full_key)
        license_key = AppLicenseKey(
            customer=customer,
            key_type=key_type,
            status=LicenseKeyStatus.ISSUED,
            key_prefix=prefix,
            key_suffix=suffix,
            masked_key=masked_key,
            secret_hash=make_password(full_key),
            secret_fingerprint=_fingerprint(full_key),
            starts_at=starts_at,
            expires_at=expires_at,
            timezone=data.timezone.strip() or "UTC",
            feature_scope=data.feature_scope.strip().upper(),
            seat_limit=data.seat_limit,
            device_limit=data.device_limit,
            territory=data.territory.strip().upper(),
            generated_by_actor_id=staff.actor_id,
            generated_reason=reason,
            idempotency_key=idempotency_key,
        )
        _clean_license_key(license_key)
        # Concurrency-safe idempotency: a racing call with the same (actor, idempotency_key) can
        # pass the check above; the unique constraint rejects the loser's INSERT. Catch it in a
        # savepoint and return the winner's key as an idempotent replay (full_key=None) rather than
        # a spurious internal error. (Mirrors `activate_device`.)
        try:
            with transaction.atomic():
                license_key.save()
        except IntegrityError:
            existing = (
                AppLicenseKey.objects.select_related("customer")
                .filter(generated_by_actor_id=staff.actor_id, idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)
            raise _validation_error()
        record_audit_event(
            staff,
            action="license_key.generated",
            target_type="app_license_key",
            target_id=str(license_key.id),
            request_id=idempotency_key,
            reason=reason,
            after={
                "customer_id": str(customer.id),
                "key_type": license_key.key_type,
                "status": license_key.status,
                "key_prefix": license_key.key_prefix,
                "key_suffix": license_key.key_suffix,
                "masked_key": license_key.masked_key,
                "feature_scope": license_key.feature_scope,
                "starts_at": license_key.starts_at.isoformat(),
                "expires_at": license_key.expires_at.isoformat(),
                "seat_limit": license_key.seat_limit,
                "device_limit": license_key.device_limit,
                "territory": license_key.territory,
            },
        )
        return GenerateLicenseKeyResult(license_key=license_key, full_key=full_key, created=True)
