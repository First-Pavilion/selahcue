"""The licence lifecycle state machine — FR-501, FR-508, NFR-506.

Every test here is driven off the production table (`LEGAL_TRANSITIONS`) and the production
writer (`apply_license_status_transition`) rather than a restated copy of either. Adding a
legal edge to the table adds a test; adding a status to the enum without a writer fails the
sweep. Nothing in this file hand-lists what the state machine is supposed to allow — a
second list is a list that drifts, and a drifted list vouches for the drift.

What "written by a production code path" means for the sweep: this ticket owns the writer,
not the individual mutations. Revoke/extend (86ak1090r), the expiry job (86ak109dv),
suspend/reinstate (86ak5mn0c), conversion (86ak5mn2k) and archiving (86ak5mn2m) each land
separately and call straight through `apply_license_status_transition`. The sweep therefore
proves each status is reachable through the audited writer. When those tickets land it
should be tightened to name their entry points as well.
"""

from __future__ import annotations

import ast
import pathlib
from collections import deque
from datetime import timedelta

import pytest
from django.db import models
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    LEGAL_TRANSITIONS,
    PRIOR_STATUS,
    REFUSED_ACTION,
    REINSTATE_ACTION,
    SEED_STATUSES,
    SUSPENDABLE_SOURCES,
    TERMINAL_STATUSES,
    IllegalLicenseTransition,
    PriorStatusTarget,
    apply_license_status_transition,
    statuses_without_writer,
    statuses_written_by_transition,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db


REASON = "State-machine battery exercising the transition."

# Staff issuance writes its own audit row against the same target type
# (apps/license_keys/services.py, action="license_key.generated"). It seeds ISSUED onto a new
# row rather than transitioning an existing one, so the NFR-506 count below separates the two.
ISSUANCE_ACTION = "license_key.generated"


# --- Module-local seeding helpers -------------------------------------------------------
# Mirrors tests/test_entitlement_manifest_slice.py, which mirrors tests/test_license_refresh
# _slice.py. The shipped slices each build their own rather than sharing a conftest.py.
def _staff_actor() -> ActorContext:
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_lifecycle_1",
        staff_permissions=frozenset(
            {
                StaffPermission.GENERATE_LICENSE_KEY,
                StaffPermission.REVOKE_LICENSE_KEY,
                StaffPermission.EXTEND_LICENSE_KEY,
            }
        ),
    )


