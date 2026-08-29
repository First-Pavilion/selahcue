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
from selahcue_api.apps.license_keys import state_machine
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.state_machine import (
    ACTION_MAX_LENGTH,
    AUDIT_TARGET_TYPE,
    SOURCE_SURFACE_MAX_LENGTH,
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
            # DEC-014 made the catalogue plan part of issuing a licence, and now refuses the
            # designated fallback outright — so this names a sellable plan rather than the
            # pre-catalogue one. The lifecycle is what these tests exercise, and the plan
            # changes nothing any of them assert.
            plan_code="PRO",
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
# The PRD's §13 clauses, transcribed LITERALLY — every edge the exhaustive list grants when
# read word for word, including the one this implementation refuses. Transcribing the
# already-resolved table instead would agree with `LEGAL_TRANSITIONS` by construction and
# could never surface where the code departs from the requirement.
def _prd_literal_transitions() -> dict[LicenseKeyStatus, set]:
    S = LicenseKeyStatus
    literal: dict[S, set] = {status: set() for status in S}
    terminal = {S.REVOKED, S.ARCHIVED}

    literal[S.ISSUED].add(S.ACTIVATED)  # "ISSUED->ACTIVATED (first activation)"
    literal[S.ISSUED].add(S.EXPIRING)  # "ISSUED/ACTIVATED->EXPIRING (clock, FR-502)"
    literal[S.ACTIVATED].add(S.EXPIRING)
    literal[S.EXPIRING].add(S.ACTIVATED)  # "EXPIRING->ACTIVATED (renewal, FR-509)"
    literal[S.EXPIRING].add(S.EXPIRED)  # "EXPIRING->EXPIRED (clock, FR-503)"
    literal[S.EXPIRED].add(S.ACTIVATED)  # "EXPIRED->ACTIVATED (late renewal, FR-509)"
    # "any non-terminal->SUSPENDED (FR-504)" — self-edges are replays, not transitions.
    for status in set(S) - terminal - {S.SUSPENDED}:
        literal[status].add(S.SUSPENDED)
    literal[S.SUSPENDED].add(PRIOR_STATUS)  # "SUSPENDED->its prior status (FR-510)"
    # "any->REVOKED (FR-505)" — read literally, "any" includes ARCHIVED.
    for status in set(S) - {S.REVOKED}:
        literal[status].add(S.REVOKED)
    literal[S.ACTIVATED].add(S.CONVERTED)  # "ACTIVATED/EXPIRING->CONVERTED (FR-506, D1)"
    literal[S.EXPIRING].add(S.CONVERTED)
    for status in (S.EXPIRED, S.REVOKED, S.CONVERTED):  # "EXPIRED/REVOKED/CONVERTED->ARCHIVED"
        literal[status].add(S.ARCHIVED)
    return literal


# The single, named departure from the literal reading. §13 also says "REVOKED and ARCHIVED
# are otherwise terminal", and FR-505's own acceptance criterion says "no mutation can leave
# REVOKED except ARCHIVED" — which is the requirements author expressing terminality as a
# by-name bound on a terminal status's OUTBOUND edges. Granting ARCHIVED an outbound edge in
# the same breath as calling it terminal contradicts that, and ARCHIVED is never named as a
# source anywhere in §13. Recorded as a footnote on PRD §13.
DOCUMENTED_DEPARTURES: dict[tuple, str] = {
    (LicenseKeyStatus.ARCHIVED, LicenseKeyStatus.REVOKED): (
        "ARCHIVED is terminal (§13 + FR-505 AC), so the literal 'any->REVOKED' does not "
        "reach it — un-archiving a licence into a kill state is not a lifecycle §13 describes"
    ),
}


def test_the_table_matches_the_prd_transition_list_except_where_documented():
    expected = {status: set(targets) for status, targets in _prd_literal_transitions().items()}
    for (source, target), why in DOCUMENTED_DEPARTURES.items():
        assert target in expected[source], (
            f"{source.value}->{target.value} is recorded as a departure from §13 but the "
            f"literal transcription does not grant it — the departure is stale ({why})"
        )
        expected[source].discard(target)

    actual = {source: set(targets) for source, targets in LEGAL_TRANSITIONS.items()}
    assert actual == expected


def test_the_only_departure_from_the_prd_is_the_documented_one():
    """Guards the list of exceptions itself: adding a second departure without recording it
    has to fail here, not pass because the test subtracted whatever disagreed."""
    literal = _prd_literal_transitions()
    departures = {
        (source, target)
        for source, targets in literal.items()
        for target in targets
        if target not in LEGAL_TRANSITIONS[source]
    }
    additions = {
        (source, target)
        for source, targets in LEGAL_TRANSITIONS.items()
        for target in targets
        if target not in literal[source]
    }
    assert departures == set(DOCUMENTED_DEPARTURES), (
        f"undocumented refusals of edges §13 grants: {sorted(departures - set(DOCUMENTED_DEPARTURES))}"
    )
    assert additions == set(), f"the table grants edges §13 does not: {sorted(additions)}"


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
    # AC6 applies to DENIED rows too. Without these, blanking reason and request_id on the
    # refusal path left the entire battery green — a refusal nobody can attribute is not an
    # audit record.
    assert row.actor_kind == ActorKind.STAFF.value
    assert row.actor_id == "staff_lifecycle_1"
    assert row.reason == REASON
    assert row.request_id == f"sm-{tag}-{_label(target).lower()}-99"
    assert row.after["refusal_code"], "a refusal must say WHY, machine-readably"
    assert row.after["refusal_detail"]
    assert row.before["prior_status"] == before_prior


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


def test_suspendable_sources_match_the_prd_not_the_production_comprehension():
    """Derived independently, from the literal §13 transcription.

    Re-running the production comprehension against the production table proves only that the
    comprehension is deterministic: a hand-restated literal in `SUSPENDABLE_SOURCES` would
    survive it. §13 says "any non-terminal -> SUSPENDED", and names REVOKED and ARCHIVED as
    the terminal pair, so the expected set follows from the requirement rather than the code.
    """
    non_terminal = {
        status
        for status in LicenseKeyStatus
        if status not in {LicenseKeyStatus.REVOKED, LicenseKeyStatus.ARCHIVED}
    }
    # SUSPENDED -> SUSPENDED is a self-edge: an idempotent replay, not a transition.
    expected = non_terminal - {LicenseKeyStatus.SUSPENDED}

    assert set(SUSPENDABLE_SOURCES) == expected
    # And a second, independent traversal of the table agrees with it.
    assert set(SUSPENDABLE_SOURCES) == {
        source for source, target in _legal_edges() if target is LicenseKeyStatus.SUSPENDED
    }
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


def _audit_mutation_sites(root: pathlib.Path | None = None) -> list[str]:
    """Every call in the production package that would mutate or remove a persisted audit row.

    Parsed rather than grepped, so a mention in a comment or docstring is not a finding. The
    scan follows local aliases — `qs = AuditEvent.objects.filter(...)` then `qs.delete()` is
    the natural shape of a retention job, and matching only on the literal `AuditEvent.` chain
    walks straight past it.

    `root` is a parameter so the scan can be pointed at a fixture containing a known offender
    and shown to find it. A scan that can only ever be run against a clean tree is
    indistinguishable from a scan that returns nothing at all.
    """
    root = root or _PRODUCTION_ROOT
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        relative = path.relative_to(root.parent)

        # Names bound to an AuditEvent-rooted expression anywhere in the module.
        aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and node.value is not None:
                value = ast.unparse(node.value)
                if value.split(".")[0] == "AuditEvent":
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            aliases.add(target.id)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in _MUTATING_CALLS:
                continue
            chain = ast.unparse(node.func)
            root_name = chain.split(".")[0]
            if root_name == "AuditEvent" or root_name in aliases or ".AuditEvent." in f".{chain}":
                findings.append(f"{relative}:{node.lineno} {chain}")
    return findings


def test_the_audit_store_has_no_update_or_delete_surface():
    """NFR-506: append-only. No production module may mutate or remove an audit row, and the
    audit app must expose exactly one writer."""
    sites = _audit_mutation_sites()
    assert sites == [], (
        f"the audit store is append-only; these calls would mutate or remove a row: {sites}"
    )

    from selahcue_api.apps.audit import services as audit_services

    public = {
        name
        for name in vars(audit_services)
        if not name.startswith("_") and callable(getattr(audit_services, name))
    }
    assert "record_audit_event" in public
    assert not {name for name in public if any(word in name for word in ("delete", "update"))}


@pytest.mark.parametrize(
    ("shape", "source"),
    [
        ("direct-delete", "AuditEvent.objects.filter(id=1).delete()\n"),
        ("direct-update", "AuditEvent.objects.all().update(reason='')\n"),
        # The retention-job shape, which evaded the first version of this scan entirely.
        ("aliased-delete", "qs = AuditEvent.objects.filter(id=1)\nqs.delete()\n"),
        ("aliased-update", "rows = AuditEvent.objects.all()\nrows.update(reason='')\n"),
    ],
)
def test_the_append_only_scan_actually_finds_a_mutation(tmp_path, shape, source):
    """Positive control that calls the real function.

    The previous version of this control re-implemented the walk inline against a literal
    string, so `_audit_mutation_sites()` could have returned `[]` unconditionally — a bad
    root, a glob that matched nothing — and both it and the test above would still pass. This
    points the actual function at a fixture tree and requires it to report.
    """
    package = tmp_path / "selahcue_api"
    package.mkdir()
    (package / "offender.py").write_text(source)

    findings = _audit_mutation_sites(package)

    assert findings, f"the {shape} mutation shape is invisible to the append-only scan"
    assert all("offender.py" in finding for finding in findings), findings


def test_the_append_only_scan_reads_the_real_production_tree():
    """The other half: the clean result above must come from a scan that really looked."""
    modules = list(_PRODUCTION_ROOT.rglob("*.py"))
    assert len(modules) > 20, f"the scan only found {len(modules)} production modules"
    assert any(path.name == "services.py" for path in modules)


# --- Writer discipline ------------------------------------------------------------------
# The table is only "the single place" if nothing writes around it. Grandfathering is BY
# SITE, never by file: excusing a whole module would excuse the new direct write that
# 86ak1090r (revoke/extend, landing in license_keys/services.py) or 86ak109dv (the expiry
# job, whose natural shape is `AppLicenseKey.objects.filter(...).update(status=...)`) might
# add next to the old one.
_STATUS_FIELDS = frozenset({"status", "prior_status"})
_QUERYSET_WRITERS = frozenset(
    {"update", "create", "update_or_create", "get_or_create", "bulk_create", "bulk_update"}
)

# `state_machine.py` is the writer itself — the module this rule is *about* — so its internal
# writes are the sanctioned ones by definition. Every other module is pinned site by site.
_THE_WRITER = "selahcue_api/apps/license_keys/state_machine.py"

# The two writes that predate this module, named individually. A third anywhere fails.
_KNOWN_DIRECT_WRITES = {
    # Staff issuance seeds ISSUED onto a new, unsaved row (apps/license_keys/services.py).
    # Not a transition — there is no prior status to move from.
    ("selahcue_api/apps/license_keys/services.py", "construct", "AppLicenseKey(status=...)"),
    # First activation flips ISSUED -> ACTIVATED inline and audits it as target_type="device".
    # The one real bypass of the state machine; tracked as 86ak5v7av, deliberately not changed
    # by this ticket. If it is ever routed through the writer, DELETE this entry — do not
    # leave it behind, or the slot stays open for a new bypass.
    ("selahcue_api/apps/devices/services.py", "assign", "license_key.status"),
}


def _licence_status_write_sites(root: pathlib.Path | None = None) -> set[tuple[str, str, str]]:
    """Every place outside the state machine that writes a licence status.

    Three layers, because a pure AST scan cannot resolve types and pretending otherwise
    would be the weaker claim:

    * exact — any constructor or queryset write rooted at the `AppLicenseKey` name, with a
      status keyword. This is the `.objects.filter(...).update(status=...)` shape.
    * exact — any assignment to `.prior_status`. That field name exists nowhere else in the
      codebase, so the attribute alone identifies a licence.
    * scoped — any assignment to `.status` in a module that mentions `AppLicenseKey`, which
      catches `lk.status`, `key.status` and `row.status` without guessing from the name.
    """
    root = root or _PRODUCTION_ROOT
    sites: set[tuple[str, str, str]] = set()
    for path in sorted(root.rglob("*.py")):
        relative = str(path.relative_to(root.parent))
        if relative == _THE_WRITER:
            continue
        source = path.read_text()
        mentions_licence = "AppLicenseKey" in source
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if not isinstance(target, ast.Attribute) or target.attr not in _STATUS_FIELDS:
                    continue
                if target.attr == "prior_status" or mentions_licence:
                    sites.add((relative, "assign", ast.unparse(target)))

            if not isinstance(node, ast.Call):
                continue
            written = sorted({kw.arg for kw in node.keywords if kw.arg in _STATUS_FIELDS})
            if not written:
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "AppLicenseKey":
                sites.add((relative, "construct", "AppLicenseKey(status=...)"))
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _QUERYSET_WRITERS
                and ast.unparse(node.func).split(".")[0] == "AppLicenseKey"
            ):
                sites.add((relative, "queryset", f"{ast.unparse(node.func)}({written})"))
    return sites


