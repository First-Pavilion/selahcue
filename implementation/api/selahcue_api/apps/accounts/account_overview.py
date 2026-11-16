"""Read-only, own-org account projection. No credentials, provider calls or admission verdicts."""

import base64
import binascii
import re
from dataclasses import dataclass, replace
from datetime import datetime

from selahcue_api.apps.accounts.models import (
    CustomerOrg, CustomerRole, CustomerStatus, CustomerUser, CustomerUserStatus,
)
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.license_keys.free_lifecycle import _may_renew
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle
from selahcue_api.apps.license_keys.selection import (
    aware_utc, find_eligible_org_license, license_window_allows_service,
)
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.usage.contracts import QuotaSnapshot
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.services import remaining
from selahcue_api.graphql.context import ActorContext, ActorKind, has_control_characters
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

MAX_COUNTER = 2**63 - 1
_POSITIVE_ID = re.compile(r'[1-9][0-9]{0,18}')
_CURSOR = re.compile(r'[A-Za-z0-9_-]{1,343}')
QUOTA_STATUSES = frozenset({'current_observed', 'stale', 'not_initialized'})


@dataclass(frozen=True)
class AccountLicense:
    status: str
    starts_at: datetime
    expires_at: datetime
    valid_now: bool
    renewal: str
    device_limit: int
    active_device_count: int


@dataclass(frozen=True)
class AccountAllowance:
    plan_display_name: str
    stt: QuotaSnapshot
    notes: QuotaSnapshot


@dataclass(frozen=True)
class AccountDevice:
    public_id: str
    display_name: str
    platform: str
    app_version: str
    created_at: datetime
    status: str


@dataclass(frozen=True)
class AccountDevicePage:
    nodes: tuple[AccountDevice, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class AccountOverview:
    org_name: str
    display_name: str
    email: str
    role: str
    can_deactivate_devices: bool
    license: AccountLicense | None
    allowance: AccountAllowance | None
    devices: AccountDevicePage


def customer_identity(actor: ActorContext | None) -> tuple[int, int]:
    """Validate untrusted principal text once, before any ORM coercion or lookup."""
    if not isinstance(actor, ActorContext):
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if actor.kind is not ActorKind.CUSTOMER:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    result = []
    for value, code in ((actor.actor_id, ErrorCode.UNAUTHENTICATED),
                        (actor.org_id, ErrorCode.NOT_FOUND)):
        if not isinstance(value, str) or not _POSITIVE_ID.fullmatch(value):
            raise SafeAPIError(code)
        pk = int(value)
        if pk > MAX_COUNTER:
            raise SafeAPIError(code)
        result.append(pk)
    return result[0], result[1]


def can_deactivate(user: CustomerUser) -> bool:
    return (
        user.status == CustomerUserStatus.ACTIVE
        and user.email_verified_at is not None
        and user.role == CustomerRole.ADMIN
    )


def validate_device_public_id(value: str) -> str:
    if (
        not isinstance(value, str) or not 1 <= len(value) <= 64
        or has_control_characters(value) or not value.strip()
    ):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from None
    return value


def encode_cursor(public_id: str) -> str:
    return base64.urlsafe_b64encode(b'\x01' + validate_device_public_id(public_id).encode('utf-8')).decode('ascii').rstrip('=')


def decode_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not _CURSOR.fullmatch(cursor):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    try:
        raw = base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True)
        if not raw or raw[0] != 1:
            raise ValueError
        public_id = validate_device_public_id(raw[1:].decode('utf-8', errors='strict'))
        if encode_cursor(public_id) != cursor:
            raise ValueError
        return public_id
    except (ValueError, UnicodeError, binascii.Error):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from None