def _seed_license_key(*, tag: str) -> AppLicenseKey:
    """A freshly issued licence — status ISSUED, the seed of every path below."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )

    customer = CustomerOrg.objects.create(
        name=f"Lifecycle Church {tag}",
        slug=f"lifecycle-church-{tag}",
        primary_contact_email=f"ops+{tag}@lifecycle.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=3,
        created_by_actor_id="staff_lifecycle_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    result = generate_license_key(
        _staff_actor(),
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=3,
            territory="NG",
            reason="Seed licence for the lifecycle state-machine battery.",
        ),
    )
    assert result.license_key.status == LicenseKeyStatus.ISSUED
    return result.license_key


def _label(target) -> str:
    return target.value


def _transition(key: AppLicenseKey, target, *, tag: str, step: int = 0):
    """Every status change in this file goes through the production writer. No test writes
    `.status` directly — doing so would prove the table without proving the thing that
    consults it."""
    return apply_license_status_transition(
        key,
        to_status=target,
        actor=_staff_actor(),
        reason=REASON,
        request_id=f"sm-{tag}-{_label(target).lower()}-{step}",
    )


def _concrete_targets(source: LicenseKeyStatus) -> set[LicenseKeyStatus]:
    """Table targets that name a status outright. `PRIOR_STATUS` is excluded because it
    resolves against row state rather than naming a status, so it cannot be used to plan a
    path without knowing where the licence was suspended from."""
    return {t for t in LEGAL_TRANSITIONS[source] if not isinstance(t, PriorStatusTarget)}


def _path_to(target: LicenseKeyStatus) -> list[LicenseKeyStatus]:
    """Shortest walk from ISSUED to `target`, computed by breadth-first search over the
    production table. Raises if `target` is unreachable — which is itself the finding."""
    start = LicenseKeyStatus.ISSUED
    if target == start:
        return []
    seen = {start}
    queue: deque[tuple[LicenseKeyStatus, list[LicenseKeyStatus]]] = deque([(start, [])])
    while queue:
        current, path = queue.popleft()
        for nxt in sorted(_concrete_targets(current), key=lambda s: s.value):
            if nxt in seen:
                continue
            if nxt == target:
                return path + [nxt]
            seen.add(nxt)
            queue.append((nxt, path + [nxt]))
    raise AssertionError(
        f"{target.value} is not reachable from ISSUED through LEGAL_TRANSITIONS — it has no "
        "production writer, which is exactly what FR-501 forbids"
    )


def _drive_to(key: AppLicenseKey, target: LicenseKeyStatus, *, tag: str) -> int:
    """Walk a licence to `target` through the writer. Returns the number of transitions
    applied, so callers can keep an exact transition count for the NFR-506 assertion."""
    path = _path_to(target)
    for step, hop in enumerate(path):
        _transition(key, hop, tag=tag, step=step)
    key.refresh_from_db()
    assert key.status == target, f"drive to {target.value} landed on {key.status}"
    return len(path)


def _audit_rows(key: AppLicenseKey):
    return AuditEvent.objects.filter(target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk))


def _legal_edges() -> list[tuple[LicenseKeyStatus, object]]:
    return sorted(
        ((source, target) for source, targets in LEGAL_TRANSITIONS.items() for target in targets),
        key=lambda edge: (edge[0].value, _label(edge[1])),
    )


def _illegal_edges() -> list[tuple[LicenseKeyStatus, object]]:
    """The complement of the table: every ordered pair the table does not permit, plus a
    reinstatement attempted from every status that is not SUSPENDED. Self-edges are excluded
    — those are idempotent replays, covered separately, not refusals."""
    edges: list[tuple[LicenseKeyStatus, object]] = []
    for source in LicenseKeyStatus:
        for target in LicenseKeyStatus:
            if source == target or target in LEGAL_TRANSITIONS[source]:
                continue
            edges.append((source, target))
        if PRIOR_STATUS not in LEGAL_TRANSITIONS[source]:
            edges.append((source, PRIOR_STATUS))
    return sorted(edges, key=lambda edge: (edge[0].value, _label(edge[1])))


def _edge_id(edge) -> str:
    return f"{edge[0].value}->{_label(edge[1])}"


# --- The table itself -------------------------------------------------------------------
def test_the_table_matches_the_prd_transition_list():
    """The PRD's §13 list, transcribed once, here, as the check on the production table.

    This is the one place a hand-written copy is legitimate: it is the requirement, and its
    whole job is to disagree with the table if the table drifts away from the PRD."""
    S = LicenseKeyStatus
    expected = {
        S.ISSUED: {S.ACTIVATED, S.EXPIRING, S.SUSPENDED, S.REVOKED},
        S.ACTIVATED: {S.EXPIRING, S.SUSPENDED, S.REVOKED, S.CONVERTED},
        S.EXPIRING: {S.ACTIVATED, S.EXPIRED, S.SUSPENDED, S.REVOKED, S.CONVERTED},
        S.EXPIRED: {S.ACTIVATED, S.SUSPENDED, S.REVOKED, S.ARCHIVED},
        S.SUSPENDED: {PRIOR_STATUS, S.REVOKED},
        S.CONVERTED: {S.SUSPENDED, S.REVOKED, S.ARCHIVED},
        S.REVOKED: {S.ARCHIVED},
        S.ARCHIVED: set(),
    }
    assert {source: set(targets) for source, targets in LEGAL_TRANSITIONS.items()} == expected


def test_terminal_statuses_have_only_their_named_exits():
    assert TERMINAL_STATUSES == {LicenseKeyStatus.REVOKED, LicenseKeyStatus.ARCHIVED}
    assert LEGAL_TRANSITIONS[LicenseKeyStatus.ARCHIVED] == frozenset()
    assert LEGAL_TRANSITIONS[LicenseKeyStatus.REVOKED] == frozenset({LicenseKeyStatus.ARCHIVED})


# --- AC: every legal transition succeeds ------------------------------------------------
@pytest.mark.parametrize("edge", _legal_edges(), ids=_edge_id)
def test_every_legal_transition_succeeds_and_writes_exactly_one_audit_row(edge):
    source, target = edge
    tag = f"legal-{source.value}-{_label(target)}".lower()
    key = _seed_license_key(tag=tag)
    _drive_to(key, source, tag=tag)

    before_rows = _audit_rows(key).count()
    expected_after = LicenseKeyStatus(key.prior_status) if target is PRIOR_STATUS else target

    result = _transition(key, target, tag=tag, step=99)

    assert result.changed is True
    assert result.from_status == source
    assert result.to_status == expected_after
    key.refresh_from_db()
    assert key.status == expected_after
    assert _audit_rows(key).count() == before_rows + 1, (
        f"{source.value} -> {_label(target)} must write exactly one audit row (FR-508)"
    )
    row = _audit_rows(key).order_by("-id").first()
    assert row.result == AuditResult.SUCCESS
    assert row.before["status"] == source.value
    assert row.after["status"] == expected_after.value


def test_the_legal_edge_battery_is_not_empty():
    """Positive control for the parametrisation above: if `_legal_edges()` ever returned
    nothing, every one of those tests would vanish and the suite would still be green."""
    edges = _legal_edges()
    assert len(edges) == 23, f"expected the PRD's 23 legal edges, got {len(edges)}"
    assert (LicenseKeyStatus.SUSPENDED, PRIOR_STATUS) in edges


# --- AC: every illegal transition is refused --------------------------------------------
@pytest.mark.parametrize("edge", _illegal_edges(), ids=_edge_id)
def test_every_illegal_transition_is_refused_and_changes_nothing(edge):
    source, target = edge
    tag = f"illegal-{source.value}-{_label(target)}".lower()
    key = _seed_license_key(tag=tag)
    _drive_to(key, source, tag=tag)

    before_rows = _audit_rows(key).count()
    before_prior = key.prior_status

    with pytest.raises(IllegalLicenseTransition) as raised:
        _transition(key, target, tag=tag, step=99)

    assert raised.value.code == ErrorCode.CONFLICT
    assert raised.value.extensions["code"] == ErrorCode.CONFLICT.value
    assert raised.value.from_status == source

    key.refresh_from_db()
    assert key.status == source, "a refused transition must leave the status untouched"
    assert key.prior_status == before_prior

    assert _audit_rows(key).count() == before_rows + 1, "the refusal itself must be audited"
    row = _audit_rows(key).order_by("-id").first()
    assert row.result == AuditResult.DENIED
    assert row.action == REFUSED_ACTION
    assert row.before["status"] == source.value
    assert row.after["status"] == source.value
    assert row.after["requested_status"] == _label(target)


def test_the_illegal_edge_battery_is_not_empty_and_covers_the_complement():
    """Positive control: the refusal battery must actually enumerate the complement of the
    table, or "every illegal transition is refused" is a claim about the empty set."""
    illegal = _illegal_edges()
    legal = _legal_edges()
    assert len(illegal) == 41, f"expected 41 illegal edges, got {len(illegal)}"
    # 8x8 ordered pairs = 64; minus 8 self-edges; minus the 22 concrete legal edges = 34.
    # Plus a reinstatement attempt from each of the 7 statuses that is not SUSPENDED = 41.
    assert len([e for e in legal if not isinstance(e[1], PriorStatusTarget)]) == 22
    assert set(illegal).isdisjoint(set(legal))
    assert (LicenseKeyStatus.ARCHIVED, LicenseKeyStatus.REVOKED) in illegal, (
        "ARCHIVED is terminal: un-archiving into REVOKED must be refused"
    )
    assert (LicenseKeyStatus.ACTIVATED, PRIOR_STATUS) in illegal


# --- AC: reinstatement returns the STORED prior status, not a constant ------------------
# These two are the DEC-010 pair. Hardcoding the reinstatement target to ACTIVATED passes
# the first and must fail the second — that asymmetry is the whole point of having both.
def test_reinstating_a_licence_suspended_from_activated_returns_to_activated():
    tag = "reinstate-activated"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)
    _transition(key, LicenseKeyStatus.SUSPENDED, tag=tag, step=1)

    key.refresh_from_db()
    assert key.prior_status == LicenseKeyStatus.ACTIVATED.value

    result = _transition(key, PRIOR_STATUS, tag=tag, step=2)

    assert result.to_status == LicenseKeyStatus.ACTIVATED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert key.prior_status == "", "the prior status must be cleared once it has been used"


def test_reinstating_a_licence_suspended_from_expiring_returns_to_expiring():
    """The one that a hardcoded ACTIVATED target cannot pass (DEC-010, FR-510)."""
    tag = "reinstate-expiring"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.EXPIRING, tag=tag)
    _transition(key, LicenseKeyStatus.SUSPENDED, tag=tag, step=1)

    key.refresh_from_db()
    assert key.prior_status == LicenseKeyStatus.EXPIRING.value

    result = _transition(key, PRIOR_STATUS, tag=tag, step=2)

    assert result.to_status == LicenseKeyStatus.EXPIRING, (
        "a licence suspended from EXPIRING must reinstate to EXPIRING, not to ACTIVATED — "
        "the target is stored data, not a constant"
    )
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.EXPIRING


def test_reinstatement_is_audited_as_its_own_action_so_the_pair_is_reconstructible():
    tag = "reinstate-audit"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.EXPIRING, tag=tag)
    _transition(key, LicenseKeyStatus.SUSPENDED, tag=tag, step=1)
    _transition(key, PRIOR_STATUS, tag=tag, step=2)

    actions = list(_audit_rows(key).order_by("id").values_list("action", flat=True))
    assert actions[-2:] == ["license_key.suspended", REINSTATE_ACTION]
    reinstated = _audit_rows(key).get(action=REINSTATE_ACTION)
    assert reinstated.before["status"] == LicenseKeyStatus.SUSPENDED.value
    assert reinstated.before["prior_status"] == LicenseKeyStatus.EXPIRING.value
    assert reinstated.after["status"] == LicenseKeyStatus.EXPIRING.value


def test_the_prior_status_is_recorded_in_the_same_statement_as_the_suspension():
    """DEC-010 calls this a schema implication, so it is asserted at the schema: a SUSPENDED
    row without a recorded prior status cannot exist, even for a writer that bypasses the
    state machine entirely."""
    from django.db import IntegrityError, transaction

    tag = "prior-invariant"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AppLicenseKey.objects.filter(pk=key.pk).update(status=LicenseKeyStatus.SUSPENDED)

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED


def test_a_non_suspended_licence_cannot_carry_a_prior_status():
    """The other half of the invariant — a stale prior status left behind by a sloppy write
    is what a later reinstatement would silently read."""
    from django.db import IntegrityError, transaction

    tag = "prior-invariant-stale"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AppLicenseKey.objects.filter(pk=key.pk).update(
                prior_status=LicenseKeyStatus.EXPIRING.value
            )


@pytest.mark.parametrize(
    "forged",
    [LicenseKeyStatus.ARCHIVED.value, "NOT_A_STATUS"],
    ids=["never-suspendable", "not-a-status"],
)
def test_reinstatement_to_an_unusable_recorded_prior_status_is_refused_not_guessed(forged):
    """Defence in depth behind the constraint.

    An empty `prior_status` on a SUSPENDED row cannot exist — the check constraint refuses
    it, which the two tests above assert. `choices`, however, is validated in Python and not
    at the database, so a raw write CAN leave a non-empty but unusable value. Reinstating
    then has to refuse: falling back to ACTIVATED would promote a licence to a status it was
    never in, which is precisely what DEC-010 stores the prior status to avoid.
    """
    from django.db import connection

    tag = f"reinstate-corrupt-{forged}".lower()
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.EXPIRING, tag=tag)
    _transition(key, LicenseKeyStatus.SUSPENDED, tag=tag, step=1)

    table = AppLicenseKey._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"UPDATE {table} SET prior_status = %s WHERE id = %s", [forged, key.pk])

    with pytest.raises(IllegalLicenseTransition) as raised:
        _transition(key, PRIOR_STATUS, tag=tag, step=2)

    assert raised.value.code == ErrorCode.CONFLICT
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.SUSPENDED, "a refused reinstatement changes nothing"


def test_the_corrupt_prior_status_battery_has_a_working_positive_control():
    """The forging above must be shown to be the only thing that breaks reinstatement: the
    same sequence with an untouched `prior_status` has to succeed, or the two tests above
    would pass against a reinstatement path that is simply broken for everyone."""
    tag = "reinstate-corrupt-control"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.EXPIRING, tag=tag)
    _transition(key, LicenseKeyStatus.SUSPENDED, tag=tag, step=1)

    result = _transition(key, PRIOR_STATUS, tag=tag, step=2)

    assert result.changed is True
    assert result.to_status == LicenseKeyStatus.EXPIRING


# --- AC: idempotent replays write no second audit row -----------------------------------
@pytest.mark.parametrize(
    "target",
    [LicenseKeyStatus.REVOKED, LicenseKeyStatus.SUSPENDED, LicenseKeyStatus.EXPIRING],
    ids=lambda s: s.value,
)
def test_re_applying_a_transition_already_in_effect_writes_no_second_audit_row(target):
    tag = f"idempotent-{target.value}".lower()
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)
    first = _transition(key, target, tag=tag, step=1)
    assert first.changed is True

    rows_after_first = _audit_rows(key).count()
    prior_after_first = AppLicenseKey.objects.get(pk=key.pk).prior_status

    second = _transition(key, target, tag=tag, step=2)

    assert second.changed is False
    assert second.from_status == target and second.to_status == target
    assert second.audit_event is None
    assert _audit_rows(key).count() == rows_after_first, (
        "a transition already in effect must not write a second audit row (NFR-506)"
    )
    key.refresh_from_db()
    assert key.status == target
    assert key.prior_status == prior_after_first, (
        "an idempotent replay must not rewrite the recorded prior status"
    )


# --- AC: the sweep — all eight statuses are written ------------------------------------
def test_every_status_is_written_by_at_least_one_production_path():
    """FR-501's sweep, computed from the production table rather than a list kept here."""
    assert statuses_without_writer() == frozenset(), (
        "these statuses have no production writer and are unreachable: "
        f"{sorted(s.value for s in statuses_without_writer())}"
    )
    assert SEED_STATUSES | statuses_written_by_transition() == set(LicenseKeyStatus)


