"""First activation moves the licence through the state machine (86ak5v7av).

Before this ticket `_activate_device_for_key` flipped ISSUED -> ACTIVATED by assigning the
field, so the transition skipped `LEGAL_TRANSITIONS`, and the only audit row it left was
`device.activated` (target_type="device"). A staff member reading the licence audit trail
could not see when, or whether, a licence was first activated (FR-508, NFR-506, FR-527).

Each assertion here is written against an observable that the old direct assignment could
not produce, so reverting the fix turns the suite RED rather than leaving it green:
the licence-level audit row, and the table consulted at activation time.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    ActivateDeviceWithSessionData,
    activate_device,
    activate_device_with_session,
)
from selahcue_api.apps.license_keys import state_machine
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    LEGAL_TRANSITIONS,
    IllegalLicenseTransition,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode

pytestmark = pytest.mark.django_db

ACTIVATED_ACTION = "license_key.activated"


# Module-local seeding helper, per the shipped slices (no shared conftest seeding).
def _seed_license_key(*, tag, device_limit=3):
    """Returns (AppLicenseKey, full_key) for a freshly issued, still-ISSUED licence."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )

    customer = CustomerOrg.objects.create(
        name=f"Transition Church {tag}",
        slug=f"transition-church-{tag}",
        primary_contact_email=f"ops+{tag}@transition.example",
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
            plan_code="PRO",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Seed licence for the activation-transition tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(full_key, *, idem, fingerprint="fp-transition-1"):
    return activate_device(
        ActivateDeviceData(
            idempotency_key=idem,
            presented_key=full_key,
            device_fingerprint=fingerprint,
            platform="macos",
        )
    )


def _licence_rows(key):
    return AuditEvent.objects.filter(target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk))


def _activated_rows(key):
    return _licence_rows(key).filter(action=ACTIVATED_ACTION)


def test_first_activation_writes_a_licence_level_transition_row():
    key, full_key = _seed_license_key(tag="firstrow")
    issuance_rows = _licence_rows(key).count()

    result = _activate(full_key, idem="transition-first-0001")

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert result.license_key.status == LicenseKeyStatus.ACTIVATED, (
        "the licence handed back to the caller must not be stale"
    )

    assert _licence_rows(key).count() == issuance_rows + 1
    row = _activated_rows(key).get()
    assert row.result == AuditResult.SUCCESS
    # The activating device is the actor, and its public id is the audit actor id.
    assert row.actor_kind == ActorKind.DEVICE.value
    assert row.actor_id == result.device.device_public_id
    assert row.before["status"] == LicenseKeyStatus.ISSUED
    assert row.after["status"] == LicenseKeyStatus.ACTIVATED
    # The activation's idempotency key is the natural request id, and a reason is mandatory
    # (>= 8 characters) for every transition.
    assert row.request_id == "transition-first-0001"
    assert len(row.reason) >= 8
    assert row.source_surface == "desktop_v1"
    # Ties the licence-level row to the device that caused it, so the licence trail alone
    # says WHICH install activated it.
    assert row.after["device_public_id"] == result.device.device_public_id


def test_the_device_level_row_is_still_written_and_unchanged():
    key, full_key = _seed_license_key(tag="devicerow")

    result = _activate(full_key, idem="transition-device-0001")

    row = AuditEvent.objects.get(action="device.activated")
    assert row.target_type == "device"
    assert row.target_id == str(result.device.id)
    assert row.actor_kind == ActorKind.DEVICE.value
    assert row.request_id == "transition-device-0001"
    assert row.after["license_key_id"] == str(key.id)


def test_a_retry_or_second_device_does_not_write_a_second_transition():
    key, full_key = _seed_license_key(tag="replay")

    _activate(full_key, idem="transition-replay-0001", fingerprint="fp-replay-a")
    # Same idempotency key: the retry replay.
    _activate(full_key, idem="transition-replay-0001", fingerprint="fp-replay-a")
    # A second install under the same, now-ACTIVATED, licence.
    _activate(full_key, idem="transition-replay-0002", fingerprint="fp-replay-b")

    assert Device.objects.filter(license_key=key).count() == 2
    assert _activated_rows(key).count() == 1


