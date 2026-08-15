"""Device-token re-mint (86ak108w0 / audit gap G1).

`DeviceToken.expires_at` is frozen from the licence at first issuance. Before this slice
`_new_device_token` had exactly ONE call site — the create-device branch — so the
known-fingerprint and idempotency-replay branches handed back whatever token already
existed, however dead. A renewed licence therefore could not revive a device: the
re-activation returned HTTP 200 with `activation_token: null` and a token already past its
`expires_at`, and every device-token-authed endpoint 401'd forever. The only escape was a
new fingerprint, which burns an instance slot nothing can reclaim.

THE SECURITY BOUNDARY THIS FILE PINS
------------------------------------
Re-mint is authorised by exactly the evidence that authorises a FIRST activation — a valid
presented enrollment key, or a valid ADMIN account session — and by nothing else. A dead
token is never a credential for reviving itself: `test_a_dead_token_alone_cannot_authorise_
its_own_remint` asserts that every device-token-authed surface still refuses it, and
`test_remint_needs_the_real_enrollment_key` asserts a wrong key mints nothing even for a
known fingerprint.
"""

import base64
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import (
    Device,
    DeviceStatus,
    DeviceToken,
    DeviceTokenStatus,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """`/v1` is rate limited per (endpoint, client IP), and the default LocMemCache lives for
    the whole pytest process — so budget spent by an earlier test would otherwise leak into
    this one and 429 it. Reset the window instead of loosening the limits."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def signing_key(settings):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    return TEST_SEED_B64


# Module-local seeding helper, following the shipped slices (each builds its own rather
# than sharing a conftest.py).
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Create a customer + issue a licence key through the real service.
    Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Remint Church {tag}",
        slug=f"remint-church-{tag}",
        primary_contact_email=f"ops+{tag}@remint.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )
    result = generate_license_key(
        actor,
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for device-token re-mint tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(client, *, license_key, fingerprint="fp-remint", idem="remint-act-000001", **extra):
    body = {
        "idempotency_key": idem,
        "license_key": license_key,
        "device_fingerprint": fingerprint,
        "platform": "macos",
    }
    body.update(extra)
    return client.post(
        "/v1/activations", data=json.dumps(body), content_type="application/json"
    )


def _refresh(client, token):
    return client.post(
        "/v1/license:refresh",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _manifest(client, token):
    return client.get(
        "/v1/entitlements/manifest", HTTP_AUTHORIZATION=f"Bearer {token}"
    )


def _expire_tokens(key, *, at):
    """Age this licence's device tokens so they are genuinely expired.

    `issued_at` has to move back with `expires_at`: the `device_token_expires_after_issue`
    CHECK constraint forbids a token that expires before it was issued, and a really-aged
    token was of course issued earlier still.
    """
    DeviceToken.objects.filter(device__license_key=key).update(
        issued_at=at - timedelta(days=30), expires_at=at
    )


def _usable_tokens():
    """Tokens a device could actually authenticate with — the same predicate `_live_token` and
    `authenticate_device_token` use. NOT `status=ACTIVE` alone: `_expire_tokens` ages a token
    past `expires_at` while leaving its status ACTIVE, which is exactly the bricked state these
    tests create, so counting bare ACTIVE rows would count dead credentials as live ones."""
    return DeviceToken.objects.filter(
        status=DeviceTokenStatus.ACTIVE, expires_at__gt=timezone.now()
    )


def _renew(key, *, expires_at, status=LicenseKeyStatus.ACTIVATED):
    """What staff renewal does today: extend the window and put the key back in an
    activatable status. (The lifecycle mutations themselves are gap G2, a separate ticket —
    tests drive the same end state directly.)"""
    AppLicenseKey.objects.filter(pk=key.pk).update(
        expires_at=expires_at, status=status, updated_at=timezone.now()
    )
    key.refresh_from_db()
    return key


# --- AC1 + AC7: the whole bricking chain, and the recovery ------------------------------
def test_renewed_licence_revives_an_expired_device_token(client):
    """The verified failure chain end to end: activate, let the licence lapse, watch every
    device-authed surface 401, renew, and re-activate back to a working device."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="renew", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )

    first = _activate(client, license_key=full_key, fingerprint="mac-booth", idem="remint-renew-01")
    assert first.status_code == 200
    original_token = first.json()["activation_token"]
    assert original_token
    assert _refresh(client, original_token).status_code == 200

    # 1-2. The licence reaches expires_at, so the frozen token expires with it.
    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(
        expires_at=expired_at, status=LicenseKeyStatus.EXPIRED
    )
    _expire_tokens(key, at=expired_at)
    assert _refresh(client, original_token).status_code == 401
    assert _manifest(client, original_token).status_code == 401

    # 3. The church renews; staff extends the licence.
    renewed_to = now + timedelta(days=365)
    _renew(key, expires_at=renewed_to)

    # 4. Re-activation must now hand back a USABLE, future-dated token — not 200 + null.
    again = _activate(client, license_key=full_key, fingerprint="mac-booth", idem="remint-renew-02")
    assert again.status_code == 200
    body = again.json()
    new_token = body["activation_token"]
    assert new_token is not None, "a bricked device must be able to re-mint"
    assert new_token != original_token
    assert body["reminted"] is True
    assert body["created"] is False, "re-mint is not a new device"
    assert timezone.datetime.fromisoformat(body["token"]["expires_at"]) > timezone.now()

    # ...and both device-authed surfaces work again.
    assert _refresh(client, new_token).status_code == 200
    assert _manifest(client, new_token).status_code == 200


# --- AC1 (revocation half / G4 reinstatement): restored licence revives a revoked token --
def test_restored_licence_revives_a_revoked_device_token(client):
    """The one-way revocation dead-end: suspending a licence revokes its tokens through the
    hourly cascade, and before this slice restoring the licence could never restore a token."""
    key, full_key = _seed_license_key(tag="restore")
    first = _activate(client, license_key=full_key, fingerprint="mac-susp", idem="remint-rest-01")
    original_token = first.json()["activation_token"]
    assert _refresh(client, original_token).status_code == 200

    # Suspend, then let the real hourly cascade revoke the live token.
    AppLicenseKey.objects.filter(pk=key.pk).update(status=LicenseKeyStatus.SUSPENDED)
    from selahcue_api.apps.devices.tasks import cascade_license_revocations

    assert cascade_license_revocations() == 1
    assert DeviceToken.objects.get().status == DeviceTokenStatus.REVOKED
    assert _refresh(client, original_token).status_code == 401

    # Reinstate the licence.
    _renew(key, expires_at=key.expires_at)

    again = _activate(client, license_key=full_key, fingerprint="mac-susp", idem="remint-rest-02")
    assert again.status_code == 200
    new_token = again.json()["activation_token"]
    assert new_token is not None, "a reinstated licence must be able to restore a device token"
    assert again.json()["reminted"] is True
    assert _refresh(client, new_token).status_code == 200


# --- AC4 + the security boundary --------------------------------------------------------
def test_a_dead_token_alone_cannot_authorise_its_own_remint(client):
    """A dead token must NOT be a credential for reviving itself. Even with the licence
    renewed, presenting only the expired token to a device-token-authed surface stays 401 —
    re-mint is reachable solely through the activation path, which demands the enrollment
    key (or an ADMIN account session)."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="deadtok", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    first = _activate(client, license_key=full_key, fingerprint="mac-dead", idem="remint-dead-01")
    dead_token = first.json()["activation_token"]

    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)

    # The licence is renewed — so the DEVICE is entitled — but the dead token is still not
    # evidence of anything.
    _renew(key, expires_at=now + timedelta(days=365))

    assert _refresh(client, dead_token).status_code == 401
    assert _manifest(client, dead_token).status_code == 401
    assert DeviceToken.objects.count() == 1, "no surface may mint a token off a dead token"
    assert DeviceToken.objects.get().token_fingerprint == first.json()["token"]["fingerprint"]


def test_remint_needs_the_real_enrollment_key(client):
    """Knowing a device fingerprint is not authorisation. A wrong enrollment key is
    NOT_FOUND and mints nothing, even though that fingerprint is a known device."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="wrongkey", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    _activate(client, license_key=full_key, fingerprint="mac-known", idem="remint-wrong-01")
    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)
    _renew(key, expires_at=now + timedelta(days=365))

    bogus = _activate(
        client,
        license_key="SC-TRIAL-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX",
        fingerprint="mac-known",
        idem="remint-wrong-02",
    )
    assert bogus.status_code == 404
    assert bogus.json()["error"]["code"] == "NOT_FOUND"
    assert DeviceToken.objects.count() == 1


