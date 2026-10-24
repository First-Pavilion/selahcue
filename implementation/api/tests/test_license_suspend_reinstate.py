"""Staff suspend + reinstate — FR-504, FR-510, FLOW-506; D3 / DEC-010 (86ak5mn0c).

SUSPENDED is a SOFT, reversible hold. The owner's rule is "a commercial problem degrades
commercial surfaces, not the show": new activations and manifest issuance stop, a device that
is already running keeps its token and keeps working, and reinstatement returns the licence
to EXACTLY the status it held before — recorded at suspension time, never guessed.

Layout, in the order a reviewer will want it:

1. the two mutations over the service layer — happy paths, every source status, retry;
2. validation, authorisation, existence, throttling and the transaction guard;
3. the audit trail — no secrets;
4. the GraphQL surface, end to end over HTTP;
5. the D3 behaviour on real devices — tokens survive, activations and manifests refuse;
6. the enforcement point for commercial device calls, and the sweeps that keep it honest;
7. activations RESUME after reinstatement (and the session path while suspended);
8. the cascade spares a suspension from an activatable status, and only that;
9. actor identities that cannot be audited are refused at the boundary;
10. the payloads do not widen what a lifecycle permission can read;
11. the shipped throttle default.

Every test is `transaction=True`. That is not decoration: the mutations REFUSE to run inside
a caller's transaction (see `_require_autocommit`), because a refusal's DENIED audit row
would be rolled back with it, and pytest-django's default per-test wrapper IS such a
transaction. The same choice is what makes "the denial row survives" measurable at all.

The state machine's own tests (`test_license_state_machine.py`) own the table; nothing here
restates it except as an independent oracle for the PRD's §13 list. Postgres-only races live
beside the other lifecycle races in `test_concurrency_postgres.py`.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import timedelta

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.db import connection, transaction
from django.urls import get_resolver
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import Device, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import (
    ACTIVATABLE_KEY_STATUSES,
    ActivateDeviceWithSessionData,
    activate_device_with_session,
    require_commercial_service,
)
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.apps.license_keys import services as license_services
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.services import (
    GenerateLicenseKeyData,
    ReinstateLicenseKeyData,
    SuspendLicenseKeyData,
    generate_license_key,
    reinstate_license_key,
    suspend_license_key,
)
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    PRIOR_STATUS,
    REFUSED_ACTION,
    REINSTATE_ACTION,
    SUSPEND_ACTION,
    SUSPENDABLE_SOURCES,
    IllegalLicenseTransition,
    _default_action,
    apply_license_status_transition,
)
from selahcue_api.graphql.context import (
    ACTOR_ID_MAX_LENGTH,
    ActorContext,
    ActorKind,
    StaffPermission,
    actor_from_request,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.route_contracts import (
    LICENSE_GATE_ALLOWED_WHILE_SUSPENDED,
    LICENSE_GATE_COMMERCIAL,
    LICENSE_GATES,
    CommandEndpointContract,
    desktop_command_contracts,
)

pytestmark = pytest.mark.django_db(transaction=True)

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

REASON = "Card declined three times; holding the licence while billing follows up."
SUSPEND_PERMS = frozenset({StaffPermission.SUSPEND_LICENSE_KEY})
REINSTATE_PERMS = frozenset({StaffPermission.REINSTATE_LICENSE_KEY})
BOTH_PERMS = SUSPEND_PERMS | REINSTATE_PERMS

S = LicenseKeyStatus

# The PRD §13 list ("any non-terminal -> SUSPENDED", with REVOKED and ARCHIVED terminal),
# written out here as an INDEPENDENT oracle rather than read back from the production table.
# `test_the_oracle_covers_every_status_and_agrees_with_the_table` ties the two together, so a
# table change forces a decision here instead of drifting past.
SUSPENDABLE = [S.ISSUED, S.ACTIVATED, S.EXPIRING, S.EXPIRED, S.CONVERTED]
NOT_SUSPENDABLE = [S.REVOKED, S.ARCHIVED]

# Shortest legal walk from ISSUED to each status, through the production writer.
PATHS = {
    S.ISSUED: [],
    S.ACTIVATED: [S.ACTIVATED],
    S.EXPIRING: [S.EXPIRING],
    S.EXPIRED: [S.EXPIRING, S.EXPIRED],
    S.CONVERTED: [S.ACTIVATED, S.CONVERTED],
    S.REVOKED: [S.REVOKED],
    S.ARCHIVED: [S.REVOKED, S.ARCHIVED],
}


# --- Module-local seeding helpers ---------------------------------------------------------
# The shipped slices each build their own rather than sharing a conftest.py — follow that.
def _staff(permissions=BOTH_PERMS, actor_id="staff_billing_1") -> ActorContext:
    return ActorContext(
        kind=ActorKind.STAFF, actor_id=actor_id, staff_permissions=frozenset(permissions)
    )


def _seed_key(tag, *, device_limit=3):
    """Returns (AppLicenseKey, full_key) — a freshly issued, ISSUED licence."""
    customer = CustomerOrg.objects.create(
        name=f"Suspend Church {tag}",
        slug=f"suspend-church-{tag}",
        primary_contact_email=f"ops+{tag}@suspend.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    result = generate_license_key(
        ActorContext(
            kind=ActorKind.STAFF,
            actor_id="staff_ops_1",
            staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
        ),
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            plan_code="PRO",
            starts_at=now,
            expires_at=now + timedelta(days=30),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Seed licence for the suspend/reinstate battery.",
        ),
    )
    return result.license_key, result.full_key


def _drive_to(key, status, *, tag="seed"):
    """Walk the licence to `status` through the production writer, as a SERVICE actor so the
    staff audit rows under test are not polluted by set-up."""
    seeder = ActorContext(kind=ActorKind.SERVICE, actor_id="test-seed-driver")
    for step, hop in enumerate(PATHS[status]):
        apply_license_status_transition(
            key,
            to_status=hop,
            actor=seeder,
            reason="Test set-up walk to the source status.",
            request_id=f"seed-{tag}-{hop.value.lower()}-{step}",
        )
    key.refresh_from_db()
    assert key.status == status


def _suspend_data(key, idem="suspend-req-0001", reason=REASON):
    return SuspendLicenseKeyData(
        idempotency_key=idem, license_key_id=str(key.pk), reason=reason
    )


def _reinstate_data(key, idem="reinstate-req-0001", reason=REASON):
    return ReinstateLicenseKeyData(
        idempotency_key=idem, license_key_id=str(key.pk), reason=reason
    )


def _suspend(key, idem="suspend-req-0001", *, actor=None, reason=REASON):
    return suspend_license_key(actor or _staff(), _suspend_data(key, idem, reason))


def _reinstate(key, idem="reinstate-req-0001", *, actor=None, reason=REASON):
    return reinstate_license_key(actor or _staff(), _reinstate_data(key, idem, reason))


def _rows(key, **filters):
    return AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), **filters
    ).order_by("id")


def _fresh(key):
    key.refresh_from_db()
    return key


def _arabic_indic(digits: str) -> str:
    # Built with chr() rather than typed escapes: the Edit/Write tools can turn a typed
    # escape into a real invisible character in committed source.
    return "".join(chr(0x0660 + int(d)) for d in digits)


@pytest.fixture(autouse=True)
def _fresh_state(settings):
    """The throttle store is a process-wide LocMemCache and the staff header bridge is off by
    default, so reset both rather than loosening anything."""
    cache.clear()
    settings.SELAHCUE_TRUST_ACTOR_HEADERS = True
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    yield
    cache.clear()


# =============================================================================================
# 1. Suspend and reinstate over the service layer
# =============================================================================================
def test_the_oracle_covers_every_status_and_agrees_with_the_table():
    """The two lists above are the PRD's §13 reading. They must name every status exactly
    once (SUSPENDED is the idempotent case) and agree with what the production table allows —
    otherwise a status could be added, or an edge moved, and every parametrised test below
    would keep passing over a list that no longer describes the system."""
    named = set(SUSPENDABLE) | set(NOT_SUSPENDABLE) | {S.SUSPENDED}
    assert named == set(LicenseKeyStatus), "the oracle must name every licence status"
    assert len(SUSPENDABLE) + len(NOT_SUSPENDABLE) + 1 == len(LicenseKeyStatus)
    assert set(SUSPENDABLE) == set(SUSPENDABLE_SOURCES)
    assert set(PATHS) == set(SUSPENDABLE) | set(NOT_SUSPENDABLE)


def test_the_audit_action_names_are_the_writers_own():
    """The audit trail's action names are a contract (support queries by them, the retry
    lookup matches on them): pinned literally, and tied to the writer's own default naming so
    the constant and the behaviour cannot drift apart."""
    assert SUSPEND_ACTION == "license_key.suspended"
    assert REINSTATE_ACTION == "license_key.reinstated"
    assert SUSPEND_ACTION == _default_action(S.SUSPENDED, S.SUSPENDED)
    assert REINSTATE_ACTION == _default_action(S.ACTIVATED, PRIOR_STATUS)


@pytest.mark.parametrize("source", SUSPENDABLE, ids=lambda s: s.value)
def test_suspend_succeeds_from_every_suspendable_status_and_records_where_it_came_from(source):
    key, _ = _seed_key(f"sus-{source.value.lower()}")
    _drive_to(key, source)
    before_rows = _rows(key).count()

    result = _suspend(key)

    assert result.changed is True
    assert result.from_status == source and result.to_status == S.SUSPENDED
    # The prior status is persisted at suspension time, in the same write as the status.
    stored = AppLicenseKey.objects.get(pk=key.pk)
    assert stored.status == S.SUSPENDED
    assert stored.prior_status == source.value
    # The object handed back to the GraphQL layer reflects the committed write, not the
    # stale pre-transition row.
    assert result.license_key.status == S.SUSPENDED
    assert result.license_key.prior_status == source.value

    new_rows = list(_rows(key))[before_rows:]
    assert len(new_rows) == 1, "one transition, one audit row (NFR-506)"
    row = new_rows[0]
    assert row.action == SUSPEND_ACTION
    assert row.result == AuditResult.SUCCESS
    assert (row.actor_kind, row.actor_id) == ("staff", "staff_billing_1")
    assert row.reason == REASON
    assert row.request_id == "suspend-req-0001"
    assert row.before == {"status": source.value, "prior_status": ""}
    assert row.after == {"status": "SUSPENDED", "prior_status": source.value}


@pytest.mark.parametrize("source", NOT_SUSPENDABLE, ids=lambda s: s.value)
def test_suspend_of_a_terminal_licence_is_refused_and_the_denial_survives(source):
    """THE durability case: a refused suspend of a REVOKED licence must leave its DENIED row.
    The refusal is raised to a caller in autocommit, so the row committed on its own."""
    key, _ = _seed_key(f"susdeny-{source.value.lower()}")
    _drive_to(key, source)
    rows_before = _rows(key).count()
    assert not connection.in_atomic_block, "the premise: this caller is in autocommit"

    with pytest.raises(IllegalLicenseTransition) as raised:
        _suspend(key)

    assert raised.value.code == ErrorCode.CONFLICT
    stored = _fresh(key)
    assert stored.status == source, "a refused suspension changes nothing"
    assert stored.prior_status == ""
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1, "exactly one row, and it is the DENIED one"
    denied = new_rows[0]
    assert denied.result == AuditResult.DENIED
    assert denied.action == REFUSED_ACTION
    assert (denied.actor_kind, denied.actor_id) == ("staff", "staff_billing_1")
    assert denied.reason == REASON
    assert denied.request_id == "suspend-req-0001"
    assert denied.before == {"status": source.value, "prior_status": ""}
    assert denied.after["requested_status"] == "SUSPENDED"
    assert denied.after["refusal_code"] == "illegal_transition"
    assert not _rows(key, result=AuditResult.SUCCESS, action=SUSPEND_ACTION).exists()


def test_suspending_an_already_suspended_licence_is_a_no_op_with_no_second_audit_row():
    key, _ = _seed_key("sus-twice")
    _drive_to(key, S.EXPIRING)
    _suspend(key, "suspend-first-0001")
    rows_before = _rows(key).count()

    # A DIFFERENT key: this is a second staff action, not a retry, so only the writer's
    # "already in the target state" rule can make it harmless.
    again = _suspend(key, "suspend-second-0002")

    assert again.changed is False
    assert again.audit_event is None
    stored = _fresh(key)
    assert stored.status == S.SUSPENDED
    assert stored.prior_status == "EXPIRING", (
        "the second suspend must not overwrite the recorded prior status with SUSPENDED"
    )
    assert _rows(key).count() == rows_before


@pytest.mark.parametrize("source", SUSPENDABLE, ids=lambda s: s.value)
def test_reinstate_returns_the_exact_prior_status(source):
    """FR-510: proven separately for every status a licence can be suspended from — and in
    particular for EXPIRING, which a hardcoded ACTIVATED would silently promote."""
    key, _ = _seed_key(f"rein-{source.value.lower()}")
    _drive_to(key, source)
    _suspend(key)
    rows_before = _rows(key).count()

    result = _reinstate(key)

    assert result.changed is True
    assert result.from_status == S.SUSPENDED and result.to_status == source
    stored = AppLicenseKey.objects.get(pk=key.pk)
    assert stored.status == source
    assert stored.prior_status == "", "the bookkeeping is cleared on the way out"
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1
    row = new_rows[0]
    assert row.action == REINSTATE_ACTION and row.result == AuditResult.SUCCESS
    assert (row.actor_kind, row.actor_id) == ("staff", "staff_billing_1")
    assert row.reason == REASON and row.request_id == "reinstate-req-0001"
    assert row.before == {"status": "SUSPENDED", "prior_status": source.value}
    assert row.after == {"status": source.value, "prior_status": ""}


@pytest.mark.parametrize(
    "status", [s for s in PATHS], ids=lambda s: s.value
)
def test_reinstating_a_licence_that_is_not_suspended_is_refused_and_audited(status):
    key, _ = _seed_key(f"reinnot-{status.value.lower()}")
    _drive_to(key, status)
    rows_before = _rows(key).count()

    with pytest.raises(IllegalLicenseTransition) as raised:
        _reinstate(key)

    assert raised.value.code == ErrorCode.CONFLICT
    assert _fresh(key).status == status, "nothing is promoted to a status it never held"
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1
    assert new_rows[0].result == AuditResult.DENIED
    assert new_rows[0].after["refusal_code"] == "not_suspended"
    assert new_rows[0].after["requested_status"] == "PRIOR_STATUS"


@pytest.mark.parametrize(
    "forged", [S.ARCHIVED.value, "NOT_A_STATUS"], ids=["never-suspendable", "not-a-status"]
)
def test_reinstate_refuses_a_corrupt_recorded_prior_status_rather_than_guessing(forged):
    """Defence in depth behind the schema's check constraint: a raw write can leave a
    non-empty but unusable value, and falling back to ACTIVATED would promote a licence to a
    status it was never in. The mutation must surface that as a coded, audited refusal."""
    key, _ = _seed_key(f"reincorrupt-{forged.lower()}")
    _drive_to(key, S.EXPIRING)
    _suspend(key)
    table = AppLicenseKey._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"UPDATE {table} SET prior_status = %s WHERE id = %s", [forged, key.pk])
    rows_before = _rows(key).count()

    with pytest.raises(IllegalLicenseTransition):
        _reinstate(key)

    assert _fresh(key).status == S.SUSPENDED
    new_rows = list(_rows(key))[rows_before:]
    assert [r.result for r in new_rows] == [AuditResult.DENIED]
    assert new_rows[0].after["refusal_code"] in {
        "prior_status_not_a_status",
        "prior_status_not_suspendable",
    }


def test_a_suspend_reinstate_cycle_can_repeat_and_every_pair_is_reconstructible():
    """FLOW-506 from the trail alone: the licence's audit rows alternate suspend / reinstate,
    and each reinstatement's `before.prior_status` is the status its suspension recorded and
    the status it restored."""
    key, _ = _seed_key("cycle")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()

    for n in range(3):
        _suspend(key, f"cycle-suspend-{n:04d}-x")
        assert _fresh(key).status == S.SUSPENDED
        _reinstate(key, f"cycle-reinstate-{n:04d}")
        assert _fresh(key).status == S.ACTIVATED

    rows = list(_rows(key))[rows_before:]
    assert [r.action for r in rows] == [SUSPEND_ACTION, REINSTATE_ACTION] * 3
    assert all(r.result == AuditResult.SUCCESS for r in rows)
    for suspension, reinstatement in zip(rows[0::2], rows[1::2]):
        assert suspension.after["prior_status"] == "ACTIVATED"
        assert reinstatement.before["prior_status"] == suspension.after["prior_status"]
        assert reinstatement.after["status"] == suspension.after["prior_status"]
        assert suspension.id < reinstatement.id
        assert suspension.target_id == reinstatement.target_id == str(key.pk)


def test_a_licence_suspended_from_each_status_comes_back_independently():
    """Two licences suspended from different statuses at the same time must each return to
    their OWN prior status — the recorded value is per-row, not shared state."""
    key_a, _ = _seed_key("indep-a")
    key_b, _ = _seed_key("indep-b")
    _drive_to(key_a, S.ACTIVATED, tag="a")
    _drive_to(key_b, S.EXPIRING, tag="b")
    _suspend(key_a, "indep-suspend-aaaa")
    _suspend(key_b, "indep-suspend-bbbb")

    _reinstate(key_b, "indep-reinstate-bbbb")
    _reinstate(key_a, "indep-reinstate-aaaa")

    assert _fresh(key_a).status == S.ACTIVATED
    assert _fresh(key_b).status == S.EXPIRING


# --- Retry and idempotency ----------------------------------------------------------------
def test_the_same_suspend_request_sent_twice_takes_effect_once():
    key, _ = _seed_key("retry-suspend")
    _drive_to(key, S.ACTIVATED)
    first = _suspend(key, "retry-suspend-0001")
    rows_after_first = _rows(key).count()

    second = _suspend(key, "retry-suspend-0001")

    assert first.changed is True and second.changed is False
    assert _rows(key).count() == rows_after_first, "the retry wrote nothing"
    assert _rows(key, action=SUSPEND_ACTION).count() == 1
    # The retry reports the ORIGINAL outcome's audit row, so a client can correlate.
    assert second.audit_event.pk == first.audit_event.pk


def test_the_same_reinstate_request_sent_twice_takes_effect_once():
    key, _ = _seed_key("retry-reinstate")
    _drive_to(key, S.EXPIRING)
    _suspend(key)
    first = _reinstate(key, "retry-reinstate-0001")
    rows_after_first = _rows(key).count()

    second = _reinstate(key, "retry-reinstate-0001")

    assert first.changed is True and second.changed is False
    assert second.audit_event.pk == first.audit_event.pk
    assert _rows(key).count() == rows_after_first
    assert _rows(key, result=AuditResult.DENIED).count() == 0, (
        "a retry of a request that already succeeded is not a refusal"
    )
    assert _fresh(key).status == S.EXPIRING


def test_a_stale_suspend_retry_cannot_undo_a_reinstatement_made_since():
    """The failure the writer's own idempotency cannot see. Suspend (key K) succeeded, staff
    reinstated, then K's response finally times out client-side and the client re-sends K.
    "Already in the target state" no longer holds — the licence is ACTIVATED — so without
    request-level recognition this would suspend the customer AGAIN, silently reversing a
    deliberate reinstatement."""
    key, _ = _seed_key("stale-suspend")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "stale-suspend-K-0001")
    _reinstate(key, "stale-reinstate-0002")
    rows_before = _rows(key).count()

    replay = _suspend(key, "stale-suspend-K-0001")

    assert replay.changed is False
    assert _fresh(key).status == S.ACTIVATED, "a stale retry must not re-suspend"
    assert _rows(key).count() == rows_before


def test_a_stale_reinstate_retry_cannot_lift_a_later_suspension():
    key, _ = _seed_key("stale-reinstate")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "stale-r-suspend-0001")
    _reinstate(key, "stale-r-reinstate-K1")
    _suspend(key, "stale-r-suspend-0003")
    rows_before = _rows(key).count()

    replay = _reinstate(key, "stale-r-reinstate-K1")

    assert replay.changed is False
    assert _fresh(key).status == S.SUSPENDED, "a stale retry must not lift a newer suspension"
    assert _rows(key).count() == rows_before


def test_a_duplicate_reinstate_after_another_staff_member_suspended_again_changes_nothing():
    """The window the retry lookup exists to close: reinstate K1 took effect, then ANOTHER
    staff member suspended the licence again, then the duplicate of K1 arrives. The licence is
    suspended once more, so an "is it still suspended?" test would happily reinstate it a
    second time and silently undo that staff member's action."""
    key, _ = _seed_key("dup-between-reinstate")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "dup-between-susp-first", actor=_staff(actor_id="staff_a"))
    _reinstate(key, "dup-between-reinstate-K1", actor=_staff(actor_id="staff_a"))
    _suspend(key, "dup-between-susp-other", actor=_staff(actor_id="staff_b"))
    rows_before = _rows(key).count()

    duplicate = _reinstate(key, "dup-between-reinstate-K1", actor=_staff(actor_id="staff_a"))

    assert duplicate.changed is False and duplicate.audit_event is not None
    assert _fresh(key).status == S.SUSPENDED, "the other staff member's suspension stands"
    assert _rows(key).count() == rows_before
    assert _rows(key, action=REINSTATE_ACTION, request_id="dup-between-reinstate-K1").count() == 1


