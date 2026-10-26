"""Staff revoke + extend — FR-505, FR-509, FLOW-504; 86ak1090r (gap G2).

Two mutations on top of the licence state machine, plus the cross-cutting controls that the
state-machine ticket (86ak5mn00) routed here because they need a real staff-facing caller to
be testable:

* AC 8 — the writer announces the wrapped-transaction denial loss (a fail-closed check on
  `connection.in_atomic_block` with a named opt-in);
* AC 9 — audit-payload redaction is depth-bounded (the pure-function half lives in
  `tests/test_redaction_depth_bound.py`; the writer-boundary half is here);
* AC 11 — authorisation is gated BEFORE the writer, with the refusal audited.

Layout, in the order a reviewer will want it:

1. revoke over the service layer — every source status, idempotency, terminality;
2. revoke and the previously dead cascade, end to end with a real device;
3. authorisation for both mutations — who is refused, what is audited, how the audit is bounded;
4. extend over the service layer — every source status, validation, overlap, replay, atomicity;
5. extend and device re-mint (G1) — a lapsed device recovers after the extension;
6. the writer's tripwire (AC 8) and the depth bound at the writer's boundary (AC 9);
7. the GraphQL surface, end to end over HTTP;
8. the status-coverage record (AC 7) and the writer-discipline behaviour (AC 10).

Every test is `transaction=True`. That is not decoration: both mutations REFUSE to run inside
a caller's transaction (a refusal's DENIED audit row would be rolled back with it), and
pytest-django's default per-test wrapper IS such a transaction. The same choice is what makes
"the denial row survives" measurable at all.

Postgres-only behaviour (the real two-caller races, the row-lock ordering) cannot run under
`make api-check`, which is SQLite. What SQLite cannot show is listed in the PR, and the
two-caller tests that CAN run only on Postgres live in `tests/test_concurrency_postgres.py`.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.core.cache import cache
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from licensing_test_support import seat_plan_code
from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import license_allows_commercial_service
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys import services as license_services
from selahcue_api.apps.license_keys import state_machine
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.services import (
    EXTEND_PERMISSION_DENIED_ACTION,
    EXTEND_REFUSED_ACTION,
    EXTENDABLE_SOURCES,
    MAX_EXTENSION_FROM_NOW,
    REVOKE_PERMISSION_DENIED_ACTION,
    ExtendLicenseKeyData,
    GenerateLicenseKeyData,
    ReinstateLicenseKeyData,
    RevokeLicenseKeyData,
    SuspendLicenseKeyData,
    extend_license_key,
    generate_license_key,
    reinstate_license_key,
    revoke_license_key,
    suspend_license_key,
)
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    DELIBERATELY_UNWRITTEN_STATUSES,
    EXTEND_ACTION,
    LEGAL_TRANSITIONS,
    REFUSED_ACTION,
    REVOKE_ACTION,
    IllegalLicenseTransition,
    WrappedTransitionRefused,
    apply_license_status_transition,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.redaction import MAX_PAYLOAD_DEPTH

pytestmark = pytest.mark.django_db(transaction=True)

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

REASON = "Chargeback confirmed with the processor; the key is being killed for fraud."
EXTEND_REASON = "Renewal paid by bank transfer on the 24th; extending by hand until billing lands."
REVOKE_PERMS = frozenset({StaffPermission.REVOKE_LICENSE_KEY})
EXTEND_PERMS = frozenset({StaffPermission.EXTEND_LICENSE_KEY})
BOTH_PERMS = REVOKE_PERMS | EXTEND_PERMS

S = LicenseKeyStatus

# The PRD §13 list ("any -> REVOKED", REVOKED and ARCHIVED terminal, ARCHIVED -> REVOKED
# refused), written out as an INDEPENDENT oracle rather than read back from the production
# table; `test_the_oracle_agrees_with_the_table` ties the two together.
REVOCABLE = [S.ISSUED, S.ACTIVATED, S.EXPIRING, S.EXPIRED, S.SUSPENDED, S.CONVERTED]
NOT_REVOCABLE = [S.ARCHIVED]  # REVOKED itself is the idempotent no-op

# Extend (FR-509): renewal restores ACTIVATED from EXPIRING / EXPIRED, and a licence that was
# never lapsed simply gets a later date. SUSPENDED is a hold to lift first; CONVERTED is
# superseded; REVOKED is permanent; ARCHIVED is retention.
EXTENDABLE = [S.ISSUED, S.ACTIVATED, S.EXPIRING, S.EXPIRED]
NOT_EXTENDABLE = [S.SUSPENDED, S.CONVERTED, S.REVOKED, S.ARCHIVED]

# Shortest legal walk from ISSUED to each status, through the production writer.
PATHS = {
    S.ISSUED: [],
    S.ACTIVATED: [S.ACTIVATED],
    S.EXPIRING: [S.EXPIRING],
    S.EXPIRED: [S.EXPIRING, S.EXPIRED],
    S.SUSPENDED: [S.SUSPENDED],
    S.CONVERTED: [S.ACTIVATED, S.CONVERTED],
    S.REVOKED: [S.REVOKED],
    S.ARCHIVED: [S.REVOKED, S.ARCHIVED],
}


# --- Module-local seeding helpers ---------------------------------------------------------
# The shipped slices each build their own rather than sharing a conftest.py — follow that.
def _staff(permissions=BOTH_PERMS, actor_id="staff_ops_7") -> ActorContext:
    return ActorContext(
        kind=ActorKind.STAFF, actor_id=actor_id, staff_permissions=frozenset(permissions)
    )


def _seed_org(tag) -> CustomerOrg:
    return CustomerOrg.objects.create(
        name=f"Revoke Church {tag}",
        slug=f"revoke-church-{tag}",
        primary_contact_email=f"ops+{tag}@revoke.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )


def _issue(org, tag, *, starts_at, expires_at, device_limit=3):
    result = generate_license_key(
        ActorContext(
            kind=ActorKind.STAFF,
            actor_id="staff_ops_1",
            staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
        ),
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(org.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            plan_code=seat_plan_code(device_limit),
            starts_at=starts_at,
            expires_at=expires_at,
            timezone="Africa/Lagos",
            seat_limit=5,
            territory="NG",
            reason="Seed licence for the revoke/extend battery.",
        ),
    )
    return result.license_key, result.full_key


def _seed_key(tag, *, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key) — a freshly issued, ISSUED licence in a fresh org."""
    now = timezone.now().replace(microsecond=0)
    return _issue(
        _seed_org(tag),
        tag,
        starts_at=starts_at or now - timedelta(days=3),
        expires_at=expires_at or now + timedelta(days=30),
        device_limit=device_limit,
    )


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


def _lapse(key, *, days_ago=1):
    """Move the licence's window into the past WITHOUT touching its status. Writing a date is
    not a status write; the clock job that would do both together does not exist yet."""
    AppLicenseKey.objects.filter(pk=key.pk).update(
        expires_at=timezone.now() - timedelta(days=days_ago)
    )
    key.refresh_from_db()


def _revoke_data(key, idem="revoke-req-00001", reason=REASON):
    return RevokeLicenseKeyData(idempotency_key=idem, license_key_id=str(key.pk), reason=reason)


def _extend_data(key, new_expires_at, idem="extend-req-00001", reason=EXTEND_REASON):
    return ExtendLicenseKeyData(
        idempotency_key=idem,
        license_key_id=str(key.pk),
        new_expires_at=new_expires_at,
        reason=reason,
    )


def _revoke(key, idem="revoke-req-00001", *, actor=None, reason=REASON):
    return revoke_license_key(actor or _staff(), _revoke_data(key, idem, reason))


def _extend(key, new_expires_at, idem="extend-req-00001", *, actor=None, reason=EXTEND_REASON):
    return extend_license_key(
        actor or _staff(), _extend_data(key, new_expires_at, idem, reason)
    )


def _later(days=90):
    return timezone.now().replace(microsecond=0) + timedelta(days=days)


def _rows(key, **filters):
    return AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), **filters
    ).order_by("id")


def _fresh(key):
    key.refresh_from_db()
    return key


def _error(callable_, *args, **kwargs) -> SafeAPIError:
    with pytest.raises(SafeAPIError) as raised:
        callable_(*args, **kwargs)
    return raised.value


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
# 1. Revoke over the service layer
# =============================================================================================
def test_the_oracle_agrees_with_the_table():
    """The lists above are the PRD's §13 reading. They must name every status exactly once and
    agree with what the production table allows — otherwise a status could be added, or an
    edge moved, and every parametrised test below would keep passing over a list that no
    longer describes the system."""
    named = set(REVOCABLE) | set(NOT_REVOCABLE) | {S.REVOKED}
    assert named == set(LicenseKeyStatus)
    assert len(REVOCABLE) + len(NOT_REVOCABLE) + 1 == len(LicenseKeyStatus)
    table_sources = {s for s, targets in LEGAL_TRANSITIONS.items() if S.REVOKED in targets}
    assert table_sources == set(REVOCABLE)

    assert set(EXTENDABLE) | set(NOT_EXTENDABLE) == set(LicenseKeyStatus)
    assert not set(EXTENDABLE) & set(NOT_EXTENDABLE)
    assert set(EXTENDABLE) == set(EXTENDABLE_SOURCES)
    # Where extend needs a STATUS change, the table must already allow it. If someone removes
    # the EXPIRED -> ACTIVATED edge, extend would start refusing a late renewal: fail here,
    # loudly, rather than as a CONFLICT in front of a customer.
    for source in (S.EXPIRING, S.EXPIRED):
        assert S.ACTIVATED in LEGAL_TRANSITIONS[source], source


def test_the_audit_action_names_are_a_contract():
    """Support queries by these, and the retry lookup matches on them: pinned literally."""
    assert REVOKE_ACTION == "license_key.revoked"
    assert EXTEND_ACTION == "license_key.extended"
    assert REVOKE_ACTION == state_machine._default_action(S.REVOKED, S.REVOKED)
    assert REVOKE_PERMISSION_DENIED_ACTION == "license_key.revoke_permission_denied"
    assert EXTEND_PERMISSION_DENIED_ACTION == "license_key.extend_permission_denied"
    assert EXTEND_REFUSED_ACTION == "license_key.extend_refused"
    assert len({REVOKE_ACTION, EXTEND_ACTION, REFUSED_ACTION, EXTEND_REFUSED_ACTION}) == 4