def test_remint_is_refused_while_the_licence_is_still_revoked(client):
    """Re-mint is not a revocation bypass: a licence that has NOT returned to an activatable
    status is refused with an explicit non-200, and no token is minted."""
    key, full_key = _seed_license_key(tag="stillrev")
    _activate(client, license_key=full_key, fingerprint="mac-rev", idem="remint-rev-01")
    AppLicenseKey.objects.filter(pk=key.pk).update(status=LicenseKeyStatus.REVOKED)

    denied = _activate(client, license_key=full_key, fingerprint="mac-rev", idem="remint-rev-02")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "POLICY_DENIED"
    assert DeviceToken.objects.count() == 1


def test_remint_is_refused_for_a_revoked_device(client):
    """Device-level revocation is terminal for this slice — re-mint must not resurrect it."""
    key, full_key = _seed_license_key(tag="revdev")
    _activate(client, license_key=full_key, fingerprint="mac-revdev", idem="remint-revdev-1")
    Device.objects.update(status=DeviceStatus.REVOKED)
    DeviceToken.objects.update(status=DeviceTokenStatus.REVOKED)

    denied = _activate(client, license_key=full_key, fingerprint="mac-revdev", idem="remint-revdev-2")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "POLICY_DENIED"
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 0


# --- AC3: no slot burn ------------------------------------------------------------------
def test_remint_does_not_consume_an_instance_slot(client):
    """THE point of the fix: a device_limit=1 church that renews must recover on its ONE
    slot. Before this, the only escape was a new fingerprint — which the limit then refused."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="slot",
        device_limit=1,
        starts_at=now - timedelta(days=40),
        expires_at=now + timedelta(minutes=5),
    )
    _activate(client, license_key=full_key, fingerprint="only-laptop", idem="remint-slot-01")
    assert Device.objects.count() == 1

    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)
    _renew(key, expires_at=now + timedelta(days=365))

    again = _activate(client, license_key=full_key, fingerprint="only-laptop", idem="remint-slot-02")
    assert again.status_code == 200, "re-mint must not be refused by the instance limit"
    assert again.json()["activation_token"] is not None
    assert Device.objects.count() == 1, "re-mint must not create a second device"
    assert (
        Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count() == 1
    ), "re-mint must not consume an instance slot"


def test_remint_is_capped_at_the_device_limit_oldest_devices(client):
    """A downgrade must not be survivable by re-minting every device that ever activated.

    Re-mint returning BEFORE the instance-limit check is correct for a device that is within
    the limit (the test above), but it also skipped the check for a device set that EXCEEDS
    it. A church on 3 devices that downgrades to 1 and renews could re-mint all three and keep
    them running indefinitely on a device_limit=1 plan — a hole the pre-re-mint code did not
    have, because those devices were simply bricked.

    POLICY (see `_remint_is_within_plan_allowance`): the `device_limit` OLDEST-activated
    devices may re-mint; the rest are refused until a slot is explicitly freed.
    """
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="downgrade",
        device_limit=3,
        starts_at=now - timedelta(days=40),
        expires_at=now + timedelta(minutes=5),
    )
    for index in range(3):
        seeded = _activate(
            client, license_key=full_key, fingerprint=f"fp-{index}", idem=f"remint-down-0{index}"
        )
        assert seeded.status_code == 200
    assert Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count() == 3

    # The licence lapses, the church downgrades 3 -> 1, then renews.
    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(
        expires_at=expired_at, status=LicenseKeyStatus.EXPIRED
    )
    _expire_tokens(key, at=expired_at)
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=1)
    _renew(key, expires_at=now + timedelta(days=365))
    assert key.device_limit == 1

    # A brand-new device is refused, as it already was.
    refused_new = _activate(
        client, license_key=full_key, fingerprint="fp-new", idem="remint-down-new"
    )
    assert refused_new.status_code == 403
    assert refused_new.json()["error"]["code"] == "POLICY_DENIED"

    # The OLDEST device recovers — a paying church keeps the one seat it pays for.
    oldest = _activate(client, license_key=full_key, fingerprint="fp-0", idem="remint-down-r0")
    assert oldest.status_code == 200, "the plan's own seat must still recover"
    assert oldest.json()["activation_token"] is not None
    assert oldest.json()["reminted"] is True

    # Everything beyond the limit is refused with the same coded error as an over-limit new
    # device. Before the fix all three revived on a one-device plan.
    for index in (1, 2):
        denied = _activate(
            client, license_key=full_key, fingerprint=f"fp-{index}", idem=f"remint-down-r{index}"
        )
        assert denied.status_code == 403, f"fp-{index} is beyond device_limit=1 and must be refused"
        assert denied.json()["error"]["code"] == "POLICY_DENIED"
        # The refusal is an error envelope, so it carries no token field at all — and nothing
        # was minted behind it. "Usable" (ACTIVE *and* unexpired) is the predicate that
        # matters: these devices still own an ACTIVE-but-long-expired row, which authenticates
        # nothing.
        assert "activation_token" not in denied.json()
        assert not _usable_tokens().filter(device__device_fingerprint=f"fp-{index}").exists()

    # Exactly one live credential exists on a one-device plan.
    assert _usable_tokens().count() == 1
    assert _usable_tokens().get().device.device_fingerprint == "fp-0"


def test_freeing_a_slot_lets_a_previously_refused_device_remint(client):
    """The refusal is a door, not a wall: deactivating a device releases its slot, and the next
    device in activation order can then recover. This is what makes the policy a CHOICE for the
    customer (which seat to keep) rather than a dead end."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="freeslot",
        device_limit=2,
        starts_at=now - timedelta(days=40),
        expires_at=now + timedelta(minutes=5),
    )
    for index in range(2):
        _activate(client, license_key=full_key, fingerprint=f"sl-{index}", idem=f"remint-fs-0{index}")

    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(
        expires_at=expired_at, status=LicenseKeyStatus.EXPIRED
    )
    _expire_tokens(key, at=expired_at)
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=1)
    _renew(key, expires_at=now + timedelta(days=365))

    # sl-1 is second-oldest, so on a one-seat plan it is refused.
    assert _activate(
        client, license_key=full_key, fingerprint="sl-1", idem="remint-fs-r1"
    ).status_code == 403

    # The customer retires the older install, freeing the seat.
    Device.objects.filter(license_key=key, device_fingerprint="sl-0").update(
        status=DeviceStatus.REVOKED
    )

    recovered = _activate(client, license_key=full_key, fingerprint="sl-1", idem="remint-fs-r2")
    assert recovered.status_code == 200, "freeing a slot must let the next device recover"
    assert recovered.json()["activation_token"] is not None
    assert recovered.json()["reminted"] is True


