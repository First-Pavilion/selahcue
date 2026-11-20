"""Time-boxed BETA grant for self-service churches (17tnw2bhkd2)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from test_bound_activation import SESSION, admin_session, body, post
from test_native_account_surface import seed_license, seed_org
from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.catalogue import beta
from selahcue_api.apps.catalogue.beta import beta_window, ensure_beta_grant
from selahcue_api.apps.catalogue.models import OrgPlanGrant
from selahcue_api.apps.license_keys.models import AppLicenseKey

pytestmark = pytest.mark.django_db
END = datetime(2027, 5, 6, tzinfo=UTC)
BETA_ON = {"SELAHCUE_BETA_PLAN_CODE": "BETA", "SELAHCUE_BETA_ENDS_AT": "2027-05-06T00:00:00+00:00"}
REASON = "Public beta: all features until the beta end date"


@pytest.fixture(autouse=True)
def fresh_state():
    cache.clear()
    beta._WARNED.clear()
    services.set_email_sender(services.EmailSender())
    yield
    cache.clear()


def register(n=1, email="pastor@beta.example"):
    with TestCase.captureOnCommitCallbacks(execute=True):
        services.register_customer_user(services.RegisterCustomerUserData(
            idempotency_key=f"beta-signup-{n:04d}-abcdef", email=email,
            password="correct horse battery staple 9!", org_name=f"Beta Chapel {n}", country="NG",
        ))
    return CustomerOrg.objects.get(primary_contact_email=email)


def self_service_org():
    org = seed_org(tag="beta")
    org.status = CustomerStatus.TRIAL
    org.created_by_actor_id = "self_signup:" + "a" * 64
    org.save(update_fields=["status", "created_by_actor_id"])
    return org


def activate(client, org):
    session = admin_session(client, org)
    response = post(client, SESSION, body(), session)
    assert response.status_code == 200, response.json()
    return session, response.json()


@override_settings(**BETA_ON)
def test_registration_creates_one_beta_grant_until_the_end_date():
    org = register()
    grant = OrgPlanGrant.objects.get(org=org)
    assert grant.plan.code == "BETA"
    assert grant.ends_at == END
    assert grant.granted_by_actor_id == "system:beta"
    assert grant.reason == REASON
    assert grant.starts_at < grant.ends_at


@override_settings(**BETA_ON)
def test_first_activation_creates_the_grant_for_an_org_registered_before_beta(client):
    org = self_service_org()
    assert not OrgPlanGrant.objects.filter(org=org).exists()
    activate(client, org)
    grant = OrgPlanGrant.objects.get(org=org)
    assert grant.plan.code == "BETA" and grant.ends_at == END


@override_settings(**BETA_ON)
def test_repeated_registration_and_activation_keep_one_grant(client):
    org = register()
    register()  # same email: uniform accepted, no duplicate
    assert OrgPlanGrant.objects.filter(org=org).count() == 1
    session, _ = activate(client, org)
    post(client, SESSION, body(), session)
    assert OrgPlanGrant.objects.filter(org=org).count() == 1
    first = ensure_beta_grant(org, at=timezone.now())
    again = ensure_beta_grant(org, at=timezone.now())
    assert first.pk == again.pk == OrgPlanGrant.objects.get(org=org).pk


@pytest.mark.parametrize("off", [
    {"SELAHCUE_BETA_PLAN_CODE": "", "SELAHCUE_BETA_ENDS_AT": "2027-05-06T00:00:00+00:00"},
    {"SELAHCUE_BETA_PLAN_CODE": "BETA", "SELAHCUE_BETA_ENDS_AT": ""},
    {"SELAHCUE_BETA_PLAN_CODE": "", "SELAHCUE_BETA_ENDS_AT": ""},
])
def test_no_grant_when_beta_is_switched_off(client, off):
    with override_settings(**off):
        org = register()
        assert beta_window() is None
        other = self_service_org()
        _, reply = activate(client, other)
    assert OrgPlanGrant.objects.count() == 0
    licence = AppLicenseKey.objects.get(customer=other)
    assert licence.expires_at - licence.starts_at == timedelta(days=365)
    org.refresh_from_db()
    assert org.status == CustomerStatus.TRIAL
    assert reply["operation_state"] != "replay"


@override_settings(**BETA_ON)
def test_no_grant_after_the_beta_end():
    org = self_service_org()
    assert ensure_beta_grant(org, at=END) is None
    assert ensure_beta_grant(org, at=datetime(2027, 6, 1, tzinfo=UTC)) is None
    assert not OrgPlanGrant.objects.exists()


@pytest.mark.parametrize("cfg", [
    {"SELAHCUE_BETA_PLAN_CODE": "NOPE", "SELAHCUE_BETA_ENDS_AT": "2027-05-06T00:00:00+00:00"},
    {"SELAHCUE_BETA_PLAN_CODE": "BETA", "SELAHCUE_BETA_ENDS_AT": "not-a-date"},
])
def test_bad_beta_config_does_not_break_registration_or_activation(cfg, client, caplog):
    with override_settings(**cfg), caplog.at_level("WARNING", logger=beta.logger.name):
        org = register()
        other = self_service_org()
        activate(client, other)
    assert org.pk and not OrgPlanGrant.objects.exists()
    assert AppLicenseKey.objects.filter(customer=other).count() == 1
    warnings = [r for r in caplog.records if "misconfigured" in r.getMessage()]
    assert len(warnings) == 1


@override_settings(SELAHCUE_BETA_PLAN_CODE="NOPE", SELAHCUE_BETA_ENDS_AT="2027-05-06T00:00:00+00:00")
def test_repeated_bad_config_logs_one_warning(caplog):
    with caplog.at_level("WARNING", logger=beta.logger.name):
        assert beta_window() is None
        assert beta_window() is None
    assert len([r for r in caplog.records if "misconfigured" in r.getMessage()]) == 1


@override_settings(**BETA_ON)
def test_staff_managed_org_gets_no_beta_grant(client):
    org = seed_org(tag="staff")  # actor "test": not self-service
    seed_license(org)
    session = admin_session(client, org)
    response = post(client, SESSION, body(), session)
    assert response.status_code == 200, response.json()
    assert not OrgPlanGrant.objects.filter(org=org).exists()