@pytest.mark.parametrize("status", [LicenseKeyStatus.ACTIVATED, LicenseKeyStatus.EXPIRING])
def test_activating_against_a_non_issued_licence_writes_no_transition(status):
    key, full_key = _seed_license_key(tag=f"nonissued-{status.value.lower()}")
    AppLicenseKey.objects.filter(pk=key.pk).update(status=status)
    before_rows = _licence_rows(key).count()

    _activate(full_key, idem=f"transition-{status.value.lower()}-1")

    key.refresh_from_db()
    assert key.status == status
    assert _licence_rows(key).count() == before_rows
    # ... and it still activates normally.
    assert Device.objects.filter(license_key=key).count() == 1
    assert AuditEvent.objects.filter(action="device.activated").count() == 1


def test_the_account_session_path_audits_the_customer_as_actor():
    from selahcue_api.apps.accounts.models import CustomerRole, CustomerUser, CustomerUserStatus

    key, _full_key = _seed_license_key(tag="session")
    user = CustomerUser.objects.create(
        customer=key.customer,
        email="admin@transition.example",
        email_fingerprint="fp-transition-admin",
        password_hash="unused",
        status=CustomerUserStatus.ACTIVE,
        role=CustomerRole.ADMIN,
        created_by_actor_id="test",
        idempotency_key="transition-session-user",
    )
    admin = ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id=str(user.id),
        org_id=str(key.customer_id),
        role=CustomerRole.ADMIN,
    )

    result = activate_device_with_session(
        admin,
        ActivateDeviceWithSessionData(
            idempotency_key="transition-session-0001",
            device_fingerprint="fp-transition-session",
            platform="macos",
        ),
    )

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    row = _activated_rows(key).get()
    # Same actor the device.activated row already carries on this path.
    assert row.actor_kind == ActorKind.CUSTOMER.value
    assert row.actor_id == str(user.id)
    assert row.request_id == "transition-session-0001"
    assert row.after["device_public_id"] == result.device.device_public_id


# --- It really goes through the machine --------------------------------------------------
def test_activation_consults_the_transition_table(monkeypatch):
    """The table is the only declaration of what is legal. If activation consulted anything
    else, removing the edge here would not stop it.

    The edge cannot be absent in production (it is the first row of `LEGAL_TRANSITIONS`), so
    this is the only way to observe that the machine, not an inline assignment, decides. The
    activation fails closed: no device, no token, the licence untouched. (The DENIED audit row
    the machine writes is inside `activate_device`'s own transaction here and rolls back with
    it; that is the documented caller-shape trade-off in `state_machine`, and it only arises
    when the table itself has been edited.)
    """
    key, full_key = _seed_license_key(tag="tablecheck")
    without_first_activation = LEGAL_TRANSITIONS[LicenseKeyStatus.ISSUED] - {
        LicenseKeyStatus.ACTIVATED
    }
    monkeypatch.setitem(
        LEGAL_TRANSITIONS, LicenseKeyStatus.ISSUED, frozenset(without_first_activation)
    )

    with pytest.raises(IllegalLicenseTransition) as raised:
        _activate(full_key, idem="transition-table-0001")

    assert raised.value.code == ErrorCode.CONFLICT
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0
    assert _activated_rows(key).count() == 0


def test_the_licence_transition_rolls_back_with_the_activation(monkeypatch):
    """The SUCCESS row must commit or roll back WITH the status change it describes, and with
    the device: a licence that reads ACTIVATED with no device behind it is a lie in the trail."""
    key, full_key = _seed_license_key(tag="atomic")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit storage failure")

    monkeypatch.setattr(state_machine, "record_audit_event", fail_audit)

    with pytest.raises(RuntimeError):
        _activate(full_key, idem="transition-atomic-0001")

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0
    assert _activated_rows(key).count() == 0
