"""The device limit and plan end come from the church's effective plan (17tnw2bhkd2).

Owner ruling 2026-11-20: after the beta ends only the church's oldest-activated device keeps
working. It still re-mints; every other device is refused on its next re-mint, new devices are
refused, and nothing is deactivated.
"""

import base64
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from test_bound_activation import SESSION, body, post
from test_device_token_remint import _expire_tokens
from test_native_account_surface import seed_org, seed_user
from selahcue_api.apps.accounts.models import CustomerStatus
from selahcue_api.apps.catalogue import beta
from selahcue_api.apps.catalogue.models import OrgPlanGrant
from selahcue_api.apps.devices.limits import effective_device_limit
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import authenticate_device_token
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.apps.license_keys.models import AppLicenseKey

pytestmark = pytest.mark.django_db
END = datetime(2027, 5, 6, tzinfo=UTC)
DURING = END - timedelta(days=10)
BETA_ON = {"SELAHCUE_BETA_PLAN_CODE": "BETA", "SELAHCUE_BETA_ENDS_AT": "2027-05-06T00:00:00+00:00"}
SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")
PASSWORD = "Synthetic-test-only-248!"


@pytest.fixture(autouse=True)
def fresh_state(settings):
    cache.clear()
    beta._WARNED.clear()
    settings.ENTITLEMENT_SIGNING_KEY = SEED_B64
    yield
    cache.clear()


@pytest.fixture
def clock(monkeypatch):
    """A movable `timezone.now`, the way the free-licence lifecycle tests freeze time."""
    state = {"now": DURING}
    monkeypatch.setattr(timezone, "now", lambda: state["now"])
    return state


def self_service_org(tag="limit"):
    org = seed_org(tag=tag)
    org.status = CustomerStatus.TRIAL
    org.created_by_actor_id = "self_signup:" + "a" * 64
    org.save(update_fields=["status", "created_by_actor_id"])
    email = f"limit-admin-{org.pk}@fixture.test"
    seed_user(org, email=email, password=PASSWORD)
    return org, email


def login(client, email):
    reply = post(client, "/v1/sessions", {"email": email, "password": PASSWORD})
    assert reply.status_code == 200, reply.json()
    return reply.json()["session_token"]


def nonce(n):
    return f"{n:032d}"


def activate(client, session, n, *, expected=None, booth=None):
    """One bound activation (request `n`) for booth `booth` (default `n`). The cache is
    cleared so the per-IP activation throttle (10 a minute) does not stand in for the limit."""
    cache.clear()
    fingerprint = f"booth-{booth or n:02d}"
    return post(
        client, SESSION, body(nonce(n), expected=expected, device_fingerprint=fingerprint), session,
    )


def payload(token):
    result = build_entitlement_manifest(token)
    return verify_envelope(result.envelope, public_key=load_signing_key(SEED_B64).public_key())


def licence_of(org):
    return AppLicenseKey.objects.get(customer=org)


@override_settings(**BETA_ON)
def test_beta_church_activates_ten_devices_and_the_eleventh_is_refused(client, clock):
    org, email = self_service_org()
    session = login(client, email)
    for n in range(1, 11):
        reply = activate(client, session, n)
        assert reply.status_code == 200, (n, reply.json())
    assert OrgPlanGrant.objects.get(org=org).plan.code == "BETA"
    eleventh = activate(client, session, 11)
    assert eleventh.status_code != 200
    assert eleventh.json()["error"]["code"] == "POLICY_DENIED"
    assert Device.objects.filter(customer=org).count() == 10
    # The licence itself still says one seat: the ten come from the plan, not a rewrite.
    assert licence_of(org).device_limit == 1


