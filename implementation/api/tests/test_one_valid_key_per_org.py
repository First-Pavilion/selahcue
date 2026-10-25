"""At most ONE valid licence key per organisation at any moment (86ak5mn0m, AS-P8).

The owner ruled (2026-08-25) that a seat is a device instance, not a licence key: a Pro
organisation holds one key with N instance slots. Before this change nothing stopped staff
issuing a second key to the same org, and an org holding two keys had a capacity equal to the
SUM of their limits — so an org could "quietly obtain 6 slots by holding two keys".

THE RULE (architect decision, approved by the owner)
----------------------------------------------------
`generate_license_key` refuses with POLICY_DENIED, and writes NOTHING, when the same org
already holds a key whose dates overlap the new key's (start to expiry, END EXCLUDED) and whose
status is one of ISSUED, ACTIVATED, EXPIRING, EXPIRED or SUSPENDED. REVOKED, ARCHIVED and
CONVERTED keys do not block.

*   It is a rule about OVERLAPPING DATES, not "any live key", because main has no renew, revoke
    or convert writer yet: today the only way to renew is to issue a NEW key, and that key may
    start the moment the old one expires.
*   EXPIRED blocks because `state_machine.py` still allows EXPIRED -> ACTIVATED (a late
    renewal), so an expired key is not yet a dead one.
*   SUSPENDED blocks because suspension is a reversible hold (DEC-010), not an ending.
*   Existing orgs that already hold overlapping keys are GRANDFATHERED: each key keeps
    enforcing its own limit, only NEW issuance is refused. The migration test holds that part.
"""

from __future__ import annotations

from datetime import timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from licensing_test_support import issue_key, seat_plan_code, seed_org, staff_actor
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.models import LicensePlanAssignment
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.apps.license_keys import services as license_services
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.apps.license_keys.services import (
    KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY,
    lock_customer_for_key_changes,
    require_no_overlapping_license_key,
)
from selahcue_api.apps.license_keys.state_machine import LEGAL_TRANSITIONS, PRIOR_STATUS
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)
SECOND = timedelta(seconds=1)

BLOCKING = [
    LicenseKeyStatus.ISSUED,
    LicenseKeyStatus.ACTIVATED,
    LicenseKeyStatus.EXPIRING,
    LicenseKeyStatus.EXPIRED,
    LicenseKeyStatus.SUSPENDED,
]
NON_BLOCKING = [
    LicenseKeyStatus.REVOKED,
    LicenseKeyStatus.ARCHIVED,
    LicenseKeyStatus.CONVERTED,
]

assert set(BLOCKING) | set(NON_BLOCKING) == set(LicenseKeyStatus), (
    "a licence status was added and is in neither list, so the matrix below does not say "
    "whether it blocks issuance"
)


def _t0():
    return timezone.now().replace(microsecond=0)


def _existing_key(org, *, tag, status, starts_at, expires_at):
    """A key that already exists in the org, written directly so it can hold ANY status.
    A SUSPENDED row must carry the status it came from (`license_key_prior_status_iff_suspended`).
    """
    return AppLicenseKey.objects.create(
        customer=org,
        key_type=LicenseKeyType.TRIAL,
        status=status,
        prior_status=LicenseKeyStatus.ACTIVATED if status == LicenseKeyStatus.SUSPENDED else "",
        key_prefix=f"SC-TRIAL-{tag}"[:32],
        key_suffix=tag[-4:].rjust(4, "x"),
        masked_key=f"SC-TRIAL-{tag}...{tag[-4:]}"[:64],
        secret_hash="x",
        secret_fingerprint=f"one-key-fp-{tag}",
        starts_at=starts_at,
        expires_at=expires_at,
        timezone="Africa/Lagos",
        feature_scope="CHURCH",
        seat_limit=5,
        device_limit=3,
        territory="NG",
        generated_by_actor_id="staff_ops_1",
        generated_reason="A key the org already holds.",
        idempotency_key=f"one-key-existing-{tag}",
    )


def _written():
    """Everything a successful issuance writes, so a refusal can be shown to write none of it."""
    return (
        AppLicenseKey.objects.count(),
        LicensePlanAssignment.objects.count(),
        AuditEvent.objects.filter(action="license_key.generated").count(),
    )


