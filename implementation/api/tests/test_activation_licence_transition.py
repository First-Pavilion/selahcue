"""First activation moves the licence through the state machine (86ak5v7av).

Before this ticket `_activate_device_for_key` flipped ISSUED -> ACTIVATED by assigning the
field, so the transition skipped `LEGAL_TRANSITIONS`, and the only audit row it left was
`device.activated` (target_type="device"). A staff member reading the licence audit trail
could not see when, or whether, a licence was first activated (FR-508, NFR-506, FR-527).

Each assertion here is written against an observable that the old direct assignment could
not produce, so reverting the fix turns the suite RED rather than leaving it green:
the licence-level audit row, and the table consulted at activation time.

"A transition row" is recognised by its SHAPE (a SUCCESS row on the licence whose before
status is ISSUED and whose after status is ACTIVATED), never by its action name, so a
renamed action cannot make the "writes none" assertions pass vacuously.

Both entry points share the activation core and are exercised side by side: the enrollment
key (`activate_device`, the device is the actor) and the signed-in account
(`activate_device_with_session`, the customer admin is the actor).
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from licensing_test_support import seat_plan_code
from selahcue_api.apps.accounts.models import (
    CustomerOrg,
    CustomerRole,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import Device, DeviceStatus, DeviceToken
from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    ActivateDeviceWithSessionData,
    activate_device,
    activate_device_with_session,
)
from selahcue_api.apps.license_keys import state_machine
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    LEGAL_TRANSITIONS,
    IllegalLicenseTransition,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

# Pinned as a literal, not imported from the service: the text is part of the audit trail's
# contract, and a test that reads the constant would vouch for any rewording.
FIRST_ACTIVATION_REASON = "First device activation of this licence."

ENROLLMENT = "enrollment"
SESSION = "session"
_PATHS = [ENROLLMENT, SESSION]

# What each entry point answers when it refuses to activate a licence. The enrollment path
# has the key in hand and denies by policy; the account path resolves "the org's activatable
# key" and finds none, which it reports as NOT_FOUND (no oracle on which orgs hold what).
_REFUSAL_CODE = {ENROLLMENT: ErrorCode.POLICY_DENIED, SESSION: ErrorCode.NOT_FOUND}


# Module-local seeding helper, per the shipped slices (no shared conftest seeding).
def _seed_license_key(*, tag, device_limit=3):
    """Returns (AppLicenseKey, full_key) for a freshly issued, still-ISSUED licence."""
    customer = CustomerOrg.objects.create(
        name=f"Transition Church {tag}",
        slug=f"transition-church-{tag}",
        primary_contact_email=f"ops+{tag}@transition.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
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
            plan_code=seat_plan_code(device_limit),
            starts_at=now,
            expires_at=now + timedelta(days=30),
            timezone="Africa/Lagos",
            seat_limit=5,
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


def _session_admin(key, *, tag, role=CustomerRole.ADMIN):
    """A signed-in customer of the licence's org, for the account-session path."""
    user = CustomerUser.objects.create(
        customer=key.customer,
        email=f"{role.value.lower()}+{tag}@transition.example",
        email_fingerprint=f"fp-transition-{role.value.lower()}-{tag}",
        password_hash="unused",
        status=CustomerUserStatus.ACTIVE,
        role=role,
        created_by_actor_id="test",
        idempotency_key=f"transition-session-user-{role.value.lower()}-{tag}",
    )
    actor = ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id=str(user.id),
        org_id=str(key.customer_id),
        role=role,
    )
    return user, actor


def _activator(path, key, full_key, *, tag):
    """`activate(idem, fingerprint)` bound to one entry point, so a test can run unchanged
    against both."""
    if path == ENROLLMENT:
        return lambda idem, fingerprint="fp-transition-1": _activate(
            full_key, idem=idem, fingerprint=fingerprint
        )
    _user, admin = _session_admin(key, tag=tag)
    return lambda idem, fingerprint="fp-transition-1": activate_device_with_session(
        admin,
        ActivateDeviceWithSessionData(
            idempotency_key=idem, device_fingerprint=fingerprint, platform="macos"
        ),
    )