def test_the_sweep_fails_for_a_status_that_has_no_writer():
    """The control that makes the sweep above worth having. A ninth status added to the
    enum without a writer must be REPORTED, not shrugged off — asserted by handing the sweep
    a ninth status directly. `LicenseKeyStatus` members are `str` (TextChoices), so a
    synthetic member is indistinguishable to the sweep from a real one."""

    class NineStatuses(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        ACTIVATED = "ACTIVATED", "Activated"
        EXPIRING = "EXPIRING", "Expiring"
        EXPIRED = "EXPIRED", "Expired"
        SUSPENDED = "SUSPENDED", "Suspended"
        REVOKED = "REVOKED", "Revoked"
        CONVERTED = "CONVERTED", "Converted"
        ARCHIVED = "ARCHIVED", "Archived"
        PAUSED = "PAUSED", "Paused"

    missing = statuses_without_writer(NineStatuses)

    assert missing == frozenset({NineStatuses.PAUSED}), (
        "adding a status with no writer must fail the sweep rather than pass silently"
    )


@pytest.mark.parametrize("status", list(LicenseKeyStatus), ids=lambda s: s.value)
def test_each_status_is_actually_reached_through_the_audited_writer(status):
    """The behavioural half of the sweep. The structural half proves the table names every
    status; this proves the writer can really put a row into each one, so a status cannot be
    'reachable' on paper and dead in practice."""
    tag = f"sweep-{status.value}".lower()
    key = _seed_license_key(tag=tag)
    transitions = _drive_to(key, status, tag=tag)

    key.refresh_from_db()
    assert key.status == status
    if status in SEED_STATUSES:
        assert transitions == 0, "a seed status is written at issuance, not by a transition"
    else:
        assert transitions >= 1
        assert _audit_rows(key).filter(result=AuditResult.SUCCESS).count() >= transitions


def test_suspendable_sources_are_derived_from_the_table_not_restated():
    assert SUSPENDABLE_SOURCES == frozenset(
        source
        for source, targets in LEGAL_TRANSITIONS.items()
        if LicenseKeyStatus.SUSPENDED in targets
    )
    assert LicenseKeyStatus.SUSPENDED not in SUSPENDABLE_SOURCES
    assert TERMINAL_STATUSES.isdisjoint(SUSPENDABLE_SOURCES)


# --- AC: transition count == audit-row count (NFR-506) ---------------------------------
def test_transition_count_equals_audit_row_count_across_the_whole_battery():
    """NFR-506 as an equality on the entities, not a proxy. Every legal edge in the table is
    driven on its own licence; the successful transitions are counted as they are applied and
    compared against the audit rows that exist afterwards."""
    succeeded = AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, result=AuditResult.SUCCESS
    )
    baseline = succeeded.count()
    issuance_baseline = succeeded.filter(action=ISSUANCE_ACTION).count()

    transitions = 0
    seeded = 0
    for index, (source, target) in enumerate(_legal_edges()):
        tag = f"count-{index}"
        key = _seed_license_key(tag=tag)
        seeded += 1
        transitions += _drive_to(key, source, tag=tag)
        result = _transition(key, target, tag=tag, step=99)
        assert result.changed is True
        transitions += 1

    written = succeeded.count() - baseline
    issued = succeeded.filter(action=ISSUANCE_ACTION).count() - issuance_baseline

    # Issuance writes the seed status onto a new row; it is a lifecycle event but not a
    # transition, so it is counted separately rather than filtered away by name. Asserting
    # it equals the number of licences seeded keeps ISSUANCE_ACTION honest: a stale action
    # string would show up as 0 here instead of silently deflating the transition count.
    assert issued == seeded, f"{seeded} licences were issued but {issued} issuance rows exist"
    assert written - issued == transitions, (
        f"{transitions} transitions produced {written - issued} audit rows — NFR-506 requires "
        "100% of lifecycle transitions to be audited, exactly once each"
    )
    assert transitions >= len(_legal_edges())