# (label, new_starts_at offset from the existing key's start, new_expires_at offset,
#  overlaps?) — the existing key runs [0, 30d).
WINDOWS = [
    ("starts-inside-and-runs-past", 10 * DAY, 40 * DAY, True),
    ("starts-before-and-ends-inside", -10 * DAY, 10 * DAY, True),
    ("inside-the-existing-window", 5 * DAY, 10 * DAY, True),
    ("contains-the-existing-window", -5 * DAY, 35 * DAY, True),
    ("identical-window", 0 * DAY, 30 * DAY, True),
    ("starts-one-second-before-the-old-key-expires", 30 * DAY - SECOND, 60 * DAY, True),
    ("starts-exactly-when-the-old-key-expires", 30 * DAY, 60 * DAY, False),
    ("starts-after-the-old-key-expired", 31 * DAY, 60 * DAY, False),
    ("ends-exactly-when-the-old-key-starts", -30 * DAY, 0 * DAY, False),
    ("ends-one-second-after-the-old-key-starts", -30 * DAY, SECOND, True),
]


@pytest.mark.parametrize("status", BLOCKING, ids=[s.value for s in BLOCKING])
@pytest.mark.parametrize("label,start,end,overlaps", WINDOWS, ids=[w[0] for w in WINDOWS])
def test_a_blocking_key_refuses_exactly_the_overlapping_windows(
    status, label, start, end, overlaps
):
    org = seed_org(f"block-{status.value}-{label}"[:40])
    t0 = _t0()
    _existing_key(
        org, tag=f"b-{status.value}"[:20], status=status, starts_at=t0, expires_at=t0 + 30 * DAY
    )
    before = _written()

    attempt = lambda: issue_key(  # noqa: E731 - one call site, named for the assertion below
        org,
        tag=f"new-{status.value}-{label}"[:60],
        plan_code=seat_plan_code(3),
        starts_at=t0 + start,
        expires_at=t0 + end,
    )

    if overlaps:
        with pytest.raises(SafeAPIError) as caught:
            attempt()
        assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value
        # NOTHING written: no key, no plan assignment, no audit row.
        assert _written() == before, "a refused issuance left a row behind"
    else:
        result = attempt()
        assert result.created is True
        assert AppLicenseKey.objects.filter(customer=org).count() == 2


@pytest.mark.parametrize("status", NON_BLOCKING, ids=[s.value for s in NON_BLOCKING])
@pytest.mark.parametrize(
    "label,start,end",
    [(w[0], w[1], w[2]) for w in WINDOWS if w[3]],
    ids=[w[0] for w in WINDOWS if w[3]],
)
def test_a_finished_key_never_blocks_even_on_an_identical_window(status, label, start, end):
    """REVOKED, ARCHIVED and CONVERTED keys are over. The windows used are exactly the ones the
    blocking matrix REFUSES, so this is the same dates with only the status changed."""
    org = seed_org(f"free-{status.value}-{label}"[:40])
    t0 = _t0()
    _existing_key(
        org, tag=f"f-{status.value}"[:20], status=status, starts_at=t0, expires_at=t0 + 30 * DAY
    )

    result = issue_key(
        org,
        tag=f"new-{status.value}-{label}"[:60],
        plan_code=seat_plan_code(3),
        starts_at=t0 + start,
        expires_at=t0 + end,
    )

    assert result.created is True


def test_the_rule_is_about_one_org_another_orgs_key_never_blocks():
    t0 = _t0()
    other = seed_org("other-org")
    _existing_key(
        other, tag="other", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 30 * DAY
    )
    mine = seed_org("my-org")

    result = issue_key(
        mine, tag="mine", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY
    )

    assert result.created is True
    assert result.license_key.customer_id == mine.id


def test_one_org_can_renew_by_issuing_a_key_that_starts_when_the_old_one_expires():
    """The renewal flow that exists today, end to end through the real service."""
    org = seed_org("renew-by-issuing")
    t0 = _t0()
    first = issue_key(
        org, tag="renew-1", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY
    )
    second = issue_key(
        org,
        tag="renew-2",
        plan_code=seat_plan_code(3),
        starts_at=first.license_key.expires_at,
        expires_at=first.license_key.expires_at + 30 * DAY,
    )
    assert second.created is True
    assert second.license_key.pk != first.license_key.pk


