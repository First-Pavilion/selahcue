"""The DEC-004 instance limit, and device-token re-mint, under real concurrency.

`activate_device` guards both with select_for_update on the licence row, which SQLite
silently no-ops (has_select_for_update = False). These tests therefore SKIP on SQLite —
they would pass there for the wrong reason and hide the very races they exist to catch.
"""

import random
import threading
import time
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import OperationalError, connection, connections, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from licensing_test_support import issue_key, seat_plan_code, seed_org
from selahcue_api.apps.accounts.models import (
    CustomerOrg,
    CustomerRole,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import (
    Device,
    DeviceStatus,
    DeviceToken,
    DeviceTokenStatus,
)
from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    ActivateDeviceWithSessionData,
    activate_device,
    activate_device_with_session,
    refresh_license,
)
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys import services as license_services
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.services import (
    EXTEND_REFUSED_ACTION,
    ExtendLicenseKeyData,
    ReinstateLicenseKeyData,
    RevokeLicenseKeyData,
    SuspendLicenseKeyData,
    extend_license_key,
    lock_customer_for_key_changes,
    reinstate_license_key,
    revoke_license_key,
    suspend_license_key,
)
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    apply_license_status_transition,
)
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="select_for_update is a no-op on SQLite; this race is only observable on Postgres",
    ),
]


@pytest.fixture(autouse=True)
def _fresh_lifecycle_budget():
    """The lifecycle mutations spend a per-staff throttle budget kept in a process-wide
    cache, and several races here share an actor. Start every test with an empty cache so
    headroom never depends on which tests ran before."""
    cache.clear()
    yield
    cache.clear()


# Module-local seeding helper, copied verbatim from tests/test_entitlement_manifest_slice.py
# (which in turn mirrors tests/test_license_refresh_slice.py). The shipped slices each build
# their own rather than sharing a conftest.py — follow that.
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Manifest Church {tag}",
        slug=f"manifest-church-{tag}",
        primary_contact_email=f"ops+{tag}@manifest.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )
    result = generate_license_key(
        actor,
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            # DEC-014 refuses issuance onto the catalogue's designated fallback, so this
            # seeder names a sellable plan. The lifecycle/transport behaviour these tests
            # assert does not depend on which plan it is.
            plan_code=seat_plan_code(device_limit),
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            territory="NG",
            reason="Pilot for entitlement-manifest tests.",
        ),
    )
    return result.license_key, result.full_key


