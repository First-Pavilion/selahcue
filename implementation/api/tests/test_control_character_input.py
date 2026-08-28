"""Caller-supplied control characters are refused at the service boundary, on BOTH engines.

A NUL byte survives `.strip()` and `str.split()` — Python does not treat it as whitespace —
so before this it reached the database, where the two engines disagreed and both answers were
wrong:

    Postgres  `DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`, unmapped,
              so it escaped as a bare failure that `safe_graphql_error` flattened to the
              generic "The request is invalid." — masked, unlogged, unaudited, and
              indistinguishable from ordinary bad input.
    SQLite    no error at all: the NUL was STORED. In `feature_scope`'s case it would travel
              into a signed entitlement manifest cached offline until the licence expired.

The fix refuses up front, which is why this file passes identically on both engines. Catching
`DataError` instead would execute only on Postgres, leaving the SQLite path — the one every
local `pytest` run takes — never entering the handler, so these tests would have passed
locally without exercising the mechanism at all.

**The lookup guards are asserted through their LOG, not only their outcome**, and that is
load-bearing rather than decorative. On SQLite `Plan.objects.filter(code="PRO\x00")` already
returns None and lands on the same NOT_FOUND, so deleting the guard entirely changes nothing
observable there — a mutation battery run on SQLite scores those tests as passing with the
control removed. The warning the guard emits is the one effect that exists on both engines, so
asserting it is what makes these tests fail when the control they name is deleted. It is also
the "auditable" half of the finding: a refusal nobody can see in a log is the masked outcome
that was being reported.

**Two different refusals, deliberately.** A value that is looked up (`plan_code`,
`dimension_key`) takes the SAME `NOT_FOUND` an ordinary unknown code takes, because a control
character cannot name a row and inventing a third outcome would make the refusal harder to
reason about, not easier. A value that is STORED (`reason`, `feature_scope`, `territory`,
`timezone`) is `VALIDATION_FAILED`, because there is no "not found" to speak of.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, PlanGrant
from selahcue_api.apps.catalogue.services import (
    SetLicensePlanAssignmentData,
    SetPlanGrantData,
    set_license_plan_assignment,
    set_plan_grant,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key
from selahcue_api.graphql.context import (
    ActorContext,
    ActorKind,
    StaffPermission,
    has_control_characters,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

NUL = "\x00"

LK_LOGGER = "selahcue_api.apps.license_keys.services"
CS_LOGGER = "selahcue_api.apps.catalogue.services"

# Pinned at IMPORT time: NUL is the character the whole file is about, and `str.split()` NOT
# treating it as whitespace is the entire reason it survived `require_reason`'s collapse. If
# Python ever changed that, the reason tests below would pass while testing nothing.
assert "x\x00y".split() == ["x\x00y"], (
    "str.split() now treats NUL as whitespace, so `require_reason`'s collapse would strip it "
    "and the reason cases in this file no longer reach the control-character guard"
)
assert has_control_characters(NUL), "the guard does not consider NUL a control character"


def _staff(*permissions):
    return ActorContext(
        kind=ActorKind.STAFF, actor_id="staff_ops_1", staff_permissions=frozenset(permissions)
    )


def _org(tag):
    return CustomerOrg.objects.create(
        name=f"Control Church {tag}",
        slug=f"control-church-{tag}",
        primary_contact_email=f"ops+{tag}@control.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=9,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"control-org-{tag}",
    )


def _issue_data(customer, *, tag, **overrides):
    now = timezone.now().replace(microsecond=0)
    fields = dict(
        idempotency_key=f"control-license-{tag}",
        customer_id=str(customer.id),
        key_type="TRIAL",
        feature_scope="CHURCH",
        plan_code="PRO",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        timezone="Africa/Lagos",
        seat_limit=5,
        device_limit=3,
        territory="NG",
        reason="Pilot for the control-character tests.",
    )
    fields.update(overrides)
    return GenerateLicenseKeyData(**fields)


def _issue(tag, **overrides):
    return generate_license_key(
        _staff(StaffPermission.GENERATE_LICENSE_KEY),
        _issue_data(_org(tag), tag=tag, **overrides),
    )


# --- Issuance --------------------------------------------------------------------------------


def test_a_control_character_in_plan_code_is_refused_as_an_unknown_plan(caplog):
    """The SAME refusal an ordinary unknown code takes — not a third outcome, and above all
    not the unmapped `DataError` that used to escape on Postgres."""
    before = set(AppLicenseKey.objects.values_list("id", flat=True))

    with caplog.at_level("WARNING", logger=LK_LOGGER):
        with pytest.raises(SafeAPIError) as caught:
            _issue("nul-plan", plan_code="PRO" + NUL)

    # The log first, because on SQLite the outcome below is identical with the guard DELETED.
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "control character" in logged, (
        "the guard did not run — on SQLite the NOT_FOUND below happens anyway, so without "
        f"this the test passes with the control removed. Log was: {logged!r}"
    )
    assert caught.value.extensions["code"] == ErrorCode.NOT_FOUND.value
    assert set(AppLicenseKey.objects.values_list("id", flat=True)) == before
    assert LicensePlanAssignment.objects.count() == 0


def test_the_control_character_refusal_matches_an_ordinary_unknown_code():
    """Consistency is the point of the finding, so it is asserted directly rather than
    inferred from two separate tests that each happen to say NOT_FOUND."""
    with pytest.raises(SafeAPIError) as nul_case:
        _issue("nul-consistency", plan_code="PRO" + NUL)
    with pytest.raises(SafeAPIError) as unknown_case:
        _issue("unknown-consistency", plan_code="NO-SUCH-PLAN")

    assert nul_case.value.extensions["code"] == unknown_case.value.extensions["code"], (
        "a control character and an ordinary unknown code produce different outcomes, which "
        "is the inconsistency this fix exists to remove"
    )


@pytest.mark.parametrize("field", ["reason", "feature_scope", "territory", "timezone"])
def test_a_control_character_in_stored_text_is_refused_and_stores_nothing(field):
    """These reach the row verbatim, and `feature_scope` travels on into a SIGNED manifest
    cached offline until the licence expires. On SQLite the NUL used to be stored silently."""
    before = set(AppLicenseKey.objects.values_list("id", flat=True))
    value = {
        "reason": "An adequate reason" + NUL + " for this.",
        "feature_scope": "CHURCH" + NUL,
        "territory": "N" + NUL,
        "timezone": "Africa/Lagos" + NUL,
    }[field]

    with pytest.raises(SafeAPIError) as caught:
        _issue(f"nul-{field}", **{field: value})

    assert caught.value.extensions["code"] == ErrorCode.VALIDATION_FAILED.value
    assert set(AppLicenseKey.objects.values_list("id", flat=True)) == before, (
        f"a licence was stored despite a control character in {field}"
    )


def test_a_clean_issuance_still_succeeds():
    """POSITIVE CONTROL. Without it, a guard that refuses EVERY issuance — or an issuance path
    broken outright — would satisfy every refusal above."""
    result = _issue("clean")

    assert result.created is True
    assert result.full_key is not None
    stored = AppLicenseKey.objects.get(id=result.license_key.id)
    assert stored.feature_scope == "CHURCH"
    assert not has_control_characters(stored.generated_reason)


def test_a_multi_line_reason_is_still_accepted():
    """POSITIVE CONTROL for the `require_reason` guard specifically. Tab, newline and carriage
    return are collapsed to single spaces BEFORE the control-character check, so a reason typed
    across lines must still work — the guard targets NUL and friends, not ordinary whitespace.
    """
    result = _issue("multiline", reason="An adequate reason\nspread\tacross\r\nseveral lines.")

    assert result.created is True
    stored = AppLicenseKey.objects.get(id=result.license_key.id)
    assert stored.generated_reason == "An adequate reason spread across several lines."


# --- The two catalogue writers ---------------------------------------------------------------


def test_a_control_character_is_refused_when_assigning_a_plan(caplog):
    key = _issue("assign-base").license_key
    LicensePlanAssignment.objects.filter(license_key=key).delete()

    with caplog.at_level("WARNING", logger=CS_LOGGER):
        with pytest.raises(SafeAPIError) as caught:
            set_license_plan_assignment(
                _staff(StaffPermission.GRANT_ENTITLEMENT),
                SetLicensePlanAssignmentData(
                    idempotency_key="control-assign-nul",
                    license_key_id=str(key.id),
                    plan_code="PLATINUM" + NUL,
                    reason="An adequate reason for this.",
                ),
            )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "control character" in logged, (
        f"the guard did not run; on SQLite the refusal below happens anyway. Log: {logged!r}"
    )
    assert caught.value.code == ErrorCode.NOT_FOUND
    assert not LicensePlanAssignment.objects.filter(license_key=key).exists()


@pytest.mark.parametrize("field", ["plan_code", "dimension_key"])
def test_a_control_character_is_refused_when_writing_a_plan_grant(field, caplog):
    """`dimension_key` is looked up exactly as `plan_code` is, and had the identical defect."""
    before = PlanGrant.objects.count()
    fields = {"plan_code": "PRO", "dimension_key": "screen_outputs"}
    fields[field] += NUL

    with caplog.at_level("WARNING", logger=CS_LOGGER):
        with pytest.raises(SafeAPIError) as caught:
            set_plan_grant(
                _staff(StaffPermission.GRANT_ENTITLEMENT),
                SetPlanGrantData(
                    idempotency_key=f"control-grant-{field}",
                    raw_value="7",
                    reason="An adequate reason for this.",
                    **fields,
                ),
            )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "control character" in logged, (
        f"the guard did not run; on SQLite the refusal below happens anyway. Log: {logged!r}"
    )
    assert field in logged, f"the log does not name the offending field: {logged!r}"
    assert caught.value.code == ErrorCode.NOT_FOUND
    assert PlanGrant.objects.count() == before, "a grant row was written despite the refusal"


def test_the_catalogue_writers_still_work_on_clean_input(caplog):
    """POSITIVE CONTROL for both writers — otherwise a guard that refuses everything would
    satisfy the two refusals above just as well."""
    key = _issue("clean-writers").license_key
    LicensePlanAssignment.objects.filter(license_key=key).delete()

    assigned = set_license_plan_assignment(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetLicensePlanAssignmentData(
            idempotency_key="control-assign-clean",
            license_key_id=str(key.id),
            plan_code="PLATINUM",
            reason="An adequate reason for this.",
        ),
    )
    assert assigned.assignment.plan.code == "PLATINUM"

    granted = set_plan_grant(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetPlanGrantData(
            idempotency_key="control-grant-clean",
            plan_code="PRO",
            dimension_key="screen_outputs",
            raw_value="7",
            reason="An adequate reason for this.",
        ),
    )
    assert granted.grant.raw_value == "7"
    assert not [r for r in caplog.records if "control character" in r.getMessage()], (
        "a clean write logged a control-character refusal, so the guard fires on valid input"
    )