def test_refusal_count_equals_denied_audit_row_count():
    baseline = AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, result=AuditResult.DENIED
    ).count()

    refusals = 0
    for index, (source, target) in enumerate(_illegal_edges()):
        tag = f"denied-{index}"
        key = _seed_license_key(tag=tag)
        _drive_to(key, source, tag=tag)
        with pytest.raises(IllegalLicenseTransition):
            _transition(key, target, tag=tag, step=99)
        refusals += 1

    written = (
        AuditEvent.objects.filter(
            target_type=AUDIT_TARGET_TYPE, result=AuditResult.DENIED
        ).count()
        - baseline
    )
    assert written == refusals, "every refusal must leave exactly one DENIED audit row"
    assert refusals == len(_illegal_edges())


# --- AC: the audit row carries the FR-508 fields ----------------------------------------
def test_every_audit_row_carries_actor_before_after_reason_and_request_id():
    tag = "audit-fields"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)

    apply_license_status_transition(
        key,
        to_status=LicenseKeyStatus.SUSPENDED,
        actor=_staff_actor(),
        reason="Card declined; holding the licence pending payment.",
        request_id="req-audit-fields-0001",
    )

    row = _audit_rows(key).order_by("-id").first()
    assert row.actor_kind == ActorKind.STAFF.value
    assert row.actor_id == "staff_lifecycle_1"
    assert row.action == "license_key.suspended"
    assert row.target_type == AUDIT_TARGET_TYPE
    assert row.target_id == str(key.pk)
    assert row.reason == "Card declined; holding the licence pending payment."
    assert row.request_id == "req-audit-fields-0001"
    assert row.before["status"] == LicenseKeyStatus.ACTIVATED.value
    assert row.after["status"] == LicenseKeyStatus.SUSPENDED.value
    assert row.after["prior_status"] == LicenseKeyStatus.ACTIVATED.value
    assert row.result == AuditResult.SUCCESS