def _licence_rows(key):
    return AuditEvent.objects.filter(target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk))


def _first_activation_rows(key):
    """Every SUCCESS row that records this licence moving ISSUED -> ACTIVATED, by shape."""
    return [
        row
        for row in _licence_rows(key)
        if row.result == AuditResult.SUCCESS
        and row.before.get("status") == LicenseKeyStatus.ISSUED
        and row.after.get("status") == LicenseKeyStatus.ACTIVATED
    ]


def _device_activated_rows():
    return AuditEvent.objects.filter(action="device.activated")


# --- Happy path: both entry points ------------------------------------------------------
def test_first_activation_writes_a_licence_level_transition_row():
    key, full_key = _seed_license_key(tag="firstrow")
    issuance_rows = _licence_rows(key).count()

    result = _activate(full_key, idem="transition-first-0001")

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert result.license_key.status == LicenseKeyStatus.ACTIVATED, (
        "the licence handed back to the caller must not be stale"
    )

    # Exactly one new licence-level row, and it is the transition.
    assert _licence_rows(key).count() == issuance_rows + 1
    (row,) = _first_activation_rows(key)
    assert row.action == "license_key.activated"
    # The activating device is the actor, and its public id is the audit actor id.
    assert row.actor_kind == ActorKind.DEVICE.value
    assert row.actor_id == result.device.device_public_id
    assert row.before["status"] == LicenseKeyStatus.ISSUED
    assert row.after["status"] == LicenseKeyStatus.ACTIVATED
    # The activation's idempotency key is the natural request id, and a reason is mandatory
    # (>= 8 characters) for every transition. The text is pinned: it is read by staff.
    assert row.request_id == "transition-first-0001"
    assert row.reason == FIRST_ACTIVATION_REASON
    assert row.source_surface == "desktop_v1"
    # Ties the licence-level row to the device that caused it, so the licence trail alone
    # says WHICH install activated it.
    assert row.after["device_public_id"] == result.device.device_public_id


def test_the_device_level_row_is_still_written_and_unchanged():
    key, full_key = _seed_license_key(tag="devicerow")

    result = _activate(full_key, idem="transition-device-0001")

    row = _device_activated_rows().get()
    assert row.target_type == "device"
    assert row.target_id == str(result.device.id)
    assert row.result == AuditResult.SUCCESS
    assert row.actor_kind == ActorKind.DEVICE.value
    assert row.actor_id == result.device.device_public_id
    assert row.request_id == "transition-device-0001"
    assert row.source_surface == "desktop_v1"
    assert row.reason == ""
    assert row.before == {}
    # The payload is pinned key by key: "unchanged" must mean unchanged, not "still has the
    # keys this test happens to read".
    assert set(row.after) == {
        "license_key_id",
        "customer_id",
        "device_public_id",
        "platform",
        "app_version",
        "token_prefix",
        "token_suffix",
        "masked_token",
        "token_fingerprint",
        "expires_at",
    }
    assert row.after["license_key_id"] == str(key.id)
    assert row.after["customer_id"] == str(key.customer_id)
    assert row.after["device_public_id"] == result.device.device_public_id


def test_the_account_session_path_audits_the_customer_as_actor():
    key, _full_key = _seed_license_key(tag="session")
    user, admin = _session_admin(key, tag="session")
    issuance_rows = _licence_rows(key).count()

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
    assert _licence_rows(key).count() == issuance_rows + 1
    (row,) = _first_activation_rows(key)
    # Same actor the device.activated row already carries on this path.
    assert row.actor_kind == ActorKind.CUSTOMER.value
    assert row.actor_id == str(user.id)
    assert row.request_id == "transition-session-0001"
    assert row.reason == FIRST_ACTIVATION_REASON
    assert row.source_surface == "account_graphql"
    assert row.after["device_public_id"] == result.device.device_public_id
    # ... and the device-level row is attributed identically.
    device_row = _device_activated_rows().get()
    assert (device_row.actor_kind, device_row.actor_id) == (row.actor_kind, row.actor_id)
    assert device_row.source_surface == row.source_surface