def test_no_production_module_writes_a_licence_status_outside_the_state_machine():
    found = _licence_status_write_sites()
    assert found == _KNOWN_DIRECT_WRITES, (
        "licence status must only be written through apply_license_status_transition.\n"
        f"  unexpected: {sorted(found - _KNOWN_DIRECT_WRITES)}\n"
        f"  expected but gone (delete the entry if intentional): "
        f"{sorted(_KNOWN_DIRECT_WRITES - found)}"
    )


@pytest.mark.parametrize(
    ("shape", "source"),
    [
        ("queryset-update", "AppLicenseKey.objects.filter(pk=1).update(status='REVOKED')\n"),
        ("queryset-create", "AppLicenseKey.objects.create(status='ISSUED')\n"),
        ("constructor", "row = AppLicenseKey(status='ISSUED')\n"),
        ("aliased-assign", "lk = AppLicenseKey.objects.get(pk=1)\nlk.status = 'REVOKED'\n"),
        ("short-name-assign", "row = AppLicenseKey.objects.get(pk=1)\nrow.status = 'REVOKED'\n"),
        ("prior-status-assign", "obj.prior_status = 'ACTIVATED'\n"),
    ],
)
def test_the_writer_discipline_scan_catches_every_bypass_shape(tmp_path, shape, source):
    """The control that makes the test above worth having.

    Each of these survived the first version of the scan, which looked only at assignments
    whose unparsed text contained the substring "license". The queryset shape is the one that
    matters most: it is an `ast.Call` with no assignment node anywhere, and it is exactly how
    86ak109dv's expiry job will want to be written.
    """
    package = tmp_path / "selahcue_api"
    package.mkdir()
    (package / "offender.py").write_text(source)

    found = _licence_status_write_sites(package)

    assert found, f"the {shape} bypass shape is invisible to the scan"
    assert all(site[0].endswith("offender.py") for site in found), found


