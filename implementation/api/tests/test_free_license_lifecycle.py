"""Free lifecycle through the released activation and refresh contracts."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from test_bound_activation import KEY, SESSION, admin_session, another_license, body, post
from test_native_account_surface import seed_license, seed_org
from selahcue_api.apps.accounts.models import CustomerStatus
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle, LicenseKeyStatus

pytestmark = pytest.mark.django_db
REFRESH = "/v1/license:refresh"
NOW = datetime(2028, 2, 29, 12, tzinfo=UTC)
RENEWED_TO = datetime(2029, 2, 28, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    cache.clear()


def self_service_org():
    org = seed_org(tag="free")
    org.status = CustomerStatus.TRIAL
    org.created_by_actor_id = "self_signup:" + "a" * 64
    org.save(update_fields=["status", "created_by_actor_id"])
    return org


def activate_free(client):
    org = self_service_org()
    session = admin_session(client, org)
    response = post(client, SESSION, body(), session)
    assert response.status_code == 200, response.json()
    return org, session, response.json(), AppLicenseKey.objects.get(customer=org)


def test_first_verified_admin_activation_issues_one_free_license(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org, session, initial, licence = activate_free(client)
    assert licence.starts_at == NOW
    assert licence.expires_at == RENEWED_TO
    assignment = LicensePlanAssignment.objects.get(license_key=licence)
    assert assignment.plan.is_fallback
    marker = FreeLicenseLifecycle.objects.get(customer=org)
    assert marker.license_key_id == licence.pk and marker.renewal_enabled
    assert AuditEvent.objects.filter(action="customer_org.free_activated").count() == 1
    org.refresh_from_db()
    assert org.status == CustomerStatus.ACTIVE
    replay = post(client, SESSION, body(), session).json()
    assert replay["device"] == initial["device"]
    assert replay["operation_state"] == "replay"
    assert replay["activation_token"] is None
    assert AppLicenseKey.objects.filter(customer=org).count() == 1
    assert Device.objects.count() == DeviceToken.objects.count() == 1


@pytest.mark.parametrize("remaining, renews", [
    (timedelta(days=30), True),
    (timedelta(days=30, microseconds=1), False),
])
def test_renewal_at_30_days_extends_only_presented_live_token(client, monkeypatch, remaining, renews):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, _session, initial, licence = activate_free(client)
    first = DeviceToken.objects.get()
    old_expiry = NOW + remaining
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=old_expiry)
    DeviceToken.objects.filter(pk=first.pk).update(expires_at=old_expiry)
    second_device = Device.objects.create(
        customer=licence.customer, license_key=licence, device_fingerprint="other-existing-device",
        device_public_id="dev_" + "6" * 32, platform="windows", activated_by_actor_id="fixture",
        idempotency_key="other-existing-device",
    )
    other = DeviceToken.objects.create(
        device=second_device, token_hash="synthetic", token_fingerprint="b" * 64,
        issued_at=NOW, expires_at=old_expiry,
    )

    response = post(client, REFRESH, {}, initial["activation_token"])
    assert response.status_code == 200, response.json()
    expected = RENEWED_TO if renews else old_expiry
    assert response.json()["license"]["expires_at"] == expected.isoformat()
    assert response.json()["token"]["expires_at"] == expected.isoformat()
    first.refresh_from_db()
    other.refresh_from_db()
    assert first.expires_at == expected
    assert other.expires_at == old_expiry
    assert DeviceToken.objects.count() == 2
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == int(renews)


def test_expired_token_requires_admin_same_fingerprint_recovery(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, session, initial, licence = activate_free(client)
    target = initial["device"]["device_public_id"]
    dead = DeviceToken.objects.get()
    expiry = NOW
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        starts_at=NOW - timedelta(days=365), expires_at=expiry, status=LicenseKeyStatus.EXPIRED,
    )
    DeviceToken.objects.filter(pk=dead.pk).update(issued_at=NOW - timedelta(days=365), expires_at=expiry)

    assert post(client, REFRESH, {}, initial["activation_token"]).status_code == 401
    replay = post(client, SESSION, body(), session)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "ACTIVATION_OPERATION_COMPLETED"
    data = body("2" * 32, expected=target)
    for field, value in [("device_fingerprint", "wrong"), ("platform", "windows")]:
        assert post(client, SESSION, {**data, field: value}, session).status_code == 409
    licence.refresh_from_db()
    assert licence.expires_at == expiry

    recovered = post(client, SESSION, data, session)
    assert recovered.status_code == 200, recovered.json()
    assert recovered.json()["reminted"]
    assert recovered.json()["device"]["device_public_id"] == target
    assert Device.objects.count() == 1
    assert DeviceActivationOperation.objects.get(operation_key="2" * 32).license_key_id == licence.pk
    assert post(client, REFRESH, {}, initial["activation_token"]).status_code == 401
    dead.refresh_from_db()
    licence.refresh_from_db()
    assert dead.expires_at == expiry
    assert licence.expires_at == RENEWED_TO
    assert licence.status == LicenseKeyStatus.ACTIVATED


@pytest.mark.parametrize("competing_window", [False, True])
def test_completed_live_replay_leaves_managed_licence_and_receipt_unchanged(
    client, monkeypatch, competing_window,
):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, session, initial, licence = activate_free(client)
    expires_at = NOW + timedelta(days=30)
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        expires_at=expires_at, status=LicenseKeyStatus.EXPIRING,
    )
    DeviceToken.objects.update(expires_at=expires_at)
    if competing_window:
        competitor, _ = another_license(licence, "future-replay")
        AppLicenseKey.objects.filter(pk=competitor.pk).update(
            starts_at=expires_at, expires_at=expires_at + timedelta(days=45),
        )

    receipt_before = DeviceActivationOperation.objects.values().get()
    token_before = DeviceToken.objects.values().get()
    audit_count = AuditEvent.objects.filter(action="license_key.free_renewed").count()

    replay = post(client, SESSION, body(), session)

    assert replay.status_code == 200, replay.json()
    assert replay.json()["operation_state"] == "replay"
    assert replay.json()["device"]["device_public_id"] == initial["device"]["device_public_id"]
    assert replay.json()["activation_token"] is None
    assert DeviceActivationOperation.objects.values().get() == receipt_before
    assert receipt_before["result_token_id"] == token_before["id"]
    assert DeviceToken.objects.values().get() == token_before
    assert Device.objects.count() == 1
    licence.refresh_from_db()
    assert licence.expires_at == expires_at
    assert licence.status == LicenseKeyStatus.EXPIRING
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == audit_count


def test_different_license_activation_is_not_same_device_recovery(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, session, initial, licence = activate_free(client)
    other, presented = another_license(licence, "competing")
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        starts_at=NOW - timedelta(days=365), expires_at=NOW, status=LicenseKeyStatus.EXPIRED,
    )
    DeviceToken.objects.update(issued_at=NOW - timedelta(days=365), expires_at=NOW)
    data = body("2" * 32, expected=initial["device"]["device_public_id"])

    assert post(client, KEY, {**data, "license_key": presented}).status_code == 409
    assert post(client, SESSION, data, session).status_code == 403
    assert not Device.objects.filter(license_key=other).exists()
    assert DeviceToken.objects.count() == DeviceActivationOperation.objects.count() == 1
    licence.refresh_from_db()
    assert licence.expires_at == NOW
    assert AuditEvent.objects.get(action="license_key.free_renewed").result == AuditResult.DENIED


def test_existing_eligible_pilot_core_license_is_preserved(client):
    org = self_service_org()
    licence = seed_license(org)
    AppLicenseKey.objects.filter(pk=licence.pk).update(key_type="PILOT")
    session = admin_session(client, org)
    response = post(client, SESSION, body(), session)
    assert response.status_code == 200
    assert Device.objects.get().license_key_id == licence.pk
    assert AppLicenseKey.objects.filter(customer=org).count() == 1
    licence.refresh_from_db()
    assert licence.key_type == "PILOT"
    assert not FreeLicenseLifecycle.objects.exists()


@pytest.mark.parametrize("status, future", [
    (LicenseKeyStatus.EXPIRED, False),
    (LicenseKeyStatus.ISSUED, True),
])
def test_unmarked_expired_or_future_license_is_not_converted(client, monkeypatch, status, future):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org = self_service_org()
    licence = seed_license(org)
    start = NOW + timedelta(days=1) if future else NOW - timedelta(days=2)
    end = NOW + timedelta(days=2) if future else NOW - timedelta(days=1)
    AppLicenseKey.objects.filter(pk=licence.pk).update(status=status, starts_at=start, expires_at=end)
    session = admin_session(client, org)
    assert post(client, SESSION, body(), session).status_code in {403, 404}
    licence.refresh_from_db()
    assert (licence.status, licence.starts_at, licence.expires_at) == (status, start, end)
    assert AppLicenseKey.objects.filter(customer=org).count() == 1
    assert not Device.objects.exists()


def test_revocation_is_not_replaced_by_free_issuance(client):
    org = self_service_org()
    licence = seed_license(org)
    AppLicenseKey.objects.filter(pk=licence.pk).update(status=LicenseKeyStatus.REVOKED)
    session = admin_session(client, org)
    assert post(client, SESSION, body(), session).status_code in {403, 404}
    assert AppLicenseKey.objects.filter(customer=org).count() == 1
    assert not Device.objects.exists()


@pytest.mark.parametrize("blocked", ["org", "marker", "licence", "device", "token"])
def test_blocked_free_lifecycle_does_not_extend_dates(client, monkeypatch, blocked):
    from selahcue_api.apps.devices.models import DeviceStatus, DeviceTokenStatus

    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org, session, initial, licence = activate_free(client)
    expiry = NOW + timedelta(days=5)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expiry)
    DeviceToken.objects.update(expires_at=expiry)

    if blocked == "org":
        type(org).objects.filter(pk=org.pk).update(status=CustomerStatus.SUSPENDED)
    elif blocked == "marker":
        FreeLicenseLifecycle.objects.filter(customer=org).update(renewal_enabled=False)
    elif blocked == "licence":
        AppLicenseKey.objects.filter(pk=licence.pk).update(
            status=LicenseKeyStatus.SUSPENDED, prior_status=LicenseKeyStatus.ACTIVATED,
        )
    elif blocked == "device":
        Device.objects.update(status=DeviceStatus.REVOKED)
    else:
        DeviceToken.objects.update(status=DeviceTokenStatus.REVOKED)

    reply = post(client, REFRESH, {}, initial["activation_token"])
    assert reply.status_code == (401 if blocked in {"device", "token"} else 200)
    licence.refresh_from_db()
    assert licence.expires_at == DeviceToken.objects.get().expires_at == expiry
    assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()
    if blocked in {"org", "device", "licence"}:
        assert post(client, SESSION, body(), session).status_code == 403


def test_presented_token_can_catch_up_after_admin_renewal(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, session, initial, licence = activate_free(client)
    expiry = NOW + timedelta(days=5)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expiry)
    DeviceToken.objects.update(expires_at=expiry)
    target = initial["device"]["device_public_id"]
    recovery = post(client, SESSION, body("2" * 32, expected=target), session)
    assert recovery.status_code == 200, recovery.json()
    assert recovery.json()["device"]["device_public_id"] == target
    assert recovery.json()["activation_token"] is None
    assert DeviceToken.objects.get().expires_at == expiry

    response = post(client, REFRESH, {}, initial["activation_token"])
    assert response.status_code == 200
    assert response.json()["token"]["expires_at"] == RENEWED_TO.isoformat()
    assert DeviceToken.objects.get().expires_at == RENEWED_TO
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == 1
    assert AuditEvent.objects.filter(action="device_token.free_validity_extended").count() == 1


def test_enrollment_key_alone_cannot_renew_managed_free_licence(client, monkeypatch):
    from django.contrib.auth.hashers import make_password
    from selahcue_api.apps.license_keys.services import _fingerprint

    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, _session, initial, licence = activate_free(client)
    presented = "test-only-synthetic-enrollment-key"
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        starts_at=NOW - timedelta(days=365), expires_at=NOW, status=LicenseKeyStatus.EXPIRED,
        secret_fingerprint=_fingerprint(presented), secret_hash=make_password(presented),
    )
    DeviceToken.objects.update(issued_at=NOW - timedelta(days=365), expires_at=NOW)
    reply = post(client, KEY, body(
        "2" * 32, expected=initial["device"]["device_public_id"], license_key=presented,
    ))
    assert reply.status_code == 403
    licence.refresh_from_db()
    assert licence.expires_at == NOW
    assert DeviceToken.objects.count() == DeviceActivationOperation.objects.count() == 1


def test_stale_admin_session_does_not_issue_free_without_verification(client):
    from selahcue_api.apps.accounts.models import CustomerUser

    org = self_service_org()
    session = admin_session(client, org)
    CustomerUser.objects.filter(customer=org).update(email_verified_at=None)
    assert post(client, SESSION, body(), session).status_code == 403
    assert not AppLicenseKey.objects.exists()


def test_reassigned_licence_keeps_current_plan_and_does_not_renew_as_free(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, session, initial, licence = activate_free(client)
    expiry = NOW + timedelta(days=5)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expiry)
    DeviceToken.objects.update(expires_at=expiry)
    LicensePlanAssignment.objects.filter(license_key=licence).update(plan=Plan.objects.get(code="PRO"))

    assert post(client, SESSION, body(), session).status_code == 200
    response = post(client, REFRESH, {}, initial["activation_token"])
    assert response.status_code == 200
    assert response.json()["license"]["expires_at"] == response.json()["token"]["expires_at"] == expiry.isoformat()
    licence.refresh_from_db()
    assert licence.expires_at == expiry
    assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()


def test_first_activation_assigns_the_renamed_fallback_plan(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    fallback = Plan.objects.get(is_fallback=True)
    Plan.objects.filter(pk=fallback.pk).update(code="ENTRY", display_name="Entry")

    org, _session, _initial, licence = activate_free(client)

    assert LicensePlanAssignment.objects.get(license_key=licence).plan_id == fallback.pk
    assert FreeLicenseLifecycle.objects.get(customer=org).license_key_id == licence.pk
    assert licence.expires_at == RENEWED_TO


def test_renaming_assigned_fallback_keeps_managed_licence_renewable(client, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org, _session, initial, licence = activate_free(client)
    fallback = Plan.objects.get(is_fallback=True)
    Plan.objects.filter(pk=fallback.pk).update(code="ENTRY", display_name="Entry")
    expiry = NOW + timedelta(days=5)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expiry)
    DeviceToken.objects.update(expires_at=expiry)

    response = post(client, REFRESH, {}, initial["activation_token"])

    assert response.status_code == 200, response.json()
    assert response.json()["license"]["expires_at"] == RENEWED_TO.isoformat()
    assert DeviceToken.objects.get().expires_at == RENEWED_TO
    assert LicensePlanAssignment.objects.get(license_key=licence).plan_id == fallback.pk
    assert FreeLicenseLifecycle.objects.get(customer=org).license_key_id == licence.pk
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == 1


def test_without_a_fallback_plan_first_activation_leaves_no_lifecycle_changes(client):
    org = self_service_org()
    session = admin_session(client, org)
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)

    reply = post(client, SESSION, body(), session)

    assert reply.status_code == 403
    assert reply.json()["error"]["code"] == "POLICY_DENIED"
    org.refresh_from_db()
    assert org.status == CustomerStatus.TRIAL
    assert not AppLicenseKey.objects.filter(customer=org).exists()
    assert not FreeLicenseLifecycle.objects.filter(customer=org).exists()
    assert not Device.objects.filter(customer=org).exists()
    assert not DeviceToken.objects.exists()
    assert not DeviceActivationOperation.objects.exists()
    assert not AuditEvent.objects.filter(
        action__in=["customer_org.free_activated", "license_key.generated", "device.activated"],
    ).exists()


@pytest.mark.parametrize("remaining, accepted", [(timedelta(microseconds=1), True), (timedelta(0), False)])
def test_refresh_uses_explicit_injected_clock_for_final_liveness(client, monkeypatch, remaining, accepted):
    from selahcue_api.apps.devices.services import authenticate_device_token
    from selahcue_api.apps.license_keys.free_lifecycle import renew_free_license_for_device
    from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

    monkeypatch.setattr(timezone, "now", lambda: NOW)
    _org, _session, initial, licence = activate_free(client)
    token = authenticate_device_token(initial["activation_token"])
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        starts_at=NOW - timedelta(days=1), expires_at=NOW + remaining,
    )
    DeviceToken.objects.filter(pk=token.pk).update(
        issued_at=NOW - timedelta(days=1), expires_at=NOW + remaining,
    )
    # A supplied instant remains authoritative in deterministic service-level tests.
    monkeypatch.setattr(timezone, "now", lambda: NOW + timedelta(days=1))
    if accepted:
        result = renew_free_license_for_device(token, NOW, "injected-final-liveness")
        assert result.changed
        assert result.token_expires_at == result.license_expires_at == RENEWED_TO
    else:
        before = DeviceToken.objects.values().get()
        with pytest.raises(SafeAPIError) as error:
            renew_free_license_for_device(token, NOW, "injected-final-liveness")
        assert error.value.code == ErrorCode.UNAUTHENTICATED
        assert DeviceToken.objects.values().get() == before
        assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()
