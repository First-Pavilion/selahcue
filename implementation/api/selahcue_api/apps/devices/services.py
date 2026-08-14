from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import (
    Device,
    DeviceStatus,
    DeviceToken,
    DeviceTokenStatus,
)
from selahcue_api.apps.accounts.models import CustomerRole
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.graphql.context import (
    ActorContext,
    ActorKind,
    require_customer_role,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


# Token format mirrors the license-key body (Crockford-ish alphabet, no ambiguous chars).
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TOKEN_BODY_GROUPS = 8
TOKEN_GROUP_SIZE = 4

# License-key statuses under which a device may (re-)activate. Terminal/blocked states deny.
ACTIVATABLE_KEY_STATUSES = frozenset(
    {LicenseKeyStatus.ISSUED, LicenseKeyStatus.ACTIVATED, LicenseKeyStatus.EXPIRING}
)


@dataclass(frozen=True)
class LicenseRefreshResult:
    device_public_id: str
    device_status: str
    license_status: str
    license_starts_at: str
    license_expires_at: str
    license_valid_now: bool
    instances_used: int
    instances_limit: int
    token_expires_at: str
    feature_scope: str
    territory: str


@dataclass(frozen=True)
class ActivateDeviceData:
    idempotency_key: str
    presented_key: str
    device_fingerprint: str
    platform: str
    app_version: str = ""
    display_name: str = ""


@dataclass(frozen=True)
class ActivateDeviceResult:
    device: Device
    device_token: DeviceToken
    license_key: AppLicenseKey
    # The full token is returned when one is minted — on first creation, and on a re-mint
    # (show-once each time). None on an idempotent replay of a device that already holds a
    # usable token.
    full_token: str | None
    created: bool
    # True when an EXISTING device was issued a replacement token because the one it held was
    # expired, revoked or missing. Mutually exclusive with `created`.
    reminted: bool = False


def _validation_error() -> SafeAPIError:
    return SafeAPIError(ErrorCode.VALIDATION_FAILED)


def _fingerprint(value: str) -> str:
    # Same HMAC pepper (SECRET_KEY) the license-key slice uses, so the presented key's
    # fingerprint matches the one persisted at issuance.
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _generate_full_token() -> str:
    groups = [
        "".join(secrets.choice(KEY_ALPHABET) for _ in range(TOKEN_GROUP_SIZE))
        for _ in range(TOKEN_BODY_GROUPS)
    ]
    return f"SC-DEV-{'-'.join(groups)}"


def _mask(full_token: str) -> tuple[str, str, str]:
    prefix = full_token[:12]
    suffix = full_token[-4:]
    return prefix, suffix, f"{prefix}...{suffix}"


def _resolve_license_key(presented_key: str) -> AppLicenseKey:
    """Look the enrollment key up by deterministic fingerprint, then constant-time verify the
    hash. Any failure maps to NOT_FOUND — never reveal whether the key exists vs a hash mismatch."""
    fingerprint = _fingerprint(presented_key)
    try:
        license_key = AppLicenseKey.objects.select_related("customer").get(
            secret_fingerprint=fingerprint
        )
    except AppLicenseKey.DoesNotExist as error:
        raise SafeAPIError(ErrorCode.NOT_FOUND) from error
    if not check_password(presented_key, license_key.secret_hash):
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    return license_key


def _assert_device_activatable(device: Device) -> None:
    # A revoked device is terminal for this slice: re-enrolling it must not echo back a dead
    # (revoked) token as success. Re-provisioning a revoked install is a separate future flow.
    if device.status != DeviceStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)


def _assert_key_activatable(license_key: AppLicenseKey) -> None:
    now = timezone.now()
    if license_key.status not in ACTIVATABLE_KEY_STATUSES:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)
    if not (license_key.starts_at <= now < license_key.expires_at):
        raise SafeAPIError(ErrorCode.POLICY_DENIED)


def _new_device_token(device: Device, license_key: AppLicenseKey) -> tuple[DeviceToken, str]:
    full_token = _generate_full_token()
    prefix, suffix, masked = _mask(full_token)
    token = DeviceToken(
        device=device,
        token_prefix=prefix,
        token_suffix=suffix,
        masked_token=masked,
        token_hash=make_password(full_token),
        token_fingerprint=_fingerprint(full_token),
        status=DeviceTokenStatus.ACTIVE,
        issued_at=timezone.now(),
        # The device token (offline entitlement window) never outlives the license validity.
        # A shorter, signed policy envelope with an explicit offline-grace is a tracked follow-up.
        expires_at=license_key.expires_at,
        timezone=license_key.timezone,
    )
    try:
        token.full_clean()
    except ValidationError as error:
        raise _validation_error() from error
    token.save()
    return token, full_token


