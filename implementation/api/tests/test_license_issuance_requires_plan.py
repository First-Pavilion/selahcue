"""Issuance names a plan, so no NEW licence can inherit the permissive fallback (DEC-014).

`resolve_plan_for_license` tries the assignment, then a legacy scope alias, then the
designated fallback. The fallback is `LEGACY`, the MOST permissive plan in the catalogue —
unlimited screen outputs, unlimited NDI, no watermark — because its job is to freeze what
licences issued before the catalogue already had.

`feature_scope` is free staff text. So before DEC-014, a licence issued with any scope
nobody had aliased fell through to that fallback silently, was signed, and was cached
offline until expiry. This file pins the refusal.

**What DEC-014 does NOT change**, and what the last two tests here hold in place: the
fallback itself. Rows that legitimately reach it — every licence issued before the
catalogue existed — keep resolving exactly as they did. The change is a validation at the
issuance boundary, not a change to resolution.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
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
FALLBACK_PLAN_CODE = "LEGACY"
NAMED_PLAN_CODE = "PRO"

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
        device_limit=9,
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
        device_limit=3,
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


def _assert_fallback_is_the_permissive_one(tag):
    """The premise the whole ticket rests on, asserted rather than assumed."""
    fallback = Plan.objects.filter(is_fallback=True).first()
    assert fallback is not None, "no fallback plan exists; there is nothing to fall through to"
    assert fallback.code == FALLBACK_PLAN_CODE, (
        f"the fallback moved to {fallback.code!r}; these tests name {FALLBACK_PLAN_CODE!r}"
    )
    resolved = resolve_entitlement(_pre_catalogue_license(tag))
    assert resolved.degraded is False, "the premise read itself failed, so it proves nothing"
    assert resolved.plan is not None and resolved.plan.pk == fallback.pk, (
        "a scope nobody aliases no longer reaches the fallback, so these tests are not "
        "exercising the fallthrough they name"
    )
    # ABSENT and `unlimited` both read as None, and only one of them is the over-grant.
    # Assert the key is PRESENT as well, or "no ceiling" is indistinguishable from "the
    # catalogue says nothing" and this premise passes on an empty map.
    assert "screen_outputs" in resolved.values, (
        "the fallback grants no screen_outputs at all, so it is not the permissive plan "
        "DEC-014 exists to keep new licences off"
    )
    assert resolved.values["screen_outputs"] is None, (
        "the fallback no longer grants UNLIMITED screen outputs, so 'inheriting the "
        "fallback' is no longer the over-grant DEC-014 exists to stop"
    )
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
    fallback = _assert_fallback_is_the_permissive_one("premise-novel")
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


def test_issuing_on_the_designated_fallback_is_refused_and_creates_nothing():
    fallback = _assert_fallback_is_the_permissive_one("premise-sold-fallback")
    customer = _org("sold-fallback")
    before_keys = set(AppLicenseKey.objects.values_list("id", flat=True))
    before_assignments = LicensePlanAssignment.objects.count()

    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(
            _actor(), _issue_data(customer, tag="sold-fallback", plan_code=fallback.code)
        )

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value, (
        "a well-formed request naming a real plan that policy forbids is a POLICY_DENIED, "
        f"not {caught.value.extensions['code']!r} — the code is what a caller branches on"
    )
    # The ENTITY, not a proxy: no row for this customer, and no new row anywhere.
    assert not AppLicenseKey.objects.filter(customer=customer).exists(), (
        "a licence was created on the fallback plan despite the refusal"
    )
    assert set(AppLicenseKey.objects.values_list("id", flat=True)) == before_keys
    assert LicensePlanAssignment.objects.count() == before_assignments


def test_the_fallback_refusal_names_why_rather_than_only_refusing():
    """The message must say WHY, so the reason exists somewhere to be read.

    Asserted on the SERVICE, for the same reason as the missing-plan refusal above: the
    admin GraphQL view replaces every message with a canned one per error code, so this text
    does not reach a GraphQL caller — see the note in the pull request. What that caller does
    get is POLICY_DENIED rather than VALIDATION_FAILED, which is at least a different and
    more accurate hint; the full reason reaches the operator through the log, asserted below.
    """
    fallback = _assert_fallback_is_the_permissive_one("premise-fallback-msg")
    customer = _org("fallback-msg")

    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(
            _actor(), _issue_data(customer, tag="fallback-msg", plan_code=fallback.code)
        )

    message = str(caught.value)
    assert "fallback" in message.lower(), (
        f"the refusal does not say the plan is the fallback: {message!r}"
    )
    assert fallback.code in message, (
        f"the refusal does not name the plan it refused: {message!r}"
    )


def test_the_fallback_refusal_reaches_the_log_where_an_operator_will_look(caplog):
    """`SAFE_MESSAGES` discards the reason for the GraphQL caller, and this service writes
    audit rows on SUCCESS only — deliberately, and consistently with every other refusal in
    it. So the log is the only diagnosis surface a refusal has, and it has to carry the
    reason rather than just the fact."""
    fallback = _assert_fallback_is_the_permissive_one("premise-fallback-log")
    customer = _org("fallback-log")

    with caplog.at_level("WARNING", logger="selahcue_api.apps.license_keys.services"):
        with pytest.raises(SafeAPIError):
            generate_license_key(
                _actor(), _issue_data(customer, tag="fallback-log", plan_code=fallback.code)
            )

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert logged, "the refusal logged nothing at all, so it is undiagnosable in production"
    assert "is_fallback=True" in logged, (
        f"the log does not say WHY the plan was refused: {logged!r}"
    )
    assert fallback.code in logged, f"the log does not name the plan refused: {logged!r}"


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


def test_the_refusal_follows_the_is_fallback_FLAG_not_the_plan_code():
    """Which plan is the fallback is DATA (FR-544/DEC-008), so the refusal must move with
    the flag. A refusal keyed on the literal 'LEGACY' would pass every test above and still
    be the hardcoded-tier-name defect this whole app exists to avoid.

    Designating a different fallback must therefore refuse THAT plan and release the old one.
    """
    old_fallback = Plan.objects.get(is_fallback=True)
    new_fallback = Plan.objects.get(code=NAMED_PLAN_CODE)
    assert old_fallback.code != new_fallback.code

    # One fallback at a time — `uniq_catalogue_fallback_plan` is a partial unique index.
    old_fallback.is_fallback = False
    old_fallback.save(update_fields=["is_fallback"])
    new_fallback.is_fallback = True
    new_fallback.save(update_fields=["is_fallback"])

    # The newly designated fallback is now refused...
    with pytest.raises(SafeAPIError) as caught:
        generate_license_key(
            _actor(),
            _issue_data(_org("moved-refused"), tag="moved-refused", plan_code=new_fallback.code),
        )
    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value, (
        f"{new_fallback.code!r} is now the fallback but issuance still allowed it — the "
        "refusal is keyed on a hardcoded plan code, not on is_fallback"
    )

    # ...and the plan that used to be the fallback is now issuable.
    result = generate_license_key(
        _actor(),
        _issue_data(_org("moved-allowed"), tag="moved-allowed", plan_code=old_fallback.code),
    )
    assert result.created is True, (
        f"{old_fallback.code!r} is no longer the fallback but issuance still refused it"
    )


# --- What issuance now writes ----------------------------------------------------------------


def test_a_licence_issued_on_a_plan_resolves_to_that_plan_not_the_fallback():
    fallback = _assert_fallback_is_the_permissive_one("premise-named")
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
    # The entity that matters commercially: PRO's capped grants, not the fallback's unlimited.
    assert resolved.values["screen_outputs"] == 5, (
        f"expected PRO's capped screen outputs, got {resolved.values.get('screen_outputs')!r} — "
        "an unlimited value here means the fallback was inherited after all"
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
    fallback = _assert_fallback_is_the_permissive_one("premise-pre-existing")
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
    assert resolved.values["screen_outputs"] is None, "the fallback's unlimited grant changed"
    assert resolved.values["watermark"] is False, "the fallback's watermark grant changed"


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
