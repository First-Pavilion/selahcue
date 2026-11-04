"""Issuance still requires an explicit known plan; the least-ranked fallback is assignable.

The weekly catalogue replaced the old permissive legacy fallback. These tests preserve
missing/unknown-plan validation and prove explicit selection of the safe fallback works.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from django.utils import timezone

from licensing_test_support import seat_plan
from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.models import GrantDimension, LicensePlanAssignment, Plan, PlanGrant
from selahcue_api.apps.catalogue.services import resolve_entitlement, resolve_plan_for_license
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.apps.license_keys.services import (
    GenerateLicenseKeyData,
    generate_license_key,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

# The plan the fallback points at, and a non-fallback plan to issue against.
#
# The named plan is created by this file (fixture below), with its own seat count and its own
# capped screen outputs, rather than borrowed from the catalogue seed: issuing a licence takes
# its device limit from the plan (86ak5mn0m), and a reseed of the catalogue (17tnw2az0gd) must
# not be able to break a test that is about the fallback refusal. LEGACY, the fallback, IS the
# migration seed's plan: that is the point of these tests.
FALLBACK_PLAN_CODE = "FREE"
NAMED_PLAN_CODE = "TEST-NAMED-PLAN"
NAMED_PLAN_SCREEN_OUTPUTS = 4

assert FALLBACK_PLAN_CODE != NAMED_PLAN_CODE, (
    "the tests below distinguish 'resolved to the named plan' from 'fell through to the "
    "fallback' by comparing the two, which says nothing if they are the same plan"
)

# Pinned at IMPORT time, beside the thing it constrains. `plan_code` having no default is
# the entire mechanism: give it one, and every caller that forgets a plan silently gets
# that default instead of the refusal — including the tests in this file, which would then
# pass while testing nothing. `dataclasses.MISSING` is the only encoding of "no default",
# so this bites on `plan_code: str = ""` exactly as it bites on `= "LEGACY"`.
_PLAN_CODE_FIELD = next(
    field for field in dataclasses.fields(GenerateLicenseKeyData) if field.name == "plan_code"
)
assert _PLAN_CODE_FIELD.default is dataclasses.MISSING, (
    "GenerateLicenseKeyData.plan_code has acquired a default, so omitting a plan no longer "
    "reaches the DEC-014 refusal and the tests in this file are vacuous"
)
assert _PLAN_CODE_FIELD.default_factory is dataclasses.MISSING, (
    "GenerateLicenseKeyData.plan_code has acquired a default_factory — same effect"
)


@pytest.fixture(autouse=True)
def _named_plan(db):
    """The sellable plan the tests issue against: 3 seats and a CAPPED screen-output grant, so
    "resolved to this plan" is distinguishable from "fell through to the unlimited fallback"."""
    return seat_plan(
        NAMED_PLAN_CODE, 3, other_grants={"screen_outputs": str(NAMED_PLAN_SCREEN_OUTPUTS)}
    )


def _actor():
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )


def _org(tag):
    return CustomerOrg.objects.create(
        name=f"Issuance Church {tag}",
        slug=f"issuance-church-{tag}",
        primary_contact_email=f"ops+{tag}@issuance.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"issuance-org-{tag}",
    )


def _issue_data(customer, *, tag, plan_code, feature_scope="CHURCH"):
    now = timezone.now().replace(microsecond=0)
    return GenerateLicenseKeyData(
        idempotency_key=f"issuance-license-{tag}",
        customer_id=str(customer.id),
        key_type="TRIAL",
        feature_scope=feature_scope,
        plan_code=plan_code,
        starts_at=now,
        expires_at=now + timedelta(days=30),
        timezone="Africa/Lagos",
        seat_limit=5,
        territory="NG",
        reason="Pilot for the issuance-requires-a-plan tests.",
    )


def _pre_catalogue_license(tag, *, feature_scope="SCOPE-FROM-BEFORE-THE-CATALOGUE"):
    """A licence row created WITHOUT going through issuance — what every existing row is.

    Saved, deliberately. `resolve_plan_for_license` filters `LicensePlanAssignment` by this
    instance, and Django refuses an unsaved model in a related filter; `resolve_entitlement`
    would swallow that as a DEGRADED read and hand back an empty `values` map. Any premise
    check written against an unsaved row therefore passes because nothing resolved at all,
    which is the definition of a check that guards nothing.
    """
    now = timezone.now().replace(microsecond=0)
    return AppLicenseKey.objects.create(
        customer=_org(tag),
        key_type=LicenseKeyType.TRIAL,
        status=LicenseKeyStatus.ACTIVATED,
        key_prefix=f"SC-TRIAL-{tag}"[:32],
        key_suffix=tag[-4:].rjust(4, "x"),
        masked_key=f"SC-TRIAL-{tag}...{tag[-4:]}"[:64],
        secret_hash="x",
        secret_fingerprint=f"issuance-fp-{tag}",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        timezone="Africa/Lagos",
        feature_scope=feature_scope,
        seat_limit=5,
        device_limit=3,
        territory="NG",
        generated_by_actor_id="staff_ops_1",
        generated_reason="Issued before the catalogue existed.",
        idempotency_key=f"issuance-license-{tag}",
    )


def _assert_fallback_is_the_lowest_one(tag):
    fallback = Plan.objects.get(is_fallback=True)
    assert fallback.code == FALLBACK_PLAN_CODE
    assert fallback.rank == Plan.objects.order_by("rank").first().rank
    resolved = resolve_entitlement(_pre_catalogue_license("premise-" + tag))
    assert not resolved.degraded and resolved.plan.pk == fallback.pk
    assert resolved.values["screen_outputs"] == 2
    assert resolved.values["ndi_outputs"] == 0
    assert resolved.values["watermark"] is True
    return fallback


# --- The refusal ---------------------------------------------------------------------------


def test_issuing_without_a_plan_is_refused_and_creates_nothing():
    customer = _org("no-plan")
    before = set(AppLicenseKey.objects.values_list("id", flat=True))

    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(_actor(), _issue_data(customer, tag="no-plan", plan_code=""))

    assert caught.value.extensions["code"] == ErrorCode.VALIDATION_FAILED.value
    # The ENTITY, not a proxy: no row for this customer, and no new row anywhere.
    assert not AppLicenseKey.objects.filter(customer=customer).exists(), (
        "a licence was created despite the refusal"
    )
    assert set(AppLicenseKey.objects.values_list("id", flat=True)) == before
    assert not LicensePlanAssignment.objects.filter(license_key__customer=customer).exists()


def test_the_refusal_says_what_is_missing_rather_than_only_that_something_is():
    """AC: the refusal names what is missing, in language a staff user can act on.

    Asserted on the SERVICE, which is where the message survives. The admin GraphQL view
    replaces every error message with a canned one per error code
    (`graphql/errors.safe_graphql_error`), so this text does not reach a GraphQL caller —
    see the note in the pull request. Every other caller of this service does see it.
    """
    customer = _org("message")
    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(_actor(), _issue_data(customer, tag="message", plan_code="   "))

    message = str(caught.value)
    assert "plan" in message.lower(), f"the refusal does not mention a plan at all: {message!r}"
    assert "plan_code" in message, (
        f"the refusal does not name the field the caller must supply: {message!r}"
    )
    # A positive control on the message itself: prove it is not simply the canned text for
    # this code, which would name nothing and satisfy a substring check by accident.
    from selahcue_api.graphql.errors import SAFE_MESSAGES

    assert message != SAFE_MESSAGES[ErrorCode.VALIDATION_FAILED], (
        "the refusal is the generic 'the request is invalid' message, which names nothing"
    )


def test_an_unknown_plan_code_is_refused_and_creates_nothing():
    customer = _org("unknown-plan")
    assert not Plan.objects.filter(code="NO-SUCH-PLAN").exists(), "premise: this plan must not exist"

    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(
            _actor(), _issue_data(customer, tag="unknown-plan", plan_code="NO-SUCH-PLAN")
        )

    assert caught.value.extensions["code"] == ErrorCode.NOT_FOUND.value
    assert not AppLicenseKey.objects.filter(customer=customer).exists()


def test_a_novel_feature_scope_cannot_silently_reach_the_fallback():
    """The exact path Finding F1 identified: a scope nobody has aliased.

    Carries its own positive control, because "refused" proves nothing on its own — if
    issuance were broken for every input the refusal would look identical.
    """
    fallback = _assert_fallback_is_the_lowest_one("premise-novel")
    novel_scope = "SCOPE-NOBODY-HAS-ALIASED"
    from selahcue_api.apps.catalogue.models import PlanScopeAlias

    assert not PlanScopeAlias.objects.filter(feature_scope=novel_scope).exists(), (
        "premise: this scope must map to no plan, or the fallback is not what it reaches"
    )

    refused_org = _org("novel-refused")
    with pytest.raises(SafeAPIError):
        generate_license_key(
            _actor(),
            _issue_data(refused_org, tag="novel-refused", plan_code="", feature_scope=novel_scope),
        )
    assert not AppLicenseKey.objects.filter(customer=refused_org).exists()

    # POSITIVE CONTROL — the same novel scope, WITH a plan, still issues, and resolves to
    # the plan that was named rather than to the fallback.
    allowed_org = _org("novel-allowed")
    result = generate_license_key(
        _actor(),
        _issue_data(
            allowed_org, tag="novel-allowed", plan_code=NAMED_PLAN_CODE, feature_scope=novel_scope
        ),
    )
    assert result.created is True
    assert result.license_key.feature_scope == novel_scope, (
        "feature_scope is still free staff text; DEC-014 does not restrict what may be typed"
    )
    resolved_plan = resolve_plan_for_license(result.license_key)
    assert resolved_plan is not None and resolved_plan.code == NAMED_PLAN_CODE, (
        f"a licence issued on {NAMED_PLAN_CODE} resolved to {resolved_plan and resolved_plan.code!r}"
    )
    assert resolved_plan.pk != fallback.pk, "the named plan resolved to the fallback anyway"


# --- The fallback cannot be sold ON PURPOSE either -------------------------------------------
#
# The refusals above close the SILENT path onto the fallback. These close the deliberate
# one. The fallback is a no-regression bridge — display name "Legacy (pre-catalogue)" — and
# the most permissive plan in the catalogue, so a licence knowingly issued on it carries
# unlimited outputs, unlimited NDI and no watermark for its whole life, signed and cached
# offline until expiry, with no revocation list to take it back.


def test_explicit_issuance_on_the_lowest_fallback_creates_a_key_and_assignment():
    fallback = _assert_fallback_is_the_lowest_one("fallback-success")
    customer = _org("fallback-success")
    result = generate_license_key(_actor(), _issue_data(customer, tag="fallback-success", plan_code=fallback.code))
    assert result.created and result.full_key
    assert result.license_key.device_limit == 1
    assert LicensePlanAssignment.objects.get(license_key=result.license_key).plan_id == fallback.pk


def test_explicit_fallback_issuance_keeps_operator_accountability():
    fallback = _assert_fallback_is_the_lowest_one("fallback-accountable")
    customer = _org("fallback-accountable")
    data = _issue_data(customer, tag="fallback-accountable", plan_code=fallback.code)
    result = generate_license_key(_actor(), data)
    assert result.license_key.generated_by_actor_id == _actor().actor_id
    assert result.license_key.generated_reason == data.reason
    assignment = LicensePlanAssignment.objects.get(license_key=result.license_key)
    assert assignment.assigned_by_actor_id == _actor().actor_id and assignment.reason


def test_fallback_issuance_does_not_emit_obsolete_permissive_policy_warning(caplog):
    fallback = _assert_fallback_is_the_lowest_one("fallback-warning")
    with caplog.at_level("WARNING", logger="selahcue_api.apps.license_keys.services"):
        result = generate_license_key(_actor(), _issue_data(_org("fallback-warning"), tag="fallback-warning", plan_code=fallback.code))
    assert result.created
    assert not any("most permissive" in record.getMessage() for record in caplog.records)


def test_a_non_fallback_plan_still_issues(caplog):
    """POSITIVE CONTROL. Without this, a refusal that refuses EVERYTHING — or an issuance
    path broken outright — is indistinguishable from the control this file names."""
    named = Plan.objects.get(code=NAMED_PLAN_CODE)
    assert named.is_fallback is False, (
        f"premise: {NAMED_PLAN_CODE!r} is now the fallback, so this control proves nothing"
    )
    customer = _org("not-fallback")

    with caplog.at_level("WARNING", logger="selahcue_api.apps.license_keys.services"):
        result = generate_license_key(
            _actor(), _issue_data(customer, tag="not-fallback", plan_code=NAMED_PLAN_CODE)
        )

    assert result.created is True
    assert result.full_key is not None
    assignment = LicensePlanAssignment.objects.get(license_key=result.license_key)
    assert assignment.plan.code == NAMED_PLAN_CODE
    assert not caplog.records, (
        f"a healthy issuance logged a refusal warning: {[r.getMessage() for r in caplog.records]}"
    )


def test_renaming_the_fallback_does_not_reintroduce_an_issuance_refusal():
    fallback = _assert_fallback_is_the_lowest_one("fallback-rename")
    fallback.display_name = "Renamed Safe Fallback"
    fallback.save(update_fields=["display_name"])
    result = generate_license_key(_actor(), _issue_data(_org("fallback-rename"), tag="fallback-rename", plan_code=fallback.code))
    assert result.created and result.license_key.device_limit == 1


# --- What issuance now writes ----------------------------------------------------------------


def test_a_licence_issued_on_a_plan_resolves_to_that_plan_not_the_fallback():
    fallback = _assert_fallback_is_the_lowest_one("premise-named")
    customer = _org("named")
    result = generate_license_key(
        _actor(), _issue_data(customer, tag="named", plan_code=NAMED_PLAN_CODE)
    )

    assignment = LicensePlanAssignment.objects.filter(license_key=result.license_key).first()
    assert assignment is not None, "issuance did not bind the licence to a plan"
    assert assignment.plan.code == NAMED_PLAN_CODE
    # The accountability columns the database requires, carrying the ISSUING staff's identity.
    assert assignment.assigned_by_actor_id == "staff_ops_1"
    assert assignment.reason

    resolved = resolve_entitlement(result.license_key)
    assert resolved.plan is not None and resolved.plan.code == NAMED_PLAN_CODE
    assert resolved.plan.pk != fallback.pk
    # The entity that matters commercially: the named plan's capped grants, not the fallback's unlimited.
    assert resolved.values["screen_outputs"] == NAMED_PLAN_SCREEN_OUTPUTS, (
        f"expected the named plan's capped screen outputs, got "
        f"{resolved.values.get('screen_outputs')!r} — an unlimited value here means the "
        "fallback was inherited after all"
    )


def test_a_refused_issuance_leaves_no_orphan_assignment_behind():
    """The licence and its plan binding commit together, or neither does."""
    customer = _org("atomic")
    before_keys = AppLicenseKey.objects.count()
    before_assignments = LicensePlanAssignment.objects.count()

    with pytest.raises(SafeAPIError):
        generate_license_key(
            _actor(), _issue_data(customer, tag="atomic", plan_code="NO-SUCH-PLAN")
        )

    assert AppLicenseKey.objects.count() == before_keys
    assert LicensePlanAssignment.objects.count() == before_assignments


# --- What DEC-014 deliberately leaves alone ---------------------------------------------------


def test_a_licence_that_predates_this_change_still_resolves_through_the_fallback():
    """AC: no entitlement changes underneath anyone.

    A pre-catalogue row is one created WITHOUT going through issuance — which is what every
    existing row is. It carries no assignment, and its scope may match no alias. It must
    keep reaching the fallback and keep granting exactly what it granted.
    """
    fallback = _assert_fallback_is_the_lowest_one("premise-pre-existing")
    pre_existing = _pre_catalogue_license("pre-existing")
    assert not LicensePlanAssignment.objects.filter(license_key=pre_existing).exists(), (
        "premise: a pre-existing row carries no assignment, or it is not testing the fallback"
    )

    resolved_plan = resolve_plan_for_license(pre_existing)
    assert resolved_plan is not None and resolved_plan.pk == fallback.pk, (
        "a pre-existing licence stopped reaching the fallback — DEC-014 changed what an "
        "already-issued licence grants, which it must not"
    )
    resolved = resolve_entitlement(pre_existing)
    assert "screen_outputs" in resolved.values, "the fallback stopped granting screen outputs"
    assert resolved.values["screen_outputs"] == 2, "the fallback must remain restrictive"
    assert resolved.values["watermark"] is True, "the fallback keeps the Free watermark"


def test_the_fallback_mechanism_itself_is_untouched():
    """AC: this ticket does not delete `is_fallback` or change `resolve_plan_for_license`."""
    fallback = Plan.objects.filter(is_fallback=True).first()
    assert fallback is not None, "the fallback plan was removed"
    assert fallback.code == FALLBACK_PLAN_CODE
    # A saved row with no assignment and a scope matching no alias exercises the
    # fallthrough arm and nothing else. Saved, for the reason in `_pre_catalogue_license`:
    # an unsaved instance makes the assignment lookup raise, and the fallthrough would
    # never be reached at all.
    untouched = _pre_catalogue_license("untouched", feature_scope="STILL-NOT-ALIASED")
    assert not LicensePlanAssignment.objects.filter(license_key=untouched).exists()
    assert resolve_plan_for_license(untouched).pk == fallback.pk