def test_the_writer_discipline_scan_does_not_flag_unrelated_status_writes(tmp_path):
    """Negative control: a device status write in a module that never mentions a licence is
    not this test's business, and flagging it would make the guard unusable for the tickets
    working on devices."""
    package = tmp_path / "selahcue_api"
    package.mkdir()
    (package / "devices_only.py").write_text(
        "token = DeviceToken.objects.get(pk=1)\ntoken.status = 'REVOKED'\n"
    )

    assert _licence_status_write_sites(package) == set()


# --- The refusal-durability trade-off, pinned -------------------------------------------
# `apply_license_status_transition` writes its DENIED row AFTER its own `atomic()` block
# unwinds, so the row commits on its own in the case that matters. These two tests pin both
# halves of the resulting asymmetry, including the half that LOSES the row. That is the
# accepted behaviour, not a bug — but it is accepted only as long as case [A] keeps working,
# and nothing else in the suite would notice if a later tidy-up moved `record_audit_event`
# back inside the transaction. Such a change passes every other test here while making the
# loss strictly worse: case [A] would start losing denials too.
#
# `transaction=True` is load-bearing. Under the default `django_db` every test already runs
# inside an outer atomic block, so case [A] — a caller in autocommit — is not reachable and
# both tests would measure case [B].
@pytest.mark.django_db(transaction=True)
def test_a_refusal_in_autocommit_leaves_a_durable_denial_row():
    """Case [A] — the one production actually takes.

    The project does not set `ATOMIC_REQUESTS`, so a top-level GraphQL resolver is in
    autocommit and the denial survives.
    """
    from django.db import connection

    tag = "durable-autocommit"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ARCHIVED, tag=tag)
    before_denied = _audit_rows(key).filter(result=AuditResult.DENIED).count()

    assert not connection.in_atomic_block, "case [A] requires the caller to be in autocommit"
    with pytest.raises(IllegalLicenseTransition):
        _transition(key, LicenseKeyStatus.REVOKED, tag=tag, step=1)

    assert _audit_rows(key).filter(result=AuditResult.DENIED).count() == before_denied + 1, (
        "a refusal raised to a caller in autocommit must leave a durable DENIED row"
    )