# --- Replays and later devices write nothing ---------------------------------------------
@pytest.mark.parametrize("path", _PATHS)
def test_a_retry_of_the_same_request_writes_no_second_transition(path):
    key, full_key = _seed_license_key(tag=f"retry-{path}")
    activate = _activator(path, key, full_key, tag=f"retry-{path}")

    first = activate("transition-retry-0001", "fp-retry")
    again = activate("transition-retry-0001", "fp-retry")

    # The retry is the idempotent replay of the same device, not a collision on the
    # (licence, idempotency key) uniqueness constraint, and the token is not shown twice.
    assert again.created is False
    assert again.device.pk == first.device.pk
    assert again.full_token is None
    assert Device.objects.filter(license_key=key).count() == 1
    assert len(_first_activation_rows(key)) == 1
    assert _device_activated_rows().count() == 1


@pytest.mark.parametrize("path", _PATHS)
def test_the_same_request_id_from_a_different_install_is_a_replay_not_a_transition(path):
    """The idempotency key alone identifies a request: a retry that arrives with a different
    fingerprint resolves to the FIRST device (it does not create a second one, and it does not
    collide on the uniqueness constraint), and writes no transition."""
    key, full_key = _seed_license_key(tag=f"samekey-{path}")
    activate = _activator(path, key, full_key, tag=f"samekey-{path}")

    first = activate("transition-samekey-0001", "fp-original")
    again = activate("transition-samekey-0001", "fp-different")

    assert again.created is False
    assert again.device.pk == first.device.pk
    assert again.full_token is None
    assert Device.objects.filter(license_key=key).count() == 1
    assert len(_first_activation_rows(key)) == 1


@pytest.mark.parametrize("path", _PATHS)
def test_a_known_install_re_enrolling_under_a_new_request_id_writes_no_second_transition(path):
    key, full_key = _seed_license_key(tag=f"reenrol-{path}")
    activate = _activator(path, key, full_key, tag=f"reenrol-{path}")

    first = activate("transition-reenrol-0001", "fp-reenrol")
    again = activate("transition-reenrol-0002", "fp-reenrol")

    assert again.device.pk == first.device.pk
    assert len(_first_activation_rows(key)) == 1


@pytest.mark.parametrize("path", _PATHS)
def test_a_second_device_on_an_activated_licence_writes_no_transition(path):
    key, full_key = _seed_license_key(tag=f"seconddev-{path}")
    activate = _activator(path, key, full_key, tag=f"seconddev-{path}")
    first = activate("transition-second-0001", "fp-second-a")
    (row_before,) = _first_activation_rows(key)

    second = activate("transition-second-0002", "fp-second-b")

    assert second.device.pk != first.device.pk
    assert second.created is True
    assert Device.objects.filter(license_key=key).count() == 2
    # Still the single row from the FIRST device, untouched.
    (row_after,) = _first_activation_rows(key)
    assert row_after.pk == row_before.pk
    assert row_after.after["device_public_id"] == first.device.device_public_id
    # Both devices still get their own device-level row.
    assert _device_activated_rows().count() == 2


def test_the_same_request_id_on_a_different_licence_is_not_a_replay():
    """Request ids are only unique within a licence (the Device constraint is per licence), so
    two churches that happen to send the same idempotency key must each get their own first
    activation, and each licence its own transition row."""
    key_a, full_key_a = _seed_license_key(tag="sharedreq-a")
    key_b, full_key_b = _seed_license_key(tag="sharedreq-b")

    result_a = _activate(full_key_a, idem="transition-shared-0001", fingerprint="fp-shared")
    result_b = _activate(full_key_b, idem="transition-shared-0001", fingerprint="fp-shared")

    assert result_a.created is True and result_b.created is True
    assert result_a.device.pk != result_b.device.pk
    row_a = _first_activation_rows(key_a)
    row_b = _first_activation_rows(key_b)
    assert len(row_a) == 1 and len(row_b) == 1
    for key, (row,), result in ((key_a, row_a, result_a), (key_b, row_b, result_b)):
        key.refresh_from_db()
        assert key.status == LicenseKeyStatus.ACTIVATED
        assert row.request_id == "transition-shared-0001"
        assert row.target_id == str(key.pk)
        assert row.after["device_public_id"] == result.device.device_public_id
    assert row_a[0].pk != row_b[0].pk and row_a[0].target_id != row_b[0].target_id
    # Two licence rows and two device rows carry the shared request id; none suppressed.
    assert AuditEvent.objects.filter(request_id="transition-shared-0001").count() == 4