def test_a_duplicate_suspend_after_another_staff_member_reinstated_changes_nothing():
    key, _ = _seed_key("dup-between-suspend")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "dup-between-suspend-K1", actor=_staff(actor_id="staff_a"))
    _reinstate(key, "dup-between-reinst-other", actor=_staff(actor_id="staff_b"))
    rows_before = _rows(key).count()

    duplicate = _suspend(key, "dup-between-suspend-K1", actor=_staff(actor_id="staff_a"))

    assert duplicate.changed is False and duplicate.audit_event is not None
    assert _fresh(key).status == S.ACTIVATED, "the other staff member's reinstatement stands"
    assert _rows(key).count() == rows_before
    assert _rows(key, action=SUSPEND_ACTION, request_id="dup-between-suspend-K1").count() == 1


def test_a_replayed_request_is_flagged_and_an_already_suspended_no_op_is_not():
    """`changed=False` alone is ambiguous; the audit row the result carries is what tells a
    retry that already took effect apart from a plain "already in that state"."""
    key, _ = _seed_key("replayed-flag")
    first = _suspend(key, "replayed-flag-req-1")
    replay = _suspend(key, "replayed-flag-req-1")
    plain_no_op = _suspend(key, "replayed-flag-req-2")

    assert (first.changed, first.audit_event is not None) == (True, True)
    assert (replay.changed, replay.audit_event is not None) == (False, True)
    assert (plain_no_op.changed, plain_no_op.audit_event) == (False, None)