def _licence_row_waiters():
    """How many backends are parked on a lock inside a licence-row query.

    Matched on the start of the query text and the table name, never on the trailing
    `FOR UPDATE`: `pg_stat_activity.query` is truncated at 1024 bytes and Django's licence
    SELECT is longer than that, so the end of the statement is not reliably visible."""
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT count(*) FROM pg_stat_activity
               WHERE datname = current_database() AND pid <> pg_backend_pid()
                 AND wait_event_type = 'Lock' AND query ILIKE %s""",
            [f"SELECT%{AppLicenseKey._meta.db_table}%"],
        )
        return cursor.fetchone()[0]


def _park_then_release(key, targets, *, one_at_a_time):
    """The park-then-release machinery shared by `_race_behind_row_lock` and
    `_race_in_arrival_order`. Returns (results, errors, waiting): `results` are
    (index, return value) and `errors` are (index, exception), each sorted by the target's
    index; `waiting` is how many callers were provably parked on a lock at release time.

    A third connection holds `FOR UPDATE` on the licence row, the targets are started, and
    this waits (polling `pg_stat_activity`) until they are provably parked. With
    `one_at_a_time` each target is started only once the previous one is parked, so they join
    the lock queue in the order given; otherwise all are started at once.
    """
    holding = threading.Event()
    release = threading.Event()
    results = []
    errors = []

    def hold():
        try:
            with transaction.atomic():
                AppLicenseKey.objects.select_for_update().get(pk=key.pk)
                holding.set()
                release.wait(timeout=60)
        finally:
            connections.close_all()

    def run(index, target):
        try:
            results.append((index, target()))
        except Exception as exc:
            errors.append((index, exc))
        finally:
            connections.close_all()

    def wait_for_waiters(count):
        deadline = time.monotonic() + 15
        while _licence_row_waiters() < count and time.monotonic() < deadline:
            time.sleep(0.02)

    holder = threading.Thread(target=hold)
    holder.start()
    threads = []
    waiting = 0
    try:
        assert holding.wait(30), "the holder never took the licence-row lock"
        for index, target in enumerate(targets):
            thread = threading.Thread(target=run, args=(index, target))
            threads.append(thread)
            thread.start()
            if one_at_a_time:
                wait_for_waiters(index + 1)
        wait_for_waiters(len(targets))
        waiting = _licence_row_waiters()
    finally:
        # Whatever happened above (a failed assertion, an error in the polling query), free
        # the row: otherwise the holder keeps it locked for its full 60 s wait and stalls
        # the next test's teardown.
        release.set()
        holder.join(timeout=60)
        for t in threads:
            t.join(timeout=60)
    assert not holder.is_alive() and not any(t.is_alive() for t in threads), (
        "a caller did not complete once the licence row was released"
    )
    return sorted(results, key=lambda r: r[0]), sorted(errors, key=lambda e: e[0]), waiting


def _race_behind_row_lock(key, targets):
    """Run `targets` concurrently with the overlap at the licence-row lock GUARANTEED.

    A barrier only lines the threads up at the start. Each activation then spends ~0.4 s in
    PBKDF2 before it reaches the lock, so whether two of them actually contend there is down
    to scheduling, and a test built on that passes whether or not the lock exists. Here a
    third connection holds `FOR UPDATE` on the licence row, every target is started, and
    this waits (polling `pg_stat_activity`) until all of them are provably parked on a lock;
    only then is the row released. Returns (errors, waiting): `waiting` is how many were
    parked at release time, for the caller to assert, so that "the race never formed" fails
    loudly instead of reading as a pass.
    """
    _, errors, waiting = _park_then_release(key, targets, one_at_a_time=False)
    return [exc for _, exc in errors], waiting


def _race_in_arrival_order(key, targets):
    """`_race_behind_row_lock`, but the targets are released into the lock queue ONE AT A TIME,
    each parked before the next is started, so the order they join the queue is the order
    given. Returns (results, errors, waiting), indexed by target (see `_park_then_release`).

    What this does and does not control. With TWO waiters, Postgres serves the first parked
    first, which is what lets a test name BOTH outcomes of a two-way race and check each
    against its own expectation. With MORE than two the first is still served first, but the
    rest are woken together and their order is a scheduling race (measured: 6 of 20 inversions
    with six waiters), so a test with three or more callers must assert invariants that hold
    for every order of the later ones, not a particular order.
    """
    return _park_then_release(key, targets, one_at_a_time=True)


def _enroll(full_key, *, idem, fingerprint):
    return lambda: activate_device(
        ActivateDeviceData(
            # Must stay >= 12 chars: validate_idempotency_key rejects anything shorter with
            # VALIDATION_FAILED, which would make BOTH activations fail and the race never run.
            idempotency_key=idem,
            presented_key=full_key,
            device_fingerprint=fingerprint,
            platform="macos",
        )
    )


def _licence_transitions(key):
    """How many ISSUED -> ACTIVATED rows this licence carries."""
    return AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), action="license_key.activated"
    ).count()


@pytest.mark.parametrize(
    "race", [_race_behind_row_lock, _race_in_arrival_order], ids=["all-at-once", "in-arrival-order"]
)
def test_a_polling_error_releases_the_held_licence_row_promptly(monkeypatch, race):
    """If the poll in either helper raises, the holder must be released at once, not left
    holding the licence row for its full 60 s wait (which would stall the next test)."""
    key, full_key = _seed_license_key(tag="pollerror", device_limit=1)

    def broken_poll():
        raise RuntimeError("simulated pg_stat_activity failure")

    monkeypatch.setitem(globals(), "_licence_row_waiters", broken_poll)
    started = time.monotonic()

    with pytest.raises(RuntimeError, match="simulated pg_stat_activity failure"):
        race(key, [_enroll(full_key, idem="poll-error-activation", fingerprint="fp-poll-error")])

    assert time.monotonic() - started < 20, "the holder kept the row locked after a poll error"
    # The row is free again: a NOWAIT lock succeeds instead of raising.
    with transaction.atomic():
        AppLicenseKey.objects.select_for_update(nowait=True).get(pk=key.pk)


def test_concurrent_activations_cannot_exceed_the_device_limit():
    """DEC-004. Two devices race for the one seat of a still-ISSUED licence, both parked on
    the licence-row lock before either is let through (see `_race_behind_row_lock`).

    Removing the activation's outer `select_for_update` fails this deterministically: both
    requests then insert a device before anything serialises them, and the licence ends up
    with two ACTIVE devices on a one-seat plan. The winner's activation is also the
    licence's ONE ISSUED -> ACTIVATED move, and the loser's refusal leaves nothing behind
    (86ak5v7av).
    """
    key, full_key = _seed_license_key(tag="conc", device_limit=1)

    errors, waiting = _race_behind_row_lock(
        key,
        [
            _enroll(full_key, idem=f"conc-activation-{n}", fingerprint=f"fp-conc-{n}")
            for n in range(2)
        ],
    )

    assert waiting == 2, f"both activations should be parked on the licence-row lock: {waiting}"
    active = Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count()
    assert active == 1, f"instance limit exceeded: {active} active devices, errors={errors}"
    assert len(errors) == 1, "exactly one activation should have been rejected"
    assert isinstance(errors[0], SafeAPIError) and errors[0].code == ErrorCode.POLICY_DENIED
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert _licence_transitions(key) == 1


def test_concurrent_remints_leave_exactly_one_live_token():
    """AC5 of 86ak108w0. Two desktops (or one desktop retrying) re-activating the same
    bricked device at the same instant must not each mint a live token — two live
    credentials for one device would defeat the supersede-on-re-mint guarantee that makes a
    replayed pre-renewal token rejectable.

    The serialisation comes from the SAME `select_for_update` on the licence row that guards
    the instance limit, so the loser blocks until the winner has committed its re-mint and
    then sees a healthy token and replays show-once.
    """
    key, full_key = _seed_license_key(tag="remintconc", device_limit=1)

    # One activated device, then age its token so the device is bricked exactly as a lapsed
    # licence would leave it. `issued_at` moves back too: `device_token_expires_after_issue`
    # forbids a token that expires before it was issued.
    activate_device(
        ActivateDeviceData(
            idempotency_key="remint-conc-seed",
            presented_key=full_key,
            device_fingerprint="fp-remint-conc",
            platform="macos",
        )
    )
    stale = timezone.now() - timedelta(days=1)
    DeviceToken.objects.filter(device__license_key=key).update(
        issued_at=stale - timedelta(days=30), expires_at=stale
    )

    results = []
    errors = []
    start = threading.Barrier(2, timeout=30)
    barrier_failures = []

    def remint(n):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            results.append(
                activate_device(
                    ActivateDeviceData(
                        # Distinct idempotency keys: this is the same INSTALL re-enrolling,
                        # which is the known-fingerprint branch, not an idempotent retry.
                        idempotency_key=f"remint-conc-{n}",
                        presented_key=full_key,
                        device_fingerprint="fp-remint-conc",
                        platform="macos",
                    )
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=remint, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert barrier_failures == [], f"the two re-mints never overlapped: {barrier_failures}"
    assert errors == [], f"a re-mint must not race into an error: {errors}"

    live = DeviceToken.objects.filter(
        device__license_key=key, status=DeviceTokenStatus.ACTIVE
    )
    assert live.count() == 1, f"concurrent re-mint produced {live.count()} live tokens"
    assert Device.objects.filter(license_key=key).count() == 1, "no slot was burned"
    # Exactly one caller minted; the other found the fresh token and replayed show-once.
    assert sorted(r.reminted for r in results) == [False, True]
    assert sorted(r.full_token is None for r in results) == [False, True]
    minted = [r.full_token for r in results if r.full_token is not None]
    assert live.get().token_prefix == minted[0][:12]


# --- 86ak5mn00: the lifecycle state machine under a real race ---------------------------
def test_concurrent_transitions_write_exactly_one_audit_row():
    """NFR-506 says 100% of transitions are audited, exactly once. Two staff members (or one
    retrying client) revoking the same licence at the same instant must produce ONE status
    change and ONE audit row — not two rows describing the same ACTIVATED -> REVOKED move.

    The serialisation is the `select_for_update` in `apply_license_status_transition`, which
    makes the loser re-read the row AFTER the winner commits and see REVOKED, turning its
    call into the idempotent replay that writes nothing. Without the lock both callers read
    ACTIVATED, both pass the legality check, and both audit.
    """
    from selahcue_api.apps.audit.models import AuditEvent, AuditResult
    from selahcue_api.apps.license_keys.models import LicenseKeyStatus
    from selahcue_api.apps.license_keys.state_machine import (
        AUDIT_TARGET_TYPE,
        apply_license_status_transition,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind

    key, full_key = _seed_license_key(tag="lifecycleconc", device_limit=1)
    # First activation flips ISSUED -> ACTIVATED, so the race starts from a real status.
    activate_device(
        ActivateDeviceData(
            idempotency_key="lifecycle-conc-seed",
            presented_key=full_key,
            device_fingerprint="fp-lifecycle-conc",
            platform="macos",
        )
    )
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED

    baseline = AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk)
    ).count()

    results = []
    errors = []
    start = threading.Barrier(2, timeout=30)
    barrier_failures = []

    def revoke(n):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            results.append(
                apply_license_status_transition(
                    key,
                    to_status=LicenseKeyStatus.REVOKED,
                    actor=ActorContext(kind=ActorKind.STAFF, actor_id=f"staff_race_{n}"),
                    reason="Chargeback received; revoking the licence.",
                    # Distinct request ids: two genuinely separate staff actions, not one
                    # request retried, so nothing upstream can dedupe them for us.
                    request_id=f"race-revoke-{n}",
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=revoke, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert barrier_failures == [], f"the two revocations never overlapped: {barrier_failures}"
    assert errors == [], f"a legal transition must not race into an error: {errors}"

    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED
    # Exactly one caller transitioned; the other found REVOKED already in effect.
    assert sorted(r.changed for r in results) == [False, True]

    written = (
        AuditEvent.objects.filter(target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk)).count()
        - baseline
    )
    assert written == 1, (
        f"one status change produced {written} audit rows — concurrent callers must not each "
        "audit the same transition (NFR-506)"
    )
    assert (
        AuditEvent.objects.filter(
            target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), result=AuditResult.DENIED
        ).count()
        == 0
    ), "the losing caller replays idempotently; it is not a refusal"


# --- 86ak5v7av: first activation goes through the state machine, under a real race -------
def _run_in_threads(targets):
    """Start every callable at the same instant behind a barrier, join them, and return
    (errors, barrier_failures). A barrier only aligns the START, so this proves nothing about
    contention at a lock: use it only where the property under test does not depend on
    overlap (activations of unrelated licences). Where it does, use `_race_behind_row_lock`.
    A thread still alive after the join timeout fails here, not as a hang."""
    errors = []
    barrier_failures = []
    start = threading.Barrier(len(targets), timeout=30)

    def run(target):
        try:
            start.wait()
        except threading.BrokenBarrierError as exc:
            barrier_failures.append(exc)
            connections.close_all()
            return
        try:
            target()
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(target,)) for target in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "activation did not complete"
    return errors, barrier_failures


def _session_admin(key, *, tag):
    user = CustomerUser.objects.create(
        customer=key.customer,
        email=f"admin+{tag}@conc.example",
        email_fingerprint=f"fp-conc-admin-{tag}",
        password_hash="unused",
        status=CustomerUserStatus.ACTIVE,
        role=CustomerRole.ADMIN,
        created_by_actor_id="test",
        idempotency_key=f"conc-session-user-{tag}",
    )
    return ActorContext(
        kind=ActorKind.CUSTOMER,
        actor_id=str(user.id),
        org_id=str(key.customer_id),
        role=CustomerRole.ADMIN,
    )


def test_concurrent_first_activations_write_exactly_one_licence_transition():
    """Two desktops present the same, still-ISSUED enrollment key and are both parked on the
    licence-row lock before either is let through. The limit allows both devices, but the
    licence moves ISSUED -> ACTIVATED exactly once and that move is audited exactly once.

    What this proves: with the row released, both requests complete without error, both devices
    exist, and one transition row is written. What it does NOT prove, on purpose:

    * It does not guard the activation's outer lock on its own. Either lock alone makes the
      loser re-read ACTIVATED and skip the transition, so removing just the outer lock leaves
      this test green; `test_concurrent_activations_cannot_exceed_the_device_limit` (limit 1,
      so a missing outer lock yields two devices) is the guard for that.
    * It does not guard the state machine's inner lock on its own: on this path that lock is
      redundant, and it is guarded where it is NOT redundant, by
      `test_concurrent_transitions_write_exactly_one_audit_row`.
    * Removing BOTH locks fails the "parked" assertion below, because nothing then waits.
    """
    key, full_key = _seed_license_key(tag="firstconc", device_limit=3)
    assert key.status == LicenseKeyStatus.ISSUED

    errors, waiting = _race_behind_row_lock(
        key,
        [
            _enroll(full_key, idem=f"first-conc-activation-{n}", fingerprint=f"fp-first-conc-{n}")
            for n in range(2)
        ],
    )

    assert waiting == 2, f"both activations should be parked on the licence-row lock: {waiting}"
    assert errors == [], f"both devices fit under the limit; neither may fail: {errors}"
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert Device.objects.filter(license_key=key).count() == 2
    assert _licence_transitions(key) == 1, "one ISSUED -> ACTIVATED move must audit once"


def test_concurrent_first_activations_of_different_licences_each_transition_once():
    """Two churches activating at the same instant share nothing: each licence is locked
    separately, so neither may block, fail or borrow the other's transition. (No lock is
    contended here by design, so the barrier is the right tool.)"""
    key_a, full_key_a = _seed_license_key(tag="diff-a", device_limit=1)
    key_b, full_key_b = _seed_license_key(tag="diff-b", device_limit=1)

    errors, barrier_failures = _run_in_threads(
        [
            # The SAME request id and fingerprint on both: only the licence differs.
            _enroll(full_key, idem="diff-licence-activation", fingerprint="fp-diff-licence")
            for full_key in (full_key_a, full_key_b)
        ]
    )

    assert barrier_failures == [], f"the two activations never overlapped: {barrier_failures}"
    assert errors == [], f"activations of different licences must not interfere: {errors}"
    for key in (key_a, key_b):
        key.refresh_from_db()
        assert key.status == LicenseKeyStatus.ACTIVATED
        assert Device.objects.filter(license_key=key).count() == 1
        assert _licence_transitions(key) == 1


def test_a_first_activation_retried_while_in_flight_writes_one_transition():
    """A client that times out and resends the SAME request while the first is still running:
    both are parked on the licence-row lock, then one device, one transition, and the second
    call is the idempotent replay rather than an IntegrityError on the (licence, idempotency
    key) constraint. Removing the outer lock fails this deterministically: both requests then
    insert a device under the same key."""
    key, full_key = _seed_license_key(tag="inflight", device_limit=3)
    activate = _enroll(full_key, idem="inflight-activation-1", fingerprint="fp-inflight")

    errors, waiting = _race_behind_row_lock(key, [activate, activate])

    assert waiting == 2, f"both requests should be parked on the licence-row lock: {waiting}"
    assert errors == [], f"a retried request must replay, not fail: {errors}"
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert Device.objects.filter(license_key=key).count() == 1
    assert _licence_transitions(key) == 1


def test_an_enrollment_activation_racing_an_account_activation_writes_one_transition():
    """The two entry points converge on one core and one row lock: whichever wins performs
    the transition, the other finds ACTIVATED, and both devices exist."""
    key, full_key = _seed_license_key(tag="mixed", device_limit=3)
    admin = _session_admin(key, tag="mixed")

    def by_session():
        return activate_device_with_session(
            admin,
            ActivateDeviceWithSessionData(
                idempotency_key="mixed-session-activation",
                device_fingerprint="fp-mixed-session",
                platform="macos",
            ),
        )

    by_enrollment = _enroll(
        full_key, idem="mixed-enroll-activation", fingerprint="fp-mixed-enroll"
    )
    errors, waiting = _race_behind_row_lock(key, [by_enrollment, by_session])

    assert waiting == 2, f"both activations should be parked on the licence-row lock: {waiting}"
    assert errors == [], f"both devices fit under the limit; neither may fail: {errors}"
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert Device.objects.filter(license_key=key).count() == 2
    assert _licence_transitions(key) == 1


# --- 86ak5mn0c: staff suspend / reinstate under a real race -------------------------------
def _lifecycle_staff(actor_id="staff_race_susp"):
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id=actor_id,
        staff_permissions=frozenset(
            {StaffPermission.SUSPEND_LICENSE_KEY, StaffPermission.REINSTATE_LICENSE_KEY}
        ),
    )


RACE_REASON = "Race battery: holding the licence while billing follows up."


def _suspend_call(key, idem, *, actor_id="staff_race_susp"):
    return lambda: suspend_license_key(
        _lifecycle_staff(actor_id),
        SuspendLicenseKeyData(
            idempotency_key=idem, license_key_id=str(key.pk), reason=RACE_REASON
        ),
    )


def _reinstate_call(key, idem, *, actor_id="staff_race_susp"):
    return lambda: reinstate_license_key(
        _lifecycle_staff(actor_id),
        ReinstateLicenseKeyData(
            idempotency_key=idem, license_key_id=str(key.pk), reason=RACE_REASON
        ),
    )


def _revoke_call(key, idem):
    """The real revoke mutation (86ak1090r), as a staff member holding only the revoke
    permission."""
    return lambda: revoke_license_key(
        ActorContext(
            kind=ActorKind.STAFF,
            actor_id="staff_race_revoke",
            staff_permissions=frozenset({StaffPermission.REVOKE_LICENSE_KEY}),
        ),
        RevokeLicenseKeyData(
            idempotency_key=idem, license_key_id=str(key.pk), reason=RACE_REASON
        ),
    )


def _extend_call(key, idem, new_expires_at, *, actor_id="staff_race_extend"):
    return lambda: extend_license_key(
        ActorContext(
            kind=ActorKind.STAFF,
            actor_id=actor_id,
            staff_permissions=frozenset({StaffPermission.EXTEND_LICENSE_KEY}),
        ),
        ExtendLicenseKeyData(
            idempotency_key=idem,
            license_key_id=str(key.pk),
            new_expires_at=new_expires_at,
            reason=RACE_REASON,
        ),
    )


def _lifecycle_rows(key, **filters):
    return AuditEvent.objects.filter(
        target_type=AUDIT_TARGET_TYPE, target_id=str(key.pk), **filters
    ).order_by("id")


def _error_codes(errors):
    return [exc.code for _, exc in errors if isinstance(exc, SafeAPIError)]


def test_a_suspension_that_wins_the_race_against_a_first_activation_refuses_the_device():
    """Suspend and a first activation are both parked on the licence row; the suspension is
    served first. The activation then re-reads under the lock, finds SUSPENDED and is refused:
    no device, no token, no ISSUED -> ACTIVATED move. A suspension must never be overtaken by
    an activation that read the licence before it."""
    key, full_key = _seed_license_key(tag="susfirst", device_limit=3)
    assert key.status == LicenseKeyStatus.ISSUED

    results, errors, waiting = _race_in_arrival_order(
        key,
        [
            _suspend_call(key, "susfirst-suspend-0001"),
            _enroll(full_key, idem="susfirst-activation-1", fingerprint="fp-susfirst"),
        ],
    )

    assert waiting == 2, f"both callers should be parked on the licence-row lock: {waiting}"
    assert _error_codes(errors) == [ErrorCode.POLICY_DENIED], errors
    assert [index for index, _ in results] == [0]
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.SUSPENDED
    assert key.prior_status == "ISSUED"
    assert Device.objects.filter(license_key=key).count() == 0
    assert DeviceToken.objects.filter(device__license_key=key).count() == 0
    assert _licence_transitions(key) == 0, "the refused activation made no licence move"
    assert _lifecycle_rows(key, action="license_key.suspended").count() == 1


def test_a_suspension_that_loses_the_race_against_a_first_activation_suspends_the_activated_licence():
    """The other order: the activation is served first and moves the licence ISSUED ->
    ACTIVATED, so the suspension that was waiting behind it records ACTIVATED — the status
    the licence actually held when the suspension took effect, not the one it held when the
    request arrived. The device that just activated keeps its token."""
    key, full_key = _seed_license_key(tag="actfirst", device_limit=3)

    results, errors, waiting = _race_in_arrival_order(
        key,
        [
            _enroll(full_key, idem="actfirst-activation-1", fingerprint="fp-actfirst"),
            _suspend_call(key, "actfirst-suspend-0001"),
        ],
    )

    assert waiting == 2
    assert errors == [], f"both are legal in this order: {errors}"
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.SUSPENDED
    assert key.prior_status == "ACTIVATED"
    assert Device.objects.filter(license_key=key).count() == 1
    assert (
        DeviceToken.objects.filter(device__license_key=key, status=DeviceTokenStatus.ACTIVE).count()
        == 1
    ), "suspending must not kill the token the racing activation just issued"
    assert _licence_transitions(key) == 1
    suspension = _lifecycle_rows(key, action="license_key.suspended").get()
    assert suspension.before["status"] == "ACTIVATED"


def test_a_suspension_racing_a_revoke_leaves_a_consistent_trail_whichever_wins():
    """Revoke is terminal and suspend is not, so the two orders genuinely differ.

    Revoke served first: REVOKED, and the waiting suspension is REFUSED (REVOKED -> SUSPENDED
    is illegal) with one durable DENIED row and no SUCCESS suspension row.
    Suspend served first: SUSPENDED, then the revoke is legal (SUSPENDED -> REVOKED) — both
    succeed, two SUCCESS rows, and the final REVOKED row carries no stale prior status, which
    the schema's check constraint would reject otherwise.
    """
    # --- revoke first -----------------------------------------------------------------
    key, _ = _seed_license_key(tag="revfirst")
    results, errors, waiting = _race_in_arrival_order(
        key, [_revoke_call(key, "revfirst-revoke-0001"), _suspend_call(key, "revfirst-suspend-01")]
    )
    assert waiting == 2
    assert len(errors) == 1 and errors[0][0] == 1
    assert errors[0][1].code == ErrorCode.CONFLICT
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED and key.prior_status == ""
    assert _lifecycle_rows(key, action="license_key.revoked").count() == 1
    assert _lifecycle_rows(key, action="license_key.suspended").count() == 0
    denied = _lifecycle_rows(key, result="DENIED").get()
    assert denied.after["requested_status"] == "SUSPENDED"
    assert denied.request_id == "revfirst-suspend-01", "the refusal survived the racing request"

    # --- suspend first ----------------------------------------------------------------
    key, _ = _seed_license_key(tag="susrev")
    results, errors, waiting = _race_in_arrival_order(
        key, [_suspend_call(key, "susrev-suspend-0001"), _revoke_call(key, "susrev-revoke-00001")]
    )
    assert waiting == 2
    assert errors == []
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED and key.prior_status == ""
    assert [r.action for r in _lifecycle_rows(key, result="SUCCESS")][-2:] == [
        "license_key.suspended",
        "license_key.revoked",
    ]
    assert not _lifecycle_rows(key, result="DENIED").exists()


@pytest.mark.parametrize("same_key", [True, False], ids=["retry-same-key", "two-staff-actions"])
def test_two_concurrent_suspensions_write_exactly_one_audit_row(same_key):
    """A retry racing its own original (same key) and two staff members suspending at once
    (different keys) both end the same way: one status change, one SUCCESS row, the second
    caller a harmless no-op that reports `changed=False`."""
    key, _ = _seed_license_key(tag=f"twosus-{same_key}")
    keys = ["twosus-request-0001"] * 2 if same_key else ["twosus-request-0001", "twosus-request-0002"]
    results = []

    def collect(idem):
        call = _suspend_call(key, idem)
        return lambda: results.append(call())

    errors, waiting = _race_behind_row_lock(key, [collect(idem) for idem in keys])

    assert waiting == 2, f"both suspensions should be parked on the licence-row lock: {waiting}"
    assert errors == [], f"a legal suspend must not race into an error: {errors}"
    assert sorted(r.changed for r in results) == [False, True]
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.SUSPENDED and key.prior_status == "ISSUED"
    assert _lifecycle_rows(key, action="license_key.suspended", result="SUCCESS").count() == 1
    assert not _lifecycle_rows(key, result="DENIED").exists()


def test_a_reinstate_retried_while_the_original_is_in_flight_succeeds_once_and_never_errors():
    """Two copies of the SAME reinstate are both parked on the licence row. The first
    reinstates; the second finds, under the lock, that its own request already took effect
    and returns that outcome. An ordinary second reinstate would be refused (the licence is no
    longer suspended); this one is not, and it leaves no refusal row behind."""
    key, _ = _seed_license_key(tag="reinretry")
    suspender = _suspend_call(key, "reinretry-suspend-0001")
    suspender()
    results = []
    retry = _reinstate_call(key, "reinretry-reinstate-01")

    errors, waiting = _race_behind_row_lock(
        key, [lambda: results.append(retry()), lambda: results.append(retry())]
    )

    assert waiting == 2
    assert errors == [], f"a retried reinstatement must replay, not fail: {errors}"
    assert sorted(r.changed for r in results) == [False, True]
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ISSUED and key.prior_status == ""
    assert _lifecycle_rows(key, action="license_key.reinstated", result="SUCCESS").count() == 1
    assert not _lifecycle_rows(key, result="DENIED").exists(), "no spurious refusal row"


ROUNDS = 3


@pytest.mark.parametrize("direction", ["reinstate-k1", "suspend-k1"])
def test_a_duplicate_request_with_another_staff_action_between_the_copies_is_not_reapplied(
    direction,
):
    """The race the retry lookup must win by being UNDER the row lock. Three callers are parked
    on the licence row: the original request (staff_a, key K1), a different staff member's
    opposite action, and a duplicate of K1. The original is served first; the other two
    follow in either order. If the duplicate is served after the other staff member's action
    it meets a licence in the state K1 was meant to leave it in — so a lookup that is merely
    "is the state still right?" (or one made before the lock) would apply K1 a SECOND time and
    silently undo that staff member's action.

    Invariants that hold for every order of the last two: nobody errors, K1 has exactly one
    SUCCESS row, no refusal rows, and the licence ends where the OTHER staff member's action
    left it. Repeated over several licences because the order of the last two is a scheduling
    race; each round is checked on its own."""
    for round_number in range(ROUNDS):
        tag = f"dupmid-{direction}-{round_number}"
        key, _ = _seed_license_key(tag=tag)
        if direction == "reinstate-k1":
            _suspend_call(key, f"{tag}-seed-suspend", actor_id="staff_seed")()
            original = _reinstate_call(key, f"{tag}-K1", actor_id="staff_a")
            other = _suspend_call(key, f"{tag}-other", actor_id="staff_b")
            duplicate = _reinstate_call(key, f"{tag}-K1", actor_id="staff_a")
            ends_as, action = LicenseKeyStatus.SUSPENDED, "license_key.reinstated"
        else:
            original = _suspend_call(key, f"{tag}-K1", actor_id="staff_a")
            other = _reinstate_call(key, f"{tag}-other", actor_id="staff_b")
            duplicate = _suspend_call(key, f"{tag}-K1", actor_id="staff_a")
            ends_as, action = LicenseKeyStatus.ISSUED, "license_key.suspended"

        results, errors, waiting = _race_in_arrival_order(key, [original, other, duplicate])

        assert waiting == 3, (tag, "all three callers should be parked on the licence row")
        assert errors == [], (tag, errors)
        key.refresh_from_db()
        assert key.status == ends_as, (tag, "the other staff member's action must stand")
        assert (
            _lifecycle_rows(key, action=action, request_id=f"{tag}-K1", result="SUCCESS").count()
            == 1
        ), (tag, "K1 took effect exactly once")
        assert not _lifecycle_rows(key, result="DENIED").exists(), tag
        by_index = dict(results)
        assert by_index[0].changed is True
        assert by_index[2].changed is False and by_index[2].audit_event is not None


def test_a_suspend_and_a_reinstate_racing_each_other_end_in_a_state_the_trail_explains():
    """A suspended licence receives a reinstate and a fresh suspend at once. Served
    reinstate-first: ISSUED -> back, then SUSPENDED again (two SUCCESS rows). Served
    suspend-first: already suspended, so a no-op, then the reinstate (one SUCCESS row, final
    ISSUED). Either way the final status is what the LAST SUCCESS row says it is."""
    for order, tag in (("reinstate-first", "srA"), ("suspend-first", "srB")):
        key, _ = _seed_license_key(tag=tag)
        _suspend_call(key, f"{tag}-seed-suspend-01")()
        calls = [
            _reinstate_call(key, f"{tag}-reinstate-0001"),
            _suspend_call(key, f"{tag}-suspend-000002"),
        ]
        if order == "suspend-first":
            calls.reverse()

        results, errors, waiting = _race_in_arrival_order(key, calls)

        assert waiting == 2 and errors == [], (order, errors)
        key.refresh_from_db()
        successes = list(_lifecycle_rows(key, result="SUCCESS"))
        last_lifecycle = [r for r in successes if r.action != "license_key.generated"][-1]
        assert key.status == last_lifecycle.after["status"], order
        assert key.prior_status == last_lifecycle.after["prior_status"], order
        expected_final = "SUSPENDED" if order == "reinstate-first" else "ISSUED"
        assert key.status == expected_final, order


# --- One valid key per org, under real concurrency (86ak5mn0m) ---------------------------------
#
# `generate_license_key` refuses a key whose dates overlap another key of the same org, and the
# check is a read followed by an insert, so two simultaneous issuances can BOTH read "no
# overlapping key" unless something serialises them. That something is the row lock on the
# CustomerOrg (`lock_customer_for_key_changes`). SQLite ignores `select_for_update`, so this can
# only be shown on Postgres.


def _org_row_waiters():
    """How many backends are parked on a lock inside an org-row query (see
    `_licence_row_waiters` for why this matches on the start of the text and the table)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT count(*) FROM pg_stat_activity
               WHERE datname = current_database() AND pid <> pg_backend_pid()
                 AND wait_event_type = 'Lock' AND query ILIKE %s""",
            [f"SELECT%{CustomerOrg._meta.db_table}%"],
        )
        return cursor.fetchone()[0]


def _race_behind_org_lock(org, targets):
    """Run `targets` concurrently with the overlap at the ORG-row lock guaranteed, the same
    way `_race_behind_row_lock` does for the licence row: a third connection holds
    `FOR UPDATE` on the org, every target is started, and the row is released only once all of
    them are provably parked on a lock. Returns (results, errors, waiting)."""
    holding = threading.Event()
    release = threading.Event()
    results = []
    errors = []

    def hold():
        try:
            with transaction.atomic():
                CustomerOrg.objects.select_for_update().get(pk=org.pk)
                holding.set()
                release.wait(timeout=60)
        finally:
            connections.close_all()

    def run(index, target):
        try:
            results.append((index, target()))
        except Exception as exc:
            errors.append((index, exc))
        finally:
            connections.close_all()

    holder = threading.Thread(target=hold)
    holder.start()
    threads = []
    waiting = 0
    try:
        assert holding.wait(30), "the holder never took the org-row lock"
        for index, target in enumerate(targets):
            thread = threading.Thread(target=run, args=(index, target))
            threads.append(thread)
            thread.start()
        deadline = time.monotonic() + 15
        while _org_row_waiters() < len(targets) and time.monotonic() < deadline:
            time.sleep(0.02)
        waiting = _org_row_waiters()
    finally:
        release.set()
        holder.join(timeout=60)
        for thread in threads:
            thread.join(timeout=60)
    assert not holder.is_alive() and not any(t.is_alive() for t in threads), (
        "a caller did not complete once the org row was released"
    )
    return sorted(results, key=lambda r: r[0]), sorted(errors, key=lambda e: e[0]), waiting


def test_two_simultaneous_issuances_to_one_org_produce_exactly_one_key():
    """Two staff members issue overlapping keys to the same org at the same instant, both
    parked on the org-row lock before either is let through.

    Removing the org lock (`select_for_update` in `lock_customer_for_key_changes`) fails this:
    nothing then queues the two, both read "no overlapping key", and the org ends with two keys
    and so with the SUM of two limits, which is the defect this ticket exists to close.
    """
    org = seed_org("issuance-race")
    plan_code = seat_plan_code(3)
    t0 = timezone.now().replace(microsecond=0)
    targets = [
        (
            lambda n=n: issue_key(
                org,
                tag=f"issuance-race-{n}",
                plan_code=plan_code,
                starts_at=t0,
                expires_at=t0 + timedelta(days=30),
            )
        )
        for n in range(2)
    ]

    results, errors, waiting = _race_behind_org_lock(org, targets)

    assert waiting == 2, f"both issuances should be parked on the org-row lock: {waiting}"
    keys = AppLicenseKey.objects.filter(customer=org)
    assert keys.count() == 1, (
        f"the org holds {keys.count()} overlapping keys; results={results}, errors={errors}"
    )
    assert len(results) == 1 and results[0][1].created is True
    assert len(errors) == 1
    assert isinstance(errors[0][1], SafeAPIError)
    assert errors[0][1].code == ErrorCode.POLICY_DENIED
    # The loser left nothing behind: one key, one plan assignment, one issuance audit row.
    assert (
        AuditEvent.objects.filter(
            action="license_key.generated", target_id=str(keys.get().pk)
        ).count()
        == 1
    )
    assert AuditEvent.objects.filter(action="license_key.generated").count() == 1


def test_a_retry_racing_the_original_issuance_is_a_replay_not_a_refusal():
    """The same staff member sends the same request twice at once (a client retry that overlaps
    the original). Both are parked on the org-row lock; the first creates the key, and the
    second must come back as the idempotent REPLAY of it, not as POLICY_DENIED from the overlap
    the first one created.

    Removing the second replay look (the one made after the org lock is taken) fails this: the
    retry then sails past the guard's view of the world and is refused as an overlap.
    """
    org = seed_org("retry-race")
    plan_code = seat_plan_code(3)
    t0 = timezone.now().replace(microsecond=0)
    targets = [
        (
            lambda: issue_key(
                org,
                tag="retry-race",  # the SAME idempotency key for both
                plan_code=plan_code,
                starts_at=t0,
                expires_at=t0 + timedelta(days=30),
            )
        )
        for _ in range(2)
    ]

    results, errors, waiting = _race_behind_org_lock(org, targets)

    assert waiting == 2, f"both requests should be parked on the org-row lock: {waiting}"
    assert errors == [], f"the retry was refused instead of replayed: {errors}"
    assert AppLicenseKey.objects.filter(customer=org).count() == 1
    created = sorted(result.created for _, result in results)
    assert created == [False, True], f"expected one creation and one replay, got {created}"
    replay = next(result for _, result in results if not result.created)
    assert replay.full_key is None, "a replay must never re-show the secret"


def test_holding_the_org_lock_does_not_block_a_row_that_references_the_org():
    """The org lock is `FOR NO KEY UPDATE`. A plain `FOR UPDATE` on the org row blocks every INSERT
    of a row that references it (a user, a device, a session, a key), because each takes
    `FOR KEY SHARE` on the parent; that would stall sign-ups and activations of the same org for
    as long as an issuance holds the lock. The race itself only needs two issuers to exclude
    each other, which the tests above still prove.

    Measured by inserting a user for the org from a second connection while the lock is held,
    with a 3 s `lock_timeout` so a blocked insert fails instead of hanging the test.
    """
    org = seed_org("lock-strength")
    holding = threading.Event()
    release = threading.Event()
    outcome = {}

    def hold():
        try:
            with transaction.atomic():
                lock_customer_for_key_changes(org.pk)
                holding.set()
                release.wait(timeout=60)
        finally:
            connections.close_all()

    def insert_child():
        started = time.monotonic()
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '3s'")
                CustomerUser.objects.create(
                    customer=org,
                    email="child@lock-strength.example",
                    email_fingerprint="f" * 64,
                    password_hash="x",
                    status=CustomerUserStatus.INVITED,
                    role=CustomerRole.ADMIN,
                    created_by_actor_id="test",
                    idempotency_key="lock-strength-child-0001",
                )
            outcome["error"] = None
        except Exception as exc:
            outcome["error"] = exc
        finally:
            outcome["seconds"] = time.monotonic() - started
            connections.close_all()

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert holding.wait(30), "the holder never took the org lock"
        child = threading.Thread(target=insert_child)
        child.start()
        child.join(timeout=30)
        assert not child.is_alive(), "the child insert is still blocked behind the org lock"
    finally:
        release.set()
        holder.join(timeout=60)

    assert outcome["error"] is None, f"inserting a row for the org was blocked: {outcome['error']!r}"
    assert outcome["seconds"] < 2.0, f"the insert waited {outcome['seconds']:.2f}s behind the lock"
    assert CustomerUser.objects.filter(customer=org).count() == 1


def test_the_org_lock_is_not_held_while_the_secret_is_hashed(monkeypatch):
    """`make_password` costs ~250 ms. Held under the org lock, every other write for the org
    (including a device activation, which locks the org row through its join) waits that long
    behind each issuance. The secret is therefore generated and hashed BEFORE the lock is
    taken, and this checks it from outside: while the hash is running, a second connection can
    take the org row `NOWAIT`.

    Fails if the hashing moves back inside the lock (`FOR UPDATE NOWAIT` then raises).
    """
    org = seed_org("hash-outside-lock")
    plan_code = seat_plan_code(3)
    t0 = timezone.now().replace(microsecond=0)
    hashing = threading.Event()
    observed = threading.Event()
    result = {}
    real_hash = license_services.make_password

    def slow_hash(*args, **kwargs):
        hashing.set()
        observed.wait(timeout=30)
        return real_hash(*args, **kwargs)

    def observe():
        try:
            assert hashing.wait(30), "issuance never reached the hash"
            try:
                with transaction.atomic():
                    CustomerOrg.objects.select_for_update(nowait=True).get(pk=org.pk)
                result["observer"] = "lock was free"
            except OperationalError as exc:
                result["observer"] = f"lock was held: {exc}"
        finally:
            observed.set()
            connections.close_all()

    monkeypatch.setattr(license_services, "make_password", slow_hash)
    observer = threading.Thread(target=observe)
    observer.start()
    try:
        issued = issue_key(
            org,
            tag="hash-outside-lock",
            plan_code=plan_code,
            starts_at=t0,
            expires_at=t0 + timedelta(days=30),
        )
    finally:
        observed.set()
        observer.join(timeout=60)

    assert issued.created is True
    assert result["observer"] == "lock was free", result


def test_two_simultaneous_issuances_to_two_orgs_both_succeed():
    """POSITIVE CONTROL for the test above. The lock is per org, so it must not serialise
    unrelated orgs into refusing each other: if it did, the test above would pass for the wrong
    reason (a global refusal) and this one would show it."""
    orgs = [seed_org(f"issuance-two-orgs-{n}") for n in range(2)]
    plan_code = seat_plan_code(3)
    t0 = timezone.now().replace(microsecond=0)
    results = []
    errors = []

    def issue(index):
        try:
            results.append(
                issue_key(
                    orgs[index],
                    tag=f"issuance-two-orgs-{index}",
                    plan_code=plan_code,
                    starts_at=t0,
                    expires_at=t0 + timedelta(days=30),
                )
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=issue, args=(n,)) for n in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    assert len(results) == 2 and all(r.created for r in results)
    assert {k.customer_id for k in AppLicenseKey.objects.all()} == {o.pk for o in orgs}


# --- 86ak1090r: staff extend / revoke under a real race -----------------------------------
# Extend takes the ORG row lock and then the LICENCE row lock. Revoke and suspend lock only the
# licence row, and activation does too once its lock names `of=("self",)`; before that it also
# locked the joined org row and deadlocked against extend (see the end of this file), so this was
# argued and wrong rather than proven.
# These tests park the callers on a held lock first (the same machinery as the suspend races
# above) so that the overlap is guaranteed rather than left to scheduling.
def _applied(results):
    return [r for _, r in results if r.changed]


def test_two_concurrent_extensions_with_the_same_key_apply_once():
    """A retry racing its own original, both parked on the org lock. One applies; the other
    waits for it, then recognises the retry under the lock and reports the original row."""
    key, _ = _seed_license_key(tag="ext-same-key")
    org = CustomerOrg.objects.get(pk=key.customer_id)
    target = timezone.now().replace(microsecond=0) + timedelta(days=90)
    call = _extend_call(key, "ext-same-key-0001", target)

    results, errors, waiting = _race_behind_org_lock(org, [call, call])

    assert waiting == 2, f"both callers should be parked on the org-row lock: {waiting}"
    assert errors == [], errors
    assert len(results) == 2 and len(_applied(results)) == 1
    original = _applied(results)[0].audit_event
    replay = [r for _, r in results if not r.changed][0]
    assert replay.audit_event.pk == original.pk
    assert _lifecycle_rows(key, action="license_key.extended").count() == 1
    key.refresh_from_db()
    assert key.expires_at == target


def test_two_concurrent_extensions_to_the_same_date_apply_once_and_reject_the_other():
    key, _ = _seed_license_key(tag="ext-same-date")
    org = CustomerOrg.objects.get(pk=key.customer_id)
    target = timezone.now().replace(microsecond=0) + timedelta(days=90)

    results, errors, waiting = _race_behind_org_lock(
        org,
        [
            _extend_call(key, "ext-same-date-0001", target, actor_id="staff_race_a"),
            _extend_call(key, "ext-same-date-0002", target, actor_id="staff_race_b"),
        ],
    )

    assert waiting == 2
    assert len(results) == 1 and results[0][1].changed is True
    assert _error_codes(errors) == [ErrorCode.VALIDATION_FAILED], errors
    assert _lifecycle_rows(key, action="license_key.extended").count() == 1
    key.refresh_from_db()
    assert key.expires_at == target


def test_two_concurrent_extensions_to_different_dates_leave_a_chain_the_trail_explains():
    """Whichever is served first, the final date is the later of those that applied, every
    applied extension has exactly one row, and a second one that applied starts where the first
    ended. A shorter request that loses the race is rejected, never applied backwards."""
    key, _ = _seed_license_key(tag="ext-diff-date")
    org = CustomerOrg.objects.get(pk=key.customer_id)
    now = timezone.now().replace(microsecond=0)
    short, long_ = now + timedelta(days=60), now + timedelta(days=90)

    results, errors, waiting = _race_behind_org_lock(
        org,
        [
            _extend_call(key, "ext-diff-date-0001", short, actor_id="staff_race_a"),
            _extend_call(key, "ext-diff-date-0002", long_, actor_id="staff_race_b"),
        ],
    )

    assert waiting == 2
    assert set(_error_codes(errors)) <= {ErrorCode.VALIDATION_FAILED}
    rows = list(_lifecycle_rows(key, action="license_key.extended"))
    assert len(rows) == len(results) >= 1
    key.refresh_from_db()
    assert key.expires_at == max(
        {"ext-diff-date-0001": short, "ext-diff-date-0002": long_}[r.request_id] for r in rows
    )
    if len(rows) == 2:
        assert rows[1].before["expires_at"] == rows[0].after["expires_at"]
        assert rows[0].request_id == "ext-diff-date-0001" and rows[1].request_id == "ext-diff-date-0002"
    else:
        assert rows[0].request_id == "ext-diff-date-0002", "only the longer one can win alone"
        assert _error_codes(errors) == [ErrorCode.VALIDATION_FAILED]


def test_an_extension_that_wins_the_race_against_a_revoke_is_followed_by_the_revoke():
    key, _ = _seed_license_key(tag="ext-then-rev")
    target = timezone.now().replace(microsecond=0) + timedelta(days=90)

    results, errors, waiting = _race_in_arrival_order(
        key, [_extend_call(key, "ext-then-rev-0001", target), _revoke_call(key, "ext-then-rev-0002")]
    )

    assert waiting == 2, f"both callers should be parked on the licence-row lock: {waiting}"
    assert errors == [], errors
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED
    assert key.expires_at == target
    assert [r.action for r in _lifecycle_rows(key, result="SUCCESS")][-2:] == [
        "license_key.extended",
        "license_key.revoked",
    ]
    assert not _lifecycle_rows(key, result="DENIED").exists()


def test_a_revoke_that_wins_the_race_against_an_extension_is_not_undone_by_it():
    """THE corruption this ticket must not allow: an extension that read the licence before the
    revoke must not resurrect it. The extension holds the org lock and waits on the licence
    row; it is served after the revoke, re-reads under the lock, and is refused with a durable
    DENIED row."""
    key, _ = _seed_license_key(tag="rev-then-ext")
    before = key.expires_at
    target = timezone.now().replace(microsecond=0) + timedelta(days=90)

    results, errors, waiting = _race_in_arrival_order(
        key, [_revoke_call(key, "rev-then-ext-0001"), _extend_call(key, "rev-then-ext-0002", target)]
    )

    assert waiting == 2
    assert _error_codes(errors) == [ErrorCode.CONFLICT], errors
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED
    assert key.expires_at == before, "the refused extension moved nothing"
    denied = _lifecycle_rows(key, result="DENIED").get()
    assert denied.action == EXTEND_REFUSED_ACTION and denied.request_id == "rev-then-ext-0002"
    assert not _lifecycle_rows(key, action="license_key.extended").exists()


def test_two_concurrent_revokes_write_exactly_one_audit_row():
    key, _ = _seed_license_key(tag="two-revokes")

    results, errors, waiting = _race_in_arrival_order(
        key, [_revoke_call(key, "two-revokes-0001"), _revoke_call(key, "two-revokes-0002")]
    )

    assert waiting == 2
    assert errors == [], errors
    assert [r.changed for _, r in results] == [True, False]
    assert _lifecycle_rows(key, action="license_key.revoked").count() == 1
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED


def test_an_extension_racing_an_issuance_never_leaves_two_overlapping_valid_keys():
    """Both move an org's dates, both take the org lock, so exactly one wins. Extending key A
    past the instant key B starts would overlap it; issuing B while A's extension is in flight
    would too. Either order must end with the org's valid keys non-overlapping."""
    org = seed_org("ext-vs-issue")
    plan_code = seat_plan_code(3)
    t0 = timezone.now().replace(microsecond=0)
    first = issue_key(
        org, tag="ext-vs-issue-a", plan_code=plan_code,
        starts_at=t0 - timedelta(days=20), expires_at=t0 + timedelta(days=10),
    ).license_key
    second_starts = first.expires_at

    results, errors, waiting = _race_behind_org_lock(
        org,
        [
            _extend_call(first, "ext-vs-issue-ext-01", first.expires_at + timedelta(days=5)),
            lambda: issue_key(
                org, tag="ext-vs-issue-b", plan_code=plan_code,
                starts_at=second_starts, expires_at=second_starts + timedelta(days=60),
            ),
        ],
    )

    assert waiting == 2
    assert len(results) == 1 and len(errors) == 1, (results, errors)
    assert errors[0][1].code == ErrorCode.POLICY_DENIED
    keys = list(AppLicenseKey.objects.filter(customer=org).order_by("starts_at"))
    for left, right in zip(keys, keys[1:]):
        assert left.expires_at <= right.starts_at, "the org's keys overlap"


