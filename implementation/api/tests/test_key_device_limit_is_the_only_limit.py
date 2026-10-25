"""Activation consults ONLY `AppLicenseKey.device_limit` (86ak5mn0m, DEC-004).

This pins the enforced truth the ticket opens with, on BOTH activation routes:

*   `POST /v1/activations` — the enrollment-key route.
*   `POST /v1/activations:with-session` — the signed-in administrator's route.

Each test changes the licence's limit and checks that the REFUSAL POINT MOVES WITH IT. That is
what makes this a pin rather than a coincidence: a limit that was read from anywhere else (a
constant, the plan, the org) would sit still when the key's number changes.

**Why the plan has MORE seats than the key here.** Every key below is issued on a plan with 5
seats and then set to a different number. If activation read the plan's seat count (or any
catalogue value) instead of the key's, the refusal would happen at 5, not at 2, and the test
fails. The org-level field no longer exists to be read; `test_org_device_limit_removed.py`
holds that part.

**Mutation record (how these were shown to bite).** The production reads are
`devices/services.py` `_activate_device_for_key` (`active_devices >= license_key.device_limit`)
and `_remint_is_within_plan_allowance` (`< license_key.device_limit`). Each was replaced in turn
with a constant and with a `customer.` attribute; every mutant turned this file red and every
revert turned it green. The record is in the pull request.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone

from licensing_test_support import issue_key, seat_plan_code, seed_org
from selahcue_api.apps.accounts import services as account_services
from selahcue_api.apps.accounts.models import CustomerRole, CustomerUser, CustomerUserStatus
from selahcue_api.apps.devices.models import Device, DeviceStatus, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

pytestmark = pytest.mark.django_db

PLAN_SEATS = 5
KEY_SEATS = 2
EMAIL = "pastor@limit.example"
PASSWORD = "correct-horse-battery"

assert KEY_SEATS < PLAN_SEATS, (
    "the key's limit must differ from the plan's, or a read of the plan instead of the key "
    "would be indistinguishable from the real one"
)


@pytest.fixture(autouse=True)
def _fresh_budgets(settings):
    """`/v1` is rate limited per (endpoint, client IP) in a process-wide cache; start empty and
    raise the budgets so a test that is not ABOUT throttling cannot trip one."""
    cache.clear()
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)


def _post(client, path, body, **extra):
    return client.post(path, data=json.dumps(body), content_type="application/json", **extra)


def _licensed_org(tag):
    """An org holding one key issued on a 5-seat plan, then set to KEY_SEATS."""
    org = seed_org(tag)
    result = issue_key(org, tag=tag, plan_code=seat_plan_code(PLAN_SEATS))
    AppLicenseKey.objects.filter(pk=result.license_key.pk).update(device_limit=KEY_SEATS)
    return org, AppLicenseKey.objects.get(pk=result.license_key.pk), result.full_key


class _EnrollmentKeyRoute:
    """`POST /v1/activations`."""

    name = "enrollment-key"

    def __init__(self, client, org, full_key):
        self.client = client
        self.full_key = full_key

    def activate(self, fingerprint):
        return _post(
            self.client,
            "/v1/activations",
            {
                "idempotency_key": f"act-{fingerprint}-0001",
                "license_key": self.full_key,
                "device_fingerprint": fingerprint,
                "platform": "macos",
            },
        )


class _SessionRoute:
    """`POST /v1/activations:with-session`, signed in as the org's administrator."""

    name = "with-session"

    def __init__(self, client, org, full_key):
        self.client = client
        CustomerUser.objects.create(
            customer=org,
            email=EMAIL,
            email_fingerprint=account_services._fingerprint(EMAIL),
            password_hash=make_password(PASSWORD),
            status=CustomerUserStatus.ACTIVE,
            role=CustomerRole.ADMIN,
            email_verified_at=timezone.now(),
            created_by_actor_id="test",
            idempotency_key="limit-user-0001",
        )
        login = _post(client, "/v1/sessions", {"email": EMAIL, "password": PASSWORD})
        assert login.status_code == 200, login.content
        self.bearer = {"HTTP_AUTHORIZATION": f"Bearer {login.json()['session_token']}"}

    def activate(self, fingerprint):
        return _post(
            self.client,
            "/v1/activations:with-session",
            {
                "idempotency_key": f"act-{fingerprint}-0001",
                "device_fingerprint": fingerprint,
                "platform": "macos",
            },
            **self.bearer,
        )