@pytest.mark.django_db(transaction=True)
def test_a_refusal_inside_a_callers_transaction_is_lost_when_the_error_propagates():
    """Case [B] — the ACCEPTED loss, asserted so it cannot get quietly worse.

    A caller that wraps the transition in its own `atomic()` and lets the error propagate
    rolls the denial back with everything else. On one database connection there is no way to
    make a write survive its enclosing rollback, so this is a trade-off rather than an
    oversight, and the asymmetry is coherent: a SUCCESS row *must* roll back with the
    transition it describes, and only a refusal can outlive its transaction because a refusal
    changes nothing.

    `transaction.atomic(durable=True)` is not the escape it appears to be — it raises when
    nested, which would forbid FR-506's conversion flow from wrapping a transition at all.

    If a flow ever needs BOTH a durable denial and a wider atomic block, the agreed answer is
    a separate `audit` database alias used for DENIED rows only, never for SUCCESS rows.
    """
    from django.db import transaction as db_transaction

    tag = "durable-wrapped"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ARCHIVED, tag=tag)
    before_denied = _audit_rows(key).filter(result=AuditResult.DENIED).count()

    with pytest.raises(IllegalLicenseTransition):
        with db_transaction.atomic():
            _transition(key, LicenseKeyStatus.REVOKED, tag=tag, step=1)

    assert _audit_rows(key).filter(result=AuditResult.DENIED).count() == before_denied, (
        "expected the accepted loss: a denial raised out of a caller's transaction is rolled "
        "back with it. If this now finds a row, the trade-off has changed and the module "
        "docstring's calling contract needs rewriting"
    )
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ARCHIVED, "the refused transition still changed nothing"