# --- 86ak1090r round 2: extend against first activation on ONE licence ---------------------
# Extend takes the org row lock and then the licence row lock. Activation locks the licence row
# with `select_for_update().select_related("customer")`, and Django's documented behaviour is
# that without `of=` the lock covers the rows pulled in by `select_related()` too: licence AND
# org, in one statement. Locks are taken licence first, then org, so the two orders cross: extend
# holds the org and waits for the licence while activation holds the licence and waits for the
# org, and Postgres aborts one of them with "deadlock detected". The tests below pin the
# interleaving that produces it, and a repeated unaligned race, so the claim in `extend_license_key`
# that nothing takes the two locks in the opposite order is proven rather than argued.
def _session_activation_call(key, admin, n):
    return lambda: activate_device_with_session(
        admin,
        ActivateDeviceWithSessionData(
            idempotency_key=f"ext-vs-act-{key.pk}-{n:04d}",
            device_fingerprint=f"fp-ext-vs-act-{key.pk}-{n}",
            platform="macos",
        ),
    )


def _deadlocks(errors):
    return [exc for exc in errors if isinstance(exc, OperationalError) and "deadlock" in str(exc).lower()]


@pytest.mark.parametrize("activation_first", [True, False], ids=["activation-first", "extension-first"])
def test_an_extension_and_a_first_activation_on_one_licence_never_deadlock(activation_first):
    """The activation joins the licence queue first (it is parked on the licence row before the
    extension has even started), then the extension takes the org lock and parks on the licence
    row behind it. Released, the activation is served the licence and wants the org, which the
    extension holds, while the extension wants the licence: a cycle, unless the activation's
    lock does not reach the org row. Both orders must complete, one device, one extension."""
    key, _ = _seed_license_key(tag=f"ext-act-{int(activation_first)}")
    admin = _session_admin(key, tag=f"ext-act-{int(activation_first)}")
    target = timezone.now().replace(microsecond=0) + timedelta(days=90)
    activate = _session_activation_call(key, admin, 0)
    extend = _extend_call(key, f"ext-act-{int(activation_first)}-0001", target)

    results, errors, waiting = _race_in_arrival_order(
        key, [activate, extend] if activation_first else [extend, activate]
    )

    assert waiting == 2, f"both callers should be parked on the licence-row lock: {waiting}"
    assert _deadlocks([exc for _, exc in errors]) == [], f"deadlock detected: {errors}"
    assert errors == [], errors
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.ACTIVATED
    assert key.expires_at == target
    assert Device.objects.filter(license_key=key).count() == 1
    assert _lifecycle_rows(key, action="license_key.extended").count() == 1
    assert _licence_transitions(key) == 1