ROUTES = [_EnrollmentKeyRoute, _SessionRoute]


@pytest.fixture(params=ROUTES, ids=[route.name for route in ROUTES])
def route(request, client):
    org, key, full_key = _licensed_org(f"route-{request.param.name}")
    assert key.device_limit == KEY_SEATS, "premise: the key's limit differs from the plan's"
    return request.param(client, org, full_key), key


def test_the_key_limit_admits_exactly_that_many_and_refuses_the_next(route):
    activator, key = route

    for index in range(KEY_SEATS):
        admitted = activator.activate(f"fp-{index}")
        assert admitted.status_code == 200, (
            f"device {index + 1} of {KEY_SEATS} was refused: {admitted.content!r}"
        )

    refused = activator.activate("fp-over")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "POLICY_DENIED"
    # The ENTITY, not a proxy: the refused device left nothing behind.
    assert Device.objects.filter(license_key=key).count() == KEY_SEATS
    assert not Device.objects.filter(device_fingerprint="fp-over").exists()
    assert not DeviceToken.objects.filter(device__device_fingerprint="fp-over").exists()


def test_the_refusal_point_moves_when_the_key_limit_changes(route):
    """Raise the key by one and the same refused device is admitted. This is the assertion
    that fails if the limit is read from anywhere but the key."""
    activator, key = route
    for index in range(KEY_SEATS):
        assert activator.activate(f"fp-{index}").status_code == 200
    assert activator.activate("fp-third").status_code == 403

    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=KEY_SEATS + 1)

    admitted = activator.activate("fp-third")
    assert admitted.status_code == 200, (
        "raising the licence's device_limit did not admit the device it had just refused, so "
        "the limit is being read from somewhere other than the key"
    )
    assert (
        Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count()
        == KEY_SEATS + 1
    )
    # ...and the new ceiling is real, not "no ceiling".
    assert activator.activate("fp-fourth").status_code == 403


def test_lowering_the_key_limit_refuses_what_it_had_admitted(route):
    """The other direction, so a read that only ever returns a large number is caught too."""
    activator, key = route
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=1)

    assert activator.activate("fp-only").status_code == 200
    assert activator.activate("fp-second").status_code == 403


def _expire_every_token(key):
    gone = timezone.now() - timedelta(days=1)
    DeviceToken.objects.filter(device__license_key=key).update(
        issued_at=gone - timedelta(days=30), expires_at=gone
    )


def test_remint_allowance_follows_the_key_limit(client):
    """The second read of `device_limit`: after a lapse and a renewal, only the
    `device_limit` OLDEST devices may re-mint (`_remint_is_within_plan_allowance`).

    Three devices activate on a key of 3, the key is lowered to 1, and only the oldest device
    recovers. A re-mint rule reading a constant, or the plan's 5, would revive all three.
    """
    org = seed_org("remint-follows")
    result = issue_key(org, tag="remint-follows", plan_code=seat_plan_code(PLAN_SEATS))
    key = AppLicenseKey.objects.get(pk=result.license_key.pk)
    AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=3)
    activator = _EnrollmentKeyRoute(client, org, result.full_key)
    for index in range(3):
        assert activator.activate(f"fp-{index}").status_code == 200

    _expire_every_token(key)
    AppLicenseKey.objects.filter(pk=key.pk).update(
        device_limit=1, status=LicenseKeyStatus.ACTIVATED
    )

    assert activator.activate("fp-0").status_code == 200, "the oldest seat must recover"
    for index in (1, 2):
        denied = activator.activate(f"fp-{index}")
        assert denied.status_code == 403, (
            f"fp-{index} is beyond the key's limit of 1 but was re-minted"
        )
        assert denied.json()["error"]["code"] == "POLICY_DENIED"
