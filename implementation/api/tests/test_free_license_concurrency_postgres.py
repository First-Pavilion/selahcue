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
from test_entitlement_manifest_slice import TEST_SEED_B64
from test_free_license_lifecycle import (
    MANIFEST, NOW, REFRESH, RENEWED_TO, activate_free, self_service_org,
)
from test_license_revoke_extend import _extend_over_http
from test_native_account_surface import seed_license, seed_org
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.devices.models import (
    Device, DeviceActivationOperation, DeviceToken, DeviceTokenStatus,
)
from selahcue_api.apps.license_keys import state_machine
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


def test_free_writer_refusal_rolls_back_and_leaves_one_denial(client, monkeypatch, settings):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org, _session, initial, licence = activate_free(client)
    bearer = initial["activation_token"]
    old_expiry = NOW + timedelta(days=2)
    AppLicenseKey.objects.filter(pk=licence.pk).update(
        status=LicenseKeyStatus.EXPIRING, expires_at=old_expiry,
    )
    DeviceToken.objects.filter(device__license_key=licence).update(expires_at=old_expiry)
    before_licence = AppLicenseKey.objects.values().get(pk=licence.pk)
    before_token = DeviceToken.objects.values().get(device__license_key=licence)
    receipt = DeviceActivationOperation.objects.values().get(license_key=licence)
    audit_before = set(AuditEvent.objects.values_list("pk", flat=True))

    # Exercise the actual writer refusal after the Free expiry save, including its inner audit.
    expiring = LicenseKeyStatus.EXPIRING
    monkeypatch.setitem(
        state_machine.LEGAL_TRANSITIONS, expiring,
        state_machine.LEGAL_TRANSITIONS[expiring] - {LicenseKeyStatus.ACTIVATED},
    )
    response = post(client, REFRESH, {}, bearer)

    assert AppLicenseKey.objects.values().get(pk=licence.pk) == before_licence
    assert DeviceToken.objects.values().get(device__license_key=licence) == before_token
    assert DeviceActivationOperation.objects.values().get(license_key=licence) == receipt
    assert Device.objects.filter(customer=org).count() == 1
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    denial = AuditEvent.objects.exclude(pk__in=audit_before).get()
    assert (denial.action, denial.result) == ("license_key.free_renewed", AuditResult.DENIED)
    assert denial.target_id == str(licence.pk)
    assert denial.after["code"] == "CONFLICT"
    assert client.get(MANIFEST, HTTP_AUTHORIZATION=f"Bearer {bearer}").status_code == 200


def test_frozen_clock_two_extensions_then_free_catchup_requires_replacement(
    client, monkeypatch, settings,
):
    settings.SELAHCUE_TRUST_ACTOR_HEADERS = True
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    org, _session, initial, licence = activate_free(client)
    bearer = initial["activation_token"]
    original = DeviceToken.objects.get(device__license_key=licence)
    receipt = DeviceActivationOperation.objects.values().get(license_key=licence)
    old_expiry = NOW + timedelta(days=2)
    AppLicenseKey.objects.filter(pk=licence.pk).update(expires_at=old_expiry)
    DeviceToken.objects.filter(pk=original.pk).update(expires_at=old_expiry)
    _extend_over_http(client, licence, "frozen-extension-one", NOW + timedelta(days=3))
    _extend_over_http(client, licence, "frozen-extension-two", NOW + timedelta(days=4))
    extensions = AuditEvent.objects.filter(action="license_key.extended", target_id=str(licence.pk))
    assert list(extensions.values_list("created_at", flat=True)) == [original.issued_at] * 2

    legacy = post(client, REFRESH, {}, bearer)
    assert legacy.status_code == 200
    assert legacy.json().get("activation_token") is None
    assert legacy.json()["license"]["expires_at"] == RENEWED_TO.isoformat()
    assert legacy.json()["token"]["expires_at"] == old_expiry.isoformat()
    original.refresh_from_db()
    assert original.expires_at == old_expiry
    assert original.status == DeviceTokenStatus.ACTIVE
    assert DeviceToken.objects.filter(device=original.device).count() == 1
    assert client.get(MANIFEST, HTTP_AUTHORIZATION=f"Bearer {bearer}").status_code == 200

    capable = {"token_rotation": "staff-extension-v1"}
    refreshed = post(client, REFRESH, capable, bearer)
    assert refreshed.status_code == 200
    payload = refreshed.json()
    replacement = payload.get("activation_token")
    replaced = bool(replacement) and replacement != bearer
    assert replaced
    assert refreshed["Cache-Control"] == "no-store"
    assert payload["device"]["device_public_id"] == initial["device"]["device_public_id"]
    assert payload["token"]["expires_at"] == RENEWED_TO.isoformat()
    assert post(client, REFRESH, capable, bearer).status_code == 401
    assert client.get(MANIFEST, HTTP_AUTHORIZATION=f"Bearer {bearer}").status_code == 401
    assert client.get(MANIFEST, HTTP_AUTHORIZATION=f"Bearer {replacement}").status_code == 200
    again = post(client, REFRESH, capable, replacement)
    assert again.status_code == 200
    assert again.json().get("activation_token") is None
    original.refresh_from_db()
    assert original.status == DeviceTokenStatus.REVOKED
    assert original.expires_at == old_expiry
    assert Device.objects.filter(customer=org).count() == 1
    tokens = DeviceToken.objects.filter(device=original.device)
    assert tokens.count() == 2
    assert tokens.get(status=DeviceTokenStatus.ACTIVE).expires_at == RENEWED_TO
    assert DeviceActivationOperation.objects.values().get(license_key=licence) == receipt
    assert AuditEvent.objects.filter(action="license_key.free_renewed", result=AuditResult.SUCCESS).count() == 1
    assert AuditEvent.objects.filter(action="device_token.reminted", result=AuditResult.SUCCESS).count() == 1
    assert not AuditEvent.objects.filter(action="device_token.free_validity_extended").exists()


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