def test_fifty_unaligned_extension_and_activation_races_never_deadlock_and_end_consistent():
    """The same pair, started together behind a barrier with a few milliseconds of random
    jitter, 50 times over fresh licences. Not deterministic (that is the test above); it is the
    one that would catch a different interleaving, or a deadlock with some other lock."""
    rng = random.Random(8675309)
    now = timezone.now().replace(microsecond=0)
    deadlocks = []
    for n in range(50):
        key, _ = _seed_license_key(tag=f"ext-act-rep-{n}")
        admin = _session_admin(key, tag=f"ext-act-rep-{n}")
        target = now + timedelta(days=90 + n)
        activate = _session_activation_call(key, admin, n)
        # A staff member of their own per iteration: 50 extensions by one actor would meet the
        # lifecycle throttle (30 a minute), which is not what this test is about.
        extend = _extend_call(key, f"ext-act-rep-{n:04d}-key", target, actor_id=f"staff_race_rep_{n}")
        delay_a, delay_b = rng.uniform(0, 0.004), rng.uniform(0, 0.004)

        def jittered(call, delay):
            def run():
                time.sleep(delay)
                return call()
            return run

        errors, barrier_failures = _run_in_threads([jittered(activate, delay_a), jittered(extend, delay_b)])

        assert barrier_failures == []
        deadlocks.extend(_deadlocks(errors))
        assert errors == [], f"iteration {n}: {errors}"
        key.refresh_from_db()
        assert key.status == LicenseKeyStatus.ACTIVATED, n
        assert key.expires_at == target, n
        assert Device.objects.filter(license_key=key).count() == 1, n
    assert deadlocks == []