# --- Every other licence status behaves exactly as before --------------------------------
# Pinned as literals rather than read from `ACTIVATABLE_KEY_STATUSES`: a test that consults
# the production constant would vouch for whatever the constant says, including a change.
_STILL_ACTIVATES = {LicenseKeyStatus.ACTIVATED, LicenseKeyStatus.EXPIRING}
_NOT_ISSUED = [status for status in LicenseKeyStatus if status != LicenseKeyStatus.ISSUED]


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("status", _NOT_ISSUED, ids=lambda status: status.value)
def test_a_licence_in_any_other_status_is_handled_as_before_and_writes_no_transition(
    path, status
):
    key, full_key = _seed_license_key(tag=f"status-{status.value.lower()}-{path}")
    prior = LicenseKeyStatus.ACTIVATED if status == LicenseKeyStatus.SUSPENDED else ""
    # `.update()` on purpose: the point is a licence that is ALREADY in this status.
    # The schema refuses a SUSPENDED row without the status it came from.
    AppLicenseKey.objects.filter(pk=key.pk).update(status=status, prior_status=prior)
    activate = _activator(path, key, full_key, tag=f"status-{status.value.lower()}-{path}")
    licence_rows_before = _licence_rows(key).count()
    all_rows_before = AuditEvent.objects.count()

    if status in _STILL_ACTIVATES:
        result = activate("transition-status-0001")
        assert result.created is True
        assert Device.objects.filter(license_key=key).count() == 1
        # Exactly the device-level row; nothing at licence level.
        assert AuditEvent.objects.count() == all_rows_before + 1
        assert _device_activated_rows().count() == 1
    else:
        with pytest.raises(SafeAPIError) as raised:
            activate("transition-status-0001")
        assert raised.value.code == _REFUSAL_CODE[path]
        assert Device.objects.count() == 0
        assert DeviceToken.objects.count() == 0
        assert AuditEvent.objects.count() == all_rows_before, "a refusal must audit nothing"

    key.refresh_from_db()
    assert (key.status, key.prior_status) == (status, prior), (
        "activation must not move a licence that is not ISSUED"
    )
    assert _first_activation_rows(key) == []
    assert _licence_rows(key).count() == licence_rows_before


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("window", ["ended", "not-yet-started"])
def test_an_issued_licence_outside_its_validity_window_is_refused_and_stays_issued(
    path, window
):
    key, full_key = _seed_license_key(tag=f"window-{window}-{path}")
    now = timezone.now()
    if window == "ended":
        starts_at, expires_at = now - timedelta(days=60), now - timedelta(days=1)
    else:
        starts_at, expires_at = now + timedelta(days=1), now + timedelta(days=60)
    AppLicenseKey.objects.filter(pk=key.pk).update(starts_at=starts_at, expires_at=expires_at)
    activate = _activator(path, key, full_key, tag=f"window-{window}-{path}")
    all_rows_before = AuditEvent.objects.count()

    with pytest.raises(SafeAPIError) as raised:
        activate("transition-window-0001")

    assert raised.value.code == _REFUSAL_CODE[path]
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert _first_activation_rows(key) == []
    assert AuditEvent.objects.count() == all_rows_before
    assert Device.objects.count() == 0


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("already_holding", [0, 1], ids=["limit-zero", "limit-one-slot-taken"])
def test_the_device_limit_refuses_a_first_activation_before_the_transition(path, already_holding):
    key, full_key = _seed_license_key(tag=f"limit-{already_holding}-{path}")
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=already_holding)
    if already_holding:
        # A slot taken by a device the licence already carries (its status is irrelevant to
        # the point: the limit is reached on what is ACTIVE, and the key is still ISSUED).
        Device.objects.create(
            license_key=key,
            customer=key.customer,
            device_public_id="dev_preexisting",
            device_fingerprint="fp-preexisting",
            platform="macos",
            status=DeviceStatus.ACTIVE,
            activated_by_actor_id="dev_preexisting",
            idempotency_key="preexisting-idem-0001",
        )
    activate = _activator(path, key, full_key, tag=f"limit-{already_holding}-{path}")
    all_rows_before = AuditEvent.objects.count()

    with pytest.raises(SafeAPIError) as raised:
        activate("transition-limit-0001", "fp-over-the-limit")

    assert raised.value.code == ErrorCode.POLICY_DENIED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED, "a refused activation must not activate"
    assert _first_activation_rows(key) == []
    assert AuditEvent.objects.count() == all_rows_before
    assert Device.objects.count() == already_holding
    assert DeviceToken.objects.count() == 0