@override_settings(**BETA_ON)
def test_entitlement_reports_ten_instances_and_the_beta_end(client, clock):
    org, email = self_service_org()
    reply = activate(client, login(client, email), 1)
    assert reply.status_code == 200, reply.json()
    signed = payload(reply.json()["activation_token"])
    assert signed["instances_limit"] == 10
    # Same formatter as `license_expires_at` (datetime.isoformat on an aware UTC value).
    assert signed["plan_ends_at"] == "2027-05-06T00:00:00+00:00"
    assert signed["plan_ends_at"] == END.isoformat()
    assert signed["grants"]["watermark"] is False
    refresh = post(client, "/v1/license:refresh", {}, reply.json()["activation_token"])
    assert refresh.status_code == 200, refresh.json()
    assert refresh.json()["instances"]["limit"] == 10


@override_settings(**BETA_ON)
def test_after_the_beta_end_a_second_new_device_is_refused(client, clock):
    org, email = self_service_org()
    session = login(client, email)
    first = activate(client, session, 1)
    assert first.status_code == 200, first.json()
    token = first.json()["activation_token"]
    key = licence_of(org)
    assert effective_device_limit(key, DURING) == 10  # positive control
    clock["now"] = END
    assert effective_device_limit(key, END) == 1
    second = activate(client, login(client, email), 2)
    assert second.status_code != 200
    assert second.json()["error"]["code"] == "POLICY_DENIED"
    signed = payload(token)
    assert signed["plan_ends_at"] is None
    assert signed["instances_limit"] == 1


def test_free_church_without_beta_keeps_one_device(client, clock):
    org, email = self_service_org()
    session = login(client, email)
    assert activate(client, session, 1).status_code == 200
    assert not OrgPlanGrant.objects.filter(org=org).exists()
    assert effective_device_limit(licence_of(org), DURING) == 1
    second = activate(client, session, 2)
    assert second.json()["error"]["code"] == "POLICY_DENIED"


@override_settings(**BETA_ON)
def test_after_the_beta_end_only_the_oldest_device_reconnects(client, clock):
    org, email = self_service_org()
    session = login(client, email)
    ids = []
    for n in (1, 2, 3):
        reply = activate(client, session, n)
        assert reply.status_code == 200, reply.json()
        ids.append(reply.json()["device"]["device_public_id"])
        clock["now"] += timedelta(seconds=1)  # distinct activation order
    key = licence_of(org)

    # Positive control: before the end every device re-mints.
    _expire_tokens(key, at=clock["now"] - timedelta(minutes=1))
    for n, expected in zip((1, 2, 3), ids):
        reply = activate(client, session, 10 + n, expected=expected, booth=n)
        assert reply.status_code == 200, reply.json()
        assert reply.json()["reminted"] is True

    clock["now"] = END
    session = login(client, email)
    _expire_tokens(key, at=END - timedelta(minutes=1))
    oldest = activate(client, session, 21, expected=ids[0], booth=1)
    assert oldest.status_code == 200, oldest.json()
    assert oldest.json()["reminted"] is True
    for n, booth, expected in zip((22, 23), (2, 3), ids[1:]):
        refused = activate(client, session, n, expected=expected, booth=booth)
        assert refused.status_code != 200
        assert refused.json()["error"]["code"] == "POLICY_DENIED"
    statuses = set(Device.objects.filter(customer=org).values_list("status", flat=True))
    assert statuses == {DeviceStatus.ACTIVE}
    assert Device.objects.filter(customer=org).count() == 3


@override_settings(**BETA_ON)
def test_effective_plan_ends_at_is_set_only_by_a_winning_grant():
    from selahcue_api.apps.catalogue.beta import ensure_beta_grant
    from selahcue_api.apps.catalogue.org_plans import effective_plan

    org, _email = self_service_org()
    assert effective_plan(org, DURING).ends_at is None  # fallback plan: no end
    grant = ensure_beta_grant(org, at=DURING)
    plan = effective_plan(org, DURING)
    assert (plan.source, plan.ends_at) == ("staff_grant", END)
    # Staff ending the grant early moves the reported end with it.
    early = DURING + timedelta(days=2)
    OrgPlanGrant.objects.filter(pk=grant.pk).update(ended_at=early)
    assert effective_plan(org, DURING).ends_at == early
    assert effective_plan(org, early).ends_at is None