@pytest.mark.parametrize("source", REVOCABLE, ids=lambda s: s.value)
def test_revoke_succeeds_from_every_revocable_status_with_one_complete_audit_row(source):
    key, _ = _seed_key(f"rev-{source.value.lower()}")
    _drive_to(key, source)
    before_rows = _rows(key).count()
    started = timezone.now() - timedelta(seconds=1)

    result = _revoke(key)

    assert result.changed is True
    assert result.from_status == source and result.to_status == S.REVOKED
    stored = AppLicenseKey.objects.get(pk=key.pk)
    assert stored.status == S.REVOKED
    assert stored.prior_status == "", "leaving SUSPENDED clears the recorded prior status"
    assert result.license_key.status == S.REVOKED, "the caller's object is not left stale"

    new_rows = list(_rows(key))[before_rows:]
    assert len(new_rows) == 1, "one transition, one audit row (NFR-506)"
    row = new_rows[0]
    assert row.action == REVOKE_ACTION
    assert row.result == AuditResult.SUCCESS
    assert (row.actor_kind, row.actor_id) == ("staff", "staff_ops_7")
    assert (row.target_type, row.target_id) == (AUDIT_TARGET_TYPE, str(key.pk))
    assert row.reason == REASON
    assert row.request_id == "revoke-req-00001"
    assert row.source_surface == "admin_graphql"
    assert row.before["status"] == source.value
    assert row.after == {"status": "REVOKED", "prior_status": ""}
    assert started <= row.created_at <= timezone.now() + timedelta(seconds=1)


def test_revoking_an_already_revoked_licence_is_a_no_op_with_no_second_audit_row():
    """AC 6: a defined no-op, not a silent second cascade. The cascade is a separate job keyed
    on token state; what this proves is that the MUTATION adds no second transition or row."""
    key, _ = _seed_key("rev-twice")
    _drive_to(key, S.ACTIVATED)
    _revoke(key, "revoke-first-0001")
    rows_before = _rows(key).count()

    # A DIFFERENT key: this is a second staff action, not a retry, so only the writer's
    # "already in the target state" rule can make it harmless.
    again = _revoke(key, "revoke-second-002")

    assert again.changed is False
    assert again.audit_event is None, "a plain no-op is not mistaken for a replay"
    assert (again.from_status, again.to_status) == (S.REVOKED, S.REVOKED)
    assert _rows(key).count() == rows_before
    assert _fresh(key).status == S.REVOKED


def test_a_retry_with_the_same_idempotency_key_reports_the_original_row():
    key, _ = _seed_key("rev-retry")
    _drive_to(key, S.EXPIRING)
    first = _revoke(key, "revoke-retry-0001")

    second = _revoke(key, "revoke-retry-0001")

    assert first.changed is True and second.changed is False
    assert second.audit_event is not None and second.audit_event.pk == first.audit_event.pk
    assert _rows(key, action=REVOKE_ACTION).count() == 1


def test_revoking_an_archived_licence_is_refused_and_the_denial_survives():
    """ARCHIVED -> REVOKED is the one departure from a literal reading of the PRD; the writer
    refuses it. Raised to a caller in autocommit, so the DENIED row committed on its own."""
    key, _ = _seed_key("rev-archived")
    _drive_to(key, S.ARCHIVED)
    rows_before = _rows(key).count()
    assert not connection.in_atomic_block, "the premise: this caller is in autocommit"

    with pytest.raises(IllegalLicenseTransition) as raised:
        _revoke(key)

    assert raised.value.code == ErrorCode.CONFLICT
    assert _fresh(key).status == S.ARCHIVED
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1
    denied = new_rows[0]
    assert denied.result == AuditResult.DENIED and denied.action == REFUSED_ACTION
    assert (denied.actor_kind, denied.actor_id) == ("staff", "staff_ops_7")
    assert denied.after["requested_status"] == "REVOKED"
    assert denied.after["refusal_code"] == "illegal_transition"
    assert not _rows(key, action=REVOKE_ACTION, actor_id="staff_ops_7").exists(), (
        "the seed walk's own REVOKED row is the test driver's; the staff actor produced none"
    )


@pytest.mark.parametrize(
    "target",
    [s for s in LicenseKeyStatus if s not in (S.REVOKED, S.ARCHIVED)],
    ids=lambda s: s.value,
)
def test_revoked_is_terminal_no_mutation_moves_a_licence_out_of_it(target):
    """PRD: "REVOKED is terminal except for ARCHIVED". Written as the invariant a later
    convenience mutation would quietly break, and driven through the production writer."""
    key, _ = _seed_key(f"terminal-{target.value.lower()}")
    _drive_to(key, S.REVOKED)

    with pytest.raises(IllegalLicenseTransition):
        apply_license_status_transition(
            key,
            to_status=target,
            actor=ActorContext(kind=ActorKind.SERVICE, actor_id="test-terminal-probe"),
            reason="Probe: nothing may leave REVOKED but ARCHIVED.",
            request_id=f"terminal-probe-{target.value.lower()}",
        )
    assert _fresh(key).status == S.REVOKED


def test_the_other_mutations_cannot_leave_revoked_either():
    key, _ = _seed_key("terminal-mutations")
    _drive_to(key, S.REVOKED)

    with pytest.raises(SafeAPIError) as extended:
        _extend(key, _later())
    assert extended.value.code == ErrorCode.CONFLICT
    with pytest.raises(IllegalLicenseTransition):
        suspend_license_key(
            _staff({StaffPermission.SUSPEND_LICENSE_KEY}),
            SuspendLicenseKeyData(
                idempotency_key="terminal-suspend-01", license_key_id=str(key.pk), reason=REASON
            ),
        )
    with pytest.raises(IllegalLicenseTransition):
        reinstate_license_key(
            _staff({StaffPermission.REINSTATE_LICENSE_KEY}),
            ReinstateLicenseKeyData(
                idempotency_key="terminal-reinst-01", license_key_id=str(key.pk), reason=REASON
            ),
        )
    stored = _fresh(key)
    assert stored.status == S.REVOKED and stored.prior_status == ""


# --- Revoke: validation changes nothing and writes nothing -------------------------------
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"reason": ""}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "short"}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "x" * 1001}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "bad" + chr(0) + "reason text"}, ErrorCode.VALIDATION_FAILED),
        ({"idempotency_key": ""}, ErrorCode.VALIDATION_FAILED),
        ({"idempotency_key": "too short"}, ErrorCode.VALIDATION_FAILED),
        ({"license_key_id": "999999"}, ErrorCode.NOT_FOUND),
        ({"license_key_id": "abc"}, ErrorCode.NOT_FOUND),
        ({"license_key_id": "-1"}, ErrorCode.NOT_FOUND),
        ({"license_key_id": ""}, ErrorCode.NOT_FOUND),
        ({"license_key_id": "9" * 40}, ErrorCode.NOT_FOUND),
    ],
    ids=[
        "reason-empty", "reason-short", "reason-long", "reason-control-char",
        "idem-empty", "idem-short", "id-unknown", "id-letters", "id-negative", "id-empty",
        "id-huge",
    ],
)
def test_revoke_rejects_bad_input_and_changes_nothing(overrides, expected):
    key, _ = _seed_key("rev-validation")
    _drive_to(key, S.ACTIVATED)
    rows_before = AuditEvent.objects.count()
    base = {"idempotency_key": "revoke-valid-0001", "license_key_id": str(key.pk), "reason": REASON}
    base.update(overrides)

    error = _error(revoke_license_key, _staff(), RevokeLicenseKeyData(**base))

    assert error.code == expected
    assert _fresh(key).status == S.ACTIVATED
    assert AuditEvent.objects.count() == rows_before, "input errors are not audited"


def test_revoke_normalises_the_reason_and_stores_it_bounded():
    key, _ = _seed_key("rev-reason")
    padded = "  Fraud   confirmed\n\tby  the   processor.  "
    _revoke(key, reason=padded)
    assert _rows(key, action=REVOKE_ACTION).get().reason == "Fraud confirmed by the processor."


# --- Reason text: a pasted licence key is refused, never stored ---------------------------
# FLOW-504 is "leaked key kill", so the person typing the reason has the leaked key in front of
# them and pasting it is the natural slip. NFR-508 allows no plaintext licensing credential at
# rest, and the audit trail is append-only, so a key stored there could never be removed.
# Refused rather than redacted: silently rewriting the reason would falsify the record.
def _audit_dump():
    return json.dumps(
        [
            [r.reason, r.before, r.after, r.request_id, r.target_id, r.actor_id, r.action]
            for r in AuditEvent.objects.all()
        ],
        default=str,
    )


@pytest.mark.parametrize("spelling", ["as-issued", "lower-case", "mid-sentence"])
@pytest.mark.parametrize("which", ["revoke", "extend"])
def test_a_reason_containing_a_full_licence_key_is_refused_and_nothing_is_stored(which, spelling):
    key, full_key = _seed_key(f"reason-key-{which}-{spelling}"[:30])
    pasted = {
        "as-issued": full_key,
        "lower-case": full_key.lower(),
        "mid-sentence": f"Leaked on a forum ({full_key}) so we are killing it today.",
    }[spelling]
    reason = pasted if len(pasted) >= 8 else pasted + " padding"
    rows_before = AuditEvent.objects.count()

    if which == "revoke":
        error = _error(_revoke, key, reason=reason)
    else:
        error = _error(_extend, key, _later(), reason=reason)

    assert error.code == ErrorCode.VALIDATION_FAILED
    assert AuditEvent.objects.count() == rows_before
    assert full_key not in _audit_dump() and full_key.lower() not in _audit_dump().lower()
    assert _fresh(key).status == S.ISSUED