def test_an_over_limit_device_that_still_holds_a_live_token_is_left_alone(client):
    """The cap governs RE-MINT, not the show-once replay. A device whose token is still live is
    already running; refusing its idempotent replay would not revoke anything, and turning a
    replay into an error would break retry-idempotency for a device that never lost its token."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="liveover",
        device_limit=2,
        starts_at=now - timedelta(days=40),
        expires_at=now + timedelta(days=365),
    )
    for index in range(2):
        _activate(client, license_key=full_key, fingerprint=f"lv-{index}", idem=f"remint-lv-0{index}")

    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=1)

    replay = _activate(client, license_key=full_key, fingerprint="lv-1", idem="remint-lv-replay")
    assert replay.status_code == 200
    assert replay.json()["activation_token"] is None, "show-once still applies"
    assert replay.json()["reminted"] is False
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 2


# --- AC6: the superseded token dies -----------------------------------------------------
def test_remint_revokes_the_superseded_token(client):
    """A replayed pre-renewal token must be rejected after a re-mint, not merely expired."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="supersede", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    first = _activate(client, license_key=full_key, fingerprint="mac-sup", idem="remint-sup-01")
    old_token = first.json()["activation_token"]

    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)
    _renew(key, expires_at=now + timedelta(days=365))

    again = _activate(client, license_key=full_key, fingerprint="mac-sup", idem="remint-sup-02")
    new_token = again.json()["activation_token"]

    old_row = DeviceToken.objects.get(token_fingerprint=first.json()["token"]["fingerprint"])
    assert old_row.status == DeviceTokenStatus.REVOKED
    assert _refresh(client, old_token).status_code == 401
    assert _refresh(client, new_token).status_code == 200
    # Exactly one live token per device — no duplicate credentials.
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 1