def test_the_activation_lock_names_the_licence_row_and_not_the_org_it_joins():
    """The statement text behind the deadlock above, pinned directly. `select_related("customer")`
    makes the lock query a join; without `of=("self",)` Postgres is told `FOR UPDATE` on BOTH
    tables. Cheap and deterministic, so it also guards the fix against someone re-ordering the
    ORM call without re-running the 50-iteration race."""
    key, _ = _seed_license_key(tag="act-lock-sql")
    admin = _session_admin(key, tag="act-lock-sql")

    with CaptureQueriesContext(connection) as queries:
        _session_activation_call(key, admin, 0)()

    org_table = CustomerOrg._meta.db_table
    joined = [
        q["sql"]
        for q in queries.captured_queries
        if "FOR UPDATE" in q["sql"]
        and AppLicenseKey._meta.db_table in q["sql"]
        and f'JOIN "{org_table}"' in q["sql"]
    ]
    assert joined, "activation no longer takes its licence lock on a join with the org (test is stale)"
    for sql in joined:
        assert f'FOR UPDATE OF "{AppLicenseKey._meta.db_table}"' in sql, sql
        assert org_table not in sql.split("FOR UPDATE", 1)[1], sql


# FR-509 refresh renewal: genuine queued row-lock interleavings, not start barriers.
def _live_extended_device(tag):
    key, full_key = _seed_license_key(tag=tag)
    activated = _enroll(full_key, idem=f"{tag}-activation", fingerprint=f"fp-{tag}")()
    _extend_call(key, f"{tag}-extension", key.expires_at + timedelta(days=30))()
    return key, activated