def test_a_replay_refreshes_the_callers_licence_instance():
    """The writer's contract is that the caller's in-memory licence reflects what is committed,
    on the replay branch too: a caller holding an instance from before the request took
    effect must not keep reading the stale status after it is told the request was a replay."""
    key, _ = _seed_key("replay-sync")
    _drive_to(key, S.ACTIVATED)
    stale = AppLicenseKey.objects.get(pk=key.pk)
    assert stale.status == S.ACTIVATED
    _suspend(key, "replay-sync-request-1")

    result = apply_license_status_transition(
        stale,
        to_status=S.SUSPENDED,
        actor=_staff(),
        reason=REASON,
        request_id="replay-sync-request-1",
        recognise_retry=True,
    )

    assert result.changed is False and result.audit_event is not None
    assert stale.status == S.SUSPENDED and stale.prior_status == "ACTIVATED"


def test_a_retry_of_a_request_that_was_itself_a_no_op_is_not_recognised():
    """The documented limit: a no-op wrote no audit row, so there is nothing to recognise.
    staff_b's no-op suspend, retried after staff_a reinstated, therefore applies. Pinned so
    the limit is a known behaviour (and a deliberate decision to leave it) rather than a
    surprise; adding a row for a no-op is explicitly NOT wanted."""
    key, _ = _seed_key("noop-limit")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "noop-limit-staff-a-1", actor=_staff(actor_id="staff_a"))
    noop = _suspend(key, "noop-limit-staff-b-1", actor=_staff(actor_id="staff_b"))
    assert noop.changed is False
    _reinstate(key, "noop-limit-staff-a-2", actor=_staff(actor_id="staff_a"))

    retried = _suspend(key, "noop-limit-staff-b-1", actor=_staff(actor_id="staff_b"))

    assert retried.changed is True


def test_one_key_used_on_two_licences_is_two_requests_and_both_take_effect():
    """The key is scoped to the licence it was used on. Reusing a key across licences is a
    client bug, but the safe reading is "two requests", never "the second is a replay of the
    first" — that would skip a suspension nobody had performed."""
    key_a, _ = _seed_key("samekey-a")
    key_b, _ = _seed_key("samekey-b")

    _suspend(key_a, "shared-key-across-0001")
    result_b = _suspend(key_b, "shared-key-across-0001")

    assert result_b.changed is True
    assert _fresh(key_a).status == S.SUSPENDED and _fresh(key_b).status == S.SUSPENDED
    assert _rows(key_a, action=SUSPEND_ACTION).count() == 1
    assert _rows(key_b, action=SUSPEND_ACTION).count() == 1


def test_one_key_used_for_suspend_then_reinstate_is_two_requests():
    """The action is part of the retry identity: a key spent on a suspension does not turn the
    reinstatement that reuses it into a replay."""
    key, _ = _seed_key("samekey-actions")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "one-key-two-actions-01")

    result = _reinstate(key, "one-key-two-actions-01")

    assert result.changed is True
    assert _fresh(key).status == S.ACTIVATED


def test_another_staff_member_reusing_a_key_is_not_a_replay():
    """Retries are scoped to the actor: staff B cannot have a suspension swallowed because
    staff A once used the same string."""
    key, _ = _seed_key("samekey-actors")
    _drive_to(key, S.ACTIVATED)
    _suspend(key, "actor-scoped-key-0001", actor=_staff(actor_id="staff_a"))
    _reinstate(key, "actor-scoped-reinstate-1", actor=_staff(actor_id="staff_a"))

    result = _suspend(key, "actor-scoped-key-0001", actor=_staff(actor_id="staff_b"))

    assert result.changed is True
    assert _fresh(key).status == S.SUSPENDED
    assert _rows(key, action=SUSPEND_ACTION).last().actor_id == "staff_b"


def test_a_refused_attempt_is_re_evaluated_on_retry_not_replayed():
    """Only SUCCESS rows make a key a replay. A reinstatement refused because the licence was
    not yet suspended must succeed when the same key is sent after the suspension — the state
    that caused the refusal has changed."""
    key, _ = _seed_key("refused-then-ok")
    _drive_to(key, S.ACTIVATED)
    with pytest.raises(IllegalLicenseTransition):
        _reinstate(key, "refused-then-ok-key-1")
    _suspend(key, "refused-then-ok-susp1")

    result = _reinstate(key, "refused-then-ok-key-1")

    assert result.changed is True
    assert _fresh(key).status == S.ACTIVATED


# =============================================================================================
# 2. Validation, authorisation, existence, throttling, transaction guard
# =============================================================================================
@pytest.mark.parametrize(
    "reason",
    ["", "   ", "\n\t ", "short", "1234567", "x" * 1001, "contains a NUL\x00 byte here"],
    ids=["empty", "spaces", "whitespace-only", "five-chars", "seven-chars", "1001-chars", "nul"],
)
@pytest.mark.parametrize("mutation", ["suspend", "reinstate"])
def test_a_missing_or_malformed_reason_is_refused_and_nothing_changes(mutation, reason):
    key, _ = _seed_key("badreason")
    _drive_to(key, S.ACTIVATED)
    if mutation == "reinstate":
        _suspend(key)
    status_before = _fresh(key).status
    rows_before = _rows(key).count()
    call = _suspend if mutation == "suspend" else _reinstate

    with pytest.raises(SafeAPIError) as raised:
        call(key, "bad-reason-request-1", reason=reason)

    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    assert _fresh(key).status == status_before
    assert _rows(key).count() == rows_before, "validation failures write no audit row"


@pytest.mark.parametrize(
    ("reason", "stored"),
    [
        ("12345678", "12345678"),
        ("x" * 1000, "x" * 1000),
        ("  held   for\n non-payment  ", "held for non-payment"),
    ],
    ids=["exactly-8", "exactly-1000", "whitespace-collapsed"],
)
def test_reason_boundaries_are_accepted_and_stored_normalised(reason, stored):
    key, _ = _seed_key("goodreason")

    _suspend(key, reason=reason)

    assert _rows(key, action=SUSPEND_ACTION).get().reason == stored


@pytest.mark.parametrize(
    "idem",
    ["", "short-key", "11-chars-ab", "has spaces in it!", "x" * 129, "bad/slash/in/key-1"],
    ids=["empty", "short", "eleven", "spaces", "129-chars", "slash"],
)
def test_an_invalid_idempotency_key_is_refused(idem):
    key, _ = _seed_key("badidem")

    with pytest.raises(SafeAPIError) as raised:
        _suspend(key, idem)

    assert raised.value.code == ErrorCode.VALIDATION_FAILED
    assert _fresh(key).status == S.ISSUED
    assert not _rows(key, action=SUSPEND_ACTION).exists()


@pytest.mark.parametrize("idem", ["a" * 12, "k" * 128], ids=["exactly-12", "exactly-128"])
def test_idempotency_key_length_boundaries_are_accepted(idem):
    key, _ = _seed_key("goodidem")

    assert _suspend(key, idem).changed is True
    assert _rows(key, action=SUSPEND_ACTION).get().request_id == idem


@pytest.mark.parametrize(
    "bad_id",
    [
        "999999999",
        "0",
        "-1",
        "+1",
        "1.5",
        "0x10",
        "abc",
        "",
        "   ",
        "1; DROP TABLE x",
        "1\x00",
        _arabic_indic("123"),  # Arabic-Indic digits: .isdecimal() is True, .isascii() is not
        "9" * 30,
    ],
    ids=[
        "no-such-row",
        "zero",
        "negative",
        "signed",
        "float",
        "hex",
        "letters",
        "empty",
        "spaces",
        "sql",
        "nul",
        "non-ascii-digits",
        "overflowing",
    ],
)
@pytest.mark.parametrize("mutation", [suspend_license_key, reinstate_license_key])
def test_a_licence_reference_that_names_nothing_is_one_uniform_not_found(mutation, bad_id):
    """Unknown, malformed, hostile and overflowing references all take the SAME refusal, so
    the response says nothing about which ids exist or what shape the lookup expects."""
    data_class = SuspendLicenseKeyData if mutation is suspend_license_key else ReinstateLicenseKeyData
    audit_before = AuditEvent.objects.count()

    with pytest.raises(SafeAPIError) as raised:
        mutation(
            _staff(),
            data_class(idempotency_key="unknown-ref-req-001", license_key_id=bad_id, reason=REASON),
        )

    assert raised.value.code == ErrorCode.NOT_FOUND
    assert raised.value.message == "The requested resource was not found."
    assert AuditEvent.objects.count() == audit_before


