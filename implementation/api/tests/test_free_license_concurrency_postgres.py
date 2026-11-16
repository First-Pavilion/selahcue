"""Managed Free issuance and renewal behaviour under PostgreSQL row locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from time import monotonic, sleep
from queue import Queue

import pytest
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from test_bound_activation import SESSION, admin_session, body, post
from test_bound_activation_postgres import parallel
from test_concurrency_postgres import _licence_row_waiters
from test_free_license_lifecycle import NOW, REFRESH, activate_free, self_service_org
from test_native_account_surface import seed_license, seed_org
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle, LicenseKeyStatus
from selahcue_api.apps.license_keys.state_machine import apply_license_status_transition
from selahcue_api.graphql.context import ActorContext, ActorKind

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="requires PostgreSQL"),
]


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    cache.clear()


def test_concurrent_first_admin_activations_use_one_free_licence():
    org = self_service_org()
    session = admin_session(Client(), org)

    responses = parallel(
        lambda: post(Client(), SESSION, body(), session),
        lambda: post(Client(), SESSION, body("2" * 32), session),
    )

    assert [reply.status_code for reply in responses] == [200, 200]
    payloads = [reply.json() for reply in responses]
    assert sum(reply["activation_token"] is not None for reply in payloads) == 1
    assert payloads[0]["device"]["device_public_id"] == payloads[1]["device"]["device_public_id"]
    assert AppLicenseKey.objects.count() == FreeLicenseLifecycle.objects.count() == 1
    assert Device.objects.count() == DeviceToken.objects.count() == 1
    assert DeviceActivationOperation.objects.count() == 2


def test_concurrent_refreshes_extend_one_licence_once(client):
    _org, _session, initial, licence = activate_free(client)
    expires = timezone.now() + timedelta(days=2)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expires)
    DeviceToken.objects.update(expires_at=expires)
    token = initial["activation_token"]

    responses = parallel(
        lambda: post(Client(), REFRESH, {}, token),
        lambda: post(Client(), REFRESH, {}, token),
    )

    assert [reply.status_code for reply in responses] == [200, 200]
    assert responses[0].json()["license"] == responses[1].json()["license"]
    assert responses[0].json()["token"] == responses[1].json()["token"]
    licence.refresh_from_db()
    assert DeviceToken.objects.get().expires_at == licence.expires_at
    assert licence.expires_at > expires + timedelta(days=360)
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == 1


@pytest.mark.parametrize("path", ["refresh", "recover"])
def test_waiting_free_renewal_rechecks_committed_suspension(client, path):
    _org, session, initial, licence = activate_free(client)
    expires = timezone.now() + timedelta(days=2)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expires)
    DeviceToken.objects.update(expires_at=expires)

    def enter_renewal():
        try:
            if path == "refresh":
                return post(Client(), REFRESH, {}, initial["activation_token"])
            return post(Client(), SESSION, body(
                "2" * 32, expected=initial["device"]["device_public_id"],
            ), session)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = AppLicenseKey.objects.select_for_update().get(pk=licence.pk)
            job = pool.submit(enter_renewal)
            deadline = monotonic() + 8
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                if _licence_row_waiters() == 1:
                    break
                sleep(0.01)
            else:
                pytest.fail("renewal did not wait on the licence row")
            apply_license_status_transition(
                locked, to_status=LicenseKeyStatus.SUSPENDED,
                actor=ActorContext(kind=ActorKind.SERVICE, actor_id="fixture-suspension"),
                reason="Test suspension while the Free renewal waits.",
                request_id="test-free-suspension",
            )
        result = job.result(timeout=10)

    assert result.status_code == (200 if path == "refresh" else 403)
    if path == "refresh":
        assert result.json()["license"]["status"] == LicenseKeyStatus.SUSPENDED
        assert not result.json()["license"]["valid_now"]
    licence.refresh_from_db()
    assert licence.status == LicenseKeyStatus.SUSPENDED
    assert licence.expires_at == DeviceToken.objects.get().expires_at == expires
    assert Device.objects.count() == DeviceActivationOperation.objects.count() == 1
    assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()


def test_migration_preserves_existing_licence_without_managing_it():
    old_leaf = ("selahcue_license_keys", "0002_applicensekey_prior_status")
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([old_leaf])
        original = seed_license(seed_org(tag="pre-managed"))
        before = AppLicenseKey.objects.values().get(pk=original.pk)
    finally:
        MigrationExecutor(connection).migrate(latest)
    assert AppLicenseKey.objects.values().get(pk=original.pk) == before
    assert not FreeLicenseLifecycle.objects.filter(license_key_id=original.pk).exists()


def test_overlap_refusal_audit_survives_recovery_rollback(client):
    from test_bound_activation import another_license

    _org, session, initial, licence = activate_free(client)
    expires = timezone.now() + timedelta(days=1)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expires)
    future, _ = another_license(licence, "future-overlap")
    AppLicenseKey.objects.filter(pk=future.pk).update(
        starts_at=expires, expires_at=expires + timedelta(days=45),
    )
    reply = post(client, SESSION, body("2" * 32, expected=initial["device"]["device_public_id"]), session)
    assert reply.status_code == 403
    assert AuditEvent.objects.get(action="license_key.free_renewed").result == AuditResult.DENIED
    licence.refresh_from_db()
    assert licence.expires_at == expires
    assert Device.objects.count() == DeviceToken.objects.count() == DeviceActivationOperation.objects.count() == 1


def _backend_pid():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


def _isolated_job(pids, action):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute("SET lock_timeout = '8s'")
        pids.put(_backend_pid())
        return action()
    finally:
        connections.close_all()


def _blocked_query(waiter, blocker):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_stat_clear_snapshot()")
        cursor.execute(
            "SELECT query FROM pg_stat_activity WHERE pid = %s "
            "AND wait_event_type = 'Lock' AND %s = ANY(pg_blocking_pids(pid))",
            [waiter, blocker],
        )
        row = cursor.fetchone()
        return row[0] if row else None


def _await_blocked_query(waiter, blocker):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        query = _blocked_query(waiter, blocker)
        if query is not None:
            return query
        sleep(0.01)
    pytest.fail(f"backend {waiter} never waited behind backend {blocker}")


def _lifecycle_rows():
    return {
        model._meta.label: list(model.objects.order_by("pk").values())
        for model in (AppLicenseKey, FreeLicenseLifecycle, Device, DeviceToken,
                      DeviceActivationOperation, AuditEvent)
    }


@pytest.mark.parametrize("lane", ["renewal", "catch-up"])
@pytest.mark.parametrize("wait_on", ["assignment", "marker"])
@pytest.mark.parametrize("elapsed", [4, 5, 10], ids=["before-expiry", "exact-expiry", "after-expiry"])
def test_refresh_rechecks_expiry_after_eligibility_lock(client, monkeypatch, lane, wait_on, elapsed):
    from selahcue_api.apps.catalogue.models import LicensePlanAssignment

    clock = [NOW]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    _org, _session, initial, licence = activate_free(client)
    token_expiry = NOW + timedelta(seconds=5)
    licence_expiry = token_expiry if lane == "renewal" else NOW + timedelta(days=300)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=licence_expiry)
    DeviceToken.objects.update(expires_at=token_expiry)
    before = _lifecycle_rows()
    lock_model = LicensePlanAssignment if wait_on == "assignment" else FreeLicenseLifecycle
    pids = Queue()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            lock_model.objects.select_for_update().get(license_key=licence)
            holder = _backend_pid()
            job = pool.submit(_isolated_job, pids, lambda: post(
                Client(), REFRESH, {}, initial["activation_token"],
            ))
            waiter = pids.get(timeout=5)
            query = _await_blocked_query(waiter, holder)
            assert lock_model._meta.db_table in query
            # Advance only after PostgreSQL confirms the real production query is waiting.
            clock[0] = NOW + timedelta(seconds=elapsed)
        response = job.result(timeout=10)

    if elapsed >= 5:
        assert response.status_code == 401, response.json()
        assert _lifecycle_rows() == before
    else:
        assert response.status_code == 200, response.json()
        expected = clock[0] + timedelta(days=365) if lane == "renewal" else licence_expiry
        licence.refresh_from_db()
        assert licence.expires_at == DeviceToken.objects.get().expires_at == expected
        after = _lifecycle_rows()
        for model in (FreeLicenseLifecycle, Device, DeviceActivationOperation):
            assert after[model._meta.label] == before[model._meta.label]
        original_token = before[DeviceToken._meta.label][0]
        token = DeviceToken.objects.values().get()
        for field in ("id", "device_id", "status", "token_hash", "token_fingerprint", "issued_at"):
            assert token[field] == original_token[field]
        assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == int(lane == "renewal")
        assert AuditEvent.objects.filter(action="device_token.free_validity_extended").count() == int(lane == "catch-up")


def test_different_org_refreshes_do_not_lock_the_shared_fallback_plan(client):
    from selahcue_api.apps.catalogue.models import LicensePlanAssignment
    from selahcue_api.apps.accounts.models import CustomerStatus

    _org, _session, first, first_licence = activate_free(client)
    other_org = seed_org(tag="independent-free")
    other_org.created_by_actor_id = "self_signup:" + "b" * 64
    other_org.status = CustomerStatus.TRIAL
    other_org.save(update_fields=["created_by_actor_id", "status"])
    other_session = admin_session(client, other_org)
    second_response = post(client, SESSION, body("3" * 32), other_session)
    assert second_response.status_code == 200, second_response.json()
    second = second_response.json()
    assert LicensePlanAssignment.objects.values("plan_id").distinct().count() == 1
    expires = timezone.now() + timedelta(days=2)
    AppLicenseKey.objects.update(expires_at=expires)
    DeviceToken.objects.update(expires_at=expires)
    pids = Queue()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(), CaptureQueriesContext(connection) as queries:
            assert post(client, REFRESH, {}, first["activation_token"]).status_code == 200
            holder = _backend_pid()
            job = pool.submit(_isolated_job, pids, lambda: post(
                Client(), REFRESH, {}, second["activation_token"],
            ))
            waiter = pids.get(timeout=5)
            deadline = monotonic() + 5
            while not job.done() and monotonic() < deadline:
                assert _blocked_query(waiter, holder) is None, "different org waits on the shared Plan"
                sleep(0.01)
            assert job.done(), "independent refresh did not complete while first transaction stayed open"
            assert job.result().status_code == 200
            assignment_sql = [q["sql"] for q in queries if
                              LicensePlanAssignment._meta.db_table in q["sql"] and "FOR UPDATE" in q["sql"]]
            assert len(assignment_sql) == 1
            assert 'FOR UPDATE OF "selahcue_catalogue_licenseplanassignment"' in assignment_sql[0]
            print("assignment-only SQL:", assignment_sql[0])
    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == 2


def test_refresh_assignment_lock_serializes_the_staff_assignment_writer(client):
    from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
    from selahcue_api.apps.catalogue.services import SetLicensePlanAssignmentData, set_license_plan_assignment
    from selahcue_api.graphql.context import StaffPermission

    _org, _session, initial, licence = activate_free(client)
    expires = timezone.now() + timedelta(days=2)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=expires)
    DeviceToken.objects.update(expires_at=expires)
    replacement = Plan.objects.filter(is_fallback=False).first()
    staff = ActorContext(kind=ActorKind.STAFF, actor_id="fixture-staff",
                         staff_permissions=frozenset({StaffPermission.GRANT_ENTITLEMENT}))
    change = SetLicensePlanAssignmentData(
        idempotency_key="staff-reassignment-after-refresh", license_key_id=str(licence.pk),
        plan_code=replacement.code, reason="Test staff reassignment serialization.",
    )
    pids = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            assert post(client, REFRESH, {}, initial["activation_token"]).status_code == 200
            job = pool.submit(_isolated_job, pids, lambda: set_license_plan_assignment(staff, change))
            waiter = pids.get(timeout=5)
            query = _await_blocked_query(waiter, _backend_pid())
            assert query.startswith("UPDATE") and LicensePlanAssignment._meta.db_table in query
            assert not job.done()
        job.result(timeout=10)
    assert LicensePlanAssignment.objects.get(license_key=licence).plan_id == replacement.pk