# --- AC5 (single-process half) + idempotency preservation -------------------------------
def test_repeated_remint_attempts_leave_exactly_one_live_token(client):
    """Serialised repeats: the first call re-mints, the second finds a healthy token and
    replays show-once. No path accumulates live credentials."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="repeat", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    _activate(client, license_key=full_key, fingerprint="mac-rep", idem="remint-rep-01")
    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)
    _renew(key, expires_at=now + timedelta(days=365))

    second = _activate(client, license_key=full_key, fingerprint="mac-rep", idem="remint-rep-02")
    third = _activate(client, license_key=full_key, fingerprint="mac-rep", idem="remint-rep-03")

    assert second.json()["activation_token"] is not None
    assert second.json()["reminted"] is True
    # The device now holds a healthy token, so show-once resumes: no re-issue, no re-show.
    assert third.json()["activation_token"] is None
    assert third.json()["reminted"] is False
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 1


def test_a_healthy_token_is_never_reshown_on_replay(client):
    """Regression guard for show-once: re-mint must trigger ONLY on a dead token. A live
    device replaying activation still gets `activation_token: null` and no new row —
    otherwise a stolen enrollment key would harvest the running install's live credential."""
    key, full_key = _seed_license_key(tag="showonce")
    first = _activate(client, license_key=full_key, fingerprint="mac-live", idem="remint-live-01")
    original = first.json()["activation_token"]

    # Same idempotency key (a retry) and a different one (a re-enrollment) both replay.
    retry = _activate(client, license_key=full_key, fingerprint="mac-live", idem="remint-live-01")
    reenroll = _activate(client, license_key=full_key, fingerprint="mac-live", idem="remint-live-02")

    for response in (retry, reenroll):
        assert response.status_code == 200
        assert response.json()["activation_token"] is None
        assert response.json()["reminted"] is False
        assert original not in json.dumps(response.json())
    assert DeviceToken.objects.count() == 1


