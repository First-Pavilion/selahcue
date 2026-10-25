"""Seeding shared by the one-device-limit tests (86ak5mn0m).

The shipped slices each build their own seeding helpers and `conftest.py` says to keep it
that way. This module is the deliberate exception, for one reason: since 86ak5mn0m a licence
issued through `generate_license_key` takes its `device_limit` from the PLAN it is issued on,
so every test that needs "a licence with N seats" now needs "a plan with N seats" first. That
is the same few lines in every one of them, and a copy in each would drift.

**The tests own their plans.** Nothing here reads the seat counts the catalogue migration
seeds (`0002`): a reseed (ClickUp 17tnw2az0gd) changes that table, and a test that leaned on
it would then fail for a reason that has nothing to do with licensing. Each plan is created
here, with the seat count the test asks for, under a code no migration uses.

Not a conftest fixture, because a fixture is invisible at the call site and what a test is
getting (which plan, how many seats) is the thing it needs to be able to read.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.models import GrantDimension, Plan, PlanGrant
from selahcue_api.apps.license_keys.services import GenerateLicenseKeyData, generate_license_key
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

# The catalogue dimension a key's seat count is read from at issuance. Named once here so a
# rename is one edit; the dimension row itself is installed by the catalogue migrations.
SEAT_DIMENSION_KEY = "device_instances"

FIXTURE_ACTOR = "test-fixture"
FIXTURE_REASON = "Test plan with its own seat count."


def staff_actor(actor_id: str = "staff_ops_1") -> ActorContext:
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id=actor_id,
        staff_permissions=frozenset(
            {StaffPermission.GENERATE_LICENSE_KEY, StaffPermission.GRANT_ENTITLEMENT}
        ),
    )


def seat_plan(code: str, device_instances) -> Plan:
    """A non-fallback plan whose `device_instances` grant is exactly `device_instances`.

    `None` creates the plan with NO grant for the dimension at all, which resolves to the
    dimension's own default (empty in the seed, so the value is absent).
    """
    plan = Plan.objects.create(
        code=code,
        display_name=f"Test plan {code}",
        is_fallback=False,
        sort_order=900,
        changed_by_actor_id=FIXTURE_ACTOR,
        reason=FIXTURE_REASON,
    )
    if device_instances is not None:
        PlanGrant.objects.create(
            plan=plan,
            dimension=GrantDimension.objects.get(key=SEAT_DIMENSION_KEY),
            raw_value=str(device_instances),
            changed_by_actor_id=FIXTURE_ACTOR,
            reason=FIXTURE_REASON,
        )
    return plan


def seat_plan_code(device_instances: int) -> str:
    """The code of a plan with exactly `device_instances` seats, creating it on first use.

    Tests that only need "a key with N seats" call this and never name a plan.
    """
    code = f"TEST-SEATS-{device_instances}"
    if not Plan.objects.filter(code=code).exists():
        seat_plan(code, device_instances)
    return code


def seed_org(tag: str) -> CustomerOrg:
    return CustomerOrg.objects.create(
        name=f"Seat Church {tag}",
        slug=f"seat-church-{tag}",
        primary_contact_email=f"ops+{tag}@seat.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        created_by_actor_id=FIXTURE_ACTOR,
        idempotency_key=f"seat-org-{tag}",
    )


def issue_key(
    customer: CustomerOrg,
    *,
    tag: str,
    plan_code: str,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    actor: ActorContext | None = None,
):
    """Issue a licence through the real service. Returns its `GenerateLicenseKeyResult`."""
    now = timezone.now().replace(microsecond=0)
    starts = starts_at or now
    return generate_license_key(
        actor or staff_actor(),
        GenerateLicenseKeyData(
            idempotency_key=f"seat-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            plan_code=plan_code,
            starts_at=starts,
            expires_at=expires_at or (starts + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            territory="NG",
            reason="Issued by the one-device-limit tests.",
        ),
    )