def test_spellings_of_a_real_licence_id_that_python_would_parse_do_not_resolve():
    """Each of these is accepted by `int()`, so a lenient parser would find the REAL licence
    and suspend it. The strictness is the point: the unknown-id battery above cannot see it,
    because there the id names nothing either way."""
    key, _ = _seed_key("spellings")
    real = str(key.pk)
    spellings = [f"+{real}", f"-{real}", _arabic_indic(real), f"{real}\x00", f"{real}.0", f"0x{real}"]
    if len(real) > 1:
        spellings.append(f"{real[0]}_{real[1:]}")

    for spelling in spellings:
        with pytest.raises(SafeAPIError) as raised:
            suspend_license_key(
                _staff(),
                SuspendLicenseKeyData(
                    idempotency_key="spelling-request-001", license_key_id=spelling, reason=REASON
                ),
            )
        assert raised.value.code == ErrorCode.NOT_FOUND, repr(spelling)
        assert raised.value.message == "The requested resource was not found."
    assert _fresh(key).status == S.ISSUED


def test_a_padded_reference_to_a_real_licence_still_resolves():
    """Positive control for the battery above: the strictness is about SHAPE, not about
    rejecting everything, so a real id with stray whitespace still finds its row."""
    key, _ = _seed_key("padded")

    result = suspend_license_key(
        _staff(),
        SuspendLicenseKeyData(
            idempotency_key="padded-ref-request-1", license_key_id=f"  {key.pk}\n", reason=REASON
        ),
    )

    assert result.changed is True


UNAUTHORISED = [
    pytest.param(None, ErrorCode.UNAUTHENTICATED, id="no-actor"),
    # Every non-staff kind below carries BOTH staff permissions on purpose: the kind check, not
    # the missing permission, is what must refuse them, so a gate that only inspected the
    # permission set would be caught here at the service level.
    pytest.param(
        ActorContext(
            kind=ActorKind.CUSTOMER,
            actor_id="cust_1",
            org_id="1",
            role="ADMIN",
            staff_permissions=BOTH_PERMS,
        ),
        ErrorCode.PERMISSION_DENIED,
        id="customer-admin",
    ),
    pytest.param(
        ActorContext(kind=ActorKind.DEVICE, actor_id="dev_1", staff_permissions=BOTH_PERMS),
        ErrorCode.PERMISSION_DENIED,
        id="device",
    ),
    pytest.param(
        ActorContext(
            kind=ActorKind.SERVICE, actor_id="expiry-sweep", staff_permissions=BOTH_PERMS
        ),
        ErrorCode.PERMISSION_DENIED,
        id="service",
    ),
    pytest.param(
        ActorContext(kind=ActorKind.STAFF, actor_id="staff_none"),
        ErrorCode.PERMISSION_DENIED,
        id="staff-no-permissions",
    ),
    pytest.param(
        _staff(
            {
                StaffPermission.REVOKE_LICENSE_KEY,
                StaffPermission.EXTEND_LICENSE_KEY,
                StaffPermission.GENERATE_LICENSE_KEY,
                StaffPermission.MANAGE_CUSTOMERS,
            }
        ),
        ErrorCode.PERMISSION_DENIED,
        id="staff-with-every-other-licence-permission",
    ),
]


@pytest.mark.parametrize(("actor", "code"), UNAUTHORISED)
def test_suspend_is_refused_to_anyone_without_the_suspend_permission(actor, code):
    """PRD §19's control pair is "actor gating + audit"; the writer is only the audit half.
    The staff member entitled to REVOKE is deliberately refused here."""
    key, _ = _seed_key("authz-suspend")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()

    with pytest.raises(SafeAPIError) as raised:
        suspend_license_key(actor, _suspend_data(key))

    assert raised.value.code == code
    assert _fresh(key).status == S.ACTIVATED and _fresh(key).prior_status == ""
    assert _rows(key).count() == rows_before, "no transition, and nothing recorded as one"


@pytest.mark.parametrize(("actor", "code"), UNAUTHORISED)
def test_reinstate_is_refused_to_anyone_without_the_reinstate_permission(actor, code):
    key, _ = _seed_key("authz-reinstate")
    _drive_to(key, S.EXPIRING)
    _suspend(key)
    rows_before = _rows(key).count()

    with pytest.raises(SafeAPIError) as raised:
        reinstate_license_key(actor, _reinstate_data(key))

    assert raised.value.code == code
    assert _fresh(key).status == S.SUSPENDED and _fresh(key).prior_status == "EXPIRING"
    assert _rows(key).count() == rows_before


def test_the_two_permissions_are_separate_authorities():
    """Holding one does not confer the other, and neither is the revoke permission."""
    key, _ = _seed_key("authz-split")
    _drive_to(key, S.ACTIVATED)

    with pytest.raises(SafeAPIError) as raised:
        suspend_license_key(_staff(REINSTATE_PERMS), _suspend_data(key))
    assert raised.value.code == ErrorCode.PERMISSION_DENIED

    suspend_license_key(_staff(SUSPEND_PERMS), _suspend_data(key))

    with pytest.raises(SafeAPIError) as raised:
        reinstate_license_key(_staff(SUSPEND_PERMS), _reinstate_data(key))
    assert raised.value.code == ErrorCode.PERMISSION_DENIED
    assert _fresh(key).status == S.SUSPENDED

    reinstate_license_key(_staff(REINSTATE_PERMS), _reinstate_data(key))
    assert _fresh(key).status == S.ACTIVATED

    assert StaffPermission.SUSPEND_LICENSE_KEY != StaffPermission.REVOKE_LICENSE_KEY
    assert StaffPermission.REINSTATE_LICENSE_KEY != StaffPermission.REVOKE_LICENSE_KEY
    assert StaffPermission.SUSPEND_LICENSE_KEY != StaffPermission.REINSTATE_LICENSE_KEY


@pytest.mark.parametrize(("actor", "code"), UNAUTHORISED)
def test_an_unauthorised_caller_cannot_tell_whether_a_licence_exists(actor, code):
    """No existence oracle: a caller who may not act gets the identical refusal for a real
    licence and for an id that names nothing — the permission gate runs before the lookup."""
    key, _ = _seed_key("oracle")

    outcomes = []
    for reference in (str(key.pk), "999999999"):
        with pytest.raises(SafeAPIError) as raised:
            suspend_license_key(
                actor,
                SuspendLicenseKeyData(
                    idempotency_key="oracle-request-0001", license_key_id=reference, reason=REASON
                ),
            )
        outcomes.append((raised.value.code, raised.value.message))

    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == code


def test_a_call_inside_a_transaction_fails_closed_before_changing_anything():
    """The tripwire for the wrapped-transaction denial loss. A refusal's DENIED row is written
    after the writer's own atomic() unwinds, so inside a caller's transaction it would be
    rolled back with the error — the one record PRD §13 requires would silently vanish.
    There are 17 atomic() sites in this codebase; a docstring is not a control."""
    key, _ = _seed_key("in-atomic")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()

    with transaction.atomic():
        with pytest.raises(SafeAPIError) as raised:
            _suspend(key)
        assert raised.value.code == ErrorCode.INTERNAL
        with pytest.raises(SafeAPIError) as raised:
            _reinstate(key)
        assert raised.value.code == ErrorCode.INTERNAL

    assert _fresh(key).status == S.ACTIVATED
    assert _rows(key).count() == rows_before
    # Positive control: the same call outside the block is fine, so the guard is the
    # only thing that stopped it above.
    assert _suspend(key).changed is True


def test_the_transaction_guard_does_not_leak_into_the_unauthorised_answer():
    """Order matters: a caller who may not suspend is told so, not told about transactions."""
    key, _ = _seed_key("in-atomic-authz")
    with transaction.atomic():
        with pytest.raises(SafeAPIError) as raised:
            suspend_license_key(_staff(set()), _suspend_data(key))
    assert raised.value.code == ErrorCode.PERMISSION_DENIED


# --- Throttling (FR-539) --------------------------------------------------------------------
def _spend(actor, key, n):
    """One call that always reaches the budget and then does nothing harmful."""
    return suspend_license_key(actor, _suspend_data(key, f"throttle-request-{n:04d}"))


