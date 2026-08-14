"""The DEC-004 instance limit under real concurrency.

`activate_device` guards the limit with select_for_update, which SQLite silently no-ops
(has_select_for_update = False). This test therefore SKIPS on SQLite — it would pass
there for the wrong reason and hide the very race it exists to catch.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection, connections
from django.utils import timezone

from selahcue_api.apps.devices.models import Device, DeviceStatus
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