@pytest.mark.django_db(transaction=True)
def test_a_caller_that_catches_the_refusal_inside_its_transaction_keeps_the_row():
    """Case [C] — the escape hatch available today, so callers that need both know what to do:
    catch `IllegalLicenseTransition` inside the block and commit, rather than letting it
    unwind the transaction."""
    from django.db import transaction as db_transaction

    tag = "durable-caught"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ARCHIVED, tag=tag)
    before_denied = _audit_rows(key).filter(result=AuditResult.DENIED).count()

    with db_transaction.atomic():
        with pytest.raises(IllegalLicenseTransition):
            _transition(key, LicenseKeyStatus.REVOKED, tag=tag, step=1)

    assert _audit_rows(key).filter(result=AuditResult.DENIED).count() == before_denied + 1


# --- The audit payload is the writer's to own, not the caller's -------------------------
def test_caller_supplied_extras_cannot_overwrite_the_mandated_audit_fields():
    """`extra_before`/`extra_after` exist so the mutation tickets can add context — the new
    `expires_at` on a renewal, the successor key on a conversion — without inventing a second
    audit shape. They must not be able to reach the FR-508 fields.

    The spread used to come last, so a caller passing `status` silently replaced the
    authoritative value and the row described a transition that never happened. Five
    downstream tickets call this function.
    """
    tag = "extras-precedence"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ACTIVATED, tag=tag)

    apply_license_status_transition(
        key,
        to_status=LicenseKeyStatus.SUSPENDED,
        actor=_staff_actor(),
        reason="Suspending while the caller lies about the payload.",
        request_id="req-extras-precedence",
        extra_before={"status": "NONSENSE", "prior_status": "NONSENSE", "note": "kept"},
        extra_after={"status": "NONSENSE", "prior_status": "NONSENSE", "note": "kept"},
    )

    row = _audit_rows(key).order_by("-id").first()
    assert row.before["status"] == LicenseKeyStatus.ACTIVATED.value
    assert row.after["status"] == LicenseKeyStatus.SUSPENDED.value
    assert row.after["prior_status"] == LicenseKeyStatus.ACTIVATED.value
    # The caller's own, non-conflicting context still lands — the point is precedence, not
    # refusing extras outright.
    assert row.before["note"] == "kept"
    assert row.after["note"] == "kept"