def test_a_masked_key_is_fine_in_a_reason_and_is_the_way_to_name_a_licence():
    key, full_key = _seed_key("reason-masked")
    _revoke(key, reason=f"Leaked key {key.masked_key} reported by the customer.")
    assert key.masked_key in _rows(key, action=REVOKE_ACTION).get().reason
    assert full_key not in _audit_dump()


def test_an_unauthorised_callers_pasted_key_is_not_stored_in_the_refusal_row():
    key, full_key = _seed_key("reason-unauthorised")
    actor = ActorContext(kind=ActorKind.DEVICE, actor_id="dev_pasting")

    error = _error(revoke_license_key, actor, _revoke_data(key, reason=f"key is {full_key} ok"))

    assert error.code == ErrorCode.PERMISSION_DENIED
    row = AuditEvent.objects.get(action=REVOKE_PERMISSION_DENIED_ACTION)
    assert row.reason == "" and full_key not in _audit_dump()


# --- Revoke: transaction guard, throttle, writer discipline -----------------------------
def test_revoke_inside_a_transaction_fails_closed_before_changing_anything():
    key, _ = _seed_key("rev-in-atomic")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()

    with transaction.atomic():
        assert _error(_revoke, key).code == ErrorCode.INTERNAL

    assert _fresh(key).status == S.ACTIVATED
    assert _rows(key).count() == rows_before
    assert _revoke(key).changed is True, "positive control: the same call outside the block works"


