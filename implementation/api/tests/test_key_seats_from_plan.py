"""A licence's device limit is COPIED FROM ITS PLAN at issuance (86ak5mn0m).

Before this change staff typed a number into `GenerateLicenseKeyData.device_limit`, and nothing
linked it to the catalogue's `device_instances` grant. A "Pro" licence could be issued with any
seat count, and the console showed one number while a plan row said another.

Now issuing a licence sets `AppLicenseKey.device_limit` from the plan's resolved
`device_instances` value, and REFUSES (POLICY_DENIED, nothing written) when that value is
absent, `unlimited` or below 1: a key with no ceiling or no seats is not a licence anyone
meant to sell. `AppLicenseKey.device_limit` stays the one number activation enforces, the
manifest publishes and the refresh endpoint reports; the catalogue is only where it comes from.

**Every plan here is created by the test, with its own seat count.** The catalogue seed is not a
fixture for seat counts (the reseed ticket 17tnw2az0gd will change it), and the derivation is
DATA-driven: changing a plan's value with `set_plan_grant` changes the NEXT key issued and no
older one.
"""

from __future__ import annotations

import pytest

from licensing_test_support import (
    SEAT_DIMENSION_KEY,
    issue_key,
    seat_plan,
    seat_plan_code,
    seed_org,
    staff_actor,
)
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import GrantDimension, LicensePlanAssignment
from selahcue_api.apps.catalogue.services import SetPlanGrantData, set_plan_grant
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db


def _set_seats(plan_code, raw_value, *, tag):
    return set_plan_grant(
        staff_actor(),
        SetPlanGrantData(
            idempotency_key=f"seat-grant-{tag}",
            plan_code=plan_code,
            dimension_key=SEAT_DIMENSION_KEY,
            raw_value=raw_value,
            reason="The test changes the plan's seat count.",
        ),
    )


def _counts():
    return (
        AppLicenseKey.objects.count(),
        LicensePlanAssignment.objects.count(),
        AuditEvent.objects.filter(action="license_key.generated").count(),
    )


@pytest.mark.parametrize("seats", [1, 3, 7, 12])
def test_the_key_takes_its_device_limit_from_the_plan(seats):
    plan = seat_plan(f"OWN-{seats}", seats)

    result = issue_key(seed_org(f"seats-{seats}"), tag=f"seats-{seats}", plan_code=plan.code)

    assert result.license_key.device_limit == seats
    # Read back from the database, not the in-memory instance the service returned.
    assert AppLicenseKey.objects.get(pk=result.license_key.pk).device_limit == seats


def test_changing_the_plan_value_changes_the_next_key_and_no_older_one():
    plan = seat_plan("OWN-MOVES", 3)
    older = issue_key(seed_org("moves-a"), tag="moves-a", plan_code=plan.code)
    assert older.license_key.device_limit == 3

    _set_seats(plan.code, "5", tag="moves-up")
    newer = issue_key(seed_org("moves-b"), tag="moves-b", plan_code=plan.code)

    assert newer.license_key.device_limit == 5, (
        "the next key did not pick up the plan's new value, so the number is cached or "
        "hardcoded rather than read from the catalogue"
    )
    assert AppLicenseKey.objects.get(pk=older.license_key.pk).device_limit == 3, (
        "an already-issued key's limit moved with the plan; this change must not touch keys "
        "that exist (plan changes after issuance are FR-516, not built)"
    )

    _set_seats(plan.code, "2", tag="moves-down")
    lower = issue_key(seed_org("moves-c"), tag="moves-c", plan_code=plan.code)
    assert lower.license_key.device_limit == 2


def test_two_plans_give_two_different_limits():
    """The limit follows the PLAN NAMED, not a constant and not a default."""
    small = seat_plan("OWN-SMALL", 2)
    large = seat_plan("OWN-LARGE", 9)

    a = issue_key(seed_org("pair-a"), tag="pair-a", plan_code=small.code)
    b = issue_key(seed_org("pair-b"), tag="pair-b", plan_code=large.code)

    assert (a.license_key.device_limit, b.license_key.device_limit) == (2, 9)


