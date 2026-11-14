"""Managed Free issuance and renewal behaviour under PostgreSQL row locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from time import monotonic, sleep

import pytest
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.utils import timezone

from test_bound_activation import SESSION, admin_session, body, post
from test_bound_activation_postgres import parallel
from test_concurrency_postgres import _licence_row_waiters
from test_free_license_lifecycle import REFRESH, activate_free, self_service_org
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
    new_leaf = ("selahcue_license_keys", "0003_free_license_lifecycle")
    executor = MigrationExecutor(connection)
    executor.migrate([old_leaf])
    try:
        original = seed_license(seed_org(tag="pre-managed"))
        before = AppLicenseKey.objects.values().get(pk=original.pk)
    finally:
        MigrationExecutor(connection).migrate([new_leaf])
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