def test_an_over_long_caller_action_is_refused_at_the_boundary():
    """`AuditEvent.action` is bounded. Unchecked, an over-long action truncates silently on
    SQLite and raises inside the transaction on Postgres — after the status row is written but
    before the audit row lands, which is the one outcome NFR-506 exists to prevent."""
    tag = "action-too-long"
    key = _seed_license_key(tag=tag)
    before_rows = _audit_rows(key).count()

    with pytest.raises(SafeAPIError) as raised:
        apply_license_status_transition(
            key,
            to_status=LicenseKeyStatus.REVOKED,
            actor=_staff_actor(),
            reason="An action name far beyond the column width.",
            request_id="req-action-too-long",
            action="x" * (ACTION_MAX_LENGTH + 1),
        )

    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED, "nothing may move when the action is invalid"
    assert _audit_rows(key).count() == before_rows

    # Positive control: the same call with an action that fits succeeds, so the refusal above
    # is the length check biting rather than the action parameter being broken outright.
    result = apply_license_status_transition(
        key,
        to_status=LicenseKeyStatus.REVOKED,
        actor=_staff_actor(),
        reason="An action name that fits the column.",
        request_id="req-action-ok",
        action="x" * ACTION_MAX_LENGTH,
    )
    assert result.changed is True
    assert _audit_rows(key).order_by("-id").first().action == "x" * ACTION_MAX_LENGTH


# --- The import-time table premises ------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "broken"),
    [
        (
            "terminality-widened",
            {**LEGAL_TRANSITIONS, LicenseKeyStatus.ARCHIVED: frozenset({LicenseKeyStatus.ACTIVATED})},
        ),
        (
            "revoked-escapes",
            {**LEGAL_TRANSITIONS, LicenseKeyStatus.REVOKED: frozenset({LicenseKeyStatus.ISSUED})},
        ),
        (
            "status-missing-from-table",
            {k: v for k, v in LEGAL_TRANSITIONS.items() if k is not LicenseKeyStatus.CONVERTED},
        ),
    ],
)
def test_the_table_validator_rejects_a_drifted_table(monkeypatch, label, broken):
    """`_validate_table()` runs at import, so a drifted table takes the whole suite down with
    it. That is the right blast radius, but it makes the guard awkward to assert — a
    collection error from this firing correctly looks exactly like a collection error from a
    typo. Calling it directly against a deliberately-drifted table pins the behaviour instead
    of leaving it to be inferred from a stack trace.

    It must RAISE rather than assert: `python -O` strips assertions, and these premises are
    load-bearing.
    """
    monkeypatch.setattr(state_machine, "LEGAL_TRANSITIONS", broken)

    with pytest.raises(RuntimeError):
        state_machine._validate_table()