def test_revoke_suspend_and_extend_draw_on_one_shared_lifecycle_budget(settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("rev-throttle")
    other, _ = _seed_key("rev-throttle-other")
    _drive_to(key, S.ACTIVATED)
    alice = _staff(BOTH_PERMS | {StaffPermission.SUSPEND_LICENSE_KEY}, actor_id="staff_alice")

    suspend_license_key(
        alice,
        SuspendLicenseKeyData(
            idempotency_key="shared-budget-susp-01", license_key_id=str(key.pk), reason=REASON
        ),
    )
    _revoke(key, "shared-budget-rev-01", actor=alice)

    # The third call is refused BEFORE it can act or be judged: an extension that would have
    # been refused as CONFLICT is RATE_LIMITED instead, and no refusal row is written.
    rows_before = _rows(key).count()
    assert _error(_extend, key, _later(), "shared-budget-ext-01", actor=alice).code == (
        ErrorCode.RATE_LIMITED
    )
    assert _error(_extend, other, _later(), "shared-budget-ext-02", actor=alice).code == (
        ErrorCode.RATE_LIMITED
    )
    assert _rows(key).count() == rows_before
    # Another staff member's budget is their own.
    assert _extend(other, _later(), "bobs-own-request-01", actor=_staff(actor_id="staff_bob")).changed


def test_revoke_and_extend_write_through_the_state_machine_not_a_direct_status_write(monkeypatch):
    """The mutations may not assign `.status` themselves (the writer-discipline scan in
    test_license_state_machine.py pins the set of direct-write sites). Proven behaviourally
    too: with the writer replaced, no status moves — and the arguments show what was asked."""
    key, _ = _seed_key("via-writer")
    _drive_to(key, S.EXPIRED)
    _lapse(key)
    calls = []

    def fake_writer(license_key, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("writer reached")

    monkeypatch.setattr(license_services, "apply_license_status_transition", fake_writer)

    with pytest.raises(RuntimeError, match="writer reached"):
        _revoke(key)
    assert calls[0]["to_status"] == S.REVOKED
    assert calls[0]["actor"].actor_id == "staff_ops_7"
    assert calls[0]["request_id"] == "revoke-req-00001"
    assert calls[0]["recognise_retry"] is True

    calls.clear()
    with pytest.raises(RuntimeError, match="writer reached"):
        _extend(key, _later())
    assert calls[0]["to_status"] == S.ACTIVATED
    assert calls[0]["action"] == EXTEND_ACTION
    assert calls[0]["allow_wrapping_transaction"] is True

    stored = _fresh(key)
    assert stored.status == S.EXPIRED, "with the writer out of the way nothing changed the status"
    assert stored.expires_at < timezone.now(), "and the rolled-back extension did not move the date"


# =============================================================================================
# 2. The previously dead cascade now fires
# =============================================================================================
def _activate(client, full_key, *, fingerprint="mac-booth", idem="revoke-act-000001"):
    return client.post(
        "/v1/activations",
        data=json.dumps(
            {
                "idempotency_key": idem,
                "license_key": full_key,
                "device_fingerprint": fingerprint,
                "platform": "macos",
            }
        ),
        content_type="application/json",
    )


REVOKE_MUTATION = """
    mutation Revoke($input: AdminRevokeLicenseKeyInput!) {
      adminRevokeLicenseKey(input: $input) {
        changed
        replayed
        licenseKey { id status priorStatus maskedKey expiresAt deviceLimit }
      }
    }
"""
EXTEND_MUTATION = """
    mutation Extend($input: AdminExtendLicenseKeyInput!) {
      adminExtendLicenseKey(input: $input) {
        changed
        replayed
        licenseKey { id status priorStatus maskedKey expiresAt deviceLimit }
      }
    }
"""


def _gql(client, query, variables, *, permissions="", actor_id="staff_ops_7", staff=True):
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


def _revoke_input(key, idem, reason=REASON):
    return {"input": {"idempotencyKey": idem, "licenseKeyId": str(key.pk), "reason": reason}}


def _extend_input(key, idem, new_expires_at, reason=EXTEND_REASON):
    return {
        "input": {
            "idempotencyKey": idem,
            "licenseKeyId": str(key.pk),
            "newExpiresAt": new_expires_at.isoformat(),
            "reason": reason,
        }
    }


def _error_code(response):
    body = response.json()
    assert body.get("errors"), body
    return body["errors"][0]["extensions"]["code"]


def test_revoking_a_licence_over_graphql_makes_the_cascade_kill_the_device_token(client):
    """AC 1 and the reason this ticket exists: the revocation cascade was correct, tested and
    UNREACHABLE because nothing could produce REVOKED. Here the status is produced by the real
    staff mutation, over HTTP, and the real hourly job then does its work."""
    key, full_key = _seed_key("cascade-live")
    activated = _activate(client, full_key)
    assert activated.status_code == 200, activated.content
    token = DeviceToken.objects.get()
    assert token.status == DeviceTokenStatus.ACTIVE
    assert _fresh(key).status == S.ACTIVATED

    # Control: with the licence healthy the cascade leaves the token alone.
    assert cascade_license_revocations() == 0
    assert DeviceToken.objects.get().status == DeviceTokenStatus.ACTIVE

    response = _gql(
        client, REVOKE_MUTATION, _revoke_input(key, "cascade-live-req-1"),
        permissions="revoke_license_key",
    )
    assert response.status_code == 200 and "errors" not in response.json(), response.content
    assert response.json()["data"]["adminRevokeLicenseKey"]["licenseKey"]["status"] == "REVOKED"
    assert DeviceToken.objects.get().status == DeviceTokenStatus.ACTIVE, (
        "revoking does not kill tokens inline; the hourly cascade does (NFR-503, 65 minutes)"
    )

    assert cascade_license_revocations() == 1
    token = DeviceToken.objects.get()
    assert token.status == DeviceTokenStatus.REVOKED
    cascade_rows = AuditEvent.objects.filter(
        action="device_token.revoked_by_cascade", target_id=str(token.pk)
    )
    assert cascade_rows.count() == 1
    assert "REVOKED" in cascade_rows.get().reason, "the cascade row names the licence status"

    # No second cascade: a re-run finds nothing, and a second revoke is a plain no-op.
    assert cascade_license_revocations() == 0
    again = _gql(
        client, REVOKE_MUTATION, _revoke_input(key, "cascade-live-req-2"),
        permissions="revoke_license_key",
    )
    assert again.json()["data"]["adminRevokeLicenseKey"]["changed"] is False
    assert cascade_license_revocations() == 0
    assert AuditEvent.objects.filter(action="device_token.revoked_by_cascade").count() == 1


def test_a_revoked_licence_refuses_new_activations_immediately(client):
    """FLOW-504: activation refuses at once (the cascade is only the backstop for tokens
    already issued)."""
    key, full_key = _seed_key("cascade-gate")
    _revoke(key)
    refused = _activate(client, full_key, fingerprint="mac-late", idem="revoke-act-000002")
    assert refused.json()["error"]["code"] == "POLICY_DENIED"
    assert not DeviceToken.objects.exists()
    assert license_allows_commercial_service(_fresh(key)) is False


def test_revoking_from_suspended_removes_the_protection_suspension_gave_the_tokens(client):
    """D3 / DEC-010: a SUSPENDED licence's tokens survive the cascade; a REVOKED licence's do
    not. Revoking a suspended licence is how an unpaid hold becomes a kill."""
    key, full_key = _seed_key("cascade-susp")
    assert _activate(client, full_key).status_code == 200
    suspend_license_key(
        _staff({StaffPermission.SUSPEND_LICENSE_KEY}),
        SuspendLicenseKeyData(
            idempotency_key="cascade-susp-hold-1", license_key_id=str(key.pk), reason=REASON
        ),
    )
    assert cascade_license_revocations() == 0, "suspension is soft: the token survives"

    _revoke(key)

    assert cascade_license_revocations() == 1
    assert DeviceToken.objects.get().status == DeviceTokenStatus.REVOKED


# =============================================================================================
# 3. Authorisation: gated before the writer, refusal audited, audit bounded (AC 2, AC 11)
# =============================================================================================
MUTATIONS = {
    "revoke": (
        lambda key, actor, idem="authz-request-0001": revoke_license_key(
            actor, _revoke_data(key, idem)
        ),
        StaffPermission.REVOKE_LICENSE_KEY,
        REVOKE_PERMISSION_DENIED_ACTION,
    ),
    "extend": (
        lambda key, actor, idem="authz-request-0001": extend_license_key(
            actor, _extend_data(key, _later(), idem)
        ),
        StaffPermission.EXTEND_LICENSE_KEY,
        EXTEND_PERMISSION_DENIED_ACTION,
    ),
}


def _unauthorised_actors(permission):
    others = frozenset(p for p in StaffPermission if p is not permission)
    return {
        "staff-no-permissions": ActorContext(kind=ActorKind.STAFF, actor_id="staff_nobody"),
        "staff-every-other-permission": ActorContext(
            kind=ActorKind.STAFF, actor_id="staff_other", staff_permissions=others
        ),
        # The header bridge lets any kind carry a permission list; the KIND is what refuses.
        "customer-with-the-permission": ActorContext(
            kind=ActorKind.CUSTOMER, actor_id="cust_1", staff_permissions=frozenset({permission})
        ),
        "device-with-the-permission": ActorContext(
            kind=ActorKind.DEVICE, actor_id="dev_1", staff_permissions=frozenset({permission})
        ),
        "service-with-the-permission": ActorContext(
            kind=ActorKind.SERVICE, actor_id="job_1", staff_permissions=frozenset({permission})
        ),
    }


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_an_unauthorised_actor_is_refused_and_no_transition_occurs(which):
    call, permission, denied_action = MUTATIONS[which]
    for index, (label, actor) in enumerate(_unauthorised_actors(permission).items()):
        key, _ = _seed_key(f"authz-{which}-{index}")
        _drive_to(key, S.ACTIVATED)
        expires_before = _fresh(key).expires_at
        status_rows = AuditEvent.objects.exclude(action=denied_action).count()

        error = _error(call, key, actor)

        assert error.code == ErrorCode.PERMISSION_DENIED, label
        stored = _fresh(key)
        assert stored.status == S.ACTIVATED, label
        assert stored.expires_at == expires_before, label
        assert AuditEvent.objects.exclude(action=denied_action).count() == status_rows, (
            f"{label}: nothing but the refusal row may be written"
        )


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_the_gate_runs_before_the_writer_and_before_any_lookup(which, monkeypatch):
    """The ordering AC 11 asks for, proven by making everything past the gate explode: the
    refusal must be reached without touching the licence table or the writer."""
    call, permission, _ = MUTATIONS[which]
    key, _ = _seed_key(f"authz-order-{which}")

    def boom(*args, **kwargs):
        raise AssertionError("reached past the permission gate")

    monkeypatch.setattr(license_services, "apply_license_status_transition", boom)
    monkeypatch.setattr(license_services, "_get_license_key_or_not_found", boom)
    monkeypatch.setattr(license_services, "_enforce_lifecycle_budget", boom)

    actor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_nobody")
    assert _error(call, key, actor).code == ErrorCode.PERMISSION_DENIED


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_the_unauthorised_answer_is_identical_for_an_existing_and_a_missing_licence(which):
    """No oracle on which licence ids exist, for an actor who may not know."""
    call, permission, _ = MUTATIONS[which]
    real, _ = _seed_key(f"authz-oracle-{which}")
    ghost = AppLicenseKey(pk=987654)
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_nobody")

    one, two = _error(call, real, actor), _error(call, ghost, actor, "authz-request-0002")

    assert (one.code, one.message) == (two.code, two.message)


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_a_refusal_for_an_authenticated_actor_writes_one_denied_audit_row(which):
    call, permission, denied_action = MUTATIONS[which]
    key, _ = _seed_key(f"authz-audit-{which}")
    actor = ActorContext(kind=ActorKind.CUSTOMER, actor_id="cust_9", org_id=str(key.customer_id))

    _error(call, key, actor, "authz-audit-req-001")

    row = AuditEvent.objects.get(action=denied_action)
    assert row.result == AuditResult.DENIED
    assert (row.actor_kind, row.actor_id) == ("customer", "cust_9")
    assert row.target_type == AUDIT_TARGET_TYPE and row.target_id == str(key.pk)
    assert row.request_id == "authz-audit-req-001"
    assert row.after["required_permission"] == permission.value
    assert row.after["refusal_code"] == "permission_denied"
    assert row.created_at is not None
    assert row.source_surface == "admin_graphql"


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_an_unauthenticated_caller_is_told_so_and_nothing_is_written(which):
    """No identity, nothing to attribute the row to: refused as UNAUTHENTICATED, not audited."""
    call, permission, _ = MUTATIONS[which]
    key, _ = _seed_key(f"authz-anon-{which}")
    rows_before = AuditEvent.objects.count()

    assert _error(call, key, None).code == ErrorCode.UNAUTHENTICATED
    too_long = ActorContext(
        kind=ActorKind.STAFF, actor_id="x" * 500, staff_permissions=frozenset({permission})
    )
    assert _error(call, key, too_long).code == ErrorCode.UNAUTHENTICATED

    assert AuditEvent.objects.count() == rows_before


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_hostile_input_from_an_unauthorised_actor_cannot_bloat_or_break_the_audit_row(which):
    """The refusal row is written for a caller we do not trust. Everything it records from the
    request is validated or replaced, never stored as sent."""
    call, permission, denied_action = MUTATIONS[which]
    actor = ActorContext(kind=ActorKind.DEVICE, actor_id="dev_hostile")
    key, _ = _seed_key(f"authz-hostile-{which}")
    nasty = ExtendLicenseKeyData if which == "extend" else RevokeLicenseKeyData
    kwargs = {
        "idempotency_key": "k" * 5000,
        "license_key_id": "1" * 5000 + chr(0),
        "reason": "r" * 1_000_000,
    }
    if which == "extend":
        kwargs["new_expires_at"] = _later()
    function = extend_license_key if which == "extend" else revoke_license_key

    assert _error(function, actor, nasty(**kwargs)).code == ErrorCode.PERMISSION_DENIED

    row = AuditEvent.objects.get(action=denied_action)
    assert len(row.reason) <= 1000
    assert len(row.target_id) <= 128 and len(row.request_id) <= 128
    assert chr(0) not in row.target_id + row.request_id + row.reason
    assert row.reason == "", "an unvalidated free-text reason is not stored from an untrusted caller"


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_the_refusal_audit_is_bounded_per_actor(which, settings):
    """An unauthorised caller must not be able to grow the audit table without limit by
    hammering a refused call. Past the budget the call is STILL refused; it just stops
    producing rows."""
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT = (3, 60)
    call, permission, denied_action = MUTATIONS[which]
    key, _ = _seed_key(f"authz-bound-{which}")
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_hammer")

    for n in range(12):
        assert _error(call, key, actor, f"hammer-request-{n:04d}").code == ErrorCode.PERMISSION_DENIED

    assert AuditEvent.objects.filter(action=denied_action).count() == 3

    # Another identity's budget is its own, so one noisy account cannot silence another's trail.
    other = ActorContext(kind=ActorKind.STAFF, actor_id="staff_quiet")
    _error(call, key, other, "quiet-request-0001")
    assert AuditEvent.objects.filter(action=denied_action).count() == 4


@pytest.mark.parametrize("which", sorted(MUTATIONS))
def test_the_refusal_audit_has_a_global_cap_too(which, settings):
    """Per-actor alone is not a bound when actor ids are free to vary."""
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT = (100, 60)
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT_GLOBAL = (4, 60)
    call, permission, denied_action = MUTATIONS[which]
    key, _ = _seed_key(f"authz-global-{which}")

    for n in range(10):
        actor = ActorContext(kind=ActorKind.CUSTOMER, actor_id=f"cust_{n}")
        assert _error(call, key, actor, f"global-request-{n:04d}").code == ErrorCode.PERMISSION_DENIED

    assert AuditEvent.objects.filter(action=denied_action).count() == 4


def test_a_failure_to_write_the_refusal_row_never_turns_the_refusal_into_a_success(monkeypatch):
    """The refusal is the control; the row is the record of it. If the record cannot be
    written, the caller is still refused (and the failure is logged)."""
    key, _ = _seed_key("authz-audit-fails")
    _drive_to(key, S.ACTIVATED)

    def broken(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(license_services, "record_audit_event", broken)
    actor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_nobody")

    assert _error(revoke_license_key, actor, _revoke_data(key)).code == ErrorCode.PERMISSION_DENIED
    assert _fresh(key).status == S.ACTIVATED


def test_the_unauthorised_answer_does_not_leak_a_transaction_complaint():
    """Order matters: a caller who may not revoke is told so, not told about transactions."""
    key, _ = _seed_key("authz-in-atomic")
    with transaction.atomic():
        assert _error(revoke_license_key, _staff(set()), _revoke_data(key)).code == (
            ErrorCode.PERMISSION_DENIED
        )


def test_refused_callers_cannot_spend_a_staff_members_lifecycle_budget(settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (2, 60)
    key, _ = _seed_key("authz-budget")
    impostor = ActorContext(kind=ActorKind.STAFF, actor_id="staff_alice")  # no permissions

    for n in range(10):
        assert _error(revoke_license_key, impostor, _revoke_data(key, f"impostor-req-{n:04d}")).code == (
            ErrorCode.PERMISSION_DENIED
        )

    assert _revoke(key, "alice-real-request", actor=_staff(actor_id="staff_alice")).changed is True


# =============================================================================================
# 4. Extend over the service layer
# =============================================================================================
def _moved_expiry_row(key):
    return _rows(key, action=EXTEND_ACTION).get()


@pytest.mark.parametrize("source", EXTENDABLE, ids=lambda s: s.value)
def test_extend_moves_the_date_and_returns_a_lapsed_licence_to_an_activatable_status(source):
    key, _ = _seed_key(f"ext-{source.value.lower()}")
    _drive_to(key, source)
    lapsed = source in (S.EXPIRING, S.EXPIRED)
    if lapsed:
        _lapse(key)
        assert license_allows_commercial_service(_fresh(key)) is False
    old_expiry = _fresh(key).expires_at
    new_expiry = _later(90)
    rows_before = _rows(key).count()
    expected_status = S.ACTIVATED if lapsed else source

    result = _extend(key, new_expiry)

    assert result.changed is True
    assert (result.from_status, result.to_status) == (source, expected_status)
    stored = AppLicenseKey.objects.get(pk=key.pk)
    assert stored.status == expected_status
    assert stored.expires_at == new_expiry
    assert stored.prior_status == ""
    # The object handed back reflects the committed write, not the stale pre-extension row.
    assert result.license_key.status == expected_status
    assert result.license_key.expires_at == new_expiry
    assert license_allows_commercial_service(stored) is True, "a device can be activated again"

    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1, "one extension, one audit row (NFR-506)"
    row = new_rows[0]
    assert row.action == EXTEND_ACTION and row.result == AuditResult.SUCCESS
    assert (row.actor_kind, row.actor_id) == ("staff", "staff_ops_7")
    assert row.reason == EXTEND_REASON and row.request_id == "extend-req-00001"
    assert row.before == {
        "status": source.value,
        "prior_status": "",
        "expires_at": old_expiry.isoformat(),
    }
    assert row.after == {
        "status": expected_status.value,
        "prior_status": "",
        "expires_at": new_expiry.isoformat(),
    }
    assert (row.target_type, row.target_id) == (AUDIT_TARGET_TYPE, str(key.pk))


def test_extending_an_issued_licence_does_not_pretend_it_was_activated():
    """A never-activated licence keeps ISSUED: extend moves a date, it does not activate."""
    key, _ = _seed_key("ext-issued-stays")
    assert _extend(key, _later()).to_status == S.ISSUED
    assert _fresh(key).status == S.ISSUED


@pytest.mark.parametrize("source", NOT_EXTENDABLE, ids=lambda s: s.value)
def test_extend_refuses_a_status_it_may_not_move_and_the_denial_survives(source):
    key, _ = _seed_key(f"extdeny-{source.value.lower()}")
    _drive_to(key, source)
    before = _fresh(key)
    rows_before = _rows(key).count()
    assert not connection.in_atomic_block, "the premise: this caller is in autocommit"

    error = _error(_extend, key, _later())

    assert error.code == ErrorCode.CONFLICT
    stored = _fresh(key)
    assert (stored.status, stored.prior_status, stored.expires_at) == (
        before.status, before.prior_status, before.expires_at
    ), "a refused extension changes nothing"
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1, "exactly one row, and it is the DENIED one"
    denied = new_rows[0]
    assert denied.result == AuditResult.DENIED and denied.action == EXTEND_REFUSED_ACTION
    assert (denied.actor_kind, denied.actor_id) == ("staff", "staff_ops_7")
    assert denied.reason == EXTEND_REASON and denied.request_id == "extend-req-00001"
    assert denied.before["status"] == source.value
    assert denied.after["refusal_code"] == "status_not_extendable"
    assert denied.after["requested_expires_at"]
    assert not _rows(key, action=EXTEND_ACTION).exists()


def test_a_suspended_licence_is_reinstated_first_and_then_extended():
    """The workflow the refusal above points at, so SUSPENDED is not a dead end."""
    key, _ = _seed_key("ext-after-reinstate")
    _drive_to(key, S.EXPIRING)
    suspend_license_key(
        _staff({StaffPermission.SUSPEND_LICENSE_KEY}),
        SuspendLicenseKeyData(
            idempotency_key="ext-flow-suspend-01", license_key_id=str(key.pk), reason=REASON
        ),
    )
    assert _error(_extend, key, _later()).code == ErrorCode.CONFLICT
    reinstate_license_key(
        _staff({StaffPermission.REINSTATE_LICENSE_KEY}),
        ReinstateLicenseKeyData(
            idempotency_key="ext-flow-reinstate-1", license_key_id=str(key.pk), reason=REASON
        ),
    )
    assert _fresh(key).status == S.EXPIRING

    result = _extend(key, _later(), "ext-flow-extend-001")

    assert (result.from_status, result.to_status) == (S.EXPIRING, S.ACTIVATED)


# --- Extend: input validation -----------------------------------------------------------
def _validation_cases():
    now = timezone.now()
    return {
        "naive-datetime": lambda key: (now + timedelta(days=90)).replace(tzinfo=None),
        "equal-to-current": lambda key: key.expires_at,
        "earlier-than-current": lambda key: key.expires_at - timedelta(days=1),
        "beyond-the-ceiling": lambda key: now + MAX_EXTENSION_FROM_NOW + timedelta(days=2),
        "year-9999": lambda key: datetime(9999, 12, 31, tzinfo=dt_timezone.utc),
        "year-1": lambda key: datetime(1, 1, 2, tzinfo=dt_timezone.utc),
    }


@pytest.mark.parametrize(
    "case",
    sorted(_validation_cases()),
)
def test_extend_rejects_a_bad_date_and_changes_nothing(case):
    key, _ = _seed_key(f"extval-{case}"[:30])
    _drive_to(key, S.ACTIVATED)
    candidate = _validation_cases()[case](_fresh(key))
    rows_before = AuditEvent.objects.count()
    before = _fresh(key)

    error = _error(_extend, key, candidate)

    assert error.code == ErrorCode.VALIDATION_FAILED
    stored = _fresh(key)
    assert (stored.status, stored.expires_at) == (before.status, before.expires_at)
    assert AuditEvent.objects.count() == rows_before, "input errors are not audited"


def test_extend_rejects_a_date_that_is_later_than_the_old_one_but_still_in_the_past():
    """A lapsed licence extended to a date that has also passed would be ACTIVATED with a
    window already over: an activatable status that activates nothing."""
    now = timezone.now().replace(microsecond=0)
    key, _ = _seed_key("extval-past", starts_at=now - timedelta(days=40))
    _drive_to(key, S.EXPIRED)
    _lapse(key, days_ago=10)

    error = _error(_extend, key, timezone.now() - timedelta(days=5))

    assert error.code == ErrorCode.VALIDATION_FAILED
    assert _fresh(key).status == S.EXPIRED


def test_the_ceiling_is_a_sanity_bound_and_a_date_just_inside_it_is_accepted():
    key, _ = _seed_key("extval-ceiling-ok")
    inside = timezone.now() + MAX_EXTENSION_FROM_NOW - timedelta(days=2)
    assert _extend(key, inside).changed is True
    assert _fresh(key).expires_at == inside


def test_the_ceiling_is_about_five_years():
    assert timedelta(days=5 * 365) <= MAX_EXTENSION_FROM_NOW <= timedelta(days=5 * 366 + 1)


def test_extend_accepts_an_aware_datetime_in_any_offset_and_stores_it_as_the_same_instant():
    key, _ = _seed_key("extval-offset")
    lagos = dt_timezone(timedelta(hours=1))
    instant = (timezone.now() + timedelta(days=90)).astimezone(lagos)

    _extend(key, instant)

    assert _fresh(key).expires_at == instant
    assert _rows(key, action=EXTEND_ACTION).get().after["expires_at"] == instant.astimezone(
        dt_timezone.utc
    ).isoformat()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"reason": ""}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "short"}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "x" * 1001}, ErrorCode.VALIDATION_FAILED),
        ({"reason": "bad" + chr(0) + "reason text"}, ErrorCode.VALIDATION_FAILED),
        ({"idempotency_key": ""}, ErrorCode.VALIDATION_FAILED),
        ({"idempotency_key": "too short"}, ErrorCode.VALIDATION_FAILED),
        ({"license_key_id": "999999"}, ErrorCode.NOT_FOUND),
        ({"license_key_id": "abc"}, ErrorCode.NOT_FOUND),
        ({"license_key_id": "9" * 40}, ErrorCode.NOT_FOUND),
    ],
    ids=[
        "reason-empty", "reason-short", "reason-long", "reason-control-char",
        "idem-empty", "idem-short", "id-unknown", "id-letters", "id-huge",
    ],
)
def test_extend_rejects_bad_reason_key_or_id_and_changes_nothing(overrides, expected):
    key, _ = _seed_key("extval-fields")
    rows_before = AuditEvent.objects.count()
    data = {
        "idempotency_key": "extend-valid-00001",
        "license_key_id": str(key.pk),
        "new_expires_at": _later(),
        "reason": EXTEND_REASON,
    }
    data.update(overrides)

    error = _error(extend_license_key, _staff(), ExtendLicenseKeyData(**data))

    assert error.code == expected
    assert AuditEvent.objects.count() == rows_before