def test_two_live_refreshes_rotate_only_once_under_real_contention():
    key, activated = _live_extended_device("two-refreshes")
    results = []
    def refresh():
        results.append(refresh_license(activated.full_token))
    errors, waiting = _race_behind_row_lock(key, [refresh, refresh])
    assert waiting == 2
    assert len(errors) == 1 and errors[0].code == ErrorCode.UNAUTHENTICATED
    assert len(results) == 1 and results[0].full_token
    assert DeviceToken.objects.filter(device=activated.device, status=DeviceTokenStatus.ACTIVE).count() == 1
    assert AuditEvent.objects.filter(action="device_token.reminted").count() == 1
    assert refresh_license(results[0].full_token).full_token is None


@pytest.mark.parametrize("revoke_first", [True, False])
def test_refresh_and_revoke_respect_licence_lock_arrival_order(revoke_first):
    key, activated = _live_extended_device(f"refresh-revoke-{revoke_first}")
    renewal = lambda: refresh_license(activated.full_token)
    revoke = _revoke_call(key, f"refresh-revoke-{revoke_first}-req")
    calls = [revoke, renewal] if revoke_first else [renewal, revoke]
    results, errors, waiting = _race_in_arrival_order(key, calls)
    assert waiting == 2 and errors == []
    renewal_result = dict(results)[1 if revoke_first else 0]
    assert bool(renewal_result.full_token) is (not revoke_first)
    assert AuditEvent.objects.filter(action="device_token.reminted").count() == (not revoke_first)
    key.refresh_from_db()
    assert key.status == LicenseKeyStatus.REVOKED