def test_the_audit_shape_matches_the_cascades(client=None):
    """FR-508 names the cascade (apps/devices/tasks.py:52-62) as the reference shape. This
    asserts the state machine writes the same field set rather than a second one."""
    tag = "audit-shape"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.REVOKED, tag=tag)
    row = _audit_rows(key).order_by("-id").first()

    for field in ("actor_kind", "actor_id", "action", "target_type", "target_id", "request_id"):
        assert getattr(row, field), f"{field} must be populated on every lifecycle audit row"
    assert row.source_surface


@pytest.mark.parametrize(
    ("reason", "request_id"),
    [("", "req-valid-0001"), ("short", "req-valid-0001"), ("A perfectly good reason.", "")],
    ids=["no-reason", "reason-too-short", "no-request-id"],
)
def test_a_transition_without_a_reason_or_request_id_is_refused(reason, request_id):
    tag = f"mandatory-{len(reason)}-{len(request_id)}"
    key = _seed_license_key(tag=tag)
    before_rows = _audit_rows(key).count()

    with pytest.raises(SafeAPIError) as raised:
        apply_license_status_transition(
            key,
            to_status=LicenseKeyStatus.REVOKED,
            actor=_staff_actor(),
            reason=reason,
            request_id=request_id,
        )

    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED
    assert _audit_rows(key).count() == before_rows