def test_extend_inside_a_transaction_fails_closed_before_changing_anything():
    key, _ = _seed_key("ext-in-atomic")
    _drive_to(key, S.EXPIRED)
    old_expiry = _fresh(key).expires_at
    rows_before = _rows(key).count()

    with transaction.atomic():
        assert _error(_extend, key, _later()).code == ErrorCode.INTERNAL

    stored = _fresh(key)
    assert (stored.status, stored.expires_at) == (S.EXPIRED, old_expiry)
    assert _rows(key).count() == rows_before
    assert _extend(key, _later()).changed is True, "positive control: outside the block it works"


# --- Extend: one valid licence per organisation, archived customers ---------------------
def test_extend_refuses_a_date_that_would_overlap_the_organisations_next_licence():
    """The overlap rule (86ak5mn0m) belongs to every writer that moves a licence's dates; its
    own docstring names a future extend as a caller."""
    now = timezone.now().replace(microsecond=0)
    org = _seed_org("ext-overlap")
    first, _ = _issue(org, "ext-overlap-a", starts_at=now - timedelta(days=20),
                      expires_at=now + timedelta(days=10))
    _issue(org, "ext-overlap-b", starts_at=first.expires_at,
           expires_at=first.expires_at + timedelta(days=60))
    expiry_before = first.expires_at
    rows_before = _rows(first).count()

    error = _error(_extend, first, expiry_before + timedelta(days=1))

    assert error.code == ErrorCode.POLICY_DENIED
    assert _fresh(first).expires_at == expiry_before
    denied = list(_rows(first))[rows_before:]
    assert len(denied) == 1 and denied[0].result == AuditResult.DENIED
    assert denied[0].action == EXTEND_REFUSED_ACTION
    assert denied[0].after["refusal_code"] == "overlaps_another_licence"


def test_a_finished_licence_in_the_same_organisation_does_not_block_an_extension():
    now = timezone.now().replace(microsecond=0)
    org = _seed_org("ext-overlap-revoked")
    first, _ = _issue(org, "ext-overlap-ra", starts_at=now - timedelta(days=20),
                      expires_at=now + timedelta(days=10))
    second, _ = _issue(org, "ext-overlap-rb", starts_at=first.expires_at,
                       expires_at=first.expires_at + timedelta(days=60))
    _revoke(second, "overlap-revoke-0001")

    assert _extend(first, first.expires_at + timedelta(days=1)).changed is True


