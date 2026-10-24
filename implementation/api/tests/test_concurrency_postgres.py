"""The DEC-004 instance limit, and device-token re-mint, under real concurrency.

`activate_device` guards both with select_for_update on the licence row, which SQLite
silently no-ops (has_select_for_update = False). These tests therefore SKIP on SQLite —
they would pass there for the wrong reason and hide the very races they exist to catch.
"""

import threading
import time
from datetime import timedelta

import pytest
from django.db import connection, connections, transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerRole, CustomerUser, CustomerUserStatus
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
)
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.license_keys.state_machine import AUDIT_TARGET_TYPE
from selahcue_api.graphql.context import ActorContext, ActorKind
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="select_for_update is a no-op on SQLite; this race is only observable on Postgres",
    ),
]


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
        device_limit=device_limit,
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
            plan_code="PRO",
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
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
    holding = threading.Event()
    release = threading.Event()
    errors = []

    def hold():
        try:
            with transaction.atomic():
                AppLicenseKey.objects.select_for_update().get(pk=key.pk)
                holding.set()
                release.wait(timeout=60)
        finally:
            connections.close_all()

    def run(target):
        try:
            target()
        except Exception as exc:
            errors.append(exc)
        finally:
            connections.close_all()

    holder = threading.Thread(target=hold)
    holder.start()
    threads = []
    try:
        assert holding.wait(30), "the holder never took the licence-row lock"
        threads = [threading.Thread(target=run, args=(target,)) for target in targets]
        for t in threads:
            t.start()
        deadline = time.monotonic() + 15
        while _licence_row_waiters() < len(targets) and time.monotonic() < deadline:
            time.sleep(0.02)
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
        "an activation did not complete once the licence row was released"
    )
    return errors, waiting


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


def test_a_polling_error_releases_the_held_licence_row_promptly(monkeypatch):
    """If the poll in `_race_behind_row_lock` raises, the holder must be released at once, not
    left holding the licence row for its full 60 s wait (which would stall the next test)."""
    key, full_key = _seed_license_key(tag="pollerror", device_limit=1)

    def broken_poll():
        raise RuntimeError("simulated pg_stat_activity failure")

    monkeypatch.setitem(globals(), "_licence_row_waiters", broken_poll)
    started = time.monotonic()

    with pytest.raises(RuntimeError, match="simulated pg_stat_activity failure"):
        _race_behind_row_lock(
            key, [_enroll(full_key, idem="poll-error-activation", fingerprint="fp-poll-error")]
        )

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