# --- AC7 evidence: audit ----------------------------------------------------------------
def test_remint_is_audited_without_the_full_token(client):
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_license_key(
        tag="audit", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    first = _activate(client, license_key=full_key, fingerprint="mac-audit", idem="remint-aud-01")
    old_fingerprint = first.json()["token"]["fingerprint"]

    expired_at = now - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired_at, status=LicenseKeyStatus.EXPIRED)
    _expire_tokens(key, at=expired_at)
    _renew(key, expires_at=now + timedelta(days=365))

    again = _activate(client, license_key=full_key, fingerprint="mac-audit", idem="remint-aud-02")
    new_token = again.json()["activation_token"]

    events = AuditEvent.objects.filter(action="device_token.reminted")
    assert events.count() == 1
    event = events.get()
    assert event.after["superseded_token_fingerprint"] == old_fingerprint
    assert event.after["masked_token"] == again.json()["token"]["masked"]

    dumped = json.dumps(
        [{"action": e.action, "after": e.after, "before": e.before} for e in AuditEvent.objects.all()],
        default=str,
    )
    assert new_token not in dumped
    assert full_key not in dumped


# --- the account-session activation path re-mints too -----------------------------------
def test_account_session_path_also_remints(client):
    """Both entry points converge on the shared core, so the DEC-005 account path must show
    identical re-mint behaviour — authorised by the ADMIN session, not by any token."""
    from selahcue_api.apps.accounts.models import CustomerRole, CustomerUser, CustomerUserStatus
    from selahcue_api.apps.devices.services import (
        ActivateDeviceWithSessionData,
        activate_device_with_session,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind

    now = timezone.now().replace(microsecond=0)
    key, _full_key = _seed_license_key(
        tag="session", starts_at=now - timedelta(days=40), expires_at=now + timedelta(days=30)
    )
    user = CustomerUser.objects.create(
        customer=key.customer,
        email="admin@remint.example",
        email_fingerprint="fp-remint-admin",
        password_hash="unused",
        status=CustomerUserStatus.ACTIVE,
        role=CustomerRole.ADMIN,
        created_by_actor_id="test",
        idempotency_key="remint-session-user",
    )
    admin = ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id=str(user.id),
        org_id=str(key.customer_id),
        role=CustomerRole.ADMIN,
    )

    first = activate_device_with_session(
        admin,
        ActivateDeviceWithSessionData(
            idempotency_key="remint-sess-0001", device_fingerprint="mac-sess", platform="macos"
        ),
    )
    assert first.created is True and first.full_token

    # Expire the token in place (the licence itself stays live, as after a renewal).
    _expire_tokens(key, at=now - timedelta(days=1))

    again = activate_device_with_session(
        admin,
        ActivateDeviceWithSessionData(
            idempotency_key="remint-sess-0002", device_fingerprint="mac-sess", platform="macos"
        ),
    )
    assert again.created is False
    assert again.reminted is True
    assert again.full_token is not None and again.full_token != first.full_token
    assert Device.objects.filter(license_key=key).count() == 1
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 1