def test_another_organisations_licence_never_blocks_an_extension():
    now = timezone.now().replace(microsecond=0)
    first, _ = _seed_key("ext-other-org-a")
    _issue(_seed_org("ext-other-org-b"), "ext-other-org-b", starts_at=first.expires_at,
           expires_at=first.expires_at + timedelta(days=60))
    assert _extend(first, now + timedelta(days=45)).changed is True


def test_extend_is_refused_for_an_archived_customer_but_revoke_is_not():
    key, _ = _seed_key("ext-archived-customer")
    CustomerOrg.objects.filter(pk=key.customer_id).update(status=CustomerStatus.ARCHIVED)
    rows_before = _rows(key).count()

    assert _error(_extend, key, _later()).code == ErrorCode.POLICY_DENIED
    denied = list(_rows(key))[rows_before:]
    assert len(denied) == 1 and denied[0].after["refusal_code"] == "customer_archived"

    # Killing a licence must stay possible whatever state the customer is in.
    assert _revoke(key).changed is True


# --- Extend: retries, repeats and ordering ----------------------------------------------
def test_a_retry_with_the_same_idempotency_key_applies_nothing_and_reports_the_original():
    key, _ = _seed_key("ext-retry")
    _drive_to(key, S.EXPIRED)
    target = _later(60)
    first = _extend(key, target, "extend-retry-0001")

    second = _extend(key, target, "extend-retry-0001")

    assert first.changed is True and second.changed is False
    assert second.audit_event is not None and second.audit_event.pk == first.audit_event.pk
    assert _rows(key, action=EXTEND_ACTION).count() == 1
    assert _fresh(key).expires_at == target


def test_a_retry_after_another_staff_action_does_not_undo_that_action():
    """The stale-duplicate case: the retry must not re-apply over a revoke made in between."""
    key, _ = _seed_key("ext-retry-after-revoke")
    _drive_to(key, S.EXPIRED)
    first = _extend(key, _later(60), "extend-stale-0001")
    _revoke(key, "revoke-in-between-1")

    replay = _extend(key, _later(60), "extend-stale-0001")

    assert replay.changed is False and replay.audit_event.pk == first.audit_event.pk
    assert _fresh(key).status == S.REVOKED, "the replay did not resurrect the licence"
    assert not _rows(key, result=AuditResult.DENIED).exists()


def test_a_second_extension_with_a_new_key_and_the_same_date_is_rejected():
    """AC 4: safely rejected on repeat, not applied twice."""
    key, _ = _seed_key("ext-repeat")
    target = _later(60)
    _extend(key, target, "extend-repeat-0001")
    rows_before = _rows(key).count()

    assert _error(_extend, key, target, "extend-repeat-0002").code == ErrorCode.VALIDATION_FAILED

    assert _rows(key).count() == rows_before


def test_extensions_chain_forward_each_with_its_own_audit_row():
    key, _ = _seed_key("ext-chain")
    _extend(key, _later(60), "extend-chain-00001")
    _extend(key, _later(120), "extend-chain-00002")
    rows = list(_rows(key, action=EXTEND_ACTION))
    assert len(rows) == 2
    assert rows[1].before["expires_at"] == rows[0].after["expires_at"]


def test_the_same_key_from_another_staff_member_is_a_different_request():
    key, _ = _seed_key("ext-other-actor")
    target = _later(60)
    _extend(key, target, "shared-key-string-1", actor=_staff(actor_id="staff_a"))

    error = _error(_extend, key, target, "shared-key-string-1", actor=_staff(actor_id="staff_b"))

    assert error.code == ErrorCode.VALIDATION_FAILED, "not a replay: a plain repeat, rejected"


def test_extend_then_revoke_keeps_the_new_date_and_revoke_then_extend_is_refused():
    one, _ = _seed_key("ext-order-1")
    _extend(one, _later(60), "order-extend-0001")
    _revoke(one, "order-revoke-00001")
    assert _fresh(one).status == S.REVOKED

    two, _ = _seed_key("ext-order-2")
    _revoke(two, "order-revoke-00002")
    assert _error(_extend, two, _later(60), "order-extend-0002").code == ErrorCode.CONFLICT
    assert _fresh(two).status == S.REVOKED


# --- Extend: atomicity -----------------------------------------------------------------
@pytest.mark.parametrize("source", [S.EXPIRED, S.ACTIVATED], ids=lambda s: s.value)
def test_a_failure_while_moving_the_date_rolls_the_status_and_the_audit_row_back(
    source, monkeypatch
):
    """The status change, the date and the audit row commit together or not at all."""
    key, _ = _seed_key(f"ext-atomic-{source.value.lower()}")
    _drive_to(key, source)
    if source is S.EXPIRED:
        _lapse(key)
    before = _fresh(key)
    rows_before = _rows(key).count()

    def explode(*args, **kwargs):
        raise RuntimeError("database went away while saving the date")

    monkeypatch.setattr(license_services, "_move_expiry", explode)
    with pytest.raises(RuntimeError, match="went away"):
        _extend(key, _later())

    stored = _fresh(key)
    assert (stored.status, stored.expires_at) == (before.status, before.expires_at)
    assert _rows(key).count() == rows_before, "no SUCCESS row survives a failed extension"


def test_if_the_table_ever_loses_the_renewal_edge_the_refusal_is_still_durable(monkeypatch):
    """Extend calls the writer inside its own transaction (the date and the status must commit
    together), which is exactly the shape that loses a DENIED row when the error propagates.
    It catches the refusal inside the block and re-raises after commit, so the compliance
    record survives. Proven by removing the edge from the table."""
    key, _ = _seed_key("ext-table-drift")
    _drive_to(key, S.EXPIRED)
    _lapse(key)
    before = _fresh(key)
    rows_before = _rows(key).count()
    drifted = LEGAL_TRANSITIONS[S.EXPIRED] - {S.ACTIVATED}
    monkeypatch.setitem(LEGAL_TRANSITIONS, S.EXPIRED, drifted)

    with pytest.raises(IllegalLicenseTransition) as raised:
        _extend(key, _later())

    assert raised.value.code == ErrorCode.CONFLICT
    stored = _fresh(key)
    assert (stored.status, stored.expires_at) == (before.status, before.expires_at)
    new_rows = list(_rows(key))[rows_before:]
    assert len(new_rows) == 1 and new_rows[0].result == AuditResult.DENIED
    assert new_rows[0].action == REFUSED_ACTION


# =============================================================================================
# 5. Extend + device re-mint (G1): a lapsed device recovers
# =============================================================================================
def test_a_device_whose_licence_lapsed_recovers_after_the_extension(client):
    """AC 3, spanning this ticket and G1 (86ak108w0, merged): activate, let the licence lapse
    and the cascade kill the token, watch re-activation be refused, extend through the real
    mutation, and re-activate back to a working device with a fresh, future-dated token."""
    now = timezone.now().replace(microsecond=0)
    key, full_key = _seed_key(
        "g1-recover", starts_at=now - timedelta(days=40), expires_at=now + timedelta(minutes=5)
    )
    first = _activate(client, full_key, fingerprint="mac-g1", idem="g1-activate-0001")
    assert first.status_code == 200, first.content
    original_token = first.json()["activation_token"]

    # The window closes. The clock job that would mark EXPIRED is a separate ticket (86ak109dv),
    # so the status is walked through the real writer and the dates aged directly.
    _drive_to(key, S.EXPIRED)
    _lapse(key)
    DeviceToken.objects.filter(device__license_key=key).update(
        issued_at=now - timedelta(days=30), expires_at=now - timedelta(days=1)
    )
    assert cascade_license_revocations() == 1

    refused = _activate(client, full_key, fingerprint="mac-g1", idem="g1-activate-0002")
    assert refused.json()["error"]["code"] == "POLICY_DENIED", "an EXPIRED licence refuses"

    renewed_to = now + timedelta(days=365)
    result = _extend(key, renewed_to)
    assert (result.from_status, result.to_status) == (S.EXPIRED, S.ACTIVATED)

    again = _activate(client, full_key, fingerprint="mac-g1", idem="g1-activate-0003")
    assert again.status_code == 200, again.content
    body = again.json()
    assert body["reminted"] is True and body["created"] is False, "same device, new token"
    assert body["activation_token"] and body["activation_token"] != original_token
    assert datetime.fromisoformat(body["token"]["expires_at"]) == renewed_to
    usable = DeviceToken.objects.filter(
        status=DeviceTokenStatus.ACTIVE, expires_at__gt=timezone.now()
    )
    assert usable.count() == 1, "exactly one live token after the re-mint"
    assert DeviceToken.objects.filter(device__license_key=key).count() == 2


# =============================================================================================
# 6. The writer's tripwire (AC 8) and the depth bound at its boundary (AC 9)
# =============================================================================================
def _writer_call(key, **extra):
    return apply_license_status_transition(
        key,
        to_status=S.SUSPENDED,
        actor=ActorContext(kind=ActorKind.SERVICE, actor_id="test-tripwire-probe"),
        reason="Probe for the wrapped-transaction tripwire.",
        request_id="tripwire-probe-0001",
        **extra,
    )


def test_the_writer_refuses_to_run_inside_a_callers_transaction_without_the_opt_in():
    """AC 8. A refusal's DENIED row is written after the writer's own atomic() unwinds, so a
    caller that wraps the transition and lets the error propagate loses it. There are 17
    atomic() sites in production; a docstring is not a control. The check is mechanical, fails
    closed, and fires BEFORE anything is read or written."""
    key, _ = _seed_key("tripwire")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()

    with transaction.atomic():
        with pytest.raises(WrappedTransitionRefused) as raised:
            _writer_call(key)
        assert raised.value.code == ErrorCode.INTERNAL
        assert isinstance(raised.value, SafeAPIError)

    stored = _fresh(key)
    assert stored.status == S.ACTIVATED and stored.prior_status == ""
    assert _rows(key).count() == rows_before