def test_a_request_id_at_the_column_limit_is_accepted():
    """The activation idempotency key is the audit request id. Its validator allows 128
    characters and so does the audit column; the machine's own bound must not be tighter."""
    key, full_key = _seed_license_key(tag="maxreq")
    idem = "r" * 128

    _activate(full_key, idem=idem)

    (row,) = _first_activation_rows(key)
    assert row.request_id == idem


# --- Authority on the account path --------------------------------------------------------
def test_a_non_admin_session_cannot_trigger_the_transition():
    key, _full_key = _seed_license_key(tag="member")
    _user, member = _session_admin(key, tag="member", role=CustomerRole.MEMBER)
    all_rows_before = AuditEvent.objects.count()

    with pytest.raises(SafeAPIError) as raised:
        activate_device_with_session(
            member,
            ActivateDeviceWithSessionData(
                idempotency_key="transition-member-0001",
                device_fingerprint="fp-member",
                platform="macos",
            ),
        )

    assert raised.value.code == ErrorCode.PERMISSION_DENIED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert AuditEvent.objects.count() == all_rows_before
    assert Device.objects.count() == 0


def test_a_session_admin_cannot_flip_another_tenants_issued_licence():
    mine, _mine_key = _seed_license_key(tag="tenant-a")
    theirs, _theirs_key = _seed_license_key(tag="tenant-b")
    # The admin's own org has nothing activatable, so a resolver that strayed outside the org
    # would find the OTHER tenant's ISSUED licence.
    AppLicenseKey.objects.filter(pk=mine.pk).update(status=LicenseKeyStatus.REVOKED)
    _user, admin = _session_admin(mine, tag="tenant-a")

    with pytest.raises(SafeAPIError) as raised:
        activate_device_with_session(
            admin,
            ActivateDeviceWithSessionData(
                idempotency_key="transition-tenant-0001",
                device_fingerprint="fp-tenant",
                platform="macos",
            ),
        )

    assert raised.value.code == ErrorCode.NOT_FOUND
    theirs.refresh_from_db()
    assert theirs.status == LicenseKeyStatus.ISSUED
    assert _first_activation_rows(theirs) == []
    assert Device.objects.count() == 0