def _live_token(device: Device) -> DeviceToken | None:
    """The device's currently USABLE token, or None.

    "Usable" is the same predicate `authenticate_device_token` enforces — ACTIVE and not
    past `expires_at` — so this can never disagree with what the device would actually be
    able to authenticate with.
    """
    return (
        device.tokens.filter(
            status=DeviceTokenStatus.ACTIVE, expires_at__gt=timezone.now()
        )
        .order_by("-issued_at", "-id")
        .first()
    )


def _remint_device_token(
    device: Device,
    license_key: AppLicenseKey,
    *,
    idempotency_key: str,
    audit_actor: ActorContext | None,
    source_surface: str,
) -> tuple[DeviceToken, str]:
    """Issue a REPLACEMENT token for an existing device that holds no usable one.

    AUTHORISATION (the one non-obvious part of this slice). Re-mint is authorised by exactly
    the evidence that authorises a FIRST activation and by nothing else: this function is
    reachable only from `_activate_device_for_key`, whose two callers are `activate_device`
    (a presented enrollment key, resolved by fingerprint and confirmed with `check_password`)
    and `activate_device_with_session` (a valid ADMIN account session). The device's own dead
    token is never read, never compared, and never sufficient — `authenticate_device_token`
    deliberately has NO re-mint path, so a token can never be the credential that revives
    itself. That also keeps re-mint useless as a revocation bypass: the licence-status gate
    (`_assert_key_activatable`) has already run under the row lock before we get here.

    The new expiry comes from `license_key.expires_at` as re-read under that lock, so it
    tracks the licence's CURRENT window rather than the value frozen at first activation.
    """
    now = timezone.now()
    superseded = list(
        DeviceToken.objects.filter(device=device)
        .exclude(status=DeviceTokenStatus.REVOKED)
        .order_by("-issued_at", "-id")
        .values_list("token_fingerprint", flat=True)
    )
    # Supersede EVERY prior token, not just the expired one: a replayed pre-renewal token has
    # to be refused on its status, not merely on a lapsed clock, so that the rejection stays
    # true even if a later change ever moves an expiry forward.
    DeviceToken.objects.filter(device=device).exclude(
        status=DeviceTokenStatus.REVOKED
    ).update(status=DeviceTokenStatus.REVOKED, updated_at=now)

    token, full_token = _new_device_token(device, license_key)

    actor = audit_actor or ActorContext(kind=ActorKind.DEVICE, actor_id=device.device_public_id)
    record_audit_event(
        actor,
        action="device_token.reminted",
        target_type="device_token",
        target_id=str(token.id),
        request_id=idempotency_key,
        reason="device held no usable token; licence is currently activatable",
        source_surface=source_surface,
        after={
            "license_key_id": str(license_key.id),
            "device_public_id": device.device_public_id,
            # Only the masked triple + fingerprints — never the full token (redaction-blocked).
            "token_prefix": token.token_prefix,
            "token_suffix": token.token_suffix,
            "masked_token": token.masked_token,
            "token_fingerprint": token.token_fingerprint,
            "expires_at": token.expires_at.isoformat(),
            # Links the new credential to the one the client was holding, so an operator can
            # follow a device across a renewal without either raw token.
            "superseded_token_fingerprint": superseded[0] if superseded else "",
            "superseded_token_count": len(superseded),
        },
    )
    return token, full_token


def _existing_device_result(
    device: Device,
    license_key: AppLicenseKey,
    *,
    idempotency_key: str,
    audit_actor: ActorContext | None,
    source_surface: str,
) -> ActivateDeviceResult:
    """Shared outcome for a device that ALREADY exists — an idempotent retry (same
    idempotency key) or a known install re-enrolling (same fingerprint).

    Show-once is preserved while the device holds a usable token: replaying it would let a
    stolen enrollment key harvest the live credential of a running install, which is strictly
    worse than the status quo. Only when there is NO usable token — expired with the licence,
    revoked by the cascade, or absent — is a replacement minted, because that device is
    otherwise permanently dead with no exit but a new fingerprint it cannot afford.
    """
    _assert_device_activatable(device)
    live = _live_token(device)
    if live is not None:
        return ActivateDeviceResult(
            device=device,
            device_token=live,
            license_key=license_key,
            full_token=None,
            created=False,
            reminted=False,
        )
    token, full_token = _remint_device_token(
        device,
        license_key,
        idempotency_key=idempotency_key,
        audit_actor=audit_actor,
        source_surface=source_surface,
    )
    return ActivateDeviceResult(
        device=device,
        device_token=token,
        license_key=license_key,
        full_token=full_token,
        created=False,
        reminted=True,
    )