def test_the_table_validator_passes_on_the_real_table():
    """Positive control: the rejections above must come from the drift, not from a validator
    that raises unconditionally."""
    state_machine._validate_table()


# --- source_surface is caller-supplied and bounded, exactly like action ------------------
def test_an_over_long_source_surface_is_refused_at_the_boundary():
    """`AuditEvent.source_surface` is `max_length=64` and arrives from the caller, so it needs
    the same boundary check `action` gets.

    Unvalidated it is worse than `action` on the refusal path: the over-length value reaches
    `record_audit_event` INSIDE the except block, so on Postgres the DENIED row is lost and
    the caller receives a raw `django.db.utils.DataError` instead of the safe
    `IllegalLicenseTransition` envelope. On SQLite it is stored over-length instead, silently
    corrupting the column the audit trail is queried by. Five downstream tickets are about to
    start passing this parameter.
    """
    tag = "surface-too-long"
    key = _seed_license_key(tag=tag)
    before_rows = _audit_rows(key).count()

    with pytest.raises(SafeAPIError) as raised:
        apply_license_status_transition(
            key,
            to_status=LicenseKeyStatus.REVOKED,
            actor=_staff_actor(),
            reason="A surface name beyond the column width.",
            request_id="req-surface-too-long",
            source_surface="s" * (SOURCE_SURFACE_MAX_LENGTH + 1),
        )

    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED, "nothing may move when the surface is invalid"
    assert _audit_rows(key).count() == before_rows

    # Positive control: a surface that fits succeeds and is stored verbatim, so the refusal
    # above is the bound biting rather than the parameter being broken outright.
    result = apply_license_status_transition(
        key,
        to_status=LicenseKeyStatus.REVOKED,
        actor=_staff_actor(),
        reason="A surface name that fits the column.",
        request_id="req-surface-ok",
        source_surface="s" * SOURCE_SURFACE_MAX_LENGTH,
    )
    assert result.changed is True
    stored = _audit_rows(key).order_by("-id").first().source_surface
    assert stored == "s" * SOURCE_SURFACE_MAX_LENGTH, (
        f"source_surface was stored as {len(stored)} chars — the column was not respected"
    )


def test_an_over_long_source_surface_on_the_REFUSAL_path_keeps_the_safe_envelope():
    """The severe half, asserted separately.

    The refusal path writes its audit row inside the `except` block, so before validation an
    over-length surface turned a clean CONFLICT into an unhandled driver error AND destroyed
    the DENIED row — losing the compliance record this whole ticket exists to guarantee.
    """
    tag = "surface-too-long-refusal"
    key = _seed_license_key(tag=tag)
    _drive_to(key, LicenseKeyStatus.ARCHIVED, tag=tag)
    before_denied = _audit_rows(key).filter(result=AuditResult.DENIED).count()

    # ARCHIVED -> REVOKED is illegal, so this would take the refusal path if it got that far.
    with pytest.raises(SafeAPIError) as raised:
        apply_license_status_transition(
            key,
            to_status=LicenseKeyStatus.REVOKED,
            actor=_staff_actor(),
            reason="Refusing with an over-long surface name.",
            request_id="req-surface-refusal",
            source_surface="s" * (SOURCE_SURFACE_MAX_LENGTH + 1),
        )

    # Rejected at the boundary, so it never reaches the refusal path at all.
    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    assert not isinstance(raised.value, IllegalLicenseTransition)
    assert _audit_rows(key).filter(result=AuditResult.DENIED).count() == before_denied

    # Positive control: the same illegal transition with a valid surface still produces the
    # coded refusal and its durable DENIED row.
    with pytest.raises(IllegalLicenseTransition):
        apply_license_status_transition(
            key,
            to_status=LicenseKeyStatus.REVOKED,
            actor=_staff_actor(),
            reason="Refusing with a valid surface name.",
            request_id="req-surface-refusal-ok",
            source_surface="admin_graphql",
        )
    assert _audit_rows(key).filter(result=AuditResult.DENIED).count() == before_denied + 1