def test_a_retry_of_a_successful_issuance_is_still_an_idempotent_replay():
    """The replay check runs BEFORE the overlap guard. The retried request's dates overlap the
    key it already created (it is the same key), so a guard placed first would refuse the
    retry — turning a safe replay into an error for a client that only lost the response."""
    org = seed_org("replay")
    t0 = _t0()
    first = issue_key(
        org, tag="replay", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY
    )
    assert first.created is True

    again = issue_key(
        org, tag="replay", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY
    )

    assert again.created is False
    assert again.full_key is None, "a replay must never re-show the secret"
    assert again.license_key.pk == first.license_key.pk
    assert AppLicenseKey.objects.filter(customer=org).count() == 1


def test_a_refused_request_is_not_remembered_so_a_corrected_retry_succeeds():
    """The refusal writes nothing, including the idempotency key, so the client's next attempt
    (a new window, the same idempotency key) is a fresh issuance and not a ghost replay."""
    org = seed_org("corrected")
    t0 = _t0()
    issue_key(org, tag="held", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY)

    with pytest.raises(SafeAPIError):
        issue_key(
            org, tag="corrected", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 10 * DAY
        )

    fixed = issue_key(
        org,
        tag="corrected",
        plan_code=seat_plan_code(3),
        starts_at=t0 + 30 * DAY,
        expires_at=t0 + 60 * DAY,
    )
    assert fixed.created is True


def test_grandfathered_orgs_keep_both_keys_and_only_new_issuance_is_refused():
    """An org that already holds two overlapping keys (it predates the rule) keeps both. The
    rule does not reach back and touch them; it only refuses a THIRD."""
    org = seed_org("grandfathered")
    t0 = _t0()
    first = _existing_key(
        org, tag="gf-1", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 30 * DAY
    )
    # The second key outlives the first, so the two disagree about when the org is next free.
    second = _existing_key(
        org, tag="gf-2", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 45 * DAY
    )

    with pytest.raises(SafeAPIError) as caught:
        issue_key(
            org, tag="gf-3", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY
        )

    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value
    for key in (first, second):
        key.refresh_from_db()
        assert key.status == LicenseKeyStatus.ACTIVATED
        assert key.device_limit == 3

    # The refusal's hint names the date the org is actually free from: the LATEST expiry among
    # the keys in the way. The earliest one (day 30) would send staff to a start that the other
    # key still refuses, and the hint would be wrong exactly for the grandfathered orgs.
    message = str(caught.value)
    assert (t0 + 45 * DAY).isoformat() in message, message
    # ...and following the hint works: a key starting at that date is issued.
    followed = issue_key(
        org,
        tag="gf-4",
        plan_code=seat_plan_code(3),
        starts_at=t0 + 45 * DAY,
        expires_at=t0 + 75 * DAY,
    )
    assert followed.created is True


# --- The guard is ONE function a future extend / renew writer must call ----------------------


def test_the_guard_can_exclude_the_key_being_extended():
    """An extend/renew writer asks "may THIS key now run to a later date?", and the key's own
    row overlaps itself by definition. `exclude_key_id` is that writer's way to say so; without
    it the guard would refuse every extension."""
    org = seed_org("exclude")
    t0 = _t0()
    held = _existing_key(
        org, tag="ex-1", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 30 * DAY
    )

    customer = lock_customer_for_key_changes(org.pk)
    with pytest.raises(SafeAPIError):
        require_no_overlapping_license_key(customer, starts_at=t0, expires_at=t0 + 60 * DAY)
    # Excluding the key itself, the extended window is fine.
    require_no_overlapping_license_key(
        customer, starts_at=t0, expires_at=t0 + 60 * DAY, exclude_key_id=held.pk
    )


