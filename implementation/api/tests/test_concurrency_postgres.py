"""The DEC-004 instance limit, and device-token re-mint, under real concurrency.

`activate_device` guards both with select_for_update on the licence row, which SQLite
silently no-ops (has_select_for_update = False). These tests therefore SKIP on SQLite —
they would pass there for the wrong reason and hide the very races they exist to catch.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection, connections
from django.utils import timezone

from selahcue_api.apps.devices.models import (
    Device,
    DeviceStatus,
    DeviceToken,
    DeviceTokenStatus,
)
from selahcue_api.apps.devices.services import ActivateDeviceData, activate_device

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="select_for_update is a no-op on SQLite; this race is only observable on Postgres",
    ),
]


# Module-local seeding helper, copied verbatim from tests/test_entitlement_manifest_slice.py
# (which in turn mirrors tests/test_license_refresh_slice.py). The shipped slices each build
# their own rather than sharing a conftest.py — follow that.
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Manifest Church {tag}",
        slug=f"manifest-church-{tag}",
        primary_contact_email=f"ops+{tag}@manifest.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
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
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for entitlement-manifest tests.",
        ),
    )
    return result.license_key, result.full_key


def test_concurrent_activations_cannot_exceed_the_device_limit():
    key, full_key = _seed_license_key(tag="conc", device_limit=1)

    errors = []
    # Without this the two threads may run start-to-finish one after the other and still
    # satisfy both assertions below — the test would pass having never produced a race at all.
    # The barrier makes both threads enter `activate_device` together, so the select_for_update
    # window is genuinely contended. Timeout so a thread that dies before arriving fails the
    # test instead of hanging the suite.
    start = threading.Barrier(2, timeout=30)

    barrier_failures = []

    def activate(n):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            # Kept OUT of `errors`: a barrier that never formed means the race never ran, and
            # counting it as a rejected activation would be the false pass this guards against.
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            activate_device(
                ActivateDeviceData(
                    # Must stay >= 12 chars: validate_idempotency_key rejects anything
                    # shorter with VALIDATION_FAILED, which would make BOTH activations
                    # fail and the race never run.
                    idempotency_key=f"conc-activation-{n}",
                    presented_key=full_key,
                    device_fingerprint=f"fp-conc-{n}",
                    platform="macos",
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=activate, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert barrier_failures == [], f"the two activations never overlapped: {barrier_failures}"
    active = Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count()
    assert active == 1, f"instance limit exceeded: {active} active devices, errors={errors}"
    assert len(errors) == 1, "exactly one activation should have been rejected"


def test_concurrent_remints_leave_exactly_one_live_token():
    """AC5 of 86ak108w0. Two desktops (or one desktop retrying) re-activating the same
    bricked device at the same instant must not each mint a live token — two live
    credentials for one device would defeat the supersede-on-re-mint guarantee that makes a
    replayed pre-renewal token rejectable.

    The serialisation comes from the SAME `select_for_update` on the licence row that guards
    the instance limit, so the loser blocks until the winner has committed its re-mint and
    then sees a healthy token and replays show-once.
    """
    key, full_key = _seed_license_key(tag="remintconc", device_limit=1)

    # One activated device, then age its token so the device is bricked exactly as a lapsed
    # licence would leave it. `issued_at` moves back too: `device_token_expires_after_issue`
    # forbids a token that expires before it was issued.
    activate_device(
        ActivateDeviceData(
            idempotency_key="remint-conc-seed",
            presented_key=full_key,
            device_fingerprint="fp-remint-conc",
            platform="macos",
        )
    )
    stale = timezone.now() - timedelta(days=1)
    DeviceToken.objects.filter(device__license_key=key).update(
        issued_at=stale - timedelta(days=30), expires_at=stale
    )

    results = []
    errors = []
    start = threading.Barrier(2, timeout=30)
    barrier_failures = []

    def remint(n):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            results.append(
                activate_device(
                    ActivateDeviceData(
                        # Distinct idempotency keys: this is the same INSTALL re-enrolling,
                        # which is the known-fingerprint branch, not an idempotent retry.
                        idempotency_key=f"remint-conc-{n}",
                        presented_key=full_key,
                        device_fingerprint="fp-remint-conc",
                        platform="macos",
                    )
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=remint, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert barrier_failures == [], f"the two re-mints never overlapped: {barrier_failures}"
    assert errors == [], f"a re-mint must not race into an error: {errors}"

    live = DeviceToken.objects.filter(
        device__license_key=key, status=DeviceTokenStatus.ACTIVE
    )
    assert live.count() == 1, f"concurrent re-mint produced {live.count()} live tokens"
    assert Device.objects.filter(license_key=key).count() == 1, "no slot was burned"
    # Exactly one caller minted; the other found the fresh token and replayed show-once.
    assert sorted(r.reminted for r in results) == [False, True]
    assert sorted(r.full_token is None for r in results) == [False, True]
    minted = [r.full_token for r in results if r.full_token is not None]
    assert live.get().token_prefix == minted[0][:12]


# --- 86ak5mn00: the lifecycle state machine under a real race ---------------------------
def test_concurrent_transitions_write_exactly_one_audit_row():
    """NFR-506 says 100% of transitions are audited, exactly once. Two staff members (or one
    retrying client) revoking the same licence at the same instant must produce ONE status
    change and ONE audit row — not two rows describing the same ACTIVATED -> REVOKED move.

    The serialisation is the `select_for_update` in `apply_license_status_transition`, which
    makes the loser re-read the row AFTER the winner commits and see REVOKED, turning its
    call into the idempotent replay that writes nothing. Without the lock both callers read
    ACTIVATED, both pass the legality check, and both audit.
    """
    from selahcue_api.apps.audit.models import AuditEvent, AuditResult
    from selahcue_api.apps.license_keys.models import LicenseKeyStatus
    from selahcue_api.apps.license_keys.state_machine import (
        AUDIT_TARGET_TYPE,
        apply_license_status_transition,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind

    key, full_key = _seed_license_key(tag="lifecycleconc", device_limit=1)
    # First activation flips ISSUED -> ACTIVATED, so the race starts from a real status.
    activate_device(
        ActivateDeviceData(
            idempotency_key="lifecycle-conc-seed",
            presented_key=full_key,
            device_fingerprint="fp-lifecycle-conc",
            platform="macos",
        )
    )
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED

    baseline = AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk)
    ).count()

    results = []
    errors = []
    start = threading.Barrier(2, timeout=30)
    barrier_failures = []

    def revoke(n):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            results.append(
                apply_license_status_transition(
                    key,
                    to_status=LicenseKeyStatus.REVOKED,
                    actor=ActorContext(kind=ActorKind.STAFF, actor_id=f"staff_race_{n}"),
                    reason="Chargeback received; revoking the licence.",
                    # Distinct request ids: two genuinely separate staff actions, not one
                    # request retried, so nothing upstream can dedupe them for us.
                    request_id=f"race-revoke-{n}",
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=revoke, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert barrier_failures == [], f"the two revocations never overlapped: {barrier_failures}"
    assert errors == [], f"a legal transition must not race into an error: {errors}"

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED
    # Exactly one caller transitioned; the other found REVOKED already in effect.
    assert sorted(r.changed for r in results) == [False, True]

    written = (
        AuditEvent.objects.filter(target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk)).count()
        - baseline
    )
    assert written == 1, (
        f"one status change produced {written} audit rows — concurrent callers must not each "
        "audit the same transition (NFR-506)"
    )
    assert (
        AuditEvent.objects.filter(
            target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), result=AuditResult.DENIED
        ).count()
        == 0
    ), "the losing caller replays idempotently; it is not a refusal"