def refresh(client, token):
    cache.clear()
    return post(client, "/v1/license:refresh", {}, token)


def token_rows(org):
    from selahcue_api.apps.devices.models import DeviceToken

    return sorted(
        DeviceToken.objects.filter(device__customer=org).values_list("pk", "status", "expires_at")
    )


@override_settings(**BETA_ON)
def test_after_the_beta_end_non_oldest_device_with_valid_token_is_refused(client, clock):
    from selahcue_api.graphql.errors import SafeAPIError

    org, email = self_service_org()
    session = login(client, email)
    tokens = []
    for n in (1, 2, 3):
        reply = activate(client, session, n)
        assert reply.status_code == 200, reply.json()
        tokens.append(reply.json()["activation_token"])
        clock["now"] += timedelta(seconds=1)

    # Positive control: during the beta every device refreshes and gets a manifest.
    for token in tokens:
        assert refresh(client, token).status_code == 200
        assert payload(token)["instances_limit"] == 10

    clock["now"] = END + timedelta(days=30)
    before = token_rows(org)
    oldest = refresh(client, tokens[0])
    assert oldest.status_code == 200, oldest.json()
    assert payload(tokens[0])["instances_limit"] == 1
    after_oldest = token_rows(org)
    for token in tokens[1:]:
        reply = refresh(client, token)
        assert reply.status_code == 403
        assert reply.json()["error"]["code"] == "POLICY_DENIED"
        with pytest.raises(SafeAPIError) as caught:
            build_entitlement_manifest(token)
        assert caught.value.code == "POLICY_DENIED"
    # No token issued or extended for the refused devices, and nothing deactivated.
    assert token_rows(org) == after_oldest
    assert len(after_oldest) == len(before) == 3
    statuses = set(Device.objects.filter(customer=org).values_list("status", flat=True))
    assert statuses == {DeviceStatus.ACTIVE}


@override_settings(**BETA_ON)
def test_a_grant_plan_without_a_usable_seat_number_falls_back_to_the_key_limit(client, clock):
    from selahcue_api.apps.catalogue.cache import GRANT_CACHE
    from selahcue_api.apps.catalogue.models import PlanGrant

    org, email = self_service_org()
    assert activate(client, login(client, email), 1).status_code == 200
    key = licence_of(org)
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=2)
    key.refresh_from_db()
    assert effective_device_limit(key, DURING) == 10  # positive control: the grant applies
    updated = PlanGrant.objects.filter(
        plan__code="BETA", dimension__key="device_instances",
    ).update(raw_value="unlimited")
    assert updated == 1
    GRANT_CACHE.clear()
    try:
        assert effective_device_limit(key, DURING) == 2
    finally:
        GRANT_CACHE.clear()


def three_beta_devices(client, clock):
    org, email = self_service_org()
    session = login(client, email)
    tokens = []
    for n in (1, 2, 3):
        reply = activate(client, session, n)
        assert reply.status_code == 200, reply.json()
        tokens.append(reply.json()["activation_token"])
        clock["now"] += timedelta(seconds=1)
    return org, email, tokens


def device_rows(org):
    return sorted(Device.objects.filter(customer=org).values_list(
        "pk", "status", "license_key_id", "created_at", "device_fingerprint",
    ))


def quota(client, token):
    cache.clear()
    return client.get("/v1/quota", HTTP_AUTHORIZATION=f"Bearer {token}")