def test_the_tripwire_has_positive_controls_so_it_is_the_only_thing_that_stopped_the_call():
    key, _ = _seed_key("tripwire-controls")
    _drive_to(key, S.ACTIVATED)

    # In autocommit the same call needs nothing.
    assert not connection.in_atomic_block
    assert _writer_call(key).changed is True

    # Wrapped, with the named opt-in, it runs (here: lifting the suspension the call above made).
    with transaction.atomic():
        wrapped = apply_license_status_transition(
            key,
            to_status=state_machine.PRIOR_STATUS,
            actor=ActorContext(kind=ActorKind.SERVICE, actor_id="test-tripwire-probe"),
            reason="Probe for the wrapped-transaction opt-in.",
            request_id="tripwire-probe-0002",
            allow_wrapping_transaction=True,
        )
    assert wrapped.changed is True and wrapped.to_status == S.ACTIVATED


def test_the_opt_in_is_keyword_only_and_off_by_default():
    import inspect

    parameter = inspect.signature(apply_license_status_transition).parameters[
        "allow_wrapping_transaction"
    ]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False


def test_the_tripwire_logs_an_error_naming_the_cause_and_no_secret(caplog):
    key, full_key = _seed_key("tripwire-log")
    with caplog.at_level(logging.ERROR):
        with transaction.atomic():
            with pytest.raises(WrappedTransitionRefused):
                _writer_call(key)
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "transaction" in messages.lower()
    assert full_key not in messages and key.secret_hash not in messages


def test_the_wrapped_denial_loss_the_tripwire_exists_for_is_real(monkeypatch):
    """Why the tripwire exists, measured: with the opt-in a refusal that propagates out of a
    caller's transaction loses its DENIED row (autocommit keeps it). This is the accepted
    trade-off device activation relies on; it is only reachable by opting in by name."""
    key, _ = _seed_key("tripwire-loss")
    _drive_to(key, S.ARCHIVED)
    before = _rows(key, result=AuditResult.DENIED).count()

    with pytest.raises(IllegalLicenseTransition):
        with transaction.atomic():
            apply_license_status_transition(
                key,
                to_status=S.REVOKED,
                actor=ActorContext(kind=ActorKind.SERVICE, actor_id="test-tripwire-probe"),
                reason="Probe: refusal inside a wrapping transaction.",
                request_id="tripwire-loss-0001",
                allow_wrapping_transaction=True,
            )
    assert _rows(key, result=AuditResult.DENIED).count() == before, "the row rolled back"

    with pytest.raises(IllegalLicenseTransition):
        _revoke(key)
    assert _rows(key, result=AuditResult.DENIED).count() == before + 1, "autocommit keeps it"


def test_first_activation_still_succeeds_once_the_check_exists(client):
    """Device activation is the one deliberate wrapped caller: the status change, the device,
    its token and both audit rows must commit together. Without its opt-in every first
    activation would fail closed (no device, no token) and there would be no warning to read."""
    key, full_key = _seed_key("tripwire-activation")
    assert key.status == S.ISSUED

    response = _activate(client, full_key, fingerprint="mac-trip", idem="trip-activate-0001")

    assert response.status_code == 200, response.content
    assert response.json()["created"] is True
    assert _fresh(key).status == S.ACTIVATED
    first_activation = _rows(key, action="license_key.activated").get()
    assert first_activation.after["device_public_id"].startswith("dev_")
    assert DeviceToken.objects.count() == 1


@pytest.mark.parametrize("extra", ["extra_before", "extra_after"])
def test_a_pathological_extra_payload_is_refused_at_the_writers_boundary(extra):
    """AC 9. Nested far past the recursion limit; must come back as a coded refusal, before the
    lock is taken, never as a RecursionError from inside the transaction."""
    key, _ = _seed_key(f"depth-{extra}")
    _drive_to(key, S.ACTIVATED)
    rows_before = _rows(key).count()
    deep: object = "leaf"
    for _ in range(5000):
        deep = {"k": deep}

    with CaptureQueriesContext(connection) as queries:
        error = _error(_writer_call, key, **{extra: deep})

    assert error.code == ErrorCode.VALIDATION_FAILED
    assert len(queries) == 0, (
        "refused at the boundary means before the transaction and the row lock: not one query "
        f"may have run, found {[q['sql'][:60] for q in queries.captured_queries]}"
    )
    stored = _fresh(key)
    assert stored.status == S.ACTIVATED
    assert _rows(key).count() == rows_before


def test_a_pathological_payload_does_not_destroy_the_denied_row_of_a_later_refusal():
    """The failure the ticket names: on the refusal path a RecursionError destroys the DENIED
    row. Refused at the boundary, the licence is untouched and the NEXT refusal still records."""
    key, _ = _seed_key("depth-refusal")
    _drive_to(key, S.ARCHIVED)
    deep: object = "leaf"
    for _ in range(5000):
        deep = [deep]

    with pytest.raises(SafeAPIError) as raised:
        apply_license_status_transition(
            key,
            to_status=S.REVOKED,
            actor=ActorContext(kind=ActorKind.SERVICE, actor_id="test-depth-probe"),
            reason="Probe: refusal path with a pathological payload.",
            request_id="depth-refusal-0001",
            extra_after={"x": deep},
        )
    assert not isinstance(raised.value, IllegalLicenseTransition)
    assert raised.value.code == ErrorCode.VALIDATION_FAILED

    with pytest.raises(IllegalLicenseTransition):
        _revoke(key)
    assert _rows(key, result=AuditResult.DENIED).count() == 1


def test_a_payload_at_the_depth_bound_still_goes_through_the_writer():
    key, _ = _seed_key("depth-at-bound")
    _drive_to(key, S.ACTIVATED)
    nested: object = "leaf"
    for _ in range(MAX_PAYLOAD_DEPTH):  # the extras mapping is itself the outermost level
        nested = {"k": nested}

    result = _writer_call(key, extra_after=nested)

    assert result.changed is True
    assert _rows(key).order_by("-id").first().after["k"] is not None


# =============================================================================================
# 7. The GraphQL surface, end to end over HTTP
# =============================================================================================
def test_graphql_revoke_happy_path(client):
    key, full_key = _seed_key("gql-revoke", device_limit=5)
    _drive_to(key, S.EXPIRING)

    response = _gql(
        client, REVOKE_MUTATION, _revoke_input(key, "gql-revoke-0001"),
        permissions="revoke_license_key",
    )

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body, body
    payload = body["data"]["adminRevokeLicenseKey"]
    assert (payload["changed"], payload["replayed"]) == (True, False)
    assert payload["licenseKey"]["status"] == "REVOKED"
    assert payload["licenseKey"]["id"] == str(key.pk)
    assert payload["licenseKey"]["deviceLimit"] == 5
    assert full_key not in json.dumps(body)
    row = _rows(key, action=REVOKE_ACTION).get()
    assert (row.actor_id, row.request_id, row.reason) == ("staff_ops_7", "gql-revoke-0001", REASON)


def test_graphql_revoke_retry_is_flagged_and_a_plain_no_op_is_not(client):
    key, _ = _seed_key("gql-revoke-retry")
    variables = _revoke_input(key, "gql-retry-request-1")
    first = _gql(client, REVOKE_MUTATION, variables, permissions="revoke_license_key")
    second = _gql(client, REVOKE_MUTATION, variables, permissions="revoke_license_key")
    new_key = _gql(
        client, REVOKE_MUTATION, _revoke_input(key, "gql-retry-request-2"),
        permissions="revoke_license_key",
    )

    one = first.json()["data"]["adminRevokeLicenseKey"]
    two = second.json()["data"]["adminRevokeLicenseKey"]
    three = new_key.json()["data"]["adminRevokeLicenseKey"]
    assert (one["changed"], one["replayed"]) == (True, False)
    assert (two["changed"], two["replayed"]) == (False, True)
    assert (three["changed"], three["replayed"]) == (False, False)
    assert _rows(key, action=REVOKE_ACTION).count() == 1


def test_graphql_extend_happy_path(client):
    key, full_key = _seed_key("gql-extend", device_limit=5)
    _drive_to(key, S.EXPIRED)
    _lapse(key)
    target = _later(120)

    response = _gql(
        client, EXTEND_MUTATION, _extend_input(key, "gql-extend-0001", target),
        permissions="extend_license_key",
    )

    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body, body
    payload = body["data"]["adminExtendLicenseKey"]
    assert (payload["changed"], payload["replayed"]) == (True, False)
    assert payload["licenseKey"]["status"] == "ACTIVATED"
    assert datetime.fromisoformat(payload["licenseKey"]["expiresAt"]) == target
    assert payload["licenseKey"]["deviceLimit"] == 5
    assert full_key not in json.dumps(body)

    again = _gql(
        client, EXTEND_MUTATION, _extend_input(key, "gql-extend-0001", target),
        permissions="extend_license_key",
    )
    replay = again.json()["data"]["adminExtendLicenseKey"]
    assert (replay["changed"], replay["replayed"]) == (False, True)
    assert _rows(key, action=EXTEND_ACTION).count() == 1


@pytest.mark.parametrize(
    ("query", "make_input", "own_permission", "other_permission"),
    [
        (REVOKE_MUTATION, lambda k, i: _revoke_input(k, i), "revoke_license_key", "extend_license_key"),
        (EXTEND_MUTATION, lambda k, i: _extend_input(k, i, _later()), "extend_license_key", "revoke_license_key"),
    ],
    ids=["revoke", "extend"],
)
def test_graphql_refuses_missing_or_wrong_permission_and_changes_nothing(
    client, query, make_input, own_permission, other_permission
):
    key, _ = _seed_key(f"gql-authz-{own_permission}"[:30])
    _drive_to(key, S.ACTIVATED)
    expiry = _fresh(key).expires_at

    for permissions in ("", other_permission, "suspend_license_key", "view_customers"):
        response = _gql(client, query, make_input(key, "gql-denied-request"), permissions=permissions)
        assert _error_code(response) == "PERMISSION_DENIED", permissions
    unauthenticated = _gql(client, query, make_input(key, "gql-denied-request"), staff=False)
    assert _error_code(unauthenticated) == "UNAUTHENTICATED"

    stored = _fresh(key)
    assert (stored.status, stored.expires_at) == (S.ACTIVATED, expiry)
    assert not _rows(key, action__in=[REVOKE_ACTION, EXTEND_ACTION]).exists()
    denied = AuditEvent.objects.filter(
        action__in=[REVOKE_PERMISSION_DENIED_ACTION, EXTEND_PERMISSION_DENIED_ACTION]
    )
    assert denied.count() == 4, "each authenticated refusal is audited; the anonymous one is not"
    assert {row.target_id for row in denied} == {str(key.pk)}