def test_the_guard_still_sees_a_different_key_when_excluding_one():
    org = seed_org("exclude-other")
    t0 = _t0()
    held = _existing_key(
        org, tag="eo-1", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 30 * DAY
    )
    _existing_key(
        org, tag="eo-2", status=LicenseKeyStatus.ACTIVATED, starts_at=t0 + 40 * DAY,
        expires_at=t0 + 70 * DAY,
    )

    customer = lock_customer_for_key_changes(org.pk)
    with pytest.raises(SafeAPIError) as caught:
        require_no_overlapping_license_key(
            customer, starts_at=t0, expires_at=t0 + 60 * DAY, exclude_key_id=held.pk
        )
    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value


def test_issuance_by_a_different_actor_is_still_guarded():
    """The guard is per ORG, not per actor: a second staff member cannot slip a second key in."""
    org = seed_org("two-actors")
    t0 = _t0()
    issue_key(
        org, tag="actor-a", plan_code=seat_plan_code(3), starts_at=t0, expires_at=t0 + 30 * DAY,
        actor=staff_actor("staff_ops_1"),
    )
    with pytest.raises(SafeAPIError) as caught:
        issue_key(
            org, tag="actor-b", plan_code=seat_plan_code(3), starts_at=t0,
            expires_at=t0 + 30 * DAY, actor=staff_actor("staff_ops_2"),
        )
    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value


def test_the_boundary_holds_when_the_new_start_is_written_with_a_utc_offset():
    """The same instant, spelled `+01:00`. The service converts to UTC before comparing, so
    "starts when the old key expires" is allowed however the caller wrote the time and "one
    second before" is refused however the caller wrote it. The guard itself needs AWARE
    datetimes (it compares instants), which is why issuance coerces first."""
    plus_one = dt_timezone(timedelta(hours=1))
    org = seed_org("offset-boundary")
    t0 = _t0()
    _existing_key(
        org, tag="off-1", status=LicenseKeyStatus.ACTIVATED, starts_at=t0, expires_at=t0 + 30 * DAY
    )
    boundary = (t0 + 30 * DAY).astimezone(plus_one)
    assert boundary.utcoffset() == timedelta(hours=1), "premise: the value really carries +01:00"

    with pytest.raises(SafeAPIError) as caught:
        issue_key(
            org,
            tag="off-early",
            plan_code=seat_plan_code(3),
            starts_at=boundary - SECOND,
            expires_at=boundary + 30 * DAY,
        )
    assert caught.value.extensions["code"] == ErrorCode.POLICY_DENIED.value

    allowed = issue_key(
        org,
        tag="off-exact",
        plan_code=seat_plan_code(3),
        starts_at=boundary,
        expires_at=boundary + 30 * DAY,
    )
    assert allowed.created is True


# --- The org lock is held for as short a time as the rule allows -------------------------------


def _record_hash_and_lock_order(monkeypatch):
    """Wrap `make_password` and the org lock so a test can see which happened first."""
    events = []
    real_hash = license_services.make_password
    real_lock = license_services.lock_customer_for_key_changes

    def hashed(*args, **kwargs):
        events.append("hash")
        return real_hash(*args, **kwargs)

    def locked(*args, **kwargs):
        events.append("lock")
        return real_lock(*args, **kwargs)

    monkeypatch.setattr(license_services, "make_password", hashed)
    monkeypatch.setattr(license_services, "lock_customer_for_key_changes", locked)
    return events


def test_the_secret_is_hashed_before_the_org_lock_is_taken(monkeypatch):
    """`make_password` takes ~250 ms. Done after the lock, every other write for the org waits
    that long behind each issuance, so the hash comes first. The Postgres suite measures the
    lock from a second connection; this pins the ORDER on any backend."""
    events = _record_hash_and_lock_order(monkeypatch)
    org = seed_org("hash-before-lock")
    t0 = _t0()

    issue_key(
        org, tag="hash-before-lock", plan_code=seat_plan_code(3), starts_at=t0,
        expires_at=t0 + 30 * DAY,
    )

    assert events == ["hash", "lock"], events


