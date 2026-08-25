"""Signed offline entitlement manifest (DEC-004 / DEC-005).

Assembles the payload a desktop install caches and verifies locally. Knows nothing about
HTTP; the view maps `SafeAPIError` codes to statuses.

**Issuance is an allow-list, and deliberately stricter than `/v1/license:refresh`.**
That endpoint reports honestly rather than denying, because it mints nothing. This one
mints a signed, device-bound credential cacheable until the licence expiry, and with no
revocation list issuance is the ONLY enforcement point that exists. Revoking a licence
key does not cascade to `DeviceToken`, and `authenticate_device_token` never consults
licence status — so without this gate a device under a REVOKED licence would
authenticate fine and be handed a freshly signed multi-year entitlement. The signed
artefact must never be laxer than the unsigned one. Do not harmonise the two endpoints.

**The payload carries VALUES, never a tier name (FR-545).** `grants` is a map of typed
values — a watermark flag, an output count, an NDI count, an STT allowance — resolved from
the product catalogue (FR-544). A client that branched on `"pro"` would misread every
future tier and turn every rename into a client release, to machines that are deliberately
offline; so `feature_scope` and `plan_display_label` are labels for humans to read and
nothing else. Adding a tier, or a whole new grant dimension, is a data change that an
unmodified client already honours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.services import resolve_entitlement
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import (
    ACTIVATABLE_KEY_STATUSES,
    authenticate_device_token,
)
from selahcue_api.apps.entitlements.signing import load_signing_key, sign_envelope
from selahcue_api.graphql.context import ActorContext, ActorKind
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.redaction import assert_no_restricted_payload_fields

# 2 adds `grants` and `plan_display_label`. Purely additive — every field version 1 carried
# is still present and still means the same thing, which
# `test_entitlement_manifest_grants.py` asserts field by field rather than by argument.
ENTITLEMENT_VERSION = 2


@dataclass(frozen=True)
class EntitlementManifestResult:
    envelope: dict[str, Any]
    payload: dict[str, Any]
    device_public_id: str


def build_entitlement_manifest(presented_token: str) -> EntitlementManifestResult:
    token = authenticate_device_token(presented_token)
    device = token.device
    license_key = device.license_key
    now = timezone.now()

    # Allow-list, not a deny-list: a status added to LicenseKeyStatus later denies by
    # default instead of silently qualifying for a signed entitlement.
    valid_now = (
        license_key.status in ACTIVATABLE_KEY_STATUSES
        and license_key.starts_at <= now < license_key.expires_at
    )
    if not valid_now:
        raise SafeAPIError(ErrorCode.POLICY_DENIED)

    instances_used = Device.objects.filter(
        license_key=license_key, status=DeviceStatus.ACTIVE
    ).count()

    # Never raises, whatever the catalogue contains — an unseeded, half-configured or
    # malformed catalogue yields empty grants and the manifest still issues. A licensing
    # lookup that can refuse a device its entitlement because of a bad admin edit is
    # exactly the failure NFR-024 forbids.
    entitlement = resolve_entitlement(license_key)

    # The catalogue's seat cap when it expresses one, otherwise the licence's own
    # `device_limit` — which is also what activation still enforces today
    # (`devices/services.py`). So a licence the catalogue says nothing about keeps precisely
    # the limit it had, rather than inheriting the model field's global default of 1.
    catalogue_instance_limit = entitlement.instance_limit
    instances_limit = (
        catalogue_instance_limit if catalogue_instance_limit is not None else license_key.device_limit
    )

    payload = {
        "entitlement_version": ENTITLEMENT_VERSION,
        "device_public_id": device.device_public_id,
        "device_fingerprint": device.device_fingerprint,
        "customer_org_id": str(license_key.customer_id),
        "license_status": license_key.status,
        "license_valid_now": valid_now,
        "license_starts_at": license_key.starts_at.isoformat(),
        "license_expires_at": license_key.expires_at.isoformat(),
        # Display labels, both of them. Kept for humans and for backward compatibility;
        # branching on either is the mistake FR-545 exists to prevent.
        "feature_scope": license_key.feature_scope,
        "plan_display_label": entitlement.plan_display_label,
        "territory": license_key.territory,
        "instances_used": instances_used,
        "instances_limit": instances_limit,
        # The typed grant dimensions (FR-545). Keys come from catalogue rows, so a new
        # dimension appears here without a code change; a client reads the keys it knows
        # and applies its own default to anything absent, which is what makes a removed
        # grant degrade instead of failing.
        "grants": entitlement.values,
        "issued_at": now.isoformat(),
        "not_before": license_key.starts_at.isoformat(),
        "expires_at": license_key.expires_at.isoformat(),
    }
    # Run redaction HERE, on the mapping — this is the only layer where the payload is
    # still walkable. Against the envelope it would be theatre: the payload is by then an
    # opaque base64 string the assertion walks straight past.
    assert_no_restricted_payload_fields(payload)

    envelope = sign_envelope(payload, private_key=load_signing_key())

    record_audit_event(
        ActorContext(kind=ActorKind.DEVICE, actor_id=device.device_public_id),
        action="entitlement.manifest_issued",
        target_type="device",
        target_id=str(device.id),
        request_id=device.device_public_id,
        source_surface="desktop_v1",
        after={"key_id": envelope["key_id"], "expires_at": payload["expires_at"]},
    )

    return EntitlementManifestResult(
        envelope=envelope,
        payload=payload,
        device_public_id=device.device_public_id,
    )