def counter(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise SafeAPIError(ErrorCode.INTERNAL)
    return value


def _quota(snapshot: QuotaSnapshot, at: datetime) -> QuotaSnapshot:
    for field in ('limit', 'settled', 'held', 'carried_debt', 'remaining'):
        counter(getattr(snapshot, field))
    if snapshot.status not in QUOTA_STATUSES:
        raise SafeAPIError(ErrorCode.INTERNAL)
    return replace(snapshot, as_of=at, resets_at=aware_utc(snapshot.resets_at))


def _allowance(org: CustomerOrg, at: datetime) -> AccountAllowance | None:
    try:
        plan = effective_plan(org, at)
    except LookupError:
        return None
    display_name = Plan.objects.filter(pk=plan.plan_id).values_list('display_name', flat=True).first()
    if display_name is None:
        return None
    try:
        snapshots = remaining(org, at)
    except LookupError:
        # The plan can disappear between the two read-only resolutions.
        return None
    if snapshots is None:
        return None
    stt, notes = snapshots
    if stt.meter != 'stt' or notes.meter != 'notes':
        raise SafeAPIError(ErrorCode.INTERNAL)
    mapping_id = ProviderCredential.objects.filter(
        org=org, provider='deepgram', state='ACTIVE',
    ).values_list('pk', flat=True).first()
    status = 'not_initialized' if mapping_id is None else read_stt_readiness(
        org_id=org.pk, mapping_id=mapping_id, at=at,
    ).status
    return AccountAllowance(display_name, _quota(replace(stt, status=status), at), _quota(notes, at))


def _license(org: CustomerOrg, at: datetime) -> AccountLicense | None:
    selected = find_eligible_org_license(org.pk, at)
    if selected is None:
        managed_id = FreeLicenseLifecycle.objects.filter(
            customer=org, license_key__customer=org,
        ).values_list('license_key_id', flat=True).first()
        if managed_id is not None:
            selected = AppLicenseKey.objects.filter(pk=managed_id, customer=org).first()
    if selected is None:
        return None
    marker = FreeLicenseLifecycle.objects.filter(customer=org, license_key=selected).first()
    renewal = 'NOT_MANAGED'
    if marker is not None:
        fallback = LicensePlanAssignment.objects.filter(license_key=selected, plan__is_fallback=True).exists()
        renewal = 'AUTOMATIC' if (
            org.status == CustomerStatus.ACTIVE and _may_renew(marker, selected, at, fallback_assigned=fallback)
        ) else 'UNAVAILABLE'
    count = counter(Device.objects.filter(license_key=selected, status=DeviceStatus.ACTIVE).count())
    if type(selected.device_limit) is not int or not 0 <= selected.device_limit <= 2**31 - 1:
        raise SafeAPIError(ErrorCode.INTERNAL)
    return AccountLicense(
        selected.status, aware_utc(selected.starts_at), aware_utc(selected.expires_at),
        license_window_allows_service(status=selected.status, starts_at=selected.starts_at,
                                      expires_at=selected.expires_at, at=at),
        renewal, selected.device_limit, count,
    )


def account_overview(
    actor: ActorContext | None, at: datetime, after: str | None, first: int = 20,
) -> AccountOverview:
    if type(first) is not int or not 1 <= first <= 100:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    anchor = decode_cursor(after)
    user_id, org_id = customer_identity(actor)
    try:
        at = aware_utc(at)
        user = CustomerUser.objects.select_related('customer').filter(
            pk=user_id, customer_id=org_id, status=CustomerUserStatus.ACTIVE,
        ).first()
        if user is None:
            code = ErrorCode.UNAUTHENTICATED if CustomerOrg.objects.filter(pk=org_id).exists() else ErrorCode.NOT_FOUND
            raise SafeAPIError(code)
        org = user.customer
        selected = _license(org, at)
        allowance = _allowance(org, at)
        rows = Device.objects.filter(customer=org, status=DeviceStatus.ACTIVE)
        if anchor is not None:
            rows = rows.filter(device_public_id__gt=anchor)
        page = list(rows.order_by('device_public_id').values(
            'device_public_id', 'display_name', 'platform', 'app_version', 'created_at', 'status',
        )[:first + 1])
        try:
            nodes = tuple(AccountDevice(
                validate_device_public_id(row['device_public_id']), row['display_name'], row['platform'],
                row['app_version'], aware_utc(row['created_at']), row['status'],
            ) for row in page[:first])
        except SafeAPIError:
            # Input was validated before DB work; invalid stored data is our fault.
            raise SafeAPIError(ErrorCode.INTERNAL) from None
        cursor = encode_cursor(nodes[-1].public_id) if len(page) > first else None
        return AccountOverview(org.name, user.display_name, user.email, user.role, can_deactivate(user),
                               selected, allowance, AccountDevicePage(nodes, cursor))
    except SafeAPIError:
        raise
    except Exception:
        # No database exception, SQL or exception chain crosses the account boundary.
        raise SafeAPIError(ErrorCode.INTERNAL) from None