@override_settings(**BETA_ON)
def test_auth_fails_open_when_the_plan_read_fails(client, clock, monkeypatch):
    from django.db import DatabaseError
    from selahcue_api.apps.devices import limits

    org, email, tokens = three_beta_devices(client, clock)
    session = login(client, email)
    for n in range(4, 11):
        assert activate(client, session, n).status_code == 200
    assert Device.objects.filter(customer=org).count() == 10

    def broken(*args, **kwargs):
        raise DatabaseError("catalogue unavailable")

    monkeypatch.setattr(limits, "_select_org_plan", broken)
    # Device 3 is past the key's own limit of 1, so its auth needs the plan read, which fails:
    # a live device is never denied over a catalogue fault (NFR-024).
    assert refresh(client, tokens[2]).status_code == 200
    # A NEW device still falls back to the key's own limit, so the 11th is refused.
    eleventh = activate(client, session, 11)
    assert eleventh.json()["error"]["code"] == "POLICY_DENIED"
    assert Device.objects.filter(customer=org).count() == 10


@override_settings(**BETA_ON)
def test_a_device_within_the_key_limit_authenticates_without_a_plan_read(client, clock, monkeypatch):
    from selahcue_api.apps.devices import limits

    _org, _email, tokens = three_beta_devices(client, clock)
    calls = []
    real = limits._select_org_plan
    monkeypatch.setattr(limits, "_select_org_plan", lambda *a: calls.append(a) or real(*a))
    authenticate_device_token(tokens[0])  # device 1: inside the key's own limit of 1
    assert calls == []
    authenticate_device_token(tokens[1])  # positive control: device 2 does need the read
    assert len(calls) == 1


@override_settings(**BETA_ON)
def test_a_cloud_route_refuses_non_oldest_devices_after_the_beta(client, clock, monkeypatch):
    from types import SimpleNamespace
    from selahcue_api.platform import cloud_views

    # The cloud budget runs AFTER auth and is not under test here (as in
    # test_quota_read_only_sql.py); stub it so device 1's pass is about auth alone.
    monkeypatch.setattr(cloud_views, "evaluate_cloud_budget", lambda **kwargs: SimpleNamespace(
        outcome=cloud_views.BudgetOutcome.ALLOWED,
    ))
    _org, _email, tokens = three_beta_devices(client, clock)
    clock["now"] = END + timedelta(days=30)
    first = quota(client, tokens[0])
    assert first.status_code == 200, first.content
    for token in tokens[1:]:
        reply = quota(client, token)
        assert reply.status_code == 403, reply.content
        assert reply.json()["error"]["code"] == "POLICY_DENIED"


@override_settings(**BETA_ON)
def test_a_dead_token_for_an_over_allowance_device_is_unauthenticated(client, clock):
    from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus

    org, _email, tokens = three_beta_devices(client, clock)
    clock["now"] = END + timedelta(days=30)
    devices = list(Device.objects.filter(customer=org).order_by("created_at", "pk"))
    DeviceToken.objects.filter(device=devices[1]).update(status=DeviceTokenStatus.REVOKED)
    DeviceToken.objects.filter(device=devices[2]).update(
        issued_at=clock["now"] - timedelta(days=60), expires_at=clock["now"] - timedelta(minutes=1),
    )
    for token in tokens[1:]:
        reply = refresh(client, token)
        assert reply.status_code == 401
        assert reply.json()["error"]["code"] == "UNAUTHENTICATED"


@override_settings(**BETA_ON)
def test_a_new_grant_after_the_beta_lets_the_same_devices_back_in(client, clock):
    from selahcue_api.apps.catalogue.models import Plan

    org, _email, tokens = three_beta_devices(client, clock)
    clock["now"] = END + timedelta(days=30)
    assert refresh(client, tokens[1]).status_code == 403
    rows = device_rows(org)
    OrgPlanGrant.objects.create(
        org=org, plan=Plan.objects.get(code="BETA"), starts_at=clock["now"],
        ends_at=clock["now"] + timedelta(days=30), granted_by_actor_id="staff_ops_1",
        reason="Beta extension for this church",
    )
    for token in tokens:
        assert refresh(client, token).status_code == 200
    assert device_rows(org) == rows