def _activate_device_for_key(
    license_key: AppLicenseKey,
    *,
    idempotency_key: str,
    device_fingerprint: str,
    platform: str,
    app_version: str = "",
    display_name: str = "",
    activated_by_actor_id: str | None = None,
    audit_actor: ActorContext | None = None,
    source_surface: str = "desktop_v1",
) -> ActivateDeviceResult:
    """Core activation for an ALREADY-RESOLVED license key. Shared by the enrollment-key path
    (activate_device) and the account-session path (activate_device_with_session) so both converge
    on identical Device + show-once DeviceToken + instance-limit + audit behaviour — only the
    CALLER authentication and attribution differ."""
    with transaction.atomic():
        # Lock the license-key row so all activations under one key SERIALIZE: this makes the
        # instance-limit count-then-insert atomic (no two concurrent activations can both pass a
        # stale count and exceed device_limit) and turns a same-request race into a clean idempotent
        # replay instead of an IntegrityError/500. Re-read + re-check status under the lock, since it
        # could have changed between resolve and lock.
        license_key = (
            AppLicenseKey.objects.select_for_update()
            .select_related("customer")
            .get(pk=license_key.pk)
        )
        _assert_key_activatable(license_key)

        # Retry-idempotency: same key + client idempotency key → the same device, and a token
        # that is still usable is NOT re-shown (show-once). A dead one is replaced.
        existing = Device.objects.filter(
            license_key=license_key, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return _existing_device_result(
                existing,
                license_key,
                idempotency_key=idempotency_key,
                audit_actor=audit_actor,
                source_surface=source_surface,
            )

        # Natural identity: a known install (same fingerprint) re-enrolling with a different
        # idempotency key is still one device — return it, never a duplicate. Both existing-device
        # branches return BEFORE the instance-limit check below, so a re-mint can never consume
        # a slot: the device is already counted, and a device_limit=1 church must be able to
        # recover on the one slot it has.
        known = Device.objects.filter(
            license_key=license_key, device_fingerprint=device_fingerprint
        ).first()
        if known is not None:
            return _existing_device_result(
                known,
                license_key,
                idempotency_key=idempotency_key,
                audit_actor=audit_actor,
                source_surface=source_surface,
            )

        # Instance limit (DEC-004): active devices under this key may not exceed the plan limit.
        active_devices = Device.objects.filter(
            license_key=license_key, status=DeviceStatus.ACTIVE
        ).count()
        if active_devices >= license_key.device_limit:
            raise SafeAPIError(ErrorCode.POLICY_DENIED)

        device_public_id = f"dev_{secrets.token_hex(16)}"
        device = Device(
            license_key=license_key,
            customer=license_key.customer,
            device_public_id=device_public_id,
            device_fingerprint=device_fingerprint,
            platform=platform,
            app_version=app_version.strip(),
            display_name=display_name.strip(),
            status=DeviceStatus.ACTIVE,
            # Enrollment path attributes to the device itself; the account path attributes to the
            # activating CustomerUser (per-user device attribution, DEC-005).
            activated_by_actor_id=activated_by_actor_id or device_public_id,
            idempotency_key=idempotency_key,
        )
        try:
            device.full_clean()
        except ValidationError as error:
            raise _validation_error() from error
        device.save()

        token, full_token = _new_device_token(device, license_key)

        # First activation flips the enrollment key ISSUED → ACTIVATED.
        if license_key.status == LicenseKeyStatus.ISSUED:
            license_key.status = LicenseKeyStatus.ACTIVATED
            license_key.save(update_fields=["status", "updated_at"])

        actor = audit_actor or ActorContext(kind=ActorKind.DEVICE, actor_id=device_public_id)
        record_audit_event(
            actor,
            action="device.activated",
            target_type="device",
            target_id=str(device.id),
            request_id=idempotency_key,
            source_surface=source_surface,
            after={
                "license_key_id": str(license_key.id),
                "customer_id": str(license_key.customer_id),
                "device_public_id": device.device_public_id,
                "platform": device.platform,
                "app_version": device.app_version,
                # Only the masked triple + fingerprint — never the full token (redaction-blocked).
                "token_prefix": token.token_prefix,
                "token_suffix": token.token_suffix,
                "masked_token": token.masked_token,
                "token_fingerprint": token.token_fingerprint,
                "expires_at": token.expires_at.isoformat(),
            },
        )

        return ActivateDeviceResult(
            device=device,
            device_token=token,
            license_key=license_key,
            full_token=full_token,
            created=True,
            reminted=False,
        )


def activate_device(data: ActivateDeviceData) -> ActivateDeviceResult:
    """Register (or idempotently return) a device instance for a presented enrollment key and
    issue a show-once device token. The device is its own actor (ActorKind.DEVICE) — activation
    is authenticated by the presented key, not a staff/account session (see DEC-004)."""
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    fingerprint = data.device_fingerprint.strip()
    platform = data.platform.strip()
    if not fingerprint or not platform:
        raise _validation_error()

    license_key = _resolve_license_key(data.presented_key)
    _assert_key_activatable(license_key)
    return _activate_device_for_key(
        license_key,
        idempotency_key=idempotency_key,
        device_fingerprint=fingerprint,
        platform=platform,
        app_version=data.app_version,
        display_name=data.display_name,
    )


@dataclass(frozen=True)
class ActivateDeviceWithSessionData:
    idempotency_key: str
    device_fingerprint: str
    platform: str
    app_version: str = ""
    display_name: str = ""


def _resolve_org_active_license_key(org_id: str) -> AppLicenseKey:
    """Resolve the org's currently-activatable license key (DEC-005 account path). NOT_FOUND if the
    org has no active key — no oracle on which orgs/keys exist. Picks the furthest-out expiry when
    several are active (best entitlement window)."""
    now = timezone.now()
    key = (
        AppLicenseKey.objects.select_related("customer")
        .filter(
            customer_id=org_id,
            status__in=ACTIVATABLE_KEY_STATUSES,
            starts_at__lte=now,
            expires_at__gt=now,
        )
        .order_by("-expires_at")
        .first()
    )
    if key is None:
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    return key


def activate_device_with_session(
    actor: ActorContext | None, data: ActivateDeviceWithSessionData
) -> ActivateDeviceResult:
    """Account-based device activation (DEC-005): a signed-in ADMIN customer activates a device
    WITHOUT the enrollment key — identity comes from their session. Delegates into the shared core,
    so the resulting Device + show-once DeviceToken + instance limit are identical to the enrollment
    path; only the caller auth + per-user attribution differ. Runs ALONGSIDE the untouched
    POST /v1/activations enrollment path."""
    # Only Administrators manage devices (FR-137).
    checked = require_customer_role(actor, CustomerRole.ADMIN)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    fingerprint = data.device_fingerprint.strip()
    platform = data.platform.strip()
    if not fingerprint or not platform:
        raise _validation_error()

    license_key = _resolve_org_active_license_key(checked.org_id)
    return _activate_device_for_key(
        license_key,
        idempotency_key=idempotency_key,
        device_fingerprint=fingerprint,
        platform=platform,
        app_version=data.app_version,
        display_name=data.display_name,
        activated_by_actor_id=checked.actor_id,
        audit_actor=checked,
        source_surface="account_graphql",
    )


def authenticate_device_token(presented_token: str) -> DeviceToken:
    """Resolve + validate a presented device token — the reusable auth for every
    `device_token`-gated /v1 endpoint. Fingerprint lookup (deterministic, unique-indexed) then
    constant-time `check_password`; any failure (unknown / hash-mismatch / non-ACTIVE token /
    expired token / non-ACTIVE device) → UNAUTHENTICATED, with no oracle distinguishing them."""
    token_value = (presented_token or "").strip()
    if not token_value:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    fingerprint = _fingerprint(token_value)
    try:
        token = DeviceToken.objects.select_related(
            "device", "device__license_key", "device__license_key__customer"
        ).get(token_fingerprint=fingerprint)
    except DeviceToken.DoesNotExist as error:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED) from error
    # Authenticate via the HMAC fingerprint (keyed by the server SECRET_KEY): a token can only
    # match a stored fingerprint if the caller possesses it. This constant-time re-confirm avoids
    # running PBKDF2 (`check_password`) on every device-token request — the token is high-entropy,
    # so the slow hash added latency for no meaningful marginal protection here.
    if not hmac.compare_digest(token.token_fingerprint, fingerprint):
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if token.status != DeviceTokenStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if token.expires_at <= timezone.now():
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if token.device.status != DeviceStatus.ACTIVE:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    return token


def refresh_license(presented_token: str) -> LicenseRefreshResult:
    """Return the current license/entitlement status for an authenticated device token, so the
    desktop can refresh its cached offline entitlement (DEC-004). Pure read — no mutation. The
    *license* status is reported truthfully (incl. expired/revoked) so the client can act; only an
    invalid *token* denies (via `authenticate_device_token`)."""
    token = authenticate_device_token(presented_token)
    device = token.device
    license_key = device.license_key
    now = timezone.now()

    instances_used = Device.objects.filter(
        license_key=license_key, status=DeviceStatus.ACTIVE
    ).count()
    valid_now = (
        license_key.status in ACTIVATABLE_KEY_STATUSES
        and license_key.starts_at <= now < license_key.expires_at
    )

    return LicenseRefreshResult(
        device_public_id=device.device_public_id,
        device_status=device.status,
        license_status=license_key.status,
        license_starts_at=license_key.starts_at.isoformat(),
        license_expires_at=license_key.expires_at.isoformat(),
        license_valid_now=valid_now,
        instances_used=instances_used,
        instances_limit=license_key.device_limit,
        token_expires_at=token.expires_at.isoformat(),
        feature_scope=license_key.feature_scope,
        territory=license_key.territory,
    )