def test_a_plan_with_no_seat_value_is_refused_and_nothing_is_written(caplog):
    plan = seat_plan("OWN-NO-SEATS", None)
    assert GrantDimension.objects.get(key=SEAT_DIMENSION_KEY).default_raw_value == "", (
        "premise: the dimension has no catalogue-wide default, so a plan that grants nothing "
        "resolves to an ABSENT value (a default would make this a different test)"
    )
    org = seed_org("no-seats")
    before = _counts()

    with caplog.at_level("WARNING", logger="selahcue_api.apps.license_keys.services"):
        with pytest.raises(SafeAPIError) as caught:
            issue_key(org, tag="no-seats", plan_code=plan.code)

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value
    assert _counts() == before, "a refused issuance left a row behind"
    assert not AppLicenseKey.objects.filter(customer=org).exists()
    # The reason has to reach somewhere an operator looks: GraphQL discards the message.
    message = str(caught.value)
    assert plan.code in message and SEAT_DIMENSION_KEY in message, message
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert plan.code in logged and SEAT_DIMENSION_KEY in logged, logged


@pytest.mark.parametrize("raw_value", ["unlimited", "0"])
def test_a_plan_with_no_ceiling_or_no_seats_is_refused(raw_value):
    plan = seat_plan(f"OWN-BAD-{raw_value}".upper(), 4)
    _set_seats(plan.code, raw_value, tag=f"bad-{raw_value}")
    org = seed_org(f"bad-{raw_value}")
    before = _counts()

    with pytest.raises(SafeAPIError) as caught:
        issue_key(org, tag=f"bad-{raw_value}", plan_code=plan.code)

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value
    assert _counts() == before


def test_a_plan_value_too_large_for_the_column_is_refused_not_a_database_error():
    """`device_limit` is a 32-bit positive integer. A plan value past it must be a refusal at
    issuance, not an unmapped database error from the INSERT."""
    plan = seat_plan("OWN-HUGE", 4)
    _set_seats(plan.code, str(2**31), tag="huge")
    org = seed_org("huge")
    before = _counts()

    with pytest.raises(SafeAPIError) as caught:
        issue_key(org, tag="huge", plan_code=plan.code)

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value
    assert _counts() == before
    # POSITIVE CONTROL: the largest value the column holds is accepted, so the bound is the
    # column's and not an arbitrary smaller number.
    _set_seats(plan.code, str(2**31 - 1), tag="huge-ok")
    ok = issue_key(seed_org("huge-ok"), tag="huge-ok", plan_code=plan.code)
    assert ok.license_key.device_limit == 2**31 - 1


def test_a_boolean_typed_seat_dimension_is_refused_rather_than_read_as_one_seat():
    """`True` is an `int` in Python, so a BOOLEAN dimension under this key would otherwise read
    as a single seat."""
    GrantDimension.objects.filter(key=SEAT_DIMENSION_KEY).update(value_type="BOOLEAN")
    GRANT_CACHE.clear()
    plan = seat_plan("OWN-BOOLEAN", "true")

    with pytest.raises(SafeAPIError) as caught:
        issue_key(seed_org("boolean"), tag="boolean", plan_code=plan.code)

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value


def test_a_plan_whose_seat_dimension_is_switched_off_is_refused():
    """`resolve` skips inactive dimensions, so the value is ABSENT, which is refused rather than
    defaulted. A switched-off dimension must not leave keys issuing with a made-up number."""
    plan = seat_plan("OWN-DIM-OFF", 4)
    GrantDimension.objects.filter(key=SEAT_DIMENSION_KEY).update(is_active=False)
    # The cache is keyed by catalogue revision and a queryset update does not bump it.
    GRANT_CACHE.clear()

    with pytest.raises(SafeAPIError) as caught:
        issue_key(seed_org("dim-off"), tag="dim-off", plan_code=plan.code)

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value


def test_the_audit_row_records_the_plan_and_the_limit_it_produced():
    plan = seat_plan("OWN-AUDITED", 6)

    result = issue_key(seed_org("audited"), tag="audited", plan_code=plan.code)

    event = AuditEvent.objects.get(
        action="license_key.generated", target_id=str(result.license_key.pk)
    )
    assert event.after["plan_code"] == plan.code
    assert event.after["device_limit"] == 6


def test_a_helper_plan_is_a_real_catalogue_plan():
    """POSITIVE CONTROL for the helper every test above relies on: the plan it builds resolves
    to the seat count it was given, through the same service path production uses."""
    code = seat_plan_code(5)
    result = issue_key(seed_org("helper"), tag="helper", plan_code=code)
    assert result.license_key.device_limit == 5