def test_a_replay_hashes_nothing_and_takes_no_lock(monkeypatch):
    """The first replay look is the fast path: a retry of an issuance that succeeded returns
    before any secret is generated or any lock is taken. POSITIVE CONTROL: the first, real
    issuance does both, so an empty event list means the replay skipped them."""
    events = _record_hash_and_lock_order(monkeypatch)
    org = seed_org("replay-fast-path")
    t0 = _t0()
    issue_key(
        org, tag="replay-fast-path", plan_code=seat_plan_code(3), starts_at=t0,
        expires_at=t0 + 30 * DAY,
    )
    assert events == ["hash", "lock"], "premise: a real issuance hashes and locks"
    events.clear()

    again = issue_key(
        org, tag="replay-fast-path", plan_code=seat_plan_code(3), starts_at=t0,
        expires_at=t0 + 30 * DAY,
    )

    assert again.created is False
    assert events == [], events


# --- The blocking set is tied to the state machine, not to a hand-written list -----------------
#
# `KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY` says which statuses can still come back into use.
# That is a fact about the TRANSITION TABLE, so it is checked against the table: if a writer
# is ever allowed to move a key from some status back to an activatable one (CONVERTED ->
# ACTIVATED, say), that status must start blocking, and this test is what notices.


def _statuses_that_can_become_activatable(table):
    """Every status a key can be in from which an activatable status is reachable, computed from
    a transition `table` shaped like `LEGAL_TRANSITIONS`.

    Walks (status, recorded-prior) pairs rather than bare statuses, because a SUSPENDED key
    only returns to the status it was suspended FROM (`PRIOR_STATUS`). Treating "SUSPENDED can
    go back to anything suspendable" as a bare edge would make CONVERTED look revivable merely
    because a converted key can be suspended, which it cannot be revived from."""
    suspendable = {s for s, targets in table.items() if LicenseKeyStatus.SUSPENDED in targets}
    nodes = [(s, None) for s in table if s != LicenseKeyStatus.SUSPENDED]
    nodes += [(LicenseKeyStatus.SUSPENDED, prior) for prior in suspendable]

    def successors(node):
        status, prior = node
        found = set()
        for target in table[status]:
            if target is PRIOR_STATUS:
                if prior is not None:
                    found.add((prior, None))
            elif target == LicenseKeyStatus.SUSPENDED:
                found.add((LicenseKeyStatus.SUSPENDED, status))
            else:
                found.add((target, None))
        return found

    reaching = {node for node in nodes if node[0] in ACTIVATABLE_KEY_STATUSES}
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if node not in reaching and successors(node) & reaching:
                reaching.add(node)
                changed = True
    return {status for status, _prior in reaching}


def test_the_blocking_statuses_cover_every_status_the_state_machine_can_revive():
    reachable = _statuses_that_can_become_activatable(LEGAL_TRANSITIONS)

    missing = reachable - set(KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY)
    assert not missing, (
        f"the state machine lets a key in {sorted(s.value for s in missing)} become usable "
        "again, but those statuses do not block an overlapping key"
    )
    assert set(ACTIVATABLE_KEY_STATUSES) <= set(KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY)
    # POSITIVE CONTROL: the walk finds the two non-obvious members (a late renewal, and a
    # suspension that returns to an activatable status) and does NOT find CONVERTED, so the
    # subset check above is not passing on an empty set.
    assert {LicenseKeyStatus.EXPIRED, LicenseKeyStatus.SUSPENDED} <= reachable
    assert LicenseKeyStatus.CONVERTED not in reachable
    assert LicenseKeyStatus.REVOKED not in reachable


def test_the_walk_notices_a_new_edge_back_into_use():
    """The mutation record for the test above, kept as a test: add a fake CONVERTED -> ACTIVATED
    edge to a COPY of the table and the walk must report CONVERTED as revivable, which the
    production set does not cover, so the test above would go red."""
    fake = {
        **LEGAL_TRANSITIONS,
        LicenseKeyStatus.CONVERTED: LEGAL_TRANSITIONS[LicenseKeyStatus.CONVERTED]
        | {LicenseKeyStatus.ACTIVATED},
    }

    reachable = _statuses_that_can_become_activatable(fake)

    assert LicenseKeyStatus.CONVERTED in reachable
    assert reachable - set(KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY) == {LicenseKeyStatus.CONVERTED}