# --- Authorisation is the caller's job, and that has to be findable ---------------------
@pytest.mark.parametrize(
    "actor",
    [
        ActorContext(kind=ActorKind.CUSTOMER, actor_id="cust_1", org_id="org_1", role="MEMBER"),
        ActorContext(kind=ActorKind.DEVICE, actor_id="device_1"),
        ActorContext(kind=ActorKind.SERVICE, actor_id="expiry-sweep"),
        ActorContext(kind=ActorKind.STAFF, actor_id="staff_no_perms"),
    ],
    ids=["customer", "device", "service", "staff-with-no-permissions"],
)
def test_the_writer_performs_no_authorisation_by_design(actor):
    """Pins the architectural seam, so it cannot move without someone noticing.

    This is NOT an assertion that unauthorised licence changes are acceptable. It records
    that gating lives in the service layer above this function, because callers are not all
    staff — the expiry job runs on its own authority and FR-537 requires billing webhooks to
    write "only through the FR-501 writers", so a hardcoded `require_staff_permission` here
    would lock those paths out.

    The consequence is that every staff-facing caller MUST gate before calling, and must
    carry its own test that an unauthorised actor gets `PERMISSION_DENIED` with no transition
    (PRD §19: "§15 actor gating + FR-508 audit" — this module is only the audit half).

    If someone later adds authorisation inside the writer, this test fails — which is the
    intended prompt to move it to the right layer, or to update the module contract if the
    decision has genuinely changed.
    """
    tag = f"authz-{actor.kind.value}-{actor.actor_id}".lower()
    key = _seed_license_key(tag=tag)

    result = apply_license_status_transition(
        key,
        to_status=LicenseKeyStatus.REVOKED,
        actor=actor,
        reason="Recording the actor without checking it, by design.",
        request_id=f"req-{tag}"[:64],
    )

    assert result.changed is True
    # The actor is RECORDED faithfully — which is what makes the missing gate detectable
    # after the fact, and what the caller's own authorisation test complements.
    row = _audit_rows(key).order_by("-id").first()
    assert row.actor_kind == actor.kind.value
    assert row.actor_id == actor.actor_id


def test_the_module_states_the_authorisation_contract():
    """Guards the finding itself.

    A security review found the contract missing from the tree entirely: the docstring was
    exhaustive about transaction and writer discipline, so a reader would reasonably conclude
    every caller obligation was listed. Prose is the deliverable here, so prose is what this
    checks — loosely, on the obligations rather than the wording.

    Under `python -OO` docstrings are stripped and this test FAILS. That is deliberate and is
    the right failure mode: the usual weakness of a prose assertion is passing vacuously when
    there is nothing left to read. A red here means "the contract could not be verified", not
    "the contract is absent".
    """
    from selahcue_api.apps.license_keys import state_machine as module

    contract = (module.__doc__ or "").lower()
    # "permission_denied" is load-bearing in this list. The other tokens each appear TWICE in
    # the docstring — "require_staff_permission" in both the obligation bullet and the
    # rationale sentence explaining why it is not hardcoded here — so the obligation itself
    # could be deleted while the rationale kept the substring alive and this test stayed
    # green. "permission_denied" occurs only inside the obligation bullet, which closes that
    # window: the caller's duty to refuse an unauthorised actor cannot vanish silently.
    for obligation in (
        "no authorisation",
        "require_staff_permission",
        "permission_denied",
        "staffpermission",
    ):
        assert obligation in contract, (
            f"the module contract must state {obligation!r} — five tickets call this writer "
            "and the gating half of PRD §19 is enforced by nobody if it is unwritten"
        )

    writer_contract = (apply_license_status_transition.__doc__ or "").lower()
    assert "no authorisation" in writer_contract, (
        "the writer's own docstring must state it too — that is what is read at the call site"
    )