# --- It really goes through the machine --------------------------------------------------
def test_activation_consults_the_transition_table(monkeypatch):
    """The table is the only declaration of what is legal. If activation consulted anything
    else, removing the edge here would not stop it.

    The edge cannot be absent in production (it is the first row of `LEGAL_TRANSITIONS`), so
    this is the only way to observe that the machine, not an inline assignment, decides. The
    activation fails closed: no device, no token, the licence untouched, no half state.

    The machine's DENIED row is written inside `activate_device`'s own transaction here, so it
    rolls back with the activation: the documented caller-shape trade-off in `state_machine`
    ("durability of refusals"), accepted for this caller because the refusal is unreachable
    unless the table itself has been edited. It is asserted, not merely commented, so that the
    day the decision changes this test says so.
    """
    key, full_key = _seed_license_key(tag="tablecheck")
    rows_before = _licence_rows(key).count()
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
    assert _first_activation_rows(key) == []
    assert _device_activated_rows().count() == 0
    # No SUCCESS row of any kind was left behind by the failed attempt ...
    assert _licence_rows(key).filter(result=AuditResult.SUCCESS).count() == rows_before, (
        "a refused activation left a licence audit row behind"
    )
    # ... and the machine's DENIED row did not survive the wrapping transaction either. This
    # is the accepted loss. If a DENIED row ever appears here, the durability decision recorded
    # in `state_machine` has changed: revisit that decision, do not just flip this assertion.
    assert AuditEvent.objects.filter(result=AuditResult.DENIED).count() == 0, (
        "the machine's DENIED row survived the activation rollback; the durability decision "
        "in state_machine ('durability of refusals') has changed"
    )

    # No half state: the same request, once the table is whole again, is simply a first
    # activation -- it does not collide with, or replay, anything the failed attempt wrote.
    monkeypatch.undo()
    retry = _activate(full_key, idem="transition-table-0001")
    assert retry.created is True
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert len(_first_activation_rows(key)) == 1


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
    assert _first_activation_rows(key) == []


def test_a_failing_device_audit_write_rolls_the_licence_transition_back_too(monkeypatch):
    """The reverse order: the licence transition has ALREADY been written when the
    device-level audit row fails. The transition and its row must not survive it."""
    key, full_key = _seed_license_key(tag="atomicdevice")
    rows_before = _licence_rows(key).count()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated device audit storage failure")

    monkeypatch.setattr("selahcue_api.apps.devices.services.record_audit_event", fail_audit)

    with pytest.raises(RuntimeError):
        _activate(full_key, idem="transition-atomicdev-0001")

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert _first_activation_rows(key) == []
    assert _licence_rows(key).count() == rows_before
    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_a_failing_device_audit_write_rolls_back_in_the_production_shape(monkeypatch):
    """Production runs in autocommit (no ATOMIC_REQUESTS), so the activation's own atomic
    block is the OUTERMOST transaction and the rollback is a real one, not a savepoint inside
    the test's wrapping transaction."""
    key, full_key = _seed_license_key(tag="autocommit")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated device audit storage failure")

    monkeypatch.setattr("selahcue_api.apps.devices.services.record_audit_event", fail_audit)

    with pytest.raises(RuntimeError):
        _activate(full_key, idem="transition-autocommit-0001")

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert _first_activation_rows(key) == []
    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0


# --- What the licence row must not hold --------------------------------------------------
@pytest.mark.parametrize("path", _PATHS)
def test_the_licence_row_holds_no_secret_material(path):
    """The licence-level row is readable by anyone who can read the licence trail. It may name
    the device by its public id, and nothing else about the install or its credentials: not
    the show-once device token, not the presented enrollment key, not either one's hash or
    fingerprint, and not the install fingerprint (which `device.activated` does not record
    either)."""
    key, full_key = _seed_license_key(tag=f"secrets-{path}")
    fingerprint = "fp-secret-install-identity"
    activate = _activator(path, key, full_key, tag=f"secrets-{path}")

    result = activate("transition-secrets-0001", fingerprint)

    (row,) = _first_activation_rows(key)
    # The exact shape, so a new field has to be argued for rather than slipping in.
    assert set(row.before) == {"status", "prior_status"}
    assert set(row.after) == {"status", "prior_status", "device_public_id"}

    token = DeviceToken.objects.get(device=result.device)
    key.refresh_from_db()
    haystack = json.dumps(
        [row.before, row.after, row.reason, row.request_id, row.actor_id, row.source_surface],
        default=str,
    )
    for secret in (
        full_key,
        result.full_token,
        fingerprint,
        token.token_hash,
        token.token_fingerprint,
        token.masked_token,
        key.secret_hash,
        key.secret_fingerprint,
    ):
        assert secret and secret not in haystack, "the licence row leaks credential material"
