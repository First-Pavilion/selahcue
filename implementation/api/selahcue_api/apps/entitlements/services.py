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

**One quantity, one field.** `instances_limit` is `AppLicenseKey.device_limit` and nothing
else, because that is the number `activate_device` enforces. Two fields in one signed,
offline-cached artefact disagreeing about the same quantity is worse than either being
wrong: the client cannot tell which to trust, and the artefact outlives the disagreement.
So the catalogue's own seat number is **not published at all** — its dimension carries
`publish_in_manifest=False` — and it stays that way until something reconciles it with
`device_limit`. There is no fourth grant state meaning "advisory, do not enforce", and a
client cannot invent one, so silence is the only honest encoding.

A dimension key absent from `grants` means the catalogue expresses nothing about it — the
client applies its own default; `null` means granted without a ceiling. Those are three
different states and the encoding keeps them apart.

**A degraded read gets a short-lived manifest.** An unconfigured catalogue and a failed
catalogue read both produce no grants, but only the first is a steady state. Minting the
usual multi-year artefact from a transient error would let a two-second blip be honoured
offline for the rest of the licence; a degraded manifest therefore expires in minutes and
self-heals on the next refresh, and is audited so an operator can alert on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from selahcue_api.apps.audit.models import AuditResult
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

logger = logging.getLogger(__name__)

# **Bump rule.** Increment this ONLY when a client that ignores unknown keys and applies
# its own default to missing ones would behave INCORRECTLY against the new payload — a
# field removed, renamed, retyped, or given a different meaning. Adding a key is not such
# a change, and bumping for one teaches the first consumer that the number is noise, so a
# genuinely breaking change later cannot be gated on it.
#
# `grants` and `plan_display_label` were added under this rule and did NOT earn a bump.
# `test_entitlement_manifest_grants.py` asserts the compatibility field by field, which is
# what actually protects a deployed client — the number never did.
ENTITLEMENT_VERSION = 1

# How long a manifest built from a FAILED catalogue read stays valid. Short on purpose:
# long enough for the device to keep working through the incident (NFR-024 — never deny an
# entitlement over server-side state), short enough that it self-heals on the next refresh
# instead of freezing the blip into a multi-year offline credential.
DEGRADED_MANIFEST_TTL_SECONDS = 900

assert 0 < DEGRADED_MANIFEST_TTL_SECONDS < 86400, (
    "a degraded manifest must outlive the incident but never approach a normal licence window"
)


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

    # A degraded manifest still issues — refusing one would deny a live service over a
    # server-side fault — but it must not outlive the fault.
    artefact_expires_at = license_key.expires_at
    if entitlement.degraded:
        artefact_expires_at = min(
            artefact_expires_at, now + timedelta(seconds=DEGRADED_MANIFEST_TTL_SECONDS)
        )
        logger.error(
            "issuing a DEGRADED entitlement manifest for device %s: the catalogue could not "
            "be read, so no grants are carried and the artefact expires in %ss",
            device.device_public_id,
            DEGRADED_MANIFEST_TTL_SECONDS,
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
        # ALWAYS `device_limit` — the number `activate_device` actually enforces, and the
        # ONLY seat number in this payload. The catalogue's `device_instances` grant is
        # deliberately unpublished (`publish_in_manifest=False`) because nothing today
        # reconciles it with this field: FR-516's write-back is specified but not built, so
        # a licence on PLATINUM would otherwise carry "7 seats" beside an enforced 3 — one
        # signed artefact promising seats the server refuses, for as long as it stays
        # cached. Publish it only once a plan change actually moves `device_limit`.
        "instances_limit": license_key.device_limit,
        # The typed grant dimensions (FR-545). Keys come from catalogue rows, so a new
        # dimension appears here without a code change; a client reads the keys it knows
        # and applies its own default to anything absent, which is what makes a removed
        # grant degrade instead of failing.
        # `dict(...)`, not the mapping itself: `published_values` is a read-only
        # MappingProxyType (so a shared cache entry cannot be mutated) and `json.dumps`
        # refuses one — the signer would raise at issuance rather than at import.
        "grants": dict(entitlement.published_values),
        "issued_at": now.isoformat(),
        "not_before": license_key.starts_at.isoformat(),
        "expires_at": artefact_expires_at.isoformat(),
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
        after={
            "key_id": envelope["key_id"],
            "expires_at": payload["expires_at"],
            # Queryable, so a rise in degraded issuance is alertable rather than buried in
            # a log line nobody greps for.
            "degraded": entitlement.degraded,
        },
        result=AuditResult.FAILED if entitlement.degraded else AuditResult.SUCCESS,
    )

    return EntitlementManifestResult(
        envelope=envelope,
        payload=payload,
        device_public_id=device.device_public_id,
    )
