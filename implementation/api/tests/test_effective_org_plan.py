from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan, OrgPlanGrant
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.catalogue.services import resolve_entitlement
from selahcue_api.apps.devices.models import Device
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.apps.usage.contracts import CloudContext

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 11, 9, 10, tzinfo=UTC)
NOTES_KEY = "sermon_notes_per_week"


def church(zone="UTC", *, pk=None):
    key = uuid4().hex
    return CustomerOrg.objects.create(
        pk=pk, name="Weekly fixture church", slug=key, timezone=zone,
        country="NG", primary_contact_email="fixture@example.test",
        created_by_actor_id="fixture", idempotency_key=key, plan="PRO",
    )


def licence(org, code="FREE", *, length=30):
    key = uuid4().hex
    row = AppLicenseKey.objects.create(
        customer=org, key_type=LicenseKeyType.PAID, status=LicenseKeyStatus.ACTIVATED,
        key_prefix="fixture", key_suffix="0000", masked_key="fixture...0000",
        secret_hash="fixture", secret_fingerprint=key,
        starts_at=NOW-timedelta(days=5), expires_at=NOW+timedelta(days=length),
        generated_by_actor_id="fixture", generated_reason="Weekly fixture", idempotency_key=key,
        feature_scope="CHURCH",
    )
    LicensePlanAssignment.objects.create(
        plan=Plan.objects.get(code=code), license_key=row,
        assigned_by_actor_id="fixture", reason="Weekly fixture",
    )
    return row


def device(key):
    identifier = uuid4().hex
    return Device.objects.create(
        customer=key.customer, license_key=key, device_public_id=identifier,
        device_fingerprint=identifier, platform="macos", activated_by_actor_id="fixture",
        idempotency_key=identifier,
    )


def context(inst, meter, at=NOW):
    return CloudContext(
        inst.customer_id, inst.license_key_id, inst.pk, meter,
        effective_plan(inst.customer, at), None, "v1",
    )


def staff_grant(org, code, starts_at, ends_at, **fields):
    return OrgPlanGrant.objects.create(
        org=org, plan=Plan.objects.get(code=code), starts_at=starts_at, ends_at=ends_at,
        granted_by_actor_id="fixture-staff", reason="Weekly fixture grant", **fields,
    )


def test_free_fallback_ignores_customer_label():
    plan = effective_plan(church(), NOW)
    assert (plan.rank, plan.stt_seconds_limit, plan.notes_limit, plan.source) == (
        1, 1200, 1, "fallback",
    )


def test_plan_follows_selected_licence_then_active_higher_staff_grant():
    org = church()
    chosen = licence(org, "CORE", length=20)
    other = licence(org, "PRO", length=10)
    assert effective_plan(org, NOW).notes_limit == 5
    assert resolve_entitlement(other, at=NOW).values[NOTES_KEY] == 5

    staff_grant(org, "FREE", NOW, NOW + timedelta(days=2))
    assert effective_plan(org, NOW).plan_id == chosen.catalogue_plan_assignment.plan_id

    end = NOW + timedelta(hours=2)
    higher = staff_grant(org, "PRO", NOW, end)
    assert effective_plan(org, NOW).source == "staff_grant"
    assert resolve_entitlement(chosen, at=NOW).values[NOTES_KEY] == 10
    assert effective_plan(org, end).notes_limit == 5
    higher.ended_at = NOW + timedelta(hours=1)
    higher.save(update_fields=["ended_at"])
    assert effective_plan(org, higher.ended_at).notes_limit == 5


def test_grant_selection_never_enters_shared_catalogue_cache():
    first, second = church(), church()
    key1, key2 = licence(first), licence(second)
    staff_grant(first, "PRO", NOW, NOW + timedelta(days=1))
    assert resolve_entitlement(key1, at=NOW).values[NOTES_KEY] == 10
    assert resolve_entitlement(key2, at=NOW).values[NOTES_KEY] == 1
    assert effective_plan(second, NOW).notes_limit == 1
    plan = effective_plan(first, NOW)
    cached = GRANT_CACHE.get(plan.plan_id, plan.catalogue_revision)
    assert cached.values[NOTES_KEY] == 10
    assert not ({"org", "org_id", "settled", "remaining", "carried_debt"} & cached.values.keys())


def test_invalid_timezone_is_rejected_on_org_validation():
    org = church()
    org.timezone = "Africa/Imaginary"
    with pytest.raises(ValidationError) as caught:
        org.full_clean()
    assert "timezone" in caught.value.message_dict