def test_graphql_a_customer_session_cannot_revoke_or_extend(client):
    key, _ = _seed_key("gql-customer")
    for query, variables, permission in (
        (REVOKE_MUTATION, _revoke_input(key, "gql-customer-req-1"), "revoke_license_key"),
        (EXTEND_MUTATION, _extend_input(key, "gql-customer-req-2", _later()), "extend_license_key"),
    ):
        response = client.post(
            "/graphql/admin",
            data=json.dumps({"query": query, "variables": variables}),
            content_type="application/json",
            HTTP_X_SELAHCUE_ACTOR_KIND="customer",
            HTTP_X_SELAHCUE_ACTOR_ID="cust_1",
            HTTP_X_SELAHCUE_ORG_ID=str(key.customer_id),
            HTTP_X_SELAHCUE_STAFF_PERMISSIONS=permission,
        )
        assert _error_code(response) == "PERMISSION_DENIED"
    assert _fresh(key).status == S.ISSUED


def test_graphql_unknown_licence_is_not_found_and_a_refusal_never_names_internals(client):
    key, full_key = _seed_key("gql-notfound")
    ghost = {"input": {"idempotencyKey": "gql-ghost-request-1", "licenseKeyId": "424242", "reason": REASON}}
    response = _gql(client, REVOKE_MUTATION, ghost, permissions="revoke_license_key")
    assert _error_code(response) == "NOT_FOUND"
    assert response.json()["errors"][0]["message"] == "The requested resource was not found."

    _drive_to(key, S.ARCHIVED)
    refused = _gql(client, REVOKE_MUTATION, _revoke_input(key, "gql-refused-req-1"),
                   permissions="revoke_license_key")
    assert _error_code(refused) == "CONFLICT"
    text = refused.content.decode()
    assert "ARCHIVED" not in text and "legal" not in text, "the refusal detail stays server-side"
    assert full_key not in text and key.secret_hash not in text


def test_graphql_a_refused_revoke_and_a_refused_extend_leave_their_denied_rows(client):
    """The durability requirement end to end, through the real view."""
    archived, _ = _seed_key("gql-durable-a")
    _drive_to(archived, S.ARCHIVED)
    revoked, _ = _seed_key("gql-durable-b")
    _drive_to(revoked, S.REVOKED)

    one = _gql(client, REVOKE_MUTATION, _revoke_input(archived, "gql-durable-req-1"),
               permissions="revoke_license_key")
    two = _gql(client, EXTEND_MUTATION, _extend_input(revoked, "gql-durable-req-2", _later()),
               permissions="extend_license_key")

    assert _error_code(one) == "CONFLICT" and _error_code(two) == "CONFLICT"
    assert _rows(archived, result=AuditResult.DENIED).get().action == REFUSED_ACTION
    denied = _rows(revoked, result=AuditResult.DENIED).get()
    assert denied.action == EXTEND_REFUSED_ACTION and denied.request_id == "gql-durable-req-2"
    assert "REVOKED" not in two.content.decode()


def test_graphql_extend_rejects_a_naive_datetime_and_an_old_one(client):
    key, _ = _seed_key("gql-extend-dates")
    naive = {"input": {"idempotencyKey": "gql-naive-request-1", "licenseKeyId": str(key.pk),
                       "newExpiresAt": "2031-01-01T00:00:00", "reason": EXTEND_REASON}}
    old = _extend_input(key, "gql-old-request-01", key.expires_at - timedelta(days=1))

    assert _error_code(_gql(client, EXTEND_MUTATION, naive, permissions="extend_license_key")) == (
        "VALIDATION_FAILED"
    )
    assert _error_code(_gql(client, EXTEND_MUTATION, old, permissions="extend_license_key")) == (
        "VALIDATION_FAILED"
    )
    assert not _rows(key, action=EXTEND_ACTION).exists()


@pytest.mark.parametrize(
    ("query", "variables"),
    [
        (REVOKE_MUTATION, {"input": {"idempotencyKey": "gql-no-reason-req1", "licenseKeyId": "1"}}),
        (REVOKE_MUTATION, {"input": {"licenseKeyId": "1", "reason": REASON}}),
        (EXTEND_MUTATION, {"input": {"idempotencyKey": "gql-no-reason-req1", "licenseKeyId": "1",
                                     "newExpiresAt": "2031-01-01T00:00:00Z"}}),
        (EXTEND_MUTATION, {"input": {"idempotencyKey": "gql-no-date-req-001", "licenseKeyId": "1",
                                     "reason": REASON}}),
    ],
    ids=["revoke-reason-omitted", "revoke-key-omitted", "extend-reason-omitted", "extend-date-omitted"],
)
def test_graphql_requires_every_field_in_the_schema_itself(client, query, variables):
    response = _gql(client, query, variables, permissions="revoke_license_key,extend_license_key")
    assert _error_code(response) == "VALIDATION_FAILED"
    assert AuditEvent.objects.filter(action__in=[REVOKE_ACTION, EXTEND_ACTION]).count() == 0


@pytest.mark.parametrize("mutation", ["revoke", "extend"])
@pytest.mark.parametrize("shape", ["direct", "inline-fragment"])
def test_neither_payload_can_be_asked_for_customer_details(client, mutation, shape):
    """The payload is the summary type, not `AdminLicenseKey`: that one's `customer` field has
    no permission check of its own, so returning it would hand a revoke-only or extend-only
    actor contact details they cannot otherwise query."""
    import re

    key, _ = _seed_key(f"no-customer-{mutation}-{shape}"[:30])
    permission = f"{mutation}_license_key"
    audit_before = AuditEvent.objects.count()
    ask = (
        "licenseKey { customer { name primaryContactEmail } }"
        if shape == "direct"
        else "licenseKey { ... on AdminLicenseKey { customer { name primaryContactEmail } } }"
    )
    base = REVOKE_MUTATION if mutation == "revoke" else EXTEND_MUTATION
    query = re.sub(r"licenseKey \{[^}]*\}", ask, base, count=1)
    variables = (
        _revoke_input(key, "no-customer-req-001")
        if mutation == "revoke"
        else _extend_input(key, "no-customer-req-001", _later())
    )
    assert "primaryContactEmail" in query, "positive control: the query really asks for it"

    refused = _gql(client, query, variables, permissions=permission)

    assert _error_code(refused) == "VALIDATION_FAILED"
    assert "revoke.example" not in refused.content.decode()
    assert _fresh(key).status == S.ISSUED, "the refused query changed nothing"
    assert AuditEvent.objects.count() == audit_before


def test_the_throttle_is_per_call_through_graphql_too(client, settings):
    settings.SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (1, 60)
    key, _ = _seed_key("gql-throttle")
    first = _gql(client, EXTEND_MUTATION, _extend_input(key, "gql-throttle-req-1", _later(60)),
                 permissions="extend_license_key")
    second = _gql(client, EXTEND_MUTATION, _extend_input(key, "gql-throttle-req-2", _later(90)),
                  permissions="extend_license_key")
    assert "errors" not in first.json()
    assert _error_code(second) == "RATE_LIMITED"


# =============================================================================================
# 8. Status coverage (AC 7) and the writer discipline (AC 10)
# =============================================================================================
def test_the_statuses_a_production_entry_point_writes_and_the_deliberately_unwritten(client):
    """AC 7, in the strict sense. `statuses_without_writer()` is TABLE-derived: a status is
    'written' once an edge targets it, which is true of all eight. This test is about CALLERS:
    it drives every production entry point that exists and records what statuses came out, then
    requires the rest to be documented as deliberately unwritten with the ticket that owns them.
    When the expiry job (86ak109dv) or conversion/archiving land, their author moves a status
    from the documented set to the produced set here and the overlap check forces it."""
    produced: set[LicenseKeyStatus] = set()

    issued, full_key = _seed_key("coverage-issue")
    produced.add(_fresh(issued).status)  # staff issuance seeds ISSUED

    assert _activate(client, full_key, idem="coverage-activate-1").status_code == 200
    produced.add(_fresh(issued).status)  # first device activation -> ACTIVATED

    suspended, _ = _seed_key("coverage-suspend")
    suspend_license_key(
        _staff({StaffPermission.SUSPEND_LICENSE_KEY}),
        SuspendLicenseKeyData(
            idempotency_key="coverage-suspend-01", license_key_id=str(suspended.pk), reason=REASON
        ),
    )
    produced.add(_fresh(suspended).status)  # adminSuspendLicenseKey -> SUSPENDED

    revoked, _ = _seed_key("coverage-revoke")
    _revoke(revoked)
    produced.add(_fresh(revoked).status)  # adminRevokeLicenseKey -> REVOKED

    lapsed, _ = _seed_key("coverage-extend")
    _drive_to(lapsed, S.EXPIRED)  # seeded by the writer: no production caller writes EXPIRED
    _extend(lapsed, _later())
    produced.add(_fresh(lapsed).status)  # adminExtendLicenseKey restores ACTIVATED

    documented = set(DELIBERATELY_UNWRITTEN_STATUSES)
    assert produced == {S.ISSUED, S.ACTIVATED, S.SUSPENDED, S.REVOKED}
    assert produced | documented == set(LicenseKeyStatus), "every status is accounted for"
    assert not produced & documented, (
        "a status is either written by a production entry point or documented as unwritten, "
        "never both: move it when its ticket lands"
    )
    for status, owner in DELIBERATELY_UNWRITTEN_STATUSES.items():
        assert "86ak" in owner and len(owner) > 20, f"{status.value} needs its owning ticket named"
    # The table-level sweep is a separate, weaker claim and stays true.
    assert state_machine.statuses_without_writer() == frozenset()
