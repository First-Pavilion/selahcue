"""Approved unpriced catalogue, effective price versions and governed write invariants."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, close_old_connections, transaction
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from licensing_test_support import seed_org, issue_key, staff_actor
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.currency_reference import currency_minor_units, HISTORICAL_CODES
from selahcue_api.apps.catalogue.models import Plan, PlanPrice, GrantDimension, PlanGrant, MAX_PRICE_AMOUNT_MINOR
from selahcue_api.apps.catalogue.pricing import AppendPlanPriceData, append_plan_price, current_plan_price, plan_price_history
from selahcue_api.apps.catalogue.services import (set_license_plan_assignment, SetLicensePlanAssignmentData,
    resolve_entitlement, plan_device_instances_for_issuance)
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import SafeAPIError, ErrorCode

pytestmark = pytest.mark.django_db


def _actor():
    return ActorContext(kind=ActorKind.STAFF, actor_id="pricing-ops", staff_permissions=frozenset({StaffPermission.MANAGE_PLAN_PRICING}))


def _data(**kwargs):
    values = dict(plan_code="CORE", currency="USD", interval="MONTH", amount_minor=100,
                  effective_from=timezone.now()+timedelta(hours=1), reason="Approved pricing configuration.",
                  idempotency_key="price-version-test-0001")
    values.update(kwargs)
    return AppendPlanPriceData(**values)


def test_catalogue_contains_exactly_the_approved_unpriced_lineup():
    plans = list(Plan.objects.order_by("rank"))
    assert [(p.code, p.rank, p.is_fallback) for p in plans] == [("FREE",1,True),("CORE",2,False),("PRO",3,False)]
    assert not PlanPrice.objects.exists()
    assert not GrantDimension.objects.get(key="stt_minutes_per_period").is_active
    for key in ("cloud_transcript_minutes_per_week", "sermon_notes_per_week"):
        dimension = GrantDimension.objects.get(key=key)
        assert (dimension.value_type, dimension.default_raw_value, dimension.is_active) == ("INTEGER", "0", True)
    assert not GrantDimension.objects.get(key="device_instances").publish_in_manifest
    for plan, minutes, notes, watermark in zip(plans, (20,50,80), (1,5,10), ("true","false","false")):
        grants = {g.dimension.key: g for g in plan.grants.select_related("dimension")}
        for key, expected in {"device_instances":"1", "screen_outputs":"2", "ndi_outputs":"0",
                              "cloud_transcript_minutes_per_week":str(minutes), "sermon_notes_per_week":str(notes), "watermark":watermark}.items():
            assert grants[key].raw_value == expected
            if plan.rank > 1 and key in {"device_instances", "screen_outputs", "ndi_outputs"}:
                assert "PENDING D7(a)" in grants[key].reason
                assert grants[key].changed_by_actor_id
        assert plan_device_instances_for_issuance(plan) == 1


def test_rank_is_unique_positive_and_independent_of_display_order():
    plan = Plan.objects.get(code="FREE")
    plan.sort_order = 999
    plan.save(update_fields=["sort_order"])
    assert Plan.objects.order_by("rank").first().pk == plan.pk
    for rank in (0, 1):
        with pytest.raises(IntegrityError), transaction.atomic():
            Plan.objects.create(code="INVALID", display_name="Invalid", rank=rank,
                changed_by_actor_id="test-ops", reason="Rank constraint test.")


@pytest.mark.parametrize("code", ["FREE", "CORE", "PRO"])
def test_all_approved_plans_can_issue_and_be_assigned(code):
    result = issue_key(seed_org(code.lower()), tag="catalogue-"+code.lower(), plan_code=code)
    key = result.license_key
    assert key.device_limit == 1
    assert result.created
    assigned = set_license_plan_assignment(staff_actor(), SetLicensePlanAssignmentData(
        idempotency_key="assign-approved-"+code.lower(), license_key_id=str(key.pk), plan_code="FREE",
        reason="Explicit least-ranked assignment."))
    assert assigned.assignment.plan.code == "FREE"
    key.refresh_from_db()
    assert key.device_limit == 1


@pytest.mark.parametrize("value", [None, "0", "unlimited", "2147483648"])
def test_issuance_refuses_absent_or_invalid_private_seats_without_partial_success(value):
    plan = Plan.objects.get(code="CORE")
    grants = PlanGrant.objects.filter(plan=plan, dimension__key="device_instances")
    if value is None:
        grants.delete()
    else:
        grants.update(raw_value=value)
    before_keys, before_audit = AppLicenseKey.objects.count(), AuditEvent.objects.count()
    with pytest.raises(SafeAPIError) as caught:
        issue_key(seed_org("bad-seat"), tag="invalid-seat-catalogue", plan_code=plan.code)
    assert caught.value.code == ErrorCode.POLICY_DENIED
    assert AppLicenseKey.objects.count() == before_keys
    assert AuditEvent.objects.count() == before_audit


def test_price_absent_null_zero_multiple_currencies_intervals_and_effective_history():
    plan = Plan.objects.get(code="CORE")
    first = timezone.now()+timedelta(hours=1)
    assert current_plan_price(plan, "USD", "MONTH", at=first) is None
    unpriced = append_plan_price(_actor(), _data(amount_minor=None, effective_from=first))
    zero = append_plan_price(_actor(), _data(amount_minor=0, effective_from=first+timedelta(hours=1)))
    assert current_plan_price(plan,"USD","MONTH",at=first-timedelta(microseconds=1)) is None
    assert current_plan_price(plan,"USD","MONTH",at=first).pk == unpriced.pk
    assert current_plan_price(plan,"USD","MONTH",at=zero.effective_from).amount_minor == 0
    assert current_plan_price(plan,"USD","MONTH") is None, "future versions must not become current early"
    with patch("selahcue_api.apps.catalogue.pricing.timezone.now", return_value=zero.effective_from):
        assert current_plan_price(plan,"USD","MONTH").pk == zero.pk
    unpriced.refresh_from_db()
    assert unpriced.amount_minor is None and unpriced.effective_until == zero.effective_from
    assert zero.effective_until is None
    annual = append_plan_price(_actor(), _data(currency="JPY",interval="YEAR",amount_minor=123,effective_from=first))
    dinar = append_plan_price(_actor(), _data(currency="KWD",interval="WEEK",amount_minor=123,effective_from=first))
    assert annual.minor_unit_exponent == 0 and dinar.minor_unit_exponent == 3
    assert currency_minor_units("USD") == 2
    assert "DEM" in HISTORICAL_CODES
    with patch("selahcue_api.apps.catalogue.models.CURRENT_MINOR_UNITS", {}):
        historical = PlanPrice.objects.get(pk=annual.pk)
        assert historical.amount_minor == 123
        assert historical.minor_unit_exponent is None, "never guess a withdrawn currency exponent"


def test_history_read_is_bounded_and_does_not_query_per_effective_end():
    plan = Plan.objects.get(code="CORE")
    first = timezone.now()+timedelta(hours=1)
    for i in range(3): append_plan_price(_actor(), _data(effective_from=first+timedelta(hours=i)))
    with CaptureQueriesContext(connection) as queries:
        rows = list(plan_price_history(plan,"USD","MONTH",limit=2))
        assert [p.effective_until for p in rows] == [first+timedelta(hours=1), first+timedelta(hours=2)]
    assert len(queries) == 1
    with pytest.raises(SafeAPIError): plan_price_history(plan,"USD","MONTH",limit=1001)


def test_price_history_is_append_only_and_protects_plan_deletion():
    row = append_plan_price(_actor(), _data())
    for action in (lambda: row.save(), lambda: row.delete(), lambda: PlanPrice.objects.filter(pk=row.pk).update(amount_minor=9),
                   lambda: PlanPrice.objects.filter(pk=row.pk).delete()):
        with pytest.raises(ValidationError): action()
    with pytest.raises(ProtectedError): row.plan.delete()
    assert PlanPrice.objects.get(pk=row.pk).amount_minor == 100


@pytest.mark.parametrize("change", [
    {"amount_minor":-1}, {"amount_minor":True}, {"amount_minor":1.2}, {"amount_minor":Decimal("1.2")},
    {"amount_minor":"100"}, {"amount_minor":MAX_PRICE_AMOUNT_MINOR+1},
    {"currency":"USD\x00"}, {"interval":"MONTH\x00"}, {"currency":"ZZZ"}, {"currency":"usd"}, {"currency":"DEM"}, {"currency":"XAU"},
    {"interval":"DAY"}, {"reason":"short"}, {"reason":None},
    {"effective_from":datetime(2026,1,1)}, {"effective_from":timezone.now()-timedelta(days=1)},
])
def test_invalid_price_writes_nothing(change):
    before = AuditEvent.objects.count()
    with pytest.raises(SafeAPIError): append_plan_price(_actor(), _data(**change))
    assert not PlanPrice.objects.exists() and AuditEvent.objects.count() == before


def test_price_permission_actor_audit_atomicity_and_duplicate_timestamp():
    data = _data()
    for actor in (None, staff_actor(), replace(_actor(), actor_id=""), replace(_actor(), actor_id="bad\x00actor")):
        with pytest.raises(SafeAPIError): append_plan_price(actor, data)
    assert not PlanPrice.objects.exists()
    with patch("selahcue_api.apps.catalogue.pricing.record_audit_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError): append_plan_price(_actor(), data)
    assert not PlanPrice.objects.exists()
    row = append_plan_price(_actor(), data)
    with pytest.raises(SafeAPIError) as caught: append_plan_price(_actor(), data)
    assert caught.value.code == ErrorCode.CONFLICT
    assert PlanPrice.objects.count() == 1
    audit = AuditEvent.objects.get(action="catalogue.plan_price_added")
    assert audit.target_id == str(row.pk) and audit.actor_id == "pricing-ops"
    assert audit.reason == data.reason and audit.request_id == data.idempotency_key


@pytest.mark.django_db(transaction=True)
def test_concurrent_price_timestamp_has_exactly_one_version_and_one_success_audit():
    if connection.vendor != "postgresql":
        pytest.skip("needs real PostgreSQL row locks; hosted API job supplies PostgreSQL16")
    data = _data()
    barrier = Barrier(2)
    def write():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                row = append_plan_price(_actor(), data)
                return ("created", row.pk)
            except SafeAPIError as error:
                return ("refused", error.code)
        finally:
            connections["default"].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert sum(result[0] == "created" for result in results) == 1, results
    assert ("refused", ErrorCode.CONFLICT) in results
    assert PlanPrice.objects.count() == 1
    assert AuditEvent.objects.filter(action="catalogue.plan_price_added").count() == 1


@pytest.mark.parametrize("column,value", [("amount_minor",-1),("interval","DAY"),("currency","ZZZ"),
                                          ("changed_by_actor_id",""),("reason","short")])
def test_price_database_backstops_reject_ungoverned_invalid_rows(column, value):
    row = dict(plan_id=Plan.objects.get(code="CORE").pk,currency="USD",interval="MONTH",amount_minor=1,
               effective_from=timezone.now(),created_at=timezone.now(),changed_by_actor_id="test-ops",reason="Database backstop test.")
    row[column] = value
    columns = list(row)
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO selahcue_catalogue_planprice ('+','.join(columns)+') VALUES ('+','.join(['%s']*len(columns))+')',
                           [row[name] for name in columns])
    assert not PlanPrice.objects.exists()