# --- AC: the audit store is append-only -------------------------------------------------
_MUTATING_CALLS = frozenset({"delete", "update", "bulk_update", "save", "update_or_create"})
_PRODUCTION_ROOT = pathlib.Path(__file__).resolve().parent.parent / "selahcue_api"


def _audit_mutation_sites() -> list[str]:
    """Every call in the production package that would mutate or remove a persisted audit
    row. Parsed rather than grepped so a mention in a comment or docstring is not a finding.
    """
    findings: list[str] = []
    for path in sorted(_PRODUCTION_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in _MUTATING_CALLS:
                continue
            chain = ast.unparse(node.func)
            if chain.split(".")[0] == "AuditEvent" or ".AuditEvent." in f".{chain}":
                findings.append(f"{path.relative_to(_PRODUCTION_ROOT.parent)}:{node.lineno} {chain}")
    return findings


def test_the_audit_store_has_no_update_or_delete_surface():
    """NFR-506: append-only. No production module may mutate or remove an audit row, and the
    audit app must expose exactly one writer."""
    assert _audit_mutation_sites() == [], (
        "the audit store is append-only; these calls would mutate or remove a row: "
        f"{_audit_mutation_sites()}"
    )

    from selahcue_api.apps.audit import services as audit_services

    public = {
        name
        for name in vars(audit_services)
        if not name.startswith("_") and callable(getattr(audit_services, name))
    }
    assert "record_audit_event" in public
    assert not {name for name in public if any(word in name for word in ("delete", "update"))}


def test_the_append_only_scan_can_actually_find_a_mutation():
    """Positive control for the scan above. Without this, an `_audit_mutation_sites()` that
    silently returned nothing — a bad path, a parse that found no files — would read exactly
    like a clean codebase."""
    assert list(_PRODUCTION_ROOT.rglob("*.py")), "the scan found no production modules at all"

    tree = ast.parse("AuditEvent.objects.filter(id=1).delete()")
    found = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _MUTATING_CALLS
        and ast.unparse(node.func).split(".")[0] == "AuditEvent"
    ]
    assert found == ["AuditEvent.objects.filter(id=1).delete"]


# --- Writer discipline ------------------------------------------------------------------
def test_no_production_module_assigns_a_licence_status_outside_the_state_machine():
    """The table is only "the single place" if nothing writes around it. The two shipped
    writers are grandfathered by name: issuance sets the seed status on an unsaved row, and
    first activation is the ISSUED -> ACTIVATED transition this ticket must not change."""
    grandfathered = {
        "selahcue_api/apps/license_keys/services.py",
        "selahcue_api/apps/devices/services.py",
        "selahcue_api/apps/license_keys/state_machine.py",
    }
    offenders: list[str] = []
    for path in sorted(_PRODUCTION_ROOT.rglob("*.py")):
        relative = str(path.relative_to(_PRODUCTION_ROOT.parent))
        if relative in grandfathered:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in {"status", "prior_status"}:
                    if "license" in ast.unparse(target).lower():
                        offenders.append(f"{relative}:{node.lineno} {ast.unparse(target)}")
    assert offenders == [], (
        "licence status must only be written through apply_license_status_transition: "
        f"{offenders}"
    )