def test_the_lifecycle_mutations_are_rate_limited_per_staff_member(settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (3, 60)
    key, _ = _seed_key("throttle")
    _drive_to(key, S.ACTIVATED)
    alice = _staff(actor_id="staff_alice")

    for n in range(3):
        _spend(alice, key, n)

    # The 4th call is refused BEFORE it can act: a reinstatement that would have succeeded
    # leaves the licence suspended.
    with pytest.raises(SafeAPIError) as raised:
        reinstate_license_key(alice, _reinstate_data(key))
    assert raised.value.code == ErrorCode.RATE_LIMITED
    assert _fresh(key).status == S.SUSPENDED

    # Another staff member's budget is their own.
    reinstate_license_key(_staff(actor_id="staff_bob"), _reinstate_data(key, "bobs-own-request-01"))
    assert _fresh(key).status == S.ACTIVATED


def test_suspend_and_reinstate_draw_on_one_shared_budget(settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("throttle-shared")
    _drive_to(key, S.ACTIVATED)
    alice = _staff(actor_id="staff_alice")

    suspend_license_key(alice, _suspend_data(key, "shared-budget-susp-01"))
    reinstate_license_key(alice, _reinstate_data(key, "shared-budget-rein-01"))

    with pytest.raises(SafeAPIError) as raised:
        suspend_license_key(alice, _suspend_data(key, "shared-budget-susp-02"))
    assert raised.value.code == ErrorCode.RATE_LIMITED
    assert _fresh(key).status == S.ACTIVATED


def test_refused_callers_cannot_spend_a_staff_members_budget(settings):
    """An unauthorised caller using a real staff id must not be able to exhaust that member's
    budget: the gate runs first, so only authorised calls are counted."""
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("throttle-gate")
    impostor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_alice")  # no permissions

    for n in range(10):
        with pytest.raises(SafeAPIError) as raised:
            suspend_license_key(impostor, _suspend_data(key, f"impostor-request-{n:03d}"))
        assert raised.value.code == ErrorCode.PERMISSION_DENIED

    assert _spend(_staff(actor_id="staff_alice"), key, 99).changed is True


def test_the_budget_applies_to_refusals_too(settings):
    """A refused-but-authorised call still costs a unit — otherwise hammering an illegal
    transition would be free."""
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("throttle-refusals")
    _drive_to(key, S.REVOKED)

    for n in range(2):
        with pytest.raises(IllegalLicenseTransition):
            _spend(_staff(), key, n)
    with pytest.raises(SafeAPIError) as raised:
        _spend(_staff(), key, 3)
    assert raised.value.code == ErrorCode.RATE_LIMITED


# --- Concurrency-adjacent behaviour that does not need Postgres ---------------------------
def test_writes_go_through_the_state_machine_not_a_direct_status_write(monkeypatch):
    """The mutations may not assign `.status` themselves (the writer-discipline scan pins the
    set of direct-write sites). Proven behaviourally too: with the writer replaced, no status
    moves."""
    key, _ = _seed_key("via-writer")
    calls = []

    def fake_writer(license_key, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("writer reached")

    monkeypatch.setattr(license_services, "apply_license_status_transition", fake_writer)
    with pytest.raises(RuntimeError, match="writer reached"):
        _suspend(key)
    assert _fresh(key).status == S.ISSUED
    assert calls and calls[0]["to_status"] == S.SUSPENDED
    assert calls[0]["actor"].actor_id == "staff_billing_1"
    assert calls[0]["request_id"] == "suspend-req-0001"
    assert calls[0]["recognise_retry"] is True, "retries are recognised inside the writer"

    calls.clear()
    with pytest.raises(RuntimeError, match="writer reached"):
        _reinstate(key)
    assert calls[0]["to_status"] is PRIOR_STATUS, (
        "reinstatement targets the recorded prior status, never a constant"
    )


# =============================================================================================
# 3. The audit trail carries no secrets
# =============================================================================================
def test_no_audit_row_error_or_log_line_carries_a_secret(caplog):
    key, full_key = _seed_key("secrets")
    _drive_to(key, S.EXPIRING)
    revoked, _ = _seed_key("secrets-revoked")
    _drive_to(revoked, S.REVOKED)
    secrets_to_find = [full_key, key.secret_hash, key.secret_fingerprint]

    with caplog.at_level(logging.DEBUG):
        _suspend(key, "secrets-suspend-0001")
        with pytest.raises(IllegalLicenseTransition) as refused:
            _suspend(revoked, "secrets-denied-0001")
        _reinstate(key, "secrets-reinstate-01")

    assert AuditEvent.objects.filter(result=AuditResult.DENIED).exists(), "a refusal was exercised"
    dump = json.dumps(
        [
            {
                "reason": r.reason,
                "before": r.before,
                "after": r.after,
                "request_id": r.request_id,
                "actor_id": r.actor_id,
            }
            for r in AuditEvent.objects.all()
        ]
    )
    for secret in secrets_to_find:
        assert secret not in dump, "a secret reached the audit trail"
        assert secret not in caplog.text, "a secret reached the logs"
        assert secret not in refused.value.message
    # The detail that explains a refusal stays server-side: the caller sees the safe message.
    assert "legal licence transition" not in refused.value.message


# =============================================================================================
# 4. The GraphQL surface, end to end over HTTP
# =============================================================================================
SUSPEND_MUTATION = """
    mutation Suspend($input: AdminSuspendLicenseKeyInput!) {
      adminSuspendLicenseKey(input: $input) {
        changed
        replayed
        licenseKey { id status priorStatus maskedKey }
      }
    }
"""
REINSTATE_MUTATION = """
    mutation Reinstate($input: AdminReinstateLicenseKeyInput!) {
      adminReinstateLicenseKey(input: $input) {
        changed
        replayed
        licenseKey { id status priorStatus }
      }
    }
"""


def _gql(client, query, variables, *, permissions="", actor_id="staff_billing_1", staff=True):
    headers = {}
    if staff:
        headers = {
            "HTTP_X_SELAHCUE_ACTOR_KIND": "staff",
            "HTTP_X_SELAHCUE_ACTOR_ID": actor_id,
            "HTTP_X_SELAHCUE_STAFF_PERMISSIONS": permissions,
        }
    return client.post(
        "/graphql/admin",
        data=json.dumps({"query": query, "variables": variables}),
        content_type="application/json",
        **headers,
    )


def _input(key, idem, reason=REASON):
    return {"input": {"idempotencyKey": idem, "licenseKeyId": str(key.pk), "reason": reason}}


def _error_code(response):
    body = response.json()
    assert body.get("errors"), body
    return body["errors"][0]["extensions"]["code"]


def test_graphql_suspend_then_reinstate_happy_path(client):
    key, full_key = _seed_key("gql-happy")
    _drive_to(key, S.EXPIRING)

    suspended = _gql(
        client, SUSPEND_MUTATION, _input(key, "gql-suspend-0001"),
        permissions="suspend_license_key",
    )
    assert suspended.status_code == 200
    body = suspended.json()
    assert "errors" not in body, body
    payload = body["data"]["adminSuspendLicenseKey"]
    assert payload["changed"] is True
    assert payload["licenseKey"]["status"] == "SUSPENDED"
    assert payload["licenseKey"]["priorStatus"] == "EXPIRING"
    assert payload["licenseKey"]["id"] == str(key.pk)
    assert payload["replayed"] is False
    assert full_key not in json.dumps(body)

    reinstated = _gql(
        client, REINSTATE_MUTATION, _input(key, "gql-reinstate-001"),
        permissions="reinstate_license_key",
    )
    body = reinstated.json()
    assert "errors" not in body, body
    payload = body["data"]["adminReinstateLicenseKey"]
    assert payload["changed"] is True
    assert payload["licenseKey"]["status"] == "EXPIRING", "back to the prior status, not ACTIVATED"
    assert payload["licenseKey"]["priorStatus"] == ""


def test_graphql_retry_reports_changed_false(client):
    key, _ = _seed_key("gql-retry")
    variables = _input(key, "gql-retry-request-1")

    first = _gql(client, SUSPEND_MUTATION, variables, permissions="suspend_license_key")
    second = _gql(client, SUSPEND_MUTATION, variables, permissions="suspend_license_key")

    assert first.json()["data"]["adminSuspendLicenseKey"]["changed"] is True
    assert first.json()["data"]["adminSuspendLicenseKey"]["replayed"] is False
    assert second.json()["data"]["adminSuspendLicenseKey"]["changed"] is False
    assert second.json()["data"]["adminSuspendLicenseKey"]["replayed"] is True
    assert _rows(key, action=SUSPEND_ACTION).count() == 1


def test_graphql_reinstate_retry_is_flagged_as_a_replay(client):
    key, _ = _seed_key("gql-reinstate-retry")
    _drive_to(key, S.EXPIRING)
    _suspend(key)
    variables = _input(key, "gql-reinstate-retry-1")

    first = _gql(client, REINSTATE_MUTATION, variables, permissions="reinstate_license_key")
    second = _gql(client, REINSTATE_MUTATION, variables, permissions="reinstate_license_key")

    one = first.json()["data"]["adminReinstateLicenseKey"]
    two = second.json()["data"]["adminReinstateLicenseKey"]
    assert (one["changed"], one["replayed"]) == (True, False)
    assert (two["changed"], two["replayed"]) == (False, True)
    assert two["licenseKey"]["status"] == "EXPIRING"
    assert _rows(key, action=REINSTATE_ACTION).count() == 1


def test_graphql_a_plain_no_op_is_not_flagged_as_a_replay(client):
    """`replayed` means "this request already took effect", not merely "nothing changed". A
    second suspend with a NEW key, and another staff member reusing the first one's key, are
    both plain no-ops on an already-suspended licence: changed=false and replayed=false."""
    key, _ = _seed_key("gql-noop")
    first = _gql(client, SUSPEND_MUTATION, _input(key, "gql-noop-first-key"),
                 permissions="suspend_license_key", actor_id="staff_a")
    assert first.json()["data"]["adminSuspendLicenseKey"]["changed"] is True

    new_key = _gql(client, SUSPEND_MUTATION, _input(key, "gql-noop-second-key"),
                   permissions="suspend_license_key", actor_id="staff_a")
    other_actor = _gql(client, SUSPEND_MUTATION, _input(key, "gql-noop-first-key"),
                       permissions="suspend_license_key", actor_id="staff_b")

    for response in (new_key, other_actor):
        payload = response.json()["data"]["adminSuspendLicenseKey"]
        assert (payload["changed"], payload["replayed"]) == (False, False)
    assert _rows(key, action=SUSPEND_ACTION).count() == 1


def test_graphql_refuses_missing_or_wrong_permission_and_changes_nothing(client):
    key, _ = _seed_key("gql-authz")
    _drive_to(key, S.ACTIVATED)

    for permissions in ("", "revoke_license_key", "reinstate_license_key", "view_customers"):
        response = _gql(client, SUSPEND_MUTATION, _input(key, "gql-denied-request"), permissions=permissions)
        assert _error_code(response) == "PERMISSION_DENIED", permissions
    unauthenticated = _gql(client, SUSPEND_MUTATION, _input(key, "gql-denied-request"), staff=False)
    assert _error_code(unauthenticated) == "UNAUTHENTICATED"

    assert _fresh(key).status == S.ACTIVATED
    assert _rows(key, action=SUSPEND_ACTION).count() == 0
    # Reinstate is gated just as hard, including against the suspend permission.
    _suspend(key)
    response = _gql(client, REINSTATE_MUTATION, _input(key, "gql-denied-reinst"), permissions="suspend_license_key")
    assert _error_code(response) == "PERMISSION_DENIED"
    assert _fresh(key).status == S.SUSPENDED


def test_graphql_a_customer_session_cannot_suspend(client):
    """A customer-kind actor (the header bridge allows any kind) is refused outright."""
    key, _ = _seed_key("gql-customer")
    response = client.post(
        "/graphql/admin",
        data=json.dumps({"query": SUSPEND_MUTATION, "variables": _input(key, "gql-customer-req-1")}),
        content_type="application/json",
        HTTP_X_SELAHCUE_ACTOR_KIND="customer",
        HTTP_X_SELAHCUE_ACTOR_ID="cust_1",
        HTTP_X_SELAHCUE_ORG_ID=str(key.customer_id),
        HTTP_X_SELAHCUE_STAFF_PERMISSIONS="suspend_license_key",
    )
    assert _error_code(response) == "PERMISSION_DENIED"
    assert _fresh(key).status == S.ISSUED


def test_graphql_unknown_licence_is_not_found_and_a_refusal_never_names_internals(client):
    key, full_key = _seed_key("gql-notfound")
    ghost = {"input": {"idempotencyKey": "gql-ghost-request-1", "licenseKeyId": "424242", "reason": REASON}}
    response = _gql(client, SUSPEND_MUTATION, ghost, permissions="suspend_license_key")
    assert _error_code(response) == "NOT_FOUND"
    assert response.json()["errors"][0]["message"] == "The requested resource was not found."

    _drive_to(key, S.REVOKED)
    refused = _gql(client, SUSPEND_MUTATION, _input(key, "gql-refused-req-1"), permissions="suspend_license_key")
    assert _error_code(refused) == "CONFLICT"
    text = refused.content.decode()
    assert "REVOKED" not in text and "legal" not in text, "the refusal detail stays server-side"
    assert full_key not in text and key.secret_hash not in text


def test_graphql_a_refused_suspend_over_http_leaves_its_denied_row(client):
    """The durability requirement end to end: through the real view, not just the service. If
    anything in the request path wrapped the resolver in a transaction this row would be gone
    (or the guard would have refused the call before it got here)."""
    key, _ = _seed_key("gql-durable")
    _drive_to(key, S.REVOKED)

    response = _gql(client, SUSPEND_MUTATION, _input(key, "gql-durable-req-1"), permissions="suspend_license_key")

    assert _error_code(response) == "CONFLICT"
    denied = _rows(key, result=AuditResult.DENIED).get()
    assert denied.actor_id == "staff_billing_1" and denied.request_id == "gql-durable-req-1"
    assert denied.after["requested_status"] == "SUSPENDED"


@pytest.mark.parametrize(
    "variables",
    [
        {"input": {"idempotencyKey": "gql-no-reason-req1", "licenseKeyId": "1"}},
        {"input": {"idempotencyKey": "gql-no-reason-req1", "licenseKeyId": "1", "reason": None}},
        {"input": {"licenseKeyId": "1", "reason": REASON}},
    ],
    ids=["reason-omitted", "reason-null", "idempotency-key-omitted"],
)
def test_graphql_requires_the_reason_and_the_key_in_the_schema_itself(client, variables):
    response = _gql(client, SUSPEND_MUTATION, variables, permissions="suspend_license_key")
    assert _error_code(response) == "VALIDATION_FAILED"
    assert AuditEvent.objects.filter(action=SUSPEND_ACTION).count() == 0


def test_graphql_rate_limit_surfaces_as_a_coded_error(client, settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("gql-throttle")
    for n in range(2):
        ok = _gql(client, SUSPEND_MUTATION, _input(key, f"gql-throttle-req-{n}1"), permissions="suspend_license_key")
        assert "errors" not in ok.json()

    limited = _gql(client, SUSPEND_MUTATION, _input(key, "gql-throttle-req-31"), permissions="suspend_license_key")

    assert _error_code(limited) == "RATE_LIMITED"


def test_the_admin_read_type_shows_the_status_and_where_it_will_return_to(client):
    key, _ = _seed_key("gql-read")
    _drive_to(key, S.ACTIVATED)
    _suspend(key)
    query = """
        query { adminCustomers(search: "suspend-church-gql-read", first: 5) {
          nodes { licenseKeys { nodes { id status priorStatus } } } } }
    """

    response = _gql(client, query, {}, permissions="view_customers")

    node = response.json()["data"]["adminCustomers"]["nodes"][0]["licenseKeys"]["nodes"][0]
    assert node == {"id": str(key.pk), "status": "SUSPENDED", "priorStatus": "ACTIVATED"}


# =============================================================================================
# 5. D3 / DEC-010 on real devices: soft suspend
# =============================================================================================
def _activate_over_http(client, full_key, tag):
    body = {
        "idempotency_key": f"suspend-act-{tag}",
        "license_key": full_key,
        "device_fingerprint": f"fp-suspend-{tag}",
        "platform": "macos",
    }
    response = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    return response


def _refresh(client, token):
    return client.post(
        "/v1/license:refresh",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def _manifest(client, token):
    return client.get("/v1/entitlements/manifest", headers={"authorization": f"Bearer {token}"})


@pytest.fixture
def running_device(client):
    """An activated licence with one running device. Returns (key, full_key, token, device)."""
    key, full_key = _seed_key("d3")
    response = _activate_over_http(client, full_key, "d3")
    assert response.status_code == 200, response.content
    payload = response.json()
    device = Device.objects.get(device_public_id=payload["device"]["device_public_id"])
    key.refresh_from_db()
    assert key.status == S.ACTIVATED
    return key, full_key, payload["activation_token"], device


def test_suspension_leaves_every_issued_device_token_valid_through_a_cascade_run(
    client, running_device
):
    """THE D3 assertion: a device already in the building keeps presenting. Mutating the
    suspension to kill tokens (or reverting the cascade scoping) turns this red, with the
    REVOKED sibling below still green."""
    key, _full, token, device = running_device
    _suspend(key)

    killed = cascade_license_revocations()

    assert killed == 0
    stored = DeviceToken.objects.get(device=device)
    assert stored.status == DeviceTokenStatus.ACTIVE
    # The device is still authenticated and the server answers it truthfully.
    refreshed = _refresh(client, token)
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["license"]["status"] == "SUSPENDED"
    assert body["license"]["valid_now"] is False, "commercial surfaces see the suspension"
    assert body["device"]["status"] == "ACTIVE"


def test_suspension_touches_no_device_or_token_row(running_device):
    key, _full, _token, device = running_device
    token_before = DeviceToken.objects.get(device=device)
    snapshot = (token_before.status, token_before.expires_at, token_before.updated_at)
    device_audit_before = AuditEvent.objects.filter(
        target_type__in=("device", "device_token")
    ).count()

    _suspend(key)

    token_after = DeviceToken.objects.get(device=device)
    assert (token_after.status, token_after.expires_at, token_after.updated_at) == snapshot
    assert Device.objects.get(pk=device.pk).status == "ACTIVE"
    assert (
        AuditEvent.objects.filter(target_type__in=("device", "device_token")).count()
        == device_audit_before
    ), "suspending writes no device-level audit row, because it changes no device"


def test_suspended_and_revoked_differ_observably_on_device_tokens(client):
    """Revoke kills, suspend does not — in the same cascade run, over two licences."""
    suspended_key, suspended_full = _seed_key("diff-sus")
    revoked_key, revoked_full = _seed_key("diff-rev")
    tokens = {}
    for name, full in (("sus", suspended_full), ("rev", revoked_full)):
        response = _activate_over_http(client, full, f"diff-{name}")
        assert response.status_code == 200, response.content
        tokens[name] = Device.objects.get(
            device_public_id=response.json()["device"]["device_public_id"]
        )
    _suspend(suspended_key)
    apply_license_status_transition(
        revoked_key,
        to_status=S.REVOKED,
        actor=ActorContext(kind=ActorKind.STAFF, actor_id="staff_revoker"),
        reason="Chargeback received; revoking the licence.",
        request_id="diff-revoke-request",
    )

    changed = cascade_license_revocations()

    assert changed == 1, "exactly the REVOKED licence's token was stripped"
    assert DeviceToken.objects.get(device=tokens["sus"]).status == DeviceTokenStatus.ACTIVE
    assert DeviceToken.objects.get(device=tokens["rev"]).status == DeviceTokenStatus.REVOKED


def test_a_suspended_licence_refuses_a_new_activation_with_a_coded_error(client, running_device):
    key, full_key, _token, _device = running_device
    _suspend(key)
    devices_before = Device.objects.filter(license_key=key).count()

    response = _activate_over_http(client, full_key, "d3-second-device")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "POLICY_DENIED"
    assert Device.objects.filter(license_key=key).count() == devices_before, "no device created"
    assert _fresh(key).status == S.SUSPENDED


def test_a_suspended_licence_refuses_manifest_issuance_and_reinstatement_restores_it(
    client, running_device
):
    key, _full, token, _device = running_device
    assert _manifest(client, token).status_code == 200
    _suspend(key)

    refused = _manifest(client, token)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "POLICY_DENIED"

    _reinstate(key)

    restored = _manifest(client, token)
    assert restored.status_code == 200, restored.content
    payload = verify_envelope(
        restored.json(), public_key=load_signing_key(TEST_SEED_B64).public_key()
    )
    assert payload["license_status"] == "ACTIVATED"
    assert payload["license_valid_now"] is True


@pytest.mark.parametrize("source", [S.ACTIVATED, S.EXPIRING], ids=lambda s: s.value)
def test_after_reinstatement_the_same_token_works_with_no_reactivation_and_no_slot_used(
    client, source
):
    """FR-510: device recovery is silent. The token never died, so the next refresh simply
    reports the licence valid again — same token, same device row, no seat consumed — for a
    licence reinstated to ACTIVATED and to EXPIRING alike."""
    key, full_key = _seed_key(f"recover-{source.value.lower()}", device_limit=1)
    response = _activate_over_http(client, full_key, f"recover-{source.value.lower()}")
    assert response.status_code == 200
    token = response.json()["activation_token"]
    if source is S.EXPIRING:
        apply_license_status_transition(
            key, to_status=S.EXPIRING, actor=_staff(), reason="Renewal window opened.",
            request_id="recover-expiring-01",
        )
    _suspend(key)
    assert _refresh(client, token).json()["license"]["valid_now"] is False
    devices_before = list(Device.objects.filter(license_key=key).values_list("pk", flat=True))
    tokens_before = list(DeviceToken.objects.filter(device__license_key=key).values_list("pk", flat=True))

    _reinstate(key)
    refreshed = _refresh(client, token)

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["license"]["status"] == source.value
    assert body["license"]["valid_now"] is True
    assert body["instances"]["used"] == 1 and body["instances"]["limit"] == 1
    assert list(Device.objects.filter(license_key=key).values_list("pk", flat=True)) == devices_before
    assert list(DeviceToken.objects.filter(device__license_key=key).values_list("pk", flat=True)) == tokens_before
    assert not AuditEvent.objects.filter(action="device_token.reminted").exists()
    # And a one-seat licence can still not take a second device: no slot was freed or burned.
    second = _activate_over_http(client, full_key, "recover-second")
    assert second.status_code == 403


def test_an_already_cached_offline_entitlement_survives_suspension_unchanged(
    client, running_device
):
    """RISK-501, asserted so the deliberate trade-off cannot silently change: a signed
    manifest issued before the suspension still verifies afterwards and still carries the
    licence's own expiry — the server holds no revocation list to claw it back, and
    suspension does not shorten the token that backs it."""
    key, _full, token, device = running_device
    issued = _manifest(client, token).json()
    payload = verify_envelope(issued, public_key=load_signing_key(TEST_SEED_B64).public_key())
    licence_expiry = _fresh(key).expires_at

    _suspend(key)

    # What the suspension must NOT have moved. The envelope itself is a static artefact the
    # server cannot recall, so the live, mutable things that decide how long the device keeps
    # serving are the two expiries below (the first was fixed when it was signed).
    assert payload["expires_at"] == licence_expiry.isoformat()
    assert payload["license_valid_now"] is True, "the cached artefact is a snapshot"
    assert _fresh(key).expires_at == licence_expiry, "suspension does not shorten the window"
    token_row = DeviceToken.objects.get(device=device)
    assert token_row.expires_at == licence_expiry
    assert token_row.status == DeviceTokenStatus.ACTIVE


def test_a_cascade_run_over_a_suspended_licence_is_idempotent_and_writes_no_audit_row(
    running_device,
):
    key, *_ = running_device
    _suspend(key)

    assert cascade_license_revocations() == 0
    assert cascade_license_revocations() == 0
    assert not AuditEvent.objects.filter(action="device_token.revoked_by_cascade").exists()


def test_build_manifest_service_refuses_a_suspended_licence_directly(running_device):
    """The same refusal at the service layer, so a future non-HTTP caller is covered too."""
    key, _full, token, _device = running_device
    _suspend(key)

    with pytest.raises(SafeAPIError) as raised:
        build_entitlement_manifest(token)

    assert raised.value.code == ErrorCode.POLICY_DENIED


# =============================================================================================
# 6. The enforcement point for commercial device calls, and the sweep that keeps it honest
# =============================================================================================
# `authenticate_device_token` checks the token and never the licence, and a suspension no
# longer kills tokens (D3). So nothing but a route's own call to `require_commercial_service`
# stops a suspended licence's device using a commercial surface. These tests make that
# decision impossible to forget: every bearer-token route must declare it, and each
# declaration is checked against what the route actually does.
BEARER_AUTH = "device_token"


def _undeclared_device_token_routes(contracts):
    return [
        contract.path
        for contract in contracts
        if contract.auth_context == BEARER_AUTH and contract.license_gate not in LICENSE_GATES
    ]


def test_every_device_token_route_declares_how_it_treats_a_suspended_licence():
    contracts = desktop_command_contracts()
    bearer_routes = [c for c in contracts if c.auth_context == BEARER_AUTH]
    assert len(bearer_routes) >= 5, "positive control: the sweep found the device-token routes"
    assert _undeclared_device_token_routes(contracts) == []
    assert {c.license_gate for c in bearer_routes} == {
        LICENSE_GATE_COMMERCIAL,
        LICENSE_GATE_ALLOWED_WHILE_SUSPENDED,
    }, "both declarations are in use, so neither is a dead branch of the sweep"
    # The declaration belongs to device-token routes only.
    assert all(c.license_gate == "" for c in contracts if c.auth_context != BEARER_AUTH)


def test_the_sweep_fails_for_a_new_route_that_declares_neither():
    """The sweep must be able to fail: a device-token route added without a decision is
    reported, whether it declares nothing or something unrecognised."""
    contracts = desktop_command_contracts() + (
        CommandEndpointContract("desktop", "v1/ai:complete", "POST", BEARER_AUTH),
        CommandEndpointContract(
            "desktop", "v1/ai:stream", "POST", BEARER_AUTH, license_gate="whatever"
        ),
    )
    assert _undeclared_device_token_routes(contracts) == ["v1/ai:complete", "v1/ai:stream"]


def _v1_urlconf_routes() -> set[str]:
    """Every `v1/` route the URL resolver actually serves, with converters stripped
    (`<str:lease_id>` -> `<lease_id>`) so they compare with the contract table's spelling."""
    found: set[str] = set()

    def walk(patterns, prefix=""):
        for entry in patterns:
            route = prefix + str(entry.pattern)
            if hasattr(entry, "url_patterns"):
                walk(entry.url_patterns, route)
            else:
                found.add(re.sub(r"<\w+:(\w+)>", r"<\1>", route))

    walk(get_resolver().url_patterns)
    return {route for route in found if route.startswith("v1/")}


def _urlconf_routes_without_a_contract(urlconf_routes, contracts) -> list[str]:
    return sorted(urlconf_routes - {contract.path for contract in contracts})


def test_every_v1_route_in_the_urlconf_has_a_contract_entry():
    """The sweeps above read the hand-written contract table, so a route added to
    `platform/urls.py` WITHOUT an entry would escape every one of them (a new device-token
    view with no gate answered 200 for a suspended licence's token in review). This ties the
    two together: the `v1/` routes the resolver serves and the contract paths must be the
    same set, in both directions. It cannot see a route registered outside `v1/`."""
    contracts = desktop_command_contracts()

    assert _urlconf_routes_without_a_contract(_v1_urlconf_routes(), contracts) == []
    assert {c.path for c in contracts} - _v1_urlconf_routes() == set(), (
        "a contract entry names a route the URLconf does not serve"
    )
    assert len(_v1_urlconf_routes()) >= 8, "positive control: the resolver walk found the routes"


def test_the_urlconf_comparison_reports_a_route_that_has_no_contract_entry():
    routes = _v1_urlconf_routes() | {"v1/ai:models"}
    assert _urlconf_routes_without_a_contract(routes, desktop_command_contracts()) == [
        "v1/ai:models"
    ]


def _route_url(path: str) -> str:
    return "/" + path.replace("<lease_id>", "lease-1")


def test_each_declaration_matches_what_the_route_does_for_a_suspended_licence(
    client, running_device
):
    """Commercial routes refuse a suspended licence's device (or are still 501, in which case
    the moment one starts answering it must refuse); allowed routes stay reachable. A route
    declared commercial that answered 200 would fail here."""
    key, _full, token, _device = running_device
    _suspend(key)

    for contract in desktop_command_contracts():
        if contract.auth_context != BEARER_AUTH:
            continue
        response = client.generic(
            contract.method,
            _route_url(contract.path),
            HTTP_AUTHORIZATION=f"Bearer {token}",
            content_type="application/json",
        )
        label = f"{contract.method} {contract.path} ({contract.license_gate})"
        if contract.license_gate == LICENSE_GATE_COMMERCIAL:
            assert response.status_code in (403, 501), f"{label} answered {response.status_code}"
            if response.status_code == 403:
                assert response.json()["error"]["code"] == "POLICY_DENIED", label
        else:
            assert response.status_code in (200, 501), f"{label} answered {response.status_code}"


@pytest.mark.parametrize("status", list(S), ids=lambda s: s.value)
def test_the_enforcement_point_admits_only_activatable_statuses(status):
    now = timezone.now()
    licence = AppLicenseKey(
        status=status, starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=1)
    )

    if status in ACTIVATABLE_KEY_STATUSES:
        require_commercial_service(licence)
    else:
        with pytest.raises(SafeAPIError) as raised:
            require_commercial_service(licence)
        assert raised.value.code == ErrorCode.POLICY_DENIED


@pytest.mark.parametrize(
    ("starts", "ends"),
    [(timedelta(hours=1), timedelta(days=2)), (timedelta(days=-2), timedelta(seconds=-1))],
    ids=["not-started-yet", "already-expired"],
)
def test_the_enforcement_point_also_refuses_outside_the_licence_window(starts, ends):
    now = timezone.now()
    licence = AppLicenseKey(status=S.ACTIVATED, starts_at=now + starts, expires_at=now + ends)

    with pytest.raises(SafeAPIError) as raised:
        require_commercial_service(licence)
    assert raised.value.code == ErrorCode.POLICY_DENIED


# =============================================================================================
# 7. Activations RESUME after reinstatement
# =============================================================================================
def test_a_second_device_is_refused_while_suspended_and_admitted_after_reinstatement(client):
    """With room under the seat limit (2 seats, 1 device) the ONLY thing refusing the second
    device while suspended is the suspension — so this cannot be mistaken for the instance
    limit the way a one-seat licence's refusal could."""
    key, full_key = _seed_key("resume", device_limit=2)
    first = _activate_over_http(client, full_key, "resume-1")
    assert first.status_code == 200

    _suspend(key)
    refused = _activate_over_http(client, full_key, "resume-2")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "POLICY_DENIED"
    assert Device.objects.filter(license_key=key).count() == 1

    _reinstate(key)
    admitted = _activate_over_http(client, full_key, "resume-2")

    assert admitted.status_code == 200, admitted.content
    assert Device.objects.filter(license_key=key).count() == 2


def test_a_never_activated_licence_can_be_suspended_reinstated_and_then_first_activated(client):
    """Suspended from ISSUED, reinstated back to ISSUED, then the FIRST activation: the licence
    ends ACTIVATED with no stale prior status (the schema's check constraint would reject one),
    and the device exists."""
    key, full_key = _seed_key("resume-issued")
    _suspend(key)
    assert _fresh(key).prior_status == "ISSUED"
    refused = _activate_over_http(client, full_key, "resume-issued-1")
    assert refused.status_code == 403
    _reinstate(key)
    assert _fresh(key).status == S.ISSUED

    response = _activate_over_http(client, full_key, "resume-issued-2")

    assert response.status_code == 200, response.content
    stored = _fresh(key)
    assert stored.status == S.ACTIVATED and stored.prior_status == ""
    assert Device.objects.filter(license_key=key).count() == 1


def _org_admin_for(key):
    return ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id="1",
        org_id=str(key.customer_id),
        role="ADMIN",
    )


def test_session_activation_on_a_suspended_licence_is_not_found_and_resumes_after_reinstatement():
    """The signed-in-admin path looks only for ACTIVATABLE licences, so a suspended one is
    simply not found (NOT_FOUND) where the enrollment-key path answers POLICY_DENIED. The
    caller is the organisation's own admin, so it is not a leak, but the desktop cannot tell
    "suspended" from "no licence" here. Behaviour deliberately unchanged; pinned so a change
    is a decision. No device is created while suspended, and activation resumes afterwards."""
    key, _ = _seed_key("session-path", device_limit=2)
    admin = _org_admin_for(key)

    def activate(n):
        return activate_device_with_session(
            admin,
            ActivateDeviceWithSessionData(
                idempotency_key=f"session-path-act-{n:04d}-x",
                device_fingerprint=f"fp-session-path-{n}",
                platform="macos",
            ),
        )

    assert activate(1).created is True
    _suspend(key)
    with pytest.raises(SafeAPIError) as raised:
        activate(2)
    assert raised.value.code == ErrorCode.NOT_FOUND
    assert Device.objects.filter(license_key=key).count() == 1

    _reinstate(key)

    assert activate(3).created is True
    assert Device.objects.filter(license_key=key).count() == 2


# =============================================================================================
# 8. The cascade spares a suspension from an activatable status, and only that
# =============================================================================================
def _activate_and_get_device(client, full_key, tag):
    response = _activate_over_http(client, full_key, tag)
    assert response.status_code == 200, response.content
    payload = response.json()
    return (
        payload["activation_token"],
        Device.objects.get(device_public_id=payload["device"]["device_public_id"]),
    )


def _writer(key, status, request_id, actor_id="staff_cascade_driver"):
    apply_license_status_transition(
        key,
        to_status=status,
        actor=ActorContext(kind=ActorKind.STAFF, actor_id=actor_id),
        reason="Walking the licence for the cascade scoping tests.",
        request_id=request_id,
    )


@pytest.mark.parametrize(
    ("path", "spared"),
    [
        ([], True),
        ([S.EXPIRING], True),
        ([S.CONVERTED], False),
        ([S.EXPIRING, S.EXPIRED], False),
    ],
    ids=["from-activated", "from-expiring", "from-converted", "from-expired"],
)
def test_the_cascade_spares_a_suspended_licences_tokens_only_if_it_came_from_an_activatable_status(
    client, path, spared
):
    """Suspending an EXPIRED or CONVERTED licence must not rescue tokens the cascade would
    have killed: the exemption follows the status the licence was suspended FROM."""
    key, full_key = _seed_key(f"scope-{'-'.join(s.value for s in path) or 'activated'}".lower())
    token, device = _activate_and_get_device(client, full_key, "scope")
    for step, status in enumerate(path):
        _writer(key, status, f"scope-walk-{step}-{status.value.lower()}")
    _suspend(key)

    killed = cascade_license_revocations()

    stored = DeviceToken.objects.get(device=device)
    refreshed = _refresh(client, token)
    if spared:
        assert killed == 0
        assert stored.status == DeviceTokenStatus.ACTIVE
        assert refreshed.status_code == 200
    else:
        assert killed == 1
        assert stored.status == DeviceTokenStatus.REVOKED
        assert refreshed.status_code == 401


def test_a_suspended_licence_that_is_then_revoked_loses_its_tokens_on_the_next_cascade(client):
    key, full_key = _seed_key("susp-then-rev")
    token, device = _activate_and_get_device(client, full_key, "susp-then-rev")
    _suspend(key)
    assert cascade_license_revocations() == 0
    assert _refresh(client, token).status_code == 200

    _writer(key, S.REVOKED, "susp-then-rev-revoke")

    assert _fresh(key).prior_status == "", "revocation clears the suspension bookkeeping"
    assert cascade_license_revocations() == 1
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.REVOKED
    assert _refresh(client, token).status_code == 401


def test_an_expiring_licence_keeps_its_device_through_suspension_and_comes_back_expiring(client):
    key, full_key = _seed_key("expiring-keeps")
    token, device = _activate_and_get_device(client, full_key, "expiring-keeps")
    _writer(key, S.EXPIRING, "expiring-keeps-walk")
    _suspend(key)

    assert cascade_license_revocations() == 0
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.ACTIVE

    _reinstate(key)

    assert _fresh(key).status == S.EXPIRING
    body = _refresh(client, token).json()
    assert body["license"]["status"] == "EXPIRING" and body["license"]["valid_now"] is True


def test_one_cascade_batch_over_suspended_and_revoked_licences_kills_only_the_right_tokens(client):
    spared_key, spared_full = _seed_key("batch-spared")
    revoked_key, revoked_full = _seed_key("batch-revoked")
    converted_key, converted_full = _seed_key("batch-converted")
    _, spared_device = _activate_and_get_device(client, spared_full, "batch-spared")
    _, revoked_device = _activate_and_get_device(client, revoked_full, "batch-revoked")
    _, converted_device = _activate_and_get_device(client, converted_full, "batch-converted")
    _suspend(spared_key)
    _writer(revoked_key, S.REVOKED, "batch-revoke")
    _writer(converted_key, S.CONVERTED, "batch-convert")
    _suspend(converted_key, "batch-susp-converted")

    killed = cascade_license_revocations()

    assert killed == 2
    status_of = lambda device: DeviceToken.objects.get(device=device).status  # noqa: E731
    assert status_of(spared_device) == DeviceTokenStatus.ACTIVE
    assert status_of(revoked_device) == DeviceTokenStatus.REVOKED
    assert status_of(converted_device) == DeviceTokenStatus.REVOKED


# =============================================================================================
# 9. Actor identities that cannot be audited are refused at the boundary
# =============================================================================================
def test_the_actor_id_limit_is_the_audit_column_width():
    assert ACTOR_ID_MAX_LENGTH == AuditEvent._meta.get_field("actor_id").max_length


def test_an_actor_id_longer_than_the_audit_column_is_refused_before_any_write():
    key, _ = _seed_key("actor-long")
    _drive_to(key, S.ACTIVATED)
    rows_before = AuditEvent.objects.count()

    with pytest.raises(SafeAPIError) as raised:
        _suspend(key, actor=_staff(actor_id="s" * (ACTOR_ID_MAX_LENGTH + 1)))

    assert raised.value.code == ErrorCode.UNAUTHENTICATED
    assert _fresh(key).status == S.ACTIVATED
    assert AuditEvent.objects.count() == rows_before


def test_an_actor_id_at_the_limit_still_gets_a_clean_conflict_and_a_durable_denial():
    """The boundary the other side of the refusal above: 128 characters fits the column, so
    an illegal transition by that actor is a CONFLICT with its DENIED row intact (on Postgres
    a wider id lost the row and answered VALIDATION_FAILED)."""
    key, _ = _seed_key("actor-limit")
    _drive_to(key, S.REVOKED)
    actor = _staff(actor_id="s" * ACTOR_ID_MAX_LENGTH)

    with pytest.raises(IllegalLicenseTransition) as raised:
        _suspend(key, actor=actor)

    assert raised.value.code == ErrorCode.CONFLICT
    denied = _rows(key, result=AuditResult.DENIED).get()
    assert denied.actor_id == "s" * ACTOR_ID_MAX_LENGTH


def test_the_header_bridge_drops_an_actor_id_longer_than_the_audit_column(rf):
    """The first of two layers (the second is `require_staff_permission`): the bridge itself
    yields no actor, so no surface ever sees an identity it cannot audit. Asserted directly
    because the GraphQL test below passes on the second layer alone."""
    def request_with(actor_id):
        return rf.post(
            "/graphql/admin",
            HTTP_X_SELAHCUE_ACTOR_KIND="staff",
            HTTP_X_SELAHCUE_ACTOR_ID=actor_id,
            HTTP_X_SELAHCUE_STAFF_PERMISSIONS="suspend_license_key",
        )

    assert actor_from_request(request_with("h" * (ACTOR_ID_MAX_LENGTH + 1))) is None
    at_limit = actor_from_request(request_with("h" * ACTOR_ID_MAX_LENGTH))
    assert at_limit is not None and at_limit.actor_id == "h" * ACTOR_ID_MAX_LENGTH


def test_graphql_refuses_an_over_long_actor_id_header_as_unauthenticated(client):
    key, _ = _seed_key("actor-header")
    too_long = "h" * (ACTOR_ID_MAX_LENGTH + 1)

    response = _gql(
        client, SUSPEND_MUTATION, _input(key, "actor-header-req-1"),
        permissions="suspend_license_key", actor_id=too_long,
    )
    assert _error_code(response) == "UNAUTHENTICATED"
    assert _fresh(key).status == S.ISSUED

    at_limit = _gql(
        client, SUSPEND_MUTATION, _input(key, "actor-header-req-2"),
        permissions="suspend_license_key", actor_id="h" * ACTOR_ID_MAX_LENGTH,
    )
    assert "errors" not in at_limit.json()
    assert _fresh(key).status == S.SUSPENDED


# =============================================================================================
# 10. The payload does not widen what a lifecycle permission can read
# =============================================================================================
def test_a_suspend_only_actor_cannot_read_customer_details_through_the_payload(client):
    """`AdminLicenseKey.customer` has no permission check of its own, so the lifecycle
    mutations return a licence view WITHOUT it. An actor holding only the suspend permission
    (not VIEW_CUSTOMERS) asking for the customer gets a schema error and no customer data."""
    key, _ = _seed_key("no-customer")
    leaking = SUSPEND_MUTATION.replace(
        "licenseKey { id status priorStatus maskedKey }",
        "licenseKey { id customer { name primaryContactEmail country plan } }",
    )

    refused = _gql(
        client, leaking, _input(key, "no-customer-req-1"), permissions="suspend_license_key"
    )

    assert _error_code(refused) == "VALIDATION_FAILED"
    text = refused.content.decode()
    assert "rivercity" not in text and "suspend.example" not in text
    assert "Suspend Church" not in text
    # The same actor's plain mutation still works, and it is the only thing that applies.
    ok = _gql(client, SUSPEND_MUTATION, _input(key, "no-customer-req-2"), permissions="suspend_license_key")
    assert "errors" not in ok.json()
    assert _fresh(key).status == S.SUSPENDED
    # Control: the same actor is refused the customer query itself.
    query = '{ adminCustomers(search: "suspend-church-no-customer", first: 1) { nodes { name } } }'
    denied = _gql(client, query, {}, permissions="suspend_license_key")
    assert _error_code(denied) == "PERMISSION_DENIED"


@pytest.mark.parametrize("mutation", ["suspend", "reinstate"])
@pytest.mark.parametrize("shape", ["direct", "inline-fragment"])
def test_neither_lifecycle_payload_can_be_asked_for_customer_details(client, mutation, shape):
    """The same regression for BOTH payloads, and for the inline-fragment spelling of the ask.
    Widening either payload back to `AdminLicenseKey` would hand a suspend-only or
    reinstate-only actor the customer's contact details, which they cannot otherwise query."""
    key, _ = _seed_key(f"no-customer-{mutation}-{shape}")
    permission = f"{mutation}_license_key"
    if mutation == "reinstate":
        _suspend(key)
    audit_before = AuditEvent.objects.count()
    status_before = _fresh(key).status
    ask = (
        "licenseKey { customer { name primaryContactEmail } }"
        if shape == "direct"
        else "licenseKey { ... on AdminLicenseKey { customer { name primaryContactEmail } } }"
    )
    base = SUSPEND_MUTATION if mutation == "suspend" else REINSTATE_MUTATION
    query = re.sub(r"licenseKey \{[^}]*\}", ask, base, count=1)
    assert "primaryContactEmail" in query, "positive control: the query really asks for the customer"

    refused = _gql(client, query, _input(key, f"no-customer-{mutation}-{shape}"), permissions=permission)

    assert _error_code(refused) == "VALIDATION_FAILED"
    assert "suspend.example" not in refused.content.decode()
    assert "Suspend Church" not in refused.content.decode()
    assert _fresh(key).status == status_before, "the refused query changed nothing"
    assert AuditEvent.objects.count() == audit_before


# =============================================================================================
# 11. The shipped throttle default
# =============================================================================================
def test_the_shipped_throttle_default_allows_thirty_calls_a_minute_and_refuses_the_next():
    """No setting override anywhere: this is the budget production runs with. The module-level
    default and the shipped setting must agree, or one of them is dead."""
    assert django_settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE == (30, 60)
    assert license_services.LIFECYCLE_BUDGET == (30, 60)
    key, _ = _seed_key("shipped-default")
    staff = _staff(actor_id="staff_default_budget")

    for n in range(30):
        suspend_license_key(staff, _suspend_data(key, f"default-budget-{n:04d}-x"))

    with pytest.raises(SafeAPIError) as raised:
        suspend_license_key(staff, _suspend_data(key, "default-budget-0030-x"))
    assert raised.value.code == ErrorCode.RATE_LIMITED