@pytest.mark.parametrize("extend_first", [True, False])
def test_refresh_and_extension_observe_the_serialized_expiry(extend_first):
    key, full_key = _seed_license_key(tag=f"refresh-extend-{extend_first}")
    activated = _enroll(full_key, idem=f"refresh-extend-{extend_first}-act", fingerprint="fp-refresh-ext")()
    target = key.expires_at + timedelta(days=30)
    renewal = lambda: refresh_license(activated.full_token)
    extension = _extend_call(key, f"refresh-extend-{extend_first}-req", target)
    results, errors, waiting = _race_in_arrival_order(
        key, [extension, renewal] if extend_first else [renewal, extension])
    assert waiting == 2 and errors == []
    renewed = dict(results)[1 if extend_first else 0]
    assert bool(renewed.full_token) is extend_first
    if not extend_first:
        renewed = refresh_license(activated.full_token)
    assert renewed.token_expires_at == target.isoformat() and renewed.full_token
    assert DeviceToken.objects.filter(device=activated.device, status=DeviceTokenStatus.ACTIVE).count() == 1


def test_two_cascades_cannot_duplicate_a_token_revocation_audit():
    key, full_key = _seed_license_key(tag="concurrent-cascade")
    activated = _enroll(full_key, idem="concurrent-cascade-act", fingerprint="concurrent-cascade")()
    _revoke_call(key, "concurrent-cascade-rev")()
    results = []
    errors, waiting = _race_behind_row_lock(key, [lambda: results.append(cascade_license_revocations()),
                                               lambda: results.append(cascade_license_revocations())])
    assert waiting == 2 and errors == []
    assert sorted(results) == [0, 1]
    assert AuditEvent.objects.filter(action="device_token.revoked_by_cascade").count() == 1


@pytest.mark.parametrize("same_intent", [True, False])
def test_concurrent_admin_replacements_are_locked_and_show_once(same_intent):
    key, full_key = _seed_license_key(tag=f"replace-{same_intent}")
    activated = _enroll(full_key, idem=f"replace-{same_intent}-activation", fingerprint="fp-replace")()
    admin = _session_admin(key, tag=f"replace-{same_intent}")
    def replace(index):
        return lambda: activate_device_with_session(admin, ActivateDeviceWithSessionData(
            idempotency_key=f"replace-request-{0 if same_intent else index}",
            device_fingerprint="fp-replace", platform="macos", replace_token=True))
    results, errors, waiting = _race_in_arrival_order(key, [replace(0), replace(1)])
    assert waiting == 2 and errors == []
    assert sum(bool(result.full_token) for _, result in results) == (1 if same_intent else 2)
    assert DeviceToken.objects.filter(device=activated.device, status=DeviceTokenStatus.ACTIVE).count() == 1
    assert DeviceToken.objects.get(pk=activated.device_token.pk).status == DeviceTokenStatus.REVOKED
    assert AuditEvent.objects.filter(action="device_token.reminted").count() == (1 if same_intent else 2)
